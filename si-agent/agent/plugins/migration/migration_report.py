#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""#774 : état des étapes de migration lancées sur cet hôte (tuile « Migration 2026-2027 ») -- lit STATE_DIR (meta,
journal, code de sortie, pause) et l'état de l'unité systemd ; mesure la taille copiée (volume ZFS, fichier, dossier)
et en tire le débit et la fin estimée d'un passage à l'autre. Lecture seule. Pur : step_state, tail, rate."""
import argparse
import glob
import json
import os
import subprocess
import sys
import time

STATE_DIR = "/var/lib/si-agent/migration"
KEEP_DAYS = 30


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


def _sh(argv):
    try:
        r = subprocess.run(argv, capture_output=True, text=True, timeout=30)
        return r.returncode, r.stdout
    except Exception:  # noqa: BLE001
        return 1, ""


def measure(m):
    if not m:
        return None
    t, target = m.get("type"), m.get("target")
    if t == "file":
        try:
            return os.stat(target).st_size
        except OSError:
            return None
    if t == "zfs":
        rc, out = _sh(["zfs", "get", "-Hp", "-o", "value", "used", target])
        return int(out.strip()) if rc == 0 and out.strip().isdigit() else None
    if t == "path":
        p = target
        while p and not os.path.exists(p):
            p = os.path.dirname(p.rstrip("/"))
        rc, out = _sh(["df", "-B1", "--output=used", p or "/"])
        v = out.strip().splitlines()[-1].strip() if rc == 0 and out.strip() else ""
        return int(v) if v.isdigit() else None
    return None


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
        size = measure(m.get("measure")) if st in ("running", "paused") or m.get("measure", {}) and m["measure"].get("type") == "file" else None
        r = rate(size, prev.get(m["id"]), now) if st == "running" else None
        total = m.get("total")
        try:
            ended = os.path.getmtime(base + ".rc") if rc is not None else None
        except OSError:
            ended = None
        steps.append({"id": m["id"], "kind": m.get("kind"), "title": m.get("title"), "state": st, "rc": rc, "started_at": m.get("started_at"),
                      "ended_at": ended, "size": size, "total": total, "rate_bps": r,
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
