# -*- coding: utf-8 -*-
"""#931 : poussée PBS -- construction des commandes, environnement (secret hors argv), interprétation."""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from si_agent import pbspush as pb  # noqa: E402

REPO = "postes-backup@pbs!sauvegarde@pbs10.intranet:backup"


class PbsPush(unittest.TestCase):
    def test_argv_push(self):
        a = pb.argv_push("/mnt/bk/extrait", REPO, "pc-paul", namespace="postes")
        self.assertEqual(a[0:2], ["proxmox-backup-client", "backup"])
        self.assertIn("poste.pxar:/mnt/bk/extrait", a)
        self.assertIn("--repository", a)
        self.assertIn(REPO, a)
        self.assertEqual(a[a.index("--backup-id") + 1], "pc-paul")
        self.assertEqual(a[a.index("--ns") + 1], "postes")
        self.assertIn("host", a)

    def test_backup_id_invalide(self):
        with self.assertRaises(ValueError):
            pb.argv_push("/x", REPO, "pc paul; rm -rf /")

    def test_preflight(self):
        a = pb.argv_preflight(REPO, "postes")
        self.assertEqual(a[0:3], ["proxmox-backup-client", "snapshot", "list"])
        self.assertIn("--output-format", a)

    def test_env_secret_hors_argv(self):
        env = pb.env_push(token_secret="S3CR3T", fingerprint="AB:CD")
        self.assertEqual(env["PBS_PASSWORD"], "S3CR3T")
        self.assertEqual(env["PBS_FINGERPRINT"], "AB:CD")
        a = pb.argv_push("/x", REPO, "pc-paul", "postes")
        self.assertNotIn("S3CR3T", " ".join(a), "le secret ne doit jamais être dans la ligne de commande")
        self.assertEqual(pb.env_push(), {})

    def test_interpreter(self):
        ok = pb.interpreter(0, "Upload image complete\nhost/pc-paul/2026-10-30T10:00:00Z was backed up", "")
        self.assertTrue(ok["ok"])
        self.assertEqual(ok["snapshot"], "host/pc-paul/2026-10-30T10:00:00Z")
        ko = pb.interpreter(255, "", "Error: authentication failed")
        self.assertFalse(ko["ok"])
        self.assertIn("authentication failed", ko["erreur"])
        pf = pb.interpreter(0, "[]", "", action="preflight")
        self.assertTrue(pf["ok"] and "vérifié" in pf["resume"])


if __name__ == "__main__":
    unittest.main()
