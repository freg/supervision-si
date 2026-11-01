"""Tests de la sonde broadcast-probe (#568) : analyseurs de trames et agrégation."""
import importlib.util
import os
import socket
import struct
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("broadcast_probe", os.path.join(HERE, "plugins", "broadcast-probe", "broadcast_probe.py"))
bp = importlib.util.module_from_spec(spec); spec.loader.exec_module(bp)

BCAST = b"\xff" * 6
SRC = bytes.fromhex("020000aabb01")


def eth(dst, src, etype, payload):
    return dst + src + struct.pack(">H", etype) + payload


def ipv4_udp(src_ip, dst_ip, sport, dport, data):
    udp = struct.pack(">HHHH", sport, dport, 8 + len(data), 0) + data
    ip = struct.pack(">BBHHHBBH4s4s", 0x45, 0, 20 + len(udp), 0, 0, 64, 17, 0, socket.inet_aton(src_ip), socket.inet_aton(dst_ip)) + udp
    return ip


def dns_q(name):
    return b"".join(bytes([len(p)]) + p.encode() for p in name.split(".")) + b"\x00"


class Parsers(unittest.TestCase):
    def test_unicast_ignored_and_arp(self):
        self.assertIsNone(bp.parse_frame(eth(bytes.fromhex("020000aabb02"), SRC, 0x0800, b"\x00" * 30)))
        arp = struct.pack(">HHBBH", 1, 0x0800, 6, 4, 1) + SRC + socket.inet_aton("192.0.2.5") + b"\x00" * 6 + socket.inet_aton("192.0.2.5")
        e = bp.parse_frame(eth(BCAST, SRC, 0x0806, arp))
        self.assertEqual(e["proto"], "arp"); self.assertTrue(e["info"]["gratuitous"]); self.assertEqual(e["src_ip"], "192.0.2.5")

    def test_mdns_ssdp_nbns_dhcp(self):
        # mDNS : réponse PTR _ipp._tcp.local -> Imprimante._ipp._tcp.local + A imprimante.local
        hdr = struct.pack(">HHHHHH", 0, 0x8400, 0, 2, 0, 0)
        ptr_name = dns_q("_ipp._tcp.local"); target = dns_q("Imprimante._ipp._tcp.local")
        rr1 = ptr_name + struct.pack(">HHIH", 12, 1, 120, len(target)) + target
        a_name = dns_q("imprimante.local"); rr2 = a_name + struct.pack(">HHIH", 1, 1, 120, 4) + socket.inet_aton("192.0.2.9")
        frame = eth(bytes.fromhex("01005e0000fb"), SRC, 0x0800, ipv4_udp("192.0.2.9", "224.0.0.251", 5353, 5353, hdr + rr1 + rr2))
        e = bp.parse_frame(frame)
        self.assertEqual(e["proto"], "mdns"); self.assertIn("_ipp._tcp", e["info"]["services"]); self.assertIn("imprimante.local", e["info"]["names"]); self.assertTrue(e["info"]["is_response"])
        ssdp = b"NOTIFY * HTTP/1.1\r\nHOST: 239.255.255.250:1900\r\nNT: urn:schemas-upnp-org:device:MediaRenderer:1\r\nSERVER: Linux UPnP/1.0 Sonos/1\r\nUSN: uuid:1\r\n\r\n"
        e = bp.parse_frame(eth(bytes.fromhex("01005e7ffffa"), SRC, 0x0800, ipv4_udp("192.0.2.9", "239.255.255.250", 1900, 1900, ssdp)))
        self.assertEqual(e["proto"], "ssdp"); self.assertEqual(e["info"]["method"], "NOTIFY"); self.assertIn("Sonos", e["info"]["server"])
        # NBNS registration de « PC-ALLEE1 »
        raw = b"PC-ALLEE1".ljust(15) + b"\x00"
        enc = b"".join(bytes([65 + (b >> 4), 65 + (b & 15)]) for b in raw)
        nb = struct.pack(">HHHHHH", 1, 0x2910, 1, 0, 0, 1) + b"\x20" + enc + b"\x00" + b"\x00" * 4
        e = bp.parse_frame(eth(BCAST, SRC, 0x0800, ipv4_udp("192.0.2.5", "192.0.2.255", 137, 137, nb)))
        self.assertEqual(e["proto"], "netbios-ns"); self.assertEqual(e["info"]["opcode"], "registration"); self.assertEqual(e["info"]["name"], "PC-ALLEE1")
        # DHCP offer serveur 192.0.2.1
        dhcp = bytes([2, 1, 6, 0]) + b"\x12\x34\x56\x78" + b"\x00" * 20 + SRC + b"\x00" * 10 + b"\x00" * 192 + b"\x63\x82\x53\x63" + bytes([53, 1, 2, 54, 4]) + socket.inet_aton("192.0.2.1") + bytes([255])
        e = bp.parse_frame(eth(BCAST, SRC, 0x0800, ipv4_udp("192.0.2.1", "255.255.255.255", 67, 68, dhcp)))
        self.assertEqual(e["proto"], "dhcp"); self.assertEqual(e["info"]["type"], "offer"); self.assertEqual(e["info"]["server_id"], "192.0.2.1")

    def test_lldp_stp_ra(self):
        tlv = lambda t, v: struct.pack(">H", (t << 9) | len(v)) + v
        lldp = tlv(1, b"\x04" + SRC) + tlv(2, b"\x05gi1/0/1") + tlv(5, b"SW-CORE") + tlv(0, b"")
        e = bp.parse_frame(eth(bytes.fromhex("0180c200000e"), SRC, 0x88cc, lldp))
        self.assertEqual(e["proto"], "lldp"); self.assertEqual(e["info"]["sysname"], "SW-CORE"); self.assertEqual(e["info"]["port"], "gi1/0/1")
        bpdu = b"\x42\x42\x03" + struct.pack(">HBB", 0, 0, 0) + bytes([0x01]) + struct.pack(">H", 32768) + SRC + b"\x00" * 4 + struct.pack(">H", 32768) + SRC + b"\x00" * 10
        e = bp.parse_frame(eth(bytes.fromhex("0180c2000000"), SRC, len(bpdu), bpdu))
        self.assertEqual(e["proto"], "stp"); self.assertTrue(e["info"]["topology_change"])
        ip6 = struct.pack(">IHBB", 0x60000000, 8, 58, 255) + socket.inet_pton(socket.AF_INET6, "fe80::1") + socket.inet_pton(socket.AF_INET6, "ff02::1") + bytes([134, 0, 0, 0, 0, 0, 0, 0])
        e = bp.parse_frame(eth(bytes.fromhex("333300000001"), SRC, 0x86dd, ip6))
        self.assertEqual(e["proto"], "icmpv6-ra")

    def test_aggregate_findings(self):
        ev = [
            {"src_mac": "aa", "proto": "dhcp", "src_ip": "192.0.2.1", "info": {"type": "offer", "server_id": "192.0.2.1"}},
            {"src_mac": "bb", "proto": "dhcp", "src_ip": "192.0.2.77", "info": {"type": "offer", "server_id": "192.0.2.77"}},
            {"src_mac": "cc", "proto": "arp", "src_ip": "192.0.2.5", "info": {"op": "reply", "sender_mac": "cc"}},
            {"src_mac": "dd", "proto": "arp", "src_ip": "192.0.2.5", "info": {"op": "reply", "sender_mac": "dd"}},
            {"src_mac": "ee", "proto": "stp", "src_ip": None, "info": {"type": "tcn"}},
            {"src_mac": "ff", "proto": "mdns", "src_ip": "192.0.2.9", "info": {"names": ["imprimante.local", "_ipp._tcp.local"], "services": ["_ipp._tcp"]}},
        ] + [{"src_mac": "gg", "proto": "ssdp", "src_ip": "192.0.2.3", "info": {}} for _ in range(700)]
        a = bp.aggregate(ev, 60)
        codes = [f["code"] for f in a["findings"]]
        self.assertIn("dhcp_multiple", codes); self.assertIn("arp_conflict", codes); self.assertIn("stp_topology_change", codes); self.assertIn("storm", codes)
        self.assertEqual(a["announcers"][0]["mac"], "gg"); self.assertEqual(a["announcers"][0]["per_minute"], 700.0)
        ff = next(x for x in a["announcers"] if x["mac"] == "ff")
        self.assertEqual(ff["names"], ["imprimante.local"]); self.assertEqual(ff["services"], ["_ipp._tcp"])
        self.assertEqual(a["protocols"][0]["proto"], "ssdp")


if __name__ == "__main__":
    unittest.main()
