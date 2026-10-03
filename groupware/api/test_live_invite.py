# -*- coding: utf-8 -*-
"""#669 : invitations contre un Radicale RÉEL (sauté sans GROUPWARE_LIVE_DAV) : copie chez le participant, réponse propagée,
participant retiré, suppression de la copie = déclin, alarme conservée."""
import os, sys, tempfile, unittest
LIVE = os.environ.get("GROUPWARE_LIVE_DAV")
if LIVE:
    d = tempfile.mkdtemp(); os.environ.setdefault("GROUPWARE_DATA_DIR", d); os.environ.setdefault("DAV_PUBLIC_URL", LIVE); os.environ["DAV_INTERNAL_URL"] = LIVE
sys.path.insert(0, os.path.dirname(__file__))
W = "&from=2026-11-01T00:00&to=2026-11-30T00:00"

@unittest.skipUnless(LIVE, "GROUPWARE_LIVE_DAV absent")
class LiveInvite(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import app as appmod
        cls.c = appmod.app.test_client(); cls.m = appmod; cls.c.post("/dav/rights/rebuild")
        for owner, coll in (("alice", "agenda-inv"), ("bob", "agenda"), ("svc", "agenda")):
            try: appmod.dav().delete_collection(owner, coll)
            except Exception: pass

    def test_flow(self):
        c = self.c
        self.assertEqual(c.post("/calendars", json={"user": "alice", "name": "inv"}).status_code, 201)
        r = c.post("/events", json={"user": "alice", "owner": "alice", "book": "agenda-inv", "event": {"title": "Comité", "start": "2026-11-03T14:00", "end": "2026-11-03T15:00", "attendees": ["bob", "svc"], "alarm": 30}})
        self.assertEqual(r.status_code, 201, r.json); uid = r.json["event"]["uid"]; self.assertEqual(r.json["event"]["organizer"], "alice"); self.assertEqual(r.json["event"]["alarm"], 30)
        bob = c.get("/events?user=bob" + W).json["events"]; self.assertEqual(len(bob), 1); self.assertEqual(bob[0]["invite_from"], "alice/agenda-inv"); self.assertEqual(bob[0]["my_partstat"], "NEEDS-ACTION"); self.assertEqual(bob[0]["alarm"], 30)
        r = c.post("/events/bob/agenda/%s/reply" % uid, json={"user": "bob", "partstat": "accepted"}); self.assertEqual(r.status_code, 200, r.json)
        self.assertEqual([a["partstat"] for a in r.json["event"]["attendees"]], ["ACCEPTED", "NEEDS-ACTION"])
        al = c.get("/events?user=alice&book=agenda-inv" + W).json["events"][0]; self.assertEqual(al["attendees"][0], {"name": "bob", "partstat": "ACCEPTED"}); self.assertEqual(al["invite_from"], "")
        self.assertEqual(c.post("/events/alice/agenda-inv/%s/reply" % uid, json={"user": "carol", "partstat": "accepted"}).status_code, 403)
        # modification par l'organisatrice : propagée, réponse de bob conservée, svc retiré
        r = c.put("/events/alice/agenda-inv/%s" % uid, json={"user": "alice", "event": {"title": "Comité (salle 1)", "attendees": ["bob"]}}); self.assertEqual(r.status_code, 200, r.json)
        self.assertEqual(r.json["event"]["attendees"], [{"name": "bob", "partstat": "ACCEPTED"}])
        bob = c.get("/events?user=bob" + W).json["events"]; self.assertEqual(bob[0]["title"], "Comité (salle 1)"); self.assertEqual(bob[0]["my_partstat"], "ACCEPTED")
        self.assertEqual(c.get("/events?user=svc" + W).json["total"], 0)
        # bob supprime sa copie = décline
        self.assertEqual(c.delete("/events/bob/agenda/%s?user=bob" % uid).status_code, 200)
        al = c.get("/events?user=alice&book=agenda-inv" + W).json["events"][0]; self.assertEqual(al["attendees"][0]["partstat"], "DECLINED")
        # suppression par l'organisatrice : plus rien nulle part
        c.put("/events/alice/agenda-inv/%s" % uid, json={"user": "alice", "event": {"attendees": ["bob", "svc"]}})
        self.assertEqual(c.get("/events?user=svc" + W).json["total"], 1)
        self.assertEqual(c.delete("/events/alice/agenda-inv/%s?user=alice" % uid).status_code, 200)
        self.assertEqual(c.get("/events?user=svc" + W).json["total"], 0); self.assertEqual(c.get("/events?user=bob" + W).json["total"], 0)

if __name__ == "__main__":
    unittest.main()
