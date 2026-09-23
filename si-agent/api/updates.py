# -*- coding: utf-8 -*-
"""Déploiement contrôlé des mises à jour d'agents (livraison #522) -- logique
pure côté central, testée sans Flask (test_updates.py).

Réglages (settings « updates ») : `beta_agents` (liste d'identifiants qui
reçoivent la nouvelle version en premier), `general_enabled` (activation
volontaire de l'administrateur pour tous les autres), `auto` (planifier
automatiquement dès qu'un agent éligible dépose une mesure ; sinon seul le
bouton « Appliquer maintenant » crée les commandes). Cible = l'archive
construite dans l'image du central (#518) : une seule version disponible à
la fois, celle du dépôt qui a construit l'image.

Statuts par agent : up-to-date · newer · unknown (version jamais remontée) ·
pending (commande envoyée, pas encore acquittée) · started (acquittée,
installeur lancé, en attente du redémarrage) · failed (dernier essai en
échec, réessai après `retry_after_s`) · eligible (à planifier) ·
not-eligible (plus ancienne, mais ni bêta ni activation générale)."""
import time

DEFAULT_SETTINGS = {"beta_agents": [], "general_enabled": False, "auto": True, "retry_after_s": 6 * 3600, "updated_at": None, "updated_by": None}


def normalize_settings(raw):
    s = dict(DEFAULT_SETTINGS)
    for k in ("beta_agents", "general_enabled", "auto", "retry_after_s", "updated_at", "updated_by"):
        if isinstance(raw, dict) and k in raw:
            s[k] = raw[k]
    s["beta_agents"] = sorted({str(a) for a in (s["beta_agents"] or []) if a})
    s["general_enabled"] = bool(s["general_enabled"])
    s["auto"] = bool(s["auto"])
    try:
        s["retry_after_s"] = max(60, int(s["retry_after_s"]))
    except (TypeError, ValueError):
        s["retry_after_s"] = DEFAULT_SETTINGS["retry_after_s"]
    return s


def version_tuple(v):
    out = []
    for part in str(v or "").split("."):
        num = "".join(ch for ch in part if ch.isdigit())
        out.append(int(num) if num else 0)
    return tuple(out) or (0,)


def eligible(agent_id, settings):
    return bool(settings.get("general_enabled")) or agent_id in (settings.get("beta_agents") or [])


def agent_status(agent, package_version, settings, last_update_cmd, now=None):
    """Statut d'un agent vis-à-vis de la version servie ; `last_update_cmd` =
    dernière commande `update` (dict avec status, params, created_at, acked_at, result) ou None."""
    now = now or time.time()
    v = agent.get("agent_version")
    if not package_version:
        return "no-package"
    if not v:
        return "unknown"
    if version_tuple(v) == version_tuple(package_version):
        return "up-to-date"
    if version_tuple(v) > version_tuple(package_version):
        return "newer"
    c = last_update_cmd or {}
    same = (c.get("params") or {}).get("version") == package_version
    if same and c.get("status") == "pending":
        return "pending"
    # #576 : le central note une commande acquittée « done » (ok) ou « failed » (le
    # test utilisait « acked ») -- avec « acked » seul, une mise à jour lancée
    # retombait aussitôt en « à planifier » et était renvoyée à chaque passage,
    # sans jamais dire que l'installeur n'avait rien donné.
    if same and c.get("status") in ("acked", "done", "failed"):
        r = c.get("result") or {}
        age = _age(c.get("acked_at"), now)
        if r.get("ok") and (r.get("result") or {}).get("started"):
            if age < settings.get("stalled_after_s", 900):
                return "started"
            if age < settings.get("retry_after_s", 21600):
                return "stalled"  # installeur lancé, agent toujours en ancienne version
        elif not r.get("ok"):
            if age < settings.get("retry_after_s", 21600):
                return "failed"
    return "eligible" if eligible(agent.get("agent_id"), settings) else "not-eligible"


def _age(iso, now):
    """Âge en secondes d'un horodatage ISO (UTC, suffixe Z) ; très grand si illisible."""
    if not iso:
        return 10 ** 9
    try:
        import datetime
        ts = datetime.datetime.strptime(iso.replace("Z", "+0000")[:24], "%Y-%m-%dT%H:%M:%S%z").timestamp()
        return max(0, now - ts)
    except (ValueError, TypeError):
        try:
            import datetime
            ts = datetime.datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp()
            return max(0, now - ts)
        except (ValueError, TypeError):
            return 10 ** 9


def plan(agents, package, settings, last_cmds, now=None):
    """[{agent_id, hostname, version, status, channel, last}] pour la tuile et l'application."""
    out = []
    pv = (package or {}).get("version")
    for a in agents:
        aid = a.get("agent_id")
        c = last_cmds.get(aid)
        out.append({"agent_id": aid, "hostname": a.get("hostname"), "site": a.get("site"), "version": a.get("agent_version"),
                    "status": agent_status(a, pv, settings, c, now),
                    "channel": "beta" if aid in (settings.get("beta_agents") or []) else ("general" if settings.get("general_enabled") else "off"),
                    "last": {"status": c.get("status"), "created_at": c.get("created_at"), "acked_at": c.get("acked_at"),
                             "to": (c.get("params") or {}).get("version"), "result": c.get("result")} if c else None})
    return out


def to_schedule(planned):
    return [p["agent_id"] for p in planned if p["status"] == "eligible"]


def command_params(package, command_id=None):
    return {"version": package["version"], "sha256": package["sha256"], "url": "/package", "size": package.get("size"), "command_id": command_id}


def summary(planned, package, settings):
    counts = {}
    for p in planned:
        counts[p["status"]] = counts.get(p["status"], 0) + 1
    return {"package": package, "settings": settings, "counts": counts, "total": len(planned)}
