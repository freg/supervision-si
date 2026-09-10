# -*- coding: utf-8 -*-
"""Corrélation de Cortex (livraison #462) -- logique PURE : à partir des
événements OUVERTS (normalisés), des relations et des entités, construit
des INCIDENTS : regroupement par fenêtre glissante + relation partagée
(principe window-cluster), regroupement faible par site (site-cluster),
cause racine = entité la plus en amont (upstream-first). Chaque incident
porte ses HYPOTHÈSES, chacune avec sa confiance, ses preuves et le principe
appliqué -- rien n'est affirmé sans dire pourquoi.
"""
import datetime as _dt
from collections import defaultdict

from principles import evaluate

SEV_ORDER = {"critical": 3, "warning": 2, "info": 1}
# poids « amont » d'une relation orientée a -> b (a est en amont de b)
UPSTREAM = {"gateway_of": 1.0, "powers_site": 0.6, "powers": 0.9, "serves": 0.7, "watches": 0.0, "flow": 0.0, "neighbor": 0.0, "talks_to": 0.0}


def parse_ts(s):
    if not s:
        return None
    try:
        d = _dt.datetime.fromisoformat(str(s).replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=_dt.timezone.utc)
    except ValueError:
        return None


def _site_key(site):
    return "site:" + site.strip().lower() if site else None


def _adjacency(relations, entities):
    """Voisinage non orienté pour le regroupement + entités « amont » orientées."""
    adj, up = defaultdict(set), defaultdict(float)
    site_of = {e["key"]: e.get("site") for e in entities}
    for r in relations:
        a, b = r["a"], r["b"]
        adj[a].add(b); adj[b].add(a)
        if r["kind"] == "powers_site":
            # l'onduleur est en amont de toutes les entités de son site
            for k, s in site_of.items():
                if s and _site_key(s) == b and k != a:
                    adj[a].add(k); adj[k].add(a)
                    up[(a, k)] = max(up[(a, k)], UPSTREAM["powers_site"] * r.get("weight", 1))
        elif UPSTREAM.get(r["kind"], 0) > 0:
            up[(a, b)] = max(up[(a, b)], UPSTREAM[r["kind"]] * r.get("weight", 1))
    return adj, up, site_of


def build_incidents(events, relations, entities, window_s=300, feedback=None, now=None):
    """-> [incident] ; incident = {key, severity, opened_at, last_at, entities, events:[fingerprints],
    root, title, confidence, hypotheses:[{claim, confidence, principle, evidence}], weak}"""
    now = now or _dt.datetime.now(_dt.timezone.utc)
    evs = [e for e in events if e.get("state", "open") == "open"]
    if not evs:
        return []
    adj, up, site_of = _adjacency(relations, entities)
    names = {e["key"]: (e.get("name") or e.get("ip") or e["key"]) for e in entities}
    kinds = {e["key"]: e.get("kind") for e in entities}
    # 1. union-find sur les événements : même entité, ou entités reliées, dans la fenêtre
    parent = {e["fingerprint"]: e["fingerprint"] for e in evs}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        parent[find(a)] = find(b)

    linkage = {}   # fingerprint pair -> principe utilisé
    evs_sorted = sorted(evs, key=lambda e: e.get("last_at") or e.get("at") or "")
    for i, a in enumerate(evs_sorted):
        ta = parse_ts(a.get("last_at") or a.get("at"))
        for b in evs_sorted[i + 1:]:
            tb = parse_ts(b.get("last_at") or b.get("at"))
            ea, eb = a.get("entity"), b.get("entity")
            if not ea or not eb:
                continue
            if ea == eb and ta and tb and abs((tb - ta).total_seconds()) > window_s:
                # même entité hors fenêtre : regroupés quand même (identité), l'incident vit tant que l'entité a des événements ouverts
                union(a["fingerprint"], b["fingerprint"]); linkage[(a["fingerprint"], b["fingerprint"])] = "identity-ip"
                continue
            if ta and tb and abs((tb - ta).total_seconds()) > window_s:
                continue
            if ea == eb:
                union(a["fingerprint"], b["fingerprint"]); linkage[(a["fingerprint"], b["fingerprint"])] = "identity-ip"
            elif eb in adj.get(ea, ()):
                union(a["fingerprint"], b["fingerprint"]); linkage[(a["fingerprint"], b["fingerprint"])] = "window-cluster"
            else:
                sa, sb = a.get("site") or site_of.get(ea), b.get("site") or site_of.get(eb)
                if sa and sb and sa.strip().lower() == sb.strip().lower():
                    union(a["fingerprint"], b["fingerprint"]); linkage[(a["fingerprint"], b["fingerprint"])] = "site-cluster"
    groups = defaultdict(list)
    for e in evs:
        groups[find(e["fingerprint"])].append(e)
    # 2. un incident par groupe
    out = []
    for gid, members in groups.items():
        ents = sorted({m["entity"] for m in members if m.get("entity")})
        fps = {m["fingerprint"] for m in members}
        principles_used = {p for (x, y), p in linkage.items() if x in fps and y in fps}
        weak = principles_used <= {"site-cluster"} and len(ents) > 1
        sev = max(members, key=lambda m: SEV_ORDER.get(m.get("severity"), 0)).get("severity", "info")
        opened = min((m.get("at") or "" for m in members), default="")
        last = max((m.get("last_at") or m.get("at") or "" for m in members), default="")
        hyps = []
        # cause racine : entité la plus en amont des autres du groupe
        if len(ents) == 1:
            root = ents[0]
            p = evaluate("single-event", feedback)
            hyps.append({"claim": "%s est la seule entité concernée" % names.get(root, root), "confidence": p["effective"], "principle": "single-event",
                         "evidence": ["%d événement(s)" % len(members)]})
        else:
            scores = {}
            for e in ents:
                s = sum(up.get((e, o), 0.0) for o in ents if o != e)
                if s > 0:
                    scores[e] = s
            if scores:
                root = max(scores, key=scores.get)
                p = evaluate("upstream-first", feedback)
                downstream = [names.get(o, o) for o in ents if up.get((root, o), 0) > 0]
                conf = round(p["effective"] * min(1.0, scores[root] / max(1, len(ents) - 1)), 2)
                hyps.append({"claim": "%s (%s) est en amont de %d entité(s) touchée(s) : cause racine probable" % (names.get(root, root), kinds.get(root, "?"), len(downstream)),
                             "confidence": conf, "principle": "upstream-first", "evidence": ["en amont de : " + ", ".join(downstream[:8])]})
                others = [e for e in ents if e != root and e not in [o for o in ents if up.get((root, o), 0) > 0]]
                if others:
                    hyps.append({"claim": "%d entité(s) regroupée(s) sans dépendance connue vers la cause" % len(others), "confidence": round(evaluate("site-cluster", feedback)["effective"], 2),
                                 "principle": "site-cluster", "evidence": [names.get(o, o) for o in others[:8]]})
            else:
                root = max(ents, key=lambda e: sum(SEV_ORDER.get(m.get("severity"), 0) for m in members if m.get("entity") == e))
                p = evaluate("site-cluster" if weak else "window-cluster", feedback)
                hyps.append({"claim": "aucune dépendance connue entre les %d entités : regroupement %s, cause non désignée" % (len(ents), "par site (faible)" if weak else "par proximité"),
                             "confidence": round(p["effective"] * 0.5, 2), "principle": p["id"], "evidence": [names.get(e, e) for e in ents[:8]]})
        for pid in principles_used:
            if pid in ("window-cluster", "site-cluster") and not any(h["principle"] == pid for h in hyps):
                p = evaluate(pid, feedback)
                hyps.append({"claim": p["title"], "confidence": p["effective"], "principle": pid, "evidence": ["%d événements en %d s" % (len(members), window_s)]})
        sev_p = evaluate("severity-max", feedback)
        hyps.append({"claim": "sévérité %s = pire événement du groupe" % sev, "confidence": sev_p["effective"], "principle": "severity-max", "evidence": []})
        title = "%s — %s" % (names.get(root, root), "; ".join(sorted({m.get("kind", "?") for m in members}))[:120])
        out.append({"key": "inc:" + min(fps), "severity": sev, "opened_at": opened, "last_at": last, "entities": ents, "events": sorted(fps),
                    "root": root, "title": title,
                    # la confiance de l'incident est celle de son hypothèse CAUSALE (la première émise), jamais un maximum flatteur
                    "confidence": next((h["confidence"] for h in hyps if h["principle"] in ("upstream-first", "single-event", "window-cluster", "site-cluster")), 0.5),
                    "hypotheses": hyps, "weak": weak, "sources": sorted({m.get("source") for m in members})})
    out.sort(key=lambda i: (-SEV_ORDER.get(i["severity"], 0), i["last_at"]), reverse=False)
    out.sort(key=lambda i: -SEV_ORDER.get(i["severity"], 0))
    return out


def stats(events, incidents, feedback=None, days=7, now=None):
    """Statistiques descriptives : par source, par sévérité, par jour, entités bruyantes, principes."""
    now = now or _dt.datetime.now(_dt.timezone.utc)
    since = now - _dt.timedelta(days=days)
    by_source, by_sev, by_day, noisy = defaultdict(int), defaultdict(int), defaultdict(int), defaultdict(int)
    for e in events:
        t = parse_ts(e.get("first_at") or e.get("at"))
        if t and t < since:
            continue
        by_source[e.get("source")] += 1
        by_sev[e.get("severity")] += 1
        noisy[e.get("entity")] += e.get("count") or 1
        if t:
            by_day[t.strftime("%Y-%m-%d")] += 1
    open_inc = [i for i in incidents if i.get("state", "open") == "open"]
    return {"days": days, "events_by_source": dict(by_source), "events_by_severity": dict(by_sev), "events_by_day": dict(sorted(by_day.items())),
            "noisy_entities": sorted(({"entity": k, "count": v} for k, v in noisy.items()), key=lambda x: -x["count"])[:10],
            "incidents_open": len(open_inc), "incidents_weak": sum(1 for i in open_inc if i.get("weak")),
            "incidents_by_severity": {s: sum(1 for i in open_inc if i.get("severity") == s) for s in ("critical", "warning", "info")}}
