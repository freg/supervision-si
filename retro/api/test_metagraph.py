# -*- coding: utf-8 -*-
"""Tests de metagraph.py (livraison #448, phase 4) : entités et attributs
de deux gestions, relations intra-application (code, journal SQL, noms de
colonnes), équivalences inter-applications (spec unique, noms), références
inter-gestions, proposition de fusion."""
import unittest

import merge
import metagraph
from test_merge import _spec_gestion, _spec_crm

COLS_GESTION = {
    "clients": [{"name": "id", "type": "int", "primary_key": True}, {"name": "nom", "type": "varchar(80)"}, {"name": "email", "type": "varchar(120)"},
                {"name": "ville_id", "type": "int"}, {"name": "remise", "type": "decimal(5,2)"}],
    "villes": [{"name": "id", "type": "int", "primary_key": True}, {"name": "nom", "type": "varchar(80)"}],
    "produits": [{"name": "id", "type": "int", "primary_key": True}, {"name": "ref", "type": "varchar(20)"}, {"name": "prix", "type": "decimal(10,2)"}],
}
COLS_CRM = {
    "customers": [{"name": "customer_id", "type": "int", "primary_key": True}, {"name": "name", "type": "varchar(80)"}, {"name": "mail", "type": "varchar(120)"},
                  {"name": "city", "type": "varchar(80)"}, {"name": "tel", "type": "varchar(20)"}, {"name": "produit_id", "type": "int"}],
    "campaigns": [{"name": "id", "type": "int", "primary_key": True}, {"name": "name", "type": "varchar(80)"}, {"name": "sent_at", "type": "date"}, {"name": "customer_id", "type": "int"}],
}
SCAN_GESTION = {"join_candidates": [{"from_table": "villes", "from_column": "id", "to_table": "clients", "to_column": "ville_id", "source_file": "app/controllers/client.php", "source_line": 3}],
                "file_tables": {"app/controllers/client.php": ["clients"]}}
QUERIES_CRM = [{"sql": "SELECT * FROM campaigns c JOIN customers u ON u.customer_id = c.customer_id WHERE c.id = 1"}]


def _specs():
    g, c = _spec_gestion(), _spec_crm()
    g["tables"] = {t: [x["name"] for x in cols] for t, cols in COLS_GESTION.items()}
    c["tables"] = {t: [x["name"] for x in cols] for t, cols in COLS_CRM.items()}
    return {"gestion": g, "crm": c}


class TestGraph(unittest.TestCase):
    def setUp(self):
        self.specs = _specs()
        self.uni = merge.unified_spec(self.specs)
        self.g = metagraph.build_metagraph(self.specs, scans={"gestion": SCAN_GESTION}, queries_by_app={"crm": QUERIES_CRM}, unified=self.uni,
                                           columns_by_app={"gestion": COLS_GESTION, "crm": COLS_CRM})

    def edges(self, kind):
        return [(e["from"], e["to"], e["sources"], e["columns"]) for e in self.g["edges"] if e["kind"] == kind]

    def test_entites_et_attributs(self):
        ids = [n["id"] for n in self.g["nodes"]]
        self.assertEqual(ids, ["crm:campaigns", "crm:customers", "gestion:clients", "gestion:produits", "gestion:villes"])
        cl = next(n for n in self.g["nodes"] if n["id"] == "gestion:clients")
        self.assertEqual([c["name"] for c in cl["columns"]], ["id", "nom", "email", "ville_id", "remise"])
        self.assertTrue(cl["columns"][0]["pk"])
        self.assertEqual(cl["columns"][3]["term"], "ville")
        self.assertEqual(sorted(cl["columns"][1]["screens"]), ["client-n", "clients"])
        self.assertEqual([s["id"] for s in cl["screens"]], ["clients", "client-n", "client-n-save"])
        self.assertTrue(cl["in_code"])
        self.assertEqual(self.g["counts"]["by_app"], {"crm": 2, "gestion": 3})

    def test_relations_intra(self):
        fk = self.edges("fk")
        # code + nom de colonne sur la même relation
        self.assertIn(("gestion:clients", "gestion:villes", ["code", "nom de colonne"], [["ville_id", "id"]]), fk)
        # journal SQL (campaigns.customer_id → customers) + nom de colonne
        self.assertIn(("crm:campaigns", "crm:customers", ["journal SQL", "nom de colonne"], [["customer_id", "customer_id"]]), fk)
        self.assertEqual(self.g["counts"]["fk"], 2)

    def test_equivalences(self):
        eq = {(a, b): (s, c) for a, b, s, c in self.edges("equiv")}
        self.assertIn(("crm:customers", "gestion:clients"), eq)
        sources, cols = eq[("crm:customers", "gestion:clients")]
        self.assertIn("écran « Clients »", sources)
        self.assertIn("écran « Fiche client »", sources)
        self.assertIn("même nom de table", sources)
        self.assertIn(["name", "nom"], cols)
        self.assertIn(["mail", "email"], cols)
        self.assertIn(["city", "ville_id"], cols)
        self.assertIn(["customer_id", "id"], cols)
        self.assertEqual(self.g["counts"]["equiv"], 1)

    def test_reference_inter_gestion(self):
        xr = self.edges("xref")
        # crm.customers.produit_id désigne produits, table absente du CRM mais présente dans gestion
        self.assertEqual(len(xr), 1)
        self.assertEqual(xr[0][:2], ("crm:customers", "gestion:produits"))
        self.assertEqual(xr[0][3], [["produit_id", "id"]])

    def test_sans_colonnes_typees(self):
        g = metagraph.build_metagraph(self.specs, unified=self.uni)
        cl = next(n for n in g["nodes"] if n["id"] == "gestion:clients")
        self.assertEqual([c["name"] for c in cl["columns"]], ["id", "nom", "email", "ville_id", "remise"])
        self.assertIsNone(cl["columns"][0]["type"])
        # la clé primaire vient alors des écrans ; relations devinées par les noms seulement
        self.assertTrue(cl["columns"][0]["pk"])
        self.assertEqual(g["counts"]["fk"], 2)  # clients.ville_id → villes, campaigns.customer_id → customers

    def test_devine_table_referencee(self):
        by = {"ville": "villes", "client": "clients"}
        self.assertEqual(metagraph._guess_ref_table("ville_id", by), "villes")
        self.assertEqual(metagraph._guess_ref_table("id_client", by), "clients")
        self.assertEqual(metagraph._guess_ref_table("customer_id", by), "clients")
        self.assertIsNone(metagraph._guess_ref_table("id", by))
        self.assertIsNone(metagraph._guess_ref_table("uuid", by))


class TestFusion(unittest.TestCase):
    def setUp(self):
        specs = _specs()
        uni = merge.unified_spec(specs)
        self.g = metagraph.build_metagraph(specs, scans={"gestion": SCAN_GESTION}, queries_by_app={"crm": QUERIES_CRM}, unified=uni,
                                           columns_by_app={"gestion": COLS_GESTION, "crm": COLS_CRM})
        self.p = metagraph.fusion_proposal(self.g)

    def test_entites_cibles(self):
        names = [e["name"] for e in self.p["entities"]]
        self.assertEqual(names[0], "client")
        self.assertEqual(self.p["counts"], {"entities": 4, "merged": 1, "kept": 3, "relations": 3, "conflicts": 1, "orphans": 3})
        client = self.p["entities"][0]
        self.assertEqual([m["id"] for m in client["members"]], ["crm:customers", "gestion:clients"])
        self.assertTrue(client["shared"])
        attrs = {a["name"]: a for a in client["attributes"]}
        self.assertEqual(attrs["nom"]["columns"], {"crm": {"table": "customers", "column": "name", "type": "varchar(80)", "pk": False},
                                                   "gestion": {"table": "clients", "column": "nom", "type": "varchar(80)", "pk": False}})
        self.assertTrue(attrs["nom"]["shared"])
        self.assertTrue(attrs["email"]["shared"])
        # ville : texte dans le CRM, clé vers villes dans gestion → conflit de type à arbitrer
        self.assertEqual(attrs["ville"]["type_conflict"], ["int", "text"])
        self.assertTrue(attrs["tel"]["orphan"])
        self.assertTrue(attrs["remise"]["orphan"])
        # clés primaires appariées en un seul attribut, en tête
        self.assertTrue(client["attributes"][0]["pk"])
        self.assertEqual(client["attributes"][0]["name"], "id")
        self.assertEqual(sorted(client["attributes"][0]["columns"]), ["crm", "gestion"])
        self.assertIn("1 conflit(s) de type à arbitrer", client["todo"])

    def test_relations_reportees(self):
        rels = {(r["from"], r["to"], r["kind"]) for r in self.p["relations"]}
        self.assertEqual(rels, {("client", "ville", "fk"), ("campaign", "client", "fk"), ("client", "produit", "xref")})

    def test_entite_propre(self):
        prod = next(e for e in self.p["entities"] if e["name"] == "produit")
        self.assertEqual(prod["apps"], ["gestion"])
        self.assertEqual(prod["todo"], ["propre à gestion : reprise telle quelle"])
        self.assertFalse(any(a["orphan"] for a in prod["attributes"]))

    def test_familles_de_types(self):
        self.assertEqual(metagraph._norm_type("INT(11)"), "int")
        self.assertEqual(metagraph._norm_type("tinyint(1)"), "bool")
        self.assertEqual(metagraph._norm_type("decimal(5,2)"), "decimal")
        self.assertEqual(metagraph._norm_type("varchar(80)"), "text")
        self.assertEqual(metagraph._norm_type("datetime"), "date")
        self.assertEqual(metagraph._norm_type("blob"), "autre")
        self.assertIsNone(metagraph._norm_type(None))


if __name__ == "__main__":
    unittest.main()
