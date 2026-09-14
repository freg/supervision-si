#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Plugin si-agent « proxmox » (livraison #487, apprentissage #488,
suivi/accès/journaux #504) -- supervision d'un hyperviseur Proxmox VE :
VM/CT, snapshots, backups (fichiers ET tâches vzdump, jobs planifiés),
stockages, ZFS, accès (console/API par VM, SSH et échecs
d'authentification de l'hyperviseur), journaux internes des VM.

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
import concurrent.futures
import json
import re
import shutil
import socket
import ssl
import subprocess
import sys
import tempfile
import time

PVESH_TIMEOUT = 20          # appel pvesh courant
GUEST_AGENT_TIMEOUT = 8     # appel qemu-guest-agent (peut pendre)

# -- suivi et accès (#504) --------------------------------------------------
# « superviser l'état / disponibilité des VM, un suivi des backup/snapshot,
# le log des accès VM (ssh, http/https) et la récupération des logs
# internes ». Tout est BORNÉ : nombre de tâches lues, lignes de journal,
# taille des extraits rapportés, VM interrogées par passage.
ACCESS_WINDOW_S = 24 * 3600
PVEPROXY_ACCESS_LOG = "/var/log/pveproxy/access.log"
PVEPROXY_TAIL_BYTES = 2 * 1024 * 1024      # ~10 000 lignes d'accès
TASKS_LIMIT = 200
GUEST_LOG_LINES = 300
GUEST_RAW_MAX = 16 * 1024                  # extrait brut conservé par journal et par VM
GUEST_EXEC_TIMEOUT = 10
GUEST_LOGS_PER_PASS = 15                   # VM interrogées par passage (tourniquet)
CONSOLE_RE = re.compile(r"/(vncproxy|termproxy|spiceproxy|vncwebsocket)\b")
ACCESS_LINE_RE = re.compile(
    r"^(?P<ip>\S+) - (?P<user>\S+) \[(?P<ts>[^\]]+)\] \"(?P<method>[A-Z]+) (?P<path>\S+)[^\"]*\" (?P<status>\d{3})")
GUEST_PATH_RE = re.compile(r"/nodes/[^/]+/(qemu|lxc)/(\d+)(/|$|\?)")
SSH_ACCEPTED_RE = re.compile(r"Accepted (?P<method>\S+) for (?P<user>\S+) from (?P<ip>\S+) port")
SSH_FAILED_RE = re.compile(r"Failed (?:password|publickey|none) for (?:invalid user )?(?P<user>\S+) from (?P<ip>\S+) port")
SSH_INVALID_RE = re.compile(r"Invalid user (?P<user>\S+) from (?P<ip>\S+)")
WEB_LINE_RE = re.compile(r"^(?P<ip>\S+) \S+ \S+ \[(?P<ts>[^\]]+)\] \"(?P<method>[A-Z]+) (?P<path>\S+)[^\"]*\" (?P<status>\d{3})")
UPID_RE = re.compile(r"^UPID:(?P<node>[^:]+):(?P<pid>[0-9A-Fa-f]+):(?P<pstart>[0-9A-Fa-f]+):(?P<start>[0-9A-Fa-f]+):(?P<type>[^:]+):(?P<id>[^:]*):(?P<user>[^:]*):")
LOOPBACK_RE = re.compile(r"^(127\.|::1$|fe80:)", re.I)
VZDUMP_RE = re.compile(r"vzdump-(?:qemu|lxc)-(\d+)-")

# -- apprentissage par exploration (#488) ----------------------------------
# « 25 ans de développement à façon, aucune vue globale » : les services
# et URLs ne sont pas DÉCLARÉS, ils sont APPRIS. L'agent a le point de
# vue LAN (DNS interne, VMs joignables) -- c'est lui qui explore.
# Balayage TCP connect BORNÉ : ports courants seulement, 0,4 s par
# tentative, parallélisé (16 fils) -- jamais un nmap.
SCAN_PORTS = [21, 22, 25, 53, 80, 110, 143, 389, 443, 445, 465, 587, 636,
              873, 993, 995, 2049, 3000, 3306, 5000, 5432, 6379, 8006,
              8080, 8443, 9000, 27017]
TLS_PORTS = {443, 465, 587, 636, 993, 995, 8006, 8443, 9443}
HTTP_PORTS = {80, 3000, 5000, 8000, 8080, 9000}
CONNECT_TIMEOUT = 0.4
PROBE_TIMEOUT = 3.0
SCAN_WORKERS = 16
SERVICE_NAMES = {21: "ftp", 22: "ssh", 25: "smtp", 53: "dns", 80: "http", 110: "pop3",
                 143: "imap", 389: "ldap", 443: "https", 445: "smb", 465: "smtps",
                 587: "submission", 636: "ldaps", 873: "rsync", 993: "imaps", 995: "pop3s",
                 2049: "nfs", 3000: "http-alt", 3306: "mysql", 5000: "http-alt",
                 5432: "postgres", 6379: "redis", 8006: "proxmox", 8080: "http-alt",
                 8443: "https-alt", 9000: "http-alt", 27017: "mongodb"}


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


# ---------------------------------------------------------------- pur (#504)

def parse_upid(upid):
    """UPID Proxmox -> {node, type, id, user, starttime} ou None."""
    m = UPID_RE.match(upid or "")
    if not m:
        return None
    return {"node": m.group("node"), "type": m.group("type"), "id": m.group("id") or None,
            "user": m.group("user") or None, "starttime": int(m.group("start"), 16)}


def backup_runs(tasks, now=None):
    """Tâches vzdump (`/nodes/<n>/tasks?typefilter=vzdump`) -> exécutions
    de sauvegarde : {upid, vmid, user, at, ended_at, duration_s, ok,
    status}, les plus récentes d'abord. Une tâche de JOB (plusieurs VM)
    a `vmid: None` -- elle compte dans le suivi global, pas par VM."""
    now = time.time() if now is None else now
    runs = []
    for t in tasks or []:
        if (t.get("type") or "") != "vzdump":
            continue
        info = parse_upid(t.get("upid") or "") or {}
        vmid = t.get("id") if t.get("id") not in (None, "") else info.get("id")
        try:
            vmid = int(vmid)
        except (TypeError, ValueError):
            vmid = None
        start = t.get("starttime") or info.get("starttime")
        end = t.get("endtime")
        status = t.get("status")
        running = end in (None, 0, "") and status in (None, "", "RUNNING")
        runs.append({"upid": t.get("upid"), "vmid": vmid, "user": t.get("user") or info.get("user"),
                     "at": start, "age_s": max(0, int(now - start)) if start else None,
                     "ended_at": end or None, "duration_s": (end - start) if (end and start) else None,
                     "ok": None if running else (status == "OK"), "status": "en cours" if running else (status or "?")})
    runs.sort(key=lambda r: r["at"] or 0, reverse=True)
    return runs


def backup_jobs(rows):
    """`/cluster/backup` -> jobs planifiés lisibles."""
    out = []
    for j in rows or []:
        out.append({"id": j.get("id"), "enabled": j.get("enabled") not in (0, "0", False),
                    "schedule": j.get("schedule") or (("%s %s" % (j.get("dow") or "", j.get("starttime") or "")).strip() or None),
                    "storage": j.get("storage"), "vmids": [int(x) for x in str(j.get("vmid") or "").split(",") if x.strip().isdigit()],
                    "all": bool(j.get("all")), "mode": j.get("mode"), "compress": j.get("compress"),
                    "prune": j.get("prune-backups") or j.get("maxfiles"), "next_run": j.get("next-run"), "comment": j.get("comment")})
    return out


def _parse_clf_time(ts):
    """`13/Sep/2026:10:22:01 +0200` -> epoch (fuseau appliqué) ou None."""
    try:
        base = time.strptime(ts[:20], "%d/%b/%Y:%H:%M:%S")
        offset = ts[21:26] if len(ts) > 25 else "+0000"
        sign = -1 if offset[0] == "-" else 1
        tz = sign * (int(offset[1:3]) * 3600 + int(offset[3:5]) * 60)
        import calendar
        return calendar.timegm(base) - tz
    except (ValueError, IndexError):
        return None


def parse_pveproxy_access(text, now=None, window_s=ACCESS_WINDOW_S):
    """Journal d'accès pveproxy (HTTPS de l'hyperviseur : GUI, API,
    consoles) sur la fenêtre -> {host: {...}, by_vm: {vmid: {...}}}.
    Par VM : sessions console (vncproxy/termproxy/spice), modifications
    (POST/PUT/DELETE), consultations, utilisateurs, adresses, dernier
    accès. Pour l'hyperviseur : requêtes, utilisateurs, adresses, échecs
    d'authentification (401), dernier accès."""
    now = time.time() if now is None else now
    since = now - window_s
    host = {"requests": 0, "auth_failures": 0, "users": {}, "ips": {}, "last_at": None}
    by_vm = {}
    for line in (text or "").splitlines():
        m = ACCESS_LINE_RE.match(line)
        if not m:
            continue
        at = _parse_clf_time(m.group("ts"))
        if at is not None and at < since:
            continue
        user, ip, status, path, method = m.group("user"), m.group("ip"), int(m.group("status")), m.group("path"), m.group("method")
        host["requests"] += 1
        if status == 401:
            host["auth_failures"] += 1
        if user != "-":
            host["users"][user] = host["users"].get(user, 0) + 1
        host["ips"][ip] = host["ips"].get(ip, 0) + 1
        if at and (host["last_at"] is None or at > host["last_at"]):
            host["last_at"] = at
        g = GUEST_PATH_RE.search(path)
        if not g:
            continue
        vmid = int(g.group(2))
        v = by_vm.setdefault(vmid, {"console_sessions": 0, "changes": 0, "views": 0, "users": {}, "ips": {}, "last_at": None, "last_console_at": None})
        if CONSOLE_RE.search(path) and method == "POST":
            v["console_sessions"] += 1
            if at and (v["last_console_at"] is None or at > v["last_console_at"]):
                v["last_console_at"] = at
        elif method in ("POST", "PUT", "DELETE"):
            v["changes"] += 1
        else:
            v["views"] += 1
        if user != "-":
            v["users"][user] = v["users"].get(user, 0) + 1
        v["ips"][ip] = v["ips"].get(ip, 0) + 1
        if at and (v["last_at"] is None or at > v["last_at"]):
            v["last_at"] = at
    return {"host": host, "by_vm": by_vm}


def _top(counter, n=5):
    return [{"key": k, "count": c} for k, c in sorted((counter or {}).items(), key=lambda kv: (-kv[1], kv[0]))[:n]]


def parse_ssh_journal(text):
    """Lignes sshd (journalctl / auth.log) -> {accepted, failed, invalid,
    accepted_by_user, failed_by_ip, last_accepted}."""
    out = {"accepted": 0, "failed": 0, "invalid_users": 0, "accepted_by_user": {}, "failed_by_ip": {}, "last_accepted": None}
    for line in (text or "").splitlines():
        m = SSH_ACCEPTED_RE.search(line)
        if m:
            out["accepted"] += 1
            key = "%s@%s" % (m.group("user"), m.group("ip"))
            out["accepted_by_user"][key] = out["accepted_by_user"].get(key, 0) + 1
            out["last_accepted"] = {"user": m.group("user"), "ip": m.group("ip"), "method": m.group("method"),
                                    "line": line.strip()[:160]}
            continue
        m = SSH_FAILED_RE.search(line)
        if m:
            out["failed"] += 1
            out["failed_by_ip"][m.group("ip")] = out["failed_by_ip"].get(m.group("ip"), 0) + 1
            continue
        if SSH_INVALID_RE.search(line):
            out["invalid_users"] += 1
    out["accepted_by_user"] = _top(out["accepted_by_user"])
    out["failed_by_ip"] = _top(out["failed_by_ip"])
    return out


def parse_web_access(text):
    """Journal d'accès web (format combiné nginx/apache) -> {hits,
    status: {2xx, 3xx, 4xx, 5xx}, top_ips, top_paths, last_at}."""
    out = {"hits": 0, "status": {"2xx": 0, "3xx": 0, "4xx": 0, "5xx": 0}, "top_ips": {}, "top_paths": {}, "last_at": None}
    for line in (text or "").splitlines():
        m = WEB_LINE_RE.match(line)
        if not m:
            continue
        out["hits"] += 1
        cls = "%sxx" % m.group("status")[0]
        if cls in out["status"]:
            out["status"][cls] += 1
        out["top_ips"][m.group("ip")] = out["top_ips"].get(m.group("ip"), 0) + 1
        path = m.group("path").split("?")[0][:120]
        out["top_paths"][path] = out["top_paths"].get(path, 0) + 1
        at = _parse_clf_time(m.group("ts"))
        if at and (out["last_at"] is None or at > out["last_at"]):
            out["last_at"] = at
    out["top_ips"] = _top(out["top_ips"])
    out["top_paths"] = _top(out["top_paths"])
    return out


def pick_guest_batch(vmids, now, per_pass=GUEST_LOGS_PER_PASS):
    """Tourniquet : les VM interrogées à ce passage (bornage du temps de
    collecte), décalé à chaque demi-heure."""
    ids = sorted(vmids)
    if len(ids) <= per_pass:
        return ids
    offset = (int(now // 1800) * per_pass) % len(ids)
    return (ids + ids)[offset:offset + per_pass]


def availability_from_states(states):
    """[(at, status)] -> {samples, running, availability_percent,
    transitions: [{at, from, to}]} -- calcul PUR, aussi utilisé côté
    central (copie dans si-agent/api/store.py)."""
    samples = [(a, s) for a, s in states if a is not None]
    samples.sort()
    running = sum(1 for _, s in samples if s == "running")
    transitions = []
    prev = None
    for at, st in samples:
        if prev is not None and st != prev:
            transitions.append({"at": at, "from": prev, "to": st})
        prev = st
    return {"samples": len(samples), "running": running,
            "availability_percent": round(100.0 * running / len(samples), 1) if samples else None,
            "transitions": transitions[-50:]}


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

    def run(self, cmd, timeout=PVESH_TIMEOUT):
        """Commande locale quelconque (journalctl, pct) ; lève RuntimeError."""
        code, out, err = self._runner(cmd, timeout)
        if code != 0:
            raise RuntimeError((err or out or "%s a échoué" % cmd[0]).strip()[:300])
        return out

    @staticmethod
    def tail_file(path, max_bytes=PVEPROXY_TAIL_BYTES):
        """Fin d'un fichier texte (bornée) ; None s'il est absent/illisible."""
        try:
            with open(path, "rb") as fh:
                fh.seek(0, 2)
                size = fh.tell()
                fh.seek(max(0, size - max_bytes))
                data = fh.read()
            if size > max_bytes:
                data = data.split(b"\n", 1)[-1]  # première ligne tronquée écartée
            return data.decode("utf-8", "replace")
        except OSError:
            return None

    def guest_exec(self, node, vmid, kind, argv, timeout=GUEST_EXEC_TIMEOUT):
        """Exécute `argv` DANS l'invité : qemu-guest-agent (`agent/exec` puis
        `agent/exec-status` jusqu'à la fin, borné) ou `pct exec` pour un
        conteneur. Retourne stdout (str) ; lève RuntimeError."""
        if kind == "lxc":
            return self.run(["pct", "exec", str(vmid), "--"] + list(argv), timeout)
        cmd = ["pvesh", "create", "/nodes/%s/qemu/%s/agent/exec" % (node, vmid), "--output-format", "json"]
        for a in argv:
            cmd += ["--command", a]
        code, out, err = self._runner(cmd, timeout)
        if code != 0:
            raise RuntimeError((err or out or "agent/exec a échoué").strip()[:300])
        try:
            pid = json.loads(out).get("pid")
        except (ValueError, AttributeError):
            raise RuntimeError("agent/exec : réponse invalide")
        if pid is None:
            raise RuntimeError("agent/exec : pas de pid (agent invité absent ou exec interdit)")
        deadline = time.time() + timeout
        while True:
            code, out, err = self._runner(["pvesh", "get", "/nodes/%s/qemu/%s/agent/exec-status" % (node, vmid),
                                           "--pid", str(pid), "--output-format", "json"], timeout)
            if code != 0:
                raise RuntimeError((err or "agent/exec-status a échoué").strip()[:300])
            try:
                st = json.loads(out)
            except ValueError:
                raise RuntimeError("agent/exec-status : réponse invalide")
            if st.get("exited"):
                data = st.get("out-data") or ""
                if st.get("out-truncated"):
                    data += "\n[… tronqué par l'agent invité]"
                return data
            if time.time() > deadline:
                raise RuntimeError("agent/exec : délai dépassé (pid %s)" % pid)
            time.sleep(0.3)


def collect(pve, hostname=None, now=None, connector=None):
    """Collecte complète, tolérante aux pannes partielles : chaque
    section en échec est listée dans `warnings`, jamais silencieuse.
    `connector` (facultatif, #488) active l'apprentissage par
    exploration : ports ouverts, sondes TLS/HTTP, URLs apprises."""
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

    if connector is not None:
        learn_host(vms, connector, warnings)

    # -- #504 : suivi des sauvegardes (tâches vzdump + jobs) ----------------
    runs, jobs = [], []
    try:
        runs = backup_runs(pve.pvesh("/nodes/%s/tasks?typefilter=vzdump&limit=%d&source=all" % (node, TASKS_LIMIT)), now)
    except RuntimeError as exc:
        warnings.append("tâches de sauvegarde : %s" % exc)
    try:
        jobs = backup_jobs(pve.pvesh("/cluster/backup"))
    except RuntimeError as exc:
        warnings.append("jobs de sauvegarde : %s" % exc)
    by_vm_runs = {}
    for r in runs:
        if r["vmid"] is not None:
            by_vm_runs.setdefault(r["vmid"], []).append(r)
    for vm in vms:
        vm["backup_runs"] = by_vm_runs.get(vm["vmid"], [])[:5]
        vm["last_backup_run"] = vm["backup_runs"][0] if vm["backup_runs"] else None
        vm["backup_jobs"] = [j["id"] for j in jobs if j["all"] or vm["vmid"] in j["vmids"]]
    backups_section = {"runs": runs[:50], "jobs": jobs,
                       "failed_24h": sum(1 for r in runs if r["ok"] is False and (r["age_s"] or 0) <= 86400),
                       "ok_24h": sum(1 for r in runs if r["ok"] and (r["age_s"] or 0) <= 86400)}

    # -- #504 : accès à l'hyperviseur et aux VM (pveproxy, SSH, échecs) ----
    access = {"host": None, "ssh": None, "auth_failures_24h": None, "window_s": ACCESS_WINDOW_S}
    txt = pve.tail_file(PVEPROXY_ACCESS_LOG)
    if txt is None:
        warnings.append("accès : %s illisible" % PVEPROXY_ACCESS_LOG)
        by_vm_access = {}
    else:
        parsed = parse_pveproxy_access(txt, now)
        access["host"] = dict(parsed["host"], users=_top(parsed["host"]["users"]), ips=_top(parsed["host"]["ips"]))
        by_vm_access = parsed["by_vm"]
    try:
        access["ssh"] = parse_ssh_journal(pve.run(["journalctl", "-u", "ssh", "-u", "sshd", "-S", "-24h", "-o", "short-iso", "--no-pager", "-q"]))
    except RuntimeError as exc:
        warnings.append("accès SSH de l'hyperviseur : %s" % exc)
    try:
        auth = pve.run(["journalctl", "-t", "pvedaemon", "-t", "pveproxy", "-S", "-24h", "-g", "authentication failure", "--no-pager", "-q", "-o", "cat"])
        access["auth_failures_24h"] = sum(1 for line in auth.splitlines() if line.strip())
    except RuntimeError:
        access["auth_failures_24h"] = None
    for vm in vms:
        a = by_vm_access.get(vm["vmid"])
        vm["access"] = dict(a, users=_top(a["users"]), ips=_top(a["ips"])) if a else None

    # -- #504 : journaux internes des VM (agent invité / pct), tourniquet --
    candidates = {vm["vmid"]: vm for vm in vms if vm.get("status") == "running" and not vm.get("template")
                  and (vm["type"] == "lxc" or vm.get("agent"))}
    for vmid in pick_guest_batch(list(candidates), now):
        vm = candidates[vmid]
        vm["guest_logs"] = collect_guest_logs(pve, node, vm, warnings, now)

    measure = assemble(node_info, vms, storages, zfs, warnings)
    measure["backups"] = backups_section
    measure["access"] = access
    return measure


def collect_guest_logs(pve, node, vm, warnings, now=None):
    """Journaux INTERNES d'une VM (#504) : accès SSH (journal sshd ou
    auth.log) et accès web (nginx/apache, format combiné), résumés +
    extrait brut borné. Rien n'est jamais écrit dans l'invité."""
    now = time.time() if now is None else now
    out = {"collected_at": int(now), "ssh": None, "web": None, "raw": {}, "errors": []}
    kind = vm["type"]
    ssh_cmd = ["sh", "-c", "journalctl -q --no-pager -o short-iso -S -24h -n %d _COMM=sshd 2>/dev/null || tail -n %d /var/log/auth.log /var/log/secure 2>/dev/null" % (GUEST_LOG_LINES, GUEST_LOG_LINES)]
    web_cmd = ["sh", "-c", "tail -q -n %d /var/log/nginx/access.log /var/log/apache2/access.log /var/log/httpd/access_log 2>/dev/null" % GUEST_LOG_LINES]
    for key, cmd, parser in (("ssh", ssh_cmd, parse_ssh_journal), ("web", web_cmd, parse_web_access)):
        try:
            text = pve.guest_exec(node, vm["vmid"], kind, cmd)
        except (RuntimeError, subprocess.TimeoutExpired) as exc:
            out["errors"].append("%s : %s" % (key, exc))
            warnings.append("journaux de %s (%s) : %s" % (vm["vmid"], key, exc))
            continue
        out[key] = parser(text)
        out["raw"][key] = text[-GUEST_RAW_MAX:] if text else ""
    return out


# ------------------------------------------------- apprentissage (#488)

def learn_urls(candidates, vm_ips, resolver):
    """Noms candidats -> URLs entrantes APRISES. `candidates` : liste de
    (nom, source) où source ∈ cert-san / cert-cn / ptr / redirect ;
    `resolver(nom)` -> liste d'IPs ([] si le nom ne résout pas). Un nom
    qui résout vers l'IP de la VM est une URL entrante probable de
    cette VM ; un nom qui ne résout pas est quand même rapporté (trou
    DNS à corriger -- c'est aussi de la supervision)."""
    by_host = {}
    for host, source in candidates or []:
        host = (host or "").strip().lower().rstrip(".")
        if not host or " " in host or "*" in host:
            continue
        by_host.setdefault(host, set()).add(source)
    out = []
    for host in sorted(by_host):
        ips = resolver(host) or []
        out.append({"host": host, "sources": sorted(by_host[host]),
                    "resolves": bool(ips), "ips": ips,
                    "matches_vm": bool(set(ips) & set(vm_ips or []))})
    return out


def assemble_services(open_ports, tls_by_port, http_by_port):
    """Ports ouverts + sondes -> liste de services lisible."""
    services = []
    for port in sorted(open_ports or []):
        svc = {"port": port, "service": SERVICE_NAMES.get(port, "tcp")}
        if port in (tls_by_port or {}):
            svc["tls"] = tls_by_port[port]
        if port in (http_by_port or {}):
            svc["http"] = http_by_port[port]
        services.append(svc)
    return services


class RealConnector(object):
    """Sondes réseau réelles (socket/ssl), toutes bornées. Injectée dans
    learn_host() -- les tests passent un faux connecteur sans réseau."""

    def scan(self, ip, ports=SCAN_PORTS, timeout=CONNECT_TIMEOUT):
        def probe(port):
            try:
                with socket.create_connection((ip, port), timeout=timeout):
                    return port
            except (OSError, OverflowError):
                return None
        with concurrent.futures.ThreadPoolExecutor(max_workers=SCAN_WORKERS) as ex:
            return [p for p in ex.map(probe, ports) if p is not None]

    def tls_cert(self, ip, port, timeout=PROBE_TIMEOUT):
        """Certificat servi (même auto-signé/expiré : on veut le LIRE,
        la validité est un constat, pas un filtre)."""
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        with socket.create_connection((ip, port), timeout=timeout) as raw:
            with ctx.wrap_socket(raw, server_hostname=ip) as tls:
                der = tls.getpeercert(binary_form=True)
        if not der:
            return None
        pem = ssl.DER_cert_to_PEM_cert(der)
        with tempfile.NamedTemporaryFile("w", suffix=".pem", delete=True) as fh:
            fh.write(pem)
            fh.flush()
            try:
                decoded = ssl._ssl._test_decode_cert(fh.name)  # stdlib, stable en 3.x
            except Exception:
                return None
        subject = dict(x[0] for x in decoded.get("subject", ()))
        issuer = dict(x[0] for x in decoded.get("issuer", ()))
        sans = [v for t, v in decoded.get("subjectAltName", ()) if t.lower() == "dns"]
        not_after = decoded.get("notAfter")
        days = None
        if not_after:
            try:
                days = int((ssl.cert_time_to_seconds(not_after) - time.time()) / 86400)
            except (ValueError, OverflowError):
                days = None
        return {"cn": subject.get("commonName"), "sans": sans, "days_left": days,
                "self_signed": subject == issuer}

    def http_get(self, ip, port, timeout=PROBE_TIMEOUT):
        """GET / minimal : statut, Server, Location, <title>."""
        req = ("GET / HTTP/1.0\r\nHost: %s\r\nUser-Agent: si-agent-proxmox/1\r\n\r\n" % ip).encode()
        with socket.create_connection((ip, port), timeout=timeout) as s:
            s.settimeout(timeout)
            s.sendall(req)
            data = b""
            while len(data) < 4096:
                chunk = s.recv(4096 - len(data))
                if not chunk:
                    break
                data += chunk
        text = data.decode("utf-8", "replace")
        head, _, body = text.partition("\r\n\r\n")
        lines = head.split("\r\n")
        m = re.match(r"HTTP/\S+\s+(\d+)", lines[0] if lines else "")
        headers = {}
        for line in lines[1:]:
            k, _, v = line.partition(":")
            if k:
                headers[k.strip().lower()] = v.strip()
        title = None
        mt = re.search(r"<title[^>]*>([^<]{1,120})", body or "", re.I)
        if mt:
            title = mt.group(1).strip()
        location = headers.get("location")
        redirect_host = None
        if location:
            ml = re.match(r"https?://([^/:]+)", location)
            if ml:
                redirect_host = ml.group(1)
        return {"status": int(m.group(1)) if m else None, "server": headers.get("server"),
                "title": title, "redirect_host": redirect_host}

    def ptr(self, ip, timeout=PROBE_TIMEOUT):
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
            try:
                return ex.submit(lambda: socket.gethostbyaddr(ip)[0]).result(timeout=timeout)
            except Exception:
                return None

    def resolve(self, host, timeout=PROBE_TIMEOUT):
        def lookup():
            return sorted({ai[4][0] for ai in socket.getaddrinfo(host, None) if _ip_ok(ai[4][0])})
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
            try:
                return ex.submit(lookup).result(timeout=timeout)
            except Exception:
                return []


def learn_host(vms, connector, warnings):
    """Exploration par VM en marche avec IP connue : ports ouverts,
    sondes TLS/HTTP, PTR, puis apprentissage des URLs. Modifie les VM
    en place (services, urls) ; les échecs de sonde grossissent
    `warnings` sans interrompre le reste."""
    for vm in vms:
        if vm.get("status") != "running" or not vm.get("ips"):
            continue
        ips = vm["ips"]
        open_ports, tls_by_port, http_by_port = [], {}, {}
        candidates = []
        for ip in ips:
            try:
                open_ports += connector.scan(ip)
            except Exception as exc:
                warnings.append("balayage de %s : %s" % (ip, exc))
            ptr = connector.ptr(ip)
            if ptr:
                candidates.append((ptr, "ptr"))
        for port in sorted(set(open_ports)):
            ip = ips[0]  # sondes sur la première IP (services identiques d'une VM)
            if port in TLS_PORTS:
                try:
                    cert = connector.tls_cert(ip, port)
                    if cert:
                        tls_by_port[port] = cert
                        if cert.get("cn"):
                            candidates.append((cert["cn"], "cert-cn"))
                        for name in cert.get("sans") or []:
                            candidates.append((name, "cert-san"))
                except Exception:
                    pass  # port fermé entre-temps ou TLS exotique : pas un warning
            if port in HTTP_PORTS:
                try:
                    page = connector.http_get(ip, port)
                    if page:
                        http_by_port[port] = page
                        if page.get("redirect_host"):
                            candidates.append((page["redirect_host"], "redirect"))
                except Exception:
                    pass
        vm["services"] = assemble_services(sorted(set(open_ports)), tls_by_port, http_by_port)
        vm["urls"] = learn_urls(candidates, ips, connector.resolve)


def main():
    if not shutil.which("pvesh"):
        print(json.dumps({"error": "pvesh absent — cet hôte n'est pas un Proxmox VE"}))
        return 2
    try:
        print(json.dumps(collect(Pve(), connector=RealConnector())))
        return 0
    except Exception as exc:  # la mesure ne doit jamais être muette
        print(json.dumps({"error": "collecte échouée : %s" % exc}))
        return 2


if __name__ == "__main__":
    sys.exit(main())
