# -*- coding: utf-8 -*-
"""Tests #977 : erreurs à traiter des agents (regroupement, rétablissement, hors ligne)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import a_traiter as A  # noqa: E402


def ev(at, agent, kind, sev="critical", task=None, msg="m"):
    return {"at": "2026-11-06T%s:00Z" % at, "agent_id": agent, "kind": kind, "severity": sev, "message": msg,
            "details": ('{"task": "%s"}' % task) if task else None}


class ATraiter(unittest.TestCase):
    def test_regroupement_et_retablissement(self):
        evs = [ev("07:00", "sonde", "probe-alert", task="wifi-probe", msg="GROUPE_I : 40 % de pertes"),
               ev("08:00", "sonde", "probe-alert", task="wifi-probe", msg="GROUPE_I : 60 % de pertes"),
               ev("08:30", "sonde", "probe-alert", task="path-probe"),
               ev("09:00", "sonde", "probe-recovered", sev="info", task="path-probe"),       # rétabli : retiré
               ev("08:10", "i9", "plugin-failed", task="docker-containers"),
               ev("08:20", "mac", "auth-refused", sev="warning"),                             # avertissement : pas listé
               ev("06:00", "pc", "agent-offline"), ev("06:30", "pc", "agent-online", sev="info")]
        r = A.regrouper(evs, hors_ligne=["nas"], bloques=["vieux"])
        cles = [x["cle"] for x in r]
        self.assertIn("sonde|probe-alert|wifi-probe", cles)
        self.assertNotIn("sonde|probe-alert|path-probe", cles)
        self.assertNotIn("pc|agent-offline|", cles)
        g = next(x for x in r if x["cle"] == "sonde|probe-alert|wifi-probe")
        self.assertEqual((g["n"], g["message"], g["premiere"][11:16], g["derniere"][11:16]), (2, "GROUPE_I : 60 % de pertes", "07:00", "08:00"))
        self.assertEqual(r[0]["cle"], "nas|agent-offline|")              # sans date : en tête
        self.assertIn("vieux|agent-blocked|", cles)
        self.assertEqual(len(r), 4)                                   # sonde wifi, i9, nas, vieux
        self.assertEqual(A.regrouper([]), [])


if __name__ == "__main__":
    unittest.main()
