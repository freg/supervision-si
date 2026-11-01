#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Gestionnaire de répartition / migration (livraison #513) -- depuis le manager,
pilote les agents de nœud (deploy/node_agent.py) par le VPN.

  repartition.py status                       état de chaque nœud (agent joignable, services, relais manquants)
  repartition.py plan [nœud]                  ce que chaque nœud lancerait (services, relais, publications)
  repartition.py apply [--build] [nœud…]      pousse deploy/nodes.json à chaque nœud et applique (core d'abord)
  repartition.py migrate <cohorte> <nœud> [--yes] [--force]
        1. vérifie zone / isolation / dépendances ; 2. arrêt de la cohorte sur le nœud source ;
        3. copie des données (bind mounts + volumes nommés) source -> cible par les agents ;
        4. nodes.json mis à jour ; 5. apply sur tous les nœuds (relais re-pointés).
        En cas d'échec de la copie : nodes.json inchangé, cohorte relancée sur la source.

Sauvegarde totale conseillée avant une migration (tuile Sauvegarde).
"""
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NODES = os.path.join(ROOT, "deploy", "nodes.json")
COHORTS = os.path.join(ROOT, "deploy", "cohorts.json")
sys.path.insert(0, os.path.join(ROOT, "deploy"))
from node_agent import DEFAULT_PORT, load_env  # noqa: E402


def load(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def save_nodes(nodes):
    with open(NODES, "w", encoding="utf-8") as fh:
        json.dump(nodes, fh, indent=2, ensure_ascii=False)


class Agents:
    def __init__(self, nodes):
        env = load_env()
        self.token = env.get("SI_NODE_TOKEN", "")
        self.port = int(env.get("SI_NODE_PORT") or DEFAULT_PORT)
        self.nodes = {n["name"]: n for n in nodes["nodes"]}
        if not self.token:
            sys.exit("SI_NODE_TOKEN absent du .env (même valeur sur tous les nœuds)")

    def call(self, node, method, path, body=None, timeout=1800):
        n = self.nodes[node]
        req = urllib.request.Request("http://%s:%d%s" % (n["wg_address"], self.port, path), method=method,
                                     headers={"X-SI-Node-Token": self.token, "Content-Type": "application/json"},
                                     data=json.dumps(body).encode("utf-8") if body is not None else None)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read() or b"{}")
        except urllib.error.HTTPError as e:
            raise RuntimeError("%s %s sur %s : HTTP %d %s" % (method, path, node, e.code, e.read()[:300].decode("utf-8", "replace")))
        except (urllib.error.URLError, OSError) as e:
            raise RuntimeError("%s injoignable (%s) : %s" % (node, n["wg_address"], e))


def ordered(nodes, only=None):
    """core (manager) d'abord : les autres relaient vers lui."""
    ns = [n for n in nodes["nodes"] if not only or n["name"] in only]
    return sorted(ns, key=lambda n: (0 if n.get("role") == "manager" else 1, n["name"]))


def cmd_status(nodes, agents):
    rc = 0
    for n in ordered(nodes):
        try:
            st = agents.call(n["name"], "GET", "/status", timeout=30)
            plan = st.get("plan") or {}
            print("== %-12s %-12s v%s cohortes %s : %d en marche ; relais %d ; gateway %s%s" % (
                n["name"], n["wg_address"], st.get("version"), ",".join(n.get("cohorts") or []), len(st.get("running") or []),
                len(plan.get("relays") or []), ",".join(plan.get("gateway") or []) or "-",
                (" ; SANS RELAIS : " + ", ".join(plan["missing"])) if plan.get("missing") else ""))
            missing = [s for s in (plan.get("services") or []) + (plan.get("relays") or []) if s not in (st.get("running") or [])]
            if missing:
                rc = 1
                print("   arrêtés : " + " ".join(missing))
        except RuntimeError as e:
            rc = 1
            print("== %-12s %s" % (n["name"], e))
    return rc


def cmd_plan(nodes, only=None):
    for n in ordered(nodes, only):
        r = subprocess.run([sys.executable, os.path.join(ROOT, "deploy", "cohorts.py"), "override", n["name"], "-o", "/dev/null"],
                           cwd=ROOT, capture_output=True, text=True)
        print("== %s : %s" % (n["name"], (r.stdout or r.stderr).strip()))
    return 0


def cmd_apply(nodes, agents, build=False, only=None):
    rc = 0
    for n in ordered(nodes, only):
        try:
            res = agents.call(n["name"], "POST", "/apply", {"nodes": nodes, "build": build})
            print("== %s : %s" % (n["name"], " ; ".join(res.get("steps") or ["rien à faire"])))
            if res.get("missing"):
                print("   sans relais : " + ", ".join(res["missing"]))
        except RuntimeError as e:
            rc = 1
            print("== %s : ÉCHEC %s" % (n["name"], e))
    return rc


def check_move(cohorts, nodes, cohort, target, force):
    c = next((x for x in cohorts["cohorts"] if x["name"] == cohort), None)
    if not c:
        return "cohorte inconnue : " + cohort
    t = next((x for x in nodes["nodes"] if x["name"] == target), None)
    if not t:
        return "nœud inconnu : " + target
    if c.get("manager") and not force:
        return "la cohorte %s (passerelle, identité, PKI) reste sur le manager (--force pour passer outre)" % cohort
    if c.get("zone", "local") != t.get("zone", "local") and not force:
        return "zone : la cohorte %s est prévue en zone %s, le nœud %s est en zone %s (--force)" % (cohort, c.get("zone", "local"), target, t.get("zone"))
    if c.get("isolated"):
        allowed = set(c.get("allowed_dependencies") or [])
        others = [x for x in t.get("cohorts") or [] if x != cohort and x not in allowed]
        if others and not force:
            return "cohorte isolée %s : le nœud %s héberge déjà %s (--force)" % (cohort, target, ",".join(others))
    return None


def cmd_migrate(nodes, agents, cohorts, cohort, target, yes=False, force=False):
    err = check_move(cohorts, nodes, cohort, target, force)
    if err:
        print(err)
        return 1
    source = next((n["name"] for n in nodes["nodes"] if cohort in (n.get("cohorts") or [])), None)
    if source == target:
        print("%s est déjà sur %s" % (cohort, target))
        return 0
    print("migration de la cohorte %s : %s -> %s" % (cohort, source or "(nulle part)", target))
    if not yes:
        if input("Continuer ? (oui) ").strip() != "oui":
            return 1
    if source:
        st = agents.call(source, "POST", "/stop", {"cohort": cohort})
        print("== %s : arrêt %s" % (source, " ".join(st.get("stopped") or []) or "(rien ne tournait)"))
        try:
            res = agents.call(target, "POST", "/import/" + cohort, {"from": agents.nodes[source]["wg_address"], "port": agents.port})
            print("== %s : données reçues -- dossiers %s ; volumes %s" % (target, ", ".join(res.get("binds") or []) or "-", ", ".join(res.get("volumes") or []) or "-"))
        except RuntimeError as e:
            print("ÉCHEC de la copie : %s -- nodes.json inchangé, relance sur %s" % (e, source))
            agents.call(source, "POST", "/apply", {"nodes": nodes})
            return 1
    for n in nodes["nodes"]:
        n["cohorts"] = [x for x in (n.get("cohorts") or []) if x != cohort]
        if n["name"] == target:
            n["cohorts"].append(cohort)
    save_nodes(nodes)
    print("deploy/nodes.json mis à jour")
    return cmd_apply(nodes, agents)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = {a for a in sys.argv[1:] if a.startswith("--")}
    cmd = args[0] if args else "status"
    if not os.path.exists(NODES):
        sys.exit("deploy/nodes.json absent (copier deploy/nodes.example.json)")
    nodes = load(NODES)
    if cmd == "plan":
        return cmd_plan(nodes, args[1:] or None)
    agents = Agents(nodes)
    if cmd == "status":
        return cmd_status(nodes, agents)
    if cmd == "apply":
        return cmd_apply(nodes, agents, "--build" in flags, args[1:] or None)
    if cmd == "migrate" and len(args) == 3:
        return cmd_migrate(nodes, agents, load(COHORTS), args[1], args[2], "--yes" in flags, "--force" in flags)
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
