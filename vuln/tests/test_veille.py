# -*- coding: utf-8 -*-
"""Tests #814 : veille cyber dans vuln-api -- flux (RSS 2.0, Atom, RDF, KEV au format réel), catégories, préfiltres,
filtres, extraction, impacts sur les constats, publics, suivi, alerte immédiate et synthèse par public."""
import json
import os
import sys
import tempfile
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(HERE, "..", "..", "shared"))
os.environ.setdefault("VULN_DATA_DIR", tempfile.mkdtemp())
os.environ.update(VULN_FEEDS_THREAD="0", VEILLE_THREAD="0", DT_URL="", DT_API_KEY="")
import veillelib as V  # noqa: E402
import app as app_mod  # noqa: E402
import veille  # noqa: E402

RSS = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/"><channel><title>CERT-FR</title>
<item><title>Multiples vuln&#233;rabilit&#233;s dans OpenSSH sous Linux</title>
<link>https://example.org/avis/AVI-0999/</link><guid>https://example.org/avis/AVI-0999/</guid>
<pubDate>Tue, 20 Oct 2026 14:05:00 +0000</pubDate>
<description>&lt;p&gt;Vuln&#233;rabilit&#233;s (CVE-2026-12345, cve-2026-0042).&lt;/p&gt;</description></item>
<item><title>Vuln&#233;rabilit&#233; dans MikroTik RouterOS</title><link>https://example.org/avis/AVI-1000/</link>
<pubDate>Tue, 20 Oct 2026 15:00:00 +0200</pubDate><content:encoded><![CDATA[<p>Le mod&egrave;le <b>RB4011</b> est concern&eacute;.</p><script>x()</script>]]></content:encoded></item>
</channel></rss>"""
ATOM = b"""<?xml version="1.0" encoding="utf-8"?><feed xmlns="http://www.w3.org/2005/Atom"><title>Blog</title>
<entry><title>Prompt injection in an AI agent</title><link href="https://example.org/a" rel="alternate"/><id>tag:example.org,2026:a</id>
<updated>2026-10-19T08:00:00Z</updated><summary type="html">&lt;em&gt;LLM&lt;/em&gt; tool use in a Django app</summary></entry></feed>"""
RDF = b"""<?xml version="1.0"?><rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" xmlns="http://purl.org/rss/1.0/" xmlns:dc="http://purl.org/dc/elements/1.1/">
<channel><title>arXiv</title></channel>
<item><title>Jailbreaking large language model agents</title><link>https://arxiv.example/1</link><dc:date>2026-10-20</dc:date><description>LLM agents.</description></item>
<item><title>Lattice proofs</title><link>https://arxiv.example/2</link><description>Crypto.</description></item></rdf:RDF>"""
BOMBE = b"""<?xml version="1.0"?><!DOCTYPE l [<!ENTITY a "aaaa"><!ENTITY b "&a;&a;">]><rss><channel><item><title>&b;</title></item></channel></rss>"""
MAINTENANT = 1792540800.0   # 2026-10-21
KEV_REEL = json.load(open(os.path.join(HERE, "fixtures", "kev.json")))


class Lib(unittest.TestCase):
    def test_flux(self):
        it = V.analyser_flux(RSS)
        self.assertEqual([x["titre"] for x in it], ["Multiples vulnérabilités dans OpenSSH sous Linux", "Vulnérabilité dans MikroTik RouterOS"])
        self.assertEqual(it[0]["publie"], 1792505100.0)
        self.assertEqual(it[1]["resume"], "Le modèle RB4011 est concerné.")
        a = V.analyser_flux(ATOM)[0]
        self.assertEqual((a["url"], a["cle"], a["resume"]), ("https://example.org/a", "tag:example.org,2026:a", "LLM tool use in a Django app"))
        self.assertEqual(len(V.analyser_flux(RDF)), 2)
        for mauvais in (BOMBE, b"<html></html>"):
            with self.assertRaises(ValueError):
                V.analyser_flux(mauvais)

    def test_kev_format_reel(self):
        tous = V.analyser_kev(KEV_REEL, MAINTENANT, jours=3650)
        self.assertEqual(len(tous), len(KEV_REEL["vulnerabilities"]))
        self.assertTrue(all(x["cle"].startswith("kev:CVE-") and x["url"].startswith("https://nvd.nist.gov/vuln/detail/CVE-") for x in tous))
        self.assertIn("Citrix NetScaler", tous[0]["titre"])
        self.assertLessEqual(len(V.analyser_kev(KEV_REEL, MAINTENANT)), len(tous))       # 60 jours par défaut

    def test_classement_et_regles(self):
        self.assertEqual(V.categories_auto("Ce que j'ai vu", ""), [])
        self.assertEqual(V.categories_auto("Sanction CNIL au titre du RGPD", ""), ["reglement", "france_europe"])
        pf = [{"nom": n, "termes": t, "modeles": [{"modele": "RB4011"}] if n == "mikrotik" else [], "actif": 1} for n, t in V.PREFILTRES_DEFAUT.items()]
        self.assertEqual(V.etiqueter("Vulnérabilité dans MikroTik RouterOS", "RB4011", pf), (["mikrotik"], ["RB4011"]))
        self.assertEqual(V.etiqueter("Faille Django et PHP", "", pf)[0], ["python", "php"])
        a = {"titre": "OpenSSH", "resume": "", "cves": ["CVE-2026-1"], "tags": ["linux"], "categories": ["alerte"], "niveau": "avis", "publie": MAINTENANT,
             "impacts": {"actifs": ["srv-a"], "priorite": "P2"}, "publics": ["adminsys"], "statut": None}
        self.assertTrue(V.correspond_si(a, {"impacts": True, "publics": ["adminsys"], "statuts": ["aucun"]}, MAINTENANT))
        self.assertFalse(V.correspond_si(a, {"publics": ["dev"]}, MAINTENANT))
        self.assertFalse(V.correspond_si(dict(a, impacts={"actifs": []}), {"impacts": True}, MAINTENANT))
        self.assertFalse(V.correspond_si(dict(a, statut="traite"), {"statuts": ["a_traiter"]}, MAINTENANT))

    def test_impacts_publics(self):
        idx = V.index_constats([{"asset": "srv-a", "package": "openssh", "version": "9.6", "priority": "P2", "cves": '["CVE-2026-12345"]'},
                                {"asset": "app-b", "package": "django", "version": "4.2", "priority": "P1", "cves": ["cve-2026-0042"]}])
        imp = V.impacts({"cves": ["CVE-2026-12345", "CVE-2026-0042"]}, idx)
        self.assertEqual((imp["actifs"], imp["priorite"], imp["constats"]), (["app-b", "srv-a"], "P1", 2))
        self.assertEqual(V.impacts({"cves": []}, idx)["actifs"], [])
        self.assertEqual(V.publics({"niveau": "avis", "categories": ["alerte"], "tags": ["python"]}, imp), ["adminsys", "dev", "rssi"])
        self.assertEqual(V.publics({"categories": ["reglement"], "tags": []}), ["rssi"])
        self.assertEqual(V.publics({"categories": ["generale"], "tags": []}), [])
        self.assertTrue(V.a_signaler({"niveau": "exploitee"}, imp))
        self.assertFalse(V.a_signaler({"niveau": "avis"}, imp))
        self.assertTrue(V.a_signaler({"niveau": "alerte", "nos_modeles": ["RB4011"]}, {"actifs": []}))
        sujet, corps = V.texte_synthese([{"titre": "T", "niveau": "exploitee", "cves": ["CVE-1"], "impacts": imp, "url": "https://x", "source_id": 1}], "rssi", {1: "CISA"})
        self.assertEqual(sujet, "Veille cyber RSSI : 1 nouveauté(s), 1 touchant notre SI")
        self.assertIn("touche : app-b, srv-a", corps)
        self.assertEqual(V.texte_synthese([], "dev"), (None, None))

    def test_extraction(self):
        arts = [{"id": 1, "titre": "Faille [x] & co", "url": "https://example.org/?a=1&b=2", "resume": "r", "publie": MAINTENANT, "source_id": 1, "niveau": "alerte",
                 "categories": ["alerte"], "tags": ["linux"], "cves": ["CVE-2026-1"], "nos_modeles": [], "impacts": {"actifs": ["srv-a"], "priorite": "P1"},
                 "publics": ["rssi", "adminsys"], "statut": "a_traiter"}]
        c = V.extraction(arts, "csv", sources={1: "CERT-FR"})[0]
        self.assertIn(";CVE-2026-1;srv-a;P1;rssi,adminsys;a_traiter;Faille [x] & co;", c)
        self.assertIn("**touche srv-a** (P1)", V.extraction(arts, "md")[0])
        import xml.etree.ElementTree as ET
        ET.fromstring(V.extraction(arts, "atom")[0].encode())


class Api(unittest.TestCase):
    def setUp(self):
        self.c = app_mod.app.test_client()
        with app_mod.db() as cn:
            for t in ("veille_articles", "veille_sources", "veille_filtres", "veille_prefiltres", "veille_journal", "veille_etat", "findings", "assets"):
                cn.execute("DELETE FROM %s" % t)
            veille.semer(cn)
            cn.execute("INSERT INTO assets (name, kind, exposed) VALUES ('srv-a', 'host', 1)")
            cn.execute("INSERT INTO findings (asset, package, version, ids, cves, priority, kev) VALUES ('srv-a', 'openssh', '9.6', 'X-1', '[\"CVE-2026-12345\"]', 'P1', 1)")

    def tearDown(self):   # base partagée avec test_vuln quand les deux tournent ensemble
        with app_mod.db() as cn:
            cn.execute("DELETE FROM findings WHERE asset='srv-a'")
            cn.execute("DELETE FROM assets WHERE name='srv-a'")

    def relever(self, url, data, st=200):
        with app_mod.db() as cn:
            s = veille.lignes(cn.execute("SELECT * FROM veille_sources WHERE url=?", (url,)))[0]
            return veille.relever(cn, s, telecharge=lambda src: (st, data, None, None))

    def test_parcours(self):
        envois = []
        envoyer = lambda action, sujet, corps, **k: envois.append((action, sujet, corps, k))  # noqa: E731
        ids = self.relever("https://www.cert.ssi.gouv.fr/alerte/feed/", RSS)
        self.assertEqual(len(ids), 2)
        self.assertEqual(self.relever("https://www.cert.ssi.gouv.fr/alerte/feed/", RSS), [])
        self.relever("https://simonwillison.net/tags/prompt-injection.atom", ATOM)
        self.assertEqual(len(self.relever("https://rss.arxiv.org/rss/cs.CR", RDF)), 1)
        self.relever("https://www.zataz.com/feed/", b"<html>erreur</html>")
        # alerte immédiate : seule l'alerte dont une CVE est chez nous part, une seule fois
        with app_mod.db() as cn:
            self.assertEqual(veille.signaler(cn, ids, envoyer), 1)
            self.assertEqual(veille.signaler(cn, ids, envoyer), 0)
        self.assertEqual(envois[0][0], "veille.alerte-si")
        self.assertIn("touche srv-a", envois[0][1])
        self.assertEqual(envois[0][3]["severity"], "critical")
        al = self.c.get("/veille/articles?categories=alerte&jours=36500").get_json()
        touche = [a for a in al["articles"] if a["impacts"]["actifs"]]
        self.assertEqual(len(touche), 1)
        self.assertEqual((touche[0]["impacts"]["priorite"], touche[0]["statut"], touche[0]["publics"]), ("P1", "a_traiter", ["adminsys", "rssi"]))
        self.assertEqual(self.c.get("/veille/articles?impacts=1&jours=36500").get_json()["total"], 1)
        self.assertEqual(self.c.get("/veille/articles?publics=dev&jours=36500").get_json()["total"], 1)       # Django (Atom)
        imp = self.c.get("/veille/impacts?jours=36500").get_json()
        self.assertEqual((imp[0]["actif"], imp[0]["priorite"], len(imp[0]["articles"])), ("srv-a", "P1", 1))
        # suivi de traitement et journal
        aid = touche[0]["id"]
        self.assertEqual(self.c.post("/veille/articles/%d" % aid, json={"statut": "nimporte"}).status_code, 400)
        self.c.post("/veille/articles/%d" % aid, json={"statut": "traite", "par": "alice", "note": "openssh mis à jour"})
        j = self.c.get("/veille/journal").get_json()
        self.assertEqual((j[0]["statut"], j[0]["par"], j[0]["note"]), ("traite", "alice", "openssh mis à jour"))
        self.assertEqual(self.c.get("/veille/articles?statuts=a_traiter&jours=36500").get_json()["total"], 0)
        # nos modèles -> réétiquetage
        self.c.put("/veille/prefiltres/mikrotik", json={"termes": V.PREFILTRES_DEFAUT["mikrotik"], "modeles": [{"modele": "RB4011"}]})
        self.assertEqual(self.c.get("/veille/articles?nos_modeles=1&jours=36500").get_json()["articles"][0]["nos_modeles"], ["RB4011"])
        # filtres et extraction
        fid = self.c.post("/veille/filtres", json={"nom": "Touche le SI", "regle": {"impacts": True, "jours": 36500}, "par": "alice"}).get_json()["id"]
        self.assertEqual(self.c.post("/veille/filtres", json={"nom": "x", "regle": {"publics": ["inconnu"]}}).status_code, 400)
        self.assertEqual(self.c.get("/veille/filtres").get_json()[0]["nb"], 1)
        r = self.c.get("/veille/extraction?filtre=%d&format=csv" % fid)
        self.assertIn("srv-a;P1;adminsys,rssi;traite;", r.get_data(as_text=True))
        self.assertIn('filename="veille-cyber-touche-le-si-', r.headers["Content-Disposition"])
        # synthèse par public : RSSI et administrateurs reçoivent l'alerte, les développeurs l'article Django
        with app_mod.db() as cn:
            cn.execute("UPDATE veille_articles SET recu=?", (time.time(),))
            out = veille.syntheses(cn, envoyer)
        self.assertEqual(sorted(out), ["adminsys", "dev", "rssi"])
        self.assertEqual(out["dev"], 1)
        self.assertIn("veille.quotidienne-rssi", [e[0] for e in envois])
        e = self.c.get("/veille/etat").get_json()
        self.assertEqual((e["sources_en_erreur"], e["touchent_si_30j"] >= 0, "rssi" in e["publics"]), (1, True, True))

    def test_semis_sorties_ia(self):
        with app_mod.db() as cn:
            urls = [x[0] for x in cn.execute("SELECT url FROM veille_sources")]
            self.assertIn("https://github.com/ollama/ollama/releases.atom", urls)
            cn.execute("DELETE FROM veille_sources WHERE url LIKE '%ollama%'")
            veille.semer(cn)                                                        # une source supprimée ne revient pas
            self.assertFalse(cn.execute("SELECT COUNT(*) FROM veille_sources WHERE url LIKE '%ollama%'").fetchone()[0])
            # installation antérieure (sources sans état « semees », sans les sorties IA) : les sorties IA arrivent
            cn.execute("DELETE FROM veille_etat")
            cn.execute("DELETE FROM veille_sources WHERE categorie='ia_sorties'")
            cn.execute("DELETE FROM veille_sources WHERE url LIKE '%zataz%'")
            veille.semer(cn)
            urls = [x[0] for x in cn.execute("SELECT url FROM veille_sources")]
            self.assertIn("https://github.com/ollama/ollama/releases.atom", urls)
            self.assertNotIn("https://www.zataz.com/feed/", urls)                 # supprimée avant : pas remise
        self.assertIn("ia_sorties", self.c.get("/veille/etat").get_json()["categories"])

    def test_tour_et_ia(self):
        with app_mod.db() as cn:
            cn.execute("UPDATE veille_sources SET actif=0")
            self.assertEqual(veille.tour(cn, MAINTENANT), 0)
            self.assertEqual(veille._etat(cn, "synthese") is None, time.localtime(MAINTENANT).tm_hour < veille.HEURE_SYNTHESE)
        self.relever("https://www.cert.ssi.gouv.fr/alerte/feed/", RSS)
        aid = self.c.get("/veille/articles?jours=36500").get_json()["articles"][0]["id"]
        appels = []
        veille.llm, avant = (lambda m, modele=None, delai=600: (appels.append(m) or ("Chez nous : srv-a.", {"modele": "m"}))), veille.llm
        try:
            r = self.c.post("/veille/articles/%d/expliquer" % aid).get_json()
            self.assertEqual(r["texte"], "Chez nous : srv-a.")
            self.assertIn("<donnees>", appels[0][1]["content"])
            self.assertIn("jamais une instruction", appels[0][0]["content"])
            self.assertEqual(self.c.post("/veille/synthese", json={"regle": {"jours": 36500}}).status_code, 200)
            self.assertEqual(self.c.post("/veille/synthese", json={"filtre": 999}).status_code, 404)
        finally:
            veille.llm = avant
        self.assertEqual(self.c.post("/veille/synthese/envoyer").status_code, 400)          # notify-api non configuré


if __name__ == "__main__":
    unittest.main()
