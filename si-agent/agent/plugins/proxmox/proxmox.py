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

    return assemble(node_info, vms, storages, zfs, warnings)


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
