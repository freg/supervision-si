# -*- coding: utf-8 -*-
"""geo-catalog-api -- catalogue de positions (livraison #429, backlog 67).

Base PostGIS DÉDIÉE (`GEO_CATALOG_DB_URL`, service `geo-catalog-postgres`
par défaut) : les référentiels (OSM via osm2pgsql, communes, cache de
géocodage) y vivent, elle se déplace seule sur un hôte secondaire (voir
README). Complément de geo-import (staging de shapefiles), jamais la même
base.

Cycle : `POST /sync` lit les localisations et correspondances de
pixel-grid, interroge les référentiels pour chaque lieu (coordonnées
saisies, BAN/Géoplateforme, commune, OSM), calcule l'interprétation la
plus précise et la justesse (catalog.interpret), rattache les objets
(correspondances nom -> lieu, hiérarchie). Décisions : `PUT
/positions/<id>/validate|correct|reset` (droit manage) ; `POST
/positions/<id>/push` recopie la position retenue dans pixel-grid.
"""
import logging as _logging
import os
import sys
from datetime import datetime, timezone

import requests
from flask import Flask, jsonify, request
from flask_cors import CORS

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import catalog  # noqa: E402
import refs  # noqa: E402
import store  # noqa: E402

try:
    from version_endpoint import register_version_route
except ImportError:
    register_version_route = None

app = Flask(__name__)
CORS(app)
if register_version_route:
    register_version_route(app, "geo-catalog-api")

_log = _logging.getLogger("geo_catalog")

DB_URL = os.environ.get("GEO_CATALOG_DB_URL", "").strip() or "postgresql://%s:%s@%s:%s/%s" % (
    os.environ.get("GEO_CATALOG_DB_USER", "geocat"), os.environ.get("GEO_CATALOG_DB_PASSWORD", "geocat"),
    os.environ.get("GEO_CATALOG_DB_HOST", "geo-catalog-postgres"), os.environ.get("GEO_CATALOG_DB_PORT", "5432"),
    os.environ.get("GEO_CATALOG_DB_NAME", "geocat"))
PIXEL_GRID_API_URL = os.environ.get("PIXEL_GRID_API_INTERNAL_URL", "http://pixel-grid-api:5000").rstrip("/")
GEOCODE_URL = os.environ.get("GEOCODE_PROVIDER_URL", "").strip() or refs.GEOCODE_URL
NOMINATIM_URL = os.environ.get("GEO_CATALOG_NOMINATIM_URL", "").strip()
RIGHTS_API_URL = os.environ.get("RIGHTS_API_URL", "").rstrip("/") or None
SYNC_MAX = int(os.environ.get("GEO_CATALOG_SYNC_MAX", "2000"))

_nominatim = refs.Nominatim(NOMINATIM_URL) if NOMINATIM_URL else None


def db():
    conn = store.connect(DB_URL)
    return conn


def _schema_ready():
    try:
        conn = db()
        store.ensure_schema(conn)
        conn.close()
        return True
    except Exception as exc:  # noqa: BLE001 -- base absente au premier démarrage : jamais bloquant
        _log.warning("schéma du catalogue reporté : %s", exc)
        return False


_schema_ready()


def _check_manage_right(body):
    """Même motif FAIL CLOSED que les autres modules (#317, #318)."""
    if not RIGHTS_API_URL:
        return True, None
    groups = body.get("groups") or []
    try:
        resp = requests.post(f"{RIGHTS_API_URL}/check", json={"groups": groups, "resource_type": "geo-catalog-api", "resource_id": None, "action": "manage"}, timeout=5)
    except requests.RequestException:
        return False, "service de droits injoignable -- action refusée par prudence"
    if resp.status_code != 200:
        return False, "service de droits indisponible -- action refusée par prudence"
    try:
        allowed = resp.json().get("allowed", False)
    except ValueError:
        return False, "réponse du service de droits illisible -- action refusée par prudence"
    return allowed, None if allowed else "droit 'manage' sur geo-catalog-api requis (groupe admin_hub, ou un octroi explicite)"


def _json(obj):
    """dates -> ISO pour jsonify."""
    if isinstance(obj, dict):
        return {k: _json(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_json(v) for v in obj]
    if isinstance(obj, datetime):
        return obj.isoformat()
    return obj


# ---- état -----------------------------------------------------------------------

@app.route("/health", methods=["GET"])
def health():
    try:
        conn = db()
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
        conn.close()
        return jsonify({"status": "ok", "db": "ok"}), 200
    except Exception as exc:  # noqa: BLE001
        return jsonify({"status": "degraded", "db": str(exc)}), 200


@app.route("/status", methods=["GET"])
def status():
    conn = db()
    try:
        store.ensure_schema(conn)
        s = store.summary(conn)
        s["osm_tables"] = store.osm_tables(conn)
        s["nominatim"] = bool(NOMINATIM_URL)
        s["geocoder"] = GEOCODE_URL.split("?")[0]
        s["db_host"] = DB_URL.split("@")[-1].split("/")[0] if "@" in DB_URL else "?"
        s["pixel_grid"] = PIXEL_GRID_API_URL
        return jsonify(_json(s)), 200
    finally:
        conn.close()


# ---- référentiels ------------------------------------------------------------------

@app.route("/referentials/communes/load", methods=["POST"])
def load_communes_route():
    body = request.get_json(silent=True) or {}
    allowed, error = _check_manage_right(body)
    if not allowed:
        return jsonify({"error": error}), 403
    conn = db()
    try:
        n = refs.load_communes(conn)
        return jsonify({"status": "ok", "communes": n}), 200
    except (requests.RequestException, ValueError) as exc:
        conn.rollback()
        return jsonify({"error": "chargement des communes impossible : %s" % exc}), 502
    finally:
        conn.close()


@app.route("/referentials/lookup", methods=["GET"])
def lookup():
    """Essai à blanc d'un libellé : références et interprétation, rien d'écrit
    (sauf le cache de géocodage)."""
    label = (request.args.get("label") or "").strip()
    if not label:
        return jsonify({"error": "paramètre 'label' requis"}), 400
    conn = db()
    try:
        found = _gather_refs(conn, {"localisation": label, "latitude": request.args.get("lat", type=float), "longitude": request.args.get("lon", type=float)})
        conn.commit()
        return jsonify(_json({"label": label, "refs": found, "interpretation": catalog.interpret(found)})), 200
    finally:
        conn.close()


def _gather_refs(conn, g):
    found = []
    sr = refs.stored_ref(g)
    if sr and g.get("localisation") != "__default__":
        found.append(sr)
    label = g.get("localisation") or ""
    try:
        found.extend(refs.ban_refs(conn, label, geocode_url=GEOCODE_URL))
    except Exception as exc:  # noqa: BLE001
        _log.warning("BAN indisponible pour %r : %s", label, exc)
    try:
        found.extend(refs.commune_refs(conn, label))
    except Exception as exc:  # noqa: BLE001
        conn.rollback()
        _log.warning("communes indisponibles pour %r : %s", label, exc)
    try:
        found.extend(refs.osm_refs(conn, label, nominatim=_nominatim))
    except Exception as exc:  # noqa: BLE001
        conn.rollback()
        _log.warning("OSM indisponible pour %r : %s", label, exc)
    return found


# ---- synchronisation ---------------------------------------------------------------

@app.route("/sync", methods=["POST"])
def sync():
    """Reconstruit le catalogue depuis pixel-grid (localisations +
    correspondances). Les décisions humaines sont conservées. `only` =
    liste de localisations à rafraîchir (sinon toutes, bornées par
    GEO_CATALOG_SYNC_MAX)."""
    body = request.get_json(silent=True) or {}
    allowed, error = _check_manage_right(body)
    if not allowed:
        return jsonify({"error": error}), 403
    started = datetime.now(timezone.utc)
    try:
        geos = refs.fetch_geolocations(PIXEL_GRID_API_URL)
    except (requests.RequestException, ValueError) as exc:
        return jsonify({"error": "pixel-grid injoignable : %s" % exc}), 502
    matches = refs.fetch_matches(PIXEL_GRID_API_URL)
    only = set(body.get("only") or [])
    conn = db()
    errors, n_pos, n_refs, n_links = [], 0, 0, 0
    try:
        store.ensure_schema(conn)
        by_loc = {}
        for m in matches:
            if m.get("localisation"):
                by_loc.setdefault(m["localisation"], []).append(m)
        children = {}
        for g in geos:
            if g.get("parent_localisation"):
                children.setdefault(g["parent_localisation"], []).append(g["localisation"])
        for g in geos[:SYNC_MAX]:
            loc = g.get("localisation")
            if not loc or loc == "__default__" or (only and loc not in only):
                continue
            try:
                pos = store.upsert_position(conn, "geolocation:%s" % loc, loc, kind="geolocation")
                found = _gather_refs(conn, g)
                store.replace_refs(conn, pos["id"], found)
                decision = {"status": pos["status"], "lat": pos["decided_lat"], "lon": pos["decided_lon"]} if pos["status"] in ("validated", "corrected") else None
                interp = catalog.interpret(found, decision)
                store.apply_interpretation(conn, pos["id"], interp)
                links = []
                for m in by_loc.get(loc, []):
                    links.append({"object_type": "supervised", "object_id": m["subject"], "label": m.get("name") or m.get("site") or m["subject"],
                                  "data": {"status": m.get("status"), "score": m.get("score"), "method": m.get("method")}})
                for c in children.get(loc, []):
                    links.append({"object_type": "geolocation", "object_id": c, "label": c, "data": {"relation": "enfant"}})
                if g.get("parent_localisation"):
                    links.append({"object_type": "geolocation", "object_id": g["parent_localisation"], "label": g["parent_localisation"], "data": {"relation": "parent"}})
                store.replace_links(conn, pos["id"], links, "sync")
                conn.commit()
                n_pos += 1; n_refs += len(found); n_links += len(links)
            except Exception as exc:  # noqa: BLE001 -- une localisation en échec n'arrête pas les autres
                conn.rollback()
                errors.append({"localisation": loc, "error": str(exc)})
                _log.exception("sync %r : %s", loc, exc)
        store.log_sync(conn, started, n_pos, n_refs, n_links, errors)
        return jsonify({"status": "ok", "positions": n_pos, "refs": n_refs, "links": n_links, "errors": errors}), 200
    finally:
        conn.close()


# ---- positions -------------------------------------------------------------------------

@app.route("/positions", methods=["GET"])
def positions():
    conn = db()
    try:
        rows = store.list_positions(conn, status=request.args.get("status"), q=request.args.get("q"),
                                    min_confidence=request.args.get("min_confidence", type=int), max_confidence=request.args.get("max_confidence", type=int),
                                    limit=min(2000, request.args.get("limit", type=int) or 500))
        refs_by, links_by = store.all_refs_and_links(conn, [r["id"] for r in rows])
        for r in rows:
            r["refs"] = refs_by.get(r["id"], [])
            r["links"] = links_by.get(r["id"], [])
            r["precision_label"] = catalog.PRECISION_LABELS.get(r.get("precision"), r.get("precision"))
        return jsonify(_json({"positions": rows, "summary": store.summary(conn)})), 200
    finally:
        conn.close()


@app.route("/positions/<int:pid>", methods=["GET"])
def position(pid):
    conn = db()
    try:
        p = store.get_position(conn, pid)
        if p is None:
            return jsonify({"error": "position inconnue"}), 404
        p["precision_label"] = catalog.PRECISION_LABELS.get(p.get("precision"), p.get("precision"))
        if p.get("lat") is not None:
            p["nearby"] = [n for n in store.nearby(conn, p["lat"], p["lon"]) if n["id"] != pid]
        return jsonify(_json(p)), 200
    finally:
        conn.close()


def _decide(pid, status):
    body = request.get_json(silent=True) or {}
    allowed, error = _check_manage_right(body)
    if not allowed:
        return jsonify({"error": error}), 403
    lat, lon = body.get("lat"), body.get("lon")
    if status == "corrected" and (lat is None or lon is None):
        return jsonify({"error": "'lat' et 'lon' requis pour corriger"}), 400
    if lat is not None and not (-90 <= float(lat) <= 90 and -180 <= float(lon) <= 180):
        return jsonify({"error": "coordonnées hors limites"}), 400
    conn = db()
    try:
        r = store.decide(conn, pid, status, lat=lat, lon=lon, note=body.get("note"))
        if r is None:
            return jsonify({"error": "position inconnue"}), 404
        if r is False:
            return jsonify({"error": "rien à valider : aucune position calculée -- corriger avec lat/lon"}), 400
        conn.commit()
        p = store.get_position(conn, pid)
        return jsonify(_json({"status": "ok", "position": p})), 200
    finally:
        conn.close()


@app.route("/positions/<int:pid>/validate", methods=["PUT"])
def validate(pid):
    return _decide(pid, "validated")


@app.route("/positions/<int:pid>/correct", methods=["PUT"])
def correct(pid):
    return _decide(pid, "corrected")


@app.route("/positions/<int:pid>/reset", methods=["PUT"])
def reset(pid):
    return _decide(pid, "auto")


@app.route("/positions/<int:pid>/push", methods=["POST"])
def push(pid):
    """Recopie la position retenue dans la table geolocations de pixel-grid
    (droit manage, transmis à pixel-grid avec les mêmes groupes)."""
    body = request.get_json(silent=True) or {}
    allowed, error = _check_manage_right(body)
    if not allowed:
        return jsonify({"error": error}), 403
    conn = db()
    try:
        p = store.get_position(conn, pid)
    finally:
        conn.close()
    if p is None:
        return jsonify({"error": "position inconnue"}), 404
    if p.get("lat") is None:
        return jsonify({"error": "aucune position à recopier"}), 400
    if p.get("kind") != "geolocation":
        return jsonify({"error": "seules les localisations pixel-grid se recopient"}), 400
    try:
        code, data = refs.push_geolocation(PIXEL_GRID_API_URL, p["label"], p["lat"], p["lon"], groups=body.get("groups"))
    except (requests.RequestException, ValueError) as exc:
        return jsonify({"error": "pixel-grid injoignable : %s" % exc}), 502
    if code != 200:
        return jsonify({"error": "pixel-grid a refusé (%s) : %s" % (code, (data or {}).get("error"))}), 502
    return jsonify({"status": "ok", "localisation": p["label"], "latitude": p["lat"], "longitude": p["lon"]}), 200


@app.route("/positions/<int:pid>/refs/<int:rid>/use", methods=["PUT"])
def use_ref(pid, rid):
    """Corriger en reprenant une référence précise du catalogue."""
    body = request.get_json(silent=True) or {}
    allowed, error = _check_manage_right(body)
    if not allowed:
        return jsonify({"error": error}), 403
    conn = db()
    try:
        p = store.get_position(conn, pid)
        if p is None:
            return jsonify({"error": "position inconnue"}), 404
        ref = next((r for r in p["refs"] if r["id"] == rid), None)
        if ref is None or ref.get("lat") is None:
            return jsonify({"error": "référence inconnue ou sans coordonnées"}), 400
        store.decide(conn, pid, "corrected", lat=ref["lat"], lon=ref["lon"], note="reprise de la référence %s : %s" % (ref["source"], ref.get("label")))
        conn.commit()
        return jsonify(_json({"status": "ok", "position": store.get_position(conn, pid)})), 200
    finally:
        conn.close()


@app.route("/logs", methods=["GET"])
def logs():
    return jsonify({"service": "geo-catalog-api", "entries": []}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")))
