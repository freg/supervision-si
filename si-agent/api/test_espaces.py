# -*- coding: utf-8 -*-
"""Tests #986 : onglet Espaces disques / données (volumes, tendance, extension, NAS, classement, groupes)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import espaces as E  # noqa: E402

G = 1024 ** 3
T = 1024 ** 4


class Espaces(unittest.TestCase):
    def test_volumes_tendance_niveaux(self):
        disques = [{"mountpoint": "/", "device": "/dev/sda2", "fstype": "ext4", "total_bytes": 100 * G, "used_bytes": 80 * G, "free_bytes": 20 * G, "used_percent": 80.0},
                   {"mountpoint": "/var/lib/docker/overlay2/x", "fstype": "overlay", "total_bytes": 100 * G},
                   {"mountpoint": "/run", "fstype": "tmpfs", "total_bytes": G},
                   {"mountpoint": "/srv", "device": "/dev/sda2", "fstype": "ext4", "total_bytes": 100 * G, "used_bytes": 80 * G},   # même périphérique
                   {"mountpoint": "/data", "device": "/dev/sdb1", "fstype": "xfs", "total_bytes": 2 * T, "used_bytes": 1960 * G, "free_bytes": 88 * G}]
        hist = {"/": [(0, 70 * G), (1, 72 * G), (2, 74 * G), (3, 76 * G)]}      # +2 Go / jour -> plein dans 10 jours
        v = {x["nom"]: x for x in E.volumes_hote(disques, hist)}
        self.assertEqual(sorted(v), ["/", "/data"])
        self.assertEqual((v["/"]["pente_jour"] // G, v["/"]["saturation_jours"], v["/"]["niveau"]), (2, 10, "attention"))
        self.assertEqual(v["/data"]["niveau"], "critique")                       # 95,7 % calculé
        self.assertIsNone(E.tendance([(0, 1), (1, 2)]))

    def test_extension_hote(self):
        st = {"blocks": [{"name": "sda", "type": "disk", "size": 500 * G}, {"name": "sda1", "type": "part", "parent": "sda", "fstype": "ext4", "mountpoint": "/"},
                         {"name": "sdb", "type": "disk", "size": 4 * T, "model": "WDC"}, {"name": "sdc", "type": "disk", "size": 32 * G, "removable": True}],
              "lvm": {"groups": [{"vg": "pve", "size": 400 * G, "free": 120 * G}]},
              "zfs": {"pools": [{"pool": "tank", "size": 2 * T, "free": T}]},
              "md": [{"array": "md1", "level": "raid5", "devices": ["sda3", "sdb3", "sdc3"]}]}
        n = E.extension_hote(st)
        self.assertTrue(any("sdb" in x and "4,0 To" in x for x in n))
        self.assertFalse(any("sdc" in x or "disque sda " in x for x in n))
        self.assertTrue(any("LVM pve" in x and "120,0 Go" in x for x in n))
        self.assertTrue(any("ZFS tank" in x for x in n))
        self.assertTrue(any("RAID 5 md1 sur 3" in x for x in n))

    def test_nas_et_assemblage(self):
        nas = {"name": "NAS-GRPi-2", "host": "192.0.2.93", "systeme": {"modele": "TS-883XU-RP"},
               "volumes": [{"nom": "DataVol1", "pct": 41, "ko": 21 * T // 1024, "libre_ko": 12 * T // 1024}],
               "disques": [{"emplacement": i, "modele": "ST12000VN0008", "octets": 12 * 10 ** 12, "etat": "Good"} for i in (1, 2, 3)]}
        ssh = {"nas": [{"name": "NAS-GRPi-2", "raid": [{"dev": "md1", "niveau": "raid5", "disques": ["sda3", "sdb3", "sdc3"]}, {"dev": "md9", "systeme": True}]}]}
        agents = [{"agent_id": "super", "hostname": "super", "site": "bureau", "os": "linux"}, {"agent_id": "pve11", "hostname": "pve11", "site": "bureau"}]
        hotes = {"super": {"_at": "t", "disks": [{"mountpoint": "/", "device": "/dev/vda1", "fstype": "ext4", "total_bytes": 100 * G, "used_bytes": 96 * G}], "storage": {}}}
        r = E.assembler(agents, hotes, {"super": {"hardware": {"disks": [{"name": "vda", "size": 100 * G}]}}}, [("super", "super", "t", {"nas": [nas]})],
                        [("super", "super", "t", ssh)], {}, {"nas:NAS-GRPi-2": {"lan": "bureau-sauvegarde"}}, {"attention": 80})
        noms = [m["nom"] for m in r["machines"]]
        self.assertEqual(noms, ["super", "NAS-GRPi-2"])                         # critique d'abord ; pve11 sans mesure : absent
        n = r["machines"][1]
        self.assertEqual((n["materiel"]["baies"], n["classement"]["role"], n["classement"]["lan"]), (8, "NAS", "bureau-sauvegarde"))
        self.assertTrue(any("5 baie(s) libre(s) sur 8" in x for x in n["extension"]))
        self.assertTrue(any("RAID 5 sur 3 disques" in x for x in n["extension"]))
        self.assertEqual(r["seuils"]["attention"], 80)
        self.assertEqual(r["groupes"]["role"]["NAS"]["machines"], 1)
        self.assertEqual(r["machines"][0]["classement"]["role"], "serveur")
        self.assertEqual(r["groupes"]["lan"]["bureau"]["critique"], 1)

    def test_deviner(self):
        self.assertEqual(E.deviner({"agent_id": "pve11", "site": "bureau"})["role"], "hyperviseur")
        self.assertEqual(E.deviner({"agent_id": "x", "hostname": "ns3037858", "site": "ovh"})["hebergeur"], "OVH")
        self.assertEqual(E.deviner({"agent_id": "prodia", "site": "campus"}, plugins=["ollama"])["role"], "IA")
        self.assertEqual(E.deviner({"agent_id": "pc", "os": "Windows 11"})["role"], "poste")
        self.assertEqual(E.taille(12 * T), "12,0 To")


if __name__ == "__main__":
    unittest.main()
