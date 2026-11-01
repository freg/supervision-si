# -*- coding: utf-8 -*-
"""Tests #879 : regroupement des copies, clones, préparations et VM de test (noms, numéros de VM, règles), listés en fin."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import etat  # noqa: E402
import etat_plan  # noqa: E402


def L(key, name, type_="CT", status="running", niveau="urgent", vmid=None, node="pve-2", score=5, dependants=()):
    return {"key": key, "name": name, "type": type_, "status": status, "niveau": niveau, "vmid": vmid, "node": node, "score": score, "impact": 0,
            "dependants": list(dependants), "utilise": [], "actions": ["mettre à jour les paquets"], "os": {"nom": "Debian 9", "famille": "debian", "version": "9", "statut": "obsolète", "fin": "2022-06-30"},
            "roles": [], "libelle": None, "maj_at": None, "attente_secu": None, "source": "relevé", "type_": type_, "expose": False, "reseau": []}


def ETAT():
    return {"systemes": [
        L("pve11/114", "serv3-clone", "VM", vmid=114, node="pve11"),
        L("hote:optick3", "optick3", "serveur", node="hors Proxmox", dependants=["pve-2/120"]),
        L("pve10/205", "pre-optick3", "VM", status="stopped", niveau="inactif", vmid=205, node="pve10"),
        L("pve-2/102", "MED10", vmid=102), L("pve-3/102", "md10", status="stopped", niveau="inactif", vmid=102, node="pve-3"),
        L("pve10/302", "MED10-old", status="stopped", niveau="inactif", vmid=302, node="pve10"),
        L("hote:r2d2", "r2d2", "serveur", node="hors Proxmox"), L("pve10/210", "pre-r2d2", "VM", vmid=210, node="pve10"),
        L("pve-1/106", "OB1", vmid=106, node="pve-1"), L("pve-3/9106", "ob1", vmid=9106, node="pve-3"),
        L("pve10/211", "test-agent", "VM", vmid=211, node="pve10"),
        L("pve10/204", "preprodia", "VM", vmid=204, node="pve10"),
        L("pve-2/120", "tickets", vmid=120)],
        "dependances": [{"de": "pve-2/120", "vers": "hote:optick3", "port": 3306, "n": 1, "nature": "base de données"},
                        {"de": "pve-2/120", "vers": "pve10/205", "port": 3306, "n": 1, "nature": "base de données"}]}


class Regroupement(unittest.TestCase):
    def test_nom_de_base(self):
        self.assertEqual(etat.nom_de_base("pre-r2d2"), ("r2d2", "préparation de migration"))
        self.assertEqual(etat.nom_de_base("serv3-clone"), ("serv3", "clone"))
        self.assertEqual(etat.nom_de_base("test-agent"), ("agent", "test"))
        self.assertEqual(etat.nom_de_base("md10-old"), ("md10", "ancienne version"))
        self.assertEqual(etat.nom_de_base("MED10"), ("med10", None))
        self.assertEqual(etat.nom_de_base("preprodia"), ("preprodia", None))     # « pre » sans séparateur : un vrai système

    def test_regrouper(self):
        e = etat.regrouper(ETAT())
        par = {l["key"]: l for l in e["systemes"]}
        self.assertEqual(par["pve10/205"]["variante_de"]["key"], "hote:optick3")
        self.assertEqual(par["pve10/210"]["variante_de"]["role"], "préparation de migration")
        self.assertEqual(par["pve-3/9106"]["variante_de"]["key"], "pve-1/106")      # 9106 -> clone de 106
        self.assertEqual(par["pve-3/9106"]["variante_de"]["role"], "clone")
        self.assertEqual(par["pve-3/102"]["variante_de"]["key"], "pve-2/102")        # md10 / MED10 : copie, la référence est en service
        self.assertEqual(par["pve10/302"]["variante_de"]["key"], "pve-2/102")
        self.assertNotIn("variante_de", par["pve10/204"])                           # preprodia reste un système à part
        self.assertTrue(par["pve11/114"]["representant"]["note"].startswith("« serv3 » n'est pas suivi"))
        self.assertNotIn("variante_de", par["pve11/114"])
        cles = [l["key"] for l in e["systemes"]]
        fin = cles[-6:]
        self.assertEqual(set(fin), {"pve10/205", "pve10/210", "pve-3/9106", "pve-3/102", "pve10/302", "pve10/211"})   # listés en fin
        self.assertEqual(len(par["pve-2/102"]["variantes"]), 2)
        self.assertEqual([d for d in e["dependances"] if d["de"] == "pve-2/120"], [e["dependances"][0]])   # lien vers la copie replié
        self.assertEqual(e["resume"]["variantes"], 6)
        self.assertEqual(e["resume"]["inactif"], 0)                                   # copies arrêtées hors compteurs

    def test_regles_manuelles(self):
        e = etat.regrouper(ETAT(), {"pve10/204": {"de": "prodia", "role": "préparation de migration"}, "pve10/211": {"seul": True}})
        par = {l["key"]: l for l in e["systemes"]}
        self.assertNotIn("variante_de", par["pve10/211"])
        self.assertTrue(par["pve10/204"].get("representant"))                       # « prodia » non suivi ici : il le représente

    def test_planning_sans_variantes(self):
        e = etat.regrouper(ETAT())
        p = etat_plan.plan(e)
        cles = {t["key"] for t in p["taches"]}
        self.assertNotIn("pve-3/9106", cles)
        self.assertNotIn("pve10/210", cles)
        self.assertIn("pve11/114", cles)                                              # représentant de serv3 : planifié

    def test_excel(self):
        try:
            import openpyxl, io
            import etat_excel
        except ImportError:
            self.skipTest("openpyxl absent")
        e = etat.assemble({}, maintenant=1793000000)
        g = etat.regrouper(ETAT())
        for l in g["systemes"]:
            l.update(composants=[], raisons=[], ips=[], usage="moyen", os=dict(l["os"], statut="obsolète", fin="2022-06-30"), maj_jours=None, attente=None)
        e.update(systemes=g["systemes"], dependances=g["dependances"], resume=g["resume"])
        wb = openpyxl.load_workbook(io.BytesIO(etat_excel.classeur(e, maintenant=1793000000, plan=etat_plan.plan(e))))
        noms = [c.value for c in wb["Systèmes"]["A"]]
        self.assertTrue(any("préparation de migration de optick3" in str(n) for n in noms))


if __name__ == "__main__":
    unittest.main()
