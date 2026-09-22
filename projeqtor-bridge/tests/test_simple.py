# -*- coding: utf-8 -*-
"""Espace Simple (livraison #541) : état d'une demande en français,
propagation des dépendances entre services."""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import simple  # noqa: E402

SERVICES = [
    {"id": "coeur", "nom": "Cœur de réseau", "sert_a": "tout relier"},
    {"id": "reseau-b", "nom": "Réseau du bâtiment B", "sert_a": "se connecter depuis le bâtiment B", "depend_de": ["coeur"]},
    {"id": "mail", "nom": "Messagerie", "sert_a": "lire et envoyer des courriels", "depend_de": ["coeur"], "sources": {"service_watch": ["mail", "webmail"]}},
    {"id": "ent", "nom": "Espace numérique de travail", "sert_a": "agenda, tâches", "depend_de": ["reseau-b"]},
    {"id": "imprimante-2", "nom": "Imprimante du 2e étage", "sert_a": "imprimer au 2e", "depend_de": ["reseau-b"]},
]


class Ref(unittest.TestCase):
    def test_public_ref(self):
        self.assertEqual(simple.public_ref("pont:s:0123456789ab"), "D-0123456789ab")
        self.assertIsNone(simple.public_ref("pont:i:42"))
        self.assertIsNone(simple.public_ref(""))
        self.assertTrue(simple.ref_matches("D-0123456789AB", "pont:s:0123456789ab"))
        self.assertTrue(simple.ref_matches(" 0123456789ab ", "pont:s:0123456789ab"))
        self.assertFalse(simple.ref_matches("D-", "pont:s:0123456789ab"))
        self.assertFalse(simple.ref_matches("D-0123456789ab", "pont:s:ffffffffffff"))


class Status(unittest.TestCase):
    def test_recue_en_cours_resolue(self):
        now = 1_000_000
        t = {"ts_created": now - 3600, "statut_label": "Nouveau", "subject": "Imprimante du 2e"}
        s = simple.plain_status(t, now=now)
        self.assertEqual((s["etat"], s["mot"]), ("recue", "reçue"))
        self.assertEqual(s["attente_heures"], 1.0)
        self.assertNotIn("demandeur", s)
        s = simple.plain_status(dict(t, user_login="alice"), now=now)
        self.assertEqual(s["etat"], "en_cours")
        s = simple.plain_status(dict(t, ts_closed=now - 10), now=now)
        self.assertEqual(s["mot"], "résolue")
        s = simple.plain_status({"ts_created": now - 3 * 86400, "statut_label": "Nouveau"}, now=now)
        self.assertIn("deux jours", s["conseil"])
        self.assertIsNone(simple.plain_status(None))


class Live(unittest.TestCase):
    def test_service_watch_vers_etats(self):
        entries = [{"name": "mail", "last": {"state": "warning", "at": "2026-09-22T09:00:00Z"}},
                   {"name": "webmail", "last": {"state": "critical", "at": "2026-09-22T09:05:00Z"}},
                   {"name": "www", "last": {"state": "critical", "at": "x"}},
                   {"name": "old", "gone_at": "y", "last": {"state": "critical"}}]
        live = simple.etats_depuis_service_watch(SERVICES, entries)
        self.assertEqual(list(live), ["mail"])
        self.assertEqual(live["mail"]["etat"], "panne")  # la pire des deux entrées
        self.assertEqual(live["mail"]["depuis"], "2026-09-22T09:05:00Z")
        self.assertEqual(simple.etats_depuis_service_watch(SERVICES, [{"name": "mail", "last": {"state": "ok"}}]), {})
        self.assertEqual(simple.etats_depuis_service_watch(SERVICES, None), {})
        fus = simple.fusion_etats({"mail": {"etat": "degrade", "message": "retour à 14 h"}, "_a": "t"}, live)
        self.assertEqual(fus["mail"]["message"], "retour à 14 h")  # l'exploitation l'emporte
        self.assertEqual(fus["_a"], "t")
        page = simple.etat_des_services(SERVICES, simple.fusion_etats({}, live))
        self.assertEqual(page["phrases"], ["Messagerie : en panne."])


class Etat(unittest.TestCase):
    def test_impact_propagation(self):
        imp = simple.impacted(SERVICES, ["reseau-b"])
        self.assertEqual(set(imp), {"ent", "imprimante-2"})
        self.assertEqual(imp["ent"], ["reseau-b"])
        imp = simple.impacted(SERVICES, ["coeur"])
        self.assertEqual(set(imp), {"reseau-b", "mail", "ent", "imprimante-2"})
        self.assertEqual(imp["ent"], ["coeur"])
        self.assertEqual(simple.impacted(SERVICES, []), {})
        # cycle toléré
        cyc = [{"id": "a", "depend_de": ["b"]}, {"id": "b", "depend_de": ["a"]}, {"id": "c", "depend_de": ["a"]}]
        self.assertEqual(set(simple.impacted(cyc, ["b"])), {"a", "c"})

    def test_page_etat(self):
        page = simple.etat_des_services(SERVICES, {"reseau-b": {"etat": "panne", "depuis": "2026-09-22T08:00:00Z", "message": "Switch en défaut"}})
        self.assertEqual(page["resume"], "3 services touchés.")
        self.assertEqual(page["phrases"], ["Réseau du bâtiment B : en panne, donc Espace numérique de travail, Imprimante du 2e étage ne marchent pas."])
        byid = {l["id"]: l for l in page["services"]}
        self.assertEqual(byid["ent"]["etat"], "panne")
        self.assertEqual(byid["ent"]["cause"], ["Réseau du bâtiment B"])
        self.assertEqual(byid["ent"]["depuis"], "2026-09-22T08:00:00Z")
        self.assertEqual(byid["mail"]["mot"], "ça marche")
        self.assertEqual(page["services"][0]["etat"], "panne")  # pannes d'abord
        ok = simple.etat_des_services(SERVICES, {})
        self.assertEqual(ok["resume"], "Tout fonctionne.")
        self.assertEqual(ok["phrases"], [])
        deg = simple.etat_des_services(SERVICES, {"coeur": {"etat": "degrade"}, "inconnu": {"etat": "panne"}})
        self.assertEqual({l["etat"] for l in deg["services"]}, {"degrade"})


if __name__ == "__main__":
    unittest.main()
