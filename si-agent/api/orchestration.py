# -*- coding: utf-8 -*-
"""Tuile « Orchestration » (livraison #832) -- « genre OpenStack » maison : un seul endroit pour les machines virtuelles
(Proxmox, vues de l'infrastructure ; création depuis les modèles du banc) et les conteneurs (k3s, Nomad) des hôtes
supervisés : clusters, nœuds, charges (image, répliques, accès, expiration), placement automatique, quotas, TTL.
Les ordres sont des commandes `orchestration` aux agents (si_agent/orchctl.py) ; l'état vient de la sonde orchestration.
Pur et testé : clusters, placer."""
from flask import Blueprint, jsonify, request

import store

try:   # copie de si_agent/orchctl.py dans l'image (source unique)
    import si_agent_orchctl as orchctl
except ImportError:   # tests : dépôt
    import os
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "agent"))
    from si_agent import orchctl

bp = Blueprint("orchestration", __name__)
DB_PATH = None          # fourni par app.py
evenement = None        # fourni par app.py : (kind, severity, message, agent_id, details)
machines = None         # fourni par app.py : () -> {nodes, vms} de l'infrastructure Proxmox


def clusters(agents, mesure_de):
    """Agents qui portent la sonde orchestration -> [{agent_id, online, k3s, nomad, expirees, at}]."""
    out = []
    for a in agents:
        m = mesure_de(a["agent_id"])
        if "orchestration" not in (a.get("plugin_ids") or []) and not m:
            continue
        d = (m or {}).get("data") or {}
        mo = d.get("moteurs") or {}
        out.append({"agent_id": a["agent_id"], "online": a.get("online"), "at": (m or {}).get("at"), "erreur": (m or {}).get("error"),
                    "k3s": mo.get("k3s") or {"installe": False, "noeuds": [], "charges": []},
                    "nomad": mo.get("nomad") or {"installe": False, "noeuds": [], "charges": []},
                    "expirees": d.get("expirees") or []})
    return out


def placer(cl, moteur):
    """Placement automatique : hôte en ligne où le moteur tourne, le moins chargé (charges, puis nœuds prêts)."""
    ok = [c for c in cl if c.get("online") and (c.get(moteur) or {}).get("installe")]
    if not ok:
        return None
    return min(ok, key=lambda c: (len(c[moteur]["charges"]) / max(1, sum(1 for n in c[moteur]["noeuds"] if n.get("pret"))), c["agent_id"]))["agent_id"]


def _clusters():
    return clusters(store.fleet(DB_PATH), lambda aid: store.latest_per_task(DB_PATH, aid).get("plugin:orchestration"))


@bp.get("/orchestration")
def etat():
    cl = _clusters()
    cmds = []
    for c in cl:
        for x in store.list_commands(DB_PATH, c["agent_id"], limit=200):
            if x["type"] == "orchestration":
                r = x.get("result") or {}
                cmds.append({"id": x["id"], "agent_id": c["agent_id"], "status": x["status"], "params": orchctl.masquer(x["params"]),
                             "created_at": x.get("created_at"), "error": r.get("error"), "sortie": ((r.get("result") or {}).get("stdout") or "")[-1500:]})
    cmds.sort(key=lambda x: x.get("created_at") or "", reverse=True)
    vm = {"nodes": [], "vms": []}
    if machines:
        try:
            o = machines() or {}
            vm = {"nodes": [{k: n.get(k) for k in ("name", "zone", "ok", "guests", "cpu", "mem")} for n in o.get("nodes") or [] if n.get("role") == "pve"],
                  "vms": [v for v in o.get("vms") or [] if v.get("zone") == "local"]}
        except Exception as e:  # noqa: BLE001
            vm["erreur"] = str(e)
    return jsonify({"clusters": cl, "commandes": cmds[:40], "machines": vm}), 200


@bp.post("/orchestration/commande")
def commande():
    b = request.get_json(silent=True) or {}
    p = {k: b.get(k) for k in ("action", "moteur", "nom", "image", "repliques", "port", "cpu", "memoire", "ttl_h", "espace", "pods", "serveur", "jeton")
         if b.get(k) not in (None, "")}
    cl = {c["agent_id"]: c for c in _clusters()}
    aid = str(b.get("agent") or "")
    if aid == "auto":
        aid = placer(list(cl.values()), str(p.get("moteur") or "")) or ""
        if not aid:
            return jsonify({"error": "placement automatique : aucun hôte en ligne avec %s installé" % (p.get("moteur") or "ce moteur")}), 400
    if aid not in cl:
        return jsonify({"error": "hôte inconnu : activer la sonde « orchestration » sur son agent"}), 400
    v, err = orchctl.valider(p)
    if err:
        return jsonify({"error": err}), 400
    c = store.create_command(DB_PATH, aid, "orchestration", p)
    if evenement:
        evenement("orchestration", "info", "orchestration : %s %s %s sur %s" % (p["action"], p.get("moteur") or "", p.get("nom") or p.get("espace") or "", aid), aid,
                  {"command": (c or {}).get("id"), "params": orchctl.masquer(p)})
    return jsonify({"commande": (c or {}).get("id"), "agent": aid}), 201
