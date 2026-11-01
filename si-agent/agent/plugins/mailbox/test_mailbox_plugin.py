# -*- coding: utf-8 -*-
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import si_mailbox as P  # noqa: E402


class Collecte(unittest.TestCase):
    def test_collecte(self):
        d = tempfile.mkdtemp()
        f = os.path.join(d, "home", "alice", ".local", "share", "si-mailbox")
        os.makedirs(f)
        json.dump({"ts": 1000, "comptes": 1, "automates": [{"nom": "factures", "mode": "essai"}], "traites_24h": 3, "erreurs_24h": 1,
                   "derniers": [], "contenu": "ne doit pas passer"}, open(os.path.join(f, "publication.json"), "w"))
        r = P.collecter((os.path.join(d, "home", "*", ".local", "share", "si-mailbox", "publication.json"),), maintenant=1000 + 7200)
        self.assertEqual(len(r["postes"]), 1)
        self.assertNotIn("contenu", r["postes"][0])
        self.assertEqual(sorted(a["code"] for a in r["alerts"]), ["mailbox-erreurs", "mailbox-silencieux"])
        self.assertEqual(P.collecter((os.path.join(d, "rien", "*.json"),)), {"postes": [], "alerts": []})


if __name__ == "__main__":
    unittest.main()
