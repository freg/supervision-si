# -*- coding: utf-8 -*-
import json
import os
import subprocess
import sys
import types
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from si_agent import orchctl as O  # noqa: E402

T0 = 1_800_000_000


class Valider(unittest.TestCase):
    def test_refus(self):
        self.assertIn("moteur", O.valider({"action": "installer"})[1])
        self.assertIn("action", O.valider({"action": "rm", "moteur": "k3s"})[1])
        self.assertIn("nom", O.valider({"action": "deployer", "moteur": "k3s", "nom": "A_b", "image": "nginx"})[1])
        self.assertIn("image", O.valider({"action": "deployer", "moteur": "k3s", "nom": "web", "image": "nginx; rm -rf /"})[1])
        self.assertIn("Enterprise", O.valider({"action": "quota", "moteur": "nomad", "cpu": 1, "memoire": 1, "pods": 1})[1])
        self.assertIn("jeton", O.valider({"action": "rejoindre", "moteur": "k3s", "serveur": "https://srv:6443", "jeton": "court"})[1])
        self.assertIn("port", O.valider({"action": "deployer", "moteur": "nomad", "nom": "web", "image": "nginx", "port": "x"})[1])

    def test_valeurs(self):
        v, e = O.valider({"action": "deployer", "moteur": "k3s", "nom": "web", "image": "nginx:1.27-alpine", "port": "80", "repliques": "2", "ttl_h": 2}, T0)
        self.assertIsNone(e)
        self.assertEqual((v["espace"], v["repliques"], v["cpu"], v["memoire"], v["expire"]), ("si", 2, 250, 256, T0 + 7200))
        self.assertEqual(O.valider({"action": "etat"})[0]["moteur"], "tous")


class Generation(unittest.TestCase):
    def test_manifeste(self):
        v, _ = O.valider({"action": "deployer", "moteur": "k3s", "nom": "web", "image": "nginx", "port": 80, "ttl_h": 1}, T0)
        m = O.manifeste_k3s(v)
        self.assertEqual([i["kind"] for i in m["items"]], ["Namespace", "Deployment", "Service"])
        self.assertEqual(m["items"][1]["metadata"]["annotations"]["si-orchestration/expire"], str(T0 + 3600))
        self.assertEqual(m["items"][2]["spec"]["type"], "NodePort")
        v["port"] = None
        self.assertEqual(len(O.manifeste_k3s(v)["items"]), 2)

    def test_job(self):
        v, _ = O.valider({"action": "deployer", "moteur": "nomad", "nom": "web", "image": "nginx", "port": 80, "cpu": 50, "repliques": 3}, T0)
        j = O.job_nomad(v)["Job"]
        g = j["TaskGroups"][0]
        self.assertEqual((j["ID"], g["Count"], g["Tasks"][0]["Resources"]["CPU"], g["Networks"][0]["DynamicPorts"][0]["To"], g["Tasks"][0]["Config"]["ports"]),
                         ("web", 3, 100, 80, ["app"]))
        self.assertNotIn("si_expire", j["Meta"])

    def test_scripts_bash(self):
        cas = [{"action": "installer", "moteur": "k3s"}, {"action": "installer", "moteur": "nomad"}, {"action": "rejoindre", "moteur": "nomad", "serveur": "10.0.0.5"},
               {"action": "rejoindre", "moteur": "k3s", "serveur": "https://srv:6443", "jeton": "K10abc::server:0123456789abcdef"},
               {"action": "etat"}, {"action": "deployer", "moteur": "k3s", "nom": "web", "image": "nginx", "port": 80},
               {"action": "deployer", "moteur": "nomad", "nom": "web", "image": "nginx"}, {"action": "echelle", "moteur": "k3s", "nom": "web", "repliques": 0},
               {"action": "echelle", "moteur": "nomad", "nom": "web", "repliques": 2}, {"action": "supprimer", "moteur": "nomad", "nom": "web"},
               {"action": "quota", "moteur": "k3s", "espace": "labo", "cpu": 2000, "memoire": 4096, "pods": 20},
               {"action": "desinstaller", "moteur": "k3s"}, {"action": "desinstaller", "moteur": "nomad"}]
        for p in cas:
            v, e = O.valider(p)
            self.assertIsNone(e, p)
            s = O.script(v)
            r = subprocess.run(["bash", "-n"], input=s, text=True, capture_output=True)
            self.assertEqual(r.returncode, 0, (p, r.stderr))
        s = O.script(O.valider(cas[1])[0])
        self.assertIn('http = "127.0.0.1"', s)
        self.assertIn("--disable traefik --disable servicelb", O.script(O.valider(cas[0])[0]))
        self.assertIn("servers = [", O.script(O.valider(cas[2])[0]))


K3S = {"items": [
    {"kind": "Deployment", "metadata": {"name": "web", "namespace": "si", "annotations": {"si-orchestration/expire": str(T0 - 1)}},
     "spec": {"replicas": 2, "template": {"spec": {"containers": [{"image": "nginx"}]}}}, "status": {"readyReplicas": 1}},
    {"kind": "Service", "metadata": {"name": "web", "namespace": "si"}, "spec": {"ports": [{"port": 80, "nodePort": 31234}]}}]}
NOEUDS = {"items": [{"kind": "Node", "metadata": {"name": "pcia", "labels": {"node-role.kubernetes.io/control-plane": "true"}},
                     "status": {"conditions": [{"type": "Ready", "status": "True"}], "nodeInfo": {"kubeletVersion": "v1.31.4+k3s1"}, "capacity": {"cpu": "16", "memory": "64Gi"}}}]}
NN = [{"Name": "pcia", "Status": "ready", "SchedulingEligibility": "eligible", "Version": "1.9.7"}]
NJ = [{"ID": "api", "Namespace": "default", "Status": "running", "Meta": {"si_orchestration": "1", "si_espace": "si", "si_expire": str(T0 + 99)},
       "JobSummary": {"Summary": {"api": {"Running": 2}}}}]


class Lecture(unittest.TestCase):
    def test_etat(self):
        out = "@@K3S\n%s\n%s\n@@NOMAD\n%s\n%s\n" % (json.dumps(K3S, indent=1), json.dumps(NOEUDS), json.dumps(NN), json.dumps(NJ))
        e = O.lire_etat(out)
        self.assertEqual(e["k3s"]["noeuds"][0]["roles"], ["control-plane"])
        self.assertEqual({k: e["k3s"]["charges"][0][k] for k in ("nom", "voulu", "pret", "acces")}, {"nom": "web", "voulu": 2, "pret": 1, "acces": 31234})
        self.assertEqual((e["nomad"]["noeuds"][0]["pret"], e["nomad"]["charges"][0]["pret"]), (True, 2))
        self.assertEqual(O.a_expirer(e, T0), [{"moteur": "k3s", "nom": "web", "espace": "si"}])
        self.assertEqual(O.lire_etat("@@K3S\n@@NOMAD\n"), {"k3s": {"installe": False, "noeuds": [], "charges": []}, "nomad": {"installe": False, "noeuds": [], "charges": []}})

    def test_run_ttl(self):
        vus = []

        def cmd(argv, timeout=0):
            vus.append(argv[2])
            if "@@K3S" in argv[2]:
                return types.SimpleNamespace(returncode=0, stdout="@@K3S\n" + json.dumps(K3S) + "\n", stderr="")
            return types.SimpleNamespace(returncode=0, stdout="deleted", stderr="")
        r = O.run(cmd, {"action": "etat", "moteur": "k3s"}, T0)
        self.assertTrue(r["ok"])
        self.assertEqual(r["result"]["expirees"], [{"moteur": "k3s", "nom": "web", "espace": "si", "ok": True, "error": None}])
        self.assertIn("delete deployment,service -l app=web", vus[1])
        self.assertEqual(O.masquer({"jeton": "x" * 20, "serveur": "s"}), {"jeton": "(masqué)", "serveur": "s"})
        r = O.run(lambda a, timeout=0: types.SimpleNamespace(returncode=1, stdout="", stderr="bla\nERREUR Docker requis"), {"action": "installer", "moteur": "nomad"})
        self.assertEqual(r["error"], "ERREUR Docker requis")


class Console(unittest.TestCase):
    """#840 console des clusters (hub maison) : Headlamp sur k3s, relais de l'interface Nomad ; jeton hors sortie."""
    def test_console(self):
        for m in ("k3s", "nomad"):
            r = subprocess.run(["bash", "-n"], input=O.script(O.valider({"action": "console", "moteur": m})[0]), text=True, capture_output=True)
            self.assertEqual(r.returncode, 0, r.stderr)
        h = O.manifeste_headlamp()
        self.assertEqual([i["kind"] for i in h["items"]], ["ServiceAccount", "ClusterRoleBinding", "Deployment", "Service"])
        self.assertIn("-base-url=/console/k3s", h["items"][2]["spec"]["template"]["spec"]["containers"][0]["args"])
        self.assertEqual(h["items"][3]["spec"]["ports"][0]["nodePort"], O.CONSOLE_K3S_PORT)
        r = O.run(lambda a, timeout=0: types.SimpleNamespace(returncode=0, stdout="prêt\nJETON eyJsecret\n", stderr=""), {"action": "console", "moteur": "k3s"})
        self.assertEqual(r["result"]["jeton"], "eyJsecret")
        self.assertNotIn("eyJsecret", r["result"]["stdout"])


if __name__ == "__main__":
    unittest.main()
