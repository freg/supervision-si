# -*- coding: utf-8 -*-
import hashlib
import os
import tempfile
import unittest

import package


class PackageTests(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.p = os.path.join(self.d, "si-agent-agent-0.4.3.tar.gz")
        with open(self.p, "wb") as fh:
            fh.write(b"x" * 1000)

    def test_find_et_info(self):
        self.assertEqual(package.find_package(self.d), self.p)
        info = package.package_info(self.p)
        self.assertEqual(info["name"], "si-agent-agent-0.4.3.tar.gz")
        self.assertEqual(info["version"], "0.4.3")
        self.assertEqual(info["size"], 1000)
        self.assertEqual(info["sha256"], hashlib.sha256(b"x" * 1000).hexdigest())
        self.assertIsNone(package.find_package(tempfile.mkdtemp()))
        self.assertIsNone(package.package_info(None))

    def test_plus_recente_version(self):
        with open(os.path.join(self.d, "si-agent-agent-0.4.10.tar.gz"), "wb") as fh:
            fh.write(b"y")
        # tri lexicographique : 0.4.10 < 0.4.3 -- une seule archive à la fois dans l'image, on documente
        self.assertTrue(package.find_package(self.d).endswith(".tar.gz"))

    def test_download_command(self):
        info = package.package_info(self.p)
        cmd = package.download_command("https://198.51.100.10:6443/api/si-agent/", info)
        self.assertIn("curl -fsSk -o si-agent-agent-0.4.3.tar.gz https://198.51.100.10:6443/api/si-agent/package", cmd)
        self.assertIn("| sha256sum -c && tar xzf si-agent-agent-0.4.3.tar.gz && cd si-agent-agent-0.4.3", cmd)
        self.assertIn(info["sha256"], cmd)
        self.assertIsNone(package.download_command("https://x", None))


if __name__ == "__main__":
    unittest.main()
