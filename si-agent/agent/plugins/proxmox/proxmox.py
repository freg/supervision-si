#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Plugin si-agent « proxmox » (livraison #487) -- supervision d'un
hyperviseur Proxmox VE : VM/CT, snapshots, backups, stockages, ZFS.

Demandé : « un agent proxmox qui supervise le host comme un agent linux
et l'ensemble des vm, snapshot, backup, disques des vm, zfs ». Le host
lui-même est déjà couvert par la mesure `host` de si-agent ; ce plugin
ne collecte que le spécifique PVE, localement :

- `pvesh get <chemin> --output-format json` (API Proxmox en localhost,
  aucun mot de passe à stocker -- root parle à pveproxy via le socket) ;
- `zpool list` / `zpool status` pour les pools (pas de chemin pvesh
  complet pour la santé ZFS).

Adressage IP des VM : qemu-guest-agent quand il est activé ET répond
(config `agent:` + appel borné à 8 s), interfaces LXC natives sinon ;
aucune IP n'est jamais inventée -- le hub recoupe par ailleurs (ARP,
exploration réseau). Sortie JSON sur stdout ; code 2 si l'hôte n'est
pas un Proxmox (pvesh absent) -- mesure en erreur, explicite.

Les fonctions de PUR TRAITEMENT (sans sous-processus) sont testées dans
si-agent/agent/tests/test_proxmox_plugin.py sur des sorties
représentatives de PVE 8 réels."""
import json
import re
import shutil
import socket
import subprocess
import sys
import time

PVESH_TIMEOUT = 20          # appel pvesh courant
GUEST_AGENT_TIMEOUT = 8     # appel qemu-guest-agent (peut pendre)
LOOPBACK_RE = re.compile(r"^(127\.|::1$|fe80:)", re.I)
VZDUMP_RE = re.compile(r"vzdump-(?:qemu|lxc)-(\d+)-")


# ---------------------------------------------------------------- pur

def agent_enabled(config):
    """Drapeau qemu-guest-agent de la config VM : `agent: 1` ou
    `agent: enabled=1,...` selon les versions de PVE."""
    v = (config or {}).get("agent")
    if v is None:
        return False
    s = str(v).strip().lower()
    if s in ("0", "no", "false", "disabled=0", ""):
        return False
    return not s.startswith("enabled=0")


def _ip_ok(addr):
    return bool(addr) and not LOOPBACK_RE.match(addr)


def extract_ips_qemu(data):
    """IPs d'une VM qemu depuis agent/network-get-interfaces. pvesh
    renvoie soit la liste des interfaces, soit {"result": [...]} selon
    le déballage -- les deux sont acceptés. Loopback et link-local
    exclus."""
    if isinstance(data, dict):
        data = data.get("result")
    ips = []
    for iface in data or []:
        for a in (iface or {}).get("ip-addresses") or []:
            addr = a.get("ip-address")
            if _ip_ok(addr):
                ips.append(addr)
    return ips


def extract_ips_lxc(rows):
    """IPs d'un CT LXC depuis /lxc/<id>/interfaces (champs inet/inet6
    au format « 10.0.0.5/24 »)."""
    ips = []
    for row in rows or []:
        for key in ("inet", "inet6"):
            cidr = (row or {}).get(key)
            if not cidr:
                continue
            addr = str(cidr).split("/")[0]
            if _ip_ok(addr):
                ips.append(addr)
    return ips


def newest_backups(rows, now=None):
    """Dernier backup par VM depuis le contenu d'un stockage
    (content=backup) : {vmid: {"at": epoch, "age_s": s, "volid": v}}.
    Le vmid vient du champ `vmid` (PVE récents) ou du volid vzdump."""
    now = time.time() if now is None else now
    out = {}
    for row in rows or []:
        vmid = row.get("vmid")
        if vmid is None:
            m = VZDUMP_RE.search(row.get("volid") or "")
            vmid = int(m.group(1)) if m else None
        if vmid is None:
            continue
        ctime = row.get("ctime")
        if ctime is None:
            continue
        cur = out.get(int(vmid))
        if cur is None or ctime > cur["at"]:
            out[int(vmid)] = {"at": ctime, "age_s": max(0, int(now - ctime)), "volid": row.get("volid")}
    return out


def parse_zpool_list(text):
    """`zpool list -H -p -o name,size,alloc,free,fragmentation,capacity,health`.
    Valeurs en octets bruts (-p) ; « - » ( fragmentation sur certains
    pools ) devient None."""
    pools = []
    for line in (text or "").splitlines():
        parts = line.split("\t")
        if len(parts) < 7:
            parts = line.split()
        if len(parts) < 7:
            continue
        name, size, alloc, free, frag, cap, health = parts[:7]

        def num(v):
            try:
                return int(v)
            except (TypeError, ValueError):
                return None

        def pct(v):
            v = v.rstrip("%")
            try:
                return int(v)
            except (TypeError, ValueError):
                return None
        pools.append({"pool": name, "size": num(size), "alloc": num(alloc), "free": num(free),
                      "frag_pct": pct(frag), "cap_pct": pct(cap), "health": health})
    return pools


def parse_zpool_status(text):
    """Résumé par pool de `zpool status` : état + message d'erreurs
    (« No known data errors » = sain). {pool: {"state": s, "errors": m}}"""
    out = {}
    pool = None
    for line in (text or "").splitlines():
        m = re.match(r"\s*pool:\s*(\S+)", line)
        if m:
            pool = m.group(1)
            out[pool] = {"state": None, "errors": None}
            continue
        if pool is None:
            continue
        m = re.match(r"\s*state:\s*(\S+)", line)
        if m:
            out[pool]["state"] = m.group(1)
            continue
        m = re.match(r"\s*errors:\s*(.+)", line)
        if m:
            out[pool]["errors"] = m.group(1).strip()
    return out


def assemble(node, vms, storages, zfs, warnings):
    """Mesure finale -- la forme lue côté hub (store.latest_proxmox,
    puis type « vm » de la supervision SI)."""
    return {"node": node, "vms": vms, "storages": storages, "zfs": zfs,
            "warnings": warnings, "collected_at": int(time.time())}


# ---------------------------------------------------------------- io

class Pve(object):
    """Appels locaux à l'hôte Proxmox. `runner(cmd, timeout)` est
    injectable -- les tests passent un faux runner sans sous-processus."""

    def __init__(self, runner=None):
        self._runner = runner or self._subprocess_runner

    @staticmethod
    def _subprocess_runner(cmd, timeout):
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return p.returncode, p.stdout, p.stderr

    def pvesh(self, path, timeout=PVESH_TIMEOUT):
        """JSON d'un chemin pvesh ; lève RuntimeError sur échec."""
        code, out, err = self._runner(["pvesh", "get", path, "--output-format", "json"], timeout)
        if code != 0:
            raise RuntimeError((err or out or "pvesh a échoué").strip()[:300])
        try:
            return json.loads(out)
        except ValueError as exc:
            raise RuntimeError("pvesh : JSON invalide (%s)" % exc)

    def zpool(self, args, timeout=PVESH_TIMEOUT):
        code, out, err = self._runner(["zpool"] + args, timeout)
        if code != 0:
            raise RuntimeError((err or "zpool a échoué").strip()[:300])
        return out


def collect(pve, hostname=None, now=None):
    """Collecte complète, tolérante aux pannes partielles : chaque
    section en échec est listée dans `warnings`, jamais silencieuse."""
    now = time.time() if now is None else now
    warnings = []
    hostname = hostname or socket.gethostname().split(".")[0]

    nodes = pve.pvesh("/nodes")
    names = [n.get("node") for n in nodes or []]
    node = hostname if hostname in names else (names[0] if names else hostname)

    status = {}
    try:
        status = pve.pvesh("/nodes/%s/status" % node)
    except RuntimeError as exc:
        warnings.append("statut du nœud : %s" % exc)
    node_info = {"name": node, "pveversion": status.get("pveversion"),
                 "kversion": status.get("kversion"), "uptime_s": status.get("uptime"),
                 "cpu": status.get("cpu"),
                 "mem_used": (status.get("memory") or {}).get("used"),
                 "mem_total": (status.get("memory") or {}).get("total")}

    backups = {}
    storages = []
    try:
        for st in pve.pvesh("/nodes/%s/storage" % node) or []:
            if st.get("enabled") in (0, "0") or st.get("active") in (0, "0"):
                continue
            storages.append({"storage": st.get("storage"), "type": st.get("type"),
                             "used": st.get("used"), "total": st.get("total"), "avail": st.get("avail"),
                             "content": st.get("content")})
            if "backup" in (st.get("content") or ""):
                try:
                    rows = pve.pvesh("/nodes/%s/storage/%s/content?content=backup" % (node, st.get("storage")))
                    for vmid, b in newest_backups(rows, now).items():
                        if vmid not in backups or b["at"] > backups[vmid]["at"]:
                            backups[vmid] = b
                except RuntimeError as exc:
                    warnings.append("backups de %s : %s" % (st.get("storage"), exc))
    except RuntimeError as exc:
        warnings.append("stockages : %s" % exc)

    vms = []
    for kind in ("qemu", "lxc"):
        try:
            guests = pve.pvesh("/nodes/%s/%s" % (node, kind)) or []
        except RuntimeError as exc:
            warnings.append("invités %s : %s" % (kind, exc))
            continue
        for g in guests:
            vmid = g.get("vmid")
            vm = {"vmid": vmid, "name": g.get("name"), "type": kind, "node": node,
                  "status": g.get("status"), "cpu": g.get("cpu"),
                  "mem": g.get("mem"), "maxmem": g.get("maxmem"),
                  "disk": g.get("disk"), "maxdisk": g.get("maxdisk"),
                  "uptime_s": g.get("uptime"), "template": bool(g.get("template")),
                  "ips": [], "agent": None, "snapshots": [],
                  "last_backup": backups.get(vmid)}
            try:
                snaps = [s for s in (pve.pvesh("/nodes/%s/%s/%s/snapshot" % (node, kind, vmid)) or [])
                         if s.get("name") and s["name"] != "current"]
                vm["snapshots"] = [{"name": s.get("name"), "at": s.get("snaptime"),
                                    "age_s": max(0, int(now - s["snaptime"])) if s.get("snaptime") else None,
                                    "description": s.get("description")} for s in snaps]
            except RuntimeError as exc:
                warnings.append("snapshots de %s : %s" % (vmid, exc))
            if g.get("status") == "running" and not vm["template"]:
                if kind == "qemu":
                    try:
                        cfg = pve.pvesh("/nodes/%s/qemu/%s/config" % (node, vmid))
                        vm["agent"] = agent_enabled(cfg)
                    except RuntimeError as exc:
                        warnings.append("config de %s : %s" % (vmid, exc))
                    if vm["agent"]:
                        try:
                            vm["ips"] = extract_ips_qemu(
                                pve.pvesh("/nodes/%s/qemu/%s/agent/network-get-interfaces" % (node, vmid),
                                          timeout=GUEST_AGENT_TIMEOUT))
                        except (RuntimeError, subprocess.TimeoutExpired) as exc:
                            warnings.append("guest-agent de %s : %s" % (vmid, exc))
                else:
                    try:
                        vm["ips"] = extract_ips_lxc(pve.pvesh("/nodes/%s/lxc/%s/interfaces" % (node, vmid)))
                    except RuntimeError as exc:
                        warnings.append("interfaces de %s : %s" % (vmid, exc))
            vms.append(vm)

    zfs = []
    if shutil.which("zpool"):
        try:
            pools = parse_zpool_list(pve.zpool(["list", "-H", "-p", "-o",
                                                "name,size,alloc,free,fragmentation,capacity,health"]))
            states = parse_zpool_status(pve.zpool(["status"]))
            for p in pools:
                st = states.get(p["pool"]) or {}
                p["state"] = st.get("state")
                p["errors"] = st.get("errors")
            zfs = pools
        except (RuntimeError, subprocess.TimeoutExpired) as exc:
            warnings.append("zfs : %s" % exc)

    return assemble(node_info, vms, storages, zfs, warnings)


def main():
    if not shutil.which("pvesh"):
        print(json.dumps({"error": "pvesh absent — cet hôte n'est pas un Proxmox VE"}))
        return 2
    try:
        print(json.dumps(collect(Pve())))
        return 0
    except Exception as exc:  # la mesure ne doit jamais être muette
        print(json.dumps({"error": "collecte échouée : %s" % exc}))
        return 2


if __name__ == "__main__":
    sys.exit(main())
