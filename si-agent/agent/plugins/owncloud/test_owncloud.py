# -*- coding: utf-8 -*-
"""#999 : sonde ownCloud -- config.php, assemblage des requêtes, fin de support, constats (valeurs fictives)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import owncloud as O  # noqa: E402

CONFIG = """<?php
$CONFIG = array (
  'instanceid' => 'abc',
  'passwordsalt' => 'NE-DOIT-PAS-SORTIR',
  'trusted_domains' =>
  array (
    0 => 'cloud.exemple.fr',
    1 => '192.0.2.86',
  ),
  'datadirectory' => '/var/www/owncloud/data',
  'overwrite.cli.url' => 'http://cloud.intranet',
  'dbtype' => 'mysql',
  'version' => '10.15.0.2',
  'dbname' => 'owncloud',
  'dbhost' => 'localhost',
  'dbtableprefix' => 'oc_',
  'dbpassword' => 'NE-DOIT-PAS-SORTIR',
);
"""
NOW = 1_794_000_000   # 2026-11-06
J = 86400


class Sonde(unittest.TestCase):
    def test_config_sans_secret(self):
        c = O.parse_config(CONFIG)
        self.assertEqual(c["version"], "10.15.0.2"); self.assertEqual(c["dbtableprefix"], "oc_")
        self.assertEqual(c["trusted_domains"], ["cloud.exemple.fr", "192.0.2.86"])
        self.assertNotIn("NE-DOIT-PAS-SORTIR", str(c))

    def test_fin_support(self):
        s = O.fin_support('PRETTY_NAME="Debian GNU/Linux 11 (bullseye)"\nVERSION_ID="11"\nID=debian\n', NOW)
        self.assertEqual((s["version"], s["fin"], s["depasse"]), ("11", "2026-08-31", True))
        self.assertFalse(O.fin_support('ID=debian\nVERSION_ID="12"\n', NOW)["depasse"])
        self.assertIsNone(O.fin_support('ID=ubuntu\nVERSION_ID="24.04"\n', NOW)["fin"])

    def test_assembler_et_constats(self):
        G = 1024 ** 3
        comptes = O.tsv("u1\tAlice ALPHA\t%d\tOCA\\\\User_LDAP\\\\User_Proxy\nu2\tBob BRAVO\t%d\tOCA\\\\User_LDAP\\\\User_Proxy\n"
                        "administrator\tadministrator\t%d\tOC\\\\User\\\\Database\nadmin\tadmin\t%d\tOC\\\\User\\\\Database\nmyriam\tmyriam\t0\tOC\\\\User\\\\Database\n"
                        % (NOW - 3600, NOW - 900 * J, NOW - 1600 * J, NOW - 80 * J))
        espaces = O.tsv("home::u1\tfiles\t%d\nhome::u1\tfiles_trashbin\t%d\nhome::u2\tfiles\t%d\nhome::u2\tfiles_versions\t%d\nlocal::/x\tfiles\t%d\n"
                        % (100 * G, 60 * G, 80 * G, 5 * G, 999 * G))
        cs, tot, act = O.assembler(comptes, espaces, O.tsv("u1\t%d\t12\n" % (NOW - 400 * J)), O.tsv("2026-11-05\t54\t6\n"))
        self.assertEqual(cs[0]["id"], "u1"); self.assertEqual(cs[0]["origine"], "ldap")
        self.assertEqual((cs[0]["go_fichiers"], cs[0]["go_corbeille"], cs[0]["corbeille_elements"]), (100.0, 60.0, 12))
        self.assertIsNone([c for c in cs if c["id"] == "myriam"][0]["derniere_connexion"])
        self.assertEqual(tot["fichiers"], 180.0); self.assertEqual(tot["corbeilles"], 60.0)   # stockage local:: ignoré
        self.assertEqual(act, [{"jour": "2026-11-05", "actions": 54, "utilisateurs": 6}])
        inst = {"disque": {"pct": 82, "libre_go": 300}, "systeme": {"nom": "Debian 11", "fin": "2026-08-31", "depasse": True}}
        al = {a["code"]: a for a in O.constats(inst, cs, tot, NOW)}
        self.assertEqual(al["owncloud-disque"]["severity"], "warning")
        self.assertIn("owncloud-systeme", al)
        self.assertIn("24 %", al["owncloud-corbeilles"]["message"])
        self.assertIn("administrator, myriam", al["owncloud-comptes-locaux"]["message"]); self.assertNotIn("admin,", al["owncloud-comptes-locaux"]["message"])


if __name__ == "__main__":
    unittest.main()
