# -*- coding: utf-8 -*-
"""Analyse des sorties « show » Cisco (livraison #508) -- logique PURE,
testée (tests/test_parsers.py) sur des sorties représentatives :
Catalyst 3750 / 2970 (IOS 12.2) et Nexus 3064PQ (NX-OS). Écrit d'après
les formats connus, jamais vérifié ici sur un équipement réel : chaque
fonction tolère l'absence d'une ligne (valeur None) et ne lève jamais.
"""
import re

SEVERITY = {0: "emergency", 1: "alert", 2: "critical", 3: "error", 4: "warning", 5: "notice", 6: "info", 7: "debug"}


def _search(rx, text, group=1, flags=re.I | re.M):
    m = re.search(rx, text or "", flags)
    return m.group(group).strip() if m else None


def parse_version(text):
    """show version (IOS ou NX-OS) -> {platform, model, version, uptime, serial, hostname, image}."""
    t = text or ""
    nxos = "NX-OS" in t or "Nexus" in t
    out = {"platform": "nxos" if nxos else "ios"}
    if nxos:
        out["version"] = _search(r"^\s*(?:NXOS|system):?\s+version\s+(\S+)", t) or _search(r"NX-OS.*?Version\s+(\S+)", t, flags=re.I | re.S)
        out["model"] = _search(r"^\s*cisco\s+(Nexus\s*\S+(?:\s+\S+)?)\s+Chassis", t) or _search(r"(N\dK-C\S+)", t)
        out["hostname"] = _search(r"^\s*Device name:\s*(\S+)", t)
        out["serial"] = _search(r"Processor Board ID\s+(\S+)", t)
        out["uptime"] = _search(r"uptime is\s+(.+)$", t)
        out["image"] = _search(r"^\s*(?:NXOS|system) image file is:\s*(\S+)", t)
    else:
        out["version"] = _search(r"Version\s+([\w.()]+)", t)
        out["model"] = _search(r"^\s*cisco\s+(WS-C\S+|C\S+|ISR\S+|\S+)\s+\(", t) or _search(r"Model number\s*:\s*(\S+)", t)
        out["hostname"] = _search(r"^(\S+)\s+uptime is", t)
        out["serial"] = _search(r"System serial number\s*:\s*(\S+)", t) or _search(r"Processor board ID\s+(\S+)", t)
        out["uptime"] = _search(r"uptime is\s+(.+)$", t)
        out["image"] = _search(r"System image file is\s+\"?([^\"\s]+)", t)
    return out


def parse_cpu(text, platform="ios"):
    """IOS : show processes cpu | include CPU -> {five_sec, one_min, five_min}.
    NX-OS : show system resources -> idem depuis « CPU states » (1 - idle)."""
    t = text or ""
    if platform == "nxos":
        idle = _search(r"CPU states\s*:.*?([\d.]+)%\s*idle", t)
        if idle is None:
            return {}
        used = round(100.0 - float(idle), 1)
        load = _search(r"load average:\s*([\d.]+)", t)
        return {"five_sec": used, "one_min": used, "five_min": used, "load1": float(load) if load else None}
    m = re.search(r"five seconds:\s*(\d+)%(?:/\d+%)?;\s*one minute:\s*(\d+)%;\s*five minutes:\s*(\d+)%", t)
    if not m:
        return {}
    return {"five_sec": int(m.group(1)), "one_min": int(m.group(2)), "five_min": int(m.group(3))}


def parse_memory(text, platform="ios"):
    """IOS : show memory statistics (ligne Processor) ; NX-OS : show system resources (Memory usage)."""
    t = text or ""
    if platform == "nxos":
        m = re.search(r"Memory usage:\s*(\d+)K total,\s*(\d+)K used,\s*(\d+)K free", t)
        if not m:
            return {}
        total, used = int(m.group(1)) * 1024, int(m.group(2)) * 1024
        return {"total": total, "used": used, "free": total - used, "used_percent": round(100.0 * used / total, 1)}
    m = re.search(r"^\s*Processor\s+\S+\s+(\d+)\s+(\d+)\s+(\d+)", t, re.M)
    if not m:
        return {}
    total, used, free = int(m.group(1)), int(m.group(2)), int(m.group(3))
    return {"total": total, "used": used, "free": free, "used_percent": round(100.0 * used / total, 1) if total else None}


_ENV_BAD = re.compile(r"\b(NOT OK|FAULTY|FAIL(?:URE|ED)?|CRITICAL|SHUTDOWN|ALARM|RED|BAD)\b", re.I)
_ENV_OK = re.compile(r"\b(OK|GREEN|NORMAL|Good)\b")


def parse_environment(text):
    """show env all (IOS) / show environment (NX-OS) -> [{item, status, ok}]
    par mots-clés : une ligne mentionnant FAN / TEMP / POWER / PSU / SUPPLY
    et un état. Tolérant aux formats des différentes gammes."""
    out = []
    for line in (text or "").splitlines():
        l = line.strip()
        if not l or not re.search(r"fan|temp|power|psu|supply|sensor|module", l, re.I):
            continue
        bad = _ENV_BAD.search(l)
        ok = _ENV_OK.search(l)
        if not bad and not ok:
            if re.search(r"Not Present|Absent", l, re.I):
                out.append({"item": l, "status": "absent", "ok": True})
            continue
        out.append({"item": l, "status": bad.group(1) if bad else ok.group(1), "ok": not bad})
    return out


def parse_interfaces_status(text):
    """show interfaces status (IOS) / show interface status (NX-OS) ->
    [{port, name, status, vlan, duplex, speed, type}]."""
    rows = []
    lines = (text or "").splitlines()
    header = next((i for i, l in enumerate(lines) if re.match(r"^\s*Port\s+Name\s+Status", l)), None)
    if header is None:
        return rows
    hl = lines[header]
    c_name, c_status, c_vlan, c_duplex, c_speed, c_type = (hl.find("Name"), hl.find("Status"), hl.find("Vlan"), hl.find("Duplex"), hl.find("Speed"), hl.find("Type"))
    for l in lines[header + 1:]:
        if not l.strip() or set(l.strip()) <= {"-"}:
            continue
        port = l[:c_name].strip()
        if not re.match(r"^[A-Za-z]{2}", port):
            continue
        rows.append({"port": port, "name": l[c_name:c_status].strip(), "status": l[c_status:c_vlan].strip(),
                     "vlan": l[c_vlan:c_duplex].strip(), "duplex": l[c_duplex:c_speed].strip(),
                     "speed": l[c_speed:c_type].strip() if c_type > 0 else l[c_speed:].strip(),
                     "type": l[c_type:].strip() if c_type > 0 else ""})
    return rows


_LOG_RE = re.compile(r"%([A-Z0-9_]+)-(\d)-([A-Z0-9_]+):\s*(.*)$")


def parse_logging(text, limit=200):
    """show logging -> dernières lignes avec sévérité : [{raw, facility, severity, level, mnemonic, message}]."""
    out = []
    for line in (text or "").splitlines():
        m = _LOG_RE.search(line)
        if not m:
            continue
        sev = int(m.group(2))
        out.append({"raw": line.strip(), "facility": m.group(1), "severity": sev, "level": SEVERITY.get(sev, "?"),
                    "mnemonic": m.group(3), "message": m.group(4).strip()})
    return out[-limit:]


def alerts(summary, interfaces=None, logs=None, thresholds=None):
    """Alertes dérivées (pur) : CPU/mémoire au-dessus des seuils, capteur
    en défaut, port err-disabled, journaux de sévérité <= 3 récents."""
    th = {"cpu_warning": 70, "cpu_critical": 90, "mem_warning": 80, "mem_critical": 95, "log_max_severity": 3, "log_recent": 20}
    th.update(thresholds or {})
    out = []
    cpu = (summary or {}).get("cpu") or {}
    if cpu.get("five_min") is not None:
        v = cpu["five_min"]
        if v >= th["cpu_critical"]:
            out.append({"severity": "critical", "kind": "cpu", "message": "CPU 5 min à %s %%" % v})
        elif v >= th["cpu_warning"]:
            out.append({"severity": "warning", "kind": "cpu", "message": "CPU 5 min à %s %%" % v})
    mem = (summary or {}).get("memory") or {}
    if mem.get("used_percent") is not None:
        v = mem["used_percent"]
        if v >= th["mem_critical"]:
            out.append({"severity": "critical", "kind": "memory", "message": "mémoire utilisée à %s %%" % v})
        elif v >= th["mem_warning"]:
            out.append({"severity": "warning", "kind": "memory", "message": "mémoire utilisée à %s %%" % v})
    for e in (summary or {}).get("environment") or []:
        if not e.get("ok"):
            out.append({"severity": "critical", "kind": "environment", "message": e["item"]})
    for i in interfaces or []:
        if "err-disabled" in (i.get("status") or ""):
            out.append({"severity": "warning", "kind": "interface", "message": "%s err-disabled%s" % (i["port"], (" (" + i["name"] + ")") if i.get("name") else "")})
    for l in (logs or [])[-th["log_recent"]:]:
        if l["severity"] <= th["log_max_severity"]:
            out.append({"severity": "critical" if l["severity"] <= 2 else "warning", "kind": "log", "message": l["raw"]})
    return out


def strip_volatile(config):
    """Lignes volatiles retirées avant comparaison de deux configurations
    (horodatage « Last configuration change », « ntp clock-period »…)."""
    keep = []
    for line in (config or "").splitlines():
        if re.match(r"^\s*(!\s*(Last configuration change|NVRAM config last updated|Time:|Running configuration last done)|ntp clock-period|Building configuration|Current configuration)", line, re.I):
            continue
        keep.append(line.rstrip())
    return "\n".join(keep).strip() + "\n"
