# -*- coding: utf-8 -*-
"""Alertes et récapitulatif des anomalies réseau (livraison #703) -- logique
PURE, testée (nebula/tests/test_report.py) :

- réglages normalisés (marche / arrêt, heure et jours du récapitulatif,
  formats joints, gravité minimale, délai avant alerte, rappel, retour à la
  normale, destinataires, sites, fréquence de contrôle) ;
- suivi des anomalies (première / dernière apparition) : une alerte
  d'urgence ne part qu'après `delay_minutes` sans retour à la normale, une
  fois (ou toutes les `repeat_hours`) ; disparition après alerte -> « retour
  à la normale » ; historique des résolues (7 jours) pour le récapitulatif ;
- échéance du récapitulatif quotidien (heure locale, jours ISO 1-7)."""
import re
from datetime import datetime, timedelta

SEV_ORDER = {"haute": 0, "moyenne": 1, "basse": 2, "info": 3}
FORMATS = ("xlsx", "pdf", "csv")
EMAIL_RE = re.compile(r"^[^@\s,;<>]+@[^@\s,;<>]+\.[A-Za-z]{2,}$")

DEFAULTS = {
    "recipients": [],
    "sites": [],                     # vide = tous les sites
    "check_minutes": 10,
    "daily": {"enabled": False, "time": "08:00", "weekdays": [1, 2, 3, 4, 5], "formats": ["xlsx", "pdf"],
              "min_severity": "info", "only_if_anomalies": False},
    "urgent": {"enabled": False, "min_severity": "haute", "delay_minutes": 15, "repeat_hours": 0, "notify_recovery": True},
}


def _int(v, lo, hi, default):
    try:
        return max(lo, min(hi, int(v)))
    except (TypeError, ValueError):
        return default


def normalize(cfg):
    """Réglages reçus (partiels, d'une ancienne version...) -> réglages complets et valides."""
    cfg = cfg if isinstance(cfg, dict) else {}
    d, u = dict(DEFAULTS["daily"]), dict(DEFAULTS["urgent"])
    din, uin = cfg.get("daily") if isinstance(cfg.get("daily"), dict) else {}, cfg.get("urgent") if isinstance(cfg.get("urgent"), dict) else {}
    d["enabled"] = bool(din.get("enabled", d["enabled"]))
    t = str(din.get("time") or d["time"]).strip()
    d["time"] = t if re.match(r"^([01]\d|2[0-3]):[0-5]\d$", t) else DEFAULTS["daily"]["time"]
    days = din.get("weekdays", d["weekdays"])
    d["weekdays"] = sorted({int(x) for x in days if str(x).isdigit() and 1 <= int(x) <= 7}) if isinstance(days, list) else d["weekdays"]
    fm = din.get("formats", d["formats"])
    d["formats"] = [f for f in FORMATS if isinstance(fm, list) and f in fm]
    d["min_severity"] = din.get("min_severity") if din.get("min_severity") in SEV_ORDER else d["min_severity"]
    d["only_if_anomalies"] = bool(din.get("only_if_anomalies", d["only_if_anomalies"]))
    u["enabled"] = bool(uin.get("enabled", u["enabled"]))
    u["min_severity"] = uin.get("min_severity") if uin.get("min_severity") in SEV_ORDER else u["min_severity"]
    u["delay_minutes"] = _int(uin.get("delay_minutes", u["delay_minutes"]), 0, 1440, u["delay_minutes"])
    u["repeat_hours"] = _int(uin.get("repeat_hours", u["repeat_hours"]), 0, 168, u["repeat_hours"])
    u["notify_recovery"] = bool(uin.get("notify_recovery", u["notify_recovery"]))
    rec = cfg.get("recipients", [])
    if isinstance(rec, str):
        rec = re.split(r"[\s,;]+", rec)
    recipients = sorted({str(e).strip().lower() for e in rec or [] if EMAIL_RE.match(str(e).strip())})[:50]
    sites = [str(s) for s in cfg.get("sites") or [] if str(s).strip()] if isinstance(cfg.get("sites"), list) else []
    return {"recipients": recipients, "sites": sites, "check_minutes": _int(cfg.get("check_minutes", DEFAULTS["check_minutes"]), 5, 120, 10),
            "daily": d, "urgent": u}


def invalid_recipients(raw):
    """Adresses refusées (pour le dire à l'utilisateur plutôt que de les ignorer en silence)."""
    if isinstance(raw, str):
        raw = re.split(r"[\s,;]+", raw)
    return [str(e).strip() for e in raw or [] if str(e).strip() and not EMAIL_RE.match(str(e).strip())]


def severity_ok(sev, minimum):
    return SEV_ORDER.get(sev, 9) <= SEV_ORDER.get(minimum, 3)


def track(state, rows, now, urgent_cfg):
    """state : {"open": {clé: entrée}, "resolved": [entrée...]} ; rows : lignes de report.rows_from (masquées exclues).
    -> (state, urgentes, rétablies). Entrée : site_id, site, id, severity, element, message, action, first_seen,
    last_seen, notified_at, resolved_at."""
    state = {"open": dict((state or {}).get("open") or {}), "resolved": list((state or {}).get("resolved") or [])}
    seen, urgent, recovered = set(), [], []
    for r in rows or []:
        key = "%s|%s" % (r["site_id"], r["id"])
        seen.add(key)
        e = dict(state["open"].get(key) or {"first_seen": now, "notified_at": None})
        e.update({k: r.get(k) for k in ("site_id", "site", "id", "severity", "element", "message", "action", "kind")})
        e["last_seen"] = now
        if urgent_cfg.get("enabled") and severity_ok(e["severity"], urgent_cfg.get("min_severity", "haute")) \
                and now - e["first_seen"] >= urgent_cfg.get("delay_minutes", 0) * 60:
            rep = urgent_cfg.get("repeat_hours") or 0
            if e.get("notified_at") is None or (rep and now - e["notified_at"] >= rep * 3600):
                e["notified_at"] = now
                urgent.append(dict(e))
        state["open"][key] = e
    for key in [k for k in state["open"] if k not in seen]:
        e = dict(state["open"].pop(key), resolved_at=now)
        if e.get("notified_at") and urgent_cfg.get("notify_recovery", True):
            recovered.append(e)
        state["resolved"].append(e)
    state["resolved"] = [e for e in state["resolved"] if now - e.get("resolved_at", now) <= 7 * 86400][-500:]
    return state, urgent, recovered


def first_seen_map(state):
    return {(e["site_id"], e["id"]): e["first_seen"] for e in ((state or {}).get("open") or {}).values()}


def scheduled_today(daily, now_dt):
    hh, mm = (int(x) for x in daily["time"].split(":"))
    return now_dt.replace(hour=hh, minute=mm, second=0, microsecond=0)


def daily_due(daily, last_sent_ts, now_dt):
    """Récapitulatif à envoyer maintenant ? (activé, jour retenu, heure passée, pas encore envoyé depuis l'heure prévue)."""
    if not daily.get("enabled") or now_dt.isoweekday() not in (daily.get("weekdays") or []):
        return False
    slot = scheduled_today(daily, now_dt)
    if now_dt < slot or now_dt - slot > timedelta(hours=6):     # rattrapage limité à 6 h (serveur arrêté...)
        return False
    return not last_sent_ts or datetime.fromtimestamp(last_sent_ts) < slot


def next_daily(daily, now_dt):
    """Prochaine émission prévue (datetime) ou None."""
    if not daily.get("enabled") or not daily.get("weekdays"):
        return None
    for i in range(8):
        day = (now_dt + timedelta(days=i))
        slot = scheduled_today(daily, day)
        if slot.isoweekday() in daily["weekdays"] and slot > now_dt:
            return slot
    return None


def resolved_since(state, since_ts):
    return [e for e in (state or {}).get("resolved") or [] if e.get("resolved_at", 0) >= since_ts]
