# -*- coding: utf-8 -*-
"""Onglet « Espaces disques / données » (livraison #986) -- logique pure, testée.

Assemble, pour chaque machine suivie (agents hôtes et NAS relevés en SNMP / SSH), la configuration matérielle (disques
physiques, RAM), les volumes (taille, occupé, libre, %), leur TENDANCE (pente sur les relevés quotidiens) et la date de
saturation estimée, les RAID / LVM / ZFS, les possibilités d'extension (baies libres, disques non utilisés, espace libre
d'un groupe LVM ou d'un pool ZFS, passage RAID 5 -> 6) et les niveaux d'alerte. Classement par rôle, LAN et hébergeur :
deviné (nom, système, site) puis corrigé dans le hub (réglage « espaces_classement »). Rien n'est écrit sur les machines.
"""
import re

SEUILS = {"attention": 85, "critique": 95, "jours_attention": 30, "jours_critique": 7}
FS_IGNORES = {"tmpfs", "devtmpfs", "overlay", "squashfs", "proc", "sysfs", "cgroup", "cgroup2", "autofs", "efivarfs", "ramfs",
              "devfs", "nullfs", "fuse.lxcfs", "fuse.portal", "fuse.gvfsd-fuse", "tracefs", "debugfs", "binfmt_misc", "mqueue"}
MONTAGES_IGNORES = re.compile(r"^(/boot/efi|/snap/|/var/lib/docker/|/run/|/dev/|/sys/|/proc/|/System/Volumes/(VM|Preboot|Update|xarts|iSCPreboot|Hardware))")
GO = 1024 ** 3


def _num(v):
    return v if isinstance(v, (int, float)) else None


def deviner(agent, hardware=None, plugins=()):
    """Classement par défaut : {role, lan, hebergeur}."""
    nom = ("%s %s" % (agent.get("hostname") or "", agent.get("agent_id") or "")).lower()
    os_ = str(agent.get("os") or "").lower()
    site = str(agent.get("site") or "").strip()
    pl = set(plugins or ())
    role = ("hyperviseur" if "proxmox" in pl or re.search(r"\bpve|proxmox", nom) else
            "sauvegarde" if "pbs" in pl or re.search(r"\bpbs|backup|sauvegarde", nom) else
            "NAS" if re.search(r"\bnas", nom) else
            "IA" if "ollama" in pl or "gpu" in pl or re.search(r"\bia\b|prodia|preprodia|pcia|ollama", nom) else
            "sonde" if re.search(r"sonde|probe", nom) else
            "poste" if "windows" in os_ or "darwin" in os_ or "mac" in os_ else "serveur")
    heb = "OVH" if re.search(r"ovh|\bns\d{5,}", nom + " " + site.lower()) else "local"
    return {"role": role, "lan": site or "?", "hebergeur": heb}


def tendance(points):
    """points [(jour_index, octets_occupés)] -> pente en octets / jour (moindres carrés), None si moins de 3 points."""
    pts = [(x, y) for x, y in points if _num(y) is not None]
    if len(pts) < 3:
        return None
    n = len(pts)
    mx, my = sum(x for x, _ in pts) / n, sum(y for _, y in pts) / n
    den = sum((x - mx) ** 2 for x, _ in pts)
    return sum((x - mx) * (y - my) for x, y in pts) / den if den else None


def niveau(pct, jours, seuils):
    if _num(pct) is None:
        return "inconnu"
    if pct >= seuils["critique"] or (jours is not None and jours <= seuils["jours_critique"]):
        return "critique"
    if pct >= seuils["attention"] or (jours is not None and jours <= seuils["jours_attention"]):
        return "attention"
    return "ok"


def volumes_hote(disques, historique=None, seuils=SEUILS):
    """Montages de la mesure `host` -> volumes utiles (pseudo-systèmes et doublons de périphérique écartés)."""
    out, vus = [], set()
    for d in disques or []:
        if not isinstance(d, dict) or str(d.get("fstype") or "").lower() in FS_IGNORES:
            continue
        mp = str(d.get("mountpoint") or "")
        if not mp or MONTAGES_IGNORES.match(mp):
            continue
        tot = _num(d.get("total_bytes"))
        if not tot or tot < 256 * 1024 ** 2:
            continue
        cle = (d.get("device"), tot)
        if cle in vus and d.get("device"):
            continue                            # même périphérique monté plusieurs fois (bind, sous-volumes) : une fois
        vus.add(cle)
        used = _num(d.get("used_bytes"))
        libre = _num(d.get("free_bytes")) if _num(d.get("free_bytes")) is not None else (tot - used if used is not None else None)
        pct = _num(d.get("used_percent")) if _num(d.get("used_percent")) is not None else (round(100.0 * used / tot, 1) if used is not None else None)
        pente = tendance((historique or {}).get(mp) or [])
        jours = int(libre / pente) if pente and pente > 0 and libre is not None else None
        out.append({"nom": mp, "peripherique": d.get("device"), "fs": d.get("fstype"), "taille": tot, "occupe": used, "libre": libre, "pct": pct,
                    "pente_jour": int(pente) if pente is not None else None, "saturation_jours": jours, "niveau": niveau(pct, jours, seuils)})
    return sorted(out, key=lambda v: v["nom"])


def extension_hote(storage, materiel=None):
    """Possibilités d'extension d'un hôte : disques non utilisés, espace libre LVM / ZFS, RAID logiciel à renforcer.
    `storage` = mesure host.storage (lsblk aplati : name, type, size, fstype, mountpoint, parent, model, removable)."""
    notes = []
    blocs = (storage or {}).get("blocks") or []
    parents = {b.get("parent") for b in blocs if b.get("parent")}
    for b in blocs:
        if (b.get("type") == "disk" and not b.get("removable") and b.get("name") not in parents and not b.get("fstype") and not b.get("mountpoint")
                and _num(b.get("size")) and b["size"] > 8 * GO and not str(b.get("name") or "").startswith(("zram", "loop", "nbd"))):
            notes.append("disque %s (%s, %s) sans partition ni montage : utilisable" % (b.get("name"), b.get("model") or "?", taille(b["size"])))
    for vg in ((storage or {}).get("lvm") or {}).get("groups") or []:
        if _num(vg.get("free")) and vg["free"] > 5 * GO:
            notes.append("groupe LVM %s : %s libres non attribués (agrandissement d'un volume possible)" % (vg.get("vg"), taille(vg["free"])))
    for p in ((storage or {}).get("zfs") or {}).get("pools") or []:
        if _num(p.get("free")) is not None and _num(p.get("size")):
            notes.append("pool ZFS %s : %s libres sur %s" % (p.get("pool"), taille(p["free"]), taille(p["size"])))
    for md in (storage or {}).get("md") or []:
        n = len(md.get("devices") or [])
        if str(md.get("level") or "") in ("raid5", "5") and n and n <= 4:
            notes.append("RAID 5 %s sur %d disques : passage en RAID 6 conseillé avec de gros disques" % (md.get("array"), n))
    return notes


def baies_nas(n):
    if isinstance(n.get("baies"), int):
        return n["baies"]
    m = re.search(r"TS-?(\d{1,2})\d{2}", str(((n.get("systeme") or {}).get("modele")) or n.get("modele") or ""), re.I)
    return int(m.group(1)) if m else None


def machine_nas(n, relais, at, seuils=SEUILS, ssh=None):
    vols = []
    for v in n.get("volumes") or []:
        ko, libre_ko, pct = _num(v.get("ko")), _num(v.get("libre_ko")), _num(v.get("pct"))
        tot = ko * 1024 if ko else None
        libre = libre_ko * 1024 if libre_ko is not None else None
        vols.append({"nom": v.get("nom"), "fs": None, "taille": tot, "occupe": (tot - libre) if tot and libre is not None else None, "libre": libre,
                     "pct": pct, "pente_jour": None, "saturation_jours": None, "niveau": niveau(pct, None, seuils)})
    disques = [{"nom": "baie %s" % d.get("emplacement"), "modele": " ".join(x for x in (d.get("marque"), d.get("modele")) if x) or None,
                "taille": _num(d.get("octets")), "etat": d.get("etat"), "temperature": d.get("temperature")} for d in n.get("disques") or [] if isinstance(d, dict)]
    baies = baies_nas(n)
    notes = []
    if baies and len(disques) < baies:
        notes.append("%d baie(s) libre(s) sur %d : ajout de disques au groupe (extension, ou passage RAID 5 -> 6)" % (baies - len(disques), baies))
    raid = [r for r in ((ssh or {}).get("raid") or []) if not r.get("systeme")] or n.get("raid") or []
    for r in raid:
        lvl = str(r.get("niveau") or r.get("level") or "").lower()
        nd = len(r.get("disques") or [])
        if "5" in lvl and nd and nd <= 4:
            notes.append("RAID 5 sur %d disques : passage en RAID 6 conseillé avec des disques de cette taille" % nd)
    return {"id": "nas:%s" % (n.get("name") or n.get("host")), "nom": n.get("name") or n.get("host"), "type": "nas", "relais": relais, "at": at,
            "erreur": n.get("error"), "materiel": {"modele": (n.get("systeme") or {}).get("modele"), "ram": None, "disques": disques, "baies": baies},
            "volumes": vols, "raid": raid, "extension": notes}


def machine_hote(agent, host, hardware, storage, historique, seuils=SEUILS):
    hw = hardware or {}
    disques = [{"nom": d.get("name"), "modele": d.get("model"), "taille": _num(d.get("size")), "rotatif": d.get("rotational"), "transport": d.get("transport")}
               for d in hw.get("disks") or [] if isinstance(d, dict)]
    prod = " ".join(x for x in (hw.get("vendor"), hw.get("product")) if x) or None
    mem = (host or {}).get("memory") or {}
    return {"id": agent["agent_id"], "nom": agent.get("hostname") or agent["agent_id"], "type": "agent", "at": (host or {}).get("_at"),
            "materiel": {"modele": prod, "cpu": (hw.get("cpu") or {}).get("model"), "ram": _num(hw.get("memory_total_bytes")) or _num(mem.get("total_bytes")),
                         "disques": disques},
            "volumes": volumes_hote((host or {}).get("disks"), historique, seuils), "raid": (storage or {}).get("md") or [],
            "extension": extension_hote(storage, hw)}


def assembler(agents, hotes, inventaires, nas_snmp, nas_ssh, historiques, classement, seuils=None, plugins=None):
    """-> {seuils, machines: [machine + classement + niveau + alertes], groupes: {role|lan|hebergeur: {valeur: {n, taille, occupe}}}}."""
    s = dict(SEUILS, **(seuils or {}))
    machines = []
    for a in agents:
        aid = a["agent_id"]
        if aid not in hotes:
            continue
        h = hotes[aid]
        inv = inventaires.get(aid) or {}
        m = machine_hote(a, h, inv.get("hardware"), h.get("storage"), historiques.get(aid), s)
        m["classement"] = dict(deviner(a, inv.get("hardware"), (plugins or {}).get(aid, ())), **(classement.get(aid) or {}))
        machines.append(m)
    ssh = {}
    for _aid, _h, _at, d in nas_ssh or []:
        for n in (d or {}).get("nas") or []:
            if isinstance(n, dict):
                ssh[str(n.get("name") or "").lower()] = n
                ssh[str(n.get("host") or "").lower()] = n
    vus = set()
    for aid, h, at, d in nas_snmp or []:
        for n in (d or {}).get("nas") or []:
            if not isinstance(n, dict) or (n.get("name") or n.get("host")) in vus:
                continue
            vus.add(n.get("name") or n.get("host"))
            x = ssh.get(str(n.get("name") or "").lower()) or ssh.get(str(n.get("host") or "").lower())
            m = machine_nas(n, h or aid, at, s, x)
            relais = next((a for a in agents if a["agent_id"] == aid), {})
            m["classement"] = dict({"role": "NAS", "lan": relais.get("site") or "?", "hebergeur": "local"}, **(classement.get(m["id"]) or {}))
            machines.append(m)
    groupes = {"role": {}, "lan": {}, "hebergeur": {}}
    for m in machines:
        niv = [v["niveau"] for v in m["volumes"]]
        m["niveau"] = "critique" if "critique" in niv else "attention" if "attention" in niv else "ok" if niv else "inconnu"
        m["alertes"] = ["%s : %s %% occupé%s" % (v["nom"], v["pct"], ", plein dans %d j au rythme actuel" % v["saturation_jours"] if v["saturation_jours"] is not None else "")
                        for v in m["volumes"] if v["niveau"] in ("critique", "attention")]
        if m.get("erreur"):
            m["alertes"].append("relevé en erreur : %s" % m["erreur"])
        m["taille"] = sum(v["taille"] or 0 for v in m["volumes"])
        m["occupe"] = sum(v["occupe"] or 0 for v in m["volumes"])
        for g in groupes:
            e = groupes[g].setdefault(m["classement"].get(g) or "?", {"machines": 0, "taille": 0, "occupe": 0, "critique": 0, "attention": 0})
            e["machines"] += 1
            e["taille"] += m["taille"]
            e["occupe"] += m["occupe"]
            if m["niveau"] in ("critique", "attention"):
                e[m["niveau"]] += 1
    ordre = {"critique": 0, "attention": 1, "ok": 2, "inconnu": 3}
    machines.sort(key=lambda m: (ordre[m["niveau"]], str(m["nom"]).lower()))
    return {"seuils": s, "machines": machines, "groupes": groupes}


def taille(o):
    if not _num(o):
        return "?"
    for u, k in (("To", 1024 ** 4), ("Go", GO), ("Mo", 1024 ** 2)):
        if o >= k:
            return ("%.1f %s" % (o / k, u)).replace(".", ",")
    return "%d o" % o
