# -*- coding: utf-8 -*-
"""Tests de la sonde PBS (#716) : configuration, arborescence réelle d'un datastore (dossier temporaire), constats."""
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pbs  # noqa: E402

CFG = """datastore: backup
\tcomment
\tgc-schedule daily
\tpath /srv/backup/datastore

datastore: autre
\tpath /mnt/autre
"""


class Sonde(unittest.TestCase):
    def test_cfg(self):
        s = pbs.parse_cfg(CFG)
        self.assertEqual([(x["name"], x["path"]) for x in s], [("backup", "/srv/backup/datastore"), ("autre", "/mnt/autre")])
        self.assertEqual(s[0]["gc-schedule"], "daily")

    def test_scan(self):
        d = tempfile.mkdtemp()
        def snap(rel, complete=True):
            p = os.path.join(d, rel); os.makedirs(p)
            if complete:
                open(os.path.join(p, "index.json.blob"), "w").close()
        snap("ct/101/2026-10-08T01:00:00Z"); snap("ct/101/2026-10-09T01:00:00Z")
        snap("ns/optick/host/optick3-prod/2026-10-09T15:14:45Z", complete=False)
        os.makedirs(os.path.join(d, ".chunks", "0000"))
        g = {(x["ns"], x["type"], x["id"]): x for x in pbs.scan_store(d)}
        self.assertEqual(g[("", "ct", "101")]["count"], 2)
        self.assertEqual(g[("", "ct", "101")]["last"], 1791507600)   # 2026-10-09T01:00:00Z
        self.assertFalse(g[("optick", "host", "optick3-prod")]["last_complete"])

    def test_summarize(self):
        now = 1_800_000_000
        stores = [{"name": "backup", "path": "/x"}]
        groups = {"backup": [{"ns": "optick", "type": "host", "id": "app", "count": 3, "last": now - 3600, "last_complete": True},
                             {"ns": "", "type": "ct", "id": "113", "count": 1, "last": now - 48 * 3600, "last_complete": True},
                             {"ns": "", "type": "ct", "id": "999", "count": 1, "last": now - 60 * 86400, "last_complete": True}]}
        usage = {"backup": {"total": 100, "used": 90, "free": 10}}
        tasks = [{"worker_type": "garbage_collection", "worker_id": "backup", "starttime": now - 7200, "endtime": now - 7100, "status": "OK"},
                 {"worker_type": "verificationjob", "worker_id": "backup:verif", "starttime": now - 3600, "endtime": now - 3500, "status": "verification failed"},
                 {"worker_type": "backup", "worker_id": "backup:host/app", "starttime": now - 100 * 3600, "endtime": now, "status": "connection error"},
                 {"worker_type": "reader", "worker_id": "x", "starttime": now, "status": "OK"}]
        out = pbs.summarize(stores, groups, usage, tasks, now)
        codes = sorted(a["code"] for a in out["alerts"])
        self.assertEqual(codes, ["pbs-full:backup", "pbs-old:backup:ct/113", "pbs-task:verify:backup:verif"])   # 999 inactif, tâche ancienne ignorée
        self.assertEqual({g["id"]: g["state"] for g in out["groups"]}, {"app": "ok", "113": "en retard", "999": "inactif"})
        self.assertEqual(out["datastores"][0]["used_percent"], 90.0)
        self.assertEqual(out["summary"]["state"], "critical")
        self.assertEqual({t["kind"] for t in out["tasks"]["recent"]}, {"gc", "verify"})

    def test_tasks_error_and_main_without_pbs(self):
        def fail(*a, **k):
            return subprocess.CompletedProcess(a, 1, "", "commande inconnue")
        with self.assertRaises(RuntimeError):
            pbs.read_tasks(runner=fail)
        self.assertEqual(pbs.main(["--cfg", "/nonexistent/datastore.cfg"]), 0)


if __name__ == "__main__":
    unittest.main()
