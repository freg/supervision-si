# -*- coding: utf-8 -*-
import os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from si_agent import vrrpctl
CONF = "global_defs { router_id web }\nvrrp_instance VI_WEB {\n    state BACKUP\n    interface eth0\n    virtual_router_id 51\n    priority 100\n    virtual_ipaddress { 192.0.2.100/24 }\n}\nvrrp_instance VI_DB {\n    priority 90\n}\n"

class Vrrp(unittest.TestCase):
    def test_rewrite(self):
        new, found = vrrpctl.rewrite_priority(CONF, "VI_WEB", 200)
        self.assertTrue(found); self.assertIn("    priority 200\n", new); self.assertIn("priority 90", new); self.assertNotIn("priority 100", new)
        self.assertEqual(vrrpctl.rewrite_priority(CONF, "VI_X", 1), (CONF, False))
        new, _ = vrrpctl.rewrite_priority("vrrp_instance V {\n    state BACKUP\n}\n", "V", 150); self.assertIn("priority 150", new)

    def test_run(self):
        files = {"/etc/keepalived/keepalived.conf": CONF}; cmds = []
        class R: returncode = 0; stdout = ""; stderr = ""
        def cmd(argv, timeout): cmds.append(argv); return R()
        res = vrrpctl.run(cmd, {"instance": "VI_WEB", "priority": 200}, read=lambda p: files[str(p)], write=lambda p, t: files.__setitem__(p, t))
        self.assertTrue(res["ok"], res); self.assertIn("priority 200", files["/etc/keepalived/keepalived.conf"]); self.assertTrue(any(k.startswith("/etc/keepalived/keepalived.conf.bak-") for k in files))
        self.assertEqual(cmds[0][:2], ["keepalived", "-t"]); self.assertEqual(cmds[1], ["systemctl", "reload", "keepalived"])
        self.assertEqual(vrrpctl.run(cmd, {"instance": "x;rm", "priority": 1}, read=lambda p: CONF)["error"], "instance VRRP invalide")
        self.assertEqual(vrrpctl.run(cmd, {"instance": "VI_WEB", "priority": 999}, read=lambda p: CONF)["error"], "priority entre 1 et 254")
        class Bad: returncode = 1; stdout = ""; stderr = "syntax error"
        files2 = {"/etc/keepalived/keepalived.conf": CONF}
        res = vrrpctl.run(lambda a, timeout: Bad(), {"instance": "VI_WEB", "priority": 120}, read=lambda p: files2[str(p)], write=lambda p, t: files2.__setitem__(p, t))
        self.assertFalse(res["ok"]); self.assertIn("restaurée", res["error"]); self.assertIn("priority 100", files2["/etc/keepalived/keepalived.conf"])

if __name__ == "__main__": unittest.main()
