# -*- coding: utf-8 -*-
"""#825 banc d'installation : validation du pool, masquage des jetons, déroulé d'un passage, échec -> nettoyage, API."""
import os
import sys
import tempfile
import unittest

os.environ.setdefault("SI_AGENT_DB_PATH", os.path.join(tempfile.mkdtemp(), "t.db"))
os.environ.setdefault("MODELES_THREAD", "0")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import app as appmod  # noqa: E402
import banc as B  # noqa: E402
import store  # noqa: E402

POOL = {"noeud": "pve-banc", "vmid_min": 9500, "vmid_max": 9510,
        "modeles": [{"nom": "debian13", "os": "linux", "vmid": 9000}, {"nom": "w11", "os": "windows", "vmid": 9001}],
        "commandes": {"linux": {"installer": "curl -fsSL -k 'https://central:6445/deploy/linux?token=SECRET42' | sh"},
                      "windows": {"installer": "msiexec /i C:\\banc\\si-agent.msi /qn CENTRAL=https://central TOKEN=SECRET42"}}}


def fait(out=""):
    return {"status": "done", "result": {"ok": True, "result": {"exec": {"out": out}}}}


def rate(err):
    return {"status": "failed", "result": {"ok": False, "error": err}}


class Pur(unittest.TestCase):
    def test_pool(self):
        p, err = B.valider_pool(POOL)
        self.assertIsNone(err)
        self.assertIn("systemctl is-active", p["commandes"]["linux"]["verifier"])
        self.assertEqual(p["commandes"]["linux"]["desinstaller"], "")
        self.assertIn("uninstall.ps1", p["commandes"]["windows"]["desinstaller"])
        self.assertIn("plage", B.valider_pool(dict(POOL, vmid_max=99999))[1])
        self.assertIn("plage des clones", B.valider_pool(dict(POOL, modeles=[{"nom": "x", "os": "linux", "vmid": 9505}]))[1])
        self.assertIn("installation", B.valider_pool(dict(POOL, commandes={}))[1])
        pub = B.pool_public(p)
        self.assertNotIn("SECRET42", str(pub))
        self.assertIn("token=•••", pub["commandes"]["linux"]["installer"])

    def test_passage_complet(self):
        p, _ = B.valider_pool(POOL)
        r, _ = B.nouveau_run(p, p["modeles"][0], 1, {9500}, 0)
        self.assertEqual((r["vmid"], r["nom"]), (9501, "banc-debian13-1"))
        t, vus = 0, []
        for _ in range(40):
            if r.get("fin"):
                break
            st = r["etapes"][r["etape"]]
            r, g = B.avancer(r, fait("active") if st["commande"] else None, t)
            if g == "envoyer":
                pa = B.params_etape(r, p)
                if pa is None:
                    B.sauter(r, t)
                else:
                    vus.append(pa["action"]); st["commande"] = len(vus)
            t += 1
        self.assertEqual(vus, ["clone", "start", "guest_ping", "guest_exec", "guest_exec", "stop", "destroy"])   # désinstaller sauté (linux)
        self.assertEqual(B.resultat(r), "réussi")
        self.assertEqual([e["etat"] for e in r["etapes"]][5], "saute")

    def test_echec_saute_au_nettoyage_et_attente_invite(self):
        p, _ = B.valider_pool(POOL)
        r, _ = B.nouveau_run(p, p["modeles"][1], 2, set(), 0)
        r["etape"] = 2
        r["etapes"][2]["commande"], r["etapes"][2]["debut"] = 5, 0
        r, g = B.avancer(r, rate("QEMU guest agent is not running"), 30)      # l'invité démarre : on redemande
        self.assertIsNone(r["etapes"][2]["commande"]); self.assertIsNone(r.get("echec"))
        r["etapes"][2]["commande"] = 6
        r, g = B.avancer(r, {"status": "pending"}, B.DELAIS["attendre_invite"] + 1)
        self.assertIn("délai dépassé", r["echec"])
        self.assertEqual(B.ETAPES[r["etape"]], "arreter")
        self.assertEqual([e["etat"] for e in r["etapes"][3:6]], ["saute"] * 3)
        r["etapes"][r["etape"]]["commande"] = 7
        r, _ = B.avancer(r, rate("VM is not running"), 1000)                   # déjà arrêtée : on détruit quand même
        self.assertEqual(B.ETAPES[r["etape"]], "detruire")
        r["etapes"][r["etape"]]["commande"] = 8
        r, _ = B.avancer(r, fait(), 1001)
        self.assertTrue(r["fin"]); self.assertTrue(B.resultat(r).startswith("échec"))
        self.assertEqual(B.params_etape(dict(r, etape=7), p), {"vmid": r["vmid"], "action": "destroy", "confirm": str(r["vmid"])})

    def test_echec_au_clonage_rien_a_nettoyer(self):
        p, _ = B.valider_pool(POOL)
        r, _ = B.nouveau_run(p, p["modeles"][0], 3, set(), 0)
        r["etapes"][0]["commande"], r["etapes"][0]["debut"] = 1, 0
        r, _ = B.avancer(r, rate("template absent"), 5)
        self.assertTrue(r["fin"]); self.assertEqual({e["etat"] for e in r["etapes"][1:]}, {"saute"})


class Api(unittest.TestCase):
    def test_parcours(self):
        db, c = appmod.DB_PATH, appmod.app.test_client()
        self.assertEqual(c.post("/banc/runs", json={}).status_code, 400)
        self.assertIn("agent du nœud inconnu", c.put("/banc/pool", json=POOL).json["error"])
        store.create_agent(db, "pve-banc", "siege")
        r = c.put("/banc/pool", json=POOL)
        self.assertEqual(r.status_code, 200)
        self.assertNotIn("SECRET42", str(r.json))
        # le hub renvoie la commande masquée : l'ancienne est gardée
        self.assertEqual(c.put("/banc/pool", json=r.json).status_code, 200)
        self.assertIn("SECRET42", store.get_setting(db, "banc_pool")["commandes"]["linux"]["installer"])
        self.assertEqual(c.post("/banc/runs", json={"modeles": ["debian13"]}).json["crees"], ["banc-debian13-1"])
        appmod._banc_tick(maintenant=100)
        cmds = store.list_commands(db, "pve-banc")
        self.assertEqual([(x["type"], x["params"]["action"]) for x in cmds], [("vm_action", "clone")])
        store.ack_command(db, "pve-banc", cmds[0]["id"], {"ok": True})
        appmod._banc_tick(maintenant=110)
        actions = [x["params"]["action"] for x in store.list_commands(db, "pve-banc", limit=10)]
        self.assertIn("start", actions)
        run = c.get("/banc").json["runs"][0]
        self.assertEqual([e["etat"] for e in run["etapes"][:2]], ["fait", "en_cours"])
        self.assertEqual(c.post("/banc/runs/%d/arreter" % run["id"]).status_code, 200)
        self.assertEqual(B.ETAPES[c.get("/banc").json["runs"][0]["etape"]], "arreter")
        self.assertEqual(c.post("/banc/runs/99/arreter").status_code, 404)


if __name__ == "__main__":
    unittest.main()
