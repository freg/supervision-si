"""#748 : virtualisation directe -- calculs de p2vctl, relais à fenêtre du central (imagestore) : refus 429 quand la cible
n'a pas suivi, lecture au fil de l'eau, perforation de ce qui est lu, clôture sans condensé côté central, fichier supprimé
quand la cible a tout ; boucle complète source -> relais -> cible avec condensé vérifié."""
import hashlib
import os
import tempfile
import unittest

from si_agent import imagestore, p2vctl

STORAGE_CFG = """dir: local
\tpath /var/lib/vz
\tcontent iso,vztmpl,backup

lvmthin: local-lvm
\tthinpool data
\tvgname pve
\tcontent rootdir,images
"""


class Calculs(unittest.TestCase):
    def test_tailles_et_choix(self):
        self.assertEqual(p2vctl.lv_size_gb(68 * 2**30), 84)                   # 68 Go + 15 % -> 79 + 5
        need = 60 * 2**30
        cands = [{"path": "C:\\", "free": 100 * 2**30}, {"path": "D:\\", "free": 80 * 2**30}, {"path": "E:\\", "free": 20 * 2**30}]
        t, rows = p2vctl.choose_source_target(need, cands, "C:\\")
        self.assertEqual(t, "D:\\")                                          # hors volume système d'abord
        t, _ = p2vctl.choose_source_target(need, cands[:1] + cands[2:], "C:\\")
        self.assertEqual(t, "C:\\")                                          # système en dernier recours
        t, _ = p2vctl.choose_source_target(need, cands, "C:\\", given="E:\\")
        self.assertIsNone(t)                                                 # cible donnée trop petite : refus, pas d'autre choix silencieux
        self.assertIsNone(p2vctl.choose_source_target(need, [{"path": "E:\\", "free": 1}], "C:\\")[0])

    def test_proxmox(self):
        cfg = p2vctl.parse_storage_cfg(STORAGE_CFG, "local-lvm")
        self.assertEqual((cfg["type"], cfg["vgname"], cfg["thinpool"]), ("lvmthin", "pve", "data"))
        self.assertIsNone(p2vctl.parse_storage_cfg(STORAGE_CFG, "absent"))
        self.assertEqual(p2vctl.thin_free("  1759218604441 10,51\n"), int(1759218604441 * 0.8949))
        self.assertIsNone(p2vctl.thin_free(""))
        lv, mnt, argv = p2vctl.target_argv("pve", "data", "vm300", 84)
        self.assertEqual(lv, "p2v-vm300"); self.assertEqual(mnt, "/var/lib/vz/import/p2v-vm300")
        self.assertEqual(argv[0], ["lvcreate", "-y", "-V", "84G", "-T", "pve/data", "-n", "p2v-vm300"])
        self.assertEqual(p2vctl.cleanup_argv("pve", "vm300")[1], ["lvremove", "-y", "pve/p2v-vm300"])
        self.assertFalse(p2vctl.JOB_RE.match("../x")); self.assertTrue(p2vctl.JOB_RE.match("vm300"))
        self.assertEqual(p2vctl.throttle_sleep(125_000_000, 0.5, 1000), 0.5)  # 1 Gbit en 0,5 s à 1000 Mbit/s : attendre 0,5 s
        self.assertEqual(p2vctl.throttle_sleep(10, 5, 0), 0.0)

    def test_montages_linux(self):
        txt = "/dev/sda1 / ext4 rw 0 0\nproc /proc proc rw 0 0\n/dev/sdb1 /mnt/img xfs rw 0 0\ntmpfs /run tmpfs rw 0 0\n"
        rows = p2vctl.linux_mounts(txt, usage=lambda p: type("U", (), {"free": 5, "total": 9})())
        self.assertEqual([r["path"] for r in rows], ["/", "/mnt/img"])


class Relais(unittest.TestCase):
    def setUp(self):
        self.st = imagestore.ImageStore(tempfile.mkdtemp())

    def test_fenetre_lecture_cloture(self):
        st, data = self.st, os.urandom(3 * 1024 * 1024 + 123)
        self.assertEqual(st.relay_read("src", "pve", 0)[0], 404)
        st.relay_open("src", "pve", window=1024 * 1024)
        code, hdr, _ = st.relay_read("src", "pve", 0)
        self.assertEqual((code, hdr["X-Relay-Name"]), (204, ""))              # rien d'envoyé encore
        self.assertEqual(st.relay_read("src", "autre", 0)[0], 403)
        chunk = 512 * 1024
        pos, got, h = 0, b"", hashlib.sha256()
        blocked = 0
        while pos < len(data) or len(got) < len(data):
            if pos < len(data):
                code, out = st.append("src", "img.vhdx", pos, data[pos:pos + chunk])
                if code == 201:
                    pos += len(data[pos:pos + chunk])
                else:
                    self.assertEqual(code, 429); blocked += 1               # la cible n'a pas suivi : la source attend
            if pos >= len(data) and not st.relay_get("src")["complete"]:
                self.assertEqual(st.complete("src", "img.vhdx", len(data), hashlib.sha256(data).hexdigest())[0], 200)
            code, hdr, buf = st.relay_read("src", "pve", len(got), max_bytes=256 * 1024)
            got += buf
        self.assertGreater(blocked, 0)
        self.assertEqual(got, data)
        code, hdr, buf = st.relay_read("src", "pve", len(got))
        self.assertEqual((code, hdr["X-Relay-Complete"], hdr["X-Relay-Sha256"]), (204, "1", hashlib.sha256(data).hexdigest()))
        self.assertTrue(st.relay_get("src")["done"])
        self.assertFalse(os.path.exists(os.path.join(st.root, "src", "img.vhdx")))   # plus rien au central
        self.assertEqual(st.list(), [])                                               # .relay.json masqué

    def test_perforation(self):
        st = self.st
        st.relay_open("s2", "pve", window=64 * 2**20)
        data = b"x" * (8 * 2**20)
        self.assertEqual(st.append("s2", "big", 0, data)[0], 201)
        st.relay_read("s2", "pve", 0)
        st.relay_read("s2", "pve", 8 * 2**20)                                        # tout lu : perforé
        path = os.path.join(st.root, "s2", "big.part")
        self.assertEqual(os.path.getsize(path), 8 * 2**20)                            # taille logique conservée (reprise)
        if imagestore.punch_hole(os.open(path, os.O_RDWR), 0, 0):
            self.assertLess(os.stat(path).st_blocks * 512, 8 * 2**20)                 # blocs libérés (si le système le permet)

    def test_hors_relais_inchange(self):
        st = self.st
        self.assertEqual(st.append("x", "a", 0, b"abc")[0], 201)
        self.assertEqual(st.complete("x", "a", 3, hashlib.sha256(b"abc").hexdigest())[0], 200)


class LectureCible(unittest.TestCase):
    """Boucle de lecture de l'agent cible (Agent.start_p2v_fetch) contre le relais réel, client HTTP simulé."""
    def test_fetch(self):
        import threading
        import time as _t
        from si_agent import agent as agent_mod
        root = tempfile.mkdtemp(); p2vctl.IMPORT_ROOT = os.path.join(root, "import"); imp = os.path.join(p2vctl.IMPORT_ROOT, "p2v-vm300")
        os.makedirs(imp)
        st = imagestore.ImageStore(os.path.join(root, "central"))
        data = os.urandom(2 * 2**20 + 77)
        events = []

        class Http:
            def get_raw_signed(self, path, timeout=120):
                q = dict(kv.split("=") for kv in path.split("?", 1)[1].split("&"))
                if not st.relay_get("src"):
                    st.relay_open("src", "pve", int(float(q["window_gb"]) * 2**30))
                code, hdr, buf = st.relay_read("src", "pve", int(q["offset"]), 512 * 1024)
                return code, hdr, buf

        fake = type("F", (), {})()
        fake.http, fake.agent_id, fake.clock, fake._fetch_job = Http(), "pve", _t.time, None
        fake.event = lambda kind, sev, msg, det=None: events.append((kind, det))
        _sleep = agent_mod.time.sleep
        agent_mod.time.sleep = lambda n: _sleep(min(n, 0.01))
        try:
            r = agent_mod.Agent.start_p2v_fetch(fake, {"source_agent": "src", "import_dir": imp, "window_gb": 0.001})
            self.assertTrue(r["ok"], r)
            self.assertFalse(agent_mod.Agent.start_p2v_fetch(fake, {"source_agent": "src", "import_dir": "/etc"})["ok"])
            def source():
                pos = 0
                while pos < len(data):
                    code, _ = st.append("src", "img.vhdx", pos, data[pos:pos + 256 * 1024])
                    if code == 201:
                        pos += len(data[pos:pos + 256 * 1024])
                    else:
                        _sleep(0.005)
                st.complete("src", "img.vhdx", len(data), hashlib.sha256(data).hexdigest())
            threading.Thread(target=source, daemon=True).start()
            for _ in range(800):
                if fake._fetch_job["state"] != "running":
                    break
                _sleep(0.01)
            self.assertEqual(fake._fetch_job["state"], "finished", fake._fetch_job.get("error"))
            with open(os.path.join(imp, "img.vhdx"), "rb") as fh:
                self.assertEqual(fh.read(), data)
            for _ in range(100):
                if any(k == "image-fetched" for k, _d in events):
                    break
                _sleep(0.02)
        finally:
            agent_mod.time.sleep = _sleep
        self.assertEqual([d["path"] for k, d in events if k == "image-fetched"], [os.path.join(imp, "img.vhdx")])


if __name__ == "__main__":
    unittest.main()
