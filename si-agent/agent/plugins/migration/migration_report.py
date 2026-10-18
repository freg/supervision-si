#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""#774 : état des étapes de migration lancées sur cet hôte (tuile « Migration 2026-2027 ») -- lit STATE_DIR (meta,
journal, code de sortie, pause) et l'état de l'unité systemd ; mesure la taille copiée (volume ZFS, fichier, dossier)
et en tire le débit et la fin estimée d'un passage à l'autre. Lecture seule. Pur : step_state, tail, rate, parse_zfs_list,
pick_total, parse_df_used.

Avancement « restant / transféré / total » : le total vient de la SOURCE (une fois par étape, gardé dans <id>.total) --
`zfs list` sur le nœud source (volumes envoyés, sous-volumes des CT, dossiers montés), à défaut `df` dans le CT en service.
Le transféré : volume ZFS de destination, fichier, ou dossier de destination (volume dédié : son occupation ; sinon
croissance du volume depuis le lancement + ce qui avait déjà été copié par un passage précédent de la même étape)."""
import argparse
import fnmatch
import glob
import json
import os
import re
import subprocess
import sys
import time

STATE_DIR = "/var/lib/si-agent/migration"
KEEP_DAYS = 30
SSH = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", "-o", "StrictHostKeyChecking=accept-new"]
TOTAL_RETRY = 1800   # nouvel essai de calcul du total au bout de 30 min s'il a échoué


def tail(path, n=40, max_bytes=16384):
    try:
        with open(path, "rb") as fh:
            fh.seek(0, 2)
            size = fh.tell()
            fh.seek(max(0, size - max_bytes))
            lines = fh.read().decode("utf-8", "replace").splitlines()
    except OSError:
        return []
    # dernière exécution seulement (après le dernier @@START)
    for i in range(len(lines) - 1, -1, -1):
        if lines[i].startswith("@@START"):
            lines = lines[i + 1:]
            break
    return [l[:300] for l in lines if l.strip() and not l.startswith("@@STEP")][-n:]


def step_state(active, rc, paused):
    """Unité systemd + code de sortie + marque de pause -> running | paused | done | failed | stopped | unknown."""
    if active in ("active", "activating", "reloading"):
        return "paused" if paused else "running"
    if rc is None:
        return "unknown" if active in ("inactive", "failed", "") else "running"
    if rc == 0:
        return "done"
    return "stopped" if rc == 143 else "failed"


def rate(size, prev, now):
    if not prev or size is None or prev.get("size") is None or now <= prev.get("at", now):
        return None
    d = (size - prev["size"]) / (now - prev["at"])
    return round(d) if d >= 0 else None


def _sh(argv, timeout=30):
    try:
        r = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout
    except Exception:  # noqa: BLE001
        return 1, ""


def _nearest(path):
    p = path
    while p and not os.path.exists(p):
        p = os.path.dirname(p.rstrip("/"))
    return p or "/"


def _df_used(path):
    rc, out = _sh(["df", "-B1", "--output=used", _nearest(path)])
    v = out.strip().splitlines()[-1].strip() if rc == 0 and out.strip() else ""
    return int(v) if v.isdigit() else None


def measure(m, meta=None):
    """-> (octets transférés, portée) ; portée : dest (mesure exacte), depuis (croissance du volume + déjà copié), volume (volume entier)."""
    if not m:
        return None, None
    t, target = m.get("type"), m.get("target")
    if t == "file":
        try:
            return os.stat(target).st_size, "dest"
        except OSError:
            return None, None
    if t == "zfs":
        rc, out = _sh(["zfs", "get", "-Hp", "-o", "value", "used", target])
        return (int(out.strip()), "dest") if rc == 0 and out.strip().isdigit() else (None, None)
    if t == "path":
        used = _df_used(target)
        if used is None:
            return None, None
        if os.path.isdir(target) and os.path.ismount(target.rstrip("/") or "/"):
            return used, "dest"          # volume dédié à la destination
        meta = meta or {}
        if meta.get("base_used") is not None:
            return (meta.get("carry") or 0) + max(0, used - meta["base_used"]), "depuis"
        return used, "volume"
    return None, None


def parse_zfs_list(out):
    """`zfs list -Hp -o name,mountpoint,referenced,logicalreferenced` -> [{name, mp, ref, lref}]."""
    rows = []
    for line in (out or "").splitlines():
        c = line.split("\t")
        if len(c) >= 4 and c[2].isdigit():
            rows.append({"name": c[0], "mp": c[1], "ref": int(c[2]), "lref": int(c[3]) if c[3].isdigit() else int(c[2])})
    return rows


def pick_total(kind, params, rows, compressed):
    """Taille de la source (octets) d'après la liste ZFS du nœud source ; compressed : la destination compresse (ZFS)."""
    key = "ref" if compressed else "lref"
    p = params or {}
    if kind == "zfs_pull":
        ids = "|".join(str(int(i)) for i in p.get("ids") or [])
        pool = str(p.get("pool") or "")
        if not ids or not pool:
            return None
        rx = re.compile(r"/(subvol|vm)-(%s)-disk-[0-9]+$" % ids)
        sel = [r["ref"] for r in rows if r["name"].startswith(pool + "/") and rx.search(r["name"])]   # send -c : compression gardée
    elif kind == "rsync_pull_all":
        pat = str(p.get("src_dir") or "").rstrip("/") + "/" + str(p.get("pattern") or "*")
        sel = [r[key] for r in rows if r["mp"].startswith("/") and fnmatch.fnmatch(r["mp"], pat)]
    elif kind == "rsync_pull" and p.get("ct"):
        rx = re.compile(r"/subvol-%d-disk-[0-9]+$" % int(p["ct"]))
        sel = [r[key] for r in rows if rx.search(r["name"])]
    elif kind == "rsync_pull" and p.get("src"):
        sel = [r[key] for r in rows if r["mp"].rstrip("/") == str(p["src"]).rstrip("/")][:1]
    else:
        return None
    return sum(sel) or None


def parse_df_used(out):
    """`df -B1 -P` -> somme de la colonne « utilisé »."""
    tot = 0
    for line in (out or "").splitlines()[1:]:
        c = line.split()
        if len(c) >= 3 and c[2].isdigit():
            tot += int(c[2])
    return tot or None


def source_total(m, sh=None):
    sh = sh or _sh
    kind, p = m.get("kind"), m.get("params") or {}
    if kind not in ("zfs_pull", "rsync_pull_all", "rsync_pull") or not p.get("host"):
        return None
    dst = (m.get("measure") or {}).get("target") or "/"
    compressed = kind == "zfs_pull" or sh(["stat", "-f", "-c", "%T", _nearest(dst)])[1].strip() == "zfs"
    rc, out = sh(SSH + ["root@%s" % p["host"], "zfs list -Hp -t filesystem,volume -o name,mountpoint,referenced,logicalreferenced"], timeout=20)
    t = pick_total(kind, p, parse_zfs_list(out), compressed) if rc == 0 else None
    if t is None and kind == "rsync_pull" and p.get("ct"):   # CT hors ZFS (LVM, répertoire) en service : occupation vue du CT
        rc, out = sh(SSH + ["root@%s" % p["host"], "pct exec %d -- df -B1 -l -P -x tmpfs -x devtmpfs" % int(p["ct"])], timeout=20)
        t = parse_df_used(out) if rc == 0 else None
    return t


def cached_total(base, m, now, compute=True, sh=None):
    """Total de la source, calculé une fois par étape (<id>.total) ; nouvel essai après TOTAL_RETRY s'il a échoué."""
    try:
        with open(base + ".total") as fh:
            c = json.load(fh)
    except (OSError, ValueError):
        c = None
    if c and c.get("started_at") == m.get("started_at") and (c.get("total") or not compute or now - (c.get("at") or 0) < TOTAL_RETRY):
        return c.get("total")
    if not compute:
        return None
    t = source_total(m, sh)
    try:
        with open(base + ".total", "w") as fh:
            json.dump({"total": t, "at": now, "started_at": m.get("started_at")}, fh)
    except OSError:
        pass
    return t


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=STATE_DIR)
    ap.add_argument("--state", default="/var/lib/si-agent/migration-report.state.json")
    a = ap.parse_args(argv)
    try:
        with open(a.state) as fh:
            prev = json.load(fh)
    except (OSError, ValueError):
        prev = {}
    now, steps, new = time.time(), [], {}
    for meta_path in sorted(glob.glob(os.path.join(a.dir, "*.json"))):
        try:
            with open(meta_path) as fh:
                m = json.load(fh)
        except (OSError, ValueError):
            continue
        if now - (m.get("started_at") or now) > KEEP_DAYS * 86400:
            continue
        base = meta_path[:-5]
        rc = None
        try:
            with open(base + ".rc") as fh:
                v = fh.read().strip()
                rc = int(v) if v.lstrip("-").isdigit() else None
        except OSError:
            pass
        _r, act = _sh(["systemctl", "show", "-p", "ActiveState", "--value", m.get("unit") or "none"])
        st = step_state(act.strip(), rc, os.path.exists(base + ".paused"))
        size, scope = measure(m.get("measure"), m) if st in ("running", "paused") or m.get("measure", {}) and m["measure"].get("type") == "file" else (None, None)
        r = rate(size, prev.get(m["id"]), now) if st == "running" else None
        total = m.get("total") or cached_total(base, m, now, compute=st in ("running", "paused"))
        if size is not None and scope in ("dest", "depuis") and st in ("running", "paused"):
            try:   # repris par migctl au prochain lancement de l'étape (ce qui est déjà copié)
                with open(base + ".done", "w") as fh:
                    json.dump({"target": (m.get("measure") or {}).get("target"), "size": size}, fh)
            except OSError:
                pass
        try:
            ended = os.path.getmtime(base + ".rc") if rc is not None else None
        except OSError:
            ended = None
        steps.append({"id": m["id"], "kind": m.get("kind"), "title": m.get("title"), "state": st, "rc": rc, "started_at": m.get("started_at"),
                      "ended_at": ended, "size": size, "total": total, "rate_bps": r, "scope": scope,
                      "remaining": max(0, total - size) if total and size is not None else None,
                      "pct": round(min(100.0, 100.0 * size / total), 1) if size is not None and total else None,
                      "eta_s": int((total - size) / r) if total and r and r > 0 and size is not None and total > size else None,
                      "log_tail": tail(base + ".log")})
        if size is not None:
            new[m["id"]] = {"size": size, "at": now}
    try:
        os.makedirs(os.path.dirname(a.state), exist_ok=True)
        with open(a.state + ".tmp", "w") as fh:
            json.dump(new, fh)
        os.replace(a.state + ".tmp", a.state)
    except OSError:
        pass
    print(json.dumps({"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)), "steps": steps}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
