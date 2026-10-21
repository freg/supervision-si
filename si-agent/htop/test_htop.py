# -*- coding: utf-8 -*-
"""#800 : si-htop -- émetteur (analyse /proc, relevé), relais (signature, rejeu, constats soutenus, historique,
HTTP, diffusion), client (abonnement, écran), bout en bout en UDP local."""
import json
import os
import shutil
import socket
import sys
import tempfile
import threading
import time
import unittest
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import client as cl  # noqa: E402
import emetteur as em  # noqa: E402
import relais as rl  # noqa: E402

CLE_E, CLE_C = b"cle-des-emetteurs-0123456789", b"cle-des-clients-0123456789"


def releve(h="pve-a", k="pve", t=None, s=1, c=10.0, io=1.0, st=0.0, mem=(64e9, 20e9, 10e9), l1=1.0, n=8, g=None, d=None, z=None, b="b1"):
    return {"v": 1, "h": h, "k": k, "t": t if t is not None else time.time(), "b": b, "s": s, "n": n, "c": c, "cc": [c] * n, "io": io, "st": st,
            "l": [l1, l1, l1], "m": list(mem), "sw": [8e9, 0], "up": 100, "pr": [[1, "kvm", 50.0, 2e9, "100"], [2, "mysqld", 5.0, 6e9, "102"]], "np": 300,
            "d": d or [["/", 100e9, 40e9]], "g": g if g is not None else [[102, "med10", "ct", 12.5, 1.0, 9e9, 6e9, 8e9], [100, "thd", "vm", 25.0, 2.0, 4e9, 4e9, 8e9]],
            "z": z or [["rpool", 1000, 820, "ONLINE"]]}


class Horloge(object):
    def __init__(self, t=1_000_000.0):
        self.t = t

    def __call__(self):
        return self.t


class Emetteur(unittest.TestCase):
    def test_cpu(self):
        a = em.cpu_stat("cpu  100 0 100 700 100 0 0 0 0 0\ncpu0 50 0 50 350 50 0 0 0\nintr 1")
        b = em.cpu_stat("cpu  200 0 200 1300 200 0 0 100 0 0\ncpu0 100 0 100 650 100 0 0 50")
        self.assertEqual(sorted(a), ["cpu", "cpu0"])
        self.assertEqual(em.cpu_pourcents(b["cpu"], a["cpu"]), (30.0, 10.0, 10.0))   # occupé = tout sauf idle + iowait
        self.assertEqual(em.cpu_pourcents(a["cpu"], None), (None, None, None))
        self.assertEqual(em.cpu_pourcents(a["cpu"], a["cpu"]), (None, None, None))

    def test_memoire_arc_proc(self):
        m = em.meminfo("MemTotal: 1000 kB\nMemFree: 100 kB\nMemAvailable: 400 kB\nSwapTotal: 200 kB\nSwapFree: 50 kB\n")
        self.assertEqual(m, {"total": 1024000, "used": 614400, "swap_total": 204800, "swap_used": 153600})
        self.assertEqual(em.meminfo("MemTotal: 1000 kB\nMemFree: 100 kB\nCached: 200 kB\n")["used"], 700 * 1024)   # noyau ancien sans MemAvailable
        self.assertEqual(em.arc_taille("c_max 4 99\nsize                            4    8589934592\n"), 8589934592)
        self.assertEqual(em.arc_taille(""), 0)
        st = "1234 (Web Content (x)) S 1 1 1 0 -1 0 0 0 0 0 150 50 0 0 20 0 1 0 100 1000 2500 0"
        self.assertEqual(em.proc_stat(st), ("Web Content (x)", 200, 2500))
        self.assertIsNone(em.proc_stat("garbage"))
        self.assertEqual(em.invite_du_cgroup("12:memory:/lxc/102/ns\n"), "102")
        self.assertEqual(em.invite_du_cgroup("0::/lxc.payload.105/init.scope"), "105")
        self.assertEqual(em.invite_du_cgroup("1:name=systemd:/qemu.slice/100.scope"), "100")
        self.assertIsNone(em.invite_du_cgroup("0::/system.slice/ssh.service"))

    def test_montages(self):
        t = ("rpool/ROOT/pve-1 / zfs rw 0 0\nrpool/data/subvol-102-disk-0 /rpool/data/subvol-102-disk-0 zfs rw 0 0\n"
             "/dev/sda1 /boot/efi vfat rw 0 0\nproc /proc proc rw 0 0\n/dev/sdb1 /mnt/sauve\\040ovh ext4 rw 0 0\n/dev/sdb1 /bind ext4 rw 0 0\n"
             "tmpfs /run tmpfs rw 0 0\nrpool /rpool zfs rw 0 0")
        self.assertEqual(em.montages(t), [("rpool/ROOT/pve-1", "/"), ("/dev/sdb1", "/mnt/sauve ovh"), ("rpool", "/rpool")])
        self.assertEqual(em.nom_invite("arch: amd64\nhostname: med10\nmemory: 8192", "hostname"), "med10")
        self.assertEqual(em.cibles("relais.example.org:9000, 10.0.0.5"), [("relais.example.org", 9000), ("10.0.0.5", 8399)])

    def test_releve_reel(self):
        """Deux relevés sur le /proc de la machine de test : structure complète, pourcentages calculés au second."""
        r = em.Releve("essai")
        a = r.mesurer()
        self.assertIsNone(a["c"])
        x = [i for i in range(200000)]   # un peu de CPU
        time.sleep(0.3)
        b = r.mesurer()
        del x
        self.assertEqual((b["h"], b["s"], b["v"]), ("essai", 2, 1))
        self.assertIsNotNone(b["c"])
        self.assertEqual(len(b["cc"]), b["n"])
        self.assertGreater(b["m"][0], 0)
        self.assertTrue(b["pr"] and all(len(p) >= 4 for p in b["pr"]))
        self.assertLess(len(em.emballer(em.MAGIE, CLE_E, b)), 1400)
        self.assertEqual(rl.deballer(em.emballer(em.MAGIE, CLE_E, b), CLE_E, rl.MAGIE_E)["h"], "essai")


class Relais(unittest.TestCase):
    def setUp(self):
        self.h = Horloge()
        self.r = rl.Relais(CLE_E, CLE_C, {"duree_s": 60}, horloge=self.h)

    def envoyer(self, **kw):
        kw.setdefault("t", self.h.t)
        return self.r.recevoir(em.emballer(em.MAGIE, CLE_E, releve(**kw)), ("192.0.2.10", 40000))

    def test_signature_rejeu_horloge(self):
        self.assertTrue(self.envoyer(s=1))
        self.assertFalse(self.envoyer(s=1))                        # rejeu
        self.assertTrue(self.envoyer(s=1, b="b2"))                 # émetteur redémarré
        p = bytearray(em.emballer(em.MAGIE, CLE_E, releve(t=self.h.t, s=9)))
        p[-1] ^= 1
        self.assertFalse(self.r.recevoir(bytes(p), ("x", 1)))     # altéré
        self.assertFalse(self.r.recevoir(em.emballer(em.MAGIE, b"mauvaise-cle-0123456789", releve(t=self.h.t, s=10)), ("x", 1)))
        self.assertFalse(self.envoyer(s=11, t=self.h.t - 1000))   # horloge
        self.assertFalse(self.envoyer(s=12, h="nom avec espace"))
        self.assertFalse(self.r.recevoir(b"n'importe quoi", ("x", 1)))
        self.assertEqual(self.r.rejets["rejeu"], 1)
        self.assertEqual(self.r.rejets["horloge"], 1)

    def test_constats_soutenus_et_hysteresis(self):
        self.envoyer(s=1, c=95.0)
        self.assertEqual([a["code"] for a in self.r.evaluer() if a["code"].startswith("htop-cpu")], [])   # pas encore 60 s
        self.h.t += 30
        self.envoyer(s=2, c=96.0)
        self.r.evaluer()
        self.h.t += 31
        self.envoyer(s=3, c=99.0)
        cs = {a["code"]: a for a in self.r.evaluer()}
        self.assertEqual(cs["htop-cpu:pve-a"]["severity"], "critical")
        self.assertIn("100 thd (2.0 cœurs)", cs["htop-cpu:pve-a"]["message"])    # plus gros invités nommés
        self.h.t += 2
        self.envoyer(s=4, c=87.0)                                    # sous le seuil mais dans l'hystérésis
        self.assertIn("htop-cpu:pve-a", [a["code"] for a in self.r.evaluer()])
        self.h.t += 2
        self.envoyer(s=5, c=50.0)
        self.assertNotIn("htop-cpu:pve-a", [a["code"] for a in self.r.evaluer()])
        self.h.t += 2
        self.envoyer(s=6, c=95.0)                                    # redépasse : nouveau délai
        self.assertNotIn("htop-cpu:pve-a", [a["code"] for a in self.r.evaluer()])

    def test_memoire_hors_arc_disque_pool_invite_muet(self):
        self.envoyer(s=1, mem=(64e9, 62e9, 10e9), d=[["/", 100, 98]], z=[["rpool", 100, 90, "DEGRADED"]],
                     g=[[102, "med10", "ct", 1.0, 0.1, 8.2e9, 7.9e9, 8e9]])
        self.r.evaluer()                                              # le relais évalue toutes les 2 s
        self.h.t += 61
        self.envoyer(s=2, mem=(64e9, 62e9, 10e9), d=[["/", 100, 98]], z=[["rpool", 100, 90, "DEGRADED"]],
                     g=[[102, "med10", "ct", 1.0, 0.1, 8.2e9, 7.9e9, 8e9]])
        cs = {a["code"]: a for a in self.r.evaluer()}
        self.assertNotIn("htop-memoire:pve-a", cs)                    # 52 / 64 hors ARC : 81 %
        self.assertEqual(cs["htop-disque:pve-a:/"]["severity"], "critical")
        self.assertEqual(cs["htop-pool:pve-a:rpool"]["severity"], "warning")
        self.assertEqual(cs["htop-pool-etat:pve-a:rpool"]["severity"], "critical")
        self.assertIn("med10 à 98.8 %", cs["htop-invite-memoire:pve-a:102"]["message"])
        self.h.t += 45
        cs = {a["code"]: a for a in self.r.evaluer()}
        self.assertIn("htop-muet:pve-a", cs)
        self.assertNotIn("htop-disque:pve-a:/", cs)                   # muet : seul constat de l'hôte
        self.h.t += 86400
        self.r.evaluer()
        self.assertEqual(self.r.hotes, {})                            # oublié après 24 h

    def test_historique_et_pics(self):
        for i in range(130):                                          # 130 relevés à 2 s : 4 à 5 minutes
            self.envoyer(s=i + 1, c=float(i % 50), mem=(100.0, 50.0 + (i % 10), 0))
            self.h.t += 2
        e = self.r.etat()
        h = e["hotes"][0]
        self.assertEqual(h["nom"], "pve-a")
        self.assertGreaterEqual(h["pic_24h"]["minutes"], 3)
        self.assertEqual(h["pic_24h"]["cpu"], 49.0)
        self.assertEqual(h["pic_24h"]["memoire"], 59.0)
        self.assertEqual(h["pics_invites"]["100"], [2.0, 4e9])
        d = self.r.detail("pve-a")
        self.assertEqual(len(d["brut"]), 130)
        self.assertEqual(d["minutes"][-1][0] % 60, 0)
        self.assertIsNone(self.r.detail("absent"))

    def test_persistance(self):
        for i in range(70):
            self.envoyer(s=i + 1)
            self.h.t += 2
        tmp = tempfile.mkdtemp()
        try:
            f = os.path.join(tmp, "e.json")
            self.r.sauver(f)
            r2 = rl.Relais(CLE_E, CLE_C, horloge=self.h)
            self.assertEqual(r2.charger(f), 1)
            self.assertEqual(len(r2.hotes["pve-a"]["minute"]), len(self.r.hotes["pve-a"]["minute"]))
            self.assertEqual(r2.charger(os.path.join(tmp, "absent")), 0)
        finally:
            shutil.rmtree(tmp)

    def test_abonnements_et_paquets(self):
        self.envoyer(s=1)
        self.envoyer(s=1, h="med10", k="ct", g=[], z=[])
        self.assertFalse(self.r.recevoir(cl.emballer(rl.MAGIE_S, CLE_E, {"t": self.h.t}), ("198.51.100.7", 5000)))   # clé émetteur refusée
        self.assertTrue(self.r.recevoir(cl.emballer(rl.MAGIE_S, CLE_C, {"t": self.h.t, "voir": "pve-a"}), ("198.51.100.7", 5000)))
        ps = self.r.paquets_clients()
        objs = [cl.deballer(p, CLE_C, cl.MAGIE_R) for _, p in ps]
        self.assertEqual([o["y"] for o in objs], ["c", "h", "h", "d"])
        self.assertTrue(all(len(p) < 1400 for _, p in ps))
        v = cl.Vue()
        for o in objs:
            v.integrer(o)
        self.assertEqual([(i, h["nom"]) for i, h in v.liste()], [(0, "pve-a"), (1, "med10")])   # CT rangé sous son Proxmox
        self.h.t += 31
        self.assertEqual(self.r.paquets_clients(), [])               # abonnement expiré
        for i in range(rl.MAX_CLIENTS + 2):
            self.r.recevoir(cl.emballer(rl.MAGIE_S, CLE_C, {"t": self.h.t}), ("198.51.100.%d" % i, 5000))
        self.assertEqual(len(self.r.clients), rl.MAX_CLIENTS)


class Client(unittest.TestCase):
    def test_ecrans(self):
        v = cl.Vue()
        self.assertIn("en attente", "".join(t for t, _ in cl.lignes_liste(v, 0, 120)))
        h = rl.Relais(CLE_E, CLE_C).sommaire("pve-a", {"s": releve(c=95.0), "recu": time.time(), "minute": [], "invites": {}}, time.time())
        h["pic_24h"] = {"cpu": 99.0, "cpu_p95": 80.0, "memoire": 50.0}
        v.integrer({"y": "h", "h": h})
        nouveaux = v.integrer({"y": "c", "c": [{"code": "x", "severity": "critical", "message": "pve-a : CPU"}], "n": ["pve-a"]})
        self.assertEqual(len(nouveaux), 1)
        self.assertEqual(v.integrer({"y": "c", "c": [{"code": "x", "severity": "critical", "message": "pve-a : CPU"}], "n": ["pve-a"]}), [])   # déjà signalé
        ls = cl.lignes_liste(v, 0, 140)
        self.assertEqual(ls[1][1], "choix")
        self.assertTrue(ls[1][0].startswith("> pve-a"))
        self.assertIn("!! pve-a : CPU", "".join(t for t, _ in ls))
        self.assertEqual(cl.niveau(h), "alerte")
        h2 = dict(h, processus_top=h.get("processus_top") or releve()["pr"])
        txt = "\n".join(t for t, _ in cl.lignes_detail(h2, 160))
        self.assertIn("med10", txt)
        self.assertIn("mysqld", txt)
        self.assertIn("dont ARC 10.0G", txt)
        self.assertIn("pics 24 h : CPU 99", txt)
        self.assertEqual(cl.barre(50, 10), "|||||     ")
        self.assertEqual(cl.barre(None, 4), "····")
        v.integrer({"y": "c", "c": [], "n": []})
        self.assertEqual(v.hotes, {})                                   # hôte oublié par le relais


class BoutEnBout(unittest.TestCase):
    def test_udp_http(self):
        r = rl.Relais(CLE_E, CLE_C)
        su = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        su.bind(("127.0.0.1", 0))
        srv = rl.serveur_http(r, 0, "jeton-interne")
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        stop = []

        def recevoir():
            su.settimeout(0.2)
            while not stop:
                try:
                    p, a = su.recvfrom(65535)
                    r.recevoir(p, a)
                except socket.timeout:
                    pass
        threading.Thread(target=recevoir, daemon=True).start()
        try:
            e = em.Releve("bout")
            e.mesurer()
            time.sleep(0.2)
            tx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            tx.sendto(em.emballer(em.MAGIE, CLE_E, e.mesurer()), su.getsockname())
            c = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            c.settimeout(2)
            c.sendto(cl.emballer(cl.MAGIE_S, CLE_C, {"t": time.time(), "voir": "bout"}), su.getsockname())
            for _ in range(50):
                if r.hotes and r.clients:
                    break
                time.sleep(0.05)
            for adr, p in r.paquets_clients():
                su.sendto(p, adr)
            v = cl.Vue()
            for _ in range(3):
                v.integrer(cl.deballer(c.recvfrom(65535)[0], CLE_C, cl.MAGIE_R))
            self.assertIn("bout", v.hotes)
            self.assertEqual(v.detail["nom"], "bout")
            port = srv.server_address[1]
            with self.assertRaises(urllib.error.HTTPError):
                urllib.request.urlopen("http://127.0.0.1:%d/etat" % port)
            q = urllib.request.Request("http://127.0.0.1:%d/etat" % port, headers={"X-Htop-Token": "jeton-interne"})
            et = json.loads(urllib.request.urlopen(q).read())
            self.assertEqual([h["nom"] for h in et["hotes"]], ["bout"])
            self.assertEqual(et["abonnes"], 1)
            q = urllib.request.Request("http://127.0.0.1:%d/hote/bout" % port, headers={"X-Htop-Token": "jeton-interne"})
            self.assertEqual(json.loads(urllib.request.urlopen(q).read())["nom"], "bout")
        finally:
            stop.append(1)
            srv.shutdown()


if __name__ == "__main__":
    unittest.main()
