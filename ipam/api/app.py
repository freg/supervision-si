"""
API IPAM — expose en LECTURE SEULE la base MySQL de l'application
phpipam existante (externe à ce projet, hébergée sur l'infrastructure
de la personne) pour alimenter l'onglet IPAM du frontend : racines
indépendantes, arbre radial, vue JSON d'un nœud.

Garantie de lecture seule (défense en profondeur, trois niveaux) :
  1. Aucune route POST/PUT/DELETE n'existe dans ce fichier.
  2. Toute requête SQL passe par run_select(), qui refuse tout texte
     ne commençant pas par SELECT.
  3. Le compte MySQL utilisé doit lui-même n'avoir QUE le privilège
     SELECT côté serveur (GRANT SELECT ON phpipam.* — voir README) :
     c'est la garantie qui compte vraiment, l'appli ne doit jamais en
     être le seul rempart.

Colonnes exposées délibérément restreintes : ni `permissions` (ACL
JSON interne à phpipam), ni les tables d'authentification/comptes
(`users`, `settings*`) ne sont lues ici — seules les tables qui
composent la hiérarchie IPAM elle-même le sont.
"""
import ipaddress
import os
import re
import time

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

app = Flask(__name__)
CORS(app)
if register_version_route:
    register_version_route(app, "ipam-api")

DB_HOST = os.environ.get("IPAM_DB_HOST", "")
DB_PORT = int(os.environ.get("IPAM_DB_PORT", "3306"))
DB_NAME = os.environ.get("IPAM_DB_NAME", "phpipam")
DB_USER = os.environ.get("IPAM_DB_USER", "")
DB_PASSWORD = os.environ.get("IPAM_DB_PASSWORD", "")
DB_SSL = os.environ.get("IPAM_DB_SSL", "false").lower() == "true"

CACHE_TTL = int(os.environ.get("IPAM_CACHE_TTL", "60"))
MEMCACHED_HOST = os.environ.get("MEMCACHED_HOST", "memcached")
MEMCACHED_PORT = int(os.environ.get("MEMCACHED_PORT", "11211"))


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
        raise RuntimeError("IPAM_DB_HOST / IPAM_DB_USER non configurés (voir ipam/README.md)")
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
            cursorclass=pymysql.cursors.DictCursor,
            connect_timeout=5,
            read_timeout=15,
            ssl={"ssl": {}} if DB_SSL else None,
            autocommit=False,  # jamais de commit dans ce fichier — voir garanties ci-dessus
        )
    except Exception as exc:
        elapsed_ms = int((time.monotonic() - start) * 1000)
        app.logger.debug("get_connection : ÉCHEC après %d ms -- %s", elapsed_ms, exc)
        raise
    elapsed_ms = int((time.monotonic() - start) * 1000)
    app.logger.debug("get_connection : succès en %d ms", elapsed_ms)
    return conn


def run_select(cur, sql, params=None):
    """Garde-fou : n'exécute que des requêtes commençant par SELECT."""
    if not sql.strip().upper().startswith("SELECT"):
        raise ValueError("run_select() n'accepte que des requêtes SELECT")
    cur.execute(sql, params or [])
    return cur.fetchall()


# ------------------------------------------------------------------
# Assemblage de l'arbre — fonctions PURES (aucun accès DB ici), donc
# testables directement avec des jeux de lignes construits à la main.
# ------------------------------------------------------------------

def to_epoch_seconds(value):
    """MySQL TIMESTAMP revient via pymysql comme datetime.datetime (jamais
    directement sérialisable en JSON) — converti en epoch secondes ; None
    reste None (colonne editDate nullable : jamais modifié depuis
    création). Défensif face à une valeur déjà numérique (au cas où)."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value)
    return int(value.timestamp())


def format_subnet_address(raw_subnet):
    """phpipam stocke `subnets.subnet` comme un entier 32 bits non
    signé (convention historique INET_ATON — confirmé en conditions
    réelles : 175374352 correspond exactement à 10.116.0.16, borne du
    /28 contenant 10.116.0.23 dans une capture d'écran fournie par la
    personne). Convertit en notation pointée standard pour l'affichage
    ("subnet/mask"). Défensif : si la valeur est déjà une chaîne
    (schéma différent, ou déjà convertie en amont), la renvoie telle
    quelle plutôt que de la corrompre — ne lève jamais, une valeur
    vraiment inattendue retombe sur sa représentation brute plutôt que
    de faire échouer tout l'arbre ou /ip_list pour une seule ligne."""
    if isinstance(raw_subnet, str):
        return raw_subnet
    try:
        return str(ipaddress.IPv4Address(int(raw_subnet)))
    except (TypeError, ValueError, ipaddress.AddressValueError):
        return str(raw_subnet)


def build_forest(sections, subnets, ip_counts):
    """
    sections : lignes {id, name, description, masterSection, order}
    subnets  : lignes {id, subnet, mask, sectionId, description,
                        masterSubnetId, isFolder, vlanId, vlanName,
                        vrfId, vrfName, allowRequests, state}
    ip_counts: {subnetId: count}

    Retourne (section_nodes, root_ids) :
      - section_nodes : {id: node} pour TOUTES les sections, nœuds
        entièrement reliés (children peuplés, sous-arbres inclus).
      - root_ids : ids des sections racines indépendantes (masterSection
        absent/0/pointant vers une section inexistante).

    Défensif par construction : une donnée réelle peut être incohérente
    (id parent absent, cycle) — on ne perd jamais silencieusement un
    nœud, et un cycle est coupé plutôt que de boucler indéfiniment (le
    nœud qui refermerait le cycle redevient racine, marqué `cycle`).
    """
    subnet_nodes = {}
    for row in subnets:
        sid = row["id"]
        ip_count = ip_counts.get(sid, 0)
        subnet_nodes[sid] = {
            "id": sid,
            "type": "subnet",
            "name": f"{format_subnet_address(row['subnet'])}/{row['mask']}" if row.get("mask") else format_subnet_address(row["subnet"]),
            "children": [],
            "_masterSubnetId": row.get("masterSubnetId") or 0,
            "_sectionId": row.get("sectionId"),
            "raw": {
                "id": sid,
                "subnet": row.get("subnet"),
                "mask": row.get("mask"),
                "sectionId": row.get("sectionId"),
                "description": row.get("description"),
                "masterSubnetId": row.get("masterSubnetId") or 0,
                "isFolder": bool(row.get("isFolder")),
                "allowRequests": bool(row.get("allowRequests")),
                "state": row.get("state"),
                "vlanId": row.get("vlanId"),
                "vlanName": row.get("vlanName"),
                "vrfId": row.get("vrfId"),
                "vrfName": row.get("vrfName"),
                "ipCount": ip_count,
                "editDate": to_epoch_seconds(row.get("editDate")),
            },
        }

    # Rattache chaque subnet à son parent (subnet ou section), en coupant
    # les cycles éventuels.
    subnet_root_of_section = {}  # sectionId -> [subnet_node, ...]
    for sid, node in subnet_nodes.items():
        parent_id = node["_masterSubnetId"]
        if parent_id and parent_id in subnet_nodes and parent_id != sid:
            # Détection de cycle : remonter les parents jusqu'à la racine ;
            # si on retombe sur sid, le lien est cassé ici.
            seen, cursor = {sid}, parent_id
            is_cycle = False
            for _ in range(len(subnet_nodes) + 1):
                if cursor == sid:
                    is_cycle = True
                    break
                if cursor in seen:
                    break
                seen.add(cursor)
                cursor = subnet_nodes.get(cursor, {}).get("_masterSubnetId") or 0
                if not cursor or cursor not in subnet_nodes:
                    break
            if is_cycle:
                node["raw"]["cycle"] = True
                subnet_root_of_section.setdefault(node["_sectionId"], []).append(node)
            else:
                subnet_nodes[parent_id]["children"].append(node)
        else:
            subnet_root_of_section.setdefault(node["_sectionId"], []).append(node)

    section_nodes = {}
    for row in sections:
        section_id = row["id"]
        section_nodes[section_id] = {
            "id": section_id,
            "type": "section",
            "name": row["name"],
            "children": [],
            "_masterSection": row.get("masterSection") or 0,
            "raw": {
                "id": section_id,
                "name": row.get("name"),
                "description": row.get("description"),
                "masterSection": row.get("masterSection") or 0,
                "order": row.get("order"),
                "editDate": to_epoch_seconds(row.get("editDate")),
            },
        }

    root_ids = []
    for section_id, node in section_nodes.items():
        parent_id = node["_masterSection"]
        if parent_id and parent_id in section_nodes and parent_id != section_id:
            seen, cursor = {section_id}, parent_id
            is_cycle = False
            for _ in range(len(section_nodes) + 1):
                if cursor == section_id:
                    is_cycle = True
                    break
                if cursor in seen:
                    break
                seen.add(cursor)
                cursor = section_nodes.get(cursor, {}).get("_masterSection") or 0
                if not cursor or cursor not in section_nodes:
                    break
            if is_cycle:
                node["raw"]["cycle"] = True
                root_ids.append(section_id)
            else:
                section_nodes[parent_id]["children"].append(node)
        else:
            root_ids.append(section_id)

    # Attache enfin, sous chaque section, ses subnets racines (après les
    # éventuelles sous-sections, pour un ordre stable et prévisible).
    for section_id, node in section_nodes.items():
        node["children"].extend(subnet_root_of_section.get(section_id, []))

    # Subnets dont la sectionId ne correspond à aucune section connue
    # (donnée orpheline) : jamais perdus silencieusement — rattachés
    # sous une racine synthétique dédiée plutôt qu'ignorés.
    orphan_section_ids = set(subnet_root_of_section) - set(section_nodes) - {None}
    if orphan_section_ids:
        orphan_children = []
        for orphan_sid in sorted(orphan_section_ids, key=str):
            orphan_children.extend(subnet_root_of_section[orphan_sid])
        section_nodes["_orphans"] = {
            "id": "_orphans",
            "type": "section",
            "name": "⚠️ Sous-réseaux sans section valide",
            "children": orphan_children,
            "raw": {"note": "sectionId ne correspond à aucune section existante"},
        }
        root_ids.append("_orphans")

    return section_nodes, root_ids


def count_descendants(node):
    """(nb sections descendantes, nb subnets descendants), racine exclue."""
    sections = subnets = 0
    for child in node["children"]:
        if child["type"] == "section":
            sections += 1
        else:
            subnets += 1
        cs, cn = count_descendants(child)
        sections += cs
        subnets += cn
    return sections, subnets


def strip_internal_fields(node):
    """Copie publique d'un nœud : retire les clés internes _* utilisées
    seulement pendant l'assemblage (_masterSubnetId, _masterSection, _sectionId)."""
    return {
        "id": node["id"],
        "type": node["type"],
        "name": node["name"],
        "raw": node["raw"],
        "children": [strip_internal_fields(c) for c in node["children"]],
    }


# ------------------------------------------------------------------
# Accès DB — SELECT uniquement, colonnes volontairement restreintes.
# ------------------------------------------------------------------

_IPV4_DOTTED_RE = re.compile(r"^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$")


def normalize_ip_addr(raw_value):
    """phpipam a historiquement stocké `ipaddresses.ip_addr` soit en
    notation pointée ('10.0.0.1'), soit en entier décimal encodant
    l'IPv4 sur 32 bits ('167772161'), selon la version — JAMAIS vérifié
    en conditions réelles depuis cet environnement (voir
    ipam/README.md, section Fusion IP/MAC). Normalise vers la notation
    pointée dans les deux cas ; une valeur qui ne correspond à aucun
    des deux formats (IPv6, valeur corrompue...) est renvoyée TELLE
    QUELLE plutôt que de planter — elle ne participera simplement pas
    à la corrélation par égalité de chaîne."""
    if raw_value is None:
        return None
    s = str(raw_value).strip()
    if not s:
        return None
    if _IPV4_DOTTED_RE.match(s):
        return s
    if s.isdigit():
        n = int(s)
        if 0 <= n <= 0xFFFFFFFF:
            return f"{(n >> 24) & 0xFF}.{(n >> 16) & 0xFF}.{(n >> 8) & 0xFF}.{n & 0xFF}"
    return s


def normalize_mac(raw_value):
    """Uniformise vers XX:XX:XX:XX:XX:XX (majuscules) quelle que soit la
    ponctuation d'origine (tirets, points Cisco, aucune). Une valeur
    qui n'a pas 12 chiffres hexadécimaux est renvoyée telle quelle
    (jamais silencieusement perdue) ; None/vide reste None."""
    if not raw_value:
        return None
    hex_only = re.sub(r"[^0-9a-fA-F]", "", str(raw_value))
    if len(hex_only) != 12:
        cleaned = str(raw_value).strip()
        return cleaned or None
    pairs = [hex_only[i:i + 2] for i in range(0, 12, 2)]
    return ":".join(pairs).upper()


def build_ip_entries(rows):
    """Fonction pure — transforme les lignes SQL brutes de
    fetch_ip_addresses() en entrées normalisées pour /ip_list. Une
    ligne sans ip_addr exploitable est silencieusement écartée (rien à
    corréler), toutes les autres sont gardées même sans MAC ni nom
    d'hôte (l'IP seule reste une clé de corrélation valide)."""
    entries = []
    for row in rows:
        ip = normalize_ip_addr(row.get("ip_addr"))
        if not ip:
            continue
        entries.append({
            "id": row["id"],
            "ip": ip,
            "mac": normalize_mac(row.get("mac")),
            "hostname": row.get("dns_name") or None,
            "description": row.get("description") or None,
            "subnet": f"{format_subnet_address(row['subnet'])}/{row['mask']}" if row.get("subnet") else None,
            "sectionId": row.get("sectionId"),
            "state": row.get("state"),
        })
    return entries


def fetch_sections(cur):
    return run_select(cur, "SELECT id, name, description, masterSection, `order`, editDate FROM sections")


def fetch_subnets(cur):
    return run_select(
        cur,
        """SELECT s.id, s.subnet, s.mask, s.sectionId, s.description,
                  s.masterSubnetId, s.isFolder, s.allowRequests, s.state, s.editDate,
                  s.vlanId, v.name AS vlanName, s.vrfId, r.name AS vrfName
           FROM subnets s
           LEFT JOIN vlans v ON v.vlanId = s.vlanId
           LEFT JOIN vrf r ON r.vrfId = s.vrfId""",
    )


def fetch_ip_counts(cur):
    rows = run_select(cur, "SELECT subnetId, COUNT(*) AS n FROM ipaddresses GROUP BY subnetId")
    return {row["subnetId"]: row["n"] for row in rows if row["subnetId"] is not None}


def fetch_ip_addresses(cur):
    """Adresses individuelles avec contexte subnet — pour la
    corrélation Fusion IP/MAC (voir README). Colonnes volontairement
    restreintes : ni `owner`, ni `note` (texte libre), ni les champs
    d'administration système (`custom_Serial`, `Login_PPPoE`,
    `switch`/`port`, `firewallAddressObject`) ne sont lus ici."""
    return run_select(
        cur,
        """SELECT ia.id, ia.ip_addr, ia.mac, ia.dns_name, ia.description,
                  ia.subnetId, ia.state, s.subnet, s.mask, s.sectionId
           FROM ipaddresses ia
           LEFT JOIN subnets s ON s.id = ia.subnetId""",
    )


def load_forest():
    conn = get_connection()
    try:
        cur = conn.cursor()
        sections = fetch_sections(cur)
        subnets = fetch_subnets(cur)
        ip_counts = fetch_ip_counts(cur)
        return build_forest(sections, subnets, ip_counts)
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

SERVICE_NAME = "ipam-api"
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
    except Exception as exc:  # noqa: BLE001 — l'appelant a juste besoin de savoir "up ou pas"
        return jsonify({"status": "degraded", "db": "unreachable", "error": str(exc)}), 200


def summarize_subnet_states(state_counts):
    """Fonction pure — transforme {state: n} (convention phpipam :
    0=hors ligne, 1=en ligne/actif, 2=non surveillé) en un résumé
    exploitable par un panneau d'aperçu. unmonitoredCount = total -
    actifs - hors ligne : couvre state=2 ET toute valeur inattendue
    (donnée réelle imprévue), jamais silencieusement ignorée."""
    active = state_counts.get(1, 0)
    offline = state_counts.get(0, 0)
    total = sum(state_counts.values())
    return {
        "subnetCount": total,
        "activeCount": active,
        "offlineCount": offline,
        "unmonitoredCount": total - active - offline,
    }


@app.route("/stats", methods=["GET"])
def stats():
    """Résumé global (comptages seulement, pas d'arbre) — pensé pour un
    panneau d'aperçu léger appelé directement depuis un autre onglet du
    frontend (ex. la vue générale), sans jamais passer par un import ou
    un service intermédiaire : juste une requête HTTP de plus vers ce
    service, comme depuis l'onglet IPAM lui-même."""
    cached = cache_get("ipam:stats")
    if cached:
        return app.response_class(cached, mimetype="application/json")

    try:
        conn = get_connection()
        try:
            cur = conn.cursor()
            section_count = run_select(cur, "SELECT COUNT(*) AS n FROM sections")[0]["n"]
            state_rows = run_select(cur, "SELECT state, COUNT(*) AS n FROM subnets GROUP BY state")
        finally:
            conn.close()
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": f"base IPAM injoignable : {exc}"}), 503

    state_counts = {row["state"]: row["n"] for row in state_rows}
    summary = summarize_subnet_states(state_counts)
    summary["sectionCount"] = section_count

    import json as _json
    body = _json.dumps(summary)
    cache_set("ipam:stats", body)
    return app.response_class(body, mimetype="application/json")


@app.route("/ip_list", methods=["GET"])
def ip_list():
    """Liste plate des adresses IP connues (ip, mac, hostname,
    contexte subnet) — pour l'onglet Fusion IP/MAC, qui la combine
    CÔTÉ NAVIGATEUR avec l'équivalent d'autres sources (aucun service
    intermédiaire, aucune copie de données — voir la doc du module
    fusion)."""
    cached = cache_get("ipam:ip_list")
    if cached:
        return app.response_class(cached, mimetype="application/json")

    try:
        conn = get_connection()
        try:
            cur = conn.cursor()
            rows = fetch_ip_addresses(cur)
        finally:
            conn.close()
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": f"base IPAM injoignable : {exc}"}), 503

    entries = build_ip_entries(rows)

    import json as _json
    body = _json.dumps({"entries": entries})
    cache_set("ipam:ip_list", body)
    return app.response_class(body, mimetype="application/json")


@app.route("/roots", methods=["GET"])
def list_roots():
    """Racines indépendantes (sections de tête) — panneau de gauche."""
    cached = cache_get("ipam:roots")
    if cached:
        return app.response_class(cached, mimetype="application/json")

    try:
        section_nodes, root_ids = load_forest()
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": f"base IPAM injoignable : {exc}"}), 503

    roots = []
    for rid in root_ids:
        node = section_nodes[rid]
        n_sections, n_subnets = count_descendants(node)
        roots.append({
            "id": node["id"],
            "name": node["name"],
            "description": node["raw"].get("description"),
            "childSectionCount": n_sections,
            "subnetCount": n_subnets,
        })
    roots.sort(key=lambda r: (r["name"] or "").lower())

    import json as _json
    body = _json.dumps({"roots": roots})
    cache_set("ipam:roots", body)
    return app.response_class(body, mimetype="application/json")


@app.route("/tree/<path:root_id>", methods=["GET"])
def get_tree(root_id):
    """Arbre complet enraciné à une section — panneau central."""
    # Les ids réels sont numériques ; "_orphans" est la seule racine
    # textuelle possible (voir build_forest) — pas de conversion forcée
    # en int pour ne pas la casser.
    key_id = int(root_id) if root_id.lstrip("-").isdigit() else root_id

    cache_key = f"ipam:tree:{key_id}"
    cached = cache_get(cache_key)
    if cached:
        return app.response_class(cached, mimetype="application/json")

    try:
        section_nodes, root_ids = load_forest()
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": f"base IPAM injoignable : {exc}"}), 503

    if key_id not in root_ids:
        return jsonify({"error": f"'{root_id}' n'est pas une racine indépendante connue"}), 404

    import json as _json
    body = _json.dumps({"tree": strip_internal_fields(section_nodes[key_id])})
    cache_set(cache_key, body)
    return app.response_class(body, mimetype="application/json")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
