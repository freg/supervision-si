# -*- coding: utf-8 -*-
"""Santé du réseau Nebula (livraison #546) -- logique PURE, testée
(nebula/tests/test_health.py).

Demandé : « une mesure régulière à la minute ou un delta t raisonnable en
termes de charge induite et d'observation : ne rien louper en considérant
qu'un incident dure un temps minimum et que la fenêtre de consultation est
assez étroite pour le voir ».

Règle d'échantillonnage : un incident qui dure au moins D est vu par au
moins un relevé dès que la période T est inférieure ou égale à D. Nebula
lui-même ne déclare un appareil hors ligne qu'après son propre délai de
battement (quelques minutes) : un incident visible dans Nebula dure donc
toujours plus que ce délai, et T = 60 s le voit toujours. Charge : un
appel `online-status` par site et par minute = 1 440 appels par site et
par jour, loin des quotas de l'OpenAPI ; ce qui coûte (clients, inventaire)
est relevé bien moins souvent. Ce module ne conserve que les
TRANSITIONS (état différent du précédent) et l'état courant, jamais un
relevé par minute : la base ne grossit qu'avec les incidents.
"""
import time

ONLINE = "online"


def normalize_status(value):
    """`currentStatus` Nebula (« online », « offline », « alerting »,
    parfois booléen ou majuscules) -> chaîne minuscule stable."""
    if value is True:
        return ONLINE
    if value is False or value is None:
        return "offline"
    return str(value).strip().lower() or "offline"


def diff_statuses(previous, current, at=None):
    """previous : {devId: status} déjà connu ; current : liste
    [{"devId", "currentStatus"}] du relevé. Retourne (nouveaux états,
    transitions [{dev_id, from, to, at}]). Un appareil vu pour la première
    fois compte comme transition depuis `None` (utile pour l'historique)."""
    at = at if at is not None else int(time.time())
    now = {}
    transitions = []
    for entry in current or []:
        if not isinstance(entry, dict) or not entry.get("devId"):
            continue
        dev = entry["devId"]
        st = normalize_status(entry.get("currentStatus"))
        now[dev] = st
        before = (previous or {}).get(dev)
        if before != st:
            transitions.append({"dev_id": dev, "from": before, "to": st, "at": at})
    return now, transitions


def availability(transitions, window_start, window_end, initial_status=ONLINE):
    """Part du temps en ligne d'UN appareil sur [window_start, window_end],
    à partir de ses transitions (triées ou non) ; `initial_status` = état
    au début de la fenêtre quand aucune transition ne le précède.
    Retourne (taux 0..1, secondes hors ligne, nombre d'incidents)."""
    if window_end <= window_start:
        return 1.0, 0, 0
    trs = sorted((t for t in transitions or [] if t.get("to")), key=lambda t: t["at"])
    status = initial_status
    for t in trs:
        if t["at"] <= window_start:
            status = t["to"]
    cursor = window_start
    down = 0
    incidents = 0
    for t in trs:
        if t["at"] <= window_start:
            continue
        if t["at"] > window_end:
            break
        if status != ONLINE:
            down += t["at"] - cursor
        if status == ONLINE and t["to"] != ONLINE:
            incidents += 1
        status = t["to"]
        cursor = t["at"]
    if status != ONLINE:
        down += window_end - cursor
    total = window_end - window_start
    return round(1 - down / total, 4), int(down), incidents


def health_board(devices, statuses, transitions, window_start, window_end, now=None):
    """Le tableau de santé d'un site : devices = inventaire
    [{devId, name, model, type}], statuses = {devId: {status, since}},
    transitions = liste sur la fenêtre (tous appareils). Retourne des
    phrases et des lignes prêtes pour un non-initié."""
    now = now if now is not None else window_end
    by_dev = {}
    for t in transitions or []:
        by_dev.setdefault(t["dev_id"], []).append(t)
    rows = []
    for d in devices or []:
        dev = d.get("devId")
        st = (statuses or {}).get(dev) or {}
        status = normalize_status(st.get("status")) if st else "inconnu"
        rate, down_s, inc = availability(by_dev.get(dev, []), window_start, window_end, initial_status=ONLINE if status == ONLINE and not by_dev.get(dev) else ONLINE)
        rows.append({"dev_id": dev, "name": d.get("name") or dev, "model": d.get("model") or "", "type": d.get("type") or "",
                     "status": status, "since": st.get("since"), "availability": rate, "down_seconds": down_s, "incidents": inc})
    ordre = {"offline": 0, "alerting": 1, "inconnu": 2, ONLINE: 3}
    rows.sort(key=lambda r: (ordre.get(r["status"], 2), r["name"].lower()))
    total = len(rows)
    offline = [r for r in rows if r["status"] not in (ONLINE, "inconnu")]
    unknown = [r for r in rows if r["status"] == "inconnu"]
    avail = round(sum(r["availability"] for r in rows) / total, 4) if total else None
    incidents = sum(r["incidents"] for r in rows)
    if total == 0:
        resume = "Aucun équipement connu."
    elif not offline and not unknown:
        resume = "Tout le réseau est en ligne (%d équipements)." % total
    elif offline:
        resume = "%d équipement%s hors ligne sur %d." % (len(offline), "s" if len(offline) > 1 else "", total)
    else:
        resume = "%d équipement%s en ligne, %d sans relevé." % (total - len(unknown), "s" if total - len(unknown) > 1 else "", len(unknown))
    phrases = []
    for r in offline:
        depuis = ""
        if r.get("since"):
            mins = max(0, int((now - r["since"]) / 60))
            depuis = " depuis %s" % ("%d min" % mins if mins < 120 else "%d h" % (mins // 60))
        phrases.append("%s (%s) : %s%s." % (r["name"], r["model"] or r["type"], "hors ligne" if r["status"] == "offline" else "en alerte", depuis))
    return {"resume": resume, "phrases": phrases, "total": total, "online": total - len(offline) - len(unknown), "offline": len(offline),
            "availability": avail, "incidents": incidents, "window": {"start": window_start, "end": window_end}, "devices": rows}
