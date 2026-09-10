# -*- coding: utf-8 -*-
"""Cortex, étape 4 (livraison #465) : CAUSALITÉ APPRISE et ANTICIPATION,
signaux faibles -- logique pure, rien ne lit le réseau.

1. Séquences apprises (`mine_sequences`) : dans l'historique des
   occurrences d'événements, les paires « A précède B en moins de N min »
   plus fréquentes que le hasard deviennent des RÈGLES PROPOSÉES, avec
   support, confiance (B suit A dans x cas sur n), délai typique (médiane)
   et attendu sous indépendance. Une règle est proposée tant qu'une
   personne ne l'a pas confirmée ou rejetée (principes `sequence-learned`,
   `sequence-confirmed`).
2. Anticipation (`anticipate`) : quand A est ouvert et qu'une règle A → B
   existe, Cortex annonce « B suit habituellement dans 4 min (12 fois sur
   15) » ; l'annonce est ensuite jugée (`settle_predictions`) : B est venu
   (juste) ou non (fausse) -- ce qui mesure la règle.
3. Signaux faibles (`detect_drifts`) : sur les mesures relevées (CPU,
   mémoire, disque, charge, latence, tension, batterie…), écart de la
   dernière heure au regard des 24 h précédentes (z-score), tendance
   linéaire vers un seuil (« à ce rythme, 90 % dans 3 j »), et écart au même
   créneau horaire des jours précédents (saisonnalité simple).

Signature d'une occurrence : « source:type@entité » (règle spécifique) et
« source:type@rôle:<rôle> » (règle généralisée, quand le rôle est connu).
"""
import datetime as _dt
import json
import math
import statistics
from collections import defaultdict


def parse_ts(s):
    if not s:
        return None
    try:
        return _dt.datetime.strptime(str(s)[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=_dt.timezone.utc)
    except ValueError:
        return None


def iso(t):
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------- signatures
def signature(occ, roles=None, generalized=False):
    """occ: {source, kind, entity} ; roles: {entité: rôle dominant}."""
    base = "%s:%s" % (occ.get("source"), occ.get("kind"))
    if generalized:
        r = (roles or {}).get(occ.get("entity"))
        return "%s@role:%s" % (base, r) if r else None
    return "%s@%s" % (base, occ.get("entity"))


def describe_signature(sig, names=None):
    names = names or {}
    src_kind, _, who = sig.partition("@")
    if who.startswith("role:"):
        return "%s sur un(e) %s" % (src_kind.split(":", 1)[-1], who[5:])
    return "%s sur %s" % (src_kind.split(":", 1)[-1], names.get(who, who))


# ---------------------------------------------------------------- séquences
def mine_sequences(occurrences, roles=None, window_s=600, min_support=3, min_confidence=0.5, min_lift=2.0, now=None):
    """occurrences: [{fingerprint, source, kind, entity, at}] (historique).
    -> [règle] ; règle = {a, b, count, support_a, support_b, confidence,
    expected, lift, delay_s (médiane), delays, first_at, last_at, scope}
    scope = 'entity' (A et B nommés) ou 'role' (généralisé par rôle)."""
    occs = [dict(o, t=parse_ts(o.get("at"))) for o in occurrences or []]
    occs = [o for o in occs if o["t"]]
    if len(occs) < 2:
        return []
    occs.sort(key=lambda o: o["t"])
    span_s = max(window_s, (occs[-1]["t"] - occs[0]["t"]).total_seconds())
    rules = []
    for generalized in (False, True):
        sig = [signature(o, roles, generalized) for o in occs]
        support = defaultdict(int)
        for s in sig:
            if s:
                support[s] += 1
        pairs, delays, first, last = defaultdict(int), defaultdict(list), {}, {}
        for i, a in enumerate(occs):
            sa = sig[i]
            if not sa:
                continue
            seen_b = set()
            for j in range(i + 1, len(occs)):
                d = (occs[j]["t"] - a["t"]).total_seconds()
                if d > window_s:
                    break
                sb = sig[j]
                if not sb or sb == sa or sb in seen_b:
                    continue
                if generalized and occs[j].get("entity") == a.get("entity"):
                    continue     # généralisé : on cherche la propagation entre entités, pas le même hôte
                seen_b.add(sb)
                pairs[(sa, sb)] += 1
                delays[(sa, sb)].append(d)
                first.setdefault((sa, sb), a["t"]); last[(sa, sb)] = a["t"]
        for (sa, sb), n in pairs.items():
            if n < min_support:
                continue
            conf = n / support[sa]
            expected = support[sa] * support[sb] * window_s / span_s
            lift = n / expected if expected > 0 else float("inf")
            if conf < min_confidence or lift < min_lift:
                continue
            rules.append({"a": sa, "b": sb, "count": n, "support_a": support[sa], "support_b": support[sb], "confidence": round(conf, 3),
                          "expected": round(expected, 2), "lift": round(min(lift, 999.0), 2), "delay_s": int(statistics.median(delays[(sa, sb)])),
                          "delay_min_s": int(min(delays[(sa, sb)])), "delay_max_s": int(max(delays[(sa, sb)])),
                          "first_at": iso(first[(sa, sb)]), "last_at": iso(last[(sa, sb)]), "scope": "role" if generalized else "entity",
                          "principle": "sequence-learned"})
    rules.sort(key=lambda r: (-r["count"] * r["confidence"], r["a"]))
    return rules


def rule_id(rule):
    return "%s=>%s" % (rule["a"], rule["b"])


def rule_confidence(rule, principle_effective):
    """Confiance affichée d'une règle : confiance observée × principe
    (appris 0,6 ; confirmé 0,9 ; rejeté 0) ; ajustée par les annonces jugées."""
    hits, misses = rule.get("hits") or 0, rule.get("misses") or 0
    obs = rule["confidence"]
    if hits + misses >= 3:
        obs = (obs * 3 + hits) / (3 + hits + misses)
    return round(obs * principle_effective, 3)


# ---------------------------------------------------------------- anticipation
def anticipate(open_events, rules, roles=None, names=None, now=None, principle_eff=None):
    """open_events: événements ouverts {fingerprint, source, kind, entity, at, first_at, site} ;
    rules: règles non rejetées (avec hits/misses). -> [annonce] ;
    annonce = {rule_id, trigger (empreinte), entity, expected_kind, expected_at, message, confidence, principle, scope}."""
    now = now or _dt.datetime.now(_dt.timezone.utc)
    names = names or {}
    eff = principle_eff or {}
    by_a = defaultdict(list)
    for r in rules or []:
        if r.get("state") == "rejected":
            continue
        by_a[r["a"]].append(r)
    present = set()
    for e in open_events or []:
        present.add(signature(e, roles, False))
        g = signature(e, roles, True)
        if g:
            present.add(g)
    out = []
    for e in open_events or []:
        t = parse_ts(e.get("first_at") or e.get("at"))
        if not t:
            continue
        for generalized in (False, True):
            sa = signature(e, roles, generalized)
            for r in by_a.get(sa, []):
                if r["b"] in present:
                    continue          # B est déjà là : rien à annoncer
                expected_at = t + _dt.timedelta(seconds=r["delay_s"])
                if now > expected_at + _dt.timedelta(seconds=max(r.get("delay_max_s", r["delay_s"]), 60) * 2):
                    continue          # trop tard pour annoncer
                pid = "sequence-confirmed" if r.get("state") == "confirmed" else "sequence-learned"
                conf = rule_confidence(r, eff.get(pid, 0.9 if r.get("state") == "confirmed" else 0.6))
                b_txt = describe_signature(r["b"], names)
                mins = max(1, int(round(r["delay_s"] / 60.0)))
                out.append({"rule_id": rule_id(r), "trigger": e["fingerprint"], "entity": e.get("entity"), "site": e.get("site"),
                            "expected": r["b"], "expected_at": iso(expected_at), "since": iso(t), "scope": r["scope"],
                            "message": "%s suit habituellement %s dans %d min (%d fois sur %d)" % (b_txt, describe_signature(sa, names), mins, r["count"], r["support_a"]),
                            "confidence": conf, "principle": "anticipation", "rule_principle": pid})
    # une seule annonce par B attendu (le déclencheur le plus sûr)
    best = {}
    for p in out:
        cur = best.get(p["expected"])
        if not cur or p["confidence"] > cur["confidence"]:
            best[p["expected"]] = p
    out = sorted(best.values(), key=lambda p: -p["confidence"])
    return out


def settle_predictions(pending, occurrences, now=None, grace_factor=2.0):
    """Juge les annonces en attente : B est survenu après l'annonce (hit)
    ou le délai maximal × 2 est dépassé sans B (miss). pending:
    [{id, rule_id, expected (signature), since, expected_at, delay_max_s, entity, scope}] ;
    occurrences récentes : [{source, kind, entity, at}] ; roles pour la
    signature généralisée passés dans chaque annonce (`roles`).
    -> [{id, outcome: hit|miss, at}]"""
    now = now or _dt.datetime.now(_dt.timezone.utc)
    out = []
    occs = [dict(o, t=parse_ts(o.get("at"))) for o in occurrences or []]
    for p in pending or []:
        since, exp = parse_ts(p.get("since")), parse_ts(p.get("expected_at"))
        if not since or not exp:
            continue
        roles = p.get("roles") or {}
        hit = None
        for o in occs:
            if not o["t"] or o["t"] < since:
                continue
            if p["scope"] == "role" and o.get("entity") == p.get("entity"):
                continue
            s = signature(o, roles, p["scope"] == "role")
            if s == p["expected"]:
                hit = o["t"]
                break
        if hit:
            out.append({"id": p["id"], "outcome": "hit", "at": iso(hit)})
        elif now > exp + _dt.timedelta(seconds=max(p.get("delay_max_s") or 0, 60) * grace_factor):
            out.append({"id": p["id"], "outcome": "miss", "at": iso(now)})
    return out


# ---------------------------------------------------------------- mesures
METRICS = {
    "cpu_percent": {"label": "CPU", "unit": "%", "max": 100, "threshold": 90, "direction": "up"},
    "memory_percent": {"label": "mémoire", "unit": "%", "max": 100, "threshold": 90, "direction": "up"},
    "disk_max_percent": {"label": "disque (partition la plus pleine)", "unit": "%", "max": 100, "threshold": 90, "direction": "up"},
    "load5": {"label": "charge 5 min", "unit": "", "threshold": None, "direction": "up"},
    "latency_ms": {"label": "latence", "unit": "ms", "threshold": None, "direction": "up"},
    "packet_loss_percent": {"label": "pertes", "unit": "%", "max": 100, "threshold": 20, "direction": "up"},
    "output_load": {"label": "charge onduleur", "unit": "%", "max": 100, "threshold": 80, "direction": "up"},
    "battery_capacity": {"label": "batterie", "unit": "%", "max": 100, "threshold": 30, "direction": "down"},
    "input_voltage": {"label": "tension d'entrée", "unit": "V", "threshold": None, "direction": "any"},
    "output_voltage": {"label": "tension de sortie", "unit": "V", "threshold": None, "direction": "any"},
    "bytes_total": {"label": "volume échangé", "unit": "o", "threshold": None, "direction": "any"},
}


def samples_from_si_agent(fleet, key_of):
    out = []
    for a in fleet or []:
        k = key_of(a)
        s = a.get("summary") or {}
        if not k or not s:
            continue
        at = s.get("host_at") or a.get("last_seen_at")
        for m in ("cpu_percent", "memory_percent", "disk_max_percent", "load5"):
            if isinstance(s.get(m), (int, float)):
                out.append({"entity": k, "metric": m, "at": at, "value": float(s[m])})
    return out


def samples_from_netprobe(targets, latest, key_of):
    out = []
    by_id = {t.get("id"): key_of(t) for t in targets or []}
    for s in latest or []:
        k = by_id.get(s.get("target_id"))
        if not k:
            continue
        for m in ("latency_ms", "packet_loss_percent"):
            if isinstance(s.get(m), (int, float)):
                out.append({"entity": k, "metric": m, "at": s.get("sampled_at"), "value": float(s[m])})
    return out


def samples_from_ups(devices, key_of):
    out = []
    for d in devices or []:
        k = key_of(d)
        if not k:
            continue
        summ = d.get("last_summary")
        if isinstance(summ, str):
            try:
                summ = json.loads(summ)
            except ValueError:
                summ = {}
        summ = summ or {}
        for m in ("output_load", "battery_capacity", "input_voltage", "output_voltage"):
            v = summ.get(m, d.get(m))
            if isinstance(v, (int, float)):
                out.append({"entity": k, "metric": m, "at": d.get("last_polled_at"), "value": float(v)})
    return out


# ---------------------------------------------------------------- dérives
def _linreg(points):
    """points: [(x_s, y)] -> (slope per second, intercept)"""
    n = len(points)
    if n < 2:
        return 0.0, points[0][1] if points else 0.0
    mx = sum(p[0] for p in points) / n
    my = sum(p[1] for p in points) / n
    sxx = sum((p[0] - mx) ** 2 for p in points)
    if sxx == 0:
        return 0.0, my
    slope = sum((p[0] - mx) * (p[1] - my) for p in points) / sxx
    return slope, my - slope * mx


def detect_drifts(series, now=None, recent_s=3600, baseline_s=86400, min_points=6, z_warn=3.0, z_crit=5.0, eta_warn_s=7 * 86400):
    """series: {(entité, métrique): [(at ISO, valeur)]} -> [dérive] ;
    dérive = {entity, metric, kind: zscore|trend|season, severity, value, baseline, z,
    slope_per_h, eta_s, message, principle, evidence}. Une série n'émet
    au plus qu'une dérive par genre."""
    now = now or _dt.datetime.now(_dt.timezone.utc)
    out = []
    for (entity, metric), pts in (series or {}).items():
        meta = METRICS.get(metric, {"label": metric, "unit": "", "threshold": None, "direction": "any"})
        pts = sorted(((parse_ts(a), v) for a, v in pts if parse_ts(a) and isinstance(v, (int, float))), key=lambda p: p[0])
        pts = [(t, float(v)) for t, v in pts if (now - t).total_seconds() <= baseline_s + recent_s]
        if len(pts) < min_points:
            continue
        recent = [v for t, v in pts if (now - t).total_seconds() <= recent_s]
        base = [v for t, v in pts if (now - t).total_seconds() > recent_s]
        label = "%s %s" % (meta["label"], entity)
        unit = meta.get("unit", "")
        # 1. écart de la dernière heure au regard de la base
        if len(recent) >= 2 and len(base) >= 4:
            bm = statistics.mean(base)
            bs = statistics.pstdev(base) or (abs(bm) * 0.02) or 0.5
            rm = statistics.mean(recent)
            z = (rm - bm) / bs
            direction = meta.get("direction", "any")
            worrying = abs(z) >= z_warn and (direction == "any" or (direction == "up" and z > 0) or (direction == "down" and z < 0))
            if worrying:
                out.append({"entity": entity, "metric": metric, "kind": "zscore", "severity": "warning" if abs(z) < z_crit else "critical",
                            "value": round(rm, 2), "baseline": round(bm, 2), "z": round(z, 1), "principle": "drift-zscore",
                            "message": "%s : %.1f%s sur la dernière heure contre %.1f%s en moyenne sur 24 h (écart %.1f σ)" % (label, rm, unit, bm, unit, z),
                            "evidence": "%d relevés récents, %d de base" % (len(recent), len(base))})
        # 2. tendance vers un seuil
        thr = meta.get("threshold")
        stepped = any(d["entity"] == entity and d["metric"] == metric and d["kind"] == "zscore" for d in out)
        if thr is not None and len(pts) >= min_points and not stepped:   # un saut brutal n'est pas une tendance : le z-score suffit
            x0 = pts[0][0]
            slope, icpt = _linreg([((t - x0).total_seconds(), v) for t, v in pts])
            last = pts[-1][1]
            per_h = slope * 3600
            direction = meta.get("direction", "up")
            going = (direction == "up" and slope > 0 and last < thr) or (direction == "down" and slope < 0 and last > thr)
            if going and abs(per_h) > 1e-6:
                eta = (thr - last) / slope
                if 0 < eta <= eta_warn_s:
                    days = eta / 86400
                    when = "%.0f h" % (eta / 3600) if eta < 2 * 86400 else "%.1f j" % days
                    out.append({"entity": entity, "metric": metric, "kind": "trend", "severity": "warning" if eta > 86400 else "critical",
                                "value": round(last, 2), "baseline": thr, "slope_per_h": round(per_h, 3), "eta_s": int(eta), "principle": "drift-trend",
                                "message": "%s : %.1f%s, %+.2f%s/h — à ce rythme le seuil de %s%s est atteint dans %s" % (label, last, unit, per_h, unit, thr, unit, when),
                                "evidence": "régression linéaire sur %d relevés (%s)" % (len(pts), iso(x0))})
        # 3. saisonnalité simple : même heure les jours précédents
        if len(recent) >= 2:
            hour = now.hour
            same = [v for t, v in pts if (now - t).total_seconds() > recent_s and abs(((t.hour - hour + 12) % 24) - 12) <= 1]
            if len(same) >= 4:
                sm = statistics.mean(same)
                ss = statistics.pstdev(same) or (abs(sm) * 0.02) or 0.5
                rm = statistics.mean(recent)
                z = (rm - sm) / ss
                if abs(z) >= z_warn and not any(d["entity"] == entity and d["metric"] == metric and d["kind"] == "zscore" for d in out):
                    out.append({"entity": entity, "metric": metric, "kind": "season", "severity": "info" if abs(z) < z_crit else "warning",
                                "value": round(rm, 2), "baseline": round(sm, 2), "z": round(z, 1), "principle": "seasonality",
                                "message": "%s : %.1f%s, inhabituel pour ce créneau horaire (%.1f%s d'ordinaire, écart %.1f σ)" % (label, rm, unit, sm, unit, z),
                                "evidence": "%d relevés au même créneau ±1 h" % len(same)})
    out.sort(key=lambda d: ({"critical": 0, "warning": 1, "info": 2}.get(d["severity"], 3), d["entity"]))
    return out


def drift_events(drifts, sites=None):
    """Les dérives deviennent des événements normalisés de source « cortex »
    (empreinte par entité / métrique / genre) : même cycle de vie que les
    autres, donc regroupables en incidents et fermées quand elles cessent."""
    import hashlib
    sites = sites or {}
    out = []
    for d in drifts:
        fp = "cortex:" + hashlib.sha1(("drift|%s|%s|%s" % (d["entity"], d["metric"], d["kind"])).encode("utf-8")).hexdigest()[:16]
        out.append({"fingerprint": fp, "at": None, "source": "cortex", "kind": "drift:%s:%s" % (d["metric"], d["kind"]), "severity": d["severity"],
                    "entity": d["entity"], "site": sites.get(d["entity"]), "message": d["message"], "raw_ref": "cortex:drift:%s" % d["principle"]})
    return out
