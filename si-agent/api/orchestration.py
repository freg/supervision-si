# -*- coding: utf-8 -*-
"""Tuile « Orchestration » (livraison #832) -- « genre OpenStack » maison : un seul endroit pour les machines virtuelles
(Proxmox, vues de l'infrastructure ; création depuis les modèles du banc) et les conteneurs (k3s, Nomad) des hôtes
supervisés : clusters, nœuds, charges (image, répliques, accès, expiration), placement automatique, quotas, TTL.
Les ordres sont des commandes `orchestration` aux agents (si_agent/orchctl.py) ; l'état vient de la sonde orchestration.
Pur et testé : clusters, placer."""
from flask import Blueprint, jsonify, request

import banc
import dockerhub
import orch_vms
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
    if v["action"] == "console":
        return jsonify({"error": "console des clusters : hub maison seulement pour l'instant (son jeton resterait dans les commandes du central)"}), 400
    c = store.create_command(DB_PATH, aid, "orchestration", p)
    if evenement:
        evenement("orchestration", "info", "orchestration : %s %s %s sur %s" % (p["action"], p.get("moteur") or "", p.get("nom") or p.get("espace") or "", aid), aid,
                  {"command": (c or {}).get("id"), "params": orchctl.masquer(p)})
    return jsonify({"commande": (c or {}).get("id"), "agent": aid}), 201


@bp.get("/orchestration/images")
def images():
    """#834 catalogue : sélection de départ (sans q) ou recherche Docker Hub."""
    try:
        return jsonify({"images": dockerhub.rechercher(request.args.get("q"))}), 200
    except Exception as e:  # noqa: BLE001
        return jsonify({"error": "Docker Hub injoignable : %s" % e}), 502


@bp.get("/orchestration/images/tags")
def images_tags():
    try:
        return jsonify({"tags": dockerhub.etiquettes(request.args.get("image"))}), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:  # noqa: BLE001
        return jsonify({"error": "Docker Hub injoignable : %s" % e}), 502


# -- #836 VM à la demande (clones de modèles Proxmox, durée de vie) --------------------------------
def _vm_cfg():
    return store.get_setting(DB_PATH, "orch_vms_config", None)


def _vm_liste():
    return store.get_setting(DB_PATH, "orch_vms", None) or []


def _vm_noeud(noeud):
    """Modèles du nœud (sonde proxmox) et vmid déjà pris."""
    data = ((store.latest_per_task(DB_PATH, noeud).get("plugin:proxmox") or {}).get("data")) or {}
    vms = data.get("vms") or []
    return banc.modeles_du_noeud(vms), {v.get("vmid") for v in vms}


@bp.get("/orchestration/vms")
def vms_etat():
    cfg = _vm_cfg()
    modeles = _vm_noeud(cfg["noeud"])[0] if cfg else []
    return jsonify({"config": cfg, "modeles": modeles, "vms": [orch_vms.resume(v) for v in reversed(_vm_liste())][:60]}), 200


@bp.put("/orchestration/vms/config")
def vms_config():
    cfg, err = orch_vms.valider_config(request.get_json(silent=True) or {})
    if err:
        return jsonify({"error": err}), 400
    if store.get_agent(DB_PATH, cfg["noeud"]) is None:
        return jsonify({"error": "agent du nœud inconnu : %s" % cfg["noeud"]}), 400
    banc_pool = store.get_setting(DB_PATH, "banc_pool", None) or {}
    if banc_pool and banc_pool.get("noeud") == cfg["noeud"] and not (cfg["vmid_max"] < banc_pool["vmid_min"] or cfg["vmid_min"] > banc_pool["vmid_max"]):
        return jsonify({"error": "plage de vmid chevauchant celle du Banc (%d-%d)" % (banc_pool["vmid_min"], banc_pool["vmid_max"])}), 400
    store.set_setting(DB_PATH, "orch_vms_config", cfg)
    return jsonify(cfg), 200


@bp.post("/orchestration/vms")
def vms_creer():
    import time
    cfg = _vm_cfg()
    if not cfg:
        return jsonify({"error": "VM à la demande non configurées : nœud et plage de vmid d'abord"}), 400
    b = request.get_json(silent=True) or {}
    modeles, pris = _vm_noeud(cfg["noeud"])
    m = next((x for x in modeles if str(x["vmid"]) == str(b.get("modele"))), None)
    if not m:
        return jsonify({"error": "modèle inconnu sur %s (modèles vus par la sonde proxmox)" % cfg["noeud"]}), 400
    liste = _vm_liste()
    utilises = pris | {v["vmid"] for v in liste if v["phase"] not in ("detruite", "echec")}
    vm, err = orch_vms.nouvelle_vm(cfg, m, b, max([v["id"] for v in liste] or [0]) + 1, utilises, time.time())
    if err:
        return jsonify({"error": err}), 400
    liste.append(vm)
    store.set_setting(DB_PATH, "orch_vms", liste[-200:])
    if evenement:
        evenement("orchestration", "info", "VM à la demande %s (vmid %d) depuis %s sur %s" % (vm["nom"], vm["vmid"], m["nom"], cfg["noeud"]), cfg["noeud"],
                  {"vmid": vm["vmid"], "modele": m["vmid"], "expire": vm["expire"]})
    return jsonify(orch_vms.resume(vm)), 201


@bp.post("/orchestration/vms/<int:vmid>/<geste>")
def vms_geste(vmid, geste):
    import time
    liste = _vm_liste()
    vm = next((v for v in reversed(liste) if v["vmid"] == vmid and v["phase"] not in ("detruite",)), None)
    if not vm:
        return jsonify({"error": "VM à la demande inconnue"}), 404
    if geste == "detruire":
        if not orch_vms.detruire(vm, "demandée", time.time()):
            return jsonify({"error": "déjà en destruction ou détruite"}), 409
        store.set_setting(DB_PATH, "orch_vms", liste)
        return jsonify(orch_vms.resume(vm)), 200
    if geste in ("demarrer", "arreter") and vm["phase"] == "en_service":
        c = store.create_command(DB_PATH, vm["noeud"], "vm_action", {"vmid": vmid, "action": "start" if geste == "demarrer" else "shutdown"})
        return jsonify({"commande": (c or {}).get("id")}), 201
    return jsonify({"error": "geste impossible (%s, phase %s)" % (geste, vm["phase"])}), 400


def vms_tick(maintenant=None):
    """Avance les VM à la demande (une commande à la fois par VM) et applique la durée de vie ; verrou de fichier."""
    import fcntl
    import time
    liste = _vm_liste()
    if not any(v["phase"] in ("creation", "en_service", "destruction") for v in liste):
        return
    t = maintenant or time.time()
    with open(DB_PATH + ".orchvms.lock", "a") as fh:
        try:
            fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            return
        liste = _vm_liste()
        for v in orch_vms.a_expirer(liste, t):
            orch_vms.detruire(v, "durée de vie atteinte", t)
        for v in liste:
            for _ in range(6):
                e = orch_vms.courante(v)
                if e is None:
                    break
                c = store.get_command(DB_PATH, e["commande"]) if e["commande"] else None
                avant = (id(e), e["etat"], e["commande"])
                v, geste = orch_vms.avancer(v, c, t)
                if geste == "envoyer":
                    cmd = store.create_command(DB_PATH, v["noeud"], "vm_action", e["params"])
                    e["commande"] = (cmd or {}).get("id")
                    if not cmd:
                        orch_vms._echec(v, e, "commande refusée par le central (agent du nœud inconnu ?)", t)
                    break
                if (id(e), e["etat"], e["commande"]) == avant:
                    break
            if v["phase"] in ("en_service", "detruite", "echec") and not v.get("signale_" + v["phase"]):
                v["signale_" + v["phase"]] = True
                if evenement:
                    evenement("orchestration", "warning" if v["phase"] == "echec" else "info",
                              "VM à la demande %s (vmid %d) : %s%s" % (v["nom"], v["vmid"], {"en_service": "en service", "detruite": "détruite", "echec": "échec"}[v["phase"]],
                                                                      " -- %s" % (v.get("echec") or v.get("raison_fin") or "") if v.get("echec") or v.get("raison_fin") else ""),
                              v["noeud"], {"vmid": v["vmid"]})
        store.set_setting(DB_PATH, "orch_vms", liste[-200:])
