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


class MultiPlateforme711(unittest.TestCase):
    def test_windows_zip_et_exclusions(self):
        import zipfile
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("LICENSE", "Apache"); z.writestr("syft.exe", b"MZ...")
        data = buf.getvalue()
        name = "syft_%s_windows_amd64.zip" % sc.SYFT_VERSION
        base = sc.RELEASES % {"v": sc.SYFT_VERSION}
        files = {base + name: data, base + "syft_%s_checksums.txt" % sc.SYFT_VERSION: ("%s  %s\n" % (hashlib.sha256(data).hexdigest(), name)).encode()}
        d = tempfile.mkdtemp()
        p = sc.install_syft(lambda url: files[url], d, cpu="amd64", system="windows")
        self.assertEqual(os.path.basename(p), "syft.exe"); self.assertEqual(open(p, "rb").read(), b"MZ...")
        self.assertEqual(sc.find_syft(d, lambda b: None, "windows"), p)
        self.assertIn("./Windows/WinSxS/**", sc.excludes_for("windows")); self.assertIn("./System/Volumes/**", sc.excludes_for("darwin"))
        self.assertTrue(sc.default_root("windows").endswith("\\")); self.assertEqual(sc.default_root("darwin"), "/")
        argv = sc.scan_argv("syft.exe", "C:\\", sc.excludes_for("windows"), which=lambda b: None)
        self.assertEqual(argv[:3], ["syft.exe", "scan", "dir:C:\\"]); self.assertIn("./pagefile.sys", argv)

    def test_logiciels_installes(self):
        out, n = sc.add_installed(BOM, [{"name": "openssl", "version": "1.1.0l-1~deb9u6"}, {"name": "7-Zip", "version": "23.01", "publisher": "Igor Pavlov", "source": "registry"},
                                        {"name": "7-zip", "version": "23.01"}, {"name": ""}])
        self.assertEqual(n, 1)
        c = json.loads(out)["components"][-1]
        self.assertEqual((c["type"], c["name"], c["version"], c["publisher"], c["properties"][0]["value"]), ("application", "7-Zip", "23.01", "Igor Pavlov", "registry"))
        self.assertEqual(sc.summarize(out)["components"], 5)

    def test_images_docker(self):
        calls, sent = [], []

        def runner(argv, timeout=3600):
            calls.append(argv)
            if argv[:2] == ["docker", "ps"]:
                return 0, b"nginx:1.25\nregistry.exemple/app:2\nnginx:1.25\nbad image\n", ""
            if "docker:registry.exemple/app:2" in argv:
                return 1, b"", "error: image introuvable\n"
            return 0, BOM, ""

        def upload(gz, kind="host", name=None):
            sent.append((kind, name)); return 201, {"findings": 3}
        self.assertEqual(sc.docker_images(runner, which=lambda b: None), [])
        r = sc.inventory(upload, runner=runner, tools_dir=tempfile.mkdtemp(), which=lambda b: "/usr/bin/" + b, system="linux", images=True)
        self.assertTrue(r["ok"], r)
        self.assertEqual(sent, [("host", None), ("image", "nginx:1.25")])
        self.assertEqual([(i["name"], i["ok"]) for i in r["images"]], [("nginx:1.25", True), ("registry.exemple/app:2", False)])
        self.assertEqual(r["images"][0]["findings"], 3)
        scan = [a for a in calls if "docker:nginx:1.25" in a][0]
        self.assertNotIn("--exclude", scan)
        r = sc.inventory(lambda gz: (201, {}), runner=runner, tools_dir=tempfile.mkdtemp(), which=lambda b: "/usr/bin/" + b, system="windows",
                         installed=[{"name": "Firefox", "version": "131.0"}])
        self.assertEqual((r["installed_added"], r["images"]), (1, []))


if __name__ == "__main__":
    unittest.main()
