"""Tests de la sonde app-logwatch (#739) : décodage, lecture incrémentale et rotation, catégories (réseau, Winsock,
adresses), constats ; scénario Linux réel (processus « neutrino » qui garde son journal ouvert)."""
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("app_logwatch", os.path.join(HERE, "app_logwatch.py"))
al = importlib.util.module_from_spec(spec); spec.loader.exec_module(al)

LINES = ["2026-10-12 10:00:01 INFO démarrage du serveur GLT",
         "2026-10-12 10:00:05 ERROR Verbindung zu 192.0.2.10:47808 fehlgeschlagen (10060)",
         "2026-10-12 10:00:09 ERROR Verbindung zu 192.0.2.10:47808 fehlgeschlagen (10060)",
         "2026-10-12 10:01:00 Fehler: connexion refusée 192.0.2.11:502 WSAECONNREFUSED 10061",
         "2026-10-12 10:02:00 WARNING base de données lente",
         "2026-10-12 10:03:00 Exception in Modul Alarmierung: NullReference"]


class Logwatch(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.log = os.path.join(self.tmp, "Neutrino.log")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_decode(self):
        self.assertEqual(al.decode_bytes("héllo".encode("utf-16")), "héllo")
        self.assertEqual(al.decode_bytes(("x" * 40 + "é").encode("utf-16-le")), "x" * 40 + "é")
        self.assertEqual(al.decode_bytes("é".encode("cp1252")), "é")

    def test_incremental_and_rotation(self):
        with open(self.log, "w", encoding="utf-8") as fh:
            fh.write("\n".join(LINES) + "\n")
        s, st = al.scan_log(self.log, {}, 1 << 20)
        self.assertTrue(s["first_read"]); self.assertEqual(s["counts"], {"error": 1, "warning": 1, "network": 3})
        self.assertEqual(s["addresses"][0], ("192.0.2.10:47808", 2))
        self.assertEqual({w["code"] for w in s["winsock"]}, {"10060", "10061"})
        self.assertEqual(s["top"][0]["count"], 2)                      # messages regroupés malgré l'horodatage
        s2, st = al.scan_log(self.log, st, 1 << 20)
        self.assertEqual(s2["read_bytes"], 0)                          # rien de nouveau
        with open(self.log, "a", encoding="utf-8") as fh:
            fh.write("2026-10-12 11:00:00 ERROR timeout 192.0.2.12\n")
        s3, st = al.scan_log(self.log, st, 1 << 20)
        self.assertEqual(s3["counts"]["network"], 1)
        with open(self.log, "w", encoding="utf-8") as fh:              # rotation
            fh.write("ERROR nouveau fichier\n")
        s4, _st = al.scan_log(self.log, st, 1 << 20)
        self.assertTrue(s4["rotated"]); self.assertEqual(s4["counts"]["error"], 1)

    def test_findings(self):
        with open(self.log, "w", encoding="utf-8") as fh:
            fh.write("\n".join(LINES) + "\n")
        s, _ = al.scan_log(self.log, {}, 1 << 20)
        f = al.findings([], [{"name": "NeutrinoSrv", "display": "Neutrino Server", "state": "Stopped", "start": "Auto", "pid": 0}],
                        [s], [{"id": 1000, "source": "Application Error", "at": "2026-10-12T10:00:00", "message": "Neutrino.exe"}], ["neutrino"])
        codes = {x["code"] for x in f}
        self.assertEqual(codes, {"process-absent", "service-stopped", "app-crash", "log-network", "log-errors"})
        self.assertIn("10060", next(x for x in f if x["code"] == "log-network")["text"])

    @unittest.skipUnless(sys.platform.startswith("linux"), "scénario /proc")
    def test_linux_process_holding_log(self):
        exe = os.path.join(self.tmp, "neutrino-glt")
        shutil.copy(shutil.which("sleep"), exe)
        with open(self.log, "w", encoding="utf-8") as fh:
            fh.write("\n".join(LINES) + "\n")
        fh = open(self.log, "a")
        p = subprocess.Popen([exe, "30"], stdout=fh)
        try:
            time.sleep(0.3)
            state = os.path.join(self.tmp, "st.json")
            r = subprocess.run([sys.executable, os.path.join(HERE, "app_logwatch.py"), "--match", "neutrino", "--state", state],
                               capture_output=True, text=True, timeout=60)
            d = json.loads(r.stdout)
            self.assertEqual([x["pid"] for x in d["processes"]], [p.pid])
            self.assertIn(self.log, [x["path"] for x in d["open_files"]])
            lg = next(x for x in d["logs"] if x["path"] == self.log)
            self.assertEqual(lg["open_by"], [p.pid]); self.assertEqual(lg["counts"]["network"], 3)
            self.assertTrue(any(a["code"].startswith("log-network@") for a in d["alerts"]))
            self.assertTrue(os.path.exists(state))
        finally:
            p.kill(); fh.close()


if __name__ == "__main__":
    unittest.main()
