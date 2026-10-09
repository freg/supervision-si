#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Inventaire de Proxmox VE distants sans agent (#723) : ssh <hôte> en lecture seule.
  pvesh get /cluster/resources --type vm --output-format json   (PVE >= 5.3) ; à défaut pct list + qm list
  pvesm status                                                    (stockages : total, utilisé, libre)
Hôtes : fichier JSON [{name, host, key?, user?}] (hors dépôt). Sortie : {"nodes": [{name, host, ok, error, guests, storages}],
"alerts", "summary"}. Pur : parse_pct_list, parse_qm_list, parse_pvesm, merge."""
import argparse
import json
import re
import subprocess
import sys

SSH_OPTS = ["-o", "BatchMode=yes", "-o", "ConnectTimeout=15", "-o", "ServerAliveInterval=15", "-o", "StrictHostKeyChecking=accept-new"]


def parse_pct_list(text):
    """« VMID Status Lock Name » -> [{vmid, status, name, type: lxc}] (colonne Lock souvent vide)."""
    out = []
    for line in (text or "").splitlines()[1:]:
        p = line.split()
        if len(p) >= 2 and p[0].isdigit():
            out.append({"vmid": int(p[0]), "status": p[1], "name": p[-1] if len(p) >= 3 else "", "type": "lxc"})
    return out


def parse_qm_list(text):
    """« VMID NAME STATUS MEM(MB) BOOTDISK(GB) PID » -> [{vmid, name, status, maxdisk, type: qemu}]."""
    out = []
    for line in (text or "").splitlines()[1:]:
        p = line.split()
        if len(p) >= 3 and p[0].isdigit():
            disk = float(p[4]) * 1024 ** 3 if len(p) >= 5 and re.fullmatch(r"[\d.]+", p[4]) else None
            out.append({"vmid": int(p[0]), "name": p[1], "status": p[2], "maxdisk": int(disk) if disk else None, "type": "qemu"})
    return out


def parse_pvesm(text):
    """« Name Type Status Total Used Available % » (Kio) -> [{storage, type, active, total, used, avail}] en octets."""
    out = []
    for line in (text or "").splitlines()[1:]:
        p = line.split()
        if len(p) >= 6 and p[3].isdigit():
            out.append({"storage": p[0], "type": p[1], "active": p[2] == "active", "total": int(p[3]) * 1024,
                        "used": int(p[4]) * 1024, "avail": int(p[5]) * 1024})
    return out


# #724 : snapshots et sauvegardes en UN appel ssh par famille (pas un par CT)
SNAP_CMD = ("for id in $(pct list 2>/dev/null | awk 'NR>1{print $1}'); do echo \"== lxc $id\"; pct listsnapshot $id 2>/dev/null; done; "
            "for id in $(qm list 2>/dev/null | awk 'NR>1{print $1}'); do echo \"== qemu $id\"; qm listsnapshot $id 2>/dev/null; done")
BACKUP_CMD = "for s in $(pvesm status 2>/dev/null | awk 'NR>1{print $1}'); do echo \"== $s\"; pvesm list $s 2>/dev/null; done"
VZDUMP_TS = re.compile(r"vzdump-(lxc|qemu|openvz)-(\d+)-(\d{4})_(\d{2})_(\d{2})-(\d{2})_(\d{2})_(\d{2})")
SNAP_LINE = re.compile(r"^[\s`|>-]*([A-Za-z0-9_.-]+)(?:\s+(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}))?\s*(.*)$")


def parse_snapshots(text):
    """Sortie de SNAP_CMD -> [{vmid, type, name, at (« AAAA-MM-JJ hh:mm:ss » ou None), description}] (« current » exclu)."""
    out, cur = [], None
    for line in (text or "").splitlines():
        m = re.match(r"^== (lxc|qemu) (\d+)$", line.strip())
        if m:
            cur = (m.group(1), int(m.group(2)))
            continue
        if not cur or not line.strip():
            continue
        m = SNAP_LINE.match(line)
        if m and m.group(1) != "current" and not line.strip().startswith("You are here"):
            out.append({"vmid": cur[1], "type": cur[0], "name": m.group(1), "at": m.group(2), "description": (m.group(3) or "").strip()[:120]})
    return out


def parse_backups(text):
    """Sortie de BACKUP_CMD (pvesm list par stockage) -> sauvegardes [{vmid, volid, storage, at, size, format}] ;
    la date vient du nom vzdump (aaaa_mm_jj-hh_mm_ss), seule source sur les PVE anciens."""
    out, store = [], None
    for line in (text or "").splitlines():
        m = re.match(r"^== (\S+)$", line.strip())
        if m:
            store = m.group(1)
            continue
        p = line.split()
        if store is None or len(p) < 4 or p[0] == "Volid":
            continue
        ts = VZDUMP_TS.search(p[0])
        if p[2] != "backup" and not ts:
            continue
        size = int(p[3]) if p[3].isdigit() else None
        vmid = int(p[4]) if len(p) >= 5 and p[4].isdigit() else (int(ts.group(2)) if ts else None)
        at = "%s-%s-%s %s:%s:%s" % ts.groups()[2:] if ts else None
        out.append({"vmid": vmid, "volid": p[0], "storage": store, "at": at, "size": size, "format": p[1]})
    return out


def from_resources(items, node_name=None):
    """pvesh /cluster/resources --type vm -> invités (filtrés sur le nœud si fourni)."""
    out = []
    for r in items or []:
        if r.get("type") not in ("lxc", "qemu") or (node_name and r.get("node") and r["node"] != node_name):
            continue
        out.append({"vmid": int(r.get("vmid") or 0), "name": r.get("name") or "", "type": r["type"], "status": r.get("status") or "",
                    "maxdisk": r.get("maxdisk"), "disk": r.get("disk"), "node": r.get("node")})
    return out


def ssh(target, key, cmd, runner=subprocess.run, timeout=90):
    args = ["ssh"] + SSH_OPTS + (["-i", key, "-o", "IdentitiesOnly=yes"] if key else []) + [target, cmd]
    p = runner(args, capture_output=True, text=True, timeout=timeout)
    if p.returncode != 0:
        raise RuntimeError((p.stderr or "").strip().splitlines()[-1][:200] if (p.stderr or "").strip() else "code %d" % p.returncode)
    return p.stdout


def inventory(h, runner=subprocess.run):
    name, target, key = h.get("name") or h["host"], "%s@%s" % (h.get("user") or "root", h["host"]), h.get("key")
    node = {"name": name, "host": h["host"], "ok": True, "error": None, "guests": [], "storages": [], "source": None, "snapshots": [], "backups": []}
    try:
        try:
            res = json.loads(ssh(target, key, "pvesh get /cluster/resources --type vm --output-format json", runner) or "[]")
            hostname = ssh(target, key, "hostname", runner).strip()
            node["guests"], node["source"] = from_resources(res, hostname), "pvesh"
        except (RuntimeError, ValueError):
            node["guests"] = parse_pct_list(ssh(target, key, "pct list", runner)) + parse_qm_list(ssh(target, key, "qm list", runner))
            node["source"] = "pct/qm"
        try:
            node["storages"] = parse_pvesm(ssh(target, key, "pvesm status", runner))
        except RuntimeError:
            pass
        for k, cmd, parse in (("snapshots", SNAP_CMD, parse_snapshots), ("backups", BACKUP_CMD, parse_backups)):   # #724
            try:
                node[k] = parse(ssh(target, key, cmd, runner, timeout=240))[:3000]
            except RuntimeError as e:
                node.setdefault("warnings", []).append("%s : %s" % (k, e))
    except Exception as e:  # noqa: BLE001 -- un nœud injoignable n'empêche pas les autres
        node["ok"], node["error"] = False, str(e)[:200]
    return node


def summarize(nodes):
    alerts = [{"code": "pve-remote-unreachable:" + n["name"], "severity": "warning", "message": "PVE %s injoignable par ssh (%s)" % (n["name"], n["error"])}
              for n in nodes if not n["ok"]]
    g = [x for n in nodes for x in n["guests"]]
    return {"nodes": nodes, "alerts": alerts, "summary": {"nodes": len(nodes), "reachable": sum(1 for n in nodes if n["ok"]), "guests": len(g),
                                                          "running": sum(1 for x in g if x["status"] == "running"),
                                                          "stopped": sum(1 for x in g if x["status"] == "stopped")}}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="/etc/si-agent/pve-remote.json")
    a = ap.parse_args(argv)
    try:
        with open(a.config, encoding="utf-8") as fh:
            hosts = [h for h in json.load(fh) if isinstance(h, dict) and h.get("host")]
    except (OSError, ValueError) as e:
        print(json.dumps({"nodes": [], "alerts": [], "error": "configuration %s illisible (%s)" % (a.config, e)}, ensure_ascii=False))
        return 0
    print(json.dumps(summarize([inventory(h) for h in hosts]), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
