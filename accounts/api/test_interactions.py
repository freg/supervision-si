"""Tests #638 : journal des interactions (parse CHANGELOG, catégories, comptes-rendus)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import interactions as it  # noqa: E402

SAMPLE = """# CHANGELOG

## 2026-09-27 — Tuile Proxmox : MAC des VM (livraison #637)

L'agent Proxmox extrait la MAC de chaque VM.

## 2026-09-26 — Agent 0.5.28 : Bureau à distance, mise à jour de l'agent (livraison #636, items 100/104)

RDP intégré, service Terminal Server.

## 2026-09-26 — Sonde front-access : journal du frontal résumé dans le hub (livraison #622, item 99)

Codes 401 A0, 403 périmètre.

## 2026-09-19 — PoC assistant IA sous Ollama (livraison #532)

qwen3:8b évalué sur 20 cas.
"""


class InteractionsTests(unittest.TestCase):
    def test_parse(self):
        e = it.parse_changelog(SAMPLE)
        self.assertEqual(len(e), 4)
        self.assertEqual(e[0]["date"], "2026-09-27"); self.assertEqual(e[0]["delivery"], 637)
        self.assertEqual(e[0]["title"], "Tuile Proxmox : MAC des VM")
        self.assertEqual([x["delivery"] for x in e], [637, 636, 622, 532])  # plus récent d'abord
        self.assertEqual(it.parse_changelog(""), [])

    def test_categorize(self):
        self.assertEqual(it.categorize("Bureau à distance RDP"), "Sécurité & accès")
        self.assertEqual(it.categorize("PoC assistant IA sous Ollama"), "IA")
        self.assertEqual(it.categorize("Agent 0.5.28 Windows lanceur"), "Agent & postes")
        self.assertEqual(it.categorize("Tuile Proxmox : MAC des VM"), "Réseau & infra")
        self.assertEqual(it.categorize("bla bla"), "Autre")

    def test_timeline_filtre(self):
        t = it.timeline(SAMPLE, category="IA")
        self.assertEqual(t["total"], 1); self.assertEqual(t["entries"][0]["delivery"], 532)
        self.assertEqual(it.timeline(SAMPLE, query="terminal server")["total"], 1)
        full = it.timeline(SAMPLE)
        self.assertEqual(full["span"], {"from": "2026-09-19", "to": "2026-09-27"})
        self.assertIn("Réseau & infra", full["by_category"])

    def test_minutes(self):
        m = it.period_minutes(it.parse_changelog(SAMPLE), by="week")
        self.assertTrue(all("period" in x and "summary" in x for x in m))
        self.assertEqual(sum(x["count"] for x in m), 4)
        mois = it.period_minutes(it.parse_changelog(SAMPLE), by="month")
        sep = [x for x in mois if x["period"] == "2026-09"][0]
        self.assertEqual(sep["count"], 4); self.assertEqual(sep["deliveries"], [532, 622, 636, 637])


if __name__ == "__main__":
    unittest.main()
