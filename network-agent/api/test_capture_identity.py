"""Tests de `capture.interface_identity` (livraison #412) -- unittest pur,
`python3 -m unittest network-agent/api/test_capture_identity.py` ou
`cd network-agent/api && python3 -m unittest`. Aucune dépendance Flask :
seule la fonction d'identité de l'interface est couverte, le reste de
capture.py exige tcpdump."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import capture  # noqa: E402


class InterfaceIdentityTests(unittest.TestCase):
    def setUp(self):
        self.sysfs = tempfile.mkdtemp()

    def _write_mac(self, iface, mac):
        os.makedirs(os.path.join(self.sysfs, iface), exist_ok=True)
        with open(os.path.join(self.sysfs, iface, "address"), "w", encoding="utf-8") as fh:
            fh.write(mac + "\n")

    def test_mac_lue_dans_sysfs_normalisee_en_minuscules(self):
        self._write_mac("cap0", "AA:BB:CC:DD:EE:FF")
        ident = capture.interface_identity("cap0", self.sysfs)
        self.assertEqual(ident["interface"], "cap0")
        self.assertEqual(ident["interface_mac"], "aa:bb:cc:dd:ee:ff")
        self.assertIn("interface_ip", ident)

    def test_interface_absente_donne_none_sans_exception(self):
        ident = capture.interface_identity("n-existe-pas-0", self.sysfs)
        self.assertEqual(ident, {"interface": "n-existe-pas-0", "interface_mac": None, "interface_ip": None})

    def test_mac_nulle_ignoree(self):
        self._write_mac("lo", "00:00:00:00:00:00")
        ident = capture.interface_identity("lo", self.sysfs)
        self.assertIsNone(ident["interface_mac"])

    def test_nom_trop_long_ne_leve_pas(self):
        ident = capture.interface_identity("x" * 40, self.sysfs)
        self.assertIsNone(ident["interface_mac"])
        self.assertIsNone(ident["interface_ip"])

    @unittest.skipUnless(sys.platform.startswith("linux"), "ioctl SIOCGIFADDR : Linux seulement")
    def test_ip_de_loopback_sous_linux(self):
        ident = capture.interface_identity("lo", self.sysfs)
        self.assertEqual(ident["interface_ip"], "127.0.0.1")


if __name__ == "__main__":
    unittest.main()
