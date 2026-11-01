# -*- coding: utf-8 -*-
"""Veille cyber : rejets fins (#820) -- article, source, sujet (CVE), thème, mots-clés ; archive, repêchage, diffusion."""
import os
import sys
import tempfile
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
os.environ.setdefault("VULN_DATA_DIR", tempfile.mkdtemp())
os.environ.update(VULN_FEEDS_THREAD="0", VEILLE_THREAD="0", DT_URL="", DT_API_KEY="")
import veillelib as V  # noqa: E402
import app as app_mod  # noqa: E402
import veille  # noqa: E402


class Pur(unittest.TestCase):
    def test_valider_et_rejet_de(self):
        self.assertEqual(V.valider_rejet({"type": "sujet", "valeur": "cve-2026-1234,CVE-2025-99999"})[0]["valeur"], "CVE-2025-99999,CVE-2026-1234")
        self.assertIsNotNone(V.valider_rejet({"type": "motcle", "valeur": "-windows"})[1])
        self.assertIsNotNone(V.valider_rejet({"type": "source", "valeur": "9"}, [1])[1])
        a = {"id": 3, "source_id": 7, "titre": "Faille OpenSSH sur Windows", "cves": ["CVE-2026-1"], "tags": ["linux"], "categories": ["alerte"]}
        R = lambda t, v: {"id": 1, "type": t, "valeur": v}
        for g in (R("article", "3"), R("source", "7"), R("sujet", "CVE-2026-1"), R("theme", "linux"), R("motcle", "openssh windows")):
            self.assertTrue(V.rejet_de(a, [g]), g)
        self.assertIsNone(V.rejet_de(a, [R("motcle", "openssh -windows")]))
        self.assertIsNone(V.rejet_de(dict(a, repeche=1), [R("source", "7")]))


class Parcours(unittest.TestCase):
    def setUp(self):
        self.c = app_mod.app.test_client()
        with veille.cnx() as cn:
            cn.execute("DELETE FROM veille_rejets")
            cn.execute("INSERT OR IGNORE INTO veille_sources (id, nom, url, categorie) VALUES (701, 'Rej A', 'https://rej.test/a', 'generale')")
            cn.execute("INSERT OR IGNORE INTO veille_sources (id, nom, url, categorie) VALUES (702, 'Rej B', 'https://rej.test/b', 'generale')")
            t = time.time() - 60
            for i, (src, titre) in enumerate([(701, "Bruit marketing"), (701, "Autre bruit"), (702, "Faille php critique"), (702, "Nouveau modèle ouvert")]):
                cn.execute("INSERT OR REPLACE INTO veille_articles (id, cle, source_id, titre, publie, recu, categories, tags, repeche) VALUES (?,?,?,?,?,?,?,?,0)",
                           (8000 + i, "rej-%d" % i, src, titre, t, t, '["generale"]', '["php"]' if "php" in titre else "[]"))
            cn.commit()

    def ids(self, q=""):
        return sorted(a["id"] for a in self.c.get("/veille/articles?jours=1&categories=generale" + q).get_json()["articles"] if 8000 <= a["id"] < 8100)

    def test_parcours(self):
        self.assertEqual(self.ids(), [8000, 8001, 8002, 8003])
        self.assertEqual(self.c.post("/veille/rejets", json={"type": "source", "valeur": "701", "motif": "bruit", "par": "rssi"}).status_code, 201)
        self.assertEqual(self.c.post("/veille/rejets", json={"type": "source", "valeur": "701"}).status_code, 409)
        self.assertEqual(self.c.post("/veille/rejets", json={"type": "article", "valeur": "999999"}).status_code, 404)
        self.assertEqual(self.c.post("/veille/rejets", json={"type": "motcle", "valeur": "nouveau modèle"}).status_code, 201)
        self.assertEqual(self.ids(), [8002])
        self.assertEqual(self.ids("&rejetes=seuls"), [8000, 8001, 8003])
        r = {a["id"]: a for a in self.c.get("/veille/articles?jours=1&rejetes=seuls").get_json()["articles"]}
        self.assertEqual((r[8000]["rejet"]["type"], r[8000]["rejet"]["par"]), ("source", "rssi"))
        regles = self.c.get("/veille/rejets").get_json()
        self.assertEqual(sorted((g["type"], g["articles"]) for g in regles["regles"]), [("motcle", 1), ("source", 2)])
        self.c.post("/veille/articles/8001", json={"repeche": True, "par": "admin"})
        self.assertEqual(self.ids(), [8001, 8002])
        j = self.c.get("/veille/journal").get_json()
        self.assertTrue(any(x.get("statut") == "repeche" for x in (j.get("journal") if isinstance(j, dict) else j)))
        rid = [g["id"] for g in regles["regles"] if g["type"] == "source"][0]
        self.assertEqual(self.c.delete("/veille/rejets/%d" % rid).status_code, 200)
        self.assertEqual(self.ids(), [8000, 8001, 8002])

    def test_synthese_sans_rejetes_et_alerte_si_maintenue(self):
        self.c.post("/veille/rejets", json={"type": "source", "valeur": "701"})
        with veille.cnx() as cn:
            arts = veille.marquer_rejets(veille.enrichir(cn, veille.lignes(cn.execute("SELECT * FROM veille_articles WHERE id >= 8000 AND id < 8100"))), veille.regles_rejet(cn))
        self.assertEqual(sorted(a["id"] for a in arts if a.get("rejet")), [8000, 8001])


if __name__ == "__main__":
    unittest.main()
