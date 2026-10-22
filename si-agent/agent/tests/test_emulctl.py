# -*- coding: utf-8 -*-
"""#831 émulation : catalogue (Raspberry, Android), validation, scripts bash (syntaxe, vérifications), registre."""
import json
import os
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from si_agent import emulctl as E  # noqa: E402


class R(object):
    def __init__(self, rc, out="", err=""):
        self.returncode, self.stdout, self.stderr = rc, out, err


def bash_ok(s):
    r = subprocess.run(["bash", "-n", "-c", s], capture_output=True, text=True)
    return r.returncode == 0, r.stderr


class Emul(unittest.TestCase):
    def test_profils(self):
        x86 = {p["id"]: p for p in E.profils("x86_64")}
        self.assertTrue({"rpi3b", "rpi0w", "rpi02w"} <= set(x86))
        self.assertTrue(x86["android-34-x86_64"]["disponible"])
        self.assertFalse(x86["android-34-arm64-v8a"]["disponible"])
        self.assertNotIn("android-34-x86", x86)                      # plus d'image x86 32 bits après Android 11
        self.assertIn("android-30-x86", x86)
        arm = {p["id"]: p for p in E.profils("aarch64")}
        self.assertTrue(arm["android-34-arm64-v8a"]["disponible"])
        self.assertEqual(E.RASPBERRY["rpi0w"]["plateforme"], "linux/arm/v6")

    def test_valider(self):
        self.assertIn("action", E.valider({"action": "rm"})[1])
        self.assertIn("instance", E.valider({"action": "arreter", "instance": "../x"})[1])
        self.assertIn("profil", E.valider({"action": "preparer", "profil": "rpi5"})[1])
        self.assertIn("mode", E.valider({"action": "preparer", "profil": "rpi3b", "mode": "avd"})[1])
        self.assertIn("licences", E.valider({"action": "preparer", "profil": "android-34-x86_64"})[1])
        self.assertIn("hôte ARM", E.valider({"action": "preparer", "profil": "android-34-arm64-v8a", "accepter_licences": True}, "x86_64")[1])
        v, e = E.valider({"action": "lancer", "profil": "rpi0w", "mode": "systeme", "instance": "emu-rpi0w-1", "port": 52201})
        self.assertIsNone(e)
        self.assertIn("ligne", E.valider({"action": "deployer_agent", "instance": "emu-rpi3b-1", "ligne": "a\nb"})[1])

    def test_scripts(self):
        cas = [{"action": "preparer", "profil": p, "mode": m} for p in E.RASPBERRY for m in ("conteneur", "systeme")]
        cas += [{"action": "lancer", "profil": p, "mode": m, "instance": "emu-%s-1" % p, "port": 52201} for p in E.RASPBERRY for m in ("conteneur", "systeme")]
        cas += [{"action": "lancer", "profil": "android-34-x86_64", "instance": "emu-a34-1", "port": 5556, "accepter_licences": True},
                {"action": "arreter", "instance": "emu-a34-1"}, {"action": "detruire", "instance": "emu-a34-1"}, {"action": "lister"},
                {"action": "deployer_agent", "instance": "emu-rpi3b-1", "ligne": "curl -fsSL -k 'https://c:6445/deploy/linux?token=x' | sh"}]
        for c in cas:
            v, e = E.valider(c, "x86_64")
            self.assertIsNone(e, c)
            s = E.script(v)
            ok, err = bash_ok(s)
            self.assertTrue(ok, (c, err))
        s = E.script(E.valider(cas[0])[0])
        self.assertIn("sha256sum", s); self.assertIn("raspios_lite_arm64_latest", s); self.assertIn("tonistiigi/binfmt", s)
        s = E.script(E.valider({"action": "lancer", "profil": "rpi0w", "mode": "conteneur", "instance": "emu-z-1"})[0])
        self.assertIn("--platform linux/arm/v6", s); self.assertIn("QEMU_CPU=arm1176", s)
        s = E.script(E.valider({"action": "lancer", "profil": "rpi02w", "mode": "systeme", "instance": "emu-z2-1", "port": 52230})[0])
        self.assertIn("-M raspi3b", s); self.assertIn("bcm2710-rpi-zero-2-w.dtb", s); self.assertIn("hostfwd=tcp:127.0.0.1:52230-:22", s)
        s = E.script(E.valider({"action": "lancer", "profil": "android-30-x86", "instance": "emu-a30-1", "port": 5560, "accepter_licences": True})[0])
        self.assertIn("system-images;android-30;google_apis;x86", s); self.assertIn("-port 5560", s); self.assertIn("/dev/kvm", s)

    def test_liste_et_run(self):
        out = '{"id": "emu-rpi3b-1", "mode": "conteneur", "profil": "rpi3b"}\n{"id": "emu-a34-1", "mode": "avd", "etat": "demarre"}\nDOCKER {"Names": "emu-rpi3b-1", "State": "running", "Status": "Up 3 minutes"}\n'
        l = E.lire_liste(out)
        self.assertEqual([(x["id"], x["etat"]) for x in l], [("emu-a34-1", "demarre"), ("emu-rpi3b-1", "en_marche")])
        r = E.run(lambda argv, timeout: R(0, out), {"action": "lister"}, "x86_64")
        self.assertTrue(r["ok"]); self.assertEqual(len(r["result"]["instances"]), 2); self.assertTrue(r["result"]["profils"])
        r = E.run(lambda argv, timeout: R(1, "", "x\nERREUR : KVM absent : émulateur Android impossible\n"),
                  {"action": "preparer", "profil": "android-34-x86_64", "accepter_licences": True}, "x86_64")
        self.assertEqual(r["error"], "ERREUR : KVM absent : émulateur Android impossible")


class ExportApkEcran(unittest.TestCase):
    """#835 : image installable (carte SD), APK dans l'émulateur, écran dans le navigateur (noVNC)."""
    def test_validation(self):
        self.assertIsNone(E.valider({"action": "exporter_image", "instance": "emu-rpi0w-2"})[1])
        self.assertIsNone(E.valider({"action": "installer_apk", "instance": "emu-a34-x8664-1", "url": "https://f-droid.org/F-Droid.apk"})[1])
        self.assertIsNone(E.valider({"action": "installer_apk", "instance": "emu-a", "url": "https://exemple.org/telecharger?id=3", "sha256": "a" * 64})[1])
        for p in ({"action": "installer_apk", "instance": "emu-a", "url": "http://x/a.apk"}, {"action": "installer_apk", "instance": "emu-a", "fichier": "/etc/passwd"},
                  {"action": "installer_apk", "instance": "emu-a", "url": "https://x/a.apk$(id)"}, {"action": "supprimer_export", "nom": "../x.img.xz"},
                  {"action": "installer_apk", "instance": "emu-a", "url": "https://x/a.apk", "sha256": "zz"}):
            self.assertIsNotNone(E.valider(p)[1], p)

    def test_scripts(self):
        for p in ({"action": "exporter_image", "instance": "emu-rpi0w-2"}, {"action": "supprimer_export", "nom": "emu-rpi0w-2-20261022-2130.img.xz"},
                  {"action": "installer_apk", "instance": "emu-a", "fichier": E.RACINE + "/apk/app.apk", "sha256": "b" * 64},
                  {"action": "lancer", "profil": "rpi3b", "mode": "systeme", "instance": "emu-rpi3b-1", "port": 52201},
                  {"action": "lancer", "profil": "android-34-x86_64", "instance": "emu-a34-x8664-1", "port": 5556, "accepter_licences": True}):
            ok, err = bash_ok(E.script(E.valider(p)[0]))
            self.assertTrue(ok, (p, err))
        s = E.script(E.valider({"action": "exporter_image", "instance": "emu-rpi0w-2"})[0])
        for x in ("ssh_host_", "machine-id", "resize2fs -M", "xz -T0", "si-premier-demarrage.service", "emul:!:", "agent.json"):
            self.assertIn(x, s)
        self.assertNotIn("%%", s)
        r = subprocess.run(["sh", "-n"], input=E.PREMIER_DEMARRAGE, text=True, capture_output=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("MOT_DE_PASSE=", E.CONF_EXEMPLE)                       # seulement un hash, jamais le mot de passe en clair

    def test_ecran(self):
        self.assertEqual((E.ecran_ports("systeme", 52203), E.ecran_ports("avd", 5558), E.ecran_ports("conteneur", 0)), ((5903, 6903), (6002, 7002), (None, None)))
        s = E.script(E.valider({"action": "lancer", "profil": "rpi0w", "mode": "systeme", "instance": "emu-rpi0w-3", "port": 52203})[0])
        self.assertIn("-display vnc=127.0.0.1:3", s)
        self.assertIn("websockify -D --web /usr/share/novnc", s)
        s = E.script(E.valider({"action": "lancer", "profil": "android-34-x86_64", "instance": "emu-a", "port": 5558, "accepter_licences": True})[0])
        self.assertIn("Xvfb :102", s)
        self.assertIn("-rfbport 6002", s)
        self.assertNotIn("-no-window", s)


if __name__ == "__main__":
    unittest.main()
