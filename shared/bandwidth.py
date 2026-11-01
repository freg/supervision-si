# -*- coding: utf-8 -*-
"""Analyse de bande passante par tranche horaire (livraison #641, item 107).

Logique PURE, sans réseau : transforme une série de compteurs d'interface
(octets cumulés relevés par une API -- Proxmox rrddata, MikroTik, SNMP/switch)
en débits, en tranches temporelles, et surtout **estime automatiquement la
fenêtre temporelle unitaire** = la plus petite durée d'activité continue
observée. Cette fenêtre dit à quelle granularité agréger : ni plus grossière
que les rafales réelles, ni plus fine que l'échantillonnage.

Copiée au build là où on l'utilise (comme protocol.py). Testée :
shared/test_bandwidth.py.
"""
import math

IDLE_FLOOR_BPS = 8000  # 1 ko/s : en dessous, on considère la liaison au repos


def rates(samples):
    """samples = [(t_epoch, octets_cumulés), …] (t croissant) -> [(t0, t1, débit_bps)].
    Gère les remises à zéro du compteur (redémarrage) : un delta négatif est ignoré."""
    pts = sorted((float(t), float(b)) for t, b in samples if t is not None and b is not None)
    out = []
    for (t0, b0), (t1, b1) in zip(pts, pts[1:]):
        dt = t1 - t0
        if dt <= 0:
            continue
        db = b1 - b0
        if db < 0:  # compteur réinitialisé
            continue
        out.append((t0, t1, 8.0 * db / dt))  # bits/s
    return out


def _auto_idle(series):
    """Seuil de repos : max(plancher, 10 % du débit actif médian)."""
    nz = sorted(r for _, _, r in series if r > IDLE_FLOOR_BPS)
    if not nz:
        return IDLE_FLOOR_BPS
    med = nz[len(nz) // 2]
    return max(IDLE_FLOOR_BPS, 0.10 * med)


def activity_runs(series, idle_bps=None):
    """Durées des plages d'activité continue (intervalles consécutifs au-dessus du repos)."""
    idle = _auto_idle(series) if idle_bps is None else idle_bps
    runs, cur = [], 0.0
    for t0, t1, r in series:
        if r > idle:
            cur += (t1 - t0)
        elif cur > 0:
            runs.append(cur); cur = 0.0
    if cur > 0:
        runs.append(cur)
    return runs, idle


def estimate_unit_window(series, idle_bps=None):
    """Fenêtre unitaire = plus petite durée d'activité continue (robuste : 10e centile
    des plages, pour ignorer une rafale isolée d'un seul échantillon). -> dict."""
    runs, idle = activity_runs(series, idle_bps)
    if not runs:
        return {"unit_seconds": None, "runs": 0, "idle_bps": round(idle, 1), "suggested_slot_seconds": None}
    runs_sorted = sorted(runs)
    idx = max(0, int(math.ceil(0.10 * len(runs_sorted)) - 1))
    unit = runs_sorted[idx]
    return {"unit_seconds": round(unit, 1), "min_run_seconds": round(runs_sorted[0], 1),
            "max_run_seconds": round(runs_sorted[-1], 1), "runs": len(runs),
            "idle_bps": round(idle, 1), "suggested_slot_seconds": _round_slot(unit)}


def _round_slot(seconds):
    """Arrondit la fenêtre à un pas d'agrégation lisible."""
    for step in (1, 5, 10, 15, 30, 60, 120, 300, 600, 900, 1800, 3600):
        if seconds <= step:
            return step
    return 3600


def per_slot(series, slot_seconds, origin=None):
    """Agrège les débits par tranche de `slot_seconds` -> [{start, end, avg_bps, peak_bps, bytes, active_fraction}].
    Pondère chaque intervalle par sa durée (débit moyen = octets/temps de la tranche)."""
    if not series or not slot_seconds:
        return []
    origin = series[0][0] if origin is None else origin
    slots = {}
    for t0, t1, r in series:
        k = int((t0 - origin) // slot_seconds)
        s = slots.setdefault(k, {"start": origin + k * slot_seconds, "end": origin + (k + 1) * slot_seconds,
                                 "bits": 0.0, "seconds": 0.0, "active": 0.0, "peak_bps": 0.0})
        dt = t1 - t0
        s["bits"] += r * dt; s["seconds"] += dt
        s["peak_bps"] = max(s["peak_bps"], r)
        if r > IDLE_FLOOR_BPS:
            s["active"] += dt
    out = []
    for k in sorted(slots):
        s = slots[k]
        avg = s["bits"] / s["seconds"] if s["seconds"] else 0.0
        out.append({"start": int(s["start"]), "end": int(s["end"]), "avg_bps": round(avg, 1),
                    "peak_bps": round(s["peak_bps"], 1), "bytes": int(s["bits"] / 8),
                    "active_fraction": round(s["active"] / s["seconds"], 3) if s["seconds"] else 0.0})
    return out


def analyze(samples, slot_seconds=None):
    """Chaîne complète : compteurs -> débits -> fenêtre unitaire estimée -> tranches.
    slot_seconds None => tranche horaire (3600) pour l'affichage, la fenêtre unitaire
    étant fournie à part comme granularité naturelle détectée."""
    series = rates(samples)
    window = estimate_unit_window(series)
    hourly = per_slot(series, slot_seconds or 3600)
    unit_slots = per_slot(series, window["suggested_slot_seconds"]) if window["suggested_slot_seconds"] else []
    peak = max((s["peak_bps"] for s in hourly), default=0.0)
    total_bytes = sum(s["bytes"] for s in hourly)
    return {"samples": len(samples), "intervals": len(series), "window": window,
            "hourly": hourly, "unit_slots": unit_slots,
            "summary": {"total_bytes": total_bytes, "peak_bps": round(peak, 1),
                        "unit_seconds": window["unit_seconds"], "suggested_slot_seconds": window["suggested_slot_seconds"]}}
