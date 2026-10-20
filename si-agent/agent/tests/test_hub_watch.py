# -*- coding: utf-8 -*-
"""#793 : sonde hub-watch -- garde du hub depuis un autre hôte, alerte hors hub."""
import importlib.util
import os
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("hub_watch", os.path.join(HERE, "..", "plugins", "hub-watch", "hub_watch.py"))
H = importlib.util.module_from_spec(spec)
spec.loader.exec_module(H)


class HubWatchTest(unittest.TestCase):
    def setUp(self):
        d = tempfile.mkdtemp()
        self.etat = os.path.join(d, "etat.json")
        self.url_sms = os.path.join(d, "sms")
        with open(self.url_sms, "w") as fh:
            fh.write("http://passerelle/cgi-bin/sms_send?number={numero}&text={texte}\n")
        self.mails, self.smss = [], []
        self.argv = ["--url", "hub=https://h:6443/", "--courriel", "support@example.org", "--echecs", "2",
                     "--sms-url-fichier", self.url_sms, "--numero", "+33600000000"]

    def passe(self, ok, t):
        return H.collect(self.argv, tester=lambda u: (ok, "HTTP 200" if ok else "injoignable : timed out"),
                         envoyer_courriel=lambda *a: (self.mails.append(a[2]) or (True, "ok")),
                         envoyer_sms=lambda m, n, x: (self.smss.append((m, n, x)) or (True, "HTTP 200")),
                         etat_chemin=self.etat, maintenant=t)

    def test_cycle(self):
        self.assertEqual(self.passe(True, 1000)["alerts"], [])
        r = self.passe(False, 1120)                         # 1er échec : pas encore d'alerte (micro-coupure)
        self.assertEqual((self.mails, r["alerts"][0]["severity"]), ([], "warning"))
        r = self.passe(False, 1240)                         # 2e échec : alerte courriel + SMS
        self.assertTrue(r["panne"])
        self.assertEqual(len(self.mails), 1)
        self.assertIn("[ALERTE]", self.mails[0])
        self.assertEqual(self.smss[0][1], "+33600000000")
        self.passe(False, 1360)                             # pas de rappel avant 1 h
        self.assertEqual(len(self.mails), 1)
        self.passe(False, 1240 + 3600)
        self.assertIn("[RAPPEL]", self.mails[-1])
        self.passe(True, 1240 + 3700)
        self.assertIn("[RETABLI]", self.mails[-1])
        self.assertEqual(len(self.mails), 3)

    def test_envoi_impossible_signale(self):
        r = H.collect(self.argv, tester=lambda u: (False, "HTTP 502"), envoyer_courriel=lambda *a: (False, "pas de sendmail"),
                      envoyer_sms=lambda *a: (False, "refusé"), etat_chemin=self.etat, maintenant=10)
        r = H.collect(self.argv, tester=lambda u: (False, "HTTP 502"), envoyer_courriel=lambda *a: (False, "pas de sendmail"),
                      envoyer_sms=lambda *a: (False, "refusé"), etat_chemin=self.etat, maintenant=130)
        self.assertIn("hub-watch-alert-failed", [a["code"] for a in r["alerts"]])

    def test_sans_url(self):
        self.assertIn("--url", H.collect([], etat_chemin=self.etat)["error"])


if __name__ == "__main__":
    unittest.main()


class SmsTrbTest(unittest.TestCase):
    def test_login_puis_envoi(self):
        import json
        appels = []

        def faux(url, corps, jeton=None):
            appels.append((url, corps, jeton))
            if url.endswith("/api/login"):
                return 200, json.dumps({"data": {"token": "T"}})
            return 200, '{"data":{"sms_used":1},"success":true}'
        ok, d = H.sms_trb("https://t", "freg", "M", "3-1", "+33600000000", "ALERTE hub", http=faux)
        self.assertTrue(ok)
        self.assertEqual(appels[1][1], {"data": {"number": "+33600000000", "message": "ALERTE hub", "modem": "3-1"}})
        self.assertEqual(appels[1][2], "T")

    def test_login_refuse(self):
        ok, d = H.sms_trb("https://t", "freg", "faux", "3-1", "+336", "x", http=lambda u, c, j=None: (401, "{}"))
        self.assertFalse(ok)
        self.assertIn("refusée", d)

    def test_collect_utilise_trb(self):
        d = tempfile.mkdtemp()
        mdp = os.path.join(d, "mdp")
        open(mdp, "w").write("M\n")
        envois = []
        argv = ["--url", "hub=https://h/", "--echecs", "1", "--trb", "https://t", "--trb-compte", "freg", "--trb-mdp-fichier", mdp,
                "--trb-modem", "3-1", "--numero", "+336"]
        r = H.collect(argv, tester=lambda u: (False, "HTTP 502"), envoyer_courriel=lambda *a: (True, "ok"),
                      envoyer_sms_trb=lambda *a: (envois.append(a) or (True, "ok")), etat_chemin=os.path.join(d, "e"), maintenant=5)
        self.assertEqual(envois[0][:5], ("https://t", "freg", "M", "3-1", "+336"))
        self.assertEqual([e[0] for e in r["envois"]], ["sms"])
