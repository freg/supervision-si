# -*- coding: utf-8 -*-
"""#856 : récapitulatif du risque -- axes réplication, sauvegarde, accès, support, nœud ; niveau ; tri."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import risque as R  # noqa: E402

T = 1792000000
INV = {"invites": [
    {"key": "pve-2/100", "node": "pve-2", "vmid": 100, "name": "THD85", "type": "lxc", "status": "running", "disques": ["subvol-100-disk-0"],
     "verdict": "ok", "raisons": [], "meilleure": {"type": "réplique", "hote": "pve-3", "distance": "3.0 Go modifiés · 0.2 h"}},
    {"key": "pve10/100", "node": "pve10", "vmid": 100, "name": "partages", "type": "qemu", "status": "running", "disques": ["vm-100-disk-1"],
     "verdict": "critique", "raisons": ["aucune copie qui survive à la perte de pve10"], "meilleure": None},
    {"key": "pve10/9101", "node": "pve10", "vmid": 9101, "name": "MED86", "type": "lxc", "status": "stopped", "disques": [], "verdict": "info",
     "raisons": [], "meilleure": None, "copie_de": "pve-3/101"},
    {"key": "pve-3/101", "node": "pve-3", "vmid": 101, "name": "MED86", "type": "lxc", "status": "stopped", "disques": ["subvol-101-disk-0"],
     "verdict": "ok", "raisons": [], "meilleure": {"type": "zfs", "hote": "pve11", "distance": "0 (identique)"}}]}
HOTES = [{"name": "pve-2", "replication": [{"job": "100-0", "vmid": 100, "target": "pve-3", "last_sync": "2026-10-26 08:30:01", "fail_count": 0, "enabled": True}],
          "zfs": [{"name": "rpool/subvol-100-disk-0"}], "pools": [{"name": "rpool", "health": "ONLINE", "redondance": "oui"}]},
         {"name": "pve10", "zfs": [{"name": "rpool/data/vm-100-disk-1"}], "pools": [{"name": "rpool", "health": "DEGRADED", "redondance": "non"}]},
         {"name": "pve-3", "zfs": [{"name": "rpool/subvol-101-disk-0"}], "pools": [{"name": "rpool", "health": "ONLINE", "redondance": "oui"}]}]
ACCES = {"pve-2/100": {"etat": "partiel", "cibles": [{"cible": "tcp://x:22", "ok": True}, {"cible": "tcp://x:443", "ok": False}]}}


class Risque(unittest.TestCase):
    def test_assemble(self):
        now = R._ts("2026-10-26 08:40:00")
        r = R.assemble(INV, HOTES, {"pve-3": {"quorum": {"quorate": True}}}, ACCES, cible="pve-3", maintenant=now)
        L = {l["key"]: l for l in r["lignes"]}
        self.assertNotIn("pve10/9101", L)                                        # copie restaurée : pas une source
        self.assertEqual(L["pve10/100"]["niveau"], "critique")
        self.assertEqual(L["pve10/100"]["axes"]["support"]["etat"], "critique")
        self.assertEqual(L["pve10/100"]["axes"]["replication"]["etat"], "na")
        self.assertEqual(L["pve-2/100"]["axes"]["replication"]["etat"], "ok")
        self.assertEqual(L["pve-2/100"]["axes"]["acces"]["etat"], "attention")
        self.assertEqual(L["pve-2/100"]["niveau"], "moyen")
        self.assertEqual(L["pve-3/101"]["axes"]["noeud"]["etat"], "attention")
        self.assertEqual(L["pve-3/101"]["axes"]["acces"]["etat"], "na")
        self.assertEqual(r["lignes"][0]["key"], "pve10/100")                     # le plus risqué d'abord
        self.assertEqual(r["resume"]["critique"], 1)

    def test_replication(self):
        now = R._ts("2026-10-26 12:00:00")
        self.assertEqual(R.replication([{"job": "1-0", "target": "x", "last_sync": "2026-10-26 08:30:01", "fail_count": 0}], now)["etat"], "attention")
        self.assertEqual(R.replication([{"job": "1-0", "target": "x", "last_sync": "2026-10-26 11:59:00", "fail_count": 2}], now)["etat"], "critique")
        self.assertEqual(R.replication([], now)["etat"], "aucune")


if __name__ == "__main__":
    unittest.main()
