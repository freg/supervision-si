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
        # #967 : versions des listes -- modification puis suppression gardent l'état précédent, restaurable
        cl.put("/flux/listes", json={"nom": "Idruide", "texte": "idruide;admin.idruide.com;tcp;443"})   # inchangée : pas de version
        self.assertEqual(cl.get("/flux/listes/versions?id=idruide").get_json()["versions"], [])
        cl.put("/flux/listes", json={"id": "idruide", "nom": "Idruide", "texte": "idruide;maestro.v1.idruide.eu;tcp;443"})
        cl.delete("/flux/listes/idruide")
        v = cl.get("/flux/listes/versions?id=idruide").get_json()["versions"]
        self.assertEqual([x["motif"] for x in v], ["suppression", "modification"])
        self.assertIn("admin.idruide.com", v[1]["texte"])
        self.assertEqual(cl.post("/flux/listes/versions/%d/restaurer" % v[1]["vid"]).get_json()["id"], "idruide")
        self.assertIn("admin.idruide.com", cl.get("/flux/listes/idruide.txt").get_data(as_text=True))
        self.assertEqual(cl.post("/flux/listes/versions/9999/restaurer").status_code, 404)
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


class TestSI(unittest.TestCase):
    def test_ferme_cert_sites(self):
        lignes, err = F.lire_liste("lan;extranet.exemple.fr;tcp;443\nlan;extranet.exemple.fr;tcp;22,3306;ferme\nx.fr tcp 3389\n")
        self.assertEqual([l["attendu"] for l in lignes], ["ouvert", "ferme", "ouvert"]); self.assertIn("22,3306;ferme", F.texte_liste(lignes))
        p, _ = F.valider_resultats({"source": "agent-ovh", "resultats": [
            res("e.fr", 22, "OUVERT"), dict(res("e.fr", 3306, "OK", "ferme comme attendu"), attendu="ferme"), res("e.fr", 443, "CERT", "expire dans 5 j"),
            dict(res("f.fr", 22, "KO"), attendu="ferme")]})
        b = F.bilan(p["lignes"]); self.assertEqual((b["OUVERT"], b["CERT"], b["etat"]), (1, 1, "alerte"))
        self.assertEqual([l["statut"] for l in p["lignes"] if l["hote"] == "f.fr"], ["KO"])      # attendu fermé : jamais reclassé NS
        n, _, _ = F.diff_alertes({}, p["lignes"], "agent-ovh", 1); self.assertEqual(sorted(a["statut"] for a in n), ["CERT", "KO", "OUVERT"])

    def test_route_sites(self):
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
        app = Flask(__name__); R.register(app, {"conn": conn, "sites": lambda: []})
        cl = app.test_client()
        self.assertEqual(cl.put("/flux/sites", json={}).status_code, 400)
        self.assertEqual(cl.put("/flux/sites", json={"nom": "SI Optline", "description": "agent OVH + agent LAN"}).get_json()["site_id"], "si-optline")
        s = cl.get("/flux/sites").get_json()["sites"]; self.assertEqual((s[0]["site_id"], s[0]["nom"], s[0]["declare"]), ("si-optline", "SI Optline", True))
        cl.delete("/flux/sites/si-optline"); self.assertEqual(cl.get("/flux/sites").get_json()["sites"], [])


class Test964(unittest.TestCase):
    def test_pur(self):
        L = [res("a.com", 443, "KO", "DNS"), res("b.com", 5228, "NS"), res("c.com", 443, "OK")]
        li = F.appliquer_ignores(L, {F.cle_ignore("A.com", "tcp", 443)})
        self.assertEqual([l["ignore"] for l in li], [True, False, False])
        b = F.bilan_ignores(li); self.assertEqual((b["KO"], b["IGN"], b["NS"], b["etat"]), (0, 1, 1, "ok"))
        n, r, m = F.diff_alertes({}, F.alertants(li), "s", 1); self.assertEqual(n, [])
        sujet, texte, k = F.recap([{"site_id": "s1", "nom": "Campus", "sources": [{"source": "mini", "at": 0, "lignes": li}]}], avec_ns=True)
        self.assertEqual(k, 1); self.assertIn("b.com tcp/5228", texte); self.assertNotIn("a.com", texte); self.assertIn("1 flux", sujet)
        self.assertEqual(F.recap([{"site_id": "s1", "sources": [{"source": "m", "at": 0, "lignes": li}]}], avec_ns=False)[2], 0)
        nat = [{"kind": "redirection", "name": "rdp", "enabled": True, "public_ip": "1.2.3.4", "private_ip": "10.0.0.5", "ports": [3389], "explicit_ports": [3389], "all_ports": False,
                "any_remote": True, "remote": [], "protocol": "TCP"},
               {"kind": "1:1", "name": "vieux", "enabled": True, "private_ip": "10.0.0.9", "ports": [], "all_ports": True, "any_remote": False, "remote": ["5.6.7.8"]},
               {"kind": "redirection", "name": "off", "enabled": False, "private_ip": "10.0.0.7", "ports": [80], "all_ports": False, "any_remote": True, "remote": []}]
        lignes, sugg = F.synthese_nat(nat, [{"ip": "10.0.0.5", "last_seen": 1000}, {"ip": "10.0.0.7", "last_seen": 1000}], 1000 + 40 * 86400)
        self.assertEqual(lignes[0]["sensibles"], ["3389 (Bureau à distance (RDP))"]); self.assertTrue(lignes[0]["cible_inactive"])
        t = " ".join(x["texte"] for x in sugg)
        self.assertIn("jamais été vue", t); self.assertIn("désactivée", t); self.assertIn("sans restriction d'origine", t); self.assertIn("30 jours", t)
        zs = F.zones({"vlans": [{"vid": 22, "subnet": "172.16.22.0/24", "gateway_interface": None, "ssids": [{"name": "X"}], "clients": 3}]})
        self.assertEqual(zs[0]["zone"], "sans interface passerelle"); self.assertEqual(len(F.suggestions_zones(zs)), 1)
        j = F.resume_journal([{"message": "Blocked 10.0.0.1:443 -> 8.8.8.8", "timestamp": 1700000000000}, {"message": "Blocked 10.0.0.2:443 -> 8.8.8.8"}, {"msg": "VPN up"}, "x"])
        self.assertEqual((j[0]["message"], j[0]["n"]), ("Blocked <ip> -> <ip>", 2)); self.assertEqual(j[0]["dernier"], 1700000000.0)
        self.assertIn("+allow 443", F.diff_regles("deny 22", "deny 22\nallow 443"))

    def test_routes(self):
        try:
            import flask  # noqa: F401
        except ImportError:
            self.skipTest("flask absent")
        import sqlite3
        from flask import Flask
        import flux_routes as R

        class N:
            envois = []
            @staticmethod
            def notify(*a, **k): N.envois.append((a, k)); return {"status": "sent", "recipients": 1}
            @staticmethod
            def register_actions(a): pass
        R.notify_client = N
        db = os.path.join(tempfile.mkdtemp(), "n.db")

        def conn():
            c = sqlite3.connect(db); c.row_factory = sqlite3.Row; return c

        class Cl:
            def gw_system_status(self, sid, gw): return {"sessions": 1234}
            def gw_event_logs(self, sid): return {"data": [{"message": "Blocked 1.2.3.4"}]}
        vmap = {"vlans": [{"vid": 20, "subnet": "172.16.20.0/24", "gateway_interface": "lan1", "ssids": []}],
                "nat": [{"kind": "redirection", "name": "web", "enabled": True, "private_ip": "172.16.20.5", "ports": [443], "explicit_ports": [443], "all_ports": False, "any_remote": True, "remote": []}],
                "anomalies_detail": [{"kind": "nat_to_guest", "message": "pub invité"}, {"kind": "vlan_x", "message": "autre"}]}
        app = Flask(__name__)
        R.register(app, {"conn": conn, "sites": lambda: [{"siteId": "campus", "name": "Campus"}], "vlan_map": lambda s: vmap, "client": lambda: Cl(), "gw_of": lambda s: "gw1"})
        cl = app.test_client()
        cl.post("/sites/campus/flux/resultats", json={"source": "m", "resultats": [res("a.com", 443, "KO", "nom non resolu (DNS)"), res("b.com", 5228, "KO")]})
        self.assertEqual(len(cl.get("/sites/campus/flux").get_json()["alertes_ouvertes"]), 2)
        self.assertEqual(cl.put("/sites/campus/flux/ignores", json={"hote": "a.com"}).status_code, 400)
        self.assertEqual(cl.put("/sites/campus/flux/ignores", json={"hote": "a.com", "proto": "tcp", "port": 443, "par": "freg"}).get_json()["ignores"], 1)
        f = cl.get("/sites/campus/flux").get_json()
        self.assertEqual(len(f["alertes_ouvertes"]), 1); self.assertEqual(f["sources"][0]["bilan"]["IGN"], 1)
        self.assertEqual(next(l for l in f["sources"][0]["matrice"]["lignes"] if l["hote"] == "a.com")["cellules"]["tcp/443"], "IGN")
        pid = f["historique"][0]["id"]
        p = cl.get("/sites/campus/flux/passages/%d" % pid).get_json(); self.assertEqual([l["ignore"] for l in p["lignes"]], [True, False])
        time.sleep(1.01)
        r = cl.post("/sites/campus/flux/resultats", json={"source": "m", "resultats": [res("a.com", 443, "KO", "nom non resolu (DNS)"), res("b.com", 5228, "KO")]}).get_json()
        self.assertEqual((r["bilan"]["KO"], r["bilan"]["IGN"], r["alertes"]["nouvelles"]), (1, 1, 0))
        cl.delete("/sites/campus/flux/ignores", json={"hote": "a.com", "proto": "tcp", "port": 443}); self.assertEqual(cl.get("/sites/campus/flux/ignores").get_json()["ignores"], [])
        reg = cl.put("/flux/reglages", json={"heure": 30, "ns": False, "destinataires": "a@b.fr"}).get_json()["recap"]; self.assertEqual((reg["heure"], reg["ns"]), (23, False))
        self.assertIn("b.com", cl.get("/flux/recap").get_json()["texte"])
        e = cl.post("/flux/recap/envoyer").get_json(); self.assertEqual(e["resultat"]["status"], "sent")
        self.assertEqual(N.envois[-1][1]["to"], ["a@b.fr"]); self.assertEqual(N.envois[-1][0][0], "flux.recapitulatif")
        pf = cl.get("/sites/campus/flux/parefeu").get_json()
        self.assertEqual((pf["systeme"], pf["journal"]["total"], pf["passerelle"]), ({"sessions": 1234}, 1, "gw1"))
        self.assertEqual([c["texte"] for c in pf["constats"]], ["pub invité"]); self.assertEqual(pf["nat"][0]["ip_privee"], "172.16.20.5")
        self.assertEqual(cl.put("/sites/campus/flux/parefeu/regles", json={}).status_code, 400)
        cl.put("/sites/campus/flux/parefeu/regles", json={"texte": "1 LAN1>WAN allow any", "par": "freg"}); time.sleep(1.01)
        self.assertTrue(cl.put("/sites/campus/flux/parefeu/regles", json={"texte": "1 LAN1>WAN allow any"}).get_json()["inchange"])
        d = cl.put("/sites/campus/flux/parefeu/regles", json={"texte": "1 LAN1>WAN allow any\n2 GUEST>LAN deny"}).get_json(); self.assertIn("+2 GUEST>LAN deny", d["diff"])
        pf = cl.get("/sites/campus/flux/parefeu").get_json(); self.assertEqual(pf["versions"], 2); self.assertIn("+2 GUEST", pf["regles"]["diff"])
        R.notify_client = None
