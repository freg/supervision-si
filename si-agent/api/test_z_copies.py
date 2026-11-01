# -*- coding: utf-8 -*-
"""#856 : inventaire des copies -- rattachement à la source, distance (instantané commun exact, majorant, source figée),
volume, survie à la perte du nœud, support fragile, verdict."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import copies as C  # noqa: E402

T = 1792000000
G = 1024 ** 3


def z(name, typ="filesystem", lref=10 * G, creation=T, written=0):
    ds, _, snap = name.partition("@")
    return {"name": name, "type": "snapshot" if snap else typ, "used": lref, "refer": lref, "lref": lref, "creation": creation, "written": written,
            "dataset": ds, "snap": snap or None, "mountpoint": None}


def hote(name, **kw):
    return dict({"name": name, "ok": True, "complete": True, "pools": [], "zfs": [], "guests": [], "cluster_vms": [], "storages": {}, "replication": [],
                 "pbs": [], "pbs_datastore": [], "supports": {}, "archives": [], "flux": [], "dirs": []}, **kw)


PVE3 = hote("pve-3", cluster="Clust-01",
            guests=[{"type": "lxc", "vmid": 101, "status": "stopped", "name": "MED86"}, {"type": "lxc", "vmid": 110, "status": "stopped", "name": "CD28"}],
            cluster_vms=[{"vmid": 100, "node": "pve-2"}, {"vmid": 101, "node": "pve-3"}, {"vmid": 110, "node": "pve-3"}],
            pools=[{"name": "rpool", "health": "ONLINE", "redondance": "oui"}],
            zfs=[z("rpool/subvol-101-disk-0", lref=177 * G, written=0), z("rpool/subvol-101-disk-0@mig1", lref=177 * G, creation=T - 8 * 86400, written=177 * G),
                 z("rpool/subvol-110-disk-1", lref=9 * G, written=0), z("rpool/subvol-110-disk-1@__replicate_110-0_1", lref=9 * G, creation=T - 600, written=1 * G),
                 z("rpool/subvol-100-disk-0", lref=480 * G), z("rpool/subvol-100-disk-0@__replicate_100-0_9", lref=480 * G, creation=T - 900, written=2 * G)])
PVE2 = hote("pve-2", cluster="Clust-01",
            guests=[{"type": "lxc", "vmid": 100, "status": "running", "name": "THD85"}],
            cluster_vms=[{"vmid": 100, "node": "pve-2"}, {"vmid": 101, "node": "pve-3"}, {"vmid": 110, "node": "pve-3"}],
            zfs=[z("rpool/subvol-100-disk-0", lref=483 * G, written=3 * G), z("rpool/subvol-100-disk-0@__replicate_100-0_9", lref=480 * G, creation=T - 900, written=5 * G),
                 z("rpool/subvol-110-disk-1", lref=9 * G), z("rpool/subvol-110-disk-1@__replicate_110-0_1", lref=9 * G, creation=T - 600)],
            archives=[{"path": "/var/lib/vz/dump/vzdump-lxc-110-2018_11_28-08_37_24.tar.lzo", "type": "lxc", "vmid": 110, "at": T - 8 * 365 * 86400, "size": 700 * 1024 ** 2, "compresse": True}])
PVE11 = hote("pve11", cluster="lan", pools=[{"name": "data", "health": "ONLINE", "redondance": "oui"}],
             zfs=[z("data/ovh/pve3/subvol-101-disk-0", lref=177 * G), z("data/ovh/pve3/subvol-101-disk-0@mig1", lref=177 * G, creation=T - 8 * 86400)])
PVE10 = hote("pve10", cluster="lan", guests=[{"type": "qemu", "vmid": 100, "status": "running", "name": "partages"},
                                              {"type": "lxc", "vmid": 9101, "status": "stopped", "name": "MED86"}],
             cluster_vms=[{"vmid": 100, "node": "pve10"}, {"vmid": 9101, "node": "pve10"}],
             pools=[{"name": "rpool", "health": "DEGRADED", "redondance": "non"}],
             zfs=[z("rpool/data/vm-100-disk-1", "volume", lref=1170 * G, written=1 * G), z("rpool/data/subvol-9101-disk-0", lref=177 * G, creation=T - 5 * 86400)],
             supports={"/opt/usb": {"fs": "ext4", "device": "/dev/sdd2"}},
             archives=[{"path": "/opt/usb/pve10-2026-10-26/vzdump-qemu-100-2026_10_26-10_03_01.vma.zst", "type": "qemu", "vmid": 100, "at": T - 3600, "size": 700 * G, "compresse": True}],
             dirs=[{"path": "/opt/usb/ovh/pve2/subvol-100-disk-0", "vmid": 100, "disk": "subvol-100-disk-0", "at": T - 20 * 3600, "size": 470 * G}],
             pbs=[{"storage": "pbs10", "volid": "pbs10:backup/ct/9101/x", "type": "lxc", "vmid": 9101, "at": T - 86400, "size": 100 * G}])
PBS10 = hote("pbs10", dans="pve10")
REP = [("a", "h", "2026-10-26T10:00:00", {"hosts": [PVE3, PVE2, PVE11, PVE10, PBS10, {"name": "pve-1", "ok": False, "error": "ssh"}]})]


def inv(regles=None):
    r = C.assemble(REP, regles, maintenant=T)
    return r, {i["key"]: i for i in r["invites"]}


class Copies(unittest.TestCase):
    def test_regex_noeud(self):
        rx = C._noeud_regex("pve-1")
        self.assertTrue(rx.search("data/ovh/pve1/x"))
        self.assertTrue(rx.search("vzdump-lxc-101-pve-1-2026"))
        self.assertFalse(rx.search("pve10-2026-10-26"))
        self.assertFalse(rx.search("pve11"))

    def test_source_figee_copie_lan(self):
        _r, I = inv()
        med = I["pve-3/101"]
        self.assertEqual(med["fige_depuis"], T - 8 * 86400)
        lan = next(c for c in med["copies"] if c["hote"] == "pve11")
        self.assertEqual((lan["type"], lan["delta"], lan["exact"], lan["commun"], lan["volume"], lan["rattachement"]),
                         ("zfs", 0, True, "mig1", "ok", "nom du nœud dans le chemin"))
        self.assertTrue(lan["survit"])
        self.assertEqual(med["verdict"], "ok")
        self.assertEqual(med["meilleure"]["hote"], "pve11")                         # à distance égale : le support solide
        restau = next(c for c in med["copies"] if c["type"] == "restauré")
        self.assertEqual((restau["hote"], restau["delta"]), ("pve10", 0))          # restauré après le gel de la source
        self.assertTrue(restau["support"]["fragile"])                                  # pool pve10 sans redondance
        self.assertEqual(I["pve10/9101"]["verdict"], "info")
        self.assertEqual(med["copies"][0]["hote"], "pve11")                           # tri : survivantes puis distance

    def test_replique_et_archives(self):
        _r, I = inv()
        thd = I["pve-2/100"]
        rep = next(c for c in thd["copies"] if c["type"] == "réplique")
        self.assertEqual((rep["hote"], rep["delta"], rep["exact"]), ("pve-3", 3 * G, True))    # depuis l'instantané commun
        rs = next(c for c in thd["copies"] if c["type"] == "rsync")
        self.assertEqual((rs["hote"], rs["rattachement"], rs["volume"]), ("pve10", "nom du nœud dans le chemin", "ok"))
        self.assertEqual(rs["support"]["fragile"], "disque simple (ext4 /dev/sdd2)")
        self.assertEqual(thd["meilleure"]["type"], "réplique")
        self.assertEqual(thd["verdict"], "ok")                                          # en marche, réplique < 26 h
        cd28 = I["pve-3/110"]
        vieux = next(c for c in cd28["copies"] if c["type"] == "vzdump")
        self.assertEqual((vieux["hote"], vieux["rattachement"]), ("pve-2", "même cluster"))
        self.assertEqual(I["pve10/100"]["meilleure"], None)                           # archive sur le nœud lui-même
        self.assertEqual(I["pve10/100"]["verdict"], "critique")
        part = next(c for c in I["pve10/100"]["copies"] if c["type"] == "vzdump")
        self.assertFalse(part["survit"])
        self.assertEqual(part["volume"], "plausible")

    def test_pbs_dans_le_meme_hote(self):
        _r, I = inv()
        pbs = [c for i in I.values() for c in i["copies"] if c["type"] == "pbs"]
        self.assertEqual(len(pbs), 1)
        self.assertEqual(pbs[0]["hote"], "pbs10")

    def test_regles_et_orphelines(self):
        r, I = inv({"origines": {"data/ovh/pve3": "pve-9"}})
        self.assertTrue(any(o["hote"] == "pve11" and "règle" in o["raison"] for o in r["orphelines"]))
        self.assertEqual(I["pve-3/101"]["verdict"], "attention")                       # ne reste que la copie restaurée, sur un pool fragile
        self.assertIn("support fragile", " ".join(I["pve-3/101"]["raisons"]))

    def test_distance_texte(self):
        self.assertEqual(C._distance({"delta": 0, "exact": True}, "stopped"), "0 (identique)")
        self.assertEqual(C._distance({"delta": 3 * G, "exact": True, "age_h": 0.2}, "running"), "3.0 Go modifiés · 0.2 h")
        self.assertIn("≤", C._distance({"delta": G, "exact": False, "age_h": 100}, "running"))
        self.assertEqual(C.taille_lisible(None), "?")

    def test_hote_en_echec(self):
        r, _I = inv()
        self.assertEqual(next(h for h in r["hotes"] if h["name"] == "pve-1")["error"], "ssh")


if __name__ == "__main__":
    unittest.main()
