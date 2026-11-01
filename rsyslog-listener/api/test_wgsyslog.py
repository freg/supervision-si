# -*- coding: utf-8 -*-
"""Tests #895 : sessions WireGuard d'après le syslog d'un MikroTik (format réel, valeurs fictives)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import journal  # noqa: E402
import wgsyslog as wg  # noqa: E402

K = "A" * 43 + "="
H = "routeur-exemple"


def m(t, ev, forme="bsd", sev=7):
    if forme == "bsd":
        return {"t": t, "ip": "192.0.2.182", "hote": H, "app": "wireguard1", "sev": sev, "msg": "[alice] %s: %s" % (K, ev)}
    return {"t": t, "ip": "192.0.2.182", "hote": "", "app": "", "sev": 5, "msg": "wireguard,info wireguard1: [alice] %s: %s" % (K, ev)}


T = 1_800_000_000
LIGNES = [
    m(T, "Receiving handshake initiation from peer (198.51.100.7:38245) extra:0 (einval)"),
    m(T + 0.01, "Sending handshake response to peer (198.51.100.7:38245)"),
    m(T + 120, "Receiving handshake initiation from peer (198.51.100.7:38245)"),
    m(T + 120.01, "Sending handshake response to peer (198.51.100.7:38245)"),
    m(T + 170, "Retrying handshake with peer because we stopped hearing back after 15 seconds"),
    m(T + 170.01, "Sending handshake initiation to peer (198.51.100.7:38245)"),
    m(T + 175, "Handshake for peer did not complete after 5 seconds, retrying (try 2)", forme="nu"),
    m(T + 175.002, "Handshake for peer did not complete after 5 seconds, retrying (try 2)", sev=6),     # doublon
    m(T + 900, "Receiving handshake initiation from peer (203.0.113.9:60584)"),                         # nouvelle adresse
    m(T + 900.01, "Sending handshake response to peer (203.0.113.9:60584)"),
]


class WgSyslog(unittest.TestCase):
    def test_evenements(self):
        e = wg.evenement(LIGNES[1])
        self.assertEqual((e["interface"], e["nom"], e["cle"], e["type"], e["origine"]), ("wireguard1", "alice", K, "reussite", "198.51.100.7:38245"))
        e = wg.evenement(LIGNES[6])
        self.assertEqual((e["interface"], e["type"], e["essai"]), ("wireguard1", "echec", 2))
        self.assertIsNone(wg.evenement({"t": T, "msg": "system,info log rule changed by winbox"}))

    def test_sessions(self):
        r = wg.sessions(list(reversed(LIGNES)), maintenant=T + 1000)
        s1, s2 = sorted(r["sessions"], key=lambda s: s["debut"])
        self.assertEqual((s1["debut"], s1["fin"], s1["duree_s"], s1["en_cours"], s1["pertes"], s1["echecs"]), (T + 0.01, T + 120.01, 120, False, 1, 1))
        self.assertTrue(s2["en_cours"])
        self.assertEqual(s2["origine"], "203.0.113.9:60584")
        p = r["pairs"][0]
        self.assertEqual((p["nom"], p["connecte"], p["echecs"], p["pertes"], p["origines"]), ("alice", True, 1, 1, ["198.51.100.7", "203.0.113.9"]))
        r = wg.sessions(LIGNES, maintenant=T + 5000)                       # plus d'activité : session close, pair déconnecté
        self.assertFalse(any(s["en_cours"] for s in r["sessions"]))
        self.assertFalse(r["pairs"][0]["connecte"])

    def test_forme_sans_entete(self):
        e = journal.analyser("<13>wireguard,info wireguard1: [alice] %s: Handshake for peer did not complete after 5 seconds, retrying (try 2)" % K)
        self.assertEqual((e["app"], e["sujet"]), ("wireguard1", "wireguard,info"))


if __name__ == "__main__":
    unittest.main()
