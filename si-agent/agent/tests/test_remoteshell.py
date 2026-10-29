# -*- coding: utf-8 -*-
"""#919 : commandes à distance (analyse technique) -- modes, garde PowerShell, tâches, intégration à l'agent.
Les exécutions réelles demandent PowerShell (`pwsh`) : sautées sinon. `cd si-agent/agent && python3 -m unittest tests.test_remoteshell`"""
import os
import shutil
import sys
import tempfile
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from si_agent import remoteshell as rs  # noqa: E402
import tests.test_si_agent as _base  # noqa: E402  (fixture d'agent réutilisée, sans relancer ses tests)

PWSH = shutil.which("pwsh") or shutil.which("powershell.exe")


def attendre(t, s=30):
    t.thread.join(s)
    return t


class Modes(unittest.TestCase):
    def test_plafond_local(self):
        self.assertEqual(rs.mode_autorise("intervention"), "intervention")
        self.assertEqual(rs.mode_autorise("intervention", "lecture"), "lecture")       # le poste plafonne
        self.assertEqual(rs.mode_autorise("lecture", "intervention"), "lecture")       # le plafond n'élargit pas
        self.assertEqual(rs.mode_autorise("n'importe quoi"), "off")
        self.assertEqual(rs.mode_autorise("lecture", "off"), "off")


@unittest.skipUnless(PWSH, "PowerShell absent")
class Execution(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()

    def tache(self, script, mode="lecture", delai=60, tid="t1"):
        t = rs.Tache(tid, script, mode=mode, titre="essai", delai=delai, dossier=self.d, interp=PWSH)
        t.demarrer()
        return t

    def test_lecture_execute_et_accents(self):
        t = attendre(self.tache('"Été à 60 °C"; Get-Date | Out-Null; [pscustomobject]@{a=1} | Format-List'))
        self.assertEqual(t.statut, "fini", t.sortie()[0])
        self.assertIn("Été à 60 °C", t.etat()["sortie"])
        self.assertEqual(os.listdir(self.d), [], "le script est effacé après exécution")

    def test_lecture_refuse_sans_executer(self):
        temoin = os.path.join(self.d, "temoin")
        t = attendre(self.tache('New-Item -ItemType File "%s" | Out-Null' % temoin))
        self.assertEqual(t.statut, "refuse")
        self.assertIn("SI-SHELL-REFUS", t.etat()["sortie"])
        self.assertFalse(os.path.exists(temoin))

    def test_intervention_execute(self):
        temoin = os.path.join(self.d, "temoin")
        t = attendre(self.tache('New-Item -ItemType File "%s" | Out-Null; "fait"' % temoin, mode="intervention"))
        self.assertEqual(t.statut, "fini", t.sortie()[0])
        self.assertTrue(os.path.exists(temoin))

    def test_delai_puis_arret(self):
        t = attendre(self.tache('"debut"; Start-Sleep -Seconds 60', delai=5), 30)
        self.assertEqual(t.statut, "delai")
        t2 = self.tache('"debut"; Start-Sleep -Seconds 60', tid="t2")
        for _ in range(100):
            if "debut" in t2.sortie()[0]:
                break
            time.sleep(0.1)
        self.assertFalse(t2.termine)
        self.assertIn("debut", t2.etat()["sortie"], "sortie relevée pendant l'exécution")
        t2.arreter()
        attendre(t2)
        self.assertEqual(t2.statut, "interrompu")


class Agent(unittest.TestCase):
    """Intégration : réglage du central, plafond local, commande shell, poussée au central."""
    setUp = _base.AgentTests.setUp

    def envoyer(self, **p):
        p.setdefault("id", "sh-1")
        return self.agent.execute_command({"id": "c-" + p["id"], "type": "shell", "params": p})

    def test_desactive_par_defaut_et_plafond(self):
        r = self.envoyer(script="Get-Date")
        self.assertFalse(r["ok"])
        self.assertIn("non autorisé", r["error"])
        self.agent.cfg["remote_shell"] = "intervention"
        self.agent.cfg["remote_shell_max"] = "lecture"
        r = self.envoyer(id="sh-2", script="Get-Date", mode="intervention")
        self.assertFalse(r["ok"])
        self.assertIn("plafonné", r["error"])

    def test_reglage_recu_du_central(self):
        self.http.config = dict(self.http.config, version="v-rs", remote_shell="lecture")
        self.agent.refresh_config(force=True)
        self.assertEqual(self.agent.cfg["remote_shell"], "lecture")
        self.http.config = dict(self.http.config, version="v-rs2", remote_shell="root")
        self.agent.refresh_config(force=True)
        self.assertEqual(self.agent.cfg["remote_shell"], "off", "valeur inconnue -> off")

    def test_validation(self):
        self.agent.cfg["remote_shell"] = "lecture"
        self.assertFalse(self.envoyer(id="../x", script="Get-Date")["ok"])
        self.assertFalse(self.envoyer(id="sh-3", script="   ")["ok"])
        self.assertFalse(self.envoyer(id="sh-4", action="stop")["ok"], "rien à arrêter")

    @unittest.skipUnless(PWSH, "PowerShell absent")
    def test_execution_et_poussee(self):
        self.agent.cfg["remote_shell"] = "lecture"
        r = self.envoyer(id="sh-9", script='"bonjour depuis le poste"', titre="essai", par="francois")
        self.assertTrue(r["ok"], r)
        t = self.agent._shell["sh-9"]
        attendre(t)
        for _ in range(3):
            self.clock[0] += 1
            self.agent.shell_tick()
        self.assertNotIn("sh-9", self.agent._shell, "commande terminée et poussée -> oubliée")
        m = self.agent.queue.latest(task="shell:sh-9", limit=1)[0]
        self.assertEqual(m["data"]["statut"], "fini")
        self.assertIn("bonjour depuis le poste", m["data"]["sortie"])
        ev = [e["data"]["kind"] for e in self.agent.queue.latest(task="event", limit=20)]
        self.assertIn("remote-shell", ev)


if __name__ == "__main__":
    unittest.main()
