# -*- coding: utf-8 -*-
"""Référentiels du catalogue de positions (livraison #429) -- chaque
fonction renvoie des RÉFÉRENCES au format de catalog.interpret :
{source, ref_key, label, precision, lat, lon, score, data}. Tout appel
externe est borné (délai, cadence) et mis en cache dans la base ; une
panne d'un référentiel ne bloque jamais les autres.

Sources :
  - geolocations : la table pixel-grid (coordonnées saisies, hiérarchie) ;
  - ban : géocodage Géoplateforme / BAN (data.gouv.fr), index address + poi ;
  - commune : centroïde de commune (référentiel chargé en base depuis
    geo.api.gouv.fr, ou appel direct si non chargé) ;
  - osm : base OSM locale (osm2pgsql) via pg_trgm, sinon Nominatim si une
    URL est configurée (cadence 1 requête/s, politique d'usage OSM).
"""
import logging
import time
from urllib.parse import quote_plus

import requests

import catalog
import store

_log = logging.getLogger("geo_catalog.refs")

import os

# Fournisseurs publics par défaut, remplaçables par un miroir interne
# (GEOCODE_PROVIDER_URL, GEO_CATALOG_COMMUNES_URL, GEO_CATALOG_COMMUNE_BY_CP_URL).
GEOCODE_URL = os.environ.get("GEOCODE_PROVIDER_URL", "").strip() or "https://data.geopf.fr/geocodage/search?q={q}&limit={limit}&index={index}"
COMMUNES_URL = os.environ.get("GEO_CATALOG_COMMUNES_URL", "").strip() or "https://geo.api.gouv.fr/communes?fields=nom,code,codesPostaux,centre,population&format=json"
COMMUNE_BY_CP_URL = os.environ.get("GEO_CATALOG_COMMUNE_BY_CP_URL", "").strip() or "https://geo.api.gouv.fr/communes?codePostal={cp}&fields=nom,code,codesPostaux,centre,population&format=json"
TIMEOUT = 8


# ---- pixel-grid ---------------------------------------------------------------

def fetch_geolocations(pixel_grid_url):
    r = requests.get(pixel_grid_url.rstrip("/") + "/geolocations", timeout=TIMEOUT)
    r.raise_for_status()
    return r.json().get("geolocations") or []


def fetch_matches(pixel_grid_url):
    try:
        r = requests.get(pixel_grid_url.rstrip("/") + "/geolocations/matches", timeout=TIMEOUT)
        r.raise_for_status()
        return r.json().get("matches") or []
    except (requests.RequestException, ValueError) as exc:
        _log.warning("correspondances pixel-grid indisponibles : %s", exc)
        return []


def push_geolocation(pixel_grid_url, localisation, lat, lon, groups=None):
    r = requests.post(pixel_grid_url.rstrip("/") + "/geolocations", json={"localisation": localisation, "latitude": lat, "longitude": lon, "groups": groups or []}, timeout=TIMEOUT)
    return r.status_code, (r.json() if r.content else {})


# ---- BAN / Géoplateforme ---------------------------------------------------------

def ban_refs(conn, label, geocode_url=GEOCODE_URL, limit=3, http=None):
    http = http or requests.get  # résolu à l'appel (simulable dans les tests)
    q = catalog.geocode_query(label)
    if len(q) < 3:
        return []
    out = []
    for index in ("address", "poi"):
        key = "%s|%s" % (index, q)
        cached = store.cache_get(conn, "ban", key)
        if cached is None:
            try:
                r = http(geocode_url.format(q=quote_plus(q), limit=limit, index=index), timeout=TIMEOUT)
                cached = r.json() if r.status_code == 200 else {"error": "HTTP %s" % r.status_code}
            except (requests.RequestException, ValueError) as exc:
                cached = {"error": str(exc)}
            store.cache_put(conn, "ban", key, cached)
        for f in (cached or {}).get("features") or []:
            props, geom = f.get("properties") or {}, f.get("geometry") or {}
            coords = geom.get("coordinates") or [None, None]
            precision = "poi" if index == "poi" else catalog.ban_precision(props.get("type"))
            label_out = props.get("label") or props.get("toponym") or props.get("name") or q
            out.append({"source": "ban", "ref_key": "%s:%s" % (index, props.get("id") or label_out), "label": label_out, "precision": precision,
                        "lat": coords[1], "lon": coords[0], "score": props.get("score"),
                        "data": {"index": index, "type": props.get("type"), "city": props.get("city"), "postcode": props.get("postcode"), "query": q}})
    return out


# ---- communes -----------------------------------------------------------------------

def load_communes(conn, url=COMMUNES_URL, http=None):
    r = (http or requests.get)(url, timeout=60)
    r.raise_for_status()
    rows = []
    for c in r.json():
        centre = (c.get("centre") or {}).get("coordinates") or [None, None]
        rows.append({"code": c.get("code"), "nom": c.get("nom"), "codesPostaux": c.get("codesPostaux") or [], "lat": centre[1], "lon": centre[0], "population": c.get("population")})
    return store.replace_communes(conn, [x for x in rows if x["code"] and x["nom"]])


GENERIC_WORDS = {"site", "agence", "bureau", "salle", "local", "batiment", "bat", "zone", "secteur", "annexe", "depot", "centre", "mairie"}


def commune_refs(conn, label, http=None):
    """Code postal dans le libellé -> commune (base locale, sinon
    geo.api.gouv.fr en cache) ; sinon nom de commune proche (base locale,
    mots génériques « site », « agence »… retirés)."""
    http = http or requests.get
    cp = catalog.commune_query(label)
    out = []
    if cp:
        c = store.commune_by_postal(conn, cp)
        if c is None:
            key = "cp|%s" % cp
            cached = store.cache_get(conn, "commune", key)
            if cached is None:
                try:
                    r = http(COMMUNE_BY_CP_URL.format(cp=cp), timeout=TIMEOUT)
                    cached = r.json() if r.status_code == 200 else []
                except (requests.RequestException, ValueError):
                    cached = []
                store.cache_put(conn, "commune", key, cached)
            best = sorted(cached or [], key=lambda x: -(x.get("population") or 0))
            if best:
                centre = (best[0].get("centre") or {}).get("coordinates") or [None, None]
                c = {"code": best[0].get("code"), "nom": best[0].get("nom"), "lat": centre[1], "lon": centre[0], "population": best[0].get("population")}
        if c:
            out.append({"source": "commune", "ref_key": c["code"], "label": "%s (%s)" % (c["nom"], cp), "precision": "commune", "lat": c["lat"], "lon": c["lon"], "score": 0.9,
                        "data": {"code": c["code"], "postcode": cp, "population": c.get("population")}})
    else:
        q = " ".join(w for w in catalog.geocode_query(label).split() if catalog.normalize(w) not in GENERIC_WORDS)
        if len(q) >= 3:
            try:
                c = store.commune_by_name(conn, q, min_similarity=0.4)
            except Exception:  # noqa: BLE001 -- pg_trgm absent ou table vide
                c = None
            if c:
                out.append({"source": "commune", "ref_key": c["code"], "label": c["nom"], "precision": "municipality", "lat": c["lat"], "lon": c["lon"], "score": float(c.get("sim") or 0.5),
                            "data": {"code": c["code"], "population": c.get("population"), "similarity": c.get("sim")}})
    return out


# ---- OSM ------------------------------------------------------------------------------

class Nominatim(object):
    """Client Nominatim minimal : 1 requête par seconde, User-Agent
    identifié (politique d'usage du service public OSM), cache en base."""

    def __init__(self, url, user_agent="supervision-si geo-catalog", http=None, sleep=time.sleep):
        self.url, self.user_agent, self.http, self.sleep = url.rstrip("/"), user_agent, http or requests.get, sleep
        self._last = 0.0

    def search(self, conn, q, limit=3):
        key = q
        cached = store.cache_get(conn, "nominatim", key)
        if cached is None:
            wait = 1.0 - (time.time() - self._last)
            if wait > 0:
                self.sleep(wait)
            try:
                r = self.http(self.url + "/search", params={"q": q, "format": "jsonv2", "limit": limit, "addressdetails": 0}, headers={"User-Agent": self.user_agent}, timeout=TIMEOUT)
                cached = r.json() if r.status_code == 200 else []
            except (requests.RequestException, ValueError):
                cached = []
            self._last = time.time()
            store.cache_put(conn, "nominatim", key, cached)
        out = []
        for it in cached or []:
            try:
                out.append({"source": "osm", "ref_key": "nominatim:%s/%s" % (it.get("osm_type"), it.get("osm_id")), "label": it.get("display_name"), "precision": "osm",
                            "lat": float(it["lat"]), "lon": float(it["lon"]), "score": float(it.get("importance") or 0.3), "data": {"category": it.get("category"), "type": it.get("type")}})
            except (KeyError, ValueError, TypeError):
                continue
        return out


def osm_refs(conn, label, nominatim=None):
    q = catalog.geocode_query(label)
    if len(q) < 3:
        return []
    try:
        local = store.osm_search(conn, q)
    except Exception as exc:  # noqa: BLE001 -- tables absentes ou requête refusée : jamais bloquant
        conn.rollback()
        local = []
    if local:
        return local
    if nominatim is not None:
        return nominatim.search(conn, q)
    return []


def stored_ref(g):
    if g.get("latitude") is None or g.get("longitude") is None:
        return None
    return {"source": "geolocations", "ref_key": g["localisation"], "label": "coordonnées saisies (%s)" % g["localisation"], "precision": "stored",
            "lat": g["latitude"], "lon": g["longitude"], "score": None,
            "data": {"parent": g.get("parent_localisation"), "type": g.get("location_type"), "updated_at": g.get("updated_at")}}
