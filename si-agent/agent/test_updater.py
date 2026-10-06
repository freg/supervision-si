"""Tests de l'auto-mise à jour de l'agent (#576 : journal de l'installeur, mise à jour restée sans effet)."""
import json
import os
import tempfile
import time
import unittest

from si_agent import updater


class Updater(unittest.TestCase):
    def test_stalled_and_log(self):
        d = tempfile.mkdtemp()
        pend = os.path.join(d, "update-pending.json"); log = os.path.join(d, "update-1.log")
        with open(log, "w") as fh:
            fh.write("copie des fichiers\nerreur : permission refusée sur /opt/si-agent\n")
        updater.write_pending(pend, "0.5.7", "0.5.13", "cmd1", now=1000, log_path=log)
        self.assertIsNone(updater.check_stalled(pend, "0.5.7", now=1000 + 60))          # trop tôt
        ev = updater.check_stalled(pend, "0.5.7", now=1000 + updater.STALL_SECONDS + 1)
        self.assertEqual(ev[0], "agent-update-failed"); self.assertIn("permission refusée", ev[2]); self.assertIn("permission refusée", ev[3]["log_tail"])
        self.assertFalse(os.path.exists(pend))                                            # marqueur consommé
        updater.write_pending(pend, "0.5.7", "0.5.13", "cmd2", now=1000, log_path=log)
        self.assertIsNone(updater.check_stalled(pend, "0.5.13", now=5000))               # version atteinte : ce n'est pas un blocage
        ev = updater.check_pending(pend, "0.5.13"); self.assertEqual(ev[0], "agent-updated")
        updater.write_pending(pend, "0.5.7", "0.5.13", "cmd3", now=1000, log_path=log)
        self.assertEqual(updater.check_pending(pend, "0.5.14")[0], "agent-updated")  # #577 : plus récent que la cible = réussi
        self.assertEqual(updater.log_tail("/nulle/part"), "")

    def test_run_update_spawn_failure(self):
        class A:
            cfg = {"state_path": os.path.join(tempfile.mkdtemp(), "state.json")}
        import hashlib, io, tarfile
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w:gz") as tar:
            info = tarfile.TarInfo("si-agent-agent-0.9.9/install.sh"); data = b"#!/bin/bash\n"; info.size = len(data); tar.addfile(info, io.BytesIO(data))
        blob = buf.getvalue()
        params = {"version": "0.9.9", "sha256": hashlib.sha256(blob).hexdigest(), "command_id": "c"}
        def boom(cmd, mode, log_path=None):
            raise OSError("powershell introuvable")
        r = updater.run_update(A(), params, fetch=lambda u: blob, spawn=boom, current_version="0.5.7")
        self.assertFalse(r["ok"]); self.assertIn("introuvable", r["error"])
        seen = {}
        def ok(cmd, mode, log_path=None):
            seen.update(cmd=cmd, log=log_path)
        r = updater.run_update(A(), params, fetch=lambda u: blob, spawn=ok, current_version="0.5.7")
        self.assertTrue(r["ok"]); self.assertTrue(seen["log"].endswith(".log")); self.assertIn("--upgrade", " ".join(seen["cmd"]))
        self.assertIn(os.path.join(os.path.dirname(A.cfg["state_path"]), "update"), " ".join(seen["cmd"]))  # #577 : hors /tmp (PrivateTmp)


class InstallerOutput(unittest.TestCase):
    """#685 : sortie de l'installeur lancé par systemd-run redirigée vers le journal de mise à jour."""

    def test_systemd_run_redirige(self):
        cmd, mode = updater.installer_command("/var/lib/si-agent/update/x", platform="linux", which=lambda b: "/usr/bin/" + b,
                                              log_path="/var/lib/si-agent/update-1.log")
        self.assertEqual(mode, "systemd-run")
        self.assertEqual(cmd[cmd.index("-c") + 2:], ["/var/lib/si-agent/update/x/install.sh", "/var/lib/si-agent/update-1.log"])
        import subprocess
        d = tempfile.mkdtemp(); script = os.path.join(d, "install.sh"); log = os.path.join(d, "u.log")
        with open(script, "w") as fh:
            fh.write('echo "args:$*"; echo erreur >&2\n')
        subprocess.run(["/bin/bash"] + cmd[cmd.index("-c"):cmd.index("-c") + 2] + [script, log], check=True)
        with open(log) as fh:
            self.assertEqual(fh.read(), "args:--upgrade\nerreur\n")

    def test_sans_systemd_run(self):
        cmd, mode = updater.installer_command("/r", platform="linux", which=lambda b: None, log_path="/l")
        self.assertEqual((cmd, mode), (["/bin/bash", "/r/install.sh", "--upgrade"], "setsid"))


if __name__ == "__main__":
    unittest.main()
