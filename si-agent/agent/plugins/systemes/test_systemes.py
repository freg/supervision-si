# -*- coding: utf-8 -*-
"""Tests #861 : sonde systemes -- relevé Linux (script réel sous sh), Windows (découpage), hôtes distants simulés."""
import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
import systemes as S  # noqa: E402


class Systemes(unittest.TestCase):
    def test_windows(self):
        self.assertEqual(S.windows_os("Microsoft Windows Server 2019 Standard", "10.0.17763"), ("windows-server", "2019"))
        self.assertEqual(S.windows_os("Microsoft Windows Server 2012 R2 Standard", "6.3.9600"), ("windows-server", "2012r2"))
        self.assertEqual(S.windows_os("Microsoft Windows 11 Pro", "10.0.22631"), ("windows", "11"))
        self.assertEqual(S.windows_os("Microsoft Windows 10 Pro", "10.0.19045"), ("windows", "10"))
        o = S.parse_windows("@@os windows|10.0.26100|Microsoft Windows Server 2025 Standard 10.0.26100\n@@maj 1792000000\n"
                            "@@ecoute 445 0.0.0.0 System\n@@cnxout 192.0.2.31 445 3\n@@svc LanmanServer\n@@fin")
        self.assertEqual((o["os"]["id"], o["os"]["version"], o["maj_at"]), ("windows-server", "2025", 1792000000))
        self.assertEqual(o["cnx_out"], [{"hote": "192.0.2.31", "port": 445, "n": 3}])

    def test_local_reel_et_distants(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = os.path.join(tmp, "remote.json")
            with open(r, "w") as fh:
                json.dump([{"name": "nms", "host": "192.0.2.30"}, {"name": "nas", "host": "192.0.2.32", "role": "serveur"}], fh)

            def runner(args, **kw):
                if args[0] == "ssh":
                    if "root@192.0.2.32" in args:
                        return subprocess.CompletedProcess(args, 255, "", "Permission denied (publickey)")
                    return subprocess.CompletedProcess(args, 0, "@@node nms\n@@os debian|9|Debian 9\n@@fin\n", "")
                return subprocess.run(args, **kw)
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                S.main(["--remote", r], runner=runner)
            d = json.loads(out.getvalue())
            loc = d["systemes"][0]
            self.assertTrue(loc["ok"], loc)                       # script réel exécuté sous sh
            self.assertTrue(loc["systeme"]["os"]["id"])
            nms = d["systemes"][1]
            self.assertEqual((nms["name"], nms["systeme"]["os"]["version"], nms["role"]), ("nms", "9", "serveur"))
            self.assertEqual((d["systemes"][2]["ok"], d["systemes"][2]["error"]), (False, "Permission denied (publickey)"))
            self.assertEqual(d["alerts"][0]["code"], "systeme-injoignable:nas")


if __name__ == "__main__":
    unittest.main()
