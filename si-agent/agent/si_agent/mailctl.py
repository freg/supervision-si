# -*- coding: utf-8 -*-
"""Serveur de messagerie -- recherche et consultation depuis le hub
(livraison #697, tuile « Serveur de messagerie »). Commande du central
`mail` {action, ...} exécutée en root sur l'hôte Postfix / Amavis / Dovecot :

  log_tree          journal des N dernières minutes en arbre : programme →
                    évènement → lignes (feuilles)
  log_search        historique de traitement regroupé par message (n° de file
                    Postfix, mail_id Amavis, rejets NOQUEUE) ; filtres
                    expéditeur / destinataire / n° / Message-ID / état
  quarantine_search quarantaine SQL d'Amavis (Modoboa) ; expéditeur,
                    destinataire, sujet, type, période
  quarantine_get    message mis en quarantaine (source brute)          [motif]
  quarantine_release  libération (amavisd-release)                      [motif]
  mailbox_search    toutes les boîtes (doveadm, -A ou -u motif) ; de, à,
                    sujet, corps, plein texte, période, dossier
  mailbox_get       message d'une boîte (source brute)                  [motif]

Jokers `*` et `?` partout (insensibles à la casse). Secret des
correspondances : consulter un contenu ou libérer exige un `reason` ; chaque
action (recherches comprises) est journalisée sur l'hôte, avec l'acteur et
le motif, dans /var/log/si-agent/mail-audit.log. Les identifiants SQL
d'Amavis sont lus dans sa configuration et passés à `mysql` par un fichier
temporaire 0600 -- jamais renvoyés au central ; le secret_id d'un message
n'est lu qu'au moment de la libération.
"""
import fnmatch
import glob
import gzip
import json
import os
import re
import subprocess
import tempfile
import time
from datetime import datetime

AUDIT_LOG = "/var/log/si-agent/mail-audit.log"
AMAVIS_CONF = ("/etc/amavis/conf.d", "/etc/amavis", "/etc/amavisd")
MAX_RAW = 3 * 1024 * 1024
MAX_LIMIT = 300
CONTENT_ACTIONS = ("quarantine_get", "quarantine_release", "mailbox_get")

MONTHS = {m: i for i, m in enumerate(["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], 1)}
SYSLOG_RE = re.compile(r"^(?P<mon>[A-Z][a-z]{2}) +(?P<day>\d{1,2}) (?P<hms>\d\d:\d\d:\d\d) \S+ (?P<prog>[\w/.-]+)(?:\[\d+\])?: (?P<msg>.*)$")
ISO_RE = re.compile(r"^(?P<iso>\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d)\S* \S+ (?P<prog>[\w/.-]+)(?:\[\d+\])?: (?P<msg>.*)$")
QID_RE = re.compile(r"^(?P<q>[0-9A-F]{6,12}|[0-9B-DF-HJ-NP-TV-Zb-df-hj-np-tv-z]{11,20}): (?P<rest>.*)$")
QUEUED_AS_RE = re.compile(r"queued as (?P<q>[0-9A-Za-z]{6,20})")
AMAVIS_RE = re.compile(r"\((?P<am>[\d-]+)\) (?P<verdict>Passed|Blocked) (?P<cat>[A-Z-]+)(?: \{(?P<action>[^}]*)\})?,.*?<(?P<from>[^>]*)> -> (?P<to>(?:<[^>]*>,?)+)")
MAIL_ID_RE = re.compile(r"mail_id: (?P<id>[\w+-]+)")
QAS_RE = re.compile(r"queued_as: (?P<q>[\w]+)")
HITS_RE = re.compile(r"Hits: (?P<h>-?[\d.]+)")
QUAR_RE = re.compile(r"quarantine: (?P<q>[^,\s]+)")
MSGID_RE = re.compile(r"[Mm]essage-I[Dd]: ?<(?P<m>[^>]*)>|message-id=<(?P<m2>[^>]*)>")
FROM_RE = re.compile(r"from=<(?P<f>[^>]*)>")
TO_RE = re.compile(r"to=<(?P<t>[^>]*)>")
STATUS_RE = re.compile(r"status=(?P<s>\w+)")
CLIENT_RE = re.compile(r"client=(?P<c>\S+)")
SIZE_RE = re.compile(r"size=(?P<s>\d+)")
MAIL_ID_OK = re.compile(r"^[A-Za-z0-9+_-]{6,24}$")
GUID_OK = re.compile(r"^[0-9a-f]{32}$")
USER_OK = re.compile(r"^[^\s*?/]{1,200}$")


# ------------------------------------------------------------------ outils

def run(argv, timeout=120, stdin=None):
    try:
        p = subprocess.run(argv, input=stdin, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
        return p.returncode, p.stdout.decode("utf-8", "replace"), p.stderr.decode("utf-8", "replace")
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 127, "", str(exc)


def wild(value):
    """Motif utilisateur -> motif fnmatch en minuscules ; sans joker = « contient »."""
    v = str(value or "").strip().lower()
    if not v:
        return None
    return v if ("*" in v or "?" in v) else "*%s*" % v


def match(pattern, *values):
    """Vrai si un des `values` correspond au motif (None = pas de filtre)."""
    if pattern is None:
        return True
    return any(fnmatch.fnmatchcase((v or "").lower(), pattern) for v in values)


def longest_literal(value):
    """« *credit*agricole » -> « agricole » : ce qu'un moteur sans joker peut chercher."""
    parts = [p for p in re.split(r"[*?]+", str(value or "")) if p.strip()]
    return max(parts, key=len).strip() if parts else ""


def parse_time(line, now):
    m = SYSLOG_RE.match(line)
    if m:
        d = datetime.fromtimestamp(now)
        try:
            t = datetime(d.year, MONTHS[m.group("mon")], int(m.group("day")), *[int(x) for x in m.group("hms").split(":")])
        except (KeyError, ValueError):
            return None
        ts = t.timestamp()
        if ts > now + 86400:                 # journal de décembre lu en janvier
            ts = t.replace(year=d.year - 1).timestamp()
        return ts, m.group("prog"), m.group("msg")
    m = ISO_RE.match(line)
    if m:
        try:
            return datetime.strptime(m.group("iso"), "%Y-%m-%dT%H:%M:%S").timestamp(), m.group("prog"), m.group("msg")
        except ValueError:
            return None
    return None


def read_logs(path, since, now, max_bytes=300 * 1024 * 1024):
    """Lignes du journal depuis `since` : fichier courant + rotations (.1, .2.gz ...) tant qu'elles couvrent la période."""
    files = [path] + sorted(glob.glob(path + ".[0-9]*"), key=lambda p: int(re.search(r"\.(\d+)", p[len(path):]).group(1)))
    chunks, total = [], 0
    for f in files:
        try:
            if os.path.getmtime(f) < since and f != path:
                break
            opener = gzip.open if f.endswith(".gz") else open
            with opener(f, "rb") as fh:
                data = fh.read(max_bytes - total)
        except OSError:
            continue
        total += len(data)
        chunks.append(data.decode("utf-8", "replace").splitlines())
        if total >= max_bytes:
            break
    lines = []
    for c in reversed(chunks):               # du plus ancien au plus récent
        lines.extend(c)
    return lines


# ------------------------------------------------------------------ journal en arbre

def classify(prog, msg):
    """(branche, sous-branche) d'une ligne du journal."""
    p = prog.split("/")[-1] if "/" in prog else prog
    if prog.startswith("amavis"):
        m = re.search(r"\) (Passed|Blocked) ([A-Z-]+)", msg)
        if m:
            return "amavis", "%s %s" % (m.group(1), m.group(2))
        if re.search(r"TROUBLE|FAILED|Can't connect|timed out|DBI|error", msg, re.I):
            return "amavis", "erreurs"
        return "amavis", "autres"
    if p == "postscreen":
        for k in ("PASS NEW", "PASS OLD", "DNSBL", "PREGREET", "HANGUP", "COMMAND", "NOQUEUE", "CONNECT", "DISCONNECT", "WHITELISTED"):
            if k in msg:
                return "postscreen", k
        return "postscreen", "autres"
    if p == "smtpd" or p == "submission" or p.startswith("smtps"):
        for k, label in (("NOQUEUE: reject", "refus"), ("proxy-reject", "refus du filtre"), ("proxy-accept", "accepté par le filtre"),
                         ("warning", "avertissements"), ("SASL", "authentification"), ("connect from", "connexions"),
                         ("disconnect from", "déconnexions"), ("lost connection", "connexions perdues"), ("client=", "messages reçus")):
            if k in msg:
                return "smtpd", label
        return "smtpd", "autres"
    if p in ("lmtp", "smtp", "virtual", "local", "pipe", "relay", "error", "discard"):
        st = STATUS_RE.search(msg)
        return "remise (%s)" % p, ("status=%s" % st.group(1)) if st else "autres"
    if p in ("qmgr", "cleanup", "bounce", "pickup", "postqueue", "postsuper", "anvil", "scache", "tlsmgr", "master", "trivial-rewrite"):
        if "removed" in msg:
            return p, "retirés de la file"
        if "warning" in msg or "fatal" in msg or "error" in msg:
            return p, "avertissements"
        return p, "évènements"
    if prog.startswith("dovecot") or prog.startswith("imap") or prog.startswith("pop3"):
        if "Login:" in msg:
            return "dovecot", "connexions"
        if "auth failed" in msg or "Authentication failure" in msg or "auth-worker" in msg and "failed" in msg:
            return "dovecot", "échecs d'authentification"
        if "Error" in msg or "Panic" in msg or "Fatal" in msg:
            return "dovecot", "erreurs"
        if "Disconnected" in msg or "Logged out" in msg:
            return "dovecot", "déconnexions"
        return "dovecot", "autres"
    if prog.startswith("clamd") or prog.startswith("freshclam"):
        return "clamav", "évènements"
    if prog.startswith("opendkim") or prog.startswith("opendmarc"):
        return prog.split("[")[0], "évènements"
    return prog, "autres"


def log_tree(lines, now, minutes=60, per_leaf=200, total=4000):
    """Lignes -> {branche: {sous-branche: {count, lines:[{at, line}]}}} (récentes en dernier). Pure."""
    since = now - minutes * 60
    tree, kept = {}, 0
    for line in lines or []:
        p = parse_time(line, now)
        if not p or p[0] < since:
            continue
        b, s = classify(p[1], p[2])
        leaf = tree.setdefault(b, {}).setdefault(s, {"count": 0, "lines": []})
        leaf["count"] += 1
        leaf["lines"].append({"at": int(p[0]), "line": line[:1000]})
        if len(leaf["lines"]) > per_leaf:
            leaf["lines"].pop(0)
        kept += 1
    # borne globale : les feuilles les plus fournies d'abord tronquées
    while sum(len(l["lines"]) for b in tree.values() for l in b.values()) > total:
        biggest = max((l for b in tree.values() for l in b.values()), key=lambda l: len(l["lines"]))
        del biggest["lines"][:max(1, len(biggest["lines"]) // 4)]
    return {"minutes": minutes, "lines": kept, "tree": tree}


# ------------------------------------------------------------------ historique par message

def log_messages(lines, now, hours=24):
    """Regroupe le journal par message. Clé : n° de file Postfix ; un message
    passé par Amavis (filtre avant file) est rattaché par « queued as » ; un
    refus NOQUEUE ou un blocage Amavis sans file forment leur propre entrée. Pure."""
    since = now - hours * 3600
    msgs, alias, order = {}, {}, []

    def get(key):
        key = alias.get(key, key)
        if key not in msgs:
            msgs[key] = {"key": key, "queue_ids": [], "from": None, "to": [], "message_id": None, "client": None, "size": None,
                         "first": None, "last": None, "states": [], "amavis": None, "lines": []}
            order.append(key)
        return msgs[key]

    def touch(m, ts, line, prog):
        m["first"] = m["first"] or int(ts)
        m["last"] = int(ts)
        if len(m["lines"]) < 60:
            m["lines"].append({"at": int(ts), "prog": prog, "line": line[:800]})

    n_noqueue = 0
    for line in lines or []:
        p = parse_time(line, now)
        if not p or p[0] < since:
            continue
        ts, prog, msg = p
        if prog.startswith("amavis"):
            am = AMAVIS_RE.search(msg)
            if not am:
                continue
            q = QAS_RE.search(msg)
            mid = MAIL_ID_RE.search(msg)
            key = q.group("q") if q else "amavis-%s" % (mid.group("id") if mid else am.group("am"))
            m = get(key)
            hits = HITS_RE.search(msg)
            quar = QUAR_RE.search(msg)
            m["amavis"] = {"verdict": "%s %s" % (am.group("verdict"), am.group("cat")), "action": am.group("action"),
                           "hits": float(hits.group("h")) if hits else None, "mail_id": mid.group("id") if mid else None,
                           "quarantine": quar.group("q") if quar else None}
            m["from"] = m["from"] or am.group("from")
            for t in re.findall(r"<([^>]*)>", am.group("to")):
                if t not in m["to"]:
                    m["to"].append(t)
            mm = MSGID_RE.search(msg)
            if mm:
                m["message_id"] = m["message_id"] or (mm.group("m") or mm.group("m2"))
            if am.group("verdict") == "Blocked":
                m["states"].append("bloqué (%s)" % am.group("cat"))
            touch(m, ts, line, prog)
            continue
        qm = QID_RE.match(msg)
        if qm:
            q, rest = qm.group("q"), qm.group("rest")
            m = get(q)
            if q not in m["queue_ids"]:
                m["queue_ids"].append(q)
            for rx, field in ((FROM_RE, "from"), (CLIENT_RE, "client")):
                x = rx.search(rest)
                if x and not m[field]:
                    m[field] = x.group(1)
            x = SIZE_RE.search(rest)
            if x and m["size"] is None:
                m["size"] = int(x.group("s"))
            x = MSGID_RE.search(rest)
            if x:
                m["message_id"] = m["message_id"] or (x.group("m") or x.group("m2"))
            st = STATUS_RE.search(rest)
            if st:
                t = TO_RE.search(rest)
                if t and t.group("t") not in m["to"]:
                    m["to"].append(t.group("t"))
                m["states"].append(st.group("s"))
            elif "removed" == rest.strip():
                m["states"].append("retiré de la file")
            touch(m, ts, line, prog)
            continue
        if "NOQUEUE:" in msg:
            qa = QUEUED_AS_RE.search(msg)
            if qa:                                   # proxy-accept : rattaché au message réinjecté
                m = get(qa.group("q"))
            else:
                n_noqueue += 1
                m = get("noqueue-%d" % n_noqueue)
                code = re.search(r": (\d{3} \d\.\d\.\d) ", msg)
                m["states"].append("refusé %s" % (code.group(1) if code else ""))
            f, t = FROM_RE.search(msg), TO_RE.search(msg)
            if f and not m["from"]:
                m["from"] = f.group("f")
            if t and t.group("t") not in m["to"]:
                m["to"].append(t.group("t"))
            touch(m, ts, line, prog)
    return [msgs[k] for k in order]


def filter_messages(items, params):
    pf, pt = wild(params.get("from")), wild(params.get("to"))
    pq, pmid, pst = (params.get("queue_id") or "").strip(), wild(params.get("message_id")), wild(params.get("status"))
    out = []
    for m in items:
        if not match(pf, m["from"]) or not match(pt, *(m["to"] or [""])):
            continue
        if pq and pq not in m["queue_ids"] and pq != (m["amavis"] or {}).get("mail_id") and pq != m["key"]:
            continue
        if pmid is not None and not match(pmid, m["message_id"]):
            continue
        if pst is not None and not match(pst, *(m["states"] + [(m["amavis"] or {}).get("verdict") or ""])):
            continue
        out.append(m)
    out.sort(key=lambda m: -(m["last"] or 0))
    return out


# ------------------------------------------------------------------ quarantaine SQL d'Amavis

def amavis_dsn(dirs=AMAVIS_CONF):
    """Configuration Amavis -> {driver, database, host, port, user, password} ; @storage_sql_dsn d'abord."""
    found = {}
    for d in dirs:
        for f in sorted(glob.glob(os.path.join(d, "*"))):
            if not os.path.isfile(f):
                continue
            try:
                text = open(f, encoding="utf-8", errors="replace").read()
            except OSError:
                continue
            text = "\n".join(l for l in text.splitlines() if not l.lstrip().startswith("#"))
            for var in ("storage_sql_dsn", "lookup_sql_dsn"):
                m = re.search(r"@%s\s*=\s*\(\s*\[\s*(['\"])DBI:(?P<drv>\w+):(?P<args>[^'\"]*)\1\s*,\s*(['\"])(?P<user>[^'\"]*)\4\s*,\s*(['\"])(?P<pw>[^'\"]*)\6" % var, text)
                if m:
                    args = dict(kv.split("=", 1) for kv in m.group("args").split(";") if "=" in kv)
                    found.setdefault(var, {"driver": m.group("drv").lower(), "database": args.get("database") or args.get("dbname"),
                                           "host": args.get("host", "localhost"), "port": args.get("port"), "user": m.group("user"),
                                           "password": m.group("pw")})
    return found.get("storage_sql_dsn") or found.get("lookup_sql_dsn")


def lit(s):
    """Littéral SQL sans échappement possible à contourner : X'…' (octets UTF-8)."""
    return "X'%s'" % str(s).encode("utf-8").hex()


def like_pattern(value):
    """Motif utilisateur -> motif LIKE (jokers * ? -> % _, le reste échappé)."""
    raw = str(value or "").strip()
    v = raw.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    v = v.replace("*", "%").replace("?", "_")
    return v if ("*" in raw or "?" in raw) else "%" + v + "%"


def like(col, value):
    return "LOWER(CONVERT(%s USING utf8)) LIKE LOWER(CONVERT(%s USING utf8))" % (col, lit(like_pattern(value)))


def quarantine_sql(params, now):
    days = max(1, min(365, int(params.get("days") or 30)))
    limit = max(1, min(MAX_LIMIT, int(params.get("limit") or 100)))
    where = ["m.time_num >= %d" % int(now - days * 86400)]
    if params.get("only_quarantined", True):
        where.append("m.quar_type = 'Q'")
    if params.get("from"):
        where.append(like("s.email", params["from"]))
    if params.get("to"):
        where.append(like("r.email", params["to"]))
    if params.get("subject"):
        where.append(like("m.subject", params["subject"]))
    if params.get("content") and re.match(r"^[A-Za-z]$", str(params["content"])):
        where.append("m.content = %s" % lit(params["content"]))
    if params.get("min_score") not in (None, ""):
        where.append("m.spam_level >= %f" % float(params["min_score"]))
    if params.get("max_score") not in (None, ""):
        where.append("m.spam_level < %f" % float(params["max_score"]))
    cols = ["HEX(m.mail_id)", "m.time_num", "HEX(IFNULL(m.content,''))", "HEX(IFNULL(m.quar_type,''))", "IFNULL(m.spam_level,'')", "IFNULL(m.size,0)",
            "HEX(IFNULL(s.email,''))", "HEX(IFNULL(m.subject,''))", "HEX(IFNULL(GROUP_CONCAT(DISTINCT r.email SEPARATOR ','),''))",
            "HEX(IFNULL(m.client_addr,''))", "HEX(IFNULL(m.message_id,''))"]
    return ("SELECT %s FROM msgs m LEFT JOIN maddr s ON s.id = m.sid LEFT JOIN msgrcpt mr ON mr.mail_id = m.mail_id "
            "LEFT JOIN maddr r ON r.id = mr.rid WHERE %s GROUP BY m.mail_id ORDER BY m.time_num DESC LIMIT %d") % (", ".join(cols), " AND ".join(where), limit)


def _unhex(h):
    try:
        return bytes.fromhex(h).decode("utf-8", "replace")
    except ValueError:
        return h


CONTENT = {"S": "spam", "V": "virus", "B": "pièce jointe interdite", "H": "en-tête invalide", "Y": "spam (sous le seuil de blocage)",
           "C": "propre", "O": "trop gros", "U": "non vérifié", "T": "échec du filtre", "M": "MIME invalide"}


def parse_quarantine_rows(out):
    rows = []
    for line in (out or "").splitlines():
        f = line.split("\t")
        if len(f) < 11:
            continue
        content = _unhex(f[2])
        rows.append({"mail_id": _unhex(f[0]), "at": int(float(f[1] or 0)), "content": content, "content_label": CONTENT.get(content.upper(), content),
                     "quarantined": _unhex(f[3]) == "Q", "score": float(f[4]) if f[4] not in ("", "NULL") else None, "size": int(float(f[5] or 0)),
                     "from": _unhex(f[6]), "subject": _unhex(f[7]), "to": [x for x in _unhex(f[8]).split(",") if x],
                     "client": _unhex(f[9]), "message_id": _unhex(f[10]).strip("<>")})
    return rows


def mysql(dsn, sql, runner=run, timeout=120):
    """`mysql` avec un fichier d'identifiants temporaire 0600 (jamais sur la ligne de commande). -> (code, out, err)."""
    if not dsn:
        return 2, "", "connexion SQL d'Amavis introuvable (@storage_sql_dsn / @lookup_sql_dsn)"
    if dsn["driver"] != "mysql":
        return 2, "", "base %s non prise en charge (MySQL / MariaDB seulement)" % dsn["driver"]
    fd, path = tempfile.mkstemp(prefix=".si-agent-my-", suffix=".cnf")
    try:
        os.chmod(path, 0o600)
        with os.fdopen(fd, "w") as fh:
            fh.write("[client]\nuser=%s\npassword=%s\nhost=%s\n%s" % (dsn["user"], dsn["password"], dsn["host"],
                                                                     ("port=%s\n" % dsn["port"]) if dsn.get("port") else ""))
        return runner(["mysql", "--defaults-extra-file=%s" % path, "-N", "-B", dsn["database"] or "amavis", "-e", sql], timeout=timeout)
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


# ------------------------------------------------------------------ boîtes (Dovecot)

FETCH_FIELDS = ["mailbox", "mailbox-guid", "uid", "date.received", "size.physical", "hdr.from", "hdr.to", "hdr.cc", "hdr.subject", "hdr.message-id"]


def parse_pager(out, fields=None):
    """Sortie `doveadm -f pager` : enregistrements séparés par \\f, « champ: valeur » (valeur éventuellement sur plusieurs lignes)."""
    known = set((fields or []) + ["username", "user", "text"])
    recs = []
    for block in (out or "").split("\f"):
        rec, cur = {}, None
        for line in block.split("\n"):
            m = None if cur == "text" else re.match(r"^([\w.-]+):(?: (.*)|$)", line)   # le corps (dernier champ) va jusqu'au bout
            if m and (m.group(1) in known or m.group(1).startswith("hdr.")):
                cur = m.group(1)
                rec[cur] = m.group(2) or ""
            elif cur is not None:
                rec[cur] = (rec[cur] + "\n" + line) if rec[cur] else line
        if rec:
            recs.append({k: v.rstrip("\n") if k != "text" else v for k, v in rec.items()})
    return recs


def decode_header(value):
    """En-tête RFC 2047 -> texte lisible (=?utf-8?B?...?=)."""
    from email.header import decode_header as dh, make_header
    try:
        return str(make_header(dh(value or "")))
    except Exception:  # noqa: BLE001 -- en-tête malformé : tel quel
        return value or ""


def mailbox_query(params, now):
    """Critères -> requête doveadm (liste) + motifs pour le filtrage final (jokers)."""
    q = []
    for key, word in (("from", "from"), ("to", "to"), ("subject", "subject"), ("body", "body"), ("text", "text")):
        v = params.get(key)
        if v:
            lit_ = longest_literal(v)
            if lit_:
                q += [word, lit_]
    for key, word in (("since", "since"), ("before", "before")):
        v = str(params.get(key) or "").strip()
        if re.match(r"^\d{4}-\d\d-\d\d$", v):
            q += [word, v]
    if params.get("mailbox"):
        q += ["mailbox", str(params["mailbox"])]
    if not q:                                    # jamais « tout » : 7 jours par défaut
        q = ["since", datetime.fromtimestamp(now - 7 * 86400).strftime("%Y-%m-%d")]
    return q


def mailbox_search(params, now, runner=run):
    user = str(params.get("user") or "").strip()
    target = ["-u", user] if user else ["-A"]
    argv = ["doveadm", "-f", "pager", "fetch"] + target + [" ".join(FETCH_FIELDS)] + mailbox_query(params, now)
    code, out, err = runner(argv, timeout=300)
    if code != 0 and not out:
        return {"ok": False, "error": "doveadm %s : %s" % (code, (err.strip().splitlines() or ["?"])[-1][:300])}
    limit = max(1, min(MAX_LIMIT, int(params.get("limit") or 100)))
    pf, pt, ps = wild(params.get("from")), wild(params.get("to")), wild(params.get("subject"))
    rows, total = [], 0
    for r in parse_pager(out, FETCH_FIELDS):
        frm, to, cc, subj = (decode_header(r.get(h, "")) for h in ("hdr.from", "hdr.to", "hdr.cc", "hdr.subject"))
        if not (match(pf, frm) and match(pt, to, cc) and match(ps, subj)):
            continue
        total += 1
        if len(rows) < limit:
            rows.append({"user": r.get("username") or r.get("user") or user, "mailbox": r.get("mailbox"), "guid": r.get("mailbox-guid"),
                         "uid": r.get("uid"), "date": r.get("date.received"), "size": int(r["size.physical"]) if (r.get("size.physical") or "").isdigit() else None,
                         "from": frm, "to": to, "cc": cc, "subject": subj, "message_id": (r.get("hdr.message-id") or "").strip().strip("<>")})
    return {"ok": True, "total": total, "truncated": total > len(rows), "rows": rows, "query": argv[5:]}


# ------------------------------------------------------------------ audit + aiguillage

def audit(entry, path=AUDIT_LOG):
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
        os.chmod(path, 0o600)
    except OSError:
        pass


def _raw(text):
    b = text.encode("utf-8", "surrogateescape") if isinstance(text, str) else text
    trunc = len(b) > MAX_RAW
    return {"raw": b[:MAX_RAW].decode("utf-8", "replace"), "size": len(b), "truncated": trunc}


def run_action(params, now=None, runner=run, log_path="/var/log/mail.log", dsn_dirs=AMAVIS_CONF, audit_path=AUDIT_LOG):
    now = now or time.time()
    action = str(params.get("action") or "")
    reason = str(params.get("reason") or "").strip()
    refused = action in CONTENT_ACTIONS and len(reason) < 4
    safe = {k: v for k, v in params.items() if k not in ("reason", "actor")}
    audit({"at": int(now), "action": action, "actor": params.get("actor"), "reason": reason or None, "params": safe,
           "refused": refused or None}, audit_path)             # tentatives refusées comprises
    if refused:
        return {"ok": False, "error": "motif obligatoire pour consulter ou libérer un message (secret des correspondances)"}

    if action == "log_tree":
        minutes = max(1, min(1440, int(params.get("minutes") or 60)))
        return dict(log_tree(read_logs(log_path, now - minutes * 60, now), now, minutes), ok=True)
    if action == "log_search":
        hours = max(1, min(24 * 14, int(params.get("hours") or 24)))
        items = filter_messages(log_messages(read_logs(log_path, now - hours * 3600, now), now, hours), params)
        limit = max(1, min(MAX_LIMIT, int(params.get("limit") or 100)))
        return {"ok": True, "hours": hours, "total": len(items), "truncated": len(items) > limit, "rows": items[:limit]}
    if action == "quarantine_search":
        code, out, err = mysql(amavis_dsn(dsn_dirs), quarantine_sql(params, now), runner)
        if code != 0:
            return {"ok": False, "error": (err.strip().splitlines() or ["mysql %s" % code])[-1][:300]}
        rows = parse_quarantine_rows(out)
        return {"ok": True, "rows": rows, "total": len(rows)}
    if action in ("quarantine_get", "quarantine_release"):
        mid = str(params.get("mail_id") or "")
        if not MAIL_ID_OK.match(mid):
            return {"ok": False, "error": "mail_id invalide"}
        dsn = amavis_dsn(dsn_dirs)
        if action == "quarantine_get":
            code, out, err = mysql(dsn, "SELECT HEX(mail_text) FROM quarantine WHERE mail_id = %s ORDER BY chunk_ind" % lit(mid), runner)
            if code != 0:
                return {"ok": False, "error": (err.strip().splitlines() or ["mysql %s" % code])[-1][:300]}
            data = b"".join(bytes.fromhex(l.strip()) for l in out.splitlines() if l.strip())
            if not data:
                return {"ok": False, "error": "message absent de la quarantaine (déjà libéré ou purgé ?)"}
            return dict(_raw(data), ok=True, mail_id=mid)
        code, out, err = mysql(dsn, "SELECT HEX(secret_id) FROM msgs WHERE mail_id = %s AND quar_type = 'Q' LIMIT 1" % lit(mid), runner)
        secret = _unhex(out.strip()) if code == 0 and out.strip() else ""
        if not secret:
            return {"ok": False, "error": "message introuvable en quarantaine SQL"}
        argv = ["amavisd-release", mid, secret] + [r for r in (params.get("recipients") or []) if re.match(r"^[^\s@]+@[^\s@]+$", str(r))]
        code, out, err = runner(argv, timeout=120)
        text = (out + err).strip()
        ok = code == 0 and " 250 " in (" " + text + " ")
        return {"ok": ok, "mail_id": mid, "output": text[-500:], "error": None if ok else (text.splitlines() or ["amavisd-release %s" % code])[-1][:300]}
    if action == "mailbox_search":
        return mailbox_search(params, now, runner)
    if action == "mailbox_get":
        user, guid, uid = str(params.get("user") or ""), str(params.get("guid") or ""), str(params.get("uid") or "")
        if not (USER_OK.match(user) and GUID_OK.match(guid) and uid.isdigit()):
            return {"ok": False, "error": "user / guid / uid invalides"}
        code, out, err = runner(["doveadm", "-f", "pager", "fetch", "-u", user, "text", "mailbox-guid", guid, "uid", uid], timeout=120)
        recs = parse_pager(out, ["text"])
        if code != 0 or not recs or "text" not in recs[0]:
            return {"ok": False, "error": "doveadm %s : %s" % (code, (err.strip().splitlines() or ["message introuvable"])[-1][:300])}
        return dict(_raw(recs[0]["text"]), ok=True, user=user, guid=guid, uid=uid)
    return {"ok": False, "error": "action inconnue : %s" % action}
