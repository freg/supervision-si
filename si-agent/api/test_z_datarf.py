# -*- coding: utf-8 -*-
"""#806 : assemblage de la tuile « Data RF » (collecte d'un site + sondes directes)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import datarf  # noqa: E402

RF = {"canaux": [{"canal": 36, "occupation_pct": 61.0}], "alerts": [{"code": "spectre-occupe:36", "severity": "warning", "message": "canal 36 occupé"}]}


class Assemblage(unittest.TestCase):
    def test_collecte_et_directes(self):
        collectes = [("mini-pc", "minipc", "2026-10-21T15:00:00Z", {"sondes": [{"sonde": "sonde-3b", "rf_spectrum": RF, "rf_spectrum_at": "2026-10-21T14:59:00Z"}, "x"],
                                                                     "alerts": [{"code": "sonde-3b:spectre-occupe:36", "severity": "warning", "message": "sonde-3b : canal 36 occupé"}]})]
        directes = {"plugin:wifi-monitor": [("sonde-zero", "sonde-zero", "2026-10-21T15:01:00Z", {"canaux": [], "alerts": [{"code": "monitor-absente", "severity": "warning", "message": "carte absente"}]})],
                    "plugin:rf-spectrum": [("sonde-3b-ancien", "SONDE-3B", "2026-10-20T10:00:00Z", {"canaux": []})]}
        r = datarf.assembler(collectes, directes)
        self.assertEqual([s["sonde"] for s in r["sondes"]], ["sonde-3b", "sonde-zero"])
        s3 = r["sondes"][0]
        self.assertEqual((s3["via"], s3["rf_spectrum"]), ("minipc", RF))      # mesure directe plus ancienne : ignorée
        self.assertEqual(r["sondes"][1]["via"], None)
        self.assertEqual([c["message"] for c in r["constats"]], ["sonde-3b : canal 36 occupé", "sonde-zero : carte absente"])
        self.assertEqual(datarf.assembler([], {}), {"sondes": [], "constats": []})
        r = datarf.assembler([], {"plugin:wifi-probe": [("i9", "i9freg", "2026-10-21T15:00:00Z", {"link": {}})]})
        self.assertEqual(r["sondes"], [])                                       # poste avec wifi-probe seulement : pas une sonde radio


if __name__ == "__main__":
    unittest.main()
