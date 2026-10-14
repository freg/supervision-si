# -*- coding: utf-8 -*-
"""Virtualisation directe pilotée par deux agents (livraison #748) -- commande `p2v` {action, …} :

  prepare_source  (poste à virtualiser) espace utilisé des volumes à imager, emplacements temporaires possibles
                  (lecteurs / montages avec assez de place, hors volume imagé de préférence), cible recommandée ;
  prepare_target  (nœud Proxmox) place du stockage, volume temporaire créé dans le pool LVM-thin (jamais sur le
                  disque système : une image de 70 Go l'avait rempli à 100 %), monté sous /var/lib/vz/import/p2v-<job> ;
  fetch           (nœud Proxmox) lecture au fil de l'eau de l'image de la source par le relais du central (#748),
                  débit borné, condensé vérifié à la fin ; status : progression ;
  cleanup         (nœud Proxmox) démontage et suppression du volume temporaire.
Pur ici (calculs, argv, analyse) ; exécution dans Agent (commande `p2v`)."""
import math
import os
import re
import shutil

JOB_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,31}$")
NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
IMPORT_ROOT = "/var/lib/vz/import"
MARGIN = 1.15


def need_with_margin(used):
    return int((used or 0) * MARGIN)


def lv_size_gb(need_bytes):
    """Taille du volume temporaire : besoin + 15 % + 5 Go (système de fichiers, journaux), arrondi au Go."""
    return int(math.ceil(need_with_margin(need_bytes) / 2**30)) + 5


def choose_source_target(need, candidates, system=None, given=None):
    """candidates : [{path, free}] ; -> (cible recommandée ou None, lignes annotées). La cible donnée prime si elle suffit ;
    sinon le plus grand espace hors volume système ; le volume système en dernier recours (Disk2vhd le tolère, VSS)."""
    rows = []
    for c in candidates or []:
        ok = c.get("free") is not None and c["free"] >= need_with_margin(need)
        rows.append(dict(c, ok=ok, system=bool(system) and str(c["path"]).rstrip("\\/").upper() == str(system).rstrip("\\/").upper()))
    if given:
        g = next((r for r in rows if str(r["path"]).rstrip("\\/") == str(given).rstrip("\\/")), None)
        return (given if g and g["ok"] else None), rows
    best = sorted([r for r in rows if r["ok"] and not r["system"]], key=lambda r: -r["free"]) or sorted([r for r in rows if r["ok"]], key=lambda r: -r["free"])
    return (best[0]["path"] if best else None), rows


def windows_drives(letters="CDEFGHIJKLMNOPQRSTUVWXYZ"):
    out = []
    for L in letters:
        p = "%s:\\" % L
        try:
            if os.path.exists(p):
                u = shutil.disk_usage(p)
                out.append({"path": p, "free": u.free, "total": u.total})
        except OSError:
            continue
    return out


def linux_mounts(proc_mounts_text, usage=shutil.disk_usage):
    """Montages candidats pour une image temporaire (systèmes de fichiers réels, réseau compris)."""
    keep = ("ext4", "ext3", "xfs", "btrfs", "nfs", "nfs4", "cifs", "zfs", "f2fs")
    seen, out = set(), []
    for line in (proc_mounts_text or "").splitlines():
        f = line.split()
        if len(f) < 3 or f[2] not in keep or f[1] in seen or f[1].startswith(("/boot", "/snap", "/proc", "/sys", "/run")):
            continue
        seen.add(f[1])
        try:
            u = usage(f[1])
            out.append({"path": f[1], "free": u.free, "total": u.total, "device": f[0], "fstype": f[2]})
        except OSError:
            continue
    return out


def parse_storage_cfg(text, storage):
    """/etc/pve/storage.cfg -> {type, vgname, thinpool, path} du stockage nommé, ou None."""
    cur = found = None
    for line in (text or "").splitlines():
        m = re.match(r"^(\w+):\s*(\S+)\s*$", line)
        if m:
            cur = {"type": m.group(1), "name": m.group(2)} if m.group(2) == storage else None
            found = cur or found
            continue
        if cur is not None and line.strip():
            k, _, v = line.strip().partition(" ")
            cur[k] = v.strip()
    return found


def thin_free(lvs_text):
    """`lvs --noheadings --units b --nosuffix -o lv_size,data_percent vg/pool` -> octets libres du pool, ou None."""
    try:
        size, pct = lvs_text.split()[:2]
        return int(float(size) * (1 - float(pct.replace(",", ".")) / 100.0))
    except (ValueError, AttributeError):
        return None


def target_argv(vg, pool, job, size_gb):
    lv = "p2v-%s" % job
    mnt = os.path.join(IMPORT_ROOT, lv)
    return lv, mnt, [["lvcreate", "-y", "-V", "%dG" % size_gb, "-T", "%s/%s" % (vg, pool), "-n", lv],
                     ["mkfs.ext4", "-q", "-m", "0", "-L", lv[:16], "/dev/%s/%s" % (vg, lv)],
                     ["mkdir", "-p", mnt],
                     ["mount", "/dev/%s/%s" % (vg, lv), mnt]]


def cleanup_argv(vg, job):
    lv = "p2v-%s" % job
    return [["umount", os.path.join(IMPORT_ROOT, lv)], ["lvremove", "-y", "%s/%s" % (vg, lv)]]


def throttle_sleep(sent_bytes, elapsed_s, mbps):
    """Secondes à attendre pour rester sous `mbps` Mbit/s (0 = pas de limite)."""
    if not mbps or mbps <= 0:
        return 0.0
    ideal = sent_bytes * 8 / (mbps * 1e6)
    return max(0.0, ideal - elapsed_s)
