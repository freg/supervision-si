"""Livraison #427 -- IP distantes derrière un relais, sous-réseaux observés
à deux origines, fiche récapitulative d'un sous-réseau.
python3 -m unittest test_observed_subnets (depuis network-agent/api/)."""
import os
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import capture  # noqa: E402
import store  # noqa: E402

GW, PC, NAS = "aa:bb:cc:00:00:01", "aa:bb:cc:00:00:04", "aa:bb:cc:00:00:03"


def pkt(kind, src_mac, dst_mac, src_ip, dst_ip, dst_port=None, size=100):
    return {"kind": kind, "src_mac": src_mac, "dst_mac": dst_mac, "src_ip": src_ip, "dst_ip": dst_ip,
            "src_port": 40000, "dst_port": dst_port, "orig_len": size, "arp": None, "protocol": 6}


class ObservedSubnetsTest(unittest.TestCase):
    def setUp(self):
        self.db = os.path.join(tempfile.mkdtemp(), "na.db")
        store.ensure_schema(self.db)
        conn = sqlite3.connect(self.db)
        conn.execute("INSERT INTO na_sites (id, name, created_at) VALUES (1, 'Siège', '2026-01-01T00:00:00Z')")
        conn.execute("INSERT INTO na_network_segments (id, site_id, label, cidr, created_at) VALUES (1, 1, 'lan', '192.168.1.0/24', '2026-01-01T00:00:00Z')")
        conn.execute("INSERT INTO na_network_segments (id, site_id, label, cidr, created_at) VALUES (2, 1, 'sans-cidr', NULL, '2026-01-01T00:00:00Z')")
        conn.commit(); conn.close()
        self.conn = store.get_connection(self.db)
        # ARP du PC, PC -> 8.8.8.8 via la passerelle, réponse 8.8.8.8 -> PC (src_mac = passerelle),
        # 10.20.0.5 (autre site, routé) -> NAS, PC -> NAS local
        capture.process_packet(self.conn, 1, "192.168.1.0/24", {"kind": "arp", "arp": {"sender_mac": PC, "sender_ip": "192.168.1.35"}, "orig_len": 60})
        capture.process_packet(self.conn, 1, "192.168.1.0/24", pkt("udp", PC, GW, "192.168.1.35", "8.8.8.8", 53))
        capture.process_packet(self.conn, 1, "192.168.1.0/24", pkt("udp", GW, PC, "8.8.8.8", "192.168.1.35", 40000, 300))
        capture.process_packet(self.conn, 1, "192.168.1.0/24", pkt("tcp", GW, NAS, "10.20.0.5", "192.168.1.21", 445, 500))
        capture.process_packet(self.conn, 1, "192.168.1.0/24", pkt("tcp", PC, NAS, "192.168.1.35", "192.168.1.21", 445, 900))
        self.conn.commit()

    def tearDown(self):
        self.conn.close()

    def test_ip_distante_jamais_attribuee_au_relais(self):
        cur = self.conn.cursor()
        cur.execute("SELECT ip_address, external_relay_count FROM na_devices WHERE mac_address = ?", [GW])
        row = cur.fetchone()
        self.assertIsNone(row["ip_address"], "la passerelle ne prend pas l'IP 8.8.8.8 / 10.20.0.5 qu'elle relaie")
        self.assertEqual(row["external_relay_count"], 3, "1 destination distante + 2 sources distantes")
        cur.execute("SELECT ip_address, direction FROM na_remote_ips ORDER BY ip_address, direction")
        self.assertEqual([tuple(r) for r in cur.fetchall()], [("10.20.0.5", "in"), ("8.8.8.8", "in"), ("8.8.8.8", "out")])
        cur.execute("SELECT ip_address FROM na_devices WHERE mac_address = ?", [PC])
        self.assertEqual(cur.fetchone()["ip_address"], "192.168.1.35")

    def test_sous_reseaux_deux_origines(self):
        subs = {s["subnet"]: s for s in store.list_observed_subnets(self.db, 1)}
        self.assertEqual(set(subs), {"192.168.1.0/24", "8.8.8.0/24", "10.20.0.0/24"})
        lan = subs["192.168.1.0/24"]
        self.assertEqual((lan["device_count"], lan["remote_ip_count"], lan["origin"], lan["in_segment"]), (2, 0, "local", True))
        dns = subs["8.8.8.0/24"]
        self.assertEqual((dns["device_count"], dns["remote_ip_count"], dns["origin"], dns["in_segment"]), (0, 1, "relais", False))
        self.assertEqual(dns["via"], ["aa:bb:cc:00:00:01"], "relais = la passerelle (sans IP ni nom : sa MAC)")
        self.assertEqual(subs["10.20.0.0/24"]["packet_count"], 1)
        self.assertEqual(store.list_observed_subnets(self.db, 1, prefix_length=16)[0]["subnet"], "192.168.0.0/16")

    def test_fiche_sous_reseau(self):
        d = store.subnet_detail(self.db, 1, "8.8.8.0/24")
        self.assertEqual((d["in_segment"], d["device_count"], d["remote_ip_count"]), (False, 0, 1))
        self.assertIn("HORS du CIDR", d["explanation"])
        self.assertEqual(d["ips"][0]["kind"], "distante")
        self.assertEqual(sorted(d["ips"][0]["directions"]), ["in", "out"])
        self.assertEqual(d["ips"][0]["bytes_total"], 400)
        self.assertEqual(d["relays"][0]["mac"], GW)
        self.assertEqual(d["sources"], ["trafic relayé (IP distantes derrière une passerelle)"])
        lan = store.subnet_detail(self.db, 1, "192.168.1.0/24")
        self.assertEqual((lan["in_segment"], lan["device_count"]), (True, 2))
        self.assertEqual([i["ip"] for i in lan["ips"]], ["192.168.1.21", "192.168.1.35"])
        self.assertIn(("tcp", 445), {(s["protocol"], s["port"]) for s in lan["services"]})
        self.assertEqual(len(lan["links"]), 4, "PC <-> passerelle, passerelle -> NAS, PC -> NAS")
        self.assertIsNone(store.subnet_detail(self.db, 1, "pas-un-cidr"))
        empty = store.subnet_detail(self.db, 1, "172.16.0.0/24")
        self.assertIn("Aucune adresse", empty["explanation"])

    def test_sans_cidr_les_ip_publiques_sont_distantes(self):
        capture.process_packet(self.conn, 2, None, pkt("udp", GW, PC, "8.8.4.4", "192.168.1.35", 40000))
        capture.process_packet(self.conn, 2, None, pkt("udp", GW, PC, "10.9.9.9", "192.168.1.35", 40000))
        self.conn.commit()
        subs = {s["subnet"]: s for s in store.list_observed_subnets(self.db, 2)}
        self.assertEqual(subs["8.8.4.0/24"]["origin"], "relais")
        self.assertEqual(subs["10.9.9.0/24"]["origin"], "local", "privé sans CIDR : impossible à distinguer, attribué à la MAC")
        self.assertIsNone(subs["10.9.9.0/24"]["in_segment"])
        self.assertIn("Aucun CIDR", store.subnet_detail(self.db, 2, "10.9.9.0/24")["explanation"])


if __name__ == "__main__":
    unittest.main()
