# -*- coding: utf-8 -*-
"""Tests de la logique pure de création de comptes / groupes (ldap_accounts)."""
import unittest
import base64
import ldap_accounts as a


class DnTests(unittest.TestCase):
    def test_account_dn(self):
        self.assertEqual(a.account_dn("alex1", "interne", "ou=accounts,dc=groupe-i,dc=fr", "ou=external,ou=accounts,dc=groupe-i,dc=fr"),
                         "uid=alex1,ou=accounts,dc=groupe-i,dc=fr")
        self.assertEqual(a.account_dn("aga1", "externe", "ou=accounts,dc=groupe-i,dc=fr", "ou=external,ou=accounts,dc=groupe-i,dc=fr"),
                         "uid=aga1,ou=external,ou=accounts,dc=groupe-i,dc=fr")
        with self.assertRaises(ValueError):
            a.account_dn("x", "autre", "a", "b")

    def test_valid_uid(self):
        self.assertTrue(a.valid_uid("demo_moa"))
        self.assertTrue(a.valid_uid("g.lambert"))
        self.assertFalse(a.valid_uid("Demo"))       # majuscule
        self.assertFalse(a.valid_uid("a b"))          # espace
        self.assertFalse(a.valid_uid("-x"))           # commence par -
        self.assertFalse(a.valid_uid(""))


class UidNumberTests(unittest.TestCase):
    def test_next_uid_number(self):
        text = "dn: uid=a,...\nuidNumber: 17940\n\ndn: uid=b,...\nuidNumber: 17942\n\ndn: uid=c\nuidNumber: 100\n"
        self.assertEqual(a.next_uid_number(text, floor=1000), 17943)

    def test_next_uid_number_casse_et_vide(self):
        self.assertEqual(a.next_uid_number("uidnumber: 5000\n", floor=1000), 5001)  # casse
        self.assertIsNone(a.next_uid_number("", floor=1000))                         # rien
        self.assertIsNone(a.next_uid_number("uidNumber: 3\n", floor=1000))           # sous le plancher


class LdifTests(unittest.TestCase):
    def test_ldif_attr_base64_accents(self):
        line = a.ldif_attr("cn", "Amélie")
        self.assertTrue(line.startswith("cn:: "))
        self.assertEqual(base64.b64decode(line.split(":: ", 1)[1]).decode("utf-8"), "Amélie")
        self.assertEqual(a.ldif_attr("sn", "MOA"), "sn: MOA")           # ASCII simple
        self.assertTrue(a.ldif_attr("x", " début").startswith("x:: "))  # espace de tête

    def test_build_add_account_ldif(self):
        ldif = a.build_add_account_ldif(
            "uid=demo_moa,ou=external,ou=accounts,dc=groupe-i,dc=fr", "demo_moa", "MOA",
            17943, 65534, given_name="Demo", mail="w.leroy@omalleyconsulting.net",
            password="s3cret!!", description="compte externe")
        self.assertIn("changetype: add", ldif)
        self.assertIn("objectClass: posixAccount", ldif)
        self.assertIn("objectClass: inetOrgPerson", ldif)
        self.assertIn("cn: Demo MOA", ldif)
        self.assertIn("displayName: Demo MOA", ldif)
        self.assertIn("uidNumber: 17943", ldif)
        self.assertIn("gidNumber: 65534", ldif)
        self.assertIn("homeDirectory: /home/demo_moa", ldif)
        self.assertIn("loginShell: /bin/false", ldif)
        self.assertIn("userPassword: s3cret!!", ldif)

    def test_cn_sans_prenom(self):
        ldif = a.build_add_account_ldif("uid=x,ou=accounts", "x", "NOM", 1001, 65534)
        self.assertIn("cn: NOM", ldif)
        self.assertNotIn("givenName:", ldif)
        self.assertNotIn("mail:", ldif)


class GroupTests(unittest.TestCase):
    def test_member_attr(self):
        self.assertEqual(a.group_member_attr(["top", "groupOfNames"]), "member")
        self.assertEqual(a.group_member_attr(["groupOfUniqueNames"]), "uniqueMember")
        self.assertEqual(a.group_member_attr(["posixGroup"]), "memberUid")
        self.assertIsNone(a.group_member_attr(["top", "organizationalUnit"]))

    def test_member_value_et_ldif(self):
        self.assertEqual(a.group_member_value("memberUid", "uid=x,ou=accounts", "x"), "x")
        self.assertEqual(a.group_member_value("member", "uid=x,ou=accounts", "x"), "uid=x,ou=accounts")
        ldif = a.build_group_member_ldif("cn=g,ou=groups", "member", "uid=x,ou=accounts", add=True)
        self.assertIn("changetype: modify", ldif)
        self.assertIn("add: member", ldif)
        self.assertIn("member: uid=x,ou=accounts", ldif)
        self.assertIn("delete: memberUid", a.build_group_member_ldif("cn=g", "memberUid", "x", add=False))


if __name__ == "__main__":
    unittest.main()
