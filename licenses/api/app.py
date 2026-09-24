# -*- coding: utf-8 -*-
"""licenses-api (livraison #595) -- gestionnaire de licences logicielles par
site : catalogue de logiciels, contrats (par utilisateur / par poste /
abonnement / perpétuel / site), attributions poste ou utilisateur,
installations relevées par la sonde `software-inventory` des agents,
comptes vendeurs (Microsoft Graph, export, manuel), écarts, imports des
tableurs d'inventaire, installation / désinstallation via l'agent du poste
(commande `software_action`).

Lecture libre (hub) ; toute écriture exige un jeton Keycloak vérifié
(groupe administrateurs, comme la tour de contrôle). Aucun secret ici : les
comptes vendeurs référencent un accès du coffre par son nom ; les jetons
Graph vivent le temps d'une synchronisation. Aucune donnée d'exemple
nominative dans le dépôt.
"""
import datetime as _dt
import io
import json
import logging
import os
import sqlite3
import time

import requests
from flask import Flask, g, jsonify, request
from flask_cors import CORS

import owncloud
import rules
import vendors
from auth import AuthError, KeycloakVerifier, bearer_from_header

try:
    from version_endpoint import register_version_route
except ImportError:  # pragma: no cover
    register_version_route = None
try:
    from notify_client import notify as _notify, register_actions as _register_actions
except ImportError:  # tests hors conteneur
    def _notify(*a, **k):
        return None

    def _register_actions(*a, **k):
        return None

logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(name)s %(message)s")
_log = logging.getLogger("licenses-api")

DB_PATH = os.environ.get("LICENSES_DB", "/data/licenses.sqlite")
SI_AGENT_URL = os.environ.get("SI_AGENT_API_URL", "http://si-agent-api:5000").rstrip("/")
CREDENTIALS_API_URL = os.environ.get("CREDENTIALS_API_URL", "http://credentials-api:5000").rstrip("/")
CREDENTIALS_TOKEN = os.environ.get("CREDENTIALS_INTERNAL_TOKEN", "")
KEYCLOAK_INTERNAL_URL = os.environ.get("KEYCLOAK_INTERNAL_URL", "http://keycloak:8080/auth")
KEYCLOAK_REALM = os.environ.get("KEYCLOAK_REALM", "supervision-si")
JWKS_URL = os.environ.get("LICENSES_JWKS_URL") or "%s/realms/%s/protocol/openid-connect/certs" % (KEYCLOAK_INTERNAL_URL, KEYCLOAK_REALM)
ADMIN_GROUPS = [x for x in os.environ.get("LICENSES_ADMIN_GROUPS", "administrateurs").split(",") if x.strip()]
ADMIN_USERS = [x for x in os.environ.get("LICENSES_ADMIN_USERS", "").split(",") if x.strip()]
EXPIRING_DAYS = int(os.environ.get("LICENSES_EXPIRING_DAYS", "60"))

app = Flask(__name__)
CORS(app)
if register_version_route:
    register_version_route(app, "licenses-api")
verifier = KeycloakVerifier(JWKS_URL, ADMIN_USERS, allowed_groups=ADMIN_GROUPS, what="les licences")
_register_actions([
    {"id": "licenses.contract", "label": "Contrat de licence créé / modifié", "severity": "info"},
    {"id": "licenses.assignment", "label": "Attribution de licence", "severity": "info"},
    {"id": "licenses.action", "label": "Installation / désinstallation demandée", "severity": "warning"},
    {"id": "licenses.gap", "label": "Écart de licence (dépassement, expiration)", "severity": "warning"},
])

SCHEMA = """
CREATE TABLE IF NOT EXISTS software (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE, vendor TEXT DEFAULT '', category TEXT DEFAULT '', patterns TEXT DEFAULT '[]', package TEXT DEFAULT '{}', notes TEXT DEFAULT '', created_at REAL);
CREATE TABLE IF NOT EXISTS contracts (id INTEGER PRIMARY KEY AUTOINCREMENT, software_id INTEGER, site TEXT DEFAULT '', label TEXT DEFAULT '', kind TEXT DEFAULT 'per-user', quantity INTEGER DEFAULT 0,
    start TEXT, end TEXT, cost REAL, currency TEXT DEFAULT 'EUR', renewal TEXT DEFAULT '', vendor_account TEXT DEFAULT '', sku TEXT DEFAULT '', reference TEXT DEFAULT '', notes TEXT DEFAULT '', created_at REAL, updated_at REAL);
CREATE TABLE IF NOT EXISTS assignments (id INTEGER PRIMARY KEY AUTOINCREMENT, contract_id INTEGER, subject_kind TEXT, subject TEXT, site TEXT DEFAULT '', since TEXT, note TEXT DEFAULT '', UNIQUE (contract_id, subject_kind, subject));
CREATE TABLE IF NOT EXISTS vendor_accounts (name TEXT PRIMARY KEY, kind TEXT, site TEXT DEFAULT '', config TEXT DEFAULT '{}', credential TEXT DEFAULT '', last_sync REAL, last_error TEXT DEFAULT '', snapshot TEXT DEFAULT '[]');
CREATE TABLE IF NOT EXISTS actions (id INTEGER PRIMARY KEY AUTOINCREMENT, agent_id TEXT, host TEXT, action TEXT, package TEXT, manager TEXT DEFAULT '', software_id INTEGER, command_id TEXT, status TEXT, result TEXT DEFAULT '', user TEXT, created_at REAL, updated_at REAL);
CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY AUTOINCREMENT, at REAL, event TEXT, text TEXT, user TEXT);
CREATE TABLE IF NOT EXISTS users (login TEXT PRIMARY KEY, name TEXT DEFAULT '', mail TEXT DEFAULT '', site TEXT DEFAULT '', source TEXT DEFAULT 'manual', directory INTEGER DEFAULT 0, enabled INTEGER DEFAULT 1, aliases TEXT DEFAULT '[]', note TEXT DEFAULT '', updated_at REAL,
    groups TEXT DEFAULT '[]', missing INTEGER DEFAULT 0, synced_at REAL, fiche TEXT DEFAULT '', fiche_path TEXT DEFAULT '', fiche_former INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);
"""
ACCOUNTS_API_URL = os.environ.get("ACCOUNTS_API_URL", "http://accounts-api:5000").rstrip("/")
# #598 : groupe(s) de l'annuaire signalant les personnes qui ne travaillent plus avec nous
FORMER_GROUPS = [x.strip() for x in os.environ.get("LICENSES_FORMER_GROUPS", "anciens").split(",") if x.strip()]
DIRECTORY_INTERVAL = int(os.environ.get("LICENSES_DIRECTORY_INTERVAL", "3600"))


def db():
    conn = getattr(g, "_db", None)
    if conn is None:
        conn = sqlite3.connect(DB_PATH, timeout=10)
        conn.row_factory = sqlite3.Row
        g._db = conn
    return conn


def init_db():
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
    c = sqlite3.connect(DB_PATH)
    c.executescript(SCHEMA)
    cols = {r[1] for r in c.execute("PRAGMA table_info(users)")}
    for name, ddl in (("groups", "TEXT DEFAULT '[]'"), ("missing", "INTEGER DEFAULT 0"), ("synced_at", "REAL"), ("fiche", "TEXT DEFAULT ''"), ("fiche_path", "TEXT DEFAULT ''"), ("fiche_former", "INTEGER DEFAULT 0")):
        if name not in cols:
            c.execute("ALTER TABLE users ADD COLUMN %s %s" % (name, ddl))
    c.commit()
    c.close()


init_db()


@app.teardown_appcontext
def _close(_exc):
    conn = getattr(g, "_db", None)
    if conn is not None:
        conn.close()


def event(kind, text):
    db().execute("INSERT INTO events (at, event, text, user) VALUES (?, ?, ?, ?)", (time.time(), kind, text, getattr(g, "user", {}).get("username") if hasattr(g, "user") else None))
    db().commit()
    _log.info("%s -- %s", kind, text)


# -- garde : écritures réservées ------------------------------------------------------
@app.before_request
def _guard():
    if request.method in ("GET", "OPTIONS") or request.path in ("/health", "/version"):
        return None
    try:
        g.user = verifier.verify(bearer_from_header(request.headers.get("Authorization")))
    except AuthError as exc:
        return jsonify({"error": str(exc)}), exc.status
    return None


def _row(r):
    d = dict(r)
    for k in ("patterns", "package", "config", "snapshot", "aliases", "groups", "fiche"):
        if k in d and isinstance(d[k], str):
            try:
                d[k] = json.loads(d[k] or ("[]" if k in ("patterns", "snapshot", "aliases", "groups") else "{}"))
            except ValueError:
                pass
    return d


@app.route("/health", methods=["GET"])
def health():
    c = db()
    n = {t: c.execute("SELECT COUNT(*) FROM %s" % t).fetchone()[0] for t in ("software", "contracts", "assignments", "vendor_accounts", "actions")}
    return jsonify({"status": "ok", "counts": n, "si_agent": SI_AGENT_URL, "credentials": bool(CREDENTIALS_TOKEN)}), 200


# -- sources externes ----------------------------------------------------------------
def fetch_inventories(site=None):
    try:
        r = requests.get(SI_AGENT_URL + "/software-inventory", params={"site": site} if site else None, timeout=8)
        return (r.json() or {}).get("inventories") or [] if r.status_code == 200 else []
    except (requests.RequestException, ValueError):
        return []


app.fetch_inventories = fetch_inventories  # remplaçable dans les tests


def reveal(name):
    if not (CREDENTIALS_TOKEN and name):
        return None, None, "coffre non configuré ou accès non renseigné"
    try:
        r = requests.get("%s/credentials/reveal/%s" % (CREDENTIALS_API_URL, name), timeout=5, headers={"X-Credentials-Token": CREDENTIALS_TOKEN, "X-Credentials-Consumer": "licenses-api"})
    except requests.RequestException as exc:
        return None, None, "coffre injoignable (%s)" % exc.__class__.__name__
    if r.status_code != 200:
        return None, None, "accès « %s » : %s" % (name, "absent du coffre" if r.status_code == 404 else "refus %s" % r.status_code)
    b = r.json()
    return b.get("username"), b.get("password"), None


app.reveal = reveal


def _catalog(c):
    return [_row(r) for r in c.execute("SELECT * FROM software ORDER BY name")]


def _contracts(c, site=None):
    q, p = "SELECT * FROM contracts", ()
    if site:
        q, p = q + " WHERE site = ? OR site = ''", (site,)
    return [_row(r) for r in c.execute(q + " ORDER BY software_id, end", p)]


def _assignments(c):
    return [dict(r) for r in c.execute("SELECT * FROM assignments")]


def _users(c, site=None):
    q, p = "SELECT * FROM users", ()
    if site:
        q, p = q + " WHERE site = ? OR site = ''", (site,)
    return [_row(r) for r in c.execute(q + " ORDER BY login", p)]


def resolve_or_create_user(c, person, site, source, mail=""):
    """#597 : une personne d'un import / d'un vendeur -> login de la table users
    (rapprochée avec l'annuaire quand elle y est, créée « info » sinon)."""
    users = _users(c)
    login = rules.resolve_person(person, users)
    if login:
        if site and not next((u for u in users if u["login"] == login), {}).get("site"):
            c.execute("UPDATE users SET site = ? WHERE login = ?", (site, login))
        return login, False
    login = rules.login_from(person) or rules.fold(person)
    if not login:
        return None, False
    is_mail = "@" in str(person)
    c.execute("INSERT OR IGNORE INTO users (login, name, mail, site, source, directory, aliases, updated_at) VALUES (?, ?, ?, ?, ?, 0, '[]', ?)",
              (login, "" if is_mail else str(person).strip(), mail or (str(person).strip() if is_mail else ""), site or "", source, time.time()))
    return login, True


def fetch_directory():
    """Annuaire : comptes Keycloak (fédérés LDAP) via accounts-api."""
    r = requests.get(ACCOUNTS_API_URL + "/users", timeout=15)
    if r.status_code != 200:
        raise RuntimeError("accounts-api : %s" % r.status_code)
    return (r.json() or {}).get("users") or []


app.fetch_directory = fetch_directory


# -- catalogue --------------------------------------------------------------------------
@app.route("/software", methods=["GET"])
def software_list():
    return jsonify({"software": _catalog(db())}), 200


@app.route("/software", methods=["POST"])
@app.route("/software/<int:sid>", methods=["PUT"])
def software_save(sid=None):
    b = request.get_json(silent=True) or {}
    name = str(b.get("name") or "").strip()
    if not name:
        return jsonify({"error": "nom requis"}), 400
    patterns = [str(x).strip() for x in (b.get("patterns") or []) if str(x).strip()]
    package = b.get("package") if isinstance(b.get("package"), dict) else {}
    c = db()
    try:
        if sid is None:
            cur = c.execute("INSERT INTO software (name, vendor, category, patterns, package, notes, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                            (name, str(b.get("vendor") or ""), str(b.get("category") or ""), json.dumps(patterns), json.dumps(package), str(b.get("notes") or ""), time.time()))
            sid = cur.lastrowid
        else:
            c.execute("UPDATE software SET name = ?, vendor = ?, category = ?, patterns = ?, package = ?, notes = ? WHERE id = ?",
                      (name, str(b.get("vendor") or ""), str(b.get("category") or ""), json.dumps(patterns), json.dumps(package), str(b.get("notes") or ""), sid))
        c.commit()
    except sqlite3.IntegrityError:
        return jsonify({"error": "un logiciel porte déjà ce nom"}), 409
    return jsonify({"status": "ok", "id": sid}), 200


@app.route("/software/<int:sid>", methods=["DELETE"])
def software_delete(sid):
    c = db()
    if c.execute("SELECT 1 FROM contracts WHERE software_id = ?", (sid,)).fetchone():
        return jsonify({"error": "des contrats référencent ce logiciel"}), 400
    c.execute("DELETE FROM software WHERE id = ?", (sid,))
    c.commit()
    return jsonify({"status": "ok"}), 200


# -- contrats ----------------------------------------------------------------------------
@app.route("/contracts", methods=["GET"])
def contracts_list():
    c = db()
    sw = {s["id"]: s for s in _catalog(c)}
    asg = _assignments(c)
    portals = {r["name"]: vendors.portal_url(r["kind"], json.loads(r["config"] or "{}")) for r in c.execute("SELECT name, kind, config FROM vendor_accounts")}
    out = []
    for ct in _contracts(c, request.args.get("site")):
        ct["portal"] = portals.get(ct.get("vendor_account") or "", "")  # #598
        ct["software"] = (sw.get(ct["software_id"]) or {}).get("name")
        ct["vendor"] = (sw.get(ct["software_id"]) or {}).get("vendor")
        ct["assigned"] = len([a for a in asg if a["contract_id"] == ct["id"]])
        ct["days_left"] = rules.days_until(ct.get("end"))
        out.append(ct)
    return jsonify({"contracts": out}), 200


@app.route("/contracts", methods=["POST"])
@app.route("/contracts/<int:cid>", methods=["PUT"])
def contract_save(cid=None):
    b = request.get_json(silent=True) or {}
    c = db()
    try:
        sid = int(b.get("software_id"))
    except (TypeError, ValueError):
        return jsonify({"error": "software_id requis"}), 400
    if not c.execute("SELECT 1 FROM software WHERE id = ?", (sid,)).fetchone():
        return jsonify({"error": "logiciel inconnu"}), 404
    kind = str(b.get("kind") or "per-user")
    if kind not in rules.KINDS:
        return jsonify({"error": "kind : %s" % " / ".join(rules.KINDS)}), 400
    try:
        qty = max(0, int(b.get("quantity") or 0))
        cost = float(b["cost"]) if b.get("cost") not in (None, "") else None
    except (TypeError, ValueError):
        return jsonify({"error": "quantité / coût invalides"}), 400
    start, end = rules._date(b.get("start")), rules._date(b.get("end"))
    vals = (sid, str(b.get("site") or ""), str(b.get("label") or ""), kind, qty, start, end, cost, str(b.get("currency") or "EUR"), str(b.get("renewal") or ""),
            str(b.get("vendor_account") or ""), str(b.get("sku") or ""), str(b.get("reference") or ""), str(b.get("notes") or ""))
    if cid is None:
        cur = c.execute("INSERT INTO contracts (software_id, site, label, kind, quantity, start, end, cost, currency, renewal, vendor_account, sku, reference, notes, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", vals + (time.time(), time.time()))
        cid = cur.lastrowid
    else:
        c.execute("UPDATE contracts SET software_id = ?, site = ?, label = ?, kind = ?, quantity = ?, start = ?, end = ?, cost = ?, currency = ?, renewal = ?, vendor_account = ?, sku = ?, reference = ?, notes = ?, updated_at = ? WHERE id = ?", vals + (time.time(), cid))
    c.commit()
    event("contract", "contrat %s (%s, %s × %d) par %s" % (cid, vals[2] or vals[0], kind, qty, g.user["username"]))
    _notify("licenses.contract", "contrat « %s » enregistré" % (vals[2] or cid), "%s ; site %s ; %s × %d ; fin %s" % (kind, vals[1] or "-", kind, qty, end or "-"), {"contract": cid})
    return jsonify({"status": "ok", "id": cid}), 200


@app.route("/contracts/<int:cid>", methods=["DELETE"])
def contract_delete(cid):
    c = db()
    c.execute("DELETE FROM assignments WHERE contract_id = ?", (cid,))
    c.execute("DELETE FROM contracts WHERE id = ?", (cid,))
    c.commit()
    event("contract-deleted", "contrat %s supprimé par %s" % (cid, g.user["username"]))
    return jsonify({"status": "ok"}), 200


# -- attributions ---------------------------------------------------------------------------
@app.route("/assignments", methods=["GET"])
def assignments_list():
    return jsonify({"assignments": _assignments(db())}), 200


@app.route("/assignments", methods=["POST"])
def assignment_add():
    b = request.get_json(silent=True) or {}
    kind, subject = str(b.get("subject_kind") or "user"), str(b.get("subject") or "").strip()
    if kind not in ("user", "host") or not subject:
        return jsonify({"error": "subject_kind (user | host) et subject requis"}), 400
    c = db()
    ct = c.execute("SELECT * FROM contracts WHERE id = ?", (b.get("contract_id"),)).fetchone()
    if not ct:
        return jsonify({"error": "contrat inconnu"}), 404
    if kind == "user":  # #597 : la personne rejoint la table utilisateurs (annuaire ou info)
        subject = resolve_or_create_user(c, subject, str(b.get("site") or ct["site"] or ""), "manual")[0] or subject
    try:
        c.execute("INSERT INTO assignments (contract_id, subject_kind, subject, site, since, note) VALUES (?, ?, ?, ?, ?, ?)",
                  (ct["id"], kind, subject, str(b.get("site") or ct["site"] or ""), _dt.date.today().isoformat(), str(b.get("note") or "")))
        c.commit()
    except sqlite3.IntegrityError:
        return jsonify({"error": "déjà attribué"}), 409
    n = c.execute("SELECT COUNT(*) FROM assignments WHERE contract_id = ?", (ct["id"],)).fetchone()[0]
    over = ct["quantity"] and ct["kind"] in ("per-user", "subscription") and n > ct["quantity"]
    event("assignment", "%s %s → contrat %s (%d/%s)%s par %s" % (kind, subject, ct["id"], n, ct["quantity"] or "∞", " DÉPASSEMENT" if over else "", g.user["username"]))
    _notify("licenses.gap" if over else "licenses.assignment", "%s attribué à %s%s" % (ct["label"] or ct["id"], subject, " -- dépassement (%d/%d)" % (n, ct["quantity"]) if over else ""), "", {"contract": ct["id"]},
            severity="warning" if over else None)
    return jsonify({"status": "ok", "count": n, "over": bool(over)}), 200


@app.route("/assignments/<int:aid>", methods=["DELETE"])
def assignment_del(aid):
    c = db()
    c.execute("DELETE FROM assignments WHERE id = ?", (aid,))
    c.commit()
    return jsonify({"status": "ok"}), 200


# -- installations, écarts, grille --------------------------------------------------------------
@app.route("/installations", methods=["GET"])
def installations():
    c = db()
    invs = app.fetch_inventories(request.args.get("site"))
    found, unknown = rules.match_installations(_catalog(c), invs)
    hosts = [{"agent_id": i.get("agent_id"), "hostname": i.get("hostname"), "site": i.get("site"), "os": i.get("os"), "at": i.get("at"), "count": i.get("count"), "users": i.get("users") or [], "warnings": i.get("warnings") or []} for i in invs]
    return jsonify({"hosts": hosts, "found": found, "unknown": unknown[:300], "sites": sorted({i.get("site") for i in invs if i.get("site")})}), 200


@app.route("/installations/<agent_id>", methods=["GET"])
def installation_detail(agent_id):
    for i in app.fetch_inventories():
        if i.get("agent_id") == agent_id:
            q = rules.fold(request.args.get("q"))
            items = [x for x in i.get("installed") or [] if not q or q in rules.fold(x.get("name")) or q in rules.fold(x.get("publisher"))]
            return jsonify(dict(i, installed=items[:2000])), 200
    return jsonify({"error": "poste inconnu"}), 404


@app.route("/gaps", methods=["GET"])
def gaps_route():
    c = db()
    cat = _catalog(c)
    found, _ = rules.match_installations(cat, app.fetch_inventories(request.args.get("site")))
    g_ = rules.gaps(cat, _contracts(c, request.args.get("site")), _assignments(c), found, expiring_days=EXPIRING_DAYS)
    g_ += rules.user_gaps([u for u in _users(c, request.args.get("site")) if not request.args.get("site") or u.get("site") == request.args.get("site")], _assignments(c), FORMER_GROUPS)  # #598
    counts = {"critical": 0, "warning": 0, "info": 0}
    for x in g_:
        counts[x["severity"]] += 1
    return jsonify({"gaps": g_, "counts": counts}), 200


@app.route("/grid", methods=["GET"])
def grid_route():
    c = db()
    site = request.args.get("site")
    users = [u for u in _users(c, site) if not site or u.get("site") == site]
    return jsonify(rules.grid(_catalog(c), _contracts(c, site), _assignments(c), app.fetch_inventories(site), users)), 200


@app.route("/sites", methods=["GET"])
def sites():
    c = db()
    s = {r[0] for r in c.execute("SELECT DISTINCT site FROM contracts WHERE site != ''")} | {r[0] for r in c.execute("SELECT DISTINCT site FROM vendor_accounts WHERE site != ''")} | {r[0] for r in c.execute("SELECT DISTINCT site FROM users WHERE site != ''")}
    s |= {i.get("site") for i in app.fetch_inventories() if i.get("site")}
    return jsonify({"sites": sorted(x for x in s if x)}), 200


# -- import des tableurs -------------------------------------------------------------------------
def _rows_from_upload(f):
    name = (f.filename or "").lower()
    data = f.read()
    if name.endswith(".csv"):
        import csv
        text = data.decode("utf-8-sig", "replace")
        head = text[:4096]
        delim = max(";,\t", key=lambda d: head.count(d))  # séparateur le plus fréquent (exports FR : « ; »)
        return list(csv.reader(io.StringIO(text, newline=""), delimiter=delim))
    import openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(data), data_only=True, read_only=True)
    ws = wb.worksheets[0]
    return [list(r) for r in ws.iter_rows(values_only=True)]


@app.route("/import", methods=["POST"])
def import_route():
    """Analyse (dry_run=1) ou import d'un tableur : matrice logiciel × personne,
    export Microsoft 365, comparatif licence × initiales. Crée logiciels et
    contrats manquants (site du formulaire), attribue les personnes."""
    f = request.files.get("file")
    if not f:
        return jsonify({"error": "fichier .xlsx ou .csv attendu (champ « file »)"}), 400
    site = str(request.form.get("site") or "")
    dry = request.form.get("dry_run") in ("1", "true")
    vendor_account = str(request.form.get("vendor_account") or "").strip()  # #604 : export déposé sur un compte vendeur
    try:
        rows = _rows_from_upload(f)
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": "fichier illisible : %s" % exc}), 400
    fmt = request.form.get("format") or rules.detect_format(rows)
    if fmt == "matrix":
        items, err = rules.import_matrix(rows)
        plan = [{"software": it["software"], "vendor": it["vendor"], "kind_label": it["kind_label"], "end": it["end"], "people": it["people"]} for it in items]
    elif fmt == "contracts":  # #602 : une ligne par contrat, tous les champs
        items, err = rules.import_contracts(rows)
        plan = [dict(it, kind_label=it["kind"]) for it in items]
    elif fmt == "m365":
        items, err = rules.import_m365(rows)
        by_lic = {}
        for it in items:
            for lic in it["licenses"]:
                by_lic.setdefault(lic, []).append(it["upn"] or it["user"])
        plan = [{"software": lic, "vendor": "Microsoft", "kind_label": "abonnement", "end": None, "people": ppl} for lic, ppl in by_lic.items()]
    else:
        items, err = rules.import_comparatif(rows)
        plan = [{"software": it["software"], "vendor": "", "kind_label": "", "end": None, "people": it["people"]} for it in items]
    if err:
        return jsonify({"error": err, "format": fmt}), 400
    c = db()
    users = _users(c)
    people_total, unknown = 0, []
    for p in plan:
        p["resolved"] = []
        for person in p["people"]:
            login = rules.resolve_person(person, users)
            p["resolved"].append({"person": person, "login": login})
            people_total += 1
            if not login and person not in unknown:
                unknown.append(person)
    if dry:
        return jsonify({"format": fmt, "plan": plan, "dry_run": True, "people": people_total, "unknown_people": unknown}), 200
    created = {"software": 0, "contracts": 0, "assignments": 0, "users": 0}
    for p in plan:
        row = c.execute("SELECT id FROM software WHERE lower(name) = lower(?)", (p["software"],)).fetchone()
        if row:
            sid = row["id"]
        else:
            sid = c.execute("INSERT INTO software (name, vendor, patterns, created_at) VALUES (?, ?, '[]', ?)", (p["software"], p["vendor"] or "", time.time())).lastrowid
            created["software"] += 1
        p_site = p.get("site") or site if fmt == "contracts" else site
        if fmt == "contracts":  # une ligne = un contrat identifié par logiciel + site + libellé (ou référence)
            ct = c.execute("SELECT id FROM contracts WHERE software_id = ? AND site = ? AND (label = ? OR (reference != '' AND reference = ?))", (sid, p_site, p.get("label") or "", p.get("reference") or "")).fetchone()
        else:
            ct = c.execute("SELECT id, quantity FROM contracts WHERE software_id = ? AND site = ?", (sid, site)).fetchone()
        if ct:
            cid = ct["id"]
            if fmt == "contracts":  # mise à jour des champs du contrat existant
                c.execute("UPDATE contracts SET kind = ?, quantity = ?, start = ?, end = ?, cost = ?, currency = ?, renewal = ?, vendor_account = ?, sku = ?, reference = ?, notes = ?, updated_at = ? WHERE id = ?",
                          (p["kind"], p["quantity"], p["start"], p["end"], p["cost"], p["currency"], p["renewal"], p["vendor_account"], p["sku"], p["reference"], p["notes"], time.time(), cid))
                created["updated"] = created.get("updated", 0) + 1
        elif fmt == "contracts":
            cid = c.execute("INSERT INTO contracts (software_id, site, label, kind, quantity, start, end, cost, currency, renewal, vendor_account, sku, reference, notes, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                            (sid, p_site, p["label"] or p["software"], p["kind"], p["quantity"], p["start"], p["end"], p["cost"], p["currency"], p["renewal"], p["vendor_account"] or vendor_account, p["sku"], p["reference"], p["notes"] or "importé de %s" % (f.filename or "tableur"), time.time(), time.time())).lastrowid
            created["contracts"] += 1
        else:
            kind = "subscription" if "abonnement" in rules.fold(p["kind_label"]) or p["vendor"] == "Microsoft" else "per-user"
            cid = c.execute("INSERT INTO contracts (software_id, site, label, kind, quantity, end, vendor_account, notes, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                            (sid, site, "%s%s" % (p["software"], " (%s)" % p["kind_label"] if p["kind_label"] else ""), kind, len(p["people"]), p["end"], vendor_account, "importé de %s" % (f.filename or "tableur"), time.time(), time.time())).lastrowid
            created["contracts"] += 1
        for person in p["people"]:
            login, new = resolve_or_create_user(c, person, p_site, "import")
            if not login:
                continue
            created["users"] += 1 if new else 0
            try:
                c.execute("INSERT INTO assignments (contract_id, subject_kind, subject, site, since, note) VALUES (?, 'user', ?, ?, ?, 'import')", (cid, login, p_site, _dt.date.today().isoformat()))
                created["assignments"] += 1
            except sqlite3.IntegrityError:
                pass
    if vendor_account:
        c.execute("UPDATE vendor_accounts SET last_sync = ?, last_error = '', snapshot = ? WHERE name = ?", (time.time(), json.dumps([{"sku": "", "label": p["software"], "quantity": len(p["people"]), "consumed": len(p["people"])} for p in plan], ensure_ascii=False), vendor_account))
    c.commit()
    event("import", "import %s (%s)%s : %s par %s" % (f.filename, fmt, " pour le compte " + vendor_account if vendor_account else "", created, g.user["username"]))
    return jsonify({"format": fmt, "created": created, "plan": plan}), 200


# -- utilisateurs par site (#597) : annuaire (Keycloak / LDAP) + personnes « info » des imports -----------
@app.route("/users", methods=["GET"])
def users_list():
    c = db()
    counts = {r[0]: r[1] for r in c.execute("SELECT subject, COUNT(*) FROM assignments WHERE subject_kind = 'user' GROUP BY subject")}
    out = []
    for u in _users(c, request.args.get("site")):
        u["assigned"] = counts.get(u["login"], 0)
        al = rules.user_alert(u, FORMER_GROUPS)
        u["alert"], u["alert_label"] = (al[0], al[1]) if al else (None, None)
        out.append(u)
    last = c.execute("SELECT MAX(synced_at) FROM users").fetchone()[0]
    return jsonify({"users": out, "former_groups": FORMER_GROUPS, "last_sync": last, "sync_error": _sync_state.get("error"), "owncloud": setting_get(c, "owncloud_state", {}) or {}}), 200


@app.route("/users", methods=["POST"])
def user_save():
    """Ajout / modification manuelle : {login, name?, mail?, site?, aliases?, note?} (login = identifiant LDAP quand il existe)."""
    b = request.get_json(silent=True) or {}
    login = rules.fold(str(b.get("login") or "").strip())
    if not login:
        return jsonify({"error": "login requis"}), 400
    c = db()
    cur = c.execute("SELECT * FROM users WHERE login = ?", (login,)).fetchone()
    aliases = [str(a).strip() for a in (b.get("aliases") or []) if str(a).strip()] if "aliases" in b else (json.loads(cur["aliases"]) if cur else [])
    if cur:
        c.execute("UPDATE users SET name = ?, mail = ?, site = ?, aliases = ?, note = ?, updated_at = ? WHERE login = ?",
                  (str(b.get("name", cur["name"]) or ""), str(b.get("mail", cur["mail"]) or ""), str(b.get("site", cur["site"]) or ""), json.dumps(aliases), str(b.get("note", cur["note"]) or ""), time.time(), login))
    else:
        c.execute("INSERT INTO users (login, name, mail, site, source, directory, aliases, note, updated_at) VALUES (?, ?, ?, ?, 'manual', 0, ?, ?, ?)",
                  (login, str(b.get("name") or ""), str(b.get("mail") or ""), str(b.get("site") or ""), json.dumps(aliases), str(b.get("note") or ""), time.time()))
    c.commit()
    return jsonify({"status": "ok", "login": login}), 200


@app.route("/users/<login>", methods=["DELETE"])
def user_delete(login):
    c = db()
    if c.execute("SELECT 1 FROM assignments WHERE subject_kind = 'user' AND subject = ?", (login,)).fetchone():
        return jsonify({"error": "des attributions référencent cet utilisateur (les retirer d'abord)"}), 400
    c.execute("DELETE FROM users WHERE login = ?", (login,))
    c.commit()
    return jsonify({"status": "ok"}), 200


_sync_state = {"error": "", "at": 0}


@app.route("/users/sync", methods=["POST"])
def users_sync():
    try:
        r = sync_directory(db(), g.user["username"])
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": "annuaire injoignable : %s" % str(exc)[:200]}), 502
    return jsonify(dict(r, status="ok")), 200


def sync_directory(c, who="automatique"):
    """Annuaire -> table users : les comptes Keycloak (fédérés LDAP) deviennent
    « annuaire » (login, nom, mail, activé, GROUPES) ; les lignes « info » dont
    le login ou le mail correspond sont rattachées ; le site n'est jamais
    écrasé ; un compte d'annuaire qui a disparu est marqué `missing` (#598)."""
    directory = app.fetch_directory()
    now = time.time()
    users = _users(c)
    by_login = {u["login"]: u for u in users}
    by_mail = {rules.fold(u["mail"]): u for u in users if u.get("mail")}
    added, linked, updated = 0, 0, 0
    for d in directory:
        login = rules.fold(d.get("username") or "")
        if not login:
            continue
        name = " ".join(x for x in (d.get("first_name"), d.get("last_name")) if x) or login
        mail = d.get("email") or ""
        cur = by_login.get(login) or (by_mail.get(rules.fold(mail)) if mail else None)
        groups = json.dumps(sorted({str(x) for x in (d.get("groups") or []) if x}))
        enabled = 1 if d.get("enabled", True) else 0
        if cur and cur["login"] != login:  # ligne « info » créée depuis un mail -> renommée au login LDAP
            c.execute("UPDATE assignments SET subject = ? WHERE subject_kind = 'user' AND subject = ?", (login, cur["login"]))
            c.execute("DELETE FROM users WHERE login = ?", (cur["login"],))
            c.execute("INSERT INTO users (login, name, mail, site, source, directory, enabled, aliases, note, updated_at, groups, missing, synced_at) VALUES (?, ?, ?, ?, 'ldap', 1, ?, ?, ?, ?, ?, 0, ?)",
                      (login, name, mail, cur["site"], enabled, json.dumps(sorted(set(cur["aliases"] + [cur["login"]]))), cur["note"], now, groups, now))
            linked += 1
        elif cur:
            c.execute("UPDATE users SET name = ?, mail = ?, source = 'ldap', directory = 1, enabled = ?, updated_at = ?, groups = ?, missing = 0, synced_at = ? WHERE login = ?", (name, mail, enabled, now, groups, now, login))
            updated += 1 if cur["directory"] else 0
            linked += 0 if cur["directory"] else 1
        else:
            c.execute("INSERT INTO users (login, name, mail, site, source, directory, enabled, aliases, updated_at, groups, missing, synced_at) VALUES (?, ?, ?, '', 'ldap', 1, ?, '[]', ?, ?, 0, ?)", (login, name, mail, enabled, now, groups, now))
            added += 1
    # comptes d'annuaire disparus (jamais supprimés : leurs attributions restent visibles en écart)
    c.execute("UPDATE users SET missing = 1 WHERE directory = 1 AND (synced_at IS NULL OR synced_at < ?)", (now,))
    gone = c.execute("SELECT COUNT(*) FROM users WHERE missing = 1").fetchone()[0]
    # rattachement des lignes « info » restantes par nom (« Prénom Nom » ↔ prenom.nom)
    users = _users(c)
    for u in [x for x in users if not x["directory"]]:
        login = rules.resolve_person(u["name"] or u["login"], [x for x in users if x["directory"]])
        if login and login != u["login"]:
            c.execute("UPDATE assignments SET subject = ? WHERE subject_kind = 'user' AND subject = ?", (login, u["login"]))
            c.execute("DELETE FROM users WHERE login = ?", (u["login"],))
            if u["site"]:
                c.execute("UPDATE users SET site = COALESCE(NULLIF(site, ''), ?) WHERE login = ?", (u["site"], login))
            linked += 1
    c.commit()
    former = [u["login"] for u in _users(c) if rules.user_alert(u, FORMER_GROUPS) and rules.user_alert(u, FORMER_GROUPS)[0] == "former"]
    _sync_state.update(error="", at=now)
    if added or linked or gone or who != "automatique":
        event("users-sync", "annuaire : %d compte(s), %d ajouté(s), %d rattaché(s), %d disparu(s), %d ancien(s) par %s" % (len(directory), added, linked, gone, len(former), who))
    return {"directory": len(directory), "added": added, "linked": linked, "updated": updated, "missing": gone, "former": len(former)}


def _directory_loop():
    """#598 : analyse croisée automatique avec l'annuaire (toutes les LICENSES_DIRECTORY_INTERVAL s)."""
    import threading  # noqa: F401
    time.sleep(20)
    while True:
        try:
            with app.app_context():
                sync_directory(db())
                s = owncloud_settings(db())
                st = setting_get(db(), "owncloud_state", {}) or {}
                if s["url"] and s["folder"] and s["credential"] and s["interval"] and time.time() - (st.get("at") or 0) >= s["interval"]:
                    try:
                        sync_owncloud(db())
                    except Exception as exc:  # noqa: BLE001
                        st.update(error=str(exc)[:300], error_at=time.time())
                        setting_set(db(), "owncloud_state", st)
                        db().commit()
                # alerte « type logiciel » : anciens avec licences -> notification (une par passage et par changement)
                c = db()
                bad = [x for x in rules.user_gaps(_users(c), _assignments(c), FORMER_GROUPS) if x["severity"] == "critical"]
                key = ",".join(sorted(x["user"] for x in bad))
                if bad and key != _sync_state.get("notified"):
                    _notify("licenses.gap", "%d ancien(s) avec des licences attribuées" % len(bad), "\n".join(x["text"] for x in bad), {"users": key}, severity="critical")
                    _sync_state["notified"] = key
        except Exception as exc:  # noqa: BLE001
            _sync_state["error"] = str(exc)[:200]
            _log.warning("annuaire : %s", exc)
        time.sleep(max(60, DIRECTORY_INTERVAL))


if DIRECTORY_INTERVAL > 0 and os.environ.get("LICENSES_DIRECTORY_WORKER", "1") == "1":
    import threading
    threading.Thread(target=_directory_loop, name="directory-sync", daemon=True).start()


# -- connecteur ownCloud (#600) : fiches utilisateurs (secrets, clés de licence, adresses) ---------------------
OWNCLOUD_DEFAULTS = {"url": "", "folder": "", "former_subfolder": "anciens utilisateurs", "credential": "", "verify": True, "interval": 21600}


def setting_get(c, key, default=None):
    r = c.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return json.loads(r[0]) if r else default


def setting_set(c, key, value):
    c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, json.dumps(value)))


def owncloud_settings(c):
    return dict(OWNCLOUD_DEFAULTS, **(setting_get(c, "owncloud", {}) or {}))


@app.route("/owncloud", methods=["GET"])
def owncloud_get():
    c = db()
    s = owncloud_settings(c)
    st = setting_get(c, "owncloud_state", {}) or {}
    n = c.execute("SELECT COUNT(*), SUM(fiche_former) FROM users WHERE fiche_path != ''").fetchone()
    return jsonify({"settings": s, "state": st, "fiches": n[0], "fiches_former": n[1] or 0}), 200


@app.route("/owncloud", methods=["PUT"])
def owncloud_put():
    """{url, folder, former_subfolder, credential (nom d'un accès du coffre : utilisateur + mot de passe ownCloud), verify, interval}"""
    b = request.get_json(silent=True) or {}
    c = db()
    s = owncloud_settings(c)
    for k in ("url", "folder", "former_subfolder", "credential"):
        if k in b:
            s[k] = str(b[k] or "").strip()
    if "verify" in b:
        s["verify"] = bool(b["verify"])
    if "interval" in b:
        s["interval"] = max(0, int(b["interval"] or 0))
    setting_set(c, "owncloud", s)
    c.commit()
    event("owncloud", "réglages ownCloud : %s %s (accès « %s ») par %s" % (s["url"], s["folder"], s["credential"], g.user["username"]))
    return jsonify({"status": "ok", "settings": s}), 200


def owncloud_client(c):
    s = owncloud_settings(c)
    if not (s["url"] and s["folder"] and s["credential"]):
        raise RuntimeError("connecteur ownCloud non configuré (adresse, dossier, accès du coffre)")
    user, password, err = app.reveal(s["credential"])
    if err:
        raise RuntimeError(err)
    return owncloud.OwnCloud(s["url"], user, password, verify=s["verify"]), s


def sync_owncloud(c, who="automatique"):
    """Fiches -> table users : rapprochement par adresse / nom, création « info »
    sinon (source owncloud), sous-dossier des anciens -> fiche_former. Le texte
    des fiches n'est jamais conservé : seulement le résumé masqué."""
    client, s = owncloud_client(c)
    fiches = owncloud.scan(client, s["folder"], s["former_subfolder"])
    now = time.time()
    seen, created, linked = set(), 0, 0
    c.execute("UPDATE users SET fiche_former = 0 WHERE fiche_path != ''")
    for f in fiches:
        users = _users(c)
        login = None
        for m in f["fiche"]["mails"]:
            login = rules.resolve_person(m, users)
            if login:
                break
        login = login or rules.resolve_person(f["name"], users)
        if login:
            linked += 1
        else:
            login = rules.login_from(f["fiche"]["mails"][0] if f["fiche"]["mails"] else f["name"])
            if not login:
                continue
            c.execute("INSERT OR IGNORE INTO users (login, name, mail, site, source, directory, aliases, updated_at) VALUES (?, ?, ?, '', 'owncloud', 0, '[]', ?)", (login, f["name"], f["fiche"]["mails"][0] if f["fiche"]["mails"] else "", now))
            created += 1
        if login in seen:
            continue
        seen.add(login)
        c.execute("UPDATE users SET fiche = ?, fiche_path = ?, fiche_former = ?, mail = CASE WHEN mail = '' THEN ? ELSE mail END WHERE login = ?",
                  (json.dumps(dict(f["fiche"], modified=f["modified"], size=f["size"]), ensure_ascii=False), f["path"], 1 if f["former"] else 0, f["fiche"]["mails"][0] if f["fiche"]["mails"] else "", login))
    # fiches disparues : on garde la dernière lecture mais on l'indique
    gone = [r[0] for r in c.execute("SELECT login FROM users WHERE fiche_path != ''") if r[0] not in seen]
    setting_set(c, "owncloud_state", {"at": now, "error": "", "fiches": len(fiches), "former": sum(1 for f in fiches if f["former"]), "created": created, "linked": linked, "gone": gone})
    c.commit()
    if created or who != "automatique":
        event("owncloud-sync", "ownCloud : %d fiche(s) (%d anciens), %d créé(s), %d rattaché(s), %d disparue(s) par %s" % (len(fiches), sum(1 for f in fiches if f["former"]), created, linked, len(gone), who))
    return {"fiches": len(fiches), "former": sum(1 for f in fiches if f["former"]), "created": created, "linked": linked, "gone": gone}


@app.route("/owncloud/sync", methods=["POST"])
def owncloud_sync_route():
    c = db()
    try:
        r = sync_owncloud(c, g.user["username"])
    except Exception as exc:  # noqa: BLE001
        st = setting_get(c, "owncloud_state", {}) or {}
        st.update(error=str(exc)[:300], error_at=time.time())
        setting_set(c, "owncloud_state", st)
        c.commit()
        return jsonify({"error": str(exc)[:300]}), 502
    return jsonify(dict(r, status="ok")), 200


@app.route("/owncloud/test", methods=["POST"])
def owncloud_test():
    c = db()
    try:
        client, s = owncloud_client(c)
        items = client.list(s["folder"])
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": str(exc)[:300]}), 502
    return jsonify({"status": "ok", "entries": len(items), "text_files": sum(1 for i in items if owncloud.is_text_file(i)), "folders": [i["path"] for i in items if i["dir"]][:50]}), 200


@app.route("/users/<login>/fiche", methods=["POST"])
def user_fiche(login):
    """Texte complet de la fiche (secrets en clair) : POST = geste explicite,
    réservé aux administrateurs (garde), journalisé ; jamais mémorisé ici."""
    c = db()
    u = c.execute("SELECT fiche_path FROM users WHERE login = ?", (login,)).fetchone()
    if not u or not u["fiche_path"]:
        return jsonify({"error": "pas de fiche ownCloud pour cet utilisateur"}), 404
    try:
        client, _s = owncloud_client(c)
        text = client.read(u["fiche_path"])
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": str(exc)[:300]}), 502
    event("fiche-read", "fiche de %s lue par %s" % (login, g.user["username"]))
    return jsonify({"login": login, "path": u["fiche_path"], "text": text}), 200


# -- #602 : compte Microsoft 365 d'un administrateur (sans inscription d'application) ---------------------
_device_flows = {}  # name -> {device_code, tenant, expires, user_code, verification_uri}


def account_token(c, v):
    """Jeton d'accès pour un compte « microsoft-account » : jeton de
    rafraîchissement mémorisé (connexion par code) en priorité, sinon e-mail +
    mot de passe de l'accès du coffre (ROPC). Le jeton de rafraîchissement vit
    dans la base (hors dépôt) et n'est jamais renvoyé par l'API."""
    tenant = (v["config"] or {}).get("tenant") or "organizations"
    saved = setting_get(c, "vendor_token:" + v["name"], None)
    if saved and saved.get("refresh_token"):
        tok = vendors.refresh_token(tenant, saved["refresh_token"])
        setting_set(c, "vendor_token:" + v["name"], {"refresh_token": tok.get("refresh_token") or saved["refresh_token"], "at": time.time(), "account": saved.get("account")})
        c.commit()
        return tok["access_token"]
    if v.get("credential"):
        user, password, err = app.reveal(v["credential"])
        if err:
            raise RuntimeError(err)
        tok = vendors.ropc_token(tenant, user, password)
        if tok.get("refresh_token"):
            setting_set(c, "vendor_token:" + v["name"], {"refresh_token": tok["refresh_token"], "at": time.time(), "account": user})
            c.commit()
        return tok["access_token"]
    raise RuntimeError("compte non connecté : se connecter par code, ou renseigner un accès du coffre (e-mail + mot de passe)")


app.account_token = account_token


@app.route("/vendors/<name>/connect", methods=["POST"])
def vendor_connect(name):
    """Connexion par code : renvoie le code à saisir sur microsoft.com/devicelogin ; le hub interroge ensuite /connect/status."""
    c = db()
    v = c.execute("SELECT * FROM vendor_accounts WHERE name = ?", (name,)).fetchone()
    if not v or v["kind"] != "microsoft-account":
        return jsonify({"error": "compte « microsoft-account » requis"}), 404
    cfg = json.loads(v["config"] or "{}")
    try:
        r = vendors.device_code_start(cfg.get("tenant") or "organizations")
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": str(exc)[:300]}), 502
    _device_flows[name] = {"device_code": r["device_code"], "tenant": cfg.get("tenant") or "organizations", "expires": time.time() + int(r.get("expires_in") or 900), "interval": int(r.get("interval") or 5), "user_code": r["user_code"], "verification_uri": r.get("verification_uri") or "https://microsoft.com/devicelogin"}
    event("vendor-connect", "connexion par code demandée pour %s par %s" % (name, g.user["username"]))
    return jsonify({"user_code": r["user_code"], "verification_uri": _device_flows[name]["verification_uri"], "expires_in": r.get("expires_in"), "message": r.get("message")}), 200


@app.route("/vendors/<name>/connect/status", methods=["POST"])
def vendor_connect_status(name):
    f = _device_flows.get(name)
    if not f:
        return jsonify({"status": "none"}), 200
    if time.time() > f["expires"]:
        _device_flows.pop(name, None)
        return jsonify({"status": "expired"}), 200
    try:
        st, tok = vendors.device_code_poll(f["tenant"], f["device_code"])
    except Exception as exc:  # noqa: BLE001
        return jsonify({"status": "error", "error": str(exc)[:300]}), 200
    if st == "pending":
        return jsonify({"status": "pending", "user_code": f["user_code"], "verification_uri": f["verification_uri"]}), 200
    _device_flows.pop(name, None)
    if st == "error":
        return jsonify({"status": "error", "error": tok}), 200
    c = db()
    setting_set(c, "vendor_token:" + name, {"refresh_token": tok.get("refresh_token"), "at": time.time(), "account": "code"})
    c.commit()
    event("vendor-connect", "compte %s connecté par code par %s" % (name, g.user["username"]))
    return jsonify({"status": "ok"}), 200


@app.route("/vendors/<name>/disconnect", methods=["POST"])
def vendor_disconnect(name):
    c = db()
    c.execute("DELETE FROM settings WHERE key = ?", ("vendor_token:" + name,))
    c.commit()
    _device_flows.pop(name, None)
    return jsonify({"status": "ok"}), 200


# -- comptes vendeurs -------------------------------------------------------------------------
@app.route("/vendors", methods=["GET"])
def vendors_list():
    out = []
    for r in db().execute("SELECT * FROM vendor_accounts ORDER BY name"):
        d = _row(r)
        d["portal"] = vendors.portal_url(d["kind"], d["config"])  # #598
        if d["kind"] == "microsoft-account":  # #602 : connecté ? (jamais le jeton)
            saved = setting_get(db(), "vendor_token:" + d["name"], None) or {}
            d["connected"] = bool(saved.get("refresh_token"))
            d["connected_at"] = saved.get("at")
            d["connected_as"] = saved.get("account")
        out.append(d)
    return jsonify({"vendors": out, "kinds": vendors.KINDS}), 200


@app.route("/vendors", methods=["POST"])
def vendor_save():
    b = request.get_json(silent=True) or {}
    name = rules.re.sub(r"[^a-z0-9_-]+", "-", str(b.get("name") or "").strip().lower())[:40].strip("-")
    kind = str(b.get("kind") or "manual")
    if not name or kind not in vendors.KINDS:
        return jsonify({"error": "nom et kind (%s) requis" % " / ".join(vendors.KINDS)}), 400
    config = b.get("config") if isinstance(b.get("config"), dict) else {}
    if kind == "microsoft-account" and "tenant" not in config:
        config["tenant"] = ""
    if kind == "microsoft-graph" and not (config.get("tenant") and config.get("client_id") and b.get("credential")):
        return jsonify({"error": "microsoft-graph : config.tenant, config.client_id et credential (accès du coffre dont le mot de passe est le secret client) requis"}), 400
    c = db()
    c.execute("INSERT OR REPLACE INTO vendor_accounts (name, kind, site, config, credential, last_sync, last_error, snapshot) VALUES (?, ?, ?, ?, ?, (SELECT last_sync FROM vendor_accounts WHERE name = ?), '', (SELECT COALESCE(snapshot, '[]') FROM vendor_accounts WHERE name = ?))",
              (name, kind, str(b.get("site") or ""), json.dumps(config), str(b.get("credential") or ""), name, name))
    c.commit()
    event("vendor", "compte vendeur %s (%s) par %s" % (name, kind, g.user["username"]))
    return jsonify({"status": "ok", "name": name}), 200


@app.route("/vendors/<name>", methods=["DELETE"])
def vendor_delete(name):
    db().execute("DELETE FROM settings WHERE key = ?", ("vendor_token:" + name,))  # #602
    db().execute("DELETE FROM vendor_accounts WHERE name = ?", (name,))
    db().commit()
    return jsonify({"status": "ok"}), 200


@app.route("/vendors/<name>/sync", methods=["POST"])
def vendor_sync(name):
    """Lit l'état chez le vendeur, met à jour les contrats liés (sku ↔ compte) : quantité, consommé, utilisateurs."""
    c = db()
    v = c.execute("SELECT * FROM vendor_accounts WHERE name = ?", (name,)).fetchone()
    if not v:
        return jsonify({"error": "compte inconnu"}), 404
    v = _row(v)
    try:
        if v["kind"] == "microsoft-graph":
            _, secret, err = app.reveal(v["credential"])
            if err:
                raise RuntimeError(err)
            snapshot = vendors.sync_microsoft_graph(v["config"], secret)
        elif v["kind"] == "microsoft-account":  # #602 : compte administrateur (code ou e-mail / mot de passe)
            snapshot = vendors.sync_with_token(app.account_token(c, v))
        else:
            return jsonify({"error": "ce type de compte n'a pas de synchronisation (export ou saisie)"}), 400
    except Exception as exc:  # noqa: BLE001
        c.execute("UPDATE vendor_accounts SET last_error = ? WHERE name = ?", (str(exc)[:300], name))
        c.commit()
        return jsonify({"error": str(exc)[:300]}), 502
    c.execute("UPDATE vendor_accounts SET last_sync = ?, last_error = '', snapshot = ? WHERE name = ?", (time.time(), json.dumps(snapshot, ensure_ascii=False), name))
    updated, created_sw, created_ct = 0, 0, 0
    for s in snapshot:
        ct = c.execute("SELECT id, software_id FROM contracts WHERE vendor_account = ? AND sku = ?", (name, s["sku"])).fetchone()
        if ct:
            c.execute("UPDATE contracts SET quantity = ?, updated_at = ? WHERE id = ?", (s["quantity"], time.time(), ct["id"]))
            cid, updated = ct["id"], updated + 1
        else:
            row = c.execute("SELECT id FROM software WHERE lower(name) = lower(?)", (s["label"],)).fetchone()
            if row:
                sid = row["id"]
            else:
                sid = c.execute("INSERT INTO software (name, vendor, patterns, created_at) VALUES (?, 'Microsoft', '[]', ?)", (s["label"], time.time())).lastrowid
                created_sw += 1
            cid = c.execute("INSERT INTO contracts (software_id, site, label, kind, quantity, vendor_account, sku, notes, created_at, updated_at) VALUES (?, ?, ?, 'subscription', ?, ?, ?, 'synchronisé depuis le vendeur', ?, ?)",
                            (sid, v["site"], s["label"], s["quantity"], name, s["sku"], time.time(), time.time())).lastrowid
            created_ct += 1
        # attributions = utilisateurs du vendeur (remplace celles marquées « vendeur »)
        c.execute("DELETE FROM assignments WHERE contract_id = ? AND note = 'vendeur'", (cid,))
        for upn in s.get("users") or []:
            login, _new = resolve_or_create_user(c, upn, v["site"], "vendeur", mail=upn)
            try:
                c.execute("INSERT INTO assignments (contract_id, subject_kind, subject, site, since, note) VALUES (?, 'user', ?, ?, ?, 'vendeur')", (cid, login or upn, v["site"], _dt.date.today().isoformat()))
            except sqlite3.IntegrityError:
                pass
    c.commit()
    event("vendor-sync", "%s : %d SKU (%d contrats mis à jour, %d créés) par %s" % (name, len(snapshot), updated, created_ct, g.user["username"]))
    return jsonify({"status": "ok", "skus": len(snapshot), "updated": updated, "created_software": created_sw, "created_contracts": created_ct, "snapshot": snapshot}), 200


# -- installation / désinstallation via l'agent --------------------------------------------------
@app.route("/actions", methods=["GET"])
def actions_list():
    c = db()
    rows = [dict(r) for r in c.execute("SELECT * FROM actions ORDER BY id DESC LIMIT 100")]
    for a in rows:  # rafraîchit les états en attente auprès du central des agents
        if a["status"] in ("pending", "acked") and a.get("command_id"):
            try:
                r = requests.get("%s/commands/%s" % (SI_AGENT_URL, a["command_id"]), timeout=5)
                if r.status_code == 200:
                    cmd = r.json()
                    st = cmd.get("status")
                    if st in ("done", "failed"):
                        res = cmd.get("result") or {}
                        a["status"] = "done" if st == "done" and res.get("ok", True) else "failed"
                        a["result"] = (res.get("error") or (res.get("result") or {}).get("output") or "")[-2000:]
                        c.execute("UPDATE actions SET status = ?, result = ?, updated_at = ? WHERE id = ?", (a["status"], a["result"], time.time(), a["id"]))
            except (requests.RequestException, ValueError):
                pass
    c.commit()
    return jsonify({"actions": rows}), 200


@app.route("/actions", methods=["POST"])
def action_create():
    """{agent_id, action: install|uninstall, package, manager?, software_id?, confirm: <agent_id>} -> commande software_action à l'agent."""
    b = request.get_json(silent=True) or {}
    agent_id, action, package = str(b.get("agent_id") or ""), str(b.get("action") or ""), str(b.get("package") or "").strip()
    if not agent_id or action not in ("install", "uninstall") or not package:
        return jsonify({"error": "agent_id, action (install | uninstall) et package requis"}), 400
    if b.get("confirm") != agent_id:
        return jsonify({"error": "confirmation requise : confirm = identifiant de l'agent"}), 400
    params = {"action": action, "package": package}
    if b.get("manager"):
        params["manager"] = str(b["manager"])
    try:
        r = requests.post("%s/agents/%s/commands" % (SI_AGENT_URL, agent_id), json={"type": "software_action", "params": params}, timeout=8)
        if r.status_code not in (200, 201):
            return jsonify({"error": "central des agents : %s" % ((r.json() or {}).get("error") or r.status_code)}), 502
        cmd = r.json()
    except (requests.RequestException, ValueError) as exc:
        return jsonify({"error": "central des agents injoignable (%s)" % exc.__class__.__name__}), 502
    c = db()
    aid = c.execute("INSERT INTO actions (agent_id, host, action, package, manager, software_id, command_id, status, user, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?)",
                    (agent_id, str(b.get("host") or ""), action, package, params.get("manager", ""), b.get("software_id"), str(cmd.get("id")), g.user["username"], time.time(), time.time())).lastrowid
    c.commit()
    event("action", "%s %s sur %s (commande %s) par %s" % (action, package, agent_id, cmd.get("id"), g.user["username"]))
    _notify("licenses.action", "%s de %s sur %s" % ("installation" if action == "install" else "désinstallation", package, b.get("host") or agent_id), "Demandé par %s -- commande %s" % (g.user["username"], cmd.get("id")), {"agent": agent_id, "package": package})
    return jsonify({"status": "ok", "id": aid, "command_id": cmd.get("id")}), 200


@app.route("/events", methods=["GET"])
def events():
    return jsonify({"events": [dict(r) for r in db().execute("SELECT at, event, text, user FROM events ORDER BY id DESC LIMIT 200")]}), 200


if __name__ == "__main__":  # pragma: no cover
    app.run(host="0.0.0.0", port=5000)
