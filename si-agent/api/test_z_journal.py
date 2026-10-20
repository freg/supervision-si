# -*- coding: utf-8 -*-
"""#795 : journal des chantiers -- validation, indicateurs (week-end, hors heures), import / export CSV, suggestions."""
import datetime
import os
import sys
import tempfile
import unittest

os.environ.setdefault("SI_AGENT_DB_PATH", os.path.join(tempfile.mkdtemp(), "t.db"))
os.environ.setdefault("SI_AGENT_PURGE_THREAD", "0")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import app as appmod  # noqa: E402
import journal as J  # noqa: E402
import store  # noqa: E402


class Pur(unittest.TestCase):
    def test_validate(self):
        e, err = J.validate({"chantier": "Serveurs", "day": "20/10/2026", "start": "17h50", "end": "18:17:00", "acte": "Bascule du site A"})
        self.assertIsNone(err)
        self.assertEqual((e["day"], e["start"], e["end"], e["nature"], e["statut"]), ("2026-10-20", "17:50", "18:17", "Acte", "Fait"))
        for bad, msg in (({"acte": "x"}, "chantier"), ({"chantier": "c"}, "acte"), ({"chantier": "c", "acte": "a", "day": "31/02/2026"}, "date"),
                         ({"chantier": "c", "acte": "a", "start": "25:00"}, "heure"), ({"chantier": "c", "acte": "a", "nature": "Autre"}, "nature"),
                         ({"chantier": "c", "acte": "a", "statut": "Fini"}, "statut")):
            self.assertIn(msg, J.validate(bad)[1], bad)

    def test_heures(self):
        mar = {"day": "2026-10-20"}
        self.assertFalse(J.off_hours(dict(mar, start="09:00", end="12:15")))          # bornes incluses
        self.assertTrue(J.off_hours(dict(mar, start="12:22", end="14:59")))           # début pendant la pause
        self.assertTrue(J.off_hours(dict(mar, start="17:50", end="18:17")))           # fin après 18 h
        self.assertTrue(J.off_hours({"day": "2026-10-18", "start": "10:00"}))         # dimanche
        self.assertFalse(J.off_hours({"day": None, "start": "23:00"}))                 # non daté : pas compté
        self.assertEqual(J.duration_min({"start": "17:50", "end": "18:17"}), 27)
        self.assertEqual(J.duration_min({"start": "23:30", "end": "00:10"}), 40)
        self.assertIsNone(J.duration_min({"start": "10:00"}))
        self.assertEqual(J.weekday_fr("2026-10-20"), "mardi")

    def test_stats(self):
        rows = [J.validate(r)[0] for r in (
            {"chantier": "B", "day": "2026-10-18", "start": "22:29", "end": "23:20", "acte": "a", "nature": "Relance"},
            {"chantier": "B", "day": "2026-10-20", "start": "10:00", "end": "11:00", "acte": "b"},
            {"chantier": "A", "acte": "c", "statut": "À faire"})]
        s = {x["chantier"]: x for x in J.stats(rows)}
        self.assertEqual((s["B"]["lignes"], s["B"]["weekend"], s["B"]["hors_heures"], s["B"]["minutes"], s["B"]["natures"]["Relance"]), (2, 1, 1, 111, 1))
        self.assertEqual((s["B"]["premier"], s["B"]["dernier"]), ("2026-10-18", "2026-10-20"))
        self.assertEqual((s["A"]["a_faire"], s["A"]["premier"]), (1, None))

    def test_csv_aller_retour(self):
        rows = [J.validate({"chantier": "SMS", "day": "2026-10-20", "start": "10:27", "end": "12:07", "acte": "Bascule ; « 4G »",
                            "description": "ligne 1\nligne 2", "nature": "Intervention"})[0]]
        txt = J.to_csv(rows)
        self.assertTrue(txt.startswith("﻿Chantier;Date;Jour"))
        self.assertIn("20/10/2026;mardi;10:27;12:07;1:40;Intervention", txt)
        back = J.parse_csv(txt)
        self.assertEqual((back[0]["acte"], back[0]["description"], J.validate(back[0])[0]["day"]), ("Bascule ; « 4G »", "ligne 1\nligne 2", "2026-10-20"))
        sans_col = J.parse_csv("Date,Acte\n20/10/2026,Test\n\n", chantier="Divers")
        self.assertEqual(sans_col, [{"day": "20/10/2026", "acte": "Test", "chantier": "Divers"}])

    def test_suggestion(self):
        s = J.suggestion_for({"id": 7, "at": "2026-10-18T20:29:00Z", "kind": "migration", "severity": "info", "message": "migration : start B8 par freg -> ok"})
        self.assertEqual((s["chantier"], s["nature"], s["event_id"], s["statut"]), ("Migration des serveurs", "Intervention", 7, "Fait"))
        if J._tz() is not None:
            self.assertEqual((s["day"], s["start"]), ("2026-10-18", "22:29"))      # heure de Paris (UTC+2 en octobre)
        self.assertIsNone(J.suggestion_for({"id": 8, "at": "x", "kind": "probe-alert", "severity": "warning", "message": "m"}))
        self.assertEqual(J.suggestion_for({"id": 9, "at": "x", "kind": "probe-alert", "severity": "critical", "message": "m"})["statut"], "En cours")
        self.assertIsNone(J.suggestion_for({"id": 10, "at": "x", "kind": "latency", "severity": "info", "message": "m"}))


class Routes(unittest.TestCase):
    def setUp(self):
        self.c = appmod.app.test_client()
        conn = store._connect(appmod.DB_PATH)
        J.ensure(conn)
        conn.execute("DELETE FROM journal")
        conn.commit()
        conn.close()

    def test_parcours(self):
        r = self.c.put("/journal", json={"entry": {"chantier": "Serveurs", "day": "2026-10-20", "start": "17:50", "end": "18:17", "acte": "Bascule du site A",
                                                   "nature": "Intervention"}, "actor": "alice"})
        self.assertEqual(r.status_code, 200, r.get_json())
        eid = r.get_json()["entry"]["id"]
        self.assertEqual(self.c.put("/journal", json={"entry": {"chantier": "Serveurs"}}).status_code, 400)
        r = self.c.put("/journal", json={"entry": {"id": eid, "chantier": "Serveurs", "day": "2026-10-20", "start": "17:50", "end": "18:17",
                                                   "acte": "Bascule du site A", "resultat": "accessible à 18 h 17", "nature": "Intervention"}})
        self.assertEqual(r.get_json()["entry"]["resultat"], "accessible à 18 h 17")
        csv_txt = J.to_csv([{"chantier": "SMS", "day": "2026-10-20", "start": "10:27", "end": "12:07", "nature": "Intervention", "acte": "Bascule 4G",
                             "statut": "Fait"}, {"chantier": "SMS", "nature": "Acte", "acte": "Clé définitive", "statut": "À faire"}])
        r = self.c.post("/journal/import", json={"csv": csv_txt, "actor": "alice"}).get_json()
        self.assertEqual((r["added"], r["skipped"], r["errors"]), (2, 0, []))
        r = self.c.post("/journal/import", json={"rows": [{"chantier": "SMS", "day": "2026-10-20", "start": "10:27", "acte": "bascule 4g"},
                                                          {"chantier": "SMS", "acte": "x", "day": "99/99/2026"}]}).get_json()
        self.assertEqual((r["added"], r["skipped"], len(r["errors"])), (0, 1, 1))
        v = self.c.get("/journal").get_json()
        self.assertEqual((len(v["entries"]), v["chantiers"]), (3, ["Serveurs", "SMS"]))
        e = [x for x in v["entries"] if x["acte"] == "Bascule du site A"][0]
        self.assertEqual((e["jour"], e["duree_min"], e["hors_heures"]), ("mardi", 27, True))
        self.assertEqual(len(self.c.get("/journal?chantier=SMS").get_json()["entries"]), 2)
        r = self.c.get("/journal/export.csv?chantier=SMS")
        self.assertEqual(r.mimetype, "text/csv")
        self.assertIn("journal-chantiers-SMS.csv", r.headers["Content-Disposition"])
        self.assertIn("Bascule 4G", r.data.decode("utf-8"))
        self.assertTrue(self.c.delete("/journal/%d" % eid).get_json()["ok"])
        self.assertEqual(len(self.c.get("/journal").get_json()["entries"]), 2)

    def test_suggestions(self):
        conn = store._connect(appmod.DB_PATH)
        now = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        conn.execute("INSERT INTO events (at, kind, severity, message, source) VALUES (?, 'migration', 'info', 'migration : start B8 par alice -> ok', 'central')", (now,))
        conn.execute("INSERT INTO events (at, kind, severity, message, source) VALUES (?, 'latency', 'info', 'sans intérêt', 'central')", (now[:-3] + "01Z",))
        conn.commit()
        conn.close()
        s = self.c.get("/journal/suggestions").get_json()["suggestions"]
        mine = [x for x in s if "start B8" in x["acte"]]
        self.assertEqual(len(mine), 1)
        self.assertFalse(any(x["acte"] == "sans intérêt" for x in s))
        r = self.c.post("/journal/suggestions/%d" % mine[0]["event_id"], json={"actor": "alice", "chantier": "Serveurs"}).get_json()
        self.assertEqual((r["entry"]["chantier"], r["entry"]["nature"]), ("Serveurs", "Intervention"))
        self.assertEqual(self.c.post("/journal/suggestions/%d" % mine[0]["event_id"], json={}).status_code, 400)   # déjà au journal
        self.assertFalse(any("start B8" in x["acte"] for x in self.c.get("/journal/suggestions").get_json()["suggestions"]))


if __name__ == "__main__":
    unittest.main()
