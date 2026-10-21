# -*- coding: utf-8 -*-
"""#806 : collecte des sondes d'un site -- lecture de l'état du collecteur (central local), résumé, constats."""
import calendar
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "..", "plugins", "collecte-sondes", "collecte_sondes.py")
spec = importlib.util.spec_from_file_location("collecte_sondes", SCRIPT)
cs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cs)

T0 = calendar.timegm((2026, 10, 21, 15, 0, 0))
ETAT = {"agents": {"sonde-3b": {"hostname": "sonde-3b", "ip": "192.0.2.160", "last_seen": "2026-10-21T14:59:30Z", "site": "campus"},
                   "sonde-zero": {"hostname": "sonde-zero", "last_seen": "2026-10-21T14:40:00Z"}},
        "measurements": {"sonde-3b": {
            "plugin:rf-spectrum": {"at": "2026-10-21T14:58:00Z", "data": {"canaux": [{"canal": 36, "occupation_pct": 61}], "alerts": [{"code": "spectre-occupe:36", "severity": "warning", "message": "canal 36 occupé"}]}},
            "plugin:wifi-probe": {"at": "2026-10-21T14:59:00Z", "data": {"iface": "wlan0", "link": {"connected": True, "signal": -52, "bss": {"x": 1}},
                                                                        "neighbourhood": {"radios": [1, 2, 3]}, "station": {"tx": 1}, "summary": "ok"}},
            "host": {"at": "x", "data": {}}}}}


class Collecte(unittest.TestCase):
    def test_sondes_et_constats(self):
        s, c = cs.sondes(ETAT, T0)
        self.assertEqual([x["sonde"] for x in s], ["sonde-3b", "sonde-zero"])
        a = s[0]
        self.assertEqual((a["age_s"], a["ip"], a["rf_spectrum_at"]), (30, "192.0.2.160", "2026-10-21T14:58:00Z"))
        self.assertEqual(a["wifi_probe"], {"iface": "wlan0", "summary": "ok", "link": {"connected": True, "signal": -52}})   # voisinage, station écartés
        self.assertNotIn("wifi_monitor", a)
        self.assertEqual([x["code"] for x in c], ["sonde-3b:spectre-occupe:36", "sonde-muette:sonde-zero"])
        self.assertEqual(c[0]["message"], "sonde-3b : canal 36 occupé")
        self.assertIn("20 min", c[1]["message"])

    def test_script(self):
        with tempfile.TemporaryDirectory() as d:
            f = os.path.join(d, "state.json")
            with open(f, "w") as fh:
                json.dump(ETAT, fh)
            out = json.loads(subprocess.run([sys.executable, SCRIPT, "--etat", f, "--muette", "999999999"], capture_output=True, text=True).stdout)
            self.assertEqual(len(out["sondes"]), 2)
            self.assertEqual([x["code"] for x in out["alerts"]], ["sonde-3b:spectre-occupe:36"])
            out = json.loads(subprocess.run([sys.executable, SCRIPT, "--etat", os.path.join(d, "absent")], capture_output=True, text=True).stdout)
            self.assertEqual(out["alerts"][0]["code"], "collecteur-illisible")


if __name__ == "__main__":
    unittest.main()
