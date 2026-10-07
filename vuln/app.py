# -*- coding: utf-8 -*-
"""vuln-api -- vulnérabilités du SI (livraison #688).

Chaîne : SBOM CycloneDX (syft, sur l'hôte par l'agent ou ici sur un dossier
monté) → correspondance OSV (osv-scanner) → priorisation EPSS + KEV ×
exposition de l'actif → (option) dépôt dans Dependency-Track (`DT_URL` +
`DT_API_KEY`), qui garde l'historique, les politiques et les licences.

Les flux EPSS et KEV sont rechargés chaque jour (`VULN_FEEDS_HOURS`) et toutes
les vulnérabilités sont re-priorisées à chaque rechargement : une CVE
endormie qui devient exploitée remonte d'elle-même en P1."""
import json
import logging
import os
import pathlib
import re
import shutil
import sqlite3
import subprocess
import tempfile
import threading
import time
import uuid

import requests
from flask import Flask, jsonify, request
from flask_cors import CORS

import vulnlib

try:
    from version_endpoint import register_version_route
except ImportError:
    register_version_route = None

app = Flask(__name__)
CORS(app)
if register_version_route:
    register_version_route(app, "vuln")
log = logging.getLogger("vuln_api")
DATA = pathlib.Path(os.environ.get("VULN_DATA_DIR", "/data"))
DATA.mkdir(parents=True, exist_ok=True)
(DATA / "sboms").mkdir(exist_ok=True)
DB_PATH = os.environ.get("VULN_DB_PATH", str(DATA / "vuln.db"))
OSV_BIN = os.environ.get("OSV_SCANNER_BIN", "osv-scanner")
SYFT_BIN = os.environ.get("SYFT_BIN", "syft")
EPSS_URL = os.environ.get("EPSS_URL", "https://epss.empiricalsecurity.com/epss_scores-current.csv.gz")
KEV_URLS = [u for u in os.environ.get("KEV_URLS", "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json,"
                                       "https://raw.githubusercontent.com/cisagov/kev-data/main/known_exploited_vulnerabilities.json").split(",") if u.strip()]
DT_URL = os.environ.get("DT_URL", "").rstrip("/")
DT_API_KEY = os.environ.get("DT_API_KEY", "").strip()
SELF_SCAN_DIR = os.environ.get("VULN_SELF_SCAN_DIR", "/src")
# #693 : le dépôt monté contient aussi les données des modules (Go de GED,
# sauvegardes, bases) -- syft n'y trouverait rien d'utile et y passerait des heures.
SELF_SCAN_EXCLUDES = [e for e in os.environ.get("VULN_SELF_SCAN_EXCLUDES", "./**/node_modules/**,./**/.git/**,./**/data/**,./**/dist/**,"
                                                "./**/__pycache__/**,./**/.venv/**,./**/backups/**,./**/*.zip").split(",") if e.strip()]
OSV_EXTRA_ARGS = os.environ.get("OSV_SCANNER_ARGS", "").split()
NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ._:@/()+-]{0,119}$")
KINDS = ("host", "image", "app", "repo", "device")
_lock = threading.Lock()


def run_tool(argv, timeout=900):
    """Lance un outil (osv-scanner, syft) -> (code, stdout, stderr). Remplacé dans les tests."""
    p = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
    return p.returncode, p.stdout.decode("utf-8", "replace"), p.stderr.decode("utf-8", "replace")


def http_get(url, timeout=120):
    """Téléchargement d'un flux -> bytes. Remplacé dans les tests."""
    r = requests.get(url, timeout=timeout, headers={"User-Agent": "supervision-si/vuln-api"})
    r.raise_for_status()
    return r.content


def http_probe(url, timeout=10):
    """Joignabilité d'une URL -> (code HTTP ou None, erreur). Remplacé dans les tests."""
    try:
        r = requests.head(url, timeout=timeout, allow_redirects=True, headers={"User-Agent": "supervision-si/vuln-api"})
        if r.status_code in (403, 405):          # certains CDN refusent HEAD
            r = requests.get(url, timeout=timeout, stream=True, headers={"User-Agent": "supervision-si/vuln-api"})
            r.close()
        return r.status_code, ""
    except requests.RequestException as exc:
        return None, str(exc)[:200]


def db():
    cn = sqlite3.connect(DB_PATH, timeout=30)
    cn.row_factory = sqlite3.Row
    return cn


def init_db():
    with db() as cn:
        cn.executescript("""
        CREATE TABLE IF NOT EXISTS assets (name TEXT PRIMARY KEY, kind TEXT DEFAULT 'host', exposed INTEGER DEFAULT 0, source TEXT DEFAULT '',
            notes TEXT DEFAULT '', last_sbom_at INTEGER, components INTEGER DEFAULT 0, last_scan_error TEXT DEFAULT '', dt_status TEXT DEFAULT '');
        CREATE TABLE IF NOT EXISTS findings (asset TEXT NOT NULL, package TEXT, version TEXT, ecosystem TEXT, ids TEXT, cves TEXT, score REAL, score_source TEXT,
            summary TEXT, fixed TEXT, epss REAL, percentile REAL, kev INTEGER, priority TEXT, reason TEXT, first_seen INTEGER, last_seen INTEGER,
            PRIMARY KEY (asset, package, version, ids));
        CREATE INDEX IF NOT EXISTS idx_findings_prio ON findings(priority);
        CREATE TABLE IF NOT EXISTS epss (cve TEXT PRIMARY KEY, epss REAL, percentile REAL);
        CREATE TABLE IF NOT EXISTS kev (cve TEXT PRIMARY KEY, info TEXT);
        CREATE TABLE IF NOT EXISTS feeds (name TEXT PRIMARY KEY, at INTEGER, meta TEXT, error TEXT DEFAULT '');
        """)


init_db()


# ------------------------------------------------------------------ flux EPSS / KEV

def _epss_lookup(cn, cves):
    out = {}
    for c in cves:
        r = cn.execute("SELECT epss, percentile FROM epss WHERE cve = ?", (c,)).fetchone()
        if r:
            out[c] = (r["epss"], r["percentile"])
    return out


def _kev_lookup(cn, cves):
    out = {}
    for c in cves:
        r = cn.execute("SELECT info FROM kev WHERE cve = ?", (c,)).fetchone()
        if r:
            out[c] = json.loads(r["info"])
    return out


def refresh_feeds():
    """Recharge EPSS et KEV puis re-priorise tout. -> {epss: ..., kev: ...}."""
    res = {}
    now = int(time.time())
    try:
        scores, meta = vulnlib.parse_epss(http_get(EPSS_URL))
        if not scores:
            raise ValueError("fichier EPSS vide")
        with _lock, db() as cn:
            cn.execute("DELETE FROM epss")
            cn.executemany("INSERT INTO epss VALUES (?,?,?)", [(c, e, p) for c, (e, p) in scores.items()])
            cn.execute("INSERT OR REPLACE INTO feeds VALUES ('epss', ?, ?, '')", (now, json.dumps(dict(meta, count=len(scores)))))
        res["epss"] = dict(meta, count=len(scores))
    except Exception as exc:  # noqa: BLE001 -- flux indisponible : on garde l'ancien
        _feed_error("epss", exc)
        res["epss"] = {"error": str(exc)[:200]}
    last_exc = None
    for url in KEV_URLS:
        try:
            kev, meta = vulnlib.parse_kev(http_get(url.strip()))
            with _lock, db() as cn:
                cn.execute("DELETE FROM kev")
                cn.executemany("INSERT INTO kev VALUES (?,?)", [(c, json.dumps(i)) for c, i in kev.items()])
                cn.execute("INSERT OR REPLACE INTO feeds VALUES ('kev', ?, ?, '')", (now, json.dumps(dict(meta, source=url.strip()))))
            res["kev"] = dict(meta, source=url.strip())
            last_exc = None
            break
        except Exception as exc:  # noqa: BLE001 -- miroir suivant
            last_exc = exc
    if last_exc is not None:
        _feed_error("kev", last_exc)
        res["kev"] = {"error": str(last_exc)[:200]}
    res["reprioritized"] = reprioritize()
    return res


def _feed_error(name, exc):
    log.warning("flux %s indisponible : %s", name, exc)
    with db() as cn:
        if cn.execute("UPDATE feeds SET error = ? WHERE name = ?", (str(exc)[:300], name)).rowcount == 0:
            cn.execute("INSERT INTO feeds VALUES (?, NULL, '{}', ?)", (name, str(exc)[:300]))


def reprioritize(asset=None):
    with _lock, db() as cn:
        rows = cn.execute("SELECT f.*, a.exposed FROM findings f JOIN assets a ON a.name = f.asset" + (" WHERE f.asset = ?" if asset else ""),
                          (asset,) if asset else ()).fetchall()
        for r in rows:
            cves = json.loads(r["cves"] or "[]")
            p = vulnlib.prioritize({"cves": cves, "score": r["score"], "fixed": json.loads(r["fixed"] or "[]")},
                                   _epss_lookup(cn, cves), _kev_lookup(cn, cves), bool(r["exposed"]))
            cn.execute("UPDATE findings SET epss=?, percentile=?, kev=?, priority=?, reason=? WHERE asset=? AND package IS ? AND version IS ? AND ids=?",
                       (p["epss"], p["percentile"], int(p["kev"]), p["priority"], p["reason"], r["asset"], r["package"], r["version"], r["ids"]))
    return len(rows)


def _feeds_loop():
    hours = float(os.environ.get("VULN_FEEDS_HOURS", "24") or 24)
    time.sleep(30)
    while True:
        try:
            refresh_feeds()
        except Exception as exc:  # noqa: BLE001
            log.warning("rechargement des flux : %s", exc)
        time.sleep(hours * 3600)


if os.environ.get("VULN_FEEDS_THREAD", "1") == "1":
    threading.Thread(target=_feeds_loop, daemon=True).start()


# ------------------------------------------------------------------ SBOM → osv-scanner → constats

def ingest_sbom(name, bom_bytes, kind="host", exposed=None, source=""):
    """Enregistre le SBOM, lance osv-scanner, remplace les constats de l'actif
    (première apparition conservée), dépose dans Dependency-Track si configuré."""
    bom = json.loads(bom_bytes)
    if str(bom.get("bomFormat", "")).lower() != "cyclonedx":
        raise ValueError("SBOM CycloneDX JSON attendu (syft -o cyclonedx-json)")
    comps = vulnlib.sbom_components(bom)
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", name)[:80]
    path = DATA / "sboms" / ("%s.cdx.json" % safe)   # un fichier par actif (le dernier) ; osv-scanner reconnaît *.cdx.json
    path.write_bytes(bom_bytes)
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as out:
        out_path = out.name
    try:
        code, _o, err = run_tool([OSV_BIN, "scan", "source", "-L", str(path), "--format", "json", "--output-file", out_path] + OSV_EXTRA_ARGS)
        report = pathlib.Path(out_path).read_text(encoding="utf-8") if os.path.getsize(out_path) else ""
    finally:
        try:
            os.unlink(out_path)
        except OSError:
            pass
    # 0 = rien, 1 = vulnérabilités trouvées, 128 = aucun paquet ; le reste = échec
    scan_error = "" if code in (0, 1, 128) else ("osv-scanner %s : %s" % (code, err.strip().splitlines()[-1][:200] if err.strip() else "?"))
    found = vulnlib.osv_findings(report) if report and not scan_error else []
    now = int(time.time())
    with _lock, db() as cn:
        row = cn.execute("SELECT exposed FROM assets WHERE name = ?", (name,)).fetchone()
        exp = int(bool(exposed)) if exposed is not None else (row["exposed"] if row else 0)
        cn.execute("INSERT INTO assets (name, kind, exposed, source, last_sbom_at, components, last_scan_error) VALUES (?,?,?,?,?,?,?) "
                   "ON CONFLICT(name) DO UPDATE SET kind=excluded.kind, exposed=excluded.exposed, source=excluded.source, "
                   "last_sbom_at=excluded.last_sbom_at, components=excluded.components, last_scan_error=excluded.last_scan_error",
                   (name, kind, exp, source, now, len(comps), scan_error))
        if not scan_error:
            first = {(r["package"], r["version"], r["ids"]): r["first_seen"] for r in cn.execute("SELECT package, version, ids, first_seen FROM findings WHERE asset = ?", (name,))}
            cn.execute("DELETE FROM findings WHERE asset = ?", (name,))
            for f in found:
                p = vulnlib.prioritize(f, _epss_lookup(cn, f["cves"]), _kev_lookup(cn, f["cves"]), bool(exp))
                ids = json.dumps(p["ids"])
                cn.execute("INSERT OR REPLACE INTO findings VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                           (name, p["package"], p["version"], p["ecosystem"], ids, json.dumps(p["cves"]), p["score"], p["score_source"], p["summary"],
                            json.dumps(p["fixed"]), p["epss"], p["percentile"], int(p["kev"]), p["priority"], p["reason"],
                            first.get((p["package"], p["version"], ids), now), now))
    dt = push_dependency_track(name, kind, bom_bytes)
    if dt:
        with db() as cn:
            cn.execute("UPDATE assets SET dt_status = ? WHERE name = ?", (dt, name))
    return {"asset": name, "components": len(comps), "findings": len(found), "scan_error": scan_error or None, "dependency_track": dt or None}


def push_dependency_track(name, kind, bom_bytes):
    """PUT /api/v1/bom (projet créé au besoin, version = type d'actif). -> statut lisible ou ''."""
    if not (DT_URL and DT_API_KEY):
        return ""
    import base64
    try:
        r = requests.put(DT_URL + "/api/v1/bom", timeout=60, headers={"X-Api-Key": DT_API_KEY, "Content-Type": "application/json"},
                         json={"projectName": name, "projectVersion": kind, "autoCreate": True, "bom": base64.b64encode(bom_bytes).decode()})
        return "déposé (%s)" % r.status_code if r.ok else "refusé %s : %s" % (r.status_code, r.text[:120])
    except requests.RequestException as exc:
        return "injoignable : %s" % str(exc)[:120]


def _params():
    name = (request.args.get("asset") or "").strip()
    if not NAME_RE.match(name):
        raise ValueError("asset : nom de l'actif requis (lettres, chiffres, . _ - : @ / ( ) +)")
    kind = request.args.get("kind") or "host"
    if kind not in KINDS:
        raise ValueError("kind : %s" % ", ".join(KINDS))
    exposed = request.args.get("exposed")
    return name, kind, (None if exposed is None else exposed in ("1", "true", "oui"))


@app.route("/health")
def health():
    return jsonify({"ok": True}), 200


@app.route("/sbom", methods=["POST", "PUT"])
def sbom_route():
    """Dépôt d'un SBOM CycloneDX JSON (corps ou champ `file`) : `?asset=<nom>&kind=host|image|app|repo|device&exposed=0|1`."""
    try:
        name, kind, exposed = _params()
        raw = request.files["file"].read() if "file" in request.files else request.get_data()
        if not raw or len(raw) > 200 * 1024 * 1024:
            raise ValueError("SBOM vide ou trop volumineux")
        return jsonify(ingest_sbom(name, raw, kind, exposed, source=request.args.get("source", "dépôt"))), 201
    except (ValueError, json.JSONDecodeError) as exc:
        return jsonify({"error": str(exc)}), 400


# ------------------------------------------------------------------ travaux en arrière-plan (#693)
# « Analyser le dépôt » (syft) et « Recharger EPSS/KEV » durent plusieurs
# minutes : au-delà de 300 s le tls-proxy coupait la requête (504) et le hub
# affichait une erreur alors que le travail continuait. Ils deviennent des
# travaux : 202 + identifiant, suivi par GET /jobs/<id> ; ?wait=1 garde
# l'ancien comportement synchrone (scripts, tests).
JOBS = {}
_jobs_lock = threading.Lock()


def start_job(kind, fn, *args):
    """-> (travail, créé). Un seul travail en cours par type."""
    with _jobs_lock:
        for j in JOBS.values():
            if j["kind"] == kind and j["state"] == "running":
                return j, False
        job = {"id": uuid.uuid4().hex[:12], "kind": kind, "state": "running", "started": int(time.time()), "ended": None, "result": None, "error": None}
        JOBS[job["id"]] = job
        for old in sorted(JOBS.values(), key=lambda j: j["started"])[:-20]:
            if old["state"] != "running":
                JOBS.pop(old["id"], None)

    def run():
        try:
            job["result"] = fn(*args)
            job["state"] = "done"
        except Exception as exc:  # noqa: BLE001 -- remonté au hub tel quel
            log.warning("travail %s en échec : %s", kind, exc)
            job["error"] = str(exc)[:500]
            job["state"] = "error"
        job["ended"] = int(time.time())
    threading.Thread(target=run, daemon=True).start()
    return job, True


def _job_response(kind, fn, *args):
    job, created = start_job(kind, fn, *args)
    if request.args.get("wait") == "1":
        while job["state"] == "running":
            time.sleep(0.2)
        if job["state"] == "error":
            return jsonify({"error": job["error"], "job": job}), 502
        return jsonify(job["result"]), 201 if kind == "scan-self" else 200
    return jsonify(dict(job, already_running=not created)), 202


def do_scan_self(asset):
    if not os.path.isdir(SELF_SCAN_DIR):
        raise RuntimeError("dossier %s absent (monter le dépôt en lecture seule)" % SELF_SCAN_DIR)
    argv = [SYFT_BIN, "scan", "dir:%s" % SELF_SCAN_DIR, "-o", "cyclonedx-json", "-q"]
    for e in SELF_SCAN_EXCLUDES:
        argv += ["--exclude", e.strip()]
    code, out, err = run_tool(argv, timeout=3600)
    if code != 0 or not out.strip():
        raise RuntimeError("syft %s : %s" % (code, (err.strip().splitlines() or ["?"])[-1][:200]))
    return ingest_sbom(asset, out.encode("utf-8"), "repo", False, source="syft (central)")


@app.route("/scan/self", methods=["POST"])
def scan_self():
    """SBOM du dépôt supervision-si lui-même (monté en lecture seule) par syft, puis même chaîne -- en arrière-plan."""
    if not os.path.isdir(SELF_SCAN_DIR):
        return jsonify({"error": "dossier %s absent (monter le dépôt en lecture seule)" % SELF_SCAN_DIR}), 400
    return _job_response("scan-self", do_scan_self, request.args.get("asset") or "supervision-si (dépôt)")


@app.route("/jobs", methods=["GET"])
def jobs_route():
    return jsonify(sorted(JOBS.values(), key=lambda j: -j["started"])), 200


@app.route("/jobs/<job_id>", methods=["GET"])
def job_route(job_id):
    job = JOBS.get(job_id)
    if job is None:
        return jsonify({"error": "travail inconnu (vuln-api redémarré ?)"}), 404
    return jsonify(job), 200


# ------------------------------------------------------------------ diagnostic de l'installation (#693)

def _tool_version(argv):
    try:
        code, out, err = run_tool(argv, timeout=30)
    except (OSError, subprocess.SubprocessError) as exc:
        return {"ok": False, "error": str(exc)[:200]}
    text = (out or err).strip()
    line = next((l.strip() for l in text.splitlines() if re.search(r"\d+\.\d+", l)), text.splitlines()[0] if text else "")
    return {"ok": code == 0, "version": line[:120], "error": None if code == 0 else (err.strip() or "code %s" % code)[:200]}


def diag(network=True):
    """État de l'installation : outils, stockage, dépôt monté, base, flux, réseau, travaux. -> {ok, problems, ...}."""
    problems = []
    tools = {"syft": _tool_version([SYFT_BIN, "version"]), "osv-scanner": _tool_version([OSV_BIN, "--version"])}
    for name, t in tools.items():
        if not t["ok"]:
            problems.append("%s absent ou en échec dans l'image (reconstruire vuln-api) : %s" % (name, t.get("error")))
    storage = {"path": str(DATA)}
    try:
        with tempfile.NamedTemporaryFile(dir=str(DATA), prefix=".diag-"):
            pass
        storage["writable"] = True
        du = shutil.disk_usage(str(DATA))
        storage["free_gb"] = round(du.free / 1e9, 1)
        if du.free < 1e9:
            problems.append("moins de 1 Go libre sous %s" % DATA)
    except OSError as exc:
        storage.update(writable=False, error=str(exc)[:200])
        problems.append("dossier de données non inscriptible : %s" % exc)
    src = {"path": SELF_SCAN_DIR, "present": os.path.isdir(SELF_SCAN_DIR), "excludes": SELF_SCAN_EXCLUDES}
    if not src["present"]:
        problems.append("dépôt non monté sur %s : « Analyser le dépôt » indisponible" % SELF_SCAN_DIR)
    with db() as cn:
        counts = {t: cn.execute("SELECT COUNT(*) FROM %s" % t).fetchone()[0] for t in ("assets", "findings", "epss", "kev")}
        feeds = {r["name"]: {"at": r["at"], "error": r["error"] or None} for r in cn.execute("SELECT name, at, error FROM feeds")}
    for name in ("epss", "kev"):
        f = feeds.get(name)
        if not f or not f["at"]:
            problems.append("flux %s jamais chargé%s" % (name.upper(), (" : " + f["error"]) if f and f["error"] else " (bouton « Recharger EPSS et KEV »)"))
    net = {}
    if network:
        targets = [("api.osv.dev (osv-scanner)", "https://api.osv.dev/v1/vulns/GHSA-462w-v97r-4m45"), ("EPSS", EPSS_URL)]
        targets += [("KEV %d" % (i + 1), u.strip()) for i, u in enumerate(KEV_URLS)]
        if DT_URL:
            targets.append(("Dependency-Track", DT_URL + "/api/version"))
        for label, url in targets:
            code, err = http_probe(url)
            net[label] = {"url": url, "status": code, "ok": bool(code and code < 400), "error": err or None}
        if not net["api.osv.dev (osv-scanner)"]["ok"]:
            problems.append("api.osv.dev injoignable depuis le conteneur : osv-scanner ne trouvera rien (sortie Internet, DNS, proxy ?)")
        if not net["EPSS"]["ok"]:
            problems.append("flux EPSS injoignable")
        if not any(v["ok"] for k, v in net.items() if k.startswith("KEV")):
            problems.append("flux KEV injoignable (CISA et miroir GitHub)")
        if DT_URL and not net["Dependency-Track"]["ok"]:
            problems.append("Dependency-Track configuré (DT_URL) mais injoignable")
    running = [j for j in JOBS.values() if j["state"] == "running"]
    return {"ok": not problems, "problems": problems, "tools": tools, "storage": storage, "self_scan": src, "counts": counts,
            "feeds": feeds, "network": net, "dependency_track": bool(DT_URL and DT_API_KEY), "jobs_running": running}


@app.route("/diag", methods=["GET"])
def diag_route():
    """`?network=0` pour éviter les sondes externes."""
    return jsonify(diag(network=request.args.get("network") != "0")), 200


@app.route("/feeds", methods=["GET"])
def feeds_route():
    with db() as cn:
        return jsonify({r["name"]: {"at": r["at"], "meta": json.loads(r["meta"] or "{}"), "error": r["error"] or None}
                        for r in cn.execute("SELECT * FROM feeds")}), 200


@app.route("/feeds/refresh", methods=["POST"])
def feeds_refresh_route():
    return _job_response("feeds", refresh_feeds)


@app.route("/epss/<cve>", methods=["GET"])
def epss_route(cve):
    cve = cve.upper()
    with db() as cn:
        e = _epss_lookup(cn, [cve]).get(cve)
        k = _kev_lookup(cn, [cve]).get(cve)
    return jsonify({"cve": cve, "epss": e[0] if e else None, "percentile": e[1] if e else None, "kev": k}), 200


def _finding_public(r):
    d = dict(r)
    for k in ("ids", "cves", "fixed"):
        d[k] = json.loads(d.get(k) or "[]")
    d["kev"] = bool(d.get("kev"))
    return d


@app.route("/assets", methods=["GET"])
def assets_route():
    with db() as cn:
        rows = cn.execute("SELECT a.*, "
                          "(SELECT COUNT(*) FROM findings f WHERE f.asset = a.name AND f.priority = 'P1') AS p1, "
                          "(SELECT COUNT(*) FROM findings f WHERE f.asset = a.name AND f.priority = 'P2') AS p2, "
                          "(SELECT COUNT(*) FROM findings f WHERE f.asset = a.name AND f.priority = 'P3') AS p3, "
                          "(SELECT COUNT(*) FROM findings f WHERE f.asset = a.name AND f.priority = 'P4') AS p4, "
                          "(SELECT COUNT(*) FROM findings f WHERE f.asset = a.name AND f.kev = 1) AS kev "
                          "FROM assets a ORDER BY p1 DESC, p2 DESC, a.name").fetchall()
    return jsonify([dict(r, exposed=bool(r["exposed"])) for r in rows]), 200


@app.route("/assets/<path:name>", methods=["PATCH"])
def asset_patch(name):
    body = request.get_json(silent=True) or {}
    with db() as cn:
        if cn.execute("SELECT 1 FROM assets WHERE name = ?", (name,)).fetchone() is None:
            return jsonify({"error": "actif inconnu"}), 404
        if "exposed" in body:
            cn.execute("UPDATE assets SET exposed = ? WHERE name = ?", (int(bool(body["exposed"])), name))
        if body.get("kind") in KINDS:
            cn.execute("UPDATE assets SET kind = ? WHERE name = ?", (body["kind"], name))
        if "notes" in body:
            cn.execute("UPDATE assets SET notes = ? WHERE name = ?", (str(body["notes"])[:500], name))
    reprioritize(name)
    return jsonify({"ok": True}), 200


@app.route("/findings", methods=["GET"])
def findings_route():
    """`?asset=` `?priority=P1,P2` `?kev=1` `?limit=`."""
    q, args = "SELECT * FROM findings WHERE 1=1", []
    if request.args.get("asset"):
        q += " AND asset = ?"; args.append(request.args["asset"])
    prios = [p for p in (request.args.get("priority") or "").split(",") if p in ("P1", "P2", "P3", "P4")]
    if prios:
        q += " AND priority IN (%s)" % ",".join("?" * len(prios)); args += prios
    if request.args.get("kev") == "1":
        q += " AND kev = 1"
    q += " ORDER BY priority, kev DESC, epss DESC, score DESC LIMIT ?"
    args.append(max(1, min(5000, int(request.args.get("limit") or 500))))
    with db() as cn:
        return jsonify([_finding_public(r) for r in cn.execute(q, args)]), 200


@app.route("/summary", methods=["GET"])
def summary_route():
    with db() as cn:
        rows = [_finding_public(r) for r in cn.execute("SELECT priority, kev FROM findings")]
        assets = cn.execute("SELECT COUNT(*) AS n, SUM(exposed) AS exp FROM assets").fetchone()
        feeds = {r["name"]: {"at": r["at"], "error": r["error"] or None} for r in cn.execute("SELECT name, at, error FROM feeds")}
    s = vulnlib.summarize(rows)
    s.update(assets=assets["n"], exposed_assets=assets["exp"] or 0, feeds=feeds, dependency_track=bool(DT_URL and DT_API_KEY))
    return jsonify(s), 200
