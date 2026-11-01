# -*- coding: utf-8 -*-
"""#666 : agenda contre un Radicale RÉEL (sauté sans GROUPWARE_LIVE_DAV) : agenda créé, événement récurrent développé, partage
lecture/écriture, disponibilités sans détail, ressource réservée puis conflit refusé, modification conservant la récurrence."""
import os, sys, tempfile, unittest
LIVE = os.environ.get("GROUPWARE_LIVE_DAV")
if LIVE:
    d = tempfile.mkdtemp(); os.environ.setdefault("GROUPWARE_DATA_DIR", d); os.environ.setdefault("DAV_PUBLIC_URL", LIVE); os.environ["DAV_INTERNAL_URL"] = LIVE
sys.path.insert(0, os.path.dirname(__file__))

@unittest.skipUnless(LIVE, "GROUPWARE_LIVE_DAV absent")
class LiveCal(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import app as appmod
        cls.c = appmod.app.test_client(); cls.m = appmod; cls.c.post("/dav/rights/rebuild")
        for owner, coll in (("alice", "agenda-test"), (appmod.RESOURCE_OWNER, "agenda-salle-test")):
            try: appmod.dav().delete_collection(owner, coll)
            except Exception: pass

    def test_flow(self):
        c = self.c
        r = c.post("/calendars", json={"user": "alice", "name": "test", "displayname": "Agenda de test"}); self.assertEqual(r.status_code, 201, r.json); self.assertEqual(r.json["calendar"]["name"], "agenda-test")
        r = c.post("/events", json={"user": "alice", "owner": "alice", "book": "agenda-test", "event": {"title": "Point hebdo", "start": "2026-10-05T09:00", "end": "2026-10-05T09:30", "rrule": {"freq": "weekly", "byday": "MO"}}})
        self.assertEqual(r.status_code, 201, r.json); uid = r.json["event"]["uid"]; self.assertTrue(r.json["event"]["recurring"])
        ev = c.get("/events?user=alice&from=2026-10-01T00:00&to=2026-11-01T00:00&book=agenda-test").json; self.assertEqual(ev["total"], 4); self.assertEqual(ev["events"][1]["start"][:10], "2026-10-12")
        self.assertEqual(c.get("/events?user=bob&from=2026-10-01T00:00&to=2026-11-01T00:00").json["total"], 0)
        fb = c.get("/freebusy?users=alice,bob&from=2026-10-05T00:00&to=2026-10-06T00:00").json["busy"]; self.assertEqual(len(fb["alice"]), 1); self.assertEqual(fb["bob"], []); self.assertNotIn("title", fb["alice"][0])
        c.post("/grants", json={"owner": "alice", "app": "calendar", "grantee": "bob", "rights": "r"})
        self.assertEqual(c.get("/events?user=bob&from=2026-10-01T00:00&to=2026-11-01T00:00&book=agenda-test").json["total"], 4)
        self.assertEqual(c.post("/events", json={"user": "bob", "owner": "alice", "book": "agenda-test", "event": {"title": "x", "start": "2026-10-07T10:00"}}).status_code, 403)
        r = c.put("/events/alice/agenda-test/%s" % uid, json={"user": "alice", "event": {"title": "Point hebdo (salle 2)", "location": "Salle 2"}}); self.assertEqual(r.status_code, 200, r.json); self.assertTrue(r.json["event"]["recurring"]); self.assertEqual(r.json["event"]["location"], "Salle 2")
        self.assertEqual(c.get("/events?user=alice&from=2026-10-01T00:00&to=2026-11-01T00:00&book=agenda-test").json["total"], 4)
        # ressource : réservation ouverte, conflit refusé, suppression réservée au demandeur
        r = c.post("/resources", json={"name": "Salle test", "slug": "salle-test", "kind": "salle", "capacity": 8}); self.assertEqual(r.status_code, 201, r.json)
        r = c.post("/events", json={"user": "bob", "owner": self.m.RESOURCE_OWNER, "book": "agenda-salle-test", "event": {"title": "Réunion client", "start": "2026-10-20T10:00", "end": "2026-10-20T12:00"}}); self.assertEqual(r.status_code, 201, r.json); ruid = r.json["event"]["uid"]
        r = c.post("/events", json={"user": "alice", "owner": self.m.RESOURCE_OWNER, "book": "agenda-salle-test", "event": {"title": "Chevauche", "start": "2026-10-20T11:00", "end": "2026-10-20T11:30"}}); self.assertEqual(r.status_code, 409); self.assertEqual(len(r.json["conflicts"]), 1)
        self.assertEqual(c.post("/events", json={"user": "alice", "owner": self.m.RESOURCE_OWNER, "book": "agenda-salle-test", "event": {"title": "Après", "start": "2026-10-20T12:00", "end": "2026-10-20T13:00"}}).status_code, 201)
        cals = c.get("/calendars?user=alice").json["calendars"]; self.assertTrue(any(x["resource"] and x["name"] == "agenda-salle-test" for x in cals))
        fb = c.get("/freebusy?resources=salle-test&from=2026-10-20T00:00&to=2026-10-21T00:00").json["busy"]["ressource:salle-test"]; self.assertEqual(len(fb), 1)   # 10-12 et 12-13 fusionnés
        self.assertEqual(c.delete("/events/%s/agenda-salle-test/%s?user=alice" % (self.m.RESOURCE_OWNER, ruid)).status_code, 403)
        self.assertEqual(c.delete("/events/%s/agenda-salle-test/%s?user=bob" % (self.m.RESOURCE_OWNER, ruid)).json["ok"], True)
        self.assertEqual(c.delete("/resources/salle-test").json["ok"], True)

if __name__ == "__main__":
    unittest.main()
