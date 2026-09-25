# -*- coding: utf-8 -*-
"""Chien de garde applicatif (livraison #613) -- l'agent surveille une liste
d'applications et relance celles qui ne tournent plus.

Configuration reçue du central (commande `watchdog_config`, persistée dans
state.json sous `watchdog`) :
  {"interval_seconds": 60, "apps": [
     {"id": "caisse", "label": "Logiciel de caisse", "process": "caisse.exe",
      "command": "C:\\\\Caisse\\\\caisse.exe", "cwd": null, "enabled": true,
      "cooldown_seconds": 120, "max_restarts_per_hour": 5,
      "hours": "08:00-20:00", "days": "1-7"}]}

Pure : `evaluate(config, running, now, state)` -> (actions, nouvel état,
mesure). `running` = noms des processus en cours (minuscules) ; `state` =
{app_id: {"restarts": [horodatages], "last_restart": t, "down_since": t}}.
Décisions : hors fenêtre horaire -> `idle` ; présent -> `ok` ; absent et
relance possible -> `restart` ; absent et quota atteint -> `down`
(événement critical une seule fois, jusqu'au retour). Le lancement lui-même
(`spawn`) est fourni par l'agent : détaché, jamais attendu.
"""
import datetime as _dt
import os
import re

DEFAULT_INTERVAL = 60
LIMITS = {"cooldown_seconds": (10, 3600, 120), "max_restarts_per_hour": (0, 60, 5)}
APP_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,39}$")


def normalize_config(cfg):
    """-> (config propre, erreurs). Les entrées invalides sont écartées et
    signalées, jamais une config à moitié appliquée en silence."""
    cfg = cfg or {}
    errors = []
    try:
        interval = max(15, min(3600, int(cfg.get("interval_seconds") or DEFAULT_INTERVAL)))
    except (TypeError, ValueError):
        interval, _ = DEFAULT_INTERVAL, errors.append("interval_seconds entier")
    apps, seen = [], set()
    for i, a in enumerate(cfg.get("apps") or []):
        if not isinstance(a, dict):
            errors.append("app %d : objet attendu" % i); continue
        aid = str(a.get("id") or "").strip().lower()
        proc = str(a.get("process") or "").strip()
        if not APP_ID_RE.match(aid):
            errors.append("app %d : id invalide (a-z, 0-9, _ -)" % i); continue
        if aid in seen:
            errors.append("app %s : id en double" % aid); continue
        if not proc or len(proc) > 120:
            errors.append("app %s : process requis (nom de l'exécutable)" % aid); continue
        cmd = str(a.get("command") or "").strip()
        if len(cmd) > 500:
            errors.append("app %s : command trop longue" % aid); continue
        clean = {"id": aid, "label": str(a.get("label") or aid)[:80], "process": proc, "command": cmd or None,
                 "cwd": (str(a.get("cwd")).strip() or None) if a.get("cwd") else None, "enabled": a.get("enabled", True) is not False,
                 "hours": _hours(a.get("hours")), "days": _days(a.get("days"))}
        for key, (lo, hi, default) in LIMITS.items():
            try:
                clean[key] = max(lo, min(hi, int(a.get(key, default))))
            except (TypeError, ValueError):
                clean[key] = default
        seen.add(aid); apps.append(clean)
    return {"interval_seconds": interval, "apps": apps}, errors


def _hours(v):
    m = re.match(r"^\s*(\d{1,2}):(\d{2})\s*-\s*(\d{1,2}):(\d{2})\s*$", str(v or ""))
    if not m:
        return None
    a, b = int(m.group(1)) * 60 + int(m.group(2)), int(m.group(3)) * 60 + int(m.group(4))
    return "%02d:%02d-%02d:%02d" % (a // 60, a % 60, b // 60, b % 60) if 0 <= a < 1440 and 0 <= b < 1440 else None


def _days(v):
    m = re.match(r"^\s*([1-7])\s*-\s*([1-7])\s*$", str(v or ""))
    return "%s-%s" % (m.group(1), m.group(2)) if m else None


def in_window(app, now_dt):
    """now_dt : datetime local. Fenêtre horaire (HH:MM-HH:MM, peut passer
    minuit) et jours ISO (1 = lundi … 7 = dimanche, 'a-b' peut boucler)."""
    d = app.get("days")
    if d:
        a, b = int(d[0]), int(d[2])
        wd = now_dt.isoweekday()
        if not ((a <= wd <= b) if a <= b else (wd >= a or wd <= b)):
            return False
    h = app.get("hours")
    if h:
        a = int(h[0:2]) * 60 + int(h[3:5]); b = int(h[6:8]) * 60 + int(h[9:11])
        cur = now_dt.hour * 60 + now_dt.minute
        if a <= b:
            return a <= cur < b
        return cur >= a or cur < b
    return True


def _base(path):
    return re.split(r"[\\/]", str(path))[-1]


def _is_running(process, running):
    p = process.lower()
    base = _base(p)
    return any(r == p or r == base or _base(r) == base for r in running)


def evaluate(config, running, now, state, now_dt=None):
    """-> (actions, state, measurement). actions = [{"app", "action": restart|down-alert|recovered, "command", "cwd"}]."""
    running = {str(r).lower() for r in (running or [])}
    now_dt = now_dt or _dt.datetime.fromtimestamp(now)
    state = dict(state or {})
    actions, rows = [], []
    for app in (config or {}).get("apps") or []:
        st = dict(state.get(app["id"]) or {})
        st["restarts"] = [t for t in st.get("restarts") or [] if now - t < 3600]
        if not app.get("enabled"):
            status = "disabled"
        elif not in_window(app, now_dt):
            status = "idle"
        elif _is_running(app["process"], running):
            status = "ok"
            if st.get("down_alerted") or st.get("down_since"):
                actions.append({"app": app["id"], "label": app["label"], "action": "recovered", "down_for": int(now - (st.get("down_since") or now))})
            st.pop("down_since", None); st.pop("down_alerted", None)
        else:
            st.setdefault("down_since", now)
            can_restart = bool(app.get("command")) and len(st["restarts"]) < app["max_restarts_per_hour"] \
                and now - (st.get("last_restart") or 0) >= app["cooldown_seconds"]
            if can_restart:
                status = "restart"
                st["restarts"].append(now); st["last_restart"] = now
                actions.append({"app": app["id"], "label": app["label"], "action": "restart", "command": app["command"], "cwd": app.get("cwd"),
                                "attempt": len(st["restarts"])})
            elif now - (st.get("last_restart") or 0) < app["cooldown_seconds"]:
                status = "waiting"
            else:
                status = "down"
                if not st.get("down_alerted"):
                    st["down_alerted"] = True
                    actions.append({"app": app["id"], "label": app["label"], "action": "down-alert",
                                    "reason": "pas de commande de relance" if not app.get("command") else "quota de relances atteint (%d/h)" % app["max_restarts_per_hour"]})
        rows.append({"id": app["id"], "label": app["label"], "process": app["process"], "status": status,
                     "restarts_last_hour": len(st["restarts"]), "down_since": st.get("down_since"), "enabled": app.get("enabled", True)})
        state[app["id"]] = st
    for k in list(state):  # applications retirées de la configuration
        if k not in {a["id"] for a in (config or {}).get("apps") or []}:
            state.pop(k)
    meas = {"apps": rows, "summary": {"total": len(rows), "ok": sum(1 for r in rows if r["status"] == "ok"),
                                      "down": sum(1 for r in rows if r["status"] in ("down", "restart", "waiting")),
                                      "idle": sum(1 for r in rows if r["status"] in ("idle", "disabled"))}}
    return actions, state, meas


def parse_process_list(text, platform="win32"):
    """Sortie de `tasklist /FO CSV /NH` (Windows) ou `ps -eo comm=` -> noms en minuscules."""
    names = set()
    for line in (text or "").splitlines():
        line = line.strip()
        if not line:
            continue
        if platform == "win32":
            m = re.match(r'^"([^"]+)"', line)
            if m:
                names.add(m.group(1).lower())
        else:
            names.add(_base(line).lower())
    return names


def process_list_argv(platform="win32"):
    return ["tasklist.exe", "/FO", "CSV", "/NH"] if platform == "win32" else ["ps", "-eo", "comm="]
