# -*- coding: utf-8 -*-
"""#753 : vues de parc paramétrables -- listes d'agents organisées en groupes (« Serveurs », « Postes », « Serveurs
d'IA », « Postes personnels », ou toute autre vue), avec pour chaque agent l'en-tête de htop (CPU, charge, mémoire,
swap, disques, uptime, services en échec, constats) et, s'il porte Ollama, ses modèles (chargés, part sur GPU).
Assemblage pur : la route lit la flotte et les dernières mesures, ce module les met en forme."""
import re

VIEW_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,39}$")
DEFAULT_VIEWS = [
    {"id": "serveurs", "label": "Serveurs", "groups": []},
    {"id": "postes", "label": "Postes", "groups": []},
    {"id": "ia", "label": "Serveurs d'IA", "groups": []},
    {"id": "perso", "label": "Postes personnels", "groups": []},
]


def normalize(views):
    """-> (vues, erreur). Chaque vue : id (minuscules, tirets), libellé, groupes [{name, agents: [ids], note}]."""
    if not isinstance(views, list) or not views or len(views) > 20:
        return None, "1 à 20 vues"
    out, ids = [], set()
    for i, v in enumerate(views, 1):
        if not isinstance(v, dict):
            return None, "vue %d : objet attendu" % i
        vid = str(v.get("id") or "").strip().lower()
        if not VIEW_ID.match(vid) or vid in ids:
            return None, "vue %d : identifiant (minuscules, chiffres, tirets) unique requis" % i
        ids.add(vid)
        label = str(v.get("label") or vid).strip()[:60]
        groups = []
        for j, g in enumerate(v.get("groups") or [], 1):
            if not isinstance(g, dict) or not str(g.get("name") or "").strip():
                return None, "vue %s, groupe %d : nom requis" % (vid, j)
            agents = [str(a) for a in (g.get("agents") or []) if re.match(r"^[A-Za-z0-9._-]{1,64}$", str(a))]
            groups.append({"name": str(g["name"]).strip()[:60], "agents": list(dict.fromkeys(agents))[:300], "note": str(g.get("note") or "")[:200]})
        if len(groups) > 40:
            return None, "vue %s : 40 groupes au plus" % vid
        out.append({"id": vid, "label": label, "groups": groups})
    return out, None


def _num(x):
    return x if isinstance(x, (int, float)) else None


def row(agent, latest):
    """Agent de la flotte + dernières mesures {task: mesure} -> ligne « htop »."""
    host = ((latest.get("host") or {}).get("data")) or {}
    sysd, cpu, mem = host.get("system") or {}, host.get("cpu") or {}, host.get("memory") or {}
    disks = [d for d in host.get("disks") or [] if d.get("visible", True) and d.get("used_percent") is not None]
    disks.sort(key=lambda d: -(d.get("used_percent") or 0))
    failed = (host.get("services") or {}).get("failed") or []
    r = {"agent_id": agent.get("agent_id"), "hostname": agent.get("hostname") or sysd.get("hostname"), "label": agent.get("label"),
         "site": agent.get("site"), "online": agent.get("online"), "last_seen": agent.get("last_seen_at"),
         "os": sysd.get("os") or agent.get("os"), "kernel": sysd.get("kernel"), "cpu_model": sysd.get("cpu_model"),
         "cpus": _num(sysd.get("cpus")), "uptime_s": _num(sysd.get("uptime_seconds")),
         "cpu_pct": _num(cpu.get("percent")), "load1": _num(cpu.get("load1")), "load5": _num(cpu.get("load5")), "load15": _num(cpu.get("load15")),
         "mem_total": _num(mem.get("total_bytes")), "mem_pct": _num(mem.get("used_percent")),
         "swap_total": _num(mem.get("swap_total_bytes")), "swap_pct": _num(mem.get("swap_used_percent")),
         "disks": [{"mount": d.get("mount") or d.get("mountpoint") or d.get("device"), "pct": d.get("used_percent"), "total": d.get("total_bytes")} for d in disks[:8]],
         "disk_max_pct": disks[0]["used_percent"] if disks else None,
         "failed_services": len(failed) if isinstance(failed, list) else _num(failed),
         "risks": (agent.get("risks") or {}).get("counts") or {}, "risk_state": (agent.get("risks") or {}).get("state"),
         "version": agent.get("agent_version"), "host_at": (latest.get("host") or {}).get("at")}
    na = ((latest.get("plugin:node-activity") or {}).get("data")) or {}
    local = next((n for n in na.get("nodes") or [] if n.get("zone") == "local"), None)
    if local:                                     # #749 : relevé plus fin (cœurs, swap, débits) quand la sonde est active
        r["cores_pct"] = [c for c in local.get("cores_pct") or [] if c is not None]
        net = [n for n in local.get("net") or [] if not str(n.get("iface", "")).startswith(("lo", "veth", "tap", "fwbr", "fwpr", "fwln"))]
        r["net_rx_bps"] = sum(n.get("rx_bps") or 0 for n in net) if net else None
        r["net_tx_bps"] = sum(n.get("tx_bps") or 0 for n in net) if net else None
    ol = ((latest.get("plugin:ollama") or {}).get("data")) or {}
    if ol:
        models = ol.get("models") or []
        r["ollama"] = {"up": ol.get("up"), "version": ol.get("version"), "models": len(models), "loaded": [
            {"name": m.get("name"), "gpu_pct": m.get("gpu_pct"), "vram": m.get("vram"), "context": m.get("context")} for m in models if m.get("loaded")],
            "alerts": len(ol.get("alerts") or [])}
    return r


def _avg(xs):
    xs = [x for x in xs if isinstance(x, (int, float))]
    return round(sum(xs) / len(xs), 1) if xs else None


def group_totals(rows):
    return {"agents": len(rows), "online": sum(1 for r in rows if r.get("online") == "online"),
            "cpu_avg": _avg(r.get("cpu_pct") for r in rows), "mem_avg": _avg(r.get("mem_pct") for r in rows),
            "disk_max": max([r["disk_max_pct"] for r in rows if r.get("disk_max_pct") is not None] or [None]) if rows else None,
            "critical": sum(1 for r in rows if r.get("risk_state") == "critical" or r.get("online") == "offline"),
            "failed_services": sum(r.get("failed_services") or 0 for r in rows)}


def overview(view, rows_by_agent):
    """Vue + {agent_id: ligne} -> {view, groups: [{name, note, totals, rows, missing}], unassigned: [ids]}."""
    groups, used = [], set()
    for g in view["groups"]:
        rows = [rows_by_agent[a] for a in g["agents"] if a in rows_by_agent]
        used.update(g["agents"])
        groups.append({"name": g["name"], "note": g.get("note", ""), "totals": group_totals(rows), "rows": rows,
                       "missing": [a for a in g["agents"] if a not in rows_by_agent]})
    allrows = [r for g in groups for r in g["rows"]]
    return {"view": {"id": view["id"], "label": view["label"]}, "groups": groups, "totals": group_totals(allrows),
            "unassigned": sorted(a for a in rows_by_agent if a not in used)}
