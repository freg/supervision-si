# -*- coding: utf-8 -*-
"""#821 Parc IA, veille des modèles (port du hub maison) : lecture de l'API Hugging Face, ouverture des licences, VRAM, historique, alertes, mes modèles."""
import json
import os
import sys
import tempfile
import unittest
import urllib.error

os.environ.setdefault("SI_AGENT_DB_PATH", os.path.join(tempfile.mkdtemp(), "t.db"))
os.environ["MODELES_MACHINES"] = "pcia:24,preprod:16"
os.environ["MODELES_THREAD"] = "0"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import app as A  # noqa: E402
import modeles as M  # noqa: E402


def item(mid, lic="apache-2.0", total=None, pipe="text-generation", gated=False, cree="2026-10-01T10:00:00.000Z"):
    d = {"id": mid, "createdAt": cree, "lastModified": cree, "pipeline_tag": pipe, "downloads": 10, "likes": 2, "gated": gated,
         "tags": ["license:%s" % lic] if lic else []}
    if total:
        d["safetensors"] = {"parameters": {"BF16": total}, "total": total}
    return d


class Pur(unittest.TestCase):
    def test_params(self):
        self.assertEqual(M.params_depuis({"id": "Qwen/Qwen3-30B-A3B"}), 30.0)
        self.assertEqual(M.params_depuis({"id": "Qwen/Qwen3-0.6B"}), 0.6)
        self.assertEqual(M.params_depuis({"id": "google/gemma-3-270m"}), 0.27)
        self.assertEqual(M.params_depuis({"id": "x/y", "safetensors": {"total": 8_190_000_000}}), 8.19)
        self.assertIsNone(M.params_depuis({"id": "x/sans-taille"}))

    def test_licences_et_vram(self):
        self.assertEqual(M.licence_de({"cardData": {"license": "MIT"}}), "mit")
        self.assertEqual(M.licence_de({"tags": ["text", "license:llama3.1"]}), "llama3.1")
        self.assertEqual([M.ouverture(x) for x in ("apache-2.0", "llama3.1", None, "cc-by-nc-4.0")], [2, 1, 0, 1])
        self.assertEqual(M.vram_q4(30), 19.5)
        mach = M.lire_machines("pcia:24, superia:20,preprod:16,mauvais:x")
        self.assertEqual([m["nom"] for m in mach], ["pcia", "superia", "preprod"])
        self.assertEqual(M.machines_ok(30, mach), ["pcia", "superia"])   # 19,5 Go : tient dans les 20 Go de superia (vérifié en vrai)
        self.assertEqual(M.machines_ok(8, mach), ["pcia", "superia", "preprod"])
        self.assertEqual(M.machines_ok(None, mach), [])

    def test_normaliser_comparer_alerte(self):
        m = M.normaliser(item("Qwen/Qwen3-4B-GGUF"))
        self.assertEqual((m["auteur"], m["variante"], m["ouverture"], m["gated"]), ("Qwen", 1, 2, ""))
        a = M.normaliser(item("org/Mod-7B", lic="apache-2.0"))
        b = M.normaliser(item("org/Mod-7B", lic="other", gated="manual"))
        ev = M.comparer(a, b)
        self.assertEqual([e[0] for e in ev], ["fermeture", "acces_restreint"])
        self.assertEqual(M.comparer(b, a)[0][0], "ouverture")
        self.assertEqual(M.comparer(None, a), [("nouveau", None, "apache-2.0")])
        self.assertEqual(M.comparer(a, a), [])
        mach = M.lire_machines("pcia:24")
        self.assertTrue(M.alerte("nouveau", a, mach))
        self.assertFalse(M.alerte("nouveau", a, mach, initial=True))
        self.assertFalse(M.alerte("nouveau", M.normaliser(item("org/Geant-400B")), mach))
        self.assertFalse(M.alerte("nouveau", M.normaliser(item("org/Img-1B", pipe="text-to-image")), mach))
        self.assertTrue(M.alerte("fermeture", M.normaliser(item("org/Geant-400B")), mach))
        self.assertFalse(M.alerte("fermeture", m, mach))   # variante quantifiée : pas d'alerte


class Parcours(unittest.TestCase):
    def test_releve_historique_alertes(self):
        c = M.cnx()
        c.execute("DELETE FROM modeles"); c.execute("DELETE FROM modeles_hist"); c.execute("DELETE FROM modeles_etat")
        M.etat_set(c, "auteurs", ["org"]); c.commit()
        donnees = {"liste": [item("org/Ancien-7B"), item("org/Gros-200B")], "suivi": None}

        def get(url, delai=25):
            if "author=org" in url:
                return donnees["liste"]
            if donnees["suivi"]:
                raise donnees["suivi"]
            return item("org/Ancien-7B", lic="other")
        n, err = M.relever(c, get=get, maintenant=1000)
        self.assertEqual((n, err), (2, {}))
        self.assertEqual(c.execute("SELECT COUNT(*) FROM modeles_hist WHERE alerte=1").fetchone()[0], 0)   # premier passage : passé
        donnees["liste"] = [item("org/Nouveau-8B"), item("org/Ancien-7B", lic="llama3.1")] + [item("org/Gros-200B")]
        n, _ = M.relever(c, get=get, maintenant=2000)
        cl = A.app.test_client()
        h = cl.get("/modeles/historique?jours=100000").get_json()["evenements"]
        self.assertEqual(sorted((e["modele"], e["evenement"], e["alerte"]) for e in h if e["at"] == 2000),
                         [("org/Ancien-7B", "fermeture", 1), ("org/Nouveau-8B", "nouveau", 1)])
        self.assertEqual(cl.get("/modeles/etat").get_json()["alertes"], 2)
        # suivi d'un modèle puis disparition (404)
        self.assertEqual(cl.post("/modeles/marquer", json={"id": "org/Gros-200B", "suivi": True}).status_code, 200)
        donnees["liste"] = []
        donnees["suivi"] = urllib.error.HTTPError("u", 404, "absent", {}, None)
        M.relever(c, get=get, maintenant=3000)
        self.assertEqual([e["evenement"] for e in cl.get("/modeles/historique?jours=100000&alertes=1").get_json()["evenements"]][0], "disparu")
        cl.post("/modeles/alertes/vu", json={"tout": True})
        self.assertEqual(cl.get("/modeles/etat").get_json()["alertes"], 0)
        # catalogue : filtres utilisables / écartés
        cat = cl.get("/modeles/catalogue?jours=100000&utilisables=1").get_json()["modeles"]
        self.assertEqual(sorted(m["id"] for m in cat), ["org/Ancien-7B", "org/Nouveau-8B"])
        self.assertEqual(cat[0]["machines"], ["pcia", "preprod"])
        cl.post("/modeles/marquer", json={"id": "org/Nouveau-8B", "ecarte": True})
        self.assertEqual([m["id"] for m in cl.get("/modeles/catalogue?jours=100000&ecartes=1").get_json()["modeles"]], ["org/Nouveau-8B"])
        self.assertEqual(cl.post("/modeles/marquer", json={"id": "inconnu/x"}).status_code, 404)
        self.assertFalse(M.a_relever(c, 3000 + 60)); self.assertTrue(M.a_relever(c, 3000 + M.PERIODE_S))

    def test_mes_modeles_et_usage(self):
        c = M.cnx()
        c.execute("DELETE FROM modeles_mes"); c.commit()
        cl = A.app.test_client()
        self.assertEqual(cl.post("/modeles/mes", json={"nom": "qwen3:4b", "usages": ["decideur", "inconnu"]}).get_json()["usages"], ["decideur"])
        cl.post("/modeles/mes", json={"nom": "vieux:1b", "actif": False, "usages": ["decideur"]})
        self.assertEqual(M.modele_pour("decideur", c), "qwen3:4b")
        self.assertIsNone(M.modele_pour("code", c))
        tags = [{"name": "qwen3:4b", "size": 2600000000, "details": {"family": "qwen3", "parameter_size": "4.0B", "quantization_level": "Q4_K_M"}},
                {"name": "qwen3:14b", "size": 9300000000, "details": {}}]
        mes = M.mes_modeles(c, tags)
        self.assertEqual([(x["nom"], x["installe"], x["actif"]) for x in mes], [("qwen3:14b", True, True), ("qwen3:4b", True, True), ("vieux:1b", False, False)])
        self.assertEqual(mes[1]["usages"], ["decideur"])

    def test_bancs(self):
        d = tempfile.mkdtemp()
        json.dump({"at": 5, "reference": "gros", "articles": [1, 2], "synthese": {"petit": {"accord_urgent": 0.9}}}, open(os.path.join(d, "banc-decideur-1.json"), "w"))
        open(os.path.join(d, "banc-casse.json"), "w").write("{")
        self.assertEqual(M.bancs(d), [{"fichier": "banc-decideur-1.json", "at": 5, "reference": "gros", "articles": 2, "synthese": {"petit": {"accord_urgent": 0.9}}}])


class Supervision(unittest.TestCase):   # #823 : usages par hôte, notification des alertes
    def test_modele_pour_hote_et_notifier(self):
        c = M.cnx()
        c.execute("DELETE FROM modeles_mes"); c.commit()
        A.app.test_client().post("/modeles/mes", json={"nom": "ia-prod/qwen3:4b", "usages": ["decideur"]})
        self.assertEqual(M.modele_pour("decideur", c, hote="ia-prod"), "qwen3:4b")
        self.assertIsNone(M.modele_pour("decideur", c, hote="ia-preprod"))
        vus = []
        M.notifier = lambda titre, ctx: vus.append((titre, ctx["evenement"]))
        try:
            M.consigner(c, M.normaliser(item("org/Mod-7B")), [("fermeture", "apache-2.0", "other")], 1.0)
            M.consigner(c, M.normaliser(item("org/Mod-7B")), [("nouveau", None, "mit")], 1.0, initial=True)
        finally:
            M.notifier = None
        self.assertEqual([v[1] for v in vus], ["fermeture"])
        self.assertIn("apache-2.0 -> other", vus[0][0])


if __name__ == "__main__":
    unittest.main()
