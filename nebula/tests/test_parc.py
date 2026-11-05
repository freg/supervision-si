# -*- coding: utf-8 -*-
"""#971 : parc des terminaux -- synthèse, association MAC <-> terminal par le nom réseau, inconnus, changements de bail, déplacements."""
import os
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "api"))
import parc as P  # noqa: E402
import reperage as R  # noqa: E402

EQS = [{"id": "t1", "nom": "E11 AmpIm", "categorie": "Tablettes", "lab": "Amphi Immersif"},
       {"id": "t2", "nom": "Med-05", "categorie": "Tablettes", "lab": "Médiateurs", "mac": "aa:00:00:00:00:05"},
       {"id": "t3", "nom": "Doublon", "categorie": "Postes"}, {"id": "t4", "nom": "Doublon", "categorie": "Postes"},
       {"id": "b1", "nom": "WBE660S-Studio", "role": "borne", "local": "Studio"},
       {"id": "b2", "nom": "WBE660S-Amphi", "role": "borne", "local": "Amphi"}]
VUS = [{"mac": "aa:00:00:00:00:11", "ip": "172.16.20.11", "name": "E11-AmpIm", "manufacturer": "Samsung", "last_seen": 1000, "first_seen": 10},
       {"mac": "aa:00:00:00:00:05", "ip": "172.16.20.5", "name": "MED-05-Mediateurs", "last_seen": 900},
       {"mac": "aa:00:00:00:00:31", "name": "doublon", "last_seen": 800}, {"mac": "aa:00:00:00:00:32", "name": "Doublon", "last_seen": 800},
       {"mac": "aa:00:00:00:00:99", "ip": "172.16.20.99", "name": "inconnu", "last_seen": 50, "ssid": "Campus"}]


class TestParc(unittest.TestCase):
    def test_synthese_et_association(self):
        s = P.synthese(EQS)
        self.assertEqual((s["total"], s["avec_mac"]), (6, 1)); self.assertEqual(s["tableau"]["Tablettes"]["Médiateurs"], 1)
        p = P.associer(EQS, VUS)
        self.assertEqual([(x["id"], x["mac"], x["par"]) for x in p], [("t1", "aa:00:00:00:00:11", "nom réseau")])   # nom ambigu : rien
        self.assertEqual(P.norm_nom("Écran-01 Amphi"), "ecran01amphi")
        inc = P.inconnus(VUS, EQS, depuis=100)
        self.assertEqual([x["mac"] for x in inc], ["aa:00:00:00:00:11", "aa:00:00:00:00:31", "aa:00:00:00:00:32"])

    def test_baux_et_deplacements(self):
        eqs = [dict(EQS[1]), {"id": "x", "nom": "Autre", "mac": "aa:00:00:00:00:07"}] + EQS[4:]
        ses = [{"mac": "aa:00:00:00:00:05", "start": 0, "end": 100, "ip": "172.16.20.5", "device": "WBE660S-Studio", "ssid": "Campus"},
               {"mac": "aa:00:00:00:00:05", "start": 200, "end": 300, "ip": "172.16.20.8", "device": "WBE660S-Amphi", "ssid": "Campus"},
               {"mac": "aa:00:00:00:00:05", "start": 400, "end": 500, "ip": "172.16.20.8", "device": "WBE660S-Amphi", "ssid": "Campus"},
               {"mac": "aa:00:00:00:00:07", "start": 350, "end": 450, "ip": "172.16.20.5", "device": "GS2220", "port": "12"}]
        b = P.baux(ses, eqs)
        self.assertEqual(b["changements"][0], {"mac": "aa:00:00:00:00:05", "nom": "Med-05", "ancienne": "172.16.20.5", "nouvelle": "172.16.20.8", "at": 200})
        self.assertEqual(b["par_mac"][0]["n"], 1)
        self.assertEqual([p["ip"] for p in b["ip_partagees"]], ["172.16.20.5"])
        self.assertEqual([m["nom"] for m in b["ip_partagees"][0]["macs"]], ["Med-05", "Autre"])
        d = P.deplacements(ses, eqs)
        self.assertEqual([l["piece"] for l in d["par_mac"]["aa:00:00:00:00:05"]], ["Studio", "Amphi", "Amphi"])
        self.assertEqual(d["changements"][-1]["de"], "Studio · Campus"); self.assertEqual(len([c for c in d["changements"] if c["nom"] == "Med-05"]), 1)
        self.assertEqual(P.baux([], []), {"changements": [], "par_mac": [], "ip_partagees": []})

    def test_champs_parc_et_import(self):
        e, err = R.valider_equipement({"nom": "E11 AmpIm", "categorie": "Tablettes", "serie": "R5GY", "lab": "Amphi Immersif", "inconnu": "x"})
        self.assertIsNone(err); self.assertEqual((e["categorie"], e["serie"]), ("Tablettes", "R5GY")); self.assertNotIn("inconnu", e)
        lignes, err = R.lire_csv_equipements("Nom;Catégorie;Numero de série;Lab;Adresse MAC\nE11 AmpIm;Tablettes;R5GY;Amphi;E4-9F-7D-BD-CE-52\n")
        self.assertEqual((lignes[0]["serie"], lignes[0]["lab"], lignes[0]["mac"]), ("R5GY", "Amphi", "e4:9f:7d:bd:ce:52"))
        # plusieurs MAC (Wi-Fi, Ethernet, virtuelles) : la MAC matérielle devient la principale, toutes servent au rapprochement
        e, err = R.valider_equipement({"nom": "PC", "mac": "32-94-20-52-41-53, E4-1F-D5-C5-70-74;E4-1F-D5-C5-70-75"})
        self.assertIsNone(err); self.assertEqual(e["mac"], "e4:1f:d5:c5:70:74"); self.assertEqual(len(e["macs"]), 3)
        self.assertIn("MAC invalide", R.valider_equipement({"nom": "PC", "mac": "e4-1f-d5-c5-70-74, zz"})[1])
        self.assertIsNone(R.valider_equipement({"nom": "PC", "mac": "e4-1f-d5-c5-70-74"})[0]["macs"])
        eqs = [dict(e, id="pc")]
        self.assertEqual(P.inconnus([{"mac": "32:94:20:52:41:53", "last_seen": 5}], eqs), [])
        b = P.baux([{"mac": "e4:1f:d5:c5:70:75", "start": 0, "end": 1, "ip": "1.1.1.1"}, {"mac": "e4:1f:d5:c5:70:75", "start": 2, "end": 3, "ip": "1.1.1.2"}], eqs)
        self.assertEqual(b["changements"][0]["nom"], "PC")

    def test_routes(self):
        try:
            from flask import Flask
        except ImportError:
            self.skipTest("flask absent")
        import reperage_routes as RR
        import client_history as CH
        d = tempfile.mkdtemp(); db = os.path.join(d, "n.db")

        def conn():
            c = sqlite3.connect(db); c.row_factory = sqlite3.Row; return c
        app = Flask(__name__)
        RR.register(app, {"conn": conn, "client": lambda: None, "db_path": db, "devices": lambda sid: []})
        cl = app.test_client()
        g = cl.get("/sites/s1/reperage/parc").get_json()
        self.assertIn("historique", g["erreur"]); self.assertEqual(g["synthese"]["total"], 0)      # avant toute relève : pas d'erreur 500
        c = conn(); CH.ingest(c, "s1", {"aa:00:00:00:00:11": {"mac": "aa:00:00:00:00:11", "ip": "172.16.20.11", "name": "E11-AmpIm", "last_seen": 2_000_000_000, "ssid": "Campus"}},
                              now=2_000_000_000); c.close()
        r = cl.post("/sites/s1/reperage/equipements/import", json={"texte": "nom;categorie;serie;lab\nE11 AmpIm;Tablettes;R5GY;Amphi\n"}).get_json()
        self.assertEqual(r["ajoutes"], 1)
        r = cl.post("/sites/s1/reperage/equipements/import", json={"texte": "nom;stockage\nE11 AmpIm;Chariot 16\n"}).get_json()
        self.assertEqual((r["ajoutes"], r["mis_a_jour"]), (0, 1))                               # même nom, sans MAC ni IP : même fiche
        g = cl.get("/sites/s1/reperage/parc?jours=400").get_json()
        self.assertEqual(g["propositions"][0]["mac"], "aa:00:00:00:00:11")
        self.assertEqual(cl.post("/sites/s1/reperage/parc/associer", json={"par": "fr"}).get_json()["associes"], 1)
        eq = cl.get("/sites/s1/reperage/equipements").get_json()["equipements"][0]
        self.assertEqual((eq["mac"], eq["ip"], eq["mac_source"], eq["stockage"]), ("aa:00:00:00:00:11", "172.16.20.11", "appris (nom réseau)", "Chariot 16"))
        e = cl.put("/sites/s1/reperage/equipements", json={"id": eq["id"], "nom": "E11 AmpIm", "mac": eq["mac"], "role": "tablette"}).get_json()
        self.assertEqual((e["categorie"], e["serie"]), ("Tablettes", "R5GY"))                  # le formulaire ne fait pas perdre la fiche de parc
        t = cl.get("/sites/s1/reperage/parc/terminal/%s?jours=400" % eq["id"]).get_json()
        self.assertEqual(t["lieux"][0]["ssid"], "Campus")
        self.assertEqual(cl.get("/sites/s1/reperage/parc/terminal/zz").status_code, 404)


if __name__ == "__main__":
    unittest.main()
