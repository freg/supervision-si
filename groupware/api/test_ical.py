import unittest, ical
from datetime import datetime, date, timedelta
class I(unittest.TestCase):
    def test_validate_serialize_parse(self):
        ev, err = ical.validate({"title": "Réunion", "start": "2026-10-05T14:00", "end": "2026-10-05T15:30", "location": "Salle 1", "categories": ["interne"], "rrule": {"freq": "weekly", "byday": "MO,WE", "until": "2026-12-31T00:00"}})
        self.assertIsNone(err); txt = ical.serialize(ev, "u1"); self.assertIn("RRULE:FREQ=WEEKLY", txt); self.assertIn("BYDAY=MO,WE", txt)
        p = ical.parse(txt); self.assertEqual(p["title"], "Réunion"); self.assertEqual(p["start"].hour, 14); self.assertFalse(p["all_day"]); self.assertEqual(p["categories"], ["interne"]); self.assertIn("FREQ=WEEKLY", p["rrule_text"])
        self.assertIn("title", ical.validate({"start": "2026-10-05"})[1]); self.assertIn("end", ical.validate({"title": "x", "start": "2026-10-05T10:00", "end": "2026-10-05T09:00"})[1]); self.assertIn("freq", ical.validate({"title": "x", "start": "2026-10-05T10:00", "rrule": {"freq": "hourly"}})[1])
        ad, _ = ical.validate({"title": "Congé", "start": "2026-10-10", "all_day": True}); self.assertEqual(ad["end"], date(2026, 10, 11)); p2 = ical.parse(ical.serialize(ad, "u2")); self.assertTrue(p2["all_day"]); self.assertEqual(p2["end"], date(2026, 10, 11))
    def test_occurrences_and_busy(self):
        ev, _ = ical.validate({"title": "Point", "start": "2026-10-05T09:00", "end": "2026-10-05T09:30", "rrule": {"freq": "weekly", "byday": "MO"}})
        p = ical.parse(ical.serialize(ev, "u3"))
        occ = ical.occurrences(p, "2026-10-01T00:00", "2026-11-01T00:00"); self.assertEqual([o[0].day for o in occ], [5, 12, 19, 26])
        single, _ = ical.validate({"title": "Seul", "start": "2026-10-20T10:00", "end": "2026-10-20T12:00"}); single = ical.parse(ical.serialize(single, "u4"))
        self.assertEqual(len(ical.occurrences(single, "2026-10-01T00:00", "2026-10-15T00:00")), 0); self.assertEqual(len(ical.occurrences(single, "2026-10-20T11:00", "2026-10-21T00:00")), 1)
        transp, _ = ical.validate({"title": "Libre", "start": "2026-10-20T10:00", "end": "2026-10-20T11:00", "transparent": True}); transp = ical.parse(ical.serialize(transp, "u5"))
        busy = ical.busy_blocks([p, single, transp], "2026-10-19T00:00", "2026-10-21T00:00"); self.assertEqual(len(busy), 2); self.assertEqual(busy[1][0].hour, 10); self.assertEqual(busy[1][1].hour, 12)
        overlap, _ = ical.validate({"title": "Chevauche", "start": "2026-10-20T11:30", "end": "2026-10-20T13:00"}); overlap = ical.parse(ical.serialize(overlap, "u6"))
        self.assertEqual(len(ical.busy_blocks([single, overlap], "2026-10-20T00:00", "2026-10-21T00:00")), 1)
    def test_conflicts(self):
        room, _ = ical.validate({"title": "Réservé", "start": "2026-10-20T10:00", "end": "2026-10-20T12:00"}); room = ical.parse(ical.serialize(room, "r1"))
        cand, _ = ical.validate({"title": "Demande", "start": "2026-10-20T11:00", "end": "2026-10-20T11:30"}); self.assertEqual(len(ical.conflicts(cand, [room])), 1)
        cand2, _ = ical.validate({"title": "Après", "start": "2026-10-20T12:00", "end": "2026-10-20T13:00"}); self.assertEqual(ical.conflicts(cand2, [room]), [])
        self.assertEqual(ical.conflicts(dict(cand, uid="r1"), [room]), [])        # soi-même
        pub = ical.public(room); self.assertEqual(pub["start"], "2026-10-20T10:00+02:00"); self.assertFalse(pub["recurring"])
if __name__ == "__main__": unittest.main()
