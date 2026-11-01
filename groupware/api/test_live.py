# -*- coding: utf-8 -*-
"""#665 : test d'intégration contre un Radicale RÉEL (sauté sans GROUPWARE_LIVE_DAV=http://…). Prérequis : compte de service
dans Radicale (htpasswd ou LDAP) avec la règle [service] -- rights file écrit dans DAV_CONFIG_DIR, lu par Radicale.
Joue : carnet créé par alice, contact ajouté, bob sans partage ne voit rien, partage lecture -> bob lit mais ne crée pas,
partage écriture -> bob crée et modifie, retrait du partage -> bob ne voit plus."""
import os, sys, tempfile, unittest
LIVE = os.environ.get("GROUPWARE_LIVE_DAV")
if LIVE:
    d = tempfile.mkdtemp(); os.environ.setdefault("GROUPWARE_DATA_DIR", d); os.environ.setdefault("DAV_PUBLIC_URL", LIVE); os.environ["DAV_INTERNAL_URL"] = LIVE
sys.path.insert(0, os.path.dirname(__file__))

@unittest.skipUnless(LIVE, "GROUPWARE_LIVE_DAV absent")
class Live(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import app as appmod
        cls.c = appmod.app.test_client(); cls.appmod = appmod
        cls.c.post("/dav/rights/rebuild")
        for owner in ("alice",):
            try: appmod.dav().delete_collection(owner, "contacts-test")
            except Exception: pass

    def test_flow(self):
        c = self.c
        r = c.post("/addressbooks", json={"user": "alice", "name": "test", "displayname": "Carnet de test"}); self.assertEqual(r.status_code, 201, r.json); self.assertEqual(r.json["addressbook"]["name"], "contacts-test")
        r = c.post("/contacts", json={"user": "alice", "owner": "alice", "book": "contacts-test", "contact": {"first": "Alice", "last": "Martin", "org": "Alpha", "emails": [{"value": "alice@exemple.fr"}], "categories": ["client"]}})
        self.assertEqual(r.status_code, 201, r.json); uid = r.json["contact"]["uid"]
        self.assertEqual(c.get("/contacts?user=alice&book=contacts-test&q=alpha").json["total"], 1)
        self.assertEqual(c.get("/contacts?user=bob").json["total"], 0); self.assertEqual(c.get("/addressbooks?user=bob").json["addressbooks"], [])
        c.post("/grants", json={"owner": "alice", "app": "addressbook", "grantee": "bob", "rights": "r"})
        self.assertEqual(c.get("/contacts?user=bob&book=contacts-test").json["total"], 1); self.assertEqual(c.get("/addressbooks?user=bob").json["addressbooks"][0]["rights"], "r")
        self.assertEqual(c.post("/contacts", json={"user": "bob", "owner": "alice", "book": "contacts-test", "contact": {"first": "X"}}).status_code, 403)
        c.post("/grants", json={"owner": "alice", "app": "addressbook", "grantee": "bob", "rights": "rae"})
        r = c.post("/contacts", json={"user": "bob", "owner": "alice", "book": "contacts-test", "contact": {"first": "Bob", "last": "Durand", "tels": [{"type": "cell", "value": "06 00 00 00 00"}]}}); self.assertEqual(r.status_code, 201, r.json)
        uid2 = r.json["contact"]["uid"]
        r = c.put("/contacts/alice/contacts-test/%s" % uid2, json={"user": "bob", "contact": {"org": "Beta"}}); self.assertEqual(r.status_code, 200, r.json); self.assertEqual(r.json["contact"]["org"], "Beta"); self.assertEqual(r.json["contact"]["tels"][0]["value"], "06 00 00 00 00")
        self.assertEqual(c.delete("/contacts/alice/contacts-test/%s?user=bob" % uid2).status_code, 403)       # pas de d
        self.assertEqual(c.delete("/contacts/alice/contacts-test/%s?user=alice" % uid2).json["ok"], True)
        # côté Radicale, bob lit directement avec ses identifiants (droits générés) -- vérifié par le fichier
        txt = open(os.path.join(os.environ["DAV_CONFIG_DIR"], "rights"), encoding="utf-8").read(); self.assertIn("user: ^bob$", txt); self.assertIn("[service]", txt)
        gid = [g["id"] for g in c.get("/grants?owner=alice").json["grants"] if g["grantee"] == "bob"][0]; c.delete("/grants/%d" % gid)
        self.assertEqual(c.get("/contacts?user=bob").json["total"], 0)
        self.assertEqual(c.delete("/contacts/alice/contacts-test/%s?user=alice" % uid).json["ok"], True)

if __name__ == "__main__":
    unittest.main()
