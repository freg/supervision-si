"""Risques internes de l'hôte (livraison #420) -- évaluation PURE d'une
mesure `host` (voir host.collect_all) en une liste de constats :

    {"id": "disk-full", "severity": "critical"|"warning"|"info", "message": "...", "subject": "/"}

Seuils volontairement simples et lisibles, surchargeables par la
configuration de l'agent (`risk_thresholds`) puis, plus tard, par le
central. Un constat est un FAIT observé sur l'hôte, jamais une
interprétation réseau (ça, c'est le rôle des plugins et du central).
"""

DEFAULT_THRESHOLDS = {
    "disk_warning_percent": 85,
    "disk_critical_percent": 95,
    "memory_warning_percent": 90,
    "swap_warning_percent": 50,
    "load_per_cpu_warning": 2.0,
    "recent_boot_seconds": 600,
    "log_errors_warning": 20,
    "defender_signatures_max_days": 7,  # #440 Windows
}

# Ports dont l'exposition sur toutes les interfaces est un risque en soi
# (protocoles en clair, bases sans authentification par défaut, prise en
# main à distance) -- liste courte, assumée ; le reste est de l'inventaire.
SENSITIVE_PORTS = {
    21: "FTP (en clair)", 23: "Telnet (en clair)", 69: "TFTP", 111: "portmapper/NFS", 135: "MS-RPC",
    139: "NetBIOS", 445: "SMB", 512: "rexec", 513: "rlogin", 514: "rsh", 1433: "SQL Server", 1521: "Oracle",
    2049: "NFS", 3306: "MySQL/MariaDB", 3389: "RDP", 5432: "PostgreSQL", 5900: "VNC", 5901: "VNC",
    6379: "Redis", 9200: "Elasticsearch", 11211: "memcached", 27017: "MongoDB",
}


def evaluate(host_data, thresholds=None):
    t = dict(DEFAULT_THRESHOLDS)
    t.update(thresholds or {})
    out = []
    d = host_data or {}

    for disk in d.get("disks") or []:
        pct = disk.get("used_percent")
        if pct is None:
            continue
        if pct >= t["disk_critical_percent"]:
            out.append({"id": "disk-full", "severity": "critical", "subject": disk.get("mountpoint"),
                        "message": "%s plein à %.0f %%" % (disk.get("mountpoint"), pct)})
        elif pct >= t["disk_warning_percent"]:
            out.append({"id": "disk-high", "severity": "warning", "subject": disk.get("mountpoint"),
                        "message": "%s rempli à %.0f %%" % (disk.get("mountpoint"), pct)})

    mem = d.get("memory") or {}
    if mem.get("used_percent") is not None and mem["used_percent"] >= t["memory_warning_percent"]:
        out.append({"id": "memory-high", "severity": "warning", "subject": "memory",
                    "message": "mémoire utilisée à %.0f %%" % mem["used_percent"]})
    if mem.get("swap_used_percent") is not None and mem["swap_used_percent"] >= t["swap_warning_percent"]:
        out.append({"id": "swap-high", "severity": "warning", "subject": "swap",
                    "message": "swap utilisé à %.0f %%" % mem["swap_used_percent"]})

    cpu = d.get("cpu") or {}
    cpus = (d.get("system") or {}).get("cpus") or 1
    if cpu.get("load5") is not None and cpu["load5"] >= t["load_per_cpu_warning"] * cpus:
        out.append({"id": "load-high", "severity": "warning", "subject": "cpu",
                    "message": "charge moyenne 5 min %.2f pour %d CPU" % (cpu["load5"], cpus)})

    system = d.get("system") or {}
    if system.get("reboot_required"):
        out.append({"id": "reboot-required", "severity": "info", "subject": "system",
                    "message": "redémarrage requis (mises à jour appliquées)"})
    up = system.get("uptime_seconds")
    if up is not None and up < t["recent_boot_seconds"]:
        out.append({"id": "recent-boot", "severity": "info", "subject": "system",
                    "message": "hôte démarré il y a %d s" % int(up)})

    is_windows = (d.get("system") or {}).get("os_id") == "windows"
    for unit in (d.get("services") or {}).get("failed") or []:
        out.append({"id": "service-failed", "severity": "warning", "subject": unit,
                    "message": ("service Windows automatique arrêté : %s" if is_windows else "unité systemd en échec : %s") % unit})

    for p in (d.get("ports") or {}).get("ports") or []:
        if p.get("exposed") and p.get("port") in SENSITIVE_PORTS:
            out.append({"id": "port-exposed", "severity": "warning", "subject": "%s/%s" % (p.get("proto"), p.get("port")),
                        "message": "%s exposé sur toutes les interfaces (port %s%s)" % (
                            SENSITIVE_PORTS[p["port"]], p["port"], " -- " + p["process"] if p.get("process") else "")})

    accounts = d.get("accounts") or {}
    for name in accounts.get("uid0_not_root") or []:
        out.append({"id": "uid0-account", "severity": "critical", "subject": name,
                    "message": "compte %s avec l'UID 0 (équivalent root)" % name})

    logs = d.get("logs") or {}
    n = len(logs.get("lines") or [])
    if n >= t["log_errors_warning"]:
        out.append({"id": "log-errors", "severity": "warning", "subject": logs.get("source"),
                    "message": "%d erreur(s) dans le journal sur 24 h" % n})

    # #440 : Windows -- Defender, pare-feu, mises à jour en attente
    win = d.get("windows") or {}
    defender = win.get("defender")
    if isinstance(defender, dict):
        if defender.get("enabled") is False:
            out.append({"id": "defender-off", "severity": "critical", "subject": "defender", "message": "antivirus Microsoft Defender désactivé"})
        elif defender.get("realtime") is False:
            out.append({"id": "defender-realtime-off", "severity": "warning", "subject": "defender", "message": "protection en temps réel de Defender désactivée"})
        age = defender.get("signatures_age_days")
        if age is not None and age > t.get("defender_signatures_max_days", 7):
            out.append({"id": "defender-signatures-old", "severity": "warning", "subject": "defender", "message": "signatures Defender vieilles de %d jours" % age})
    for prof in win.get("firewall") or []:
        if isinstance(prof, dict) and prof.get("enabled") is False:
            out.append({"id": "firewall-profile-off", "severity": "warning", "subject": "firewall:%s" % prof.get("profile"),
                        "message": "pare-feu Windows désactivé pour le profil %s" % prof.get("profile")})
    upd = (d.get("activity") or {}).get("updates_available")
    if is_windows and upd:
        out.append({"id": "updates-pending", "severity": "info", "subject": "windows-update", "message": "%d mise(s) à jour Windows en attente" % upd})

    return out


def summarize(risks):
    """Compte par sévérité + état global (critical > warning > info > ok)."""
    counts = {"critical": 0, "warning": 0, "info": 0}
    for r in risks or []:
        counts[r.get("severity", "info")] = counts.get(r.get("severity", "info"), 0) + 1
    state = "ok"
    if counts["critical"]:
        state = "critical"
    elif counts["warning"]:
        state = "warning"
    elif counts["info"]:
        state = "info"
    return {"state": state, "counts": counts, "total": len(risks or [])}
