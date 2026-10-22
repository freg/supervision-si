# -*- coding: utf-8 -*-
"""#822 diffusions en cascade : validation, ordre des dépendances, cibles, plan par agent, gestes, API."""
import os
import sys
import tempfile
import unittest

os.environ.setdefault("SI_AGENT_DB_PATH", os.path.join(tempfile.mkdtemp(), "t.db"))
os.environ.setdefault("MODELES_THREAD", "0")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import app as appmod  # noqa: E402
import diffusion as D  # noqa: E402
import store  # noqa: E402


class Pur(unittest.TestCase):
    def test_ordre_et_valider(self):
        e = [{"id": "c", "apres": ["b"]}, {"id": "a"}, {"id": "b", "apres": ["a"]}]
        self.assertEqual([x["id"] for x in D.ordre(e)], ["a", "b", "c"])
        with self.assertRaises(ValueError):
            D.ordre([{"id": "a", "apres": ["b"]}, {"id": "b", "apres": ["a"]}])
        with self.assertRaises(ValueError):
            D.ordre([{"id": "a", "apres": ["z"]}])
        r, err = D.valider(D.EXEMPLE, {"pve-preflight", "guest-usage"})
        self.assertIsNone(err)
        self.assertEqual([x["id"] for x in r["etapes"]], ["maj", "preflight", "releve"])
        self.assertIn("sonde inconnue", D.valider(D.EXEMPLE, {"autre"})[1])
        self.assertIn("cible vide", D.valider({"nom": "x", "etapes": [{"id": "a", "type": "mise_a_jour"}]})[1])
        self.assertIn("cycle", D.valider({"nom": "x", "cible": {"os": ["linux"]}, "etapes": [{"id": "a", "type": "mise_a_jour", "apres": ["b"]},
                                                                                          {"id": "b", "type": "mise_a_jour", "apres": ["a"]}]})[1])
        self.assertIn("type inconnu", D.valider({"nom": "x", "cible": {"os": ["linux"]}, "etapes": [{"id": "a", "type": "rm"}]})[1])

    def test_cibles(self):
        ag = [{"agent_id": "a", "os": "linux", "plugin_ids": ["guest-usage"]}, {"agent_id": "b", "os": "linux", "plugin_ids": ["pve-remote", "x"]},
              {"agent_id": "c", "os": "windows", "plugin_ids": []}]
        f = lambda c: [x["agent_id"] for x in D.cibles({"cible": c}, ag)]
        self.assertEqual(f({"plugins_any": ["guest-usage", "pve-remote"]}), ["a", "b"])
        self.assertEqual(f({"plugins_any": ["guest-usage", "pve-remote"], "exclure": ["b"]}), ["a"])
        self.assertEqual(f({"plugins_all": ["pve-remote", "x"]}), ["b"])
        self.assertEqual(f({"os": ["windows"]}), ["c"])

    def test_planifier_dependances(self):
        regle, _ = D.valider(D.EXEMPLE)
        ag = [{"agent_id": "vieux", "agent_version": "0.5.90", "plugin_ids": ["guest-usage"]},
              {"agent_id": "neuf", "agent_version": "0.5.96", "plugin_ids": ["pve-remote"]}]
        ctx = {"vieux": ({}, {}, None), "neuf": ({}, {}, None)}
        p = D.planifier(regle, ag, lambda a: ctx[a], "0.5.96")
        etats = {l["agent_id"]: [e["etat"] for e in l["etapes"]] for l in p["agents"]}
        self.assertEqual(etats, {"vieux": ["a_faire", "attente", "attente"], "neuf": ["fait", "a_faire", "attente"]})
        self.assertEqual(sorted((a, e["id"]) for a, e in p["gestes"]), [("neuf", "preflight"), ("vieux", "maj")])
        # mise à jour envoyée : en cours, pas de second geste
        ctx["vieux"] = ({}, {}, {"status": "pending", "params": {"version": "0.5.96"}})
        p = D.planifier(regle, ag, lambda a: ctx[a], "0.5.96")
        self.assertEqual([e["etat"] for e in p["agents"][0]["etapes"]], ["en_cours", "attente", "attente"])
        self.assertNotIn("vieux", [a for a, _ in p["gestes"]])
        # sonde active, relevé en erreur puis réussi
        ctx["neuf"] = ({"pve-preflight": {"enabled": True}}, {"plugin:pve-preflight": {"ok": False, "error": "ssh refusé"}}, None)
        self.assertEqual(D.planifier(regle, ag, lambda a: ctx[a], "0.5.96")["agents"][1]["etapes"][2]["etat"], "echec")
        ctx["neuf"] = ({"pve-preflight": {"enabled": True}}, {"plugin:pve-preflight": {"ok": True, "at": "t"}}, None)
        self.assertTrue(D.planifier(regle, ag, lambda a: ctx[a], "0.5.96")["agents"][1]["termine"])
        # sans paquet servi
        self.assertEqual(D.planifier(regle, ag[:1], lambda a: ({}, {}, None), None)["agents"][0]["etapes"][0]["etat"], "echec")


class Api(unittest.TestCase):
    def test_parcours(self):
        db, c = appmod.DB_PATH, appmod.app.test_client()
        for pid in ("guest-usage", "pve-preflight"):
            store.upsert_plugin(db, {"id": pid, "version": "1", "runner": "python", "entry": "x.py", "interval_seconds": 60, "description": pid}, "print(1)")
        store.create_agent(db, "nd-a", "siege"); store.create_agent(db, "nd-b", "siege")
        store.assign_plugin(db, "nd-a", "guest-usage", enabled=True)
        conn = store._connect(db)
        conn.execute("UPDATE agents SET agent_version='0.5.95' WHERE agent_id IN ('nd-a','nd-b')"); conn.commit(); conn.close()
        regle = dict(D.EXEMPLE, etapes=[dict(D.EXEMPLE["etapes"][0], version_min="0.5.95")] + D.EXEMPLE["etapes"][1:])
        self.assertEqual(c.post("/diffusions", json={"nom": "x"}).status_code, 400)
        r = c.post("/diffusions", json=regle)
        self.assertEqual(r.status_code, 201)
        did = r.json["id"]
        d = c.get("/diffusions").json["diffusions"][0]
        self.assertEqual([l["agent_id"] for l in d["plan"]], ["nd-a"])
        self.assertEqual([e["etat"] for e in d["plan"][0]["etapes"]], ["fait", "a_faire", "attente"])
        sim = c.post("/diffusions/%d/executer" % did, json={"simulation": True}).json
        self.assertEqual(sim["gestes"], [{"agent_id": "nd-a", "etape": "preflight", "type": "activer_sonde", "sonde": "pve-preflight"}])
        self.assertFalse(any(p["id"] == "pve-preflight" for p in store.agent_plugins(db, "nd-a")))
        faits = c.post("/diffusions/%d/executer" % did, json={"actor": "test"}).json["faits"]
        self.assertEqual(faits[0]["resultat"], "sonde pve-preflight activée")
        self.assertTrue(any(p["id"] == "pve-preflight" and p["enabled"] for p in store.agent_plugins(db, "nd-a")))
        store.ingest_measurements(db, "nd-a", [{"task": "plugin:pve-preflight", "at": "2026-10-22T12:00:00Z", "ok": True, "data": {"nodes": []}}])
        self.assertTrue(c.get("/diffusions").json["diffusions"][0]["plan"][0]["termine"])
        self.assertEqual(c.put("/diffusions/99", json=regle).status_code, 404)
        self.assertEqual(c.delete("/diffusions/%d" % did).status_code, 200)
        self.assertEqual(c.get("/diffusions").json["diffusions"], [])


if __name__ == "__main__":
    unittest.main()
