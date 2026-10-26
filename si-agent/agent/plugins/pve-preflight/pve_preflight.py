#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Sonde « pve-preflight » (#815) : tout ce qu'il faut savoir AVANT de réinstaller (ou d'arrêter) un nœud Proxmox,
pour le nœud local et les nœuds distants de pve-remote.json (un ssh par nœud, script sur l'entrée standard, lecture
seule, PVE 5.4 compris : bash 4.4, pct exec ... sh -s) :
  - quorum : pvecm status (votes attendus, présents, quorum, membres, QDevice), pveversion, ha-manager status ;
  - réplications (pvesr status), stockages (pvesm status, storage.cfg : partagé ou non), sauvegardes vzdump de chaque
    stockage (date tirée du nom), tâches planifiées (vzdump.cron / jobs.cfg), tâches récentes (sauvegardes réussies
    ou en échec, migrations des 60 derniers jours) ;
  - pour chaque CT / VM : configuration (MAC virtuelle OVH 02:00:00…, démarrage auto), charge des dernières 24 h (RRD
    du nœud, moyenne et pic), et DANS l'invité démarré : erreurs et avertissements du journal sur 24 h (ou syslog),
    unités systemd en échec, taux de réponses HTTP 5xx / 4xx sur les dernières requêtes des journaux d'accès.
Seuls des NOMBRES remontent (aucune ligne de journal). Sert la page « Préparer la réinstallation d'un nœud » de la
tuile Migration. Pur et testé : parse_driver, parse_pvecm, parse_pvesr, parse_storage_cfg, parse_pvesm_status,
parse_backups, parse_vzdump_cron, parse_jobs_cfg, tasks_summary, parse_conf, rrd_stats, parse_checks, build_node."""
import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
import time

SSH_OPTS = ["-o", "BatchMode=yes", "-o", "ConnectTimeout=15", "-o", "ServerAliveInterval=30", "-o", "StrictHostKeyChecking=accept-new"]
VZDUMP_TS = re.compile(r"vzdump-(lxc|qemu|openvz)-(\d+)-(\d{4})_(\d{2})_(\d{2})-(\d{2})_(\d{2})_(\d{2})")
SHARED_TYPES = ("nfs", "cifs", "pbs", "glusterfs", "cephfs", "rbd", "iscsi", "iscsidirect")
MIGRATION_DAYS = 60

# Script de l'invité (sh POSIX : dash, busybox ; mawk 1.3.3) -- des nombres seulement.
GUEST_SH = r"""LC_ALL=C; export LC_ALL
S=$(date -d '24 hours ago' '+%Y-%m-%d %H:%M:%S' 2>/dev/null)
if command -v journalctl >/dev/null 2>&1 && [ -n "$S" ] && journalctl -q -n 1 --no-pager >/dev/null 2>&1; then
  echo "@@src journal"
  echo "@@err $(journalctl -q -p 3 --since "$S" --no-pager 2>/dev/null | wc -l)"
  echo "@@warn $(journalctl -q -p 4 --since "$S" --no-pager 2>/dev/null | wc -l)"
elif [ -r /var/log/syslog ]; then
  echo "@@src syslog"
  echo "@@err $(tail -n 50000 /var/log/syslog 2>/dev/null | grep -ciE 'error|crit|fatal|panic|segfault')"
fi
if command -v systemctl >/dev/null 2>&1; then echo "@@failed $(systemctl --failed --no-legend 2>/dev/null | grep -c .)"; fi
L=""
for f in /var/log/apache2/*access*.log /var/log/nginx/*access*.log /var/log/httpd/*access*log; do [ -f "$f" ] && L="$L $f"; done
if [ -n "$L" ]; then
  tail -q -n 20000 $L 2>/dev/null | awk -F'"' 'NF >= 3 { split($3, a, " "); c = a[1] + 0; if (c >= 100 && c < 600) { t++; if (c >= 500) e5++; else if (c >= 400) e4++ } } END { printf "@@http %d %d %d\n", t, e5, e4 }'
fi
echo "@@fin"
"""

# Pilote du nœud : une fonction lue en entier par `bash -s`, exécutée entrée standard fermée (pct / pvesh / qm
# avaleraient la suite du script) ; script de l'invité écrit dans un fichier puis passé aux CT par l'entrée standard.
DRIVER_SH = r"""si_main() {
N=$(basename "$(readlink -f /etc/pve/local 2>/dev/null)" 2>/dev/null)
[ -n "$N" ] && [ "$N" != "local" ] || N=$(hostname -s)
echo "@@node $N"
GF=$(mktemp /tmp/si-pf.XXXXXX)
cat > "$GF" <<'__SI_GUEST__'
%s
__SI_GUEST__
echo "## pveversion"; pveversion 2>&1 | head -c 2000
echo "## pvecm"; pvecm status 2>&1 | head -c 20000
echo "## ha"; ha-manager status 2>&1 | head -c 10000
echo "## resources"; pvesh get /cluster/resources --type vm --output-format json 2>/dev/null | head -c 600000; echo
echo "## pvesm"; pvesm status 2>&1 | head -c 20000
echo "## storagecfg"; cat /etc/pve/storage.cfg 2>/dev/null | head -c 30000
echo "## pvesr"; pvesr status 2>&1 | head -c 50000
echo "## vzdumpcron"; cat /etc/pve/vzdump.cron 2>/dev/null | head -c 20000
echo "## jobscfg"; cat /etc/pve/jobs.cfg 2>/dev/null | head -c 20000
echo "## tasks"; pvesh get /nodes/$N/tasks --limit 500 --output-format json 2>/dev/null | head -c 800000; echo
echo "## backups"
for s in $(pvesm status 2>/dev/null | awk 'NR>1 && $3 == "active" {print $1}'); do echo "== $s"; pvesm list "$s" 2>/dev/null | grep vzdump | head -c 400000; done
pct list 2>/dev/null | awk 'NR>1 {print $1, $2, $NF}' | while read id st name; do
  echo "=== lxc $id $st $name"
  echo "## conf"; pct config $id 2>/dev/null | head -c 20000
  echo "## rrd"; pvesh get /nodes/$N/lxc/$id/rrddata --timeframe day --cf AVERAGE --output-format json 2>/dev/null | head -c 200000; echo
  echo "## rrdmax"; pvesh get /nodes/$N/lxc/$id/rrddata --timeframe day --cf MAX --output-format json 2>/dev/null | head -c 200000; echo
  [ "$st" = running ] && { echo "## exec"; cat "$GF" | timeout 60 pct exec $id -- sh -s 2>&1 | head -c 20000; echo; }
done
qm list 2>/dev/null | awk 'NR>1 {print $1, $3, $2}' | while read id st name; do
  echo "=== qemu $id $st $name"
  echo "## conf"; qm config $id 2>/dev/null | head -c 20000
  echo "## rrd"; pvesh get /nodes/$N/qemu/$id/rrddata --timeframe day --cf AVERAGE --output-format json 2>/dev/null | head -c 200000; echo
  echo "## rrdmax"; pvesh get /nodes/$N/qemu/$id/rrddata --timeframe day --cf MAX --output-format json 2>/dev/null | head -c 200000; echo
  [ "$st" = running ] && { echo "## qga"; timeout 60 qm guest exec $id --timeout 50 -- sh -c "$(cat "$GF")" 2>&1 | head -c 50000; echo; }
done
rm -f "$GF"
echo "@@done"
}
si_main </dev/null
"""


def driver_script():
    return DRIVER_SH % GUEST_SH.rstrip("\n")


# ---------------------------------------------------------------- découpage
def parse_driver(text):
    """-> (nœud, {section du nœud: texte}, [{type, vmid, status, name, sections}], complet ?)."""
    node, nsec, guests, cur, sec, done = None, {}, [], None, None, False
    for line in (text or "").splitlines():
        if line.startswith("@@node "):
            node = line[7:].strip() or None
            continue
        if line.strip() == "@@done":
            done = True
            continue
        m = re.match(r"^=== (lxc|qemu) (\d+) (\S+)\s*(.*)$", line)
        if m:
            cur = {"type": m.group(1), "vmid": int(m.group(2)), "status": m.group(3), "name": m.group(4).strip(), "sections": {}}
            guests.append(cur)
            sec = None
            continue
        m = re.match(r"^## (\w+)$", line.strip())
        if m:
            sec = m.group(1)
            (cur["sections"] if cur is not None else nsec)[sec] = []
            continue
        if sec:
            (cur["sections"] if cur is not None else nsec)[sec].append(line)
    nsec = {k: "\n".join(v) for k, v in nsec.items()}
    for g in guests:
        g["sections"] = {k: "\n".join(v) for k, v in g["sections"].items()}
    return node, nsec, guests, done


def _json(text, defaut):
    t = (text or "").strip()
    i = min([x for x in (t.find("["), t.find("{")) if x >= 0] or [-1])
    if i < 0:
        return defaut
    try:
        return json.loads(t[i:])
    except ValueError:
        return defaut


def parse_pvecm(text):
    """pvecm status -> {quorate, nodes, expected, total, quorum, flags, qdevice, membres: [{id, votes, name, local}]} ; None si hors cluster."""
    t = text or ""
    if "Quorum information" not in t and "Votequorum information" not in t:
        return None

    def val(label):
        m = re.search(r"^%s:\s*(.+?)\s*$" % re.escape(label), t, re.M)
        return m.group(1) if m else None

    def num(label):
        v = val(label)
        m = re.match(r"(\d+)", v or "")
        return int(m.group(1)) if m else None
    membres, dans = [], False
    for line in t.splitlines():
        if line.strip().startswith("Nodeid"):
            dans = True
            continue
        if dans:
            m = re.match(r"^\s*(0x[0-9a-fA-F]+|\d+)\s+(\d+)\s+(.+?)\s*$", line)
            if not m:
                if line.strip():
                    continue
                break
            nom = m.group(3)
            membres.append({"id": m.group(1), "votes": int(m.group(2)), "name": nom.replace("(local)", "").strip(), "local": "(local)" in nom,
                            "qdevice": nom.strip().lower().startswith("qdevice")})
    flags = val("Flags") or ""
    return {"quorate": (val("Quorate") or "").lower().startswith("yes") or "Quorate" in flags.split(), "nodes": num("Nodes"),
            "expected": num("Expected votes"), "total": num("Total votes"), "quorum": num("Quorum"), "flags": flags,
            "qdevice": "Qdevice" in flags or any(x["qdevice"] for x in membres), "membres": membres}


def parse_pvesr(text):
    """pvesr status -> [{job, vmid, enabled, target, last_sync, next_sync, duration_s, fail_count, state}]."""
    out = []
    for line in (text or "").splitlines():
        p = line.split()
        if len(p) < 7 or p[0] == "JobID" or not re.match(r"^\d+-\d+$", p[0]):
            continue
        out.append({"job": p[0], "vmid": int(p[0].split("-")[0]), "enabled": p[1].lower() == "yes", "target": p[2].split("/")[-1],
                    "last_sync": None if p[3] == "-" else p[3].replace("_", " "), "next_sync": None if p[4] == "-" else p[4].replace("_", " "),
                    "duration_s": float(p[5]) if re.match(r"^[\d.]+$", p[5]) else None,
                    "fail_count": int(p[6]) if p[6].isdigit() else None, "state": " ".join(p[7:]) or None})
    return out


def parse_storage_cfg(text):
    """storage.cfg -> {nom: {type, shared, nodes, content}} (partagé : type réseau ou « shared 1 »)."""
    out, cur = {}, None
    for line in (text or "").splitlines():
        m = re.match(r"^(\w+):\s*(\S+)\s*$", line)
        if m:
            cur = out.setdefault(m.group(2), {"type": m.group(1), "shared": m.group(1) in SHARED_TYPES, "nodes": None, "content": []})
            continue
        m = re.match(r"^\s+(\w+)\s+(.*?)\s*$", line)
        if m and cur is not None:
            k, v = m.groups()
            if k == "shared" and v.strip() == "1":
                cur["shared"] = True
            elif k == "nodes":
                cur["nodes"] = [x.strip() for x in v.split(",") if x.strip()]
            elif k == "content":
                cur["content"] = [x.strip() for x in v.split(",") if x.strip()]
    return out


def parse_pvesm_status(text):
    """pvesm status -> {nom: {type, active, total, used, avail}} (Kio -> octets)."""
    out = {}
    for line in (text or "").splitlines():
        p = line.split()
        if len(p) >= 6 and p[0] != "Name" and p[3].isdigit():
            out[p[0]] = {"type": p[1], "active": p[2] == "active", "total": int(p[3]) * 1024, "used": int(p[4]) * 1024, "avail": int(p[5]) * 1024}
    return out


def parse_backups(text):
    """« == stockage » puis lignes de pvesm list -> [{vmid, type, volid, storage, at (UTC approché), size}] ; date du nom vzdump."""
    out, store = [], None
    for line in (text or "").splitlines():
        m = re.match(r"^== (\S+)$", line.strip())
        if m:
            store = m.group(1)
            continue
        p = line.split()
        ts = VZDUMP_TS.search(p[0]) if p else None
        if store is None or not ts:
            continue
        nums = [int(x) for x in p[1:] if x.isdigit()]
        size = max(nums) if nums and max(nums) > 4096 else None
        at = "%s-%s-%sT%s:%s:%s" % ts.groups()[2:]
        out.append({"vmid": int(ts.group(2)), "type": ts.group(1), "volid": p[0], "storage": store, "at": at, "size": size})
    return out


def parse_vzdump_cron(text):
    """/etc/pve/vzdump.cron (PVE 5/6) -> [{schedule, all, vmids, storage, mode}]."""
    out = []
    for line in (text or "").splitlines():
        line = line.strip()
        if not line or line.startswith(("#", "PATH")) or "vzdump" not in line:
            continue
        p = line.split()
        if len(p) < 7:
            continue
        args = p[p.index("vzdump") + 1:] if "vzdump" in p else []
        pos = next((i for i, x in enumerate(args) if x.startswith("--")), len(args))
        vmids = [int(x) for x in args[:pos] if x.isdigit()]
        opt = {args[i][2:]: (args[i + 1] if i + 1 < len(args) else "") for i in range(len(args)) if args[i].startswith("--")}
        out.append({"schedule": " ".join(p[:5]), "all": opt.get("all") == "1", "vmids": vmids, "exclude": [int(x) for x in re.split(r"[ ,]", opt.get("exclude", "")) if x.isdigit()],
                    "storage": opt.get("storage"), "mode": opt.get("mode")})
    return out


def parse_jobs_cfg(text):
    """/etc/pve/jobs.cfg (PVE 7+) -> mêmes champs que parse_vzdump_cron."""
    out, cur = [], None
    for line in (text or "").splitlines():
        m = re.match(r"^vzdump:\s*(\S+)", line)
        if m:
            cur = {"schedule": None, "all": False, "vmids": [], "exclude": [], "storage": None, "mode": None, "id": m.group(1), "enabled": True}
            out.append(cur)
            continue
        m = re.match(r"^\s+(\w+)\s+(.*?)\s*$", line)
        if m and cur is not None:
            k, v = m.groups()
            if k == "schedule":
                cur["schedule"] = v
            elif k == "all":
                cur["all"] = v == "1"
            elif k == "vmid":
                cur["vmids"] = [int(x) for x in re.split(r"[ ,]", v) if x.isdigit()]
            elif k == "exclude":
                cur["exclude"] = [int(x) for x in re.split(r"[ ,]", v) if x.isdigit()]
            elif k in ("storage", "mode"):
                cur[k] = v
            elif k == "enabled":
                cur["enabled"] = v != "0"
        elif not line.strip():
            cur = None
    return out


def tasks_summary(rows, now=None, days=MIGRATION_DAYS):
    """Tâches du nœud -> {last_vzdump: {vmid: {at, ok, status}}, migrations: [{vmid, type, at, ok}]} (vmid en chaîne)."""
    now = now or time.time()
    last, migr = {}, []
    for t in rows or []:
        if not isinstance(t, dict):
            continue
        typ, vid, st = t.get("type"), str(t.get("id") or ""), t.get("status")
        at = t.get("starttime") or 0
        ok = st == "OK"
        if typ == "vzdump" and vid.isdigit():
            if vid not in last or at > last[vid]["at"]:
                last[vid] = {"at": at, "ok": ok, "status": (st or "en cours")[:120]}
        elif typ in ("vzmigrate", "qmigrate") and vid.isdigit() and at >= now - days * 86400:
            migr.append({"vmid": int(vid), "type": typ, "at": at, "ok": ok, "status": (st or "en cours")[:120]})
    migr.sort(key=lambda m: -m["at"])
    return {"last_vzdump": last, "migrations": migr}


def parse_conf(text):
    """pct / qm config -> {vmac, macs, onboot, cores, memory_mb, disks: [stockage]} (MAC virtuelle OVH : 02:00:00…)."""
    macs = [m.upper() for m in re.findall(r"(?:hwaddr=|=)([0-9A-Fa-f]{2}(?::[0-9A-Fa-f]{2}){5})", text or "")]
    stor = sorted(set(re.findall(r"^(?:rootfs|mp\d+|scsi\d+|virtio\d+|sata\d+|ide\d+|efidisk\d+):\s*([A-Za-z0-9_.-]+):(?!.*media=cdrom)", text or "", re.M)))

    def num(k):
        m = re.search(r"^%s:\s*(\d+)" % k, text or "", re.M)
        return int(m.group(1)) if m else None
    ips = []    # #856 : adresses IPv4 fixes (LXC : net0 ip= ; VM cloud-init : ipconfig0 ip=) -> contrôle d'accessibilité
    for ip in re.findall(r"(?:^net\d+|^ipconfig\d+):.*?\bip=(\d{1,3}(?:\.\d{1,3}){3})", text or "", re.M):
        if ip not in ips:
            ips.append(ip)
    return {"vmac": any(m.startswith("02:00:00") for m in macs), "macs": macs, "onboot": num("onboot") == 1, "cores": num("cores"),
            "memory_mb": num("memory"), "disks": stor, "ips": ips}


def rrd_stats(avg_rows, max_rows=None):
    """RRD jour (AVERAGE, MAX) -> {cpu_avg_pct, cpu_max_pct, mem_avg_pct, mem_max_pct, netin_avg, netout_avg, points} (cpu en % des vCPU)."""
    def vals(rows, k):
        return [r[k] for r in rows or [] if isinstance(r, dict) and isinstance(r.get(k), (int, float))]

    def mem_pct(rows):
        return [100.0 * r["mem"] / r["maxmem"] for r in rows or [] if isinstance(r, dict) and isinstance(r.get("mem"), (int, float)) and r.get("maxmem")]
    cpu, cpux = vals(avg_rows, "cpu"), vals(max_rows if max_rows else avg_rows, "cpu")
    mem, memx = mem_pct(avg_rows), mem_pct(max_rows if max_rows else avg_rows)
    ni, no = vals(avg_rows, "netin"), vals(avg_rows, "netout")
    r = lambda v: round(v, 1)  # noqa: E731
    return {"cpu_avg_pct": r(100 * sum(cpu) / len(cpu)) if cpu else None, "cpu_max_pct": r(100 * max(cpux)) if cpux else None,
            "mem_avg_pct": r(sum(mem) / len(mem)) if mem else None, "mem_max_pct": r(max(memx)) if memx else None,
            "netin_avg": r(sum(ni) / len(ni)) if ni else None, "netout_avg": r(sum(no) / len(no)) if no else None, "points": len(cpu)}


def unwrap_qga(text):
    t = (text or "").strip()
    i = t.find("{")
    if i < 0:
        return "", (t.splitlines() or ["agent invité absent"])[-1][:160] or "agent invité absent"
    try:
        d = json.loads(t[i:])
    except ValueError:
        return "", "réponse de l'agent invité illisible"
    return d.get("out-data") or "", None


def parse_checks(text):
    """Sortie de GUEST_SH -> {src, err_24h, warn_24h, failed_units, http_total, http_5xx, http_4xx, complet}."""
    out = {"src": None, "err_24h": None, "warn_24h": None, "failed_units": None, "http_total": None, "http_5xx": None, "http_4xx": None,
           "complet": "@@fin" in (text or "")}
    for line in (text or "").splitlines():
        p = line.strip().split()
        if not p or not p[0].startswith("@@"):
            continue
        k, v = p[0][2:], p[1:]
        num = lambda i: int(v[i]) if len(v) > i and v[i].isdigit() else None  # noqa: E731
        if k == "src" and v:
            out["src"] = v[0]
        elif k == "err":
            out["err_24h"] = num(0)
        elif k == "warn":
            out["warn_24h"] = num(0)
        elif k == "failed":
            out["failed_units"] = num(0)
        elif k == "http":
            out["http_total"], out["http_5xx"], out["http_4xx"] = num(0), num(1), num(2)
    return out


def build_node(name, zone, nsec, guests, complete, now=None):
    """Assemble le relevé d'un nœud."""
    now = now or time.time()
    res = _json(nsec.get("resources"), [])
    res_by = {int(r["vmid"]): r for r in res if isinstance(r, dict) and str(r.get("vmid", "")).isdigit()}
    rows = []
    for g in guests:
        s = g["sections"]
        r = res_by.get(g["vmid"], {})
        if g["type"] == "qemu":
            txt, err = unwrap_qga(s.get("qga")) if "qga" in s else ("", None)
        else:
            txt, err = s.get("exec", ""), None
        checks = parse_checks(txt) if (txt or err) else None
        if checks is not None and not checks["complet"]:
            checks["erreur"] = err or ((txt or "").strip().splitlines() or ["relevé interrompu"])[-1][:160]
        rows.append({"vmid": g["vmid"], "type": g["type"], "name": g["name"] or r.get("name") or "", "status": g["status"],
                     "conf": parse_conf(s.get("conf")), "charge": rrd_stats(_json(s.get("rrd"), []), _json(s.get("rrdmax"), [])),
                     "checks": checks, "disk": r.get("disk"), "maxdisk": r.get("maxdisk"), "maxmem": r.get("maxmem"), "maxcpu": r.get("maxcpu"),
                     "uptime_s": r.get("uptime"), "template": bool(r.get("template"))})
    jobs = parse_vzdump_cron(nsec.get("vzdumpcron")) + parse_jobs_cfg(nsec.get("jobscfg"))
    ha = (nsec.get("ha") or "").strip()
    return {"name": name, "zone": zone, "ok": True, "complete": complete, "error": None if complete else "relevé incomplet (délai dépassé ?)",
            "pveversion": (nsec.get("pveversion") or "").strip().splitlines()[0][:120] if (nsec.get("pveversion") or "").strip() else None,
            "quorum": parse_pvecm(nsec.get("pvecm")), "ha": {"actif": bool(re.search(r"^service ", ha, re.M)), "texte": ha[:600]},
            "cluster_vms": [{"vmid": int(r["vmid"]), "node": r.get("node"), "name": r.get("name"), "type": r.get("type"), "status": r.get("status")}
                            for r in res_by.values()],
            "storages": {k: dict(v, **parse_storage_cfg(nsec.get("storagecfg")).get(k, {})) for k, v in parse_pvesm_status(nsec.get("pvesm")).items()},
            "replication": parse_pvesr(nsec.get("pvesr")), "backups": parse_backups(nsec.get("backups")), "vzdump_jobs": jobs,
            "tasks": tasks_summary(_json(nsec.get("tasks"), []), now), "guests": rows}


def alerts_for(nodes):
    out = []
    for n in nodes:
        if not n.get("ok"):
            out.append({"code": "pve-preflight-unreachable:%s" % n["name"], "severity": "warning", "message": "%s : relevé de préparation impossible (%s)" % (n["name"], n.get("error"))})
            continue
        q = n.get("quorum")
        if q and not q.get("quorate"):
            out.append({"code": "pve-quorum:%s" % n["name"], "severity": "critical", "message": "%s : cluster SANS quorum (%s / %s votes)" % (n["name"], q.get("total"), q.get("expected"))})
        for j in n.get("replication") or []:
            if (j.get("fail_count") or 0) > 0:
                out.append({"code": "pve-replication:%s" % j["job"], "severity": "warning",
                            "message": "%s : réplication %s vers %s en échec (%s fois) : %s" % (n["name"], j["job"], j["target"], j["fail_count"], j.get("state") or "")})
    return out


def run_node(h, script, runner=subprocess.run):
    if h is None:
        p = runner(["bash", "-s"], input=script, capture_output=True, text=True, timeout=900)
    else:
        if h.get("key") and not os.path.exists(h["key"]):
            raise RuntimeError("clé %s introuvable pour le service si-agent (la placer dans /etc/si-agent/keys/, chmod 600, et corriger pve-remote.json)" % h["key"])
        args = ["ssh"] + SSH_OPTS + (["-i", h["key"], "-o", "IdentitiesOnly=yes"] if h.get("key") else []) + ["%s@%s" % (h.get("user") or "root", h["host"]), "bash -s"]
        p = runner(args, input=script, capture_output=True, text=True, timeout=900)
    if "@@node" not in (p.stdout or ""):
        raise RuntimeError(((p.stderr or "").strip().splitlines() or ["code %d" % p.returncode])[-1][:200])
    return p.stdout


def main(argv=None, runner=subprocess.run):
    ap = argparse.ArgumentParser()
    ap.add_argument("--remote", default="/etc/si-agent/pve-remote.json")
    ap.add_argument("--no-local", action="store_true")
    a = ap.parse_args(argv)
    targets = [] if a.no_local or not os.path.isdir("/etc/pve") else [("local", "local", None)]
    if a.remote and os.path.exists(a.remote):
        try:
            with open(a.remote, encoding="utf-8") as fh:
                targets += [(h.get("name") or h["host"], "distant", h) for h in json.load(fh) if isinstance(h, dict) and h.get("host")]
        except (OSError, ValueError):
            pass
    nodes, script = [], driver_script()
    for name, zone, h in targets:
        try:
            node, nsec, guests, done = parse_driver(run_node(h, script, runner))
            nodes.append(build_node(node or name, zone, nsec, guests, done))
        except Exception as e:  # noqa: BLE001 -- un nœud injoignable n'empêche pas les autres
            nodes.append({"name": name, "zone": zone, "ok": False, "error": str(e)[:200], "guests": []})
    g = [x for n in nodes for x in n.get("guests") or []]
    print(json.dumps({"at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "nodes": nodes, "alerts": alerts_for(nodes),
                      "summary": {"nodes": len(nodes), "guests": len(g), "checked": sum(1 for x in g if x.get("checks"))}}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
