# -*- coding: utf-8 -*-
"""Accès PostGIS du catalogue de positions (livraison #429). Base DÉDIÉE
(`GEO_CATALOG_DB_URL`) : les référentiels (OSM, communes, cache de
géocodage) y pèsent lourd, elle se déplace seule sur un hôte secondaire.
Toutes les écritures passent ici ; le SQL est PostgreSQL uniquement."""
import json
from datetime import datetime, timezone

import psycopg2
import psycopg2.extras

SCHEMA = """
CREATE TABLE IF NOT EXISTS catalog_positions (
    id SERIAL PRIMARY KEY,
    key TEXT UNIQUE NOT NULL,
    kind TEXT NOT NULL DEFAULT 'geolocation',
    label TEXT NOT NULL,
    lat DOUBLE PRECISION,
    lon DOUBLE PRECISION,
    geom geography(Point, 4326),
    precision TEXT,
    confidence INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'auto',
    decided_lat DOUBLE PRECISION,
    decided_lon DOUBLE PRECISION,
    decided_at TIMESTAMPTZ,
    note TEXT,
    interpretation JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_catalog_positions_geom ON catalog_positions USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_catalog_positions_label ON catalog_positions USING GIN (label gin_trgm_ops);

CREATE TABLE IF NOT EXISTS catalog_refs (
    id SERIAL PRIMARY KEY,
    position_id INTEGER NOT NULL REFERENCES catalog_positions(id) ON DELETE CASCADE,
    source TEXT NOT NULL,
    ref_key TEXT NOT NULL,
    label TEXT,
    precision TEXT,
    lat DOUBLE PRECISION,
    lon DOUBLE PRECISION,
    score REAL,
    data JSONB,
    fetched_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (position_id, source, ref_key)
);

CREATE TABLE IF NOT EXISTS catalog_links (
    id SERIAL PRIMARY KEY,
    position_id INTEGER NOT NULL REFERENCES catalog_positions(id) ON DELETE CASCADE,
    object_type TEXT NOT NULL,
    object_id TEXT NOT NULL,
    label TEXT,
    source TEXT,
    data JSONB,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (position_id, object_type, object_id)
);

CREATE TABLE IF NOT EXISTS ref_communes (
    code TEXT PRIMARY KEY,
    nom TEXT NOT NULL,
    codes_postaux TEXT[] NOT NULL DEFAULT '{}',
    lat DOUBLE PRECISION,
    lon DOUBLE PRECISION,
    geom geography(Point, 4326),
    population INTEGER,
    loaded_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_ref_communes_cp ON ref_communes USING GIN (codes_postaux);
CREATE INDEX IF NOT EXISTS idx_ref_communes_nom ON ref_communes USING GIN (nom gin_trgm_ops);

CREATE TABLE IF NOT EXISTS ref_geocode_cache (
    provider TEXT NOT NULL,
    query TEXT NOT NULL,
    result JSONB,
    fetched_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (provider, query)
);

CREATE TABLE IF NOT EXISTS catalog_sync_log (
    id SERIAL PRIMARY KEY,
    started_at TIMESTAMPTZ NOT NULL,
    finished_at TIMESTAMPTZ,
    positions INTEGER,
    refs INTEGER,
    links INTEGER,
    errors JSONB
);
"""


def connect(db_url):
    conn = psycopg2.connect(db_url)
    conn.autocommit = False
    return conn


def ensure_schema(conn):
    with conn.cursor() as cur:
        cur.execute("CREATE EXTENSION IF NOT EXISTS postgis")
        cur.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
        cur.execute(SCHEMA)
    conn.commit()


def _now():
    return datetime.now(timezone.utc)


def _row(cur):
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


# ---- positions ----------------------------------------------------------------

def upsert_position(conn, key, label, kind="geolocation"):
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO catalog_positions (key, kind, label) VALUES (%s, %s, %s)
               ON CONFLICT (key) DO UPDATE SET label = EXCLUDED.label, kind = EXCLUDED.kind, updated_at = now()
               RETURNING id, status, decided_lat, decided_lon""",
            (key, kind, label),
        )
        pid, status, dlat, dlon = cur.fetchone()
    return {"id": pid, "status": status, "decided_lat": dlat, "decided_lon": dlon}


def replace_refs(conn, position_id, refs):
    """Remplace les références NON humaines d'une position."""
    with conn.cursor() as cur:
        cur.execute("DELETE FROM catalog_refs WHERE position_id = %s AND source <> 'human'", (position_id,))
        for r in refs:
            cur.execute(
                """INSERT INTO catalog_refs (position_id, source, ref_key, label, precision, lat, lon, score, data)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                   ON CONFLICT (position_id, source, ref_key) DO UPDATE SET label = EXCLUDED.label, precision = EXCLUDED.precision,
                     lat = EXCLUDED.lat, lon = EXCLUDED.lon, score = EXCLUDED.score, data = EXCLUDED.data, fetched_at = now()""",
                (position_id, r["source"], str(r.get("ref_key") or r.get("label") or r["source"])[:500], r.get("label"), r.get("precision"),
                 r.get("lat"), r.get("lon"), r.get("score"), json.dumps(r.get("data") or {}, ensure_ascii=False)),
            )


def apply_interpretation(conn, position_id, interp):
    with conn.cursor() as cur:
        cur.execute(
            """UPDATE catalog_positions SET lat = %s, lon = %s,
                 geom = CASE WHEN %s IS NULL THEN NULL ELSE ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography END,
                 precision = %s, confidence = %s, interpretation = %s, updated_at = now() WHERE id = %s""",
            (interp["lat"], interp["lon"], interp["lon"], interp["lon"], interp["lat"], interp["precision"], interp["confidence"],
             json.dumps({k: v for k, v in interp.items() if k != "best"} | {"best": interp.get("best")}, ensure_ascii=False, default=str), position_id),
        )


def replace_links(conn, position_id, links, source):
    with conn.cursor() as cur:
        cur.execute("DELETE FROM catalog_links WHERE position_id = %s AND source = %s", (position_id, source))
        for l in links:
            cur.execute(
                """INSERT INTO catalog_links (position_id, object_type, object_id, label, source, data)
                   VALUES (%s, %s, %s, %s, %s, %s)
                   ON CONFLICT (position_id, object_type, object_id) DO UPDATE SET label = EXCLUDED.label, source = EXCLUDED.source, data = EXCLUDED.data, updated_at = now()""",
                (position_id, l["object_type"], str(l["object_id"]), l.get("label"), source, json.dumps(l.get("data") or {}, ensure_ascii=False)),
            )


def list_positions(conn, status=None, q=None, min_confidence=None, max_confidence=None, limit=500):
    clauses, params = [], []
    if status:
        clauses.append("p.status = %s"); params.append(status)
    if q:
        clauses.append("(p.label ILIKE %s OR p.key ILIKE %s)"); params.extend(["%%%s%%" % q, "%%%s%%" % q])
    if min_confidence is not None:
        clauses.append("p.confidence >= %s"); params.append(min_confidence)
    if max_confidence is not None:
        clauses.append("p.confidence <= %s"); params.append(max_confidence)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    with conn.cursor() as cur:
        cur.execute(
            f"""SELECT p.id, p.key, p.kind, p.label, p.lat, p.lon, p.precision, p.confidence, p.status, p.decided_lat, p.decided_lon,
                       p.decided_at, p.note, p.interpretation, p.created_at, p.updated_at,
                       (SELECT count(*) FROM catalog_links l WHERE l.position_id = p.id) AS link_count,
                       (SELECT count(*) FROM catalog_refs r WHERE r.position_id = p.id) AS ref_count
                FROM catalog_positions p {where}
                ORDER BY (p.status = 'auto') DESC, p.confidence ASC, p.label LIMIT %s""",
            params + [limit],
        )
        rows = _row(cur)
    return rows


def get_position(conn, position_id):
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM catalog_positions WHERE id = %s", (position_id,))
        rows = _row(cur)
        if not rows:
            return None
        p = rows[0]
        p.pop("geom", None)
        cur.execute("SELECT id, source, ref_key, label, precision, lat, lon, score, data, fetched_at FROM catalog_refs WHERE position_id = %s ORDER BY id", (position_id,))
        p["refs"] = _row(cur)
        cur.execute("SELECT id, object_type, object_id, label, source, data, updated_at FROM catalog_links WHERE position_id = %s ORDER BY object_type, label", (position_id,))
        p["links"] = _row(cur)
    return p


def all_refs_and_links(conn, ids):
    if not ids:
        return {}, {}
    with conn.cursor() as cur:
        cur.execute("SELECT position_id, source, ref_key, label, precision, lat, lon, score FROM catalog_refs WHERE position_id = ANY(%s) ORDER BY id", (list(ids),))
        refs = {}
        for r in _row(cur):
            refs.setdefault(r["position_id"], []).append(r)
        cur.execute("SELECT position_id, object_type, object_id, label, source FROM catalog_links WHERE position_id = ANY(%s) ORDER BY object_type, label", (list(ids),))
        links = {}
        for l in _row(cur):
            links.setdefault(l["position_id"], []).append(l)
    return refs, links


def decide(conn, position_id, status, lat=None, lon=None, note=None):
    """validated : garde l'interprétation (ou lat/lon fournis) ; corrected :
    lat/lon obligatoires ; auto : oubli de la décision."""
    with conn.cursor() as cur:
        cur.execute("SELECT lat, lon FROM catalog_positions WHERE id = %s", (position_id,))
        row = cur.fetchone()
        if row is None:
            return None
        if status == "auto":
            cur.execute("UPDATE catalog_positions SET status = 'auto', decided_lat = NULL, decided_lon = NULL, decided_at = NULL, note = %s, updated_at = now() WHERE id = %s", (note, position_id))
            cur.execute("DELETE FROM catalog_refs WHERE position_id = %s AND source = 'human'", (position_id,))
        else:
            dlat = lat if lat is not None else row[0]
            dlon = lon if lon is not None else row[1]
            if dlat is None or dlon is None:
                return False
            cur.execute(
                """UPDATE catalog_positions SET status = %s, decided_lat = %s, decided_lon = %s, decided_at = now(), note = %s,
                     lat = %s, lon = %s, geom = ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography,
                     precision = %s, confidence = %s, updated_at = now() WHERE id = %s""",
                (status, dlat, dlon, note, dlat, dlon, dlon, dlat, "manual" if status == "corrected" else "validated", 100 if status == "corrected" else 95, position_id),
            )
            cur.execute(
                """INSERT INTO catalog_refs (position_id, source, ref_key, label, precision, lat, lon, score, data)
                   VALUES (%s, 'human', %s, %s, %s, %s, %s, 1.0, %s)
                   ON CONFLICT (position_id, source, ref_key) DO UPDATE SET label = EXCLUDED.label, precision = EXCLUDED.precision, lat = EXCLUDED.lat, lon = EXCLUDED.lon, fetched_at = now()""",
                (position_id, status, "décision humaine (%s)" % status, "manual" if status == "corrected" else "validated", dlat, dlon, json.dumps({"note": note})),
            )
    return True


def summary(conn):
    with conn.cursor() as cur:
        cur.execute("""SELECT count(*) AS total,
                              count(*) FILTER (WHERE status = 'auto') AS auto,
                              count(*) FILTER (WHERE status = 'validated') AS validated,
                              count(*) FILTER (WHERE status = 'corrected') AS corrected,
                              count(*) FILTER (WHERE lat IS NULL) AS without_position,
                              count(*) FILTER (WHERE status = 'auto' AND confidence < 60) AS to_review,
                              round(avg(confidence)) AS avg_confidence
                       FROM catalog_positions""")
        s = _row(cur)[0]
        cur.execute("SELECT count(*) FROM catalog_links")
        s["links"] = cur.fetchone()[0]
        cur.execute("SELECT count(*), max(loaded_at) FROM ref_communes")
        n, at = cur.fetchone()
        s["communes"] = {"count": n, "loaded_at": at}
        cur.execute("SELECT count(*) FROM ref_geocode_cache")
        s["geocode_cache"] = cur.fetchone()[0]
        cur.execute("SELECT started_at, finished_at, positions, refs, links, errors FROM catalog_sync_log ORDER BY id DESC LIMIT 1")
        rows = _row(cur)
        s["last_sync"] = rows[0] if rows else None
    return s


# ---- référentiels -----------------------------------------------------------------

def osm_tables(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT table_name FROM information_schema.tables WHERE table_name IN ('planet_osm_point', 'planet_osm_polygon', 'planet_osm_line')")
        return sorted(r[0] for r in cur.fetchall())


def osm_search(conn, query, limit=3, min_similarity=4.84):
    """Recherche par nom dans les tables osm2pgsql locales (pg_trgm) --
    points puis polygones (centroïde). Vide si la base OSM n'est pas chargée."""
    tables = osm_tables(conn)
    out = []
    with conn.cursor() as cur:
        for t in tables:
            if t == "planet_osm_line":
                continue
            geom = "way" if t == "planet_osm_point" else "ST_Centroid(way)"
            cur.execute(
                f"""SELECT osm_id, name, similarity(name, %s) AS sim, ST_Y(ST_Transform({geom}, 4326)) AS lat, ST_X(ST_Transform({geom}, 4326)) AS lon,
                           coalesce(amenity, building, office, shop, landuse, '') AS kind
                    FROM {t} WHERE name IS NOT NULL AND name %% %s ORDER BY sim DESC LIMIT %s""",
                (query, query, limit),
            )
            for osm_id, name, sim, lat, lon, kind in cur.fetchall():
                if sim >= min_similarity:
                    out.append({"source": "osm", "ref_key": "%s:%s" % (t, osm_id), "label": "%s%s" % (name, " (%s)" % kind if kind else ""),
                                "precision": "osm", "lat": lat, "lon": lon, "score": float(sim), "data": {"table": t, "osm_id": osm_id, "kind": kind}})
    return sorted(out, key=lambda r: -r["score"])[:limit]


def replace_communes(conn, communes):
    with conn.cursor() as cur:
        cur.execute("DELETE FROM ref_communes")
        psycopg2.extras.execute_batch(
            cur,
            """INSERT INTO ref_communes (code, nom, codes_postaux, lat, lon, geom, population)
               VALUES (%s, %s, %s, %s, %s, CASE WHEN %s IS NULL THEN NULL ELSE ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography END, %s)""",
            [(c["code"], c["nom"], c.get("codesPostaux") or [], c.get("lat"), c.get("lon"), c.get("lon"), c.get("lon"), c.get("lat"), c.get("population")) for c in communes],
            page_size=500,
        )
    conn.commit()
    return len(communes)


def commune_by_postal(conn, code):
    with conn.cursor() as cur:
        cur.execute("SELECT code, nom, codes_postaux, lat, lon, population FROM ref_communes WHERE %s = ANY(codes_postaux) ORDER BY population DESC NULLS LAST LIMIT 1", (code,))
        rows = _row(cur)
    return rows[0] if rows else None


def commune_by_name(conn, name, min_similarity=0.5):
    with conn.cursor() as cur:
        cur.execute("SELECT code, nom, codes_postaux, lat, lon, population, similarity(nom, %s) AS sim FROM ref_communes WHERE nom %% %s ORDER BY sim DESC, population DESC NULLS LAST LIMIT 1", (name, name))
        rows = _row(cur)
    return rows[0] if rows and rows[0]["sim"] >= min_similarity else None


def cache_get(conn, provider, query):
    with conn.cursor() as cur:
        cur.execute("SELECT result FROM ref_geocode_cache WHERE provider = %s AND query = %s", (provider, query))
        row = cur.fetchone()
    return row[0] if row else None


def cache_put(conn, provider, query, result):
    with conn.cursor() as cur:
        cur.execute("INSERT INTO ref_geocode_cache (provider, query, result) VALUES (%s, %s, %s) ON CONFLICT (provider, query) DO UPDATE SET result = EXCLUDED.result, fetched_at = now()",
                    (provider, query, json.dumps(result, ensure_ascii=False)))


def log_sync(conn, started, positions, refs, links, errors):
    with conn.cursor() as cur:
        cur.execute("INSERT INTO catalog_sync_log (started_at, finished_at, positions, refs, links, errors) VALUES (%s, now(), %s, %s, %s, %s)",
                    (started, positions, refs, links, json.dumps(errors, ensure_ascii=False)))
    conn.commit()


def nearby(conn, lat, lon, radius_m=500, limit=20):
    with conn.cursor() as cur:
        cur.execute(
            """SELECT id, key, label, lat, lon, confidence, status, ST_Distance(geom, ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography) AS distance_m
               FROM catalog_positions WHERE geom IS NOT NULL AND ST_DWithin(geom, ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography, %s)
               ORDER BY distance_m LIMIT %s""",
            (lon, lat, lon, lat, radius_m, limit),
        )
        return _row(cur)
