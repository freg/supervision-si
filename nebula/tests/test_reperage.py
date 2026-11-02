# -*- coding: utf-8 -*-
import json, os, sys, tempfile, unittest
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "api"))
import reperage as R  # noqa: E402

SW = [{"macAddress": "AA:BB:CC:00:00:01", "ipv4Address": "172.16.20.10", "connectedTo": "dev-sw1", "connectedPort": 12, "vlan": 20, "osHostname": {"hostname": "ecran-amphi"}},
      {"macAddress": "aa-bb-cc-00-00-02", "connectedTo": "dev-sw1", "connectedPort": 3, "vlan": 99, "manufacturer": "Zyxel"}]
AP = [{"macAddress": "aabbcc000003", "ipv4Address": "172.16.22.51", "connectedTo": "dev-ap7", "ssid": "Campus_Numeria", "wifiStation": {"signal": -58, "band": "band5", "channel": 44},
       "osHostname": {"hostname": "Pixel-freg"}}]
SC = [{"macAddress": "AA:BB:CC:00:00:01", "manufacturer": "Samsung", "lastSeen": 1700000000, "description": "Ecran amphi"},
      {"macAddress": "AA:BB:CC:00:00:03", "manufacturer": "Google"}]
DEV = [{"devId": "dev-sw1", "name": "GS2220-50HP-1"}, {"devId": "dev-ap7", "name": "WBE660S-Studio"}]


class TestReperage(unittest.TestCase):
    def test_norm_mac(self):
        self.assertEqual(R.norm_mac("AA-BB-CC-00-00-01"), "aa:bb:cc:00:00:01"); self.assertEqual(R.norm_mac("aabb.cc00.0001"), "aa:bb:cc:00:00:01")
        self.assertIsNone(R.norm_mac("zz")); self.assertIsNone(R.norm_mac(None))

    def test_inventaire_fusion(self):
        inv = R.inventaire(SW, AP, SC, DEV, now=1)
        c = {x["mac"]: x for x in inv["clients"]}
        e = c["aa:bb:cc:00:00:01"]
        self.assertEqual((e["type"], e["commutateur"], e["port"], e["vlan"], e["ip"], e["nom"], e["fabricant"]), ("filaire", "GS2220-50HP-1", 12, 20, "172.16.20.10", "ecran-amphi", "Samsung"))
        p = c["aa:bb:cc:00:00:03"]
        self.assertEqual((p["type"], p["borne"], p["ssid"], p["signal"], p["bande"], p["canal"], p["fabricant"]), ("wifi", "WBE660S-Studio", "Campus_Numeria", -58, "band5", 44, "Google"))
        self.assertEqual(inv["commutateurs"][0]["ports"], {"12": ["aa:bb:cc:00:00:01"], "3": ["aa:bb:cc:00:00:02"]})
        self.assertEqual(inv["bornes"][0]["signal_moyen"], -58); self.assertEqual(inv["bornes"][0]["clients"], 1)

    def test_recherche(self):
        inv = R.inventaire(SW, AP, SC, DEV)
        prises = [{"prise": "B-12", "local": "Amphi", "commutateur": "GS2220-50HP-1", "port": 12, "mac": "aa:bb:cc:00:00:01"}]
        self.assertEqual(R.rechercher(inv, prises, "a"), [])
        r = R.rechercher(inv, prises, "aa:bb:cc:00:00:01"); self.assertEqual(r[0]["genre"], "client"); self.assertEqual(r[0]["score"], 100)
        r = R.rechercher(inv, prises, "amphi"); self.assertEqual({x["genre"] for x in r}, {"client", "prise"})
        r = R.rechercher(inv, prises, "gs2220 p12"); self.assertTrue(all(str(x["objet"].get("port")) == "12" for x in r)); self.assertEqual(len(r), 2)
        r = R.rechercher(inv, prises, "172.16.22"); self.assertEqual(r[0]["objet"]["mac"], "aa:bb:cc:00:00:03")
        r = R.rechercher(inv, prises, "b-12"); self.assertEqual(r[0]["genre"], "prise")

    def test_valider_prise(self):
        p, err = R.valider_prise({"prise": " B-12 ", "port": "12", "mac": "AA-BB-CC-00-00-01", "x": 1.4, "y": -1, "long_cordon": 1, "photos": ["a.jpg", 5]})
        self.assertIsNone(err); self.assertEqual((p["prise"], p["port"], p["mac"], p["x"], p["y"], p["long_cordon"], p["wifi"], p["photos"]), ("B-12", 12, "aa:bb:cc:00:00:01", 1.0, 0.0, True, False, ["a.jpg", "5"]))
        self.assertEqual(R.valider_prise({})[1], "libellé de prise requis (ex. « B-12 »)"); self.assertEqual(R.valider_prise({"prise": "x", "port": "ab"})[1], "port invalide")
        self.assertEqual(R.valider_prise({"prise": "x"})[0]["x"], None)

    def test_signal_et_releve(self):
        self.assertEqual([R.signal_couleur(s) for s in (-50, -65, -75, -85, None, "x")], ["bon", "moyen", "faible", "mauvais", "inconnu", "inconnu"])
        m = next(c for c in R.inventaire(SW, AP, SC, DEV)["clients"] if c["mac"] == "aa:bb:cc:00:00:03")
        r = R.releve_depuis_mobile(m, 0.5, 2, "près de la porte", rssi_mobile="-61", now=5)
        self.assertEqual((r["x"], r["y"], r["borne"], r["signal"], r["rssi_mobile"], r["classe"], r["at"]), (0.5, 1.0, "WBE660S-Studio", -58, -61, "moyen", 5))
        self.assertIsNone(R.releve_depuis_mobile({}, "a", 0))
        self.assertEqual(R.releve_depuis_mobile({}, 0.1, 0.1)["classe"], "inconnu")

    def test_appareils_et_connus(self):
        self.assertEqual(R.valider_appareil({"mac": "AA:BB:CC:00:00:01", "nom": " Tél ", "genre": "zz"})[0], {"mac": "aa:bb:cc:00:00:01", "nom": "Tél", "genre": "autre"})
        self.assertEqual(R.valider_appareil({"mac": "aa:bb:cc:00:00:01"})[1], "nom requis (ex. « Téléphone Freg »)")
        inv = R.enrichir_connus(R.inventaire(SW, AP, SC, DEV), [{"mac": "aa:bb:cc:00:00:02", "nom": "Borne de test", "genre": "autre"}])
        c = next(x for x in inv["clients"] if x["mac"] == "aa:bb:cc:00:00:02"); self.assertEqual((c["nom"], c["connu"]), ("Borne de test", "Borne de test"))
        t = R.inventaire_test(now=100, appareils=[{"mac": "02:00:00:00:00:55", "nom": "T", "genre": "telephone"}, {"mac": "02:00:00:00:00:56", "nom": "PC", "genre": "pc"}])
        self.assertTrue(any(c["mac"] == "02:00:00:00:00:55" and c["type"] == "wifi" for c in t["clients"])); self.assertFalse(any(c["mac"] == "02:00:00:00:00:56" for c in t["clients"]))

    def test_csv(self):
        t = R.prises_csv([{"prise": "B-12", "port": 12, "long_cordon": True, "photos": ["a", "b"], "note": "x;y\nz"}])
        self.assertEqual(t.splitlines()[1].split(";")[:4], ["B-12", "", "", "12"]); self.assertIn("oui", t); self.assertIn("a b", t); self.assertIn("x,y z", t)


class TestRoutes(unittest.TestCase):
    def test_routes(self):
        try:
            import flask  # noqa: F401
        except ImportError:
            self.skipTest("flask absent")
        import sqlite3
        from flask import Flask
        import reperage_routes as RR
        d = tempfile.mkdtemp(); db = os.path.join(d, "n.db")

        def conn():
            c = sqlite3.connect(db); c.row_factory = sqlite3.Row; return c

        class Cl:
            def sw_clients(self, sid, period="1d"): return {"data": SW}
            def ap_clients_v2(self, sid, period="1d"): return AP
            def get_site_clients(self, sid, period="2h", features=None): return SC
        app = Flask(__name__); RR._cache.clear()
        RR.register(app, {"conn": conn, "client": lambda: Cl(), "db_path": db, "devices": lambda sid: DEV})
        cl = app.test_client()
        inv = cl.get("/sites/s1/reperage/inventaire").get_json(); self.assertEqual(len(inv["clients"]), 3); self.assertEqual(inv["erreurs"], [])
        r = cl.put("/sites/s1/reperage/prises", json={"prise": "B-12", "local": "Amphi", "port": 12, "commutateur": "GS2220-50HP-1", "par": "freg"}).get_json(); self.assertEqual(r["port"], 12)
        self.assertEqual(cl.put("/sites/s1/reperage/prises", json={"prise": "B-12", "local": "Amphi 2", "port": 12}).status_code, 200)
        ps = cl.get("/sites/s1/reperage/prises").get_json()["prises"]; self.assertEqual(len(ps), 1); self.assertEqual(ps[0]["local"], "Amphi 2")
        self.assertEqual(cl.put("/sites/s1/reperage/prises", json={"port": 1}).status_code, 400)
        self.assertIn("B-12", cl.get("/sites/s1/reperage/prises.csv").get_data(as_text=True))
        rs = cl.get("/sites/s1/reperage/recherche?q=p12").get_json()["resultats"]; self.assertEqual({x["genre"] for x in rs}, {"client", "prise"})
        m = cl.get("/sites/s1/reperage/mobile?mac=AA:BB:CC:00:00:03").get_json(); self.assertTrue(m["vu"]); self.assertEqual(m["mobile"]["signal"], -58); self.assertEqual(m["classe"], "bon")
        self.assertEqual(cl.get("/sites/s1/reperage/mobile?mac=zz").status_code, 400)
        rl = cl.post("/sites/s1/reperage/releves", json={"x": 0.2, "y": 0.3, "mac": "aa:bb:cc:00:00:03", "note": "porte"}).get_json(); self.assertEqual(rl["borne"], "WBE660S-Studio")
        self.assertEqual(cl.post("/sites/s1/reperage/releves", json={"x": "a"}).status_code, 400)
        self.assertEqual(len(cl.get("/sites/s1/reperage/releves").get_json()["releves"]), 1)
        self.assertEqual(cl.delete("/sites/s1/reperage/releves/" + rl["id"]).get_json()["supprime"], 1)
        # photo : type, taille, lecture
        import io
        r = cl.post("/sites/s1/reperage/photos", data={"file": (io.BytesIO(b"\xff\xd8\xff" + b"0" * 100), "p.jpg", "image/jpeg")}, content_type="multipart/form-data")
        self.assertEqual(r.status_code, 201); pid = r.get_json()["id"]; self.assertTrue(pid.endswith(".jpg"))
        self.assertEqual(cl.get("/sites/s1/reperage/photos/" + pid).status_code, 200)
        self.assertEqual(cl.post("/sites/s1/reperage/photos", data={"file": (io.BytesIO(b"x"), "p.txt", "text/plain")}, content_type="multipart/form-data").status_code, 415)
        self.assertEqual(cl.delete("/sites/s1/reperage/prises/B-12").get_json()["supprime"], 1)
        # site de test (bureau, sans Nebula) : inventaire simulé, téléphone vu avec un signal, liste des sites
        self.assertEqual([s["site_id"] for s in cl.get("/reperage/sites").get_json()["sites"]][-1], "test-bureau")
        inv = cl.get("/sites/test-bureau/reperage/inventaire").get_json(); self.assertTrue(inv["test"]); self.assertEqual(inv["commutateurs"][0]["nom"], "SW-TEST")
        m = cl.get("/sites/test-bureau/reperage/mobile?mac=11:22:33:44:55:66").get_json(); self.assertTrue(m["vu"]); self.assertEqual(m["mobile"]["borne"], "BORNE-TEST"); self.assertLessEqual(m["mobile"]["signal"], -48)
        self.assertTrue(any(c["mac"] == "11:22:33:44:55:66" for c in cl.get("/sites/test-bureau/reperage/inventaire").get_json()["clients"]))
        self.assertTrue(cl.get("/sites/test-bureau/reperage/recherche?q=p3").get_json()["resultats"])
        # appareils connus : validation, enregistrement, visibles sur le site de test et nommés dans les inventaires
        self.assertEqual(cl.put("/reperage/appareils", json={"mac": "zz", "nom": "x"}).status_code, 400)
        self.assertEqual(cl.put("/reperage/appareils", json={"mac": "FC-02-96-72-7E-89", "nom": "Téléphone test"}).get_json(), {"mac": "fc:02:96:72:7e:89", "nom": "Téléphone test", "genre": "telephone"})
        self.assertEqual([a["nom"] for a in cl.get("/reperage/appareils").get_json()["appareils"]], ["Téléphone test"])
        inv = cl.get("/sites/test-bureau/reperage/inventaire").get_json()
        tel = next(c for c in inv["clients"] if c["mac"] == "fc:02:96:72:7e:89"); self.assertEqual((tel["borne"], tel["connu"], tel["ssid"]), ("BORNE-TEST", "Téléphone test", "GROUPE_I"))
        self.assertEqual(cl.delete("/reperage/appareils/fc:02:96:72:7e:89").get_json()["supprime"], 1)
        os.environ["REPERAGE_APPAREILS"] = "02:00:00:00:00:99=Tablette env"
        try:
            self.assertEqual(cl.get("/reperage/appareils").get_json()["appareils"][0]["nom"], "Tablette env")
        finally:
            del os.environ["REPERAGE_APPAREILS"]


if __name__ == "__main__":
    unittest.main()
