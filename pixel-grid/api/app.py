"""
API d'agrégation du module pixel-grid — supporte deux backends au choix
(variable d'environnement DB_BACKEND=sqlite|postgres, défaut sqlite).

Principe inchangé quel que soit le backend : le frontend ne charge
jamais le dataset complet — chaque requête d'agrégation ne renvoie que
les cellules du niveau de zoom et de la période demandés.

Non vérifié depuis l'environnement Claude : le chemin PostgreSQL n'a
pas pu être testé contre un vrai serveur (pas de PostgreSQL disponible,
pas d'accès réseau pour en installer un). La syntaxe SQL a été relue
avec attention mais reste à valider en conditions réelles.
"""
import ipaddress
import json
import logging
import os
import sqlite3
import time
from datetime import datetime, timezone
from urllib.parse import quote_plus

import requests
from flask import Flask, jsonify, request
from flask_cors import CORS
try:
    from version_endpoint import register_version_route
except ImportError:
    register_version_route = None

app = Flask(__name__)
CORS(app)
if register_version_route:
    register_version_route(app, "pixel-grid-api")

_log = logging.getLogger("pixel_grid_app")

# Branchement rights-api -- livraison #317, item 38 du backlog.
# Coordonnées de carte pour la visualisation -- une entrée trafiquée
# ne configure rien de réel mais peut égarer la lecture d'une carte
# (mauvais lieu affiché). Gardé sur les 4 routes d'ÉCRITURE
# (créer/modifier/supprimer une géolocalisation, scan, enregistrement
# d'IP) -- jamais la lecture/agrégation.
RIGHTS_API_URL = os.environ.get("RIGHTS_API_URL", "").rstrip("/") or None


def _check_manage_right(body):
    """Même motif FAIL CLOSED que les branchements précédents
    (#289-292, #308-316) -- jamais fail-open, y compris pour
    admin_hub si rights-api est injoignable."""
    if not RIGHTS_API_URL:
        return True, None
    groups = body.get("groups") or []
    try:
        resp = requests.post(
            f"{RIGHTS_API_URL}/check",
            json={"groups": groups, "resource_type": "pixel-grid-api", "resource_id": None, "action": "manage"},
            timeout=5,
        )
    except requests.RequestException as exc:
        _log.debug("_check_manage_right : rights-api injoignable, refus par prudence -- %s", exc)
        return False, "service de droits injoignable -- action refusée par prudence"
    if resp.status_code != 200:
        _log.debug("_check_manage_right : rights-api a répondu %s", resp.status_code)
        return False, "service de droits indisponible -- action refusée par prudence"
    try:
        allowed = resp.json().get("allowed", False)
    except ValueError:
        return False, "réponse du service de droits illisible -- action refusée par prudence"
    if not allowed:
        _log.debug("_check_manage_right : refusé pour les groupes %s", groups)
    return allowed, None if allowed else "droit 'manage' sur pixel-grid-api requis (groupe admin_hub, ou un octroi explicite)"

DB_BACKEND = os.environ.get("DB_BACKEND", "sqlite").strip().lower()
DB_PATH = os.environ.get("PIXEL_GRID_DB_PATH", "/data/timeseries.db")  # sqlite uniquement

DEFAULT_LOCATION_KEY = "__default__"
_default_lat_raw = os.environ.get("PIXEL_GRID_DEFAULT_LAT", "").strip()
_default_lon_raw = os.environ.get("PIXEL_GRID_DEFAULT_LON", "").strip()
DEFAULT_LAT = float(_default_lat_raw) if _default_lat_raw else None
DEFAULT_LON = float(_default_lon_raw) if _default_lon_raw else None

# Géolocalisation IP publique — service externe gratuit et sans clé
# par défaut (ip-api.com, 45 requêtes/minute sur le tier gratuit) ;
# GEOIP_PROVIDER_URL entièrement remplaçable via .env pour passer à
# un service payant/plus généreux le jour venu, tant que la forme de
# réponse reste compatible (status/lat/lon/city/country). Jamais
# appelé pour une IP privée — classify_ip() en amont, voir plus bas.
GEOIP_PROVIDER_URL = os.environ.get("GEOIP_PROVIDER_URL", "").strip() or (
    "http://ip-api.com/json/{ip}?fields=status,message,lat,lon,city,country"
)
GEOIP_TIMEOUT_SECONDS = float(os.environ.get("GEOIP_TIMEOUT_SECONDS", "5"))
# Pause entre deux appels externes lors d'un lot — reste sous la
# limite du tier gratuit (45/min = 1 toutes les 1,33s) quel que soit
# le nombre d'IP publiques à résoudre en une fois, sans avoir besoin
# de suivre un compteur glissant.
GEOIP_MIN_INTERVAL_SECONDS = float(os.environ.get("GEOIP_MIN_INTERVAL_SECONDS", "1.5"))

# Géocodage de noms de lieux/adresses (bouton "🔍 Chercher" de
# GeolocationApp) — service BAN/Géoplateforme (gratuit, sans clé,
# limite 50 requêtes/seconde/IP) par défaut. L'ancienne URL
# api-adresse.data.gouv.fr est dépréciée (décommissionnement prévu fin
# janvier 2026) — data.geopf.fr est la nouvelle adresse officielle.
# GEOCODE_PROVIDER_URL entièrement remplaçable via .env pour passer à
# un autre fournisseur, tant que la réponse reste un GeoJSON
# FeatureCollection (features[].geometry.coordinates + .properties).
# GEOCODE_INDEX : "poi" par défaut (lieux nommés) plutôt que "address"
# (adresses postales structurées) — les valeurs de `localisation` de
# ce module sont des noms de site (ex. "Parc/Batiment 5"), pas
# des adresses avec numéro de voie ; à repasser à "address" via .env
# si votre usage réel est différent.
GEOCODE_PROVIDER_URL = os.environ.get("GEOCODE_PROVIDER_URL", "").strip() or (
    "https://data.geopf.fr/geocodage/search?q={q}&limit={limit}&index={index}"
)
GEOCODE_INDEX = os.environ.get("GEOCODE_INDEX", "poi").strip() or "poi"
GEOCODE_TIMEOUT_SECONDS = float(os.environ.get("GEOCODE_TIMEOUT_SECONDS", "5"))

# Centroïde de commune par code postal (colonne "Position" de l'onglet
# Fusion IP/MAC, pour les noms d'hôte qui embarquent un code postal —
# ex. "BIO17-17300-ISLANDE-RB3011"). Service officiel API Découpage
# Administratif (geo.api.gouv.fr), gratuit, sans clé, aucune limite de
# débit documentée pour un usage normal. `centre` est le point retenu
# par l'IGN (chef-lieu si le centroïde mathématique tombe hors de la
# zone habitée principale, cf. sa documentation) — pas un centroïde
# géométrique brut, plus utile cartographiquement.
COMMUNE_PROVIDER_URL = os.environ.get("COMMUNE_PROVIDER_URL", "").strip() or (
    "https://geo.api.gouv.fr/communes?codePostal={code_postal}"
    "&fields=nom,code,centre,codesPostaux,population&format=json"
)
COMMUNE_TIMEOUT_SECONDS = float(os.environ.get("COMMUNE_TIMEOUT_SECONDS", "5"))

LEVELS = ["year", "month", "day", "hour", "minute"]

_STRFTIME_FORMATS = {"year": "%Y", "month": "%m", "day": "%d", "hour": "%H", "minute": "%M"}
_TOCHAR_FORMATS = {"year": "YYYY", "month": "MM", "day": "DD", "hour": "HH24", "minute": "MI"}

# Formats "plage" — pour /aggregate_range, qui couvre potentiellement
# plusieurs années/mois d'affilée : contrairement à /aggregate (calé sur
# un calendrier classique, ex. "tous les mois de l'année 2026"), ces
# formats gardent le contexte complet (année-mois-jour...) pour ne
# jamais fusionner deux périodes différentes dans la même case — sinon
# tous les mois de mars, toutes années confondues, finiraient dans la
# même cellule.
_RANGE_STRFTIME_FORMATS = {
    "year": "%Y", "month": "%Y-%m", "day": "%Y-%m-%d",
    "hour": "%Y-%m-%d %H", "minute": "%Y-%m-%d %H:%M",
}
_RANGE_TOCHAR_FORMATS = {
    "year": "YYYY", "month": "YYYY-MM", "day": "YYYY-MM-DD",
    "hour": "YYYY-MM-DD HH24", "minute": "YYYY-MM-DD HH24:MI",
}
# Bornes de sécurité : évite qu'une requête mal calibrée (ex: minute sur
# 2 ans = ~1M cellules) ne fasse exploser la réponse ou le navigateur.
_UNIT_SECONDS = {"year": 31536000, "month": 2592000, "day": 86400, "hour": 3600, "minute": 60}
MAX_RANGE_CELLS = 5000

if DB_BACKEND == "postgres":
    import psycopg2

    PG_CONFIG = {
        "host": os.environ.get("PGHOST", "localhost"),
        "port": os.environ.get("PGPORT", "6543"),
        "user": os.environ.get("PGUSER", "pixelgrid"),
        "password": os.environ.get("PGPASSWORD", "pixelgrid"),
        "dbname": os.environ.get("PGDATABASE", "pixelgrid"),
    }
    PLACEHOLDER = "%s"
elif DB_BACKEND == "sqlite":
    PLACEHOLDER = "?"
else:
    raise RuntimeError(f"DB_BACKEND inconnu : '{DB_BACKEND}' (attendu: sqlite ou postgres)")


def get_connection():
    if DB_BACKEND == "postgres":
        conn = psycopg2.connect(**PG_CONFIG)
        conn.set_session(readonly=True)
        return conn
    # Lecture seule côté API : l'écriture n'est faite que par le
    # générateur (import CSV en masse), jamais par ce service — SAUF
    # pour la table geolocations (voir get_write_connection), éditable
    # en direct depuis l'interface.
    return sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)


def get_write_connection():
    """
    Connexion en écriture — réservée aux endpoints de géolocalisation
    (/geolocations, /geolocations/scan). events et type_meta restent
    en lecture seule via get_connection().
    """
    if DB_BACKEND == "postgres":
        return psycopg2.connect(**PG_CONFIG)
    return sqlite3.connect(DB_PATH)


def ensure_geolocations_hierarchy_columns():
    """
    Migration DOUCE -- ajoute parent_localisation/location_type à la
    table geolocations existante si absentes, jamais une recréation :
    cette table contient déjà des données réelles (équipements
    réseau géocodés) sur un vrai déploiement. Appelée une fois au
    chargement du module, comme les ensure_schema() des autres
    services de ce projet -- mais celui-ci n'a normalement AUCUNE
    logique de schéma (table créée une fois par le générateur de
    données, voir data-generator/schema.sql) : exception volontaire
    pour cet ajout précis, plutôt que d'exiger une recréation complète
    de la base sur un déploiement existant.
    """
    try:
        conn = get_write_connection()
        cur = conn.cursor()
        if DB_BACKEND == "postgres":
            cur.execute(
                "SELECT column_name FROM information_schema.columns WHERE table_name = 'geolocations'"
            )
            existing = {row[0] for row in cur.fetchall()}
        else:
            cur.execute("PRAGMA table_info(geolocations)")
            existing = {row[1] for row in cur.fetchall()}
        if "parent_localisation" not in existing:
            cur.execute("ALTER TABLE geolocations ADD COLUMN parent_localisation TEXT")
        if "location_type" not in existing:
            cur.execute("ALTER TABLE geolocations ADD COLUMN location_type TEXT")
        conn.commit()
        conn.close()
    except Exception as exc:  # noqa: BLE001 — la base peut ne pas être prête au tout premier démarrage (générateur pas encore passé), jamais bloquant
        app.logger.warning("Migration hiérarchie geolocations reportée : %s", exc)


ensure_geolocations_hierarchy_columns()


def bucket_expr(level):
    """Expression SQL de regroupement temporel calendaire, adaptée au dialecte."""
    if DB_BACKEND == "postgres":
        fmt = _TOCHAR_FORMATS[level]
        return f"to_char(to_timestamp(ts) AT TIME ZONE 'UTC', '{fmt}')"
    fmt = _STRFTIME_FORMATS[level]
    return f"strftime('{fmt}', ts, 'unixepoch')"


def bucket_expr_range(level):
    """
    Expression SQL de regroupement pour /aggregate_range — garde le
    contexte complet (voir commentaire sur _RANGE_STRFTIME_FORMATS).
    Les deux dialectes produisent volontairement la même chaîne pour un
    même point (ex: "2026-03-15 14"), ce qui permet de reparser le
    résultat de façon identique quel que soit le backend.
    """
    if DB_BACKEND == "postgres":
        fmt = _RANGE_TOCHAR_FORMATS[level]
        return f"to_char(to_timestamp(ts) AT TIME ZONE 'UTC', '{fmt}')"
    fmt = _RANGE_STRFTIME_FORMATS[level]
    return f"strftime('{fmt}', ts, 'unixepoch')"


def parse_bucket_key(level, key):
    """Reparse une clé de bucket 'plage' en date de début exacte (UTC)."""
    fmt = {
        "year": "%Y", "month": "%Y-%m", "day": "%Y-%m-%d",
        "hour": "%Y-%m-%d %H", "minute": "%Y-%m-%d %H:%M",
    }[level]
    return datetime.strptime(key, fmt).replace(tzinfo=timezone.utc)


def get_type_meta(cur, type_name):
    cur.execute(
        f"SELECT kind, config_json FROM type_meta WHERE type = {PLACEHOLDER}", (type_name,)
    )
    row = cur.fetchone()
    if row is None:
        return None
    kind, config_json = row
    return {"kind": kind, "config": json.loads(config_json)}


def parse_period_bounds(level, period):
    """
    Renvoie (start_epoch, end_epoch, group_expr) pour la requête
    d'agrégation. `period` scope la fenêtre ; `level` détermine à la
    fois la granularité de regroupement et l'unité de la période reçue.
    """
    group = bucket_expr(level)

    if level == "year":
        return None, None, group

    if level == "month":
        year = int(period)
        start = datetime(year, 1, 1, tzinfo=timezone.utc)
        end = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
        return int(start.timestamp()), int(end.timestamp()), group

    if level == "day":
        year, month = (int(p) for p in period.split("-"))
        start = datetime(year, month, 1, tzinfo=timezone.utc)
        end_year, end_month = (year, month + 1) if month < 12 else (year + 1, 1)
        end = datetime(end_year, end_month, 1, tzinfo=timezone.utc)
        return int(start.timestamp()), int(end.timestamp()), group

    if level == "hour":
        year, month, day = (int(p) for p in period.split("-"))
        start = datetime(year, month, day, tzinfo=timezone.utc)
        end = datetime.fromtimestamp(start.timestamp() + 86400, tz=timezone.utc)
        return int(start.timestamp()), int(end.timestamp()), group

    if level == "minute":
        date_part, hour_part = period.split("T")
        year, month, day = (int(p) for p in date_part.split("-"))
        hour = int(hour_part)
        start = datetime(year, month, day, hour, tzinfo=timezone.utc)
        end = datetime.fromtimestamp(start.timestamp() + 3600, tz=timezone.utc)
        return int(start.timestamp()), int(end.timestamp()), group

    raise ValueError(f"level inconnu : {level}")


def color_for_enum_bucket(error_count, none_count, total, seuil_attention, seuil_alerte):
    """
    Coloration par TAUX plutôt que simple présence : une seule erreur
    dans une cellule à la minute (total=1) donne un taux de 100%, donc
    se comporte naturellement comme avant à grain fin ; à grain grossier
    (mois, année), le taux évite qu'une seule erreur noyée dans des
    milliers de points ne fasse basculer toute la cellule au rouge.
    """
    if total == 0:
        return "empty"
    error_rate = error_count / total
    if error_rate >= seuil_alerte:
        return "red"
    if error_rate >= seuil_attention or none_count > 0:
        return "amber"
    return "green"


def color_for_continuous_bucket(avg_value, seuil_bas, seuil_moyen):
    if avg_value is None:
        return "empty"
    if avg_value < seuil_bas:
        return "green"
    if avg_value < seuil_moyen:
        return "amber"
    return "red"


def ensure_default_geolocation():
    """
    Garantit l'existence d'une entrée "position par défaut" (repli pour
    les événements sans localisation connue) — pré-remplie depuis les
    variables d'environnement si fournies, sinon laissée en attente
    (comme n'importe quel lieu non mappé, éditable dans l'onglet
    Géolocalisation).
    """
    conn = get_write_connection()
    try:
        cur = conn.cursor()
        cur.execute(f"SELECT 1 FROM geolocations WHERE localisation = {PLACEHOLDER}", [DEFAULT_LOCATION_KEY])
        if cur.fetchone() is not None:
            return
        now = datetime.now(timezone.utc).isoformat()
        cur.execute(
            f"INSERT INTO geolocations (localisation, latitude, longitude, created_at, updated_at) "
            f"VALUES ({PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER})",
            [DEFAULT_LOCATION_KEY, DEFAULT_LAT, DEFAULT_LON, now, now],
        )
        conn.commit()
    except Exception as exc:  # noqa: BLE001 — ne doit jamais empêcher le démarrage de l'API
        app.logger.warning("ensure_default_geolocation a échoué : %s", exc)
    finally:
        conn.close()


def ensure_admin_user():
    """Ébauche multi-utilisateur — seed du seul utilisateur pour l'instant."""
    conn = get_write_connection()
    try:
        cur = conn.cursor()
        cur.execute(f"SELECT 1 FROM users WHERE login = {PLACEHOLDER}", ["admin"])
        if cur.fetchone() is not None:
            return
        now = datetime.now(timezone.utc).isoformat()
        cur.execute(
            f"INSERT INTO users (login, group_name, config_json, created_at, updated_at) "
            f"VALUES ({PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER})",
            ["admin", "admins", "{}", now, now],
        )
        conn.commit()
    except Exception as exc:  # noqa: BLE001
        app.logger.warning("ensure_admin_user a échoué : %s", exc)
    finally:
        conn.close()


try:
    ensure_default_geolocation()
    ensure_admin_user()
except Exception as exc:  # noqa: BLE001 — la base peut ne pas être prête au tout premier démarrage
    app.logger.warning("Seed au démarrage reporté : %s", exc)


# ------------------------------------------------------------------
# Journal en memoire (endpoint /logs) -- capture les WARNING et plus
# graves de CE service pour l'agregateur de logs du frontend (onglet
# Logs + bandeau pied de page). Ne capture PAS le corps des requetes
# ni de donnee metier -- seulement ce que ce fichier journalise deja
# lui-meme (app.logger.warning/error) plus les exceptions non gerees
# que Flask/Werkzeug journalisent nativement en ERROR. Tampon
# circulaire en memoire, borne (LOG_BUFFER_SIZE, defaut 200), jamais
# persiste sur disque -- perdu au redemarrage du conteneur, attendu
# pour un outil de diagnostic a chaud, pas un historique long terme.
# Seuil par defaut WARNING (pas INFO) : evite de capturer le bruit des
# logs d'acces Werkzeug (une ligne par requete HTTP, y compris le
# polling de /logs lui-meme), qui noierait le signal utile.
# ------------------------------------------------------------------
# Client Memcached -- livraison #145, nécessaire au tampon de logs
# PARTAGÉ ci-dessous (ce service tourne avec 2 workers Gunicorn,
# processus séparés, mémoire NON partagée). Recréé à chaque appel
# (même motif établi ailleurs dans ce projet, voir api/app.py) --
# évite de garder une connexion morte si Memcached redémarre.
from pymemcache.client.base import Client as _MemcacheClient

MEMCACHED_HOST = os.environ.get("MEMCACHED_HOST", "memcached")
MEMCACHED_PORT = int(os.environ.get("MEMCACHED_PORT", "11211"))


def get_memcache_client():
    return _MemcacheClient((MEMCACHED_HOST, MEMCACHED_PORT), connect_timeout=2, timeout=2)


# Journal PARTAGE (endpoint /logs) -- stocke dans Memcached (voir
# shared/log_buffer.py pour le raisonnement complet) -- PAS un tampon
# en memoire de processus.
try:
    from log_buffer import make_shared_log_handler, read_shared_log_buffer
except ImportError:
    make_shared_log_handler = None
    read_shared_log_buffer = None

SERVICE_NAME = "pixel-grid-api"
LOG_BUFFER_SIZE = int(os.environ.get("LOG_BUFFER_SIZE", "200"))
LOG_CAPTURE_LEVEL = os.environ.get("LOG_CAPTURE_LEVEL", "WARNING").strip().upper()

if make_shared_log_handler:
    import logging as _logging
    _log_handler = make_shared_log_handler(
        SERVICE_NAME, get_memcache_client, buffer_size=LOG_BUFFER_SIZE, capture_level=LOG_CAPTURE_LEVEL,
    )
    _logging.getLogger().addHandler(_log_handler)


@app.route("/logs", methods=["GET"])
def get_logs():
    limit = request.args.get("limit", type=int)
    entries = read_shared_log_buffer(SERVICE_NAME, get_memcache_client, limit=limit, buffer_size=LOG_BUFFER_SIZE) if read_shared_log_buffer else []
    return jsonify({"service": SERVICE_NAME, "entries": entries}), 200


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "backend": DB_BACKEND}), 200


@app.route("/meta", methods=["GET"])
def meta():
    type_name = request.args.get("type")
    if not type_name:
        return jsonify({"error": "paramètre 'type' requis"}), 400

    conn = get_connection()
    try:
        cur = conn.cursor()
        type_meta = get_type_meta(cur, type_name)
        if type_meta is None:
            return jsonify({"error": f"type inconnu : {type_name}"}), 404

        cur.execute(
            f"SELECT MIN(ts), MAX(ts), COUNT(*) FROM events WHERE type = {PLACEHOLDER}",
            (type_name,),
        )
        min_ts, max_ts, count = cur.fetchone()

        return jsonify(
            {
                "type": type_name,
                "kind": type_meta["kind"],
                "config": type_meta["config"],
                "min_ts": min_ts,
                "max_ts": max_ts,
                "count": count,
                "span_days": (max_ts - min_ts) / 86400 if min_ts and max_ts else 0,
                "backend": DB_BACKEND,
            }
        ), 200
    finally:
        conn.close()


@app.route("/types", methods=["GET"])
def list_types():
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT type, kind FROM type_meta ORDER BY type")
        rows = cur.fetchall()
        return jsonify({"types": [{"type": t, "kind": k} for t, k in rows]}), 200
    finally:
        conn.close()


def classify_ip(ip_str):
    """Classe une chaîne en 'private' (RFC1918, loopback, link-local,
    réservée, multicast — jamais géolocalisable publiquement, par
    définition, pas une limite technique contournable), 'public'
    (candidate à un lookup GeoIP externe) ou 'invalid' (ne ressemble à
    aucune adresse IP valide — v4 ou v6). S'appuie sur le module
    standard `ipaddress` plutôt que sur des plages codées à la main :
    plus complet (couvre aussi IPv6) et déjà éprouvé, jamais une
    exception ici même sur une chaîne complètement absurde."""
    try:
        addr = ipaddress.ip_address(ip_str)
    except (ValueError, TypeError):
        return "invalid"
    if addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_reserved or addr.is_multicast or addr.is_unspecified:
        return "private"
    return "public"


def geoip_lookup(ip_str):
    """Interroge le service GeoIP externe configuré. Ne fait JAMAIS
    l'appel réseau pour une IP privée — re-vérifié ici même si
    l'appelant est censé l'avoir déjà fait (classify_ip), pour ne
    jamais dépendre d'une seule garde-fou avant une fuite vers un
    tiers. Dégradé systématique (retourne None) sur toute erreur —
    service indisponible, quota dépassé, réponse inattendue, IP non
    résolue par le fournisseur — jamais bloquant pour l'appelant."""
    if classify_ip(ip_str) != "public":
        return None
    # Traces DEBUG (livraison #225, audit rétroactif) -- l'URL
    # COMPLÈTE n'est jamais tracée : GEOIP_PROVIDER_URL est
    # surchargeable via .env, un déploiement pourrait un jour
    # configurer un fournisseur dont l'URL embarque une clé d'API.
    app.logger.debug("geoip_lookup : démarré pour %s", ip_str)
    start = time.monotonic()
    try:
        url = GEOIP_PROVIDER_URL.format(ip=ip_str)
        response = requests.get(url, timeout=GEOIP_TIMEOUT_SECONDS)
        response.raise_for_status()
        data = response.json()
    except (requests.RequestException, ValueError) as exc:
        elapsed_ms = int((time.monotonic() - start) * 1000)
        app.logger.debug("geoip_lookup : ÉCHEC après %d ms pour %s -- %s", elapsed_ms, ip_str, exc)
        return None
    elapsed_ms = int((time.monotonic() - start) * 1000)
    if not isinstance(data, dict) or data.get("status") == "fail":
        app.logger.debug("geoip_lookup : réponse en %d ms mais IP %s non résolue par le fournisseur", elapsed_ms, ip_str)
        return None
    lat, lon = data.get("lat"), data.get("lon")
    if lat is None or lon is None:
        app.logger.debug("geoip_lookup : réponse en %d ms mais sans coordonnées pour %s", elapsed_ms, ip_str)
        return None
    app.logger.debug("geoip_lookup : succès en %d ms pour %s", elapsed_ms, ip_str)
    return {"latitude": lat, "longitude": lon, "city": data.get("city"), "country": data.get("country")}


# ------------------------------------------------------------------
# Géocodage de noms de lieux/adresses — même esprit que geoip_lookup
# (service externe configurable, dégradé systématique, jamais
# d'exception non gérée), mais fonction de parsing gardée PURE et
# séparée de l'appel réseau pour être testable sans requête réelle.
# ------------------------------------------------------------------

def parse_geocode_response(data):
    """data : réponse JSON brute du service de géocodage (GeoJSON
    FeatureCollection attendu, format "geocodejson" — features[] avec
    geometry.coordinates=[lon,lat] et properties.label/score/...).
    Retourne une liste de candidats normalisés, triée par score
    décroissant. Ne lève jamais : toute forme inattendue -> liste
    vide plutôt qu'une exception qui remonterait à l'appelant."""
    if not isinstance(data, dict):
        return []
    features = data.get("features")
    if not isinstance(features, list):
        return []

    candidates = []
    for feat in features:
        if not isinstance(feat, dict):
            continue
        geom = feat.get("geometry")
        if not isinstance(geom, dict):
            continue
        coords = geom.get("coordinates")
        if not (isinstance(coords, list) and len(coords) >= 2):
            continue
        lon, lat = coords[0], coords[1]
        if not isinstance(lon, (int, float)) or not isinstance(lat, (int, float)):
            continue
        props = feat.get("properties") if isinstance(feat.get("properties"), dict) else {}
        candidates.append({
            "label": props.get("label"),
            "latitude": lat,
            "longitude": lon,
            "score": props.get("score"),
            "city": props.get("city"),
            "context": props.get("context"),
        })

    candidates.sort(key=lambda c: c["score"] if isinstance(c["score"], (int, float)) else -1, reverse=True)
    return candidates


def geocode_query(query, limit=5):
    """Interroge le service de géocodage externe configuré
    (GEOCODE_PROVIDER_URL). Dégradé systématique (liste vide + message
    d'erreur explicite) sur toute panne/quota dépassé/réponse
    inattendue — jamais bloquant pour l'appelant. Un 429 (quota des 50
    req/s/IP dépassé côté service, avec un header Retry-After) est
    remonté tel quel dans le message d'erreur plutôt que ré-essayé en
    boucle depuis le serveur — un seul appel utilisateur ne devrait de
    toute façon jamais s'en approcher."""
    query = (query or "").strip()
    if not query:
        return {"candidates": [], "error": None}

    # Traces DEBUG (livraison #225, audit rétroactif) -- jamais
    # l'URL complète (même raisonnement que geoip_lookup ci-dessus :
    # GEOCODE_PROVIDER_URL surchargeable via .env).
    app.logger.debug("geocode_query : démarré pour la requête '%s' (limit=%s)", query, limit)
    start = time.monotonic()
    url = GEOCODE_PROVIDER_URL.format(q=quote_plus(query), limit=limit, index=GEOCODE_INDEX)
    try:
        response = requests.get(url, timeout=GEOCODE_TIMEOUT_SECONDS)
    except requests.RequestException as exc:
        elapsed_ms = int((time.monotonic() - start) * 1000)
        app.logger.debug("geocode_query : ÉCHEC réseau après %d ms -- %s", elapsed_ms, exc)
        return {"candidates": [], "error": f"service de géocodage injoignable : {exc}"}

    elapsed_ms = int((time.monotonic() - start) * 1000)
    if response.status_code == 429:
        retry_after = response.headers.get("Retry-After")
        suffix = f" (réessayer dans {retry_after}s)" if retry_after else ""
        app.logger.debug("geocode_query : ÉCHEC -- quota atteint (429) après %d ms", elapsed_ms)
        return {"candidates": [], "error": f"limite d'appels du service de géocodage atteinte{suffix}"}
    if not response.ok:
        app.logger.debug("geocode_query : ÉCHEC HTTP %s après %d ms", response.status_code, elapsed_ms)
        return {"candidates": [], "error": f"le service de géocodage a répondu {response.status_code}"}

    try:
        data = response.json()
    except ValueError:
        app.logger.debug("geocode_query : ÉCHEC -- réponse non-JSON après %d ms", elapsed_ms)
        return {"candidates": [], "error": "réponse du service de géocodage illisible (pas du JSON)"}

    candidates = parse_geocode_response(data)
    app.logger.debug("geocode_query : succès en %d ms -- %d candidat(s)", elapsed_ms, len(candidates))
    return {"candidates": candidates, "error": None}


# ------------------------------------------------------------------
# Centroïde de commune par code postal — même esprit que geocode_query
# (dégradé systématique, jamais d'exception non gérée), fonction de
# parsing gardée PURE et séparée de l'appel réseau.
# ------------------------------------------------------------------

def parse_commune_response(data):
    """data : réponse JSON brute de l'API Découpage Administratif
    (liste de communes). Un code postal français peut couvrir
    PLUSIEURS communes (ex. petites communes rurales partageant le
    bureau de poste d'un bourg voisin) — retient celle de plus grande
    population, meilleure approximation par défaut de "la ville
    principale de ce code postal" sans intervention humaine. Ne lève
    jamais : toute forme inattendue -> None."""
    if not isinstance(data, list) or not data:
        return None

    def population_of(commune):
        pop = commune.get("population") if isinstance(commune, dict) else None
        return pop if isinstance(pop, (int, float)) else -1

    best = max(data, key=population_of)
    if not isinstance(best, dict):
        return None

    centre = best.get("centre")
    coords = centre.get("coordinates") if isinstance(centre, dict) else None
    if not (isinstance(coords, list) and len(coords) >= 2):
        return None
    lon, lat = coords[0], coords[1]
    if not isinstance(lon, (int, float)) or not isinstance(lat, (int, float)):
        return None

    return {"nom": best.get("nom"), "codeInsee": best.get("code"), "latitude": lat, "longitude": lon}


def commune_centroid_for_postal_code(code_postal):
    """Interroge l'API Découpage Administratif pour un code postal
    donné. Dégradé systématique (commune=None + message d'erreur) sur
    toute panne/réponse inattendue — jamais bloquant pour l'appelant.
    Un code postal qui ne correspond à aucune commune connue (faux
    positif d'extraction, ou DOM-TOM/Corse aux formats particuliers)
    n'est PAS une erreur : commune=None, error=None."""
    code_postal = (code_postal or "").strip()
    if not code_postal:
        return {"commune": None, "error": None}

    app.logger.debug("commune_centroid_for_postal_code : démarré pour le code postal %s", code_postal)
    start = time.monotonic()
    url = COMMUNE_PROVIDER_URL.format(code_postal=quote_plus(code_postal))
    try:
        response = requests.get(url, timeout=COMMUNE_TIMEOUT_SECONDS)
    except requests.RequestException as exc:
        elapsed_ms = int((time.monotonic() - start) * 1000)
        app.logger.debug("commune_centroid_for_postal_code : ÉCHEC réseau après %d ms -- %s", elapsed_ms, exc)
        return {"commune": None, "error": f"service de découpage administratif injoignable : {exc}"}

    elapsed_ms = int((time.monotonic() - start) * 1000)
    if not response.ok:
        app.logger.debug("commune_centroid_for_postal_code : ÉCHEC HTTP %s après %d ms", response.status_code, elapsed_ms)
        return {"commune": None, "error": f"le service a répondu {response.status_code}"}

    try:
        data = response.json()
    except ValueError:
        app.logger.debug("commune_centroid_for_postal_code : ÉCHEC -- réponse non-JSON après %d ms", elapsed_ms)
        return {"commune": None, "error": "réponse illisible (pas du JSON)"}

    app.logger.debug("commune_centroid_for_postal_code : succès en %d ms", elapsed_ms)
    return {"commune": parse_commune_response(data), "error": None}


@app.route("/geocode", methods=["GET"])
def geocode():
    """EXCEPTION réseau délibérée : contrairement au reste de cette
    API, cette route fait un appel HTTP sortant vers un service
    externe configurable (BAN/Géoplateforme par défaut, voir
    GEOCODE_PROVIDER_URL en tête de fichier). Même esprit que
    geoip_lookup pour les IP publiques : ne renvoie jamais une
    exception brute, toujours un JSON exploitable même en cas
    d'échec. Ne modifie jamais `geolocations` elle-même — c'est
    upsert_geolocation() (existant) qui écrit, après confirmation
    humaine côté frontend."""
    query = request.args.get("q", "").strip()
    if not query:
        return jsonify({"error": "paramètre 'q' requis"}), 400
    limit = request.args.get("limit", type=int)
    limit = 5 if limit is None else limit
    limit = max(1, min(limit, 20))  # borne raisonnable, indépendante de ce que le client demande

    result = geocode_query(query, limit)
    if result["error"] and not result["candidates"]:
        return jsonify(result), 502
    return jsonify(result), 200


@app.route("/commune_centroid", methods=["GET"])
def commune_centroid():
    """EXCEPTION réseau délibérée, même esprit que /geocode : appel
    sortant vers l'API Découpage Administratif (geo.api.gouv.fr).
    Utilisée pour la colonne "Position" de l'onglet Fusion IP/MAC —
    géocodage automatique via un code postal extrait d'un nom d'hôte,
    jamais via son contenu réel. Ne modifie jamais `geolocations`
    elle-même — c'est upsert_geolocation() (existant) qui écrit."""
    code_postal = request.args.get("code_postal", "").strip()
    if not code_postal:
        return jsonify({"error": "paramètre 'code_postal' requis"}), 400

    result = commune_centroid_for_postal_code(code_postal)
    if result["error"]:
        return jsonify(result), 502
    return jsonify(result), 200


@app.route("/geolocations", methods=["GET"])
def list_geolocations():
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT localisation, latitude, longitude, parent_localisation, location_type, created_at, updated_at "
            "FROM geolocations ORDER BY localisation"
        )
        rows = cur.fetchall()
        return jsonify(
            {
                "geolocations": [
                    {
                        "localisation": loc,
                        "latitude": lat,
                        "longitude": lon,
                        "parent_localisation": parent,
                        "location_type": loc_type,
                        "created_at": created_at,
                        "updated_at": updated_at,
                        "mapped": lat is not None and lon is not None,
                        "is_default": loc == DEFAULT_LOCATION_KEY,
                    }
                    for loc, lat, lon, parent, loc_type, created_at, updated_at in rows
                ]
            }
        ), 200
    finally:
        conn.close()


@app.route("/geolocations", methods=["POST"])
def upsert_geolocation():
    """Crée ou met à jour les coordonnées (et la hiérarchie) d'un
    chemin Localisation. parent_localisation/location_type utilisent
    COALESCE côté mise à jour -- ne pas les fournir dans le corps de
    la requête PRÉSERVE la hiérarchie déjà en place (ex. mise à jour
    des seules coordonnées, sans avoir à ressaisir la hiérarchie à
    chaque fois), jamais un écrasement silencieux vers NULL.

    Protégée par rights-api (#317)."""
    body = request.get_json(silent=True) or {}
    allowed, error = _check_manage_right(body)
    if not allowed:
        return jsonify({"error": error}), 403
    localisation = body.get("localisation")
    latitude = body.get("latitude")
    longitude = body.get("longitude")
    parent_localisation = body.get("parent_localisation")
    location_type = body.get("location_type")

    if not localisation:
        return jsonify({"error": "'localisation' requis"}), 400

    now = datetime.now(timezone.utc).isoformat()
    conn = get_write_connection()
    try:
        cur = conn.cursor()
        if DB_BACKEND == "postgres":
            cur.execute(
                f"""
                INSERT INTO geolocations (localisation, latitude, longitude, parent_localisation, location_type, created_at, updated_at)
                VALUES ({PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER})
                ON CONFLICT (localisation) DO UPDATE
                SET latitude = EXCLUDED.latitude, longitude = EXCLUDED.longitude,
                    parent_localisation = COALESCE(EXCLUDED.parent_localisation, geolocations.parent_localisation),
                    location_type = COALESCE(EXCLUDED.location_type, geolocations.location_type),
                    updated_at = EXCLUDED.updated_at
                """,
                [localisation, latitude, longitude, parent_localisation, location_type, now, now],
            )
        else:
            cur.execute(
                f"""
                INSERT INTO geolocations (localisation, latitude, longitude, parent_localisation, location_type, created_at, updated_at)
                VALUES ({PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER})
                ON CONFLICT (localisation) DO UPDATE
                SET latitude = excluded.latitude, longitude = excluded.longitude,
                    parent_localisation = COALESCE(excluded.parent_localisation, geolocations.parent_localisation),
                    location_type = COALESCE(excluded.location_type, geolocations.location_type),
                    updated_at = excluded.updated_at
                """,
                [localisation, latitude, longitude, parent_localisation, location_type, now, now],
            )
        conn.commit()
        return jsonify({"status": "ok", "localisation": localisation}), 200
    finally:
        conn.close()


@app.route("/geolocations", methods=["DELETE"])
def delete_geolocation():
    """Protégée par rights-api (#317)."""
    body = request.get_json(silent=True) or {}
    allowed, error = _check_manage_right(body)
    if not allowed:
        return jsonify({"error": error}), 403
    localisation = request.args.get("localisation")
    if not localisation:
        return jsonify({"error": "paramètre 'localisation' requis"}), 400
    if localisation == DEFAULT_LOCATION_KEY:
        return jsonify({"error": "la position par défaut ne peut pas être supprimée, seulement modifiée"}), 400

    conn = get_write_connection()
    try:
        cur = conn.cursor()
        cur.execute(f"DELETE FROM geolocations WHERE localisation = {PLACEHOLDER}", [localisation])
        conn.commit()
        return jsonify({"status": "ok", "deleted": localisation}), 200
    finally:
        conn.close()


@app.route("/geolocations/scan", methods=["POST"])
def scan_geolocations():
    """
    Parcourt les événements d'un type et détecte les chemins
    Localisation jamais vus — les ajoute comme entrées "en attente"
    (latitude/longitude NULL), sans toucher à celles déjà connues
    (mappées ou non). Appelé automatiquement par les loaders après
    chargement, et disponible ici pour un re-scan à la demande.

    Protégée par rights-api (#317).
    """
    body = request.get_json(silent=True) or {}
    allowed, error = _check_manage_right(body)
    if not allowed:
        return jsonify({"error": error}), 403
    type_name = request.args.get("type")
    if not type_name:
        return jsonify({"error": "paramètre 'type' requis"}), 400

    conn = get_write_connection()
    try:
        cur = conn.cursor()
        cur.execute(f"SELECT data FROM events WHERE type = {PLACEHOLDER}", [type_name])
        rows = cur.fetchall()

        found = set()
        for (data,) in rows:
            if not data:
                continue
            try:
                parsed = json.loads(data)
            except (TypeError, ValueError):
                continue
            loc = parsed.get("localisation") if isinstance(parsed, dict) else None
            if loc:
                found.add(loc)

        cur.execute("SELECT localisation FROM geolocations")
        existing = {row[0] for row in cur.fetchall()}
        new_locations = found - existing

        now = datetime.now(timezone.utc).isoformat()
        for loc in new_locations:
            cur.execute(
                f"INSERT INTO geolocations (localisation, latitude, longitude, created_at, updated_at) "
                f"VALUES ({PLACEHOLDER}, NULL, NULL, {PLACEHOLDER}, {PLACEHOLDER})",
                [loc, now, now],
            )
        conn.commit()

        return jsonify({"type": type_name, "scanned_events": len(rows), "new_locations": sorted(new_locations), "new_count": len(new_locations)}), 200
    finally:
        conn.close()


@app.route("/geolocations/register_ips", methods=["POST"])
def register_ips():
    """
    Enregistre une liste d'adresses IP — venant d'AUTRES modules
    (IPAM, Zenoss, Fusion IP/MAC), toujours appelés directement par le
    frontend, jamais un import ici — dans le système de
    géolocalisation déjà existant. Généralisation du mécanisme déjà
    en place pour les équipements pixel-grid : la table `geolocations`
    n'a jamais été structurellement liée à pixel-grid, seulement
    alimentée par lui jusqu'ici — une IP est juste une autre sorte de
    clé de `localisation`, aucun changement de schéma nécessaire.

    Ne touche JAMAIS une entrée déjà connue (mappée ou non, manuelle
    ou auto-résolue) — même principe que scan_geolocations().
      - IP privée -> entrée "en attente" (lat/lon NULL), à placer à la
        main comme aujourd'hui pour un équipement pixel-grid. Ce n'est
        PAS une limite technique contournable : une IP privée n'a pas
        de position géographique publique par définition.
      - IP publique -> tentative de résolution via geoip_lookup() ;
        succès -> coordonnées déjà renseignées ; échec (service
        indisponible, IP non résolue) -> "en attente" comme une IP
        privée, jamais bloquant pour le reste du lot.

    Protégée par rights-api (#317).
    """
    body = request.get_json(silent=True) or {}
    allowed, error = _check_manage_right(body)
    if not allowed:
        return jsonify({"error": error}), 403
    ips = body.get("ips")
    if not isinstance(ips, list) or not ips:
        return jsonify({"error": "'ips' (liste non vide) requis"}), 400

    conn = get_write_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT localisation FROM geolocations")
        existing = {row[0] for row in cur.fetchall()}

        now = datetime.now(timezone.utc).isoformat()
        summary = {"alreadyKnown": 0, "invalid": 0, "privatePending": 0, "publicResolved": 0, "publicPending": 0}
        first_public_lookup = True

        for ip in ips:
            if ip in existing:
                summary["alreadyKnown"] += 1
                continue
            kind = classify_ip(ip)
            if kind == "invalid":
                summary["invalid"] += 1
                continue

            lat, lon = None, None
            if kind == "public":
                if not first_public_lookup:
                    time.sleep(GEOIP_MIN_INTERVAL_SECONDS)
                first_public_lookup = False
                result = geoip_lookup(ip)
                if result:
                    lat, lon = result["latitude"], result["longitude"]
                    summary["publicResolved"] += 1
                else:
                    summary["publicPending"] += 1
            else:
                summary["privatePending"] += 1

            cur.execute(
                f"INSERT INTO geolocations (localisation, latitude, longitude, created_at, updated_at) "
                f"VALUES ({PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER})",
                [ip, lat, lon, now, now],
            )
            existing.add(ip)  # une même IP soumise deux fois dans le même lot ne doit compter qu'une fois

        conn.commit()
        return jsonify({"status": "ok", **summary}), 200
    finally:
        conn.close()


@app.route("/devices", methods=["GET"])
def list_devices():
    """Liste les équipements (`nom` distincts) d'un type, avec leur nombre de points."""
    type_name = request.args.get("type")
    if not type_name:
        return jsonify({"error": "paramètre 'type' requis"}), 400

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            f"SELECT nom, COUNT(*) AS total, MIN(ts) AS min_ts, MAX(ts) AS max_ts "
            f"FROM events WHERE type = {PLACEHOLDER} GROUP BY nom ORDER BY nom",
            [type_name],
        )
        rows = cur.fetchall()
        return jsonify(
            {
                "type": type_name,
                "devices": [
                    {"nom": nom, "total": total, "min_ts": min_ts, "max_ts": max_ts}
                    for nom, total, min_ts, max_ts in rows
                ],
            }
        ), 200
    finally:
        conn.close()


def pair_incidents(events):
    """
    Apparie automatiquement les couples début/fin : un événement
    valeur=1 (alerte active) ouvre un incident, le prochain valeur=0
    (résolution) pour ce même équipement le referme. valeur=-1 (aucune
    donnée) n'intervient pas dans l'appariement, juste dans la série
    brute. Un incident sans fin trouvée est marqué "en cours".
    """
    incidents = []
    open_incident = None

    for event in events:
        if event["valeur"] == 1:
            if open_incident is None:
                open_incident = {
                    "start_ts": event["ts"],
                    "start_iso": event["iso"],
                    "end_ts": None,
                    "end_iso": None,
                    "duration_seconds": None,
                    "ongoing": True,
                    "data": event["data"],
                }
            # Un second valeur=1 alors qu'un incident est déjà ouvert est
            # ignoré ici (rare, signalerait un chevauchement) — reste
            # visible dans la série brute renvoyée à côté.
        elif event["valeur"] == 0 and open_incident is not None:
            open_incident["end_ts"] = event["ts"]
            open_incident["end_iso"] = event["iso"]
            open_incident["duration_seconds"] = event["ts"] - open_incident["start_ts"]
            open_incident["ongoing"] = False
            incidents.append(open_incident)
            open_incident = None

    if open_incident is not None:
        incidents.append(open_incident)

    return incidents


@app.route("/timeline", methods=["GET"])
def timeline():
    """
    Timeline d'un équipement précis. Pour les types integer_enum :
    événements bruts + incidents appariés (début/fin). Pour les types
    continuous : événements bruts seulement (série à tracer telle
    quelle, pas de notion d'incident).
    """
    type_name = request.args.get("type")
    nom = request.args.get("nom")
    if not type_name or not nom:
        return jsonify({"error": "paramètres 'type' et 'nom' requis"}), 400

    conn = get_connection()
    try:
        cur = conn.cursor()
        type_meta = get_type_meta(cur, type_name)
        if type_meta is None:
            return jsonify({"error": f"type inconnu : {type_name}"}), 404

        cur.execute(
            f"SELECT ts, valeur, data FROM events WHERE type = {PLACEHOLDER} AND nom = {PLACEHOLDER} ORDER BY ts",
            [type_name, nom],
        )
        rows = cur.fetchall()

        events = []
        for ts, valeur, data in rows:
            try:
                parsed_data = json.loads(data) if data else None
            except (TypeError, ValueError):
                parsed_data = None
            events.append(
                {"ts": ts, "iso": datetime.fromtimestamp(ts, tz=timezone.utc).isoformat(), "valeur": valeur, "data": parsed_data}
            )

        kind = type_meta["kind"]
        incidents = pair_incidents(events) if kind == "integer_enum" else []

        return jsonify(
            {
                "type": type_name,
                "nom": nom,
                "kind": kind,
                "events": events,
                "incidents": incidents,
            }
        ), 200
    finally:
        conn.close()


@app.route("/events", methods=["GET"])
def list_events():
    """
    Liste les événements bruts d'une plage — utilisé par la colonne de
    détail : quand on clique une cellule de la mosaïque, on montre les
    points individuels qui la composent, pas juste l'agrégat.
    """
    type_name = request.args.get("type")
    start_iso = request.args.get("start")
    end_iso = request.args.get("end")
    limit = min(int(request.args.get("limit", 200)), 5000)

    if not all([type_name, start_iso, end_iso]):
        return jsonify({"error": "paramètres 'type', 'start', 'end' requis"}), 400

    try:
        start_epoch = int(datetime.fromisoformat(start_iso.replace("Z", "+00:00")).timestamp())
        end_epoch = int(datetime.fromisoformat(end_iso.replace("Z", "+00:00")).timestamp())
    except ValueError:
        return jsonify({"error": "start/end doivent être des dates ISO 8601 valides"}), 400

    conn = get_connection()
    try:
        cur = conn.cursor()
        query = f"""
            SELECT ts, valeur, nom, data FROM events
            WHERE type = {PLACEHOLDER} AND ts >= {PLACEHOLDER} AND ts < {PLACEHOLDER}
            ORDER BY ts
            LIMIT {PLACEHOLDER}
        """
        cur.execute(query, [type_name, start_epoch, end_epoch, limit])
        rows = cur.fetchall()

        events = []
        for ts, valeur, nom, data in rows:
            try:
                parsed_data = json.loads(data) if data else None
            except (TypeError, ValueError):
                parsed_data = None
            events.append(
                {
                    "ts": ts,
                    "iso": datetime.fromtimestamp(ts, tz=timezone.utc).isoformat(),
                    "valeur": valeur,
                    "nom": nom,
                    "data": parsed_data,
                }
            )

        return jsonify({"type": type_name, "start": start_iso, "end": end_iso, "events": events, "truncated": len(events) >= limit}), 200
    finally:
        conn.close()


@app.route("/aggregate_range", methods=["GET"])
def aggregate_range():
    """
    Agrégation en mosaïque dense sur une plage arbitraire (pas calée sur
    un calendrier), pour la grille pixel-grid — chaque cellule garde son
    contexte complet (pas de fusion "tous les mois de mars" comme pour
    /aggregate). Plafonnée à MAX_RANGE_CELLS pour éviter une réponse
    disproportionnée.
    """
    type_name = request.args.get("type")
    level = request.args.get("level")
    start_iso = request.args.get("start")
    end_iso = request.args.get("end")

    if not all([type_name, level, start_iso, end_iso]):
        return jsonify({"error": "paramètres 'type', 'level', 'start', 'end' requis"}), 400
    if level not in LEVELS:
        return jsonify({"error": f"level doit être l'un de {LEVELS}"}), 400

    try:
        start_dt = datetime.fromisoformat(start_iso.replace("Z", "+00:00"))
        end_dt = datetime.fromisoformat(end_iso.replace("Z", "+00:00"))
    except ValueError:
        return jsonify({"error": "start/end doivent être des dates ISO 8601 valides"}), 400

    start_epoch, end_epoch = int(start_dt.timestamp()), int(end_dt.timestamp())
    if end_epoch <= start_epoch:
        return jsonify({"error": "'end' doit être postérieur à 'start'"}), 400

    estimated_cells = (end_epoch - start_epoch) / _UNIT_SECONDS[level]
    if estimated_cells > MAX_RANGE_CELLS:
        return jsonify(
            {
                "error": (
                    f"Plage trop large pour level='{level}' (~{int(estimated_cells)} cellules "
                    f"estimées, max {MAX_RANGE_CELLS}). Réduis la plage ou choisis un niveau "
                    "plus grossier."
                )
            }
        ), 400

    conn = get_connection()
    try:
        cur = conn.cursor()
        type_meta = get_type_meta(cur, type_name)
        if type_meta is None:
            return jsonify({"error": f"type inconnu : {type_name}"}), 404
        kind = type_meta["kind"]

        group_expr = bucket_expr_range(level)
        where_sql = f"type = {PLACEHOLDER} AND ts >= {PLACEHOLDER} AND ts < {PLACEHOLDER}"
        params = [type_name, start_epoch, end_epoch]
        # Même filtre optionnel que /aggregate (livraison #371) --
        # voir ce commentaire pour le détail complet.
        nom_filter = request.args.get("nom")
        if nom_filter:
            where_sql += f" AND nom = {PLACEHOLDER}"
            params.append(nom_filter)

        if kind == "integer_enum":
            seuil_attention = type_meta["config"].get("seuil_taux_attention", 0.03)
            seuil_alerte = type_meta["config"].get("seuil_taux_alerte", 0.15)
            query = f"""
                SELECT {group_expr} AS bucket,
                       SUM(CASE WHEN valeur = 1 THEN 1 ELSE 0 END) AS error_count,
                       SUM(CASE WHEN valeur = -1 THEN 1 ELSE 0 END) AS none_count,
                       COUNT(*) AS total
                FROM events
                WHERE {where_sql}
                GROUP BY bucket
                ORDER BY bucket
            """
            cur.execute(query, params)
            rows = cur.fetchall()
            buckets = [
                {
                    "key": bucket,
                    "start": parse_bucket_key(level, bucket).isoformat(),
                    "color": color_for_enum_bucket(error_count, none_count, total, seuil_attention, seuil_alerte),
                    "value": error_count,
                    "total": total,
                }
                for bucket, error_count, none_count, total in rows
            ]
        else:  # continuous
            seuil_bas = type_meta["config"]["seuil_bas"]
            seuil_moyen = type_meta["config"]["seuil_moyen"]
            query = f"""
                SELECT {group_expr} AS bucket,
                       AVG(valeur) AS avg_value,
                       COUNT(*) AS total
                FROM events
                WHERE {where_sql}
                GROUP BY bucket
                ORDER BY bucket
            """
            cur.execute(query, params)
            rows = cur.fetchall()
            buckets = [
                {
                    "key": bucket,
                    "start": parse_bucket_key(level, bucket).isoformat(),
                    "color": color_for_continuous_bucket(avg_value, seuil_bas, seuil_moyen),
                    "value": round(avg_value, 1) if avg_value is not None else None,
                    "total": total,
                }
                for bucket, avg_value, total in rows
            ]

        return jsonify(
            {
                "type": type_name, "level": level, "start": start_iso, "end": end_iso,
                "kind": kind, "buckets": buckets, "backend": DB_BACKEND, "nom": nom_filter,
            }
        ), 200
    finally:
        conn.close()


@app.route("/aggregate", methods=["GET"])
def aggregate():
    type_name = request.args.get("type")
    level = request.args.get("level")
    period = request.args.get("period")  # absent pour level=year
    # Filtre optionnel par utilisateur/équipement réel (livraison
    # #371, backlog item 10 -- "filtrage utilisateur réel dans
    # l'interface", resté hors portée jusqu'ici). Chaque export
    # (#218-219) écrit déjà le VRAI nom (technicien, personne ayant
    # lié un document) dans cette même colonne `nom` que les exports
    # "équipement" -- même mécanisme de filtrage, sans distinction
    # technique entre les deux usages.
    nom_filter = request.args.get("nom")

    if not type_name or not level:
        return jsonify({"error": "paramètres 'type' et 'level' requis"}), 400
    if level not in LEVELS:
        return jsonify({"error": f"level doit être l'un de {LEVELS}"}), 400
    if level != "year" and not period:
        return jsonify({"error": "paramètre 'period' requis pour ce level"}), 400

    conn = get_connection()
    try:
        cur = conn.cursor()
        type_meta = get_type_meta(cur, type_name)
        if type_meta is None:
            return jsonify({"error": f"type inconnu : {type_name}"}), 404
        kind = type_meta["kind"]

        try:
            start_epoch, end_epoch, group_expr = parse_period_bounds(level, period)
        except (ValueError, IndexError):
            return jsonify({"error": f"period invalide pour level={level} : '{period}'"}), 400

        where_clauses = [f"type = {PLACEHOLDER}"]
        params = [type_name]
        if start_epoch is not None:
            where_clauses.append(f"ts >= {PLACEHOLDER} AND ts < {PLACEHOLDER}")
            params.extend([start_epoch, end_epoch])
        if nom_filter:
            where_clauses.append(f"nom = {PLACEHOLDER}")
            params.append(nom_filter)
        where_sql = " AND ".join(where_clauses)

        if kind == "integer_enum":
            seuil_attention = type_meta["config"].get("seuil_taux_attention", 0.03)
            seuil_alerte = type_meta["config"].get("seuil_taux_alerte", 0.15)
            query = f"""
                SELECT {group_expr} AS bucket,
                       SUM(CASE WHEN valeur = 1 THEN 1 ELSE 0 END) AS error_count,
                       SUM(CASE WHEN valeur = -1 THEN 1 ELSE 0 END) AS none_count,
                       COUNT(*) AS total
                FROM events
                WHERE {where_sql}
                GROUP BY bucket
                ORDER BY bucket
            """
            cur.execute(query, params)
            rows = cur.fetchall()
            buckets = [
                {
                    "key": int(bucket),
                    "color": color_for_enum_bucket(error_count, none_count, total, seuil_attention, seuil_alerte),
                    "value": error_count,
                    "total": total,
                }
                for bucket, error_count, none_count, total in rows
            ]

        else:  # continuous
            seuil_bas = type_meta["config"]["seuil_bas"]
            seuil_moyen = type_meta["config"]["seuil_moyen"]
            query = f"""
                SELECT {group_expr} AS bucket,
                       AVG(valeur) AS avg_value,
                       COUNT(*) AS total
                FROM events
                WHERE {where_sql}
                GROUP BY bucket
                ORDER BY bucket
            """
            cur.execute(query, params)
            rows = cur.fetchall()
            buckets = [
                {
                    "key": int(bucket),
                    "color": color_for_continuous_bucket(avg_value, seuil_bas, seuil_moyen),
                    "value": round(avg_value, 1) if avg_value is not None else None,
                    "total": total,
                }
                for bucket, avg_value, total in rows
            ]

        return jsonify(
            {"type": type_name, "level": level, "period": period, "kind": kind, "buckets": buckets, "backend": DB_BACKEND, "nom": nom_filter}
        ), 200
    finally:
        conn.close()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
