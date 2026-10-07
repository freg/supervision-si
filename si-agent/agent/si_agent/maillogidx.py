# -*- coding: utf-8 -*-
"""#710 : index local de l'historique de traitement du courrier (journal mail), sur le serveur de messagerie.

La recherche « historique » de la tuile Messagerie (#697) relisait le journal à chaque requête, au plus 14 jours et
300 Mo. L'index garde les MÉTADONNÉES de chaque message (n° de file, expéditeur, destinataires, Message-ID, client,
taille, états de remise, verdict Amavis, lignes du journal) -- jamais le contenu -- dans une base SQLite locale (0600),
alimentée au fil de l'eau (inode + position du journal, reprise après rotation), conservée `retention_days` (183 par
défaut : six mois), avec un index plein texte FTS5 quand SQLite le fournit (recherche `q` sur tous les champs).

Fonctions pures testées : `merge`, `like`, `fts_query` ; `update` et `search` sur base temporaire."""
import glob
import gzip
import hashlib
import json
import os
import re
import sqlite3
import time

from . import mailctl

DB_PATH = "/var/lib/si-agent/mail-log-index.db"
SCHEMA = """
CREATE TABLE IF NOT EXISTS msgs (id INTEGER PRIMARY KEY AUTOINCREMENT, qkey TEXT NOT NULL, first INTEGER, last INTEGER, sender TEXT,
    rcpts TEXT, message_id TEXT, client TEXT, size INTEGER, states TEXT, amavis TEXT, queue_ids TEXT, lines TEXT);
CREATE INDEX IF NOT EXISTS msgs_qkey ON msgs (qkey, last);
CREATE INDEX IF NOT EXISTS msgs_last ON msgs (last);
CREATE TABLE IF NOT EXISTS kv (k TEXT PRIMARY KEY, v TEXT);
"""
MAX_LINES = 60
REUSE_GAP = 86400            # un n° de file Postfix revu plus d'un jour après : nouveau message (n° recyclé)


def connect(path=DB_PATH):
    new = not os.path.exists(path)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    conn = sqlite3.connect(path, timeout=30)
    conn.row_factory = sqlite3.Row
    if new:
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
    conn.executescript(SCHEMA)
    try:
        conn.execute("CREATE VIRTUAL TABLE IF NOT EXISTS msgs_fts USING fts5(body, content='', tokenize='unicode61')")
        conn.execute("INSERT OR IGNORE INTO kv (k, v) VALUES ('fts', '1')")
    except sqlite3.OperationalError:
        conn.execute("INSERT OR IGNORE INTO kv (k, v) VALUES ('fts', '0')")
    conn.commit()
    return conn


def _kv(conn, k, default=None):
    r = conn.execute("SELECT v FROM kv WHERE k = ?", (k,)).fetchone()
    if not r:
        return default
    try:
        return json.loads(r["v"])
    except (TypeError, ValueError):
        return r["v"]


def _set(conn, k, v):
    conn.execute("INSERT INTO kv (k, v) VALUES (?, ?) ON CONFLICT(k) DO UPDATE SET v = excluded.v", (k, json.dumps(v)))


def merge(old, new):
    """Fusion de deux vues d'un même message (lot précédent + lot courant). Pure."""
    out = dict(old)
    out["first"] = min(x for x in (old.get("first"), new.get("first")) if x) if (old.get("first") or new.get("first")) else None
    out["last"] = max(old.get("last") or 0, new.get("last") or 0) or None
    for f in ("from", "message_id", "client", "size"):
        out[f] = old.get(f) if old.get(f) not in (None, "") else new.get(f)
    out["to"] = list(dict.fromkeys((old.get("to") or []) + (new.get("to") or [])))
    out["queue_ids"] = list(dict.fromkeys((old.get("queue_ids") or []) + (new.get("queue_ids") or [])))
    out["states"] = (old.get("states") or []) + (new.get("states") or [])
    out["amavis"] = new.get("amavis") or old.get("amavis")
    out["lines"] = ((old.get("lines") or []) + (new.get("lines") or []))[:MAX_LINES]
    return out


def _body(m):
    am = m.get("amavis") or {}
    return " ".join(str(x) for x in [m.get("from"), " ".join(m.get("to") or []), m.get("message_id"), m.get("client"),
                                       " ".join(m.get("states") or []), am.get("verdict"), am.get("mail_id"), " ".join(m.get("queue_ids") or [])] if x)


def _row_to_msg(r):
    return {"key": r["qkey"], "id": r["id"], "first": r["first"], "last": r["last"], "from": r["sender"],
            "to": [x for x in (r["rcpts"] or "").split(",") if x], "message_id": r["message_id"], "client": r["client"], "size": r["size"],
            "states": json.loads(r["states"] or "[]"), "amavis": json.loads(r["amavis"] or "null"), "queue_ids": json.loads(r["queue_ids"] or "[]"),
            "lines": json.loads(r["lines"] or "[]")}


def _store(conn, m, fts):
    key = m["key"]
    if key.startswith("noqueue-"):                     # numérotation propre à un lot : clé rendue unique
        key = "nq-%s-%s" % (m.get("first"), hashlib.sha1(((m.get("lines") or [{}])[0].get("line") or "").encode()).hexdigest()[:8])
    r = conn.execute("SELECT * FROM msgs WHERE qkey = ? ORDER BY last DESC LIMIT 1", (key,)).fetchone()
    if r and (m.get("first") or 0) - (r["last"] or 0) <= REUSE_GAP:
        cur = merge(_row_to_msg(r), m)
        rid = r["id"]
        conn.execute("UPDATE msgs SET first=?, last=?, sender=?, rcpts=?, message_id=?, client=?, size=?, states=?, amavis=?, queue_ids=?, lines=? WHERE id=?",
                     (cur["first"], cur["last"], cur["from"], ",".join(cur["to"]), cur["message_id"], cur["client"], cur["size"],
                      json.dumps(cur["states"], ensure_ascii=False), json.dumps(cur["amavis"], ensure_ascii=False), json.dumps(cur["queue_ids"]),
                      json.dumps(cur["lines"], ensure_ascii=False), rid))
        if fts:
            conn.execute("INSERT INTO msgs_fts (msgs_fts, rowid, body) VALUES ('delete', ?, ?)", (rid, _body(_row_to_msg(r))))
    else:
        cur = m
        rid = conn.execute("INSERT INTO msgs (qkey, first, last, sender, rcpts, message_id, client, size, states, amavis, queue_ids, lines) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                           (key, m.get("first"), m.get("last"), m.get("from"), ",".join(m.get("to") or []), m.get("message_id"), m.get("client"), m.get("size"),
                            json.dumps(m.get("states") or [], ensure_ascii=False), json.dumps(m.get("amavis"), ensure_ascii=False),
                            json.dumps(m.get("queue_ids") or []), json.dumps((m.get("lines") or [])[:MAX_LINES], ensure_ascii=False))).lastrowid
    if fts:
        conn.execute("INSERT INTO msgs_fts (rowid, body) VALUES (?, ?)", (rid, _body(cur)))


def _read_from(path, offset, max_bytes):
    opener = gzip.open if path.endswith(".gz") else open
    with opener(path, "rb") as fh:
        if offset:
            fh.seek(offset)
        data = fh.read(max_bytes)
        pos = fh.tell()
    cut = data.rfind(b"\n")                              # jamais une ligne coupée
    if cut < 0:
        return [], offset
    return data[:cut + 1].decode("utf-8", "replace").splitlines(), offset + cut + 1 if not path.endswith(".gz") else pos


def update(log_path="/var/log/mail.log", db_path=DB_PATH, now=None, retention_days=183, backfill_days=31, max_bytes=200 * 1024 * 1024):
    """Ajoute à l'index les lignes nouvelles du journal. Premier passage : rattrapage sur `backfill_days` (rotations
    comprises). Ensuite : position mémorisée (inode, octet) ; rotation détectée par l'inode -> fin de l'ancien
    fichier (.1) puis le nouveau depuis le début. -> {added_lines, messages, rows, fts}."""
    now = now or time.time()
    conn = connect(db_path)
    try:
        fts = _kv(conn, "fts") in (1, "1", True)
        pos = _kv(conn, "pos") or None
        try:
            st = os.stat(log_path)
        except OSError as exc:
            return {"ok": False, "error": "journal illisible : %s" % exc}
        lines = []
        if not isinstance(pos, dict):
            lines = mailctl.read_logs(log_path, now - backfill_days * 86400, now)
            new_pos = {"inode": st.st_ino, "offset": st.st_size}
        elif pos.get("inode") != st.st_ino:
            rotated = log_path + ".1"
            try:
                if os.stat(rotated).st_ino == pos.get("inode"):
                    lines, _ = _read_from(rotated, pos.get("offset") or 0, max_bytes)
            except OSError:
                pass
            more, off = _read_from(log_path, 0, max_bytes)
            lines += more
            new_pos = {"inode": st.st_ino, "offset": off}
        else:
            off0 = pos.get("offset") or 0
            if st.st_size < off0:                        # tronqué (copytruncate) : depuis le début
                off0 = 0
            lines, off = _read_from(log_path, off0, max_bytes)
            new_pos = {"inode": st.st_ino, "offset": off}
        msgs = mailctl.log_messages(lines, now, hours=max(1, backfill_days * 24 + 24)) if lines else []
        for m in msgs:
            _store(conn, m, fts)
        _set(conn, "pos", new_pos)
        _set(conn, "updated_at", int(now))
        cutoff = int(now - retention_days * 86400)
        if fts:
            for r in conn.execute("SELECT * FROM msgs WHERE last < ?", (cutoff,)).fetchall():
                conn.execute("INSERT INTO msgs_fts (msgs_fts, rowid, body) VALUES ('delete', ?, ?)", (r["id"], _body(_row_to_msg(r))))
        conn.execute("DELETE FROM msgs WHERE last < ?", (cutoff,))
        conn.commit()
        rows = conn.execute("SELECT COUNT(*), MIN(first) FROM msgs").fetchone()
        return {"ok": True, "added_lines": len(lines), "messages": len(msgs), "rows": rows[0], "since": rows[1], "fts": fts}
    finally:
        conn.close()


def like(value):
    """Motif utilisateur (jokers * ?) -> LIKE ; sans joker : « contient ». Pure."""
    raw = str(value or "").strip().lower()
    v = raw.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_").replace("*", "%").replace("?", "_")
    return v if ("*" in raw or "?" in raw) else "%" + v + "%"


def fts_query(q):
    """Texte libre -> requête FTS5 : chaque mot entre guillemets, préfixe autorisé (mot*). Pure."""
    terms = []
    for w in re.findall(r"[\w@.+-]+\*?", str(q or "")):
        star = w.endswith("*")
        w = w.rstrip("*")
        if w:
            terms.append('"%s"%s' % (w.replace('"', ""), "*" if star else ""))
    return " ".join(terms)


def search(params, db_path=DB_PATH, now=None):
    """Recherche dans l'index : from, to, message_id, queue_id, status (jokers), q (plein texte), days, limit."""
    now = now or time.time()
    if not os.path.exists(db_path):
        return None
    conn = connect(db_path)
    try:
        days = int(params.get("days") or 0) or -(-int(params.get("hours") or 24) // 24)
        days = max(1, min(3650, days))
        limit = max(1, min(mailctl.MAX_LIMIT, int(params.get("limit") or 100)))
        where, args = ["last >= ?"], [int(now - days * 86400)]
        for field, col in (("from", "sender"), ("to", "rcpts"), ("message_id", "message_id")):
            if params.get(field):
                where.append("LOWER(IFNULL(%s,'')) LIKE ? ESCAPE '\\'" % col); args.append(like(params[field]))
        if params.get("status"):                         # mêmes règles que la relecture du journal : un état ou le verdict
            pat = mailctl.wild(params["status"])
            conn.create_function("status_ok", 2, lambda st, am: 1 if mailctl.match(pat, *(json.loads(st or "[]") + [(json.loads(am or "null") or {}).get("verdict") or ""])) else 0)
            where.append("status_ok(states, amavis) = 1")
        if params.get("queue_id"):
            q = str(params["queue_id"]).strip()
            where.append("(qkey = ? OR queue_ids LIKE ? OR amavis LIKE ?)"); args += [q, '%%"%s"%%' % q, '%%"%s"%%' % q]
        fts = _kv(conn, "fts") in (1, "1", True)
        if params.get("q"):
            if fts and fts_query(params["q"]):
                where.append("id IN (SELECT rowid FROM msgs_fts WHERE msgs_fts MATCH ?)"); args.append(fts_query(params["q"]))
            else:
                where.append("(LOWER(IFNULL(sender,'') || ' ' || IFNULL(rcpts,'') || ' ' || IFNULL(message_id,'') || ' ' || states || ' ' || IFNULL(amavis,'')) LIKE ? ESCAPE '\\')")
                args.append(like(params["q"]))
        sql = "SELECT * FROM msgs WHERE %s ORDER BY last DESC LIMIT %d" % (" AND ".join(where), limit + 1)
        rows = [_row_to_msg(r) for r in conn.execute(sql, args).fetchall()]
        info = conn.execute("SELECT COUNT(*), MIN(first) FROM msgs").fetchone()
        return {"ok": True, "indexed": True, "days": days, "total": len(rows[:limit]), "truncated": len(rows) > limit, "rows": rows[:limit],
                "index": {"rows": info[0], "since": info[1], "updated_at": _kv(conn, "updated_at"), "fts": fts}}
    finally:
        conn.close()
