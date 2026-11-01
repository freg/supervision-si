# -*- coding: utf-8 -*-
"""#751 : récepteur LAN (nœud) et émetteur (poste) -- jeton, reprise par offset, condensé, fermeture."""
import hashlib
import os
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from si_agent import lanpush  # noqa: E402


class LanPushTest(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(); self.got = []
        self.rx = lanpush.Receiver(self.d, "jeton-secret", on_complete=self.got.append, bind="127.0.0.1")
        self.url = "http://127.0.0.1:%d" % self.rx.port

    def tearDown(self):
        self.rx.close()

    def test_flow(self):
        data = os.urandom(300000); sha = hashlib.sha256(data).hexdigest()
        bad = lanpush.Client(self.url, "faux")
        self.assertEqual(bad.request("GET", "/p2v/img.vhdx/status")[0], 403)
        c = lanpush.Client(self.url, "jeton-secret")
        self.assertEqual(c.request("GET", "/p2v/img.vhdx/status"), (200, {"size": 0}))
        self.assertEqual(c.send_raw("PUT", "/p2v/img.vhdx?offset=0", data[:100000])[0], 200)
        st, body = c.send_raw("PUT", "/p2v/img.vhdx?offset=5", data[5:10])
        self.assertEqual((st, body["size"]), (409, 100000))                 # décalage : la source reprend à size
        self.assertEqual(c.request("GET", "/p2v/img.vhdx/status")[1]["size"], 100000)
        # reprise après redémarrage du récepteur : condensé recalculé depuis le .part
        self.rx.close(); self.rx = lanpush.Receiver(self.d, "jeton-secret", on_complete=self.got.append, bind="127.0.0.1"); c = lanpush.Client("http://127.0.0.1:%d" % self.rx.port, "jeton-secret")
        self.assertEqual(c.send_raw("PUT", "/p2v/img.vhdx?offset=100000", data[100000:])[0], 200)
        self.assertEqual(c.request("POST", "/p2v/img.vhdx/complete", {"size": 300000, "sha256": "0" * 64})[0], 409)
        st, body = c.request("POST", "/p2v/img.vhdx/complete", {"size": 300000, "sha256": sha})
        self.assertEqual(st, 200, body); self.assertEqual(body["sha256"], sha)
        with open(os.path.join(self.d, "img.vhdx"), "rb") as fh:
            self.assertEqual(fh.read(), data)
        for _ in range(50):
            if self.got: break
            time.sleep(0.05)
        self.assertEqual(self.got[0]["bytes"], 300000)
        self.assertEqual(c.send_raw("PUT", "/p2v/img.vhdx?offset=300000", b"x")[0], 409)   # clos : plus rien n'est accepté

    def test_guards(self):
        c = lanpush.Client(self.url, "jeton-secret")
        self.assertEqual(c.request("GET", "/p2v/../etc/status")[0], 404)
        self.assertEqual(c.send_raw("PUT", "/p2v/a.img", b"x")[0], 400)            # offset manquant
        self.rx.allow_ip = "192.0.2.9"
        self.assertEqual(c.request("GET", "/p2v/a.img/status")[0], 403)
        self.assertEqual(lanpush.Client("http://127.0.0.1:1", "t").request("GET", "/p2v/a/status")[0], 0)
        self.assertEqual(lanpush.local_ip_towards("127.0.0.1"), "127.0.0.1")


    def test_agent_end_to_end(self):
        """Nœud : start_p2v_receive ouvre le récepteur ; poste : le fil d'envoi pousse l'image (reprise, condensé) ; le
        nœud émet image-fetched."""
        from si_agent import agent as agent_mod, p2vctl
        root = tempfile.mkdtemp(); p2vctl.IMPORT_ROOT = root; imp = os.path.join(root, "p2v-vm301"); os.makedirs(imp)
        events = []

        class Node:
            cfg = {"central_url": "https://127.0.0.1:6443/api/si-agent"}; _p2v_rx = None
            def event(self, kind, sev, msg, det=None): events.append((kind, det))
        node = Node()
        self.assertFalse(agent_mod.Agent.start_p2v_receive(node, {"import_dir": "/etc"})["ok"])
        r = agent_mod.Agent.start_p2v_receive(node, {"import_dir": imp, "lan_ip": "127.0.0.1", "port": 0, "source_ip": "127.0.0.1"})
        self.assertTrue(r["ok"], r); self.assertTrue(r["url"].startswith("http://127.0.0.1:"))
        try:
            src = os.path.join(tempfile.mkdtemp(), "poste.vhdx"); data = os.urandom(5 * 2**20 + 7)
            with open(src, "wb") as fh:
                fh.write(data)

            class Poste:
                agent_id = "poste"; _upload_bwlimit = 0; http = None
            job = {"path": src, "name": "poste.vhdx", "total": len(data), "sent": 0, "state": "running", "error": None,
                   "push": agent_mod.Agent._push_target({"push_url": r["url"], "push_token": r["token"]})}
            self.assertIsNone(agent_mod.Agent._push_target({"push_url": "file:///etc/passwd", "push_token": "x"}))
            agent_mod.Agent._upload_worker(Poste(), job)
            self.assertEqual(job["state"], "finished", job.get("error"))
            with open(os.path.join(imp, "poste.vhdx"), "rb") as fh:
                self.assertEqual(hashlib.sha256(fh.read()).hexdigest(), hashlib.sha256(data).hexdigest())
            for _ in range(50):
                if any(k == "image-fetched" for k, _ in events): break
                time.sleep(0.05)
            fetched = [d for k, d in events if k == "image-fetched"][0]
            self.assertEqual((fetched["bytes"], fetched["source"]), (len(data), "lan"))
        finally:
            node._p2v_rx and node._p2v_rx.close()


if __name__ == "__main__":
    unittest.main()
