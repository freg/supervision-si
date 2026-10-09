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
    node = {"name": name, "host": h["host"], "ok": True, "error": None, "guests": [], "storages": [], "source": None}
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
