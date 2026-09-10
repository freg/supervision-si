# -*- coding: utf-8 -*-
"""Synthèse « supervision / analyse réseau » du bastion (livraison #454) --
logique PURE à partir de l'état du relais (/status) et de la queue du
journal d'audit (/audit). Sert la catégorie « Bastion » de la tuile
Supervision SI (état relais / shim host / sessions) et les liens « accès
bastion » de l'analyse réseau (cibles jointes depuis le Mac par le hub).
"""
import datetime as _dt


def _parse_ts(s):
    if not s:
        return None
    try:
        return _dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def target_host(target):
    """'192.168.1.10:443' -> '192.168.1.10' ; '[fe80::1]:22' -> 'fe80::1' ; None -> None."""
    if not target:
        return None
    t = str(target)
    if t.startswith("["):
        return t[1:].split("]", 1)[0]
    if t.count(":") == 1:
        return t.split(":", 1)[0]
    return t


def build_summary(status, events, now=None, window_h=24):
    """-> {relay, host, enabled, sessions_active, banned, refused_window,
    sessions_window, last_session, last_refused, targets:[{host, target,
    count, kinds, bytes, last}]} -- métadonnées seulement."""
    now = now or _dt.datetime.now(_dt.timezone.utc)
    since = now - _dt.timedelta(hours=window_h)
    status = status or {}
    counters = status.get("counters") or {}
    out = {
        "relay": "up" if status.get("_reachable", True) else "down",
        "host_connected": bool(status.get("host_connected")),
        "enabled": bool(status.get("enabled", True)),
        "sessions_active": len(status.get("sessions") or []),
        "active": status.get("sessions") or [],
        "banned": status.get("banned") or [],
        "counters": {"opened": counters.get("opened", 0), "closed": counters.get("closed", 0), "refused": counters.get("refused", 0)},
        "refused_window": 0, "sessions_window": 0, "last_session": None, "last_refused": None,
        "window_h": window_h, "targets": [],
    }
    agg = {}
    for ev in events or []:
        ts = _parse_ts(ev.get("at"))
        kind = ev.get("event")
        if kind == "refused":
            if ts and ts >= since:
                out["refused_window"] += 1
            if not out["last_refused"] or (ev.get("at") or "") >= (out["last_refused"].get("at") or ""):
                out["last_refused"] = {"at": ev.get("at"), "peer": ev.get("peer"), "reason": ev.get("reason"), "client": ev.get("client")}
        elif kind == "session-start":
            if ts and ts >= since:
                out["sessions_window"] += 1
            if not out["last_session"] or (ev.get("at") or "") >= (out["last_session"].get("at") or ""):
                out["last_session"] = {"at": ev.get("at"), "client": ev.get("client"), "kind": ev.get("kind"), "target": ev.get("target")}
            tgt = ev.get("target")
            if tgt:
                a = agg.setdefault(tgt, {"host": target_host(tgt), "target": tgt, "count": 0, "kinds": set(), "bytes": 0, "last": None})
                a["count"] += 1
                a["kinds"].add(ev.get("kind") or "?")
                if not a["last"] or (ev.get("at") or "") > a["last"]:
                    a["last"] = ev.get("at")
        elif kind == "session-end":
            tgt = ev.get("target")
            if tgt and tgt in agg:
                agg[tgt]["bytes"] += int(ev.get("bytes_up") or 0) + int(ev.get("bytes_down") or 0)
    out["targets"] = sorted(({**a, "kinds": sorted(a["kinds"])} for a in agg.values()),
                            key=lambda a: (-a["count"], a["target"]))
    # état synthétique pour la supervision : critical si relais injoignable,
    # warning si shim host absent ou bastion en pause, ok sinon.
    if out["relay"] == "down":
        out["state"], out["state_text"] = "critical", "relais injoignable"
    elif not out["host_connected"]:
        out["state"], out["state_text"] = "warning", "shim host non connecté"
    elif not out["enabled"]:
        out["state"], out["state_text"] = "warning", "bastion en pause"
    else:
        n = out["sessions_active"]
        out["state"], out["state_text"] = "ok", ("%d session(s) en cours" % n if n else "prêt, aucune session")
    return out
