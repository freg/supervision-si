# -*- coding: utf-8 -*-
import json, os, sys, tempfile, time, unittest
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "api"))
import flux as F  # noqa: E402


def res(hote, port, st, detail="", proto="tcp", grp="g"):
    return {"groupe": grp, "hote": hote, "ip": "1.2.3.4", "proto": proto, "port": port, "statut": st, "detail": detail}


class TestPur(unittest.TestCase):
    def test_ports_liste(self):
        self.assertEqual(F.ports("443,5228-5230"), [443, 5228, 5229, 5230])
        self.assertRaises(ValueError, F.ports, "1-9999")
        self.assertRaises(ValueError, F.ports, "x")
        lignes, err = F.lire_liste("# idruide\nidruide;Admin.Idruide.com;tcp;443\nhttps://api.idruide.com/v1 tcp 443,8443\nmdm.idruide.com:5223\nidruide;bad host;tcp;443\nx;y.com;icmp;1\n")
        self.assertEqual([(l["hote"], l["ports"]) for l in lignes], [("admin.idruide.com", "443"), ("api.idruide.com", "443,8443"), ("mdm.idruide.com", "5223")])
        self.assertEqual(len(err), 2)
        g, e = F.lire_liste(F.GOOGLE); self.assertFalse(e); self.assertGreater(len(g), 50)
        self.assertIn("time.google.com;udp;123", F.texte_liste(g))

    def test_resultats_ns_bilan_matrice(self):
        self.assertEqual(F.valider_resultats({})[1], "source requise")
        self.assertEqual(F.valider_resultats({"source": "x", "resultats": [{"statut": "zz"}]})[1], "aucun résultat exploitable")
        p, _ = F.valider_resultats({"source": "mini-PC", "ip_source": "172.16.20.129/24", "resultats": [
            res("mtalk.google.com", 5228, "OK"), res("play.google.com", 5228, "KO", "connexion refusee"), res("beacons.gvt3.com", 443, "KO", "nom non resolu (DNS)"),
            res("play.google.com", 443, "INSPECTE", "certificat Zyxel"), res("time.google.com", 123, "OK", proto="udp")]})
        self.assertEqual(p["ip_source"], "172.16.20.129")
        st = {(l["hote"], l["port"]): l["statut"] for l in p["lignes"]}
        self.assertEqual(st[("play.google.com", 5228)], "NS"); self.assertEqual(st[("beacons.gvt3.com", 443)], "KO")
        b = F.bilan(p["lignes"]); self.assertEqual((b["OK"], b["NS"], b["KO"], b["INSPECTE"], b["etat"]), (2, 1, 1, 1, "alerte"))
        m = F.matrice(p["lignes"]); self.assertEqual(m["colonnes"], ["tcp/443", "tcp/5228", "udp/123"])
        self.assertEqual(next(h for h in m["lignes"] if h["hote"] == "play.google.com")["cellules"], {"tcp/5228": "NS", "tcp/443": "INSPECTE"})
        self.assertIn("NS", F.csv_passage(p["lignes"]))

    def test_alertes(self):
        l1 = [res("a.com", 443, "KO"), res("b.com", 443, "OK"), res("c.com", 443, "INSPECTE")]
        n, r, m = F.diff_alertes({}, l1, "s", 100); self.assertEqual(sorted(a["hote"] for a in n), ["a.com", "c.com"]); self.assertEqual((r, m), ([], []))
        ouv = {a["cle"]: dict(a, id=i) for i, a in enumerate(n)}
        l2 = [res("a.com", 443, "OK"), res("c.com", 443, "INSPECTE"), res("d.com", 443, "KO")]
        n, r, m = F.diff_alertes(ouv, l2, "s", 200)
        self.assertEqual([a["hote"] for a in n], ["d.com"]); self.assertEqual([a["hote"] for a in r], ["a.com"]); self.assertEqual([a["hote"] for a in m], ["c.com"])
        self.assertEqual(r[0]["statut_fin"], "OK")
        n, r, m = F.diff_alertes(ouv, [res("b.com", 443, "OK")], "s", 300)       # cible absente du passage : alerte gardée telle quelle
        self.assertEqual((n, r, m), ([], [], []))

    def test_analyse_nebula(self):
        vmap = {"vlans": [{"vid": 20, "subnet": "172.16.20.0/24", "ssids": []}, {"vid": 30, "subnet": "172.16.30.0/23", "ssids": [{"name": "numeria"}]},
                          {"vid": 40, "subnet": "172.16.40.0/24", "ssids": [{"name": "Invites"}], "guest": True}]}
        clients = [{"fabricant": "Samsung Electronics", "ip": "172.16.30.12", "ssid": "numeria", "vlan": "30"},
                   {"fabricant": "Lenovo", "ip": "172.16.31.40", "ssid": "numeria"},
                   {"fabricant": "Google", "ip": "172.16.40.9", "ssid": "Invites", "vlan": 40},
                   {"fabricant": "Dell", "ip": "172.16.20.50", "vlan": 20}]
        passages = [{"source": "mini-PC", "ip_source": "172.16.20.129", "at": 10, "bilan": {"etat": "ok"}},
                    {"source": "mini-PC wifi", "ip_source": "172.16.31.63", "at": 20, "bilan": {"etat": "alerte"}}]
        a = F.analyse_nebula(vmap, clients, passages, [{"kind": "ssid_guest_not_isolated", "message": "SSID invité non isolé"}])
        v = {x["vlan"]: x for x in a["vlans"]}
        self.assertEqual((v[30]["terminaux"], v[30]["teste"], v[30]["etat"]), (2, True, "alerte"))
        self.assertEqual((v[40]["terminaux"], v[40]["teste"]), (1, False)); self.assertEqual((v[20]["terminaux"], v[20]["teste"]), (0, True))
        self.assertEqual((a["terminaux"], a["a_couvrir"], a["couverts"]), (3, 2, 1))
        txt = " ".join(c["texte"] for c in a["constats"])
        self.assertIn("VLAN 40 : 1 terminal", txt); self.assertIn("VLAN 30 : 2 terminal", txt); self.assertIn("réseau invité", txt); self.assertIn("SSID invité non isolé", txt)
        self.assertIn("security policies", txt)


class TestRoutes(unittest.TestCase):
    def test_routes(self):
        try:
            import flask  # noqa: F401
        except ImportError:
            self.skipTest("flask absent")
        import sqlite3
        from flask import Flask
        import flux_routes as R
        R.notify_client = None
        db = os.path.join(tempfile.mkdtemp(), "n.db")

        def conn():
            c = sqlite3.connect(db); c.row_factory = sqlite3.Row; return c
        app = Flask(__name__)
        R.register(app, {"conn": conn, "sites": lambda: [{"siteId": "campus", "name": "Campus"}],
                         "vlan_map": lambda sid: {"vlans": [{"vid": 20, "subnet": "172.16.20.0/24", "ssids": []}]}})
        cl = app.test_client()
        ls = cl.get("/flux/listes").get_json()["listes"]; self.assertEqual(ls[0]["id"], "google"); self.assertGreater(ls[0]["n_tests"], 80)
        self.assertEqual(cl.put("/flux/listes", json={"nom": "google", "texte": "a.com tcp 443"}).status_code, 400)
        r = cl.put("/flux/listes", json={"nom": "Idruide", "texte": "idruide;admin.idruide.com;tcp;443\nfaux\n"}).get_json()
        self.assertEqual((r["id"], r["cibles"], len(r["erreurs"])), ("idruide", 1, 1))
        self.assertIn("admin.idruide.com;tcp;443", cl.get("/flux/listes/idruide.txt").get_data(as_text=True))
        self.assertEqual(cl.delete("/flux/listes/google").status_code, 400)
        self.assertEqual(cl.post("/sites/../flux/resultats", json={}).status_code, 400)
        self.assertEqual(cl.post("/sites/bad%20id/flux/resultats", json={"source": "x"}).status_code, 400)
        body = {"source": "mini-PC", "ip_source": "172.16.20.129", "resultats": [res("a.com", 443, "KO", "nom non resolu (DNS)"), res("b.com", 443, "OK"), res("c.com", 5228, "KO")]}
        r = cl.post("/sites/campus/flux/resultats", json=body).get_json()
        self.assertEqual((r["bilan"]["KO"], r["alertes"]["nouvelles"]), (2, 2))
        body["resultats"][0]["statut"] = "OK"; time.sleep(1.01)
        r = cl.post("/sites/campus/flux/resultats", json=body).get_json(); self.assertEqual((r["alertes"]["retablies"], r["alertes"]["ouvertes"]), (1, 1))
        cl.post("/sites/bureau/flux/resultats", json={"source": "poste", "resultats": [res("a.com", 443, "OK")]})
        sites = {s["site_id"]: s for s in cl.get("/flux/sites").get_json()["sites"]}
        self.assertEqual((sites["campus"]["nebula"], sites["campus"]["alertes"], sites["bureau"]["nebula"]), (True, 1, False))
        f = cl.get("/sites/campus/flux").get_json()
        self.assertEqual((len(f["sources"]), len(f["historique"]), len(f["alertes_ouvertes"])), (1, 2, 1))
        self.assertEqual(f["sources"][0]["matrice"]["colonnes"], ["tcp/443", "tcp/5228"])
        pid = f["historique"][0]["id"]
        self.assertEqual(len(cl.get("/sites/campus/flux/passages/%d" % pid).get_json()["lignes"]), 3)
        self.assertIn("a.com", cl.get("/sites/campus/flux/passages/%d.csv" % pid).get_data(as_text=True))
        al = cl.get("/sites/campus/flux/alertes?etat=retablies").get_json()["alertes"]; self.assertEqual((len(al), al[0]["hote"]), (1, "a.com"))
        aid = f["alertes_ouvertes"][0]["id"]
        cl.post("/sites/campus/flux/alertes/%d/acquitter" % aid, json={"par": "freg", "note": "port non servi"})
        self.assertEqual(cl.get("/sites/campus/flux/alertes?etat=ouvertes").get_json()["alertes"][0]["acquitte_par"], "freg")
        a = cl.get("/sites/campus/flux/analyse").get_json()
        self.assertEqual(a["vlans"][0]["vlan"], 20); self.assertTrue(a["vlans"][0]["teste"])


if __name__ == "__main__":
    unittest.main()
