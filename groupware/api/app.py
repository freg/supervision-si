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
import core, vcard
from carddav import Dav, DavError, new_uid, COLL_RE

app = Flask(__name__); CORS(app)
if register_version_route: register_version_route(app, "groupware")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s groupware: %(message)s"); log = logging.getLogger("groupware")
DATA = pathlib.Path(os.environ.get("GROUPWARE_DATA_DIR", "/data")); DATA.mkdir(parents=True, exist_ok=True)
DB_PATH = str(DATA / "groupware.db")
DAV_CONFIG = pathlib.Path(os.environ.get("DAV_CONFIG_DIR", "/dav-config")); DAV_PUBLIC_URL = os.environ.get("DAV_PUBLIC_URL", "").rstrip("/")
LDAP = {k: os.environ.get(k, "") for k in ("LDAP_URL", "LDAP_BIND_DN", "LDAP_BIND_PASSWORD", "LDAP_GROUPS_DN", "LDAP_USERS_DN")}
DAV_INTERNAL_URL = os.environ.get("DAV_INTERNAL_URL", "http://radicale:5232").rstrip("/")
DAV_SERVICE_USER, DAV_SERVICE_PASSWORD = os.environ.get("GROUPWARE_DAV_SERVICE_USER", ""), os.environ.get("GROUPWARE_DAV_SERVICE_PASSWORD", "")
def dav(): return Dav(DAV_INTERNAL_URL, DAV_SERVICE_USER, DAV_SERVICE_PASSWORD)
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
    txt = core.radicale_rights(grants, ldap_members, service_user=DAV_SERVICE_USER)
    try:
        DAV_CONFIG.mkdir(parents=True, exist_ok=True); tmp = DAV_CONFIG / "rights.tmp"; tmp.write_text(txt, encoding="utf-8"); tmp.replace(DAV_CONFIG / "rights")
        return {"ok": True, "rules": txt.count("[grant-"), "path": str(DAV_CONFIG / "rights")}
    except OSError as exc:
        return {"ok": False, "error": str(exc)}

@app.route("/health")
def health(): return jsonify(status="ok", dav=bool(DAV_PUBLIC_URL), ldap=bool(LDAP["LDAP_URL"] and LDAP["LDAP_GROUPS_DN"]), contacts=bool(DAV_SERVICE_USER))

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

# ---------------------------------------------------------------- #665 : carnet d'adresses (CardDAV via le compte de service, partages vérifiés ici)
def _rights_on(app_, user, groups, owner):
    cn = db(); rows = [dict(r) for r in cn.execute("SELECT * FROM grants WHERE app = ?", (app_,))]; cn.close()
    return core.effective(rows, app_, user, groups).get(owner, 0)

def _need_service():
    if not DAV_SERVICE_USER: return jsonify(error="GROUPWARE_DAV_SERVICE_USER / PASSWORD absents : carnet dans le hub indisponible (les clients CardDAV fonctionnent)"), 503
    return None

@app.route("/addressbooks", methods=["GET"])
def addressbooks():
    """?user=&groups= -> mes carnets + ceux partagés avec moi (droits effectifs), via le serveur CardDAV."""
    err = _need_service()
    if err: return err
    user, groups = request.args.get("user") or "", groups_arg()
    if not core.NAME_RE.match(user): return jsonify(error="user requis"), 400
    eff = {}
    cn = db(); rows = [dict(r) for r in cn.execute("SELECT * FROM grants WHERE app = 'addressbook'")]; cn.close()
    eff = core.effective(rows, "addressbook", user, groups)
    out = []
    try:
        d = dav()
        for owner, mask in sorted(eff.items(), key=lambda x: (x[0] != user, x[0])):
            if not mask & core.RIGHTS["r"]: continue
            for c in d.list_collections(owner):
                if c["kind"] == "addressbook" and re.match(r"^(contacts|carnet|ab|addressbook)", c["name"], re.I):
                    out.append(dict(c, owner=owner, rights=core.rights_text(mask), mine=owner == user))
    except DavError as e:
        return jsonify(error="serveur CardDAV : %s" % e), 502
    return jsonify(addressbooks=out)

@app.route("/addressbooks", methods=["POST"])
def addressbook_create():
    err = _need_service()
    if err: return err
    b = request.get_json(silent=True) or {}; user = str(b.get("user") or ""); name = re.sub(r"[^A-Za-z0-9._-]", "-", str(b.get("name") or "")).strip("-").lower()
    if not core.NAME_RE.match(user) or not name: return jsonify(error="user et name requis"), 400
    coll = name if re.match(r"^(contacts|carnet|ab|addressbook)", name) else "contacts-" + name
    if not COLL_RE.match(coll): return jsonify(error="nom invalide"), 400
    try: c = dav().create_collection(user, coll, "addressbook", str(b.get("displayname") or b.get("name") or coll))
    except DavError as e: return jsonify(error="serveur CardDAV : %s" % e), 502
    journal(user, "carnet créé %s/%s" % (user, coll))
    return jsonify(addressbook=dict(c, owner=user, rights="raedp", mine=True)), 201

@app.route("/contacts", methods=["GET"])
def contacts_list():
    """?user=&groups=&q=&owner=&book= -> contacts de tous les carnets lisibles (ou d'un seul), filtrés par q."""
    err = _need_service()
    if err: return err
    user, groups, q = request.args.get("user") or "", groups_arg(), request.args.get("q") or ""
    only_owner, only_book = request.args.get("owner"), request.args.get("book")
    if not core.NAME_RE.match(user): return jsonify(error="user requis"), 400
    cn = db(); rows = [dict(r) for r in cn.execute("SELECT * FROM grants WHERE app = 'addressbook'")]; cn.close()
    eff = core.effective(rows, "addressbook", user, groups)
    out = []
    try:
        d = dav()
        for owner, mask in eff.items():
            if not mask & core.RIGHTS["r"] or (only_owner and owner != only_owner): continue
            for c in d.list_collections(owner):
                if c["kind"] != "addressbook" or (only_book and c["name"] != only_book): continue
                for it in d.list_items(owner, c["name"]):
                    card = vcard.parse(it["data"]); card["uid"] = card["uid"] or it["uid"]
                    if vcard.matches(card, q):
                        out.append(dict(card, owner=owner, book=c["name"], book_name=c["displayname"], etag=it["etag"], rights=core.rights_text(mask), extra=len(card["extra"])))
    except DavError as e:
        return jsonify(error="serveur CardDAV : %s" % e), 502
    out.sort(key=lambda c: (c["fn"] or "").lower())
    return jsonify(contacts=out, total=len(out))

@app.route("/contacts", methods=["POST"])
def contacts_create():
    """{user, groups, owner, book, contact: {...}} -> création (droit a sur le carnet du propriétaire)."""
    err = _need_service()
    if err: return err
    b = request.get_json(silent=True) or {}; user, owner, book = str(b.get("user") or ""), str(b.get("owner") or b.get("user") or ""), str(b.get("book") or "")
    if not (core.NAME_RE.match(user) and core.NAME_RE.match(owner) and COLL_RE.match(book)): return jsonify(error="user, owner, book requis"), 400
    if not _rights_on("addressbook", user, b.get("groups") or [], owner) & core.RIGHTS["a"]: return jsonify(error="pas le droit d'ajouter dans le carnet de %s" % owner), 403
    c = dict(b.get("contact") or {}); c["uid"] = new_uid()
    try: r = dav().put_item(owner, book, c["uid"], vcard.serialize(c))
    except DavError as e: return jsonify(error="serveur CardDAV : %s" % e), 502
    return jsonify(contact=dict(vcard.parse(vcard.serialize(c)), owner=owner, book=book, etag=r["etag"])), 201

@app.route("/contacts/<owner>/<book>/<uid>", methods=["PUT", "DELETE"])
def contacts_update(owner, book, uid):
    err = _need_service()
    if err: return err
    b = request.get_json(silent=True) or {}; user = str(b.get("user") or request.args.get("user") or "")
    groups = b.get("groups") or groups_arg()
    if not (core.NAME_RE.match(user) and core.NAME_RE.match(owner) and COLL_RE.match(book) and re.match(r"^[A-Za-z0-9._@-]{1,120}$", uid)): return jsonify(error="paramètres invalides"), 400
    need = core.RIGHTS["d"] if request.method == "DELETE" else core.RIGHTS["e"]
    if not _rights_on("addressbook", user, groups, owner) & need: return jsonify(error="droit insuffisant sur le carnet de %s" % owner), 403
    try:
        d = dav()
        if request.method == "DELETE":
            d.delete_item(owner, book, uid); return jsonify(ok=True)
        current = next((it for it in d.list_items(owner, book) if it["uid"] == uid), None)
        if not current: return jsonify(error="contact inconnu"), 404
        old = vcard.parse(current["data"]); c = dict(old, **{k: v for k, v in (b.get("contact") or {}).items() if k != "extra"}); c["uid"] = old["uid"] or uid
        r = d.put_item(owner, book, uid, vcard.serialize(c))
        return jsonify(contact=dict(vcard.parse(vcard.serialize(c)), owner=owner, book=book, etag=r["etag"]))
    except DavError as e:
        return jsonify(error="serveur CardDAV : %s" % e), 502

@app.route("/journal", methods=["GET"])
def journal_route():
    cn = db(); rows = [dict(r) for r in cn.execute("SELECT * FROM journal ORDER BY id DESC LIMIT 200")]; cn.close(); return jsonify(journal=rows)

@app.route("/logs", methods=["GET"])
def logs_route():
    cn = db(); rows = [dict(r) for r in cn.execute("SELECT at, who, what FROM journal ORDER BY id DESC LIMIT 100")]; cn.close()
    return jsonify(lines=["%s %s %s" % (r["at"], r["who"], r["what"]) for r in rows])
