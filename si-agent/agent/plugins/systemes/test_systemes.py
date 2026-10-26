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


    def test_hote_ancien_sans_ss_ni_systemctl(self):
        """#865 : Debian 4 (optick3) -- pas de ss, pas de systemctl, dpkg sans db:Status-Abbrev : netstat, rcN.d, ${Status}."""
        with tempfile.TemporaryDirectory() as tmp:
            b = os.path.join(tmp, "bin")
            os.mkdir(b)
            for o in ("hostname", "uname", "cut", "df", "stat", "head", "sed", "awk", "mawk", "gawk", "grep", "sort", "tr", "wc", "cat", "basename"):
                for d in ("/usr/bin", "/bin"):
                    if os.path.exists(os.path.join(d, o)):
                        os.symlink(os.path.join(d, o), os.path.join(b, o))
                        break
            stubs = {
                "apt-get": "true",
                "runlevel": "echo 'N 2'",
                "dpkg-query": "printf '%s\\n' 'install ok installed apache 1.3.34-4.1' 'deinstall ok config-files php4-common 4.4.4' "
                              "'install ok installed php5-common 5.2.0-8' 'install ok installed mysql-server-5.0 5.0.32-7'",
                "netstat": """case "$1" in
-ltnp) printf '%s\\n' 'Active Internet connections (only servers)' 'Proto Recv-Q Send-Q Local Address Foreign Address State PID/Program name' \
  'tcp 0 0 0.0.0.0:80 0.0.0.0:* LISTEN 2203/apache' 'tcp 0 0 127.0.0.1:3306 0.0.0.0:* LISTEN 1987/mysqld' 'tcp 0 0 0.0.0.0:22 0.0.0.0:* LISTEN -' ;;
-ltn) printf '%s\\n' 'tcp 0 0 0.0.0.0:80 0.0.0.0:* LISTEN' 'tcp 0 0 127.0.0.1:3306 0.0.0.0:* LISTEN' ;;
-tn) printf '%s\\n' 'tcp 0 0 192.0.2.40:80 192.0.2.77:51000 ESTABLISHED' 'tcp 0 0 192.0.2.40:80 192.0.2.77:51001 ESTABLISHED' \
  'tcp 0 0 192.0.2.40:42000 192.0.2.5:25 ESTABLISHED' 'tcp 0 0 127.0.0.1:3306 127.0.0.1:40000 ESTABLISHED' ;;
esac""",
            }
            for n, c in stubs.items():
                with open(os.path.join(b, n), "w") as fh:
                    fh.write("#!/bin/sh\n" + c + "\n")
                os.chmod(os.path.join(b, n), 0o755)
            p = subprocess.run(["/bin/sh", "-s"], input=S.INVENTAIRE_SH, capture_output=True, text=True, timeout=60,
                               env={"PATH": b, "LC_ALL": "C"})
            o = S.parse_systeme(p.stdout)
            self.assertEqual(o["paquets"], {"apache": "1.3.34-4.1", "php5-common": "5.2.0-8", "mysql-server-5.0": "5.0.32-7"}, p.stdout)
            self.assertEqual(sorted((e["port"], e["proc"]) for e in o["ecoute"]), [(22, "?"), (80, "apache"), (3306, "mysqld")])
            self.assertEqual(o["cnx_in"], [{"port": 80, "n": 2, "clients": 1}])
            self.assertEqual(o["cnx_out"], [{"hote": "192.0.2.5", "port": 25, "n": 1}])
        o = S.parse_systeme("@@os debian|4|Debian GNU/Linux 4.0\n@@fin")
        self.assertEqual((o["os"]["id"], o["os"]["version"]), ("debian", "4"))

    def test_options_ssh_par_hote(self):
        vu = []
        S._ssh({"host": "192.0.2.40", "ssh_options": ["-o", "HostKeyAlgorithms=+ssh-rsa"]}, "true",
               lambda args, **kw: vu.append(args) or subprocess.CompletedProcess(args, 0, "", ""))
        self.assertIn("HostKeyAlgorithms=+ssh-rsa", vu[0])
        self.assertEqual(vu[0][-2:], ["root@192.0.2.40", "sh -s"])


if __name__ == "__main__":
    unittest.main()
