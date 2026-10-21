# -*- coding: utf-8 -*-
"""Tests #815 : préparer la réinstallation d'un nœud -- quorum (simulation sans la cible, version), contrôles,
santé des invités transférés, sauvegardes (hors du nœud ou non), PRA estimé, route /migration/preparation."""
import os
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("SI_AGENT_DB_PATH", os.path.join(tempfile.mkdtemp(), "t.db"))
import app as appmod  # noqa: E402
import prep  # noqa: E402

NOW = time.time()
ISO = lambda h: time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(NOW - h * 3600))  # noqa: E731
SYNC = lambda h: time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(NOW - h * 3600))  # noqa: E731
Q = lambda local: {"quorate": True, "nodes": 2, "expected": 2, "total": 2, "quorum": 2, "flags": "Quorate", "qdevice": False,  # noqa: E731
                   "membres": [{"id": "0x1", "votes": 1, "name": "192.0.2.12", "local": local == "pve-2", "qdevice": False},
                               {"id": "0x2", "votes": 1, "name": "192.0.2.13", "local": local == "pve-3", "qdevice": False}]}
STOR = {"local": {"type": "dir", "active": True, "shared": False}, "nfs1": {"type": "nfs", "active": True, "shared": True}}


def invite(vmid, nom, status="running", checks=None, charge=None, vmac=False, disk=100e9):
    return {"vmid": vmid, "type": "lxc", "name": nom, "status": status, "conf": {"vmac": vmac}, "disk": disk, "maxdisk": disk * 2,
            "charge": charge or {"cpu_avg_pct": 5.0, "cpu_max_pct": 40.0, "mem_avg_pct": 30.0, "mem_max_pct": 50.0},
            "checks": checks if checks is not None else ({"err_24h": 3, "warn_24h": 10, "failed_units": 0, "http_total": 1000, "http_5xx": 2, "complet": True} if status == "running" else None)}


PVE2 = {"name": "pve-2", "ok": True, "pveversion": "pve-manager/5.4-15/d0ec33c6", "quorum": Q("pve-2"), "ha": {"actif": False}, "storages": STOR,
        "replication": [{"job": "102-0", "vmid": 102, "target": "pve-3", "last_sync": SYNC(0.2), "fail_count": 0, "state": "OK"}],
        "backups": [{"vmid": 119, "storage": "nfs1", "at": ISO(30), "size": 5e10, "volid": "nfs1:backup/vzdump-lxc-119-x.tar.lzo"},
                    {"vmid": 102, "storage": "local", "at": ISO(10), "size": 9e10, "volid": "local:backup/vzdump-lxc-102-x.tar.lzo"}],
        "tasks": {"last_vzdump": {"102": {"at": NOW - 36000, "ok": True, "status": "OK"}, "119": {"at": NOW - 108000, "ok": False, "status": "job errors"}},
                  "migrations": [{"vmid": 102, "type": "vzmigrate", "at": NOW - 30000, "ok": True}]},
        "guests": [invite(102, "med", vmac=True, disk=370e9), invite(119, "cloud", checks={"err_24h": 800, "failed_units": 1, "http_total": 1000, "http_5xx": 150, "complet": True}, vmac=True),
                   invite(130, "web", charge={"cpu_max_pct": 97.0, "mem_max_pct": 40.0})]}
PVE3 = {"name": "pve-3", "ok": True, "pveversion": "pve-manager/5.4-15/d0ec33c6", "quorum": Q("pve-3"), "ha": {"actif": False}, "storages": STOR,
        "replication": [], "backups": [{"vmid": 110, "storage": "local", "at": ISO(5), "size": 1e10, "volid": "local:backup/vzdump-lxc-110-x"}],
        "tasks": {"last_vzdump": {}, "migrations": []},
        "guests": [invite(110, "tickets"), invite(113, "vieux", status="stopped")]}
REPORTS = [("a1", "deb13", "2026-10-21T20:00:00Z", {"nodes": [PVE2, PVE3]}), ("a2", "i9", "2026-10-21T19:00:00Z", {"nodes": [dict(PVE2, guests=[])]})]
LAN = [("a3", "pbs", "x", {"backups": [{"host": "pve-2", "vmid": 130, "at": NOW - 48 * 3600, "age_h": 48.0, "ok": True, "size": 2e10}]})]


class Prep(unittest.TestCase):
    def setUp(self):
        self.r = prep.assemble(REPORTS, LAN, {("pve-3", 113): {"decision": "archiver"}}, "pve-3", "pve-2", {"debit_lan": 50}, [119], NOW)
        self.i = {g["vmid"]: g for g in self.r["invites"]}

    def test_quorum(self):
        q = self.r["quorum"]
        self.assertEqual(q["verdict"], "attention")
        self.assertEqual(q["sans_cible"], {"votes": 1, "quorum": 2, "quorate": False})
        self.assertEqual([a["cmd"] for a in q["actions"]][:2], ["pvecm expected 1", "pvecm status"])
        self.assertTrue(all(a["ou"] == "pve-2" for a in q["actions"]))
        self.assertIn("ne pourra PAS rejoindre", q["detail"])                     # PVE 5.4 : un nœud neuf ne rejoint pas
        qd = dict(Q("pve-2"), total=3, qdevice=True, membres=Q("pve-2")["membres"] + [{"id": "0x0", "votes": 1, "name": "Qdevice", "local": False, "qdevice": True}])
        self.assertEqual(prep.quorum(dict(PVE3, pveversion="pve-manager/8.2.4", quorum=dict(qd, membres=Q("pve-3")["membres"])), dict(PVE2, quorum=qd, pveversion="pve-manager/8.2.4"))["verdict"], "ok")
        self.assertEqual(prep.quorum(None, dict(PVE2, quorum=None))["verdict"], "ok")
        self.assertEqual(prep.quorum(PVE3, dict(PVE2, quorum=dict(Q("pve-2"), quorate=False)))["verdict"], "bloquant")

    def test_releve_le_plus_frais(self):
        self.assertEqual(len(prep.noeuds(REPORTS)["pve-2"]["guests"]), 3)

    def test_sante(self):
        self.assertEqual(self.i[102]["sante"]["verdict"], "ok")
        self.assertTrue(self.i[102]["transfere"])                                  # migration pct détectée
        self.assertTrue(self.i[119]["transfere"])                                  # coché à la main
        self.assertFalse(self.i[130]["transfere"])
        self.assertEqual(self.i[119]["sante"]["verdict"], "bloquant")
        self.assertIn("15.0 % de réponses HTTP 5xx (1000 requêtes)", self.i[119]["sante"]["raisons"])
        self.assertEqual(self.i[130]["sante"]["verdict"], "attention")
        self.assertEqual(self.i[113]["sante"]["verdict"], "inconnu")
        self.assertEqual(prep.sante(dict(invite(1, "x"), checks={"erreur": "QEMU guest agent is not running", "complet": False}))["verdict"], "inconnu")

    def test_sauvegardes(self):
        s102 = self.i[102]["sauvegardes"]
        self.assertEqual((s102["verdict"], s102["hors_noeud"]), ("bloquant", None))       # seule copie : stockage local du même nœud
        s119 = self.i[119]["sauvegardes"]
        self.assertEqual((s119["hors_noeud"]["storage"], s119["verdict"]), ("nfs1", "attention"))   # tâche vzdump en échec
        self.assertEqual(self.i[130]["sauvegardes"]["lan"]["host"], "pve-2")
        self.assertEqual((self.i[110]["sauvegardes"]["hors_noeud"], self.i[110]["sauvegardes"]["verdict"]), (None, "bloquant"))   # seule copie sur pve-3
        self.assertEqual(self.r["perdues"]["nb"], 1)
        # une copie d'un invité de pve-2 posée sur le stockage local de pve-3 disparaîtra avec la réinstallation
        tous = prep.noeuds([("a", "h", "x", {"nodes": [PVE2, dict(PVE3, backups=[{"vmid": 130, "storage": "local", "at": ISO(5), "size": 1, "volid": "v"}])]})])
        s = prep.sauvegardes(130, "pve-2", tous, {}, NOW, "pve-3")
        self.assertEqual((s["hors_noeud"], s["verdict"]), (None, "bloquant"))
        self.assertIn("celles de pve-3 seront effacées", s["raisons"][0])
        self.assertEqual(prep.sauvegardes(130, "pve-2", tous, {}, NOW)["hors_noeud"]["noeud"], "pve-3")

    def test_pra(self):
        self.assertEqual((self.i[102]["pra"]["retenu"], self.i[102]["pra"]["verdict"]), (None, "bloquant"))   # réplica sur pve-3, qui sera effacé
        self.assertIn("disparaît avec la réinstallation", self.i[102]["pra"]["scenarios"][0]["remarque"])
        tous = prep.noeuds(REPORTS)
        g102 = next(g for g in PVE2["guests"] if g["vmid"] == 102)
        p = prep.pra(g102, "pve-2", tous, prep.sauvegardes(102, "pve-2", tous, {}, NOW), None, True)   # hors réinstallation
        self.assertEqual(p["retenu"]["type"], "replica")
        self.assertLess(p["retenu"]["rpo_h"], 1)
        self.assertEqual(p["retenu"]["rto_min"], 25)                                # démarrage 5 + IP OVH 15 + quorum 5
        self.assertIn("mv /etc/pve/nodes/pve-2/lxc/102.conf /etc/pve/nodes/pve-3/lxc/", " ".join(p["retenu"]["etapes"]))
        self.assertIn("locale", [s["type"] for s in p["scenarios"]])
        p119 = self.i[119]["pra"]["retenu"]
        self.assertEqual((p119["type"], p119["rto_min"]), ("sauvegarde", round(100 * 1000 / 150 / 60 + 25)))
        p130 = self.i[130]["pra"]["retenu"]
        self.assertEqual((p130["type"], p130["rto_min"]), ("lan", round(100 * 1000 / 50 / 60 + 100 * 1000 / 150 / 60 + 10)))
        sans = prep.pra(invite(7, "x"), "pve-2", {}, {"locale": None, "hors_noeud": None, "lan": None}, None, False)
        self.assertEqual((sans["verdict"], sans["retenu"]), ("bloquant", None))

    def test_controles(self):
        c = {x["id"]: x for x in self.r["controles"]}
        self.assertEqual(c["vider"]["verdict"], "bloquant")                        # 110 tourne encore sur pve-3, sans décision
        self.assertIn("113 vieux (stopped)", c["vider"]["detail"])
        self.assertEqual(c["replications"]["actions"][0]["cmd"], "pvesr delete 102-0")
        self.assertEqual(c["transferes"]["verdict"], "bloquant")
        self.assertEqual(c["sauvegardes"]["verdict"], "bloquant")
        self.assertEqual(self.r["verdict"], "bloquant")
        manque = prep.assemble(REPORTS[1:], [], {}, "pve-3", "pve-2")
        self.assertEqual(manque["controles"][0]["id"], "releves")


class Route(unittest.TestCase):
    def test_route(self):
        c = appmod.app.test_client()
        avant = appmod.infra.latest
        appmod.infra.latest = lambda conn, t: REPORTS if t == "plugin:pve-preflight" else LAN if t == "plugin:pulled-backups" else []
        try:
            r = c.get("/migration/preparation?debit_lan=50&transferes=119").get_json()
            self.assertEqual((r["cible"], r["accueil"], r["params"]["debit_lan"]), ("pve-3", "pve-2", 50.0))
            self.assertEqual(c.get("/migration/preparation?debit_lan=x").status_code, 400)
            appmod.infra.latest = lambda conn, t: []
            self.assertIn("activer la sonde pve-preflight", c.get("/migration/preparation").get_json()["error"])
        finally:
            appmod.infra.latest = avant


if __name__ == "__main__":
    unittest.main()
