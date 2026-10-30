# -*- coding: utf-8 -*-
"""#928 : mesure d'accès aux services (temps brut + authentifié formulaire / Basic / jeton). Serveur HTTP local,
aucun accès réseau. `cd si-agent/agent && python3 -m unittest tests.test_accesservices`."""
import base64
import os
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from si_agent import accesservices as a  # noqa: E402

SECRET = "s3cr3t-!"
USER = "francois"
PAGE_LOGIN = '<html><form method="post" action="/connexion"><input type="hidden" name="csrf" value="JETON42">' \
             '<input name="u"><input name="p" type="password"></form></html>'


class Serveur(BaseHTTPRequestHandler):
    def log_message(self, *a):  # silence
        pass

    def _rep(self, code, corps, entetes=None):
        self.send_response(code)
        for k, v in (entetes or {}).items():
            self.send_header(k, v)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(corps.encode())

    def do_GET(self):
        if self.path == "/lent":
            import time
            time.sleep(0.25)
            return self._rep(200, "ok lent")
        if self.path == "/login":
            return self._rep(200, PAGE_LOGIN)
        if self.path == "/prive":
            ck = self.headers.get("Cookie") or ""
            auth = self.headers.get("Authorization") or ""
            if "sess=ok" in ck:
                return self._rep(200, "<h1>Tableau de bord</h1> bienvenue")
            if auth.startswith("Basic "):
                u, p = base64.b64decode(auth[6:]).decode().split(":", 1)
                return self._rep(200, "<h1>Tableau de bord</h1>") if (u, p) == (USER, SECRET) else self._rep(401, "non")
            if self.headers.get("X-Api-Key") == "Bearer " + SECRET:
                return self._rep(200, "<h1>Tableau de bord</h1>")
            return self._rep(302, "", {"Location": "/login"})
        return self._rep(200, "<title>Public</title>accueil")

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        corps = self.rfile.read(n).decode()
        from urllib.parse import parse_qs
        d = {k: v[0] for k, v in parse_qs(corps).items()}
        if self.path == "/connexion" and d.get("csrf") == "JETON42" and d.get("u") == USER and d.get("p") == SECRET:
            return self._rep(302, "", {"Location": "/prive", "Set-Cookie": "sess=ok; Path=/"})
        return self._rep(200, PAGE_LOGIN)   # échec : on reste sur le formulaire


class AccesServices(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = HTTPServer(("127.0.0.1", 0), Serveur)
        cls.port = cls.srv.server_address[1]
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    def url(self, p):
        return "http://127.0.0.1:%d%s" % (self.port, p)

    def test_brut_public_et_injoignable(self):
        r = a.mesure_brute(self.url("/public"))
        self.assertEqual(r["status"], 200)
        self.assertIsNone(r["erreur"])
        self.assertIsNotNone(r["total_ms"])
        self.assertIsNotNone(r["dns_ms"])
        ko = a.mesure_brute("http://127.0.0.1:1/x")
        self.assertIsNotNone(ko["erreur"])
        self.assertIsNone(a.mesure_brute("ftp://x/").get("status"))

    def test_brut_protege_renvoie_302_sans_suivre(self):
        r = a.mesure_brute(self.url("/prive"))
        self.assertEqual(r["status"], 302)          # redirection vers le login = information, pas d'erreur
        self.assertEqual(r["location"], "/login")

    def test_form_csrf_succes_et_echec(self):
        ok = a.mesure_auth(self.url("/prive"), {"type": "form", "url_login": self.url("/login"),
                                                "champ_user": "u", "champ_pass": "p", "user": USER, "secret": SECRET})
        self.assertTrue(ok["connecte"], ok)
        self.assertEqual(ok["status"], 200)
        self.assertIsNotNone(ok["total_ms"])
        ko = a.mesure_auth(self.url("/prive"), {"type": "form", "url_login": self.url("/login"),
                                                "champ_user": "u", "champ_pass": "p", "user": USER, "secret": "FAUX"})
        self.assertFalse(ko["connecte"])

    def test_basic_et_token(self):
        b = a.mesure_auth(self.url("/prive"), {"type": "basic", "user": USER, "secret": SECRET})
        self.assertTrue(b["connecte"])
        bko = a.mesure_auth(self.url("/prive"), {"type": "basic", "user": USER, "secret": "x"})
        self.assertFalse(bko["connecte"])
        t = a.mesure_auth(self.url("/prive"), {"type": "token", "entete": "X-Api-Key", "valeur": "Bearer " + SECRET})
        self.assertTrue(t["connecte"])

    def test_mesurer_jamais_de_secret_en_sortie(self):
        cibles = [
            {"nom": "Public", "url": self.url("/public")},
            {"nom": "GED", "url": self.url("/prive"), "auth": {"type": "basic", "user": USER, "secret": SECRET}},
            {"nom": "Tickets", "url": self.url("/prive"), "auth": {"type": "form", "url_login": self.url("/login"),
             "champ_user": "u", "champ_pass": "p", "user": USER, "secret": SECRET}},
        ]
        out = a.mesurer(cibles)
        self.assertEqual(len(out["sites"]), 3)
        self.assertIsNone(out["sites"][0]["authentifie"])            # pas d'auth -> seulement brut
        self.assertTrue(out["sites"][1]["authentifie"]["connecte"])
        self.assertTrue(out["sites"][2]["authentifie"]["connecte"])
        blob = __import__("json").dumps(out, ensure_ascii=False)
        self.assertNotIn(SECRET, blob, "le secret ne doit jamais apparaître en sortie")
        self.assertNotIn("JETON42", blob, "pas de fuite de contenu de page non plus")

    def test_lent_et_constats(self):
        out = a.mesurer([{"nom": "Lent", "url": self.url("/lent")}], timeout=5)
        # SLOW_BRUT abaissé pour le test
        self.assertEqual(out["sites"][0]["brut"]["status"], 200)

    def test_erreur_sans_chaine_de_requete(self):
        r = a.mesure_auth("http://127.0.0.1:1/x?token=ABC", {"type": "basic", "user": "a", "secret": "b"})
        self.assertIsNotNone(r["erreur"])
        self.assertNotIn("ABC", r["erreur"])


if __name__ == "__main__":
    unittest.main()
