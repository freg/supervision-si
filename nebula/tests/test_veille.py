# -*- coding: utf-8 -*-
"""Veille de santé du réseau du campus (livraison #847) : réglages, créneaux à usage mixte, agents muets,
équipements Nebula, VLAN vus par la sonde « chemin de service », DHCP inattendu, liaison Internet, postes
présents / absents, synthèse et lignes d'alerte."""
import os
import sys
import unittest
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "api"))
import veille  # noqa: E402

LUNDI_10H = datetime(2026, 10, 19, 10, 0)
NOW = LUNDI_10H.timestamp()
ISO = lambda dt: datetime.utcfromtimestamp(NOW - dt).strftime("%Y-%m-%dT%H:%M:%SZ")

CFG = veille.normalize({
    "agents": ["pc-campus"], "heures": "lun-ven 08:00-18:00",
    "vlans": [{"id": 10, "nom": "Wi-Fi général", "connexion": "wifi-general", "dhcp_attendus": "192.0.2.1"},
              {"id": 51, "nom": "Partagé", "sous_reseau": "198.51.100.0/24", "creneaux": "1-5 08:00-12:30 externe; 1-5 13:30-18:00 interne"},
              {"id": 99, "nom": "Invités", "connexion": "wifi-invites"}],
    "postes": [{"nom": "serveur-labo", "mac": "02-00-5E-00-00-01", "attendu": "toujours"},
               {"nom": "borne-accueil", "ip": "198.51.100.20", "vlan": 51, "attendu": "heures"},
               {"nom": "portable", "mac": "02:00:5e:00:00:09", "attendu": "info"}]})[0]


def chemin(conn, ip, alerts=(), server="192.0.2.1", https_ok=True):
    return {"connection": conn, "ip": ip, "gateway": ip.rsplit(".", 1)[0] + ".1", "dhcp": {"server": server},
            "dns": [{"server": "192.0.2.53", "ok": True}], "https": {"ok": https_ok, "ms": 80, "error": None if https_ok else "délai"},
            "alerts": [{"severity": s, "code": c, "message": m} for s, c, m in alerts]}


def entrees(paths, last_seen=60, devices=None, clients=None, dhcp_vus=None, announcers=None):
    latest = {"plugin:path-probe": {"at": ISO(90), "ok": True, "data": {"paths": paths}},
              "plugin:broadcast-probe": {"at": ISO(120), "ok": True, "data": {"dhcp_servers": dhcp_vus or {"192.0.2.1": 3}, "announcers": announcers or []}}}
    return {"agents": [{"agent_id": "pc-campus", "hostname": "pc-campus", "last_seen_at": ISO(last_seen), "latest": latest}],
            "nebula": {"ok": True, "devices": devices if devices is not None else [
                {"dev_id": "g1", "name": "pare-feu", "type": "GW", "status": "online"},
                {"dev_id": "s1", "name": "coeur", "type": "SW", "status": "online"},
                {"dev_id": "a1", "name": "borne hall", "type": "AP", "status": "online"},
                {"dev_id": "a2", "name": "borne studio", "type": "AP", "status": "online"}]},
            "clients": clients if clients is not None else [{"mac": "02:00:5e:00:00:01", "status": "connected"}]}


def par_id(res):
    return {v["id"]: v for v in res["verifs"]}


class Reglages(unittest.TestCase):
    def test_creneaux(self):
        c = veille.parse_creneaux("lun-ven 08:00-12:30 externe ; sam 9:00-12:00")
        self.assertEqual(c[0], {"jours": [1, 2, 3, 4, 5], "debut": "08:00", "fin": "12:30", "usage": "externe"})
        self.assertEqual((c[1]["jours"], c[1]["debut"], c[1]["usage"]), ([6], "09:00", "interne"))
        self.assertEqual(veille.parse_creneaux("ven-lun 08:00-09:00")[0]["jours"], [1, 5, 6, 7])
        for mauvais in ("lundi matin", "1-5 12:00-08:00", "8 08:00-09:00"):
            with self.assertRaises(ValueError):
                veille.parse_creneaux(mauvais)
        cr = CFG["vlans"][1]["creneaux"]
        self.assertEqual(veille.usage_a(cr, LUNDI_10H), "externe")
        self.assertEqual(veille.usage_a(cr, datetime(2026, 10, 19, 15, 0)), "interne")
        self.assertEqual(veille.usage_a(cr, datetime(2026, 10, 18, 10, 0)), "interne")   # dimanche

    def test_normalize(self):
        cfg, errs = veille.normalize({"vlans": [{"id": "x"}, {"id": 51, "sous_reseau": "pas un réseau", "creneaux": "n'importe quoi"}],
                                      "postes": [{"nom": "sans adresse"}, {"mac": "0200.5e00.0001", "attendu": "bizarre"}], "heures": "??"})
        self.assertEqual(len(cfg["vlans"]), 1)
        self.assertEqual((cfg["vlans"][0]["sous_reseau"], cfg["vlans"][0]["creneaux"]), ("", []))
        self.assertEqual(cfg["postes"], [{"nom": "02:00:5e:00:00:01", "mac": "02:00:5e:00:00:01", "ip": "", "vlan": None, "attendu": "info"}])
        self.assertEqual(cfg["heures"], veille.DEFAUT["heures"])
        self.assertEqual(len(errs), 4)
        self.assertEqual(CFG["vlans"][0]["dhcp_attendus"], ["192.0.2.1"])
        self.assertEqual(CFG["postes"][0]["mac"], "02:00:5e:00:00:01")


class Evaluer(unittest.TestCase):
    def test_tout_va_bien(self):
        res = veille.evaluer(CFG, entrees([chemin("wifi-general", "192.0.2.40"), chemin("eth0", "198.51.100.5"), chemin("wifi-invites", "203.0.113.7")],
                                          announcers=[{"mac": "02:00:5e:00:00:07", "ips": ["198.51.100.20"]}]), NOW, LUNDI_10H)
        v = par_id(res)
        self.assertEqual(res["etat"], "ok", res["resume"])
        self.assertEqual(v["vlans:51"]["usage"], "externe")                       # créneau de l'organisme extérieur
        self.assertEqual(v["vlans:51"]["source"], "agent:pc-campus")              # rapproché par sous-réseau
        self.assertEqual(v["vlans:10"]["detail"], "DHCP ✓ · passerelle ✓ · DNS ✓ · Internet ✓")
        self.assertEqual(v["internet:liaison"]["statut"], "ok")
        self.assertEqual(v["postes:198.51.100.20"]["detail"], "présent (vu par annonces (pc-campus))")
        self.assertEqual(v["postes:02:00:5e:00:00:09"]["statut"], "inconnu")      # absent, simple information
        self.assertEqual(veille.lignes_alerte(res, "s", "Site"), [])

    def test_pannes(self):
        paths = [chemin("wifi-general", "192.0.2.40", alerts=[("critical", "dns-all-down", "wifi-general : aucun des DNS distribués ne répond")], server="192.0.2.66"),
                 chemin("eth0", "198.51.100.5", alerts=[("critical", "https-failed", "eth0 : HTTPS en échec (délai)")], https_ok=False)]
        devices = [{"dev_id": "g1", "name": "pare-feu", "type": "GW", "status": "online"},
                   {"dev_id": "a1", "name": "borne hall", "type": "AP", "status": "offline", "since": NOW - 1800},
                   {"dev_id": "a2", "name": "borne studio", "type": "AP", "status": "online"}]
        res = veille.evaluer(CFG, entrees(paths, devices=devices, clients=[], dhcp_vus={"192.0.2.1": 2, "192.0.2.66": 1}), NOW, LUNDI_10H)
        v = par_id(res)
        self.assertEqual(res["etat"], "panne")
        self.assertEqual(v["vlans:10"]["statut"], "ko")
        self.assertIn("aucun des DNS", v["vlans:10"]["detail"])
        self.assertEqual(v["vlans:10-dhcp"]["detail"], "bail reçu de 192.0.2.66, attendu 192.0.2.1")
        self.assertIn("192.0.2.66", v["vlans:dhcp-inattendu"]["detail"])
        self.assertEqual(v["vlans:99"]["statut"], "inconnu")                      # pas de sonde dans le VLAN invités
        self.assertEqual(v["internet:liaison"]["statut"], "doute")                # un chemin sur deux
        self.assertEqual((v["equipements:dev-a1"]["statut"], v["equipements:dev-a1"]["detail"]), ("ko", "hors ligne depuis 30 min"))
        self.assertEqual(v["equipements:bornes"]["detail"], "1/2 en ligne")
        self.assertEqual(v["postes:02:00:5e:00:00:01"]["statut"], "ko")           # serveur attendu toujours, absent
        self.assertEqual(v["postes:198.51.100.20"]["statut"], "ko")               # attendu aux heures ouvrées
        lignes = veille.lignes_alerte(res, "s", "Site")
        self.assertEqual({l["kind"] for l in lignes if l["id"] == "veille:vlans:51"}, {"externe"})
        self.assertTrue(all(l["id"].startswith("veille:") for l in lignes))

    def test_aveugle(self):
        res = veille.evaluer(CFG, entrees([chemin("wifi-general", "192.0.2.40")], last_seen=3600), NOW, LUNDI_10H)
        v = par_id(res)
        self.assertEqual((v["agents:pc-campus"]["statut"], v["agents:pc-campus"]["detail"]), ("ko", "muet depuis 60 min"))
        self.assertEqual(res["etat"], "panne")
        vieux = entrees([chemin("wifi-general", "192.0.2.40")])
        vieux["agents"][0]["latest"]["plugin:path-probe"]["at"] = ISO(3600)
        v = par_id(veille.evaluer(CFG, vieux, NOW, LUNDI_10H))
        self.assertEqual(v["vlans:10"]["statut"], "inconnu")
        self.assertEqual(v["internet:liaison"]["statut"], "inconnu")
        rien = veille.evaluer(veille.normalize({})[0], {"agents": [], "nebula": {"ok": False, "erreur": "clé absente"}, "clients": None}, NOW, LUNDI_10H)
        self.assertEqual(rien["etat"], "inconnu")


class Routes(unittest.TestCase):
    """Routes et passage d'alerte sur une application Flask de test (hooks et notify-api simulés)."""
    def test_routes_et_alertes(self):
        import sqlite3
        import tempfile
        from flask import Flask
        import report_routes as rr
        import veille_routes as vr
        db = os.path.join(tempfile.mkdtemp(), "t.db")

        def conn():
            c = sqlite3.connect(db)
            c.row_factory = sqlite3.Row
            return c

        envois = []

        class Notif:
            def notify(self, action, subject, body="", **kw):
                envois.append((action, subject))
                return {"status": "queued", "recipients": 1, "reason": ""}

            def register_actions(self, a):
                pass
        rr.notify_client = Notif()
        app = Flask("t")
        sites = lambda: [{"siteId": "s1", "name": "Site Alpha"}]
        rr.register(app, {"conn": conn, "sites": sites, "anomalies": lambda sid, refresh=False: ([], [], {}), "manage": lambda b: (True, None),
                          "configured": lambda: True, "lock_dir": tempfile.mkdtemp()}, start_loop=False)
        etat = {"devs": [{"dev_id": "g1", "name": "pare-feu", "type": "GW", "status": "offline"}]}
        vr.register(app, {"sites": sites, "board": lambda sid: etat["devs"], "clients": lambda sid: [], "manage": lambda b: (b.get("user") == "admin", "droit requis"),
                          "lock_dir": tempfile.mkdtemp()}, start_loop=False)
        vr._agents = lambda cfg: ([], None)
        c = app.test_client()
        self.assertEqual(c.put("/veille/reglages", json={"user": "x", "reglages": {}}).status_code, 403)
        r = c.put("/veille/reglages", json={"user": "admin", "reglages": {"vlans": [{"id": 51, "creneaux": "lundi matin"}]}})
        self.assertEqual(r.status_code, 400)
        self.assertIn("créneau illisible", r.get_json()["error"])
        r = c.put("/veille/reglages", json={"user": "admin", "reglages": {"alerte": {"delay_minutes": 0}}})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.get_json()["resultat"]["etat"], "panne")
        r = c.get("/veille/etat")
        self.assertEqual(r.status_code, 503)
        self.assertTrue(r.get_data(as_text=True).startswith("PANNE "))
        vr.passage()
        self.assertEqual([a for a, _s in envois], ["nebula.veille-campus"])
        vr.passage()
        self.assertEqual(len(envois), 1)                                  # une fois, puis rappel après repeat_hours
        etat["devs"] = [{"dev_id": "g1", "name": "pare-feu", "type": "GW", "status": "online"}]
        vr.passage()
        self.assertEqual(envois[-1][0], "nebula.veille-campus-retabli")
        vr._cache["at"] = 0
        self.assertEqual(c.get("/veille/etat").status_code, 200)
        os.environ["NEBULA_VEILLE_TOKEN"] = "secret"
        try:
            self.assertEqual(c.get("/veille/etat").status_code, 401)
            self.assertEqual(c.get("/veille/etat?jeton=secret").status_code, 200)
        finally:
            del os.environ["NEBULA_VEILLE_TOKEN"]
        d = c.get("/veille").get_json()
        self.assertEqual((d["site"], len(d["retablies_24h"])), ("Site Alpha", 1))


if __name__ == "__main__":
    unittest.main()
