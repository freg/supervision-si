# -*- coding: utf-8 -*-
"""Collecteurs Windows 10/11 de si-agent (livraison #440, backlog 63
« Windows à explorer ») -- même paquet, même protocole, mêmes mesures
(`host`, `risks`, `netview`, `inventory`) que sous Linux : seule la source
change. Chaque mesure vient d'UN script PowerShell livré avec le paquet
(`si_agent/win/*.ps1`, Windows PowerShell 5.1 fourni avec Windows) qui
imprime UN objet JSON ; ce module le lance (`powershell.exe -NoProfile
-NonInteractive -ExecutionPolicy Bypass -File`) et traduit le résultat
dans la forme que le central, les risques et la tuile connaissent déjà
(voir host.py / review.py / netview.py pour les formes Linux).

Les fonctions `map_*` sont PURES (JSON -> mesure) et testées sur des
sorties représentatives ; `collect_*` les enchaînent avec l'exécution
réelle. Les scripts eux-mêmes ont été exécutés sous PowerShell 7 (Linux)
pour leur syntaxe et leur enchaînement -- pas encore sur un Windows réel
(premier test prévu par la personne).
"""
import json
import os
import re
import sys

from . import host, netview

IS_WINDOWS = sys.platform == "win32"
WIN_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "win")
POWERSHELL = "powershell.exe" if IS_WINDOWS else "pwsh"
PS_TIMEOUTS = {"host": 90, "activity": 90, "hardware": 120, "netview": 60}


def script_path(name):
    return os.path.join(WIN_DIR, name + ".ps1")


def run_ps(cmd, name, timeout=None):
    """(objet JSON | None, erreur | None) -- un script `win/<name>.ps1`."""
    argv = [POWERSHELL, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", script_path(name)]
    r = cmd(argv, timeout=timeout or PS_TIMEOUTS.get(name, 60))
    out = (r.stdout or "").strip().lstrip("\ufeff")
    if r.returncode < 0:
        return None, r.stderr or ("échec %s" % name)
    if not out:
        return None, (r.stderr or "").strip()[:300] or ("aucune sortie de %s.ps1" % name)
    # PowerShell peut faire précéder le JSON d'avertissements : on prend à partir du premier '{'
    start = out.find("{")
    if start < 0:
        return None, "sortie de %s.ps1 sans JSON : %s" % (name, out[:200])
    try:
        return json.loads(out[start:]), None
    except ValueError as exc:
        return None, "JSON de %s.ps1 illisible : %s" % (name, exc)


def _mac(s):
    return s.replace("-", ":").lower() if s else None


def _human_size(n):
    try:
        n = float(n)
    except (TypeError, ValueError):
        return None
    for unit in ("", "K", "M", "G", "T", "P"):
        if n < 1000 or unit == "P":
            return ("%d%s" % (n, unit)) if unit == "" else ("%.1f%s" % (n, unit)).replace(".0", "")
        n /= 1024.0
    return None


# ---------------------------------------------------------------------
# host
# ---------------------------------------------------------------------

def map_host(raw, hostname=None):
    """JSON de host.ps1 -> mesure `host` (forme de host.collect_all)."""
    raw = raw or {}
    system = raw.get("system") or {}
    partial = list(raw.get("partial") or [])
    mem = raw.get("memory") or {}
    total, avail = mem.get("total_bytes"), mem.get("available_bytes")
    used_pct = round(100.0 * (total - avail) / total, 1) if total and avail is not None else None
    page_total, page_used = mem.get("page_total_bytes"), mem.get("page_used_bytes")
    disks = []
    for d in raw.get("disks") or []:
        t, f = d.get("total_bytes"), d.get("free_bytes")
        entry = {"mountpoint": d.get("mountpoint"), "device": d.get("provider") or d.get("label") or d.get("mountpoint"), "fstype": d.get("fstype"),
                 "remote": d.get("drive_type") == 4, "removable": d.get("drive_type") == 2, "visible": True,
                 "total_bytes": t, "used_bytes": (t - f) if t and f is not None else None, "free_bytes": f,
                 "used_percent": round(100.0 * (t - f) / t, 1) if t and f is not None else None}
        if not t:
            entry["error"] = "taille inconnue (lecteur non prêt ou inaccessible pour le compte de l'agent)"
        disks.append(entry)
    ports = []
    for p in raw.get("ports") or []:
        addr = p.get("address") or ""
        ports.append({"proto": p.get("proto"), "address": addr, "port": p.get("port"), "process": p.get("process"), "pid": p.get("pid"),
                      "exposed": addr in ("0.0.0.0", "::", "*", "")})
    lines = []
    for e in raw.get("logs") or []:
        lines.append("%s [%s] %s (%s) : %s" % (e.get("time") or "?", e.get("log") or "?", e.get("source") or "?", e.get("id"), e.get("message") or ""))
    acc = raw.get("accounts") or {}
    services = raw.get("services") or {}
    data = {
        "system": {
            "hostname": hostname or system.get("hostname"),
            "os": system.get("os"), "os_id": "windows", "os_version": system.get("os_version"),
            "kernel": ("build %s" % system.get("build")) if system.get("build") else None,
            "display_version": system.get("display_version"), "arch": system.get("arch"),
            "cpus": system.get("cpus"), "cpu_model": (system.get("cpu_model") or "").strip() or None,
            "uptime_seconds": system.get("uptime_seconds"), "reboot_required": bool(system.get("reboot_required")),
            "domain": system.get("domain"), "part_of_domain": system.get("part_of_domain"), "install_date": system.get("install_date"),
        },
        "cpu": {"percent": (raw.get("cpu") or {}).get("percent"), "load1": None, "load5": None, "load15": None},
        "memory": {"total_bytes": total, "available_bytes": avail, "used_percent": used_pct,
                   "swap_total_bytes": page_total, "swap_used_percent": round(100.0 * page_used / page_total, 1) if page_total and page_used is not None else None},
        "disks": disks,
        "services": {"available": "services" not in partial, "failed": list(services.get("failed") or []), "running_count": services.get("running_count")},
        "ports": {"available": "tcp-listen" not in partial, "ports": ports},
        "logs": {"source": "eventlog" if lines or "logs" not in partial else None, "lines": lines},
        "accounts": {"sudoers": list(acc.get("admins") or []), "interactive": list(acc.get("local_users") or []), "uid0_not_root": [],
                     "console_user": acc.get("console_user")},
        "windows": raw.get("windows") or {},
        "partial": partial,
    }
    if data["system"].get("os") is None and "os" not in partial:
        partial.append("os")
    return data


def collect_all(files=None, cmd=host.run_cmd, usage=None, which=None, sleep=None, previous_cpu=None, hostname=None, include_tools=True, exists=None):
    """Signature de host.collect_all ; (mesure, previous_cpu=None)."""
    raw, err = run_ps(cmd, "host")
    if raw is None:
        data = map_host({}, hostname=hostname)
        data["partial"] = ["powershell:host"]
        data["error"] = err
    else:
        data = map_host(raw, hostname=hostname)
    if include_tools:
        data["tools"] = collect_tools(which or __import__("shutil").which)
    return data, None


KNOWN_TOOLS = ("powershell", "pwsh", "netstat", "ipconfig", "wmic", "msiexec", "docker", "ssh", "python", "py")


def collect_tools(which):
    return [t for t in KNOWN_TOOLS if which(t)]


# ---------------------------------------------------------------------
# activity
# ---------------------------------------------------------------------

def parse_quser(lines):
    """Sortie de `quser` (colonnes à largeur fixe, en-têtes localisés) ->
    [{user, session, id, state, idle, since}] ; la première ligne donne
    les positions des colonnes, un `>` marque la session courante."""
    lines = [l for l in (lines or []) if l and l.strip()]
    if len(lines) < 2:
        return []
    header = lines[0]
    starts = [m.start() for m in re.finditer(r"\S+(?: \S+)*", header)]  # un libellé peut contenir UN espace (« TEMPS INACT. »)
    if len(starts) < 4:
        return []
    out = []
    for row in lines[1:]:
        # chaque valeur (mot ou mots séparés d'UN espace) rejoint la colonne
        # dont l'en-tête commence à sa gauche (tolérance d'un caractère :
        # les colonnes numériques sont alignées à droite)
        cols = [""] * len(starts)
        for m in re.finditer(r"\S+(?: \S+)*", row):
            idx = 0
            for k, st in enumerate(starts):
                if st <= m.start() + 1:
                    idx = k
            cols[idx] = (cols[idx] + " " + m.group(0)).strip()
        user = cols[0].lstrip(">").strip()
        if not user:
            continue
        out.append({"user": user, "session": cols[1] or None, "id": cols[2] or None, "state": cols[3] or None,
                    "idle": cols[4] if len(cols) > 4 else None, "since": (cols[5] or None) if len(cols) > 5 else None})
    return out


_LOGON_TTY = {2: "console", 10: "rdp", 11: "cached", 7: "unlock"}


def map_activity(raw):
    raw = raw or {}
    partial = list(raw.get("partial") or [])

    def proc(p):
        return {"pid": p.get("pid"), "user": p.get("user"), "cpu_percent": p.get("cpu_percent"), "mem_percent": None,
                "rss_bytes": p.get("rss_bytes"), "elapsed_seconds": p.get("elapsed_seconds"), "command": p.get("command")}
    sessions = [{"user": s.get("user"), "tty": _LOGON_TTY.get(s.get("type"), str(s.get("type"))), "since": s.get("since"), "from": None}
                for s in raw.get("sessions") or []]
    if not sessions:
        sessions = [{"user": q["user"], "tty": q.get("session") or "déconnectée", "since": q.get("since"), "from": None, "state": q.get("state")}
                    for q in parse_quser(raw.get("sessions_raw"))]
    logins = [{"user": l.get("user"), "tty": _LOGON_TTY.get(l.get("type"), str(l.get("type"))), "from": None if l.get("from") in (None, "-", "::1", "127.0.0.1") else l.get("from"),
               "at": l.get("at")} for l in raw.get("last_logins") or []]
    running = raw.get("running_services")
    return {"process_count": raw.get("process_count"), "top_cpu": [proc(p) for p in raw.get("top_cpu") or []],
            "top_memory": [proc(p) for p in raw.get("top_memory") or []], "sessions": sessions, "last_logins": logins,
            "running_services": list(running) if running is not None else None,
            "running_services_count": raw.get("running_services_count") if running is not None else None,
            "updates_available": raw.get("updates_available"), "partial": partial}


def collect_activity(cmd=host.run_cmd, files=None):
    raw, err = run_ps(cmd, "activity")
    if raw is None:
        d = map_activity({})
        d["partial"] = ["powershell:activity"]
        d["error"] = err
        return d
    return map_activity(raw)


# ---------------------------------------------------------------------
# hardware (inventory)
# ---------------------------------------------------------------------

def map_hardware(raw):
    raw = raw or {}
    c = raw.get("cpu") or {}
    cpu = {"model": c.get("model"), "cpus": c.get("cpus"), "sockets": c.get("sockets"), "cores_per_socket": c.get("cores_per_socket"),
           "threads_per_core": c.get("threads_per_core"), "arch": c.get("arch"), "mhz_max": c.get("mhz_max"),
           "hypervisor": c.get("hypervisor"), "virtualization": None} if c else None
    disks = []
    for d in raw.get("disks") or []:
        media = (d.get("media") or "").upper()
        disks.append({"name": d.get("name"), "model": d.get("model"), "serial": d.get("serial"), "size": _human_size(d.get("size_bytes")),
                      "size_bytes": d.get("size_bytes"), "rotational": (None if not media else media not in ("SSD", "NVME", "SCM")),
                      "transport": (d.get("bus") or d.get("interface") or "").lower() or None, "vendor": None, "health": d.get("health")})
    nics = [{"name": n.get("name"), "mac": _mac(n.get("mac")), "state": n.get("state"), "speed_mbps": n.get("speed_mbps"), "description": n.get("description")}
            for n in raw.get("nics") or []]
    return {
        "vendor": raw.get("vendor"), "product": raw.get("product"), "product_version": raw.get("product_version"), "serial": (raw.get("serial") or "").strip() or None,
        "uuid": raw.get("uuid"), "bios": raw.get("bios"), "board": raw.get("board"), "cpu": cpu, "memory_total_bytes": raw.get("memory_total_bytes"),
        "disks": disks, "nics": nics, "gpus": list(raw.get("gpus") or []), "virtualization": raw.get("virtualization"),
        "software": list(raw.get("software") or []), "software_count": raw.get("software_count"),
        "partial": list(raw.get("partial") or []),
    }


def collect_hardware(cmd=host.run_cmd, files=None):
    raw, err = run_ps(cmd, "hardware")
    if raw is None:
        d = map_hardware({})
        d["partial"] = ["powershell:hardware"]
        d["error"] = err
        return d
    return map_hardware(raw)


# ---------------------------------------------------------------------
# netview
# ---------------------------------------------------------------------

_NEIGH_STATE = {"reachable": "reachable", "stale": "stale", "delay": "delay", "probe": "probe", "incomplete": "incomplete", "unreachable": "failed", "permanent": "permanent"}


def map_netview(raw):
    raw = raw or {}
    by_index = {}
    interfaces = []
    for a in raw.get("adapters") or []:
        itf = {"name": a.get("name"), "mac": _mac(a.get("mac")), "mtu": a.get("mtu"), "state": "up" if (a.get("status") or "").lower() == "up" else "down",
               "description": a.get("description"), "speed": a.get("speed"), "addresses": []}
        by_index[a.get("index")] = itf
        interfaces.append(itf)
    for a in raw.get("addresses") or []:
        ip = a.get("ip")
        if not ip:
            continue
        fam = "inet6" if (a.get("family") or "").lower() == "ipv6" or ":" in ip else "inet"
        scope = "link" if ip.lower().startswith("fe80") or ip.startswith("169.254.") else ("host" if ip.startswith("127.") or ip == "::1" else "global")
        itf = by_index.get(a.get("index"))
        if itf is None:
            itf = {"name": a.get("alias"), "mac": None, "mtu": None, "state": "up", "addresses": []}
            by_index[a.get("index")] = itf
            interfaces.append(itf)
        itf["addresses"].append({"ip": ip, "prefix": a.get("prefix"), "family": fam, "scope": scope, "origin": a.get("origin")})
    # boucle locale écartée (comme `ip addr` -> netview.parse_ip_addr ne garde que les vraies interfaces)
    interfaces = [i for i in interfaces if (i["addresses"] or i.get("state") == "up") and not any(a["scope"] == "host" for a in i["addresses"])]
    routes = []
    for r in raw.get("routes") or []:
        dst, gw = r.get("dst") or "", r.get("gateway") or ""
        if (r.get("family") or "").lower() == "ipv6" or ":" in dst:
            continue
        if dst.startswith(("224.", "255.255.255.255", "127.")) or dst.endswith("/32"):
            continue
        if dst == "0.0.0.0/0":
            kind = "default"
        elif gw in ("", "0.0.0.0"):
            kind = "direct"
            gw = None
        else:
            kind = "via"
        routes.append({"dst": "default" if kind == "default" else dst, "gateway": gw, "dev": r.get("alias"), "protocol": (r.get("protocol") or "").lower() or None,
                       "scope": "link" if kind == "direct" else None, "metric": r.get("metric"), "kind": kind})
    routes.sort(key=lambda r: (r["kind"] != "default", r.get("metric") or 0))
    neighbors = []
    for n in raw.get("neighbors") or []:
        ip = n.get("ip") or ""
        if not ip or ip.startswith(("224.", "239.", "255.", "ff")) or ip == "255.255.255.255":
            continue
        neighbors.append({"ip": ip, "mac": _mac(n.get("mac")), "dev": n.get("alias"), "state": _NEIGH_STATE.get((n.get("state") or "").lower(), (n.get("state") or "").lower() or None)})
    conns = [{"proto": c.get("proto") or "tcp", "local_ip": c.get("local_ip"), "local_port": c.get("local_port"), "remote_ip": c.get("remote_ip"),
              "remote_port": c.get("remote_port"), "process": c.get("process"), "pid": c.get("pid")} for c in raw.get("connections") or []]
    dns = raw.get("dns") or {}
    return {"interfaces": interfaces, "routes": routes, "neighbors": neighbors, "connections": conns[:500],
            "dns": {"servers": list(dns.get("servers") or []), "search": list(dns.get("search") or [])},
            "summary": netview.summarize(interfaces, routes, neighbors, conns), "partial": list(raw.get("partial") or [])}


def collect_netview(cmd=host.run_cmd, files=None):
    raw, err = run_ps(cmd, "netview")
    if raw is None:
        d = map_netview({})
        d["partial"] = ["powershell:netview"]
        d["error"] = err
        return d
    return map_netview(raw)
