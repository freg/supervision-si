# -*- coding: utf-8 -*-
"""#792 : sonde remote-status -- veilles distantes lues par ssh."""
import importlib.util
import os
import subprocess
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("remote_status", os.path.join(HERE, "..", "plugins", "remote-status", "remote_status.py"))
R = importlib.util.module_from_spec(spec)
spec.loader.exec_module(R)


class FauxSsh:
    def __init__(self, sortie=b"", code=0, err=b""):
        self.r = subprocess.CompletedProcess([], code, sortie, err)
        self.argv = None

    def __call__(self, argv, **kw):
        self.argv = argv
        return self.r


class RemoteStatusTest(unittest.TestCase):
    def test_cible(self):
        self.assertEqual(R.parse_cible("sms-nms=francois@192.0.2.20:/var/www/sms/veille-etat.txt"),
                         {"nom": "sms-nms", "compte": "francois", "hote": "192.0.2.20", "chemin": "/var/www/sms/veille-etat.txt"})
        self.assertIsNone(R.parse_cible("sans-egal"))
        self.assertIsNone(R.parse_cible("x=a@b:relatif"))

    def test_etat(self):
        now = time.mktime((2026, 10, 20, 10, 0, 0, 0, 0, -1))
        e = R.parse_etat("KO 2026-10-20 09:50:00 aucune confirmation\n", now)
        self.assertEqual((e["etat"], e["age_s"], e["detail"]), ("KO", 600, "aucune confirmation"))
        self.assertIsNone(R.parse_etat("n'importe quoi", now)["etat"])
        self.assertIsNone(R.parse_etat("", now)["etat"])

    def test_constats(self):
        now = time.mktime((2026, 10, 20, 10, 0, 0, 0, 0, -1))
        ok = R.collect(["--cible", "s=f@h:/e"], run=FauxSsh(b"OK 2026-10-20 09:55:00 envoye en 10 s\n"), maintenant=now)
        self.assertEqual(ok["alerts"], [])
        ko = R.collect(["--cible", "s=f@h:/e"], run=FauxSsh(b"KO 2026-10-20 09:55:00 modem\n"), maintenant=now)
        self.assertEqual([(a["code"], a["severity"]) for a in ko["alerts"]], [("remote-status-ko@s", "critical")])
        vieux = R.collect(["--cible", "s=f@h:/e", "--age-max", "1500"], run=FauxSsh(b"OK 2026-10-20 09:00:00 x\n"), maintenant=now)
        self.assertEqual([a["code"] for a in vieux["alerts"]], ["remote-status-stale@s"])
        f = FauxSsh(code=255, err=b"ssh: connect to host h port 22: Connection timed out\n")
        hs = R.collect(["--cible", "s=f@h:/e"], run=f, maintenant=now)
        self.assertEqual([a["code"] for a in hs["alerts"]], ["remote-status-unreachable@s"])
        self.assertIn("timed out", hs["alerts"][0]["message"])
        self.assertIn("f@h", f.argv)
        self.assertIn("cat /e", f.argv)

    def test_sans_cible(self):
        self.assertIn("aucune --cible", R.collect([], run=FauxSsh())["error"])


if __name__ == "__main__":
    unittest.main()


class ArgsLocauxTest(unittest.TestCase):
    def test_fichier(self):
        import tempfile
        p = os.path.join(tempfile.mkdtemp(), "args")
        with open(p, "w") as fh:
            fh.write("# veille du NMS\n--cible sms-nms=f@192.0.2.20:/e\n--age-max 1800\n\n")
        self.assertEqual(R.args_locaux([], p), ["--cible", "sms-nms=f@192.0.2.20:/e", "--age-max", "1800"])
        self.assertEqual(R.args_locaux(["--x"], p + ".absent"), ["--x"])
