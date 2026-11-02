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

    def test_radar(self):
        self.assertEqual((R.canal_depuis_frequence(2412), R.canal_depuis_frequence(2484), R.canal_depuis_frequence(5180), R.canal_depuis_frequence(5955), R.canal_depuis_frequence("x")), (1, 14, 36, 1, None))
        self.assertEqual((R.bande_depuis_frequence(2437), R.bande_depuis_frequence(5500), R.bande_depuis_frequence(6100)), ("band24", "band5", "band6"))
        self.assertEqual(R.distance_estimee(-40, 2437), 1.0); self.assertEqual(R.distance_estimee(-45, 5180), 1.0); self.assertGreater(R.distance_estimee(-80, 2437), 20); self.assertIsNone(R.distance_estimee("x"))
        # sortie de termux-wifi-scaninfo acceptée telle quelle
        b, err = R.valider_balayage({"source": " Tél ", "scan": [{"bssid": "AA:BB:CC:00:00:01", "ssid": "GROUPE_I", "rssi": -52, "frequency_mhz": 5180},
                                                                     {"bssid": "aa:bb:cc:00:00:02", "rssi": "-71", "frequency_mhz": 2437}, {"bssid": "zz", "rssi": -1}]}, now=100)
        self.assertIsNone(err); self.assertEqual((b["source"], b["at"], b["x"]), ("Tél", 100.0, None))
        self.assertEqual([x["bssid"] for x in b["bornes"]], ["aa:bb:cc:00:00:01", "aa:bb:cc:00:00:02"]); self.assertEqual((b["bornes"][0]["canal"], b["bornes"][0]["bande"]), (36, "band5"))
        self.assertEqual(R.valider_balayage({"scan": [{"bssid": "a"}]})[1], "source requise (nom ou MAC de l'appareil qui balaie)")
        self.assertEqual(R.valider_balayage({"source": "s", "scan": [{"bssid": "zz", "rssi": 1}]})[1], "aucune borne exploitable (bssid + rssi requis)")
        self.assertIn("scan_id;source", R.radar_csv([{"scan_id": "x", "source": "s;t", "rssi": -50}]))

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
        # radar : dépôt d'un balayage, dernier par source, position, historique, CSV
        r = cl.post("/sites/s1/reperage/radar", json={"source": "Tél", "scan": [{"bssid": "aa:bb:cc:00:00:01", "ssid": "GROUPE_I", "rssi": -52, "frequency_mhz": 5180}, {"bssid": "aa:bb:cc:00:00:02", "rssi": -71, "frequency_mhz": 2437}]})
        self.assertEqual(r.status_code, 201); self.assertEqual(r.get_json()["bornes"], 2); self.assertEqual(r.get_json()["plus_forte"]["ssid"], "GROUPE_I")
        self.assertEqual(cl.post("/sites/s1/reperage/radar", json={"source": "Tél"}).status_code, 400)
        self.assertEqual(cl.post("/sites/s1/reperage/radar/position", json={"source": "Tél", "x": 0.3, "y": 0.4}).status_code, 201)
        g = cl.get("/sites/s1/reperage/radar").get_json(); self.assertEqual((g["scans"], g["bssids"], g["positions"]), (1, 2, 1)); self.assertEqual(g["derniers"]["Tél"]["bornes"][0]["rssi"], -52)
        h = cl.get("/sites/s1/reperage/radar?depuis=0").get_json(); self.assertEqual(len(h["lignes"]), 2); self.assertEqual(len(h["positions"]), 1)
        self.assertIn("GROUPE_I", cl.get("/sites/s1/reperage/radar.csv").get_data(as_text=True))
        os.environ["REPERAGE_APPAREILS"] = "02:00:00:00:00:99=Tablette env"
        try:
            self.assertEqual(cl.get("/reperage/appareils").get_json()["appareils"][0]["nom"], "Tablette env")
        finally:
            del os.environ["REPERAGE_APPAREILS"]


if __name__ == "__main__":
    unittest.main()


class TestSonde(unittest.TestCase):
    def test_pur(self):
        self.assertEqual([R.numero_port(v) for v in ("12", "ge12", "port 12", "1/12", 7, None, "x")], [12, 12, 12, 12, 7, None, None])
        self.assertEqual(R.valider_sonde({})[1], "source requise (nom de la sonde)")
        r, _ = R.valider_sonde({"source": "pi3", "mac": "AA:BB:CC:00:00:09", "lldp": {"chassis": "GS2220-50HP-1", "port": "12", "port_descr": "Studio", "vlan": "20"}})
        self.assertEqual((r["commutateur"], r["port"], r["vlan"], r["lldp"], r["mode"]), ("GS2220-50HP-1", 12, 20, True, "prise"))
        inv = {"clients": [{"mac": "aa:bb:cc:00:00:09", "type": "filaire", "commutateur": "GS2220-50HP-1", "port": 12}]}
        prises = [{"prise": "B-12", "commutateur": "gs2220-50hp-1", "port": 12}]
        x = R.rapprocher_sonde(r, inv, prises); self.assertTrue(x["confirme"]); self.assertEqual(x["prise_connue"]["prise"], "B-12")
        inv["clients"][0]["port"] = 13; self.assertFalse(R.rapprocher_sonde(r, inv)["confirme"])
        self.assertIsNone(R.rapprocher_sonde(r, {"clients": []})["confirme"])
        r2, _ = R.valider_sonde({"source": "pi3", "mac": "aa:bb:cc:00:00:09", "mode": "brassage"})     # sans LLDP : Nebula fait foi
        y = R.rapprocher_sonde(r2, inv); self.assertEqual((y["commutateur"], y["port"], y["confirme"]), ("GS2220-50HP-1", 13, True))
        p = R.fusion_prise_sonde({"prise": "B-12", "local": "Amphi", "port": 3}, x, {"prise": "B-12"}); self.assertEqual((p["port"], p["local"]), (12, "Amphi"))
        p = R.fusion_prise_sonde(None, y, {"prise": "B-13", "panneau": "baie 1 A-07"}); self.assertEqual((p["panneau"], p["port"]), ("baie 1 A-07", 13))

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
        vu = {"n": 0}

        class Cl:
            def sw_clients(self, sid, period="1d"):
                vu["n"] += 1
                return {"data": SW + ([{"macAddress": "AA:BB:CC:00:00:09", "connectedTo": "dev-sw1", "connectedPort": 12, "vlan": 20}] if vu["n"] > 1 else [])}
            def ap_clients_v2(self, sid, period="1d"): return AP
            def get_site_clients(self, sid, period="2h", features=None): return SC
        app = Flask(__name__); RR._cache.clear()
        RR.register(app, {"conn": conn, "client": lambda: Cl(), "db_path": db, "devices": lambda sid: DEV})
        cl = app.test_client()
        r = cl.post("/sites/s1/reperage/sonde", json={"source": "pi3", "mac": "AA:BB:CC:00:00:09", "lldp": {"chassis": "GS2220-50HP-1", "port": "12"}}).get_json()
        self.assertEqual((r["commutateur"], r["port"], r["lldp"], r["ack"]), ("GS2220-50HP-1", 12, True, False)); rid = r["id"]
        self.assertIsNone(r["confirme"])                                           # Nebula n'a pas encore vu la sonde (1re lecture)
        r = cl.post("/sites/s1/reperage/sonde?refresh=1", json={"id": rid, "source": "pi3", "mac": "AA:BB:CC:00:00:09", "lldp": {"chassis": "GS2220-50HP-1", "port": "12"}}).get_json()
        self.assertEqual(r["id"], rid); self.assertTrue(r["confirme"])            # relecture forcée : confirmé, même relevé mis à jour
        e = cl.get("/sites/s1/reperage/sonde/etat?source=pi3").get_json()["derniere"]; self.assertEqual((e["id"], e["ack"], e["confirme"]), (rid, False, True))
        self.assertEqual(cl.get("/sites/s1/reperage/sonde").get_json()["en_attente"], [rid])
        self.assertEqual(cl.post("/sites/s1/reperage/sonde/%d/valider" % rid, json={}).status_code, 400)     # prise requise
        v = cl.post("/sites/s1/reperage/sonde/%d/valider" % rid, json={"prise": "B-12", "local": "Studio"}).get_json(); self.assertEqual(v["prise"], "B-12")
        self.assertTrue(cl.get("/sites/s1/reperage/sonde/etat?source=pi3").get_json()["derniere"]["ack"])
        ps = cl.get("/sites/s1/reperage/prises").get_json()["prises"]; self.assertEqual((ps[0]["prise"], ps[0]["commutateur"], ps[0]["port"], ps[0]["local"]), ("B-12", "GS2220-50HP-1", 12, "Studio"))
        # brassage : même prise, on ajoute la position en baie ; le relevé acquitté n'est plus mis à jour par un POST avec son id
        r = cl.post("/sites/s1/reperage/sonde", json={"id": rid, "source": "pi3", "mode": "brassage", "mac": "AA:BB:CC:00:00:09", "lldp": {"chassis": "GS2220-50HP-1", "port": "12"}}).get_json()
        self.assertNotEqual(r["id"], rid); self.assertEqual(r["prise_connue"]["prise"], "B-12")
        cl.post("/sites/s1/reperage/sonde/%d/valider" % r["id"], json={"prise": "B-12", "panneau": "baie 1 A-07"})
        ps = cl.get("/sites/s1/reperage/prises").get_json()["prises"]; self.assertEqual((len(ps), ps[0]["panneau"], ps[0]["local"]), (1, "baie 1 A-07", "Studio"))
        r = cl.post("/sites/s1/reperage/sonde", json={"source": "pi3", "mac": "AA:BB:CC:00:00:99"}).get_json()
        self.assertEqual(cl.post("/sites/s1/reperage/sonde/%d/valider" % r["id"], json={"ignorer": True}).get_json()["prise"], None)
        self.assertEqual(cl.delete("/sites/s1/reperage/sonde/%d" % r["id"]).get_json()["supprime"], 1)
        self.assertEqual(cl.get("/sites/s1/reperage/sonde").get_json()["en_attente"], [])
