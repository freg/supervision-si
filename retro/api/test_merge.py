# -*- coding: utf-8 -*-
"""Tests de merge.py (livraison #445) : deux applications de gestion de
clients aux tables et champs nommés différemment → rapprochement des
écrans par fonction, spec unique, projection par application."""
import unittest

import merge


def _spec_gestion():
    return {"version": 1, "app": "gestion", "dba_connection_id": 1, "dba_database": "gestion", "screens": [
        {"id": "clients", "screen": "/clients", "title": "Clients", "kind": "list", "table": "clients", "pk": "id",
         "columns": [{"label": "Nom", "column": "nom"}, {"label": "Ville", "column": "ville"}, {"label": "Email", "column": "email"}], "fields": []},
        {"id": "client-n", "screen": "/client/{n}", "title": "Fiche client", "kind": "form", "table": "clients", "pk": "id",
         "columns": [], "fields": [{"name": "nom", "label": "Nom", "type": "text", "required": True, "column": "nom", "confidence": 1.0},
                                   {"name": "email", "label": "Email", "type": "text", "column": "email", "confidence": 1.0},
                                   {"name": "ville_id", "label": "Ville", "type": "select", "column": "ville_id", "confidence": 1.0},
                                   {"name": "remise", "label": "Remise", "type": "text", "column": "remise", "confidence": 1.0}]},
        {"id": "client-n-save", "screen": "/client/{n}/save", "title": "save", "kind": "action", "table": "clients", "fields": [], "columns": []},
        {"id": "produits", "screen": "/produits", "title": "Produits", "kind": "list", "table": "produits", "pk": "id",
         "columns": [{"label": "Référence", "column": "ref"}, {"label": "Prix", "column": "prix"}], "fields": []},
    ]}


def _spec_crm():
    return {"version": 1, "app": "crm", "dba_connection_id": 2, "dba_database": "crm", "screens": [
        {"id": "customers", "screen": "/customers", "title": "Customers", "kind": "list", "table": "customers", "pk": "customer_id",
         "columns": [{"label": "Nom", "column": "name"}, {"label": "Ville", "column": "city"}, {"label": "Téléphone", "column": "tel"}], "fields": []},
        {"id": "customer-n", "screen": "/customer/{n}", "title": "Fiche client", "kind": "form", "table": "customers", "pk": "customer_id",
         "columns": [], "fields": [{"name": "txtNom", "label": "Nom", "type": "text", "required": True, "column": "name", "confidence": 0.9},
                                   {"name": "txtEmail", "label": "Email", "type": "text", "column": "mail", "confidence": 0.7},
                                   {"name": "tel", "label": "Téléphone", "type": "text", "column": "tel", "confidence": 1.0}]},
        {"id": "campagnes", "screen": "/campagnes", "title": "Campagnes", "kind": "list", "table": "campaigns", "pk": "id",
         "columns": [{"label": "Nom", "column": "name"}, {"label": "Date", "column": "sent_at"}], "fields": []},
    ]}


class TestSimilarity(unittest.TestCase):
    def test_formulaires_equivalents(self):
        a = _spec_gestion()["screens"][1]
        b = _spec_crm()["screens"][1]
        score, why = merge.screen_similarity(a, b)
        self.assertGreaterEqual(score, merge.MATCH_THRESHOLD)
        self.assertTrue(any("nom" in w and "email" in w for w in why), why)
        self.assertIn("titres/chemins voisins", why)

    def test_genres_differents(self):
        score, why = merge.screen_similarity(_spec_gestion()["screens"][0], _spec_crm()["screens"][1])
        self.assertEqual(score, 0.0)
        self.assertEqual(why, ["genres différents"])

    def test_prefixes_de_formulaire_ignores(self):
        # txtNom / nom sont le même champ après normalisation
        self.assertEqual(merge._screen_terms(_spec_crm()["screens"][1]), {"nom", "email", "tel"})
        # synonymes / pluriels : customers ≡ client, ville_id ≡ ville
        self.assertEqual(merge._term("customers"), "client")
        self.assertEqual(merge._term("ville_id"), "ville")
        self.assertEqual(merge._term("txtPhone"), "tel")


class TestCompareApps(unittest.TestCase):
    def setUp(self):
        self.specs = {"gestion": _spec_gestion(), "crm": _spec_crm()}
        self.cmp = merge.compare_apps(self.specs)

    def test_groupes(self):
        self.assertEqual(self.cmp["apps"], ["crm", "gestion"])
        fns = {g["function"]: g for g in self.cmp["groups"]}
        self.assertIn("Fiche client", fns)
        fiche = fns["Fiche client"]
        self.assertEqual(sorted(fiche["apps"]), ["crm", "gestion"])
        self.assertEqual(fiche["kind"], "form")
        self.assertEqual(fiche["common_fields"], ["email", "nom"])
        self.assertEqual(fiche["specific_fields"]["gestion"], ["remise", "ville"])
        self.assertEqual(fiche["specific_fields"]["crm"], ["tel"])
        # listes de clients rapprochées (Nom, Ville communs)
        lists = [g for g in self.cmp["groups"] if g["kind"] == "list"]
        self.assertEqual(len(lists), 1)
        self.assertEqual(lists[0]["common_fields"], ["nom", "ville"])

    def test_actions_ignorees_et_uniques(self):
        ids = {(u["app"], u["id"]) for u in self.cmp["unique"]}
        self.assertEqual(ids, {("gestion", "produits"), ("crm", "campagnes")})
        self.assertNotIn(("gestion", "client-n-save"), ids)
        self.assertEqual(self.cmp["counts"]["shared_by_all"], 2)
        self.assertEqual(self.cmp["counts"]["screens"], {"gestion": 3, "crm": 3})

    def test_un_ecran_par_application_et_par_groupe(self):
        for g in self.cmp["groups"]:
            apps = [s["app"] for s in g["screens"]]
            self.assertEqual(len(apps), len(set(apps)))


class TestUnified(unittest.TestCase):
    def setUp(self):
        self.specs = {"gestion": _spec_gestion(), "crm": _spec_crm()}
        self.uni = merge.unified_spec(self.specs, label="clients unifiés")

    def test_ecran_unifie_et_sources(self):
        fiche = next(s for s in self.uni["screens"] if s["title"] == "Fiche client")
        self.assertTrue(fiche["shared"])
        by = {f["name"]: f for f in fiche["fields"]}
        self.assertEqual(by["nom"]["sources"], {"gestion": {"table": "clients", "column": "nom", "confidence": 1.0},
                                                 "crm": {"table": "customers", "column": "name", "confidence": 0.9}})
        self.assertTrue(by["nom"]["shared"])
        self.assertEqual(by["nom"]["names"], {"gestion": "nom", "crm": "txtNom"})
        self.assertTrue(by["nom"]["required"])
        self.assertFalse(by["tel"]["shared"])
        self.assertEqual(by["tel"]["apps"], ["crm"])
        self.assertEqual(fiche["targets"]["crm"], {"table": "customers", "pk": "customer_id", "screen_id": "customer-n", "dba_connection_id": 2, "dba_database": "crm"})
        self.assertEqual(fiche["todo"], ["champs propres à une application : 3"])

    def test_ecrans_propres_et_ordre(self):
        titles = [s["title"] for s in self.uni["screens"]]
        # partagés d'abord (liste puis formulaire), puis propres
        self.assertEqual(titles[:2], ["Clients", "Fiche client"])
        self.assertIn("Produits (gestion)", titles)
        self.assertIn("Campagnes (crm)", titles)
        self.assertEqual(self.uni["counts"], {"screens": 4, "shared": 2, "partial": 0, "unique": 2})

    def test_projection_par_application(self):
        v = merge.per_app_view(self.uni, "crm")
        self.assertEqual(v["app"], "crm")
        self.assertEqual(v["dba_connection_id"], 2)
        self.assertEqual([s["title"] for s in v["screens"]], ["Clients", "Fiche client", "Campagnes (crm)"])
        fiche = v["screens"][1]
        self.assertEqual(fiche["table"], "customers")
        self.assertEqual(fiche["pk"], "customer_id")
        cols = {f["name"]: f["column"] for f in fiche["fields"]}
        # remise n'existe pas dans crm : champ présent, sans colonne
        self.assertEqual(cols, {"nom": "name", "email": "mail", "ville": None, "remise": None, "tel": "tel"})
        self.assertTrue(v["screens"][0]["nav"])

    def test_trois_applications_partiel(self):
        specs = dict(self.specs)
        specs["compta"] = {"app": "compta", "screens": [{"id": "factures", "screen": "/factures", "title": "Factures", "kind": "list", "table": "factures",
                                                          "columns": [{"label": "Numéro", "column": "num"}, {"label": "Montant", "column": "montant"}], "fields": []}]}
        uni = merge.unified_spec(specs)
        self.assertEqual(uni["apps"], ["compta", "crm", "gestion"])
        self.assertEqual(uni["counts"]["shared"], 0)
        self.assertEqual(uni["counts"]["partial"], 2)
        self.assertEqual(uni["counts"]["unique"], 3)


if __name__ == "__main__":
    unittest.main()
