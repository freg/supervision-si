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
import core, vcard, ical
from carddav import Dav, DavError, new_uid, COLL_RE

app = Flask(__name__); CORS(app)
if register_version_route: register_version_route(app, "groupware")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s groupware: %(message)s"); log = logging.getLogger("groupware")
DATA = pathlib.Path(os.environ.get("GROUPWARE_DATA_DIR", "/data")); DATA.mkdir(parents=True, exist_ok=True)
DB_PATH = str(DATA / "groupware.db")
DAV_CONFIG = pathlib.Path(os.environ.get("DAV_CONFIG_DIR", "/dav-config")); DAV_PUBLIC_URL = os.environ.get("DAV_PUBLIC_URL", "").rstrip("/")
LDAP = {k: os.environ.get(k, "") for k in ("LDAP_URL", "LDAP_BIND_DN", "LDAP_BIND_PASSWORD", "LDAP_GROUPS_DN", "LDAP_USERS_DN")}
DAV_INTERNAL_URL = os.environ.get("DAV_INTERNAL_URL", "http://radicale:5232").rstrip("/")
# compte de service DAV : d'abord le coffre des accès (#498 : entrée « groupware-dav », gérée depuis la tuile Accès d'équipements),
# sinon les variables d'environnement. Mis en cache 60 s ; le nom du compte sert aussi à la règle [service] des droits Radicale.
CREDENTIALS_API_URL = os.environ.get("CREDENTIALS_API_URL", "http://credentials-api:5000").rstrip("/"); CREDENTIALS_TOKEN = os.environ.get("CREDENTIALS_INTERNAL_TOKEN", "").strip()
DAV_CREDENTIAL_NAME = os.environ.get("GROUPWARE_DAV_CREDENTIAL", "groupware-dav")
_dav_cred = {"until": 0.0, "user": "", "password": "", "source": ""}

def dav_credentials():
    """(user, password, source) : coffre si l'entrée existe, sinon .env ; ("", "", "") si rien."""
    if _dav_cred["until"] > time.monotonic(): return _dav_cred["user"], _dav_cred["password"], _dav_cred["source"]
    user, pw, src = os.environ.get("GROUPWARE_DAV_SERVICE_USER", ""), os.environ.get("GROUPWARE_DAV_SERVICE_PASSWORD", ""), "env" if os.environ.get("GROUPWARE_DAV_SERVICE_USER") else ""
    if CREDENTIALS_TOKEN:
        try:
            import urllib.request
            req = urllib.request.Request("%s/credentials/reveal/%s" % (CREDENTIALS_API_URL, DAV_CREDENTIAL_NAME), headers={"X-Credentials-Token": CREDENTIALS_TOKEN, "X-Credentials-Consumer": "groupware-api"})
            with urllib.request.urlopen(req, timeout=5) as r:
                d = json.loads(r.read().decode("utf-8") or "{}")
            if d.get("username") and d.get("password"): user, pw, src = d["username"], d["password"], "coffre"
        except Exception as exc:  # noqa: BLE001
            if "404" not in str(exc): log.warning("coffre des accès : %s", exc)
    _dav_cred.update(until=time.monotonic() + 60, user=user, password=pw, source=src)
    return user, pw, src

def dav():
    u, p, _ = dav_credentials(); return Dav(DAV_INTERNAL_URL, u, p)
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
    CREATE TABLE IF NOT EXISTS infolog (id INTEGER PRIMARY KEY AUTOINCREMENT, owner TEXT NOT NULL, type TEXT NOT NULL, title TEXT NOT NULL, description TEXT DEFAULT '', status TEXT DEFAULT 'open',
        priority INTEGER DEFAULT 1, due TEXT DEFAULT '', start TEXT DEFAULT '', responsible TEXT DEFAULT '', private INTEGER DEFAULT 0, categories TEXT DEFAULT '', created_by TEXT, created_at TEXT, updated_at TEXT, done_at TEXT DEFAULT '');
    CREATE TABLE IF NOT EXISTS resources (id INTEGER PRIMARY KEY AUTOINCREMENT, slug TEXT UNIQUE NOT NULL, name TEXT NOT NULL, kind TEXT DEFAULT 'salle', capacity INTEGER DEFAULT 0, notes TEXT DEFAULT '', created_at TEXT);
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
    txt = core.radicale_rights(grants, ldap_members, service_user=dav_credentials()[0])
    try:
        DAV_CONFIG.mkdir(parents=True, exist_ok=True); tmp = DAV_CONFIG / "rights.tmp"; tmp.write_text(txt, encoding="utf-8"); tmp.replace(DAV_CONFIG / "rights")
        return {"ok": True, "rules": txt.count("[grant-"), "path": str(DAV_CONFIG / "rights")}
    except OSError as exc:
        return {"ok": False, "error": str(exc)}

@app.route("/health")
def health():
    u, _, src = dav_credentials()
    return jsonify(status="ok", dav=bool(DAV_PUBLIC_URL), ldap=bool(LDAP["LDAP_URL"] and LDAP["LDAP_GROUPS_DN"]), contacts=bool(u), service_source=src, credential_name=DAV_CREDENTIAL_NAME)

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
    if not dav_credentials()[0]: return jsonify(error="compte de service DAV absent : entrée « %s » du coffre des accès (tuile Accès d'équipements) ou GROUPWARE_DAV_SERVICE_USER / PASSWORD" % DAV_CREDENTIAL_NAME), 503
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

# ---------------------------------------------------------------- #666 : agenda (CalDAV via le compte de service), disponibilités, ressources
RESOURCE_OWNER = os.environ.get("GROUPWARE_RESOURCE_OWNER", "ressources")   # principal Radicale qui porte les agendas des ressources (salles, matériel)
CAL_RE = re.compile(r"^(agenda|cal|calendar)", re.I)

def _readable_calendars(d, user, groups):
    """[(owner, collection, droits, kind)] : mes agendas, ceux partagés (droits effectifs), ceux des ressources (lecture pour tous)."""
    cn = db(); rows = [dict(r) for r in cn.execute("SELECT * FROM grants WHERE app = 'calendar'")]; cn.close()
    eff = core.effective(rows, "calendar", user, groups)
    out = []
    for owner, mask in sorted(eff.items(), key=lambda x: (x[0] != user, x[0])):
        if not mask & core.RIGHTS["r"]: continue
        for c in d.list_collections(owner):
            if c["kind"] == "calendar" and CAL_RE.match(c["name"]): out.append(dict(c, owner=owner, rights=core.rights_text(mask), mine=owner == user, resource=False))
    cn = db(); res = {("agenda-" + r["slug"]): dict(r) for r in cn.execute("SELECT * FROM resources")}; cn.close()
    if res:
        try:
            for c in d.list_collections(RESOURCE_OWNER):
                if c["name"] in res: out.append(dict(c, owner=RESOURCE_OWNER, rights="ra", mine=False, resource=True, displayname=res[c["name"]]["name"], kind="calendar", resource_info=res[c["name"]]))
        except DavError: pass
    return out

def _events_in(d, owner, book, start, end):
    evs = []
    for it in d.list_items(owner, book):
        try: ev = ical.parse(it["data"])
        except Exception as exc:  # noqa: BLE001
            log.warning("ics illisible %s/%s/%s : %s", owner, book, it["uid"], exc); continue
        if not ev: continue
        ev["uid"] = ev["uid"] or it["uid"]; ev["etag"] = it["etag"]; evs.append(ev)
    return evs

@app.route("/calendars", methods=["GET"])
def calendars():
    err = _need_service()
    if err: return err
    user = request.args.get("user") or ""
    if not core.NAME_RE.match(user): return jsonify(error="user requis"), 400
    try: cals = _readable_calendars(dav(), user, groups_arg())
    except DavError as e: return jsonify(error="serveur CalDAV : %s" % e), 502
    return jsonify(calendars=[{k: v for k, v in c.items() if k != "resource_info"} for c in cals])

@app.route("/calendars", methods=["POST"])
def calendar_create():
    err = _need_service()
    if err: return err
    b = request.get_json(silent=True) or {}; user = str(b.get("user") or ""); name = re.sub(r"[^A-Za-z0-9._-]", "-", str(b.get("name") or "")).strip("-").lower()
    if not core.NAME_RE.match(user) or not name: return jsonify(error="user et name requis"), 400
    coll = name if CAL_RE.match(name) else "agenda-" + name
    if not COLL_RE.match(coll): return jsonify(error="nom invalide"), 400
    try: c = dav().create_collection(user, coll, "calendar", str(b.get("displayname") or b.get("name") or coll))
    except DavError as e: return jsonify(error="serveur CalDAV : %s" % e), 502
    journal(user, "agenda créé %s/%s" % (user, coll))
    return jsonify(calendar=dict(c, owner=user, rights="raedp", mine=True, resource=False)), 201

@app.route("/events", methods=["GET"])
def events_list():
    """?user=&groups=&from=&to=&owner=&book= -> occurrences (récurrences développées) de tous les agendas lisibles dans la fenêtre."""
    err = _need_service()
    if err: return err
    user, groups = request.args.get("user") or "", groups_arg()
    if not core.NAME_RE.match(user): return jsonify(error="user requis"), 400
    try: ws, we = ical.parse_dt(request.args.get("from") or ""), ical.parse_dt(request.args.get("to") or "")
    except Exception: return jsonify(error="from / to : dates ISO requises"), 400
    only_owner, only_book = request.args.get("owner"), request.args.get("book")
    out = []
    try:
        d = dav()
        for c in _readable_calendars(d, user, groups):
            if (only_owner and c["owner"] != only_owner) or (only_book and c["name"] != only_book): continue
            for ev in _events_in(d, c["owner"], c["name"], ws, we):
                for s, e in ical.occurrences(ev, ws, we):
                    mine = next((a["partstat"] for a in ev.get("attendees") or [] if a["name"] == user), "")
                    out.append(ical.public(ev, s, e, owner=c["owner"], book=c["name"], book_name=c["displayname"], rights=c["rights"], resource=c["resource"], etag=ev["etag"],
                                           invite_from=_invite_from(ev), my_partstat=mine))
    except DavError as e:
        return jsonify(error="serveur CalDAV : %s" % e), 502
    out.sort(key=lambda x: x["start"])
    return jsonify(events=out, total=len(out))

@app.route("/events", methods=["POST"])
def events_create():
    """{user, groups, owner, book, event} ; ressource (owner = ressources) : réservation ouverte à tous, refusée en cas de chevauchement (409)."""
    err = _need_service()
    if err: return err
    b = request.get_json(silent=True) or {}; user, owner, book = str(b.get("user") or ""), str(b.get("owner") or b.get("user") or ""), str(b.get("book") or "")
    if not (core.NAME_RE.match(user) and core.NAME_RE.match(owner) and COLL_RE.match(book)): return jsonify(error="user, owner, book requis"), 400
    is_res = owner == RESOURCE_OWNER
    if not is_res and not _rights_on("calendar", user, b.get("groups") or [], owner) & core.RIGHTS["a"]: return jsonify(error="pas le droit d'ajouter dans l'agenda de %s" % owner), 403
    ev, err = ical.validate(b.get("event") or {})
    if err: return jsonify(error=err), 400
    ev["uid"] = new_uid(); ev["extra"] = ["X-SI-BOOKED-BY:" + user] if is_res else []
    if is_res: ev["attendees"] = []
    if ev["attendees"]: ev["organizer"] = user
    try:
        d = dav()
        if is_res:
            hits = ical.conflicts(ev, _events_in(d, owner, book, ev["start"], ev["end"]))
            if hits: return jsonify(error="ressource déjà réservée : %s" % ", ".join("%s (%s)" % (h["title"], ical.iso(h["start"])) for h in hits[:3]), conflicts=[ical.public(h) for h in hits]), 409
        r = d.put_item(owner, book, ev["uid"], ical.serialize(ev), kind="ics")
        if ev["attendees"]: _sync_invites(d, owner, book, ev)
    except DavError as e: return jsonify(error="serveur CalDAV : %s" % e), 502
    journal(user, "%s %s/%s : %s" % ("réservation" if is_res else "événement", owner, book, ev["title"]))
    return jsonify(event=ical.public(ev, owner=owner, book=book, etag=r["etag"])), 201

@app.route("/events/<owner>/<book>/<uid>", methods=["PUT", "DELETE"])
def events_update(owner, book, uid):
    err = _need_service()
    if err: return err
    b = request.get_json(silent=True) or {}; user = str(b.get("user") or request.args.get("user") or ""); groups = b.get("groups") or groups_arg()
    if not (core.NAME_RE.match(user) and core.NAME_RE.match(owner) and COLL_RE.match(book) and re.match(r"^[A-Za-z0-9._@-]{1,120}$", uid)): return jsonify(error="paramètres invalides"), 400
    is_res = owner == RESOURCE_OWNER
    try:
        d = dav()
        current = next((ev for ev in _events_in(d, owner, book, None, None) if ev["uid"] == uid), None)
        if not current: return jsonify(error="événement inconnu"), 404
        if is_res:
            booker = next((x.split(":", 1)[1] for x in current.get("extra") or [] if x.upper().startswith("X-SI-BOOKED-BY:")), "")
            if booker != user and not (b.get("admin") or request.args.get("admin")): return jsonify(error="réservation faite par %s" % (booker or "?")), 403
        else:
            need = core.RIGHTS["d"] if request.method == "DELETE" else core.RIGHTS["e"]
            if not _rights_on("calendar", user, groups, owner) & need: return jsonify(error="droit insuffisant sur l'agenda de %s" % owner), 403
        if request.method == "DELETE":
            d.delete_item(owner, book, uid, kind="ics"); journal(user, "supprimé %s/%s/%s" % (owner, book, uid))
            inv = _invite_from(current)
            if inv:                                                   # supprimer sa copie = décliner
                o, _, bk = inv.partition("/")
                try: _set_partstat(d, o, bk, uid, owner, "DECLINED")
                except DavError as e: log.warning("déclin non propagé : %s", e)
            elif current.get("attendees"):
                _sync_invites(d, owner, book, dict(current, attendees=[]), prev=current)
            return jsonify(ok=True)
        merged = {k: v for k, v in (b.get("event") or {}).items()}
        body = dict(ical.public(current), **merged)                   # champs non fournis conservés (rrule comprise)
        ev, err = ical.validate(body)
        if err: return jsonify(error=err), 400
        ev["uid"] = uid; ev["extra"] = current.get("extra") or []
        if is_res: ev["attendees"] = []
        if "attendees" in merged:                                     # réponses déjà données conservées
            old = {a["name"]: a["partstat"] for a in current.get("attendees") or []}
            for a in ev["attendees"]: a["partstat"] = old.get(a["name"], a["partstat"])
        if ev["attendees"] and not ev.get("organizer"): ev["organizer"] = current.get("organizer") or user
        if is_res:
            hits = ical.conflicts(ev, _events_in(d, owner, book, ev["start"], ev["end"]))
            if hits: return jsonify(error="ressource déjà réservée sur ce créneau", conflicts=[ical.public(h) for h in hits]), 409
        r = d.put_item(owner, book, uid, ical.serialize(ev), kind="ics")
        if (ev["attendees"] or current.get("attendees")) and not _invite_from(current): _sync_invites(d, owner, book, ev, prev=current)
        return jsonify(event=ical.public(ev, owner=owner, book=book, etag=r["etag"]))
    except DavError as e:
        return jsonify(error="serveur CalDAV : %s" % e), 502


# ---------------------------------------------------------------- #669 : invitations (copie dans l'agenda de chaque participant, réponses) — Radicale n'a pas de scheduling
INVITE_TAG = "X-SI-INVITE-FROM:"

def _invite_from(ev):
    return next((x.split(":", 1)[1] for x in ev.get("extra") or [] if x.upper().startswith(INVITE_TAG)), "")

def _find_event(d, user, uid):
    """Cherche uid dans les agendas de user -> (collection, événement) ou (None, None)."""
    for c in d.list_collections(user):
        if c["kind"] != "calendar" or not CAL_RE.match(c["name"]): continue
        ev = next((e for e in _events_in(d, user, c["name"], None, None) if e["uid"] == uid), None)
        if ev: return c["name"], ev
    return None, None

def _default_calendar(d, user):
    cals = [c["name"] for c in d.list_collections(user) if c["kind"] == "calendar" and CAL_RE.match(c["name"])]
    if cals: return "agenda" if "agenda" in cals else sorted(cals)[0]
    d.create_collection(user, "agenda", "calendar", "Agenda"); return "agenda"

def _sync_invites(d, owner, book, ev, prev=None):
    """Après écriture de l'événement maître (owner/book) : copie à jour chez chaque participant (sa réponse conservée), retrait chez ceux enlevés."""
    names = [a["name"] for a in ev.get("attendees") or []]
    for a in ev.get("attendees") or []:
        if a["name"] == owner: continue
        try:
            coll, cur = _find_event(d, a["name"], ev["uid"])
            if not coll: coll = _default_calendar(d, a["name"])
            copy = dict(ev, extra=[INVITE_TAG + "%s/%s" % (owner, book)], transparent=ev.get("transparent") or a.get("partstat") == "DECLINED")
            d.put_item(a["name"], coll, ev["uid"], ical.serialize(copy), kind="ics")
        except DavError as e:
            log.warning("invitation %s non déposée chez %s : %s", ev["uid"], a["name"], e)
    for a in (prev or {}).get("attendees") or []:
        if a["name"] in names or a["name"] == owner: continue
        try:
            coll, cur = _find_event(d, a["name"], ev["uid"])
            if coll and _invite_from(cur): d.delete_item(a["name"], coll, ev["uid"], kind="ics")
        except DavError as e:
            log.warning("retrait de l'invitation chez %s : %s", a["name"], e)

def _set_partstat(d, owner, book, uid, who, partstat):
    """Réponse de `who` : PARTSTAT mis à jour dans l'événement maître et dans sa copie. -> événement maître."""
    master = next((e for e in _events_in(d, owner, book, None, None) if e["uid"] == uid), None)
    if not master: return None
    if who not in [a["name"] for a in master.get("attendees") or []]: return False
    for a in master["attendees"]:
        if a["name"] == who: a["partstat"] = partstat
    d.put_item(owner, book, uid, ical.serialize(master), kind="ics")
    coll, cur = _find_event(d, who, uid)
    if coll and _invite_from(cur):
        copy = dict(master, extra=cur.get("extra"), transparent=master.get("transparent") or partstat == "DECLINED")
        d.put_item(who, coll, uid, ical.serialize(copy), kind="ics")
    return master

@app.route("/events/<owner>/<book>/<uid>/reply", methods=["POST"])
def events_reply(owner, book, uid):
    """{user, partstat: accepted|declined|tentative} — réponse à une invitation (depuis la copie ou l'événement maître)."""
    err = _need_service()
    if err: return err
    b = request.get_json(silent=True) or {}; user = str(b.get("user") or ""); ps = str(b.get("partstat") or "").upper().replace("NEEDS_ACTION", "NEEDS-ACTION")
    if not (core.NAME_RE.match(user) and core.NAME_RE.match(owner) and COLL_RE.match(book)) or ps not in ical.PARTSTAT: return jsonify(error="user et partstat (accepted / declined / tentative) requis"), 400
    try:
        d = dav()
        src = "%s/%s" % (owner, book)
        cur = next((e for e in _events_in(d, owner, book, None, None) if e["uid"] == uid), None)
        if cur and _invite_from(cur): src = _invite_from(cur)
        o, _, bk = src.partition("/")
        master = _set_partstat(d, o, bk, uid, user, ps)
        if master is None: return jsonify(error="événement inconnu"), 404
        if master is False: return jsonify(error="vous n'êtes pas invité à cet événement"), 403
    except DavError as e: return jsonify(error="serveur CalDAV : %s" % e), 502
    journal(user, "réponse %s à %s (%s)" % (ps.lower(), master["title"], src))
    return jsonify(event=ical.public(master, owner=o, book=bk, my_partstat=ps))

@app.route("/freebusy", methods=["GET"])
def freebusy():
    """?users=a,b&resources=salle-1&from=&to= -> créneaux occupés par principal, sans détail (tous agendas, quels que soient les partages)."""
    err = _need_service()
    if err: return err
    try: ws, we = ical.parse_dt(request.args.get("from") or ""), ical.parse_dt(request.args.get("to") or "")
    except Exception: return jsonify(error="from / to requis"), 400
    users = [u for u in (request.args.get("users") or "").split(",") if core.NAME_RE.match(u)][:20]
    res = [r for r in (request.args.get("resources") or "").split(",") if r]
    out = {}
    try:
        d = dav()
        for u in users:
            evs = []
            for c in d.list_collections(u):
                if c["kind"] == "calendar": evs += _events_in(d, u, c["name"], ws, we)
            out[u] = [{"start": ical.iso(s), "end": ical.iso(e)} for s, e in ical.busy_blocks(evs, ws, we)]
        for slug in res:
            evs = _events_in(d, RESOURCE_OWNER, "agenda-" + slug, ws, we)
            out["ressource:" + slug] = [{"start": ical.iso(s), "end": ical.iso(e)} for s, e in ical.busy_blocks(evs, ws, we)]
    except DavError as e:
        return jsonify(error="serveur CalDAV : %s" % e), 502
    return jsonify(busy=out)

@app.route("/resources", methods=["GET"])
def resources_list():
    cn = db(); rows = [dict(r) for r in cn.execute("SELECT * FROM resources ORDER BY kind, name")]; cn.close(); return jsonify(resources=rows, owner=RESOURCE_OWNER)

@app.route("/resources", methods=["POST"])
def resources_create():
    err = _need_service()
    if err: return err
    b = request.get_json(silent=True) or {}; name = str(b.get("name") or "").strip(); slug = re.sub(r"[^a-z0-9-]", "-", (b.get("slug") or name).lower()).strip("-")
    if not name or not slug: return jsonify(error="name requis"), 400
    try: dav().create_collection(RESOURCE_OWNER, "agenda-" + slug, "calendar", name)
    except DavError as e:
        if e.code != 405: return jsonify(error="serveur CalDAV : %s" % e), 502      # 405 = existe déjà
    cn = db()
    cn.execute("INSERT INTO resources (slug, name, kind, capacity, notes, created_at) VALUES (?,?,?,?,?,?) ON CONFLICT(slug) DO UPDATE SET name = excluded.name, kind = excluded.kind, capacity = excluded.capacity, notes = excluded.notes",
               (slug, name, str(b.get("kind") or "salle")[:40], int(b.get("capacity") or 0), str(b.get("notes") or "")[:400], now()))
    cn.commit(); row = dict(cn.execute("SELECT * FROM resources WHERE slug = ?", (slug,)).fetchone()); cn.close()
    journal(actor(), "ressource %s (%s)" % (name, slug))
    return jsonify(resource=row, book="agenda-" + slug), 201

@app.route("/resources/<slug>", methods=["DELETE"])
def resources_delete(slug):
    cn = db(); n = cn.execute("DELETE FROM resources WHERE slug = ?", (slug,)).rowcount; cn.commit(); cn.close()
    return (jsonify(ok=True, note="l'agenda %s/agenda-%s est conservé (réservations passées)" % (RESOURCE_OWNER, slug)), 200) if n else (jsonify(error="ressource inconnue"), 404)

# ---------------------------------------------------------------- #668 : InfoLog -- notes, appels, tâches liés à tout (contacts, événements, tickets, documents)
def _infolog_links(cn, ids):
    out = {i: [] for i in ids}
    if ids:
        q = "SELECT * FROM links WHERE (app1 = 'infolog' AND id1 IN (%s)) OR (app2 = 'infolog' AND id2 IN (%s))" % (",".join("?" * len(ids)), ",".join("?" * len(ids)))
        for r in cn.execute(q, [str(i) for i in ids] * 2):
            r = dict(r)
            me, other = (r["id1"], {"app": r["app2"], "id": r["id2"]}) if r["app1"] == "infolog" else (r["id2"], {"app": r["app1"], "id": r["id1"]})
            out.setdefault(int(me), []).append(dict(other, link_id=r["id"], remark=r["remark"]))
    return out

def _infolog_public(rows, cn):
    links = _infolog_links(cn, [r["id"] for r in rows])
    return [dict(r, private=bool(r["private"]), categories=[c for c in (r["categories"] or "").split(",") if c], links=links.get(r["id"], [])) for r in rows]

@app.route("/infolog", methods=["GET"])
def infolog_list():
    """?user=&groups=&q=&type=&status=&scope=all|mine|responsible&linked=app:id -> entrées visibles (partages infolog, privé)."""
    user, groups = request.args.get("user") or "", groups_arg()
    if not core.NAME_RE.match(user): return jsonify(error="user requis"), 400
    cn = db(); grants = [dict(r) for r in cn.execute("SELECT * FROM grants WHERE app = 'infolog'")]
    where, args = [], []
    if request.args.get("type") in core.INFOLOG_TYPES: where.append("type = ?"); args.append(request.args["type"])
    st = request.args.get("status")
    if st == "active": where.append("status IN ('open','ongoing')")
    elif st in core.INFOLOG_STATUS: where.append("status = ?"); args.append(st)
    scope = request.args.get("scope") or "all"
    if scope == "mine": where.append("owner = ?"); args.append(user)
    elif scope == "responsible": where.append("responsible = ?"); args.append(user)
    linked = request.args.get("linked")
    if linked and ":" in linked:
        a, i = linked.split(":", 1)
        ids = [str(r["id1"] if r["app1"] == "infolog" else r["id2"]) for r in cn.execute("SELECT * FROM links WHERE (app1 = 'infolog' AND app2 = ? AND id2 = ?) OR (app2 = 'infolog' AND app1 = ? AND id1 = ?)", (a, i, a, i))]
        where.append("id IN (%s)" % (",".join("?" * len(ids)) or "NULL")); args += ids
    q = (request.args.get("q") or "").strip().lower()
    rows = [dict(r) for r in cn.execute("SELECT * FROM infolog%s ORDER BY CASE status WHEN 'open' THEN 0 WHEN 'ongoing' THEN 1 ELSE 2 END, priority DESC, CASE WHEN due = '' THEN 1 ELSE 0 END, due, updated_at DESC LIMIT 2000" % ((" WHERE " + " AND ".join(where)) if where else ""), args)]
    if q: rows = [r for r in rows if all(w in " ".join([r["title"], r["description"], r["categories"], r["responsible"], r["owner"]]).lower() for w in q.split())]
    vis = core.infolog_visible(rows, user, groups, grants)
    out = _infolog_public(vis, cn); cn.close()
    return jsonify(entries=out, total=len(out), types=list(core.INFOLOG_TYPES), status=list(core.INFOLOG_STATUS))

@app.route("/infolog", methods=["POST"])
def infolog_create():
    b = request.get_json(silent=True) or {}; user = str(b.get("user") or "")
    if not core.NAME_RE.match(user): return jsonify(error="user requis"), 400
    e, err = core.validate_infolog(b.get("entry") or {}, user)
    if err: return jsonify(error=err), 400
    if e["owner"] != user and not _rights_on("infolog", user, b.get("groups") or [], e["owner"]) & core.RIGHTS["a"]: return jsonify(error="pas le droit d'ajouter dans l'InfoLog de %s" % e["owner"]), 403
    cn = db()
    cur = cn.execute("INSERT INTO infolog (owner, type, title, description, status, priority, due, start, responsible, private, categories, created_by, created_at, updated_at, done_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                     (e["owner"], e["type"], e["title"], e["description"], e["status"], e["priority"], e["due"], e["start"], e["responsible"], e["private"], e["categories"], user, now(), now(), now() if e["status"] == "done" else ""))
    eid = cur.lastrowid
    for l in e["links"]: cn.execute("INSERT OR IGNORE INTO links (app1, id1, app2, id2, remark, created_by, created_at) VALUES ('infolog',?,?,?,?,?,?)", (str(eid), l["app"], l["id"], "", user, now()))
    cn.commit(); row = _infolog_public([dict(cn.execute("SELECT * FROM infolog WHERE id = ?", (eid,)).fetchone())], cn)[0]; cn.close()
    return jsonify(entry=dict(row, rights="raedp" if e["owner"] == user else core.rights_text(_rights_on("infolog", user, b.get("groups") or [], e["owner"])))), 201

@app.route("/infolog/<int:eid>", methods=["GET", "PUT", "DELETE"])
def infolog_one(eid):
    b = request.get_json(silent=True) or {}; user = str(b.get("user") or request.args.get("user") or ""); groups = b.get("groups") or groups_arg()
    if not core.NAME_RE.match(user): return jsonify(error="user requis"), 400
    cn = db(); row = cn.execute("SELECT * FROM infolog WHERE id = ?", (eid,)).fetchone()
    if not row: cn.close(); return jsonify(error="entrée inconnue"), 404
    grants = [dict(r) for r in cn.execute("SELECT * FROM grants WHERE app = 'infolog'")]
    vis = core.infolog_visible([dict(row)], user, groups, grants)
    if not vis: cn.close(); return jsonify(error="entrée non visible"), 403
    cur = vis[0]
    if request.method == "GET":
        out = _infolog_public([cur], cn)[0]; cn.close(); return jsonify(entry=dict(out, rights=cur["rights"]))
    if request.method == "DELETE":
        if "d" not in cur["rights"]: cn.close(); return jsonify(error="droit insuffisant"), 403
        cn.execute("DELETE FROM infolog WHERE id = ?", (eid,)); cn.execute("DELETE FROM links WHERE (app1 = 'infolog' AND id1 = ?) OR (app2 = 'infolog' AND id2 = ?)", (str(eid), str(eid))); cn.commit(); cn.close()
        return jsonify(ok=True)
    if "e" not in cur["rights"]: cn.close(); return jsonify(error="droit insuffisant"), 403
    merged = dict(cur, categories=[c for c in (cur["categories"] or "").split(",") if c]); merged.update({k: v for k, v in (b.get("entry") or {}).items() if k not in ("owner", "links")})
    e, err = core.validate_infolog(merged, cur["owner"])
    if err: cn.close(); return jsonify(error=err), 400
    cn.execute("UPDATE infolog SET type=?, title=?, description=?, status=?, priority=?, due=?, start=?, responsible=?, private=?, categories=?, updated_at=?, done_at=? WHERE id=?",
               (e["type"], e["title"], e["description"], e["status"], e["priority"], e["due"], e["start"], e["responsible"], e["private"], e["categories"], now(), (cur["done_at"] or now()) if e["status"] == "done" else "", eid))
    if "links" in (b.get("entry") or {}):
        cn.execute("DELETE FROM links WHERE app1 = 'infolog' AND id1 = ?", (str(eid),))
        for l in core.validate_infolog({"title": "x", "links": b["entry"]["links"]}, user)[0]["links"]: cn.execute("INSERT OR IGNORE INTO links (app1, id1, app2, id2, remark, created_by, created_at) VALUES ('infolog',?,?,?,?,?,?)", (str(eid), l["app"], l["id"], "", user, now()))
    cn.commit(); out = _infolog_public([dict(cn.execute("SELECT * FROM infolog WHERE id = ?", (eid,)).fetchone())], cn)[0]; cn.close()
    return jsonify(entry=dict(out, rights=cur["rights"]))

@app.route("/journal", methods=["GET"])
def journal_route():
    cn = db(); rows = [dict(r) for r in cn.execute("SELECT * FROM journal ORDER BY id DESC LIMIT 200")]; cn.close(); return jsonify(journal=rows)

@app.route("/logs", methods=["GET"])
def logs_route():
    cn = db(); rows = [dict(r) for r in cn.execute("SELECT at, who, what FROM journal ORDER BY id DESC LIMIT 100")]; cn.close()
    return jsonify(lines=["%s %s %s" % (r["at"], r["who"], r["what"]) for r in rows])
