# -*- coding: utf-8 -*-
"""Stockage de l'hôte Linux (livraison #503) : volumes, partitions et
systèmes de fichiers -- « compléter l'agent linux sur la gestion de
Z{volume/partition/fs} ».

Quatre couches, chacune facultative (outil absent = couche absente,
jamais une erreur) :

- **blocs** : `lsblk -J -b` -- disques, partitions, LVM, md, zvols avec
  type, taille, FS, point de montage, parent ;
- **LVM** : `pvs` / `vgs` / `lvs` en JSON -- volumes physiques, groupes,
  volumes logiques (thin pools : occupation données/métadonnées) ;
- **RAID logiciel** : `/proc/mdstat` -- niveau, disques, état dégradé ;
- **ZFS** : `zpool list` / `zpool status` (santé, capacité,
  fragmentation, erreurs, dernier scrub), `zfs list` (datasets et
  zvols : utilisé, disponible, quota, compression), snapshots agrégés
  par dataset (nombre, plus ancien, plus récent, espace).

Tout ce qui est traitement pur (parseurs, agrégations) est testable sans
outil ; `collect_storage(cmd, which)` injecte l'exécution. La mesure
`host` embarque le résultat sous `storage` ; `risks.evaluate` en tire
les risques (pool dégradé, capacité ZFS, erreurs, scrub ancien, thin
pool plein, md dégradé, dataset proche de son quota).
"""
import json
import re
import shutil
import time

from . import host

ZPOOL_LIST_FIELDS = "name,size,alloc,free,fragmentation,capacity,health"
ZFS_LIST_FIELDS = "name,type,used,avail,refer,mountpoint,compressratio,quota,volsize"
SNAP_LIST_FIELDS = "name,used,creation"
MAX_SNAPSHOT_ROWS = 20000  # garde-fou mémoire sur un hôte à très nombreux snapshots


def _int(v):
    try:
        if v in (None, "", "-"):
            return None
        return int(float(str(v).strip().rstrip("%B")))
    except (ValueError, TypeError):
        return None


def _pct(v):
    try:
        s = str(v).strip().rstrip("%")
        return None if s in ("", "-") else float(s)
    except (ValueError, TypeError):
        return None


# ------------------------------------------------------------ lsblk

def flatten_lsblk(tree):
    """`lsblk -J` (arbre) -> liste plate [{name, type, size, fstype,
    mountpoint, parent, model, rotational, removable}]."""
    out = []

    def walk(nodes, parent):
        for n in nodes or []:
            out.append({"name": n.get("name"), "type": n.get("type"), "size": _int(n.get("size")),
                        "fstype": n.get("fstype"), "mountpoint": n.get("mountpoint") or (n.get("mountpoints") or [None])[0],
                        "parent": parent, "model": (n.get("model") or "").strip() or None,
                        "rotational": None if n.get("rota") is None else bool(n.get("rota") in (True, 1, "1")),
                        "removable": None if n.get("rm") is None else bool(n.get("rm") in (True, 1, "1"))})
            walk(n.get("children"), n.get("name"))

    walk((tree or {}).get("blockdevices"), None)
    return out


# ------------------------------------------------------------ LVM

def parse_lvm_report(text, key):
    """Sortie `--reportformat json` de pvs/vgs/lvs -> liste de dicts
    (clé `pv`, `vg` ou `lv`)."""
    try:
        data = json.loads(text or "{}")
    except ValueError:
        return []
    out = []
    for rep in data.get("report") or []:
        out.extend(rep.get(key) or [])
    return out


def lvm_summary(pvs, vgs, lvs):
    """Vue LVM compacte : groupes avec taille/libre, volumes logiques avec
    attributs lisibles, thin pools avec occupation."""
    groups = []
    for vg in vgs:
        groups.append({"vg": vg.get("vg_name"), "size": _int(vg.get("vg_size")), "free": _int(vg.get("vg_free")),
                       "pv_count": _int(vg.get("pv_count")), "lv_count": _int(vg.get("lv_count"))})
    volumes = []
    for lv in lvs:
        attr = lv.get("lv_attr") or ""
        kind = {"t": "thin-pool", "V": "thin", "o": "origin", "s": "snapshot", "m": "mirror", "r": "raid", "-": "linear"}.get(attr[:1], attr[:1] or None)
        volumes.append({"lv": lv.get("lv_name"), "vg": lv.get("vg_name"), "size": _int(lv.get("lv_size")),
                        "kind": kind, "attr": attr, "active": attr[4:5] == "a" if len(attr) > 4 else None,
                        "data_percent": _pct(lv.get("data_percent")), "metadata_percent": _pct(lv.get("metadata_percent")),
                        "pool": lv.get("pool_lv") or None, "origin": lv.get("origin") or None})
    physical = [{"pv": pv.get("pv_name"), "vg": pv.get("vg_name") or None, "size": _int(pv.get("pv_size")), "free": _int(pv.get("pv_free"))} for pv in pvs]
    return {"physical": physical, "groups": groups, "volumes": volumes}


# ------------------------------------------------------------ mdstat

MD_LINE_RE = re.compile(r"^(md\d+)\s*:\s*(\w+)\s+(\S+)\s+(.*)$")
MD_STATE_RE = re.compile(r"\[(\d+)/(\d+)\]\s*\[([U_]+)\]")


def parse_mdstat(text):
    """`/proc/mdstat` -> [{array, state, level, devices, total, active,
    degraded, resync}]."""
    arrays = []
    cur = None
    for line in (text or "").splitlines():
        m = MD_LINE_RE.match(line.strip())
        if m:
            devs = [d.split("[")[0] for d in m.group(4).split()]
            cur = {"array": m.group(1), "state": m.group(2), "level": m.group(3), "devices": devs,
                   "total": None, "active": None, "degraded": False, "resync": None}
            arrays.append(cur)
            continue
        if cur is None:
            continue
        st = MD_STATE_RE.search(line)
        if st:
            cur["total"], cur["active"] = int(st.group(1)), int(st.group(2))
            cur["degraded"] = "_" in st.group(3) or cur["active"] < cur["total"]
        if "resync" in line or "recovery" in line or "reshape" in line or "check" in line:
            pm = re.search(r"=\s*([\d.]+)%", line)
            cur["resync"] = (line.strip().split()[1] if len(line.split()) > 1 else "en cours") + (" %s%%" % pm.group(1) if pm else "")
    return arrays


# ------------------------------------------------------------ ZFS

def parse_zpool_list(text):
    pools = []
    for line in (text or "").splitlines():
        parts = line.split("\t") if "\t" in line else line.split()
        if len(parts) < 7:
            continue
        pools.append({"pool": parts[0], "size": _int(parts[1]), "alloc": _int(parts[2]), "free": _int(parts[3]),
                      "fragmentation_percent": _pct(parts[4]), "capacity_percent": _pct(parts[5]), "health": parts[6]})
    return pools


SCRUB_DONE_RE = re.compile(r"scrub repaired .*? on (.+)$")
SCRUB_PROGRESS_RE = re.compile(r"scrub in progress")
DEV_LINE_RE = re.compile(r"^\s+(\S+)\s+(ONLINE|DEGRADED|FAULTED|OFFLINE|UNAVAIL|REMOVED)\s+(\d+)\s+(\d+)\s+(\d+)")


def parse_zpool_status(text, now=None):
    """`zpool status` -> {pool: {state, errors, scan, scrub_at, scrub_age_s,
    devices: [{name, state, read, write, cksum}]}}."""
    now = time.time() if now is None else now
    pools, cur = {}, None
    for line in (text or "").splitlines():
        s = line.strip()
        if s.startswith("pool:"):
            cur = {"state": None, "errors": None, "scan": None, "scrub_at": None, "scrub_age_s": None, "devices": []}
            pools[s.split(":", 1)[1].strip()] = cur
        elif cur is None:
            continue
        elif s.startswith("state:"):
            cur["state"] = s.split(":", 1)[1].strip()
        elif s.startswith("scan:"):
            cur["scan"] = s.split(":", 1)[1].strip()
            m = SCRUB_DONE_RE.search(cur["scan"])
            if m:
                cur["scrub_at"] = m.group(1).strip()
                for fmt in ("%a %b %d %H:%M:%S %Y",):
                    try:
                        t = time.mktime(time.strptime(cur["scrub_at"], fmt))
                        cur["scrub_age_s"] = max(0, int(now - t))
                    except ValueError:
                        pass
            elif SCRUB_PROGRESS_RE.search(cur["scan"]):
                cur["scrub_age_s"] = 0
        elif s.startswith("errors:"):
            cur["errors"] = s.split(":", 1)[1].strip()
        else:
            dm = DEV_LINE_RE.match(line)
            if dm and dm.group(1) not in pools:
                cur["devices"].append({"name": dm.group(1), "state": dm.group(2), "read": int(dm.group(3)),
                                       "write": int(dm.group(4)), "cksum": int(dm.group(5))})
    return pools


def parse_zfs_list(text):
    """`zfs list -Hp -t filesystem,volume -o <ZFS_LIST_FIELDS>`."""
    out = []
    for line in (text or "").splitlines():
        parts = line.split("\t")
        if len(parts) < 9:
            continue
        name, typ, used, avail, refer, mp, ratio, quota, volsize = parts[:9]
        used_i, avail_i, quota_i = _int(used), _int(avail), _int(quota)
        limit = quota_i if quota_i else ((used_i or 0) + (avail_i or 0) if avail_i is not None else None)
        out.append({"name": name, "pool": name.split("/")[0], "type": typ, "used": used_i, "avail": avail_i, "refer": _int(refer),
                    "mountpoint": None if mp in ("-", "none", "legacy") else mp,
                    "compressratio": _pct(ratio.rstrip("x")) if ratio else None,
                    "quota": quota_i or None, "volsize": _int(volsize) or None,
                    "used_percent": round(100.0 * used_i / limit, 1) if limit and used_i is not None else None})
    return out


def aggregate_snapshots(text, now=None):
    """`zfs list -Hp -t snapshot -o name,used,creation` -> {dataset:
    {count, used, oldest_age_s, newest_age_s}} -- jamais la liste brute
    (des milliers de lignes sur un hôte de backup)."""
    now = time.time() if now is None else now
    agg = {}
    for i, line in enumerate((text or "").splitlines()):
        if i >= MAX_SNAPSHOT_ROWS:
            break
        parts = line.split("\t")
        if len(parts) < 3 or "@" not in parts[0]:
            continue
        ds = parts[0].split("@", 1)[0]
        used, created = _int(parts[1]) or 0, _int(parts[2])
        a = agg.setdefault(ds, {"count": 0, "used": 0, "oldest_age_s": None, "newest_age_s": None})
        a["count"] += 1
        a["used"] += used
        if created is not None:
            age = max(0, int(now - created))
            a["oldest_age_s"] = age if a["oldest_age_s"] is None else max(a["oldest_age_s"], age)
            a["newest_age_s"] = age if a["newest_age_s"] is None else min(a["newest_age_s"], age)
    return agg


# ------------------------------------------------------------ collecte

def _run(cmd, argv, timeout=20):
    try:
        r = cmd(argv, timeout=timeout)
    except TypeError:
        r = cmd(argv)
    except Exception:  # noqa: BLE001 -- une couche en panne ne fait jamais tomber la mesure
        return None
    if r is None or getattr(r, "returncode", 1) != 0:
        return None
    return r.stdout or ""


def collect_storage(cmd=host.run_cmd, files=host.read_file, which=shutil.which, now=None):
    """Toutes les couches disponibles ; `available` liste celles trouvées."""
    now = time.time() if now is None else now
    out = {"available": [], "blocks": [], "lvm": None, "md": [], "zfs": None}
    if which("lsblk"):
        txt = _run(cmd, ["lsblk", "-J", "-b", "-o", "NAME,TYPE,SIZE,FSTYPE,MOUNTPOINT,MODEL,ROTA,RM"])
        if txt:
            try:
                out["blocks"] = flatten_lsblk(json.loads(txt))
                out["available"].append("lsblk")
            except ValueError:
                pass
    if which("lvs"):
        pvs = parse_lvm_report(_run(cmd, ["pvs", "--reportformat", "json", "--units", "b", "--nosuffix", "-o", "pv_name,vg_name,pv_size,pv_free"]), "pv")
        vgs = parse_lvm_report(_run(cmd, ["vgs", "--reportformat", "json", "--units", "b", "--nosuffix", "-o", "vg_name,vg_size,vg_free,pv_count,lv_count"]), "vg")
        lvs = parse_lvm_report(_run(cmd, ["lvs", "--reportformat", "json", "--units", "b", "--nosuffix", "-o", "lv_name,vg_name,lv_size,lv_attr,data_percent,metadata_percent,pool_lv,origin"]), "lv")
        if vgs or lvs or pvs:
            out["lvm"] = lvm_summary(pvs, vgs, lvs)
            out["available"].append("lvm")
    mdstat = files("/proc/mdstat")
    if mdstat:
        out["md"] = parse_mdstat(mdstat)
        if out["md"]:
            out["available"].append("md")
    if which("zpool") and which("zfs"):
        pools = parse_zpool_list(_run(cmd, ["zpool", "list", "-H", "-p", "-o", ZPOOL_LIST_FIELDS]))
        if pools:
            states = parse_zpool_status(_run(cmd, ["zpool", "status"]), now)
            for p in pools:
                st = states.get(p["pool"]) or {}
                p.update({"state": st.get("state"), "errors": st.get("errors"), "scan": st.get("scan"),
                          "scrub_age_s": st.get("scrub_age_s"), "devices": st.get("devices") or []})
            datasets = parse_zfs_list(_run(cmd, ["zfs", "list", "-H", "-p", "-t", "filesystem,volume", "-o", ZFS_LIST_FIELDS]))
            snaps = aggregate_snapshots(_run(cmd, ["zfs", "list", "-H", "-p", "-t", "snapshot", "-o", SNAP_LIST_FIELDS], timeout=60), now)
            for d in datasets:
                d["snapshots"] = snaps.get(d["name"]) or {"count": 0, "used": 0, "oldest_age_s": None, "newest_age_s": None}
            out["zfs"] = {"pools": pools, "datasets": datasets,
                          "snapshot_total": sum(a["count"] for a in snaps.values())}
            out["available"].append("zfs")
    return out
