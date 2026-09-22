# -*- coding: utf-8 -*-
"""Tests du PoC assistant (#532) : découpage, BM25, invites, extraction JSON, notation, API avec modèle simulé."""
import json
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
os.environ["ASSISTANT_INDEX_AT_START"] = "0"
os.environ["ASSISTANT_DATA_DIR"] = tempfile.mkdtemp()
os.environ["ASSISTANT_DOCS_DIR"] = tempfile.mkdtemp()
os.environ["ASSISTANT_REPO_DOCS_DIR"] = tempfile.mkdtemp()
import rag  # noqa: E402
import app as app_mod  # noqa: E402


class Pure(unittest.TestCase):
    def test_tokenize_and_chunks(self):
        self.assertEqual(rag.tokenize("Les Sondes réseau des agents"), ["sonde", "reseau", "agent"])
        text = ("Phrase numéro %d. " % i for i in range(200))
        chunks = rag.chunk_text("".join(text), size=300, overlap=50)
        self.assertGreater(len(chunks), 5)
        self.assertTrue(all(len(c) <= 320 for c in chunks))
        self.assertEqual(rag.chunk_text(""), [])
        self.assertEqual(rag.chunk_text("court"), ["court"])

    def test_bm25(self):
        idx = rag.BM25().build([
            {"id": "a", "source": "documents", "title": "Agents hôtes", "text": "la sonde path-probe teste le bail DHCP, le DNS et une page HTTP"},
            {"id": "b", "source": "tickets", "title": "Ticket 1", "text": "imprimante en panne au deuxième étage"},
            {"id": "c", "source": "documents", "title": "Coffre", "text": "le coffre credentials-api ne renvoie jamais le mot de passe au navigateur"},
        ])
        h = idx.search("que teste la sonde path-probe ?")
        self.assertEqual(h[0]["id"], "a")
        self.assertEqual([x["id"] for x in idx.search("mot de passe navigateur", source="documents")], ["c"])
        self.assertEqual(idx.search(""), [])

    def test_weight_title_and_per_doc_cap(self):
        # #535 : poids réduit d'un journal, titre compté triple, 2 morceaux max par document.
        idx = rag.BM25().build([
            {"id": "j#0", "doc": "j", "title": "CHANGELOG.md", "text": "si-agent : la commande update de l'agent hôte", "weight": 0.4},
            {"id": "j#1", "doc": "j", "title": "CHANGELOG.md", "text": "si-agent : update de l'agent hôte corrigé", "weight": 0.4},
            {"id": "j#2", "doc": "j", "title": "CHANGELOG.md", "text": "si-agent : agent hôte, update encore", "weight": 0.4},
            {"id": "r#0", "doc": "r", "title": "si-agent.md", "text": "mise à jour : la commande update connaît la version minimale 0.5.3"},
        ])
        h = idx.search("comment un agent hôte se met-il à jour, commande update si-agent ?", k=3, max_per_doc=2)
        self.assertEqual(h[0]["id"], "r#0")
        self.assertEqual(sum(1 for x in h if x["doc"] == "j"), 2)
        self.assertEqual(len(idx.search("agent update", k=5)), 4)  # plafond désactivé par défaut (#536)

    def test_tokenize_stop_clitics_compounds(self):
        # #536 : interrogatifs et verbes creux ignorés, clitiques ôtés, composés indexés avec leurs parties.
        self.assertEqual(rag.tokenize("À quoi sert la sonde et que teste-t-elle ? Comment se met-il à jour ?"),
                         ["sonde", "teste", "jour"])
        self.assertEqual(rag.tokenize("auto-mise à jour path-probe"), ["auto-mise", "auto", "mise", "jour", "path-probe", "path", "probe"])

    def test_chunk_markdown_headings(self):
        md = "# Module\n\nintro\n\n## Mise à jour\n\n### Version\n\nagent 0.5.3\n\n## Sondes\n\npath-probe"
        ch = rag.chunk_markdown(md)
        self.assertEqual(ch[0], "§ Module\nintro")
        self.assertEqual(ch[1], "§ Module › Mise à jour › Version\nagent 0.5.3")
        self.assertEqual(ch[2], "§ Module › Sondes\npath-probe")
        self.assertEqual(rag.chunk_markdown("sans titre"), ["sans titre"])
        self.assertEqual(rag.chunk_markdown(""), [])

    def test_prompts_and_json(self):
        m = rag.build_rag_messages("q ?", [{"source": "documents", "title": "T", "text": "x" * 2000, "id": "1"}], max_chars=1000)
        self.assertEqual(len(m), 2); self.assertLess(len(m[1]["content"]), 1200)
        self.assertIn("Question : q ?", m[1]["content"])
        self.assertEqual(rag.extract_json('Voici : ```json\n{"type": "facture", "n": {"a": 1}}\n``` merci')["type"], "facture")
        self.assertEqual(rag.extract_json("<think>blabla {pas du json}</think>{\"a\": 2}")["a"], 2)
        self.assertIsNone(rag.extract_json("rien"))
        self.assertIn("Types possibles : facture, devis", rag.build_classify_messages("x", ["facture", "devis"], [])[1]["content"])

    def test_score(self):
        c = {"expect": {"keywords": ["DNS", "HTTP"], "forbidden": ["je ne sais pas"], "source": "doc:README"}}
        s = rag.score_case(c, "La sonde teste le dns et une page http.", sources=[{"id": "doc:README.md#3"}])
        self.assertEqual((s["keywords"], s["forbidden_ok"], s["source_found"], s["score"]), (1.0, 1.0, 1.0, 1.0))
        c = {"expect": {"json": {"type": "facture", "site": ["villexemple", "parc"], "titre": None}}}
        s = rag.score_case(c, "", parsed={"type": "Facture", "site": "Parc"})
        self.assertEqual((s["json_valid"], s["json_fields"]), (1.0, 0.67))
        self.assertEqual(rag.score_case(c, "", parsed=None)["json_valid"], 0.0)


class Llm(unittest.TestCase):
    """#534 : API native Ollama sans réflexion, réponses des deux formes."""

    def test_native_url(self):
        self.assertEqual(app_mod.native_chat_url("http://ia:11434/v1"), "http://ia:11434/api/chat")
        self.assertIsNone(app_mod.native_chat_url("http://vllm:8000/openai"))

    def test_parse_both_shapes(self):
        t, u, tok = app_mod.parse_chat_response({"message": {"content": "ok"}, "prompt_eval_count": 10, "eval_count": 20, "eval_duration": 2_000_000_000})
        self.assertEqual((t, u["completion_tokens"], tok), ("ok", 20, 10.0))
        t, u, tok = app_mod.parse_chat_response({"choices": [{"message": {"content": "hi"}}], "usage": {"completion_tokens": 5}})
        self.assertEqual((t, u["completion_tokens"], tok), ("hi", 5, None))

    def test_think_false_uses_native(self):
        seen = {}

        def fake_post(url, json=None, timeout=None):
            seen.update(url=url, body=json)
            return type("R", (), {"status_code": 200, "text": "", "json": lambda self=None: {"message": {"content": "{\"a\":1}"}, "eval_count": 3, "eval_duration": 1_000_000_000}})()
        old = app_mod.requests.post
        app_mod.requests.post = fake_post
        try:
            out = app_mod.llm_chat([{"role": "user", "content": "x"}], json_mode=True)
        finally:
            app_mod.requests.post = old
        self.assertTrue(seen["url"].endswith("/api/chat"))
        self.assertFalse(seen["body"]["think"]); self.assertEqual(seen["body"]["format"], "json")
        self.assertEqual((out["text"], out["tok_s"], out["think"]), ('{"a":1}', 3.0, False))


class Api(unittest.TestCase):
    def setUp(self):
        self.c = app_mod.app.test_client()
        open(os.path.join(app_mod.DOCS_DIR, "README.md"), "w", encoding="utf-8").write("# Projet\nLe numéro de livraison est dans shared/DELIVERY_NUMBER ; commits sur la branche dev.\n")
        os.makedirs(app_mod.REPO_DOCS_DIR, exist_ok=True)
        open(os.path.join(app_mod.REPO_DOCS_DIR, "si-agent.md"), "w", encoding="utf-8").write("# si-agent\nLa sonde path-probe teste le bail DHCP, le DNS et le chemin HTTP.\n")
        app_mod.build_index()
        self.calls = []

        def fake_post(url, json=None, timeout=None):
            self.calls.append(json)
            content = "Le numéro est dans shared/DELIVERY_NUMBER, sur la branche dev [1]." if "Extraits" in json["messages"][-1]["content"] else '{"type": "facture", "site": "Villexemple", "categorie": "reseau", "urgence": "haute"}'
            return type("R", (), {"status_code": 200, "text": "", "json": lambda self=None: {"choices": [{"message": {"content": content}}], "usage": {"completion_tokens": 20}, "model": "fake"}})()
        app_mod.requests.post = fake_post

    def test_status_index_search(self):
        app_mod.requests.get = lambda url, **k: (_ for _ in ()).throw(app_mod.requests.RequestException("x"))
        st = self.c.get("/assistant/status").get_json()
        self.assertFalse(st["llm_reachable"]); self.assertEqual(st["index"]["docs"], 2)
        self.assertEqual(st["index"]["sources"], {"documents": 1, "repo": 1}); self.assertFalse(st["think"])
        h = self.c.get("/assistant/search?q=numéro de livraison").get_json()["hits"]
        self.assertEqual(h[0]["source"], "documents")
        self.assertEqual(self.c.get("/assistant/search?q=sonde path-probe DNS").get_json()["hits"][0]["source"], "repo")

    def test_ask_classify_summarize(self):
        r = self.c.post("/assistant/ask", json={"question": "où est le numéro de livraison ?"}).get_json()
        self.assertIn("DELIVERY_NUMBER", r["text"]); self.assertEqual(r["sources"][0]["source"], "documents"); self.assertIsNotNone(r["tok_s"])
        r = self.c.post("/assistant/classify", json={"text": "FACTURE n° 1", "types": ["facture"], "sites": ["Villexemple"]}).get_json()
        self.assertEqual(r["parsed"]["type"], "facture")
        self.assertEqual(self.calls[-1].get("format") or self.calls[-1].get("response_format", {}).get("type"), "json")
        r = self.c.post("/assistant/summarize", json={"text": "plus d'Internet"}).get_json()
        self.assertEqual(r["parsed"]["urgence"], "haute")
        self.assertEqual(self.c.post("/assistant/ask", json={}).status_code, 400)

    def test_eval(self):
        cases = self.c.get("/assistant/eval/cases").get_json()["cases"]
        self.assertEqual(len(cases), 20)
        rep = app_mod.run_eval([c for c in cases if c["id"] in ("c01", "s04", "a01")])
        self.assertEqual(rep["cases"], 3)
        self.assertEqual(rep["by_kind"]["classify"]["score"], 1.0)
        self.assertEqual(rep["by_kind"]["summarize"]["score"], 1.0)
        self.assertGreaterEqual(rep["by_kind"]["ask"]["score"], 0.5)
        self.assertTrue(self.c.get("/assistant/eval/last").get_json()["history"])
        j = self.c.get("/assistant/journal").get_json()["journal"]
        ev = [e for e in j if e["kind"] == "eval"]
        self.assertEqual(len(ev), 3)  # #540 : une ligne par cas, produit + attendu + note
        c01 = next(e for e in ev if e["case"] == "c01")
        self.assertEqual(c01["usage"], "classify")
        self.assertIsInstance(c01["result"], dict)
        self.assertEqual(c01["expected"], next(c for c in cases if c["id"] == "c01")["expect"])
        self.assertEqual(c01["score"], 1.0)
        self.assertIn("json_fields", c01["detail"])
        self.assertFalse([e for e in j if e["kind"] in ("ask", "classify", "summarize") and e.get("case")])


if __name__ == "__main__":
    unittest.main()
