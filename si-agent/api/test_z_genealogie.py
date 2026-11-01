# -*- coding: utf-8 -*-
"""#854 Généalogie des modèles : base relevée à la main, relevés Hugging Face, fusion, lignée, mode d'emploi."""
import os
import sys
import tempfile
import time
import unittest
import urllib.error

os.environ.setdefault("SI_AGENT_DB_PATH", os.path.join(tempfile.mkdtemp(), "t.db"))
os.environ["MODELES_MACHINES"] = "pcia:24,preprod:16"
os.environ["MODELES_THREAD"] = "0"
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import app as A  # noqa: E402
import genealogie as G  # noqa: E402
P = "/modeles"


def it(mid, tags=(), card=None, cree="2026-10-01T10:00:00.000Z", pipe="text-generation", dl=100):
    return {"id": mid, "tags": list(tags), "cardData": card or {}, "createdAt": cree, "pipeline_tag": pipe, "downloads": dl, "likes": 1}


class Base(unittest.TestCase):
    def test_base_livree_valide(self):
        b = G.charger_base()
        self.assertEqual(G.valider(b["noeuds"]), [])
        self.assertGreater(len(b["noeuds"]), 60)
        ids = {n["id"] for n in b["noeuds"]}
        self.assertIn("transformer", ids)
        sans_parent = [n["id"] for n in b["noeuds"] if not n["parents"]]
        self.assertEqual(sans_parent, ["transformer"])   # tout remonte à l'origine

    def test_valider_detecte(self):
        n = [{"id": "a", "date": "2020-01", "ouverture": "ouvert", "parents": [{"id": "b"}]},
             {"id": "b", "date": "2020", "ouverture": "libre", "parents": [{"id": "a"}]},
             {"id": "b", "date": "2020-02", "ouverture": "ouvert", "parents": [{"id": "z"}]},
             {"id": "c", "date": "2020-02", "ouverture": "ouvert", "parents": [{"id": "d"}]},
             {"id": "d", "date": "2020-02", "ouverture": "ouvert", "parents": [{"id": "c"}]}]
        e = " | ".join(G.valider(n))
        for attendu in ("doublon : b", "date « 2020 »", "ouverture « libre »", "parent inconnu z", "cycle"):
            self.assertIn(attendu, e)


class Pur(unittest.TestCase):
    def test_parents_hf(self):
        self.assertEqual(G.parents_hf(it("x/y", ["base_model:finetune:Qwen/Qwen3-8B", "base_model:quantized:Qwen/Qwen3-8B"])),
                         [("Qwen/Qwen3-8B", "affinage")])
        self.assertEqual(G.parents_hf(it("x/y", ["base_model:merge:a/b", "base_model:merge:c/d", "base_model:adapter:a/b"])),
                         [("a/b", "fusion"), ("c/d", "fusion")])
        self.assertEqual(G.parents_hf(it("x/y", [], {"base_model": ["m/n", "m/N"]})), [("m/n", "affinage")])
        self.assertEqual(G.parents_hf(it("x/y", ["base_model:quantized:a/b"])), [])
        self.assertEqual(G.parents_hf({}), [])

    def test_noeud_hf(self):
        n = G.noeud_hf(it("NousResearch/Hermes-9-8B", ["license:apache-2.0"], cree="2026-09-12T00:00:00Z"), [{"id": "qwen3", "relation": "affinage"}])
        self.assertEqual((n["id"], n["nom"], n["org"], n["date"], n["ouverture"], n["params_b"], n["auto"]),
                         ("hf:NousResearch/Hermes-9-8B", "Hermes-9-8B", "NousResearch", "2026-09", "ouvert", 8.0, True))
        self.assertEqual(G.noeud_hf(it("a/b", ["license:llama3.1"]), [])["ouverture"], "poids")

    def test_fusionner(self):
        base = [{"id": "o", "hf": "org/O", "parents": []}, {"id": "p", "hf": "org/P", "parents": [{"id": "o"}]}]
        rel = [{"id": "hf:x/petit", "hf": "x/petit", "parents": [{"id": "hf:x/fils", "relation": "affinage"}]},
               {"id": "hf:x/fils", "hf": "x/fils", "parents": [{"id": "p", "relation": "affinage"}]},
               {"id": "hf:org/P", "hf": "org/P", "parents": [{"id": "o"}]},            # doublon de la base
               {"id": "hf:x/orphelin", "hf": "x/orphelin", "parents": [{"id": "inconnu"}]}]
        ids = [n["id"] for n in G.fusionner(base, rel)]
        self.assertEqual(ids, ["o", "p", "hf:x/fils", "hf:x/petit"])

    def test_lignee(self):
        b = G.charger_base()["noeuds"]
        lg = G.lignee(b, "r1-distill-qwen")
        asc = {x["id"]: x["distance"] for x in lg["ascendants"]}
        self.assertEqual(asc["deepseek-r1"], 1)
        self.assertIn("transformer", asc)
        self.assertEqual(G.lignee(b, "transformer")["ascendants"], [])
        self.assertGreater(len(G.lignee(b, "transformer")["descendants"]), 60)

    def test_emploi(self):
        mach = [{"nom": "pcia", "vram": 24}, {"nom": "petite", "vram": 8}]
        e = G.emploi({"params_b": 8, "ouverture": "ouvert", "emploi": {"ollama": "qwen3:8b"}}, mach)
        self.assertEqual((e["commande"], e["vram_q4"], e["machines"]), ("ollama run qwen3:8b", 6.3, ["pcia", "petite"]))
        self.assertEqual(G.emploi({"params_b": 8, "ouverture": "ferme"}, mach)["machines"], [])
        self.assertIn("hf.co/a/b", G.emploi({"auto": True, "hf": "a/b", "ouverture": "ouvert"}, mach)["commande"])


class Releve(unittest.TestCase):
    def setUp(self):
        self.c = G.cnx()
        self.c.execute("DELETE FROM genealogie_releves")
        self.c.execute("DELETE FROM modeles_etat WHERE cle='genealogie_releve'")
        self.c.commit()

    def test_relever_et_route(self):
        base = [{"id": "o", "nom": "O", "hf": "org/O", "ouverture": "ouvert", "parents": []},
                {"id": "f", "nom": "F", "ouverture": "ferme", "hf": "", "parents": [{"id": "o"}]}]
        appels = []

        def get(url):
            appels.append(url)
            if "filter=base_model%3Afinetune%3Aorg%2FO" in url:
                return [it("x/fils", ["license:mit"]), it("x/fils-GGUF"), it("org/O")]
            if "/api/models/z/nouveau" in url:
                return it("z/nouveau", ["base_model:finetune:x/fils"])
            if "/api/models/z/seul" in url:
                return it("z/seul", ["base_model:finetune:ailleurs/inconnu"])
            return []
        self.c.execute("DELETE FROM modeles WHERE id LIKE 'z/%'")
        for mid in ("z/nouveau", "z/seul"):
            self.c.execute("INSERT INTO modeles (id, auteur, premier_vu, variante, ecarte) VALUES (?,?,?,0,0)", (mid, "z", time.time()))
        n, err = G.relever(self.c, get=get, base=base)
        self.assertEqual((n, err), (2, {}))
        self.assertEqual(sum("filter=" in u for u in appels), 2)    # finetune + adapter, jamais pour un modèle fermé
        ids = sorted(r["id"] for r in G.releves(self.c))
        self.assertEqual(ids, ["hf:x/fils", "hf:z/nouveau"])
        self.assertFalse(G.a_relever(self.c))
        fus = [x["id"] for x in G.fusionner(base, G.releves(self.c))]
        self.assertEqual(fus, ["o", "f", "hf:x/fils", "hf:z/nouveau"])

    def test_erreur_reseau(self):
        def get(url):
            raise urllib.error.URLError("hors ligne")
        n, err = G.relever(self.c, get=get, base=[{"id": "o", "hf": "org/O", "ouverture": "ouvert", "parents": []}])
        self.assertEqual(n, 0)
        self.assertIn("org/O", err)

    def test_routes(self):
        cl = A.app.test_client()
        r = cl.get(P + "/genealogie")
        self.assertEqual(r.status_code, 200)
        d = r.get_json()
        self.assertEqual(d["erreurs_base"], [])
        self.assertEqual(d["compte"]["base"], len(d["noeuds"]))
        q = next(x for x in d["noeuds"] if x["id"] == "qwen3")
        self.assertTrue(q["emploi"]["commande"].startswith("ollama run "))
        self.assertEqual(cl.post(P + "/genealogie/ecarter", json={"id": "qwen3"}).status_code, 400)
        G.garder(self.c, {"id": "hf:a/b", "hf": "a/b", "parents": [{"id": "qwen3", "relation": "affinage"}]}, time.time())
        self.c.commit()
        self.assertEqual(cl.get(P + "/genealogie").get_json()["compte"]["releves"], 1)
        self.assertTrue(cl.post(P + "/genealogie/ecarter", json={"id": "hf:a/b"}).get_json()["ok"])
        self.assertEqual(cl.get(P + "/genealogie").get_json()["compte"]["releves"], 0)


if __name__ == "__main__":
    unittest.main()
