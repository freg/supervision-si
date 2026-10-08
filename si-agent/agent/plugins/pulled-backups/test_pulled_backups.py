# -*- coding: utf-8 -*-
"""Tests #714 : script pve-pull-backup.sh (ssh simulé) et sonde pulled-backups."""
import gzip
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pulled_backups as pb  # noqa: E402

SCRIPT = os.path.join(HERE, "..", "..", "..", "tools", "pve-pull-backup.sh")


class Script(unittest.TestCase):
    def run_script(self, ssh_body, *args):
        d = tempfile.mkdtemp()
        fake = os.path.join(d, "bin"); os.makedirs(fake)
        with open(os.path.join(fake, "ssh"), "w") as fh:
            fh.write("#!/bin/bash\n" + ssh_body)
        os.chmod(os.path.join(fake, "ssh"), 0o755)
        env = dict(os.environ, PATH=fake + ":" + os.environ["PATH"], PULL_DEST=os.path.join(d, "dumps"), PULL_KEY="/nonexistent", PULL_NAME="pve-3")
        p = subprocess.run(["bash", SCRIPT] + list(args), env=env, capture_output=True, text=True)
        return p, os.path.join(d, "dumps")

    def test_succes_retention_et_echec(self):
        body = 'echo "INFO: sending archive to stdout" >&2; echo "contenu" | gzip -c\n'
        for _ in range(3):
            p, dest = self.run_script(body, "203.0.113.21", "113", "stop", "2")
            self.assertEqual(p.returncode, 0, p.stderr)
        files = sorted(f for f in os.listdir(os.path.join(dest, "pve-3")) if f.endswith(".tar.gz"))
        self.assertLessEqual(len(files), 2)
        rows = [json.loads(l) for l in open(os.path.join(dest, "pulls.jsonl"))]
        self.assertTrue(rows[-1]["ok"]); self.assertEqual((rows[-1]["host"], rows[-1]["vmid"], len(rows[-1]["sha256"])), ("pve-3", 113, 64))
        p, dest = self.run_script('echo "ERROR: CT 999 introuvable" >&2; exit 2\n', "203.0.113.21", "999")
        self.assertEqual(p.returncode, 1)
        row = json.loads(open(os.path.join(dest, "pulls.jsonl")).readlines()[-1])
        self.assertEqual((row["ok"], row["file"]), (False, "")); self.assertIn("introuvable", row["error"])
        p, dest = self.run_script('echo "pas du gzip"\n', "203.0.113.21", "113")
        self.assertEqual(json.loads(open(os.path.join(dest, "pulls.jsonl")).readlines()[-1])["error"], "archive gzip invalide")
        self.assertEqual(self.run_script(body, "h; rm -rf /", "1")[0].returncode, 2)                    # arguments refusés
        self.assertEqual(self.run_script(body, "h", "1", "fast")[0].returncode, 2)


class Sonde(unittest.TestCase):
    def test_resume(self):
        now = 1_800_000_000
        rows = [{"host": "pve-3", "vmid": 113, "ok": True, "ended": now - 3600, "size": 10, "sha256": "a", "file": "/x/113.tar.gz"},
                {"host": "pve-3", "vmid": 113, "ok": False, "ended": now - 60, "error": "ssh"},
                {"host": "pve-1", "vmid": 108, "ok": True, "ended": now - 10 * 86400, "size": 5, "file": "/x/108.tar.gz"},
                {"host": "pve-1", "vmid": "x"}]
        backups, alerts = pb.summarize(rows, now, 8, exists=lambda p: p.endswith("113.tar.gz"))
        b = {(x["host"], x["vmid"]): x for x in backups}
        self.assertEqual((b[("pve-3", 113)]["ok"], b[("pve-3", 113)]["age_h"], b[("pve-3", 113)]["failures"], b[("pve-3", 113)]["present"]), (False, 1.0, 1, True))
        self.assertEqual(sorted(a["code"] for a in alerts), ["pull-failed", "pull-missing", "pull-old"])
        d = tempfile.mkdtemp(); idx = os.path.join(d, "pulls.jsonl")
        with open(idx, "w") as fh:
            fh.write(json.dumps(rows[0]) + "\nnon json\n")
        self.assertEqual(len(pb.read_index(idx)), 1); self.assertIsNone(pb.read_index(os.path.join(d, "absent")))


if __name__ == "__main__":
    unittest.main()
