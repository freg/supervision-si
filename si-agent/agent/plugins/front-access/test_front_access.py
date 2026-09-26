import json, os, subprocess, sys, tempfile, time, unittest
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import front_access as fa

def line(ip, path, status, ts="25/Sep/2026:14:03:12 +0200", ua="Mozilla/5.0 Firefox/130", us=None, b="512"):
    return '%s - - [%s] "GET %s HTTP/1.1" %s %s "-" "%s"%s' % (ip, ts, path, status, b, ua, (" %d" % us) if us is not None else "")

class FrontAccessTests(unittest.TestCase):
    def test_parse(self):
        e = fa.parse_line(line("203.0.113.9", "/api/si-agent/fleet", 401, us=12500))
        self.assertEqual((e["ip"], e["path"], e["status"], e["ms"], e["bytes"]), ("203.0.113.9", "/api/si-agent/fleet", 401, 12.5, 512))
        self.assertAlmostEqual(e["t"], 1790337792.0, delta=1)
        self.assertIsNone(fa.parse_line("n'importe quoi"))
        self.assertEqual(fa.parse_line(line("1.2.3.4", "/", 200, us=None))["ms"], None)
        self.assertEqual(fa.ua_family("curl/8"), "curl"); self.assertEqual(fa.ua_family("Mozilla/5.0 Chrome/1 Safari/1"), "Chrome")

    def test_summary_constats(self):
        now = 1790337792.0 + 60
        rows = [fa.parse_line(line("198.51.100.5", "/", 200, us=200000)), fa.parse_line(line("198.51.100.5", "/api/x", 200, us=4_500_000))]
        rows += [fa.parse_line(line("203.0.113.9", "/api/si-agent/fleet", 401)) for _ in range(25)]
        rows += [fa.parse_line(line("203.0.113.9", "/api/y", 200))]
        rows += [fa.parse_line(line("192.0.2.77", "/wp-login.php", 404)) for _ in range(40)]
        rows += [fa.parse_line(line("198.51.100.5", "/auth/realms/x", 502)) for _ in range(6)]
        rows += [fa.parse_line(line("9.9.9.9", "/old", 200, ts="25/Sep/2026:10:00:00 +0200"))]  # hors fenêtre
        s = fa.summarize(rows, now=now, slow_s=3, window_minutes=60)
        self.assertEqual(s["total"], 74); self.assertEqual(s["status"]["401"], 25); self.assertEqual(s["status"]["5xx"], 6)
        codes = {f["code"] for f in s["findings"]}
        self.assertEqual(codes, {"hub-unreachable", "auth-refused-burst", "scan-404"})
        self.assertEqual(s["summary"]["state"], "critical"); self.assertEqual(s["api_auth_refused"], 25)
        self.assertEqual(s["clients"][0]["ip"], "192.0.2.77"); self.assertEqual(s["latency"]["max_ms"], 4500.0)
        self.assertEqual(s["slow"][0]["ms"], 4500.0); self.assertEqual(len(s["errors_5xx"]), 6)

    def test_cli(self):
        d = tempfile.mkdtemp(); p = os.path.join(d, "hub-x-access.log")
        with open(p, "w") as fh:
            fh.write(line("1.1.1.1", "/", 200, ts=time.strftime("%d/%b/%Y:%H:%M:%S +0000", time.gmtime())) + "\n")
        r = subprocess.run([sys.executable, os.path.join(HERE, "front_access.py"), "--log", os.path.join(d, "hub-*-access.log")], capture_output=True, text=True, timeout=30)
        out = json.loads(r.stdout); self.assertEqual(out["total"], 1); self.assertEqual(out["files"], [p])
        r = subprocess.run([sys.executable, os.path.join(HERE, "front_access.py"), "--log", "/nonexistent/*.log"], capture_output=True, text=True, timeout=30)
        self.assertIn("aucun journal", json.loads(r.stdout)["error"])

if __name__ == "__main__":
    unittest.main()
