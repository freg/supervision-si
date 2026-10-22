# -*- coding: utf-8 -*-
"""Catalogue Docker Hub : résumés de recherche et d'étiquettes, noms, sélection de départ (sans réseau)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dockerhub as D  # noqa: E402


class Pur(unittest.TestCase):
    def test_recherche(self):
        r = D.resumer_recherche({"results": [{"repo_name": "bitnami/nginx", "pull_count": 900, "is_official": False},
                                             {"repo_name": "nginx", "short_description": "web", "pull_count": 10, "star_count": 5, "is_official": True}]})
        self.assertEqual([(x["image"], x["officielle"], x["port"]) for x in r], [("nginx", True, 80), ("bitnami/nginx", False, None)])

    def test_tags(self):
        t = D.resumer_tags({"results": [{"name": "1.27-alpine", "last_updated": "2026-10-01", "full_size": 20, "images": [
            {"architecture": "amd64", "os": "linux"}, {"architecture": "arm", "variant": "v6", "os": "linux"}, {"architecture": "arm64", "variant": "v8", "os": "linux"},
            {"architecture": "unknown", "os": "unknown"}, {"architecture": "amd64", "os": "windows"}]}]})
        self.assertEqual(t[0]["architectures"], ["amd64", "arm/v6", "arm64/v8"])

    def test_noms(self):
        self.assertEqual((D.normaliser("nginx"), D.normaliser("grafana/grafana"), D.normaliser("x; rm"), D.normaliser("A/B/C")), ("library/nginx", "grafana/grafana", None, None))
        self.assertRaises(ValueError, D.etiquettes, "../x")

    def test_selection_et_cache(self):
        s = D.rechercher("")
        self.assertTrue(any(x["image"] == "nginx" and x["port"] == 80 for x in s))
        appels = []
        D._get, avant = (lambda url: appels.append(url) or {"results": [{"repo_name": "redis", "is_official": True}]}), D._get
        try:
            self.assertEqual(D.rechercher("red is")[0]["port"], 6379)
            self.assertIn("query=red+is", appels[0])
        finally:
            D._get = avant


if __name__ == "__main__":
    unittest.main()
