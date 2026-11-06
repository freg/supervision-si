# -*- coding: utf-8 -*-
"""#996 : déploiement de hermes-web sur un nœud IA par l'agent (noeudia)."""
import hashlib
import io
import os
import sys
import tarfile
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from si_agent import noeudia as N  # noqa: E402


def archive(fichiers, prefixe="hermes-web/"):
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as t:
        for nom, contenu in fichiers.items():
            data = contenu.encode("utf-8")
            ti = tarfile.TarInfo(prefixe + nom if prefixe is not None else nom)
            ti.size = len(data)
            t.addfile(ti, io.BytesIO(data))
    return buf.getvalue()


KIT = {"hermes_web/__init__.py": '__version__ = "0.29.0"\n', "deploy/noeud/compose.yml": "services: {}\n",
       "deploy/noeud/hermes-config.yaml": "model: {}\n", "config/ia.json": "{}"}
JETON = "a" * 32


class Validation(unittest.TestCase):
    def test_valider(self):
        self.assertIsNone(N.valider({"action": "etat"}))
        self.assertIsNone(N.valider({"action": "deployer", "nom": "prodia", "sha256": "0" * 64}))
        self.assertIn("action", N.valider({"action": "shell"}))
        self.assertIn("nom", N.valider({"action": "deployer", "nom": "../x", "sha256": "0" * 64}))
        self.assertIn("empreinte", N.valider({"action": "deployer", "nom": "prodia"}))
        self.assertIn("port", N.valider({"action": "deployer", "nom": "p", "sha256": "0" * 64, "port": 80}))
        self.assertIn("modèle", N.valider({"action": "deployer", "nom": "p", "sha256": "0" * 64, "modele": "x;rm"}))

    def test_env_et_compose(self):
        e = N.contenu_env(JETON, 8093, "qwen3:4b", "/opt/x")
        self.assertIn("HERMES_WEB_JETON=%s\n" % JETON, e); self.assertIn("HERMES_WEB_PORT=8093", e); self.assertIn("DONNEES=/opt/x", e)
        with self.assertRaises(ValueError):
            N.contenu_env("x\nAUTRE=1")
        a = N.argv_compose("/opt/x")
        self.assertEqual(a[:4], ["docker", "compose", "-p", "hermes-ia"]); self.assertIn("/opt/x/env", a); self.assertEqual(a[-3:], ["up", "-d", "--build"])


class Deploiement(unittest.TestCase):
    def _dep(self, data, sha=None, rc=0, sante=True):
        r = tempfile.mkdtemp()
        appels = []

        def telecharger(dest):
            with open(dest, "wb") as fh:
                fh.write(data)
        p = {"action": "deployer", "nom": "prodia", "sha256": sha or hashlib.sha256(data).hexdigest(), "port": 8092}
        d = N.Deploiement(p, telecharger, lambda: JETON, lambda argv, t: (appels.append(argv), (rc, "construit"))[1],
                          lambda port: (sante, '{"version": "0.29.0"}'), chown=lambda c, u: None, racine=r, horloge=lambda: 100.0)
        N.time.sleep = lambda s: None
        return d, r, appels

    def test_reussi_puis_mise_a_jour(self):
        d, r, appels = self._dep(archive(KIT))
        e = d.executer()
        self.assertTrue(e["ok"], e); self.assertEqual(e["version"], "0.29.0"); self.assertFalse(e["en_cours"])
        self.assertEqual(oct(os.stat(os.path.join(r, "env")).st_mode & 0o777), "0o600")
        self.assertTrue(os.path.isfile(os.path.join(r, "hermes-web", "deploy", "noeud", "compose.yml")))
        self.assertTrue(os.path.isfile(os.path.join(r, "opt-data", "config.yaml")))
        self.assertFalse(os.path.exists(os.path.join(r, "kit.tar.gz")))
        self.assertEqual(N.lire_jeton(r), JETON); self.assertTrue(N.etat_disque(r)["ok"])
        self.assertNotIn(JETON, open(os.path.join(r, "etat.json")).read())
        self.assertEqual(len(appels), 1)
        # mise à jour : l'ancienne version est gardée
        d2 = N.Deploiement(d.p, lambda dest: open(dest, "wb").write(archive(KIT)), lambda: JETON, lambda a, t: (0, ""),
                           lambda port: (True, "ok"), chown=lambda c, u: None, racine=r)
        self.assertTrue(d2.executer()["ok"]); self.assertTrue(os.path.isdir(os.path.join(r, "hermes-web.old")))

    def test_empreinte_differente(self):
        d, r, appels = self._dep(archive(KIT), sha="0" * 64)
        e = d.executer()
        self.assertFalse(e["ok"]); self.assertEqual(e["etape"], "vérification"); self.assertEqual(appels, [])
        self.assertFalse(os.path.exists(os.path.join(r, "env")))

    def test_archive_dangereuse(self):
        d, r, _ = self._dep(archive({"../evil": "x", **KIT}))
        e = d.executer()
        self.assertFalse(e["ok"]); self.assertIn("refusée", e["erreur"])

    def test_archive_trop_ancienne(self):
        d, r, _ = self._dep(archive({"hermes_web/__init__.py": '__version__ = "0.27.0"\n'}))
        e = d.executer()
        self.assertFalse(e["ok"]); self.assertIn("0.29", e["erreur"])
        self.assertFalse(os.path.exists(os.path.join(r, "hermes-web")))

    def test_compose_en_echec(self):
        d, r, _ = self._dep(archive(KIT), rc=1)
        e = d.executer()
        self.assertFalse(e["ok"]); self.assertEqual(e["etape"], "construction et démarrage"); self.assertEqual(e["sortie"], "construit")


if __name__ == "__main__":
    unittest.main()


class Agent(unittest.TestCase):
    """Commande noeud_ia dans l'agent : lecture libre, déploiement gardé par « intervention »."""
    def setUp(self):
        import tests.test_si_agent as _base
        _base.AgentTests.setUp(self)
        self.agent.cfg["noeud_ia_racine"] = tempfile.mkdtemp()

    def test_etat_sans_deploiement(self):
        r = self.agent.execute_command({"id": "n0", "type": "noeud_ia", "params": {"action": "etat"}})
        self.assertTrue(r["ok"], r); self.assertEqual(r["result"], {})

    def test_deployer_garde(self):
        p = {"action": "deployer", "nom": "prodia", "sha256": "0" * 64}
        for permis in ("off", "lecture"):
            self.agent.cfg["remote_shell"] = permis
            r = self.agent.execute_command({"id": "n1", "type": "noeud_ia", "params": p})
            self.assertFalse(r["ok"]); self.assertIn("intervention", r["error"])
        r = self.agent.execute_command({"id": "n2", "type": "noeud_ia", "params": {"action": "deployer", "nom": "../x", "sha256": "0" * 64}})
        self.assertFalse(r["ok"]); self.assertIn("nom", r["error"])
