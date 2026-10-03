# -*- coding: utf-8 -*-
"""dns-api -- DNS éditable de la tour de contrôle (livraison #656).

Choix de la personne (3 oct. 2026) : fournisseurs Internet OVH et Online/Scaleway avec CACHE, DNS INTRANET (BIND, mises à
jour dynamiques TSIG) en FALLBACK ; Nebula hors contexte pour l'instant (à prévoir côté relais du hub local au campus).

Modèle : une ZONE = un nom + une liste ORDONNÉE de fournisseurs (OVH / Scaleway / bind) ; une modification est appliquée à
TOUS les fournisseurs de la zone dans l'ordre ; si un fournisseur Internet est injoignable ou refuse, on continue (état
« dégradé », à rejouer), l'intranet reçoit toujours la modification -- c'est lui qui répond quand Internet manque. Le
CACHE (table records) est la dernière lecture de chaque fournisseur, consultable sans réseau, rafraîchi à la demande.
Chaque modification est JOURNALISÉE (avant/après, auteur, fournisseurs réussis/échoués) et RÉVERSIBLE (revert).

Secrets : coffre des accès (credentials-api, jeton interne), jamais ici. Noms/types validés par motifs fermés."""
import os, re, json, time, sqlite3, pathlib, logging, requests
from flask import Flask, jsonify, request
from flask_cors import CORS
import providers
try:
    from version_endpoint import register_version_route
except ImportError:
    register_version_route = None

app = Flask(__name__); CORS(app)
if register_version_route: register_version_route(app, "dns")
log = logging.getLogger("dns_api")
DATA = pathlib.Path(os.environ.get("DNS_DATA_DIR", "/data")); DATA.mkdir(parents=True, exist_ok=True)
DB_PATH = os.environ.get("DNS_DB_PATH", str(DATA / "dns.db"))
CREDENTIALS_API_URL = os.environ.get("CREDENTIALS_API_URL", "http://credentials-api:5000").rstrip("/")
CREDENTIALS_TOKEN = os.environ.get("CREDENTIALS_INTERNAL_TOKEN", "").strip()
KINDS = ("ovh", "scaleway", "bind")
PROVIDER_FACTORY = providers.build        # remplacé dans les tests
_cred_cache = {}

def db():
    cn = sqlite3.connect(DB_PATH, timeout=30); cn.row_factory = sqlite3.Row; cn.execute("PRAGMA foreign_keys = ON"); return cn

def init_db():
    with db() as cn:
        cn.executescript("""
        CREATE TABLE IF NOT EXISTS zones (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL, providers TEXT NOT NULL DEFAULT '[]', notes TEXT DEFAULT '',
            created_at TEXT, updated_at TEXT);
        CREATE TABLE IF NOT EXISTS records (zone TEXT NOT NULL, provider TEXT NOT NULL, name TEXT NOT NULL, type TEXT NOT NULL, value TEXT NOT NULL, ttl INTEGER,
            fetched_at TEXT, PRIMARY KEY (zone, provider, name, type, value));
        CREATE TABLE IF NOT EXISTS provider_state (zone TEXT NOT NULL, provider TEXT NOT NULL, status TEXT DEFAULT 'unknown', last_ok TEXT DEFAULT '', last_error TEXT DEFAULT '',
            pending INTEGER DEFAULT 0, PRIMARY KEY (zone, provider));
        CREATE TABLE IF NOT EXISTS changes (id INTEGER PRIMARY KEY AUTOINCREMENT, zone TEXT NOT NULL, name TEXT NOT NULL, type TEXT NOT NULL, before TEXT DEFAULT '',
            after TEXT DEFAULT '', ttl INTEGER, action TEXT NOT NULL, by_user TEXT DEFAULT '', at TEXT, results TEXT DEFAULT '{}', status TEXT DEFAULT '', reverted_by INTEGER);
        """)
init_db()
def now(): return time.strftime("%Y-%m-%dT%H:%M:%S")

def credentials_for(name):
    """(user, password) depuis le coffre (même motif que mikrotik #498) ; ProviderError lisible sinon."""
    hit = _cred_cache.get(name)
    if hit and hit[0] > time.monotonic(): return hit[1], hit[2]
    if not CREDENTIALS_TOKEN: raise providers.ProviderError("coffre des accès non configuré côté dns (CREDENTIALS_INTERNAL_TOKEN)")
    try:
        r = requests.get(f"{CREDENTIALS_API_URL}/credentials/reveal/{name}", timeout=5, headers={"X-Credentials-Token": CREDENTIALS_TOKEN, "X-Credentials-Consumer": "dns-api"})
    except requests.RequestException: raise providers.ProviderError("coffre des accès injoignable")
    if r.status_code == 404: raise providers.ProviderError(f"accès « {name} » absent du coffre (tuile Accès d'équipements)")
    if r.status_code != 200: raise providers.ProviderError(f"coffre : HTTP {r.status_code}")
    d = r.json(); u, p = d.get("username") or "", d.get("password") or ""
    _cred_cache[name] = (time.monotonic() + 60, u, p); return u, p

def zone_public(r):
    z = dict(r); z["providers"] = json.loads(z.get("providers") or "[]"); return z

def get_zone(name):
    with db() as cn: r = cn.execute("SELECT * FROM zones WHERE name = ?", (name,)).fetchone()
    return zone_public(r) if r else None

def validate_zone(b):
    name = (b.get("name") or "").strip().lower().rstrip(".")
    if not re.fullmatch(r"[a-z0-9.-]{3,253}", name) or "." not in name: return None, "nom de zone invalide"
    provs = b.get("providers") or []
    if not isinstance(provs, list) or not provs: return None, "au moins un fournisseur {kind, credential}"
    out = []
    for i, p in enumerate(provs, 1):
        if p.get("kind") not in KINDS: return None, "fournisseur %d : kind ovh | scaleway | bind" % i
        if not (p.get("credential") or "").strip(): return None, "fournisseur %d : credential (nom dans le coffre) requis" % i
        if p["kind"] == "bind" and not (p.get("server") or "").strip(): return None, "fournisseur %d (bind) : server requis" % i
        out.append(dict(kind=p["kind"], credential=p["credential"].strip(), label=str(p.get("label") or p["kind"])[:40], endpoint=p.get("endpoint") or "", server=(p.get("server") or "").strip(), port=int(p.get("port") or 53), algorithm=p.get("algorithm") or "hmac-sha256",
                        role=("intranet" if p["kind"] == "bind" else "internet")))
    return dict(name=name, providers=out, notes=str(b.get("notes") or "")), None

def validate_record(b):
    name = (b.get("name") or "").strip().rstrip("."); rtype = (b.get("type") or "A").upper(); value = (b.get("value") or "").strip()
    if not providers.NAME_RE.match(name): return None, "nom d'enregistrement invalide (@, www, api.int…)"
    if rtype not in providers.TYPES: return None, "type : " + " | ".join(providers.TYPES)
    if not value or len(value) > 1000 or "\n" in value: return None, "valeur requise"
    if rtype == "A" and not re.fullmatch(r"(\d{1,3}\.){3}\d{1,3}", value): return None, "A : adresse IPv4 attendue"
    try: ttl = int(b.get("ttl") or 300)
    except (TypeError, ValueError): return None, "ttl entier"
    return dict(name=name, type=rtype, value=value, ttl=max(60, min(ttl, 86400))), None

def provider_for(spec): return PROVIDER_FACTORY(spec, credentials_for)

def _set_state(cn, zone, label, ok, err=""):
    cn.execute("""INSERT INTO provider_state (zone, provider, status, last_ok, last_error, pending) VALUES (?,?,?,?,?,?)
                  ON CONFLICT(zone, provider) DO UPDATE SET status = excluded.status, last_ok = CASE WHEN excluded.status = 'ok' THEN excluded.last_ok ELSE provider_state.last_ok END,
                  last_error = excluded.last_error, pending = CASE WHEN excluded.status = 'ok' THEN 0 ELSE provider_state.pending + 1 END""",
               (zone, label, "ok" if ok else "degraded", now() if ok else "", err[:300], 0 if ok else 1))

# ------------------------------------------------------------------ zones
@app.route("/health")
def health(): return jsonify(status="ok", vault=bool(CREDENTIALS_TOKEN))

@app.route("/zones", methods=["GET"])
def zones_list():
    with db() as cn:
        zs = [zone_public(r) for r in cn.execute("SELECT * FROM zones ORDER BY name")]
        for z in zs:
            z["state"] = [dict(r) for r in cn.execute("SELECT provider, status, last_ok, last_error, pending FROM provider_state WHERE zone = ?", (z["name"],))]
            z["cached"] = cn.execute("SELECT count(DISTINCT name || '/' || type) FROM records WHERE zone = ?", (z["name"],)).fetchone()[0]
            z["providers"] = [{k: v for k, v in p.items() if k != "credential"} | {"credential": p["credential"]} for p in z["providers"]]
    return jsonify(zones=zs, kinds=list(KINDS))

@app.route("/zones", methods=["POST"])
def zones_create():
    f, err = validate_zone(request.get_json(silent=True) or {})
    if err: return jsonify(error=err), 400
    with db() as cn:
        if cn.execute("SELECT 1 FROM zones WHERE name = ?", (f["name"],)).fetchone(): return jsonify(error="zone déjà déclarée"), 409
        cn.execute("INSERT INTO zones (name, providers, notes, created_at, updated_at) VALUES (?,?,?,?,?)", (f["name"], json.dumps(f["providers"]), f["notes"], now(), now()))
    return jsonify(zone=get_zone(f["name"])), 201

@app.route("/zones/<zone>", methods=["PUT", "DELETE"])
def zones_edit(zone):
    z = get_zone(zone)
    if not z: return jsonify(error="zone inconnue"), 404
    if request.method == "DELETE":
        with db() as cn:
            for t in ("records", "provider_state", "changes"): cn.execute(f"DELETE FROM {t} WHERE zone = ?", (zone,))
            cn.execute("DELETE FROM zones WHERE name = ?", (zone,))
        return jsonify(ok=True)
    f, err = validate_zone({**z, **(request.get_json(silent=True) or {}), "name": zone})
    if err: return jsonify(error=err), 400
    with db() as cn: cn.execute("UPDATE zones SET providers = ?, notes = ?, updated_at = ? WHERE name = ?", (json.dumps(f["providers"]), f["notes"], now(), zone))
    return jsonify(zone=get_zone(zone))

# ------------------------------------------------------------------ enregistrements (cache + rafraîchissement)
@app.route("/zones/<zone>/records", methods=["GET"])
def records_get(zone):
    z = get_zone(zone)
    if not z: return jsonify(error="zone inconnue"), 404
    refreshed = {}
    if request.args.get("refresh") == "1":
        with db() as cn:
            for p in z["providers"]:
                try:
                    recs = provider_for(p).list_records(zone)
                    cn.execute("DELETE FROM records WHERE zone = ? AND provider = ?", (zone, p["label"]))
                    for r in recs: cn.execute("INSERT OR REPLACE INTO records (zone, provider, name, type, value, ttl, fetched_at) VALUES (?,?,?,?,?,?,?)", (zone, p["label"], r["name"], r["type"], r["value"], r.get("ttl"), now()))
                    _set_state(cn, zone, p["label"], True); refreshed[p["label"]] = len(recs)
                except (providers.ProviderError, Exception) as e:
                    _set_state(cn, zone, p["label"], False, str(e)); refreshed[p["label"]] = "erreur : " + str(e)[:200]
    with db() as cn:
        rows = [dict(r) for r in cn.execute("SELECT * FROM records WHERE zone = ? ORDER BY name, type, provider", (zone,))]
        state = [dict(r) for r in cn.execute("SELECT provider, status, last_ok, last_error, pending FROM provider_state WHERE zone = ?", (zone,))]
    # vue consolidée : par (name,type), valeur par fournisseur ; divergence si les fournisseurs ne disent pas la même chose
    cons = {}
    for r in rows:
        k = (r["name"], r["type"]); e = cons.setdefault(k, dict(name=r["name"], type=r["type"], by_provider={}, ttl=r["ttl"]))
        e["by_provider"].setdefault(r["provider"], []).append(r["value"])
    out = []
    for e in cons.values():
        vals = {tuple(sorted(v)) for v in e["by_provider"].values()}
        e["divergent"] = len(vals) > 1 and len(e["by_provider"]) > 1; e["value"] = sorted(next(iter(vals)))[0] if vals else ""; out.append(e)
    return jsonify(records=sorted(out, key=lambda x: (x["name"], x["type"])), state=state, refreshed=refreshed, providers=[p["label"] for p in z["providers"]])

def apply_change(zone, z, rec, action, by_user):
    """Applique à chaque fournisseur dans l'ordre ; journalise ; renvoie (change, status)."""
    with db() as cn:
        before = [r["value"] for r in cn.execute("SELECT value FROM records WHERE zone = ? AND name = ? AND type = ? GROUP BY value", (zone, rec["name"], rec["type"]))]
    results = {}
    for p in z["providers"]:
        try:
            prov = provider_for(p)
            if action == "set": prov.set_record(zone, rec["name"], rec["type"], rec["value"], rec["ttl"])
            else: prov.delete_record(zone, rec["name"], rec["type"])
            results[p["label"]] = {"ok": True}
            with db() as cn:
                cn.execute("DELETE FROM records WHERE zone = ? AND provider = ? AND name = ? AND type = ?", (zone, p["label"], rec["name"], rec["type"]))
                if action == "set": cn.execute("INSERT OR REPLACE INTO records (zone, provider, name, type, value, ttl, fetched_at) VALUES (?,?,?,?,?,?,?)", (zone, p["label"], rec["name"], rec["type"], rec["value"], rec["ttl"], now()))
                _set_state(cn, zone, p["label"], True)
        except Exception as e:
            results[p["label"]] = {"ok": False, "error": str(e)[:300]}
            with db() as cn: _set_state(cn, zone, p["label"], False, str(e))
    oks = [k for k, v in results.items() if v["ok"]]; status = "ok" if len(oks) == len(results) else ("partial" if oks else "failed")
    with db() as cn:
        cur = cn.execute("INSERT INTO changes (zone, name, type, before, after, ttl, action, by_user, at, results, status) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                         (zone, rec["name"], rec["type"], json.dumps(before), rec.get("value", ""), rec.get("ttl"), action, by_user, now(), json.dumps(results, ensure_ascii=False), status))
        ch = dict(cn.execute("SELECT * FROM changes WHERE id = ?", (cur.lastrowid,)).fetchone())
    ch["results"] = results; ch["before"] = before; return ch, status

@app.route("/zones/<zone>/records", methods=["PUT"])
def records_put(zone):
    z = get_zone(zone)
    if not z: return jsonify(error="zone inconnue"), 404
    b = request.get_json(silent=True) or {}; rec, err = validate_record(b)
    if err: return jsonify(error=err), 400
    ch, status = apply_change(zone, z, rec, "set", str(b.get("by_user") or ""))
    return jsonify(change=ch, status=status), (200 if status == "ok" else 207 if status == "partial" else 502)

@app.route("/zones/<zone>/records", methods=["DELETE"])
def records_delete(zone):
    z = get_zone(zone)
    if not z: return jsonify(error="zone inconnue"), 404
    b = request.get_json(silent=True) or {}; rec, err = validate_record({**b, "value": b.get("value") or "-"})
    if err: return jsonify(error=err), 400
    ch, status = apply_change(zone, z, dict(rec, value=""), "delete", str(b.get("by_user") or ""))
    return jsonify(change=ch, status=status), (200 if status == "ok" else 207 if status == "partial" else 502)

@app.route("/zones/<zone>/changes", methods=["GET"])
def changes_list(zone):
    with db() as cn: rows = [dict(r) for r in cn.execute("SELECT * FROM changes WHERE zone = ? ORDER BY id DESC LIMIT 100", (zone,))]
    for r in rows: r["results"] = json.loads(r["results"] or "{}"); r["before"] = json.loads(r["before"] or "[]")
    return jsonify(changes=rows)

@app.route("/changes/<int:cid>/revert", methods=["POST"])
def change_revert(cid):
    """Retour en arrière : remet la valeur d'avant (ou supprime si l'enregistrement n'existait pas), nouvelle entrée de journal liée."""
    with db() as cn: ch = cn.execute("SELECT * FROM changes WHERE id = ?", (cid,)).fetchone()
    if not ch: return jsonify(error="modification inconnue"), 404
    z = get_zone(ch["zone"]); before = json.loads(ch["before"] or "[]"); by = str((request.get_json(silent=True) or {}).get("by_user") or "")
    rec = dict(name=ch["name"], type=ch["type"], value=before[0] if before else "", ttl=ch["ttl"] or 300)
    new, status = apply_change(ch["zone"], z, rec, "set" if before else "delete", by)
    with db() as cn: cn.execute("UPDATE changes SET reverted_by = ? WHERE id = ?", (new["id"], cid))
    return jsonify(change=new, status=status), (200 if status == "ok" else 207 if status == "partial" else 502)

@app.route("/zones/<zone>/replay", methods=["POST"])
def replay(zone):
    """Rejoue sur les fournisseurs dégradés les modifications partielles (fallback rattrapé quand Internet revient)."""
    z = get_zone(zone)
    if not z: return jsonify(error="zone inconnue"), 404
    with db() as cn: rows = [dict(r) for r in cn.execute("SELECT * FROM changes WHERE zone = ? AND status = 'partial' AND reverted_by IS NULL ORDER BY id", (zone,))]
    done = 0; errors = []
    for ch in rows:
        res = json.loads(ch["results"] or "{}"); still = {}
        for p in z["providers"]:
            if res.get(p["label"], {}).get("ok"): continue
            try:
                prov = provider_for(p)
                if ch["action"] == "set": prov.set_record(zone, ch["name"], ch["type"], ch["after"], ch["ttl"] or 300)
                else: prov.delete_record(zone, ch["name"], ch["type"])
                res[p["label"]] = {"ok": True}
                with db() as cn: _set_state(cn, zone, p["label"], True)
            except Exception as e: still[p["label"]] = str(e)[:200]; res[p["label"]] = {"ok": False, "error": str(e)[:300]}
        status = "ok" if all(v["ok"] for v in res.values()) else "partial"
        with db() as cn: cn.execute("UPDATE changes SET results = ?, status = ? WHERE id = ?", (json.dumps(res, ensure_ascii=False), status, ch["id"]))
        if status == "ok": done += 1
        else: errors.append({"change": ch["id"], **still})
    return jsonify(replayed=done, remaining=len(rows) - done, errors=errors)
