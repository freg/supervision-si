#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Sonde « sauvegardes tirées » (#714) : journal de pve-pull-backup.sh -> dernière sauvegarde par (nœud, CT).
Sortie JSON : {"backups": [{host, vmid, at, ok, size, sha256, file, present, age_h, last_error, failures}], "free_bytes",
"alerts": [...], "summary"}. Pur : `summarize`."""
import argparse
import json
import os
import shutil
import sys
import time


def read_index(path, max_lines=20000):
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            lines = fh.readlines()[-max_lines:]
    except OSError:
        return None
    out = []
    for l in lines:
        try:
            r = json.loads(l)
        except ValueError:
            continue
        if isinstance(r, dict) and r.get("host") and str(r.get("vmid", "")).isdigit():
            out.append(r)
    return out


def summarize(rows, now, max_age_days=8, exists=os.path.exists):
    """Lignes du journal -> dernier succès et dernière tentative par (hôte, vmid) + constats. Pur (sauf `exists`)."""
    last, last_ok, fails = {}, {}, {}
    for r in rows or []:
        if not r.get("host") or not str(r.get("vmid", "")).isdigit():
            continue
        k = (str(r["host"]), int(r["vmid"]))
        if k not in last or (r.get("ended") or 0) >= (last[k].get("ended") or 0):
            last[k] = r
        if r.get("ok"):
            if k not in last_ok or (r.get("ended") or 0) >= (last_ok[k].get("ended") or 0):
                last_ok[k] = r
            fails[k] = 0
        else:
            fails[k] = fails.get(k, 0) + 1
    backups, alerts = [], []
    for k in sorted(last):
        ok = last_ok.get(k)
        at = (ok or {}).get("ended")
        b = {"host": k[0], "vmid": k[1], "at": at, "ok": bool(last[k].get("ok")), "size": (ok or {}).get("size"), "sha256": (ok or {}).get("sha256"),
             "file": (ok or {}).get("file"), "present": bool(ok and ok.get("file") and exists(ok["file"])),
             "age_h": round((now - at) / 3600, 1) if at else None, "last_error": None if last[k].get("ok") else last[k].get("error"),
             "failures": fails.get(k, 0)}
        backups.append(b)
        label = "%s / CT %s" % k
        if not b["ok"]:
            alerts.append({"code": "pull-failed", "severity": "warning", "message": "%s : dernière sauvegarde tirée en échec (%s)" % (label, b["last_error"] or "?")})
        if at and now - at > max_age_days * 86400:
            alerts.append({"code": "pull-old", "severity": "warning", "message": "%s : dernière sauvegarde réussie il y a %d jours" % (label, (now - at) // 86400)})
        if ok and not b["present"]:
            alerts.append({"code": "pull-missing", "severity": "warning", "message": "%s : fichier de la dernière sauvegarde introuvable (%s)" % (label, ok.get("file"))})
    return backups, alerts


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--index", default="/srv/backup/dumps/pulls.jsonl")
    ap.add_argument("--max-age-days", type=float, default=8)
    a = ap.parse_args(argv)
    now = time.time()
    rows = read_index(a.index)
    if rows is None:
        print(json.dumps({"backups": [], "alerts": [], "error": "journal %s absent (pve-pull-backup.sh pas encore lancé ?)" % a.index}, ensure_ascii=False))
        return 0
    backups, alerts = summarize(rows, now, a.max_age_days)
    try:
        free = shutil.disk_usage(os.path.dirname(a.index) or ".").free
    except OSError:
        free = None
    print(json.dumps({"backups": backups, "alerts": alerts, "free_bytes": free, "index": a.index,
                      "summary": {"backups": len(backups), "failed": sum(1 for b in backups if not b["ok"]), "alerts": len(alerts)}}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
