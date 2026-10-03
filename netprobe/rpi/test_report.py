# -*- coding: utf-8 -*-
import os, sys, json, tempfile, unittest, importlib.util
spec = importlib.util.spec_from_file_location("rep", os.path.join(os.path.dirname(__file__), "report-wifi-day.py")); rep = importlib.util.module_from_spec(spec); spec.loader.exec_module(rep)

def rows():
    out = []
    for i in range(6):
        at = "2026-10-04T%02d:%02d:00" % (8 + i // 3, (i % 3) * 20)
        out.append({"agent_id": "sonde-3b", "task": "plugin:wifi-probe", "at": at, "ok": True, "data": {"link": {"signal_dbm": -60 - i, "tx_mbit": 72}, "channel": {"busy_pct": 20 + 10 * i},
                    "path": {"rtt_avg_ms": 5.5, "loss_pct": 0}, "alerts": ([{"kind": "canal saturé", "message": "canal 6 occupé à 70 %"}] if i >= 5 else []),
                    "neighbors": [{"bssid": "02:00:00:00:00:01", "ssid": "campus", "freq": 2437, "signal_dbm": -55 - i, "bss_load": {"stations": 3 + i}}]}})
    out.append({"agent_id": "sonde-zero", "task": "plugin:path-probe", "at": "2026-10-04T08:05:00", "ok": True, "data": {"summary": {"http_ms": 120}}})
    out.append({"agent_id": "sonde-zero", "task": "plugin:wifi-probe", "at": "2026-10-04T08:06:00", "ok": False, "error": "non associé", "data": None})
    return out

class Report(unittest.TestCase):
    def test_pure(self):
        r = rows(); s = rep.series(r, "plugin:wifi-probe", "link.signal_dbm"); self.assertEqual([v for _, v in s], [-60, -61, -62, -63, -64, -65])
        h = rep.hourly(s); self.assertEqual(sorted(h), ["2026-10-04T08", "2026-10-04T09"]); self.assertEqual(h["2026-10-04T08"]["avg"], -61.0)
        f = rep.findings(r); self.assertEqual((f[0]["label"], f[0]["n"], f[0]["agent"]), ("canal 6 occupé à 70 %", 1, "sonde-3b"))
        aps = rep.aps_seen(r); self.assertEqual((aps[0]["n"], aps[0]["rssi_max"], aps[0]["stations_max"]), (6, -55, 8))
        self.assertEqual(rep.series(r, "plugin:wifi-probe", "nope.x"), [])

    def test_build_and_cli(self):
        d = tempfile.mkdtemp(); hist = os.path.join(d, "history.jsonl")
        with open(hist, "w") as fh:
            for r in rows(): fh.write(json.dumps(r) + "\n")
            fh.write("pas du json\n")
        loaded = rep.load(hist, since="2026-10-04T08:00", until="2026-10-04T09:59"); self.assertEqual(len(loaded), 8); self.assertEqual(len(rep.load(hist, until="2026-10-04T09:30")), 7)      # la mesure de 09:40 est hors fenêtre
        page, md = rep.build(loaded)
        self.assertIn("Sonde sonde-3b", page); self.assertIn("<svg", page); self.assertIn("canal 6 occupé", page); self.assertIn("02:00:00:00:00:01", page); self.assertIn("HTTP réel", page)
        self.assertIn("## Constats", md); self.assertIn("| 08h |", md)
        import subprocess
        r = subprocess.run([sys.executable, os.path.join(os.path.dirname(__file__), "report-wifi-day.py"), hist, os.path.join(d, "r.html"), "--md", os.path.join(d, "r.md")], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr); self.assertIn("8 mesure(s)", r.stdout); self.assertTrue(os.path.getsize(os.path.join(d, "r.html")) > 1000); self.assertTrue(os.path.exists(os.path.join(d, "r.md")))

if __name__ == "__main__": unittest.main()
