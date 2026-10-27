# -*- coding: utf-8 -*-
"""Tests #883 : sonde nas-snmp sur un relevé QNAP de même structure qu'un TS-883XU-RP réel (valeurs fictives)."""
import json
import os
import sys
import tempfile
import unittest

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
import nas_snmp as ns  # noqa: E402

with open(os.path.join(ICI, "test_releve_exemple.txt"), encoding="utf-8") as fh:
    TEXTE = fh.read()


class NasSnmp(unittest.TestCase):
    def setUp(self):
        self.r = ns.releve(ns.parse_walk(TEXTE))

    def test_parse(self):
        d = ns.parse_walk('iso.3.6.1.4.1.55062.1.10.2.1.4.1 = STRING: "Seagate X"\n.1.3.6.1.4.1.55062.1.10.2.1.8.1 = INTEGER: 37\nbruit')
        self.assertEqual(d["1.3.6.1.4.1.55062.1.10.2.1.4.1"], "Seagate X")
        self.assertEqual(d["1.3.6.1.4.1.55062.1.10.2.1.8.1"], 37)

    def test_disques_et_smart(self):
        dq = self.r["disques"]
        self.assertEqual([x["emplacement"] for x in dq], [1, 2, 3, 8])
        self.assertEqual([x["heures"] for x in dq], [67625, 67625, 20600, 67619])
        self.assertEqual(dq[3]["smart"]["secteurs réalloués"], 1)

    def test_volumes(self):
        v = {x["nom"]: x["pct"] for x in self.r["volumes"]}
        self.assertEqual((v["Volume-1"], v["TimeMachineAlice"]), (83.9, 89.7))

    def test_alertes(self):
        a = {(x["code"], x["severity"]) for x in self.r["alertes"]}
        self.assertIn(("nas-volume-plein@Volume-1", "warning"), a)
        self.assertIn(("nas-volume-plein@TimeMachineAlice", "warning"), a)
        self.assertNotIn(("nas-volume-plein@Backup", "warning"), a)
        self.assertIn(("nas-disque-age@1", "warning"), a)
        self.assertNotIn(("nas-disque-age@3", "warning"), a)           # 20 600 h : sous le seuil
        self.assertIn(("nas-disque-smart@8", "warning"), a)            # 1 secteur réalloué sur le SSD
        self.assertIn(("nas-raid-redondance@/dev/md2", "warning"), a)
        self.assertIn(("nas-applications-maj", "info"), a)
        self.assertFalse(any(x["code"].startswith("nas-ventilateur") for x in self.r["alertes"]))
        r = ns.releve(ns.parse_walk(TEXTE), crit_pct=89)
        self.assertIn(("nas-volume-plein@TimeMachineAlice", "critical"), {(x["code"], x["severity"]) for x in r["alertes"]})

    def test_applications(self):
        apps = {x["nom"]: x for x in self.r["applications"]}
        self.assertTrue(apps["PlexMediaServer"]["mise_a_jour"])
        self.assertFalse(apps["FileStation5"]["mise_a_jour"])

    def test_main(self):
        with tempfile.TemporaryDirectory() as d:
            cfg = os.path.join(d, "c.json")
            with open(cfg, "w") as fh:
                json.dump([{"name": "nas-1", "host": "192.0.2.92", "community": "secret"}], fh)
            appels = []

            def runner(args, **kw):
                appels.append(args)
                return type("P", (), {"returncode": 0, "stdout": TEXTE if "snmpwalk" in args[0] and "55062.1" in args[-1] and len(appels) == 1 else "", "stderr": ""})()
            out = ns.main(["--config", cfg], runner=runner, which=lambda x: "/usr/bin/snmpwalk")
            self.assertTrue(out["nas"][0]["ok"])
            self.assertTrue(any(x["code"].endswith("#nas-1") for x in out["alerts"]))
            self.assertNotIn("secret", json.dumps(out))                    # la communauté ne sort jamais
            out = ns.main(["--config", cfg], which=lambda x: None)
            self.assertEqual(out["alerts"][0]["code"], "nas-snmp-outil")


if __name__ == "__main__":
    unittest.main()
