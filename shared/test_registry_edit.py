# -*- coding: utf-8 -*-
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import registry_edit as re_  # noqa: E402


class Registry(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.ex = os.path.join(self.d, "routers.json")
        self.local = os.path.join(self.d, "routers.local.json")
        json.dump({"routers": [{"name": "exemple", "host": "192.0.2.1", "credential": "default"}]}, open(self.ex, "w"))

    def test_read_upsert_write(self):
        items, src = re_.read_items(self.local, self.ex, "routers")
        self.assertEqual((src, len(items)), ("exemple", 1))
        entry, errs = re_.validate_common({"name": "rb", "host": "192.0.2.253", "transport": "ssh", "port": "22", "credential": "bureau", "site": "bureau"}, ("rest", "ssh"), {"rest": 443, "ssh": 22})
        self.assertEqual(errs, [])
        self.assertNotIn("port", entry)  # port par défaut du transport : omis
        items, what = re_.upsert(items, entry)
        self.assertEqual(what, "added")
        re_.write_items(self.local, "routers", items)
        items, src = re_.read_items(self.local, self.ex, "routers")
        self.assertEqual((src, [i["name"] for i in items]), ("local", ["exemple", "rb"]))
        items, what = re_.upsert(items, dict(entry, host="192.0.2.254"))
        self.assertEqual((what, items[1]["host"]), ("updated", "192.0.2.254"))
        items, ok = re_.remove(items, "exemple")
        self.assertTrue(ok and len(items) == 1)
        self.assertFalse(re_.remove(items, "absent")[1])

    def test_validate_errors(self):
        _, errs = re_.validate_common({"name": "a b", "host": "x y", "transport": "telnet", "port": 0, "credential": ""}, ("rest", "ssh"), {})
        self.assertEqual(len(errs), 5)

    def test_readonly(self):
        os.chmod(self.d, 0o500)
        try:
            with self.assertRaises(PermissionError):
                re_.write_items(self.local, "routers", [])
        finally:
            os.chmod(self.d, 0o700)


if __name__ == "__main__":
    unittest.main()
