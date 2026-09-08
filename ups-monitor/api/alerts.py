# -*- coding: utf-8 -*-
"""Alertes et seuils des onduleurs (livraison #433, backlog 62) -- logique
PURE : à partir d'un onduleur (ses seuils), du relevé courant, du relevé
précédent et des alertes déjà ouvertes, dire ce qui s'ouvre, ce qui se
ferme, ce qui reste. Aucune base ni réseau ; testé dans test_ups_monitor.py.

Genres d'alerte :
  - alarm        : la carte de l'onduleur signale une alarme (state = alarm,
                   raisons = champs d'état hors valeur normale) ;
  - unreachable  : N relevés consécutifs en échec (N = `unreachable_after`,
                   3 par défaut) ;
  - threshold:<champ> : franchissement d'un seuil (input_voltage min/max,
                   output_load max, battery_capacity min, temperature max) ;
  - (relevé en retard : plus de relevé depuis 2,5 intervalles, automate
     arrêté -- calculé à la LECTURE par l'API (`stale` sur chaque onduleur),
     jamais stocké : personne ne tournerait pour l'ouvrir).
Une alerte se FERME quand sa condition disparaît (relevé ok pour
unreachable, valeur revenue dans la plage avec hystérésis pour un seuil,
state != alarm). L'acquittement humain n'efface pas la condition : il
coupe seulement les notifications tant qu'elle dure.
"""
import json

DEFAULT_THRESHOLDS = {
    "input_voltage_min": 207.0,   # -10 % de 230 V
    "input_voltage_max": 253.0,   # +10 %
    "output_load_max": 80.0,      # % de charge
    "battery_capacity_min": 50.0,  # % de batterie restante
    "temperature_max": 40.0,      # °C
}
THRESHOLD_LABELS = {
    "input_voltage_min": "tension d'entrée basse", "input_voltage_max": "tension d'entrée haute",
    "output_load_max": "charge élevée", "battery_capacity_min": "batterie faible", "temperature_max": "température élevée",
}
# Hystérésis (fraction du seuil) pour ne pas battre autour de la valeur.
HYSTERESIS = 0.02
SEVERITY = {"alarm": "critical", "unreachable": "critical", "stale": "warning",
            "threshold:input_voltage_min": "warning", "threshold:input_voltage_max": "warning", "threshold:output_load_max": "warning",
            "threshold:battery_capacity_min": "critical", "threshold:temperature_max": "warning"}


def parse_thresholds(raw):
    """Seuils d'un onduleur : JSON (texte ou dict) fusionné avec les
    défauts ; une clé à null désactive le seuil."""
    out = dict(DEFAULT_THRESHOLDS)
    if isinstance(raw, str):
        try:
            raw = json.loads(raw) if raw.strip() else {}
        except ValueError:
            raw = {}
    for k, v in (raw or {}).items():
        if k not in DEFAULT_THRESHOLDS:
            continue
        if v in (None, ""):
            out[k] = None
        else:
            try:
                out[k] = float(v)
            except (TypeError, ValueError):
                pass
    return out


def validate_thresholds(raw):
    """(seuils normalisés, erreur) pour l'API."""
    if raw in (None, ""):
        return {}, None
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except ValueError:
            return None, "'thresholds' : JSON invalide"
    if not isinstance(raw, dict):
        return None, "'thresholds' : objet attendu"
    out = {}
    for k, v in raw.items():
        if k not in DEFAULT_THRESHOLDS:
            return None, "'thresholds' : clé inconnue %s (attendues : %s)" % (k, ", ".join(sorted(DEFAULT_THRESHOLDS)))
        if v in (None, ""):
            out[k] = None
        else:
            try:
                out[k] = float(v)
            except (TypeError, ValueError):
                return None, "'thresholds' : %s doit être un nombre ou null" % k
    return out, None


def _value(reading, key):
    v = reading.get(key)
    if v is None:
        fields = reading.get("fields") or {}
        e = fields.get(key) if isinstance(fields, dict) else None
        v = e.get("number") if isinstance(e, dict) else None
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def threshold_checks(thresholds, reading):
    """[(kind, message, details)] des seuils franchis sur ce relevé."""
    out = []
    if not reading or not reading.get("ok"):
        return out
    for key, limit in thresholds.items():
        if limit is None:
            continue
        field, bound = key.rsplit("_", 1)
        v = _value(reading, field)
        if v is None:
            continue
        if bound == "min" and v < limit:
            out.append(("threshold:%s" % key, "%s : %s < %s" % (THRESHOLD_LABELS[key], _fmt(v), _fmt(limit)), {"field": field, "value": v, "limit": limit, "bound": "min"}))
        elif bound == "max" and v > limit:
            out.append(("threshold:%s" % key, "%s : %s > %s" % (THRESHOLD_LABELS[key], _fmt(v), _fmt(limit)), {"field": field, "value": v, "limit": limit, "bound": "max"}))
    return out


def threshold_cleared(kind, thresholds, reading):
    """Un seuil ouvert est-il revenu dans la plage (avec hystérésis) ?"""
    key = kind.split(":", 1)[1]
    limit = thresholds.get(key)
    if limit is None:
        return True
    field, bound = key.rsplit("_", 1)
    v = _value(reading, field)
    if v is None or not reading.get("ok"):
        return False  # pas de donnée : on ne ferme pas sur une absence
    margin = abs(limit) * HYSTERESIS
    return v >= limit + margin if bound == "min" else v <= limit - margin


def _fmt(v):
    return ("%.1f" % v).rstrip("0").rstrip(".")


def evaluate(device, reading, consecutive_failures, open_alerts):
    """Après un relevé : (à ouvrir [{kind, severity, message, details}],
    à fermer [kind], inchangées [kind]).

    `consecutive_failures` : nombre d'échecs consécutifs INCLUANT ce relevé
    (0 si réussi) ; `open_alerts` : {kind: alerte ouverte}."""
    thresholds = parse_thresholds(device.get("thresholds"))
    after = device.get("unreachable_after") or 3
    to_open, to_close, kept = [], [], []
    current = {}
    if not reading.get("ok"):
        if consecutive_failures >= after:
            current["unreachable"] = ("onduleur injoignable depuis %d relevés : %s" % (consecutive_failures, reading.get("error") or "?"), {"failures": consecutive_failures, "error": reading.get("error")})
        # sur un échec, les alertes de seuil/alarme restent telles quelles (pas de donnée)
        for kind in open_alerts:
            if kind != "unreachable" and kind != "stale":
                kept.append(kind)
    else:
        if reading.get("state") == "alarm":
            reasons = reading.get("state_reasons") or []
            current["alarm"] = ("alarme de l'onduleur : %s" % ("; ".join(reasons) if reasons else "état anormal"), {"reasons": reasons})
        for kind, message, details in threshold_checks(thresholds, reading):
            current[kind] = (message, details)
        for kind in open_alerts:
            if kind.startswith("threshold:") and kind not in current:
                if threshold_cleared(kind, thresholds, reading):
                    to_close.append(kind)
                else:
                    kept.append(kind)  # dans la zone d'hystérésis
    for kind, (message, details) in current.items():
        if kind in open_alerts:
            kept.append(kind)
        else:
            to_open.append({"kind": kind, "severity": SEVERITY.get(kind, "warning"), "message": message, "details": details})
    for kind in open_alerts:
        if kind in kept or kind in to_close:
            continue
        if kind == "unreachable" and reading.get("ok"):
            to_close.append(kind)
        elif kind == "alarm" and reading.get("ok") and reading.get("state") != "alarm":
            to_close.append(kind)
        elif kind == "stale":
            to_close.append(kind)
    return to_open, to_close, kept


def stale_check(device, now_ts, last_polled_ts, default_interval):
    """(ouvrir ?, message) : plus de relevé depuis 2,5 intervalles."""
    if not device.get("enabled") or last_polled_ts is None:
        return False, None
    interval = device.get("poll_interval_seconds") or default_interval or 3600
    age = now_ts - last_polled_ts
    if age > interval * 2.5:
        return True, "aucun relevé depuis %d min (intervalle %d s)" % (age // 60, interval)
    return False, None


def format_message(device, alert, closing=False):
    return "[supervision-si/ups] %s %s%s : %s" % (
        "RÉTABLI" if closing else (alert.get("severity") or "warning").upper(), device.get("name"), " (%s)" % device["site"] if device.get("site") else "", alert.get("message"))
