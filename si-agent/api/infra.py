# -*- coding: utf-8 -*-
"""#749 : vue d'ensemble des Proxmox VE / PBS locaux et distants (tuile « Infra PVE / PBS ») -- assemblage PUR des
dernières mesures : plugin:node-activity (CPU, cœurs, mémoire, swap, tâches, partitions, ZFS, débits, connexions,
transferts), plugin:proxmox (VM locales), plugin:pve-remote (VM et stockages des nœuds distants), plugin:pbs
(datastores). Testé dans test_z_infra.py."""
import json


def latest(conn, task):
    """-> [(agent_id, hostname, at, data)] : dernière mesure `task` de chaque agent."""
    rows = conn.execute("SELECT a.agent_id, a.hostname, m.at, m.data FROM agents a JOIN (SELECT agent_id, MAX(at) AS at FROM measurements "
                        "WHERE task = ? GROUP BY agent_id) l ON l.agent_id = a.agent_id JOIN measurements m ON m.agent_id = l.agent_id "
                        "AND m.at = l.at AND m.task = ?", (task, task)).fetchall()
    out = []
    for r in rows:
        try:
            d = json.loads(r["data"]) if isinstance(r["data"], str) else (r["data"] or {})
        except (TypeError, ValueError):
            d = {}
        out.append((r["agent_id"], r["hostname"], r["at"], d or {}))
    return out


def _vm(node, g, zone):
    maxcpu = g.get("maxcpu")
    cpu = g.get("cpu")
    return {"node": node, "zone": zone, "vmid": g.get("vmid"), "name": g.get("name") or "", "type": g.get("type"), "status": g.get("status"),
            "cpu_pct": round(100.0 * cpu, 1) if isinstance(cpu, (int, float)) else None, "ncpu": maxcpu,
            "mem": g.get("mem"), "maxmem": g.get("maxmem"), "uptime_s": g.get("uptime_s", g.get("uptime"))}


def overview(activity, proxmox, remote, pbs):
    """Chaque argument : liste (agent_id, hostname, at, data) de `latest`. -> {nodes, vms, transfers, totals, alerts}."""
    nodes, vms, alerts = {}, [], []

    def node(name, **kw):
        n = nodes.setdefault(name, {"name": name, "zone": kw.get("zone", "local"), "role": "pve", "ok": True, "storages": [], "datastores": [],
                                    "guests": {"running": 0, "stopped": 0, "total": 0}, "collected_by": None, "at": None})
        for k, v in kw.items():
            if v is not None:
                n[k] = v
        return n

    for aid, host, at, d in activity:
        for x in d.get("nodes") or []:
            zone = "local" if x.get("zone") == "local" else "distant"
            n = node(x.get("name") or host, zone=zone, collected_by=aid, at=at)
            n.update({k: v for k, v in x.items() if k not in ("name", "zone")})
        alerts += [dict(a, agent_id=aid) for a in d.get("alerts") or []]
    for aid, host, at, d in proxmox:
        nm = (d.get("node") or {}).get("name") or host
        n = node(nm, zone="local")
        n["role"] = "pve"; n["storages"] = d.get("storages") or n["storages"]; n.setdefault("pveversion", (d.get("node") or {}).get("pveversion"))
        for g in d.get("vms") or []:
            if g.get("template"):
                continue
            vms.append(_vm(nm, g, "local"))
    for aid, host, at, d in remote:
        for x in d.get("nodes") or []:
            n = node(x.get("name"), zone="distant")
            n["storages"] = x.get("storages") or n["storages"]
            if not x.get("ok"):
                n["ok"], n["error"] = False, x.get("error")
            elif not n.get("ok"):                       # inventaire ssh OK alors que le relevé d'activité a échoué
                n["activity_error"], n["ok"], n["error"] = n.get("error"), True, None
            for g in x.get("guests") or []:
                vms.append(_vm(x.get("name"), g, "distant"))
    for aid, host, at, d in pbs:
        n = node(host or aid)
        n["role"] = "pbs"; n["datastores"] = d.get("datastores") or []
    for v in vms:
        g = nodes.get(v["node"], {}).get("guests")
        if g is not None:
            g["total"] += 1
            g["running" if v["status"] == "running" else "stopped"] += 1
    transfers = []
    for n in nodes.values():
        for p in n.get("procs") or []:
            transfers.append(dict(p, node=n["name"], zone=n["zone"], what="processus"))
        for f in n.get("files") or []:
            transfers.append({"node": n["name"], "zone": n["zone"], "what": "fichier", "path": f.get("path"), "size": f.get("size"),
                              "rate_bps": f.get("rate_bps"), "active": f.get("active")})
    ns = sorted(nodes.values(), key=lambda n: (n["zone"] != "local", n["role"] != "pve", n["name"]))
    tot = {}
    for zone in ("local", "distant"):
        zn = [n for n in ns if n["zone"] == zone]
        disk_size = sum(d.get("size") or 0 for n in zn for d in n.get("disks") or [])
        disk_used = sum(d.get("used") or 0 for n in zn for d in n.get("disks") or [])
        uniq = {(n["name"], s.get("total"), s.get("avail")): s for n in zn for s in n.get("storages") or [] if s.get("active", True) and s.get("total")}
        st_total = sum(s.get("total") or 0 for s in uniq.values())     # stockages « dir » d'un même système de fichiers comptés une fois
        st_used = sum(s.get("used") or 0 for s in uniq.values())
        tot[zone] = {"nodes": len(zn), "reachable": sum(1 for n in zn if n.get("ok")), "disk_size": disk_size, "disk_used": disk_used,
                     "storage_total": st_total, "storage_used": st_used,
                     "vms_running": sum(n["guests"]["running"] for n in zn), "vms_stopped": sum(n["guests"]["stopped"] for n in zn),
                     "rx_bps": sum(i.get("rx_bps") or 0 for n in zn for i in n.get("net") or []),
                     "tx_bps": sum(i.get("tx_bps") or 0 for n in zn for i in n.get("net") or []),
                     "estab": sum((n.get("conn") or {}).get("estab") or 0 for n in zn)}
    return {"nodes": ns, "vms": sorted(vms, key=lambda v: (v["node"] or "", v["vmid"] or 0)), "transfers": transfers, "totals": tot, "alerts": alerts}
