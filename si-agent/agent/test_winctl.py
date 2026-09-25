"""Tests #613 : powerctl (reboot / arrêt / WoL), startupctl (lanceurs), watchdog (chien de garde)."""
import datetime as dt
import os
import sys
import unittest
from types import SimpleNamespace as NS

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from si_agent import powerctl, startupctl, watchdog  # noqa: E402


class PowerTests(unittest.TestCase):
    def test_reboot_windows_avec_message_borne(self):
        argv, err, delay = powerctl.build_argv({"action": "reboot", "delay_seconds": 30, "message": 'Maj "urgente"\nmaintenant'}, "win32")
        self.assertIsNone(err)
        self.assertEqual(argv[:4], ["shutdown.exe", "/r", "/t", "30"])
        self.assertNotIn('"', argv[5]); self.assertNotIn("\n", argv[5]); self.assertNotIn("/f", argv)

    def test_console_active_refuse_sans_force(self):
        argv, err, _ = powerctl.build_argv({"action": "shutdown"}, "win32", console_active=True)
        self.assertIsNone(argv); self.assertIn("force", err)
        argv, err, _ = powerctl.build_argv({"action": "shutdown", "force": True}, "win32", console_active=True)
        self.assertEqual(argv[1], "/s"); self.assertIn("/f", argv)

    def test_linux_et_cancel_et_bornes(self):
        argv, _, _ = powerctl.build_argv({"action": "reboot", "delay_seconds": 600}, "linux")
        self.assertEqual(argv[:3], ["shutdown", "-r", "+10"])
        argv, _, _ = powerctl.build_argv({"action": "shutdown", "delay_seconds": 5}, "linux")
        self.assertEqual(argv[2], "now")
        self.assertEqual(powerctl.build_argv({"action": "cancel"}, "win32")[0], ["shutdown.exe", "/a"])
        self.assertEqual(powerctl.build_argv({"action": "reboot", "delay_seconds": 99999}, "win32")[2], 3600)
        self.assertIsNotNone(powerctl.build_argv({"action": "explode"}, "win32")[1])

    def test_interpret_codes_windows(self):
        self.assertIn("déjà programmé", powerctl.interpret(NS(returncode=1190, stdout="", stderr="1190"), "reboot", 60)["error"])
        ok = powerctl.interpret(NS(returncode=0, stdout="", stderr=""), "reboot", 60)
        self.assertTrue(ok["ok"]); self.assertIn("60 s", ok["message"])

    def test_run_journalise_argv(self):
        calls = []
        r = powerctl.run(lambda argv, timeout: (calls.append(argv), NS(returncode=0, stdout="", stderr=""))[1], {"action": "reboot"}, "win32")
        self.assertTrue(r["ok"]); self.assertEqual(calls[0][0], "shutdown.exe")

    def test_wol(self):
        self.assertEqual(powerctl.normalize_mac("AA-BB-CC-DD-EE-FF"), "aa:bb:cc:dd:ee:ff")
        self.assertIsNone(powerctl.normalize_mac("aa:bb"))
        pkt = powerctl.magic_packet("aa:bb:cc:dd:ee:ff")
        self.assertEqual(len(pkt), 102); self.assertEqual(pkt[:6], b"\xff" * 6); self.assertEqual(pkt[6:12], bytes.fromhex("aabbccddeeff"))
        sent = []
        r = powerctl.send_wol({"mac": "aa:bb:cc:dd:ee:ff", "broadcast": "192.0.2.255"}, sender=lambda p, a, port: sent.append((a, port)))
        self.assertTrue(r["ok"]); self.assertEqual(sent, [("192.0.2.255", 9)] * 3)
        self.assertFalse(powerctl.send_wol({"mac": "zz"}, sender=lambda *a: None)["ok"])
        self.assertFalse(powerctl.send_wol({"mac": "aa:bb:cc:dd:ee:ff", "broadcast": "lan"}, sender=lambda *a: None)["ok"])


class StartupTests(unittest.TestCase):
    def test_run_key_startup_approved(self):
        argv, err = startupctl.build_argv({"kind": "run", "scope": "user", "name": "OneDrive", "enable": False})
        self.assertIsNone(err)
        self.assertEqual(argv[0], "reg.exe"); self.assertTrue(argv[2].startswith("HKCU\\")); self.assertTrue(argv[2].endswith("StartupApproved\\Run"))
        self.assertEqual(argv[argv.index("/d") + 1][:2], "03")
        argv, _ = startupctl.build_argv({"kind": "folder", "name": "Caisse.lnk", "enable": True})
        self.assertTrue(argv[2].startswith("HKLM\\")); self.assertTrue(argv[2].endswith("StartupFolder")); self.assertEqual(argv[argv.index("/d") + 1][:2], "02")

    def test_task_et_service_proteges(self):
        argv, _ = startupctl.build_argv({"kind": "task", "name": "\\Caisse\\Lancement", "enable": False})
        self.assertEqual(argv, ["schtasks.exe", "/Change", "/TN", "\\Caisse\\Lancement", "/Disable"])
        self.assertIsNotNone(startupctl.build_argv({"kind": "task", "name": "\\Microsoft\\Windows\\Defrag", "enable": False})[1])
        self.assertIsNotNone(startupctl.build_argv({"kind": "service", "name": "WinDefend", "enable": False})[1])
        argv, _ = startupctl.build_argv({"kind": "service", "name": "CaisseSvc", "enable": True})
        self.assertEqual(argv, ["sc.exe", "config", "CaisseSvc", "start=", "auto"])
        self.assertIsNotNone(startupctl.build_argv({"kind": "run", "name": "x & del", "enable": True})[1])
        self.assertIsNotNone(startupctl.build_argv({"kind": "bios", "name": "x", "enable": True})[1])

    def test_summarize(self):
        s = startupctl.summarize([{"kind": "run", "enabled": True}, {"kind": "run", "enabled": False}, {"kind": "service"}])
        self.assertEqual((s["total"], s["enabled"], s["disabled"], s["by_kind"]["run"]), (3, 2, 1, 2))


class WatchdogTests(unittest.TestCase):
    CFG = {"interval_seconds": 30, "apps": [
        {"id": "caisse", "label": "Caisse", "process": "caisse.exe", "command": "C:\\Caisse\\caisse.exe", "cooldown_seconds": 60, "max_restarts_per_hour": 2, "hours": "08:00-20:00", "days": "1-6"},
        {"id": "afficheur", "process": "afficheur.exe"},
        {"id": "Bad Id", "process": "x"},
    ]}

    def test_normalize(self):
        cfg, errors = watchdog.normalize_config(self.CFG)
        self.assertEqual([a["id"] for a in cfg["apps"]], ["caisse", "afficheur"])
        self.assertEqual(len(errors), 1); self.assertEqual(cfg["interval_seconds"], 30)
        self.assertEqual(cfg["apps"][0]["hours"], "08:00-20:00"); self.assertEqual(cfg["apps"][1]["max_restarts_per_hour"], 5)

    def test_cycle_relance_quota_retour(self):
        cfg, _ = watchdog.normalize_config(self.CFG)
        mon10 = dt.datetime(2026, 9, 28, 10, 0)  # lundi 10h
        t0 = 1_000_000
        acts, st, meas = watchdog.evaluate(cfg, ["explorer.exe"], t0, {}, now_dt=mon10)
        self.assertEqual([a["action"] for a in acts], ["restart", "down-alert"])  # caisse relancée, afficheur sans commande
        self.assertEqual(meas["apps"][0]["status"], "restart"); self.assertEqual(meas["apps"][1]["status"], "down")
        acts, st, meas = watchdog.evaluate(cfg, [], t0 + 10, st, now_dt=mon10)
        self.assertEqual(meas["apps"][0]["status"], "waiting"); self.assertEqual(acts, [])  # cooldown, alerte afficheur une seule fois
        acts, st, meas = watchdog.evaluate(cfg, [], t0 + 70, st, now_dt=mon10)
        self.assertEqual([a["action"] for a in acts], ["restart"]); self.assertEqual(acts[0]["attempt"], 2)
        acts, st, meas = watchdog.evaluate(cfg, [], t0 + 140, st, now_dt=mon10)
        self.assertEqual([a["action"] for a in acts], ["down-alert"]); self.assertIn("quota", acts[0]["reason"])
        acts, st, meas = watchdog.evaluate(cfg, ["C:\\Caisse\\CAISSE.EXE", "afficheur.exe"], t0 + 200, st, now_dt=mon10)
        self.assertEqual(sorted(a["action"] for a in acts), ["recovered", "recovered"])
        self.assertEqual(meas["summary"], {"total": 2, "ok": 2, "down": 0, "idle": 0})

    def test_fenetre_horaire(self):
        cfg, _ = watchdog.normalize_config(self.CFG)
        sun = dt.datetime(2026, 9, 27, 10, 0)
        acts, _, meas = watchdog.evaluate(cfg, [], 5, {}, now_dt=sun)
        self.assertEqual(meas["apps"][0]["status"], "idle")
        night = dt.datetime(2026, 9, 28, 22, 0)
        self.assertFalse(watchdog.in_window(cfg["apps"][0], night))
        self.assertTrue(watchdog.in_window({"hours": "22:00-06:00"}, night))

    def test_parse_process_list(self):
        win = '"System Idle Process","0","Services","0","8 K"\n"caisse.exe","1234","Console","1","50 000 K"\n'
        self.assertIn("caisse.exe", watchdog.parse_process_list(win, "win32"))
        self.assertIn("caisse", watchdog.parse_process_list("/opt/caisse/caisse\nbash\n", "linux"))


if __name__ == "__main__":
    unittest.main()
