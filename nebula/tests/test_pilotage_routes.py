# -*- coding: utf-8 -*-
"""#855 : routes /pilotage/* -- netprobe simulé (tâches des sondes, mesures), charge et veille factices."""
import os
import sys
import tempfile
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "api"))
sys.path.insert(0, os.path.join(HERE, "..", "..", "shared"))
TMP = tempfile.mkdtemp()
os.environ.setdefault("NEBULA_DB_PATH", os.path.join(TMP, "nebula.db"))
os.environ["NEBULA_POLL_DISABLED"] = "1"
os.environ["NEBULA_API_KEY"] = "x"
import app as app_mod  # noqa: E402
import pilotage_routes as PR  # noqa: E402
import report_routes as rr  # noqa: E402


def iso(t):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t))


class FauxNetprobe:
    def __init__(self):
        self.taches = {"a1": [{"type": "wifi_link", "every": 30}], "a2": [{"type": "sys", "every": 60}]}
        self.puts = []

    def __call__(self, methode, chemin, corps=None, timeout=10):
        if chemin == "/agents":
            return {"agents": [{"agent_id": a, "label": "Sonde " + a, "role": "probe", "active": True} for a in self.taches]
                    + [{"agent_id": "x", "role": "explorer"}]}
        if chemin == "/agents/latest":
            return {"latest": [{"agent_id": "a1", "task": "ping:192.0.2.1", "at": iso(time.time() - 5), "ok": True, "data": {"rtt_avg_ms": 120}}]}
        a = chemin.split("/")[2].split("?")[0]
        if "/measurements" in chemin:
            return {"measurements": [{"task": "ping:192.0.2.1", "at": iso(time.time()), "ok": True, "data": {"rtt_avg_ms": 20, "loss_pct": 0}}]}
        if methode == "PUT":
            self.puts.append((a, corps["tasks"]))
            self.taches[a] = corps["tasks"]
            return {"agent_id": a}
        return {"agent_id": a, "tasks": self.taches[a]}


class Routes(unittest.TestCase):
    def setUp(self):
        for k in ("pilotage_boucles", "pilotage_plans", "pilotage_runs", "pilotage_reglages", "pilotage_etats", "pilotage_recos", "pilotage_journal"):
            rr.kv_set(k, None)
        self.np = FauxNetprobe()
        PR._np = self.np
        self.notes = []
        PR._hooks.update({"sites": lambda: [{"siteId": "s1", "name": "Site"}],
                          "charge": lambda sid: {"bornes": [{"nom": "B1", "simultanes_max": 30}], "total": {"clients_wifi": 30}},
                          "veille": lambda: {"etat": "ok", "verifs": []},
                          "manage": lambda body: (body.get("user") != "intrus", "droit insuffisant"),
                          "notify": lambda a, s, c: self.notes.append((a, s)) or {"ok": True}})
        self.c = app_mod.app.test_client()

    def post(self, url, corps=None, methode="post"):
        return getattr(self.c, methode)(url, json=dict(corps or {}, user="freg", groups=["admins"]))

    def test_catalogue_scenarios_et_droits(self):
        cat = self.c.get("/pilotage/catalogue").get_json()
        self.assertTrue(cat["outils"] and cat["metriques"] and not cat["plans"])
        self.assertEqual(self.c.post("/pilotage/scenarios/borne-saturee/installer", json={"user": "intrus"}).status_code, 403)
        self.assertEqual(self.post("/pilotage/scenarios/nope/installer").status_code, 404)
        r = self.post("/pilotage/scenarios/cast-degrade/installer").get_json()
        self.assertEqual((len(r["boucles"]), r["plans"]), (2, ["Cast vers les écrans (flux UDP type vidéo)"]))
        cat = self.c.get("/pilotage/catalogue").get_json()
        self.assertTrue(next(s for s in cat["scenarios"] if s["id"] == "cast-degrade")["installe"])
        self.assertEqual(self.c.get("/pilotage/sondes").get_json()["sondes"][1]["agent_id"], "a2")

    def test_boucle_a_chaud_et_declenchement(self):
        b = self.post("/pilotage/boucles", {"boucle": {"nom": "Latence", "condition": {"metrique": "sonde.rtt_ms", "cible": "*", "op": ">", "seuil": 80, "duree_min": 0},
                                                       "actions": [{"type": "notifier"}, {"type": "recommander", "outil": "ncc-limite-appli"}]}})
        self.assertEqual(b.status_code, 201)
        bid = b.get_json()["id"]
        self.assertEqual(self.post("/pilotage/boucles", {"boucle": {"nom": "x"}}).status_code, 400)
        self.post("/pilotage/passer")
        self.assertEqual(self.notes, [])                                     # boucle inactive
        self.assertTrue(self.post("/pilotage/boucles/%s/basculer" % bid, {"actif": True, "mode": "auto"}).get_json()["actif"])
        self.post("/pilotage/passer")
        self.assertEqual([n[0] for n in self.notes], ["nebula.pilotage"])
        t = self.c.get("/pilotage/tableau").get_json()
        self.assertIn(bid, t["recommandations"])
        self.assertEqual(t["dernier"]["valeurs"]["borne.simultanes"], {"B1": 30})
        self.assertEqual(t["dernier"]["valeurs"]["sonde.rtt_ms"], {"Sonde a1": 120})
        self.post("/pilotage/recommandations/%s/acquitter" % bid)
        self.assertNotIn(bid, self.c.get("/pilotage/tableau").get_json()["recommandations"])
        self.assertEqual(self.post("/pilotage/boucles/%s" % bid, {"boucle": {"delai_min": 30}}, "put").get_json()["delai_min"], 30)
        self.assertEqual(self.post("/pilotage/boucles/%s" % bid, methode="delete").status_code, 200)
        self.assertEqual(self.post("/pilotage/boucles/%s" % bid, methode="delete").status_code, 404)

    def test_banc_injection_et_restauration(self):
        self.post("/pilotage/scenarios/cast-degrade/installer")
        r = self.post("/pilotage/plans/cast/lancer")
        self.assertEqual(r.status_code, 409)
        self.assertIn("réglages manquants", r.get_json()["error"])
        self.post("/pilotage/reglages", {"reglages": {"sondes": ["a1", "a2"], "serveur_iperf": "192.0.2.5", "cible_ping": "192.0.2.1",
                                                      "urls": ["https://intra.exemple.fr", "ftp://non"]}}, "put")
        self.assertEqual(rr.kv_get("pilotage_reglages")["urls"], ["https://intra.exemple.fr"])
        run = self.post("/pilotage/plans/cast/lancer").get_json()
        self.assertEqual(run["statut"], "en_cours")
        self.assertEqual(self.post("/pilotage/plans/cast/lancer").status_code, 409)              # un seul banc à la fois
        self.assertEqual(self.post("/pilotage/plans/cast", methode="delete").status_code, 409)
        a1 = self.np.taches["a1"]
        self.assertEqual(a1[0], {"type": "wifi_link", "every": 30})                             # tâches d'origine gardées
        self.assertEqual(sorted(t["type"] for t in a1 if t.get("banc")), ["iperf3", "ping"])
        self.assertTrue(next(t for t in a1 if t["type"] == "iperf3")["params"]["udp"])
        fin = self.post("/pilotage/runs/arreter").get_json()
        self.assertEqual(fin["statut"], "arrete")
        self.assertEqual(self.np.taches, {"a1": [{"type": "wifi_link", "every": 30}], "a2": [{"type": "sys", "every": 60}]})
        self.assertEqual(fin["synthese"]["etapes"][0]["lignes"][0]["rtt_ms"], 20)
        self.assertTrue(any("Banc" in n[1] for n in self.notes))
        self.assertEqual(self.c.get("/pilotage/runs/%s" % run["id"]).get_json()["id"], run["id"])
        self.assertEqual(self.post("/pilotage/runs/arreter").status_code, 404)

    def test_banc_arrete_si_panne(self):
        self.post("/pilotage/scenarios/cast-degrade/installer")
        self.post("/pilotage/reglages", {"reglages": {"sondes": ["a1"], "serveur_iperf": "s", "cible_ping": "c"}}, "put")
        self.post("/pilotage/plans/cast/lancer")
        PR._hooks["veille"] = lambda: {"etat": "panne", "verifs": [{"statut": "ko"}]}
        self.post("/pilotage/passer")
        runs = rr.kv_get("pilotage_runs")
        self.assertEqual((runs[-1]["statut"], runs[-1]["motif"]), ("arrete", "panne du réseau détectée par la veille"))
        self.assertEqual(self.np.taches["a1"], [{"type": "wifi_link", "every": 30}])

    def test_plan_personnalise(self):
        p = {"id": "mon-banc", "nom": "Mon banc", "etapes": [{"nom": "E", "duree_min": 2, "sondes": 1, "taches": [{"type": "ping", "params": {"host": "{cible}"}}]}]}
        self.assertEqual(self.post("/pilotage/plans", {"plan": p}).status_code, 201)
        self.assertEqual(self.post("/pilotage/plans", {"plan": {"id": "x"}}).status_code, 400)
        self.assertEqual(self.post("/pilotage/plans/mon-banc", methode="delete").status_code, 200)

    def test_netprobe_injoignable(self):
        def ko(*a, **k):
            raise OSError("refusé")
        PR._np = ko
        r = self.post("/pilotage/passer").get_json()
        self.assertTrue(any("sondes injoignables" in e for e in r["erreurs"]))
        self.assertIn("erreur", self.c.get("/pilotage/sondes").get_json())


if __name__ == "__main__":
    unittest.main()
