"""Collecteurs de l'hôte (livraison #420, backlog 63) -- « l'agent host
surveille le host : CPU, disque, mémoire, logs, risques internes ».

Tout passe par `/proc`, `/sys`, `/etc` et quelques binaires système
(`systemctl`, `journalctl`, `ss`), jamais une bibliothèque tierce :
l'agent doit tourner tel quel sur un Debian/Ubuntu minimal, un Pi, une
VM ancienne, avec le seul Python 3 du système. `files` (lecture de
fichier) et `cmd` (exécution) sont INJECTABLES : les tests rejouent des
contenus réels capturés, sans hôte.

Chaque collecteur renvoie un dict sérialisable ; un collecteur qui n'a pas
ce qu'il lui faut (fichier absent, binaire absent) renvoie ce qu'il peut
et jamais une exception -- l'agent doit produire une mesure même sur un
hôte exotique, quitte à ce qu'elle soit partielle et le dise
(`partial: [...]`).
"""
import os
import re
import shutil
import subprocess
import time

DEFAULT_TIMEOUT = 15


class CmdResult(object):
    __slots__ = ("returncode", "stdout", "stderr")

    def __init__(self, returncode, stdout, stderr=""):
        self.returncode, self.stdout, self.stderr = returncode, stdout, stderr


def run_cmd(argv, timeout=DEFAULT_TIMEOUT, env=None):
    """Exécution réelle ; jamais d'exception (binaire absent → -127, délai
    → -124), même contrat que netprobe_agent.tasks.run_cmd. `env` :
    variables AJOUTÉES à l'environnement courant (plugins)."""
    try:
        full_env = None
        if env:
            full_env = dict(os.environ)
            full_env.update({k: str(v) for k, v in env.items()})
        p = subprocess.run(argv, capture_output=True, text=True, timeout=timeout, env=full_env)
        return CmdResult(p.returncode, p.stdout, p.stderr)
    except FileNotFoundError:
        return CmdResult(-127, "", "binaire introuvable : %s" % argv[0])
    except subprocess.TimeoutExpired:
        return CmdResult(-124, "", "délai dépassé (%ss) : %s" % (timeout, " ".join(argv)))
    except OSError as exc:
        return CmdResult(-1, "", str(exc))


def read_file(path):
    try:
        with open(path, "r", errors="replace") as fh:
            return fh.read()
    except OSError:
        return ""


def _kv_file(text):
    """`/etc/os-release`, `/proc/meminfo`… → dict (clé: valeur brute)."""
    out = {}
    for line in (text or "").splitlines():
        if "=" in line and ":" not in line.split("=", 1)[0]:
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip().strip('"')
        elif ":" in line:
            k, v = line.split(":", 1)
            out[k.strip()] = v.strip()
    return out


def _kb(value):
    m = re.match(r"\s*(\d+)", value or "")
    return int(m.group(1)) * 1024 if m else None


# ---------------------------------------------------------------------
# Identité et système
# ---------------------------------------------------------------------

def collect_system(files=read_file, hostname=None, exists=os.path.exists):
    osr = _kv_file(files("/etc/os-release"))
    uptime = None
    m = re.match(r"([\d.]+)", files("/proc/uptime") or "")
    if m:
        uptime = float(m.group(1))
    kernel = (files("/proc/sys/kernel/osrelease") or "").strip() or None
    cpus = len([l for l in (files("/proc/cpuinfo") or "").splitlines() if l.startswith("processor")]) or None
    model = None
    for line in (files("/proc/cpuinfo") or "").splitlines():
        if line.lower().startswith(("model name", "hardware", "model")):
            model = line.split(":", 1)[1].strip()
            if line.lower().startswith("model name"):
                break
    # Raspberry Pi : /proc/device-tree/model est plus parlant que cpuinfo.
    dt_model = (files("/proc/device-tree/model") or "").replace("\x00", "").strip()
    if dt_model:
        model = dt_model
    return {
        "hostname": hostname or (files("/etc/hostname") or "").strip() or None,
        "os": osr.get("PRETTY_NAME") or osr.get("NAME"),
        "os_id": osr.get("ID"),
        "os_version": osr.get("VERSION_ID"),
        "kernel": kernel,
        "cpus": cpus,
        "cpu_model": model,
        "uptime_seconds": uptime,
        # Debian/Ubuntu : fichier (souvent vide) déposé par apt quand un
        # redémarrage est requis -- son EXISTENCE compte, pas son contenu.
        "reboot_required": bool(exists("/var/run/reboot-required")),
    }


# ---------------------------------------------------------------------
# CPU / charge / mémoire
# ---------------------------------------------------------------------

def parse_proc_stat(text):
    """Première ligne `cpu ...` → (busy, total) en jiffies, ou None."""
    for line in (text or "").splitlines():
        if line.startswith("cpu "):
            parts = [int(x) for x in line.split()[1:] if x.isdigit()]
            if len(parts) < 4:
                return None
            idle = parts[3] + (parts[4] if len(parts) > 4 else 0)   # idle + iowait
            total = sum(parts)
            return total - idle, total
    return None


def cpu_percent(before, after):
    """Usage CPU entre deux lectures de /proc/stat (0-100), None si
    impossible (même instant, lecture manquante)."""
    if not before or not after:
        return None
    d_busy = after[0] - before[0]
    d_total = after[1] - before[1]
    if d_total <= 0:
        return None
    return round(100.0 * d_busy / d_total, 1)


def collect_cpu(files=read_file, sleep=time.sleep, sample_seconds=0.5, previous=None):
    """`previous` = (busy, total) d'un passage précédent : évite de dormir
    dans la boucle de l'agent ; sans lui, deux lectures espacées de
    `sample_seconds`."""
    now_stat = parse_proc_stat(files("/proc/stat"))
    if previous is None and now_stat is not None and sample_seconds:
        sleep(sample_seconds)
        previous, now_stat = now_stat, parse_proc_stat(files("/proc/stat"))
    load = (files("/proc/loadavg") or "").split()
    try:
        load1, load5, load15 = float(load[0]), float(load[1]), float(load[2])
    except (IndexError, ValueError):
        load1 = load5 = load15 = None
    return {
        "percent": cpu_percent(previous, now_stat),
        "load1": load1, "load5": load5, "load15": load15,
        "_stat": now_stat,   # pour le passage suivant (retiré avant envoi)
    }


def collect_memory(files=read_file):
    mi = _kv_file(files("/proc/meminfo"))
    total = _kb(mi.get("MemTotal"))
    available = _kb(mi.get("MemAvailable"))
    if available is None and total is not None:
        free = _kb(mi.get("MemFree")) or 0
        available = free + (_kb(mi.get("Buffers")) or 0) + (_kb(mi.get("Cached")) or 0)
    swap_total = _kb(mi.get("SwapTotal"))
    swap_free = _kb(mi.get("SwapFree"))
    used_pct = round(100.0 * (total - available) / total, 1) if total and available is not None else None
    swap_used_pct = round(100.0 * (swap_total - swap_free) / swap_total, 1) if swap_total and swap_free is not None else None
    return {
        "total_bytes": total, "available_bytes": available, "used_percent": used_pct,
        "swap_total_bytes": swap_total, "swap_used_percent": swap_used_pct,
    }


# ---------------------------------------------------------------------
# Disques
# ---------------------------------------------------------------------

_SKIP_FS = {"proc", "sysfs", "devtmpfs", "devpts", "tmpfs", "cgroup", "cgroup2", "pstore", "bpf", "securityfs",
            "debugfs", "tracefs", "configfs", "mqueue", "hugetlbfs", "fusectl", "fuse.gvfsd-fuse", "autofs",
            "binfmt_misc", "rpc_pipefs", "nsfs", "overlay", "squashfs", "efivarfs", "ramfs"}


def parse_mounts(text):
    """`/proc/mounts` → [{device, mountpoint, fstype}] des systèmes de
    fichiers « réels » (disques, cartes SD, NFS…), sans les pseudo-fs."""
    out = []
    seen = set()
    for line in (text or "").splitlines():
        parts = line.split()
        if len(parts) < 3:
            continue
        dev, mp, fs = parts[0], parts[1].replace("\\040", " "), parts[2]
        if fs in _SKIP_FS or mp.startswith(("/snap/", "/proc", "/sys", "/dev", "/run")) or mp in seen:
            continue
        seen.add(mp)
        out.append({"device": dev, "mountpoint": mp, "fstype": fs})
    return out


def collect_disks(files=read_file, usage=shutil.disk_usage):
    disks = []
    for m in parse_mounts(files("/proc/mounts")):
        try:
            u = usage(m["mountpoint"])
        except OSError:
            continue
        total = u.total
        if not total:
            continue
        disks.append({
            "mountpoint": m["mountpoint"], "device": m["device"], "fstype": m["fstype"],
            "total_bytes": total, "used_bytes": u.used, "free_bytes": u.free,
            "used_percent": round(100.0 * u.used / total, 1),
        })
    return disks


# ---------------------------------------------------------------------
# Services, ports, journaux, comptes
# ---------------------------------------------------------------------

def collect_failed_services(cmd=run_cmd):
    r = cmd(["systemctl", "--failed", "--no-legend", "--plain", "--no-pager"])
    if r.returncode < 0:
        return {"available": False, "failed": []}
    failed = []
    for line in r.stdout.splitlines():
        parts = line.split()
        if parts and parts[0].endswith((".service", ".timer", ".socket", ".mount")):
            failed.append(parts[0])
        elif len(parts) > 1 and parts[1].endswith((".service", ".timer", ".socket", ".mount")):
            failed.append(parts[1])   # ligne avec puce « ● »
    return {"available": True, "failed": failed}


def parse_ss_listening(text):
    """`ss -Hlntup` → [{proto, local, port, process}], toutes adresses."""
    out = []
    for line in (text or "").splitlines():
        parts = line.split()
        if len(parts) < 5:
            continue
        proto = parts[0]
        local = parts[4] if parts[1] in ("LISTEN", "UNCONN") else parts[3]
        if ":" not in local:
            continue
        addr, port = local.rsplit(":", 1)
        try:
            port = int(port)
        except ValueError:
            continue
        addr = addr.strip("[]")
        process = None
        m = re.search(r'users:\(\("([^"]+)"', line)
        if m:
            process = m.group(1)
        out.append({"proto": proto, "address": addr, "port": port, "process": process,
                    "exposed": addr in ("0.0.0.0", "*", "::", "")})
    return out


def collect_listening_ports(cmd=run_cmd):
    r = cmd(["ss", "-Hlntup"])
    if r.returncode < 0:
        return {"available": False, "ports": []}
    return {"available": True, "ports": parse_ss_listening(r.stdout)}


def collect_log_errors(cmd=run_cmd, files=read_file, lines=40):
    """Dernières erreurs du journal : journald si présent, sinon la queue
    de /var/log/syslog ou /var/log/messages filtrée sur err/crit/fail."""
    r = cmd(["journalctl", "-p", "err", "-n", str(lines), "--no-pager", "-o", "short-iso", "--since", "-24h"])
    if r.returncode >= 0 and r.returncode != -127:
        entries = [l for l in r.stdout.splitlines() if l and not l.startswith("-- ")]
        return {"source": "journald", "lines": entries[-lines:]}
    for path in ("/var/log/syslog", "/var/log/messages"):
        text = files(path)
        if text:
            pat = re.compile(r"\b(error|err|crit|critical|fail(ed|ure)?|panic|oom)\b", re.IGNORECASE)
            entries = [l for l in text.splitlines()[-2000:] if pat.search(l)]
            return {"source": path, "lines": entries[-lines:]}
    return {"source": None, "lines": []}


def collect_accounts(files=read_file):
    """Comptes à privilèges : membres de sudo/wheel/adm, comptes à shell
    interactif, comptes root-équivalents (uid 0 autres que root)."""
    groups = {}
    for line in (files("/etc/group") or "").splitlines():
        parts = line.split(":")
        if len(parts) >= 4:
            groups[parts[0]] = [u for u in parts[3].split(",") if u]
    sudoers = sorted(set(groups.get("sudo", []) + groups.get("wheel", []) + groups.get("admin", [])))
    interactive, uid0 = [], []
    for line in (files("/etc/passwd") or "").splitlines():
        parts = line.split(":")
        if len(parts) < 7:
            continue
        name, uid, shell = parts[0], parts[2], parts[6]
        if uid == "0" and name != "root":
            uid0.append(name)
        if shell.endswith(("sh",)) and not shell.endswith(("nologin", "false")):
            interactive.append(name)
    return {"sudoers": sudoers, "interactive": interactive, "uid0_not_root": uid0}


# ---------------------------------------------------------------------
# Inventaire des capacités (binaires disponibles)
# ---------------------------------------------------------------------

KNOWN_TOOLS = ["nmap", "iperf3", "tcpdump", "iw", "iwconfig", "snmpwalk", "snmpget", "ss", "ip", "arp",
               "journalctl", "systemctl", "docker", "python3", "curl", "wget", "dig", "nslookup", "ping",
               "traceroute", "mtr", "lldpctl", "ethtool", "smartctl", "sensors", "vcgencmd", "apt", "dnf"]


def collect_tools(which=shutil.which, tools=KNOWN_TOOLS):
    found = {}
    for t in tools:
        p = which(t)
        if p:
            found[t] = p
    return {"available": sorted(found), "paths": found, "missing": [t for t in tools if t not in found]}


# ---------------------------------------------------------------------
# Passage complet
# ---------------------------------------------------------------------

def collect_all(files=read_file, cmd=run_cmd, usage=shutil.disk_usage, which=shutil.which,
                sleep=time.sleep, previous_cpu=None, hostname=None, include_tools=True, exists=os.path.exists):
    """Une mesure `host` complète. `previous_cpu` = `_stat` du passage
    précédent pour un pourcentage CPU sans pause."""
    partial = []
    system = collect_system(files, hostname=hostname, exists=exists)
    cpu = collect_cpu(files, sleep=sleep, previous=previous_cpu)
    memory = collect_memory(files)
    disks = collect_disks(files, usage=usage)
    services = collect_failed_services(cmd)
    ports = collect_listening_ports(cmd)
    logs = collect_log_errors(cmd, files)
    accounts = collect_accounts(files)
    if system.get("os") is None:
        partial.append("os-release")
    if cpu.get("load1") is None:
        partial.append("loadavg")
    if memory.get("total_bytes") is None:
        partial.append("meminfo")
    if not disks:
        partial.append("mounts")
    if not services.get("available"):
        partial.append("systemctl")
    if not ports.get("available"):
        partial.append("ss")
    if logs.get("source") is None:
        partial.append("logs")
    data = {
        "system": system,
        "cpu": {k: v for k, v in cpu.items() if not k.startswith("_")},
        "memory": memory,
        "disks": disks,
        "services": services,
        "ports": ports,
        "logs": logs,
        "accounts": accounts,
        "partial": partial,
    }
    if include_tools:
        data["tools"] = collect_tools(which)
    return data, cpu.get("_stat")
