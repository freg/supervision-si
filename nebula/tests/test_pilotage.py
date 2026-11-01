# -*- coding: utf-8 -*-
"""#855 : pilotage du réseau du campus -- logique pure (relevé, boucles, scénarios, bancs, synthèse)."""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "api"))
import pilotage as P  # noqa: E402

T0 = 1_800_000_000


def iso(t):
    import time
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t))


def hist(metrique, cible, valeurs, pas=60, t0=T0):
    return [{"at": t0 + i * pas, "valeurs": {metrique: {cible: v}}} for i, v in enumerate(valeurs)]


class Instantane(unittest.TestCase):
    def test_sources(self):
        charge = {"bornes": [{"nom": "B1", "simultanes_max": 30, "clients": 41, "debit_mbps": 12.5}, {"dev_id": "x", "clients": None}],
                  "ssids": [{"ssid": "Campus", "clients": 40}], "commutateurs": [{"nom": "Coeur", "debit_mbps": 300}, {"nom": "K", "debit_mbps": 1, "erreur": "x"}],
                  "total": {"clients_wifi": 41, "wifi_debit_mbps": 12.5}}
        veille = {"etat": "degrade", "verifs": [{"statut": "ok"}, {"statut": "ko"}, {"statut": "doute"}]}
        t = T0
        sondes = [{"agent_id": "a1", "task": "wifi_link", "at": iso(t - 30), "ok": True, "data": {"signal_dbm": -65}},
                  {"agent_id": "a1", "task": "ping:192.0.2.1", "at": iso(t - 30), "ok": True, "data": {"rtt_avg_ms": 12, "loss_pct": 0}},
                  {"agent_id": "a1", "task": "iperf3:192.0.2.5:5202/udp", "at": iso(t - 30), "ok": True, "data": {"udp": True, "jitter_ms": 4.2, "loss_pct": 0.5}},
                  {"agent_id": "a2", "task": "iperf3:192.0.2.5", "at": iso(t - 30), "ok": True, "data": {"received_mbps": 0, "sent_mbps": 40}},
                  {"agent_id": "a2", "task": "http:https://exemple.fr/", "at": iso(t - 30), "ok": True, "data": {"time_ms": 350}},
                  {"agent_id": "a2", "task": "ping:192.0.2.1", "at": iso(t - 2000), "ok": True, "data": {"rtt_avg_ms": 999}},   # trop vieille
                  {"agent_id": "a2", "task": "wifi_link", "at": iso(t - 10), "ok": False, "data": {"signal_dbm": -90}}]           # en échec
        v = P.instantane(charge, veille, sondes, {"a1": "Sonde A"}, maintenant=t)["valeurs"]
        self.assertEqual(v["borne.simultanes"], {"B1": 30})
        self.assertEqual(v["commutateur.debit_mbps"], {"Coeur": 300})
        self.assertEqual((v["veille.niveau"]["campus"], v["veille.anomalies"]["campus"]), (1, 2))
        self.assertEqual(v["sonde.rssi_dbm"], {"Sonde A": -65})
        self.assertEqual(v["sonde.gigue_ms"], {"Sonde A": 4.2})
        self.assertEqual(v["sonde.perte_udp_pct"], {"Sonde A": 0.5})
        self.assertEqual(v["sonde.debit_mbps"], {"a2": 40})   # reçu nul -> envoyé
        self.assertEqual(v["sonde.http_ms"], {"a2": 350})
        self.assertNotIn("a2", v["sonde.rtt_ms"])

    def test_vide(self):
        self.assertEqual(P.instantane(maintenant=T0), {"at": T0, "valeurs": {}})

    def test_historique_et_serie(self):
        h = P.ajouter_historique([], {"at": 1, "valeurs": {"m": {"c": 1}}})
        h = P.ajouter_historique(h, {"at": 1, "valeurs": {"m": {"c": 2}}})
        h = P.ajouter_historique(h, {"at": 2, "valeurs": {}}, maxi=2)
        self.assertEqual(len(h), 2)
        self.assertEqual(P.serie(h, "m", "c"), [[1, 2]])


class Boucles(unittest.TestCase):
    COND = {"metrique": "borne.simultanes", "cible": "*", "op": ">", "seuil": 25, "duree_min": 5}

    def test_validation(self):
        self.assertIsNotNone(P.valider_condition({"metrique": "nope"})[1])
        self.assertIsNotNone(P.valider_condition(dict(self.COND, op="~"))[1])
        self.assertIsNotNone(P.valider_condition(dict(self.COND, seuil="x"))[1])
        b, err = P.valider_boucle({"nom": "B", "condition": self.COND, "actions": [{"type": "notifier"}], "delai_min": 1})
        self.assertIsNone(err)
        self.assertEqual((b["mode"], b["delai_min"], b["actif"]), ("conseil", 5, False))
        self.assertIn("outil", P.valider_boucle({"nom": "B", "condition": self.COND, "actions": [{"type": "recommander", "outil": "x"}]})[1])
        self.assertIn("banc", P.valider_boucle({"nom": "B", "condition": self.COND, "actions": [{"type": "banc", "plan": "cast"}]})[1])
        self.assertIsNone(P.valider_boucle({"nom": "B", "condition": self.COND, "actions": [{"type": "banc", "plan": "cast"}]}, {"cast"})[1])
        self.assertIsNotNone(P.valider_boucle({"nom": "B", "condition": self.COND, "actions": []})[1])
        self.assertIsNotNone(P.valider_boucle({"condition": self.COND, "actions": [{"type": "notifier"}]})[1])

    def test_violations_fenetre(self):
        cond = P.valider_condition(self.COND)[0]
        self.assertEqual(P.violations(cond, hist("borne.simultanes", "B1", [30, 30, 30])), [])        # 2 min seulement
        h = hist("borne.simultanes", "B1", [30] * 7)
        self.assertEqual(P.violations(cond, h), [{"cible": "B1", "valeur": 30}])
        h = hist("borne.simultanes", "B1", [30, 30, 20, 30, 30, 30, 30])                              # creux dans la fenêtre
        self.assertEqual(P.violations(cond, h), [])
        self.assertEqual(P.violations(dict(cond, cible="B2"), hist("borne.simultanes", "B1", [30] * 7)), [])
        self.assertEqual(P.violations(dict(cond, duree_min=0), hist("borne.simultanes", "B1", [10, 30])), [{"cible": "B1", "valeur": 30}])
        self.assertEqual(P.violations(cond, []), [])
        # valeur absente d'un relevé de la fenêtre : pas de violation
        h = hist("borne.simultanes", "B1", [30] * 7)
        h[3]["valeurs"] = {}
        self.assertEqual(P.violations(cond, h), [])

    def test_decider(self):
        b = {"actif": True, "delai_min": 60}
        v = [{"cible": "B1", "valeur": 30}]
        ev, e = P.decider(b, v, None, maintenant=T0)
        self.assertEqual(ev, "declenche")
        self.assertEqual(P.decider(b, v, e, maintenant=T0 + 60)[0], None)          # toujours en cours : pas de 2e alerte
        ev, e = P.decider(b, [], e, maintenant=T0 + 120)
        self.assertEqual(ev, "retour")
        self.assertEqual(P.decider(b, v, e, maintenant=T0 + 600)[0], None)         # délai de 60 min pas écoulé
        self.assertEqual(P.decider(b, v, e, maintenant=T0 + 3600)[0], "declenche")
        self.assertEqual(P.decider(b, [], {}, maintenant=T0)[0], None)             # pas de retour sans déclenchement
        ev, e = P.decider(dict(b, actif=False), v, {"en_cours": True, "dernier": 5})
        self.assertEqual((ev, e["en_cours"], e["dernier"]), (None, False, 5))

    def test_actions_conseil_auto(self):
        b = {"mode": "conseil", "actions": [{"type": "notifier"}, {"type": "recommander", "outil": "ncc-equilibrage"}, {"type": "banc", "plan": "cast"},
                                            {"type": "banc", "plan": "supprime"}]}
        v = [{"cible": "B1", "valeur": 30.123}]
        a = P.actions_a_faire(b, v, {"cast"})
        self.assertEqual([x["type"] for x in a], ["notifier", "recommander", "banc"])
        self.assertFalse(a[2]["lancer"])
        self.assertEqual(a[0]["detail"], "B1 = 30.12")
        self.assertTrue(P.actions_a_faire(dict(b, mode="auto"), v, {"cast"})[2]["lancer"])

    def test_scenarios(self):
        for s in P.SCENARIOS:            # tous les scénarios s'installent sans erreur, boucles inactives en mode conseil
            boucles, plans, ajouts = P.installer_scenario(s["id"], [], [], maintenant=T0)
            self.assertEqual(len(boucles), len(s["boucles"]), s["id"])
            self.assertEqual({p["id"] for p in plans}, set(s["plans"]))
            self.assertTrue(all(not b["actif"] and b["mode"] == "conseil" and b["scenario"] == s["id"] for b in boucles))
            for p in plans:
                self.assertIsNone(P.valider_plan(p)[1], p["id"])
            b2, p2, aj2 = P.installer_scenario(s["id"], boucles, plans, maintenant=T0 + 1)   # sans doublon
            self.assertEqual((len(b2), len(p2), aj2), (len(boucles), len(plans), {"boucles": [], "plans": []}))
        self.assertIsNone(P.installer_scenario("nope", [], [])[2])
        b, p, _ = P.installer_scenario("cast-degrade", [], [], maintenant=T0)       # deux scénarios dans la même seconde
        b, p, _ = P.installer_scenario("borne-saturee", b, p, maintenant=T0)
        self.assertEqual(len({x["id"] for x in b}), 3)

    def test_outils_liens(self):
        for o in P.OUTILS:
            self.assertTrue(o["url"].startswith(("https://", "?view=")), o["id"])
            if o["type"] == "lien":
                self.assertTrue(o["chemin"], o["id"])


class Bancs(unittest.TestCase):
    def test_valider_plafonds(self):
        p, err = P.valider_plan({"id": "Mon Banc!", "nom": "X", "etapes": [{"duree_min": 5, "sondes": 2, "taches": [
            {"type": "iperf3", "params": {"host": "{serveur}", "udp": True, "bitrate_mbit": 500, "duration": 99, "parallel": 9}, "every": 1}]}],
            "objectifs": {"rtt_ms": "50", "inconnu": 3}})
        self.assertIsNone(err)
        t = p["etapes"][0]["taches"][0]
        self.assertEqual((p["id"], t["params"]["bitrate_mbit"], t["params"]["duration"], t["params"]["parallel"], t["every"]), ("monbanc", 50, 20, 4, 10))
        self.assertEqual(p["objectifs"], {"rtt_ms": 50.0})
        E = {"duree_min": 30, "taches": [{"type": "ping", "params": {"host": "h"}}]}
        self.assertIn("totale", P.valider_plan({"id": "a", "nom": "a", "etapes": [E, E, E]})[1])
        self.assertIsNotNone(P.valider_plan({"id": "a", "nom": "a", "etapes": [dict(E, duree_min=31)]})[1])
        self.assertIsNotNone(P.valider_plan({"id": "a", "nom": "a", "etapes": [dict(E, taches=[{"type": "rm"}])]})[1])
        self.assertIsNotNone(P.valider_plan({"id": "a", "nom": "a", "etapes": [dict(E, taches=[])]})[1])
        self.assertIsNotNone(P.valider_plan({"id": "a", "nom": "a", "etapes": [dict(E, sondes="beaucoup")]})[1])
        self.assertIsNotNone(P.valider_plan({"id": "a", "nom": "a"})[1])
        self.assertIsNotNone(P.valider_plan({"nom": "a", "etapes": [E]})[1])

    def test_sondes_etape(self):
        d = ["a", "b", "c"]
        self.assertEqual(P.sondes_etape({"sondes": "toutes"}, d), d)
        self.assertEqual(P.sondes_etape({"sondes": "moitie"}, d), ["a", "b"])
        self.assertEqual(P.sondes_etape({"sondes": "moitie"}, ["a"]), ["a"])
        self.assertEqual(P.sondes_etape({"sondes": 1}, d), ["a"])
        self.assertEqual(P.sondes_etape({"sondes": ["c", "z"]}, d), ["c"])
        self.assertEqual(P.sondes_etape({}, []), [])

    def test_taches_et_restauration(self):
        reg = {"serveur_iperf": "192.0.2.5", "cible_ping": "", "urls": ["https://intra.exemple.fr/a", "http://www.exemple.fr"]}
        e = {"taches": [{"type": "iperf3", "params": {"host": "{serveur}", "udp": True}, "every": 30},
                        {"type": "ping", "params": {"host": "{cible}"}, "every": 10},
                        {"type": "dns", "params": {"name": "{nom}"}, "every": 30},
                        {"type": "http", "params": {"url": "{url}"}, "every": 20}]}
        t = P.taches_banc(e, reg, "r1")
        self.assertEqual([x["type"] for x in t], ["iperf3", "dns", "http"])          # ping écarté : cible absente
        self.assertEqual(t[0]["params"]["host"], "192.0.2.5")
        self.assertEqual(t[1]["params"]["name"], "intra.exemple.fr")                 # i = 2 -> urls[0]
        self.assertEqual(t[2]["params"]["url"], "http://www.exemple.fr")             # i = 3 -> urls[1]
        self.assertTrue(all(x["banc"] == "r1" for x in t))
        orig = [{"type": "wifi_link", "every": 30}, {"type": "ping", "params": {"host": "x"}, "banc": "r0"}]
        f = P.fusionner(orig, t)
        self.assertEqual(len(f), 4)
        self.assertEqual(P.restaurer(f), [{"type": "wifi_link", "every": 30}])

    def test_manquants(self):
        plan = P.PLANS_MODELES[0]
        self.assertEqual(P.manquants(plan, {}), ["cible du ping", "serveur iperf3", "sondes autorisées pour les bancs"])
        self.assertEqual(P.manquants(plan, {"serveur_iperf": "s", "cible_ping": "c", "sondes": ["a"]}), [])
        nav = next(p for p in P.PLANS_MODELES if p["id"] == "navigation")
        self.assertIn("adresses à charger", P.manquants(nav, {"sondes": ["a"], "cible_ping": "c"}))

    def test_synthese(self):
        run = {"etapes": [{"nom": "E1", "debut": T0, "fin": T0 + 300, "sondes": ["a", "b"], "nebula_simultanes_max": 12},
                          {"nom": "E2", "debut": T0 + 300, "fin": T0 + 600, "sondes": ["a"]}]}
        m = [{"agent_id": "a", "task": "ping:h", "at": iso(T0 + 10), "ok": True, "data": {"rtt_avg_ms": 10, "loss_pct": 0}},
             {"agent_id": "a", "task": "ping:h", "at": iso(T0 + 20), "ok": True, "data": {"rtt_avg_ms": 30, "loss_pct": 0}},
             {"agent_id": "b", "task": "iperf3:s:5202/udp", "at": iso(T0 + 30), "ok": True, "data": {"jitter_ms": 5, "loss_pct": 3}},
             {"agent_id": "b", "task": "iperf3:s", "at": iso(T0 + 40), "ok": False, "error": "refus"},
             {"agent_id": "a", "task": "iperf3:s", "at": iso(T0 + 310), "ok": True, "data": {"received_mbps": 4}},
             {"agent_id": "c", "task": "ping:h", "at": iso(T0 + 10), "ok": True, "data": {"rtt_avg_ms": 999}},     # hors banc
             {"agent_id": "a", "task": "ping:h", "at": iso(T0 + 9999), "ok": True, "data": {"rtt_avg_ms": 999}}]   # hors étapes
        s = P.synthese(run, m, {"rtt_ms": 50, "perte_udp_pct": 1, "debit_min_mbps": 5, "http_ms": 2000})
        e1 = {l["sonde"]: l for l in s["etapes"][0]["lignes"]}
        self.assertEqual((e1["a"]["rtt_ms"], e1["a"]["mesures"]), (20, 2))
        self.assertEqual((e1["b"]["perte_udp_pct"], e1["b"]["echecs"]), (3, 1))
        self.assertEqual(s["etapes"][0]["nebula_simultanes_max"], 12)
        self.assertEqual(s["etapes"][1]["lignes"][0]["debit_mbps"], 4)
        v = {x["objectif"]: x for x in s["verdicts"]}
        self.assertTrue(v["latence"]["ok"])
        self.assertFalse(v["pertes du flux cast"]["ok"])
        self.assertFalse(v["débit par sonde"]["ok"])
        self.assertIsNone(v["chargement HTTP"]["ok"])
        self.assertFalse(s["reussi"])
        self.assertIsNone(P.synthese({"etapes": []}, [], {})["reussi"])


if __name__ == "__main__":
    unittest.main()
