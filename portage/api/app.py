"""portage-api -- module « Portage PHP → Python » du hub (livraison #650).

Interface de création d'un PROJET DE PORTAGE : fiche (nom, type, charset,
préfixe de tables, comptes de test), import du CODE (archive zip/tgz) et des
DONNÉES (dump SQL chargé dans la MariaDB dédiée portage-db), puis exécution
des étapes de l'IA de portage (portage-kit, projet indépendant monté dans le
conteneur sous /opt/portage-kit) : inventaire, schéma mesuré, squelette,
écrans, installation, migrations, fumée. Les rapports produits (PORT_SPEC
avec sa colonne « décision » éditable ici, schéma mesuré, fumée, journal)
sont servis au hub.

Décisions :
- portage-kit n'est PAS copié dans ce dépôt (la personne veut l'IA de
  portage en projet indépendant) : volume ${PORTAGE_KIT_DIR} -> /opt/portage-kit,
  installé au démarrage du conteneur (entrypoint). Sans ce volume, l'API
  répond mais /run refuse avec un message explicite.
- une seule exécution à la fois par projet, dans un thread du processus
  (gunicorn --workers 1, voir Dockerfile : pas de doublon multi-workers).
- le dump est chargé tel quel dans une base portant le slug du projet ;
  l'anonymisation (kit/anonymize.py) reste une étape explicite, jamais
  automatique -- les données réelles ne quittent pas portage-db.
- jamais de valeur venant d'une requête HTTP interpolée dans un nom de
  base ou un chemin sans passer par le slug (lettres, chiffres, tirets)."""
import os, re, io, json, shutil, sqlite3, subprocess, tarfile, threading, time, zipfile, pathlib, logging
from flask import Flask, jsonify, request, send_file
from flask_cors import CORS
import portspec
try:
    from version_endpoint import register_version_route
except ImportError:
    register_version_route = None

app = Flask(__name__); CORS(app)
if register_version_route: register_version_route(app, "portage")
log = logging.getLogger("portage_api")
DATA = pathlib.Path(os.environ.get("PORTAGE_DATA_DIR", "/data")); PROJECTS = DATA / "projects"; PROJECTS.mkdir(parents=True, exist_ok=True)
DB_PATH = os.environ.get("PORTAGE_DB_PATH", str(DATA / "portage.db"))
KIT = pathlib.Path(os.environ.get("PORTAGE_KIT_DIR", "/opt/portage-kit"))
MDB = dict(host=os.environ.get("PORTAGE_DB_HOST", "portage-db"), user=os.environ.get("PORTAGE_DB_USER", "root"), password=os.environ.get("PORTAGE_DB_PASSWORD", ""),
           socket=os.environ.get("PORTAGE_DB_SOCKET", ""))
STEPS = ["inventory", "schema", "scaffold", "routes", "install", "migrate", "smoke"]
MAX_UPLOAD = int(os.environ.get("PORTAGE_MAX_UPLOAD_MB", "512")) * 1024 * 1024
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD
_runs = {}        # slug -> thread

# ------------------------------------------------------------------ stockage
def db():
    cn = sqlite3.connect(DB_PATH); cn.row_factory = sqlite3.Row; cn.execute("PRAGMA foreign_keys = ON"); return cn

def init_db():
    with db() as cn:
        cn.execute("""CREATE TABLE IF NOT EXISTS projects (id INTEGER PRIMARY KEY AUTOINCREMENT, slug TEXT UNIQUE NOT NULL, name TEXT NOT NULL,
                      kind TEXT DEFAULT '', entry TEXT DEFAULT 'index.php', charset TEXT DEFAULT 'latin1', table_prefix TEXT DEFAULT '',
                      auth_json TEXT DEFAULT '{}', notes TEXT DEFAULT '', created_at TEXT, updated_at TEXT,
                      code_file TEXT DEFAULT '', dump_file TEXT DEFAULT '', dump_loaded_at TEXT DEFAULT '',
                      run_status TEXT DEFAULT '', run_steps TEXT DEFAULT '', run_started_at TEXT DEFAULT '', run_finished_at TEXT DEFAULT '')""")
init_db()

def now(): return time.strftime("%Y-%m-%dT%H:%M:%S")
def row_to_dict(r): d = dict(r); d["auth"] = json.loads(d.pop("auth_json") or "{}"); return d
def pdir(slug): return PROJECTS / slug
def get_project(slug):
    with db() as cn:
        r = cn.execute("SELECT * FROM projects WHERE slug = ?", (slug,)).fetchone()
    return row_to_dict(r) if r else None

def project_files(slug):
    d = pdir(slug); a = d / "apps"
    return dict(source=(d / "source").is_dir() and any((d / "source").iterdir()), dump=(d / "dump.sql").exists(),
                yml=(a / f"{slug}.yml").exists(), inventory=(a / f"{slug}.inventory.json").exists(), port_spec=(a / f"{slug}.PORT_SPEC.md").exists(),
                schema=(a / f"{slug}.schema_report.md").exists(), schema_graph=(a / f"{slug}.schema_graph.json").exists(),
                py=(d / "out" / "py").is_dir(), smoke=(d / "out" / "smoke.md").exists(), log=(d / "run.log").exists())

def write_yml(p):
    d = pdir(p["slug"]); (d / "apps").mkdir(parents=True, exist_ok=True)
    (d / "apps" / f"{p['slug']}.yml").write_text(portspec.build_app_yml(p, str(d / "source"), dict(MDB, name=db_name(p["slug"]))), encoding="utf-8")

def db_name(slug): return "port_" + re.sub(r"[^a-z0-9_]", "_", slug)

# ------------------------------------------------------------------ projets
@app.route("/health")
def health(): return jsonify(status="ok", kit=KIT.exists(), kit_installed=_kit_ok())

def _kit_ok():
    return (KIT / "kit" / "portage.py").exists()

@app.route("/projects", methods=["GET"])
def projects_list():
    with db() as cn:
        rows = [row_to_dict(r) for r in cn.execute("SELECT * FROM projects ORDER BY updated_at DESC")]
    for p in rows: p["files"] = project_files(p["slug"])
    return jsonify(projects=rows, kit_installed=_kit_ok(), steps=STEPS, decisions=portspec.DECISIONS)

@app.route("/projects", methods=["POST"])
def projects_create():
    b = request.get_json(silent=True) or {}
    name = (b.get("name") or "").strip()
    if not name: return jsonify(error="Le nom du projet est obligatoire"), 400
    slug = portspec.slugify(b.get("slug") or name)
    if get_project(slug): return jsonify(error=f"Un projet « {slug} » existe déjà"), 409
    fields = dict(slug=slug, name=name, kind=b.get("kind") or "", entry=b.get("entry") or "index.php", charset=b.get("charset") or "latin1",
                  table_prefix=b.get("table_prefix") or "", auth_json=json.dumps(b.get("auth") or {}), notes=b.get("notes") or "", created_at=now(), updated_at=now())
    with db() as cn:
        cn.execute("INSERT INTO projects (slug, name, kind, entry, charset, table_prefix, auth_json, notes, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                   tuple(fields.values()))
    (pdir(slug) / "source").mkdir(parents=True, exist_ok=True); write_yml(get_project(slug))
    return jsonify(project=project_detail(slug)), 201

def project_detail(slug):
    p = get_project(slug); p["files"] = project_files(slug); p["db_name"] = db_name(slug); p["running"] = slug in _runs and _runs[slug].is_alive()
    lg = pdir(slug) / "run.log"; p["log_tail"] = lg.read_text(encoding="utf-8", errors="replace")[-4000:] if lg.exists() else ""
    return p

@app.route("/projects/<slug>", methods=["GET"])
def projects_get(slug):
    p = get_project(portspec.slugify(slug))
    return (jsonify(project=project_detail(p["slug"])), 200) if p else (jsonify(error="Projet inconnu"), 404)

@app.route("/projects/<slug>", methods=["PUT"])
def projects_update(slug):
    p = get_project(portspec.slugify(slug))
    if not p: return jsonify(error="Projet inconnu"), 404
    b = request.get_json(silent=True) or {}
    cols = {k: b[k] for k in ("name", "kind", "entry", "charset", "table_prefix", "notes") if k in b}
    if "auth" in b: cols["auth_json"] = json.dumps(b["auth"] or {})
    cols["updated_at"] = now()
    with db() as cn:
        cn.execute("UPDATE projects SET " + ", ".join(f"{k} = ?" for k in cols) + " WHERE slug = ?", (*cols.values(), p["slug"]))
    write_yml(get_project(p["slug"]))
    return jsonify(project=project_detail(p["slug"]))

@app.route("/projects/<slug>", methods=["DELETE"])
def projects_delete(slug):
    p = get_project(portspec.slugify(slug))
    if not p: return jsonify(error="Projet inconnu"), 404
    if p["slug"] in _runs and _runs[p["slug"]].is_alive(): return jsonify(error="Une exécution est en cours"), 409
    with db() as cn: cn.execute("DELETE FROM projects WHERE slug = ?", (p["slug"],))
    shutil.rmtree(pdir(p["slug"]), ignore_errors=True)
    return jsonify(ok=True, dropped_db=_drop_db(db_name(p["slug"])))

# ------------------------------------------------------------------ imports
@app.route("/projects/<slug>/code", methods=["POST"])
def upload_code(slug):
    p = get_project(portspec.slugify(slug))
    if not p: return jsonify(error="Projet inconnu"), 404
    f = request.files.get("file")
    if not f: return jsonify(error="Fichier attendu (champ « file », archive .zip, .tar.gz ou .tgz)"), 400
    src = pdir(p["slug"]) / "source"; shutil.rmtree(src, ignore_errors=True); src.mkdir(parents=True)
    data = f.read(); name = f.filename or "code"
    try:
        if name.lower().endswith(".zip"):
            with zipfile.ZipFile(io.BytesIO(data)) as z: _safe_extract_zip(z, src)
        elif re.search(r"\.(tar\.gz|tgz|tar)$", name.lower()):
            with tarfile.open(fileobj=io.BytesIO(data), mode="r:*") as t: _safe_extract_tar(t, src)
        else: return jsonify(error="Format non reconnu : .zip, .tar.gz ou .tgz"), 400
    except (zipfile.BadZipFile, tarfile.TarError, ValueError) as e:
        return jsonify(error=f"Archive illisible : {e}"), 400
    # archive avec un dossier racine unique : on le remonte
    kids = [k for k in src.iterdir() if not k.name.startswith("__MACOSX")]
    if len(kids) == 1 and kids[0].is_dir():
        for k in list(kids[0].iterdir()): shutil.move(str(k), str(src / k.name))
        shutil.rmtree(kids[0], ignore_errors=True)
    kind, entry = portspec.detect_kind(src)
    with db() as cn:
        cn.execute("UPDATE projects SET code_file = ?, kind = COALESCE(NULLIF(kind, ''), ?), entry = ?, updated_at = ? WHERE slug = ?", (name, kind, entry, now(), p["slug"]))
    write_yml(get_project(p["slug"]))
    n = sum(1 for _ in src.rglob("*.php"))
    return jsonify(project=project_detail(p["slug"]), detected=dict(kind=kind, entry=entry, php_files=n))

def _safe_extract_zip(z, dst):
    for m in z.infolist():
        tgt = (dst / m.filename).resolve()
        if not str(tgt).startswith(str(dst.resolve())): raise ValueError("chemin hors archive : " + m.filename)
    z.extractall(dst)

def _safe_extract_tar(t, dst):
    for m in t.getmembers():
        tgt = (dst / m.name).resolve()
        if not str(tgt).startswith(str(dst.resolve())) or m.issym() or m.islnk(): raise ValueError("entrée refusée : " + m.name)
    t.extractall(dst)

@app.route("/projects/<slug>/dump", methods=["POST"])
def upload_dump(slug):
    p = get_project(portspec.slugify(slug))
    if not p: return jsonify(error="Projet inconnu"), 404
    f = request.files.get("file")
    if not f: return jsonify(error="Fichier attendu (champ « file », .sql ou .sql.gz)"), 400
    data = f.read(); name = f.filename or "dump.sql"
    if name.lower().endswith(".gz"):
        import gzip; data = gzip.decompress(data)
    (pdir(p["slug"]) / "dump.sql").write_bytes(data)
    with db() as cn: cn.execute("UPDATE projects SET dump_file = ?, updated_at = ? WHERE slug = ?", (name, now(), p["slug"]))
    loaded = None
    if (request.form.get("load") or "1") != "0":
        loaded = _load_dump(p["slug"])
        if loaded.get("error"): return jsonify(project=project_detail(p["slug"]), load=loaded), 502
    return jsonify(project=project_detail(p["slug"]), load=loaded)

def _mariadb_cmd():
    c = ["mariadb"] + (["-S", MDB["socket"]] if MDB["socket"] else ["-h", MDB["host"]]) + ["-u", MDB["user"]]
    if MDB["password"]: c.append("-p" + MDB["password"])
    return c

def _load_dump(slug):
    """Charge dump.sql dans la base port_<slug> (recréée) via le client mariadb -- la charset du projet pilote le client."""
    p = get_project(slug); dbn = db_name(slug); dump = pdir(slug) / "dump.sql"
    cs = {"latin1": "latin1", "utf-8": "utf8mb4", "utf8": "utf8mb4"}.get((p["charset"] or "latin1").lower(), "latin1")
    try:
        subprocess.run(_mariadb_cmd() + ["-e", f"DROP DATABASE IF EXISTS `{dbn}`; CREATE DATABASE `{dbn}` CHARACTER SET {cs};"], check=True, capture_output=True, text=True, timeout=60)
        with open(dump, "rb") as fh:
            r = subprocess.run(_mariadb_cmd() + [f"--default-character-set={cs}", "--force", dbn], stdin=fh, capture_output=True, text=True, timeout=3600)
        tables = subprocess.run(_mariadb_cmd() + ["-N", "-e", f"SELECT count(*) FROM information_schema.tables WHERE table_schema = '{dbn}'"], capture_output=True, text=True, timeout=60).stdout.strip()
        with db() as cn: cn.execute("UPDATE projects SET dump_loaded_at = ?, updated_at = ? WHERE slug = ?", (now(), now(), slug))
        return dict(db=dbn, tables=int(tables or 0), warnings=r.stderr[-2000:], charset=cs)
    except subprocess.CalledProcessError as e:
        return dict(error="MariaDB : " + (e.stderr or str(e))[-500:])
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        return dict(error=f"client mariadb indisponible ou délai dépassé : {e}")

def _drop_db(dbn):
    try: subprocess.run(_mariadb_cmd() + ["-e", f"DROP DATABASE IF EXISTS `{dbn}`"], check=True, capture_output=True, timeout=60); return True
    except Exception: return False

@app.route("/projects/<slug>/load-dump", methods=["POST"])
def load_dump(slug):
    p = get_project(portspec.slugify(slug))
    if not p: return jsonify(error="Projet inconnu"), 404
    if not (pdir(p["slug"]) / "dump.sql").exists(): return jsonify(error="Aucun dump importé"), 400
    r = _load_dump(p["slug"]); return (jsonify(load=r), 502 if r.get("error") else 200)

# ------------------------------------------------------------------ exécution de la chaîne
@app.route("/projects/<slug>/run", methods=["POST"])
def run_steps(slug):
    p = get_project(portspec.slugify(slug))
    if not p: return jsonify(error="Projet inconnu"), 404
    if not _kit_ok(): return jsonify(error="portage-kit absent du conteneur : monter PORTAGE_KIT_DIR (voir portage/README.md)"), 503
    steps = [s for s in ((request.get_json(silent=True) or {}).get("steps") or STEPS) if s in STEPS]
    if not steps: return jsonify(error="Aucune étape valide"), 400
    if not project_files(p["slug"])["source"]: return jsonify(error="Importez d'abord le code"), 400
    if p["slug"] in _runs and _runs[p["slug"]].is_alive(): return jsonify(error="Une exécution est déjà en cours"), 409
    write_yml(p); d = pdir(p["slug"]); yml = d / "apps" / f"{p['slug']}.yml"; lg = d / "run.log"
    with db() as cn: cn.execute("UPDATE projects SET run_status = 'running', run_steps = ?, run_started_at = ?, run_finished_at = '' WHERE slug = ?", (" ".join(steps), now(), p["slug"]))
    def work():
        env = dict(os.environ, PYTHONUNBUFFERED="1")
        with open(lg, "w", encoding="utf-8") as out:
            out.write(f"# {now()} étapes : {' '.join(steps)}\n"); out.flush()
            try:
                r = subprocess.run(["python3", str(KIT / "kit" / "portage.py"), str(yml), str(d / "out"), *steps], cwd=str(KIT), env=env, stdout=out, stderr=subprocess.STDOUT, timeout=7200)
                st = "ok" if r.returncode == 0 else "failed"
            except subprocess.TimeoutExpired:
                out.write("\n# délai dépassé (2 h)\n"); st = "failed"
        with db() as cn: cn.execute("UPDATE projects SET run_status = ?, run_finished_at = ?, updated_at = ? WHERE slug = ?", (st, now(), now(), p["slug"]))
    t = threading.Thread(target=work, daemon=True); _runs[p["slug"]] = t; t.start()
    return jsonify(project=project_detail(p["slug"])), 202

# ------------------------------------------------------------------ rapports et décisions
REPORTS = {"port_spec": "apps/{s}.PORT_SPEC.md", "schema": "apps/{s}.schema_report.md", "schema_graph": "apps/{s}.schema_graph.json",
           "inventory": "apps/{s}.inventory.json", "smoke": "out/smoke.md", "log": "run.log", "yml": "apps/{s}.yml"}

@app.route("/projects/<slug>/report/<name>", methods=["GET"])
def report(slug, name):
    p = get_project(portspec.slugify(slug))
    if not p: return jsonify(error="Projet inconnu"), 404
    if name not in REPORTS: return jsonify(error="Rapport inconnu"), 404
    f = pdir(p["slug"]) / REPORTS[name].format(s=p["slug"])
    if not f.exists(): return jsonify(error="Pas encore produit"), 404
    txt = f.read_text(encoding="utf-8", errors="replace")
    if name.endswith("json") or name in ("schema_graph", "inventory"):
        return jsonify(name=name, data=json.loads(txt))
    return jsonify(name=name, text=txt)

@app.route("/projects/<slug>/decisions", methods=["GET"])
def decisions_get(slug):
    p = get_project(portspec.slugify(slug))
    if not p: return jsonify(error="Projet inconnu"), 404
    f = pdir(p["slug"]) / f"apps/{p['slug']}.PORT_SPEC.md"
    if not f.exists(): return jsonify(units=[], choices=portspec.DECISIONS)
    return jsonify(units=portspec.read_decisions(f.read_text(encoding="utf-8")), choices=portspec.DECISIONS)

@app.route("/projects/<slug>/decisions", methods=["PUT"])
def decisions_put(slug):
    p = get_project(portspec.slugify(slug))
    if not p: return jsonify(error="Projet inconnu"), 404
    f = pdir(p["slug"]) / f"apps/{p['slug']}.PORT_SPEC.md"
    if not f.exists(): return jsonify(error="Lancez d'abord l'inventaire"), 400
    b = (request.get_json(silent=True) or {}).get("decisions") or {}
    bad = [v for v in b.values() if v not in portspec.DECISIONS]
    if bad: return jsonify(error=f"Décision inconnue : {bad[0]}"), 400
    f.write_text(portspec.write_decisions(f.read_text(encoding="utf-8"), {str(k): v for k, v in b.items()}), encoding="utf-8")
    return jsonify(units=portspec.read_decisions(f.read_text(encoding="utf-8")), choices=portspec.DECISIONS)

@app.route("/projects/<slug>/archive", methods=["GET"])
def archive(slug):
    """Zip du port généré (out/py) + rapports : ce que la personne récupère pour continuer hors du hub."""
    p = get_project(portspec.slugify(slug))
    if not p: return jsonify(error="Projet inconnu"), 404
    d = pdir(p["slug"]); buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for base in ("out/py", "apps", "out/smoke.md", "run.log"):
            path = d / base
            if path.is_file(): z.write(path, f"{p['slug']}/{base}")
            elif path.is_dir():
                for f in path.rglob("*"):
                    if f.is_file() and "__pycache__" not in f.parts and ".egg-info" not in str(f): z.write(f, f"{p['slug']}/{f.relative_to(d)}")
    buf.seek(0)
    return send_file(buf, mimetype="application/zip", as_attachment=True, download_name=f"portage-{p['slug']}.zip")
