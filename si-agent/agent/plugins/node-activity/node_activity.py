#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Activité des nœuds PVE / PBS (#749) : un même relevé shell pour l'hôte local et pour chaque nœud distant (ssh, lecture
seule), analysé ici ; débits calculés d'un passage à l'autre (état JSON).
Usage : node_activity.py [--watch d1,d2] [--remote pve-remote.json] [--state fichier]
Sortie : {at, nodes: [{name, zone, ok, error, cpu_pct, ncpu, load, mem_total, mem_used, disks, zpools, net, conn, procs,
files}], alerts}. Pur : parse_*, rates, file_rates."""
import argparse
import json
import os
import re
import subprocess
import sys
import time

SEP = "@@SECTION@@"
PROC_RE = r"vzdump|pct restore|qmrestore|qm importdisk|zfs (send|recv|receive)|rsync|scp |gzip|zstd|pigz|lzop|pvesr|proxmox-backup-client"
# #766 : tâches Proxmox en cours (fichier active : une tâche en cours = UPID seul sur sa ligne), extrait de leur journal,
# octets lus par proxmox-backup-client (sauvegarde de CT vers PBS : pas de pourcentage dans le journal)
TASK_SH = (r"""for u in $(awk 'NF==1 && /^UPID:/{print $1}' /var/log/pve/tasks/active 2>/dev/null | head -5); do echo "@@TASK $u"; """
           r"""f=$(ls /var/log/pve/tasks/*/"$u" 2>/dev/null | head -1); [ -n "$f" ] && { grep -E 'starting new backup job|Starting Backup of VM|"""
           r"""Finished Backup of VM|ERROR|INFO: +[0-9]+% \(|had to backup|Backup job finished|^TASK' "$f" | tail -n 60; """
           r"""tail -n 1 "$f" | sed 's/^/@@LAST /'; }; done; for p in $(pgrep -f 'proxmox-backup-client backup' 2>/dev/null | head -3); do """
           r"""echo "@@PBC $p $(awk '/^rchar/{print $2}' /proc/$p/io 2>/dev/null)"; done""")
SKIP_IF = re.compile(r"^(lo|veth|tap|fwbr|fwpr|fwln|docker|br-|virbr|vnet)")


def metric_cmd(watch):
    dirs = " ".join("'%s'" % d.replace("'", "") for d in watch if d)
    return "; ".join([
        "cat /proc/loadavg", "echo %s" % SEP, "grep '^cpu' /proc/stat", "echo %s" % SEP,
        "grep -E '^(MemTotal|MemAvailable|SwapTotal|SwapFree):' /proc/meminfo", "echo %s" % SEP, "cat /proc/net/dev", "echo %s" % SEP,
        "ss -s 2>/dev/null", "echo %s" % SEP, "df -B1 -P -x tmpfs -x devtmpfs -x overlay -x squashfs 2>/dev/null", "echo %s" % SEP,
        "zpool list -Hp -o name,size,alloc,free,frag,cap,health 2>/dev/null", "echo %s" % SEP, "nproc", "echo %s" % SEP,
        "ps -eo pid,etimes,args --no-headers | grep -E '%s' | grep -v -E 'grep|node_activity' | head -20" % PROC_RE, "echo %s" % SEP,
        "for d in %s; do find \"$d\" -maxdepth 2 -type f -mmin -30 -printf '%%p\\t%%s\\t%%T@\\n' 2>/dev/null; done" % (dirs or "/nonexistent"),
        "echo %s" % SEP, "hostname", "echo %s" % SEP, "cat /proc/uptime", "echo %s" % SEP, TASK_SH])


def sections(text):
    return [s.strip("\n") for s in (text or "").split(SEP)]


def parse_cpu(line):
    f = line.split()
    if not f or f[0] != "cpu":
        return None
    v = [int(x) for x in f[1:9]]
    idle = v[3] + (v[4] if len(v) > 4 else 0)
    return sum(v), sum(v) - idle


def parse_mem(text):
    kv = dict(re.findall(r"^(\w+):\s+(\d+)", text or "", re.M))
    tot, av = int(kv.get("MemTotal", 0)) * 1024, int(kv.get("MemAvailable", 0)) * 1024
    return (tot, tot - av) if tot else (None, None)


def parse_swap(text):
    kv = dict(re.findall(r"^(\w+):\s+(\d+)", text or "", re.M))
    tot, free = int(kv.get("SwapTotal", 0)) * 1024, int(kv.get("SwapFree", 0)) * 1024
    return tot, tot - free


def parse_cpus(text):
    """Lignes cpuN de /proc/stat -> {N: (total, occupé)} (htop : une barre par cœur)."""
    out = {}
    for line in (text or "").splitlines():
        m = re.match(r"^cpu(\d+)\s", line)
        if m:
            out[m.group(1)] = parse_cpu("cpu " + line.split(None, 1)[1])
    return out


def parse_netdev(text):
    out = {}
    for line in (text or "").splitlines()[2:]:
        if ":" not in line:
            continue
        name, rest = line.split(":", 1)
        name, f = name.strip(), rest.split()
        if len(f) >= 9 and not SKIP_IF.match(name):
            out[name] = (int(f[0]), int(f[8]))
    return out


def parse_ss(text):
    out = {}
    m = re.search(r"TCP:\s+(\d+)\s*\(estab (\d+), closed (\d+), orphaned (\d+), (?:synrecv \d+, )?timewait (\d+)", text or "")
    if m:
        out.update(tcp=int(m.group(1)), estab=int(m.group(2)), timewait=int(m.group(5)))
    m = re.search(r"^UDP\s+(\d+)", text or "", re.M)
    if m:
        out["udp"] = int(m.group(1))
    return out


def parse_df(text):
    out = []
    for line in (text or "").splitlines()[1:]:
        f = line.split()
        if len(f) >= 6 and f[1].isdigit() and int(f[1]) > 0 and not f[5].startswith(("/boot", "/run", "/snap", "/dev")):
            size, used = int(f[1]), int(f[2])
            out.append({"device": f[0], "mount": f[5], "size": size, "used": used, "pct": round(100.0 * used / size, 1)})
    return out


def parse_zpool(text):
    out = []
    for line in (text or "").splitlines():
        f = line.split("\t")
        if len(f) >= 7 and f[1].isdigit():
            out.append({"name": f[0], "size": int(f[1]), "alloc": int(f[2]), "free": int(f[3]), "frag": f[4].rstrip("%"),
                        "pct": int(f[5].rstrip("%")) if f[5].rstrip("%").isdigit() else None, "health": f[6]})
    return out


def parse_procs(text):
    out = []
    for line in (text or "").splitlines():
        f = line.strip().split(None, 2)
        if len(f) == 3 and f[0].isdigit():
            kind = next((k for k in ("vzdump", "restore", "importdisk", "zfs", "rsync", "scp", "pvesr", "proxmox-backup", "zstd", "gzip", "pigz", "lzop")
                         if k in f[2]), "autre")
            out.append({"pid": int(f[0]), "elapsed_s": int(f[1]), "kind": kind, "cmd": re.sub(r"(-i|--key|password\S*)\s+\S+", r"\1 …", f[2])[:200]})
    return out


def parse_tasks(text, now):
    """#766 : section des tâches en cours -> [{upid, type, id, user, started, elapsed_s, guests, done, failed, current, percent,
    detail, read_bytes, last}]."""
    tasks, pbc, cur = [], 0, None
    for line in (text or "").splitlines():
        line = line.rstrip()
        if line.startswith("@@TASK "):
            u = line[7:].strip(); f = u.split(":")
            try:
                started = int(f[4], 16)
            except (IndexError, ValueError):
                started = None
            cur = {"upid": u, "type": f[5] if len(f) > 5 else "?", "id": f[6] if len(f) > 6 else "", "user": f[7] if len(f) > 7 else "",
                   "started": started, "elapsed_s": int(now - started) if started else None, "guests": [], "done": [], "failed": [],
                   "current": None, "percent": None, "detail": None, "read_bytes": None, "last": None, "summary": None}
            tasks.append(cur)
            continue
        if line.startswith("@@PBC "):
            p = line.split()
            pbc += int(p[2]) if len(p) > 2 and p[2].isdigit() else 0
            continue
        if cur is None:
            continue
        if line.startswith("@@LAST "):
            cur["last"] = line[7:][:200]
            continue
        m = re.search(r"starting new backup job: vzdump (.*)", line)
        if m:
            cur["guests"] = [int(x) for x in m.group(1).split() if x.isdigit()]
            continue
        m = re.search(r"Starting Backup of VM (\d+)", line)
        if m:
            cur.update(current=int(m.group(1)), percent=None, detail=None)
            continue
        m = re.search(r"Finished Backup of VM (\d+) \(([\d:]+)\)", line)
        if m:
            cur["done"].append({"vmid": int(m.group(1)), "duration": m.group(2)})
            if cur["current"] == int(m.group(1)):
                cur["current"] = None
            continue
        m = re.search(r"ERROR: Backup of VM (\d+) failed - (.*)", line)
        if m:
            cur["failed"].append({"vmid": int(m.group(1)), "error": m.group(2)[:200]})
            if cur["current"] == int(m.group(1)):
                cur["current"] = None
            continue
        m = re.search(r"INFO:\s+(\d+)% \(([^)]*)\)", line)
        if m:
            cur["percent"], cur["detail"] = int(m.group(1)), m.group(2)
            continue
        m = re.search(r"(\S+): had to backup (.*)", line)
        if m:
            cur["summary"] = "%s : %s" % (m.group(1), m.group(2)[:160])
    for t in tasks:
        if t["type"] == "vzdump" and t["current"] is not None and pbc:
            t["read_bytes"] = pbc
    return tasks


def parse_files(text):
    out = []
    for line in (text or "").splitlines():
        f = line.split("\t")
        if len(f) == 3 and f[1].isdigit():
            out.append({"path": f[0], "size": int(f[1]), "mtime": float(f[2])})
    return out


def rates(cur, prev, dt):
    """{k: (a, b)} courant / précédent -> {k: (da/dt, db/dt)} (compteurs remis à zéro ignorés)."""
    out = {}
    for k, v in (cur or {}).items():
        p = (prev or {}).get(k)
        if p and dt > 0 and v[0] >= p[0] and v[1] >= p[1]:
            out[k] = ((v[0] - p[0]) / dt, (v[1] - p[1]) / dt)
    return out


def file_rates(files, prev_sizes, dt, now):
    out = []
    for f in files:
        p = (prev_sizes or {}).get(f["path"])
        rate = (f["size"] - p) / dt if p is not None and dt > 0 and f["size"] >= p else None
        out.append(dict(f, rate_bps=round(rate) if rate is not None else None, active=now - f["mtime"] < 180))
    return sorted(out, key=lambda x: -x["size"])[:30]


def build_node(name, zone, text, prev, now):
    s = sections(text)
    while len(s) < 13:
        s.append("")
    lf = s[0].split()
    load = lf[:3]
    cpu = parse_cpu(s[1].splitlines()[0] if s[1] else "")
    cores = parse_cpus(s[1])
    swap_total, swap_used = parse_swap(s[2])
    mem_total, mem_used = parse_mem(s[2])
    net = parse_netdev(s[3])
    files = parse_files(s[9])
    dt = now - (prev or {}).get("at", now)
    node = {"name": name, "hostname": s[10].strip() or name, "zone": zone, "ok": True, "error": None,
            "load": [float(x) for x in load] if len(load) == 3 else None, "ncpu": int(s[7]) if s[7].strip().isdigit() else None,
            "mem_total": mem_total, "mem_used": mem_used, "disks": parse_df(s[5]), "zpools": parse_zpool(s[6]), "conn": parse_ss(s[4]),
            "procs": parse_procs(s[8]), "cpu_pct": None, "net": [], "swap_total": swap_total, "swap_used": swap_used,
            "tasks": {"running": int(lf[3].split("/")[0]), "total": int(lf[3].split("/")[1])} if len(lf) > 3 and "/" in lf[3] else None,
            "uptime_s": int(float(s[11].split()[0])) if s[11].split() else None, "cores_pct": [], "pve_tasks": parse_tasks(s[12], now)}
    pc = (prev or {}).get("cpu")
    if cpu and pc and cpu[0] > pc[0]:
        node["cpu_pct"] = round(100.0 * (cpu[1] - pc[1]) / (cpu[0] - pc[0]), 1)
    pcores = (prev or {}).get("cores") or {}
    node["cores_pct"] = [round(100.0 * (v[1] - pcores[k][1]) / (v[0] - pcores[k][0]), 1) if k in pcores and v[0] > pcores[k][0] else None
                         for k, v in sorted(cores.items(), key=lambda kv: int(kv[0]))]
    r = rates(net, (prev or {}).get("net"), dt)
    node["net"] = sorted([{"iface": k, "rx_total": v[0], "tx_total": v[1], "rx_bps": round(r[k][0] * 8) if k in r else None,
                           "tx_bps": round(r[k][1] * 8) if k in r else None} for k, v in net.items()], key=lambda x: x["iface"])
    node["files"] = file_rates(files, (prev or {}).get("files"), dt, now)
    state = {"at": now, "cpu": cpu, "cores": cores, "net": net, "files": {f["path"]: f["size"] for f in files}}
    return node, state


def alerts_for(nodes):
    out = []
    for n in nodes:
        if not n["ok"]:
            out.append({"code": "node-unreachable:%s" % n["name"], "severity": "warning", "message": "%s injoignable : %s" % (n["name"], n["error"])}); continue
        for d in n.get("disks") or []:
            if d["pct"] >= 90:
                out.append({"code": "disk-full:%s:%s" % (n["name"], d["mount"]), "severity": "critical" if d["pct"] >= 97 else "warning",
                            "message": "%s : %s plein à %s %%" % (n["name"], d["mount"], d["pct"])})
        for z in n.get("zpools") or []:
            if (z.get("pct") or 0) >= 85:
                out.append({"code": "zpool-full:%s:%s" % (n["name"], z["name"]), "severity": "critical" if z["pct"] >= 95 else "warning",
                            "message": "%s : pool ZFS %s à %s %%" % (n["name"], z["name"], z["pct"])})
        for f in n.get("files") or []:
            if f.get("rate_bps") == 0 and f["path"].endswith((".part", ".tmp", ".dat")) and f.get("active") is False:
                out.append({"code": "transfer-stalled:%s:%s" % (n["name"], f["path"]), "severity": "warning", "message": "%s : %s ne grossit plus" % (n["name"], f["path"])})
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--watch", default="/var/lib/vz/dump,/var/lib/vz/import")
    ap.add_argument("--remote", default="")
    ap.add_argument("--state", default="/var/lib/si-agent/node-activity.state.json")
    a = ap.parse_args(argv)
    watch = [d for d in a.watch.split(",") if d.strip()]
    try:
        with open(a.state) as fh:
            state = json.load(fh)
    except (OSError, ValueError):
        state = {}
    now, nodes, new_state = time.time(), [], {}
    cmd = metric_cmd(watch)
    targets = [("local", "local", None)]
    if a.remote and os.path.exists(a.remote):
        try:
            with open(a.remote, encoding="utf-8") as fh:
                targets += [(h.get("name") or h["host"], "remote", h) for h in json.load(fh) if isinstance(h, dict) and h.get("host")]
        except (OSError, ValueError):
            pass
    for name, zone, h in targets:
        try:
            if h is None:
                out = subprocess.run(["bash", "-c", cmd], capture_output=True, text=True, timeout=40).stdout
            else:
                args = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", "-o", "StrictHostKeyChecking=accept-new"]
                if h.get("key"):
                    args += ["-i", h["key"], "-o", "IdentitiesOnly=yes"]
                p = subprocess.run(args + ["%s@%s" % (h.get("user") or "root", h["host"]), cmd], capture_output=True, text=True, timeout=40)
                if p.returncode not in (0, 1) or SEP not in p.stdout:
                    raise RuntimeError(((p.stderr or "").strip().splitlines() or ["code %d" % p.returncode])[-1][:200])
                out = p.stdout
            node, st = build_node(name, zone, out, state.get(name), now)
            if zone == "local":
                node["name"] = node["hostname"]
            nodes.append(node); new_state[name] = st
        except Exception as e:  # noqa: BLE001 -- un nœud injoignable n'empêche pas les autres
            nodes.append({"name": name, "zone": zone, "ok": False, "error": str(e)[:200]})
    try:
        os.makedirs(os.path.dirname(a.state), exist_ok=True)
        with open(a.state + ".tmp", "w") as fh:
            json.dump(new_state, fh)
        os.replace(a.state + ".tmp", a.state)
    except OSError:
        pass
    print(json.dumps({"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)), "nodes": nodes, "alerts": alerts_for(nodes)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
