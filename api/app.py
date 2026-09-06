"""
API de centralisation — point d'écriture unique (Memcached + fichiers),
point de découverte des fichiers du dossier data, et analyse calendaire
(recherche de dates/timestamps + filtre par mots-clés).

Trois façons pour une source d'exister :
- POST /ingest/<source>  : chemin de confiance, auto-enregistré immédiatement.
- Dépôt manuel d'un fichier dans le dossier data : détecté au scan, mais
  proposé (pas auto-activé) tant qu'il n'est pas confirmé via
  POST /sources/<source>/register.
"""
import calendar
import glob
import json
import logging
import os
import re
import time
from datetime import datetime, timezone

import requests
from flask import Flask, jsonify, request
from flask_cors import CORS
from pymemcache.client.base import Client as MemcacheClient
from pymemcache.exceptions import MemcacheError
# Import DÉFENSIF -- version_endpoint.py n'existe que dans le
# conteneur Docker réel (copié depuis shared/ au build, comme
# theme.css/preferences.js pour les fronts). Sans ce garde, tout
# test qui importe ce module directement (sans passer par le build
# complet) casserait au chargement -- bug réel rencontré : plusieurs
# harnais de test existants, sans rapport avec /version, important
# app.py directement.
try:
    from version_endpoint import register_version_route
except ImportError:
    register_version_route = None

app = Flask(__name__)
# En dev, le frontend (Vite, autre port) appelle l'API en cross-origin.
# À restreindre à l'origine réelle du frontend une fois en prod.
CORS(app)
if register_version_route:
    register_version_route(app, "api")

_log = logging.getLogger("central_api_app")

# Branchement rights-api -- livraison #320, item 38 du backlog.
# DÉCOUVERTE CRITIQUE avant d'agir : POST /ingest/<source> (le
# "chemin de confiance" documenté en tête de fichier) est appelé PAR
# D'AUTRES SERVICES en conteneur-à-conteneur (imap-client-api,
# pixel-grid/bridge, pipeline/main.py, connectors/zenoss_legacy) --
# AUCUN de ces appelants n'a de contexte utilisateur/groupes Keycloak
# à transmettre. Le garder aurait cassé ces pipelines automatisés dès
# l'activation de rights-api -- DÉLIBÉRÉMENT JAMAIS gardé.
# Gardé UNIQUEMENT sur les 4 routes de gestion des sources
# (from-selection, register, delete, restore) -- confirmé qu'aucun
# autre service Python ni aucun composant du hub ne les appelle
# actuellement (comme revoke_collection_access/reset_user en #308) --
# pas un risque exploité aujourd'hui, mais un vrai trou pour un appel
# API direct.
RIGHTS_API_URL = os.environ.get("RIGHTS_API_URL", "").rstrip("/") or None


def _check_manage_right(body):
    """Même motif FAIL CLOSED que les branchements précédents
    (#289-292, #308-319) -- jamais fail-open, y compris pour
    admin_hub si rights-api est injoignable."""
    if not RIGHTS_API_URL:
        return True, None
    groups = body.get("groups") or []
    try:
        resp = requests.post(
            f"{RIGHTS_API_URL}/check",
            json={"groups": groups, "resource_type": "api", "resource_id": None, "action": "manage"},
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
    return allowed, None if allowed else "droit 'manage' sur api requis (groupe admin_hub, ou un octroi explicite)"

DATA_DIR = os.environ.get("DATA_DIR", "/app/data")
MEMCACHED_HOST = os.environ.get("MEMCACHED_HOST", "memcached")
MEMCACHED_PORT = int(os.environ.get("MEMCACHED_PORT", "11211"))
CACHE_TTL_SECONDS = int(os.environ.get("CACHE_TTL_SECONDS", "300"))
REGISTRY_PATH = os.path.join(DATA_DIR, "_registry.json")

# Garde-fou différentiel sur /ingest — préparation du futur mode push
# (services/serveurs -> supervision-si) annoncé mais pas encore
# construit côté émetteur : protège dès maintenant ce même endpoint
# contre tout appelant qui enverrait des mises à jour redondantes ou
# trop rapprochées pour une même source (double-clic, script en boucle,
# et demain un service qui pousserait en continu). Le pipeline actuel
# pousse toutes les 30s par défaut (PUSH_INTERVAL_SECONDS) — largement
# au-dessus de ce seuil, aucun impact sur son fonctionnement existant.
DIFF_WATCHDOG_MIN_INTERVAL_MS = int(os.environ.get("DIFF_WATCHDOG_MIN_INTERVAL_MS", "2000"))

os.makedirs(DATA_DIR, exist_ok=True)


def get_memcache_client():
    """
    Client Memcached recréé à chaque appel : évite de garder une connexion
    morte si Memcached redémarre. Le coût de reconnexion est négligeable
    ici vu le volume attendu.
    """
    return MemcacheClient(
        (MEMCACHED_HOST, MEMCACHED_PORT),
        connect_timeout=1,
        timeout=1,
    )


def file_path_for(source: str) -> str:
    safe_source = source.replace("/", "_")
    return os.path.join(DATA_DIR, f"{safe_source}.json")


# ============================================================
# Registre des sources
# ============================================================

def load_registry() -> dict:
    if not os.path.exists(REGISTRY_PATH):
        return {}
    try:
        with open(REGISTRY_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        app.logger.warning("Registre illisible, repart d'un registre vide")
        return {}


def save_registry(registry: dict) -> None:
    with open(REGISTRY_PATH, "w", encoding="utf-8") as f:
        json.dump(registry, f, ensure_ascii=False)


def mark_registered(source: str, mtime: float) -> None:
    # L'origine (external/selection) est PRÉSERVÉE à travers une
    # promotion en source enregistrée -- un élément versé depuis la
    # bannette d'interaction puis confirmé par la personne reste tracé
    # comme tel, pour l'historique, même une fois pérenne.
    registry = load_registry()
    existing = registry.get(source, {})
    entry = {"registered": True, "last_seen_mtime": mtime}
    if "origin" in existing:
        entry["origin"] = existing["origin"]
    registry[source] = entry
    save_registry(registry)


def mark_proposed(source: str, mtime: float, origin: str = "external") -> None:
    """Enregistre une source comme PROPOSÉE (pas encore confirmée) en
    traçant son origine dès la création -- nécessaire pour la bannette
    d'interaction (origin="selection") : contrairement à un simple
    dépôt manuel de fichier (qui n'a besoin de rien tant que
    scan_sources() n'a pas tourné et créé l'entrée implicitement),
    une source versée depuis une sélection doit exister dans le
    registre dès son écriture pour porter cette origine."""
    registry = load_registry()
    registry[source] = {"registered": False, "last_seen_mtime": mtime, "origin": origin}
    save_registry(registry)


def mark_deleted(source: str) -> None:
    """
    Suppression DOUCE : le fichier de données reste intact sur disque,
    seul le registre change (source retirée de la liste active).
    Permet une restauration triviale — voir mark_restored().
    """
    registry = load_registry()
    entry = registry.get(source, {})
    entry["registered"] = False
    entry["deleted"] = True
    entry["deleted_at"] = datetime.now(timezone.utc).isoformat()
    registry[source] = entry
    save_registry(registry)


def mark_restored(source: str) -> None:
    registry = load_registry()
    entry = registry.get(source, {})
    entry["registered"] = True
    entry["deleted"] = False
    entry.pop("deleted_at", None)
    path = file_path_for(source)
    if os.path.exists(path):
        entry["last_seen_mtime"] = os.path.getmtime(path)
    registry[source] = entry
    save_registry(registry)


# ============================================================
# Lecture / écriture des données d'une source
# ============================================================

# ============================================================
# Garde-fou différentiel (préparation mode push — voir config ci-dessus)
# ============================================================

def fingerprint_payload(payload):
    """Empreinte simple et stable d'un JSON — pas cryptographique, sert
    seulement à détecter un changement de contenu entre deux appels
    (sort_keys=True : l'ordre des clés ne doit jamais faire croire à un
    changement)."""
    text = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    h = 0
    for ch in text:
        h = (h * 31 + ord(ch)) & 0xFFFFFFFF
    return f"{len(text)}:{h}"


def check_diff_watchdog(source, payload, min_interval_ms=None):
    """
    Décide si un /ingest doit réellement écrire, en comparant une
    empreinte du contenu au dernier état connu ET en imposant un
    intervalle minimal entre deux écritures RÉELLES pour une même
    source — même si le contenu change à chaque appel (anti-rafale).

    Retourne (verdict, retry_after_ms) :
      - ("ok", 0)        : contenu changé, assez de temps écoulé -> écrire.
      - ("unchanged", 0) : contenu identique au dernier écrit -> ne rien faire.
      - ("throttled", N) : contenu changé mais trop tôt après le dernier
                           écrit accepté -> ne rien faire maintenant,
                           réessayer dans N ms.

    État partagé entre les workers Gunicorn via Memcached — un dict en
    mémoire de processus ne suffirait pas avec plusieurs workers (2 par
    défaut ici, voir Dockerfile). Dégradé si Memcached est indisponible :
    on laisse toujours passer plutôt que de risquer de perdre une
    donnée réelle sur un simple souci d'infra annexe.
    """
    if min_interval_ms is None:
        min_interval_ms = DIFF_WATCHDOG_MIN_INTERVAL_MS

    fp = fingerprint_payload(payload)
    now_ms = int(time.time() * 1000)
    state_key = f"diffwatchdog:{source}"

    try:
        client = get_memcache_client()
        raw = client.get(state_key)
    except MemcacheError:
        return "ok", 0

    prev = json.loads(raw) if raw else None

    if prev and prev.get("fingerprint") == fp:
        return "unchanged", 0

    if prev and (now_ms - prev.get("last_accepted_ms", 0)) < min_interval_ms:
        retry_after_ms = min_interval_ms - (now_ms - prev["last_accepted_ms"])
        return "throttled", retry_after_ms

    try:
        client.set(state_key, json.dumps({"fingerprint": fp, "last_accepted_ms": now_ms}), expire=3600)
    except MemcacheError:
        pass  # dégradé : l'écriture réelle ci-après a toujours lieu
    return "ok", 0


def write_source_data(source: str, payload: dict, origin: str = "external", auto_register: bool = True) -> dict:
    envelope = {
        "source": source,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "data": payload,
    }

    path = file_path_for(source)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(envelope, f, ensure_ascii=False)

    try:
        client = get_memcache_client()
        client.set(f"source:{source}", json.dumps(envelope), expire=CACHE_TTL_SECONDS)
    except MemcacheError:
        app.logger.warning("Memcached indisponible, écriture fichier seule pour %s", source)

    if auto_register:
        mark_registered(source, os.path.getmtime(path))
    else:
        # Chemin de la bannette d'interaction (/sources/from-selection) :
        # reste PROPOSÉE, jamais auto-enregistrée comme /ingest -- la
        # personne décide explicitement de la promouvoir ou non.
        mark_proposed(source, os.path.getmtime(path), origin=origin)
    return envelope


def normalize_file_content(source: str, raw_content, mtime: float) -> dict:
    if isinstance(raw_content, dict) and {"source", "updated_at", "data"} <= raw_content.keys():
        return raw_content

    return {
        "source": source,
        "updated_at": datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat(),
        "data": raw_content,
    }


def read_source_data(source: str) -> dict | None:
    try:
        client = get_memcache_client()
        cached = client.get(f"source:{source}")
        if cached:
            return json.loads(cached)
    except MemcacheError:
        app.logger.warning("Memcached indisponible en lecture, fallback fichier pour %s", source)

    path = file_path_for(source)
    if not os.path.exists(path):
        return None

    with open(path, "r", encoding="utf-8") as f:
        raw_content = json.load(f)

    return normalize_file_content(source, raw_content, os.path.getmtime(path))


# ============================================================
# Découverte — scan du dossier data, propositions
# ============================================================

def scan_sources() -> list[dict]:
    registry = load_registry()
    results = []

    for path in sorted(glob.glob(os.path.join(DATA_DIR, "*.json"))):
        filename = os.path.basename(path)
        if filename == "_registry.json":
            continue

        source = filename[:-len(".json")]
        entry = registry.get(source)

        # Une source supprimée (douce) n'apparaît pas dans la liste
        # normale — voir GET /sources/deleted pour la retrouver.
        if entry and entry.get("deleted"):
            continue

        mtime = os.path.getmtime(path)

        if entry is None:
            status = "new"
        elif mtime > entry.get("last_seen_mtime", 0):
            status = "modified"
        else:
            status = "ok"

        results.append(
            {
                "source": source,
                "status": status,
                "registered": bool(entry and entry.get("registered")),
                "origin": (entry or {}).get("origin", "external"),
                "updated_at": datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat(),
            }
        )

    return results


@app.route("/sources/from-selection", methods=["POST"])
def create_source_from_selection():
    """
    "Verser" une sélection (Fusion, RadialTree, carte...) comme
    nouvelle source dans la bannette d'interaction. Contrairement à
    /ingest (chemin de confiance, auto-enregistré), reste PROPOSÉE
    jusqu'à promotion explicite -- une sélection ad hoc n'a pas la
    même légitimité immédiate qu'un flux poussé par un système externe
    de confiance.

    Préfixe "selection-" imposé au nom, en plus du champ origin dans
    le registre -- double signal (visible même sans consulter le
    registre) qu'une entrée vient d'une sélection plutôt que d'un
    dépôt externe, utile si le registre venait à être perdu/corrompu.

    Protégée par rights-api (#320).
    """
    body = request.get_json(silent=True) or {}
    allowed, error = _check_manage_right(body)
    if not allowed:
        return jsonify({"error": error}), 403
    name = (body.get("name") or "").strip()
    data = body.get("data")
    if not name:
        return jsonify({"error": "'name' requis"}), 400
    if data is None:
        return jsonify({"error": "'data' requis"}), 400

    safe_name = f"selection-{name.replace('/', '_')}"
    envelope = write_source_data(safe_name, data, origin="selection", auto_register=False)
    return jsonify({"status": "ok", "source": safe_name, **envelope}), 201


@app.route("/sources", methods=["GET"])
def list_sources():
    return jsonify({"sources": scan_sources()}), 200


@app.route("/sources/<source>/register", methods=["POST"])
def register_source(source: str):
    """Protégée par rights-api (#320)."""
    body = request.get_json(silent=True) or {}
    allowed, error = _check_manage_right(body)
    if not allowed:
        return jsonify({"error": error}), 403
    path = file_path_for(source)
    if not os.path.exists(path):
        return jsonify({"error": f"aucun fichier trouvé pour la source '{source}'"}), 404

    mark_registered(source, os.path.getmtime(path))
    return jsonify({"status": "ok", "source": source, "registered": True}), 200


@app.route("/sources/<source>", methods=["DELETE"])
def delete_source(source: str):
    """
    Suppression douce — le fichier reste sur disque, la source disparaît
    juste de la liste active. Voir POST /sources/<source>/restore pour
    annuler.

    Protégée par rights-api (#320).
    """
    body = request.get_json(silent=True) or {}
    allowed, error = _check_manage_right(body)
    if not allowed:
        return jsonify({"error": error}), 403
    path = file_path_for(source)
    if not os.path.exists(path):
        return jsonify({"error": f"aucun fichier trouvé pour la source '{source}'"}), 404

    mark_deleted(source)
    return jsonify({"status": "ok", "source": source, "deleted": True}), 200


@app.route("/sources/deleted", methods=["GET"])
def list_deleted_sources():
    registry = load_registry()
    deleted = [
        {"source": source, "deleted_at": entry.get("deleted_at")}
        for source, entry in registry.items()
        if entry.get("deleted")
    ]
    deleted.sort(key=lambda d: d["deleted_at"] or "", reverse=True)
    return jsonify({"sources": deleted}), 200


@app.route("/sources/<source>/restore", methods=["POST"])
def restore_source(source: str):
    """Protégée par rights-api (#320)."""
    body = request.get_json(silent=True) or {}
    allowed, error = _check_manage_right(body)
    if not allowed:
        return jsonify({"error": error}), 403
    path = file_path_for(source)
    if not os.path.exists(path):
        return jsonify({"error": f"aucun fichier trouvé pour la source '{source}' (elle a peut-être été purgée)"}), 404

    mark_restored(source)
    return jsonify({"status": "ok", "source": source, "restored": True}), 200


# ============================================================
# Analyse calendaire — recherche de dates/timestamps + mots-clés
# ============================================================

# Couvre "YYYY-MM-DD" seul, ou avec heure séparée par 'T' ou espace,
# secondes/millisecondes et fuseau optionnels (offset ou 'Z').
_ISO_DATE_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}([T ]\d{2}:\d{2}(:\d{2}(\.\d+)?)?([+-]\d{2}:?\d{2}|Z)?)?$"
)


def try_parse_date_string(value: str):
    candidate = value.strip()
    if not _ISO_DATE_RE.match(candidate):
        return None

    normalized = candidate.replace(" ", "T", 1)
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def try_parse_epoch(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    # Bornes larges (secondes: ~2001-2096, millisecondes: proportionnel)
    # pour capter des timestamps Unix sans supposer une unité précise.
    if 1e9 <= value < 4e9:
        return datetime.fromtimestamp(value, tz=timezone.utc)
    if 1e12 <= value < 4e12:
        return datetime.fromtimestamp(value / 1000, tz=timezone.utc)
    return None


def extract_dates(obj, path="$"):
    """
    Parcourt récursivement une structure JSON et renvoie chaque valeur
    qui ressemble à une date/timestamp, avec le chemin où elle a été
    trouvée. Ne suppose aucun nom de champ particulier — générique,
    comme demandé.
    """
    results = []

    if isinstance(obj, dict):
        for key, value in obj.items():
            results.extend(extract_dates(value, f"{path}.{key}"))
    elif isinstance(obj, list):
        for index, value in enumerate(obj):
            results.extend(extract_dates(value, f"{path}[{index}]"))
    elif isinstance(obj, str):
        dt = try_parse_date_string(obj)
        if dt:
            results.append((path, obj, dt))
    else:
        dt = try_parse_epoch(obj)
        if dt:
            results.append((path, obj, dt))

    return results


def parse_keyword_expression(expr: str) -> list[list[str]]:
    """
    Transforme une expression du type "incident OR panne AND regions" en
    une liste de groupes ET, combinés en OU entre eux (précédence
    standard : AND se lie plus fort que OR).
    Ex: "incident OR panne AND regions" -> [["incident"], ["panne", "regions"]]
    -> matche si "incident" seul, OU ("panne" ET "regions") ensemble.
    Une expression vide renvoie [] (convention : "carte blanche", tout matche).
    """
    tokens = expr.split()
    or_groups: list[list[str]] = []
    current_group: list[str] = []

    for token in tokens:
        upper = token.upper()
        if upper == "OR":
            if current_group:
                or_groups.append(current_group)
                current_group = []
        elif upper == "AND":
            continue  # simple séparateur, le terme suivant rejoint le groupe courant
        else:
            current_group.append(token)

    if current_group:
        or_groups.append(current_group)

    return or_groups


def match_keywords(source: str, data, keyword_expr: str) -> bool:
    """
    Expression vide ("carte blanche") : tout matche, pas de filtre.
    Sinon : évalue l'expression OR/AND contre le nom de la source et
    tout le contenu JSON (recherche texte simple, insensible à la casse).
    """
    or_groups = parse_keyword_expression(keyword_expr)
    if not or_groups:
        return True

    haystack = (source + " " + json.dumps(data, ensure_ascii=False)).lower()
    return any(all(term.lower() in haystack for term in and_group) for and_group in or_groups)


def collect_matches(keyword_expr: str) -> list[dict]:
    """
    Parcourt toutes les sources enregistrées (pas les propositions non
    confirmées), filtre par l'expression mots-clés, et extrait toutes les
    dates trouvées dans celles qui matchent.
    """
    registry = load_registry()
    matches = []

    for source, entry in registry.items():
        if not entry.get("registered"):
            continue

        envelope = read_source_data(source)
        if not envelope:
            continue

        data = envelope.get("data")
        if not match_keywords(source, data, keyword_expr):
            continue

        for path, raw_value, dt in extract_dates(data):
            matches.append(
                {
                    "source": source,
                    "path": path,
                    "raw_value": raw_value,
                    "date": dt.date().isoformat(),
                }
            )

    return matches


def find_date_in_dict(d: dict):
    """
    Cherche une date/timestamp parmi les valeurs directes (non récursif)
    d'un dict — utilisé pour rattacher un compteur trouvé dans un objet
    à un jour, en supposant que la date est un champ frère du compteur
    dans le même objet JSON.
    """
    for value in d.values():
        if isinstance(value, str):
            dt = try_parse_date_string(value)
            if dt:
                return dt
        else:
            dt = try_parse_epoch(value)
            if dt:
                return dt
    return None


def walk_for_label(obj, key: str, value_filter: str | None):
    """
    Parcourt récursivement le JSON à la recherche d'objets contenant
    `key`. Deux modes selon `value_filter` :
    - None (mode "compteur") : la valeur de `key` doit être numérique,
      elle est prise telle quelle comme montant.
    - une chaîne (mode "occurrences", `key=value_filter`) : compte 1 par
      correspondance exacte (comparaison texte, insensible à la casse).
    Chaque correspondance est datée via find_date_in_dict() sur le même
    objet ; sans date trouvée à ce niveau, l'occurrence est ignorée (v1 :
    pas de remontée vers les objets englobants).
    """
    results = []

    if isinstance(obj, dict):
        if key in obj:
            amount = None
            if value_filter is not None:
                if str(obj[key]).lower() == value_filter.lower():
                    amount = 1
            else:
                raw = obj[key]
                if isinstance(raw, (int, float)) and not isinstance(raw, bool):
                    amount = raw

            if amount is not None:
                dt = find_date_in_dict(obj)
                if dt:
                    results.append((dt.date().isoformat(), amount))

        for value in obj.values():
            results.extend(walk_for_label(value, key, value_filter))

    elif isinstance(obj, list):
        for item in obj:
            results.extend(walk_for_label(item, key, value_filter))

    return results


def parse_keywords_param() -> str:
    """Renvoie l'expression brute telle quelle (ex: "incident OR panne AND regions")."""
    return request.args.get("keywords", "").strip()


def collect_pixel_events(label: str, keyword_expr: str) -> dict[str, float]:
    """
    Agrège, par jour, les montants trouvés pour `label` (mode compteur ou
    occurrences selon la présence de "=") à travers toutes les sources
    enregistrées qui matchent le filtre mots-clés courant.
    """
    if "=" in label:
        key, value_filter = label.split("=", 1)
        key, value_filter = key.strip(), value_filter.strip()
    else:
        key, value_filter = label.strip(), None

    registry = load_registry()
    totals: dict[str, float] = {}

    for source, entry in registry.items():
        if not entry.get("registered"):
            continue
        envelope = read_source_data(source)
        if not envelope:
            continue
        data = envelope.get("data")
        if not match_keywords(source, data, keyword_expr):
            continue

        for day, amount in walk_for_label(data, key, value_filter):
            totals[day] = totals.get(day, 0) + amount

    return totals


@app.route("/calendar/summary", methods=["GET"])
def calendar_summary():
    """
    Agrégation par cellule pour une période donnée, adaptée au niveau
    de zoom :
    - level=year, period=YYYY  -> une cellule par mois (12)
    - level=month, period=YYYY-MM -> une cellule par jour
    Couleur simple (présence) : has_match = au moins une date trouvée.
    """
    level = request.args.get("level", "year")
    period = request.args.get("period")
    keywords = parse_keywords_param()

    if not period:
        return jsonify({"error": "paramètre 'period' requis"}), 400

    matched_dates = {m["date"] for m in collect_matches(keywords)}
    buckets = []

    if level == "year":
        try:
            year = int(period)
        except ValueError:
            return jsonify({"error": "period doit être une année, ex: 2026"}), 400
        for month in range(1, 13):
            prefix = f"{year:04d}-{month:02d}-"
            has_match = any(d.startswith(prefix) for d in matched_dates)
            buckets.append({"key": month, "has_match": has_match})

    elif level == "month":
        try:
            year_str, month_str = period.split("-")
            year, month = int(year_str), int(month_str)
        except ValueError:
            return jsonify({"error": "period doit être YYYY-MM, ex: 2026-08"}), 400
        days_in_month = calendar.monthrange(year, month)[1]
        for day in range(1, days_in_month + 1):
            key = f"{year:04d}-{month:02d}-{day:02d}"
            buckets.append({"key": day, "has_match": key in matched_dates})

    else:
        return jsonify({"error": "level doit être 'year' ou 'month'"}), 400

    return jsonify({"level": level, "period": period, "buckets": buckets}), 200


@app.route("/calendar/pixel-summary", methods=["GET"])
def calendar_pixel_summary():
    """
    Variante "compteur" du résumé calendaire : agrège une valeur
    numérique par cellule au lieu d'une simple présence.
    - label sans "=" (ex: "frequence") : somme la valeur numérique de ce
      champ, où qu'il apparaisse dans le JSON, rattachée au jour trouvé
      dans le même objet.
    - label avec "=" (ex: "type=incident") : compte les occurrences où
      ce champ vaut exactement cette valeur.
    Décide automatiquement binaire vs tricolore selon le volume observé
    sur la période affichée (règle simple v1 : max >= 3 -> tricolore).
    """
    level = request.args.get("level", "year")
    period = request.args.get("period")
    label = request.args.get("label", "").strip()
    keywords = parse_keywords_param()

    if not period:
        return jsonify({"error": "paramètre 'period' requis"}), 400
    if not label:
        return jsonify({"error": "paramètre 'label' requis"}), 400

    daily_totals = collect_pixel_events(label, keywords)
    buckets = []

    if level == "year":
        try:
            year = int(period)
        except ValueError:
            return jsonify({"error": "period doit être une année, ex: 2026"}), 400
        for month in range(1, 13):
            prefix = f"{year:04d}-{month:02d}-"
            total = sum(v for d, v in daily_totals.items() if d.startswith(prefix))
            buckets.append({"key": month, "value": total})

    elif level == "month":
        try:
            year_str, month_str = period.split("-")
            year, month = int(year_str), int(month_str)
        except ValueError:
            return jsonify({"error": "period doit être YYYY-MM, ex: 2026-08"}), 400
        days_in_month = calendar.monthrange(year, month)[1]
        for day in range(1, days_in_month + 1):
            key = f"{year:04d}-{month:02d}-{day:02d}"
            buckets.append({"key": day, "value": daily_totals.get(key, 0)})

    else:
        return jsonify({"error": "level doit être 'year' ou 'month'"}), 400

    max_value = max((b["value"] for b in buckets), default=0)
    if max_value >= 3:
        color_scheme = "tricolor"
        thresholds = {"mid": max_value / 2, "max": max_value}
    else:
        color_scheme = "binary"
        thresholds = {"max": max_value}

    mode = "occurrence" if "=" in label else "numeric"

    return jsonify(
        {
            "level": level,
            "period": period,
            "label": label,
            "mode": mode,
            "buckets": buckets,
            "color_scheme": color_scheme,
            "thresholds": thresholds,
        }
    ), 200
def calendar_day():
    """Vue précise : liste des correspondances exactes pour un jour donné."""
    date_str = request.args.get("date")
    keywords = parse_keywords_param()

    if not date_str:
        return jsonify({"error": "paramètre 'date' requis (YYYY-MM-DD)"}), 400

    matches = [m for m in collect_matches(keywords) if m["date"] == date_str]
    return jsonify({"date": date_str, "matches": matches}), 200


@app.route("/calendar/sources", methods=["GET"])
def calendar_sources():
    """
    Résout une sélection de dates (potentiellement à cheval sur plusieurs
    mois/années) en sources concernées — alimente la corbeille de
    sélection côté frontend. Une source apparaît dès qu'elle a au moins
    une correspondance sur l'une des dates sélectionnées.
    """
    dates_param = request.args.get("dates", "")
    selected_dates = {d.strip() for d in dates_param.split(",") if d.strip()}
    keywords = parse_keywords_param()

    if not selected_dates:
        return jsonify({"sources": []}), 200

    match_counts: dict[str, int] = {}
    for m in collect_matches(keywords):
        if m["date"] in selected_dates:
            match_counts[m["source"]] = match_counts.get(m["source"], 0) + 1

    sources = [{"source": s, "match_count": c} for s, c in sorted(match_counts.items())]
    return jsonify({"sources": sources}), 200


# ============================================================
# Endpoints existants — push et lecture d'une source
# ============================================================

@app.route("/ingest/<source>", methods=["POST"])
def ingest(source: str):
    payload = request.get_json(silent=True)
    if payload is None:
        return jsonify({"error": "corps JSON invalide ou absent"}), 400

    verdict, retry_after_ms = check_diff_watchdog(source, payload)
    if verdict == "unchanged":
        return jsonify({"status": "unchanged"}), 200
    if verdict == "throttled":
        return jsonify({
            "status": "throttled",
            "retry_after_ms": retry_after_ms,
            "error": f"Trop de mises à jour rapprochées pour « {source} » — réessayer dans {retry_after_ms} ms.",
        }), 429

    envelope = write_source_data(source, payload)
    return jsonify({"status": "ok", "updated_at": envelope["updated_at"]}), 200


@app.route("/data/<source>", methods=["GET"])
def get_data(source: str):
    envelope = read_source_data(source)
    if envelope is None:
        return jsonify({"status": "unavailable", "source": source}), 503

    return jsonify({"status": "ok", **envelope}), 200


# ------------------------------------------------------------------
# Journal PARTAGÉ (endpoint /logs) -- capture les WARNING et plus
# graves de CE service pour l'agregateur de logs du hub. Ne capture
# PAS le corps des requetes ni de donnee metier -- seulement ce que
# ce fichier journalise deja lui-meme (app.logger.warning/error) plus
# les exceptions non gerees que Flask/Werkzeug journalisent
# nativement en ERROR.
#
# Stocké dans Memcached (livraison #145, voir shared/log_buffer.py
# pour le raisonnement complet) -- PAS un tampon en mémoire de
# processus : ce service tourne avec 2 workers Gunicorn (processus
# séparés, mémoire NON partagée), un tampon en mémoire laissait des
# entrées invisibles selon le worker qui traitait la lecture
# suivante. Toujours volatile/borné (perdu seulement si Memcached
# lui-même redémarre) -- outil de diagnostic à chaud, jamais un
# historique long terme, même philosophie qu'avant.
# ------------------------------------------------------------------
try:
    from log_buffer import make_shared_log_handler, read_shared_log_buffer
except ImportError:
    make_shared_log_handler = None
    read_shared_log_buffer = None

SERVICE_NAME = "api"
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
    return jsonify({"status": "ok", "time": time.time()}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
