"""Tests de la sonde windows-probe (#567) : analyseurs NBSTAT, SMB2, RDP, cibles, constats."""
import importlib.util
import os
import struct
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("windows_probe", os.path.join(HERE, "plugins", "windows-probe", "windows_probe.py"))
wp = importlib.util.module_from_spec(spec); spec.loader.exec_module(wp)


def nbstat_response(names, mac):
    q = b"\x20" + b"CKAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA" + b"\x00"
    rr = q + struct.pack(">HHI", 0x21, 1, 0)
    body = bytes([len(names)]) + b"".join(n.ljust(15).encode()[:15] + bytes([suf]) + struct.pack(">H", 0x8000 if grp else 0) for n, suf, grp in names) + bytes.fromhex(mac.replace(":", "")) + b"\x00" * 40
    return struct.pack(">HHHHHH", 1, 0x8400, 0, 1, 0, 0) + rr + struct.pack(">H", len(body)) + body


class Parsers(unittest.TestCase):
    def test_nbstat(self):
        r = wp.parse_nbstat(nbstat_response([("PC-ALLEE1", 0x00, False), ("WORKGROUP", 0x00, True), ("PC-ALLEE1", 0x20, False)], "02:00:00:aa:bb:cc"))
        self.assertEqual(r["name"], "PC-ALLEE1"); self.assertEqual(r["workgroup"], "WORKGROUP"); self.assertEqual(r["mac"], "02:00:00:aa:bb:cc")
        self.assertIsNone(wp.parse_nbstat(b"\x00" * 10))
        self.assertEqual(len(wp.nbstat_query(7)), 50)

    def test_smb2(self):
        hdr = b"\xfeSMB" + b"\x00" * 60
        body = struct.pack("<HHH", 65, 0x03, 0x0311) + b"\x00\x00" + b"\x11" * 16
        r = wp.parse_smb2_negotiate(hdr + body)
        self.assertEqual(r["dialect"], "3.1.1"); self.assertTrue(r["signing_required"])
        self.assertIsNone(wp.parse_smb2_negotiate(b"\xffSMB" + b"\x00" * 80))
        self.assertEqual(wp.smb2_negotiate_request()[:4], struct.pack(">I", len(wp.smb2_negotiate_request()) - 4))
        self.assertIn(b"NT LM 0.12", wp.smb1_negotiate_request())

    def test_rdp(self):
        req = wp.rdp_request()
        self.assertEqual(req[0], 3); self.assertEqual(struct.unpack(">H", req[2:4])[0], len(req))
        conf = struct.pack(">BBH", 3, 0, 19) + struct.pack(">BBHHB", 14, 0xD0, 0, 0x1234, 0) + struct.pack("<BBHI", 2, 0, 8, 2)
        r = wp.parse_rdp_response(conf)
        self.assertTrue(r["nla"]); self.assertEqual(r["protocol"], "CredSSP (NLA)")
        legacy = struct.pack(">BBH", 3, 0, 11) + struct.pack(">BBHHB", 6, 0xD0, 0, 0x1234, 0)
        self.assertFalse(wp.parse_rdp_response(legacy)["nla"])
        fail = struct.pack(">BBH", 3, 0, 19) + struct.pack(">BBHHB", 14, 0xD0, 0, 0x1234, 0) + struct.pack("<BBHI", 3, 0, 8, 5)
        self.assertIn("refus", wp.parse_rdp_response(fail)["protocol"])
        self.assertIsNone(wp.parse_rdp_response(b"\x03\x00"))

    def test_targets_and_findings(self):
        ips = wp.expand_targets(["192.0.2.0/30", "198.51.100.7", "pas-une-ip", "198.51.100.7"])
        self.assertEqual(ips, ["192.0.2.1", "192.0.2.2", "198.51.100.7"])
        host = {"ip": "192.0.2.1", "name": None, "windows_like": True, "ports": {"smb": 445, "rdp": 3389, "vnc": 5900},
                "smb": {"open": True, "smb1": True, "signing_required": False}, "rdp": {"open": True, "nla": False, "protocol": "TLS"}}
        codes = [f["code"] for f in wp.findings_for(host)]
        self.assertEqual(codes, ["smb1_enabled", "smb_signing_optional", "rdp_without_nla", "vnc_open", "netbios_silent"])
        self.assertEqual(wp.findings_for({"ip": "x", "name": "PC", "windows_like": True, "ports": {}, "smb": {"open": True, "smb1": False, "signing_required": True}}), [])


if __name__ == "__main__":
    unittest.main()
