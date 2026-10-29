# -*- coding: utf-8 -*-
"""#919 : analyse technique à distance -- réglage par agent, routes, conservation, interprétation, catalogue vs garde.
`cd si-agent/api && python3 -m unittest test_z_shell`."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
os.environ.setdefault("SI_AGENT_DB_PATH", os.path.join(tempfile.mkdtemp(), "si-agent.db"))
os.environ.setdefault("SI_AGENT_PURGE_THREAD", "0")
os.environ.setdefault("SI_AGENT_CA_FILE", os.path.join(tempfile.mkdtemp(), "ca.crt"))
sys.path.insert(0, HERE)
import app as A  # noqa: E402
import store  # noqa: E402
import shell_analyses as SA  # noqa: E402

PWSH = shutil.which("pwsh") or shutil.which("powershell.exe")
GARDE = os.path.join(HERE, "..", "agent", "si_agent", "garde.ps1")

# Triage calqué sur un vrai poste (valeurs anonymisées) : disque amovible en erreur, 2 arrêts brutaux sans écran bleu,
# Explorateur et ownCloud instables, antivirus actif et à jour.
TRIAGE = {
    "poste": {"nom": "PC-ALPHA", "memoire_go": 15.7, "disque_systeme": 0, "redemarrage_en_attente": False},
    "materiel": {
        "evenements": [
            {"date": "2026-10-28T17:51:56", "source": "disk", "id": 11, "message": "Le pilote a détecté une erreur du contrôleur sur \\Device\\Harddisk1\\DR2."},
            {"date": "2026-10-28T15:23:45", "source": "disk", "id": 11, "message": "Le pilote a détecté une erreur du contrôleur sur \\Device\\Harddisk1\\DR2."},
            {"date": "2026-10-28T14:37:49", "source": "disk", "id": 153, "message": "L'opération d'E/S ... pour le disque 1 (nom d'objet ...) a été tentée à nouveau."},
            {"date": "2026-10-28T09:31:19", "source": "Microsoft-Windows-Kernel-Power", "id": 41, "message": "Le système a redémarré sans s'arrêter correctement au préalable."},
            {"date": "2026-10-27T15:05:42", "source": "Microsoft-Windows-Kernel-Power", "id": 41, "message": "Le système a redémarré sans s'arrêter correctement au préalable."},
        ],
        "disques": {"numero": 0, "nom": "NVMe 1TB", "sante": "Healthy", "temperature": 60, "erreurs_lecture_nc": None, "heures": None, "usure": 0},
        "volumes": [{"lecteur": "C:", "taille_go": 950, "libre_go": 400}],
        "minidumps": [],
    },
    "systeme": {
        "par_appli": [{"appli": "dllhost.exe", "n": 10}, {"appli": "explorer.exe", "n": 6}, {"appli": "userinit.exe", "n": 5}, {"appli": "owncloud.exe", "n": 2}],
        "incidents": [{"appli": "owncloud.exe", "type": "blocage", "module": ""}, {"appli": "Explorer.EXE", "type": "plantage", "module": "ntshrui.dll"},
                      {"appli": "Explorer.EXE", "type": "plantage", "module": "windows.storage.dll"}],
        "services_en_echec": [],
    },
    "viral": {
        "antivirus": [{"nom": "Windows Defender", "etat": 393472}, {"nom": "Bitdefender Endpoint Security Tools", "etat": 266240}],
        "detections": [],
        "demarrage": [{"nom": "ownCloud", "chemin": "C:\\Program Files\\ownCloud\\owncloud.exe", "signature": "signé : ownCloud GmbH"}],
        "services": [], "taches": [{"nom": "\\Maj", "chemin": "C:\\Users\\alice\\AppData\\Local\\x\\maj.exe", "signature": "NotSigned"}],
        "connexions": [], "signatures_connexions": [], "hosts": [],
    },
}


def sortie_triage(doc=TRIAGE):
    return "préambule\n%s\n%s\n%s\n" % (SA.JSON_DEBUT, json.dumps(doc, ensure_ascii=False, indent=1), SA.JSON_FIN)


class Interpretation(unittest.TestCase):
    def test_triage_reel(self):
        r = SA.interpreter("triage", sortie_triage())
        ax = r["axes"]
        textes = " | ".join(c["texte"] for a in ax.values() for c in a["constats"])
        self.assertEqual(ax["materiel"]["niveau"], "suspect")
        self.assertIn("disque n° 1, absent", textes)                     # support amovible, pas le disque système
        self.assertNotIn("disque SYSTÈME", textes)
        self.assertIn("SANS écran bleu", textes)
        self.assertEqual(ax["systeme"]["niveau"], "suspect")
        self.assertIn("Explorateur : 6", textes)
        self.assertIn("ntshrui.dll", textes)
        self.assertIn("ownCloud : 2 blocage", textes)
        self.assertIn("userinit", textes)
        self.assertEqual(ax["viral"]["niveau"], "suspect")                 # tâche non signée dans AppData
        self.assertIn("Bitdefender", textes)
        self.assertIn("Pistes par nombre d'indices : système (3), matériel (2), viral (1)", r["synthese"])

    def test_disque_systeme_et_whea(self):
        doc = json.loads(json.dumps(TRIAGE))
        doc["materiel"]["evenements"] = [{"date": "2026-10-28T10:00:00", "source": "disk", "id": 7, "message": "bloc défectueux sur \\Device\\Harddisk0\\DR0."},
                                         {"date": "2026-10-28T09:00:00", "source": "Microsoft-Windows-WHEA-Logger", "id": 17, "message": "erreur corrigée"}]
        r = SA.interpreter("triage", sortie_triage(doc))
        self.assertEqual(r["axes"]["materiel"]["niveau"], "probable")
        self.assertIn("disque SYSTÈME", " ".join(c["texte"] for c in r["axes"]["materiel"]["constats"]))
        self.assertIn("matériel", r["synthese"].split("Piste")[1])

    def test_antivirus_et_sorties_illisibles(self):
        self.assertEqual(SA.etat_antivirus(266240), (True, True))       # 0x041000 : actif, à jour
        self.assertEqual(SA.etat_antivirus(393472), (False, True))      # 0x060100 : Defender en veille (autre antivirus actif)
        self.assertEqual(SA.etat_antivirus(397584), (True, False))      # 0x061110 : actif, signatures périmées
        self.assertIsNone(SA.interpreter("triage", "pas de JSON"))
        self.assertIsNone(SA.interpreter("processus", "x"))

    def test_integrite(self):
        ok = SA.interpreter("integrite", "No component store corruption detected.\nLa protection des ressources Windows n'a trouv? aucune violation d'int?grit?.\n"
                                         "Windows a analys? le syst?me de fichiers sans trouver de probl?me.")
        self.assertEqual(ok["axes"]["systeme"]["niveau"], "info")
        ko = SA.interpreter("integrite", "The component store is repairable.\nWindows Resource Protection found integrity violations.")
        self.assertEqual(ko["axes"]["systeme"]["niveau"], "probable")
        self.assertIn("CHKDSK : résultat non reconnu", " ".join(c["texte"] for c in ko["axes"]["systeme"]["constats"]))


@unittest.skipUnless(PWSH, "PowerShell absent")
class CatalogueEtGarde(unittest.TestCase):
    def test_chaque_analyse_passe_la_garde_en_lecture(self):
        d = tempfile.mkdtemp()
        for a in SA.CATALOGUE:
            p = os.path.join(d, a["id"] + ".ps1")
            with open(p, "w", encoding="utf-8-sig") as fh:
                fh.write(a["script"])
            r = subprocess.run([PWSH, "-NoProfile", "-NonInteractive", "-File", GARDE, "-Script", p, "-Mode", "lecture", "-Verifier"],
                               capture_output=True, text=True, timeout=120)
            self.assertEqual(r.stdout.strip(), "SI-SHELL-OK", "%s refusée par la garde : %s" % (a["id"], r.stdout + r.stderr))


class Routes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c = A.app.test_client()
        store.create_agent(A.DB_PATH, "pc-sh", "siege", label="pc-sh")

    def test_cycle_complet(self):
        c = self.c
        self.assertEqual(len(c.get("/shell/analyses").get_json()["analyses"]), len(SA.CATALOGUE))
        self.assertEqual(c.post("/agents/pc-sh/shell", json={"analyse": "triage"}).status_code, 403, "désactivé par défaut")
        self.assertEqual(store.config_for_agent(A.DB_PATH, "pc-sh")["remote_shell"], "off")
        v0 = store.config_for_agent(A.DB_PATH, "pc-sh")["version"]
        self.assertEqual(c.put("/agents/pc-sh", json={"remote_shell": "root"}).status_code, 400)
        self.assertEqual(c.put("/agents/pc-sh", json={"remote_shell": "lecture", "actor": "alice"}).status_code, 200)
        cfg = store.config_for_agent(A.DB_PATH, "pc-sh")
        self.assertEqual(cfg["remote_shell"], "lecture")
        self.assertNotEqual(cfg["version"], v0, "le changement de mode change la version de configuration (l'agent l'applique)")
        self.assertEqual(c.post("/agents/pc-sh/shell", json={"script": "Remove-Item x", "mode": "intervention"}).status_code, 403)
        r = c.post("/agents/pc-sh/shell", json={"analyse": "triage", "actor": "alice"})
        self.assertEqual(r.status_code, 200)
        tid = r.get_json()["job"]
        cmd = [x for x in store.list_commands(A.DB_PATH, "pc-sh") if x["type"] == "shell"][0]
        self.assertEqual(cmd["params"]["mode"], "lecture")
        self.assertIn("SI-JSON-DEBUT", cmd["params"]["script"])
        jobs = c.get("/agents/pc-sh/shell").get_json()["jobs"]
        self.assertEqual(jobs[0]["statut"], "en_attente")
        # l'agent pousse l'avancement puis la fin : une seule mesure gardée par commande
        base = {"titre": "Triage", "mode": "lecture", "id": tid}
        store.ingest_measurements(A.DB_PATH, "pc-sh", [{"task": "shell:" + tid, "at": "2026-10-29T15:00:01Z", "agent_id": "pc-sh", "data": dict(base, statut="en_cours", sortie="...")}])
        store.ingest_measurements(A.DB_PATH, "pc-sh", [{"task": "shell:" + tid, "at": "2026-10-29T15:00:09Z", "agent_id": "pc-sh", "data": dict(base, statut="fini", code=0, sortie=sortie_triage())}])
        self.assertEqual(len(store.list_measurements(A.DB_PATH, "pc-sh", task="shell:" + tid)), 1)
        det = c.get("/agents/pc-sh/shell/" + tid).get_json()
        self.assertEqual(det["job"]["statut"], "fini")
        self.assertEqual(det["interpretation"]["axes"]["materiel"]["niveau"], "suspect")
        self.assertIn("SI-JSON-DEBUT", det["job"]["script"])
        self.assertEqual(c.post("/agents/pc-sh/shell/%s/stop" % tid).status_code, 200)
        ev = [e for e in store.list_events(A.DB_PATH, limit=50) if e.get("kind") in ("remote-shell-sent", "remote-shell-mode")]
        self.assertTrue(any("alice" in e["message"] for e in ev), "qui a fait quoi : journalisé")

    def test_intervention(self):
        store.create_agent(A.DB_PATH, "pc-sh2", "siege")
        self.c.put("/agents/pc-sh2", json={"remote_shell": "intervention"})
        r = self.c.post("/agents/pc-sh2/shell", json={"script": "Restart-Service Spooler", "mode": "intervention", "delai": 99999})
        self.assertEqual(r.status_code, 200)
        cmd = [x for x in store.list_commands(A.DB_PATH, "pc-sh2") if x["type"] == "shell"][0]
        self.assertEqual(cmd["params"]["delai"], 3600, "délai borné")
        self.assertEqual(cmd["params"]["titre"], "Restart-Service Spooler")
        self.assertEqual(self.c.post("/agents/pc-sh2/shell", json={"script": "   "}).status_code, 400)


if __name__ == "__main__":
    unittest.main()
