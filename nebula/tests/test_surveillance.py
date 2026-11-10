# -*- coding: utf-8 -*-
"""Tests #1001 : liste de surveillance -- dépôt d'une liste collée, concordance élément par élément, discordances,
repères « du lot », apprentissage par décision. Données inventées."""
import os
import sqlite3
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "api"))
import client_history as ch  # noqa: E402
import surveillance as sv  # noqa: E402

T0 = 1_791_000_000
LISTE = ("Nom\tType\tModèle\tRéférence\tN° série\tMAC\n"
         "T01 Atelier\tTablette\tTab A11+\tSM-X230\tR5XXA01AAAA\ta4:9f:00:00:00:01\n"
         "T02 Atelier\tTablette\tTab A11+\tSM-X230\tR5XXA02BBBB\ta4:9f:00:00:00:02\n"
         "T03 Atelier\tTablette\tTab A11+\tSM-X230\tR5XXA03CCCC\ta4:9f:00:00:00:03\n"
         "\n"
         "une ligne de commentaire\n")


def vus(conn, clients, now=T0):
    ch.ingest(conn, "site-alpha", ch.merge(clients, now=now), now=now)


class Depot(unittest.TestCase):
    def test_analyse(self):
        a = sv.analyser_texte(LISTE)
        self.assertEqual(len(a["elements"]), 3)
        e = a["elements"][0]
        self.assertEqual((e["libelle"], e["type"], e["modele"], e["reference"], e["serie"], e["mac"], e["fabricant"]),
                         ("T01 Atelier", "tablette", "Tab A11+", "SM-X230", "R5XXA01AAAA", "a4:9f:00:00:00:01", "Samsung"))
        self.assertEqual([i["raison"] for i in a["ignorees"]], ["ligne d'en-tête", "aucun identifiant reconnu (MAC, n° de série, ou nom + modèle)"])

    def test_separateurs_et_ordre_libre(self):
        e = sv.analyser_ligne("A4-9F-00-00-00-09; SM-X230; poste 9; R5XXA09ZZZZ")
        self.assertEqual((e["mac"], e["reference"], e["libelle"], e["serie"]), ("a4:9f:00:00:00:09", "SM-X230", "poste 9", "R5XXA09ZZZZ"))

    def test_enregistrer_dedoublonne(self):
        c = sqlite3.connect(":memory:")
        els = sv.analyser_texte(LISTE)["elements"]
        self.assertEqual(sv.enregistrer(c, "tablettes", els, now=T0), {"ajoutes": 3, "maj": 0})
        self.assertEqual(sv.enregistrer(c, "tablettes", els, now=T0), {"ajoutes": 0, "maj": 3})
        self.assertEqual(sv.listes(c), [{"liste": "tablettes", "elements": 3}])


class Concordance(unittest.TestCase):
    def setUp(self):
        self.c = sqlite3.connect(":memory:")
        sv.enregistrer(self.c, "tablettes", sv.analyser_texte(LISTE)["elements"], now=T0)
        self.els = {e["libelle"]: e for e in sv.elements(self.c)}

    def test_mac_declaree(self):
        r = sv.concorder(self.els["T01 Atelier"], {"mac": "a4:9f:00:00:00:01", "name": "Galaxy-Tab-A11", "manufacturer": "Samsung Electronics Co.,Ltd"})
        self.assertEqual(r["statut"], "reconnu")
        self.assertEqual([p["element"] for p in r["preuves"]], ["MAC", "nom", "fabricant"])

    def test_mac_clonee_discordance(self):
        r = sv.concorder(self.els["T01 Atelier"], {"mac": "a4:9f:00:00:00:01", "name": "DESKTOP-4F2K", "manufacturer": "Intel Corporate", "os": "Windows"})
        self.assertEqual(r["statut"], "discordant")
        self.assertEqual([d["force"] for d in r["discordances"]], ["faible", "forte", "forte"])

    def test_mac_aleatoire_par_les_autres_elements(self):
        r = sv.concorder(self.els["T02 Atelier"], {"mac": "6e:11:22:33:44:55", "name": "R5XXA02BBBB", "os": "Android"})
        self.assertFalse(r["par_mac"])
        self.assertEqual(r["statut"], "probable")          # n° de série (40) + système (10)
        self.assertIn("MAC aléatoire", r["preuves"][0]["texte"])

    def test_contre_indice(self):
        r = sv.concorder(self.els["T02 Atelier"], {"mac": "6e:11:22:33:44:55", "name": "Galaxy Tab A11", "os": "Windows 11"})
        self.assertIsNone(r["statut"])

    def test_lot_puis_apprentissage(self):
        vus(self.c, [{"mac": "6e:11:22:33:44:55", "name": "Galaxy-Tab-A11", "os": "Android", "lastSeen": T0},
                     {"mac": "a4:9f:00:00:00:03", "name": "Galaxy-Tab-A11", "manufacturer": "Samsung Electronics", "lastSeen": T0},
                     {"mac": "00:0c:29:00:00:01", "name": "serveur", "lastSeen": T0}])
        ev = sv.rapprocher(self.c, "site-alpha", T0 - 3600, now=T0)
        self.assertEqual(sorted((e["statut"], e["element"]) for e in ev), [("lot", None), ("reconnu", "T03 Atelier")])
        self.assertEqual(sv.rapprocher(self.c, "site-alpha", T0 - 3600, now=T0), [])     # rien de neuf à la relève suivante
        lot = next(r for r in sv.reperes(self.c, "site-alpha") if r["statut"] == "lot")
        with self.assertRaises(ValueError):
            sv.decider(self.c, lot["id"], "confirme")
        sv.decider(self.c, lot["id"], "confirme", element_id=self.els["T01 Atelier"]["id"], par="freg", now=T0)
        t1 = next(e for e in sv.elements(self.c) if e["libelle"] == "T01 Atelier")
        self.assertEqual(t1["macs_apprises"], ["6e:11:22:33:44:55"])
        self.assertEqual(sv.concorder(t1, {"mac": "6e:11:22:33:44:55"})["statut"], "reconnu")   # la MAC aléatoire est apprise
        sv.decider(self.c, lot["id"], "annule")
        self.assertEqual(next(e for e in sv.elements(self.c) if e["libelle"] == "T01 Atelier")["macs_apprises"], [])

    def test_rejet_definitif_et_discordance_signalee(self):
        vus(self.c, [{"mac": "a4:9f:00:00:00:02", "name": "Galaxy-Tab-A11", "manufacturer": "Samsung Electronics", "lastSeen": T0}])
        sv.rapprocher(self.c, "site-alpha", T0 - 3600, now=T0)
        vus(self.c, [{"mac": "a4:9f:00:00:00:02", "name": "Galaxy-Tab-A11", "os": "Windows", "lastSeen": T0 + 3600}], now=T0 + 3600)
        ev = sv.rapprocher(self.c, "site-alpha", T0, now=T0 + 3600)
        self.assertEqual([(e["type"], e["statut"]) for e in ev], [("discordance", "discordant")])
        r = sv.reperes(self.c, "site-alpha")[0]
        sv.decider(self.c, r["id"], "rejete")
        self.assertEqual(sv.rapprocher(self.c, "site-alpha", T0, now=T0 + 3600), [])

    def test_comportement(self):
        machine = lambda cl: {"categorie": "machine Linux / sans écran", "confiance": 70}
        mobile = lambda cl: {"categorie": "mobile Android", "confiance": 80}
        vus(self.c, [{"mac": "a4:9f:00:00:00:01", "name": "Galaxy-Tab-A11", "manufacturer": "Samsung Electronics", "lastSeen": T0}])
        ev = sv.rapprocher(self.c, "site-alpha", T0 - 3600, now=T0, categorie_de=machine)
        self.assertEqual(ev[0]["statut"], "discordant")
        self.assertIn("comportement de « machine Linux / sans écran »", ev[0]["discordances"][0])
        r = sv.ajuster_par_comportement(sv.concorder(self.els["T02 Atelier"], {"mac": "6e:00:00:00:00:09", "name": "R5XXA02BBBB"}), "tablette", mobile({}))
        self.assertEqual((r["statut"], r["score"]), ("probable", 50))
        self.assertIs(sv.ajuster_par_comportement(r, "tablette", {"categorie": "mobile Android", "confiance": 20}), r)

    def test_prefixe_deduit_du_site(self):
        vus(self.c, [{"mac": "a4:9f:00:00:00:77", "manufacturer": "Samsung Electronics", "lastSeen": T0}])
        el = {"mac": "a4:9f:00:00:00:01"}
        self.assertEqual(sv.contexte(self.c, "site-alpha")["oui"]["a4:9f:00"], "Samsung Electronics")
        r = sv.concorder(el, {"mac": "a4:9f:00:00:00:01", "manufacturer": "Apple"}, sv.contexte(self.c, "site-alpha"))
        self.assertEqual(r["statut"], "discordant")


if __name__ == "__main__":
    unittest.main()
