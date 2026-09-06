"""
API Zenoss — expose en LECTURE SEULE la base MySQL "events" de
l'application Zenoss existante (externe à ce projet) pour alimenter
l'onglet Zenoss du frontend : racines indépendantes, arbre radial,
vue JSON d'un nœud.

Mêmes garanties de lecture seule que ipam/api/app.py et
optick/api/app.py (voir ipam/README.md pour le détail des trois
niveaux de défense).

Particularité de ce schéma : il n'y a AUCUNE colonne parent/enfant.
La hiérarchie exploitée est la classification d'événements Zenoss
("Event Class", ex. "/App/Fail/Http") — un chemin façon système de
fichiers stocké comme simple chaîne dans `status.eventClass` /
`history.eventClass`. L'arbre est reconstruit en découpant ces
chemins, pas en suivant des clés étrangères.

Colonnes JAMAIS lues : `message`, `summary`, `Location`, `Systems`,
`manager`, `agent`, `ownerid` — le contenu individuel d'un événement
(texte libre, potentiellement sensible) n'est jamais exposé.

EXCEPTION délibérée et scopée : `ipAddress` et `device` (nom de
machine) SONT lus par `/ip_list`, pour la corrélation Fusion IP/MAC
demandée explicitement — voir ce endpoint et zenoss/README.md pour le
détail. Nulle part ailleurs dans ce fichier ces deux colonnes ne sont
lues ; `/tree` et `/roots` (arbre par classification) continuent à ne
renvoyer que des comptages agrégés, jamais d'IP ni de nom de machine.

DEUXIÈME EXCEPTION délibérée et scopée : `Location` et `Systems`
(en plus de `device`/`ipAddress`) SONT lues par `/location_roots` et
`/location_tree/<root_id>`, pour reconstruire un inventaire physique
(hiérarchie de localisation) demandé explicitement — voir ces deux
endpoints et zenoss/README.md, section "Inventaire physique". Nulle
part ailleurs dans ce fichier `Location`/`Systems` ne sont lues ;
`message`, `summary`, `manager`, `agent`, `ownerid` restent exclus
PARTOUT, y compris dans ces deux endpoints.
"""
import logging
import os
import time
import re

import pymysql
import pymysql.cursors
from flask import Flask, jsonify, request
from flask_cors import CORS
from pymemcache.client.base import Client as MemcacheClient
from pymemcache.exceptions import MemcacheError
try:
    from version_endpoint import register_version_route
except ImportError:
    register_version_route = None

_log = logging.getLogger("zenoss_app")

app = Flask(__name__)
CORS(app)
if register_version_route:
    register_version_route(app, "zenoss-api")

DB_HOST = os.environ.get("ZENOSS_DB_HOST", "")
DB_PORT = int(os.environ.get("ZENOSS_DB_PORT", "3306"))
DB_NAME = os.environ.get("ZENOSS_DB_NAME", "events")
DB_USER = os.environ.get("ZENOSS_DB_USER", "")
DB_PASSWORD = os.environ.get("ZENOSS_DB_PASSWORD", "")
DB_SSL = os.environ.get("ZENOSS_DB_SSL", "false").lower() == "true"
DB_CHARSET = os.environ.get("ZENOSS_DB_CHARSET", "utf8")

CACHE_TTL = int(os.environ.get("ZENOSS_CACHE_TTL", "60"))
MEMCACHED_HOST = os.environ.get("MEMCACHED_HOST", "memcached")
MEMCACHED_PORT = int(os.environ.get("MEMCACHED_PORT", "11211"))

# Sévérités Zenoss standard (convention historique du produit).
SEVERITY_LABELS = {5: "Critical", 4: "Error", 3: "Warning", 2: "Info", 1: "Debug", 0: "Clear"}


def get_memcache_client():
    return MemcacheClient((MEMCACHED_HOST, MEMCACHED_PORT), connect_timeout=2, timeout=2)


def cache_get(key):
    try:
        raw = get_memcache_client().get(key)
        return raw.decode("utf-8") if raw else None
    except MemcacheError:
        return None


def cache_set(key, value):
    try:
        get_memcache_client().set(key, value.encode("utf-8"), expire=CACHE_TTL)
    except MemcacheError:
        app.logger.warning("Memcached indisponible en écriture pour %s", key)


def get_connection():
    if not DB_HOST or not DB_USER:
        raise RuntimeError("ZENOSS_DB_HOST / ZENOSS_DB_USER non configurés (voir zenoss/README.md)")
    # Traces DEBUG (livraison #224, audit rétroactif) -- RÈGLE
    # ABSOLUE : DB_PASSWORD n'apparaît JAMAIS dans une trace.
    app.logger.debug("get_connection : démarré (%s:%s, base=%s, jamais le mot de passe ici)", DB_HOST, DB_PORT, DB_NAME)
    start = time.monotonic()
    try:
        conn = pymysql.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
            charset=DB_CHARSET,
            cursorclass=pymysql.cursors.DictCursor,
            connect_timeout=5,
            read_timeout=15,
            ssl={"ssl": {}} if DB_SSL else None,
            autocommit=False,
        )
    except Exception as exc:
        elapsed_ms = int((time.monotonic() - start) * 1000)
        app.logger.debug("get_connection : ÉCHEC après %d ms -- %s", elapsed_ms, exc)
        raise
    elapsed_ms = int((time.monotonic() - start) * 1000)
    app.logger.debug("get_connection : succès en %d ms", elapsed_ms)
    return conn


def run_select(cur, sql, params=None):
    if not sql.strip().upper().startswith("SELECT"):
        raise ValueError("run_select() n'accepte que des requêtes SELECT")
    cur.execute(sql, params or [])
    return cur.fetchall()


# ------------------------------------------------------------------
# Assemblage de l'arbre — fonctions PURES, testables sans base réelle.
# ------------------------------------------------------------------

def normalize_class_path(raw_path):
    """'/App//Fail/' -> ['App', 'Fail'] ; vide/None -> ['Unknown']
    (valeur par défaut de la colonne eventClass dans ce schéma)."""
    if not raw_path or not raw_path.strip("/"):
        return ["Unknown"]
    return [seg for seg in raw_path.split("/") if seg]


def build_class_tree(active_by_class_severity, history_count_by_class):
    """
    active_by_class_severity : {eventClass_path: {severity: n}}
    history_count_by_class   : {eventClass_path: n}

    Retourne (root_nodes, root_ids) : un nœud par segment de chemin
    distinct, avec ses PROPRES comptages (pas cumulés — les cumuls sont
    calculés séparément par count_descendants pour le panneau des
    racines). id de nœud = chemin canonique "/App/Fail".
    """
    all_paths = set(active_by_class_severity) | set(history_count_by_class)

    nodes = {}  # id (chemin canonique) -> node

    def ensure_node(segments):
        node_id = "/" + "/".join(segments)
        if node_id in nodes:
            return nodes[node_id]
        node = {
            "id": node_id,
            "type": "class",
            "name": segments[-1],
            "children": [],
            "raw": {"path": node_id, "activeCount": 0, "activeBySeverity": {}, "historyCount": 0},
        }
        nodes[node_id] = node
        if len(segments) > 1:
            parent = ensure_node(segments[:-1])
            parent["children"].append(node)
        return node

    for path in all_paths:
        segments = normalize_class_path(path)
        node = ensure_node(segments)
        by_sev = active_by_class_severity.get(path, {})
        node["raw"]["activeCount"] = sum(by_sev.values())
        node["raw"]["activeBySeverity"] = {
            SEVERITY_LABELS.get(sev, str(sev)): n for sev, n in sorted(by_sev.items(), reverse=True)
        }
        node["raw"]["historyCount"] = history_count_by_class.get(path, 0)

    root_ids = [node_id for node_id, node in nodes.items() if node["id"].count("/") == 1]
    root_nodes = {nid: nodes[nid] for nid in root_ids}
    return root_nodes, root_ids


def count_descendants(node):
    """(nb nœuds descendants, nb événements actifs cumulés), racine exclue."""
    n_nodes = n_active = 0
    for child in node["children"]:
        n_nodes += 1
        n_active += child["raw"]["activeCount"]
        cn, ca = count_descendants(child)
        n_nodes += cn
        n_active += ca
    return n_nodes, n_active


# ------------------------------------------------------------------
# Inventaire physique (Location/IP/Systems) — DEUXIÈME EXCEPTION
# délibérée et scopée au périmètre "jamais lu" (voir en-tête du
# module). Fonctions PURES, testables sans base réelle — même
# principe que build_class_tree, mais gardées séparées plutôt que
# fusionnées : la logique diffère (devices en feuilles, pas de
# sévérité) et ça évite tout risque de régression sur le code de
# classification déjà testé.
# ------------------------------------------------------------------

# Heuristique de nommage (PAS une donnée de topologie réelle — aucune
# clé étrangère ni table de routage/interface dans ce schéma) pour une
# coloration/tri indicatifs des devices dans l'arbre de localisation.
# Convention Cisco + préfixes locaux observés sur ce déploiement — à
# ajuster si un autre inventaire suit une convention différente.
LOCATION_ROLE_HINTS = [
    (re.compile(r"C3750|C3560|C3064|C6500|C4500", re.I), 1, "distribution"),
    (re.compile(r"C2960|C2950|C2970", re.I), 2, "acces"),
    (re.compile(r"AF5|AF24|IP10|PTP|PMP", re.I), 0, "liaison_radio_FH"),
    (re.compile(r"^RF-", re.I), 0, "radio"),
    (re.compile(r"^UPS-", re.I), 9, "onduleur"),
    (re.compile(r"Switch\d*_Elec", re.I), 5, "switch_elec_local"),
]


def guess_device_role(device_name):
    """(tier, étiquette) — heuristique de nommage uniquement, jamais
    présenté comme une donnée de topologie certaine côté front."""
    name = device_name or ""
    for pattern, tier, label in LOCATION_ROLE_HINTS:
        if pattern.search(name):
            return tier, label
    return 5, "inconnu"


def normalize_location_path(raw_path):
    """'/Parc//Batiment 5/' -> ['Parc', 'Batiment 5'] ;
    vide/None -> ['Sans localisation'] (pas de valeur par défaut
    connue pour Location dans ce schéma, contrairement à eventClass)."""
    if not raw_path or not raw_path.strip("/"):
        return ["Sans localisation"]
    return [seg for seg in raw_path.split("/") if seg]


def build_location_tree(rows):
    """
    rows : itérable de dicts {device, Location, ipAddress, Systems}.

    Retourne (root_nodes, root_ids) — même contrat "forêt de racines
    indépendantes" que build_class_tree, mais feuilles = devices
    (type "device"), noeuds intermédiaires = segments de Location
    (type "location"), chacun avec son propre `deviceCount` (devices
    directement rattachés, pas cumulé — cumul séparé via
    count_location_descendants, même principe que la classification).

    Fusion : clé (device, noeud de localisation). Le même device
    apparaissant plusieurs fois pour la MÊME Location (`history` est
    un historique, pas un état unique) voit ses tags Systems fusionnés
    et conserve la première IP rencontrée. Le même device sous une
    Location DIFFÉRENTE ressort comme deux noeuds distincts — un
    déplacement réel d'équipement n'est pas une duplication à fusionner.
    """
    nodes = {}  # id de chemin -> noeud "location"
    device_index = {}  # (location_node_id, device) -> noeud "device"

    def ensure_location_node(segments):
        node_id = "/" + "/".join(segments)
        if node_id in nodes:
            return nodes[node_id]
        node = {
            "id": node_id,
            "type": "location",
            "name": segments[-1],
            "children": [],
            "raw": {"path": node_id, "deviceCount": 0},
        }
        nodes[node_id] = node
        if len(segments) > 1:
            parent = ensure_location_node(segments[:-1])
            parent["children"].append(node)
        return node

    for row in rows:
        device = row.get("device")
        if not device:
            continue
        segments = normalize_location_path(row.get("Location"))
        loc_node = ensure_location_node(segments)
        key = (loc_node["id"], device)
        systems = [t for t in (row.get("Systems") or "").split("|") if t]

        existing = device_index.get(key)
        if existing is None:
            dev_node = {
                "id": f"{loc_node['id']}/device:{device}",
                "type": "device",
                "name": device,
                "children": [],
                "raw": {
                    "path": f"{loc_node['raw']['path']}/{device}",
                    "ip": row.get("ipAddress"),
                    "systems": systems,
                    "roleGuess": guess_device_role(device)[1],
                },
            }
            device_index[key] = dev_node
            loc_node["children"].append(dev_node)
            loc_node["raw"]["deviceCount"] += 1
        else:
            for t in systems:
                if t not in existing["raw"]["systems"]:
                    existing["raw"]["systems"].append(t)

    root_ids = [nid for nid, node in nodes.items() if node["id"].count("/") == 1]
    root_nodes = {nid: nodes[nid] for nid in root_ids}
    return root_nodes, root_ids


def count_location_descendants(node):
    """(nb noeuds descendants [locations + devices], nb devices
    cumulés), racine exclue — même principe que count_descendants
    (classification) mais gardée séparée (voir commentaire de section)."""
    n_nodes = n_devices = 0
    for child in node["children"]:
        n_nodes += 1
        if child["type"] == "device":
            n_devices += 1
        cn, cd = count_location_descendants(child)
        n_nodes += cn
        n_devices += cd
    return n_nodes, n_devices


def fetch_location_rows(cur, ip_prefix=None):
    """EXCEPTION délibérée et scopée (voir en-tête du module et
    zenoss/README.md, section "Inventaire physique") : lit device,
    Location, ipAddress, Systems sur `history` — colonnes normalement
    dans le périmètre "jamais lu". message/summary/manager/agent/
    ownerid restent exclus partout, y compris ici."""
    if ip_prefix:
        return run_select(
            cur,
            "SELECT DISTINCT device, Location, ipAddress, Systems FROM history "
            "WHERE ipAddress LIKE %s",
            [ip_prefix + "%"],
        )
    return run_select(
        cur,
        "SELECT DISTINCT device, Location, ipAddress, Systems FROM history",
    )


def load_location_forest(ip_prefix=None):
    conn = get_connection()
    try:
        cur = conn.cursor()
        rows = fetch_location_rows(cur, ip_prefix)
        return build_location_tree(rows)
    finally:
        conn.close()


# ------------------------------------------------------------------
# Accès DB — SELECT uniquement, agrégats seulement (jamais un
# événement individuel).
# ------------------------------------------------------------------

def fetch_active_by_class_severity(cur, start=None, end=None):
    """Comptage par (classe, sévérité) sur `status` (événements actifs).
    Fenêtre optionnelle sur `firstTime` (première occurrence de ce
    dédoublonnage d'événement) — pas `lastTime`, pour rester cohérent
    avec le choix fait côté tickets (Optick/TTS-GU) : "apparu pendant
    cette fenêtre", pas "actif pendant cette fenêtre" (qui inclurait
    aussi des événements plus anciens toujours en cours)."""
    if start is not None and end is not None:
        rows = run_select(
            cur,
            "SELECT eventClass, severity, COUNT(*) AS n FROM status "
            "WHERE firstTime BETWEEN %s AND %s GROUP BY eventClass, severity",
            [start, end],
        )
    else:
        rows = run_select(cur, "SELECT eventClass, severity, COUNT(*) AS n FROM status GROUP BY eventClass, severity")
    result = {}
    for row in rows:
        result.setdefault(row["eventClass"], {})[row["severity"]] = row["n"]
    return result


def fetch_history_count_by_class(cur, start=None, end=None):
    if start is not None and end is not None:
        rows = run_select(
            cur,
            "SELECT eventClass, COUNT(*) AS n FROM history WHERE firstTime BETWEEN %s AND %s GROUP BY eventClass",
            [start, end],
        )
    else:
        rows = run_select(cur, "SELECT eventClass, COUNT(*) AS n FROM history GROUP BY eventClass")
    return {row["eventClass"]: row["n"] for row in rows}


def fetch_date_bounds(cur, class_paths):
    """MIN/MAX firstTime (status + history réunis) pour un ensemble de
    chemins de classe — dimensionne le curseur. `firstTime` est un
    double (epoch, potentiellement fractionnaire) : arrondi à la
    seconde pour un curseur en secondes entières. None si aucun
    chemin ou aucun événement daté."""
    if not class_paths:
        return None
    placeholders = ",".join(["%s"] * len(class_paths))
    rows = run_select(
        cur,
        f"""SELECT MIN(firstTime) AS min_d, MAX(firstTime) AS max_d FROM (
                SELECT firstTime FROM status WHERE eventClass IN ({placeholders})
                UNION ALL
                SELECT firstTime FROM history WHERE eventClass IN ({placeholders})
            ) t""",
        [*class_paths, *class_paths],
    )
    if not rows or rows[0]["min_d"] is None:
        return None
    return {"min": int(rows[0]["min_d"]), "max": int(rows[0]["max_d"])}


def collect_class_paths(node):
    """Fonction pure — chemins de classe (ids canoniques) dans un
    sous-arbre, racine comprise."""
    paths = [node["id"]]
    for c in node["children"]:
        paths.extend(collect_class_paths(c))
    return paths


# ------------------------------------------------------------------
# Fusion IP/MAC — EXCEPTION délibérée et scopée au périmètre "jamais
# lu" du reste de ce fichier (voir en-tête du module). Aucune colonne
# de contenu libre (message/summary) touchée ici non plus : seuls
# ipAddress/device/severity, déjà des identifiants réseau ou une
# sévérité numérique, jamais du texte libre.
# ------------------------------------------------------------------

def fetch_ip_activity(cur):
    """(ip, device, sévérité) -> comptage d'événements ACTIFS (table
    status). Le format `ipAddress` (char(15)) est déjà une notation
    IPv4 pointée standard dans ce schéma — pas d'ambiguïté de type
    décimal comme pour phpipam, donc pas de normalisation nécessaire
    ici."""
    return run_select(
        cur,
        "SELECT ipAddress, device, severity, COUNT(*) AS n FROM status "
        "WHERE ipAddress IS NOT NULL AND ipAddress != '' "
        "GROUP BY ipAddress, device, severity",
    )


def fetch_ip_history_counts(cur):
    """Volume d'événements HISTORIQUES par IP (contexte additionnel,
    pas de sévérité détaillée nécessaire pour cet usage)."""
    rows = run_select(
        cur,
        "SELECT ipAddress, COUNT(*) AS n FROM history "
        "WHERE ipAddress IS NOT NULL AND ipAddress != '' GROUP BY ipAddress",
    )
    return {row["ipAddress"]: row["n"] for row in rows}


def build_ip_activity_entries(status_rows, history_counts):
    """Fonction pure — regroupe les lignes (ip, device, sévérité, n)
    par (ip, device), calcule le total actif et la sévérité MAX (les
    sévérités Zenoss sont croissantes avec la gravité — 5=Critical),
    puis ajoute le comptage historique associé à cette IP (additionné
    tous devices confondus à cette IP, non recoupé par device)."""
    grouped = {}
    for row in status_rows:
        key = (row["ipAddress"], row["device"])
        entry = grouped.setdefault(key, {
            "ip": row["ipAddress"], "device": row["device"],
            "activeCount": 0, "maxSeverity": None,
        })
        entry["activeCount"] += row["n"]
        if entry["maxSeverity"] is None or row["severity"] > entry["maxSeverity"]:
            entry["maxSeverity"] = row["severity"]

    entries = list(grouped.values())
    for entry in entries:
        entry["historyCount"] = history_counts.get(entry["ip"], 0)
        entry["severityLabel"] = SEVERITY_LABELS.get(entry["maxSeverity"], str(entry["maxSeverity"]))
    return entries


def load_forest(start=None, end=None):
    conn = get_connection()
    try:
        cur = conn.cursor()
        active = fetch_active_by_class_severity(cur, start, end)
        history = fetch_history_count_by_class(cur, start, end)
        return build_class_tree(active, history)
    finally:
        conn.close()


def load_date_bounds(class_paths):
    if not class_paths:
        return None
    conn = get_connection()
    try:
        cur = conn.cursor()
        return fetch_date_bounds(cur, class_paths)
    finally:
        conn.close()


# ------------------------------------------------------------------
# Routes — GET uniquement.
# ------------------------------------------------------------------

# ------------------------------------------------------------------
# Journal PARTAGE (endpoint /logs) -- capture les WARNING et plus
# graves de CE service. Stocke dans Memcached (livraison #145, voir
# shared/log_buffer.py) -- PAS un tampon en memoire de processus : ce
# service tourne avec 2 workers Gunicorn (processus separes, memoire
# NON partagee), un tampon en memoire laissait des entrees invisibles
# selon le worker qui traitait la lecture suivante. Toujours
# volatile/borne (perdu seulement si Memcached lui-meme redemarre).
# ------------------------------------------------------------------
try:
    from log_buffer import make_shared_log_handler, read_shared_log_buffer
except ImportError:
    make_shared_log_handler = None
    read_shared_log_buffer = None

SERVICE_NAME = "zenoss-api"
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
    if not DB_HOST or not DB_USER:
        return jsonify({"status": "degraded", "db": "non configuré"}), 200
    try:
        conn = get_connection()
        try:
            cur = conn.cursor()
            run_select(cur, "SELECT 1")
        finally:
            conn.close()
        return jsonify({"status": "ok", "db": "reachable"}), 200
    except Exception as exc:  # noqa: BLE001
        return jsonify({"status": "degraded", "db": "unreachable", "error": str(exc)}), 200


@app.route("/ip_list", methods=["GET"])
def ip_list():
    """Corrélation IP/MAC (onglet Fusion) — combinée CÔTÉ NAVIGATEUR
    avec l'équivalent d'autres sources, aucun service intermédiaire.
    Voir le commentaire d'en-tête de ce fichier : exception délibérée
    et scopée sur ipAddress/device, tout le reste du périmètre "jamais
    lu" reste inchangé."""
    cached = cache_get("zenoss:ip_list")
    if cached:
        return app.response_class(cached, mimetype="application/json")

    try:
        conn = get_connection()
        try:
            cur = conn.cursor()
            status_rows = fetch_ip_activity(cur)
            history_counts = fetch_ip_history_counts(cur)
        finally:
            conn.close()
    except Exception as exc:  # noqa: BLE001
        _log.debug("ip_list : base Zenoss injoignable -- %s", exc)
        return jsonify({"error": f"base Zenoss injoignable : {exc}"}), 503

    entries = build_ip_activity_entries(status_rows, history_counts)

    import json as _json
    body = _json.dumps({"entries": entries})
    cache_set("zenoss:ip_list", body)
    return app.response_class(body, mimetype="application/json")


@app.route("/roots", methods=["GET"])
def list_roots():
    cached = cache_get("zenoss:roots")
    if cached:
        return app.response_class(cached, mimetype="application/json")

    try:
        root_nodes, root_ids = load_forest()
    except Exception as exc:  # noqa: BLE001
        _log.debug("list_roots : base Zenoss injoignable -- %s", exc)
        return jsonify({"error": f"base Zenoss injoignable : {exc}"}), 503

    roots = []
    for rid in root_ids:
        node = root_nodes[rid]
        n_nodes, n_active = count_descendants(node)
        roots.append({
            "id": node["id"],
            "name": node["name"],
            "description": None,
            "childSectionCount": n_nodes,
            "subnetCount": n_active + node["raw"]["activeCount"],  # même contrat de champ que les autres modules
        })
    roots.sort(key=lambda r: (r["name"] or "").lower())

    import json as _json
    body = _json.dumps({"roots": roots})
    cache_set("zenoss:roots", body)
    return app.response_class(body, mimetype="application/json")


@app.route("/tree/<path:root_id>", methods=["GET"])
def get_tree(root_id):
    # Les ids réels sont "/App" (slash initial inclus, id canonique
    # du nœud) ; le front envoie la valeur SANS ce slash pour éviter
    # toute ambiguïté d'encodage de %2F selon la pile WSGI — on
    # renormalise ici plutôt que de dépendre d'une convention côté client.
    key_id = root_id if root_id.startswith("/") else f"/{root_id}"

    start = request.args.get("start", type=int)
    end = request.args.get("end", type=int)
    windowed = start is not None and end is not None

    cache_key = f"zenoss:tree:{key_id}"
    if not windowed:
        cached = cache_get(cache_key)
        if cached:
            return app.response_class(cached, mimetype="application/json")

    try:
        root_nodes, root_ids = load_forest(start if windowed else None, end if windowed else None)
    except Exception as exc:  # noqa: BLE001
        _log.debug("get_tree : base Zenoss injoignable -- %s", exc)
        return jsonify({"error": f"base Zenoss injoignable : {exc}"}), 503

    if key_id not in root_ids:
        return jsonify({"error": f"'{root_id}' n'est pas une racine indépendante connue"}), 404

    tree_node = root_nodes[key_id]
    try:
        date_bounds = load_date_bounds(collect_class_paths(tree_node))
    except Exception:  # noqa: BLE001
        date_bounds = None

    import json as _json
    body = _json.dumps({"tree": tree_node, "dateBounds": date_bounds})
    if not windowed:
        cache_set(cache_key, body)
    return app.response_class(body, mimetype="application/json")


@app.route("/device_location", methods=["GET"])
def get_device_location():
    """Localisation d'UN équipement précis (livraison #268, backlog
    item 31 -- "je dois aussi identifier les lieux d'intervention",
    volontairement différé en #253-254 : "structure en arbre côté
    Zenoss, pas de recherche directe par équipement"). Corrige ce
    point -- requête CIBLÉE plutôt qu'un parcours de tout l'arbre
    (voir `fetch_location_rows` : les colonnes `device`/`Location`/
    `ipAddress`/`Systems` sont DIRECTEMENT interrogeables, jamais
    besoin de construire l'arbre complet pour répondre à "où est CET
    équipement précis"). `device` (nom exact) OU `ip` (adresse IP
    exacte) -- au moins l'un des deux requis, recherche PAR L'UN OU
    L'AUTRE (jamais les deux combinés en ET, un appelant peut ne
    connaître que l'IP). `None` (jamais une erreur 404) si
    l'équipement n'apparaît dans AUCUN événement Zenoss connu -- un
    équipement peut légitimement ne jamais avoir généré d'événement,
    ce n'est pas une erreur de recherche."""
    device = (request.args.get("device") or "").strip()
    ip = (request.args.get("ip") or "").strip()
    if not device and not ip:
        return jsonify({"error": "'device' ou 'ip' requis"}), 400

    cache_key = f"zenoss:device_location:{device}:{ip}"
    cached = cache_get(cache_key)
    if cached:
        return app.response_class(cached, mimetype="application/json")

    conn = get_connection()
    try:
        cur = conn.cursor()
        if device and ip:
            rows = run_select(
                cur,
                "SELECT DISTINCT device, Location, ipAddress, Systems FROM history "
                "WHERE device = %s OR ipAddress = %s LIMIT 1",
                [device, ip],
            )
        elif device:
            rows = run_select(cur, "SELECT DISTINCT device, Location, ipAddress, Systems FROM history WHERE device = %s LIMIT 1", [device])
        else:
            rows = run_select(cur, "SELECT DISTINCT device, Location, ipAddress, Systems FROM history WHERE ipAddress = %s LIMIT 1", [ip])
    except Exception as exc:  # noqa: BLE001
        _log.debug("get_device_location : base Zenoss injoignable -- %s", exc)
        return jsonify({"error": f"base Zenoss injoignable : {exc}"}), 503
    finally:
        conn.close()

    result = {
        "device": rows[0]["device"], "location": rows[0]["Location"],
        "ip_address": rows[0]["ipAddress"], "systems": rows[0]["Systems"],
    } if rows else None

    import json as _json
    body = _json.dumps({"result": result})
    cache_set(cache_key, body)
    return app.response_class(body, mimetype="application/json")


@app.route("/location_roots", methods=["GET"])
def list_location_roots():
    """EXCEPTION délibérée et scopée (voir en-tête du module) :
    racines de l'inventaire physique (Location), pas de la
    classification d'événements. `subnetCount` réutilisé pour le
    nombre de devices cumulé — même contrat de champ que /roots."""
    ip_prefix = request.args.get("ip_prefix") or None
    cache_key = f"zenoss:location:roots:{ip_prefix or ''}"
    cached = cache_get(cache_key)
    if cached:
        return app.response_class(cached, mimetype="application/json")

    try:
        root_nodes, root_ids = load_location_forest(ip_prefix)
    except Exception as exc:  # noqa: BLE001
        _log.debug("list_location_roots : base Zenoss injoignable -- %s", exc)
        return jsonify({"error": f"base Zenoss injoignable : {exc}"}), 503

    roots = []
    for rid in root_ids:
        node = root_nodes[rid]
        n_nodes, n_devices = count_location_descendants(node)
        roots.append({
            "id": node["id"],
            "name": node["name"],
            "description": None,
            "childSectionCount": n_nodes,
            "subnetCount": n_devices,
        })
    roots.sort(key=lambda r: (r["name"] or "").lower())

    import json as _json
    body = _json.dumps({"roots": roots})
    cache_set(cache_key, body)
    return app.response_class(body, mimetype="application/json")


@app.route("/location_tree/<path:root_id>", methods=["GET"])
def get_location_tree(root_id):
    """Même convention d'id que /tree/<root_id> : le front envoie la
    valeur SANS le slash initial, renormalisé ici. Pas de fenêtre
    temporelle ici (Location n'est pas horodatée par ligne dans le
    besoin exprimé) — simplification délibérée pour cette v1."""
    key_id = root_id if root_id.startswith("/") else f"/{root_id}"
    ip_prefix = request.args.get("ip_prefix") or None

    cache_key = f"zenoss:location:tree:{key_id}:{ip_prefix or ''}"
    cached = cache_get(cache_key)
    if cached:
        return app.response_class(cached, mimetype="application/json")

    try:
        root_nodes, root_ids = load_location_forest(ip_prefix)
    except Exception as exc:  # noqa: BLE001
        _log.debug("get_location_tree : base Zenoss injoignable -- %s", exc)
        return jsonify({"error": f"base Zenoss injoignable : {exc}"}), 503

    if key_id not in root_ids:
        return jsonify({"error": f"'{root_id}' n'est pas une racine indépendante connue"}), 404

    tree_node = root_nodes[key_id]

    import json as _json
    body = _json.dumps({"tree": tree_node})
    cache_set(cache_key, body)
    return app.response_class(body, mimetype="application/json")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
