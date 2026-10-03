# -*- coding: utf-8 -*-
"""#664 : routes groupware-api -- partages (création, effectifs, retrait, fichier de droits Radicale régénéré), catégories,
liens dans les deux sens, préférences résolues, URLs DAV."""
import os, sys, tempfile, unittest
d = tempfile.mkdtemp(); os.environ["GROUPWARE_DATA_DIR"] = d; os.environ["DAV_CONFIG_DIR"] = os.path.join(d, "dav"); os.environ["DAV_PUBLIC_URL"] = "https://hub.exemple.fr:6443/dav"
sys.path.insert(0, os.path.dirname(__file__))
import app as appmod

class Api(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.c = appmod.app.test_client()

    def test_grants_and_dav(self):
        self.assertEqual(self.c.post("/grants", json={"owner": "alice", "app": "x"}).status_code, 400)
        r = self.c.post("/grants", json={"owner": "alice", "app": "calendar", "grantee": "bob", "rights": "r", "actor": "alice"}); self.assertEqual(r.status_code, 201, r.json)
        self.assertEqual(r.json["grant"]["rights_text"], "r"); self.assertTrue(r.json["dav"]["ok"]); self.assertEqual(r.json["dav"]["rules"], 1)
        self.c.post("/grants", json={"owner": "alice", "app": "calendar", "grantee": "bob", "rights": "raed"})       # mise à jour
        self.c.post("/grants", json={"owner": "alice", "app": "infolog", "grantee_kind": "group", "grantee": "secretariat", "rights": "r"})
        g = self.c.get("/grants?user=bob&groups=secretariat").json
        self.assertEqual(len(g["grants"]), 2); self.assertEqual(g["effective"]["calendar"]["alice"], 15); self.assertEqual(g["effective"]["infolog"]["alice"], 1); self.assertEqual(len(g["received"]), 2)
        self.assertEqual(self.c.get("/grants/effective?app=calendar&user=eve").json["text"], {"eve": "raedp"})
        txt = open(os.path.join(d, "dav", "rights"), encoding="utf-8").read(); self.assertIn("user: ^bob$", txt); self.assertIn("rRwW", txt)
        gid = g["grants"][0]["id"]; self.assertEqual(self.c.delete("/grants/%d" % gid).json["ok"], True); self.assertEqual(self.c.delete("/grants/%d" % gid).status_code, 404)
        self.assertEqual(self.c.post("/dav/rights/rebuild").json["rules"], 0)
        me = self.c.get("/dav/me?user=bob").json; self.assertEqual(me["principal"], "https://hub.exemple.fr:6443/dav/bob/"); self.assertIn("thunderbird", me["clients"])
        self.assertEqual(self.c.get("/dav/me?user=../x").status_code, 400)

    def test_categories_links_prefs(self):
        r = self.c.post("/categories", json={"name": "Urgent", "app": "*", "color": "#ff0000"}); self.assertEqual(r.status_code, 201); cid = r.json["category"]["id"]
        self.c.post("/categories", json={"name": "Bâtiment", "app": "infolog", "parent_id": cid}); self.assertEqual(self.c.post("/categories", json={"name": "x", "color": "rouge"}).status_code, 400)
        self.assertEqual(len(self.c.get("/categories?app=infolog").json["categories"]), 2); self.assertEqual(len(self.c.get("/categories?app=calendar").json["categories"]), 1)
        self.assertEqual(self.c.put("/categories/%d" % cid, json={"name": "Très urgent"}).json["category"]["name"], "Très urgent")
        self.assertEqual(self.c.delete("/categories/%d" % cid).json["ok"], True); self.assertEqual(len(self.c.get("/categories").json["categories"]), 0)   # enfant supprimé avec le parent
        r = self.c.post("/links", json={"app1": "ticket", "id1": "42", "app2": "contact", "id2": "7", "remark": "demandeur"}); self.assertEqual(r.status_code, 201)
        self.c.post("/links", json={"app1": "ticket", "id1": "42", "app2": "contact", "id2": "7"})   # doublon ignoré
        self.assertEqual(self.c.post("/links", json={"app1": "a", "id1": "1", "app2": "a", "id2": "1"}).status_code, 400)
        l = self.c.get("/links?app=contact&id=7").json["links"]; self.assertEqual(len(l), 1); self.assertEqual(l[0]["other"], {"app": "ticket", "id": "42"})
        self.assertEqual(self.c.get("/links?app=ticket&id=42").json["links"][0]["other"], {"app": "contact", "id": "7"})
        self.assertEqual(self.c.delete("/links/%d" % l[0]["id"]).json["ok"], True)
        self.c.put("/prefs", json={"level": "default", "app": "*", "key": "lang", "value": "fr"}); self.c.put("/prefs", json={"level": "forced", "app": "*", "key": "tz", "value": "Europe/Paris"})
        self.c.put("/prefs", json={"level": "user", "subject": "bob", "app": "calendar", "key": "view", "value": "month"}); self.assertEqual(self.c.put("/prefs", json={"level": "user", "key": "x"}).status_code, 400)
        self.assertEqual(self.c.get("/prefs?app=calendar&user=bob").json["prefs"], {"lang": "fr", "tz": "Europe/Paris", "view": "month"})
        self.assertEqual(len(self.c.get("/prefs?raw=1").json["prefs"]), 3); self.assertTrue(self.c.delete("/prefs", json={"level": "user", "subject": "bob", "app": "calendar", "key": "view"}).json["ok"])
        self.assertTrue(self.c.get("/journal").json["journal"]); self.assertEqual(self.c.get("/health").json["status"], "ok")

if __name__ == "__main__":
    unittest.main()
