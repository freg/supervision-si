#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Sonde Proxmox Backup Server (#716). Lecture seule, sans jeton ni mot de passe :
  - /etc/proxmox-backup/datastore.cfg -> datastores et chemins ;
  - arborescence de chaque datastore -> groupes (<type>/<id>, espaces de noms ns/<a>/ns/<b>/…) et snapshots
    (dossiers horodatés ; un snapshot sans index.json.blob est incomplet) ;
  - `proxmox-backup-manager task list --all` -> tâches récentes (échecs, avertissements, dernier GC / vérif / purge).
Sortie JSON : {"datastores": [...], "groups": [...], "tasks": {...}, "alerts": [...], "summary": {...}}. Pur : parse_cfg,
scan_store (fs injectable), summarize."""
import argparse
import calendar
import json
import os
import re
import shutil
import subprocess
import sys
import time

CFG = "/etc/proxmox-backup/datastore.cfg"
SNAP_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})Z$")
TYPES = ("vm", "ct", "host")
TASK_KINDS = {"garbage_collection": "gc", "verificationjob": "verify", "verify": "verify", "prunejob": "prune", "prune": "prune",
              "backup": "backup", "syncjob": "sync", "reader": None}


def parse_cfg(text):
    """datastore.cfg -> [{name, path, gc-schedule, …}] (format section-config de Proxmox)."""
    out, cur = [], None
    for line in (text or "").splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        m = re.match(r"^datastore:\s*(\S+)", line)
        if m:
            cur = {"name": m.group(1)}
            out.append(cur)
        elif cur is not None and line[:1] in (" ", "\t"):
            k, _, v = line.strip().partition(" ")
            cur[k] = v.strip()
    return out


def snap_epoch(name):
    m = SNAP_RE.match(name)
    return calendar.timegm(tuple(int(x) for x in m.groups()) + (0, 0, 0)) if m else None


def scan_store(path, listdir=os.listdir, isdir=os.path.isdir, exists=os.path.exists, max_depth=8):
    """Groupes d'un datastore : [{ns, type, id, count, last, last_complete}]."""
    groups = []

    def level(base, ns, depth):
        if depth > max_depth:
            return
        for t in TYPES:
            tdir = os.path.join(base, t)
            if not isdir(tdir):
                continue
            for gid in sorted(listdir(tdir)):
                gdir = os.path.join(tdir, gid)
                if not isdir(gdir):
                    continue
                snaps = sorted(e for e in (snap_epoch(s) and s for s in listdir(gdir)) if e)
                if not snaps:
                    continue
                last = snaps[-1]
                groups.append({"ns": ns, "type": t, "id": gid, "count": len(snaps), "last": snap_epoch(last),
                               "last_complete": exists(os.path.join(gdir, last, "index.json.blob"))})
        nsdir = os.path.join(base, "ns")
        if isdir(nsdir):
            for child in sorted(listdir(nsdir)):
                if isdir(os.path.join(nsdir, child)):
                    level(os.path.join(nsdir, child), (ns + "/" if ns else "") + child, depth + 1)
    level(path, "", 0)
    return groups


def read_tasks(runner=subprocess.run, limit=500):
    p = runner(["proxmox-backup-manager", "task", "list", "--all", "--limit", str(limit), "--output-format", "json"],
               capture_output=True, text=True, timeout=60)
    if p.returncode != 0:
        raise RuntimeError((p.stderr or p.stdout or "").strip()[:200] or "code %d" % p.returncode)
    return json.loads(p.stdout or "[]") or []


def summarize(stores, groups_by_store, usage, tasks, now, max_age_h=36, forget_after_days=30, full_warn=85, full_crit=95, task_hours=24):
    alerts, datastores, groups = [], [], []
    for st in stores:
        name = st["name"]
        u = usage.get(name)
        pct = round(100.0 * u["used"] / u["total"], 1) if u and u.get("total") else None
        datastores.append({"name": name, "path": st.get("path"), "used_percent": pct, "total": (u or {}).get("total"),
                           "free": (u or {}).get("free"), "gc_schedule": st.get("gc-schedule")})
        if pct is not None and pct >= full_warn:
            alerts.append({"code": "pbs-full:" + name, "severity": "critical" if pct >= full_crit else "warning",
                           "message": "PBS : datastore %s rempli à %.0f %%" % (name, pct)})
        for g in groups_by_store.get(name) or []:
            age_h = (now - g["last"]) / 3600 if g.get("last") else None
            state = "ok" if age_h is not None and age_h <= max_age_h else ("inactif" if age_h is not None and age_h > forget_after_days * 24 else "en retard")
            ref = "%s:%s%s/%s" % (name, g["ns"] + "/" if g["ns"] else "", g["type"], g["id"])
            groups.append(dict(g, store=name, ref=ref, age_h=round(age_h, 1) if age_h is not None else None, state=state))
            if state == "en retard":
                alerts.append({"code": "pbs-old:" + ref, "severity": "warning",
                               "message": "PBS : %s sans sauvegarde depuis %d h" % (ref, age_h)})
            if not g.get("last_complete") and age_h is not None and age_h > 6:
                alerts.append({"code": "pbs-incomplete:" + ref, "severity": "warning",
                               "message": "PBS : dernier snapshot de %s incomplet (sans index)" % ref})
    recent, last_by = [], {}
    for t in tasks or []:
        kind = TASK_KINDS.get(t.get("worker_type"), t.get("worker_type"))
        if not kind:
            continue
        start = t.get("starttime") or 0
        status = str(t.get("status") or ("en cours" if not t.get("endtime") else ""))
        key = (kind, str(t.get("worker_id") or ""))
        if start > last_by.get(key, {}).get("start", -1):
            last_by[key] = {"kind": kind, "id": key[1], "start": start, "end": t.get("endtime"), "status": status}
        if now - start <= task_hours * 3600:
            recent.append({"kind": kind, "id": key[1], "start": start, "end": t.get("endtime"), "status": status, "user": t.get("user")})
    for (kind, wid), t in sorted(last_by.items()):
        if t["status"] and t["status"] not in ("OK", "en cours") and now - t["start"] <= task_hours * 3600:
            warn = t["status"].upper().startswith("WARNINGS")
            alerts.append({"code": "pbs-task:%s:%s" % (kind, wid), "severity": "warning" if warn else "critical" if kind in ("backup", "verify") else "warning",
                           "message": "PBS : tâche %s %s %s (%s)" % (kind, wid, "avec avertissements" if warn else "en échec", t["status"][:120])})
    return {"datastores": datastores, "groups": groups, "tasks": {"recent": recent[-100:], "last": list(last_by.values())},
            "alerts": alerts, "summary": {"datastores": len(datastores), "groups": len(groups),
                                          "late": sum(1 for g in groups if g["state"] == "en retard"), "alerts": len(alerts),
                                          "state": "critical" if any(a["severity"] == "critical" for a in alerts) else "warning" if alerts else "ok"}}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--cfg", default=CFG)
    ap.add_argument("--max-age-h", type=float, default=36)
    ap.add_argument("--forget-after-days", type=float, default=30)
    ap.add_argument("--full-warn", type=float, default=85)
    ap.add_argument("--full-crit", type=float, default=95)
    a = ap.parse_args(argv)
    try:
        with open(a.cfg, encoding="utf-8") as fh:
            stores = parse_cfg(fh.read())
    except OSError as e:
        print(json.dumps({"datastores": [], "groups": [], "alerts": [], "error": "configuration PBS illisible (%s) -- serveur PBS ?" % e}, ensure_ascii=False))
        return 0
    groups, usage = {}, {}
    for st in stores:
        p = st.get("path")
        if p and os.path.isdir(p):
            groups[st["name"]] = scan_store(p)
            try:
                du = shutil.disk_usage(p)
                usage[st["name"]] = {"total": du.total, "used": du.used, "free": du.free}
            except OSError:
                pass
    try:
        tasks, terr = read_tasks(), None
    except Exception as e:  # noqa: BLE001
        tasks, terr = [], str(e)[:200]
    out = summarize(stores, groups, usage, tasks, time.time(), a.max_age_h, a.forget_after_days, a.full_warn, a.full_crit)
    if terr:
        out["tasks_error"] = terr
    print(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
