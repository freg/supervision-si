# -*- coding: utf-8 -*-
"""#792 : sonde sms-gateway -- envoi de test par le relais du TRB140 et état du modem."""
import importlib.util
import json
import os
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("sms_gateway", os.path.join(HERE, "..", "plugins", "sms-gateway", "sms_gateway.py"))
G = importlib.util.module_from_spec(spec)
spec.loader.exec_module(G)


class Faux:
    def __init__(self, reponses):
        self.reponses, self.urls = reponses, []

    def __call__(self, url, data=None, headers=None, timeout=40):
        self.urls.append(url)
        for motif, rep in self.reponses:
            if motif in url:
                if isinstance(rep, Exception):
                    raise rep
                return rep
        return 404, ""


class SmsGatewayTest(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        for n, v in (("cle", "K"), ("mdp", "M")):
            with open(os.path.join(self.d, n), "w") as fh:
                fh.write(v + "\n")
        self.base = ["--relais", "http://r:8090", "--numero", "+33600000000", "--cle-fichier", os.path.join(self.d, "cle")]

    def test_envoi_ok_et_modem_4g(self):
        st = {"data": [{"operator": "Free", "conntype": "LTE", "netstate": "Registered (home)", "rssi": -71}]}
        f = Faux([("/send?", (200, "ok")), ("/api/login", (200, json.dumps({"data": {"token": "T"}}))), ("/api/modems/status", (200, json.dumps(st)))])
        r = G.collect(self.base + ["--trb", "https://t", "--trb-compte", "u", "--trb-mdp-fichier", os.path.join(self.d, "mdp")], http=f)
        self.assertEqual(r["alerts"], [])
        self.assertTrue(r["envoi"]["ok"])
        self.assertEqual((r["modem"]["operateur"], r["modem"]["reseau"], r["modem"]["signal_dbm"]), ("Free", "LTE", -71))
        self.assertIn("key=K", f.urls[0])

    def test_envoi_refuse_et_2g(self):
        st = {"data": [{"conntype": "GSM", "netstate": "Not registered", "rssi": "-105"}]}
        f = Faux([("/send?", (502, "erreur TRB140")), ("/api/login", (200, json.dumps({"data": {"token": "T"}}))), ("/api/modems/status", (200, json.dumps(st)))])
        r = G.collect(self.base + ["--trb", "https://t", "--trb-mdp-fichier", os.path.join(self.d, "mdp")], http=f)
        self.assertEqual(sorted(a["code"] for a in r["alerts"]),
                         ["sms-gateway-fallback", "sms-gateway-send", "sms-gateway-signal", "sms-gateway-unregistered"])
        self.assertEqual([a["severity"] for a in r["alerts"] if a["code"] == "sms-gateway-send"], ["critical"])

    def test_relais_injoignable(self):
        r = G.collect(self.base, http=Faux([("/send?", OSError("connexion refusée"))]))
        self.assertEqual([a["code"] for a in r["alerts"]], ["sms-gateway-send"])
        self.assertIn("injoignable", r["alerts"][0]["message"])

    def test_login_trb_refuse(self):
        r = G.collect(self.base + ["--trb", "https://t", "--trb-mdp-fichier", os.path.join(self.d, "mdp")],
                      http=Faux([("/send?", (200, "ok")), ("/api/login", (401, "{}"))]))
        self.assertEqual([a["code"] for a in r["alerts"]], ["sms-gateway-modem-api"])

    def test_sans_parametres(self):
        self.assertIn("--relais", G.collect([], http=Faux([]))["error"])


if __name__ == "__main__":
    unittest.main()
