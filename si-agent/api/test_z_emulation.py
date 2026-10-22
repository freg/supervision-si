# -*- coding: utf-8 -*-
"""#831 tuile Émulation : hôtes (sonde emulation), numérotation des instances, commandes, masquage de la ligne."""
import os
import sys
import tempfile
import unittest

os.environ.setdefault("SI_AGENT_DB_PATH", os.path.join(tempfile.mkdtemp(), "t.db"))
os.environ.setdefault("MODELES_THREAD", "0")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import app as appmod  # noqa: E402
import emulation as EM  # noqa: E402
import store  # noqa: E402


class Pur(unittest.TestCase):
    def test_numerotation(self):
        self.assertEqual(EM.prochaine_instance("rpi0w", ["emu-rpi0w-1", "emu-rpi0w-3", "emu-rpi3b-2"]), ("emu-rpi0w-2", 2))
        self.assertEqual(EM.prochaine_instance("android-34-x86_64", []), ("emu-a34-x8664-1", 1))
        self.assertEqual(EM.prochaine_instance("android-34-arm64-v8a", ["emu-a34-arm64-1"])[0], "emu-a34-arm64-2")
        self.assertEqual((EM.port_pour("systeme", 3), EM.port_pour("avd", 2), EM.port_pour("conteneur", 1)), (52203, 5558, 0))


class Api(unittest.TestCase):
    def test_parcours(self):
        db, c = appmod.DB_PATH, appmod.app.test_client()
        store.create_agent(db, "emu-hote", "siege")
        self.assertIn("activer la sonde", c.post("/emulation/commande", json={"agent": "emu-hote", "action": "lister"}).json["error"])
        store.ingest_measurements(db, "emu-hote", [{"task": "plugin:emulation", "at": "2026-10-22T12:00:00Z", "ok": True,
            "data": {"capacites": {"arch": "x86_64", "kvm": True, "docker": True}, "instances": [{"id": "emu-rpi0w-1", "mode": "conteneur", "etat": "en_marche"}]}}])
        e = c.get("/emulation").json
        h = e["hotes"][0]
        self.assertEqual((h["agent_id"], h["instances"][0]["id"]), ("emu-hote", "emu-rpi0w-1"))
        self.assertFalse(next(p for p in h["profils"] if p["id"] == "android-34-arm64-v8a")["disponible"])
        r = c.post("/emulation/commande", json={"agent": "emu-hote", "action": "lancer", "profil": "rpi0w", "mode": "systeme"})
        self.assertEqual((r.status_code, r.json["instance"], r.json["port"]), (201, "emu-rpi0w-2", 52202))
        r = c.post("/emulation/commande", json={"agent": "emu-hote", "action": "lancer", "profil": "rpi0w"})
        self.assertEqual(r.json["instance"], "emu-rpi0w-3")              # la commande en attente compte
        self.assertIn("licences", c.post("/emulation/commande", json={"agent": "emu-hote", "action": "lancer", "profil": "android-34-x86_64"}).json["error"])
        self.assertIn("hôte ARM", c.post("/emulation/commande", json={"agent": "emu-hote", "action": "preparer", "profil": "android-34-arm64-v8a", "accepter_licences": True}).json["error"])
        # #835 : export d'image, APK, suppression d'un export
        self.assertEqual(c.post("/emulation/commande", json={"agent": "emu-hote", "action": "exporter_image", "instance": "emu-rpi0w-1"}).status_code, 201)
        r = c.post("/emulation/commande", json={"agent": "emu-hote", "action": "installer_apk", "instance": "emu-a34-x8664-1", "url": "https://f-droid.org/F-Droid.apk", "sha256": "a" * 64})
        self.assertEqual(r.status_code, 201, r.json)
        self.assertIn("https", c.post("/emulation/commande", json={"agent": "emu-hote", "action": "installer_apk", "instance": "emu-a", "url": "http://x/a.apk"}).json["error"])
        self.assertEqual(c.post("/emulation/commande", json={"agent": "emu-hote", "action": "supprimer_export", "nom": "emu-rpi0w-1-20261022-2130.img.xz"}).status_code, 201)
        c.post("/emulation/commande", json={"agent": "emu-hote", "action": "deployer_agent", "instance": "emu-rpi0w-1",
                                             "ligne": "curl -fsSL -k 'https://central:6443/deploy/linux?token=SECRET99' | sh"})
        # #839 : porte des écrans déclarée dans le registre des navigateurs (usage « emulation »)
        self.assertEqual(c.put("/navigateurs", json={"navigateurs": [{"nom": "emu-hote", "agent_id": "emu-hote", "usage": "emulation"}]}).status_code, 200)
        e = c.get("/emulation").json
        self.assertEqual((e["ecrans"], e["porte_ecrans"]), ({"emu-hote": "emu-hote"}, 6899))
        self.assertIn("usage", c.put("/navigateurs", json={"navigateurs": [{"nom": "x", "agent_id": "emu-hote", "usage": "autre"}]}).json["error"])
        c.put("/navigateurs", json={"navigateurs": []})                # base partagée entre modules de test
        cmds = c.get("/emulation").json["commandes"]
        self.assertEqual(len(cmds), 6)
        self.assertNotIn("SECRET99", str(cmds))                          # jeton masqué à la relecture


if __name__ == "__main__":
    unittest.main()
