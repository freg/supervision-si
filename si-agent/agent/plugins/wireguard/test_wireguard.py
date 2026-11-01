# -*- coding: utf-8 -*-
"""Tests #884 : sonde wireguard (lecture du dump, noms, aucune clé privée en sortie, mode SSH)."""
import json
import os
import sys
import tempfile
import types
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import wireguard as wg  # noqa: E402

NOW = 1_800_000_000
DUMP = ("wg0\tPRIVEE_SECRETE=\tPUBSERVEUR=\t51820\toff\n"
        "wg0\tPUBALICE=\tPSK_SECRETE=\t198.51.100.7:40123\t10.8.0.2/32\t%d\t1000\t2000\t25\n"
        "wg0\tPUBBOB=\t(none)\t(none)\t10.8.0.3/32,10.8.1.0/24\t0\t0\t0\toff\n"
        "wg0\tPUBCAROL=\t(none)\t203.0.113.9:5000\t10.8.0.4/32\t%d\t5\t6\toff\n") % (NOW - 30, NOW - 4000)
CONF = "[Interface]\n# serveur\nPrivateKey = PRIVEE_SECRETE=\n\n# Name = Alice (portable)\n[Peer]\nPublicKey = PUBALICE=\n\n[Peer]\n# Bob\nPublicKey = PUBBOB=\n"


class Wireguard(unittest.TestCase):
    def test_dump(self):
        i = wg.parse_dump(DUMP, now=NOW)[0]
        self.assertEqual((i["interface"], i["public_key"], i["port"]), ("wg0", "PUBSERVEUR=", 51820))
        a, b, c = i["peers"]
        self.assertTrue(a["connected"])
        self.assertEqual((a["endpoint"], a["rx"], a["handshake_age_s"]), ("198.51.100.7:40123", 1000, 30))
        self.assertEqual((b["endpoint"], b["handshake_at"], b["connected"], b["allowed_ips"]), (None, None, False, ["10.8.0.3/32", "10.8.1.0/24"]))
        self.assertFalse(c["connected"])
        self.assertNotIn("SECRETE", json.dumps(i))

    def test_noms(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "wg0.conf"), "w") as fh:
                fh.write(CONF)
            self.assertEqual(wg.noms_conf(d), {"PUBALICE=": "Alice (portable)", "PUBBOB=": "Bob"})

    def test_main_local_et_ssh(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "wg0.conf"), "w") as fh:
                fh.write(CONF)
            appels = []

            def runner(cmd, **kw):
                appels.append(cmd)
                return types.SimpleNamespace(returncode=0, stdout=DUMP, stderr="")
            out = wg.main(["--conf-dir", d], runner=runner, which=lambda x: "/usr/bin/wg", now=NOW)
            self.assertEqual(appels[-1], ["/usr/bin/wg", "show", "all", "dump"])
            self.assertEqual([p["name"] for p in out["interfaces"][0]["peers"]], ["Alice (portable)", "Bob", ""])
            self.assertNotIn("SECRETE", json.dumps(out))
            noms = os.path.join(d, "n.json")
            with open(noms, "w") as fh:
                json.dump({"PUBCAROL=": "Carol"}, fh)
            out = wg.main(["--ssh", "wgetat@vpn", "--ssh-key", "/k", "--names", noms], runner=runner, now=NOW)
            self.assertEqual(appels[-1][-2:], ["wgetat@vpn", "wg-etat"])
            self.assertEqual([p["name"] for p in out["interfaces"][0]["peers"]], ["", "", "Carol"])   # pas de lecture des conf en distant

    def test_echec(self):
        out = wg.main([], which=lambda x: None)
        self.assertEqual(out["alerts"][0]["code"], "vpn-lecture")


if __name__ == "__main__":
    unittest.main()
