# -*- coding: utf-8 -*-
"""Tests de câblage des routes création compte / groupes (Flask test_client),
avec ldapsearch/ldapmodify SIMULÉS -- valide surtout la REMONTÉE d'erreur."""
import os
import tempfile
import unittest

os.environ.setdefault("LDAP_ADMIN_URL", "ldap://ldap.test")
os.environ.setdefault("LDAP_ADMIN_BIND_DN", "cn=admin,dc=groupe-i,dc=fr")
os.environ.setdefault("LDAP_ADMIN_BASE_DN", "dc=groupe-i,dc=fr")
os.environ.setdefault("RIGHTS_API_URL", "")  # droit manage passant en test
os.environ.setdefault("LDAP_ADMIN_BACKUP_DIR", tempfile.mkdtemp())

import app as appmod  # noqa: E402
import ldap_client  # noqa: E402
import ldap_backup  # noqa: E402

PW = {"X-LDAP-Bind-Password": "secret"}


class RouteTests(unittest.TestCase):
    def setUp(self):
        self.c = appmod.app.test_client()
        self._search_calls = []
        # sauvegarde toujours OK (pas d'écriture disque réelle)
        ldap_backup.create_backup = lambda *a, **k: "backup.ldif"

    def _patch_search(self, responder):
        def fake(config, base, filt, attrs=None, scope=None, runner=None):
            self._search_calls.append((base, filt))
            return responder(base, filt)
        ldap_client.search = fake

    def test_config(self):
        r = self.c.get("/accounts/config")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()["external_dn"], "ou=external,ou=accounts,dc=groupe-i,dc=fr")

    def test_creation_ok_uidnumber_auto(self):
        self._patch_search(lambda base, filt: (
            {"ok": True, "stdout": "", "stderr": "", "returncode": 0} if filt.startswith("(uid=")
            else {"ok": True, "stdout": "uidNumber: 17942\n", "stderr": "", "returncode": 0}))
        applied = {}
        def _ok(config, ldif):
            applied["ldif"] = ldif
            return {"ok": True, "stdout": "", "stderr": "", "returncode": 0}
        ldap_client.apply_ldif = _ok
        r = self.c.post("/accounts", json={"uid": "demo2", "kind": "externe", "sn": "MOA", "given_name": "Demo", "password": "s3cret!!"}, headers=PW)
        self.assertEqual(r.status_code, 201, r.get_json())
        body = r.get_json()
        self.assertEqual(body["uid_number"], 17943)   # max+1 auto
        self.assertEqual(body["dn"], "uid=demo2,ou=external,ou=accounts,dc=groupe-i,dc=fr")
        self.assertIn("uidNumber: 17943", applied["ldif"])

    def test_creation_uid_existant_409(self):
        self._patch_search(lambda base, filt: {"ok": True, "stdout": "dn: uid=demo2,ou=external,ou=accounts,dc=groupe-i,dc=fr\n", "stderr": "", "returncode": 0})
        r = self.c.post("/accounts", json={"uid": "demo2", "kind": "externe", "sn": "MOA", "password": "x12345678"}, headers=PW)
        self.assertEqual(r.status_code, 409)
        self.assertIn("déjà", r.get_json()["error"])

    def test_creation_erreur_ldapmodify_remontee(self):
        self._patch_search(lambda base, filt: (
            {"ok": True, "stdout": "", "stderr": "", "returncode": 0} if filt.startswith("(uid=")
            else {"ok": True, "stdout": "uidNumber: 100\n", "stderr": "", "returncode": 0}))
        # uidNumber sous plancher -> refus clair
        r = self.c.post("/accounts", json={"uid": "demo3", "kind": "interne", "sn": "T", "password": "x12345678"}, headers=PW)
        self.assertEqual(r.status_code, 500)
        self.assertIn("uidNumber", r.get_json()["error"])
        # cette fois uidNumber OK mais ldapmodify échoue -> 502 avec stderr
        self._patch_search(lambda base, filt: (
            {"ok": True, "stdout": "", "stderr": "", "returncode": 0} if filt.startswith("(uid=")
            else {"ok": True, "stdout": "uidNumber: 5000\n", "stderr": "", "returncode": 0}))
        ldap_client.apply_ldif = lambda config, ldif: {"ok": False, "stdout": "", "stderr": "ldap_add: Insufficient access (50)", "returncode": 50}
        r = self.c.post("/accounts", json={"uid": "demo3", "kind": "interne", "sn": "T", "password": "x12345678"}, headers=PW)
        self.assertEqual(r.status_code, 502)
        self.assertIn("Insufficient access", r.get_json()["error"])  # stderr remonté, pas avalé

    def test_groupe_memberUid_et_member(self):
        # posixGroup -> memberUid = uid, sans lookup du DN
        self._patch_search(lambda base, filt: {"ok": True, "stdout": "dn: %s\nobjectClass: posixGroup\n" % base, "stderr": "", "returncode": 0})
        applied = {}
        def _ok(config, ldif):
            applied["ldif"] = ldif
            return {"ok": True, "stdout": "", "stderr": "", "returncode": 0}
        ldap_client.apply_ldif = _ok
        r = self.c.post("/groups/member", json={"group_dn": "cn=svc,ou=groups,ou=accounts,dc=groupe-i,dc=fr", "uid": "demo2"}, headers=PW)
        self.assertEqual(r.status_code, 200, r.get_json())
        self.assertEqual(r.get_json()["member_attr"], "memberUid")
        self.assertIn("memberUid: demo2", applied["ldif"])

        # groupOfNames -> member = DN complet (résolu par recherche uid)
        def responder(base, filt):
            if "objectClass=*" in filt or filt == "(objectClass=*)":
                return {"ok": True, "stdout": "dn: %s\nobjectClass: groupOfNames\n" % base, "stderr": "", "returncode": 0}
            return {"ok": True, "stdout": "dn: uid=demo2,ou=external,ou=accounts,dc=groupe-i,dc=fr\n", "stderr": "", "returncode": 0}
        self._patch_search(responder)
        r = self.c.post("/groups/member", json={"group_dn": "cn=eq,ou=groups,ou=accounts,dc=groupe-i,dc=fr", "uid": "demo2"}, headers=PW)
        self.assertEqual(r.status_code, 200, r.get_json())
        self.assertEqual(r.get_json()["member_attr"], "member")
        self.assertIn("member: uid=demo2,ou=external,ou=accounts,dc=groupe-i,dc=fr", applied["ldif"])

    def test_liste_groupes(self):
        self._patch_search(lambda base, filt: {"ok": True, "stdout":
            "dn: cn=svc,ou=groups,ou=accounts,dc=groupe-i,dc=fr\ncn: svc\nobjectClass: posixGroup\nmemberUid: a\nmemberUid: b\n", "stderr": "", "returncode": 0})
        r = self.c.get("/groups", headers=PW)
        self.assertEqual(r.status_code, 200, r.get_json())
        gs = r.get_json()["groups"]
        self.assertEqual(len(gs), 1)
        self.assertEqual(gs[0]["cn"], "svc")
        self.assertEqual(gs[0]["member_attr"], "memberUid")
        self.assertEqual(gs[0]["member_count"], 2)


if __name__ == "__main__":
    unittest.main()
