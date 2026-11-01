# -*- coding: utf-8 -*-
"""notify-api (livraison #590, backlog item 92) -- notifications par courriel
des actions du hub et gestionnaire d'envoi DÉTACHÉ.

Deux faces :
- producteurs (modules du hub, services externes) : `POST /notify` avec un
  jeton de consommateur -> mise en file immédiate, jamais bloquante ;
  `POST /actions/register` déclare des actions (catalogue) : chaque action
  est rattachée par défaut au groupe automatique de son module ;
- administration (jeton Keycloak vérifié, groupe `administrateurs`) :
  groupes / méta-groupes, affectations action → groupes, liste noire,
  consommateurs (jeton généré, montré une fois, haché ici), file, journal,
  réglages, test d'envoi.

Le fil d'envoi (thread) lit la file : regroupement des messages identiques
dans la fenêtre, retenue des rafales (résumé unique), débit maximal,
backoff et disjoncteur SMTP. Rien n'est perdu : tout reste en base (SQLite)
avec son état. Aucun secret dans les réponses (jetons hachés, mot de passe
SMTP jamais lu ailleurs qu'à l'envoi).
"""
import base64
import hashlib
import json
import logging
import os
import secrets
import smtplib
import sqlite3
import threading
import time
from email.message import EmailMessage

from flask import Flask, g, has_app_context, jsonify, request
from flask_cors import CORS

import core
import push
import sms
from auth import AuthError, KeycloakVerifier, bearer_from_header

try:
    from version_endpoint import register_version_route
except ImportError:  # pragma: no cover
    register_version_route = None

logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(name)s %(message)s")
_log = logging.getLogger("notify-api")

DB_PATH = os.environ.get("NOTIFY_DB", "/data/notify.sqlite")
INTERNAL_TOKEN = os.environ.get("NOTIFY_INTERNAL_TOKEN", "")
KEYCLOAK_INTERNAL_URL = os.environ.get("KEYCLOAK_INTERNAL_URL", "http://keycloak:8080/auth")
KEYCLOAK_REALM = os.environ.get("KEYCLOAK_REALM", "supervision-si")
JWKS_URL = os.environ.get("NOTIFY_JWKS_URL") or "%s/realms/%s/protocol/openid-connect/certs" % (KEYCLOAK_INTERNAL_URL, KEYCLOAK_REALM)
ADMIN_USERS = [u for u in os.environ.get("NOTIFY_ADMIN_USERS", "").split(",") if u.strip()]
ADMIN_GROUPS = [g_ for g_ in os.environ.get("NOTIFY_ADMIN_GROUPS", "administrateurs").split(",") if g_.strip()]
ENV_SMTP = {k: os.environ.get("NOTIFY_SMTP_" + k, os.environ.get("SECRETS_ALERT_SMTP_" + k, "")) for k in ("HOST", "PORT", "USER", "PASSWORD", "FROM", "USE_TLS")}
SMTP_KEYS = ("host", "port", "security", "user", "password", "from")  # #591 : réglages SMTP dans la tuile (base), le .env sert de défaut


def smtp_config():
    """Réglages SMTP effectifs : base (tuile Réglages) puis .env. -> dict host, port, security (starttls|ssl|none), user, password, from."""
    env = {"host": ENV_SMTP["HOST"], "port": ENV_SMTP["PORT"] or "587", "user": ENV_SMTP["USER"], "password": ENV_SMTP["PASSWORD"], "from": ENV_SMTP["FROM"],
           "security": "none" if (ENV_SMTP["USE_TLS"] or "true").lower() == "false" else "starttls"}
    try:
        c = _conn()
        rows = {r["key"]: r["value"] for r in c.execute("SELECT key, value FROM settings WHERE key LIKE 'smtp_%'")}
        c.close()
    except sqlite3.Error:
        rows = {}
    out = dict(env)
    for k in SMTP_KEYS:
        v = rows.get("smtp_" + k)
        if v is not None:
            try:
                v = json.loads(v)
            except ValueError:
                pass
            if v not in (None, ""):
                out[k] = v
    return out
SUBJECT_PREFIX = os.environ.get("NOTIFY_SUBJECT_PREFIX", "[Hub SI]")
DEFAULTS = {"enabled": True, "max_per_minute": 20, "coalesce_seconds": 60, "burst_threshold": 30, "burst_window": 300,
            "breaker_failures": 3, "breaker_cooldown": 300, "retry_max": 6}
WORKER_INTERVAL = int(os.environ.get("NOTIFY_WORKER_INTERVAL", "5"))

app = Flask(__name__)
CORS(app)
if register_version_route:
    register_version_route(app, "notify-api")
verifier = KeycloakVerifier(JWKS_URL, ADMIN_USERS, allowed_groups=ADMIN_GROUPS, what="les notifications")
_lock = threading.RLock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS actions (id TEXT PRIMARY KEY, module TEXT, label TEXT, severity TEXT DEFAULT 'info', created_at REAL, last_seen REAL, count INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS groups (id TEXT PRIMARY KEY, name TEXT, kind TEXT DEFAULT 'group', emails TEXT DEFAULT '[]', members TEXT DEFAULT '[]', auto INTEGER DEFAULT 0, note TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS assignments (action TEXT, group_id TEXT, PRIMARY KEY (action, group_id));
CREATE TABLE IF NOT EXISTS consumers (name TEXT PRIMARY KEY, token_hash TEXT, external INTEGER DEFAULT 1, created_at REAL, last_seen REAL, note TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS blacklist (kind TEXT, value TEXT, reason TEXT DEFAULT '', created_at REAL, PRIMARY KEY (kind, value));
CREATE TABLE IF NOT EXISTS queue (id INTEGER PRIMARY KEY AUTOINCREMENT, action TEXT, consumer TEXT, severity TEXT, subject TEXT, body TEXT, context TEXT,
    recipients TEXT, status TEXT, reason TEXT DEFAULT '', created_at REAL, due_at REAL, sent_at REAL, attempts INTEGER DEFAULT 0, last_error TEXT DEFAULT '', merged INTEGER DEFAULT 0, ckey TEXT);
CREATE INDEX IF NOT EXISTS queue_status ON queue (status, due_at);
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY AUTOINCREMENT, at REAL, event TEXT, text TEXT);
CREATE TABLE IF NOT EXISTS pauses (id INTEGER PRIMARY KEY AUTOINCREMENT, debut REAL, fin REAL, motif TEXT, site TEXT, type TEXT, actions TEXT, consommateurs TEXT,
    contexte TEXT DEFAULT '{}', cree_par TEXT, cree_le REAL, bilan_envoye INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS attachments (queue_id INTEGER, filename TEXT, content_type TEXT, data BLOB);
CREATE TABLE IF NOT EXISTS sms_out (id INTEGER PRIMARY KEY AUTOINCREMENT, created_at REAL, consumer TEXT, to_number TEXT, text TEXT, status TEXT,
    due_at REAL, sent_at REAL, attempts INTEGER DEFAULT 0, last_error TEXT DEFAULT '', reply TEXT DEFAULT '');
CREATE INDEX IF NOT EXISTS sms_out_status ON sms_out (status, due_at);
CREATE TABLE IF NOT EXISTS sms_in (id INTEGER PRIMARY KEY AUTOINCREMENT, received_at REAL, from_number TEXT, text TEXT, consumer TEXT, source_ip TEXT);
CREATE TABLE IF NOT EXISTS push_subs (id INTEGER PRIMARY KEY AUTOINCREMENT, endpoint TEXT UNIQUE, p256dh TEXT, auth TEXT, username TEXT, label TEXT,
    min_severity TEXT DEFAULT 'critical', created_at REAL, last_ok REAL, last_error TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS push_out (id INTEGER PRIMARY KEY AUTOINCREMENT, sub_id INTEGER, created_at REAL, payload TEXT, status TEXT DEFAULT 'queued',
    attempts INTEGER DEFAULT 0, last_error TEXT DEFAULT '', due_at REAL);
CREATE INDEX IF NOT EXISTS push_out_status ON push_out (status, due_at);
"""
# #787 : SMS internes -- relais du TRB140 avec une clé PROPRE au hub (utilisateur dédié du relais, distinct du client externe)
SMS_RELAY_URL = os.environ.get("NOTIFY_SMS_RELAY_URL", "").rstrip("/")


def ui_url(v):
    """#791 : lien d'interface affiché dans le hub -- http(s) seulement, sans identifiants (user:mdp@) ni paramètres."""
    v = (v or "").strip()
    if not v.lower().startswith(("http://", "https://")):
        return ""
    sch, rest = v.split("//", 1)
    hote, _, chemin = rest.partition("/")
    return sch + "//" + hote.rsplit("@", 1)[-1] + ("/" + chemin.split("?")[0].split("#")[0] if chemin else "")


SMS_RELAY_UI = ui_url(os.environ.get("NOTIFY_SMS_RELAY_UI", "") or SMS_RELAY_URL)   # #791 : interface du relais (défaut : URL du relais)
SMS_TRB_UI = ui_url(os.environ.get("NOTIFY_SMS_TRB_UI", ""))                          # #791 : interface web du TRB140 (facultatif)
SMS_RELAY_KEY = os.environ.get("NOTIFY_SMS_RELAY_KEY", "")


def db():
    conn = getattr(g, "_db", None) if g else None
    if conn is None:
        conn = sqlite3.connect(DB_PATH, timeout=10, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        try:
            g._db = conn
        except RuntimeError:
            pass
    return conn


def _conn():
    conn = sqlite3.connect(DB_PATH, timeout=10, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
    c = _conn()
    c.executescript(SCHEMA)
    c.commit()
    c.close()


init_db()


@app.teardown_appcontext
def _close(_exc):
    conn = getattr(g, "_db", None)
    if conn is not None:
        conn.close()


def event(kind, text):
    """Journal. Dans une requête : MÊME connexion (jamais un second lien qui
    attendrait le verrou d'écriture de la transaction en cours)."""
    with _lock:
        if has_app_context():
            c = db()
            c.execute("INSERT INTO events (at, event, text) VALUES (?, ?, ?)", (time.time(), kind, text))
            c.commit()
        else:
            c = _conn()
            c.execute("INSERT INTO events (at, event, text) VALUES (?, ?, ?)", (time.time(), kind, text))
            c.commit()
            c.close()
    _log.info("%s -- %s", kind, text)


def settings_get(conn=None):
    if conn is None and has_app_context():
        conn = db()
    c = conn or _conn()
    out = dict(DEFAULTS)
    for r in c.execute("SELECT key, value FROM settings"):
        try:
            out[r["key"]] = json.loads(r["value"])
        except ValueError:
            pass
    if conn is None:
        c.close()
    return out


def _hash(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


# -- authentification -------------------------------------------------------------
def consumer_from_request():
    tok = request.headers.get("X-Notify-Token") or ""
    if not tok and request.path.startswith("/sms/"):   # #787 : appels « à l'ancienne » (?key= du relais, ?jeton= du TRB140)
        tok = request.args.get("key") or request.args.get("jeton") or ""
    if not tok:
        return None
    if INTERNAL_TOKEN and secrets.compare_digest(tok, INTERNAL_TOKEN):
        return {"name": request.headers.get("X-Notify-Consumer") or "hub", "external": False}
    c = db()
    row = c.execute("SELECT name, external FROM consumers WHERE token_hash = ?", (_hash(tok),)).fetchone()
    if row:
        c.execute("UPDATE consumers SET last_seen = ? WHERE name = ?", (time.time(), row["name"]))
        c.commit()
        return {"name": row["name"], "external": bool(row["external"])}
    return None


PRODUCER = ("/notify", "/actions/register", "/sms", "/sms/send", "/sms/recu", "/pauses/actives")   # #853 : pauses lues par les producteurs
PUBLIC = ("/health", "/version", "/push/key")   # #796 : la clé publique VAPID n'est pas un secret


@app.before_request
def _guard():
    if request.method == "OPTIONS" or request.path in PUBLIC:
        return None
    if request.path in PRODUCER:
        g.consumer = consumer_from_request()
        if not g.consumer:
            return jsonify({"error": "jeton de consommateur requis (X-Notify-Token)"}), 401
        return None
    try:
        g.user = verifier.verify(bearer_from_header(request.headers.get("Authorization")))
    except AuthError as exc:
        return jsonify({"error": str(exc)}), exc.status
    return None


@app.route("/health", methods=["GET"])
def health():
    c = db()
    st = settings_get(c)
    n = {r["status"]: r["n"] for r in c.execute("SELECT status, COUNT(*) AS n FROM queue GROUP BY status")}
    smtp = smtp_config()
    return jsonify({"status": "ok" if smtp["host"] else "degraded", "smtp": bool(smtp["host"]), "enabled": st["enabled"], "queue": n,
                    "internal_token": bool(INTERNAL_TOKEN), "sms": bool(SMS_RELAY_URL and SMS_RELAY_KEY)}), 200


# -- producteurs -------------------------------------------------------------------
def ensure_action(c, action, label=None, severity=None, seen=False):
    module = core.module_of(action)
    row = c.execute("SELECT id FROM actions WHERE id = ?", (action,)).fetchone()
    now = time.time()
    if row is None:
        c.execute("INSERT INTO actions (id, module, label, severity, created_at, last_seen, count) VALUES (?, ?, ?, ?, ?, ?, 0)",
                  (action, module, label or action, severity if severity in core.SEVERITIES else "info", now, now if seen else None))
        gid = core.default_group_id(action)
        if c.execute("SELECT 1 FROM groups WHERE id = ?", (gid,)).fetchone() is None:
            c.execute("INSERT INTO groups (id, name, kind, emails, members, auto, note) VALUES (?, ?, 'group', '[]', '[]', 1, ?)",
                      (gid, "Module %s (défaut)" % module, "groupe par défaut généré pour le module « %s » -- renseigner les adresses" % module))
    else:
        if label:
            c.execute("UPDATE actions SET label = ? WHERE id = ?", (label, action))
        if severity in core.SEVERITIES:
            c.execute("UPDATE actions SET severity = ? WHERE id = ?", (severity, action))
    if seen:
        c.execute("UPDATE actions SET last_seen = ?, count = count + 1 WHERE id = ?", (now, action))


def _blacklist(c):
    out = {"email": set(), "action": set(), "consumer": set()}
    for r in c.execute("SELECT kind, value FROM blacklist"):
        out.setdefault(r["kind"], set()).add(r["value"])
    return out


def _groups(c):
    return {r["id"]: {"kind": r["kind"], "emails": json.loads(r["emails"] or "[]"), "members": json.loads(r["members"] or "[]")} for r in c.execute("SELECT * FROM groups")}


def _assignments(c):
    out = {}
    for r in c.execute("SELECT action, group_id FROM assignments"):
        out.setdefault(r["action"], []).append(r["group_id"])
    return out


@app.route("/actions/register", methods=["POST"])
def register_actions():
    body = request.get_json(silent=True) or {}
    items = body.get("actions") if isinstance(body, dict) else body
    if not isinstance(items, list):
        return jsonify({"error": "{\"actions\": [{id, label, severity}]} attendu"}), 400
    c = db()
    done, bad = [], []
    with _lock:
        for it in items:
            aid = (it.get("id") if isinstance(it, dict) else it) or ""
            if not core.valid_action(aid):
                bad.append(aid)
                continue
            ensure_action(c, aid, (it.get("label") if isinstance(it, dict) else None), (it.get("severity") if isinstance(it, dict) else None))
            done.append(aid)
        c.commit()
    return jsonify({"registered": done, "rejected": bad}), 200


@app.route("/notify", methods=["POST"])
def notify():
    body = request.get_json(silent=True) or {}
    action = str(body.get("action") or "").strip()
    if not core.valid_action(action):
        return jsonify({"error": "action attendue sous la forme module.action (ex. mikrotik.nat.add)"}), 400
    subject = str(body.get("subject") or action)[:200]
    text = str(body.get("body") or "")[:20000]
    severity = body.get("severity") if body.get("severity") in core.SEVERITIES else None
    context = body.get("context") if isinstance(body.get("context"), dict) else {}
    consumer = g.consumer["name"]
    # #703 : destinataires explicites en plus des groupes (liste noire appliquée) et pièces jointes
    extra = sorted({str(e).strip().lower() for e in (body.get("to") or [])[:50] if core.valid_email(str(e).strip())}) if isinstance(body.get("to"), list) else []
    try:
        files = parse_attachments(body.get("attachments"))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    c = db()
    with _lock:
        ensure_action(c, action, seen=True)
        c.commit()
        st = settings_get(c)
        sev = severity or c.execute("SELECT severity FROM actions WHERE id = ?", (action,)).fetchone()["severity"]
        recipients, why = core.resolve(action, _assignments(c), _groups(c), _blacklist(c), consumer=consumer)
        if extra and why not in ("action en liste noire", "consommateur en liste noire"):
            blocked = {e.lower() for e in (_blacklist(c).get("email") or set())}
            recipients = sorted(set(recipients) | {e for e in extra if e not in blocked})
            why = None if recipients else (why or "destinataires explicites en liste noire")
        now = time.time()
        status, reason = ("queued", "") if recipients else ("no-recipients", why)
        pz = core.pause_applicable(_pauses(c), action, consumer, context, now)   # #853 : maintenance planifiée
        if pz:
            cur = c.execute("INSERT INTO queue (action, consumer, severity, subject, body, context, recipients, status, reason, created_at, due_at, ckey) VALUES (?, ?, ?, ?, ?, ?, ?, 'paused', ?, ?, ?, '')",
                            (action, consumer, sev, subject, text, json.dumps(dict(context, pause_id=pz["id"]), ensure_ascii=False)[:4000], json.dumps(recipients),
                             "pause : %s (jusqu'au %s)" % (pz["motif"], time.strftime("%d/%m %H:%M", time.localtime(pz["fin"]))), now, now))
            c.commit()
            return jsonify({"status": "paused", "id": cur.lastrowid, "reason": pz["motif"], "fin": pz["fin"]}), 202
        if recipients and not st.get("enabled", True):
            status, reason = "held", "envoi suspendu (réglages)"
        ckey = core.coalesce_key(action, subject, recipients)
        # regroupement : même action + même sujet + mêmes destinataires encore en file -> on incrémente
        if status == "queued" and st.get("coalesce_seconds") and not files:
            twin = c.execute("SELECT id FROM queue WHERE ckey = ? AND status = 'queued' AND created_at > ? ORDER BY id DESC LIMIT 1",
                             (ckey, now - st["coalesce_seconds"])).fetchone()
            if twin:
                c.execute("UPDATE queue SET merged = merged + 1 WHERE id = ?", (twin["id"],))
                c.commit()
                return jsonify({"status": "merged", "id": twin["id"]}), 202
        # emballement : trop de messages de cette action dans la fenêtre -> retenu (un résumé partira)
        if status == "queued" and st.get("burst_threshold"):
            recent = c.execute("SELECT COUNT(*) AS n FROM queue WHERE action = ? AND created_at > ?", (action, now - st["burst_window"])).fetchone()["n"]
            if core.burst_state(recent, st["burst_threshold"]) == "hold":
                status, reason = "held", "rafale : %d messages en %d s" % (recent, st["burst_window"])
                if c.execute("SELECT 1 FROM queue WHERE action = ? AND status = 'queued' AND subject LIKE 'Rafale de notifications%' AND created_at > ?", (action, now - st["burst_window"])).fetchone() is None:
                    first = c.execute("SELECT subject FROM queue WHERE action = ? AND created_at > ? ORDER BY id LIMIT 1", (action, now - st["burst_window"])).fetchone()
                    c.execute("INSERT INTO queue (action, consumer, severity, subject, body, context, recipients, status, created_at, due_at, ckey) VALUES (?, ?, 'warning', ?, ?, '{}', ?, 'queued', ?, ?, '')",
                              (action, "notify-api", "Rafale de notifications « %s »" % action, core.summary_body(action, recent + 1, first["subject"] if first else "", st["burst_window"]),
                               json.dumps(recipients), now, now))
                    event("burst", "%s : rafale retenue (%d en %d s), résumé envoyé" % (action, recent + 1, st["burst_window"]))
        cur = c.execute("INSERT INTO queue (action, consumer, severity, subject, body, context, recipients, status, reason, created_at, due_at, ckey) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (action, consumer, sev, subject, text, json.dumps(context, ensure_ascii=False)[:4000], json.dumps(recipients), status, reason, now, now, ckey))
        for f in files:
            c.execute("INSERT INTO attachments (queue_id, filename, content_type, data) VALUES (?, ?, ?, ?)", (cur.lastrowid, f["filename"], f["content_type"], f["data"]))
        pushed = push_enqueue(c, sev, subject, text, context, now)   # #796 : téléphones abonnés (selon leur seuil)
        c.commit()
    return jsonify({"status": status, "id": cur.lastrowid, "recipients": len(recipients), "reason": reason, "attachments": len(files), "push": pushed}), 202


# -- #853 : pauses planifiées ------------------------------------------------------------------------------------------
def _pauses(c, actives_seulement=False):
    q = "SELECT * FROM pauses" + (" WHERE fin > ?" if actives_seulement else "") + " ORDER BY debut"
    out = []
    for r in c.execute(q, (time.time(),) if actives_seulement else ()):
        d = dict(r)
        d["contexte"] = json.loads(d.get("contexte") or "{}")
        out.append(d)
    return out


@app.route("/pauses", methods=["GET"])
def pauses_liste():
    c = db()
    lst = _pauses(c)
    now = time.time()
    for p in lst:
        p["etat"] = "à venir" if now < p["debut"] else "en cours" if now < p["fin"] else "terminée"
        p["retenues"] = c.execute("SELECT COUNT(*) AS n FROM queue WHERE status = 'paused' AND context LIKE ?", ('%%"pause_id": %d%%' % p["id"],)).fetchone()["n"]
    return jsonify({"pauses": list(reversed(lst))[:100]}), 200


@app.route("/pauses", methods=["POST"])
def pauses_creer():
    p, err = core.valider_pause(request.get_json(silent=True) or {}, time.time())
    if err:
        return jsonify({"error": err}), 400
    c = db()
    with _lock:
        cur = c.execute("INSERT INTO pauses (debut, fin, motif, site, type, actions, consommateurs, contexte, cree_par, cree_le) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (p["debut"], p["fin"], p["motif"], p["site"], p["type"], p["actions"], p["consommateurs"], json.dumps(p["contexte"], ensure_ascii=False),
                         (getattr(g, "user", None) or {}).get("preferred_username") if isinstance(getattr(g, "user", None), dict) else "", time.time()))
        c.commit()
    event("pause", "pause %s du %s au %s : %s" % (p["type"], time.strftime("%d/%m %H:%M", time.localtime(p["debut"])), time.strftime("%d/%m %H:%M", time.localtime(p["fin"])), p["motif"]))
    return jsonify(dict(p, id=cur.lastrowid)), 201


@app.route("/pauses/<int:pid>", methods=["DELETE"])
def pauses_supprimer(pid):
    c = db()
    with _lock:
        c.execute("DELETE FROM pauses WHERE id = ?", (pid,))
        c.commit()
    return jsonify({"ok": True}), 200


@app.route("/pauses/actives", methods=["GET"])
def pauses_actives():
    """Pour les producteurs (veille du campus, si-veille par le résumé de veille) : pauses en cours qui les couvrent."""
    now = time.time()
    lst = [p for p in _pauses(db(), True) if p["debut"] <= now]
    cons = request.args.get("consumer") or g.consumer["name"]
    ctx = {k: v for k, v in request.args.items() if k not in ("consumer", "action")}
    act = request.args.get("action") or ""
    # sans contexte ni action précisés : toutes les pauses en cours de ce consommateur (le producteur filtre lui-même)
    sel = [p for p in lst if core.pause_applicable([dict(p, contexte=p["contexte"] if ctx else {}, actions=p["actions"] if act else "")], act, cons, ctx, now)]
    return jsonify({"pauses": sel}), 200


def bilan_pauses(c, now=None):
    """Fin d'une pause : un message « reprise » récapitule ce qui a été retenu (action notify.maintenance-fin)."""
    now = now or time.time()
    for p in c.execute("SELECT * FROM pauses WHERE fin <= ? AND bilan_envoye = 0", (now,)).fetchall():
        rows = c.execute("SELECT action, subject, created_at FROM queue WHERE status = 'paused' AND context LIKE ? ORDER BY created_at", ('%%"pause_id": %d%%' % p["id"],)).fetchall()
        corps = "Fin de la pause « %s » (%s → %s).\n\n%d notification(s) retenue(s) pendant la pause :\n%s\n\nVérifier la reprise : agents revenus, veille du site, équipements en ligne.\n" % (
            p["motif"], time.strftime("%d/%m %H:%M", time.localtime(p["debut"])), time.strftime("%d/%m %H:%M", time.localtime(p["fin"])), len(rows),
            "\n".join("  %s  %s -- %s" % (time.strftime("%d/%m %H:%M", time.localtime(r["created_at"])), r["action"], r["subject"]) for r in rows[-80:]) or "  aucune")
        ensure_action(c, "notify.maintenance-fin", "Fin d'une pause planifiée : bilan des notifications retenues", "warning")
        rec, _why = core.resolve("notify.maintenance-fin", _assignments(c), _groups(c), _blacklist(c), consumer="notify-api")
        c.execute("INSERT INTO queue (action, consumer, severity, subject, body, context, recipients, status, reason, created_at, due_at, ckey) VALUES (?, ?, 'warning', ?, ?, '{}', ?, ?, ?, ?, ?, '')",
                  ("notify.maintenance-fin", "notify-api", "Reprise après « %s » : %d notification(s) retenue(s)" % (p["motif"], len(rows)), corps, json.dumps(rec),
                   "queued" if rec else "no-recipients", "" if rec else "aucun destinataire pour notify.maintenance-fin", now, now))
        c.execute("UPDATE pauses SET bilan_envoye = 1 WHERE id = ?", (p["id"],))
        c.commit()


MAX_ATTACH_BYTES = int(os.environ.get("NOTIFY_MAX_ATTACH_BYTES", str(8 * 1024 * 1024)))


def parse_attachments(items):
    """[{filename, content_type, data (base64)}] -> [{filename, content_type, data bytes}] ; 5 fichiers, 8 Mo au total."""
    if not items:
        return []
    if not isinstance(items, list) or len(items) > 5:
        raise ValueError("attachments : liste de 5 fichiers au plus")
    out, total = [], 0
    for it in items:
        if not isinstance(it, dict):
            raise ValueError("attachments : objets {filename, content_type, data}")
        name = os.path.basename(str(it.get("filename") or "piece-jointe"))[:120] or "piece-jointe"
        ctype = str(it.get("content_type") or "application/octet-stream")
        if "/" not in ctype or len(ctype) > 100:
            raise ValueError("attachments : content_type invalide")
        try:
            data = base64.b64decode(str(it.get("data") or ""), validate=True)
        except (ValueError, TypeError):
            raise ValueError("attachments : %s n'est pas en base64" % name)
        total += len(data)
        if total > MAX_ATTACH_BYTES:
            raise ValueError("attachments : %d octets au plus au total" % MAX_ATTACH_BYTES)
        out.append({"filename": name, "content_type": ctype, "data": data})
    return out


# -- administration ---------------------------------------------------------------
def _row(r):
    d = dict(r)
    for k in ("emails", "members", "recipients", "context"):
        if k in d and isinstance(d[k], str):
            try:
                d[k] = json.loads(d[k] or ("[]" if k != "context" else "{}"))
            except ValueError:
                pass
    return d


@app.route("/actions", methods=["GET"])
def actions():
    c = db()
    asg = _assignments(c)
    rows = [dict(_row(r), groups=asg.get(r["id"], []), default_group=core.default_group_id(r["id"])) for r in c.execute("SELECT * FROM actions ORDER BY module, id")]
    return jsonify({"actions": rows}), 200


@app.route("/actions/<path:action>/groups", methods=["PUT"])
def set_assignment(action):
    if not core.valid_action(action) and not action.endswith(".*"):
        return jsonify({"error": "action invalide"}), 400
    gids = (request.get_json(silent=True) or {}).get("groups")
    if not isinstance(gids, list):
        return jsonify({"error": "{\"groups\": [id...]} attendu (vide = groupe par défaut du module)"}), 400
    c = db()
    known = {r["id"] for r in c.execute("SELECT id FROM groups")}
    bad = [x for x in gids if x not in known]
    if bad:
        return jsonify({"error": "groupe(s) inconnu(s) : %s" % ", ".join(bad)}), 400
    with _lock:
        c.execute("DELETE FROM assignments WHERE action = ?", (action,))
        for x in gids:
            c.execute("INSERT INTO assignments (action, group_id) VALUES (?, ?)", (action, x))
        c.commit()
    event("assign", "%s → %s (par %s)" % (action, ", ".join(gids) or "groupe par défaut", g.user["username"]))
    return jsonify({"status": "ok", "action": action, "groups": gids}), 200


@app.route("/groups", methods=["GET"])
def groups():
    c = db()
    rows = [_row(r) for r in c.execute("SELECT * FROM groups ORDER BY auto DESC, name")]
    gmap = _groups(c)
    for r in rows:
        r["resolved"] = sorted(core.expand_group(r["id"], gmap))
    return jsonify({"groups": rows}), 200


@app.route("/groups", methods=["POST"])
@app.route("/groups/<gid>", methods=["PUT"])
def save_group(gid=None):
    body = request.get_json(silent=True) or {}
    c = db()
    if gid is None:
        name = str(body.get("name") or "").strip()
        if not name:
            return jsonify({"error": "nom requis"}), 400
        kind = "meta" if body.get("kind") == "meta" else "group"
        gid = ("m:" if kind == "meta" else "g:") + core.re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:40]
        if c.execute("SELECT 1 FROM groups WHERE id = ?", (gid,)).fetchone():
            return jsonify({"error": "un groupe porte déjà ce nom (%s)" % gid}), 409
        c.execute("INSERT INTO groups (id, name, kind, emails, members, auto, note) VALUES (?, ?, ?, '[]', '[]', 0, '')", (gid, name, kind))
    row = c.execute("SELECT * FROM groups WHERE id = ?", (gid,)).fetchone()
    if row is None:
        return jsonify({"error": "groupe inconnu"}), 404
    emails = body.get("emails", json.loads(row["emails"] or "[]"))
    members = body.get("members", json.loads(row["members"] or "[]"))
    if not isinstance(emails, list) or not isinstance(members, list):
        return jsonify({"error": "emails et members : listes"}), 400
    emails = [e.strip().lower() for e in emails if isinstance(e, str) and e.strip()]
    bad = [e for e in emails if not core.valid_email(e)]
    if bad:
        return jsonify({"error": "adresse(s) invalide(s) : %s" % ", ".join(bad)}), 400
    known = {r["id"] for r in c.execute("SELECT id FROM groups")}
    badm = [m for m in members if m not in known or m == gid]
    if badm:
        return jsonify({"error": "membre(s) inconnu(s) ou circulaire(s) : %s" % ", ".join(badm)}), 400
    with _lock:
        c.execute("UPDATE groups SET name = ?, emails = ?, members = ?, note = ? WHERE id = ?",
                  (str(body.get("name") or row["name"]).strip()[:80], json.dumps(emails), json.dumps(members), str(body.get("note") or row["note"] or "")[:300], gid))
        c.commit()
    event("group", "%s : %d adresse(s), %d membre(s) (par %s)" % (gid, len(emails), len(members), g.user["username"]))
    return jsonify({"status": "ok", "id": gid}), 200


@app.route("/groups/<gid>", methods=["DELETE"])
def delete_group(gid):
    c = db()
    row = c.execute("SELECT auto FROM groups WHERE id = ?", (gid,)).fetchone()
    if row is None:
        return jsonify({"error": "groupe inconnu"}), 404
    if row["auto"]:
        return jsonify({"error": "groupe par défaut d'un module : non supprimable (vider ses adresses ou affecter un autre groupe)"}), 400
    with _lock:
        c.execute("DELETE FROM groups WHERE id = ?", (gid,))
        c.execute("DELETE FROM assignments WHERE group_id = ?", (gid,))
        for r in c.execute("SELECT id, members FROM groups").fetchall():
            ms = json.loads(r["members"] or "[]")
            if gid in ms:
                c.execute("UPDATE groups SET members = ? WHERE id = ?", (json.dumps([m for m in ms if m != gid]), r["id"]))
        c.commit()
    event("group-deleted", "%s (par %s)" % (gid, g.user["username"]))
    return jsonify({"status": "ok"}), 200


@app.route("/blacklist", methods=["GET"])
def blacklist_list():
    return jsonify({"blacklist": [dict(r) for r in db().execute("SELECT * FROM blacklist ORDER BY kind, value")]}), 200


@app.route("/blacklist", methods=["POST"])
def blacklist_add():
    body = request.get_json(silent=True) or {}
    kind, value = body.get("kind"), str(body.get("value") or "").strip().lower()
    if kind not in ("email", "action", "consumer") or not value:
        return jsonify({"error": "kind (email | action | consumer) et value requis"}), 400
    with _lock:
        db().execute("INSERT OR REPLACE INTO blacklist (kind, value, reason, created_at) VALUES (?, ?, ?, ?)", (kind, value, str(body.get("reason") or "")[:200], time.time()))
        db().commit()
    event("blacklist", "%s « %s » (par %s)" % (kind, value, g.user["username"]))
    return jsonify({"status": "ok"}), 200


@app.route("/blacklist/<kind>/<path:value>", methods=["DELETE"])
def blacklist_del(kind, value):
    with _lock:
        db().execute("DELETE FROM blacklist WHERE kind = ? AND value = ?", (kind, value))
        db().commit()
    return jsonify({"status": "ok"}), 200


@app.route("/consumers", methods=["GET"])
def consumers():
    return jsonify({"consumers": [dict(r, token_hash=None) for r in db().execute("SELECT name, external, created_at, last_seen, note FROM consumers ORDER BY name")],
                    "internal_token_configured": bool(INTERNAL_TOKEN)}), 200


@app.route("/consumers", methods=["POST"])
def consumer_add():
    body = request.get_json(silent=True) or {}
    name = core.re.sub(r"[^a-z0-9_-]+", "-", str(body.get("name") or "").strip().lower())[:40].strip("-")
    if not name:
        return jsonify({"error": "nom requis (ex. ged-externe)"}), 400
    token = secrets.token_urlsafe(32)
    with _lock:
        db().execute("INSERT OR REPLACE INTO consumers (name, token_hash, external, created_at, note) VALUES (?, ?, 1, ?, ?)", (name, _hash(token), time.time(), str(body.get("note") or "")[:200]))
        db().commit()
    event("consumer", "jeton (ré)émis pour « %s » (par %s)" % (name, g.user["username"]))
    return jsonify({"status": "ok", "name": name, "token": token, "note": "jeton montré UNE fois -- à donner au service externe (en-tête X-Notify-Token)"}), 200


@app.route("/consumers/<name>", methods=["DELETE"])
def consumer_del(name):
    with _lock:
        db().execute("DELETE FROM consumers WHERE name = ?", (name,))
        db().commit()
    return jsonify({"status": "ok"}), 200


@app.route("/queue", methods=["GET"])
def queue():
    c = db()
    status = request.args.get("status")
    try:
        limit = max(10, min(500, int(request.args.get("limit", "100"))))
    except ValueError:
        limit = 100
    q = "SELECT id, action, consumer, severity, subject, recipients, status, reason, created_at, due_at, sent_at, attempts, last_error, merged FROM queue"
    args = ()
    if status:
        q += " WHERE status = ?"
        args = (status,)
    rows = [_row(r) for r in c.execute(q + " ORDER BY id DESC LIMIT ?", args + (limit,))]
    counts = {r["status"]: r["n"] for r in c.execute("SELECT status, COUNT(*) AS n FROM queue GROUP BY status")}
    return jsonify({"queue": rows, "counts": counts, "sender": SENDER.state()}), 200


@app.route("/queue/<int:qid>", methods=["GET"])
def queue_item(qid):
    r = db().execute("SELECT * FROM queue WHERE id = ?", (qid,)).fetchone()
    return (jsonify(_row(r)), 200) if r else (jsonify({"error": "inconnu"}), 404)


@app.route("/queue/<int:qid>/<verb>", methods=["POST"])
def queue_act(qid, verb):
    c = db()
    r = c.execute("SELECT * FROM queue WHERE id = ?", (qid,)).fetchone()
    if not r:
        return jsonify({"error": "inconnu"}), 404
    with _lock:
        if verb == "retry":
            recipients, why = core.resolve(r["action"], _assignments(c), _groups(c), _blacklist(c), consumer=r["consumer"])
            if not recipients:
                return jsonify({"error": why}), 400
            c.execute("UPDATE queue SET status = 'queued', recipients = ?, reason = '', due_at = ?, attempts = 0, last_error = '' WHERE id = ?", (json.dumps(recipients), time.time(), qid))
        elif verb == "drop":
            c.execute("UPDATE queue SET status = 'dropped', reason = ? WHERE id = ?", ("abandonné par %s" % g.user["username"], qid))
        else:
            return jsonify({"error": "verbe : retry | drop"}), 400
        c.commit()
    return jsonify({"status": "ok"}), 200


@app.route("/queue/release", methods=["POST"])
def queue_release():
    """Libère les messages retenus (rafale / suspension) : ils repartent en file."""
    with _lock:
        n = db().execute("UPDATE queue SET status = 'queued', reason = '', due_at = ? WHERE status = 'held'", (time.time(),)).rowcount
        db().commit()
    event("release", "%d message(s) retenu(s) libéré(s) par %s" % (n, g.user["username"]))
    return jsonify({"status": "ok", "released": n}), 200


@app.route("/settings", methods=["GET"])
def get_settings():
    smtp = smtp_config()
    return jsonify(dict(settings_get(db()), subject_prefix=SUBJECT_PREFIX,
                        smtp={"host": smtp["host"], "port": int(smtp["port"] or 587), "security": smtp["security"], "user": smtp["user"], "from": smtp["from"],
                              "password_set": bool(smtp["password"]), "from_env": {k: bool(ENV_SMTP[k.upper()]) for k in ("host", "user", "from")}})), 200


@app.route("/settings", methods=["PUT"])
def put_settings():
    body = request.get_json(silent=True) or {}
    cur = settings_get(db())
    smtp_in = body.pop("smtp", None)
    if isinstance(smtp_in, dict):  # #591 : SMTP depuis la tuile ; mot de passe en écriture seule (vide = inchangé)
        sec = str(smtp_in.get("security") or "starttls").lower()
        if sec not in ("starttls", "ssl", "none"):
            return jsonify({"error": "security : starttls, ssl ou none"}), 400
        try:
            port = int(smtp_in.get("port") if smtp_in.get("port") not in (None, "") else 587)
            assert 1 <= port <= 65535
        except (TypeError, ValueError, AssertionError):
            return jsonify({"error": "port SMTP invalide"}), 400
        frm = str(smtp_in.get("from") or "").strip()
        if frm and not core.valid_email(frm):
            return jsonify({"error": "expéditeur invalide"}), 400
        with _lock:
            for k, v in (("host", str(smtp_in.get("host") or "").strip()[:200]), ("port", port), ("security", sec), ("user", str(smtp_in.get("user") or "").strip()[:200]), ("from", frm)):
                db().execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", ("smtp_" + k, json.dumps(v)))
            if smtp_in.get("password"):
                db().execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", ("smtp_password", json.dumps(str(smtp_in["password"]))))
            elif smtp_in.get("clear_password"):
                db().execute("DELETE FROM settings WHERE key = 'smtp_password'")
            db().commit()
        SENDER.failures, SENDER.opened_at = 0, None  # nouveau réglage : on referme le disjoncteur
        event("smtp", "réglages SMTP modifiés par %s (%s:%s, %s, utilisateur %s)" % (g.user["username"], smtp_in.get("host"), port, sec, "oui" if smtp_in.get("user") else "non"))
    with _lock:
        for k, v in body.items():
            if k not in DEFAULTS:
                continue
            if k == "enabled":
                v = bool(v)
            else:
                try:
                    v = max(0, int(v))
                except (TypeError, ValueError):
                    return jsonify({"error": "%s : entier attendu" % k}), 400
            db().execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (k, json.dumps(v)))
        db().commit()
    new = settings_get(db())
    changes = {k: new[k] for k in new if new[k] != cur.get(k)}
    if changes:
        event("settings", "réglages modifiés par %s : %s" % (g.user["username"], changes))
    return get_settings()


@app.route("/events", methods=["GET"])
def events():
    return jsonify({"events": [dict(r) for r in db().execute("SELECT at, event, text FROM events ORDER BY id DESC LIMIT 300")]}), 200


@app.route("/test", methods=["POST"])
def test_send():
    to = str((request.get_json(silent=True) or {}).get("to") or "").strip().lower()
    if not core.valid_email(to):
        return jsonify({"error": "adresse « to » invalide"}), 400
    ok, err = SENDER.deliver([to], core.render_subject(SUBJECT_PREFIX, "info", "test d'envoi"), "Message de test du gestionnaire de notifications du hub, demandé par %s." % g.user["username"])
    return jsonify({"status": "ok" if ok else "error", "error": err}), (200 if ok else 502)


# -- SMS internes (#787) -----------------------------------------------------------
def sms_enqueue(c, consumer, numbers, text, now=None):
    now = now or time.time()
    ids = []
    with _lock:
        for n in numbers:
            cur = c.execute("INSERT INTO sms_out (created_at, consumer, to_number, text, status, due_at) VALUES (?, ?, ?, ?, 'queued', ?)", (now, consumer, n, text, now))
            ids.append(cur.lastrowid)
        c.commit()
    return ids


@app.route("/sms", methods=["POST"])
def sms_post():
    """Producteurs du hub et scripts internes : {to: "+336…,06…" | [...], text} -> mis en file (202)."""
    body = request.get_json(silent=True) or {}
    numbers, bad = sms.destinataires(body.get("to"))
    text = sms.texte(body.get("text") or body.get("message"))
    if not numbers or not text:
        return jsonify({"error": "destinataire(s) et texte requis", "rejected": bad}), 400
    ids = sms_enqueue(db(), g.consumer["name"], numbers, text)
    return jsonify({"queued": ids, "rejected": bad, "segments": sms.segments(text)}), 202


@app.route("/sms/send", methods=["GET", "POST"])
def sms_send_compat():
    """Compatible avec le relais du TRB140 (GET /send?number&message&key) : le pont smstools y envoie sans changement
    de format -- seule l'URL et la clé (jeton de consommateur) changent. 200 quand le message est en file."""
    f = dict(request.args)
    f.update(request.form or {})
    numbers, bad = sms.destinataires(f.get("number") or f.get("to") or "")
    text = sms.texte(f.get("message") or f.get("text"))
    if not numbers or not text:
        return jsonify({"status": "error", "error": "number et message requis", "rejected": bad}), 400
    ids = sms_enqueue(db(), g.consumer["name"], numbers, text)
    return jsonify({"status": "queued", "ids": ids}), 200


@app.route("/sms/recu", methods=["GET", "POST"])
def sms_received():
    """SMS reçus, transmis par le TRB140 (SMS Forwarding HTTP) : ?jeton=…&de=…&texte=… (GET ou POST)."""
    f = {k: v for k, v in request.args.items() if k not in ("jeton", "key")}
    f.update(request.form or {})
    f.update(request.get_json(silent=True) or {})
    de = sms.normaliser(sms.premier(f, sms.CHAMPS_DE)) or sms.premier(f, sms.CHAMPS_DE)[:40]
    if not de:
        return jsonify({"error": "expéditeur absent (de)"}), 400
    text = sms.texte(sms.premier(f, sms.CHAMPS_TEXTE))
    c = db()
    with _lock:
        c.execute("INSERT INTO sms_in (received_at, from_number, text, consumer, source_ip) VALUES (?, ?, ?, ?, ?)",
                  (time.time(), de, text, g.consumer["name"], request.headers.get("X-Real-IP") or request.remote_addr or ""))
        c.commit()
    event("sms-recu", "SMS reçu de %s (%d caractères)" % (de, len(text)))
    return jsonify({"ok": True}), 200


@app.route("/sms/journal", methods=["GET"])
def sms_journal():
    c = db()
    out = [dict(r) for r in c.execute("SELECT * FROM sms_out ORDER BY id DESC LIMIT ?", (min(500, int(request.args.get("limit") or 200)),))]
    inn = [dict(r) for r in c.execute("SELECT * FROM sms_in ORDER BY id DESC LIMIT ?", (min(500, int(request.args.get("limit") or 200)),))]
    counts = {r["status"]: r["n"] for r in c.execute("SELECT status, COUNT(*) AS n FROM sms_out GROUP BY status")}
    host = SMS_RELAY_URL.split("//")[-1].split("/")[0] if SMS_RELAY_URL else ""
    return jsonify({"relay": {"configured": bool(SMS_RELAY_URL and SMS_RELAY_KEY), "host": host, "ui": SMS_RELAY_UI, "trb_ui": SMS_TRB_UI}, "counts": counts, "out": out, "in": inn,
                    "sender": SMS_SENDER.state()}), 200


@app.route("/sms/envoyer", methods=["POST"])
def sms_admin_send():
    """Depuis la tuile (administrateur) : {to, text}."""
    body = request.get_json(silent=True) or {}
    numbers, bad = sms.destinataires(body.get("to"))
    text = sms.texte(body.get("text"))
    if not numbers or not text:
        return jsonify({"error": "destinataire(s) et texte requis", "rejected": bad}), 400
    ids = sms_enqueue(db(), "hub:" + g.user["username"], numbers, text)
    event("sms", "%s : SMS mis en file vers %s" % (g.user["username"], ", ".join(numbers)))
    return jsonify({"queued": ids, "rejected": bad, "segments": sms.segments(text)}), 202


@app.route("/sms/<int:sid>/<verb>", methods=["POST"])
def sms_act(sid, verb):
    if verb not in ("retry", "drop"):
        return jsonify({"error": "geste inconnu"}), 400
    c = db()
    with _lock:
        if verb == "retry":
            n = c.execute("UPDATE sms_out SET status = 'queued', due_at = ?, attempts = 0, last_error = '' WHERE id = ? AND status IN ('failed', 'dropped')", (time.time(), sid)).rowcount
        else:
            n = c.execute("UPDATE sms_out SET status = 'dropped' WHERE id = ? AND status IN ('queued', 'failed')", (sid,)).rowcount
        c.commit()
    return (jsonify({"ok": True}), 200) if n else (jsonify({"error": "SMS introuvable ou dans un état qui ne le permet pas"}), 409)


class SmsSender(object):
    """Fil d'envoi des SMS : relais du TRB140, reprises avec backoff (core.backoff_seconds), abandon après retry_max."""
    def __init__(self):
        self.last_error = ""
        self.last_sent = None

    def state(self):
        return {"last_error": self.last_error, "last_sent": self.last_sent}

    def deliver(self, number, text):
        if not (SMS_RELAY_URL and SMS_RELAY_KEY):
            return False, "relais non configuré (NOTIFY_SMS_RELAY_URL / NOTIFY_SMS_RELAY_KEY)", ""
        import urllib.error
        import urllib.parse
        import urllib.request
        url = SMS_RELAY_URL + "/send?" + urllib.parse.urlencode({"number": number, "message": text, "key": SMS_RELAY_KEY})
        try:
            with urllib.request.urlopen(url, timeout=30) as r:
                body = r.read(400).decode("utf-8", "replace")
                return (r.status == 200), ("" if r.status == 200 else "HTTP %d" % r.status), body[:200]
        except urllib.error.HTTPError as exc:
            return False, "relais : HTTP %d" % exc.code, ""
        except (urllib.error.URLError, OSError) as exc:
            return False, "relais injoignable : %s" % str(getattr(exc, "reason", exc))[:150], ""

    def tick(self, now=None):
        now = now or time.time()
        st = settings_get()
        c = _conn()
        rows = c.execute("SELECT * FROM sms_out WHERE status = 'queued' AND due_at <= ? ORDER BY id LIMIT 10", (now,)).fetchall()
        n = 0
        for r in rows:
            ok, err, reply = self.deliver(r["to_number"], r["text"])
            with _lock:
                if ok:
                    c.execute("UPDATE sms_out SET status = 'sent', sent_at = ?, attempts = attempts + 1, last_error = '', reply = ? WHERE id = ?", (now, reply, r["id"]))
                    self.last_sent, n = now, n + 1
                else:
                    self.last_error = err
                    attempts = r["attempts"] + 1
                    if attempts >= st["retry_max"] or err.startswith("relais : HTTP 4"):
                        c.execute("UPDATE sms_out SET status = 'failed', attempts = ?, last_error = ? WHERE id = ?", (attempts, err, r["id"]))
                    else:
                        c.execute("UPDATE sms_out SET attempts = ?, last_error = ?, due_at = ? WHERE id = ?", (attempts, err, now + core.backoff_seconds(attempts), r["id"]))
                c.commit()
            if not ok:
                break   # relais en panne : on n'insiste pas sur les suivants à ce tour
        c.close()
        return n


SMS_SENDER = SmsSender()


# -- #796 : notifications poussées (Web Push) ----------------------------------------
PUSH_KEYS = push.Keys(os.environ.get("NOTIFY_VAPID_FILE") or os.path.join(os.path.dirname(DB_PATH) or ".", "vapid.pem"))
PUSH_SUBJECT = os.environ.get("NOTIFY_VAPID_SUBJECT", "mailto:supervision@example.org")
PUSH_SEVERITIES = ("info", "warning", "critical")


def push_enqueue(c, severity, title, body, context=None, now=None, only_sub=None):
    """Un message par abonnement dont le seuil est atteint (ou pour un abonnement précis : test) -> nombre enfilé."""
    now = now or time.time()
    payload = json.dumps({"title": str(title or "")[:120], "body": str(body or "").split("\n\n")[0][:300], "severity": severity or "info",
                          "tag": (context or {}).get("kind") or "", "url": "/?view=urgence", "at": now}, ensure_ascii=False)
    n = 0
    for s in c.execute("SELECT id, min_severity FROM push_subs" + (" WHERE id = ?" if only_sub else ""), (only_sub,) if only_sub else ()):
        if only_sub or push.should_push(severity, s["min_severity"]):
            c.execute("INSERT INTO push_out (sub_id, created_at, payload, due_at) VALUES (?, ?, ?, ?)", (s["id"], now, payload, now))
            n += 1
    return n


class PushSender(object):
    def __init__(self, opener=None):
        self.opener = opener
        self.last_error = ""

    def tick(self, now=None):
        now = now or time.time()
        c = _conn()
        rows = c.execute("SELECT o.*, s.endpoint, s.p256dh, s.auth FROM push_out o JOIN push_subs s ON s.id = o.sub_id "
                         "WHERE o.status = 'queued' AND o.due_at <= ? ORDER BY o.id LIMIT 20", (now,)).fetchall()
        n, gone = 0, []
        for r in rows:
            kw = {"opener": self.opener} if self.opener else {}
            st, err = push.send({"endpoint": r["endpoint"], "p256dh": r["p256dh"], "auth": r["auth"]}, json.loads(r["payload"]), PUSH_KEYS, PUSH_SUBJECT, **kw)
            with _lock:
                if st == "ok":
                    c.execute("UPDATE push_out SET status = 'sent', attempts = attempts + 1 WHERE id = ?", (r["id"],))
                    c.execute("UPDATE push_subs SET last_ok = ?, last_error = '' WHERE id = ?", (now, r["sub_id"]))
                    n += 1
                elif st == "gone":
                    c.execute("UPDATE push_out SET status = 'failed', last_error = ? WHERE sub_id = ? AND status = 'queued'", (err, r["sub_id"]))
                    c.execute("DELETE FROM push_subs WHERE id = ?", (r["sub_id"],))
                    gone.append("abonnement push %d supprimé : %s" % (r["sub_id"], err))
                else:
                    self.last_error = err
                    a = r["attempts"] + 1
                    if a >= 5:
                        c.execute("UPDATE push_out SET status = 'failed', attempts = ?, last_error = ? WHERE id = ?", (a, err, r["id"]))
                    else:
                        c.execute("UPDATE push_out SET attempts = ?, last_error = ?, due_at = ? WHERE id = ?", (a, err, now + core.backoff_seconds(a), r["id"]))
                    c.execute("UPDATE push_subs SET last_error = ? WHERE id = ?", (err, r["sub_id"]))
                c.commit()
        c.execute("DELETE FROM push_out WHERE status != 'queued' AND created_at < ?", (now - 7 * 86400,))
        c.commit()
        c.close()
        for msg in gone:      # après la fermeture : event() ouvre sa propre connexion (sinon base verrouillée)
            event("push-gone", msg)
        return n


PUSH_SENDER = PushSender()


@app.route("/push/key", methods=["GET"])
def push_key():
    return jsonify({"publicKey": push.b64u(PUSH_KEYS.public_raw())}), 200


@app.route("/push/subscribe", methods=["POST", "DELETE"])
def push_subscribe():
    b = request.get_json(silent=True) or {}
    sub = b.get("subscription") if isinstance(b.get("subscription"), dict) else {}
    endpoint = str(sub.get("endpoint") or b.get("endpoint") or "")
    if not endpoint.startswith("https://") or len(endpoint) > 1000:
        return jsonify({"error": "abonnement invalide (adresse https du service de push attendue)"}), 400
    c = db()
    if request.method == "DELETE":
        with _lock:
            n = c.execute("DELETE FROM push_subs WHERE endpoint = ?", (endpoint,)).rowcount
            c.commit()
        return jsonify({"ok": True, "deleted": n}), 200
    keys = sub.get("keys") or {}
    p256dh, auth = str(keys.get("p256dh") or ""), str(keys.get("auth") or "")
    try:
        if len(push.b64u_dec(p256dh)) != 65 or len(push.b64u_dec(auth)) != 16:
            raise ValueError
    except Exception:  # noqa: BLE001
        return jsonify({"error": "clés de l'abonnement invalides"}), 400
    sev = b.get("min_severity") if b.get("min_severity") in PUSH_SEVERITIES else "critical"
    label = str(b.get("label") or "")[:80]
    with _lock:
        c.execute("INSERT INTO push_subs (endpoint, p256dh, auth, username, label, min_severity, created_at) VALUES (?, ?, ?, ?, ?, ?, ?) "
                  "ON CONFLICT(endpoint) DO UPDATE SET p256dh = excluded.p256dh, auth = excluded.auth, label = excluded.label, "
                  "min_severity = excluded.min_severity, username = excluded.username",
                  (endpoint, p256dh, auth, g.user["username"], label, sev, time.time()))
        sid = c.execute("SELECT id FROM push_subs WHERE endpoint = ?", (endpoint,)).fetchone()["id"]
        c.commit()
    event("push-sub", "appareil « %s » abonné aux alertes (%s et plus) par %s" % (label or sid, sev, g.user["username"]))
    return jsonify({"ok": True, "id": sid, "min_severity": sev}), 200


@app.route("/push/subscriptions", methods=["GET"])
def push_subs_list():
    rows = [dict(r) for r in db().execute("SELECT id, username, label, min_severity, created_at, last_ok, last_error, substr(endpoint, 1, 40) AS service FROM push_subs ORDER BY id")]
    q = {r["status"]: r["n"] for r in db().execute("SELECT status, COUNT(*) AS n FROM push_out GROUP BY status")}
    return jsonify({"subscriptions": rows, "queue": q, "last_error": PUSH_SENDER.last_error}), 200


@app.route("/push/subscriptions/<int:sid>", methods=["DELETE"])
def push_sub_delete(sid):
    c = db()
    with _lock:
        n = c.execute("DELETE FROM push_subs WHERE id = ?", (sid,)).rowcount
        c.commit()
    return jsonify({"ok": n > 0}), 200


@app.route("/push/test", methods=["POST"])
def push_test():
    b = request.get_json(silent=True) or {}
    c = db()
    sid = b.get("id")
    if not sid and b.get("endpoint"):
        r = c.execute("SELECT id FROM push_subs WHERE endpoint = ?", (str(b["endpoint"]),)).fetchone()
        sid = r["id"] if r else None
    if not sid:
        return jsonify({"error": "abonnement inconnu : activer d'abord les alertes sur cet appareil"}), 400
    with _lock:
        n = push_enqueue(c, "critical", "Test d'alerte du hub", "Si ce message s'affiche, les alertes poussées fonctionnent sur cet appareil (%s)." % g.user["username"],
                         {"kind": "push-test"}, only_sub=int(sid))
        c.commit()
    return jsonify({"ok": n > 0, "message": "message de test envoyé, il doit arriver en quelques secondes"}), 200


# -- fil d'envoi -------------------------------------------------------------------
class Sender(object):
    def __init__(self):
        self.failures = 0
        self.opened_at = None
        self.sent_times = []
        self.last_error = ""
        self.last_sent = None

    def state(self):
        st = settings_get()
        return {"smtp": bool(smtp_config()["host"]), "consecutive_failures": self.failures, "last_error": self.last_error, "last_sent": self.last_sent,
                "breaker_open": core.breaker_open(self.failures, st["breaker_failures"], self.opened_at, time.time(), st["breaker_cooldown"]),
                "sent_last_minute": len([t for t in self.sent_times if time.time() - t < 60])}

    def deliver(self, recipients, subject, body, attachments=None):
        """Envoi SMTP réel -> (ok, erreur)."""
        cfg = smtp_config()
        if not cfg["host"] or not cfg["from"]:
            return False, "SMTP non configuré (Réglages → serveur et expéditeur)"
        msg = EmailMessage()
        msg["From"] = cfg["from"]
        msg["To"] = ", ".join(recipients)
        msg["Subject"] = subject
        msg.set_content(body)
        for f in attachments or []:   # #703
            maintype, _, subtype = f["content_type"].partition("/")
            msg.add_attachment(f["data"], maintype=maintype, subtype=subtype or "octet-stream", filename=f["filename"])
        try:
            port = int(cfg["port"] or 587)
            if cfg["security"] == "ssl":
                smtp = smtplib.SMTP_SSL(cfg["host"], port, timeout=15)
            else:
                smtp = smtplib.SMTP(cfg["host"], port, timeout=15)
            with smtp:
                smtp.ehlo()
                if cfg["security"] == "starttls":
                    smtp.starttls()
                    smtp.ehlo()
                if cfg["user"]:
                    smtp.login(cfg["user"], cfg["password"] or "")
                smtp.send_message(msg)
            return True, ""
        except smtplib.SMTPRecipientsRefused as exc:
            return False, "destinataire(s) refusé(s) par le serveur : " + "; ".join("%s → %s %s" % (k, v[0], v[1].decode("utf-8", "replace") if isinstance(v[1], bytes) else v[1]) for k, v in exc.recipients.items())[:300]
        except smtplib.SMTPAuthenticationError as exc:
            return False, "authentification SMTP refusée (%s)" % str(exc)[:120]
        except (smtplib.SMTPException, OSError) as exc:
            return False, str(exc)[:200]

    def tick(self, now=None):
        now = now or time.time()
        st = settings_get()
        if not st.get("enabled", True):
            return 0
        if core.breaker_open(self.failures, st["breaker_failures"], self.opened_at, now, st["breaker_cooldown"]):
            return 0
        self.sent_times = [t for t in self.sent_times if now - t < 60]
        room = core.allowance(len(self.sent_times), st["max_per_minute"])
        if room <= 0:
            return 0
        c = _conn()
        rows = c.execute("SELECT * FROM queue WHERE status = 'queued' AND due_at <= ? ORDER BY id LIMIT ?", (now, room)).fetchall()
        n = 0
        for r in rows:
            recipients = json.loads(r["recipients"] or "[]")
            subject = core.render_subject(SUBJECT_PREFIX, r["severity"], r["subject"])
            body = r["body"] or ""
            if r["merged"]:
                body += "\n\n(%d notification(s) identique(s) regroupée(s) dans ce message.)" % r["merged"]
            files = [dict(a) for a in c.execute("SELECT filename, content_type, data FROM attachments WHERE queue_id = ?", (r["id"],))]
            ok, err = self.deliver(recipients, subject, body, files) if files else self.deliver(recipients, subject, body)
            with _lock:
                if ok:
                    c.execute("UPDATE queue SET status = 'sent', sent_at = ?, attempts = attempts + 1, last_error = '' WHERE id = ?", (now, r["id"]))
                    c.execute("DELETE FROM attachments WHERE queue_id = ?", (r["id"],))   # #703 : pas de stockage durable
                    self.failures, self.opened_at, self.last_sent = 0, None, now
                    self.sent_times.append(now)
                    n += 1
                else:
                    attempts = r["attempts"] + 1
                    self.failures += 1
                    self.last_error = err
                    if self.failures >= st["breaker_failures"]:
                        self.opened_at = now
                        event("breaker", "disjoncteur SMTP ouvert (%d échecs) : %s" % (self.failures, err))
                    if attempts >= st["retry_max"]:
                        c.execute("UPDATE queue SET status = 'failed', attempts = ?, last_error = ?, reason = 'abandon après %d tentatives' WHERE id = ?" % attempts, (attempts, err, r["id"]))
                    else:
                        c.execute("UPDATE queue SET attempts = ?, last_error = ?, due_at = ? WHERE id = ?", (attempts, err, now + core.backoff_seconds(attempts), r["id"]))
                c.commit()
            if not ok:
                break
        c.close()
        return n


SENDER = Sender()


def _worker():
    while True:
        time.sleep(WORKER_INTERVAL)
        try:
            SENDER.tick()
        except Exception as exc:  # noqa: BLE001
            _log.warning("fil d'envoi : %s", exc)
        try:
            with _lock:
                cb = _conn()
                try:
                    bilan_pauses(cb)   # #853
                finally:
                    cb.close()
        except Exception as exc:  # noqa: BLE001
            _log.warning("bilan des pauses : %s", exc)
        try:
            SMS_SENDER.tick()   # #787
        except Exception as exc:  # noqa: BLE001
            _log.warning("fil d'envoi SMS : %s", exc)
        try:
            PUSH_SENDER.tick()   # #796
        except Exception as exc:  # noqa: BLE001
            _log.warning("fil d'envoi push : %s", exc)


if os.environ.get("NOTIFY_WORKER", "1") == "1":
    threading.Thread(target=_worker, name="notify-sender", daemon=True).start()


if __name__ == "__main__":  # pragma: no cover
    app.run(host="0.0.0.0", port=5000)
