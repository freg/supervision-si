#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Sonde « copies-inventory » (#856) : inventaire de TOUTES les copies des CT / VM, partout où elles existent, pour
mesurer leur distance à la source (Migration › Copies et sauvegardes, Migration › Risques).

Sur chaque hôte (local et distants, un ssh par hôte, script sur l'entrée standard, lecture seule, PVE 5.4 et PBS compris) :
  - pools ZFS : santé, REDONDANCE (miroir / raidz, ou disques simples concaténés : aucune), occupation ;
  - jeux de données ZFS et instantanés : taille, taille logique, date, « written » (octets écrits depuis l'instantané
    précédent : sert à calculer exactement ce qui a changé depuis un instantané commun à la source et à la copie) ;
  - invités Proxmox du nœud et du cluster, réplications (pvesr), stockages ;
  - sauvegardes vzdump et flux « zfs send » posés en fichiers (stockages « dir » + chemins supplémentaires, ex. disque
    USB), sauvegardes des stockages PBS (pvesm list), instantanés d'un datastore PBS (sur le serveur PBS) ;
  - copies « fichiers » (rsync) : répertoires subvol-<id>-disk-<n> / vm-<id>-disk-<n> hors ZFS, date de la dernière
    synchronisation (ctime du répertoire) et volume (du, mis en cache tant que le répertoire n'a pas bougé).
Configuration : /etc/si-agent/copies-hosts.json (liste [{name, host, user, key, paths, dans, site}] ; « local »: true pour
l'hôte de l'agent ; « dans » : l'hôte physique qui porte une VM, ex. pbs10 dans pve10) ; à défaut : l'hôte local et
les nœuds de pve-remote.json. Pur et testé : parse_sections, parse_zpool_status, parse_zfs, parse_files, parse_pvesm_pbs,
parse_pvesr, build_host."""
import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
import time

SSH_OPTS = ["-o", "BatchMode=yes", "-o", "ConnectTimeout=15", "-o", "ServerAliveInterval=30", "-o", "StrictHostKeyChecking=accept-new"]
DU_CACHE = "/var/lib/si-agent/copies-du.json"

DRIVER_SH = r"""si_main() {
echo "@@node $(hostname -s)"
echo "## zpool"; command -v zpool >/dev/null 2>&1 && zpool list -H -p -o name,size,alloc,free,health 2>/dev/null
echo "## zstatus"; command -v zpool >/dev/null 2>&1 && zpool status -P 2>/dev/null | head -c 300000
echo "## zfs"; command -v zfs >/dev/null 2>&1 && zfs list -H -p -t filesystem,volume,snapshot -o name,type,used,referenced,logicalreferenced,creation,written,mountpoint 2>/dev/null | head -c 8000000
echo "## guests"
command -v pct >/dev/null 2>&1 && pct list 2>/dev/null | awk 'NR>1 {print "lxc", $1, $2, $NF}'
command -v qm >/dev/null 2>&1 && qm list 2>/dev/null | awk 'NR>1 {print "qemu", $1, $3, $2}'
echo "## resources"; command -v pvesh >/dev/null 2>&1 && pvesh get /cluster/resources --type vm --output-format json 2>/dev/null | head -c 600000; echo
echo "## cluster"; awk '/cluster_name/ {print $2; exit}' /etc/pve/corosync.conf 2>/dev/null
echo "## storagecfg"; cat /etc/pve/storage.cfg 2>/dev/null | head -c 30000
echo "## pvesr"; command -v pvesr >/dev/null 2>&1 && pvesr status 2>/dev/null | head -c 50000
echo "## pbs"
for s in $(awk '$1 == "pbs:" {print $2}' /etc/pve/storage.cfg 2>/dev/null); do echo "== $s"; timeout 120 pvesm list "$s" 2>/dev/null | head -c 1500000; done
echo "## pbsds"
if command -v proxmox-backup-manager >/dev/null 2>&1; then
  for d in $(proxmox-backup-manager datastore list --output-format json 2>/dev/null | tr '{,' '\n\n' | sed -n 's/.*"path":"\([^"]*\)".*/\1/p'); do
    [ -d "$d" ] && find "$d" -mindepth 3 -maxdepth 3 -type d -path "*/[cv][tm]/*" -printf 'P %T@ %p\n' 2>/dev/null | head -n 20000
  done
fi
echo "## files"
D="$SI_PATHS"
for p in $(awk '$1 == "dir:" {s = 1; next} /^[a-z]+:/ {s = 0} s && $1 == "path" {print $2 "/dump"}' /etc/pve/storage.cfg 2>/dev/null); do D="$D $p"; done
for p in $D; do
  [ -d "$p" ] || continue
  echo "@@df $(df -PT "$p" 2>/dev/null | awk 'NR == 2 {print $2, $1, $3 * 1024, $5 * 1024}') $p"
  find "$p" -maxdepth 4 -type f \( -name 'vzdump-*' -o -name '*.zfs' -o -name '*.zfs.gz' -o -name '*.zfs.zst' -o -name '*.zfs.lz4' \) -printf 'F %s %T@ %p\n' 2>/dev/null | head -n 20000
  find "$p" -maxdepth 4 -type d \( -name 'subvol-*-disk-*' -o -name 'vm-*-disk-*' -o -name 'basevol-*-disk-*' \) -printf 'D %C@ %T@ %p\n' -prune 2>/dev/null | head -n 5000
done
echo "@@done"
}
SI_PATHS='@@PATHS@@'
si_main </dev/null
"""
VMID = re.compile(r"(?:^|[/_.@-])(?:subvol|vm|basevol|base)-(\d+)-disk-(\d+)")
VZ = re.compile(r"vzdump-(lxc|qemu|openvz)-(\d+)-(?:.*?)(\d{4})_(\d{2})_(\d{2})-(\d{2})_(\d{2})_(\d{2})")
VZ_EXT = (".tar", ".tar.gz", ".tgz", ".tar.lzo", ".tar.zst", ".vma", ".vma.gz", ".vma.lzo", ".vma.zst")


def driver_script(paths=()):
    return DRIVER_SH.replace("@@PATHS@@", " ".join(p.replace("'", "") for p in paths if p))


def parse_sections(text):
    """-> (nœud, {section: texte}, complet ?)."""
    node, sec, cur, done = None, {}, None, False
    for line in (text or "").splitlines():
        if line.startswith("@@node "):
            node = line[7:].strip() or None
            continue
        if line.strip() == "@@done":
            done = True
            continue
        m = re.match(r"^## (\w+)$", line.strip())
        if m:
            cur = m.group(1)
            sec[cur] = []
            continue
        if cur:
            sec[cur].append(line)
    return node, {k: "\n".join(v) for k, v in sec.items()}, done


def _int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def parse_zpool_list(text):
    out = {}
    for line in (text or "").splitlines():
        p = line.split("\t")
        if len(p) >= 5:
            out[p[0]] = {"name": p[0], "size": _int(p[1]), "alloc": _int(p[2]), "free": _int(p[3]), "health": p[4]}
    return out


def parse_zpool_status(text):
    """zpool status -P -> {pool: {state, redondance: oui|non|partielle, vdevs: [{nom, type, etat, erreurs}]}}.
    Un vdev de premier niveau qui est un disque seul (pas mirror-N / raidzN-N / draid) = pas de redondance."""
    out, pool, in_cfg, base = {}, None, False, None
    for raw in (text or "").splitlines():
        line = raw.rstrip()
        m = re.match(r"^\s*pool:\s*(\S+)", line)
        if m:
            pool = m.group(1)
            out[pool] = {"state": None, "vdevs": [], "erreurs": None}
            in_cfg, base = False, None
            continue
        if pool is None:
            continue
        m = re.match(r"^\s*state:\s*(\S+)", line)
        if m:
            out[pool]["state"] = m.group(1)
            continue
        m = re.match(r"^\s*errors:\s*(.*)$", line)
        if m:
            out[pool]["erreurs"] = m.group(1).strip()
            in_cfg = False
            continue
        if re.match(r"^\s*config:", line):
            in_cfg = True
            continue
        if not in_cfg or not line.strip() or line.strip().startswith("NAME"):
            continue
        ind = len(line.expandtabs(8)) - len(line.expandtabs(8).lstrip())
        p = line.split()
        if p[0] == pool and base is None:
            base = ind
            continue
        if base is None:
            continue
        if p[0] in ("logs", "cache", "spares") and ind == base:
            in_cfg = False if p[0] != "spares" else in_cfg
            if p[0] in ("logs", "cache"):
                base = None
            continue
        if p[0] in ("special", "dedup") and ind == base:
            continue
        if ind <= base:
            continue
        if ind == base + 2:
            typ = "miroir" if p[0].startswith("mirror") else "raidz" if p[0].startswith("raidz") else "draid" if p[0].startswith("draid") else "disque"
            err = sum(_int(x) or 0 for x in p[2:5]) if len(p) >= 5 else 0
            out[pool]["vdevs"].append({"nom": p[0], "type": typ, "etat": p[1] if len(p) > 1 else None, "erreurs": err})
        elif out[pool]["vdevs"] and len(p) >= 5:
            out[pool]["vdevs"][-1]["erreurs"] += sum(_int(x) or 0 for x in p[2:5])
    for v in out.values():
        types = {d["type"] for d in v["vdevs"]}
        v["redondance"] = None if not types else "non" if types == {"disque"} else "partielle" if "disque" in types else "oui"
        v["disques_simples"] = sum(1 for d in v["vdevs"] if d["type"] == "disque")
    return out


def parse_zfs(text):
    """zfs list -H -p ... -> [{name, type, used, refer, lref, creation, written, mountpoint, snap, dataset}]."""
    out = []
    for line in (text or "").splitlines():
        p = line.split("\t")
        if len(p) < 8:
            continue
        name = p[0]
        ds, _, snap = name.partition("@")
        out.append({"name": name, "type": p[1], "used": _int(p[2]), "refer": _int(p[3]), "lref": _int(p[4]), "creation": _int(p[5]),
                    "written": _int(p[6]), "mountpoint": p[7] if p[7] not in ("-", "none", "legacy") else None, "dataset": ds, "snap": snap or None})
    return out


def parse_guests(text):
    out = []
    for line in (text or "").splitlines():
        p = line.split()
        if len(p) >= 3 and p[1].isdigit():
            out.append({"type": p[0], "vmid": int(p[1]), "status": p[2], "name": " ".join(p[3:]) if len(p) > 3 else ""})
    return out


def parse_pvesr(text):
    out = []
    for line in (text or "").splitlines()[1:]:
        p = line.split()
        if len(p) >= 8 and re.match(r"^\d+-\d+$", p[0]):
            out.append({"job": p[0], "vmid": int(p[0].split("-")[0]), "enabled": p[1].lower() == "yes", "target": p[2].split("/")[-1],
                        "last_sync": p[3].replace("_", " ") if p[3] != "-" else None, "duration": p[5], "fail_count": _int(p[6]), "state": " ".join(p[7:])})
    return out


def parse_storage_cfg(text):
    out, cur = {}, None
    for line in (text or "").splitlines():
        m = re.match(r"^(\w+):\s*(\S+)", line)
        if m:
            cur = {"type": m.group(1)}
            out[m.group(2)] = cur
            continue
        p = line.strip().split(None, 1)
        if cur is not None and len(p) == 2:
            cur[p[0]] = p[1].strip()
    return out


def parse_pvesm_pbs(text):
    """pvesm list <pbs> (sections « == stockage ») -> [{storage, volid, vmid, at, size}] ; date tirée du volid."""
    out, st = [], None
    for line in (text or "").splitlines():
        m = re.match(r"^== (\S+)$", line.strip())
        if m:
            st = m.group(1)
            continue
        p = line.split()
        if not p or p[0] == "Volid" or ":" not in p[0]:
            continue
        m = re.search(r"backup/(ct|vm)/(\d+)/(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})", p[0])
        if not m:
            continue
        at = dt.datetime.strptime(m.group(3), "%Y-%m-%dT%H:%M:%S").replace(tzinfo=dt.timezone.utc).timestamp()
        size = next((_int(x) for x in p[1:] if (_int(x) or 0) > 1000), None)
        out.append({"storage": st, "volid": p[0], "type": "lxc" if m.group(1) == "ct" else "qemu", "vmid": int(m.group(2)), "at": at, "size": size})
    return out


def parse_pbsds(text):
    out = []
    for line in (text or "").splitlines():
        m = re.match(r"^P (\d+)(?:\.\d+)? (.*/(ct|vm)/(\d+)/(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})Z?)$", line.strip())
        if m:
            at = dt.datetime.strptime(m.group(5), "%Y-%m-%dT%H:%M:%S").replace(tzinfo=dt.timezone.utc).timestamp()
            out.append({"path": m.group(2), "type": "lxc" if m.group(3) == "ct" else "qemu", "vmid": int(m.group(4)), "at": at})
    return out


def _vz_ts(name):
    m = VZ.search(name)
    if not m:          # nom libre (ex. vzdump-lxc-101-pve3-2026-10-26.tar.gz) : date = celle du fichier
        m = re.search(r"vzdump-(lxc|qemu|openvz)-(\d+)-", name)
        return (("lxc" if m.group(1) in ("lxc", "openvz") else "qemu"), int(m.group(2)), None) if m else (None, None, None)
    at = dt.datetime(*[int(x) for x in m.groups()[2:]]).replace(tzinfo=dt.timezone.utc).timestamp()
    return ("lxc" if m.group(1) in ("lxc", "openvz") else "qemu"), int(m.group(2)), at


def parse_files(text):
    """Section « files » -> (supports {chemin: {fs, device, size, avail}}, archives, flux, répertoires)."""
    supports, archives, flux, dirs = {}, [], [], []
    for line in (text or "").splitlines():
        if line.startswith("@@df "):
            p = line[5:].split()
            if len(p) >= 5:
                supports[" ".join(p[4:])] = {"fs": p[0], "device": p[1], "size": _int(p[2]), "avail": _int(p[3])}
            continue
        p = line.split(" ", 3)
        if len(p) < 4:
            continue
        if p[0] == "F":
            path, base = p[3], os.path.basename(p[3])
            size, mt = _int(p[1]), int(float(p[2]))
            if base.startswith("vzdump-"):
                if not base.endswith(VZ_EXT):
                    continue
                typ, vmid, at = _vz_ts(base)
                if vmid is None:
                    continue
                archives.append({"path": path, "type": typ, "vmid": vmid, "at": at or mt, "mtime": mt, "size": size,
                                 "compresse": not base.endswith((".tar", ".vma"))})
            else:
                m = VMID.search(base)
                snap = re.search(r"@([^./]+)", base)
                flux.append({"path": path, "vmid": int(m.group(1)) if m else None, "disk": m.group(0).lstrip("/_.@-") if m else None,
                             "snap": snap.group(1) if snap else None, "at": mt, "size": size})
        elif p[0] == "D":
            path, base = p[3], os.path.basename(p[3])
            m = VMID.search("/" + base)
            if m:
                dirs.append({"path": path, "vmid": int(m.group(1)), "disk": base, "at": int(float(p[1])), "mtime": int(float(p[2]))})
    return supports, archives, flux, dirs


def build_host(name, zone, sec, done, du_sizes=None, dans=None):
    supports, archives, flux, dirs = parse_files(sec.get("files"))
    for d in dirs:
        d["size"] = (du_sizes or {}).get(d["path"])
    try:
        res = json.loads((sec.get("resources") or "").strip() or "[]")
    except ValueError:
        res = []
    pools = parse_zpool_list(sec.get("zpool"))
    st = parse_zpool_status(sec.get("zstatus"))
    for k, v in pools.items():
        v.update(st.get(k, {}))
    return {"name": name, "zone": zone, "ok": True, "complete": done, "dans": dans, "cluster": (sec.get("cluster") or "").strip() or None,
            "pools": list(pools.values()), "zfs": parse_zfs(sec.get("zfs")), "guests": parse_guests(sec.get("guests")),
            "cluster_vms": [{"vmid": int(r["vmid"]), "node": r.get("node"), "name": r.get("name"), "type": r.get("type"), "status": r.get("status")}
                            for r in res if isinstance(r, dict) and str(r.get("vmid", "")).isdigit()],
            "storages": parse_storage_cfg(sec.get("storagecfg")), "replication": parse_pvesr(sec.get("pvesr")),
            "pbs": parse_pvesm_pbs(sec.get("pbs")), "pbs_datastore": parse_pbsds(sec.get("pbsds")),
            "supports": supports, "archives": archives, "flux": flux, "dirs": dirs}


def _run(h, script, runner, timeout=1500):
    if h is None or h.get("local"):
        p = runner(["bash", "-s"], input=script, capture_output=True, text=True, timeout=timeout)
    else:
        if h.get("key") and not os.path.exists(h["key"]):
            raise RuntimeError("clé %s introuvable (la placer dans /etc/si-agent/keys/, chmod 600)" % h["key"])
        args = ["ssh"] + SSH_OPTS + (["-i", h["key"], "-o", "IdentitiesOnly=yes"] if h.get("key") else []) + ["%s@%s" % (h.get("user") or "root", h["host"]), "bash -s"]
        p = runner(args, input=script, capture_output=True, text=True, timeout=timeout)
    return p


def du_needed(dirs, cache):
    """Répertoires dont le volume est à (re)calculer : absents du cache ou modifiés (ctime) depuis."""
    return [d["path"] for d in dirs if (cache.get(d["path"]) or [None])[0] != d["at"]]


def du_script(paths):
    q = " ".join("'%s'" % p.replace("'", "") for p in paths)
    return "for p in %s; do s=$(timeout 1200 du -sb \"$p\" 2>/dev/null | cut -f1); echo \"@@du ${s:-?} $p\"; done </dev/null\n" % q


def parse_du(text):
    out = {}
    for line in (text or "").splitlines():
        if line.startswith("@@du "):
            p = line[5:].split(" ", 1)
            if len(p) == 2 and p[0].isdigit():
                out[p[1]] = int(p[0])
    return out


def load_targets(hosts_file, remote_file):
    if hosts_file and os.path.exists(hosts_file):
        with open(hosts_file, encoding="utf-8") as fh:
            return [h for h in json.load(fh) if isinstance(h, dict) and (h.get("local") or h.get("host"))]
    out = [{"name": None, "local": True}]
    if remote_file and os.path.exists(remote_file):
        try:
            with open(remote_file, encoding="utf-8") as fh:
                out += [h for h in json.load(fh) if isinstance(h, dict) and h.get("host")]
        except (OSError, ValueError):
            pass
    return out


def main(argv=None, runner=subprocess.run, cache_file=DU_CACHE):
    ap = argparse.ArgumentParser()
    ap.add_argument("--hosts", default="/etc/si-agent/copies-hosts.json")
    ap.add_argument("--remote", default="/etc/si-agent/pve-remote.json")
    ap.add_argument("--path", action="append", default=[], help="chemin supplémentaire à parcourir sur l'hôte local")
    a = ap.parse_args(argv)
    try:
        with open(cache_file, encoding="utf-8") as fh:
            cache = json.load(fh)
    except (OSError, ValueError):
        cache = {}
    hosts = []
    for h in load_targets(a.hosts, a.remote):
        paths = list(h.get("paths") or []) + (a.path if h.get("local") else [])
        label = h.get("name") or (h.get("host") if not h.get("local") else None)
        try:
            p = _run(h, driver_script(paths), runner)
            node, sec, done = parse_sections(p.stdout)
            if not node:
                raise RuntimeError(((p.stderr or "").strip().splitlines() or ["code %d" % p.returncode])[-1][:200])
            name = label or node
            hc = cache.setdefault(name, {})
            supports, archives, flux, dirs = parse_files(sec.get("files"))
            todo = du_needed(dirs, hc)
            if todo:
                q = _run(h, du_script(todo), runner, timeout=3000)
                for path, size in parse_du(q.stdout).items():
                    d = next((x for x in dirs if x["path"] == path), None)
                    if d:
                        hc[path] = [d["at"], size]
            hosts.append(dict(build_host(name, "local" if h.get("local") else "distant", sec, done,
                                         {k: v[1] for k, v in hc.items()}, h.get("dans")), site=h.get("site")))
        except Exception as e:  # noqa: BLE001 -- un hôte injoignable n'empêche pas les autres
            hosts.append({"name": label or "local", "zone": "local" if h.get("local") else "distant", "ok": False, "error": str(e)[:200]})
    try:
        os.makedirs(os.path.dirname(cache_file), exist_ok=True)
        with open(cache_file, "w", encoding="utf-8") as fh:
            json.dump(cache, fh)
    except OSError:
        pass
    alerts = []
    for h in hosts:
        for p in h.get("pools") or []:
            if p.get("health") and p["health"] != "ONLINE":
                alerts.append({"code": "zpool:%s:%s" % (h["name"], p["name"]), "severity": "critical" if p.get("redondance") == "non" else "warning",
                               "message": "%s : pool %s %s%s" % (h["name"], p["name"], p["health"], " SANS redondance" if p.get("redondance") == "non" else "")})
    print(json.dumps({"at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "hosts": hosts, "alerts": alerts,
                      "summary": {"hosts": len(hosts), "ok": sum(1 for h in hosts if h.get("ok"))}}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
