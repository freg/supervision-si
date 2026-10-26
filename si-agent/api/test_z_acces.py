# -*- coding: utf-8 -*-
"""#856 : accessibilité des services -- découverte, contrôle, « depuis », cibles manuelles (réseau simulé)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import acces as A  # noqa: E402

NODES = {"pve-2": {"guests": [{"vmid": 100, "status": "running", "name": "THD85", "conf": {"ips": ["198.51.100.7"]}},
                              {"vmid": 102, "status": "stopped", "name": "MED10", "conf": {"ips": ["198.51.100.8"]}},
                              {"vmid": 105, "status": "running", "name": "ATHENA", "conf": {"ips": []}}]}}
OUVERTS = {("198.51.100.7", 22), ("198.51.100.7", 443)}


class Acces(unittest.TestCase):
    def test_decouverte_puis_controle(self):
        inv = A.invites_en_marche(NODES)
        self.assertEqual(sorted(inv), ["pve-2/100", "pve-2/105"])
        up = set(OUVERTS)
        ftcp = lambda h, p, t=3: ((h, p) in up, 5 if (h, p) in up else None, None if (h, p) in up else "refusé")
        fhttp = lambda u: (True, 40, None)
        e = A.passage(inv, {"manuels": {"pve-2/105": ["https://athena.exemple.fr/"]}}, ftcp, fhttp, maintenant=1000)
        self.assertEqual(e["attendus"]["pve-2/100"], ["tcp://198.51.100.7:22", "tcp://198.51.100.7:443"])
        self.assertEqual(e["resultats"]["pve-2/100"]["etat"], "ok")
        self.assertEqual(e["resultats"]["pve-2/105"]["cibles"][0]["manuel"], True)
        up.discard(("198.51.100.7", 443))
        e2 = A.passage(inv, e, ftcp, fhttp, maintenant=1300)
        self.assertEqual(e2["decouvertes"]["pve-2/100"], 1000)                        # pas de redécouverte avant 24 h
        r = {c["cible"]: c for c in e2["resultats"]["pve-2/100"]["cibles"]}
        self.assertEqual((r["tcp://198.51.100.7:443"]["ok"], r["tcp://198.51.100.7:443"]["depuis"]), (False, 1300))
        self.assertEqual(r["tcp://198.51.100.7:22"]["depuis"], 1000)
        self.assertEqual(e2["resultats"]["pve-2/100"]["etat"], "partiel")

    def test_verifier(self):
        self.assertEqual(A.verifier("tcp://h:x")[2], "cible illisible")
        self.assertEqual(A.verifier("h:22", f_tcp=lambda h, p: (True, 1, None)), (True, 1, None))
        self.assertEqual(A.etat_invite([]), "non surveillé")
        self.assertEqual(A.etat_invite([{"ok": False}]), "panne")


if __name__ == "__main__":
    unittest.main()
