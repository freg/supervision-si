#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Sonde « serveur de messagerie » (livraison #692) -- Postfix + postscreen +
Amavis (+ SpamAssassin, ClamAV) + Dovecot, typiquement sous Modoboa.

Née d'un incident réel : courrier légitime supprimé en silence pendant des
mois (seuil de suppression à 3, `blacklist_to` sur une adresse active), puis
courrier entrant refusé 14 h (« 451 queue file write error ») parce que clamd
était arrêté et qu'Amavis exige l'antivirus.

Lit le journal mail sur les N dernières minutes et l'état de l'hôte ; remonte
un résumé (jamais le contenu d'un message : adresses, scores, identifiants de
quarantaine seulement) et des constats `alerts` (code, sévérité, message) que
le central transforme en événements (apparition / disparition) :

  queue-write-error   critical  refus temporaires 451 (filtre avant file en échec)
  amavis-trouble      critical  Amavis en erreur (antivirus, base, délai)
  service-down        critical  postfix / amavis / dovecot / clamd / base arrêté
  queue-backlog       warning   file Postfix chargée ou message ancien
  spam-false-positive warning   messages bloqués avec un score proche du seuil
  blacklist-to        warning   `blacklist_to` sur un destinataire (pénalité +10 à tout son courrier)
  antivirus-outdated  warning   signatures ClamAV trop anciennes / mise à jour refusée
  dnsbl-ignored       warning   postscreen consulte des listes noires sans agir
  os-eol              warning   système hors support
  log-unreadable      warning   journal mail introuvable ou illisible

Usage : mail_server.py [--log /var/log/mail.log] [--minutes 60] [--fp-below 8]
"""
import argparse
import fnmatch
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime

MONTHS = {m: i for i, m in enumerate(["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], 1)}
SYSLOG_RE = re.compile(r"^(?P<mon>[A-Z][a-z]{2}) +(?P<day>\d{1,2}) (?P<hms>\d\d:\d\d:\d\d) \S+ (?P<prog>[\w/.-]+)(?:\[\d+\])?: (?P<msg>.*)$")
ISO_RE = re.compile(r"^(?P<iso>\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d)\S* \S+ (?P<prog>[\w/.-]+)(?:\[\d+\])?: (?P<msg>.*)$")
VERDICT_RE = re.compile(r"\) (?P<verdict>Passed|Blocked) (?P<cat>[A-Z-]+)(?: \{(?P<action>[^}]*)\})?,")
ADDR_RE = re.compile(r"<(?P<from>[^>]*)> -> (?P<to>(?:<[^>]*>,?)+)")
QUAR_RE = re.compile(r"quarantine: (?P<q>[^,\s]+)")
HITS_RE = re.compile(r"Hits: (?P<hits>-?[\d.]+|-)")
SERVICES = ("postfix", "amavis", "dovecot", "clamav-daemon", "mysql", "mariadb", "postgresql", "spamassassin", "opendkim")
EOL_DEBIAN = {"6": "2016-02", "7": "2018-05", "8": "2020-06", "9": "2022-06", "10": "2024-06"}


def parse_time(line, now):
    """-> (epoch, programme, message) ou None. Année déduite (syslog sans année)."""
    m = SYSLOG_RE.match(line)
    if m:
        t = datetime.now().replace(month=MONTHS.get(m.group("mon"), 1), day=int(m.group("day")), microsecond=0)
        h, mi, s = (int(x) for x in m.group("hms").split(":"))
        ts = t.replace(hour=h, minute=mi, second=s).timestamp()
        if ts > now + 86400:          # décembre lu en janvier
            ts = t.replace(year=t.year - 1, hour=h, minute=mi, second=s).timestamp()
        return ts, m.group("prog"), m.group("msg")
    m = ISO_RE.match(line)
    if m:
        try:
            return datetime.strptime(m.group("iso"), "%Y-%m-%dT%H:%M:%S").timestamp(), m.group("prog"), m.group("msg")
        except ValueError:
            return None
    return None


def tail_lines(path, max_bytes=40 * 1024 * 1024):
    try:
        with open(path, "rb") as fh:
            fh.seek(0, os.SEEK_END)
            size = fh.tell()
            fh.seek(max(0, size - max_bytes))
            data = fh.read()
    except OSError:
        return None
    return data.decode("utf-8", "replace").splitlines()


def analyse(lines, now, minutes=60, fp_below=8.0):
    """Lignes du journal -> résumé de la fenêtre. Pure."""
    since = now - minutes * 60
    verdicts, rejects, postscreen, delivery = Counter(), Counter(), Counter(), Counter()
    fps, trouble, write_errors, top_rcpt_blocked = [], [], 0, Counter()
    local_domains = set()
    for line in lines or []:
        p = parse_time(line, now)
        if not p or p[0] < since:
            continue
        ts, prog, msg = p
        if "queue file write error" in msg:
            write_errors += 1
        if prog.startswith("amavis"):
            m = VERDICT_RE.search(msg)
            if m:
                verdicts["%s %s" % (m.group("verdict"), m.group("cat"))] += 1
                if m.group("verdict") == "Blocked" and m.group("cat") == "SPAM":
                    ad, qm, hm = ADDR_RE.search(msg), QUAR_RE.search(msg), HITS_RE.search(msg)
                    hits = float(hm.group("hits")) if hm and hm.group("hits") != "-" else None
                    to = [x for x in re.findall(r"<([^>]*)>", ad.group("to"))] if ad else []
                    for x in to:
                        top_rcpt_blocked[x] += 1
                    if hits is not None and hits < fp_below:
                        fps.append({"at": int(ts), "from": ad.group("from") if ad else None, "to": to, "hits": hits,
                                    "quarantine": qm.group("q") if qm else None, "action": m.group("action")})
            elif re.search(r"TROUBLE|FAILED|Can't connect|timed out|DBI|virus_scan", msg):
                trouble.append(msg[:200])
        elif prog.endswith("postscreen"):
            for k in ("PASS NEW", "PASS OLD", "DNSBL rank", "PREGREET", "HANGUP", "COMMAND PIPELINING", "BARE NEWLINE"):
                if k in msg:
                    postscreen[k] += 1
        elif prog.endswith("smtpd") and "NOQUEUE: reject" in msg:
            code = re.search(r": (\d{3} \d\.\d\.\d)", msg)
            why = re.search(r"(Recipient address rejected|Sender address rejected|Client host rejected|Helo command rejected|blocked using [\w.-]+|Relay access denied)", msg)
            rejects["%s %s" % (code.group(1) if code else "?", why.group(1) if why else "autre")] += 1
        if " status=" in msg:
            st = re.search(r" status=(\w+)", msg)
            if st:
                delivery[st.group(1)] += 1
                # #694 : remise locale (lmtp/virtual/local, Dovecot) -> domaine hébergé ici
                if st.group(1) == "sent" and (prog.endswith(("/lmtp", "/virtual", "/local")) or "dovecot" in msg):
                    dm = re.search(r" to=<[^@>]+@([^>]+)>", msg)
                    if dm:
                        local_domains.add(dm.group(1).lower())
    fps.sort(key=lambda f: f["hits"])
    return {"window_minutes": minutes, "queue_write_errors": write_errors, "amavis": dict(verdicts),
            "amavis_trouble": trouble[-5:], "false_positive_candidates": fps[:30], "fp_below": fp_below,
            "blocked_by_recipient": dict(top_rcpt_blocked.most_common(10)), "postscreen": dict(postscreen),
            "smtpd_rejects": dict(rejects.most_common(15)), "delivery": dict(delivery),
            "local_domains": sorted(local_domains)}


def run(argv, timeout=20):
    try:
        p = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
        return p.returncode, p.stdout.decode("utf-8", "replace"), p.stderr.decode("utf-8", "replace")
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 127, "", str(exc)


def services_state(runner=run, ignore=()):
    """{service: état} des services présents (LoadState=loaded), hors `ignore`.
    #694 : unité désactivée (`systemctl disable`) = arrêt volontaire -> « disabled », jamais signalé."""
    out = {}
    if not shutil.which("systemctl"):
        return out
    for svc in SERVICES:
        if svc in ignore:
            continue
        _, show, _ = runner(["systemctl", "show", "-p", "LoadState", "-p", "UnitFileState", svc])
        if "LoadState=loaded" not in show:
            continue
        _, st, _ = runner(["systemctl", "is-active", svc])
        st = st.strip() or "unknown"
        if st not in ("active", "activating") and re.search(r"UnitFileState=(disabled|masked)", show):
            st = "disabled"
        out[svc] = st
    return out


def queue_state(runner=run, now=None):
    now = now or time.time()
    code, out, _ = runner(["postqueue", "-j"])
    if code != 0:
        code, out2, _ = runner(["postqueue", "-p"])
        m = re.search(r"in (\d+) Requests?", out2)
        return {"count": int(m.group(1)) if m else 0, "oldest_seconds": None}
    items = []
    for l in out.splitlines():
        try:
            items.append(json.loads(l))
        except ValueError:
            continue
    oldest = min((i.get("arrival_time") or now for i in items), default=now)
    return {"count": len(items), "deferred": sum(1 for i in items if i.get("queue_name") == "deferred"),
            "oldest_seconds": int(now - oldest) if items else 0}


def postconf_checks(runner=run):
    code, out, err = runner(["postconf", "-h", "postscreen_dnsbl_sites", "postscreen_dnsbl_action"])
    lines = out.splitlines() if code == 0 else []
    undefined = sorted(set(re.findall(r"undefined parameter: (\w+)", err)))
    return {"dnsbl_sites": bool(lines and lines[0].strip()), "dnsbl_action": lines[1].strip() if len(lines) > 1 else None,
            "undefined_parameters": undefined}


def blacklist_to_entries(paths=("/etc/spamassassin", "/etc/mail/spamassassin")):
    out = []
    for d in paths:
        for f in sorted(glob.glob(os.path.join(d, "*.cf"))):
            try:
                for i, l in enumerate(open(f, encoding="utf-8", errors="replace"), 1):
                    m = re.match(r"^\s*blacklist_to\s+(\S+)", l)
                    if m:
                        out.append({"file": f, "line": i, "address": m.group(1)})
            except OSError:
                continue
    return out


def antivirus_state(now=None, db_dir="/var/lib/clamav", fresh_log="/var/log/clamav/freshclam.log"):
    now = now or time.time()
    dbs = [f for f in glob.glob(os.path.join(db_dir, "*.c[lv]d"))]
    newest = max((os.path.getmtime(f) for f in dbs), default=None)
    refused = False
    tail = tail_lines(fresh_log, 200_000) or []
    for l in tail[-60:]:
        if "403" in l or "Blocked by CDN" in l or "OUTDATED" in l:
            refused = True
    return {"databases": [os.path.basename(f) for f in dbs], "age_days": round((now - newest) / 86400, 1) if newest else None,
            "update_refused": refused}


def os_state():
    try:
        v = open("/etc/debian_version").read().strip()
    except OSError:
        return {"debian": None, "eol": None}
    major = v.split(".")[0]
    return {"debian": v, "eol": EOL_DEBIAN.get(major)}


def local_blacklist_to(entries, local_domains):
    """#694 : adresses `blacklist_to` (dédoublonnées) qui peuvent viser un destinataire HÉBERGÉ ici -- les
    motifs sur un domaine étranger (ex. *banque*@domaine-jetable) sont de l'anti-hameçonnage, pas un risque.
    Domaines locaux inconnus (aucune remise locale dans la fenêtre) : toutes les adresses. Pure."""
    seen = []
    for e in entries:
        a = e["address"].lower()
        if a not in seen:
            seen.append(a)
    if not local_domains:
        return seen
    out = []
    for a in seen:
        dom = a.rsplit("@", 1)[1] if "@" in a else "*"
        if any(fnmatch.fnmatch(ld, dom) for ld in local_domains):
            out.append(a)
    return out


def alerts_from(s):
    """Résumé complet -> constats. Pure."""
    a = []

    def add(code, sev, msg):
        a.append({"code": code, "severity": sev, "message": msg})
    log = s.get("log") or {}
    if log.get("error"):
        add("log-unreadable", "warning", log["error"] + " (argument --log de la sonde ; journal systemd seul : activer rsyslog)")
    if log.get("queue_write_errors"):
        add("queue-write-error", "critical", "%d refus temporaire(s) « 451 queue file write error » en %d min : le filtre (Amavis) échoue, le courrier entrant est refusé"
            % (log["queue_write_errors"], log.get("window_minutes", 0)))
    if log.get("amavis_trouble"):
        add("amavis-trouble", "critical", "Amavis en erreur : %s" % log["amavis_trouble"][-1][:160])
    svcs = s.get("services") or {}
    dbs = {k: v for k, v in svcs.items() if k in ("mysql", "mariadb", "postgresql")}
    down = [k for k, v in svcs.items() if k not in dbs and v not in ("active", "activating", "disabled")]
    if svcs.get("amavis") == "active" and "spamassassin" in down:
        down.remove("spamassassin")   # #694 : Amavis embarque SpamAssassin, le démon spamd est facultatif
    if dbs and not any(v == "active" for v in dbs.values()):
        down += list(dbs)          # une seule base active suffit (mysql / mariadb : même service selon la version)
    if down:
        add("service-down", "critical", "service(s) arrêté(s) : %s" % ", ".join("%s (%s)" % (k, s["services"][k]) for k in down))
    q = s.get("queue") or {}
    if q.get("count", 0) > 50 or (q.get("oldest_seconds") or 0) > 3600:
        add("queue-backlog", "warning", "file Postfix : %d message(s), le plus ancien depuis %d min" % (q.get("count", 0), (q.get("oldest_seconds") or 0) // 60))
    fps = log.get("false_positive_candidates") or []
    if fps:
        senders = Counter(f["from"] or "<>" for f in fps)
        add("spam-false-positive", "warning", "%d message(s) bloqué(s) comme spam avec un score < %s (faux positifs probables) : %s"
            % (len(fps), log.get("fp_below"), ", ".join("%s ×%d" % kv for kv in senders.most_common(5))))
    bl = local_blacklist_to(s.get("blacklist_to") or [], log.get("local_domains") or [])
    if bl:
        add("blacklist-to", "warning", "blacklist_to sur %s : +10 sur TOUT leur courrier (légitime compris)" % ", ".join(bl[:5]))
    av = s.get("antivirus") or {}
    if av.get("databases") and (s.get("services") or {}).get("clamav-daemon") not in (None, "disabled"):
        if av.get("update_refused") or (av.get("age_days") or 0) > 7:
            add("antivirus-outdated", "warning", "signatures ClamAV âgées de %s jour(s)%s" % (av.get("age_days"), ", mise à jour refusée (version en fin de vie)" if av.get("update_refused") else ""))
    pc = s.get("postconf") or {}
    if pc.get("dnsbl_sites") and pc.get("dnsbl_action") == "ignore":
        add("dnsbl-ignored", "warning", "postscreen consulte des listes noires DNS mais postscreen_dnsbl_action = ignore (aucun blocage)")
    o = s.get("os") or {}
    if o.get("eol"):
        add("os-eol", "warning", "Debian %s hors support depuis %s" % (o["debian"], o["eol"]))
    return a


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--log", default="/var/log/mail.log")
    ap.add_argument("--minutes", type=int, default=60)
    ap.add_argument("--fp-below", type=float, default=8.0)
    ap.add_argument("--ignore-service", action="append", default=[], help="service volontairement arrêté (ex. clamav-daemon)")
    args = ap.parse_args(argv)
    now = time.time()
    lines = tail_lines(args.log)
    s = {"at": int(now), "log_file": args.log, "log": analyse(lines, now, args.minutes, args.fp_below) if lines is not None else {"error": "journal illisible : %s" % args.log},
         "services": services_state(ignore=tuple(args.ignore_service)), "queue": queue_state(now=now), "postconf": postconf_checks(),
         "blacklist_to": blacklist_to_entries(), "antivirus": antivirus_state(now), "os": os_state()}
    s["alerts"] = alerts_from(s)
    sev = {x["severity"] for x in s["alerts"]}
    s["summary"] = {"state": "critical" if "critical" in sev else "warning" if "warning" in sev else "ok",
                    "alerts": len(s["alerts"]), "blocked_spam": (s["log"].get("amavis") or {}).get("Blocked SPAM", 0),
                    "queue": s["queue"].get("count")}
    print(json.dumps(s, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
