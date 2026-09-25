# -*- coding: utf-8 -*-
"""Tests de l'auto-mise à jour (#522) : vérification, extraction sûre, choix de
l'installeur, marqueur, exécution de la commande avec téléchargeur et lanceur factices."""
import hashlib
import io
import json
import os
import sys
import tarfile
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from si_agent import updater  # noqa: E402


def make_archive(version="9.9.9", extra=None):
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for name, body in [("si-agent-agent-%s/install.sh" % version, b"#!/bin/bash\n"), ("si-agent-agent-%s/si_agent/__init__.py" % version, b"")] + (extra or []):
            ti = tarfile.TarInfo(name)
            ti.size = len(body)
            tar.addfile(ti, io.BytesIO(body))
    return buf.getvalue()


class FakeAgent(object):
    def __init__(self, state_dir):
        self.cfg = {"state_path": os.path.join(state_dir, "state.json")}


class Updater(unittest.TestCase):
    def test_verify_et_installeur(self):
        data = make_archive()
        ok, got = updater.verify_archive(data, "sha256:" + hashlib.sha256(data).hexdigest().upper())
        self.assertTrue(ok)
        self.assertFalse(updater.verify_archive(data, "00" * 32)[0])
        cmd, mode = updater.installer_command("/tmp/r", platform="linux", which=lambda n: n == "systemd-run")
        self.assertEqual((cmd[0], cmd[-1], mode), ("systemd-run", "--upgrade", "systemd-run"))
        cmd, mode = updater.installer_command("/tmp/r", platform="linux", which=lambda n: False)
        self.assertEqual((cmd[1], mode), ("/tmp/r/install.sh", "setsid"))
        cmd, mode = updater.installer_command("/tmp/r", platform="darwin")
        self.assertTrue(cmd[1].endswith("install-macos.sh") and mode == "setsid")
        cmd, mode = updater.installer_command("C:\\r", platform="win32")
        self.assertEqual((cmd[0], cmd[-1], mode), ("powershell.exe", "-Upgrade", "detached"))

    def test_extraction_refuse_les_chemins_sortants(self):
        data = make_archive(extra=[("si-agent-agent-9.9.9/../../etc/evil", b"x")])
        dest = tempfile.mkdtemp()
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
            with self.assertRaises(ValueError):
                updater.safe_extract(tar, dest)

    def test_run_update(self):
        d = tempfile.mkdtemp()
        agent = FakeAgent(d)
        data = make_archive()
        spawned = []
        res = updater.run_update(agent, {"version": "9.9.9", "sha256": hashlib.sha256(data).hexdigest(), "url": "/package", "command_id": "c1"},
                                 fetch=lambda url: data, spawn=lambda cmd, mode, log_path=None: spawned.append((cmd, mode)), current_version="0.5.2")  # #576 : log_path
        self.assertTrue(res["ok"], res)
        self.assertEqual(res["result"]["to"], "9.9.9")
        self.assertEqual(len(spawned), 1)
        self.assertTrue(spawned[0][0][-1] == "--upgrade")
        marker = updater.pending_path(agent.cfg["state_path"])
        self.assertEqual(json.load(open(marker))["command"], "c1")
        ev = updater.check_pending(marker, "9.9.9")
        self.assertEqual(ev[0], "agent-updated")
        self.assertFalse(os.path.exists(marker), "marqueur consommé")
        # même version : rien à faire ; mauvais sha : refus sans lancement
        self.assertTrue(updater.run_update(agent, {"version": "0.5.2"}, fetch=lambda u: data, spawn=None, current_version="0.5.2")["result"]["already"])
        bad = updater.run_update(agent, {"version": "9.9.9", "sha256": "00" * 32}, fetch=lambda u: data, spawn=lambda c, m: spawned.append(1), current_version="0.5.2")
        self.assertFalse(bad["ok"]); self.assertIn("SHA-256", bad["error"]); self.assertEqual(len(spawned), 1)
        # marqueur non honoré -> échec signalé
        updater.write_pending(marker, "0.5.2", "9.9.9", "c2")
        self.assertEqual(updater.check_pending(marker, "0.5.2")[0], "agent-update-failed")
        self.assertIsNone(updater.check_pending(marker, "0.5.2"))
        err = updater.run_update(agent, {"version": "9.9.9", "sha256": "x"}, fetch=lambda u: (_ for _ in ()).throw(OSError("réseau")), current_version="0.5.2")
        self.assertIn("téléchargement", err["error"])


if __name__ == "__main__":
    unittest.main()
