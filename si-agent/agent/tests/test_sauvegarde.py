# -*- coding: utf-8 -*-
"""#930 : sauvegarde des confs logicielles et des montages -- parties pures (catalogue, fusion, script de remontage,
script de capture, manifeste, constats). `cd si-agent/agent && python3 -m unittest tests.test_sauvegarde`."""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from si_agent import sauvegarde as sv  # noqa: E402


class Remontage(unittest.TestCase):
    MONT = {
        "lecteurs": [{"lettre": "Z:", "chemin": r"\\srv\partage", "utilisateur": "alice"}],
        "partages": [{"nom": "Data", "chemin": r"D:\Data", "acces": ["Tout le monde:Allow:Read", "ADMIN:Allow:Full"]}],
        "imprimantes": [{"nom": "HP couloir", "adresse": "192.0.2.50", "pilote": "HP Universal"}],
    }

    def test_script_remontage(self):
        s = sv.script_remontage(self.MONT)
        self.assertIn('net use Z: "\\\\srv\\partage" /persistent:yes', s)
        self.assertIn("New-SmbShare -Name 'Data' -Path 'D:\\Data'", s)
        self.assertIn("Grant-SmbShareAccess -Name 'Data' -AccountName 'Tout le monde' -AccessRight Read", s)
        self.assertIn("-AccountName 'ADMIN' -AccessRight Full", s)
        self.assertIn("imprimante: HP couloir", s)
        self.assertTrue(s.endswith("\r\n"))

    def test_script_remontage_vide(self):
        s = sv.script_remontage({})
        self.assertIn("Lecteurs reseau (0)", s)
        self.assertIn("@echo off", s)


class Capture(unittest.TestCase):
    def test_construire_script_capture(self):
        cibles = [{"app": "Thunderbird", "cles": [r"HKCU\Software\Mozilla"], "dossiers": [r"%APPDATA%\Thunderbird"]}]
        s = sv.construire_script_capture(cibles, r"C:\tmp\bk", r"C:\tmp\bk.zip",
                                         usb="E:\\sauvegardes", unc={"chemin": r"\\nas\backup", "avec_identifiants": True})
        self.assertIn("reg export 'HKCU\\Software\\Mozilla'", s)
        self.assertIn("ExpandEnvironmentVariables('%APPDATA%\\Thunderbird')", s)
        self.assertIn("Compress-Archive", s)
        self.assertIn("Get-FileHash", s)
        self.assertIn("type='usb'", s)
        self.assertIn("type='unc'", s)
        self.assertIn("$env:SI_BK_UNC_USER", s, "les identifiants UNC viennent de l'environnement, pas du script")
        self.assertNotIn("password", s.lower().replace("-password $env:si_bk_unc_pass", ""), "aucun mot de passe en clair")

    def test_sans_identifiants_unc(self):
        s = sv.construire_script_capture([], r"C:\t", r"C:\t.zip", unc={"chemin": r"\\nas\b", "avec_identifiants": False})
        self.assertNotIn("New-SmbMapping", s)
        self.assertIn("type='unc'", s)

    def test_extraire_json(self):
        sortie = "bla\nSI-BK-DEBUT\n{\"archive\": {\"nom\": \"bk.zip\"}, \"destinations\": [], \"erreurs\": []}\nSI-BK-FIN\nfin"
        d = sv.extraire_json(sortie)
        self.assertEqual(d["archive"]["nom"], "bk.zip")
        self.assertIsNone(sv.extraire_json("rien"))

    def test_constats(self):
        self.assertTrue(any(c["code"] == "sauvegarde-echec" for c in sv.constats({"archive": {}, "destinations": [], "erreurs": []})))
        r = {"archive": {"nom": "x.zip"}, "destinations": [{"type": "unc", "ok": False, "erreur": "refusé"}], "erreurs": ["reg KO"],
             "dossiers": [{"app": "OpenVPN", "absent": True}]}
        codes = {c["code"]: c for c in sv.constats(r)}
        self.assertIn("sauvegarde-destination", codes)
        self.assertEqual(codes["sauvegarde-destination"]["severity"], "critical")
        self.assertIn("sauvegarde-partiel", codes)
        self.assertEqual(codes["sauvegarde-dossier-absent"]["severity"], "info")

    def test_manifeste(self):
        m = sv.manifeste("pc-paul", [{"app": "A", "cles": ["k"], "dossiers": ["d"]}], {"lecteurs": [1, 2], "partages": [1]})
        self.assertEqual(m["agent"], "pc-paul")
        self.assertEqual(m["montages"], {"lecteurs": 2, "partages": 1, "imprimantes": 0})


class Restauration(unittest.TestCase):
    CIBLES = [{"app": "Thunderbird", "cles": ["HKCU\\Software\\Mozilla"], "dossiers": ["%APPDATA%\\Thunderbird"]},
              {"app": "PuTTY", "cles": ["HKCU\\Software\\SimonTatham"], "dossiers": []}]

    def test_slug_stable(self):
        self.assertEqual(sv.slug("Microsoft Office 365!"), "Microsoft_Office_365_")

    def test_simulation_lecture_seule(self):
        s = sv.construire_script_simulation("C:\\tmp\\arch")
        self.assertIn("simulation=$true", s)
        self.assertIn("manifeste.json", s)
        self.assertIn("SI-RST-DEBUT", s)
        for interdit in ("reg import", "robocopy", "Remove-Item", "New-SmbShare"):
            self.assertNotIn(interdit, s, "la simulation n'écrit rien (%s)" % interdit)

    def test_restauration_registre_repli_et_import(self):
        s = sv.construire_script_restauration(self.CIBLES, "C:\\tmp\\arch", "C:\\tmp\\rb", {"registre": True, "appdata": True, "montages": True})
        # repli (reg export de l'état courant) AVANT le réimport
        self.assertIn("reg export 'HKCU\\Software\\Mozilla' (Join-Path $rb", s)
        self.assertIn("reg import $f", s)
        self.assertIn("confs\\Thunderbird-1.reg", s)
        self.assertIn("appdata\\Thunderbird\\1", s)
        self.assertIn("robocopy $src $dst", s)
        self.assertIn("remonter.cmd", s)
        self.assertIn("SI-RST-DEBUT", s)

    def test_restauration_options(self):
        s = sv.construire_script_restauration(self.CIBLES, "C:\\a", "C:\\rb", {"registre": False, "appdata": False, "montages": False})
        self.assertNotIn("reg import", s)
        self.assertNotIn("robocopy", s)
        self.assertNotIn("cmd /c", s)

    def test_extraire_rst_et_constats(self):
        out = "x\nSI-RST-DEBUT\n{\"registre\":[{\"app\":\"A\",\"ok\":false}],\"dossiers\":[],\"montages\":null,\"erreurs\":[]}\nSI-RST-FIN"
        d = sv.extraire_json(out, "SI-RST-DEBUT", "SI-RST-FIN")
        self.assertEqual(d["registre"][0]["ok"], False)
        cs = {c["code"]: c for c in sv.constats_restauration(d)}
        self.assertEqual(cs["restauration-registre"]["severity"], "critical")


if __name__ == "__main__":
    unittest.main()
