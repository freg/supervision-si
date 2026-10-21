# -*- coding: utf-8 -*-
"""#807 : configuration radio d'une sonde (wifi_config) et relais du collecteur (collecteur)."""
import json
import os
import stat
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from si_agent import collectctl, wificonf  # noqa: E402


class Runner(object):
    def __init__(self):
        self.appels = []

    def __call__(self, args):
        self.appels.append(args)
        if args[:3] == ["nmcli", "connection", "up"] and args[3] == "si-Bloque":
            return 4, "", "Error: secrets were required"
        return 0, "", ""


class Config(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.nm = os.path.join(self.d, "nm")
        self.conf = os.path.join(self.d, "conf.d", "si.conf")
        self.reg = os.path.join(self.d, "wifi-sondes.json")

    def appliquer(self, params, run=None):
        return wificonf.appliquer(params, run or Runner(), nm_dir=self.nm, nm_conf=self.conf, reglage=self.reg)

    def test_validation(self):
        self.assertIn("rôle", wificonf.valider({"interfaces": {"wlan0": "pirate"}})[2])
        self.assertIn("8 à 63", wificonf.valider({"ssids": [{"ssid": "a", "psk": "court"}]})[2])
        self.assertIn("double", wificonf.valider({"ssids": [{"ssid": "a"}, {"ssid": "a"}]})[2])
        self.assertIn("rôle client", wificonf.valider({"interfaces": {"alfa0": "moniteur"}, "ssids": [{"ssid": "a", "iface": "alfa0"}]})[2])
        self.assertIsNone(wificonf.valider({"interfaces": {"wlan0": "client"}, "ssids": [{"ssid": "Campus", "psk": "12345678"}]})[2])
        self.assertEqual(wificonf.nom_connexion("Campus Numéria/2"), "si-Campus_Num_ria_2")

    def test_appliquer_puis_retirer(self):
        params = {"interfaces": {"wlan0": "client", "alfa0": "moniteur", "wlan1": "inactive"},
                  "ssids": [{"ssid": "Campus", "psk": "motdepasse1", "actif": True}, {"ssid": "Invites", "psk": "", "actif": True},
                            {"ssid": "Ancien", "psk": "motdepasse2", "actif": False}]}
        run = Runner()
        r = self.appliquer(params, run)
        self.assertTrue(r["ok"], r)
        self.assertEqual(sorted(r["connexions_ecrites"]), ["si-Campus", "si-Invites"])
        f = os.path.join(self.nm, "si-Campus.nmconnection")
        texte = open(f).read()
        self.assertEqual(stat.S_IMODE(os.stat(f).st_mode), 0o600)                        # clé lisible par root seul
        self.assertIn("psk=motdepasse1", texte)
        self.assertIn("never-default=true", texte)                                        # pas de route par défaut
        self.assertIn("autoconnect=true", texte)                                          # premier SSID de wlan0
        self.assertIn("interface-name=wlan0", texte)
        self.assertIn("autoconnect=false", open(os.path.join(self.nm, "si-Invites.nmconnection")).read())
        self.assertNotIn("wifi-security", open(os.path.join(self.nm, "si-Invites.nmconnection")).read())
        self.assertIn("unmanaged-devices=interface-name:alfa0;interface-name:wlan1", open(self.conf).read())
        self.assertNotIn("motdepasse", json.dumps(run.appels))                            # jamais en ligne de commande
        doc = json.load(open(self.reg))
        self.assertNotIn("motdepasse", json.dumps(doc))
        self.assertEqual([s["actif"] for s in doc["ssids"]], [True, True, False])
        self.assertIn(["ip", "link", "set", "wlan1", "down"], run.appels)
        self.assertIn(["nmcli", "connection", "up", "si-Campus"], run.appels)
        uid = open(f).read().split("uuid=")[1].split()[0]
        params["ssids"][0]["actif"] = False                                               # désactivation depuis le hub
        r = self.appliquer(params)
        self.assertEqual(r["connexions_retirees"], ["si-Campus"])
        self.assertFalse(os.path.exists(f))
        fi = os.path.join(self.nm, "si-Invites.nmconnection")
        uid_i = open(fi).read().split("uuid=")[1].split()[0]
        params["ssids"][1]["psk"] = "nouvellecle"
        self.appliquer(params)
        self.assertIn("psk=nouvellecle", open(fi).read())
        self.assertEqual(uid_i, open(fi).read().split("uuid=")[1].split()[0])            # même connexion, clé changée
        self.assertNotEqual(uid, uid_i)

    def test_echec_de_connexion_et_reglage_lu(self):
        r = self.appliquer({"interfaces": {"wlan0": "client"}, "ssids": [{"ssid": "Bloque", "psk": "12345678"}]})
        self.assertFalse(r["ok"])
        self.assertIn("secrets were required", r["error"])
        self.assertEqual(wificonf.reglage_lu(self.reg), ("wlan0", ["si-Bloque"]))
        self.assertEqual(wificonf.reglage_lu(os.path.join(self.d, "absent")), (None, []))


class Relais(unittest.TestCase):
    def test_commande_relayee(self):
        etat = {"agents": [{"agent_id": "sonde-3b", "hostname": "sonde-3b", "ip": "192.0.2.160"}], "commands": []}
        appels = []

        def http(m, chemin, corps=None):
            appels.append((m, chemin, corps))
            if m == "POST":
                etat["commands"] = [{"id": "c7", "status": "pending"}]
                return 201, {"id": "c7"}
            if len(appels) > 3:
                etat["commands"] = [{"id": "c7", "status": "done", "result": {"ok": True, "result": {"connexions_ecrites": ["si-Campus"]}}}]
            return 200, etat
        t = [0]
        r = collectctl.run({"action": "commande", "sonde": "sonde-3b", "type": "wifi_config", "params": {"action": "etat"}}, http,
                           pause=lambda s: t.__setitem__(0, t[0] + s), horloge=lambda: t[0])
        self.assertTrue(r["ok"], r)
        self.assertEqual(r["result"]["resultat"], {"connexions_ecrites": ["si-Campus"]})
        self.assertEqual(appels[1], ("POST", "/ui/command", {"agent_id": "sonde-3b", "type": "wifi_config", "params": {"action": "etat"}}))
        self.assertEqual(collectctl.run({"action": "sondes"}, http)["result"]["sondes"][0]["sonde"], "sonde-3b")
        self.assertIn("inconnue", collectctl.run({"action": "commande", "sonde": "x", "type": "wifi_config"}, http)["error"])
        self.assertIn("non relayé", collectctl.run({"action": "commande", "sonde": "sonde-3b", "type": "power_action"}, http)["error"])

    def test_sonde_absente_et_collecteur_injoignable(self):
        t = [0]
        r = collectctl.run({"action": "commande", "sonde": "sonde-3b", "type": "collect_now", "attendre_s": 20},
                           lambda m, c, b=None: (201, {"id": "c1"}) if m == "POST" else (200, {"agents": [{"agent_id": "sonde-3b"}], "commands": []}),
                           pause=lambda s: t.__setitem__(0, t[0] + s), horloge=lambda: t[0])
        self.assertFalse(r["ok"])
        self.assertIn("à son retour", r["error"])
        self.assertIn("injoignable", collectctl.run({}, lambda m, c, b=None: (0, {"error": "collecteur injoignable"}))["error"])


if __name__ == "__main__":
    unittest.main()
