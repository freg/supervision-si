# -*- coding: utf-8 -*-
"""#999 : instances ownCloud -- synthèse (statuts, doublons, comptes locaux, gains, étapes) et routes (valeurs fictives)."""
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
os.environ.setdefault("SI_AGENT_DB_PATH", os.path.join(tempfile.mkdtemp(), "si-agent.db"))
os.environ.setdefault("SI_AGENT_PURGE_THREAD", "0")
os.environ.setdefault("SI_AGENT_CA_FILE", os.path.join(tempfile.mkdtemp(), "ca.crt"))
sys.path.insert(0, HERE)
import owncloud as O  # noqa: E402

NOW = 1_794_000_000
J = 86400
MESURE = {
    "instance": {"version": "10.15.0.2", "systeme": {"nom": "Debian GNU/Linux 11 (bullseye)", "fin": "2026-08-31", "depasse": True},
                 "disque": {"pct": 80, "libre_go": 363}},
    "totaux": {"fichiers": 400.0, "corbeilles": 200.0, "versions": 20.0, "actif_jours": 30, "dormant_jours": 365},
    "comptes": [
        {"id": "u1", "nom": "Alice ALPHA", "derniere_connexion": NOW - 3600, "origine": "ldap", "go_fichiers": 150.0},
        {"id": "u2", "nom": "Bob BRAVO", "derniere_connexion": NOW - 900 * J, "origine": "ldap", "go_fichiers": 80.0},
        {"id": "u3", "nom": "Bob Bravo", "derniere_connexion": NOW - 100 * J, "origine": "ldap", "go_fichiers": 1.0},
        {"id": "admin", "nom": "admin", "derniere_connexion": NOW - 80 * J, "origine": "locale", "go_fichiers": 0.0},
        {"id": "dave", "nom": "dave", "derniere_connexion": None, "origine": "locale", "go_fichiers": 0.0},
    ],
    "activite": [{"jour": "2026-11-05", "actions": 54, "utilisateurs": 6}],
}


class Synthese(unittest.TestCase):
    def test_synthese(self):
        s = O.synthese(MESURE, {"corbeilles": {"etat": "accepte", "note": "90 jours", "par": "carol"}}, NOW)
        st = {c["id"]: c["statut"] for c in s["comptes"]}
        self.assertEqual(st, {"u1": "actif", "u2": "inactif", "u3": "recent", "admin": "recent", "dave": "jamais"})
        self.assertEqual([c["id"] for c in s["comptes"] if c["doublon"]], ["u2", "u3"])   # accents / casse ignorés
        ch = s["chiffres"]
        self.assertEqual((ch["actifs"], ch["inactifs"], ch["go_inactifs"], ch["locaux"]), (1, 1, 80.0, ["dave"]))
        self.assertEqual((ch["go_total"], ch["go_vivantes"]), (620.0, 340.0))
        e = {x["id"]: x for x in s["etapes"]}
        self.assertEqual(e["corbeilles"]["etat"], "accepte"); self.assertEqual(e["corbeilles"]["note"], "90 jours")
        self.assertEqual(e["comptes_inactifs"]["etat"], "a_decider"); self.assertEqual(e["sauvegarde"]["etat"], "a_faire")
        self.assertIn("sans mises à jour", e["systeme"]["detail"])
        self.assertIn("340 Go", e["cible"]["detail"])
        self.assertEqual((O.fr(1296.4), O.fr(381.1), O.fr(80.0), O.fr(12)), ("1 296,4", "381,1", "80", "12"))

    def test_sans_doublon_ni_local(self):
        m = dict(MESURE, comptes=MESURE["comptes"][:2] + [MESURE["comptes"][3]])
        e = {x["id"]: x["etat"] for x in O.synthese(m, {}, NOW)["etapes"]}
        self.assertEqual((e["doublons"], e["comptes_locaux"]), ("fait", "fait"))

    def test_valider(self):
        self.assertIsNone(O.valider_decision({"agent_id": "cloud-1", "etape": "corbeilles", "etat": "fait"}))
        self.assertIn("étape", O.valider_decision({"agent_id": "cloud-1", "etape": "x", "etat": "fait"}))
        self.assertIn("état", O.valider_decision({"agent_id": "cloud-1", "etape": "corbeilles", "etat": "peut-être"}))
        self.assertIn("agent_id", O.valider_decision({"etape": "corbeilles", "etat": "fait"}))


class Routes(unittest.TestCase):
    def test_routes(self):
        import json
        import app as A
        import store
        store.create_agent(A.DB_PATH, "oc-1", "bureau")
        store.ingest_measurements(A.DB_PATH, "oc-1", [{"task": "plugin:owncloud", "at": "2026-11-09T16:00:00Z", "ok": True, "data": MESURE}])
        c = A.app.test_client()
        v = c.get("/owncloud").get_json()["instances"]
        self.assertEqual(len(v), 1); self.assertEqual(v[0]["instance"]["version"], "10.15.0.2"); self.assertEqual(v[0]["chiffres"]["comptes"], 5)
        self.assertEqual(c.put("/owncloud/decisions", json={"agent_id": "oc-1", "etape": "x", "etat": "fait"}).status_code, 400)
        r = c.put("/owncloud/decisions", json={"agent_id": "oc-1", "etape": "comptes_inactifs", "etat": "accepte", "note": "accord direction", "actor": "carol"})
        self.assertEqual(r.status_code, 200)
        e = {x["id"]: x for x in c.get("/owncloud").get_json()["instances"][0]["etapes"]}
        self.assertEqual((e["comptes_inactifs"]["etat"], e["comptes_inactifs"]["par"]), ("accepte", "carol"))
        _ = json


if __name__ == "__main__":
    unittest.main()
