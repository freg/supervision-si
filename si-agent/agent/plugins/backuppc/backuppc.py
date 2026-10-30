#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Sonde « backuppc » (#939), sur le serveur BackupPC (3.x ou 4.x) : état du serveur et de chaque hôte sauvegardé,
LECTURE SEULE.

Sources (toutes en lecture) :
- `BackupPC_serverMesg status info` / `status hosts` / `status queues` (exécuté sous l'utilisateur backuppc) :
  version, démarrage, prochain réveil, taille du pool, remplissage, état et dernière erreur de chaque hôte ;
- /etc/backuppc/hosts (liste des hôtes, utilisateur) ; /etc/backuppc/config.pl (TopDir) ;
- <TopDir>/pc/<hôte>/backups (historique : n°, type, dates, taille, erreurs de transfert) ;
- df du TopDir.

Sortie JSON : {"serveur": {...}, "pool": {...}, "hotes": [{host, user, etat, raison, erreur, derniere_bonne, age_h,
derniere_pleine, derniere_incr, sauvegardes, taille, xfer_errs, en_cours}], "echecs": [...], "files": {...},
"alerts": [...], "summary": {...}}. Pur (testé hors BackupPC) : parse_perl_hash, parse_hosts, parse_backups, analyser.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time

BIN_CANDIDATS = ("/usr/share/backuppc/bin/BackupPC_serverMesg", "/usr/local/BackupPC/bin/BackupPC_serverMesg",
                 "/usr/local/bin/BackupPC_serverMesg", "/usr/bin/BackupPC_serverMesg")
CONF_CANDIDATS = ("/etc/backuppc", "/etc/BackupPC", "/usr/local/BackupPC/conf")
TOPDIR_DEFAUT = "/var/lib/backuppc"

# Champs du fichier pc/<hôte>/backups (BackupPC 3 et 4, séparés par des tabulations).
CHAMPS_BACKUPS = ["num", "type", "startTime", "endTime", "nFiles", "size", "nFilesExist", "sizeExist", "nFilesNew", "sizeNew",
                  "xferErrs", "xferBadFile", "xferBadShare", "tarErrs", "compress", "sizeExistComp", "sizeNewComp", "noFill",
                  "fillFromNum", "mangle", "xferMethod", "level"]

_PAIR = re.compile(r"'([^']*)'\s*=>\s*(?:'((?:[^'\\]|\\.)*)'|([-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)|(undef))")


def parse_perl_hash(texte):
    """`%Status = ( 'h1' => { 'k' => v, ... }, 'h2' => { ... } );` ou `%Info = ( 'k' => v, ... );` -> dict.
    Deux niveaux au plus (c'est ce que BackupPC_serverMesg produit) ; les valeurs sont str, int ou float."""
    t = str(texte or "")
    t = t[t.find("(") + 1:] if "(" in t else t
    out = {}
    pos = 0
    tete = re.compile(r"'([^']+)'\s*=>\s*\{")
    while True:
        m = tete.search(t, pos)
        if not m:
            break
        fin = _accolade_fermante(t, m.end() - 1)
        out[m.group(1)] = _paires(t[m.end():fin])
        pos = fin + 1
    if not out:
        return _paires(t)
    return out


def _accolade_fermante(t, i):
    """Index de l'accolade fermant celle en t[i] (chaînes quotées ignorées)."""
    prof, j, dans = 0, i, False
    while j < len(t):
        c = t[j]
        if dans:
            if c == "\\":
                j += 1
            elif c == "'":
                dans = False
        elif c == "'":
            dans = True
        elif c == "{":
            prof += 1
        elif c == "}":
            prof -= 1
            if prof == 0:
                return j
        j += 1
    return len(t)


def _paires(t):
    d = {}
    for m in _PAIR.finditer(t):
        k = m.group(1)
        if m.group(4) is not None:
            d[k] = None
        elif m.group(3) is not None:
            v = m.group(3)
            d[k] = float(v) if ("." in v or "e" in v.lower()) else int(v)
        else:
            d[k] = m.group(2).replace("\\'", "'").replace("\\\\", "\\")
    return d


def parse_hosts(texte):
    """/etc/backuppc/hosts -> [{host, dhcp, user, more_users}] (sans la ligne d'en-tête `host dhcp user moreUsers`)."""
    out = []
    for l in str(texte or "").splitlines():
        l = l.split("#", 1)[0].strip()
        if not l:
            continue
        p = l.split()
        if p[0].lower() == "host" and len(p) > 1 and p[1].lower() == "dhcp":
            continue
        out.append({"host": p[0], "dhcp": (p[1] if len(p) > 1 else "0") == "1", "user": p[2] if len(p) > 2 else "",
                    "more_users": (p[3].split(",") if len(p) > 3 and p[3] else [])})
    return out


def parse_backups(texte):
    """pc/<hôte>/backups -> [{num, type, start, end, n_files, size, xfer_errs, bad_files, bad_shares, level}], du plus ancien
    au plus récent."""
    out = []
    for l in str(texte or "").splitlines():
        p = l.rstrip("\n").split("\t")
        if len(p) < 6 or not p[0].isdigit():
            continue
        d = dict(zip(CHAMPS_BACKUPS, p))

        def n(k):
            try:
                return int(float(d.get(k) or 0))
            except ValueError:
                return 0
        out.append({"num": n("num"), "type": d.get("type") or "?", "start": n("startTime"), "end": n("endTime"), "n_files": n("nFiles"),
                    "size": n("size"), "xfer_errs": n("xferErrs"), "bad_files": n("xferBadFile"), "bad_shares": n("xferBadShare"),
                    "level": n("level"), "methode": d.get("xferMethod") or ""})
    return sorted(out, key=lambda b: b["num"])


ETATS = {"Status_idle": "inactif", "Status_backup_starting": "démarrage", "Status_backup_in_progress": "sauvegarde en cours",
         "Status_restore_starting": "restauration (démarrage)", "Status_restore_in_progress": "restauration en cours",
         "Status_link_pending": "liaison au pool en attente", "Status_link_running": "liaison au pool", "Status_archive_starting": "archivage",
         "Status_archive_in_progress": "archivage en cours"}
RAISONS = {"Reason_backup_done": "sauvegarde faite", "Reason_restore_done": "restauration faite", "Reason_archive_done": "archive faite",
           "Reason_nothing_to_do": "rien à faire", "Reason_backup_failed": "SAUVEGARDE EN ÉCHEC", "Reason_restore_failed": "restauration en échec",
           "Reason_archive_failed": "archive en échec", "Reason_no_ping": "injoignable (pas de ping)", "Reason_backup_canceled_by_user": "annulée par l'utilisateur",
           "Reason_backup_canceled_by_signal": "annulée (signal)", "Reason_backup_canceled_disk_too_full": "annulée : disque plein"}


def analyser(info, status, queues, hosts, backups_par_hote, topdir_usage, now=None, max_age_h=48, old_days=7, full_warn=85, full_crit=95,
             erreur_serveur=None):
    """Assemble la sortie et les constats. `backups_par_hote` : {host: [parse_backups]} ; `topdir_usage` : (total, used, free) ou None."""
    now = now if now is not None else time.time()
    al = []

    def alerte(code, sev, msg):
        al.append({"code": code, "severity": sev, "message": msg})
    info = info or {}
    serveur = {"version": str(info.get("Version") or ""), "pid": info.get("pid"), "demarre": info.get("startTime"), "config_chargee": info.get("ConfigLTime"),
               "prochain_reveil": info.get("nextWakeup"), "erreur": erreur_serveur}
    if erreur_serveur:
        alerte("backuppc-serveur", "critical", "serveur BackupPC injoignable : %s" % erreur_serveur)
    pool = {"cpool_octets": int(float(info.get("cpoolKb") or 0) * 1024) or None, "cpool_fichiers": info.get("cpoolFileCnt"), "cpool_dossiers": info.get("cpoolDirCnt"),
            "pool_octets": int(float(info.get("poolKb") or 0) * 1024) or None, "pool_fichiers": info.get("poolFileCnt"),
            "fs_pct": info.get("DUlastValue"), "fs_pct_max_jour": info.get("DUDailyMax"), "fs_pct_max_veille": info.get("DUDailyMaxPrev"),
            "nettoyage_fichiers": info.get("cpoolFileCntRm"), "nettoyage_octets": int(float(info.get("cpoolKbRm") or 0) * 1024) or None}
    if topdir_usage:
        tot, used, free = topdir_usage
        pool.update(topdir_total=tot, topdir_utilise=used, topdir_libre=free, topdir_pct=round(100.0 * used / tot, 1) if tot else None)
    pct = pool.get("topdir_pct") if pool.get("topdir_pct") is not None else pool.get("fs_pct")
    if isinstance(pct, (int, float)):
        if pct >= full_crit:
            alerte("backuppc-pool-plein", "critical", "pool BackupPC à %s %% (seuil %s)" % (pct, full_crit))
        elif pct >= full_warn:
            alerte("backuppc-pool-presque-plein", "warning", "pool BackupPC à %s %% (seuil %s)" % (pct, full_warn))
    status = status or {}
    hotes, echecs = [], []
    noms = [h["host"] for h in hosts or []] or sorted(status)
    users = {h["host"]: h.get("user") for h in hosts or []}
    for h in noms:
        s = status.get(h) or {}
        bks = backups_par_hote.get(h) or []
        pleines = [b for b in bks if b["type"] == "full"]
        incrs = [b for b in bks if b["type"] == "incr"]
        last_good = s.get("lastGoodBackupTime") or (bks[-1]["start"] if bks else None)
        age_h = round((now - last_good) / 3600.0, 1) if isinstance(last_good, (int, float)) and last_good > 0 else None
        etat = ETATS.get(str(s.get("state") or ""), str(s.get("state") or "inconnu").replace("Status_", ""))
        raison = RAISONS.get(str(s.get("reason") or ""), str(s.get("reason") or "").replace("Reason_", "").replace("_", " "))
        erreur = str(s.get("error") or "").strip() or None
        en_cours = bool(s.get("activeJob"))
        hote = {"host": h, "user": users.get(h) or "", "etat": etat, "raison": raison, "erreur": erreur, "en_cours": en_cours,
                "type": s.get("type"), "derniere_bonne": last_good, "age_h": age_h,
                "derniere_pleine": pleines[-1]["start"] if pleines else None, "derniere_incr": incrs[-1]["start"] if incrs else None,
                "sauvegardes": len(bks), "pleines": len(pleines), "taille": bks[-1]["size"] if bks else None,
                "xfer_errs": bks[-1]["xfer_errs"] if bks else None, "derniere_tentative": s.get("endTime") or s.get("startTime"),
                "morts": s.get("deadCnt"), "vivants": s.get("aliveCnt"), "configure": h in users or not hosts}
        hotes.append(hote)
        echec = erreur or (str(s.get("reason") or "").endswith("_failed")) or raison == "injoignable (pas de ping)"
        if echec:
            echecs.append({"host": h, "type": s.get("type"), "quand": s.get("endTime") or s.get("startTime"), "erreur": erreur or raison,
                           "derniere_bonne": last_good, "age_h": age_h})
        if age_h is None:
            alerte("backuppc-jamais@%s" % h, "warning", "%s : aucune sauvegarde réussie connue" % h)
        elif age_h > old_days * 24:
            alerte("backuppc-vieux@%s" % h, "critical", "%s : dernière sauvegarde réussie il y a %d j%s" % (h, int(age_h // 24), " -- " + erreur if erreur else ""))
        elif age_h > max_age_h:
            alerte("backuppc-retard@%s" % h, "warning", "%s : dernière sauvegarde réussie il y a %d h%s" % (h, int(age_h), " -- " + erreur if erreur else ""))
        elif echec:
            alerte("backuppc-echec@%s" % h, "warning", "%s : dernière tentative en échec (%s) -- dernière réussie il y a %d h" % (h, erreur or raison, int(age_h)))
    files = {k: v for k, v in (queues or {}).items()} if isinstance(queues, dict) else {}
    hotes.sort(key=lambda x: (0 if any(a["code"].endswith("@" + x["host"]) and a["severity"] == "critical" for a in al) else 1 if any(a["code"].endswith("@" + x["host"]) for a in al) else 2, x["host"]))
    return {"serveur": serveur, "pool": pool, "hotes": hotes, "echecs": echecs, "files": files, "alerts": al,
            "summary": {"hotes": len(hotes), "echecs": len(echecs), "en_cours": sum(1 for h in hotes if h["en_cours"]), "alerts": len(al),
                        "state": "critical" if any(a["severity"] == "critical" for a in al) else "warning" if al else "ok"}}


# --- accès au système (non testé hors BackupPC) ---

def _server_mesg(binaire, user, *args, runner=subprocess.run, timeout=60):
    """Exécute BackupPC_serverMesg sous l'utilisateur backuppc (la sonde tourne en root)."""
    argv = [binaire] + list(args)
    if user and os.geteuid() == 0:
        if shutil.which("runuser"):
            argv = ["runuser", "-u", user, "--"] + argv
        else:
            argv = ["su", "-s", "/bin/sh", user, "-c", " ".join(argv)]
    try:
        r = runner(argv, capture_output=True, text=True, timeout=timeout, check=False)
    except Exception as e:  # noqa: BLE001
        return None, "%s" % e
    if r.returncode != 0:
        return None, (r.stderr or r.stdout or "code %s" % r.returncode).strip()[:300]
    return r.stdout, None


def _topdir(conf_dir):
    try:
        with open(os.path.join(conf_dir, "config.pl"), encoding="utf-8", errors="replace") as fh:
            for l in fh:
                m = re.match(r"\s*\$Conf\{TopDir\}\s*=\s*['\"]([^'\"]+)['\"]", l)
                if m:
                    return m.group(1)
    except OSError:
        pass
    return TOPDIR_DEFAUT


def _lire(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return ""


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--bin", default="")
    ap.add_argument("--conf", default="")
    ap.add_argument("--topdir", default="")
    ap.add_argument("--user", default="backuppc")
    ap.add_argument("--max-age-h", type=float, default=48)
    ap.add_argument("--old-days", type=float, default=7)
    ap.add_argument("--full-warn", type=float, default=85)
    ap.add_argument("--full-crit", type=float, default=95)
    a = ap.parse_args(argv)
    binaire = a.bin or next((b for b in BIN_CANDIDATS if os.path.exists(b)), None)
    conf = a.conf or next((c for c in CONF_CANDIDATS if os.path.isdir(c)), CONF_CANDIDATS[0])
    topdir = a.topdir or _topdir(conf)
    if not binaire:
        print(json.dumps(analyser({}, {}, {}, parse_hosts(_lire(os.path.join(conf, "hosts"))), {}, None, erreur_serveur="BackupPC_serverMesg introuvable (serveur BackupPC ?)"), ensure_ascii=False))
        return 0
    info_txt, err = _server_mesg(binaire, a.user, "status", "info")
    status_txt, err2 = _server_mesg(binaire, a.user, "status", "hosts")
    queues_txt, _ = _server_mesg(binaire, a.user, "status", "queues")
    hosts = parse_hosts(_lire(os.path.join(conf, "hosts")))
    bks = {h["host"]: parse_backups(_lire(os.path.join(topdir, "pc", h["host"], "backups"))) for h in hosts}
    try:
        u = shutil.disk_usage(topdir)
        usage = (u.total, u.used, u.free)
    except OSError:
        usage = None
    out = analyser(parse_perl_hash(info_txt) if info_txt else {}, parse_perl_hash(status_txt) if status_txt else {},
                   parse_perl_hash(queues_txt) if queues_txt else {}, hosts, bks, usage, max_age_h=a.max_age_h, old_days=a.old_days,
                   full_warn=a.full_warn, full_crit=a.full_crit, erreur_serveur=(err or err2))
    out["chemins"] = {"bin": binaire, "conf": conf, "topdir": topdir}
    print(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
