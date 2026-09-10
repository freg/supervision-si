# -*- coding: utf-8 -*-
"""Collecteurs macOS de si-agent (livraison #451, backlog 63 « agent Mac »)
-- même paquet, même protocole, mêmes mesures (`host`, `activity`,
`hardware`, `netview`, `inventory`) que sous Linux et Windows : seule la
source change. Contrairement à Windows (#440), macOS a un vrai shell et le
paquet tourne déjà en Python, donc pas de scripts séparés : ce module lance
directement les commandes macOS (`sw_vers`, `sysctl`, `vm_stat`, `df`,
`mount`, `launchctl`, `lsof`, `dscl`, `system_profiler`, `ifconfig`,
`netstat`, `arp`) et traduit leur sortie dans la forme que le central,
`risks.py` et la tuile connaissent déjà (voir host.py / review.py /
netview.py pour les formes Linux).

Les parseurs `parse_*` / `map_*` sont PURS (texte -> mesure) et testés sur
des sorties représentatives ; les `collect_*` les enchaînent avec
l'exécution réelle. Chaque source absente ou en échec est signalée dans
`partial` plutôt que de faire échouer la mesure.
"""
import json
import re
import time

from . import host, netview

MACOS_TIMEOUTS = {"logs": 20}


def _mac(s):
    return s.strip().lower() if s else None


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


def _netmask_to_prefix(mask):
    """0xffffff00 ou 255.255.255.0 -> 24 ; None si illisible."""
    if not mask:
        return None
    try:
        if mask.startswith("0x") or re.fullmatch(r"[0-9a-fA-F]{8}", mask):
            val = int(mask, 16)
        else:
            val = 0
            for part in mask.split("."):
                val = (val << 8) | int(part)
        return bin(val).count("1")
    except (ValueError, AttributeError):
        return None


# ---------------------------------------------------------------------
# host : system, cpu, memory, disks, services, ports, logs, accounts
# ---------------------------------------------------------------------

def parse_sw_vers(text):
    kv = {}
    for line in (text or "").splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            kv[k.strip()] = v.strip()
    return {"name": kv.get("ProductName"), "version": kv.get("ProductVersion"), "build": kv.get("BuildVersion")}


def parse_boottime(text):
    """`sysctl -n kern.boottime` -> uptime en secondes (None si illisible)."""
    m = re.search(r"sec\s*=\s*(\d+)", text or "")
    if not m:
        return None
    return max(0, int(time.time()) - int(m.group(1)))


def parse_vm_stat(text):
    """`vm_stat` -> (pages libres+inactives+spéculatives+purgeables, taille de page)."""
    page = 4096
    m = re.search(r"page size of (\d+) bytes", text or "")
    if m:
        page = int(m.group(1))
    counts = {}
    for line in (text or "").splitlines():
        m = re.match(r'"?Pages ([^:"]+)"?:\s+(\d+)\.', line.strip())
        if m:
            counts[m.group(1).strip().lower()] = int(m.group(2))
    avail_pages = counts.get("free", 0) + counts.get("inactive", 0) + counts.get("speculative", 0) + counts.get("purgeable", 0)
    return avail_pages, page, counts


def parse_swapusage(text):
    """`sysctl -n vm.swapusage` -> (total_bytes, used_bytes)."""
    def mb(label):
        m = re.search(label + r"\s*=\s*([\d.]+)M", text or "")
        return int(float(m.group(1)) * 1024 * 1024) if m else None
    return mb("total"), mb("used")


def parse_cpu_usage(text):
    """`top -l 1 -n 0` -> pourcentage CPU (100 - idle)."""
    m = re.search(r"CPU usage:\s*([\d.]+)%\s*user,\s*([\d.]+)%\s*sys(?:tem)?,\s*([\d.]+)%\s*idle", text or "")
    if not m:
        return None
    return round(100.0 - float(m.group(3)), 1)


def parse_loadavg(text):
    """`sysctl -n vm.loadavg` -> {load1, load5, load15}."""
    nums = re.findall(r"[\d.]+", text or "")
    if len(nums) >= 3:
        return {"load1": float(nums[0]), "load5": float(nums[1]), "load15": float(nums[2])}
    return {"load1": None, "load5": None, "load15": None}


def parse_mount(text):
    """`mount` -> {mountpoint: {fstype, readonly}} (macOS : « /dev/disk1s1 on / (apfs, local, journaled) »)."""
    out = {}
    for line in (text or "").splitlines():
        m = re.match(r"(.+?) on (.+?) \(([^)]*)\)", line.strip())
        if not m:
            continue
        opts = [o.strip() for o in m.group(3).split(",")]
        out[m.group(2)] = {"device": m.group(1), "fstype": opts[0] if opts else None, "readonly": "read-only" in opts}
    return out


_REMOTE_FS = ("nfs", "smbfs", "afpfs", "webdav", "ftp", "osxfuse", "macfuse")
_SKIP_MOUNTS = ("/dev", "/System/Volumes/VM", "/System/Volumes/Preboot", "/System/Volumes/Update",
                "/System/Volumes/xarts", "/System/Volumes/iSCPreboot", "/System/Volumes/Hardware")


def parse_df(text, mounts=None):
    """`df -k` -> disques (forme host.collect_disks). `mounts` : parse_mount()
    pour le type de système de fichiers et le montage en lecture seule."""
    mounts = mounts or {}
    out = []
    lines = [l for l in (text or "").splitlines() if l.strip()]
    for line in lines[1:]:
        # Filesystem 1024-blocks Used Available Capacity iused ifree %iused Mounted on
        m = re.match(r"(.+?)\s+(\d+)\s+(\d+)\s+(-?\d+)\s+\d+%.*?%?\s+(/.*)$", line)
        if not m:
            m = re.match(r"(.+?)\s+(\d+)\s+(\d+)\s+(-?\d+)\s+\d+%\s+(/.*)$", line)
        if not m:
            continue
        dev, total_k, used_k, avail_k, mnt = m.group(1), int(m.group(2)), int(m.group(3)), int(m.group(4)), m.group(5)
        if mnt in _SKIP_MOUNTS or any(mnt.startswith(s + "/") or mnt == s for s in _SKIP_MOUNTS):
            continue
        info = mounts.get(mnt, {})
        fstype = info.get("fstype")
        total = total_k * 1024
        used = used_k * 1024
        free = max(0, avail_k) * 1024
        out.append({
            "mountpoint": mnt, "device": info.get("device") or dev, "fstype": fstype,
            "remote": fstype in _REMOTE_FS if fstype else dev.startswith(("//", "afp:", "nfs:")),
            "removable": mnt.startswith("/Volumes/") and mnt != "/Volumes",
            "readonly": bool(info.get("readonly")), "visible": True,
            "total_bytes": total, "used_bytes": used, "free_bytes": free,
            "used_percent": round(100.0 * used / total, 1) if total else None,
        })
    # APFS : « / » (système scellé, lecture seule) et « /System/Volumes/Data »
    # partagent le même conteneur -> une seule entrée « / » portant l'usage réel
    # (le volume Data, inscriptible), pour ne pas compter deux fois ni afficher
    # le système scellé comme un disque à part.
    by_mnt = {d["mountpoint"]: d for d in out}
    data_vol = by_mnt.get("/System/Volumes/Data")
    if data_vol is not None:
        out = [d for d in out if d["mountpoint"] != "/"]
        data_vol["mountpoint"] = "/"
        data_vol["readonly"] = False
    return out


def parse_launchctl_list(text):
    """`launchctl list` -> (services en échec, nombre en cours). Colonnes
    PID STATUS LABEL ; PID numérique = en cours, STATUS non nul = dernier
    code de sortie non nul (échec probable)."""
    failed, running = [], 0
    for line in (text or "").splitlines()[1:]:
        parts = line.split(None, 2)
        if len(parts) < 3:
            continue
        pid, status, label = parts[0], parts[1], parts[2].strip()
        if pid.isdigit():
            running += 1
        try:
            code = int(status)
        except ValueError:
            code = 0
        # on ignore les agents utilisateur (com.apple.*) sans PID au repos : bruit
        if code != 0 and not label.startswith("0x"):
            # macOS récent : les démons système com.apple.* sont tués puis
            # relancés en permanence par le système (pression mémoire,
            # cryptexd, jetsam…) -- code -9 = SIGKILL système, pas un
            # échec du service. Premier Mac réel : 131 « risques » dont
            # ~tout le lot en -9. On les écarte du rapport d'échecs.
            if code == -9 and label.startswith("com.apple."):
                continue
            failed.append("%s (code %d)" % (label, code))
    return failed, running


def parse_lsof_listen(text):
    """`lsof -nP -iTCP -sTCP:LISTEN` -> ports en écoute. La colonne NAME
    vaut « TCP *:22 (LISTEN) » : l'adresse:port précède « (LISTEN) »."""
    out = []
    for line in (text or "").splitlines()[1:]:
        parts = line.split()
        if len(parts) < 9:
            continue
        m = re.search(r"(?:TCP|UDP)\s+(\S+):(\d+)(?:\s+\(LISTEN\))?\s*$", line)
        if not m:
            continue
        addr, port = m.group(1), int(m.group(2))
        proto = "tcp6" if (addr.startswith("[") or (":" in addr and addr != "*")) else "tcp"
        out.append({"proto": proto, "address": addr, "port": port, "process": parts[0], "pid": int(parts[1]) if parts[1].isdigit() else None,
                    "exposed": addr in ("*", "0.0.0.0", "::", "[::]")})
    # dédoublonnage (lsof répète une ligne par FD)
    seen, uniq = set(), []
    for pr in out:
        key = (pr["proto"], pr["address"], pr["port"], pr["pid"])
        if key not in seen:
            seen.add(key)
            uniq.append(pr)
    return uniq


def parse_dscl_group(text):
    """`dscl . -read /Groups/admin GroupMembership` -> [membres]."""
    m = re.search(r"GroupMembership:\s*(.*)", text or "")
    return m.group(1).split() if m else []


def parse_dscl_users(text, min_uid=500):
    """`dscl . -list /Users UniqueID` -> comptes humains (uid >= 500, sans _)."""
    out = []
    for line in (text or "").splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[1].lstrip("-").isdigit():
            name, uid = parts[0], int(parts[1])
            if uid >= min_uid and not name.startswith("_"):
                out.append(name)
    return out


def parse_log_show(text, limit=40):
    """`log show --style syslog` (messages d'erreur) -> lignes compactes."""
    lines = []
    for line in (text or "").splitlines():
        line = line.strip()
        if not line or line.startswith(("Timestamp", "Filtering", "Skipping", "-----")):
            continue
        lines.append(line[:400])
        if len(lines) >= limit:
            break
    return lines


def collect_all(files=None, cmd=host.run_cmd, usage=None, which=None, sleep=None,
                previous_cpu=None, hostname=None, include_tools=True, exists=None):
    """Une mesure `host` complète sous macOS ; (mesure, None) -- même
    signature que host.collect_all."""
    partial = []

    def out(argv, timeout=15):
        r = cmd(argv, timeout=timeout)
        return (r.stdout or "") if r.returncode == 0 else None

    sw = parse_sw_vers(out(["sw_vers"]) or "")
    model = (out(["sysctl", "-n", "hw.model"]) or "").strip() or None
    cpu_model = (out(["sysctl", "-n", "machdep.cpu.brand_string"]) or "").strip() or None
    if not cpu_model:
        cpu_model = (out(["sysctl", "-n", "hw.model"]) or "").strip() or None  # Apple Silicon : brand_string absent
    ncpu = (out(["sysctl", "-n", "hw.ncpu"]) or "").strip()
    arch = (out(["uname", "-m"]) or "").strip() or None
    uptime = parse_boottime(out(["sysctl", "-n", "kern.boottime"]) or "")
    hn = hostname or (out(["scutil", "--get", "ComputerName"]) or "").strip() or (out(["hostname"]) or "").strip() or None
    if sw.get("name") is None:
        partial.append("sw_vers")
    system = {
        "hostname": hn, "os": ("%s %s" % (sw.get("name"), sw.get("version"))).strip() if sw.get("name") else None,
        "os_id": "macos", "os_version": sw.get("version"), "kernel": ("build %s" % sw["build"]) if sw.get("build") else None,
        "display_version": sw.get("version"), "arch": arch, "cpus": int(ncpu) if ncpu.isdigit() else None,
        "cpu_model": cpu_model, "uptime_seconds": uptime, "reboot_required": False, "model": model,
    }

    cpu_pct = parse_cpu_usage(out(["top", "-l", "1", "-n", "0"], timeout=20) or "")
    load = parse_loadavg(out(["sysctl", "-n", "vm.loadavg"]) or "")
    if cpu_pct is None:
        partial.append("top")
    if load.get("load1") is None:
        partial.append("loadavg")
    cpu = {"percent": cpu_pct, "load1": load["load1"], "load5": load["load5"], "load15": load["load15"]}

    memsize = (out(["sysctl", "-n", "hw.memsize"]) or "").strip()
    total = int(memsize) if memsize.isdigit() else None
    avail_pages, page, _counts = parse_vm_stat(out(["vm_stat"]) or "")
    avail = avail_pages * page if _counts else None
    swap_total, swap_used = parse_swapusage(out(["sysctl", "-n", "vm.swapusage"]) or "")
    if total is None:
        partial.append("memsize")
    if not _counts:
        partial.append("vm_stat")
    memory = {"total_bytes": total, "available_bytes": avail,
              "used_percent": round(100.0 * (total - avail) / total, 1) if total and avail is not None else None,
              "swap_total_bytes": swap_total,
              "swap_used_percent": round(100.0 * swap_used / swap_total, 1) if swap_total and swap_used is not None else None}

    disks = parse_df(out(["df", "-k"]) or "", parse_mount(out(["mount"]) or ""))
    if not disks:
        partial.append("df")

    lc = out(["launchctl", "list"])
    if lc is None:
        services = {"available": False, "failed": [], "running_count": None}
        partial.append("launchctl")
    else:
        failed, running = parse_launchctl_list(lc)
        services = {"available": True, "failed": failed, "running_count": running}

    lsof = out(["lsof", "-nP", "-iTCP", "-sTCP:LISTEN"], timeout=20)
    if lsof is None:
        ports = {"available": False, "ports": []}
        partial.append("lsof")
    else:
        ports = {"available": True, "ports": parse_lsof_listen(lsof)}

    logtxt = out(["log", "show", "--last", "15m", "--style", "syslog", "--predicate", 'messageType == error'], timeout=MACOS_TIMEOUTS["logs"])
    log_lines = parse_log_show(logtxt) if logtxt is not None else []
    if logtxt is None:
        partial.append("logs")

    admins = parse_dscl_group(out(["dscl", ".", "-read", "/Groups/admin", "GroupMembership"]) or "")
    users = parse_dscl_users(out(["dscl", ".", "-list", "/Users", "UniqueID"]) or "")
    console = (out(["stat", "-f", "%Su", "/dev/console"]) or "").strip() or None
    accounts = {"sudoers": admins, "interactive": users, "uid0_not_root": [], "console_user": console}

    data = {
        "system": system, "cpu": cpu, "memory": memory, "disks": disks, "services": services, "ports": ports,
        "logs": {"source": "unified-log" if logtxt is not None else None, "lines": log_lines},
        "accounts": accounts, "partial": partial,
    }
    if include_tools:
        data["tools"] = collect_tools(which or __import__("shutil").which)
    return data, None


KNOWN_TOOLS = ("bash", "zsh", "python3", "docker", "ssh", "brew", "sysctl", "lsof", "system_profiler", "networksetup")


def collect_tools(which):
    return [t for t in KNOWN_TOOLS if which(t)]


# ---------------------------------------------------------------------
# activity
# ---------------------------------------------------------------------

def parse_ps_macos(text, limit=8):
    """`ps -Ao pid,user,pcpu,pmem,rss,etime,comm` (BSD) -> processus.
    `etime` est [[dd-]hh:]mm:ss, converti en secondes."""
    out = []
    for line in (text or "").splitlines():
        parts = line.split(None, 6)
        if len(parts) < 7 or not parts[0].isdigit():
            continue
        try:
            out.append({"pid": int(parts[0]), "user": parts[1], "cpu_percent": float(parts[2]), "mem_percent": float(parts[3]),
                        "rss_bytes": int(parts[4]) * 1024, "elapsed_seconds": _etime_seconds(parts[5]), "command": parts[6].strip()})
        except ValueError:
            continue
        if len(out) >= limit:
            break
    return out


def _etime_seconds(s):
    """[[dd-]hh:]mm:ss -> secondes."""
    days = 0
    if "-" in s:
        d, s = s.split("-", 1)
        days = int(d)
    parts = [int(p) for p in s.split(":")]
    while len(parts) < 3:
        parts.insert(0, 0)
    h, m, sec = parts[-3], parts[-2], parts[-1]
    return days * 86400 + h * 3600 + m * 60 + sec


def parse_who_macos(text):
    out = []
    for line in (text or "").splitlines():
        parts = line.split()
        if len(parts) >= 2:
            m = re.search(r"\(([^)]+)\)", line)
            out.append({"user": parts[0], "tty": parts[1], "since": " ".join(parts[2:5]) if len(parts) >= 5 else None,
                        "from": m.group(1) if m else None})
    return out


def parse_last_macos(text, limit=10):
    out = []
    for line in (text or "").splitlines():
        if not line.strip() or line.startswith("wtmp") or line.lower().startswith("reboot"):
            continue
        parts = line.split()
        if len(parts) < 3:
            continue
        frm = parts[2] if (parts[2].count(".") >= 1 or ":" in parts[2]) else None
        out.append({"user": parts[0], "tty": parts[1], "from": frm, "line": line.strip()})
        if len(out) >= limit:
            break
    return out


def collect_activity(cmd=host.run_cmd, files=None):
    partial = []

    def out(argv, timeout=15):
        r = cmd(argv, timeout=timeout)
        return (r.stdout or "") if r.returncode == 0 else None

    ps_cpu = out(["ps", "-Ao", "pid,user,pcpu,pmem,rss,etime,comm", "-r"])   # -r : trié par CPU
    ps_mem = out(["ps", "-Ao", "pid,user,pcpu,pmem,rss,etime,comm", "-m"])   # -m : trié par mémoire
    if ps_cpu is None:
        partial.append("ps")
    top_cpu = parse_ps_macos(ps_cpu, 8) if ps_cpu else []
    top_mem = parse_ps_macos(ps_mem, 8) if ps_mem else []
    total = max(0, len((ps_cpu or "").splitlines()) - 1) if ps_cpu else None
    sessions = parse_who_macos(out(["who"]) or "")
    last = out(["last", "-10"])
    logins = parse_last_macos(last) if last else []
    if last is None:
        partial.append("last")
    updates = None
    su = out(["softwareupdate", "-l", "--no-scan"], timeout=20)
    if su is not None:
        found = re.findall(r"^\s*\*\s", su, re.M)
        updates = len(found)
    return {"process_count": total, "top_cpu": top_cpu, "top_memory": top_mem, "sessions": sessions, "last_logins": logins,
            "running_services": None, "running_services_count": None, "updates_available": updates, "partial": partial}


# ---------------------------------------------------------------------
# hardware (inventory)
# ---------------------------------------------------------------------

def map_hardware(sp, networksetup_text=None):
    """SPHardwareDataType (json) + `networksetup -listallhardwareports` ->
    mesure `hardware` (forme review.collect_hardware)."""
    item = {}
    try:
        item = (sp.get("SPHardwareDataType") or [{}])[0]
    except (AttributeError, IndexError):
        item = {}
    mem = item.get("physical_memory")
    mem_bytes = None
    if mem:
        m = re.match(r"([\d.]+)\s*(\w+)", mem)
        if m:
            unit = {"GB": 1024 ** 3, "MB": 1024 ** 2, "TB": 1024 ** 4}.get(m.group(2).upper(), 1)
            mem_bytes = int(float(m.group(1)) * unit)
    cores = item.get("number_processors")
    if isinstance(cores, str):
        m = re.search(r"(\d+)", cores)
        cores = int(m.group(1)) if m else None
    cpu_model = item.get("chip_type") or item.get("cpu_type")
    threads = 1 if (cpu_model or "").startswith("Apple") else None
    cpu = {"model": cpu_model, "cpus": cores, "sockets": 1, "cores_per_socket": cores, "threads_per_core": threads,
           "arch": None, "mhz_max": item.get("current_processor_speed"), "hypervisor": None, "virtualization": None} if cpu_model or cores else None
    nics = parse_networksetup(networksetup_text or "")
    return {
        "vendor": "Apple", "product": item.get("machine_model") or item.get("machine_name"),
        "product_version": item.get("model_number"), "serial": (item.get("serial_number") or "").strip() or None,
        "uuid": item.get("platform_UUID"), "bios": item.get("boot_rom_version"), "board": None,
        "cpu": cpu, "memory_total_bytes": mem_bytes, "disks": [], "nics": nics, "gpus": [],
        "virtualization": None, "software": None, "software_count": None,
        "partial": [k for k, v in (("system_profiler", item), ("nics", nics)) if not v],
    }


def parse_networksetup(text):
    """`networksetup -listallhardwareports` -> cartes réseau (nom, MAC)."""
    nics = []
    cur = {}
    for line in (text or "").splitlines():
        line = line.strip()
        if line.startswith("Hardware Port:"):
            cur = {"description": line.split(":", 1)[1].strip()}
        elif line.startswith("Device:"):
            cur["name"] = line.split(":", 1)[1].strip()
        elif line.startswith("Ethernet Address:"):
            mac = line.split(":", 1)[1].strip()
            cur["mac"] = _mac(mac) if mac and mac != "N/A" else None
            nics.append({"name": cur.get("name"), "mac": cur.get("mac"), "state": None, "speed_mbps": None,
                         "description": cur.get("description")})
            cur = {}
    return nics


def collect_hardware(cmd=host.run_cmd, files=None):
    r = cmd(["system_profiler", "SPHardwareDataType", "-json"], timeout=60)
    sp = {}
    if r.returncode == 0:
        try:
            sp = json.loads(r.stdout)
        except ValueError:
            sp = {}
    ns = cmd(["networksetup", "-listallhardwareports"], timeout=20)
    data = map_hardware(sp, ns.stdout if ns.returncode == 0 else "")
    if not sp:
        data["partial"] = list(set(data["partial"] + ["system_profiler"]))
        data["error"] = (r.stderr or "").strip()[:200] or "system_profiler indisponible"
    return data


# ---------------------------------------------------------------------
# netview
# ---------------------------------------------------------------------

def parse_ifconfig(text):
    """`ifconfig -a` (macOS) -> interfaces (forme netview.parse_ip_addr)."""
    interfaces = []
    cur = None
    for line in (text or "").splitlines():
        if not line.startswith((" ", "\t")):
            m = re.match(r"([\w.]+):\s*flags=\S*<([^>]*)>.*?mtu (\d+)", line)
            if not m:
                cur = None
                continue
            cur = {"name": m.group(1), "mac": None, "mtu": int(m.group(3)), "state": None,
                   "flags": m.group(2).split(","), "addresses": []}
            interfaces.append(cur)
            continue
        if cur is None:
            continue
        line = line.strip()
        m = re.match(r"ether ([0-9a-fA-F:]{17})", line)
        if m:
            cur["mac"] = _mac(m.group(1))
            continue
        m = re.match(r"status:\s*(\w+)", line)
        if m:
            cur["state"] = "up" if m.group(1).lower() == "active" else "down"
            continue
        m = re.match(r"inet (\d+\.\d+\.\d+\.\d+) netmask (0x[0-9a-fA-F]+)(?:\s+broadcast\s+(\S+))?", line)
        if m:
            ip = m.group(1)
            scope = "host" if ip.startswith("127.") else ("link" if ip.startswith("169.254.") else "global")
            cur["addresses"].append({"ip": ip, "prefix": _netmask_to_prefix(m.group(2)), "family": "inet", "scope": scope, "origin": None})
            continue
        m = re.match(r"inet6 ([0-9a-fA-F:]+)(?:%\w+)?(?:\s+prefixlen\s+(\d+))?", line)
        if m:
            ip = m.group(1)
            scope = "link" if ip.lower().startswith("fe80") else ("host" if ip == "::1" else "global")
            cur["addresses"].append({"ip": ip, "prefix": int(m.group(2)) if m.group(2) else None, "family": "inet6", "scope": scope, "origin": None})
    for itf in interfaces:
        if itf["state"] is None:
            itf["state"] = "up" if "UP" in itf.get("flags", []) else "down"
        itf.pop("flags", None)
    # boucle locale et interfaces sans adresse écartées (comme netview Linux)
    return [i for i in interfaces if i["addresses"] and not all(a["scope"] == "host" for a in i["addresses"])]


def parse_netstat_routes(text):
    """`netstat -rnf inet` -> routes IPv4 (forme netview.parse_ip_route)."""
    routes = []
    for line in (text or "").splitlines():
        parts = line.split()
        if len(parts) < 4 or parts[0] in ("Routing", "Internet:", "Destination", "Internet6:"):
            continue
        dst, gw, flags = parts[0], parts[1], parts[2]
        dev = parts[-1]
        if dst == "default":
            kind, out_dst = "default", "default"
        elif re.match(r"^[\d.]+(?:/\d+)?$", dst):
            if "/" not in dst:
                # host route (souvent voisin) : ignorée sauf réseau
                if flags and "H" in flags:
                    continue
                out_dst = dst
            else:
                out_dst = dst
            kind = "via" if re.match(r"^\d+\.\d+\.\d+\.\d+$", gw) else "direct"
        else:
            continue
        routes.append({"dst": out_dst, "gateway": gw if kind != "direct" else None, "dev": dev,
                       "protocol": None, "scope": "link" if kind == "direct" else None, "metric": None, "kind": kind})
    routes.sort(key=lambda r: r["kind"] != "default")
    return routes


def parse_arp(text):
    """`arp -an` -> voisins. « ? (192.168.1.1) at ac:de:.. on en0 ... »"""
    out = []
    for line in (text or "").splitlines():
        m = re.search(r"\((\d+\.\d+\.\d+\.\d+)\) at ([0-9a-fA-F:]+|\(incomplete\))(?: on (\w+))?", line)
        if not m:
            continue
        ip, mac, dev = m.group(1), m.group(2), m.group(3)
        if ip.startswith(("224.", "239.", "255.")) or ip.endswith(".255"):
            continue
        incomplete = "incomplete" in mac
        out.append({"ip": ip, "mac": None if incomplete else _mac(mac), "dev": dev,
                    "state": "failed" if incomplete else "reachable"})
    return out


def parse_netstat_conns(text):
    """`netstat -an -p tcp` -> connexions établies. « tcp4 0 0 192.168.1.20.52345 1.2.3.4.443 ESTABLISHED »"""
    out = []
    for line in (text or "").splitlines():
        parts = line.split()
        if len(parts) < 6 or not parts[0].startswith("tcp") or parts[-1] != "ESTABLISHED":
            continue
        local, remote = parts[3], parts[4]
        lm = re.match(r"(.+)\.(\d+)$", local)
        rm = re.match(r"(.+)\.(\d+)$", remote)
        if not lm or not rm:
            continue
        out.append({"proto": "tcp", "local_ip": lm.group(1), "local_port": int(lm.group(2)),
                    "remote_ip": rm.group(1), "remote_port": int(rm.group(2)), "process": None, "pid": None})
    return out


def collect_netview(cmd=host.run_cmd, files=None):
    partial = []

    def out(argv, timeout=15):
        r = cmd(argv, timeout=timeout)
        return (r.stdout or "") if r.returncode == 0 else None

    ifc = out(["ifconfig", "-a"])
    rt = out(["netstat", "-rnf", "inet"])
    ar = out(["arp", "-an"])
    cn = out(["netstat", "-an", "-p", "tcp"])
    if ifc is None:
        partial.append("ifconfig")
    if rt is None:
        partial.append("netstat-r")
    if ar is None:
        partial.append("arp")
    interfaces = parse_ifconfig(ifc or "")
    routes = parse_netstat_routes(rt or "")
    neighbors = parse_arp(ar or "")
    conns = parse_netstat_conns(cn or "")
    # MTU/état des interfaces : déjà dans ifconfig
    dns_servers = []
    scutil = out(["scutil", "--dns"])
    if scutil:
        dns_servers = list(dict.fromkeys(re.findall(r"nameserver\[\d+\]\s*:\s*(\S+)", scutil)))
    return {"interfaces": interfaces, "routes": routes, "neighbors": neighbors, "connections": conns[:500],
            "dns": {"servers": dns_servers, "search": []},
            "summary": netview.summarize(interfaces, routes, neighbors, conns), "partial": partial}
