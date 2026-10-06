# -*- coding: utf-8 -*-
"""Tests #688 : vulnérabilités du SI -- SBOM syft réel, rapport osv-scanner bâti
sur un avis OSV réel (GHSA), extraits EPSS/KEV au format réel."""
import io
import json
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
FX = os.path.join(HERE, "fixtures")
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(HERE, "..", "..", "shared"))
TMP = tempfile.mkdtemp()
os.environ.update(VULN_DATA_DIR=TMP, VULN_FEEDS_THREAD="0", DT_URL="", DT_API_KEY="")
import vulnlib  # noqa: E402
import app as app_mod  # noqa: E402


def fx(name, mode="r"):
    with open(os.path.join(FX, name), mode) as fh:
        return fh.read()


class Lib(unittest.TestCase):
    def test_epss(self):
        scores, meta = vulnlib.parse_epss(fx("epss.csv.gz", "rb"))
        self.assertEqual(meta["model_version"], "v2025.03.14")
        self.assertEqual(scores["CVE-2018-18074"], (0.62, 0.991))
        self.assertEqual(vulnlib.parse_epss("cve,epss,percentile\nCVE-1-1,x,y\n")[0], {})

    def test_kev(self):
        kev, meta = vulnlib.parse_kev(fx("kev.json"))
        self.assertEqual(meta["count"], 4)
        self.assertTrue(kev["CVE-2018-18074"]["ransomware"])

    def test_cvss3(self):
        self.assertEqual(vulnlib.cvss3_base("CVSS:3.0/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:N/A:N"), 8.6)
        self.assertEqual(vulnlib.cvss3_base("CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H"), 9.8)
        self.assertEqual(vulnlib.cvss3_base("CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:C/C:H/I:H/A:H"), 9.9)
        self.assertEqual(vulnlib.cvss3_base("CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:N"), 0.0)
        self.assertIsNone(vulnlib.cvss3_base("n'importe quoi"))

    def test_sbom_syft(self):
        comps = vulnlib.sbom_components(fx("sample.cdx.json"))
        self.assertEqual(sorted(c["purl"] for c in comps), ["pkg:pypi/flask@0.12", "pkg:pypi/jinja2@2.10", "pkg:pypi/requests@2.19.0"])

    def test_osv(self):
        f = {x["package"]: x for x in vulnlib.osv_findings(fx("osv-report.json"))}
        j = f["jinja2"]
        self.assertEqual((j["cves"], j["score"], j["score_source"], j["fixed"]), (["CVE-2019-10906"], 8.6, "osv", ["2.10.1"]))
        self.assertEqual(j["ids"], ["GHSA-462w-v97r-4m45", "PYSEC-2019-217"])
        r = f["requests"]
        self.assertEqual((r["cves"], r["score"], r["score_source"], r["fixed"]), (["CVE-2018-18074"], 7.5, "label", ["2.20.0"]))
        self.assertEqual(vulnlib.osv_findings(""), [])

    def test_priorites(self):
        base = {"cves": ["CVE-1"], "score": 5.0, "fixed": []}
        P = lambda e=None, k=None, exp=False, score=5.0: vulnlib.prioritize(dict(base, score=score), {"CVE-1": e} if e else {}, {"CVE-1": k} if k else {}, exp)["priority"]
        self.assertEqual(P(k={"added": "2026-01-01"}), "P1")                 # KEV, même interne
        self.assertEqual(P(e=(0.6, 0.99), exp=True), "P1")
        self.assertEqual(P(e=(0.6, 0.99)), "P2")                             # interne : P2
        self.assertEqual(P(e=(0.001, 0.96)), "P2")                           # centile
        self.assertEqual(P(score=9.8, exp=True), "P2")
        self.assertEqual(P(score=9.8), "P3")
        self.assertEqual(P(e=(0.02, 0.5)), "P3")
        self.assertEqual(P(), "P4")
        p = vulnlib.prioritize(dict(base, fixed=["1.2"]), {"CVE-1": (0.2, 0.97)}, {}, True)
        self.assertIn("EPSS 20.0 %", p["reason"]); self.assertIn("corrigée en 1.2", p["reason"]); self.assertIn("exposé", p["reason"])


class Api(unittest.TestCase):
    def setUp(self):
        self.c = app_mod.app.test_client()
        feeds = {app_mod.EPSS_URL: fx("epss.csv.gz", "rb"), app_mod.KEV_URLS[1].strip(): fx("kev.json", "rb")}

        def get(url, timeout=120):
            if url not in feeds:
                raise OSError("injoignable")
            return feeds[url]
        app_mod.http_get = get
        self.calls = []

        def tool(argv, timeout=900):
            self.calls.append(argv)
            if argv[0] == app_mod.OSV_BIN:
                with open(argv[argv.index("--output-file") + 1], "w") as fh:
                    fh.write(fx("osv-report.json"))
                return 1, "", ""
            return 0, fx("sample.cdx.json"), ""
        app_mod.run_tool = tool

    def test_chaine_complete(self):
        r = self.c.post("/sbom?asset=srv-alpha&kind=host&exposed=1", data=fx("sample.cdx.json"))
        self.assertEqual(r.status_code, 201, r.get_json())
        self.assertEqual(r.get_json()["findings"], 2)
        self.assertTrue(self.calls[0][self.calls[0].index("-L") + 1].endswith("srv-alpha.cdx.json"))
        # sans flux : priorités par CVSS seul
        self.assertEqual({f["package"]: f["priority"] for f in self.c.get("/findings?asset=srv-alpha").get_json()}, {"jinja2": "P3", "requests": "P3"})
        # flux : CISA injoignable -> miroir ; requests devient KEV (fixture) -> P1
        res = self.c.post("/feeds/refresh").get_json()
        self.assertEqual(res["kev"]["count"], 4); self.assertEqual(res["epss"]["count"], 3)
        fs = {f["package"]: f for f in self.c.get("/findings?asset=srv-alpha").get_json()}
        self.assertEqual(fs["requests"]["priority"], "P1"); self.assertTrue(fs["requests"]["kev"])
        self.assertEqual(fs["jinja2"]["priority"], "P3"); self.assertAlmostEqual(fs["jinja2"]["epss"], 0.01234)
        s = self.c.get("/summary").get_json()
        self.assertEqual((s["P1"], s["kev"], s["assets"], s["exposed_assets"]), (1, 1, 1, 1))
        self.assertEqual(self.c.get("/epss/cve-2021-44228").get_json()["epss"], 0.944)
        # nouveau dépôt : première apparition conservée
        first = fs["jinja2"]["first_seen"]
        self.c.post("/sbom?asset=srv-alpha", data=fx("sample.cdx.json"))
        self.assertEqual({f["package"]: f["first_seen"] for f in self.c.get("/findings?asset=srv-alpha").get_json()}["jinja2"], first)
        self.assertEqual(self.c.patch("/assets/srv-alpha", json={"exposed": False}).status_code, 200)
        self.assertFalse(self.c.get("/assets").get_json()[0]["exposed"])

    def test_refus(self):
        self.assertEqual(self.c.post("/sbom?asset=", data="{}").status_code, 400)
        self.assertEqual(self.c.post("/sbom?asset=x&kind=nope", data="{}").status_code, 400)
        self.assertEqual(self.c.post("/sbom?asset=x", data='{"spdxVersion": "SPDX-2.3"}').status_code, 400)

    def test_echec_osv(self):
        app_mod.run_tool = lambda argv, timeout=900: (2, "", "fatal: base indisponible")
        r = self.c.post("/sbom?asset=srv-beta", data=fx("sample.cdx.json")).get_json()
        self.assertIn("base indisponible", r["scan_error"])

    def test_scan_self(self):
        d = tempfile.mkdtemp(); app_mod.SELF_SCAN_DIR = d
        r = self.c.post("/scan/self")
        self.assertEqual(r.status_code, 201, r.get_json())
        self.assertEqual(self.calls[0][:3], [app_mod.SYFT_BIN, "scan", "dir:%s" % d])


if __name__ == "__main__":
    unittest.main()
