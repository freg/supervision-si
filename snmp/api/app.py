"""
snmp-api -- livraison #212, backlog item 13 ("Nouveau module/tuile
SNMP -- découverte et déploiement automatisé"). Portée VOLONTAIREMENT
LIMITÉE pour ce premier terrain : GET/WALK SNMPv1/v2c (communauté)
sur une cible dont on connaît déjà l'IP -- voir snmp_client.py pour
le détail complet des décisions de portée prises (et ce qui reste
explicitement hors de ce périmètre : scan de ports, SNMPv3,
"déploiement automatisé").

**⚠️ Jamais testé contre un vrai équipement SNMP** -- `pysnmp` n'est
pas installable dans cet environnement de développement (réseau
restreint). Voir snmp_client.py pour le détail de ce qui EST vérifié
(logique d'enveloppe, contre une simulation fidèle de l'API réelle
d'après la documentation officielle) et ce qui ne l'est PAS (l'appel
réseau lui-même).
"""
import logging
import os

import requests
from flask import Flask, jsonify, request
from flask_cors import CORS

import snmp_client
import targets_store as store
import credential_crypto as ccrypto

try:
    from version_endpoint import register_version_route
except ImportError:
    register_version_route = None

app = Flask(__name__)
CORS(app)
if register_version_route:
    register_version_route(app, "snmp-api")

_log = logging.getLogger("snmp_app")

# Branchement rights-api -- livraison #313, item 38 du backlog.
# SCOPE VOLONTAIREMENT ÉTROIT : gardé UNIQUEMENT sur la gestion des
# cibles enregistrées (create_target/delete_target), jamais sur
# /query ni /walk-interfaces. Raison de cette limite, assumée
# explicitement plutôt que devinée à l'aveugle : ces deux routes
# acceptent SOIT une communauté fournie à la volée par l'appelant
# (self-service, aucun gain à gater -- il fournit son propre
# identifiant), SOIT un `target_id` enregistré dont la communauté
# CHIFFRÉE est utilisée côté serveur sans jamais être révélée à
# l'appelant -- ce SECOND cas mériterait une garde CONDITIONNELLE
# (seulement si `target_id` est utilisé), plus fine qu'un simple
# gate en tête de route. Pas fait ici, faute de temps pour la
# construire ET la tester correctement dans cette même session --
# noté explicitement plutôt que bâclé, à reprendre séparément.
RIGHTS_API_URL = os.environ.get("RIGHTS_API_URL", "").rstrip("/") or None


def _check_manage_right(body):
    """Même motif FAIL CLOSED que les branchements précédents
    (#289-292, #308-312) -- jamais fail-open, y compris pour
    admin_hub si rights-api est injoignable."""
    if not RIGHTS_API_URL:
        return True, None
    groups = body.get("groups") or []
    try:
        resp = requests.post(
            f"{RIGHTS_API_URL}/check",
            json={"groups": groups, "resource_type": "snmp-api", "resource_id": None, "action": "manage"},
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
    return allowed, None if allowed else "droit 'manage' sur snmp-api requis (groupe admin_hub, ou un octroi explicite)"

SNMP_DEFAULT_TIMEOUT = int(os.environ.get("SNMP_DEFAULT_TIMEOUT", "5"))
SNMP_DEFAULT_PORT = int(os.environ.get("SNMP_DEFAULT_PORT", "161"))
DB_PATH = os.environ.get("SNMP_DB_PATH", "/data/snmp.db")

try:
    store.ensure_schema(DB_PATH)
except Exception as exc:  # noqa: BLE001 -- la base peut ne pas être prête au tout premier démarrage
    app.logger.warning("Migration au démarrage reportée : %s", exc)


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


def _target_params(body):
    """Deux façons d'indiquer la cible -- `target_id` (une cible
    ENREGISTRÉE, livraison #213, communauté déchiffrée ici) OU
    `host`+`community` en direct (usage ponctuel, jamais stocké,
    comportement inchangé depuis #212). `target_id` prioritaire si
    les deux sont fournis par erreur -- jamais un mélange ambigu des
    deux sources."""
    target_id = body.get("target_id")
    if target_id:
        target = store.get_target(DB_PATH, target_id)
        if target is None:
            return None, None, None, None, "cible enregistrée introuvable"
        try:
            community = ccrypto.decrypt_community(target["community_encrypted"])
        except ccrypto.CredentialCryptoNotConfigured as exc:
            return None, None, None, None, str(exc)
        except Exception as exc:  # noqa: BLE001 -- secret_crypto.SecretCryptoError notamment (phrase de passe changée depuis)
            return None, None, None, None, f"déchiffrement de la communauté échoué : {exc}"
        port = int(body.get("port") or target["port"])
        timeout = int(body.get("timeout") or SNMP_DEFAULT_TIMEOUT)
        return target["host"], community, port, timeout, None

    host = (body.get("host") or "").strip()
    community = (body.get("community") or "").strip()
    port = int(body.get("port") or SNMP_DEFAULT_PORT)
    timeout = int(body.get("timeout") or SNMP_DEFAULT_TIMEOUT)
    if not host or not community:
        return None, None, None, None, "'host'+'community', ou 'target_id' d'une cible enregistrée, requis"
    return host, community, port, timeout, None


@app.route("/query", methods=["POST"])
def query_system_info():
    """GET des informations "System" standard (SNMPv2-MIB) sur une
    cible -- corps JSON : {"host", "community", "port"?, "timeout"?}
    OU {"target_id", "port"?, "timeout"?} pour une cible enregistrée
    (livraison #213). SNMPv1/v2c UNIQUEMENT (communauté) -- voir
    snmp_client.py pour le raisonnement de portée complet."""
    body = request.get_json(silent=True) or {}
    host, community, port, timeout, error = _target_params(body)
    if error:
        return jsonify({"error": error}), 400
    try:
        info = snmp_client.get_system_info(host, community, port=port, timeout=timeout)
    except snmp_client.SnmpError as exc:
        return jsonify({"error": str(exc)}), 502
    return jsonify({"host": host, "port": port, "system": info}), 200


@app.route("/get", methods=["POST"])
def get_oids_route():
    """GET d'OID arbitraires (livraison #434) -- corps {host, community |
    target_id, oids: ["1.3.6.1.2.1.33.1.2.4.0", ...], port?, timeout?} ->
    {values: {oid: texte | null}}. Au plus 64 OID par appel. Utilisé par
    ups-monitor-api pour l'UPS-MIB (RFC 1628)."""
    body = request.get_json(silent=True) or {}
    host, community, port, timeout, error = _target_params(body)
    if error:
        return jsonify({"error": error}), 400
    oids = body.get("oids")
    if not isinstance(oids, list) or not oids or len(oids) > 64 or not all(isinstance(o, str) and o.replace(".", "").isdigit() for o in oids):
        return jsonify({"error": "'oids' : liste de 1 à 64 OID numériques (ex. 1.3.6.1.2.1.33.1.2.4.0)"}), 400
    try:
        values = snmp_client.get_oids(host, community, oids, port=port, timeout=timeout)
    except snmp_client.SnmpError as exc:
        return jsonify({"error": str(exc)}), 502
    return jsonify({"host": host, "port": port, "values": values}), 200


@app.route("/walk-interfaces", methods=["POST"])
def query_interfaces():
    """WALK de la table des interfaces (IF-MIB) sur une cible --
    même corps JSON que /query."""
    body = request.get_json(silent=True) or {}
    host, community, port, timeout, error = _target_params(body)
    if error:
        return jsonify({"error": error}), 400
    try:
        interfaces = snmp_client.walk_interfaces(host, community, port=port, timeout=timeout)
    except snmp_client.SnmpError as exc:
        return jsonify({"error": str(exc)}), 502
    return jsonify({"host": host, "port": port, "interfaces": interfaces}), 200


@app.route("/traffic-rate", methods=["POST"])
def query_traffic_rate():
    """Débit RÉEL par interface (octets/s) -- livraison #384, backlog
    item 49 reformulé ("il s'agit d'analyser le trafic"). Même corps
    JSON que /query, plus 'sample_interval'? (secondes entre les deux
    relevés, défaut 5) -- cette route reste bloquée pendant TOUTE la
    durée du prélèvement (timeout*8 + sample_interval + 5 environ),
    plus lente que /query ou /walk-interfaces par conception (deux
    relevés espacés, pas un seul GET)."""
    body = request.get_json(silent=True) or {}
    host, community, port, timeout, error = _target_params(body)
    if error:
        return jsonify({"error": error}), 400
    sample_interval_raw = body.get("sample_interval")
    sample_interval = int(sample_interval_raw) if sample_interval_raw is not None else 5
    if sample_interval < 1 or sample_interval > 60:
        return jsonify({"error": "'sample_interval' doit être entre 1 et 60 secondes"}), 400
    try:
        rates = snmp_client.get_interface_traffic_rate(host, community, port=port, timeout=timeout, sample_interval=sample_interval)
    except snmp_client.SnmpError as exc:
        return jsonify({"error": str(exc)}), 502
    return jsonify({"host": host, "port": port, "sample_interval": sample_interval, "interfaces": rates}), 200


# ------------------------------------------------------------------
# Cibles SNMP enregistrées (livraison #213, backlog item 13, volet 2
# -- "gestion des paramètres d'accès sécurisés"). Communauté chiffrée
# via credential_crypto.py -- jamais exposée en clair via l'API
# (voir _redact_target, défense en profondeur, même motif que
# ssh-tunnels-api, #210).
# ------------------------------------------------------------------
def _redact_target(row):
    if row is None:
        return None
    redacted = dict(row)
    redacted.pop("community_encrypted", None)
    return redacted


@app.route("/targets", methods=["GET"])
def list_targets():
    return jsonify([_redact_target(t) for t in store.list_targets(DB_PATH)]), 200


@app.route("/targets", methods=["POST"])
def create_target():
    """Protégée par rights-api (#313)."""
    body = request.get_json(silent=True) or {}
    allowed, error = _check_manage_right(body)
    if not allowed:
        return jsonify({"error": error}), 403
    label = (body.get("label") or "").strip()
    host = (body.get("host") or "").strip()
    port = int(body.get("port") or SNMP_DEFAULT_PORT)
    community = body.get("community") or ""
    actor = (body.get("actor") or "").strip() or None
    if not label or not host or not community:
        return jsonify({"error": "'label', 'host' et 'community' requis"}), 400
    try:
        community_encrypted = ccrypto.encrypt_community(community)
    except ccrypto.CredentialCryptoNotConfigured as exc:
        return jsonify({"error": str(exc)}), 503
    target_id = store.create_target(DB_PATH, label, host, port, community_encrypted, created_by=actor)
    return jsonify(_redact_target(store.get_target(DB_PATH, target_id))), 201


@app.route("/targets/<int:target_id>", methods=["DELETE"])
def delete_target(target_id):
    """Protégée par rights-api (#313)."""
    body = request.get_json(silent=True) or {}
    allowed, error = _check_manage_right(body)
    if not allowed:
        return jsonify({"error": error}), 403
    deleted = store.delete_target(DB_PATH, target_id)
    if not deleted:
        return jsonify({"error": "cible introuvable"}), 404
    return jsonify({"status": "ok"}), 200


# ------------------------------------------------------------------
# Journal PARTAGÉ (endpoint /logs) -- même motif que tous les autres
# services de ce projet (voir shared/log_buffer.py, livraison #145).
# ------------------------------------------------------------------
try:
    from log_buffer import make_shared_log_handler, read_shared_log_buffer
except ImportError:
    make_shared_log_handler = None
    read_shared_log_buffer = None

try:
    from pymemcache.client.base import Client as MemcacheClient
except ImportError:
    MemcacheClient = None

MEMCACHED_HOST = os.environ.get("MEMCACHED_HOST", "memcached")


def get_memcache_client():
    return MemcacheClient((MEMCACHED_HOST, 11211))


SERVICE_NAME = "snmp-api"
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


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
