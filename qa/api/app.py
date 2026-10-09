"""qa-api -- module « Tests QA en ligne » du hub (livraison #651).

Teste en ligne un site DÉPLOYÉ -- une application portée par l'IA de portage ou n'importe quel autre site du parc,
porté ou non : on décrit un site (URL, étapes de connexion), des scénarios pas à pas (aller à, saisir, cliquer,
vérifier…), on les joue dans un vrai Chromium (Playwright, captures à chaque étape). Mode QA : un scénario qui
échoue ou révèle un manque crée depuis l'exécution un TICKET (incident ou évolution) dans le module Tickets ; le
scénario devient alors un test TRAVERSANT de non-régression, rejoué en campagne (tous les scénarios de
non-régression d'un site) -- la boucle QA → ticket → non-régression demandée.

Décisions :
- Playwright vit dans ce conteneur (image Playwright officielle) ; le runner (runner.py) est injectable, les tests
  de l'API tournent sans navigateur (FakeRunner).
- une exécution = synchrone (délai borné par étape), captures sous /data/runs/<id>/ servies par l'API ;
- le ticket est créé via TICKETS_API_INTERNAL_URL (réseau Docker), type résolu par libellé (« Incident »,
  « Évolution ») s'il existe dans le référentiel des types, sinon sans type ; jamais de doublon : un run porte
  au plus un ticket ;
- secrets de connexion des sites stockés en clair dans qa.db (même décision assumée que DBA : voir dba/README.md),
  jamais renvoyés au hub (champ masqué) ;
- tout nom venant d'une requête est validé (actions dans une liste fermée) avant usage."""
import os, json, sqlite3, time, pathlib, logging, shutil, requests
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import qa_steps
import qa_design
import qa_visual
import qa_mockup
try:
    from version_endpoint import register_version_route
except ImportError:
    register_version_route = None

app = Flask(__name__); CORS(app)
if register_version_route: register_version_route(app, "qa")
log = logging.getLogger("qa_api")
DATA = pathlib.Path(os.environ.get("QA_DATA_DIR", "/data")); RUNS = DATA / "runs"; RUNS.mkdir(parents=True, exist_ok=True)
DB_PATH = os.environ.get("QA_DB_PATH", str(DATA / "qa.db"))
TICKETS = os.environ.get("TICKETS_API_INTERNAL_URL", "").rstrip("/")
STEP_TIMEOUT = int(os.environ.get("QA_STEP_TIMEOUT_MS", "15000"))
RUNNER = None     # module injectable (tests) ; défaut : runner.py (Playwright)

def runner():
    global RUNNER
    if RUNNER is None:
        import runner as r; RUNNER = r
    return RUNNER

def db():
    cn = sqlite3.connect(DB_PATH); cn.row_factory = sqlite3.Row; cn.execute("PRAGMA foreign_keys = ON"); return cn

def init_db():
    with db() as cn:
        cn.executescript("""
        CREATE TABLE IF NOT EXISTS sites (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, base_url TEXT NOT NULL, login_steps TEXT DEFAULT '[]',
            notes TEXT DEFAULT '', ported INTEGER DEFAULT 0, created_at TEXT, updated_at TEXT);
        CREATE TABLE IF NOT EXISTS scenarios (id INTEGER PRIMARY KEY AUTOINCREMENT, site_id INTEGER NOT NULL REFERENCES sites(id) ON DELETE CASCADE,
            name TEXT NOT NULL, kind TEXT DEFAULT 'qa', steps TEXT NOT NULL, tags TEXT DEFAULT '', ticket_id INTEGER, created_at TEXT, updated_at TEXT);
        CREATE TABLE IF NOT EXISTS runs (id INTEGER PRIMARY KEY AUTOINCREMENT, scenario_id INTEGER NOT NULL REFERENCES scenarios(id) ON DELETE CASCADE,
            campaign_id INTEGER, started_at TEXT, finished_at TEXT, status TEXT, results TEXT DEFAULT '[]', final_url TEXT DEFAULT '', error TEXT DEFAULT '',
            ticket_id INTEGER, ticket_kind TEXT DEFAULT '', by_user TEXT DEFAULT '');
        CREATE TABLE IF NOT EXISTS campaigns (id INTEGER PRIMARY KEY AUTOINCREMENT, site_id INTEGER NOT NULL REFERENCES sites(id) ON DELETE CASCADE,
            kind TEXT DEFAULT 'non-regression', started_at TEXT, finished_at TEXT, total INTEGER DEFAULT 0, passed INTEGER DEFAULT 0, by_user TEXT DEFAULT '');
        """)
        for col in ("ref_run_id INTEGER", "mask TEXT DEFAULT ''"):   # #727 : référence visuelle, zones masquées à la capture
            try: cn.execute("ALTER TABLE scenarios ADD COLUMN " + col)
            except sqlite3.OperationalError: pass
        for col in ("mockup_id INTEGER", "variant INTEGER"):   # #728 : exécutions d'une variante de maquette (hors historique)
            try: cn.execute("ALTER TABLE runs ADD COLUMN " + col)
            except sqlite3.OperationalError: pass
        cn.execute("""CREATE TABLE IF NOT EXISTS mockups (id INTEGER PRIMARY KEY AUTOINCREMENT, scenario_id INTEGER NOT NULL REFERENCES scenarios(id) ON DELETE CASCADE,
            base_run_id INTEGER, name TEXT NOT NULL, variants TEXT DEFAULT '[]', status TEXT DEFAULT 'brouillon', chosen INTEGER, decision_comment TEXT DEFAULT '',
            ticket_id INTEGER, by_user TEXT DEFAULT '', created_at TEXT, updated_at TEXT)""")
        for t, col in (("scenarios", "target_run_id INTEGER"), ("scenarios", "target_mockup_id INTEGER"),   # #729 : maquette validée = cible
                       ("mockups", "integrated_run_id INTEGER"), ("mockups", "integrated_at TEXT")):
            try: cn.execute(f"ALTER TABLE {t} ADD COLUMN {col}")
            except sqlite3.OperationalError: pass
init_db()
def now(): return time.strftime("%Y-%m-%dT%H:%M:%S")
def d(r): return dict(r) if r is not None else None

def site_out(r, with_login=False):
    s = d(r); steps = json.loads(s.pop("login_steps") or "[]")
    s["login_steps"] = [dict(x, value="••••" if x.get("action") == "fill" and ("pass" in (x.get("selector") or "").lower() or "mdp" in (x.get("selector") or "").lower()) and not with_login else x.get("value", "")) for x in steps]
    s["has_login"] = bool(steps); return s

def scenario_out(r):
    s = d(r); s["steps"] = json.loads(s.pop("steps") or "[]"); return s

def run_out(r):
    s = d(r); s["results"] = json.loads(s.pop("results") or "[]"); s["summary"] = qa_steps.summarize([x for x in s["results"] if not x.get("login")]); return s

# ------------------------------------------------------------------ sites
@app.route("/health")
def health(): return jsonify(status="ok", tickets=bool(TICKETS))

@app.route("/catalog")
def catalog(): return jsonify(actions=[dict(id=k, label=v, fields=list(qa_steps.ACTIONS[k])) for k, v in qa_steps.ACTION_LABELS.items()])

@app.route("/sites", methods=["GET"])
def sites_list():
    with db() as cn:
        rows = cn.execute("""SELECT s.*, (SELECT count(*) FROM scenarios x WHERE x.site_id = s.id) AS scenarios,
                             (SELECT count(*) FROM scenarios x WHERE x.site_id = s.id AND x.kind = 'non-regression') AS nr,
                             (SELECT status FROM runs r JOIN scenarios x ON x.id = r.scenario_id WHERE x.site_id = s.id ORDER BY r.id DESC LIMIT 1) AS last_status
                             FROM sites s ORDER BY s.name""").fetchall()
    return jsonify(sites=[site_out(r) for r in rows])

def _site_body(b):
    name, url = (b.get("name") or "").strip(), (b.get("base_url") or "").strip()
    if not name or not url.startswith(("http://", "https://")): raise ValueError("Nom et URL (http(s)://…) obligatoires")
    login = qa_steps.normalize_steps(b["login_steps"]) if b.get("login_steps") else []
    return dict(name=name, base_url=url.rstrip("/"), login_steps=json.dumps(login, ensure_ascii=False), notes=b.get("notes") or "", ported=1 if b.get("ported") else 0)

@app.route("/sites", methods=["POST"])
def sites_create():
    try: f = _site_body(request.get_json(silent=True) or {})
    except ValueError as e: return jsonify(error=str(e)), 400
    with db() as cn:
        cur = cn.execute("INSERT INTO sites (name, base_url, login_steps, notes, ported, created_at, updated_at) VALUES (?,?,?,?,?,?,?)", (*f.values(), now(), now()))
        r = cn.execute("SELECT * FROM sites WHERE id = ?", (cur.lastrowid,)).fetchone()
    return jsonify(site=site_out(r)), 201

@app.route("/sites/<int:sid>", methods=["PUT"])
def sites_update(sid):
    b = request.get_json(silent=True) or {}
    with db() as cn:
        cur = cn.execute("SELECT * FROM sites WHERE id = ?", (sid,)).fetchone()
        if not cur: return jsonify(error="Site inconnu"), 404
        if "login_steps" in b and b["login_steps"] and any(x.get("value") == "••••" for x in b["login_steps"]):     # mot de passe masqué renvoyé tel quel : on garde l'ancien
            old = json.loads(cur["login_steps"] or "[]")
            for i, x in enumerate(b["login_steps"]):
                if x.get("value") == "••••" and i < len(old): x["value"] = old[i].get("value", "")
        try: f = _site_body({**d(cur), "login_steps": json.loads(cur["login_steps"] or "[]"), **b})
        except ValueError as e: return jsonify(error=str(e)), 400
        cn.execute("UPDATE sites SET name=?, base_url=?, login_steps=?, notes=?, ported=?, updated_at=? WHERE id=?", (*f.values(), now(), sid))
        r = cn.execute("SELECT * FROM sites WHERE id = ?", (sid,)).fetchone()
    return jsonify(site=site_out(r))

@app.route("/sites/<int:sid>", methods=["DELETE"])
def sites_delete(sid):
    with db() as cn:
        ids = [r[0] for r in cn.execute("SELECT r.id FROM runs r JOIN scenarios x ON x.id = r.scenario_id WHERE x.site_id = ?", (sid,))]
        n = cn.execute("DELETE FROM sites WHERE id = ?", (sid,)).rowcount
    for i in ids: shutil.rmtree(RUNS / str(i), ignore_errors=True)
    return (jsonify(ok=True), 200) if n else (jsonify(error="Site inconnu"), 404)

@app.route("/sites/<int:sid>/probe", methods=["POST"])
def sites_probe(sid):
    with db() as cn: s = cn.execute("SELECT * FROM sites WHERE id = ?", (sid,)).fetchone()
    if not s: return jsonify(error="Site inconnu"), 404
    try: return jsonify(probe=runner().probe(s["base_url"], STEP_TIMEOUT))
    except Exception as e: return jsonify(error=f"Reconnaissance impossible : {str(e).splitlines()[0][:200]}"), 502

# ------------------------------------------------------------------ scénarios
@app.route("/sites/<int:sid>/scenarios", methods=["GET"])
def scenarios_list(sid):
    with db() as cn:
        rows = cn.execute("""SELECT x.*, (SELECT status FROM runs r WHERE r.scenario_id = x.id ORDER BY r.id DESC LIMIT 1) AS last_status,
                             (SELECT started_at FROM runs r WHERE r.scenario_id = x.id ORDER BY r.id DESC LIMIT 1) AS last_run_at FROM scenarios x WHERE x.site_id = ? ORDER BY x.kind, x.name""", (sid,)).fetchall()
    return jsonify(scenarios=[scenario_out(r) for r in rows])

@app.route("/sites/<int:sid>/scenarios", methods=["POST"])
def scenarios_create(sid):
    b = request.get_json(silent=True) or {}
    try: steps = qa_steps.normalize_steps(b.get("steps"))
    except ValueError as e: return jsonify(error=str(e)), 400
    if not (b.get("name") or "").strip(): return jsonify(error="Nom du scénario obligatoire"), 400
    kind = b.get("kind") if b.get("kind") in ("qa", "non-regression") else "qa"
    with db() as cn:
        if not cn.execute("SELECT 1 FROM sites WHERE id = ?", (sid,)).fetchone(): return jsonify(error="Site inconnu"), 404
        cur = cn.execute("INSERT INTO scenarios (site_id, name, kind, steps, tags, created_at, updated_at) VALUES (?,?,?,?,?,?,?)",
                         (sid, b["name"].strip(), kind, json.dumps(steps, ensure_ascii=False), b.get("tags") or "", now(), now()))
        r = cn.execute("SELECT * FROM scenarios WHERE id = ?", (cur.lastrowid,)).fetchone()
    return jsonify(scenario=scenario_out(r)), 201

@app.route("/sites/<int:sid>/hub-tour", methods=["POST"])
def hub_tour(sid):
    """#721 : « Tour du hub » -- un scénario qui visite chaque vue (?view=…) et l'audite (conformité visuelle et ergonomique).
    Corps : {views: [{view, label}], wait_ms?, strict?, name?} -- la liste vient du hub (catalogue de ses thématiques)."""
    b = request.get_json(silent=True) or {}
    steps = qa_design.hub_tour_steps(b.get("views"), int(b.get("wait_ms") or 1500), bool(b.get("strict")))
    if not steps: return jsonify(error="Aucune vue valide (liste {view, label} attendue)"), 400
    name = (b.get("name") or "Tour du hub — conformité visuelle").strip()[:120]
    with db() as cn:
        if not cn.execute("SELECT 1 FROM sites WHERE id = ?", (sid,)).fetchone(): return jsonify(error="Site inconnu"), 404
        old = cn.execute("SELECT id FROM scenarios WHERE site_id = ? AND name = ?", (sid, name)).fetchone()
        if old:   # régénéré : même scénario, étapes à jour (les exécutions passées restent comparables)
            cn.execute("UPDATE scenarios SET steps = ?, updated_at = ? WHERE id = ?", (json.dumps(qa_steps.normalize_steps(steps), ensure_ascii=False), now(), old["id"])); xid = old["id"]
        else:
            xid = cn.execute("INSERT INTO scenarios (site_id, name, kind, steps, tags, created_at, updated_at) VALUES (?,?,?,?,?,?,?)",
                             (sid, name, "qa", json.dumps(qa_steps.normalize_steps(steps), ensure_ascii=False), "design", now(), now())).lastrowid
        cn.commit()
        r = cn.execute("SELECT * FROM scenarios WHERE id = ?", (xid,)).fetchone()
    return jsonify(scenario=scenario_out(r), views=len(steps) // 3), 201 if not old else 200

@app.route("/scenarios/<int:xid>", methods=["PUT"])
def scenarios_update(xid):
    b = request.get_json(silent=True) or {}
    with db() as cn:
        cur = cn.execute("SELECT * FROM scenarios WHERE id = ?", (xid,)).fetchone()
        if not cur: return jsonify(error="Scénario inconnu"), 404
        try: steps = qa_steps.normalize_steps(b["steps"]) if "steps" in b else json.loads(cur["steps"])
        except ValueError as e: return jsonify(error=str(e)), 400
        kind = b.get("kind") if b.get("kind") in ("qa", "non-regression") else cur["kind"]
        cn.execute("UPDATE scenarios SET name=?, kind=?, steps=?, tags=?, mask=?, updated_at=? WHERE id=?",
                   ((b.get("name") or cur["name"]).strip(), kind, json.dumps(steps, ensure_ascii=False), b.get("tags", cur["tags"]) or "",
                    str(b.get("mask", cur["mask"]) or "")[:500], now(), xid))
        r = cn.execute("SELECT * FROM scenarios WHERE id = ?", (xid,)).fetchone()
    return jsonify(scenario=scenario_out(r))

@app.route("/scenarios/<int:xid>", methods=["DELETE"])
def scenarios_delete(xid):
    with db() as cn:
        ids = [r[0] for r in cn.execute("SELECT id FROM runs WHERE scenario_id = ?", (xid,))]
        n = cn.execute("DELETE FROM scenarios WHERE id = ?", (xid,)).rowcount
    for i in ids: shutil.rmtree(RUNS / str(i), ignore_errors=True)
    return (jsonify(ok=True), 200) if n else (jsonify(error="Scénario inconnu"), 404)

# ------------------------------------------------------------------ exécutions
def _execute(cn, scenario, site, campaign_id=None, by_user="", css=None, mockup_id=None, variant=None):
    cur = cn.execute("INSERT INTO runs (scenario_id, campaign_id, started_at, status, by_user, mockup_id, variant) VALUES (?,?,?,?,?,?,?)",
                     (scenario["id"], campaign_id, now(), "running", by_user, mockup_id, variant))
    rid = cur.lastrowid; cn.commit()
    login = json.loads(site["login_steps"] or "[]"); steps = json.loads(scenario["steps"])
    try:
        mask = [m.strip() for m in (scenario["mask"] or "").split(",") if m.strip()] if "mask" in scenario.keys() else []
        kw = dict(mask=mask, css=css) if css else dict(mask=mask)
        results, url = runner().run(site["base_url"], login, steps, RUNS / str(rid), STEP_TIMEOUT, **kw)
        st = qa_steps.summarize([r for r in results if not r.get("login")])["status"]
        if any(r.get("login") and not r["ok"] for r in results): st = "ko"
        err = ""
    except Exception as e:
        results, url, st, err = [], "", "error", f"{type(e).__name__} : {str(e).splitlines()[0][:300]}"
    cn.execute("UPDATE runs SET finished_at=?, status=?, results=?, final_url=?, error=? WHERE id=?", (now(), st, json.dumps(results, ensure_ascii=False), url, err, rid))
    cn.commit()
    return cn.execute("SELECT * FROM runs WHERE id = ?", (rid,)).fetchone()

def design_check(cn, run, x):
    """#729 (item 116 tranche 5) : l'exécution respecte-t-elle la maquette validée du scénario ? Comparaison des captures
    avec l'exécution de la variante retenue (aucun écart significatif = conforme) et des notes de conformité. La
    première exécution conforme marque la maquette « intégrée »."""
    if "target_run_id" not in x.keys() or not x["target_run_id"] or run["mockup_id"]: return None
    tgt = cn.execute("SELECT * FROM runs WHERE id = ?", (x["target_run_id"],)).fetchone()
    if not tgt: return None
    st = _diff_steps(run["id"], run, tgt["id"], tgt); comp = [s for s in st if not s.get("error")]
    sig = sum(1 for s in comp if s.get("significant"))
    score, tscore = qa_mockup.audit_stats(json.loads(run["results"] or "[]"))["score"], qa_mockup.audit_stats(json.loads(tgt["results"] or "[]"))["score"]
    ok = run["status"] == "ok" and bool(comp) and sig == 0
    out = dict(target_run_id=tgt["id"], mockup_id=x["target_mockup_id"], compared=len(comp), significant=sig, score=score, target_score=tscore, conforme=ok)
    if ok and x["target_mockup_id"]:
        cn.execute("UPDATE mockups SET status = 'integree', integrated_run_id = ?, integrated_at = ? WHERE id = ? AND integrated_run_id IS NULL",
                   (run["id"], now(), x["target_mockup_id"])); cn.commit()
    return out

@app.route("/runs/<int:rid>/design", methods=["GET"])
def run_design(rid):
    with db() as cn:
        r = cn.execute("SELECT * FROM runs WHERE id = ?", (rid,)).fetchone()
        if not r: return jsonify(error="Exécution inconnue"), 404
        x = cn.execute("SELECT * FROM scenarios WHERE id = ?", (r["scenario_id"],)).fetchone()
        return jsonify(design=design_check(cn, r, x))

@app.route("/scenarios/<int:xid>/target", methods=["DELETE"])
def scenario_target_clear(xid):
    """Retire la maquette cible du scénario (le développement a changé de direction)."""
    with db() as cn:
        n = cn.execute("UPDATE scenarios SET target_run_id = NULL, target_mockup_id = NULL, updated_at = ? WHERE id = ?", (now(), xid)).rowcount; cn.commit()
        r = cn.execute("SELECT * FROM scenarios WHERE id = ?", (xid,)).fetchone()
    return (jsonify(scenario=scenario_out(r)), 200) if n else (jsonify(error="Scénario inconnu"), 404)

@app.route("/scenarios/<int:xid>/run", methods=["POST"])
def scenarios_run(xid):
    by = (request.get_json(silent=True) or {}).get("by_user", "")
    with db() as cn:
        x = cn.execute("SELECT * FROM scenarios WHERE id = ?", (xid,)).fetchone()
        if not x: return jsonify(error="Scénario inconnu"), 404
        s = cn.execute("SELECT * FROM sites WHERE id = ?", (x["site_id"],)).fetchone()
        r = _execute(cn, x, s, by_user=by)
        return jsonify(run=dict(run_out(r), design=design_check(cn, r, x)))

@app.route("/sites/<int:sid>/campaign", methods=["POST"])
def site_campaign(sid):
    """Campagne : rejoue tous les scénarios de non-régression du site (ou tous si kind=all)."""
    b = request.get_json(silent=True) or {}; kind = b.get("kind") or "non-regression"
    with db() as cn:
        s = cn.execute("SELECT * FROM sites WHERE id = ?", (sid,)).fetchone()
        if not s: return jsonify(error="Site inconnu"), 404
        q = "SELECT * FROM scenarios WHERE site_id = ?" + ("" if kind == "all" else " AND kind = 'non-regression'") + " ORDER BY name"
        xs = cn.execute(q, (sid,)).fetchall()
        if not xs: return jsonify(error="Aucun scénario à rejouer (marquez des scénarios « non-régression » ou lancez kind=all)"), 400
        cur = cn.execute("INSERT INTO campaigns (site_id, kind, started_at, total, by_user) VALUES (?,?,?,?,?)", (sid, kind, now(), len(xs), b.get("by_user", ""))); cid = cur.lastrowid; cn.commit()
        runs = []
        for x in xs:
            r = _execute(cn, x, s, campaign_id=cid, by_user=b.get("by_user", "")); runs.append(dict(run_out(r), design=design_check(cn, r, x)))
        passed = sum(1 for r in runs if r["status"] == "ok")
        cn.execute("UPDATE campaigns SET finished_at=?, passed=? WHERE id=?", (now(), passed, cid))
        c = cn.execute("SELECT * FROM campaigns WHERE id = ?", (cid,)).fetchone()
    return jsonify(campaign=d(c), runs=[dict(r, scenario_name=next(x["name"] for x in xs if x["id"] == r["scenario_id"])) for r in runs])

@app.route("/sites/<int:sid>/campaigns", methods=["GET"])
def site_campaigns(sid):
    with db() as cn: rows = cn.execute("SELECT * FROM campaigns WHERE site_id = ? ORDER BY id DESC LIMIT 30", (sid,)).fetchall()
    return jsonify(campaigns=[d(r) for r in rows])

@app.route("/scenarios/<int:xid>/runs", methods=["GET"])
def scenario_runs(xid):
    with db() as cn: rows = cn.execute("SELECT * FROM runs WHERE scenario_id = ? AND mockup_id IS NULL ORDER BY id DESC LIMIT 20", (xid,)).fetchall()
    return jsonify(runs=[run_out(r) for r in rows])

@app.route("/runs/<int:rid>/shot/<name>", methods=["GET"])
def run_shot(rid, name):
    if not (name.startswith("step") or name.startswith("diff-")) or not name.endswith(".png") or "/" in name or ".." in name: return jsonify(error="capture inconnue"), 404
    return send_from_directory(RUNS / str(rid), name)

# ------------------------------------------------------------------ référence et différences visuelles (#727)
@app.route("/scenarios/<int:xid>/reference", methods=["PUT"])
def scenario_reference(xid):
    """Exécution de référence du scénario (captures attendues) ; run_id nul = aucune."""
    rid = (request.get_json(silent=True) or {}).get("run_id")
    with db() as cn:
        if not cn.execute("SELECT 1 FROM scenarios WHERE id = ?", (xid,)).fetchone(): return jsonify(error="Scénario inconnu"), 404
        if rid is not None and not cn.execute("SELECT 1 FROM runs WHERE id = ? AND scenario_id = ?", (rid, xid)).fetchone():
            return jsonify(error="Exécution inconnue pour ce scénario"), 400
        cn.execute("UPDATE scenarios SET ref_run_id = ?, updated_at = ? WHERE id = ?", (rid, now(), xid)); cn.commit()
        r = cn.execute("SELECT * FROM scenarios WHERE id = ?", (xid,)).fetchone()
    return jsonify(scenario=scenario_out(r))

@app.route("/runs/<int:rid>/diff", methods=["GET"])
def run_diff(rid):
    """Écarts visuels d'une exécution avec la référence du scénario, ou avec ?against=<exécution> (rejouer un bug :
    comparer à l'exécution jointe au ticket). Images de différence mises en cache dans le dossier de l'exécution."""
    with db() as cn:
        run = cn.execute("SELECT * FROM runs WHERE id = ?", (rid,)).fetchone()
        if not run: return jsonify(error="Exécution inconnue"), 404
        x = cn.execute("SELECT * FROM scenarios WHERE id = ?", (run["scenario_id"],)).fetchone()
        against = request.args.get("against", type=int) or x["ref_run_id"]
        if not against: return jsonify(error="Aucune référence : choisir une exécution de référence pour ce scénario"), 400
        ref = cn.execute("SELECT * FROM runs WHERE id = ?", (against,)).fetchone()
        if not ref: return jsonify(error="Exécution de référence introuvable"), 404
    out = _diff_steps(rid, run, against, ref)
    return jsonify(run_id=rid, against=against, steps=out, significant=sum(1 for s in out if s.get("significant")))

def _diff_steps(rid, run, against, ref):
    out = []
    for idx, action, rshot, nshot in qa_visual.pairs(json.loads(ref["results"] or "[]"), json.loads(run["results"] or "[]")):
        rp, np_ = RUNS / str(against) / rshot, RUNS / str(rid) / nshot
        name = f"diff-{against}-{nshot}"
        if not rp.exists() or not np_.exists():
            out.append(dict(index=idx, action=action, error="capture absente")); continue
        try: res = qa_visual.compare(rp, np_, RUNS / str(rid) / name)
        except Exception as e: out.append(dict(index=idx, action=action, error=f"{type(e).__name__} : {e}"[:200])); continue
        out.append(dict(index=idx, action=action, ref_run=against, ref_shot=rshot, shot=nshot, diff=name, **res))
    return out

# ------------------------------------------------------------------ maquettes en étapes (#728, item 116 tranche 4)
def mockup_out(cn, m):
    """Maquette + étapes de présentation (exécutions des variantes, comparaison de chacune avec la situation actuelle)."""
    m = d(m); m["variants"] = json.loads(m["variants"] or "[]")
    base = cn.execute("SELECT * FROM runs WHERE id = ?", (m["base_run_id"],)).fetchone() if m["base_run_id"] else None
    vr, diffs = {}, {}
    for r in cn.execute("SELECT * FROM runs WHERE mockup_id = ? ORDER BY id", (m["id"],)).fetchall():
        vr[r["variant"]] = r   # la plus récente l'emporte
    for i, r in vr.items():
        if base:
            st = _diff_steps(r["id"], r, base["id"], base)
            diffs[i] = dict(significant=sum(1 for s in st if s.get("significant")), steps=st)
    m["slides"] = qa_mockup.presentation(m, run_out(base) if base else None, {i: run_out(r) for i, r in vr.items()}, diffs)
    return m

@app.route("/scenarios/<int:xid>/mockups", methods=["GET"])
def mockups_list(xid):
    with db() as cn: rows = cn.execute("SELECT id, name, status, chosen, ticket_id, base_run_id, integrated_run_id, integrated_at, created_at FROM mockups WHERE scenario_id = ? ORDER BY id DESC", (xid,)).fetchall()
    return jsonify(mockups=[d(r) for r in rows])

@app.route("/scenarios/<int:xid>/mockups", methods=["POST"])
def mockups_create(xid):
    """{name, base_run_id?, variants?, auto?} -- auto : variantes calculées depuis les constats de la situation actuelle."""
    b = request.get_json(silent=True) or {}
    with db() as cn:
        x = cn.execute("SELECT * FROM scenarios WHERE id = ?", (xid,)).fetchone()
        if not x: return jsonify(error="Scénario inconnu"), 404
        rid = b.get("base_run_id") or x["ref_run_id"]
        if not rid:
            r = cn.execute("SELECT id FROM runs WHERE scenario_id = ? AND mockup_id IS NULL ORDER BY id DESC LIMIT 1", (xid,)).fetchone(); rid = r["id"] if r else None
        base = cn.execute("SELECT * FROM runs WHERE id = ? AND scenario_id = ?", (rid, xid)).fetchone() if rid else None
        if not base: return jsonify(error="Jouez d'abord le scénario : la maquette part d'une exécution (situation actuelle)"), 400
        variants = list(b.get("variants") or [])
        if b.get("auto", True):
            findings = [f for r in json.loads(base["results"] or "[]") if r.get("action") == "audit" for f in r.get("findings") or []]
            variants += qa_mockup.auto_variants(findings)
        if not variants: variants = [dict(name="Variante 1", css="", origin="manuel")]
        try: variants = qa_mockup.clean_variants(variants)
        except ValueError as e: return jsonify(error=str(e)), 400
        name = (b.get("name") or "").strip()[:120] or f"Maquette — {x['name']}"
        cur = cn.execute("INSERT INTO mockups (scenario_id, base_run_id, name, variants, by_user, created_at, updated_at) VALUES (?,?,?,?,?,?,?)",
                         (xid, base["id"], name, json.dumps(variants, ensure_ascii=False), b.get("by_user", ""), now(), now())); cn.commit()
        return jsonify(mockup=mockup_out(cn, cn.execute("SELECT * FROM mockups WHERE id = ?", (cur.lastrowid,)).fetchone())), 201

@app.route("/mockups/<int:mid>", methods=["GET"])
def mockups_get(mid):
    with db() as cn:
        m = cn.execute("SELECT * FROM mockups WHERE id = ?", (mid,)).fetchone()
        return jsonify(mockup=mockup_out(cn, m)) if m else (jsonify(error="Maquette inconnue"), 404)

@app.route("/mockups/<int:mid>", methods=["PUT"])
def mockups_update(mid):
    b = request.get_json(silent=True) or {}
    with db() as cn:
        m = cn.execute("SELECT * FROM mockups WHERE id = ?", (mid,)).fetchone()
        if not m: return jsonify(error="Maquette inconnue"), 404
        if m["status"] in ("validee", "integree"): return jsonify(error="Maquette déjà validée : en créer une nouvelle"), 409
        try: variants = qa_mockup.clean_variants(b.get("variants")) if "variants" in b else json.loads(m["variants"])
        except ValueError as e: return jsonify(error=str(e)), 400
        changed = "variants" in b and variants != json.loads(m["variants"])   # variantes changées : captures à refaire
        cn.execute("UPDATE mockups SET name = ?, variants = ?, status = ?, updated_at = ? WHERE id = ?",
                   ((b.get("name") or m["name"]).strip()[:120], json.dumps(variants, ensure_ascii=False), "brouillon" if changed else m["status"], now(), mid)); cn.commit()
        if changed:
            for r in cn.execute("SELECT id FROM runs WHERE mockup_id = ?", (mid,)).fetchall(): shutil.rmtree(RUNS / str(r["id"]), ignore_errors=True)
            cn.execute("DELETE FROM runs WHERE mockup_id = ?", (mid,)); cn.commit()
        return jsonify(mockup=mockup_out(cn, cn.execute("SELECT * FROM mockups WHERE id = ?", (mid,)).fetchone()))

@app.route("/mockups/<int:mid>", methods=["DELETE"])
def mockups_delete(mid):
    with db() as cn:
        rids = [r["id"] for r in cn.execute("SELECT id FROM runs WHERE mockup_id = ?", (mid,)).fetchall()]
        cn.execute("UPDATE scenarios SET target_run_id = NULL, target_mockup_id = NULL WHERE target_mockup_id = ?", (mid,))   # #729
        n = cn.execute("DELETE FROM mockups WHERE id = ?", (mid,)).rowcount; cn.execute("DELETE FROM runs WHERE mockup_id = ?", (mid,)); cn.commit()
    for r in rids: shutil.rmtree(RUNS / str(r), ignore_errors=True)
    return (jsonify(ok=True), 200) if n else (jsonify(error="Maquette inconnue"), 404)

@app.route("/mockups/<int:mid>/render", methods=["POST"])
def mockups_render(mid):
    """Rejoue le scénario pour chaque variante (ou ?variant=i), feuille injectée dans le navigateur de test."""
    only = request.args.get("variant", type=int); by = (request.get_json(silent=True) or {}).get("by_user", "")
    with db() as cn:
        m = cn.execute("SELECT * FROM mockups WHERE id = ?", (mid,)).fetchone()
        if not m: return jsonify(error="Maquette inconnue"), 404
        if m["status"] in ("validee", "integree"): return jsonify(error="Maquette validée : ses captures servent de cible, en créer une nouvelle"), 409
        x = cn.execute("SELECT * FROM scenarios WHERE id = ?", (m["scenario_id"],)).fetchone(); s = cn.execute("SELECT * FROM sites WHERE id = ?", (x["site_id"],)).fetchone()
        for i, v in enumerate(json.loads(m["variants"] or "[]")):
            if only is not None and i != only: continue
            for old in cn.execute("SELECT id FROM runs WHERE mockup_id = ? AND variant = ?", (mid, i)).fetchall():
                cn.execute("DELETE FROM runs WHERE id = ?", (old["id"],)); shutil.rmtree(RUNS / str(old["id"]), ignore_errors=True)
            _execute(cn, x, s, by_user=by, css=v["css"] or "/* variante vide */", mockup_id=mid, variant=i)
        if m["status"] == "brouillon": cn.execute("UPDATE mockups SET status = 'presentee', updated_at = ? WHERE id = ?", (now(), mid))
        cn.commit()
        return jsonify(mockup=mockup_out(cn, cn.execute("SELECT * FROM mockups WHERE id = ?", (mid,)).fetchone()))

@app.route("/mockups/<int:mid>/decision", methods=["POST"])
def mockups_decision(mid):
    """{status: validee|rejetee, variant, comment, ticket?} -- validée : ticket évolution avec le correctif CSS."""
    b = request.get_json(silent=True) or {}; st = b.get("status")
    if st not in ("validee", "rejetee"): return jsonify(error="Décision : validee ou rejetee"), 400
    with db() as cn:
        m = cn.execute("SELECT * FROM mockups WHERE id = ?", (mid,)).fetchone()
        if not m: return jsonify(error="Maquette inconnue"), 404
        if m["status"] in ("validee", "integree"): return jsonify(error="Maquette déjà validée"), 409
        variants = json.loads(m["variants"] or "[]"); vi = b.get("variant")
        if st == "validee" and not (isinstance(vi, int) and 0 <= vi < len(variants)): return jsonify(error="Variante à retenir manquante"), 400
        if st == "validee" and not cn.execute("SELECT 1 FROM runs WHERE mockup_id = ? AND variant = ?", (mid, vi)).fetchone():
            return jsonify(error="Générez d'abord les captures de cette variante"), 400
        cn.execute("UPDATE mockups SET status = ?, chosen = ?, decision_comment = ?, updated_at = ? WHERE id = ?",
                   (st, vi if st == "validee" else None, (b.get("comment") or "").strip()[:2000], now(), mid)); cn.commit()
        if st == "validee":   # #729 : la variante retenue devient la cible du scénario, rejouée en campagne
            vr = cn.execute("SELECT id FROM runs WHERE mockup_id = ? AND variant = ? ORDER BY id DESC LIMIT 1", (mid, vi)).fetchone()
            cn.execute("UPDATE scenarios SET target_run_id = ?, target_mockup_id = ?, kind = 'non-regression', updated_at = ? WHERE id = ?", (vr["id"], mid, now(), m["scenario_id"])); cn.commit()
        mo = mockup_out(cn, cn.execute("SELECT * FROM mockups WHERE id = ?", (mid,)).fetchone()); tid = None; warn = ""
        if st == "validee" and b.get("ticket", True):
            if not TICKETS: warn = "Module Tickets non relié : décision enregistrée sans ticket"
            else:
                x = cn.execute("SELECT * FROM scenarios WHERE id = ?", (m["scenario_id"],)).fetchone(); s = cn.execute("SELECT * FROM sites WHERE id = ?", (x["site_id"],)).fetchone()
                subject, desc = qa_mockup.ticket_text(mo, d(x), d(s), variants[vi], mo["slides"])
                try:
                    r = requests.post(f"{TICKETS}/tickets", json=dict(subject=subject, description=desc, type_id=_ticket_type_id("évolution"),
                                      source_type="qa", source_nom=s["name"], user_id=b.get("user_id")), timeout=10)
                    tid = (r.json() or {}).get("id") if r.ok else None
                    if not tid: warn = f"Ticket non créé (HTTP {r.status_code})"
                except Exception as e: warn = f"Ticket non créé : {type(e).__name__}"
                if tid: cn.execute("UPDATE mockups SET ticket_id = ? WHERE id = ?", (tid, mid)); cn.commit(); mo["ticket_id"] = tid; mo["slides"][-1]["ticket_id"] = tid
        return jsonify(mockup=mo, ticket_id=tid, warning=warn)

# ------------------------------------------------------------------ ticket depuis une exécution
def _ticket_type_id(label):
    try:
        for t in requests.get(f"{TICKETS}/types", timeout=5).json():
            if (t.get("label") or "").strip().lower().startswith(label.lower()): return t["id"]
    except Exception: pass
    return None

@app.route("/runs/<int:rid>/ticket", methods=["POST"])
def run_ticket(rid):
    """Crée un ticket Incident ou Évolution depuis l'exécution ; le scénario devient test traversant de non-régression."""
    if not TICKETS: return jsonify(error="Module Tickets non relié (TICKETS_API_INTERNAL_URL)"), 503
    b = request.get_json(silent=True) or {}; kind = b.get("kind") if b.get("kind") in ("incident", "evolution") else "incident"
    with db() as cn:
        r = cn.execute("SELECT * FROM runs WHERE id = ?", (rid,)).fetchone()
        if not r: return jsonify(error="Exécution inconnue"), 404
        if r["ticket_id"]: return jsonify(error=f"Cette exécution a déjà créé le ticket n°{r['ticket_id']}"), 409
        x = cn.execute("SELECT * FROM scenarios WHERE id = ?", (r["scenario_id"],)).fetchone(); s = cn.execute("SELECT * FROM sites WHERE id = ?", (x["site_id"],)).fetchone()
        subject, desc = qa_steps.ticket_text(kind, d(s), d(x), run_out(r), json.loads(x["steps"]))
        if b.get("subject"): subject = b["subject"].strip()
        if b.get("comment"): desc = b["comment"].strip() + "\n\n" + desc
        payload = dict(subject=subject, description=desc, type_id=_ticket_type_id("incident" if kind == "incident" else "évolution"), source_type="qa", source_nom=s["name"],
                       user_id=b.get("user_id"), level_id=b.get("level_id"), statut_id=b.get("statut_id"), site_id=b.get("site_id"))
        try:
            resp = requests.post(f"{TICKETS}/tickets", json=payload, timeout=10); data = resp.json()
            if resp.status_code >= 400 or not data.get("id"): return jsonify(error="Tickets : " + str(data.get("error") or resp.status_code)), 502
        except Exception as e: return jsonify(error=f"Tickets injoignable : {e}"), 502
        cn.execute("UPDATE runs SET ticket_id=?, ticket_kind=? WHERE id=?", (data["id"], kind, rid))
        cn.execute("UPDATE scenarios SET kind='non-regression', ticket_id=COALESCE(ticket_id, ?), updated_at=? WHERE id=?", (data["id"], now(), x["id"]))
        r = cn.execute("SELECT * FROM runs WHERE id = ?", (rid,)).fetchone(); x = cn.execute("SELECT * FROM scenarios WHERE id = ?", (x["id"],)).fetchone()
    return jsonify(ticket_id=data["id"], kind=kind, run=run_out(r), scenario=scenario_out(x)), 201
