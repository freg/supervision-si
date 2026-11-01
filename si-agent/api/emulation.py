# -*- coding: utf-8 -*-
"""Tuile « Émulation et déploiement supervisé » (livraison #831) -- hôtes d'émulation (sonde emulation), catalogue
(Raspberry Pi 3 B / Zero W / Zero 2 W en conteneur ou machine complète ; Android API 24-35 par architecture),
commandes `emulation` aux agents (préparer, lancer, arrêter, détruire, installer l'agent dans une instance).
Pur et testé : hotes, prochaine_instance."""
import re

from flask import Blueprint, jsonify, request

import store

try:   # copie de si_agent/emulctl.py dans l'image (source unique)
    import si_agent_emulctl as emulctl
except ImportError:   # tests : dépôt
    import os
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "agent"))
    from si_agent import emulctl

bp = Blueprint("emulation", __name__)
DB_PATH = None          # fourni par app.py
evenement = None        # fourni par app.py : (kind, severity, message, agent_id, details)
COURT = {"rpi3b": "rpi3b", "rpi0w": "rpi0w", "rpi02w": "rpi02w"}


def hotes(agents, mesure_de):
    """Agents qui portent la sonde emulation -> [{agent_id, online, capacites, instances, profils, at}]."""
    out = []
    for a in agents:
        m = mesure_de(a["agent_id"])
        if "emulation" not in (a.get("plugin_ids") or []) and not m:
            continue
        d = (m or {}).get("data") or {}
        cap = d.get("capacites") or {}
        out.append({"agent_id": a["agent_id"], "online": a.get("online"), "version": a.get("agent_version"), "at": (m or {}).get("at"),
                    "capacites": cap, "instances": d.get("instances") or [], "profils": emulctl.profils(cap.get("arch") or "x86_64"),
                    "erreur": (m or {}).get("error")})
    return out


def prochaine_instance(profil, existantes):
    """emu-<profil court>-<n> libre (instances du registre et commandes en attente) -> (id, n)."""
    base = "emu-%s" % (COURT.get(profil) or re.sub(r"^android-(\d+)-(.*)$", lambda m: "a%s-%s" % (m.group(1), m.group(2).replace("_", "").replace("-v8a", "")), profil))
    pris = {int(m.group(1)) for x in existantes for m in [re.match(r"^%s-(\d+)$" % re.escape(base), x or "")] if m}
    n = 1
    while n in pris:
        n += 1
    return "%s-%d" % (base, n), n


def port_pour(mode, n):
    return 52200 + n if mode == "systeme" else (5554 + 2 * (n % 40) if mode == "avd" else 0)


@bp.get("/emulation")
def etat():
    hs = hotes(store.fleet(DB_PATH), lambda aid: store.latest_per_task(DB_PATH, aid).get("plugin:emulation"))
    cmds = []
    for h in hs:
        for c in store.list_commands(DB_PATH, h["agent_id"], limit=200):
            if c["type"] == "emulation":
                r = c.get("result") or {}
                cmds.append({"id": c["id"], "agent_id": h["agent_id"], "status": c["status"], "params": c["params"], "created_at": c.get("created_at"),
                             "error": r.get("error"), "sortie": ((r.get("result") or {}).get("stdout") or "")[-1500:]})
    cmds.sort(key=lambda x: x.get("created_at") or "", reverse=True)
    # #839 : porte des écrans d'émulation publiée par le bastion (registre des navigateurs, usage « emulation »)
    ecrans = {n["agent_id"]: n["nom"] for n in store.get_setting(DB_PATH, "navigateurs", []) or [] if n.get("usage") == "emulation"}
    return jsonify({"hotes": hs, "commandes": cmds[:40], "android_api": emulctl.ANDROID_API, "ecrans": ecrans, "porte_ecrans": emulctl.PORTE_ECRANS}), 200


@bp.post("/emulation/commande")
def commande():
    b = request.get_json(silent=True) or {}
    aid = str(b.get("agent") or "")
    hs = {h["agent_id"]: h for h in hotes(store.fleet(DB_PATH), lambda a: store.latest_per_task(DB_PATH, a).get("plugin:emulation"))}
    if aid not in hs:
        return jsonify({"error": "hôte d'émulation inconnu : activer la sonde « emulation » sur son agent"}), 400
    h = hs[aid]
    p = {k: b.get(k) for k in ("action", "profil", "mode", "instance", "accepter_licences", "ligne", "port", "url", "sha256", "nom") if b.get(k) not in (None, "")}
    if p.get("action") == "lancer" and not p.get("instance"):
        pending = [str((c.get("params") or {}).get("instance") or "") for c in store.list_commands(DB_PATH, aid, status="pending")]
        iid, n = prochaine_instance(str(p.get("profil") or ""), [i.get("id") for i in h["instances"]] + pending)
        p["instance"] = iid
        mode = p.get("mode") or ("avd" if str(p.get("profil") or "").startswith("android") else "conteneur")
        p["port"] = p.get("port") or port_pour(mode, n)
    v, err = emulctl.valider(p, (h["capacites"] or {}).get("arch") or "x86_64")
    if err:
        return jsonify({"error": err}), 400
    c = store.create_command(DB_PATH, aid, "emulation", p)
    if evenement:
        evenement("emulation", "info", "émulation : %s %s sur %s" % (p["action"], p.get("instance") or p.get("profil") or "", aid), aid,
                  {"command": (c or {}).get("id"), "action": p["action"], "profil": p.get("profil"), "instance": p.get("instance")})
    return jsonify({"commande": (c or {}).get("id"), "instance": p.get("instance"), "port": p.get("port")}), 201
