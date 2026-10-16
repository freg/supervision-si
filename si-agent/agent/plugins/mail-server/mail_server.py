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
  -- #708 --
  spam-discard-silent warning   spam supprimé sans quarantaine (D_DISCARD sans copie : aucune trace récupérable)
  spam-threshold-low  warning   seuil de suppression (kill level) bas sur un domaine / une boîte (politiques Amavis)
  quarantine-short    warning   quarantaine conservée moins de --quarantine-min-days jours
  log-retention-short warning   journal mail conservé moins de --log-min-days jours (logrotate)
  sender-unauth-blocked warning expéditeur fréquent bloqué, sans DKIM aligné ni SPF « pass » (à prévenir ou à adoucir)

Usage : mail_server.py [--log /var/log/mail.log] [--minutes 60] [--fp-below 8] [--kill-min 5]
                      [--quarantine-min-days 14] [--log-min-days 30]
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
    discarded_silent = 0
    auth = {}                      # #708 : domaine d'enveloppe -> compteurs (messages, bloqués, DKIM aligné, SPF)
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
                act = m.group("action") or ""
                if m.group("verdict") == "Blocked" and "Discarded" in act and "Quarantined" not in act and not QUAR_RE.search(msg):
                    discarded_silent += 1
                ad0 = ADDR_RE.search(msg)
                dom = sender_domain(ad0.group("from")) if ad0 else None
                if dom:
                    a = auth.setdefault(dom, {"messages": 0, "blocked": 0, "dkim_aligned": 0, "spf": Counter()})
                    a["messages"] += 1
                    a["blocked"] += m.group("verdict") == "Blocked"
                    a["dkim_aligned"] += any(aligned(dom, d) for d in dkim_domains(msg))
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
        elif "policyd-spf" in prog or "Received-SPF:" in msg:
            sm = SPF_RE.search(msg)
            if sm:
                dom = sender_domain(sm.group("from"))
                if dom:
                    auth.setdefault(dom, {"messages": 0, "blocked": 0, "dkim_aligned": 0, "spf": Counter()})["spf"][sm.group("res").lower()] += 1
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
            "local_domains": sorted(local_domains), "discarded_without_quarantine": discarded_silent,
            "sender_auth": sender_auth_summary(auth)}


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


SPF_RE = re.compile(r"Received-SPF: (?P<res>\w+)\b.*?envelope-from=<?(?P<from>[^>;\s]+)>?")
DKIM_SD_RE = re.compile(r"dkim_sd=([\w.:,-]+)")


def sender_domain(addr):
    a = (addr or "").strip().lower()
    return a.rsplit("@", 1)[1] if "@" in a and a.rsplit("@", 1)[1] else None


def dkim_domains(msg):
    """Signatures DKIM valides notées par Amavis (`dkim_sd=sélecteur:domaine,…`) -> domaines."""
    m = DKIM_SD_RE.search(msg)
    return [x.split(":", 1)[1].lower() for x in (m.group(1).split(",") if m else []) if ":" in x and x.split(":", 1)[1]]


def aligned(a, b):
    """Alignement « relâché » (DMARC) : même domaine ou l'un sous-domaine de l'autre."""
    return a == b or a.endswith("." + b) or b.endswith("." + a)


def sender_auth_summary(auth, top=25):
    out = []
    for dom, a in auth.items():
        spf = dict(a["spf"])
        out.append({"domain": dom, "messages": a["messages"], "blocked": a["blocked"], "dkim_aligned": a["dkim_aligned"],
                    "spf": spf, "spf_pass": spf.get("pass", 0),
                    "authenticated": a["dkim_aligned"] > 0 or spf.get("pass", 0) > 0})
    out.sort(key=lambda x: (-x["messages"], x["domain"]))
    return out[:top]


AMAVIS_DIRS = ("/etc/amavis/conf.d", "/etc/amavis", "/etc/amavisd")
AMAVIS_VARS = ("final_spam_destiny", "sa_kill_level_deflt", "sa_tag2_level_deflt", "spam_quarantine_method", "spam_quarantine_to")


def amavis_config(dirs=AMAVIS_DIRS):
    """Réglages Amavis utiles (dernière affectation non commentée l'emporte) + connexion SQL (sans jamais la remonter)."""
    vals, dsn = {}, {}
    for d in dirs:
        for f in sorted(glob.glob(os.path.join(d, "*"))):
            if not os.path.isfile(f):
                continue
            try:
                text = open(f, encoding="utf-8", errors="replace").read()
            except OSError:
                continue
            text = "\n".join(l for l in text.splitlines() if not l.lstrip().startswith("#"))
            for m in re.finditer(r"^\s*\$(\w+)\s*=\s*([^;]+);", text, re.M):
                if m.group(1) in AMAVIS_VARS:
                    vals[m.group(1)] = m.group(2).strip().strip("'\"")
            for var in ("storage_sql_dsn", "lookup_sql_dsn"):
                m = re.search(r"@%s\s*=\s*\(\s*\[\s*(['\"])DBI:(?P<drv>\w+):(?P<args>[^'\"]*)\1\s*,\s*(['\"])(?P<user>[^'\"]*)\4\s*,\s*(['\"])(?P<pw>[^'\"]*)\6" % var, text)
                if m and var not in dsn:
                    args = dict(kv.split("=", 1) for kv in m.group("args").split(";") if "=" in kv)
                    dsn[var] = {"driver": m.group("drv").lower(), "database": args.get("database") or args.get("dbname") or "amavis",
                                "host": args.get("host", "localhost"), "port": args.get("port"), "user": m.group("user"), "password": m.group("pw")}
    return vals, dsn.get("storage_sql_dsn") or dsn.get("lookup_sql_dsn")


def mysql_query(dsn, sql, runner=None, timeout=60):
    """mysql -N -B avec identifiants dans un fichier 0600 temporaire (jamais sur la ligne de commande)."""
    import tempfile
    runner = runner or run
    if not dsn or dsn.get("driver") != "mysql":
        return None
    fd, path = tempfile.mkstemp(prefix=".si-agent-my-", suffix=".cnf")
    try:
        os.chmod(path, 0o600)
        with os.fdopen(fd, "w") as fh:
            fh.write("[client]\nuser=%s\npassword=%s\nhost=%s\n%s" % (dsn["user"], dsn["password"], dsn["host"], ("port=%s\n" % dsn["port"]) if dsn.get("port") else ""))
        code, out, _err = runner(["mysql", "--defaults-extra-file=%s" % path, "-N", "-B", dsn["database"], "-e", sql], timeout=timeout)
        return out if code == 0 else None
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


POLICY_SQL = ("SELECT HEX(u.email), u.priority, HEX(IFNULL(p.policy_name,'')), IFNULL(p.spam_tag2_level,''), IFNULL(p.spam_kill_level,''), "
              "HEX(IFNULL(p.spam_quarantine_to,'')), IFNULL(p.bypass_spam_checks,''), IFNULL(p.spam_lover,'') "
              "FROM users u LEFT JOIN policy p ON p.id = u.policy_id ORDER BY u.priority DESC, u.email LIMIT 3000")
RETENTION_SQL = ("SELECT IFNULL(MIN(m.time_num),0), IFNULL(MIN(IF(m.quar_type = 'Q' AND EXISTS (SELECT 1 FROM quarantine q WHERE q.mail_id = m.mail_id), m.time_num, NULL)),0), "
                 "SUM(m.quar_type = 'Q') FROM msgs m")


def _unhex(h):
    try:
        return bytes.fromhex(h).decode("utf-8", "replace")
    except ValueError:
        return h


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def parse_policies(out):
    """Sortie POLICY_SQL -> politiques regroupées : [{policy, tag2, kill, quarantine_to, bypass, lover, domains, mailboxes}]. Pure."""
    groups = {}
    for line in (out or "").splitlines():
        f = line.split("\t")
        if len(f) < 8:
            continue
        email = _unhex(f[0]).lower()
        key = (_unhex(f[2]), f[3], f[4], _unhex(f[5]), f[6], f[7])
        g = groups.setdefault(key, {"policy": key[0], "tag2": _num(f[3]), "kill": _num(f[4]), "quarantine_to": key[3] or None,
                                    "bypass": f[6] == "Y", "lover": f[7] == "Y", "domains": [], "mailboxes": 0})
        if email.startswith("@"):
            g["domains"].append(email)
        else:
            g["mailboxes"] += 1
    return sorted(groups.values(), key=lambda g: (g["kill"] if g["kill"] is not None else 99))


def parse_retention(out, now):
    f = (out or "").strip().split("\t")
    if len(f) < 3:
        return None
    oldest, oldest_q = int(float(f[0] or 0)), int(float(f[1] or 0))
    return {"history_days": round((now - oldest) / 86400, 1) if oldest else None,
            "quarantine_days": round((now - oldest_q) / 86400, 1) if oldest_q else None,
            "quarantined_total": int(float(f[2] or 0)) if f[2] not in ("", "NULL") else 0}


def amavis_state(now=None, runner=None, dirs=AMAVIS_DIRS):
    now = now or time.time()
    vals, dsn = amavis_config(dirs)
    out = {"config": vals, "sql": bool(dsn), "policies": None, "retention": None}
    if dsn:
        out["policies"] = parse_policies(mysql_query(dsn, POLICY_SQL, runner))
        out["retention"] = parse_retention(mysql_query(dsn, RETENTION_SQL, runner, timeout=120), now)
    return out


def logrotate_days(path="/var/log/mail.log", dirs=("/etc/logrotate.d",), main_conf="/etc/logrotate.conf"):
    """Durée de conservation du journal mail selon logrotate (rotate N x période) ; None si inconnue. Pure sur fichiers."""
    period_days = {"daily": 1, "weekly": 7, "monthly": 31, "yearly": 365}

    def scan(text, default_period, default_rotate):
        for m in re.finditer(r"((?:^[^\n{]*\S[^\n{]*\n?)+?)\{(.*?)\}", text, re.M | re.S):
            heads, body = m.group(1).split(), m.group(2)
            if not any(fnmatch.fnmatch(path, h) for h in heads):
                continue
            per = default_period
            for k in period_days:
                if re.search(r"^\s*%s\s*$" % k, body, re.M):
                    per = k
            r = re.search(r"^\s*rotate\s+(\d+)", body, re.M)
            rot = int(r.group(1)) if r else default_rotate
            if rot is not None:
                return rot * period_days[per]
        return None
    try:
        main = open(main_conf, encoding="utf-8", errors="replace").read()
    except OSError:
        main = ""
    dper = next((k for k in period_days if re.search(r"^\s*%s\s*$" % k, main, re.M)), "weekly")
    r = re.search(r"^\s*rotate\s+(\d+)", main, re.M)
    drot = int(r.group(1)) if r else None
    for d in dirs:
        for f in sorted(glob.glob(os.path.join(d, "*"))):
            try:
                v = scan(open(f, encoding="utf-8", errors="replace").read(), dper, drot)
            except OSError:
                continue
            if v is not None:
                return v
    return scan(main, dper, drot)


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
    names = [os.path.basename(f) for f in dbs]
    missing = [b for b in ("main", "daily") if not any(n.startswith(b + ".") for n in names)]   # #770 : base quotidienne absente
    return {"databases": names, "age_days": round((now - newest) / 86400, 1) if newest else None,
            "update_refused": refused, "missing": missing}


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
    avl = s.get("amavis_av")                                        # #770 : Amavis sans antivirus = courrier non analysé
    if avl and not avl.get("loaded"):
        add("antivirus-not-loaded", "critical", "Amavis tourne SANS antivirus (« ANTI-VIRUS code NOT loaded ») : le courrier passe sans analyse virale")
    if av.get("databases") and av.get("missing"):
        add("antivirus-db-missing", "critical", "base(s) ClamAV absente(s) : %s -- clamd ne peut pas démarrer ou ne détecte plus les menaces récentes" % ", ".join(av["missing"]))
    pc = s.get("postconf") or {}
    if pc.get("dnsbl_sites") and pc.get("dnsbl_action") == "ignore":
        add("dnsbl-ignored", "warning", "postscreen consulte des listes noires DNS mais postscreen_dnsbl_action = ignore (aucun blocage)")
    # #708 : politiques antispam, quarantaine, conservation, authentification des expéditeurs
    lim = s.get("limits") or {}
    am = s.get("amavis") or {}
    cfg = am.get("config") or {}
    if log.get("discarded_without_quarantine"):
        add("spam-discard-silent", "warning", "%d spam(s) supprimé(s) sans quarantaine en %d min : aucune trace récupérable en cas de faux positif"
            % (log["discarded_without_quarantine"], log.get("window_minutes", 0)))
    elif cfg.get("final_spam_destiny") == "D_DISCARD" and cfg.get("spam_quarantine_method") in ("undef", ""):
        add("spam-discard-silent", "warning", "final_spam_destiny = D_DISCARD et quarantaine désactivée : le spam est supprimé sans trace")
    kill_min = lim.get("kill_min", 5)
    local = set(log.get("local_domains") or [])
    low = []
    for g in am.get("policies") or []:
        if g.get("kill") is not None and g["kill"] < kill_min and not g.get("lover") and not g.get("bypass"):
            doms = [d for d in g["domains"] if not local or d.lstrip("@") in local or d == "@."] or g["domains"]
            if doms or g["mailboxes"]:
                low.append("%s (%s%s)" % (g["kill"], ", ".join(doms[:3]) or "", (" + %d boîte(s)" % g["mailboxes"]) if g["mailboxes"] else ""))
    dk = _num(cfg.get("sa_kill_level_deflt"))
    if dk is not None and dk < kill_min:
        low.append("%s (valeur par défaut d'Amavis)" % dk)
    if low:
        add("spam-threshold-low", "warning", "seuil de suppression du spam sous %s : %s -- courrier légitime supprimé ou bloqué" % (kill_min, "; ".join(low[:4])))
    ret = am.get("retention") or {}
    qmin = lim.get("quarantine_min_days", 14)
    if ret.get("quarantined_total") and ret.get("history_days") and ret["history_days"] > qmin and (ret.get("quarantine_days") or 0) < qmin:
        add("quarantine-short", "warning", "quarantaine récupérable sur %s jour(s) seulement (historique : %s j) : un faux positif signalé tard est perdu"
            % (ret.get("quarantine_days") or 0, ret["history_days"]))
    lr = s.get("log_retention_days")
    if lr is not None and lr < lim.get("log_min_days", 30):
        add("log-retention-short", "warning", "journal mail conservé %d jour(s) (logrotate) : trop court pour retrouver un message signalé tard" % lr)
    weak = [a for a in log.get("sender_auth") or [] if a["blocked"] >= 2 and not a["authenticated"]]
    if weak:
        add("sender-unauth-blocked", "warning", "expéditeur(s) bloqué(s) sans DKIM aligné ni SPF « pass » : %s -- à prévenir (authentification) ou à adoucir"
            % ", ".join("%s ×%d" % (a["domain"], a["blocked"]) for a in weak[:5]))
    o = s.get("os") or {}
    if o.get("eol"):
        add("os-eol", "warning", "Debian %s hors support depuis %s" % (o["debian"], o["eol"]))
    return a


# ------------------------------------------------------------------ #770 : contrôles et tests fabriqués
# Catalogue extensible depuis le hub (/etc/si-agent/mail-checks.json, écrit par l'action mailctl checks_set) :
#   canary     : boîte de test, expéditeur, fréquence, délai d'attente du verdict
#   tests      : messages fabriqués envoyés à la boîte de test (modèles clean, gtube, eicar, banned, custom),
#                verdict Amavis attendu (« Blocked INFECTED »…) relu dans le journal par leur Message-ID
#   indicators : comptage d'une expression régulière du journal sur une fenêtre, seuils d'alerte
# Le fichier complète les valeurs par défaut (même id = remplacé) ; une entrée invalide est ignorée et signalée.
CHECKS_PATH = "/etc/si-agent/mail-checks.json"
CANARY_STATE = "/var/lib/si-agent/mail-canary.json"
CANARY_FORCE = "/var/lib/si-agent/mail-canary.force"
GTUBE = "XJS*C4JDBQADN1.NSBN3*2IDNEN*GTUBE-STANDARD-ANTI-UBE-TEST-EMAIL*C.34X"
EICAR = "X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"
TEMPLATES = ("clean", "gtube", "eicar", "banned", "custom")
CHECK_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{1,40}$")
EXPECT_RE = re.compile(r"^(Passed|Blocked) [A-Z][A-Z-]{1,30}$")
DEFAULT_CHECKS = {
    "canary": {"to": "", "from": "", "every_hours": 6, "timeout_minutes": 30},
    "tests": [
        {"id": "clean", "label": "Courriel ordinaire accepté", "template": "clean", "expect": ["Passed CLEAN"], "enabled": True},
        {"id": "spam-gtube", "label": "Spam de test (GTUBE) arrêté ou marqué", "template": "gtube", "expect": ["Blocked SPAM", "Passed SPAM"], "enabled": True},
        {"id": "virus-eicar", "label": "Virus de test (EICAR) arrêté", "template": "eicar", "expect": ["Blocked INFECTED"], "enabled": True},
        {"id": "banned-exe", "label": "Pièce jointe interdite (.exe) arrêtée", "template": "banned", "expect": ["Blocked BANNED"], "enabled": False},
    ],
    "indicators": [
        {"id": "auth-failed", "label": "Échecs d'authentification SMTP", "regex": r"SASL \w+ authentication failed", "window_minutes": 60, "warn_above": 300, "crit_above": None, "enabled": True},
        {"id": "bad-header", "label": "Courriels à en-tête non conforme acceptés", "regex": r"Passed BAD-HEADER", "window_minutes": 60, "warn_above": None, "crit_above": None, "enabled": True},
        {"id": "dnsbl-rejects", "label": "Rejets par liste noire DNS", "regex": r"blocked using ", "window_minutes": 60, "warn_above": None, "crit_above": None, "enabled": True},
    ],
}


def _num_or_none(v, lo=0, hi=10 ** 9):
    if v is None or v == "":
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        raise ValueError("nombre attendu : %r" % (v,))
    if not lo <= f <= hi:
        raise ValueError("hors limites : %r" % (v,))
    return int(f) if f == int(f) else f


def validate_test(t):
    """Test du catalogue -> test normalisé (ValueError sinon). Pure."""
    if not isinstance(t, dict) or not CHECK_ID_RE.match(str(t.get("id") or "")):
        raise ValueError("test : id invalide (minuscules, chiffres, - _)")
    if t.get("template") not in TEMPLATES:
        raise ValueError("test %s : modèle inconnu (%s)" % (t["id"], ", ".join(TEMPLATES)))
    exp = t.get("expect") or []
    if isinstance(exp, str):
        exp = [exp]
    if not exp or any(not EXPECT_RE.match(str(e)) for e in exp):
        raise ValueError("test %s : verdict attendu de la forme « Blocked INFECTED », « Passed CLEAN »" % t["id"])
    out = {"id": t["id"], "label": str(t.get("label") or t["id"])[:120], "template": t["template"], "expect": [str(e) for e in exp][:6],
           "enabled": bool(t.get("enabled", True))}
    if t["template"] == "custom":
        out["subject"] = str(t.get("subject") or "test")[:200].replace("\r", " ").replace("\n", " ")
        out["body"] = str(t.get("body") or "")[:20000]
    return out


def validate_indicator(i):
    """Indicateur du catalogue -> indicateur normalisé (ValueError sinon). Pure."""
    if not isinstance(i, dict) or not CHECK_ID_RE.match(str(i.get("id") or "")):
        raise ValueError("indicateur : id invalide (minuscules, chiffres, - _)")
    rx = str(i.get("regex") or "")
    if not rx or len(rx) > 300:
        raise ValueError("indicateur %s : expression régulière vide ou trop longue" % i["id"])
    try:
        re.compile(rx)
    except re.error as e:
        raise ValueError("indicateur %s : expression régulière invalide (%s)" % (i["id"], e))
    return {"id": i["id"], "label": str(i.get("label") or i["id"])[:120], "regex": rx,
            "window_minutes": int(_num_or_none(i.get("window_minutes"), 1, 10080) or 60),
            "warn_above": _num_or_none(i.get("warn_above")), "crit_above": _num_or_none(i.get("crit_above")), "enabled": bool(i.get("enabled", True))}


def merge_checks(custom):
    """Catalogue par défaut + catalogue du hub (même id = remplacé ; « remove » : ids retirés) -> (catalogue, erreurs). Pure."""
    cat = json.loads(json.dumps(DEFAULT_CHECKS))
    errors = []
    custom = custom if isinstance(custom, dict) else {}
    c = custom.get("canary") or {}
    if isinstance(c, dict):
        for k in ("to", "from"):
            v = str(c.get(k) or "").strip()
            if v and not re.match(r"^[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+$", v):
                errors.append("canary.%s : adresse invalide" % k)
            elif v:
                cat["canary"][k] = v
        for k, lo, hi in (("every_hours", 1, 168), ("timeout_minutes", 5, 240)):
            try:
                v = _num_or_none(c.get(k), lo, hi)
                if v is not None:
                    cat["canary"][k] = v
            except ValueError as e:
                errors.append("canary.%s : %s" % (k, e))
    removed = set(custom.get("remove") or [])
    for key, check in (("tests", validate_test), ("indicators", validate_indicator)):
        items = {x["id"]: x for x in cat[key] if x["id"] not in removed}
        for x in custom.get(key) or []:
            try:
                n = check(x)
                items[n["id"]] = n
            except ValueError as e:
                errors.append(str(e))
        cat[key] = list(items.values())
    return cat, errors


def load_checks(path=CHECKS_PATH):
    try:
        with open(path, encoding="utf-8") as fh:
            custom = json.load(fh)
    except FileNotFoundError:
        custom = {}
    except (OSError, ValueError) as e:
        cat, _ = merge_checks({})
        return cat, ["catalogue %s illisible : %s" % (path, e)]
    return merge_checks(custom)


def build_message(test, frm, to, token, host, now):
    """Message fabriqué (texte RFC 5322) -> (message-id, texte). Pure. Jamais de vrai virus : EICAR est un fichier de test inoffensif."""
    mid = "si-canary.%s@%s" % (token, host)
    date = time.strftime("%a, %d %b %Y %H:%M:%S +0000", time.gmtime(now))
    head = ["From: Sonde si-agent <%s>" % frm, "To: <%s>" % to, "Date: %s" % date, "Message-ID: <%s>" % mid,
            "Subject: [si-agent test %s] %s" % (token, test.get("subject") if test["template"] == "custom" else test["label"]),
            "X-SI-Agent-Test: %s" % test["id"], "MIME-Version: 1.0"]
    intro = "Message de test fabriqué par la sonde mail-server du hub (test « %s »). Il peut être supprimé." % test["label"]
    tpl = test["template"]
    if tpl in ("eicar", "banned"):
        b = "si-canary-%s" % token
        name, data = ("eicar-test.txt", EICAR.encode()) if tpl == "eicar" else ("facture-test.exe", b"MZ test si-agent, fichier inoffensif")
        import base64
        body = ["Content-Type: multipart/mixed; boundary=\"%s\"" % b, "", "--%s" % b, "Content-Type: text/plain; charset=utf-8", "", intro, "",
                "--%s" % b, "Content-Type: application/octet-stream; name=\"%s\"" % name, "Content-Disposition: attachment; filename=\"%s\"" % name,
                "Content-Transfer-Encoding: base64", "", base64.b64encode(data).decode(), "", "--%s--" % b, ""]
    else:
        text = {"clean": intro, "gtube": intro + "\n\n" + GTUBE, "custom": test.get("body") or intro}[tpl]
        body = ["Content-Type: text/plain; charset=utf-8", "Content-Transfer-Encoding: 8bit", "", text, ""]
    return mid, "\r\n".join(head + body)


def canary_due(state, canary, now, force=False):
    """Faut-il envoyer une nouvelle série de tests ? Pure."""
    if not canary.get("to"):
        return False
    if force:
        return True
    if any(p for p in state.get("pending") or []):
        return False
    return now - (state.get("last_run") or 0) >= canary.get("every_hours", 6) * 3600


FILTER_REPLY_RE = re.compile(r"status=sent \((?P<reply>250 [^)]*)\)")


def filter_verdict(reply):
    """Réponse SMTP d'Amavis vue par le Postfix émetteur (filtre local ou VM de filtrage distante) -> verdict. Pure.
    « 250 2.7.0 Ok, discarded, id=… - INFECTED: Eicar… » -> Blocked INFECTED ; « … - spam » -> Blocked SPAM ;
    « … - BANNED: … » -> Blocked BANNED ; « 250 2.0.0 from MTA(…): 250 2.0.0 Ok: queued as … » -> Passed (catégorie inconnue)."""
    r = reply or ""
    if "discarded" in r or "rejected" in r or "2.7.0" in r:
        for key, cat in (("INFECTED", "INFECTED"), ("BANNED", "BANNED"), ("spam", "SPAM"), ("SPAM", "SPAM"), ("BAD-HEADER", "BAD-HEADER")):
            if key in r:
                return "Blocked %s" % cat
        return "Blocked"
    if "from MTA" in r or "queued as" in r:
        return "Passed"
    return None


def verdict_ok(verdict, expect):
    """« Passed » seul (filtre distant : catégorie inconnue) satisfait tout « Passed X » attendu. Pure."""
    if verdict in expect:
        return True
    return verdict in ("Passed", "Blocked") and any(e.split(" ")[0] == verdict for e in expect)


def correlate(pending, lines, now, timeout_minutes):
    """Tests envoyés + journal -> (résultats rendus, tests encore en attente). Pure.
    Verdict : ligne Amavis portant le Message-ID du test (filtre local) ; sinon réponse du filtre au Postfix émetteur,
    retrouvée par le n° de file Postfix (filtre sur une VM spécialisée) ; rejet sans verdict ou délai dépassé = échec."""
    by_mid = {p["message_id"]: p for p in pending}
    found, qids = {}, {}
    for line in lines or []:
        if "si-canary." in line:
            for mid in by_mid:
                if mid in line:
                    v = VERDICT_RE.search(line)
                    if v:
                        found[mid] = ("verdict", "%s %s" % (v.group("verdict"), v.group("cat")), line[:240])
                    elif "message-id=" in line:
                        q = re.search(r": ([0-9A-Za-z]{6,20}): message-id=", line)
                        if q:
                            qids[q.group(1)] = mid
                    elif ("reject" in line or "bounced" in line) and mid not in found:
                        found[mid] = ("rejected", None, line[:240])
        elif qids and "status=" in line:
            q = re.search(r": ([0-9A-Za-z]{6,20}): to=", line)
            mid = qids.get(q.group(1)) if q else None
            if mid and found.get(mid, ("",))[0] != "verdict":
                fr = FILTER_REPLY_RE.search(line)
                v = filter_verdict(fr.group("reply")) if fr else None
                if v:
                    found[mid] = ("verdict", v, line[:240])
                elif "status=bounced" in line or "status=deferred" in line:
                    found.setdefault(mid, ("rejected", None, line[:240]))
    done, still = [], []
    for p in pending:
        f = found.get(p["message_id"])
        r = {"test_id": p["test_id"], "sent_at": p["sent_at"], "at": int(now), "expect": p["expect"], "message_id": p["message_id"]}
        if p.get("send_error"):
            done.append(dict(r, ok=False, verdict=None, detail="envoi impossible : %s" % p["send_error"]))
        elif f and f[0] == "verdict":
            ok = verdict_ok(f[1], p["expect"])
            done.append(dict(r, ok=ok, verdict=f[1], detail=None if ok else "verdict obtenu : %s, attendu : %s" % (f[1], " ou ".join(p["expect"]))))
        elif f and now - p["sent_at"] > 120:
            done.append(dict(r, ok=False, verdict=None, detail="rejeté ou différé avant analyse : %s" % f[2][-160:]))
        elif now - p["sent_at"] > timeout_minutes * 60:
            done.append(dict(r, ok=False, verdict=None, detail="aucun verdict du filtre après %d min (filtre arrêté, file bloquée ou journal incomplet)" % timeout_minutes))
        else:
            still.append(p)
    return done, still


def eval_indicators(lines, now, indicators):
    """Journal -> valeur et état de chaque indicateur actif. Pure."""
    out = []
    for ind in indicators:
        if not ind.get("enabled", True):
            continue
        rx = re.compile(ind["regex"])
        since = now - ind["window_minutes"] * 60
        n = 0
        for line in lines or []:
            if rx.search(line):
                p = parse_time(line, now)
                if p and p[0] >= since:
                    n += 1
        state = "critical" if ind.get("crit_above") is not None and n > ind["crit_above"] else \
            "warning" if ind.get("warn_above") is not None and n > ind["warn_above"] else "ok"
        out.append({"id": ind["id"], "label": ind["label"], "value": n, "window_minutes": ind["window_minutes"],
                    "warn_above": ind.get("warn_above"), "crit_above": ind.get("crit_above"), "state": state})
    return out


def send_mail(msg, frm, to, timeout=60):
    try:
        p = subprocess.run(["/usr/sbin/sendmail", "-i", "-f", frm, to], input=msg.encode("utf-8"), stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE, timeout=timeout)
        return None if p.returncode == 0 else (p.stderr.decode("utf-8", "replace").strip() or "code %d" % p.returncode)[:200]
    except (OSError, subprocess.TimeoutExpired) as e:
        return str(e)[:200]


def run_checks(lines, now, checks, state, force=False, sender=send_mail, host=None):
    """Un passage : relève les tests en attente, envoie une nouvelle série si elle est due, évalue les indicateurs.
    -> (bloc « checks » du relevé, nouvel état). Les envois passent par `sender` (tests : simulé)."""
    c = checks["canary"]
    state = dict(state or {})
    done, pending = correlate(state.get("pending") or [], lines, now, c.get("timeout_minutes", 30))
    hist = state.get("results") or {}
    for r in done:
        hist.setdefault(r["test_id"], []).append(r)
        hist[r["test_id"]] = hist[r["test_id"]][-30:]
    sent = []
    if canary_due(dict(state, pending=pending), c, now, force):
        frm = c.get("from") or c["to"]
        host = host or (os.uname()[1] if hasattr(os, "uname") else "localhost")
        for t in checks["tests"]:
            if not t.get("enabled", True):
                continue
            token = "%s-%s-%d" % (t["id"], hex(int(now))[2:], len(sent))
            mid, msg = build_message(t, frm, c["to"], token, host, now)
            err = sender(msg, frm, c["to"])
            p = {"test_id": t["id"], "message_id": mid, "sent_at": int(now), "expect": t["expect"], "send_error": err}
            pending.append(p)
            sent.append(t["id"])
        state["last_run"] = int(now)
    state["pending"], state["results"] = pending, hist
    tests = []
    for t in checks["tests"]:
        h = hist.get(t["id"]) or []
        tests.append({"id": t["id"], "label": t["label"], "template": t["template"], "expect": t["expect"], "enabled": t.get("enabled", True),
                      "last": h[-1] if h else None, "history": [{"at": x["at"], "ok": x["ok"], "verdict": x.get("verdict")} for x in h[-14:]],
                      "pending": any(p["test_id"] == t["id"] for p in pending)})
    block = {"canary": {"to": c.get("to") or None, "every_hours": c.get("every_hours"), "timeout_minutes": c.get("timeout_minutes"),
                        "last_run": state.get("last_run"), "next_run": (state.get("last_run") or now) + c.get("every_hours", 6) * 3600 if c.get("to") else None,
                        "sent_now": sent},
             "tests": tests, "indicators": eval_indicators(lines, now, checks["indicators"])}
    return block, state


def checks_alerts(block):
    """Bloc « checks » -> constats (test-failed:<id>, indicator:<id>). Pure."""
    a = []
    for t in block.get("tests") or []:
        last = t.get("last")
        if t.get("enabled") and last and not last.get("ok"):
            sev = "critical" if any(e.startswith("Blocked") for e in t["expect"]) and (last.get("verdict") or "").startswith("Passed") else "warning"
            a.append({"code": "test-failed:%s" % t["id"], "severity": sev, "message": "test « %s » en échec : %s" % (t["label"], last.get("detail") or "?")})
    for i in block.get("indicators") or []:
        if i["state"] != "ok":
            a.append({"code": "indicator:%s" % i["id"], "severity": i["state"],
                      "message": "%s : %d en %d min (seuil %s)" % (i["label"], i["value"], i["window_minutes"], i["crit_above"] if i["state"] == "critical" else i["warn_above"])})
    if block.get("errors"):
        a.append({"code": "checks-invalid", "severity": "warning", "message": "catalogue de contrôles : %s" % "; ".join(block["errors"][:3])})
    return a


def amavis_av_loaded(lines):
    """Dernier démarrage d'Amavis : antivirus chargé ? -> {loaded, at} (None si aucun démarrage dans le journal lu). Pure."""
    for line in reversed(lines or []):
        if "ANTI-VIRUS code" in line:
            return {"loaded": "NOT loaded" not in line, "line": line[:160]}
    return None


def read_json(path, default):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return default


def write_json(path, data):
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path + ".tmp", "w", encoding="utf-8") as fh:
            json.dump(data, fh)
        os.replace(path + ".tmp", path)
    except OSError:
        pass


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--log", default="/var/log/mail.log")
    ap.add_argument("--minutes", type=int, default=60)
    ap.add_argument("--fp-below", type=float, default=8.0)
    ap.add_argument("--ignore-service", action="append", default=[], help="service volontairement arrêté (ex. clamav-daemon)")
    ap.add_argument("--kill-min", type=float, default=5.0, help="seuil de suppression minimal attendu")
    ap.add_argument("--quarantine-min-days", type=int, default=14)
    ap.add_argument("--log-min-days", type=int, default=30)
    ap.add_argument("--checks", default=CHECKS_PATH, help="#770 : catalogue des contrôles et tests (écrit depuis le hub)")
    ap.add_argument("--canary-state", default=CANARY_STATE)
    ap.add_argument("--no-canary", action="store_true", help="ne jamais envoyer de message de test")
    args = ap.parse_args(argv)
    now = time.time()
    lines = tail_lines(args.log)
    s = {"at": int(now), "log_file": args.log, "log": analyse(lines, now, args.minutes, args.fp_below) if lines is not None else {"error": "journal illisible : %s" % args.log},
         "services": services_state(ignore=tuple(args.ignore_service)), "queue": queue_state(now=now), "postconf": postconf_checks(),
         "blacklist_to": blacklist_to_entries(), "antivirus": antivirus_state(now), "os": os_state(),
         "amavis": amavis_state(now), "log_retention_days": logrotate_days(args.log),
         "limits": {"kill_min": args.kill_min, "quarantine_min_days": args.quarantine_min_days, "log_min_days": args.log_min_days}}
    s["amavis_av"] = amavis_av_loaded(lines)
    # #770 : contrôles et tests fabriqués (catalogue modifiable depuis le hub)
    checks, errors = load_checks(args.checks)
    if args.no_canary:
        checks["canary"]["to"] = ""
    force = os.path.exists(CANARY_FORCE)
    block, st = run_checks(lines, now, checks, read_json(args.canary_state, {}), force=force)
    if force:
        try:
            os.remove(CANARY_FORCE)
        except OSError:
            pass
    write_json(args.canary_state, st)
    block["errors"], block["catalog"] = errors, checks
    s["checks"] = block
    s["alerts"] = alerts_from(s) + checks_alerts(block)
    sev = {x["severity"] for x in s["alerts"]}
    s["summary"] = {"state": "critical" if "critical" in sev else "warning" if "warning" in sev else "ok",
                    "alerts": len(s["alerts"]), "blocked_spam": (s["log"].get("amavis") or {}).get("Blocked SPAM", 0),
                    "queue": s["queue"].get("count")}
    print(json.dumps(s, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
