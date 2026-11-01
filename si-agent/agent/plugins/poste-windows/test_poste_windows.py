# -*- coding: utf-8 -*-
"""Tests #896 : analyse du relevé d'un poste Windows (valeurs fictives, structure de collecte.ps1)."""
import json
import os
import sys
import types
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import poste_windows as pw  # noqa: E402

RAW = {
    "jours": 30, "nom": "PC-EXEMPLE", "systeme": "Microsoft Windows 11 Professionnel", "version": "10.0.22631",
    "profils": [{"sid": "S-1-5-21-1-1001", "chemin": "C:\\Users\\alice", "utilisateur": "alice", "charge": True},
                {"sid": "S-1-5-21-1-1002", "chemin": "C:\\Users\\bob", "utilisateur": "bob", "charge": False}],
    "partages": [{"nom": "Scans", "chemin": "D:\\Scans", "acces": ["Tout le monde:Allow:Read"]}],
    "lecteurs": [{"utilisateur": "alice", "lettre": "Z:", "chemin": "\\\\nas-exemple\\Commun", "compte": ""}],
    "imprimantes": [{"nom": "Copieur", "pilote": "PCL6", "port": "IP_192.0.2.50", "adresse": "192.0.2.50", "partagee": False}],
    "office": {"produits": "O365BusinessRetail", "version": "16.0.17928.20156", "canal": "Current"},
    "identites_office": [{"utilisateur": "alice", "courriel": "alice@exemple.fr"}],
    "thunderbird": [{"utilisateur": "alice", "profil": "C:\\Users\\alice\\AppData\\Roaming\\Thunderbird\\Profiles\\x.default", "prefs": [
        'user_pref("mail.server.server1.hostname", "imap.exemple.fr");', 'user_pref("mail.server.server1.type", "imap");',
        'user_pref("mail.server.server1.userName", "alice@exemple.fr");', 'user_pref("mail.server.server1.socketType", 3);',
        'user_pref("mail.server.server1.port", 993);', 'user_pref("mail.server.server2.hostname", "Local Folders");',
        'user_pref("mail.server.server2.type", "none");', 'user_pref("mail.identity.id1.useremail", "alice@exemple.fr");',
        'user_pref("mail.smtpserver.smtp1.hostname", "smtp.exemple.fr");', 'user_pref("mail.smtpserver.smtp1.port", 465);',
        'user_pref("calendar.registry.abc.name", "Agenda Google");', 'user_pref("calendar.registry.abc.type", "caldav");',
        'user_pref("calendar.registry.abc.uri", "https://apidata.googleusercontent.com/caldav/v2/alice%40exemple.fr/events/");',
        'user_pref("calendar.registry.loc.name", "Personnel");', 'user_pref("calendar.registry.loc.type", "storage");',
        'user_pref("calendar.registry.loc.uri", "moz-storage-calendar://");']}],
    "licences": [{"nom": "Windows(R), Professional edition", "etat": 1, "cle_partielle": "ABCDE"},
                 {"nom": "Office 16, Office16O365BusinessR_Subscription", "etat": 1, "cle_partielle": "FGHIJ"}],
    "antivirus": [{"nom": "Bitdefender Endpoint Security Tools", "etat": 266240}, {"nom": "Windows Defender", "etat": 393472}],
    "logiciels": [{"nom": "Mozilla Thunderbird (x64 fr)", "version": "128.3.0", "portee": "machine"},
                  {"nom": "Mozilla Thunderbird (x64 fr)", "version": "128.3.0", "portee": "machine"},
                  {"nom": "Autodesk AutoCAD LT 2024", "version": "24.3", "portee": "machine"}],
    "critiques": [{"t": "2026-10-20T08:00:00Z", "source": "Microsoft-Windows-Kernel-Power", "id": 41},
                  {"t": "2026-10-22T09:00:00Z", "source": "Microsoft-Windows-Kernel-Power", "id": 41},
                  {"t": "2026-10-22T09:00:05Z", "source": "Microsoft-Windows-WHEA-Logger", "id": 47},
                  {"t": "2026-10-23T10:00:00Z", "source": "Display", "id": 4101}],
    "plantages": [{"t": "2026-10-2%dT10:00:00Z" % i, "type": "plantage", "application": "acad.exe", "module": "nvwgf2umx.dll"} for i in range(3)],
    "vidages": [], "disques": [{"modele": "Samsung SSD 870", "sante": "Healthy", "usure": 3, "temperature": 41, "erreurs_lecture_non_corrigees": 0}],
    "volumes": [{"lettre": "C:", "octets": 500e9, "libre": 30e9}], "stabilite": [{"t": "2026-10-28T00:00:00Z", "indice": 3.2}],
}


class Poste(unittest.TestCase):
    def setUp(self):
        self.r = pw.analyse(json.loads(json.dumps(RAW)))

    def test_thunderbird(self):
        t = self.r["reinstallation"]["thunderbird"][0]
        self.assertEqual(t["comptes"], [{"type": "imap", "serveur": "imap.exemple.fr", "port": 993, "utilisateur": "alice@exemple.fr", "nom": None, "securite": "SSL/TLS"}])
        self.assertEqual(t["identites"], ["alice@exemple.fr"])
        self.assertEqual(t["envoi"][0]["serveur"], "smtp.exemple.fr")
        self.assertEqual({a["nom"]: a["nature"] for a in t["agendas"]}, {"Agenda Google": "Google", "Personnel": "local"})

    def test_reinstallation(self):
        r = self.r["reinstallation"]
        self.assertEqual(len(r["logiciels"]), 2)                       # doublon retiré
        self.assertEqual(r["profils_non_lus"], ["bob"])
        av = {a["nom"]: (a["actif"], a["a_jour"]) for a in r["antivirus"]}
        self.assertEqual(av["Bitdefender Endpoint Security Tools"], (True, True))     # 0x041000
        self.assertEqual(av["Windows Defender"], (False, True))                       # 0x060100 : passif

    def test_diagnostic(self):
        codes = {a["code"]: a["severity"] for a in self.r["alerts"]}
        self.assertEqual(codes["poste-materiel"], "critical")
        self.assertEqual(codes["poste-arrets-brutaux"], "warning")
        self.assertNotIn("poste-pilote-graphique", codes)              # une seule relance : sous le seuil
        self.assertIn("poste-plantages@acad.exe", codes)
        self.assertIn("poste-volume-plein@C:", codes)
        self.assertIn("poste-stabilite", codes)
        self.assertIn("poste-antivirus-inactif@Windows Defender", codes)
        self.assertEqual(self.r["diagnostic"]["plantages"][0]["modules"], ["nvwgf2umx.dll"])
        self.assertEqual(self.r["diagnostic"]["categories"]["arret_brutal"], 2)

    def test_disques_evenements_938(self):
        """#938 : les évènements disque sont rattachés au disque visé (numéro Windows), interne / externe d'après le bus."""
        raw = dict(RAW, disques=[{"numero": 0, "modele": "NVMe PC801", "bus": "NVMe", "sante": "Healthy", "volumes": ["C:"]},
                                 {"numero": 1, "modele": "Seagate Expansion", "bus": "USB", "sante": "Healthy", "volumes": ["E:"]}],
                   critiques=RAW["critiques"] + [
                       {"t": "2026-10-24T10:00:00Z", "source": "disk", "id": 153, "message": "The IO operation at logical block address 0x1 for Disk 1 (PDO name: \\Device\\00000041) was retried."},
                       {"t": "2026-10-24T10:01:00Z", "source": "disk", "id": 51, "message": "Une erreur a été détectée sur le périphérique \\Device\\Harddisk1\\DR1 pendant une opération de pagination."},
                       {"t": "2026-10-25T10:00:00Z", "source": "disk", "id": 11, "message": "Le pilote a détecté une erreur de contrôleur sur \\Device\\Harddisk0\\DR0."},
                       {"t": "2026-10-25T11:00:00Z", "source": "stornvme", "id": 129, "message": "Réinitialisation sur Périphérique, \\Device\\RaidPort1, a été émise."}])
        r = pw.analyse(json.loads(json.dumps(raw)))
        de = r["diagnostic"]["disques_evenements"]
        self.assertEqual([g["numero"] for g in de], [1, 0, None], "le plus touché d'abord ; les réinitialisations de contrôleur sans numéro à part")
        self.assertEqual((de[0]["modele"], de[0]["bus"], de[0]["externe"], de[0]["volumes"], de[0]["nombre"]), ("Seagate Expansion", "USB", True, ["E:"], 2))
        self.assertEqual(de[0]["ids"], [("disk 153", 1), ("disk 51", 1)])
        self.assertEqual((de[1]["externe"], de[1]["resolu"]), (False, True))
        self.assertEqual((de[2]["modele"], de[2]["resolu"]), (None, True))
        self.assertTrue(r["diagnostic"]["disques"][1]["externe"] and not r["diagnostic"]["disques"][0]["externe"])
        self.assertEqual(r["diagnostic"]["categories"]["disque"], 4)
        # disque cité mais inconnu de Get-PhysicalDisk (clé débranchée depuis) : non résolu
        de2 = pw.disques_evenements([{"categorie": "disque", "source": "disk", "id": 7, "message": "\\Device\\Harddisk3\\DR3 bloc défectueux", "t": "t"}], [])
        self.assertEqual((de2[0]["numero"], de2[0]["resolu"], de2[0]["externe"]), (3, False, None))
        self.assertIsNone(pw.disque_de_message("Disk1 sans espace ni Harddisk"))

    def test_main(self):
        self.assertEqual(pw.main([], plateforme="linux")["alerts"][0]["code"], "poste-windows-plateforme")
        sortie = ("\ufeff" + json.dumps(RAW, ensure_ascii=False)).encode("utf-8")
        out = pw.main([], runner=lambda *a, **k: types.SimpleNamespace(stdout=sortie, stderr=b"", returncode=0), plateforme="win32")
        self.assertEqual(out["poste"]["nom"], "PC-EXEMPLE")
        out = pw.main([], runner=lambda *a, **k: types.SimpleNamespace(stdout=b"", stderr=b"Acces refuse", returncode=1), plateforme="win32")
        self.assertEqual(out["alerts"][0]["code"], "poste-windows-collecte")


class Robustesse923(unittest.TestCase):
    def test_lignes_prefs_en_objets_powershell_51(self):
        # forme réelle relevée sur un poste (pc-paul) : chaque ligne de prefs.js est un objet, pas un texte
        ligne = {"value": 'user_pref("mail.server.server1.hostname", "imap.exemple.fr");', "PSPath": "C:\\x\\prefs.js", "ReadCount": 12}
        typ = {"value": 'user_pref("mail.server.server1.type", "imap");', "ReadCount": 13}
        tb = pw.thunderbird([{"utilisateur": "alice", "profil": "x", "prefs": [ligne, typ]}])
        self.assertEqual(tb[0]["comptes"][0]["serveur"], "imap.exemple.fr")

    def test_erreur_et_delai_deviennent_des_constats(self):
        def casse(*a, **k):
            raise TypeError("'>' not supported between instances of 'NoneType' and 'int'")
        r = pw.executer([], runner=casse, plateforme="win32")
        self.assertEqual(r["alerts"][0]["code"], "poste-windows-sonde")
        self.assertIn("TypeError", r["alerts"][0]["message"])
        self.assertIn("ligne", r["alerts"][0]["message"])
        def lent(*a, **k):
            raise pw.subprocess.TimeoutExpired("powershell", 540)
        self.assertEqual(pw.executer([], runner=lent, plateforme="win32")["alerts"][0]["code"], "poste-windows-delai")


if __name__ == "__main__":
    unittest.main()


class V5Tests(unittest.TestCase):
    """#943 : évènements NTFS par volume, processus gourmands, gpu / cartes transmis."""

    def test_fichiers_memoire_gpu(self):
        raw = dict(RAW, volumes=[{"lettre": "C:", "disque": 0, "octets": 1, "libre": 1}, {"lettre": "E:", "disque": 1, "octets": 1, "libre": 1}],
                   gpu=[{"nom": "NVIDIA GeForce RTX 4060", "pilote": "31.0.15.3623", "date_pilote": "2023-07-01T00:00:00Z"}],
                   cartes=[{"nom": "Wi-Fi", "description": "Killer(R) Wi-Fi 6E AX1675i", "pilote": "3.1.0.300", "date_pilote": "2023-01-10T00:00:00Z"}],
                   critiques=RAW["critiques"] + [
                       {"t": "2026-10-26T10:00:00Z", "source": "Ntfs", "id": 55, "message": "La structure du système de fichiers sur le volume E: a été endommagée."},
                       {"t": "2026-10-27T10:00:00Z", "source": "Ntfs", "id": 98, "message": "Volume E: (\\Device\\HarddiskVolume5) requiert une vérification."},
                       {"t": "2026-10-27T11:00:00Z", "source": "Ntfs", "id": 140, "message": "Échec d'écriture sur \\Device\\HarddiskVolume3."},
                       {"t": "2026-10-28T10:00:00Z", "source": "Microsoft-Windows-Resource-Exhaustion-Detector", "id": 2004,
                        "message": "Windows a diagnostiqué une insuffisance de mémoire virtuelle. Les programmes suivants ont consommé le plus de mémoire virtuelle : chrome.exe (4321) a consommé 3 210 Mo, acad.exe (555) a consommé 2 100 Mo, chrome.exe (4322) a consommé 900 Mo."}])
        r = pw.analyse(json.loads(json.dumps(raw)))
        fe = r["diagnostic"]["fichiers_evenements"]
        self.assertEqual([(g["volume"], g["nombre"], g["disque"]) for g in fe], [("E:", 2, 1), ("HarddiskVolume3", 1, None)])
        self.assertEqual(fe[0]["ids"][0][0] in ("Ntfs 55", "Ntfs 98"), True)
        pm = r["diagnostic"]["processus_memoire"]
        self.assertEqual([(x["processus"], x["mo"], x["fois"]) for x in pm], [("chrome.exe", 3210.0, 2), ("acad.exe", 2100.0, 1)])
        self.assertEqual(r["diagnostic"]["gpu"][0]["nom"], "NVIDIA GeForce RTX 4060")
        self.assertEqual(r["diagnostic"]["cartes"][0]["description"], "Killer(R) Wi-Fi 6E AX1675i")
        self.assertEqual(r["diagnostic"]["categories"]["fichiers"], 3)
        self.assertEqual(pw.volume_de_message("rien"), None)
        self.assertEqual(pw.volume_de_message("The file system structure on volume C: is corrupt"), "C:")
