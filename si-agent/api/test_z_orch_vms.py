# -*- coding: utf-8 -*-
"""#836 VM à la demande (Orchestration) : configuration, création, étapes, TTL, nettoyage, routes."""
import os
import sys
import tempfile
import unittest

os.environ.setdefault("SI_AGENT_DB_PATH", os.path.join(tempfile.mkdtemp(), "t.db"))
os.environ.setdefault("MODELES_THREAD", "0")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import orch_vms as V  # noqa: E402

CFG = V.valider_config({"noeud": "pve-x", "vmid_min": 9500, "vmid_max": 9502, "stockage": "local-zfs"})[0]
MOD = {"vmid": 9000, "nom": "banc-modele-debian-13", "os": "linux"}
OK = {"status": "done", "result": {"ok": True}}
KO = {"status": "failed", "result": {"ok": False, "error": "qm: boom"}}


def derouler(vm, reponses, t=1000):
    """Envoie / répond aux étapes dans l'ordre ; -> liste des actions envoyées."""
    envoyes = []
    for rep in reponses:
        vm, g = V.avancer(vm, None, t)
        if g != "envoyer":
            break
        e = V.courante(vm)
        e["commande"] = len(envoyes) + 1
        envoyes.append(e["params"]["action"])
        vm, _ = V.avancer(vm, rep, t + 1)
    return vm, envoyes


class Pur(unittest.TestCase):
    def test_config(self):
        self.assertIsNone(V.valider_config({"noeud": "pve-x", "vmid_min": 9500, "vmid_max": 9502})[1])
        self.assertIn("plage", V.valider_config({"noeud": "pve-x", "vmid_min": 50, "vmid_max": 60})[1])
        self.assertIn("noeud", V.valider_config({"noeud": "a b", "vmid_min": 9500, "vmid_max": 9502})[1])

    def test_creation(self):
        vm, e = V.nouvelle_vm(CFG, MOD, {"nom": "test-web", "ttl_h": 2, "cores": 2, "memoire": 2048}, 1, {9500}, 1000)
        self.assertIsNone(e)
        self.assertEqual((vm["vmid"], vm["nom"], vm["expire"]), (9501, "orch-test-web", 1000 + 7200))
        self.assertEqual(vm["etapes"][0]["params"], {"vmid": 9000, "action": "clone", "newid": 9501, "name": "orch-test-web", "full": False, "storage": "local-zfs"})
        self.assertEqual(vm["etapes"][1]["params"]["options"], {"description": "si-orchestration expire=8200", "cores": 2, "memory": 2048})
        vm, envoyes = derouler(vm, [OK, OK, OK])
        self.assertEqual((envoyes, vm["phase"]), (["clone", "set", "start"], "en_service"))
        self.assertEqual(V.a_expirer([vm], 8200), [vm])
        self.assertTrue(V.detruire(vm, "durée de vie atteinte", 8200))
        self.assertFalse(V.detruire(vm, "encore", 8201))
        vm, envoyes = derouler(vm, [KO, OK])                  # VM déjà arrêtée : on détruit quand même
        self.assertEqual((envoyes, vm["phase"]), (["stop", "destroy"], "detruite"))
        self.assertIn("plage", V.nouvelle_vm(CFG, MOD, {"nom": "x"}, 2, {9500, 9501, 9502}, 0)[1])
        self.assertIn("nom", V.nouvelle_vm(CFG, MOD, {"nom": "X_y"}, 2, set(), 0)[1])
        self.assertIn("durée", V.nouvelle_vm(CFG, MOD, {"nom": "x", "ttl_h": 99999}, 2, set(), 0)[1])

    def test_nettoyage(self):
        vm = V.nouvelle_vm(CFG, MOD, {"nom": "a"}, 1, set(), 0)[0]
        vm, envoyes = derouler(vm, [OK, KO, OK, OK])          # réglage refusé -> arrêt + destruction du clone
        self.assertEqual((envoyes, vm["phase"]), (["clone", "set", "stop", "destroy"], "detruite"))
        self.assertIn("regler", vm["echec"])
        vm = V.nouvelle_vm(CFG, MOD, {"nom": "b"}, 2, set(), 0)[0]
        vm, envoyes = derouler(vm, [KO])                      # clone refusé : rien à nettoyer
        self.assertEqual((envoyes, vm["phase"]), (["clone"], "echec"))
        self.assertFalse(V.detruire(vm, "x", 1))
        self.assertEqual(V.resume(vm)["etapes"][0]["etat"], "echec")


class Api(unittest.TestCase):
    def test_routes(self):
        import app as appmod
        import store
        db, c = appmod.DB_PATH, appmod.app.test_client()
        store.create_agent(db, "pve-x", "siege")
        store.ingest_measurements(db, "pve-x", [{"task": "plugin:proxmox", "at": "2026-10-22T12:00:00Z", "ok": True,
                                                 "data": {"vms": [{"vmid": 9000, "name": "banc-modele-debian-13", "template": 1, "type": "qemu"},
                                                                  {"vmid": 9500, "name": "occupee", "type": "qemu"}]}}])
        self.assertIn("configur", c.post("/orchestration/vms", json={"modele": 9000, "nom": "web"}).json["error"])
        self.assertEqual(c.put("/orchestration/vms/config", json={"noeud": "pve-x", "vmid_min": 9500, "vmid_max": 9502}).status_code, 200)
        e = c.get("/orchestration/vms").json
        self.assertEqual([m["vmid"] for m in e["modeles"]], [9000])
        self.assertIn("modèle", c.post("/orchestration/vms", json={"modele": 1234, "nom": "web"}).json["error"])
        r = c.post("/orchestration/vms", json={"modele": 9000, "nom": "web", "ttl_h": 4})
        self.assertEqual((r.status_code, r.json["vmid"]), (201, 9501))          # 9500 déjà prise sur le nœud
        appmod._orch_vms_tick()
        cmds = [x for x in store.list_commands(db, "pve-x", status="pending") if x["type"] == "vm_action"]
        self.assertEqual(cmds[0]["params"]["action"], "clone")
        self.assertEqual(c.post("/orchestration/vms/9501/detruire").status_code, 200)
        self.assertEqual(c.post("/orchestration/vms/9999/detruire").status_code, 404)
        self.assertEqual(c.get("/orchestration/vms").json["vms"][0]["phase"], "destruction")


if __name__ == "__main__":
    unittest.main()
