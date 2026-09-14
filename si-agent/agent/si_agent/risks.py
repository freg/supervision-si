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
    # #503 stockage : ZFS se dégrade bien avant 100 % (copy-on-write) ;
    # un thin pool LVM plein bloque toutes ses écritures.
    "zfs_capacity_warning_percent": 80,
    "zfs_capacity_critical_percent": 90,
    "zfs_scrub_max_days": 35,
    "thin_pool_warning_percent": 85,
    "thin_pool_critical_percent": 95,
    "dataset_quota_warning_percent": 90,
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
        if disk.get("readonly"):
            continue  # #442 : un montage en lecture seule (ISO, image, support protégé) ne peut pas se remplir
        if disk.get("removable"):
            if pct >= t["disk_critical_percent"]:
                out.append({"id": "removable-full", "severity": "info", "subject": disk.get("mountpoint"),
                            "message": "support amovible %s plein à %.0f %% (sans effet sur l'hôte)" % (disk.get("mountpoint"), pct)})
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

    os_id = (d.get("system") or {}).get("os_id")
    is_windows = os_id == "windows"
    _svc_msg = {"windows": "service Windows automatique arrêté : %s", "macos": "service launchd en échec : %s"}.get(os_id, "unité systemd en échec : %s")
    for unit in (d.get("services") or {}).get("failed") or []:
        out.append({"id": "service-failed", "severity": "warning", "subject": unit,
                    "message": _svc_msg % unit})

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

    out.extend(evaluate_storage(d.get("storage"), t))
    return out


def evaluate_storage(storage, t=None):
    """#503 : risques des volumes (ZFS, LVM thin, RAID logiciel). Pure."""
    t = dict(DEFAULT_THRESHOLDS, **(t or {}))
    out = []
    if not isinstance(storage, dict):
        return out
    zfs = storage.get("zfs") or {}
    for p in zfs.get("pools") or []:
        name = p.get("pool")
        state = (p.get("state") or p.get("health") or "").upper()
        if state in ("FAULTED", "UNAVAIL", "REMOVED"):
            out.append({"id": "zpool-faulted", "severity": "critical", "subject": "zpool:%s" % name,
                        "message": "pool ZFS %s en état %s : données inaccessibles" % (name, state)})
        elif state == "DEGRADED":
            out.append({"id": "zpool-degraded", "severity": "critical", "subject": "zpool:%s" % name,
                        "message": "pool ZFS %s DÉGRADÉ : un disque manque ou est en panne, plus de redondance" % name})
        elif state and state != "ONLINE":
            out.append({"id": "zpool-state", "severity": "warning", "subject": "zpool:%s" % name,
                        "message": "pool ZFS %s en état %s" % (name, state)})
        bad = [dv for dv in p.get("devices") or [] if (dv.get("read") or dv.get("write") or dv.get("cksum"))]
        if bad or (p.get("errors") and not str(p.get("errors")).lower().startswith("no known")):
            out.append({"id": "zpool-errors", "severity": "warning", "subject": "zpool:%s" % name,
                        "message": "pool ZFS %s : erreurs d'E/S ou de somme de contrôle (%s)" % (
                            name, ", ".join("%s r%d/w%d/c%d" % (dv["name"], dv["read"], dv["write"], dv["cksum"]) for dv in bad) or p.get("errors"))})
        cap = p.get("capacity_percent")
        if cap is not None:
            if cap >= t["zfs_capacity_critical_percent"]:
                out.append({"id": "zpool-full", "severity": "critical", "subject": "zpool:%s" % name,
                            "message": "pool ZFS %s rempli à %.0f %% : performances effondrées au-delà de 90 %%" % (name, cap)})
            elif cap >= t["zfs_capacity_warning_percent"]:
                out.append({"id": "zpool-high", "severity": "warning", "subject": "zpool:%s" % name,
                            "message": "pool ZFS %s rempli à %.0f %%" % (name, cap)})
        age = p.get("scrub_age_s")
        if age is None and p.get("scan") is not None:
            out.append({"id": "zpool-scrub-never", "severity": "info", "subject": "zpool:%s" % name,
                        "message": "pool ZFS %s : aucun scrub terminé connu" % name})
        elif age is not None and age > t["zfs_scrub_max_days"] * 86400:
            out.append({"id": "zpool-scrub-old", "severity": "info", "subject": "zpool:%s" % name,
                        "message": "pool ZFS %s : dernier scrub il y a %d jours" % (name, age // 86400)})
    for d in zfs.get("datasets") or []:
        pct = d.get("used_percent")
        if d.get("quota") and pct is not None and pct >= t["dataset_quota_warning_percent"]:
            out.append({"id": "dataset-quota", "severity": "warning", "subject": "zfs:%s" % d.get("name"),
                        "message": "dataset %s à %.0f %% de son quota" % (d.get("name"), pct)})
    lvm = storage.get("lvm") or {}
    for lv in lvm.get("volumes") or []:
        if lv.get("kind") != "thin-pool":
            continue
        for key, label in (("data_percent", "données"), ("metadata_percent", "métadonnées")):
            pct = lv.get(key)
            if pct is None:
                continue
            subj = "lvm:%s/%s" % (lv.get("vg"), lv.get("lv"))
            if pct >= t["thin_pool_critical_percent"]:
                out.append({"id": "thin-pool-full", "severity": "critical", "subject": subj,
                            "message": "thin pool %s/%s : %s à %.0f %% (les volumes fins vont se bloquer)" % (lv.get("vg"), lv.get("lv"), label, pct)})
            elif pct >= t["thin_pool_warning_percent"]:
                out.append({"id": "thin-pool-high", "severity": "warning", "subject": subj,
                            "message": "thin pool %s/%s : %s à %.0f %%" % (lv.get("vg"), lv.get("lv"), label, pct)})
    for a in storage.get("md") or []:
        if a.get("degraded"):
            out.append({"id": "md-degraded", "severity": "critical", "subject": "md:%s" % a.get("array"),
                        "message": "RAID logiciel %s (%s) dégradé : %s disque(s) actif(s) sur %s" % (a.get("array"), a.get("level"), a.get("active"), a.get("total"))})
        elif a.get("resync"):
            out.append({"id": "md-resync", "severity": "info", "subject": "md:%s" % a.get("array"),
                        "message": "RAID logiciel %s : %s" % (a.get("array"), a.get("resync"))})
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
