# -*- coding: utf-8 -*-
"""#756 : synthèses pour la tuile Parc IA -- rapports d'évaluation (un par passage) et activité du journal par jour."""
import json


def eval_summary(report, name=""):
    res = report.get("results") or []
    checks = [c for r in res for c in (r.get("checks") or [])]
    return {"name": name, "at": report.get("at"), "model": report.get("model"), "base_url": report.get("base_url"), "cases": report.get("cases"),
            "score": report.get("score"), "tok_s_avg": report.get("tok_s_avg"), "tok_s_min": report.get("tok_s_min"), "total_s": report.get("total_s"),
            "by_kind": {k: {"n": v.get("n"), "score": v.get("score"), "errors": v.get("errors")} for k, v in (report.get("by_kind") or {}).items()},
            "criteria_ok": sum(1 for c in checks if c.get("ok")) if checks else None, "criteria": len(checks) if checks else None,
            "errors": sum(1 for r in res if r.get("error"))}


def journal_stats(lines, since_day=""):
    """Lignes JSON du journal -> [{day, n, errors, ms_avg, tok_s_avg, by_kind: {kind: n}}] du plus ancien au plus récent."""
    days = {}
    for line in lines:
        try:
            e = json.loads(line)
        except ValueError:
            continue
        day = str(e.get("at") or "")[:10]
        if not day or day < since_day:
            continue
        d = days.setdefault(day, {"day": day, "n": 0, "errors": 0, "_ms": [], "_tok": [], "by_kind": {}})
        d["n"] += 1
        d["errors"] += 1 if e.get("error") else 0
        if isinstance(e.get("ms"), (int, float)):
            d["_ms"].append(e["ms"])
        if isinstance(e.get("tok_s"), (int, float)):
            d["_tok"].append(e["tok_s"])
        k = e.get("kind") or "?"
        d["by_kind"][k] = d["by_kind"].get(k, 0) + 1
    out = []
    for day in sorted(days):
        d = days[day]
        ms, tok = d.pop("_ms"), d.pop("_tok")
        d["ms_avg"] = round(sum(ms) / len(ms)) if ms else None
        d["tok_s_avg"] = round(sum(tok) / len(tok), 1) if tok else None
        out.append(d)
    return out
