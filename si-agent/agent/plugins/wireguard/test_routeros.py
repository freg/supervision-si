# -*- coding: utf-8 -*-
"""Tests #889 : API RouterOS (encodage, login, !re/!done/!trap) contre un faux routeur, et lecture WireGuard MikroTik."""
import json
import os
import socket
import sys
import tempfile
import threading
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import routeros  # noqa: E402
import wireguard as wg  # noqa: E402

NOW = 1_800_000_000
IFS = [{"name": "wg-bureau", "listen-port": "13231", "public-key": "PUBSERVEUR=", "private-key": "PRIVEE_SECRETE=", "running": "true"}]
PEERS = [
    {"interface": "wg-bureau", "public-key": "PUBALICE=", "comment": "Alice portable", "current-endpoint-address": "198.51.100.7",
     "current-endpoint-port": "40123", "allowed-address": "10.8.0.2/32", "last-handshake": "1m5s", "rx": "1000", "tx": "2000"},
    {"interface": "wg-bureau", "public-key": "PUBBOB=", "name": "bob", "allowed-address": "10.8.0.3/32,10.8.1.0/24", "rx": "0", "tx": "0"},
    {"interface": "wg-bureau", "public-key": "PUBCAROL=", "comment": "Carol", "endpoint-address": "203.0.113.9", "endpoint-port": "0",
     "allowed-address": "10.8.0.4/32", "last-handshake": "2h3m", "rx": "5", "tx": "6"},
    {"interface": "wg-bureau", "public-key": "PUBDESACTIVE=", "disabled": "true"},
]


def faux_routeur(sock, recus, mdp="bon"):
    api = routeros.Api(sock)
    try:
        while True:
            mots = api._phrase()
            recus.append(mots)
            if mots[0] == "/login":
                ok = "=password=" + mdp in mots
                sock.sendall(routeros.phrase(["!done"]) if ok else routeros.phrase(["!trap", "=message=invalid user name or password (6)"]) + routeros.phrase(["!done"]))
                continue
            lignes = IFS if mots[0] == "/interface/wireguard/print" else PEERS if mots[0] == "/interface/wireguard/peers/print" else []
            for l in lignes:
                sock.sendall(routeros.phrase(["!re"] + ["=%s=%s" % kv for kv in l.items()]))
            sock.sendall(routeros.phrase(["!done"]))
    except (ConnectionError, OSError, IndexError):
        pass


class RouterOs(unittest.TestCase):
    def setUp(self):
        self.recus = []
        self.a, self.b = socket.socketpair()
        threading.Thread(target=faux_routeur, args=(self.b, self.recus), daemon=True).start()

    def tearDown(self):
        self.a.close()
        self.b.close()

    def test_longueurs(self):
        for n in (0, 1, 0x7F, 0x80, 0x3FFF, 0x4000, 0x1FFFFF, 0x200000, 0xFFFFFFF, 0x10000000):
            a, b = socket.socketpair()
            a.sendall(routeros.enc_len(n))
            self.assertEqual(routeros.Api(b)._len(), n)
            a.close()
            b.close()

    def test_durees(self):
        self.assertEqual([routeros.duree_s(x) for x in ("1m5s", "2h3m", "1w2d", "00:01:05", "350ms", "", None)], [65, 7380, 777600, 65, 0, None, None])

    def test_lecture_seule(self):
        with self.assertRaises(ValueError):
            routeros.Api(self.a).lire("/interface/wireguard/peers/remove")

    def test_mikrotik(self):
        cfg = {"host": "192.0.2.1", "user": "supervision", "password": "bon"}
        ifs = wg.lire_mikrotik(cfg, connecter=lambda h, p, t: routeros.Api(self.a), now=NOW)
        i = ifs[0]
        self.assertEqual((i["interface"], i["port"], i["public_key"]), ("wg-bureau", 13231, "PUBSERVEUR="))
        a, b, c = i["peers"]                                 # le pair désactivé est écarté
        self.assertEqual((a["name"], a["endpoint"], a["handshake_age_s"], a["connected"], a["rx"]), ("Alice portable", "198.51.100.7:40123", 65, True, 1000))
        self.assertEqual((b["name"], b["handshake_at"], b["connected"], b["allowed_ips"]), ("bob", None, False, ["10.8.0.3/32", "10.8.1.0/24"]))
        self.assertEqual((c["endpoint"], c["connected"]), ("203.0.113.9", False))
        self.assertNotIn("SECRETE", json.dumps(ifs))
        self.assertEqual([m[0] for m in self.recus], ["/login", "/interface/wireguard/print", "/interface/wireguard/peers/print"])

    def test_main_et_mauvais_mot_de_passe(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "mk.json")
            with open(p, "w") as fh:
                json.dump({"host": "192.0.2.1", "user": "supervision", "password": "mauvais"}, fh)
            out = wg.main(["--mikrotik", p], connecter=lambda h, pt, t: routeros.Api(self.a), now=NOW)
            self.assertEqual(out["alerts"][0]["code"], "vpn-lecture")
            self.assertIn("invalid user name or password", out["alerts"][0]["message"])
            self.assertNotIn("mauvais", json.dumps(out))       # le mot de passe ne sort jamais
            self.assertEqual(out["source"], "mikrotik:192.0.2.1")


if __name__ == "__main__":
    unittest.main()


class Accent(unittest.TestCase):
    def test_mot_de_passe_accentue_en_cp1252(self):
        """Le routeur attend « é » en Windows-1252 : 1er essai UTF-8 refusé, 2e essai Windows-1252 accepté."""
        essais = []

        def routeur(sock):
            api = routeros.Api(sock)
            try:
                while True:
                    n = api._len()
                    mots = []
                    while n:
                        mots.append(api._lire(n))
                        n = api._len()
                    if mots[0] == b"/login":
                        essais.append(mots[2])
                        ok = mots[2] == b"=password=" + "été".encode("cp1252")
                        sock.sendall(routeros.phrase(["!done"]) if ok else routeros.phrase(["!trap", "=message=invalid user name or password (6)"]) + routeros.phrase(["!done"]))
                    else:
                        sock.sendall(routeros.phrase(["!done"]))
            except (ConnectionError, OSError, IndexError):
                pass
        paires = []

        def connecter(h, p, t):
            a, b = socket.socketpair()
            paires.append((a, b))
            threading.Thread(target=routeur, args=(b,), daemon=True).start()
            return routeros.Api(a)
        ifs = wg.lire_mikrotik({"host": "192.0.2.1", "user": "supervision", "password": "été"}, connecter=connecter, now=NOW)
        self.assertEqual(ifs, [])
        self.assertEqual(essais, [b"=password=" + "été".encode("utf-8"), b"=password=" + "été".encode("cp1252")])
        for a, b in paires:
            a.close()
            b.close()
