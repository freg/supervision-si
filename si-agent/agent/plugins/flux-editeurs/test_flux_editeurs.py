# -*- coding: utf-8 -*-
import json, os, socket, sys, tempfile, threading, unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import flux_editeurs as F  # noqa: E402


class Hub(BaseHTTPRequestHandler):
    recu = []
    def log_message(self, *a): pass
    def do_GET(self):
        if self.path.endswith("/flux/listes/local.txt"):
            corps = ("# local\nt;127.0.0.1;tcp;%d,%d\nt;127.0.0.2;tcp;%d\nt;127.0.0.1;tcp;%d;ferme\nt;nexistepas.invalid;tcp;443\n" % (Hub.port_ok, Hub.port_ko, Hub.port_ok, Hub.port_ok)).encode()
            self.send_response(200); self.end_headers(); self.wfile.write(corps)
        else:
            self.send_response(404); self.end_headers()
    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0); Hub.recu.append((self.path, json.loads(self.rfile.read(n))))
        self.send_response(200); self.end_headers(); self.wfile.write(b'{"ok": true, "passage": 7, "alertes": {"ouvertes": 1}}')


class TestFluxEditeurs(unittest.TestCase):
    def test_liste_et_ports(self):
        self.assertEqual(F.ports("443,5228-5230,x,0"), [443, 5228, 5229, 5230])
        l = F.lire_liste("# c\ng;A.com;tcp;443\ng;b.com;udp;123\ng;c.com;tcp;22;ferme\nmauvais\ng;d.com;icmp;1\n")
        self.assertEqual([(x["hote"], x["attendu"]) for x in l], [("a.com", "ouvert"), ("b.com", "ouvert"), ("c.com", "ferme")])
        self.assertEqual(F.jours_avant("Jan  1 00:00:00 2030 GMT", 1893456000 - 86400 * 10), 10)
        self.assertIsNone(F.jours_avant("n'importe quoi"))

    def test_reclasser_bilan(self):
        L = [{"hote": "a", "proto": "tcp", "port": 1, "statut": "OK", "detail": "", "attendu": "ouvert"},
             {"hote": "b", "proto": "tcp", "port": 1, "statut": "KO", "detail": "x", "attendu": "ouvert"},
             {"hote": "c", "proto": "tcp", "port": 1, "statut": "KO", "detail": "x", "attendu": "ferme"}]
        self.assertEqual([l["statut"] for l in F.reclasser_ns(L)], ["OK", "NS", "KO"]); self.assertEqual(F.bilan(L), {"OK": 1, "NS": 1, "KO": 1})

    def test_bout_en_bout(self):
        ecoute = socket.socket(); ecoute.bind(("127.0.0.1", 0)); ecoute.listen(5)
        libre = socket.socket(); libre.bind(("127.0.0.1", 0)); Hub.port_ko = libre.getsockname()[1]; libre.close()
        Hub.port_ok = ecoute.getsockname()[1]
        srv = HTTPServer(("127.0.0.1", 0), Hub); threading.Thread(target=srv.serve_forever, daemon=True).start()
        hub = "http://127.0.0.1:%d" % srv.server_address[1]
        F.interfaces = lambda choix: [{"iface": "lo", "ip": "127.0.0.1", "defaut": True, "gw": None}]
        F.ip_publique = lambda src, t: None
        cache = tempfile.mkdtemp()
        r = F.collect(hub, "campus", ["local"], ["auto"], "poste", 2, cache, False)
        self.assertEqual(r["passages"][0]["hub"]["passage"], 7)
        path, corps = Hub.recu[-1]
        self.assertEqual((path, corps["source"], corps["iface"]), ("/sites/campus/flux/resultats", "poste-lo", "lo"))
        st = {(l["hote"], l["port"], l["attendu"]): l["statut"] for l in corps["resultats"]}
        self.assertEqual(st[("127.0.0.1", Hub.port_ok, "ouvert")], "OK"); self.assertEqual(st[("127.0.0.1", Hub.port_ko, "ouvert")], "KO")
        self.assertEqual(st[("127.0.0.1", Hub.port_ok, "ferme")], "OUVERT"); self.assertEqual(st[("nexistepas.invalid", 443, "ouvert")], "KO")
        self.assertEqual(r["alerts"], [])                                             # alertes tenues par le hub par défaut
        r = F.collect(hub, "campus", ["local"], ["auto"], "poste", 2, cache, True)
        self.assertTrue(any(a["code"].startswith("flux-lo-") for a in r["alerts"]))
        srv.shutdown()                                                                # hub injoignable : copie locale de la liste
        r = F.collect(hub, "campus", ["local"], ["auto"], "poste", 1, cache, False)
        self.assertIn("copie locale", " ".join(r["erreurs"])); self.assertIn("flux-hub-injoignable", [a["code"] for a in r["alerts"]])
        self.assertIn("réglages manquants", F.collect("", "", ["google"], ["auto"], "p", 1, cache, False)["error"])
        ecoute.close()


class TestReglages(unittest.TestCase):
    def test_reglages(self):
        self.assertEqual(F.hub_depuis_central("https://sup.exemple.fr/api/si-agent/"), "https://sup.exemple.fr/api/nebula")
        self.assertEqual(F.hub_depuis_central("https://10.0.0.1:6443/autre"), "https://10.0.0.1:6443/api/nebula")
        self.assertEqual(F.hub_depuis_central(""), "")
        d = tempfile.mkdtemp(); conf = os.path.join(d, "c.json")
        env = {"SI_AGENT_CENTRAL": "https://h/api/si-agent", "SI_AGENT_SITE": "numeria"}
        r = F.reglages({"hub": "", "site": "", "listes": None, "ifaces": None}, env, conf)
        self.assertEqual((r["hub"], r["site"], r["listes"], r["ifaces"], r["origine"]), ("https://h/api/nebula", "numeria", ["google"], ["auto"], "agent"))
        json.dump({"site": "68d4", "listes": "google,idruide"}, open(conf, "w"))
        r = F.reglages({"hub": "", "site": "", "listes": None, "ifaces": ["eth0"]}, env, conf)
        self.assertEqual((r["site"], r["listes"], r["ifaces"], r["origine"]), ("68d4", ["google", "idruide"], ["eth0"], "fichier"))

    def test_resoudre_site(self):
        class H(BaseHTTPRequestHandler):
            def log_message(self, *a): pass
            def do_GET(self):
                self.send_response(200); self.end_headers()
                self.wfile.write(json.dumps({"sites": [{"site_id": "68d4", "nom": "Pavillon ASTRA FUTUROSCOPE"}, {"site_id": "si-optline", "nom": "SI Optline"}]}).encode())
        srv = HTTPServer(("127.0.0.1", 0), H); threading.Thread(target=srv.serve_forever, daemon=True).start()
        hub = "http://127.0.0.1:%d" % srv.server_address[1]
        self.assertEqual(F.resoudre_site(hub, "68d4")[0], "68d4"); self.assertEqual(F.resoudre_site(hub, "si optline")[0], "si-optline")
        self.assertEqual(F.resoudre_site(hub, "ASTRA")[0], "68d4"); self.assertEqual(F.resoudre_site(hub, "Bureau Paris"), ("Bureau-Paris", None))
        srv.shutdown()


if __name__ == "__main__":
    unittest.main()
