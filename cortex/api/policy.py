# -*- coding: utf-8 -*-
"""Cortex, étape 5 (livraison #466) : POLITIQUES D'ALERTE, NOTIFICATIONS
PAR INCIDENT, SILENCES, STATISTIQUES MTTA / MTTR -- logique pure.

- Une POLITIQUE dit, pour un incident, s'il faut notifier, sur quels
  canaux, avec quelle priorité et au bout de combien de temps sans accusé
  il faut escalader. Elle se choisit par rôle de la cause, par site, par
  type d'entité et par sévérité minimale : « un routeur de site vaut plus
  qu'un poste » (principe `policy-role-place`). La première politique qui
  correspond gagne (liste ordonnée) ; la politique par défaut ferme la
  liste.
- UNE notification par incident et par moment (ouverture, escalade,
  résolution), jamais par événement (`notify-per-incident`).
- Un SILENCE (maintenance planifiée, avec référence de ticket) couvre un
  site, une entité ou un rôle sur une plage horaire : les incidents
  couverts ne sont pas notifiés mais restent visibles (`silence-maintenance`).
- ESCALADE : un incident notifié, non acquitté après le délai de sa
  politique, est renotifié une fois sur les canaux d'escalade
  (`escalation`).
- Statistiques : MTTA (accusé), MTTR (clôture) par site, rôle, sévérité ;
  incidents par cause racine ; faux positifs par règle et par principe ;
  couverture ; évolution semaine par semaine.
"""
import datetime as _dt
import statistics
from collections import defaultdict

SEV_ORDER = {"critical": 0, "warning": 1, "info": 2}
PRIORITIES = ("haute", "normale", "basse")
CHANNELS = ("sms", "email", "webhook")

DEFAULT_POLICIES = [
    {"id": "infra-critique", "name": "Infrastructure de site (passerelle, routeur, switch, onduleur, DNS, DHCP)", "order": 10,
     "match": {"roles": ["passerelle", "routeur", "pare-feu", "switch", "borne-wifi", "onduleur", "dns", "dhcp", "equipement-reseau"], "severity_min": "warning"},
     "priority": "haute", "notify": True, "channels": ["sms", "email", "webhook"], "escalate_after_s": 900, "escalation_channels": ["sms"], "notify_resolved": True},
    {"id": "serveurs", "name": "Serveurs et hôtes supervisés", "order": 20,
     "match": {"roles": ["serveur", "hote-supervise", "serveur-web", "base-de-donnees", "nas"], "severity_min": "warning"},
     "priority": "normale", "notify": True, "channels": ["email", "webhook"], "escalate_after_s": 3600, "escalation_channels": ["sms"], "notify_resolved": False},
    {"id": "postes", "name": "Postes de travail, imprimantes, clients WiFi", "order": 30,
     "match": {"roles": ["poste", "imprimante", "client-wifi", "telephone", "camera"], "severity_min": "critical"},
     "priority": "basse", "notify": True, "channels": ["webhook"], "escalate_after_s": None, "escalation_channels": [], "notify_resolved": False},
    {"id": "defaut", "name": "Par défaut", "order": 1000, "match": {"severity_min": "critical"},
     "priority": "normale", "notify": True, "channels": ["email", "webhook"], "escalate_after_s": 3600, "escalation_channels": ["sms"], "notify_resolved": False},
]


def parse_ts(s):
    if not s:
        return None
    try:
        return _dt.datetime.strptime(str(s)[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=_dt.timezone.utc)
    except ValueError:
        return None


def iso(t):
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def validate_policy(p):
    """-> (politique normalisée, erreur|None)"""
    if not isinstance(p, dict) or not (p.get("id") or "").strip():
        return None, "id requis"
    m = p.get("match") or {}
    if not isinstance(m, dict):
        return None, "match doit être un objet"
    sev = m.get("severity_min") or "info"
    if sev not in SEV_ORDER:
        return None, "severity_min : critical | warning | info"
    prio = p.get("priority") or "normale"
    if prio not in PRIORITIES:
        return None, "priority : haute | normale | basse"
    ch = [c for c in (p.get("channels") or []) if c in CHANNELS]
    ech = [c for c in (p.get("escalation_channels") or []) if c in CHANNELS]
    esc = p.get("escalate_after_s")
    if esc is not None:
        try:
            esc = int(esc)
            if esc <= 0:
                esc = None
        except (TypeError, ValueError):
            return None, "escalate_after_s : entier de secondes"
    out = {"id": str(p["id"]).strip(), "name": p.get("name") or p["id"], "order": int(p.get("order") or 500),
           "match": {"roles": [str(r) for r in (m.get("roles") or [])], "sites": [str(s) for s in (m.get("sites") or [])],
                     "kinds": [str(k) for k in (m.get("kinds") or [])], "entities": [str(e) for e in (m.get("entities") or [])],
                     "severity_min": sev, "min_confidence": float(m.get("min_confidence") or 0)},
           "priority": prio, "notify": bool(p.get("notify", True)), "channels": ch, "escalate_after_s": esc, "escalation_channels": ech,
           "notify_resolved": bool(p.get("notify_resolved", False)), "enabled": bool(p.get("enabled", True))}
    return out, None


def _matches(policy, incident, root, root_role):
    m = policy["match"]
    if SEV_ORDER.get(incident.get("severity"), 2) > SEV_ORDER[m.get("severity_min", "info")]:
        return False, "sévérité sous %s" % m["severity_min"]
    if m.get("min_confidence") and (incident.get("confidence") or 0) < m["min_confidence"]:
        return False, "confiance sous %.0f %%" % (m["min_confidence"] * 100)
    if m.get("entities") and incident.get("root") not in m["entities"] and not (set(incident.get("entities") or []) & set(m["entities"])):
        return False, "entité hors liste"
    if m.get("roles") and (root_role not in m["roles"]):
        return False, "rôle %s hors liste" % (root_role or "?")
    if m.get("sites") and ((root or {}).get("site") not in m["sites"]):
        return False, "site hors liste"
    if m.get("kinds") and ((root or {}).get("kind") not in m["kinds"]):
        return False, "type hors liste"
    return True, "rôle %s, site %s, sévérité %s" % (root_role or "?", (root or {}).get("site") or "?", incident.get("severity"))


def evaluate_policy(incident, entities_by_key, roles, policies):
    """-> {policy_id, name, priority, notify, channels, escalate_after_s, escalation_channels, notify_resolved, reason, principle}"""
    root = entities_by_key.get(incident.get("root")) or {}
    root_role = roles.get(incident.get("root"))
    for p in sorted([p for p in policies if p.get("enabled", True)], key=lambda x: x.get("order", 500)):
        ok, why = _matches(p, incident, root, root_role)
        if ok:
            return {"policy_id": p["id"], "name": p["name"], "priority": p["priority"], "notify": p["notify"], "channels": p["channels"],
                    "escalate_after_s": p.get("escalate_after_s"), "escalation_channels": p.get("escalation_channels") or [],
                    "notify_resolved": p.get("notify_resolved", False), "reason": "%s : %s" % (p["name"], why), "principle": "policy-role-place"}
    return {"policy_id": None, "name": "aucune", "priority": "basse", "notify": False, "channels": [], "escalate_after_s": None, "escalation_channels": [],
            "notify_resolved": False, "reason": "aucune politique ne correspond (rôle %s, sévérité %s)" % (root_role or "?", incident.get("severity")), "principle": "policy-role-place"}


# ---------------------------------------------------------------- silences
def silence_covers(silence, incident, entities_by_key, roles, now):
    """Un silence couvre l'incident si la plage est active et que sa cible
    (site / entité / rôle / tout) contient la cause ou une entité de l'incident."""
    start, end = parse_ts(silence.get("start_at")), parse_ts(silence.get("end_at"))
    if not start or not end or not (start <= now <= end):
        return False
    target = silence.get("target") or {}
    ents = [incident.get("root")] + list(incident.get("entities") or [])
    if target.get("entities"):
        return any(e in target["entities"] for e in ents)
    if target.get("sites"):
        return any((entities_by_key.get(e) or {}).get("site") in target["sites"] for e in ents if e)
    if target.get("roles"):
        return any(roles.get(e) in target["roles"] for e in ents if e)
    return True   # silence global


def active_silence(silences, incident, entities_by_key, roles, now):
    for s in silences or []:
        if silence_covers(s, incident, entities_by_key, roles, now):
            return s
    return None


# ---------------------------------------------------------------- décisions de notification
def plan_notifications(incidents, notified, policies, silences, entities_by_key, roles, now, channels_available):
    """Décide ce qui doit partir MAINTENANT : une notification par incident et
    par moment. notified: {clé incident: {kind: at}} déjà envoyées.
    -> [{incident_key, kind: open|escalation|resolved, channels, policy, priority, message, reason}]
    + [{incident_key, kind: skipped, reason}] pour la transparence."""
    plan, skipped = [], []
    for i in incidents or []:
        ev = evaluate_policy(i, entities_by_key, roles, policies)
        done = notified.get(i["key"], {})
        state = i.get("state", "open")
        if state == "closed":
            if "open" in done and ev["notify_resolved"] and "resolved" not in done:
                plan.append({"incident_key": i["key"], "kind": "resolved", "channels": [c for c in ev["channels"] if channels_available.get(c)], "policy": ev["policy_id"],
                             "priority": ev["priority"], "message": format_message(i, "resolved", ev), "reason": "clôturé après notification"})
            continue
        if not ev["notify"]:
            skipped.append({"incident_key": i["key"], "kind": "skipped", "reason": ev["reason"]})
            continue
        sil = active_silence(silences, i, entities_by_key, roles, now)
        if sil:
            skipped.append({"incident_key": i["key"], "kind": "skipped", "reason": "silence « %s » (%s) jusqu'à %s" % (sil.get("name") or sil.get("id"), sil.get("ticket") or "sans ticket", sil.get("end_at"))})
            continue
        chans = [c for c in ev["channels"] if channels_available.get(c)]
        if "open" not in done:
            if not chans:
                skipped.append({"incident_key": i["key"], "kind": "skipped", "reason": "aucun canal disponible parmi %s" % ", ".join(ev["channels"] or ["—"])})
                continue
            plan.append({"incident_key": i["key"], "kind": "open", "channels": chans, "policy": ev["policy_id"], "priority": ev["priority"],
                         "message": format_message(i, "open", ev), "reason": ev["reason"]})
            continue
        if state == "open" and ev["escalate_after_s"] and "escalation" not in done:
            sent_at = parse_ts(done.get("open"))
            if sent_at and (now - sent_at).total_seconds() >= ev["escalate_after_s"]:
                echans = [c for c in (ev["escalation_channels"] or ev["channels"]) if channels_available.get(c)]
                if echans:
                    plan.append({"incident_key": i["key"], "kind": "escalation", "channels": echans, "policy": ev["policy_id"], "priority": ev["priority"],
                                 "message": format_message(i, "escalation", ev), "reason": "non acquitté %d min après notification" % int((now - sent_at).total_seconds() / 60)})
    return plan, skipped


def format_message(incident, kind, ev):
    tag = {"open": "INCIDENT", "escalation": "ESCALADE (non acquitté)", "resolved": "RÉSOLU"}[kind]
    sev = (incident.get("severity") or "info").upper()
    conf = incident.get("confidence")
    return "[supervision-si/cortex] %s %s · priorité %s : %s (cause proposée %s, confiance %d %%)" % (
        tag, sev, ev.get("priority") or "normale", incident.get("title") or incident.get("key"), incident.get("root") or "?", int((conf or 0) * 100))


# ---------------------------------------------------------------- statistiques MTTA / MTTR
def _mean_p(vals):
    if not vals:
        return None
    vals = sorted(vals)
    return {"n": len(vals), "mean_s": int(statistics.mean(vals)), "median_s": int(statistics.median(vals)), "max_s": int(vals[-1])}


def compute_kpis(incidents, entities_by_key, roles, positions, rules, feedback_counts, now=None, days=30, weeks=8):
    """-> {days, incidents: {...}, mtta/mttr par site / rôle / sévérité, by_root, false_positives, coverage, weekly}"""
    now = now or _dt.datetime.now(_dt.timezone.utc)
    since = now - _dt.timedelta(days=days)
    tta = {"site": defaultdict(list), "role": defaultdict(list), "severity": defaultdict(list), "all": []}
    ttr = {"site": defaultdict(list), "role": defaultdict(list), "severity": defaultdict(list), "all": []}
    by_root, by_sev = defaultdict(int), defaultdict(int)
    open_ages, n, n_open, n_acked_open = [], 0, 0, 0
    weekly = defaultdict(lambda: {"opened": 0, "closed": 0, "critical": 0})
    for i in incidents or []:
        o = parse_ts(i.get("opened_at"))
        if not o:
            continue
        wk = o.strftime("%G-W%V")
        if (now - o).days <= weeks * 7:
            weekly[wk]["opened"] += 1
            if i.get("severity") == "critical":
                weekly[wk]["critical"] += 1
            if i.get("closed_at"):
                weekly[wk]["closed"] += 1
        if o < since:
            continue
        n += 1
        root = entities_by_key.get(i.get("root")) or {}
        site, role, sev = root.get("site") or "(sans site)", roles.get(i.get("root")) or "(sans rôle)", i.get("severity") or "info"
        by_root[i.get("root") or "?"] += 1
        by_sev[sev] += 1
        a, c = parse_ts(i.get("acked_at")), parse_ts(i.get("closed_at"))
        if a and a >= o:
            d = (a - o).total_seconds()
            tta["site"][site].append(d); tta["role"][role].append(d); tta["severity"][sev].append(d); tta["all"].append(d)
        if c and c >= o:
            d = (c - o).total_seconds()
            ttr["site"][site].append(d); ttr["role"][role].append(d); ttr["severity"][sev].append(d); ttr["all"].append(d)
        if i.get("state") in ("open", "acked"):
            n_open += 1
            open_ages.append((now - o).total_seconds())
            if i.get("state") == "acked":
                n_acked_open += 1
    fmt = lambda d: {k: _mean_p(v) for k, v in d.items()}  # noqa: E731
    # faux positifs : par règle (annonces jugées) et par principe (retours)
    fp_rules = []
    for r in rules or []:
        h, m = r.get("hits") or 0, r.get("misses") or 0
        if h + m:
            fp_rules.append({"rule": r.get("id") or "%s=>%s" % (r["a"], r["b"]), "hits": h, "misses": m, "false_rate": round(m / (h + m), 3), "state": r.get("state")})
    fp_rules.sort(key=lambda x: -x["false_rate"])
    fp_principles = []
    for pid, fc in (feedback_counts or {}).items():
        c_, r_ = fc.get("confirmed", 0), fc.get("rejected", 0)
        if c_ + r_:
            fp_principles.append({"principle": pid, "confirmed": c_, "rejected": r_, "false_rate": round(r_ / (c_ + r_), 3)})
    fp_principles.sort(key=lambda x: -x["false_rate"])
    # couverture
    ents = list(entities_by_key.values())
    sup_sources = {"si-agent", "netprobe", "ups", "vigilance", "snmp", "orchestrator"}
    unsupervised = [e["key"] for e in ents if not any((o.get("source") in sup_sources) for o in e.get("origins") or [])]
    unpositioned = [e["key"] for e in ents if e["key"] not in (positions or {}) or (positions or {}).get(e["key"], {}).get("principle") == "pos-fallback"]
    sites_all = {e.get("site") for e in ents if e.get("site")}
    sites_pos = {e.get("site") for e in ents if e.get("site") and (positions or {}).get(e["key"], {}).get("principle") not in (None, "pos-fallback")}
    return {"days": days, "generated_at": iso(now),
            "incidents": {"total": n, "open": n_open, "acked_open": n_acked_open, "by_severity": dict(by_sev),
                          "open_age": _mean_p(open_ages), "acked_rate": round(len(tta["all"]) / n, 3) if n else None, "closed_rate": round(len(ttr["all"]) / n, 3) if n else None},
            "mtta": {"all": _mean_p(tta["all"]), "by_site": fmt(tta["site"]), "by_role": fmt(tta["role"]), "by_severity": fmt(tta["severity"])},
            "mttr": {"all": _mean_p(ttr["all"]), "by_site": fmt(ttr["site"]), "by_role": fmt(ttr["role"]), "by_severity": fmt(ttr["severity"])},
            "by_root": sorted(({"root": k, "name": (entities_by_key.get(k) or {}).get("name") or k, "role": roles.get(k), "count": v} for k, v in by_root.items()), key=lambda x: -x["count"])[:15],
            "false_positives": {"rules": fp_rules[:20], "principles": fp_principles},
            "coverage": {"entities": len(ents), "unsupervised": len(unsupervised), "unsupervised_keys": unsupervised[:50], "unpositioned": len(unpositioned),
                         "sites": len(sites_all), "sites_without_position": sorted(sites_all - sites_pos)},
            "weekly": [dict(week=k, **v) for k, v in sorted(weekly.items())]}


def humanize_s(s):
    if s is None:
        return "—"
    s = int(s)
    if s < 90:
        return "%d s" % s
    if s < 5400:
        return "%d min" % round(s / 60)
    if s < 2 * 86400:
        return "%.1f h" % (s / 3600)
    return "%.1f j" % (s / 86400)


# ---------------------------------------------------------------- tuiles d'origine
SOURCE_VIEW = {"si-agent": "si-agent", "vigilance": "vigilance", "ups": "ups", "netprobe": "netprobe", "network-agent": "network-agent",
               "netmap-orchestrator": "netmap-orchestrator", "backup-restore": "backup-restore", "classifier": "classifier", "nebula": "nebula", "ipam": "ipam"}


def origin_views(incident, events_by_fp=None):
    """Tuiles d'origine d'un incident : d'après ses sources (et celles de ses événements)."""
    srcs = set(incident.get("sources") or [])
    for fp in incident.get("events") or []:
        e = (events_by_fp or {}).get(fp)
        if e and e.get("source"):
            srcs.add(e["source"])
    return [{"source": s, "view": SOURCE_VIEW[s]} for s in sorted(srcs) if s in SOURCE_VIEW]
