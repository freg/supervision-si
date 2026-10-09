#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Sonde « sauvegardes tirées » (#714) : journal de pve-pull-backup.sh -> dernière sauvegarde par (nœud, CT).
#716 : le même journal accueille les TÂCHES de sauvegarde de n'importe quel script (ligne avec "job" au lieu de
"vmid") : base de données d'une application, archive d'un site… avec un délai propre (`max_age_h`) et l'option
`notify_ok` (chaque réussite est un événement « backup-done », donc une notification si on l'a routée).
Sortie JSON : {"backups": [{host, vmid|job, at, ok, size, sha256, file, present, age_h, last_error, failures}], "free_bytes",
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
        if _key(r):
            out.append(r)
    return out


def _key(r):
    """(hôte, n° de CT) ou (hôte, nom de tâche) ; None si la ligne n'est ni l'un ni l'autre."""
    if not isinstance(r, dict) or not r.get("host"):
        return None
    if str(r.get("vmid", "")).isdigit():
        return (str(r["host"]), int(r["vmid"]))
    job = str(r.get("job") or "").strip()
    return (str(r["host"]), job[:80]) if job else None


def summarize(rows, now, max_age_days=8, exists=os.path.exists):
    """Lignes du journal -> dernier succès et dernière tentative par (hôte, vmid) + constats. Pur (sauf `exists`)."""
    last, last_ok, fails = {}, {}, {}
    for r in rows or []:
        k = _key(r)
        if not k:
            continue
        if k not in last or (r.get("ended") or 0) >= (last[k].get("ended") or 0):
            last[k] = r
        if r.get("ok"):
            if k not in last_ok or (r.get("ended") or 0) >= (last_ok[k].get("ended") or 0):
                last_ok[k] = r
            fails[k] = 0
        else:
            fails[k] = fails.get(k, 0) + 1
    backups, alerts = [], []
    for k in sorted(last, key=lambda x: (x[0], str(x[1]))):
        ok = last_ok.get(k)
        at = (ok or {}).get("ended")
        is_job = not isinstance(k[1], int)
        max_age_h = last[k].get("max_age_h") if isinstance(last[k].get("max_age_h"), (int, float)) and last[k]["max_age_h"] > 0 else max_age_days * 24
        b = {"host": k[0], "vmid": None if is_job else k[1], "job": k[1] if is_job else None, "at": at, "max_age_h": max_age_h,
             "notify_ok": bool(last[k].get("notify_ok")), "ok": bool(last[k].get("ok")), "size": (ok or {}).get("size"), "sha256": (ok or {}).get("sha256"),
             "file": (ok or {}).get("file"), "present": bool(ok and ok.get("file") and exists(ok["file"])),
             "age_h": round((now - at) / 3600, 1) if at else None, "last_error": None if last[k].get("ok") else last[k].get("error"),
             "failures": fails.get(k, 0)}
        backups.append(b)
        label = "%s / %s" % (k[0], k[1]) if is_job else "%s / CT %s" % k
        if not b["ok"]:
            alerts.append({"code": "pull-failed:" + label, "severity": "warning", "key": label,
                           "message": "%s : dernière sauvegarde %s en échec (%s)" % (label, "" if is_job else "tirée", b["last_error"] or "?")})
        if at and now - at > max_age_h * 3600:
            age = now - at
            alerts.append({"code": "pull-old:" + label, "severity": "warning", "key": label, "message": "%s : dernière sauvegarde réussie il y a %s" % (
                label, "%d jours" % (age // 86400) if age >= 2 * 86400 else "%d h" % (age // 3600))})
        if ok and ok.get("file") and not b["present"]:   # #716 : une tâche peut ne pas déclarer de fichier
            alerts.append({"code": "pull-missing:" + label, "severity": "warning", "key": label, "message": "%s : fichier de la dernière sauvegarde introuvable (%s)" % (label, ok.get("file"))})
    return backups, alerts


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--index", action="append", help="journal(aux) à lire ; #725 : plusieurs --index (sauvegardes tirées, copies de secours ZFS)")
    ap.add_argument("--max-age-days", type=float, default=8)
    a = ap.parse_args(argv)
    paths = a.index or ["/srv/backup/dumps/pulls.jsonl", "/var/lib/si-agent/secours.jsonl"]
    now = time.time()
    found = [(p, read_index(p)) for p in paths]
    found = [(p, r) for p, r in found if r is not None]
    if not found:
        print(json.dumps({"backups": [], "alerts": [], "error": "journal absent (%s) : pve-pull-backup.sh ou zfs-secours.sh pas encore lancé ?" % ", ".join(paths)}, ensure_ascii=False))
        return 0
    rows = [r for _, rs in found for r in rs]
    backups, alerts = summarize(rows, now, a.max_age_days)
    try:
        free = shutil.disk_usage(os.path.dirname(found[0][0]) or ".").free
    except OSError:
        free = None
    print(json.dumps({"backups": backups, "alerts": alerts, "free_bytes": free, "index": [p for p, _ in found],
                      "summary": {"backups": len(backups), "failed": sum(1 for b in backups if not b["ok"]), "alerts": len(alerts)}}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
