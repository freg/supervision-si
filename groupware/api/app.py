# -*- coding: utf-8 -*-
"""groupware-api (livraison #664, item 115) -- noyau d'un groupware « façon eGroupware » dans le hub : partages (grants),
catégories, liens universels, préférences à quatre niveaux, et génération du fichier de droits de Radicale (CalDAV/CardDAV)
depuis les partages des applications calendar / addressbook. SQLite dans /data ; le fichier de droits est écrit dans
/dav-config (volume partagé avec le service radicale). Les groupes sont développés en membres via LDAP (ldap3) quand
LDAP_URL / LDAP_BIND_DN / LDAP_BIND_PASSWORD / LDAP_GROUPS_DN sont fournis."""
import os, re, json, time, sqlite3, pathlib, logging, threading
from flask import Flask, jsonify, request
from flask_cors import CORS
try:
    from version_endpoint import register_version_route
except ImportError:
    register_version_route = None
import core

app = Flask(__name__); CORS(app)
if register_version_route: register_version_route(app, "groupware")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s groupware: %(message)s"); log = logging.getLogger("groupware")
DATA = pathlib.Path(os.environ.get("GROUPWARE_DATA_DIR", "/data")); DATA.mkdir(parents=True, exist_ok=True)
DB_PATH = str(DATA / "groupware.db")
DAV_CONFIG = pathlib.Path(os.environ.get("DAV_CONFIG_DIR", "/dav-config")); DAV_PUBLIC_URL = os.environ.get("DAV_PUBLIC_URL", "").rstrip("/")
LDAP = {k: os.environ.get(k, "") for k in ("LDAP_URL", "LDAP_BIND_DN", "LDAP_BIND_PASSWORD", "LDAP_GROUPS_DN", "LDAP_USERS_DN")}
_lock = threading.Lock(); _log = []

def db():
    cn = sqlite3.connect(DB_PATH, timeout=30); cn.row_factory = sqlite3.Row; return cn

def init_db():
    cn = db()
    cn.executescript("""
    CREATE TABLE IF NOT EXISTS grants (id INTEGER PRIMARY KEY AUTOINCREMENT, owner TEXT NOT NULL, app TEXT NOT NULL, grantee_kind TEXT NOT NULL, grantee TEXT NOT NULL, rights INTEGER NOT NULL,
        created_at TEXT, created_by TEXT, UNIQUE(owner, app, grantee_kind, grantee));
    CREATE TABLE IF NOT EXISTS categories (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, app TEXT DEFAULT '*', owner TEXT DEFAULT '', parent_id INTEGER DEFAULT 0, color TEXT DEFAULT '', created_at TEXT);
    CREATE TABLE IF NOT EXISTS links (id INTEGER PRIMARY KEY AUTOINCREMENT, app1 TEXT NOT NULL, id1 TEXT NOT NULL, app2 TEXT NOT NULL, id2 TEXT NOT NULL, remark TEXT DEFAULT '', created_by TEXT DEFAULT '', created_at TEXT,
        UNIQUE(app1, id1, app2, id2));
    CREATE TABLE IF NOT EXISTS prefs (id INTEGER PRIMARY KEY AUTOINCREMENT, level TEXT NOT NULL, subject TEXT DEFAULT '', app TEXT DEFAULT '*', key TEXT NOT NULL, value TEXT DEFAULT '', updated_at TEXT, updated_by TEXT,
        UNIQUE(level, subject, app, key));
    CREATE TABLE IF NOT EXISTS journal (id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT, who TEXT, what TEXT);
    """); cn.commit(); cn.close()
init_db()

def now(): return time.strftime("%Y-%m-%dT%H:%M:%S")
def journal(who, what):
    cn = db(); cn.execute("INSERT INTO journal (at, who, what) VALUES (?,?,?)", (now(), who, what)); cn.commit(); cn.close(); log.info("%s : %s", who, what)
def actor(): return (request.get_json(silent=True) or {}).get("actor") or request.args.get("actor") or request.headers.get("X-User") or ""
def groups_arg(): return [g for g in (request.args.get("groups") or "").split(",") if g]

# ---------------------------------------------------------------- LDAP : membres d'un groupe (développement des grants de groupe)
def ldap_members(group):
    if not (LDAP["LDAP_URL"] and LDAP["LDAP_GROUPS_DN"]):
        return []
    try:
        import ldap3
        srv = ldap3.Server(LDAP["LDAP_URL"], get_info=ldap3.NONE)
        with ldap3.Connection(srv, user=LDAP["LDAP_BIND_DN"] or None, password=LDAP["LDAP_BIND_PASSWORD"] or None, auto_bind=True, receive_timeout=10) as c:
            c.search(LDAP["LDAP_GROUPS_DN"], "(&(|(objectClass=groupOfNames)(objectClass=posixGroup)(objectClass=groupOfUniqueNames))(cn=%s))" % ldap3.utils.conv.escape_filter_chars(group),
                     attributes=["member", "memberUid", "uniqueMember"])
            out = set()
            for e in c.entries:
                for attr in ("member", "uniqueMember"):
                    for dn in (e[attr].values if attr in e else []):
                        m = re.match(r"^uid=([^,]+),", str(dn), re.I)
                        if m: out.add(m.group(1))
                if "memberUid" in e: out.update(str(x) for x in e["memberUid"].values)
            return sorted(out)
    except Exception as exc:  # noqa: BLE001
        log.warning("LDAP groupe %s : %s", group, exc); return []

def rebuild_dav_rights():
    """Fichier rights de Radicale depuis les grants calendar / addressbook (appelé après chaque changement de partage)."""
    cn = db(); grants = [dict(r) for r in cn.execute("SELECT * FROM grants WHERE app IN ('calendar','addressbook')")]; cn.close()
    txt = core.radicale_rights(grants, ldap_members)
    try:
        DAV_CONFIG.mkdir(parents=True, exist_ok=True); tmp = DAV_CONFIG / "rights.tmp"; tmp.write_text(txt, encoding="utf-8"); tmp.replace(DAV_CONFIG / "rights")
        return {"ok": True, "rules": txt.count("[grant-"), "path": str(DAV_CONFIG / "rights")}
    except OSError as exc:
        return {"ok": False, "error": str(exc)}

@app.route("/health")
def health(): return jsonify(status="ok", dav=bool(DAV_PUBLIC_URL), ldap=bool(LDAP["LDAP_URL"] and LDAP["LDAP_GROUPS_DN"]))

# ---------------------------------------------------------------- partages (grants)
@app.route("/grants", methods=["GET"])
def grants_list():
    """?owner= (mes partages) ; ?user=&groups= (ce qu'on m'a partagé, avec droits effectifs par propriétaire) ; ?app= filtre."""
    cn = db(); rows = [dict(r) for r in cn.execute("SELECT * FROM grants ORDER BY owner, app, grantee_kind, grantee")]; cn.close()
    app_ = request.args.get("app"); owner = request.args.get("owner"); user = request.args.get("user")
    if app_: rows = [r for r in rows if r["app"] == app_]
    out = {"grants": [dict(r, rights_text=core.rights_text(r["rights"])) for r in rows if (not owner or r["owner"] == owner)], "apps": list(core.APPS), "rights": core.RIGHTS}
    if user:
        groups = groups_arg(); out["effective"] = {a: core.effective(rows, a, user, groups) for a in core.APPS}
        out["received"] = [dict(r, rights_text=core.rights_text(r["rights"])) for r in rows if r["owner"] != user and ((r["grantee_kind"] == "user" and r["grantee"] == user) or (r["grantee_kind"] == "group" and r["grantee"] in groups) or r["grantee_kind"] == "all")]
    return jsonify(out)

@app.route("/grants", methods=["POST"])
def grants_put():
    g, err = core.validate_grant(request.get_json(silent=True) or {})
    if err: return jsonify(error=err), 400
    cn = db()
    cn.execute("INSERT INTO grants (owner, app, grantee_kind, grantee, rights, created_at, created_by) VALUES (?,?,?,?,?,?,?) ON CONFLICT(owner, app, grantee_kind, grantee) DO UPDATE SET rights = excluded.rights",
               (g["owner"], g["app"], g["grantee_kind"], g["grantee"], g["rights"], now(), actor()))
    cn.commit(); row = dict(cn.execute("SELECT * FROM grants WHERE owner = ? AND app = ? AND grantee_kind = ? AND grantee = ?", (g["owner"], g["app"], g["grantee_kind"], g["grantee"])).fetchone()); cn.close()
    journal(actor(), "partage %s/%s -> %s %s : %s" % (g["owner"], g["app"], g["grantee_kind"], g["grantee"], core.rights_text(g["rights"])))
    dav = rebuild_dav_rights() if g["app"] in core.DAV_APPS else None
    return jsonify(grant=dict(row, rights_text=core.rights_text(row["rights"])), dav=dav), 201

@app.route("/grants/<int:gid>", methods=["DELETE"])
def grants_delete(gid):
    cn = db(); row = cn.execute("SELECT * FROM grants WHERE id = ?", (gid,)).fetchone()
    if not row: cn.close(); return jsonify(error="partage inconnu"), 404
    cn.execute("DELETE FROM grants WHERE id = ?", (gid,)); cn.commit(); cn.close()
    journal(actor(), "partage retiré %s/%s -> %s" % (row["owner"], row["app"], row["grantee"]))
    return jsonify(ok=True, dav=rebuild_dav_rights() if row["app"] in core.DAV_APPS else None)

@app.route("/grants/effective", methods=["GET"])
def grants_effective():
    """?app=&user=&groups= -> {owner: masque} : ce que `user` peut faire sur les données de chaque propriétaire."""
    cn = db(); rows = [dict(r) for r in cn.execute("SELECT * FROM grants")]; cn.close()
    eff = core.effective(rows, request.args.get("app") or "", request.args.get("user") or "", groups_arg())
    return jsonify(effective=eff, text={k: core.rights_text(v) for k, v in eff.items()})

# ---------------------------------------------------------------- catégories
@app.route("/categories", methods=["GET"])
def categories_list():
    cn = db(); rows = [dict(r) for r in cn.execute("SELECT * FROM categories ORDER BY app, parent_id, name")]; cn.close()
    app_ = request.args.get("app"); owner = request.args.get("owner")
    if app_: rows = [r for r in rows if r["app"] in (app_, "*")]
    if owner is not None: rows = [r for r in rows if r["owner"] in (owner, "")]
    return jsonify(categories=rows)

@app.route("/categories", methods=["POST"])
def categories_create():
    b = request.get_json(silent=True) or {}; name = str(b.get("name") or "").strip()
    if not name or len(name) > 80: return jsonify(error="nom requis (80 car. max)"), 400
    app_ = str(b.get("app") or "*")
    if app_ != "*" and app_ not in core.APPS: return jsonify(error="app : * ou " + ", ".join(core.APPS)), 400
    color = str(b.get("color") or "")
    if color and not re.match(r"^#[0-9A-Fa-f]{6}$", color): return jsonify(error="color : #rrggbb"), 400
    cn = db(); cur = cn.execute("INSERT INTO categories (name, app, owner, parent_id, color, created_at) VALUES (?,?,?,?,?,?)", (name, app_, str(b.get("owner") or ""), int(b.get("parent_id") or 0), color, now()))
    cn.commit(); row = dict(cn.execute("SELECT * FROM categories WHERE id = ?", (cur.lastrowid,)).fetchone()); cn.close()
    return jsonify(category=row), 201

@app.route("/categories/<int:cid>", methods=["PUT", "DELETE"])
def categories_update(cid):
    cn = db(); row = cn.execute("SELECT * FROM categories WHERE id = ?", (cid,)).fetchone()
    if not row: cn.close(); return jsonify(error="catégorie inconnue"), 404
    if request.method == "DELETE":
        cn.execute("DELETE FROM categories WHERE id = ? OR parent_id = ?", (cid, cid)); cn.commit(); cn.close(); return jsonify(ok=True)
    b = request.get_json(silent=True) or {}
    cn.execute("UPDATE categories SET name = ?, color = ?, parent_id = ? WHERE id = ?", (str(b.get("name") or row["name"])[:80], str(b.get("color", row["color"]) or ""), int(b.get("parent_id", row["parent_id"]) or 0), cid))
    cn.commit(); row = dict(cn.execute("SELECT * FROM categories WHERE id = ?", (cid,)).fetchone()); cn.close()
    return jsonify(category=row)

# ---------------------------------------------------------------- liens universels
@app.route("/links", methods=["GET"])
def links_list():
    """?app=&id= -> liens dans les deux sens, l'autre bout normalisé dans `other`."""
    a, i = request.args.get("app") or "", request.args.get("id") or ""
    cn = db(); rows = [dict(r) for r in cn.execute("SELECT * FROM links WHERE (app1 = ? AND id1 = ?) OR (app2 = ? AND id2 = ?) ORDER BY id DESC", (a, i, a, i))]; cn.close()
    for r in rows: r["other"] = {"app": r["app2"], "id": r["id2"]} if (r["app1"], r["id1"]) == (a, i) else {"app": r["app1"], "id": r["id1"]}
    return jsonify(links=rows)

@app.route("/links", methods=["POST"])
def links_create():
    b = request.get_json(silent=True) or {}
    ends = [(str(b.get(k) or "").strip()) for k in ("app1", "id1", "app2", "id2")]
    if not all(ends) or any(len(x) > 120 for x in ends): return jsonify(error="app1, id1, app2, id2 requis"), 400
    if (ends[0], ends[1]) == (ends[2], ends[3]): return jsonify(error="un objet ne se lie pas à lui-même"), 400
    cn = db()
    cn.execute("INSERT OR IGNORE INTO links (app1, id1, app2, id2, remark, created_by, created_at) VALUES (?,?,?,?,?,?,?)", (*ends, str(b.get("remark") or "")[:200], actor(), now()))
    cn.commit(); row = dict(cn.execute("SELECT * FROM links WHERE app1 = ? AND id1 = ? AND app2 = ? AND id2 = ?", tuple(ends)).fetchone()); cn.close()
    return jsonify(link=row), 201

@app.route("/links/<int:lid>", methods=["DELETE"])
def links_delete(lid):
    cn = db(); n = cn.execute("DELETE FROM links WHERE id = ?", (lid,)).rowcount; cn.commit(); cn.close()
    return (jsonify(ok=True), 200) if n else (jsonify(error="lien inconnu"), 404)

# ---------------------------------------------------------------- préférences
@app.route("/prefs", methods=["GET"])
def prefs_get():
    """?app=&user=&groups= -> préférences résolues ; ?raw=1 -> toutes les lignes (administration)."""
    cn = db(); rows = [dict(r) for r in cn.execute("SELECT * FROM prefs ORDER BY level, subject, app, key")]; cn.close()
    if request.args.get("raw"): return jsonify(prefs=rows, levels=["default", "group", "user", "forced"])
    return jsonify(prefs=core.resolve_prefs(rows, request.args.get("app") or "*", request.args.get("user") or "", groups_arg()))

@app.route("/prefs", methods=["PUT"])
def prefs_put():
    b = request.get_json(silent=True) or {}; level = str(b.get("level") or "user"); key = str(b.get("key") or "").strip()
    if level not in ("default", "group", "user", "forced"): return jsonify(error="level : default, group, user, forced"), 400
    if not re.match(r"^[A-Za-z0-9_.-]{1,60}$", key): return jsonify(error="key invalide"), 400
    subject = str(b.get("subject") or "") if level in ("group", "user") else ""
    if level in ("group", "user") and not subject: return jsonify(error="subject (utilisateur ou groupe) requis"), 400
    app_ = str(b.get("app") or "*")
    cn = db()
    cn.execute("INSERT INTO prefs (level, subject, app, key, value, updated_at, updated_by) VALUES (?,?,?,?,?,?,?) ON CONFLICT(level, subject, app, key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at, updated_by = excluded.updated_by",
               (level, subject, app_, key, json.dumps(b.get("value")) if not isinstance(b.get("value"), str) else b.get("value"), now(), actor()))
    cn.commit(); cn.close()
    if level in ("forced", "default"): journal(actor(), "préférence %s %s/%s = %s" % (level, app_, key, b.get("value")))
    return jsonify(ok=True)

@app.route("/prefs", methods=["DELETE"])
def prefs_delete():
    b = request.get_json(silent=True) or {}
    cn = db(); n = cn.execute("DELETE FROM prefs WHERE level = ? AND subject = ? AND app = ? AND key = ?", (str(b.get("level") or ""), str(b.get("subject") or ""), str(b.get("app") or "*"), str(b.get("key") or ""))).rowcount; cn.commit(); cn.close()
    return jsonify(ok=bool(n))

# ---------------------------------------------------------------- CalDAV / CardDAV (Radicale)
@app.route("/dav/me", methods=["GET"])
def dav_me():
    """?user= -> URLs CalDAV/CardDAV de l'utilisateur et consignes clients."""
    user = request.args.get("user") or ""
    if not core.NAME_RE.match(user): return jsonify(error="user requis"), 400
    if not DAV_PUBLIC_URL: return jsonify(error="DAV_PUBLIC_URL non configurée (service radicale absent ?)"), 503
    return jsonify(dict(core.dav_urls(DAV_PUBLIC_URL, user), user=user, naming={"calendar": "agenda-…", "addressbook": "contacts-…"},
                        clients={"thunderbird": "Agenda → Nouveau calendrier → Sur le réseau → CalDAV, emplacement = URL du principal, identifiants LDAP ; Carnet d'adresses → Nouveau carnet CardDAV, même URL",
                                 "davx5": "Compte → Connexion avec une URL et un nom d'utilisateur (URL du principal), identifiants LDAP ; agendas et carnets détectés",
                                 "ios_macos": "Réglages → Comptes → Ajouter un compte CalDAV / CardDAV : serveur = hôte du hub, utilisateur LDAP, chemin = URL du principal (avancé)"}))

@app.route("/dav/rights/rebuild", methods=["POST"])
def dav_rebuild(): return jsonify(rebuild_dav_rights())

@app.route("/journal", methods=["GET"])
def journal_route():
    cn = db(); rows = [dict(r) for r in cn.execute("SELECT * FROM journal ORDER BY id DESC LIMIT 200")]; cn.close(); return jsonify(journal=rows)

@app.route("/logs", methods=["GET"])
def logs_route():
    cn = db(); rows = [dict(r) for r in cn.execute("SELECT at, who, what FROM journal ORDER BY id DESC LIMIT 100")]; cn.close()
    return jsonify(lines=["%s %s %s" % (r["at"], r["who"], r["what"]) for r in rows])
