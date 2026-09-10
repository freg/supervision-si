"""Tests de `store.list_device_links_for_period` (livraison #414) --
unittest pur sur une base SQLite temporaire :
`cd network-agent/api && python3 -m unittest test_links_period.py`."""
import os
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import store  # noqa: E402


class LinksForPeriodTests(unittest.TestCase):
    def setUp(self):
        self.db = os.path.join(tempfile.mkdtemp(), "na.db")
        store.ensure_schema(self.db)
        conn = sqlite3.connect(self.db)
        conn.execute("INSERT INTO na_sites (id, name, created_at) VALUES (1, 'site', '2026-01-01T00:00:00Z')")
        conn.execute("INSERT INTO na_network_segments (id, site_id, label, created_at) VALUES (1, 1, 'lan', '2026-01-01T00:00:00Z')")
        conn.execute("INSERT INTO na_network_segments (id, site_id, label, created_at) VALUES (2, 1, 'autre', '2026-01-01T00:00:00Z')")
        # Trois relevés du segment 1 (T1 < T2 < T3), un du segment 2.
        for sid, seg, at in ((1, 1, "2026-09-01T00:00:00Z"), (2, 1, "2026-09-02T00:00:00Z"), (3, 1, "2026-09-03T00:00:00Z"), (4, 2, "2026-09-02T12:00:00Z")):
            conn.execute("INSERT INTO na_history_snapshots (id, network_segment_id, snapshot_at) VALUES (?, ?, ?)", (sid, seg, at))
        rows = [
            # A->B tcp/443 : 100 @T1, 300 @T2, 600 @T3 ; A->B udp/53 : 10 @T2, 40 @T3
            (1, 10, 20, "tcp", 443, 1, 100), (2, 10, 20, "tcp", 443, 3, 300), (3, 10, 20, "tcp", 443, 6, 600),
            (2, 10, 20, "udp", 53, 1, 10), (3, 10, 20, "udp", 53, 4, 40),
            # C->A tcp/22 : seulement @T1 (aucun relevé dans [T2, T3])
            (1, 30, 10, "tcp", 22, 5, 500),
            # D->B tcp/80 : apparu @T3 (pas de référence avant) -> cumul entier
            (3, 40, 20, "tcp", 80, 2, 70),
            # segment 2 : ne doit jamais apparaître
            (4, 50, 60, "tcp", 80, 9, 900),
        ]
        conn.executemany(
            "INSERT INTO na_link_history (snapshot_id, device_a_id, device_b_id, protocol, port, packet_count, bytes_total) VALUES (?, ?, ?, ?, ?, ?, ?)",
            rows,
        )
        conn.commit()
        conn.close()

    def _by_pair(self, rows):
        return {(r["device_a_id"], r["device_b_id"]): r for r in rows}

    def test_difference_entre_relevés_sommée_sur_les_services(self):
        rows = store.list_device_links_for_period(self.db, 1, "2026-09-02T00:00:00Z", "2026-09-03T00:00:00Z")
        by = self._by_pair(rows)
        # A->B : tcp 600-300 = 300, udp 40-10 = 30 -> 330 ; paquets (6-3)+(4-1) = 6
        self.assertEqual(by[(10, 20)]["bytes_total"], 330)
        self.assertEqual(by[(10, 20)]["packet_count"], 6)
        self.assertTrue(by[(10, 20)]["period"])
        self.assertEqual(by[(10, 20)]["id"], "period-10-20")

    def test_paire_apparue_pendant_la_periode_compte_son_cumul_entier(self):
        rows = store.list_device_links_for_period(self.db, 1, "2026-09-02T00:00:00Z", "2026-09-03T00:00:00Z")
        self.assertEqual(self._by_pair(rows)[(40, 20)]["bytes_total"], 70)

    def test_paire_sans_releve_dans_la_periode_omise(self):
        rows = store.list_device_links_for_period(self.db, 1, "2026-09-02T00:00:00Z", "2026-09-03T00:00:00Z")
        self.assertNotIn((30, 10), self._by_pair(rows))

    def test_autre_segment_jamais_melange(self):
        rows = store.list_device_links_for_period(self.db, 1, "2026-01-01T00:00:00Z", "2026-12-31T00:00:00Z")
        self.assertNotIn((50, 60), self._by_pair(rows))
        rows2 = store.list_device_links_for_period(self.db, 2, "2026-01-01T00:00:00Z", "2026-12-31T00:00:00Z")
        self.assertEqual(self._by_pair(rows2)[(50, 60)]["bytes_total"], 900)

    def test_periode_sans_aucun_releve_vide_et_tri_decroissant(self):
        self.assertEqual(store.list_device_links_for_period(self.db, 1, "2025-01-01T00:00:00Z", "2025-02-01T00:00:00Z"), [])
        rows = store.list_device_links_for_period(self.db, 1, "2026-09-01T00:00:00Z", "2026-09-03T00:00:00Z")
        volumes = [r["bytes_total"] for r in rows]
        self.assertEqual(volumes, sorted(volumes, reverse=True))
        # A->B depuis T1 : tcp 600-100 = 500, udp 40-0 = 40 -> 540
        self.assertEqual(self._by_pair(rows)[(10, 20)]["bytes_total"], 540)


if __name__ == "__main__":
    unittest.main()
