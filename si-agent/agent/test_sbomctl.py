# -*- coding: utf-8 -*-
"""Tests #699 : inventaire logiciel de l'hôte (syft) envoyé au central."""
import gzip
import hashlib
import io
import json
import os
import sys
import tarfile
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from si_agent import sbomctl as sc  # noqa: E402

BOM = json.dumps({"bomFormat": "CycloneDX", "specVersion": "1.6", "components": [
    {"type": "library", "name": "openssl", "version": "1.1.0l-1~deb9u6", "purl": "pkg:deb/debian/openssl@1.1.0l-1~deb9u6"},
    {"type": "library", "name": "libc6", "version": "2.24-11+deb9u4", "purl": "pkg:deb/debian/libc6@2.24-11+deb9u4"},
    {"type": "library", "name": "requests", "version": "2.19.0", "purl": "pkg:pypi/requests@2.19.0"},
    {"type": "operating-system", "name": "debian", "version": "9.13"}]}).encode()


def release(binary=b"#!/bin/sh\necho syft\n", tamper=False):
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for name, data in (("LICENSE", b"Apache"), ("syft", binary)):
            ti = tarfile.TarInfo(name); ti.size = len(data); ti.mode = 0o755
            tar.addfile(ti, io.BytesIO(data))
    data = buf.getvalue()
    name = "syft_%s_linux_amd64.tar.gz" % sc.SYFT_VERSION
    digest = hashlib.sha256(data + (b"x" if tamper else b"")).hexdigest()
    sums = "%s  syft_%s_linux_arm64.tar.gz\n%s  %s\n" % ("0" * 64, sc.SYFT_VERSION, digest, name)
    files = {sc.RELEASES % {"v": sc.SYFT_VERSION} + name: data, sc.RELEASES % {"v": sc.SYFT_VERSION} + "syft_%s_checksums.txt" % sc.SYFT_VERSION: sums.encode()}
    return lambda url: files[url]


class Syft(unittest.TestCase):
    def test_installation_verifiee(self):
        d = tempfile.mkdtemp()
        p = sc.install_syft(release(), d, cpu="amd64")
        self.assertEqual(p, os.path.join(d, "syft")); self.assertTrue(os.access(p, os.X_OK))
        self.assertEqual(sc.find_syft(d, which=lambda b: None), p)
        with self.assertRaises(RuntimeError) as ctx:
            sc.install_syft(release(tamper=True), tempfile.mkdtemp(), cpu="amd64")
        self.assertIn("SHA-256", str(ctx.exception))

    def test_commande(self):
        argv = sc.scan_argv("/opt/syft", which=lambda b: "/usr/bin/" + b)
        self.assertEqual(argv[:5], ["nice", "-n", "19", "ionice", "-c"])
        i = argv.index("/opt/syft")
        self.assertEqual(argv[i:i + 5], ["/opt/syft", "scan", "dir:/", "-o", "cyclonedx-json"])
        for zone in ("./var/vmail/**", "./var/lib/vz/**", "./proc/**", "./var/lib/docker/**"):
            self.assertIn(zone, argv)
        self.assertEqual(sc.scan_argv("syft", which=lambda b: None)[0], "syft")


class Inventaire(unittest.TestCase):
    def test_envoi(self):
        sent = []
        r = sc.inventory(lambda gz: (sent.append(gz), (201, {"asset": "mx-alpha", "findings": 7}))[1],
                         runner=lambda argv: (0, BOM, ""), tools_dir=tempfile.mkdtemp(), which=lambda b: "/usr/bin/syft" if b == "syft" else None)
        self.assertTrue(r["ok"], r)
        self.assertEqual((r["components"], r["by_type"]), (4, {"deb": 2, "pypi": 1, "operating-system": 1}))
        self.assertEqual(gzip.decompress(sent[0]), BOM); self.assertEqual(r["central"]["findings"], 7)

    def test_echecs(self):
        none = dict(tools_dir=tempfile.mkdtemp(), which=lambda b: None)
        r = sc.inventory(lambda gz: (201, {}), **none)
        self.assertFalse(r["ok"]); self.assertIn("syft absent", r["error"])
        r = sc.inventory(lambda gz: (201, {}), runner=lambda argv: (1, b"", "error: permission denied\n"), tools_dir=tempfile.mkdtemp(), which=lambda b: "/usr/bin/" + b)
        self.assertIn("permission denied", r["error"])
        r = sc.inventory(lambda gz: (413, {"error": "trop gros"}), runner=lambda argv: (0, BOM, ""), tools_dir=tempfile.mkdtemp(), which=lambda b: "/usr/bin/" + b)
        self.assertFalse(r["ok"]); self.assertIn("413", r["error"])
        # installation à la demande puis inventaire
        d = tempfile.mkdtemp()
        old = sc.arch
        sc.arch = lambda: "amd64"
        try:
            if sys.platform.startswith("linux"):
                r = sc.inventory(lambda gz: (201, {}), fetch=release(), runner=lambda argv: (0, BOM, ""), tools_dir=d, install=True, which=lambda b: None)
                self.assertTrue(r["ok"], r); self.assertTrue(os.path.exists(os.path.join(d, "syft")))
        finally:
            sc.arch = old

    def test_echeance(self):
        self.assertFalse(sc.due({}, 1e9))
        self.assertTrue(sc.due({"sbom_schedule_days": 7}, 1e9))
        self.assertFalse(sc.due({"sbom_schedule_days": 7, "sbom_last_at": 1e9 - 86400}, 1e9))
        self.assertTrue(sc.due({"sbom_schedule_days": 1, "sbom_last_at": 1e9 - 86400}, 1e9))


if __name__ == "__main__":
    unittest.main()
