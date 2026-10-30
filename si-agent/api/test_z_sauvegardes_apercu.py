# -*- coding: utf-8 -*-
"""#937 : tuile « Sauvegardes » -- assemblage pur et route /sauvegardes/apercu.
`cd si-agent/api && python3 -m unittest test_z_sauvegardes_apercu`."""
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
os.environ.setdefault("SI_AGENT_DB_PATH", os.path.join(tempfile.mkdtemp(), "si-agent.db"))
os.environ.setdefault("SI_AGENT_PURGE_THREAD", "0")
os.environ.setdefault("SI_AGENT_CA_FILE", os.path.join(tempfile.mkdtemp(), "ca.crt"))
sys.path.insert(0, HERE)
import app as A  # noqa: E402
import store  # noqa: E402
import sauvegardes_apercu as sa  # noqa: E402

NOW = sa._epoch("2026-10-30T10:00:00Z")


class Postes(unittest.TestCase):
    def test_etats(self):
        agents = [{"agent_id": a, "hostname": a.upper()} for a in ("pc-ok", "pc-vieux", "pc-ko", "pc-dest", "pc-jamais", "pc-moyen")]
        bon = {"archive": {"nom": "bk.zip", "octets": 1000}, "destinations": [{"type": "usb", "ok": True}, {"type": "unc", "ok": True}], "confs": [1, 2], "erreurs": []}
        sauv = [("pc-ok", "PC-OK", "2026-10-29T10:00:00Z", bon),
                ("pc-vieux", "PC-VIEUX", "2026-09-01T10:00:00Z", bon),
                ("pc-ko", "PC-KO", "2026-10-29T10:00:00Z", {"archive": {}, "destinations": [], "erreurs": ["7z KO"]}),
                ("pc-dest", "PC-DEST", "2026-10-29T10:00:00Z", dict(bon, destinations=[{"type": "unc", "ok": False, "erreur": "refusé"}])),
                ("pc-moyen", "PC-MOYEN", "2026-10-15T10:00:00Z", bon)]
        pousses = [{"backup_id": "pc-ok", "ok": True, "snapshot": "host/pc-ok/2026-10-29T10:05:00Z"}, {"backup_id": "pc-ok", "ok": False, "erreur": "ancienne"}]
        p = sa.postes(sauv, pousses, agents, NOW)
        etats = {x["agent_id"]: x["etat"] for x in p}
        self.assertEqual(etats, {"pc-ok": "ok", "pc-vieux": "critique", "pc-ko": "critique", "pc-dest": "critique", "pc-jamais": "jamais", "pc-moyen": "attention"})
        self.assertEqual([x["agent_id"] for x in p][:3], ["pc-dest", "pc-ko", "pc-vieux"], "critiques d'abord, par nom")
        ok = next(x for x in p if x["agent_id"] == "pc-ok")
        self.assertEqual(ok["pbs"]["snapshot"], "host/pc-ok/2026-10-29T10:05:00Z", "la poussée la plus récente l'emporte")
        self.assertEqual(ok["destinations_ok"], ["usb", "unc"])
        self.assertEqual(ok["age_j"], 1.0)
        self.assertIsNone(next(x for x in p if x["agent_id"] == "pc-jamais")["pbs"])

    def test_destination_partielle(self):
        d = {"archive": {"nom": "a.zip"}, "destinations": [{"type": "usb", "ok": True}, {"type": "unc", "ok": False}], "erreurs": []}
        p = sa.postes([("x", "X", "2026-10-30T09:00:00Z", d)], [], [{"agent_id": "x", "hostname": "X"}], NOW)
        self.assertEqual((p[0]["etat"], p[0]["destinations_ko"]), ("attention", ["unc"]))


class Autres(unittest.TestCase):
    def test_pbs_copies_nas(self):
        b = sa.pbs([("pbs10", "pbs10", "2026-10-30T09:00:00Z", {"datastores": [{"name": "ds1", "used_percent": 91.0, "total": 10, "avail": 1}],
                                                                "groups": [{"id": "101", "state": "ok"}, {"id": "102", "state": "en retard"}, {"id": "9", "state": "inactif"}],
                                                                "alerts": [{"severity": "warning", "message": "ds1 à 91 %"}], "summary": {"state": "warning", "late": 1}})])
        self.assertEqual((b[0]["etat"], b[0]["en_retard"], b[0]["inactifs"], b[0]["datastores"][0]["pct"]), ("attention", 1, 1, 91.0))
        self.assertEqual(sa.pbs([("p", "p", "t", {"error": "pas PBS"})])[0]["etat"], "erreur")
        c = sa.copies([("secours", "secours", "t", {"backups": [{"ok": True, "present": True, "age_h": 12}, {"ok": False, "present": False, "age_h": 80}], "free_bytes": 5, "alerts": ["x"]})],
                      {"ok": 3, "attention": 1, "critique": 0})
        self.assertEqual((c["hotes"][0]["copies"], c["hotes"][0]["echecs"], c["hotes"][0]["absentes"], c["hotes"][0]["plus_vieille_h"]), (2, 1, 1, 80))
        self.assertEqual(c["invites"]["attention"], 1)
        n = sa.nas([("relais", "relais", "t", {"nas": [{"name": "qnap", "host": "10.0.0.9", "ok": True, "volumes": [{"nom": "DataVol1", "pct": 96.0, "ko": 10}]},
                                                       {"name": "mort", "ok": False, "error": "timeout"}]})])
        self.assertEqual([x["etat"] for x in n], ["critique", "erreur"])
        self.assertIsNone(n[0]["snapshots"], "connecteur QNAP à venir")

    def test_resume_verdict(self):
        r = sa.assembler([], [], [], [], [], None, [], now=NOW)
        self.assertEqual((r["resume"]["verdict"], r["backuppc"]["etat"]), ("ok", "non relevé"))
        r = sa.assembler([], [], [{"agent_id": "pc", "hostname": "PC"}], [], [], {"critique": 1}, [], now=NOW)
        self.assertEqual(r["resume"]["verdict"], "critique")
        self.assertEqual(r["resume"]["postes"]["jamais"], 1)
        r = sa.assembler([], [], [{"agent_id": "pc", "hostname": "PC"}], [], [], None, [], now=NOW)
        self.assertEqual(r["resume"]["verdict"], "attention", "un poste jamais sauvegardé = attention")


class Route(unittest.TestCase):
    def setUp(self):
        self.c = A.app.test_client()
        for a in ("pc-ap1", "pbs-ap"):
            try:
                store.create_agent(A.DB_PATH, a, "siege")
            except ValueError:
                pass
        store.ingest_measurements(A.DB_PATH, "pc-ap1", [
            {"task": "plugin:poste-windows", "at": "2026-10-30T08:00:00Z", "agent_id": "pc-ap1", "data": {"poste": {"nom": "PC-AP1"}}},
            {"task": "sauvegarde-poste", "at": "2026-10-30T08:30:00Z", "agent_id": "pc-ap1",
             "data": {"archive": {"nom": "bk.zip", "octets": 10}, "destinations": [{"type": "unc", "ok": True, "cible": "\\\\pbs10\\postes\\bk.zip"}], "erreurs": [], "confs": [{"app": "Firefox"}]}}])
        store.ingest_measurements(A.DB_PATH, "pbs-ap", [
            {"task": "plugin:pbs", "at": "2026-10-30T08:00:00Z", "agent_id": "pbs-ap", "data": {"datastores": [{"name": "ds", "used_percent": 40.0}], "groups": [], "alerts": [], "summary": {"state": "ok"}}},
            {"task": "pbs-push", "at": "2026-10-30T08:40:00Z", "agent_id": "pbs-ap", "data": {"ok": True, "action": "push", "backup_id": "pc-ap1", "snapshot": "host/pc-ap1/x"}}])
        store.set_setting(A.DB_PATH, "postes-sauvegarde-pbs", {"pousseur": "pbs-ap", "repository": "r", "namespace": "postes"})

    def test_apercu(self):
        r = self.c.get("/sauvegardes/apercu")
        self.assertEqual(r.status_code, 200)
        j = r.get_json()
        self.assertEqual(set(j), {"resume", "postes", "pbs", "copies", "nas", "backuppc"})
        p = next(x for x in j["postes"] if x["agent_id"] == "pc-ap1")
        self.assertEqual((p["etat"], p["archive"], p["pbs"]["snapshot"]), ("ok", "bk.zip", "host/pc-ap1/x"))
        self.assertEqual(j["pbs"][0]["serveur"], "pbs-ap")
        self.assertEqual(j["backuppc"]["etat"], "non relevé")
        self.assertNotIn("secret", r.get_data(as_text=True).lower())


if __name__ == "__main__":
    unittest.main()
