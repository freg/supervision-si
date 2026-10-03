"""datasync-api -- module « Synchronisation centrale » du hub (livraison #652).

Liaison de synchronisation UNIDIRECTIONNELLE depuis les serveurs / applications / bases du parc vers un SGBD central
sur le hub, pour les phases de transition de déploiement et pour l'agrégation (indexation, traitements transversaux).

Liaison concentrique : une source → le central = UNE API source centrale (ce service). Chaque source a un jeton ;
un connecteur (datasync/connector/connector.py, autonome, posé près de la source) ou n'importe quel programme
pousse : /ping (présence), /schema (tables, colonnes, clés), /rows (lots de lignes, complet ou incrémental).

Stockage central : lignes génériques (source, table, clé, JSON, horodatage) + index plein texte FTS5 -- aucune DDL
par source, un seul modèle pour l'analyse, la recherche plein texte et la recherche relationnelle. SQLite par
défaut (FTS5 vérifié) ; PostgreSQL = évolution (JSONB + tsvector), le code lit/écrit par ces seules fonctions.

Outils : supervision des remontées (présence depuis le dernier ping, statistiques par table : lignes reçues,
dernier lot, durée, erreurs) ; analyse schéma/étiquette/champ/contenu (matching.py) : profils de colonnes,
correspondances entre champs de sources différentes, relations déduites par les valeurs ; validation manuelle
(proposé/confirmé/rejeté) ; recherche plein texte transversale ; recherche relationnelle : depuis une ligne, les
lignes liées par les relations confirmées ou déduites (intra et inter-sources), à N niveaux.

Règles : jetons jamais renvoyés après création (empreinte seulement) ; noms de tables/colonnes validés
(lettres, chiffres, _ . -) ; les lignes ne sont jamais modifiées par le hub (sens unique)."""
import os, re, json, time, sqlite3, secrets, hashlib, pathlib, logging, collections
from flask import Flask, jsonify, request
from flask_cors import CORS
import matching
try:
    from version_endpoint import register_version_route
except ImportError:
    register_version_route = None

app = Flask(__name__); CORS(app)
if register_version_route: register_version_route(app, "datasync")
log = logging.getLogger("datasync_api")
DATA = pathlib.Path(os.environ.get("DATASYNC_DATA_DIR", "/data")); DATA.mkdir(parents=True, exist_ok=True)
DB_PATH = os.environ.get("DATASYNC_DB_PATH", str(DATA / "datasync.db"))
PRESENCE_S = int(os.environ.get("DATASYNC_PRESENCE_S", "600"))       # au-delà : source absente
SAMPLE = int(os.environ.get("DATASYNC_SAMPLE", "400"))               # valeurs échantillonnées par colonne pour l'analyse
NAME_RE = re.compile(r"^[A-Za-z0-9_.\-]{1,100}$")
app.config["MAX_CONTENT_LENGTH"] = int(os.environ.get("DATASYNC_MAX_BATCH_MB", "64")) * 1024 * 1024

def db():
    cn = sqlite3.connect(DB_PATH, timeout=30); cn.row_factory = sqlite3.Row; cn.execute("PRAGMA foreign_keys = ON"); cn.execute("PRAGMA journal_mode = WAL"); return cn

def init_db():
    with db() as cn:
        cn.executescript("""
        CREATE TABLE IF NOT EXISTS sources (id INTEGER PRIMARY KEY AUTOINCREMENT, slug TEXT UNIQUE NOT NULL, name TEXT NOT NULL, kind TEXT DEFAULT '', notes TEXT DEFAULT '',
            token_hash TEXT NOT NULL, token_hint TEXT DEFAULT '', created_at TEXT, last_ping TEXT DEFAULT '', last_ping_info TEXT DEFAULT '{}', last_sync TEXT DEFAULT '');
        CREATE TABLE IF NOT EXISTS tables_meta (source_id INTEGER NOT NULL REFERENCES sources(id) ON DELETE CASCADE, name TEXT NOT NULL, pk TEXT DEFAULT '',
            columns TEXT DEFAULT '[]', rows INTEGER DEFAULT 0, last_batch_at TEXT DEFAULT '', last_batch_rows INTEGER DEFAULT 0, last_batch_ms INTEGER DEFAULT 0,
            batches INTEGER DEFAULT 0, errors INTEGER DEFAULT 0, last_error TEXT DEFAULT '', PRIMARY KEY (source_id, name));
        CREATE TABLE IF NOT EXISTS rows (source_id INTEGER NOT NULL REFERENCES sources(id) ON DELETE CASCADE, tname TEXT NOT NULL, pk TEXT NOT NULL, data TEXT NOT NULL,
            updated_at TEXT, PRIMARY KEY (source_id, tname, pk));
        CREATE VIRTUAL TABLE IF NOT EXISTS rows_fts USING fts5(content, source_id UNINDEXED, tname UNINDEXED, pk UNINDEXED, tokenize = 'unicode61 remove_diacritics 2');
        CREATE TABLE IF NOT EXISTS sync_log (id INTEGER PRIMARY KEY AUTOINCREMENT, source_id INTEGER, tname TEXT, at TEXT, rows INTEGER, ms INTEGER, mode TEXT, error TEXT DEFAULT '');
        CREATE TABLE IF NOT EXISTS links (id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT NOT NULL, a_source INTEGER, a_table TEXT, a_column TEXT, b_source INTEGER, b_table TEXT, b_column TEXT,
            score REAL, reasons TEXT DEFAULT '', status TEXT DEFAULT 'proposed', created_at TEXT, decided_at TEXT DEFAULT '', by_user TEXT DEFAULT '',
            UNIQUE (kind, a_source, a_table, a_column, b_source, b_table, b_column));
        """)
init_db()
def now(): return time.strftime("%Y-%m-%dT%H:%M:%S")
def d(r): return dict(r) if r is not None else None
def h(tok): return hashlib.sha256(tok.encode()).hexdigest()

def auth_source():
    tok = (request.headers.get("Authorization", "").removeprefix("Bearer ").strip() or request.headers.get("X-Source-Token", "").strip())
    if not tok: return None
    with db() as cn: r = cn.execute("SELECT * FROM sources WHERE token_hash = ?", (h(tok),)).fetchone()
    return d(r)

def source_out(r):
    s = d(r); s.pop("token_hash", None); s["last_ping_info"] = json.loads(s.get("last_ping_info") or "{}")
    age = None
    if s.get("last_ping"):
        try: age = int(time.time() - time.mktime(time.strptime(s["last_ping"], "%Y-%m-%dT%H:%M:%S")))
        except ValueError: age = None
    s["presence"] = "jamais" if age is None else ("present" if age <= PRESENCE_S else "absent"); s["ping_age_s"] = age
    return s

# ------------------------------------------------------------------ sources (hub)
@app.route("/health")
def health(): return jsonify(status="ok")

@app.route("/sources", methods=["GET"])
def sources_list():
    with db() as cn:
        srcs = [source_out(r) for r in cn.execute("SELECT * FROM sources ORDER BY name")]
        for s in srcs:
            s["tables"] = [d(t) for t in cn.execute("SELECT name, pk, rows, last_batch_at, last_batch_rows, last_batch_ms, batches, errors, last_error FROM tables_meta WHERE source_id = ? ORDER BY name", (s["id"],))]
            s["rows_total"] = sum(t["rows"] for t in s["tables"])
    return jsonify(sources=srcs, presence_s=PRESENCE_S)

@app.route("/sources", methods=["POST"])
def sources_create():
    b = request.get_json(silent=True) or {}; name = (b.get("name") or "").strip()
    slug = re.sub(r"[^a-z0-9]+", "-", (b.get("slug") or name).lower()).strip("-")
    if not name or not slug: return jsonify(error="Nom obligatoire"), 400
    tok = secrets.token_urlsafe(32)
    with db() as cn:
        if cn.execute("SELECT 1 FROM sources WHERE slug = ?", (slug,)).fetchone(): return jsonify(error=f"Source « {slug} » déjà déclarée"), 409
        cur = cn.execute("INSERT INTO sources (slug, name, kind, notes, token_hash, token_hint, created_at) VALUES (?,?,?,?,?,?,?)", (slug, name, b.get("kind") or "", b.get("notes") or "", h(tok), tok[:6] + "…", now()))
        r = cn.execute("SELECT * FROM sources WHERE id = ?", (cur.lastrowid,)).fetchone()
    return jsonify(source=source_out(r), token=tok, note="Jeton affiché une seule fois : à mettre dans la configuration du connecteur."), 201

@app.route("/sources/<int:sid>/rotate-token", methods=["POST"])
def sources_rotate(sid):
    tok = secrets.token_urlsafe(32)
    with db() as cn:
        if not cn.execute("UPDATE sources SET token_hash = ?, token_hint = ? WHERE id = ?", (h(tok), tok[:6] + "…", sid)).rowcount: return jsonify(error="Source inconnue"), 404
    return jsonify(token=tok)

@app.route("/sources/<int:sid>", methods=["PUT"])
def sources_update(sid):
    b = request.get_json(silent=True) or {}
    with db() as cn:
        r = cn.execute("SELECT * FROM sources WHERE id = ?", (sid,)).fetchone()
        if not r: return jsonify(error="Source inconnue"), 404
        cn.execute("UPDATE sources SET name = ?, kind = ?, notes = ? WHERE id = ?", ((b.get("name") or r["name"]).strip(), b.get("kind", r["kind"]), b.get("notes", r["notes"]), sid))
        r = cn.execute("SELECT * FROM sources WHERE id = ?", (sid,)).fetchone()
    return jsonify(source=source_out(r))

@app.route("/sources/<int:sid>", methods=["DELETE"])
def sources_delete(sid):
    with db() as cn:
        n = cn.execute("DELETE FROM sources WHERE id = ?", (sid,)).rowcount
        cn.execute("DELETE FROM rows_fts WHERE source_id = ?", (sid,)); cn.execute("DELETE FROM links WHERE a_source = ? OR b_source = ?", (sid, sid)); cn.execute("DELETE FROM sync_log WHERE source_id = ?", (sid,))
    return (jsonify(ok=True), 200) if n else (jsonify(error="Source inconnue"), 404)

@app.route("/sources/<int:sid>/log", methods=["GET"])
def sources_log(sid):
    with db() as cn: rows = cn.execute("SELECT * FROM sync_log WHERE source_id = ? ORDER BY id DESC LIMIT 100", (sid,)).fetchall()
    return jsonify(log=[d(r) for r in rows])

# ------------------------------------------------------------------ remontées (connecteurs, jeton)
@app.route("/ping", methods=["POST"])
def ping():
    s = auth_source()
    if not s: return jsonify(error="jeton de source invalide"), 401
    info = request.get_json(silent=True) or {}
    with db() as cn: cn.execute("UPDATE sources SET last_ping = ?, last_ping_info = ? WHERE id = ?", (now(), json.dumps({k: info[k] for k in ("host", "version", "db", "tables", "next_sync") if k in info}, ensure_ascii=False)[:2000], s["id"]))
    return jsonify(ok=True, server_time=now(), presence_s=PRESENCE_S)

@app.route("/schema", methods=["POST"])
def schema():
    """{tables: [{name, pk, columns: [{name, type}]}]} : déclaration (ou mise à jour) des tables de la source."""
    s = auth_source()
    if not s: return jsonify(error="jeton de source invalide"), 401
    b = request.get_json(silent=True) or {}; tabs = b.get("tables") or []
    with db() as cn:
        for t in tabs:
            if not NAME_RE.match(str(t.get("name", ""))): return jsonify(error=f"nom de table invalide : {t.get('name')!r}"), 400
            cols = [c for c in (t.get("columns") or []) if NAME_RE.match(str(c.get("name", "")))]
            cn.execute("""INSERT INTO tables_meta (source_id, name, pk, columns) VALUES (?,?,?,?)
                          ON CONFLICT(source_id, name) DO UPDATE SET pk = excluded.pk, columns = excluded.columns""", (s["id"], t["name"], t.get("pk") or "", json.dumps(cols, ensure_ascii=False)))
    return jsonify(ok=True, tables=len(tabs))

@app.route("/rows", methods=["POST"])
def rows_in():
    """{table, pk, mode: full|incremental, rows: [{...}], done: bool} ; en mode full, done=true retire les lignes non revues dans ce cycle (sync_id)."""
    s = auth_source()
    if not s: return jsonify(error="jeton de source invalide"), 401
    b = request.get_json(silent=True) or {}; t = str(b.get("table") or ""); pk = str(b.get("pk") or ""); mode = b.get("mode") or "incremental"; sync_id = str(b.get("sync_id") or "")
    if not NAME_RE.match(t) or not pk: return jsonify(error="table et pk obligatoires"), 400
    rows = b.get("rows") or []; t0 = time.time(); n = 0; stamp = now()
    with db() as cn:
        try:
            for r in rows:
                if not isinstance(r, dict) or pk not in r: continue
                key = str(r[pk]); data = json.dumps(r, ensure_ascii=False, default=str)
                cn.execute("INSERT INTO rows (source_id, tname, pk, data, updated_at) VALUES (?,?,?,?,?) ON CONFLICT(source_id, tname, pk) DO UPDATE SET data = excluded.data, updated_at = excluded.updated_at", (s["id"], t, key, data, stamp + "|" + sync_id))
                cn.execute("DELETE FROM rows_fts WHERE source_id = ? AND tname = ? AND pk = ?", (s["id"], t, key))
                cn.execute("INSERT INTO rows_fts (content, source_id, tname, pk) VALUES (?,?,?,?)", (matching.flatten_for_fts(r), s["id"], t, key)); n += 1
            removed = 0
            if mode == "full" and b.get("done") and sync_id:
                gone = [x[0] for x in cn.execute("SELECT pk FROM rows WHERE source_id = ? AND tname = ? AND updated_at NOT LIKE ?", (s["id"], t, "%|" + sync_id))]
                for key in gone:
                    cn.execute("DELETE FROM rows WHERE source_id = ? AND tname = ? AND pk = ?", (s["id"], t, key)); cn.execute("DELETE FROM rows_fts WHERE source_id = ? AND tname = ? AND pk = ?", (s["id"], t, key))
                removed = len(gone)
            total = cn.execute("SELECT count(*) FROM rows WHERE source_id = ? AND tname = ?", (s["id"], t)).fetchone()[0]; ms = int((time.time() - t0) * 1000)
            if rows:      # un lot clôturant vide (cycle complet) n'est pas un lot pour les statistiques
                cn.execute("""INSERT INTO tables_meta (source_id, name, pk, rows, last_batch_at, last_batch_rows, last_batch_ms, batches) VALUES (?,?,?,?,?,?,?,1)
                              ON CONFLICT(source_id, name) DO UPDATE SET pk = excluded.pk, rows = excluded.rows, last_batch_at = excluded.last_batch_at, last_batch_rows = excluded.last_batch_rows,
                              last_batch_ms = excluded.last_batch_ms, batches = tables_meta.batches + 1""", (s["id"], t, pk, total, stamp, n, ms))
                cn.execute("INSERT INTO sync_log (source_id, tname, at, rows, ms, mode) VALUES (?,?,?,?,?,?)", (s["id"], t, stamp, n, ms, mode + (" (fin, %d retirée(s))" % removed if removed else "")))
            else:
                cn.execute("UPDATE tables_meta SET rows = ? WHERE source_id = ? AND name = ?", (total, s["id"], t))
                if removed: cn.execute("INSERT INTO sync_log (source_id, tname, at, rows, ms, mode) VALUES (?,?,?,?,?,?)", (s["id"], t, stamp, 0, ms, "full (fin, %d retirée(s))" % removed))
            cn.execute("UPDATE sources SET last_sync = ?, last_ping = ? WHERE id = ?", (stamp, stamp, s["id"]))
        except Exception as e:
            cn.execute("INSERT INTO sync_log (source_id, tname, at, rows, ms, mode, error) VALUES (?,?,?,?,?,?,?)", (s["id"], t, stamp, n, 0, mode, str(e)[:300]))
            cn.execute("INSERT INTO tables_meta (source_id, name, pk, errors, last_error) VALUES (?,?,?,1,?) ON CONFLICT(source_id, name) DO UPDATE SET errors = tables_meta.errors + 1, last_error = excluded.last_error", (s["id"], t, pk, str(e)[:300]))
            return jsonify(error=str(e)[:300]), 500
    return jsonify(ok=True, received=n, total=total, removed=removed)

# ------------------------------------------------------------------ analyse schéma / étiquette / champ / contenu
def _tables_snapshot(cn, source_ids=None):
    """{(source_id, table): {pk, columns: {col: {profile, values}}}} sur un échantillon de lignes par table."""
    out = {}
    q = "SELECT source_id, name, pk FROM tables_meta" + (" WHERE source_id IN (%s)" % ",".join("?" * len(source_ids)) if source_ids else "")
    for t in cn.execute(q, tuple(source_ids or ())):
        sample = [json.loads(r[0]) for r in cn.execute("SELECT data FROM rows WHERE source_id = ? AND tname = ? LIMIT ?", (t["source_id"], t["name"], SAMPLE))]
        cols = collections.defaultdict(list)
        for r in sample:
            for k, v in r.items(): cols[k].append(v)
        out[(t["source_id"], t["name"])] = dict(pk=t["pk"], columns={c: dict(profile=matching.profile(v), values=v) for c, v in cols.items()})
    return out

@app.route("/analysis/profiles", methods=["GET"])
def analysis_profiles():
    with db() as cn:
        snap = _tables_snapshot(cn); names = {r["id"]: r["slug"] for r in cn.execute("SELECT id, slug FROM sources")}
    return jsonify(tables=[dict(source_id=s, source=names.get(s), table=t, pk=v["pk"], columns=[dict(name=c, **{k: x for k, x in i["profile"].items() if k != "sample"}, sample=i["profile"]["sample"]) for c, i in v["columns"].items()]) for (s, t), v in snap.items()])

@app.route("/analysis/run", methods=["POST"])
def analysis_run():
    """Calcule correspondances de champs et relations déduites, les enregistre en « proposées » (les confirmées/rejetées sont conservées)."""
    with db() as cn:
        snap = _tables_snapshot(cn)
        fields = [dict(source=s, table=t, column=c, profile=i["profile"], values=i["values"]) for (s, t), v in snap.items() for c, i in v["columns"].items()]
        matches = matching.match_fields(fields); rels = matching.deduce_relations(snap); n_new = 0
        for m in matches:
            n_new += cn.execute("""INSERT OR IGNORE INTO links (kind, a_source, a_table, a_column, b_source, b_table, b_column, score, reasons, created_at)
                                   VALUES ('field', ?,?,?,?,?,?,?,?,?)""", (m["a"]["source"], m["a"]["table"], m["a"]["column"], m["b"]["source"], m["b"]["table"], m["b"]["column"], m["score"], ", ".join(m["reasons"]), now())).rowcount
            cn.execute("UPDATE links SET score = ?, reasons = ? WHERE kind = 'field' AND a_source = ? AND a_table = ? AND a_column = ? AND b_source = ? AND b_table = ? AND b_column = ? AND status = 'proposed'",
                       (m["score"], ", ".join(m["reasons"]), m["a"]["source"], m["a"]["table"], m["a"]["column"], m["b"]["source"], m["b"]["table"], m["b"]["column"]))
        for r in rels:
            n_new += cn.execute("""INSERT OR IGNORE INTO links (kind, a_source, a_table, a_column, b_source, b_table, b_column, score, reasons, created_at)
                                   VALUES ('relation', ?,?,?,?,?,?,?,?,?)""", (r["from"]["source"], r["from"]["table"], r["column"], r["to"]["source"], r["to"]["table"], r["to_column"], r["score"], r["reason"], now())).rowcount
    return jsonify(fields=len(matches), relations=len(rels), new=n_new)

@app.route("/links", methods=["GET"])
def links_list():
    with db() as cn:
        names = {r["id"]: r["slug"] for r in cn.execute("SELECT id, slug FROM sources")}
        rows = [d(r) for r in cn.execute("SELECT * FROM links ORDER BY kind, status, score DESC")]
    for r in rows: r["a_source_slug"] = names.get(r["a_source"]); r["b_source_slug"] = names.get(r["b_source"])
    return jsonify(links=rows)

@app.route("/links", methods=["POST"])
def links_create():
    """Relation ou correspondance saisie à la main (status confirmé)."""
    b = request.get_json(silent=True) or {}
    try:
        vals = (b["kind"], int(b["a_source"]), b["a_table"], b["a_column"], int(b["b_source"]), b["b_table"], b["b_column"])
        if b["kind"] not in ("field", "relation") or not all(NAME_RE.match(str(x)) for x in (vals[2], vals[3], vals[5], vals[6])): raise ValueError
    except (KeyError, ValueError, TypeError): return jsonify(error="kind (field|relation), a_source, a_table, a_column, b_source, b_table, b_column obligatoires"), 400
    with db() as cn:
        cn.execute("INSERT INTO links (kind, a_source, a_table, a_column, b_source, b_table, b_column, score, reasons, status, created_at, decided_at, by_user) VALUES (?,?,?,?,?,?,?,1,'saisie manuelle','confirmed',?,?,?) ON CONFLICT DO UPDATE SET status = 'confirmed', decided_at = excluded.decided_at, by_user = excluded.by_user",
                   (*vals, now(), now(), b.get("by_user", "")))
    return jsonify(ok=True), 201

@app.route("/links/<int:lid>", methods=["PUT"])
def links_decide(lid):
    b = request.get_json(silent=True) or {}; st = b.get("status")
    if st not in ("proposed", "confirmed", "rejected"): return jsonify(error="status : proposed | confirmed | rejected"), 400
    with db() as cn:
        if not cn.execute("UPDATE links SET status = ?, decided_at = ?, by_user = ? WHERE id = ?", (st, now(), b.get("by_user", ""), lid)).rowcount: return jsonify(error="Lien inconnu"), 404
    return jsonify(ok=True)

# ------------------------------------------------------------------ recherche plein texte et relationnelle
def _fts_query(q):
    """Requête utilisateur -> FTS5 : mots en préfixe, guillemets respectés, champ:valeur accepté tel quel."""
    terms = re.findall(r'"[^"]+"|\S+', q.strip())
    out = []
    for t in terms:
        if t.startswith('"'): out.append(t)
        else:
            t = re.sub(r'["*()]', "", t)
            if t: out.append(f'"{t}"*')
    return " ".join(out) or '""'

@app.route("/search", methods=["GET"])
def search():
    q = (request.args.get("q") or "").strip(); limit = min(int(request.args.get("limit") or 50), 200)
    if not q: return jsonify(results=[], total=0)
    src = request.args.get("source"); tab = request.args.get("table")
    where = "rows_fts MATCH ?"; params = [_fts_query(q)]
    if src: where += " AND source_id = ?"; params.append(int(src))
    if tab: where += " AND tname = ?"; params.append(tab)
    with db() as cn:
        names = {r["id"]: r["slug"] for r in cn.execute("SELECT id, slug FROM sources")}
        try:
            hits = cn.execute(f"SELECT source_id, tname, pk, snippet(rows_fts, 0, '[', ']', '…', 12) AS snip, bm25(rows_fts) AS rank FROM rows_fts WHERE {where} ORDER BY rank LIMIT ?", (*params, limit)).fetchall()
        except sqlite3.OperationalError as e: return jsonify(error=f"requête invalide : {e}"), 400
        res = []
        for hh in hits:
            r = cn.execute("SELECT data FROM rows WHERE source_id = ? AND tname = ? AND pk = ?", (hh["source_id"], hh["tname"], hh["pk"])).fetchone()
            res.append(dict(source_id=hh["source_id"], source=names.get(hh["source_id"]), table=hh["tname"], pk=hh["pk"], snippet=hh["snip"], row=json.loads(r["data"]) if r else None))
    return jsonify(results=res, total=len(res), fts=params[0])

def _active_links(cn):
    rows = [d(r) for r in cn.execute("SELECT * FROM links WHERE kind = 'relation' AND status IN ('confirmed', 'proposed') ORDER BY CASE status WHEN 'confirmed' THEN 0 ELSE 1 END, score DESC")]
    return rows

@app.route("/rows/<int:sid>/<tname>/<path:pk>/related", methods=["GET"])
def related(sid, tname, pk):
    """Lignes en relation sémantique avec une ligne : via les relations (confirmées ou déduites), dans les deux sens, à `depth` niveaux (défaut 1, max 3)."""
    depth = max(1, min(int(request.args.get("depth") or 1), 3)); per = min(int(request.args.get("limit") or 25), 100)
    with db() as cn:
        names = {r["id"]: r["slug"] for r in cn.execute("SELECT id, slug FROM sources")}
        start = cn.execute("SELECT data FROM rows WHERE source_id = ? AND tname = ? AND pk = ?", (sid, tname, pk)).fetchone()
        if not start: return jsonify(error="Ligne inconnue"), 404
        links = _active_links(cn); seen = {(sid, tname, pk)}; nodes = [dict(source_id=sid, source=names.get(sid), table=tname, pk=pk, row=json.loads(start["data"]), level=0)]; edges = []
        frontier = [(sid, tname, pk, json.loads(start["data"]))]
        for level in range(1, depth + 1):
            nxt = []
            for (s0, t0, k0, row0) in frontier:
                for l in links:
                    found = []
                    if (l["a_source"], l["a_table"]) == (s0, t0) and row0.get(l["a_column"]) not in (None, ""):     # ligne -> cible (clé de la table b)
                        v = str(row0[l["a_column"]])
                        for r in cn.execute("SELECT pk, data FROM rows WHERE source_id = ? AND tname = ? AND pk = ? LIMIT ?", (l["b_source"], l["b_table"], v, per)): found.append((l["b_source"], l["b_table"], r["pk"], r["data"], "→"))
                    if (l["b_source"], l["b_table"]) == (s0, t0):                                                   # ligne cible <- lignes qui la référencent
                        for r in cn.execute("SELECT pk, data FROM rows WHERE source_id = ? AND tname = ? AND json_extract(data, ?) = ? LIMIT ?", (l["a_source"], l["a_table"], "$." + l["a_column"], _as_json_value(k0), per)): found.append((l["a_source"], l["a_table"], r["pk"], r["data"], "←"))
                    for (s1, t1, k1, data1, direction) in found:
                        edges.append(dict(**{"from": [s0, t0, k0], "to": [s1, t1, k1]}, link=f"{l['a_table']}.{l['a_column']} → {l['b_table']}.{l['b_column']}", status=l["status"], direction=direction))
                        if (s1, t1, k1) in seen: continue
                        seen.add((s1, t1, k1)); row1 = json.loads(data1); nodes.append(dict(source_id=s1, source=names.get(s1), table=t1, pk=k1, row=row1, level=level)); nxt.append((s1, t1, k1, row1))
            frontier = nxt
            if not frontier: break
    return jsonify(nodes=nodes, edges=edges, links_used=len(links))

def _as_json_value(k):
    """La clé est stockée en texte ; la colonne référente peut être numérique : json_extract renvoie un entier -> comparer sur la forme stockée."""
    try: return int(k)
    except ValueError: return k

@app.route("/rows/<int:sid>/<tname>", methods=["GET"])
def rows_list(sid, tname):
    off = int(request.args.get("offset") or 0); lim = min(int(request.args.get("limit") or 50), 500)
    with db() as cn:
        rows = [dict(pk=r["pk"], row=json.loads(r["data"]), updated_at=(r["updated_at"] or "").split("|")[0]) for r in cn.execute("SELECT pk, data, updated_at FROM rows WHERE source_id = ? AND tname = ? ORDER BY pk LIMIT ? OFFSET ?", (sid, tname, lim, off))]
        total = cn.execute("SELECT count(*) FROM rows WHERE source_id = ? AND tname = ?", (sid, tname)).fetchone()[0]
    return jsonify(rows=rows, total=total)
