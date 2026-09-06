"""
ssh-tunnels -- supervision de tunnels SSH et partages SSHFS
(livraison #159, backlog BACKLOG.md #2 ; montage SSHFS réel livré en
#180). Demandé explicitement : superviser les tunnels SSH et
partages SSHFS présents, gérer les clés (activer/désactiver/
informer), une interface de montage/démontage -- objectif : accès à
des ressources privées distantes (service redistribué en mode proxy
type rinetd/proxy-delegated, ou système de fichiers distant).

Trois points tranchés avec la personne avant de coder (voir
tunnels_store.py pour le détail) : clés = chemin protégé paramétré
(jamais générées/stockées ici) ; SSHFS = interface préparée d'abord
(#159), ACTION RÉELLE ensuite (#180, demandé explicitement -- "j'en
ai besoin pour concevoir la suite") ; mode proxy confirmé (ce
conteneur ouvre le port local, les autres API s'y connectent
directement par son nom Docker).

**Montage SSHFS (#180)** : `local_mount_path` est un NOM RELATIF
(jamais un chemin absolu) -- résolu et restreint à
`SSH_MOUNTS_BASE_DIR` (voir `_resolve_mount_path` ci-dessous), même
motif de sécurité que `SSH_KEYS_DIR`/`LOG_FILES_HOST_DIR` ailleurs
dans ce projet -- protection contre une traversée de chemin
(`../../etc`), jamais un accès libre au système de fichiers du
conteneur. **⚠️ Non vérifié contre un VRAI `sshfs`** -- réseau
restreint dans cet environnement, le binaire n'est pas installable
(même limitation déjà documentée pour `ssh`/`ssh-keygen`) --
`fusermount` en revanche EST présent et le démontage a été testé
contre le vrai binaire, voir `mount_process.py` et
`ssh-tunnels/README.md`.

Un SEUL worker Gunicorn pour ce service (voir Dockerfile) --
décision assumée : gérer de VRAIS processus OS (PID stocké en base,
récolté via SIGCHLD, voir tunnel_process.py) ne se prête PAS au même
partage via Memcached que des tampons de logs (livraison #145) --
plus simple et plus sûr de garder un seul processus responsable de
tous les sous-processus ssh/sshfs qu'il lance.
"""
import logging
import os

from flask import Flask, jsonify, request
from flask_cors import CORS
import requests

import tunnels_store as store
import key_scanner
import tunnel_process as tproc
import mount_process as mproc
import credential_crypto as ccrypto

_log = logging.getLogger("ssh_tunnels_app")


def _check_manage_right(body):
    """Livraison #289 -- vérifie le droit "manage" sur la ressource
    globale "ssh-tunnels-api" auprès de rights-api (#283), avant
    toute action sensible (génération/suppression de clé, connexion,
    tunnel, montage). `groups` transmis dans le corps de la requête
    par le hub (même convention que rights-api lui-même) -- ce
    service ne décode JAMAIS de jeton lui-même.

    Renvoie (True, None) si autorisé, (False, message_erreur) sinon.
    -- DÉSACTIVÉ (toujours autorisé) si RIGHTS_API_URL n'est pas
    configurée, pour un déploiement où rights-api n'existe pas encore
    -- jamais un service qui casse silencieusement de ce fait."""
    if not RIGHTS_API_URL:
        return True, None
    groups = body.get("groups") or []
    try:
        resp = requests.post(
            f"{RIGHTS_API_URL}/check",
            json={"groups": groups, "resource_type": "ssh-tunnels-api", "resource_id": None, "action": "manage"},
            timeout=5,
        )
    except requests.RequestException as exc:
        # rights-api injoignable -- FAIL CLOSED (refuse), jamais
        # fail-open sur un service qui gère des clés SSH réelles.
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
    return allowed, None if allowed else "droit 'manage' sur ssh-tunnels-api requis (groupe admin_hub, ou un octroi explicite)"

try:
    from version_endpoint import register_version_route
except ImportError:
    register_version_route = None

app = Flask(__name__)
CORS(app)
if register_version_route:
    register_version_route(app, "ssh-tunnels")

DB_PATH = os.environ.get("SSH_TUNNELS_DB_PATH", "/data/ssh-tunnels.db")
# Livraison #289 -- premier branchement réel de rights-api (#283)
# sur un service existant, suite à "la gestion des droits... impacte
# toutes les api" (backlog item 38). Service SANS son propre modèle
# d'accès (contrairement à vault-api, qui a déjà un contrôle d'accès
# CRYPTOGRAPHIQUE par utilisateur, propos délibérément écarté comme
# premier candidat pour ne pas faire doublon) -- candidat sensible
# choisi comme prévu (clés SSH, génération/suppression réelle depuis
# #277). Optionnel : RIGHTS_API_URL absente = gating DÉSACTIVÉ
# (comportement identique à avant #289, jamais un service qui casse
# silencieusement si rights-api n'est pas encore déployé).
RIGHTS_API_URL = os.environ.get("RIGHTS_API_URL", "").rstrip("/") or None
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
store.ensure_schema(DB_PATH)

# Chemin PROTÉGÉ PARAMÉTRÉ (monté en LECTURE SEULE) -- voir
# key_scanner.py, décidé explicitement avec la personne.
SSH_KEYS_DIR = os.environ.get("SSH_KEYS_DIR", "/keys")

# Base des points de montage SSHFS (livraison #180) -- TOUS les
# montages vivent SOUS ce répertoire, jamais ailleurs sur le disque
# du conteneur (voir _resolve_mount_path). Créé au démarrage s'il
# n'existe pas encore -- premier déploiement, avant que le volume
# hôte associé (SSH_TUNNELS_MOUNTS_DIR, docker-compose.yml) n'ait
# jamais rien contenu.
SSH_MOUNTS_BASE_DIR = os.environ.get("SSH_MOUNTS_BASE_DIR", "/mounts")
os.makedirs(SSH_MOUNTS_BASE_DIR, exist_ok=True)

# Récolteur de zombies -- voir tunnel_process.py, installé UNE SEULE
# FOIS ici, au niveau module (donc au premier import, avant que
# Gunicorn ne commence à servir des requêtes) -- couvre AUSSI les
# processus sshfs (mount_process.py réutilise is_process_alive de
# tunnel_process.py, jamais un second récolteur dupliqué).
tproc.install_reaper()


def _key_path(filename):
    return os.path.join(SSH_KEYS_DIR, filename)


def _resolve_mount_path(relative_name):
    """Résout `relative_name` À L'INTÉRIEUR de `SSH_MOUNTS_BASE_DIR`
    -- renvoie None si le résultat en sortirait (chemin absolu fourni,
    ou traversée via `..`) -- même motif exact que
    `prefs-api/file_source_poller._resolve_safe_path` (#176),
    dupliqué ici plutôt qu'importé : chaque service de ce projet reste
    autonome, sans dépendance croisée entre conteneurs pour un
    utilitaire aussi court. `os.path.realpath` sur les DEUX (base et
    candidat) avant comparaison -- résout aussi les liens symboliques,
    jamais contournable par ce biais."""
    if not relative_name or relative_name.startswith("/") or relative_name.startswith("\\"):
        return None
    candidate = os.path.normpath(os.path.join(SSH_MOUNTS_BASE_DIR, relative_name))
    base_real = os.path.realpath(SSH_MOUNTS_BASE_DIR)
    candidate_real = os.path.realpath(candidate)
    if candidate_real != base_real and not candidate_real.startswith(base_real + os.sep):
        return None
    return candidate_real


def _reconcile_tunnel(tunnel):
    """Si un tunnel est marqué "running" en base mais que son
    processus a disparu (crash, réseau coupé, hôte distant redémarré
    -- PAS forcément arrêté via /stop), corrige son statut ICI, à la
    LECTURE -- jamais besoin d'un sondage périodique séparé pour
    rester à jour, juste vérifié à chaque fois qu'on regarde ce
    tunnel."""
    if tunnel["status"] == "running" and not tproc.is_process_alive(tunnel["pid"]):
        store.update_tunnel_state(DB_PATH, tunnel["id"], "stopped", pid=None, last_error="processus disparu (arrêté en dehors de ce service)")
        tunnel = store.get_tunnel(DB_PATH, tunnel["id"])
    return tunnel


def _reconcile_mount(mount):
    """Même raisonnement que _reconcile_tunnel ci-dessus, appliqué
    aux montages SSHFS (livraison #180)."""
    if mount["status"] == "mounted" and not tproc.is_process_alive(mount["pid"]):
        store.update_mount_state(DB_PATH, mount["id"], "unmounted", pid=None, last_error="processus disparu (démonté en dehors de ce service)")
        mount = store.get_mount(DB_PATH, mount["id"])
    return mount


# ------------------------------------------------------------------
# Clés SSH
# ------------------------------------------------------------------
@app.route("/keys", methods=["GET"])
def list_keys():
    """Rescanne SSH_KEYS_DIR à CHAQUE appel (jamais un cache
    périmé) -- enregistre les nouvelles, retire celles disparues du
    disque, renvoie la liste avec empreinte/type calculés en direct
    (best-effort, None si `ssh-keygen` échoue -- voir key_scanner.py)."""
    filenames = key_scanner.scan_key_files(SSH_KEYS_DIR)
    for filename in filenames:
        store.upsert_key(DB_PATH, filename)
    store.remove_keys_not_in(DB_PATH, filenames)

    keys = store.list_keys(DB_PATH)
    for k in keys:
        info = key_scanner.get_key_fingerprint(SSH_KEYS_DIR, k["filename"])
        k["fingerprint"] = info["fingerprint"] if info else None
        k["key_type"] = info["key_type"] if info else None
    return jsonify(keys), 200


@app.route("/keys/<int:key_id>", methods=["PUT"])
def update_key(key_id):
    """Corps JSON : {"enabled": bool} et/ou {"label": str}."""
    if store.get_key(DB_PATH, key_id) is None:
        return jsonify({"error": "clé introuvable"}), 404
    body = request.get_json(silent=True) or {}
    if "enabled" in body:
        store.set_key_enabled(DB_PATH, key_id, bool(body["enabled"]))
    return jsonify(store.get_key(DB_PATH, key_id)), 200


@app.route("/keys/<int:key_id>", methods=["DELETE"])
def delete_key(key_id):
    """Suppression RÉELLE (livraison #277, demandé explicitement --
    "permettre la suppression des clés ssh sans aucune sauvegarde
    surtout") -- fichier ET registre, AUCUNE copie conservée nulle
    part, contrairement au reste de ce projet qui tend plutôt vers
    la prudence (versionnement LDIF, coffre-fort...) -- ici la
    personne veut explicitement l'inverse.

    ⚠️ Nécessite `SSH_KEYS_DIR` monté en LECTURE-ÉCRITURE -- décision
    prise EXPLICITEMENT avec la personne (2026-09-04), inversant le
    choix initial de #159 ("ce service ne génère ni ne stocke jamais
    de clé lui-même") -- un vrai changement de posture sécurité pour
    ce service, confirmé avant d'écrire cette route.

    Refuse si la clé est encore RÉFÉRENCÉE par une connexion (jamais
    la demande de "sans sauvegarde" ne portait sur l'absence de
    vérification de sécurité élémentaire -- supprimer le fichier
    d'une clé activement utilisée casserait cette connexion sans
    prévenir). Ordre délibéré : fichier supprimé D'ABORD, registre
    ENSUITE -- un échec de suppression du fichier laisse la clé
    encore visible plutôt qu'un registre incohérent."""
    body = request.get_json(silent=True) or {}
    allowed, error = _check_manage_right(body)
    if not allowed:
        return jsonify({"error": error}), 403

    key = store.get_key(DB_PATH, key_id)
    if key is None:
        return jsonify({"error": "clé introuvable"}), 404

    in_use = store.connections_using_key(DB_PATH, key_id)
    if in_use:
        labels = ", ".join(c["label"] for c in in_use)
        _log.debug("delete_key : refusé, clé %s encore référencée par %d connexion(s) -- %s", key_id, len(in_use), labels)
        return jsonify({"error": f"clé encore utilisée par {len(in_use)} connexion(s) : {labels} -- retirez-les d'abord"}), 409

    key_path = _key_path(key["filename"])
    try:
        os.remove(key_path)
    except FileNotFoundError:
        _log.debug("delete_key : fichier déjà absent (%s), poursuite -- registre à nettoyer malgré tout", key_path)
    except OSError as exc:
        _log.debug("delete_key : échec de suppression du fichier %s -- %s", key_path, exc)
        return jsonify({"error": f"suppression du fichier échouée : {exc}"}), 500

    # Fichier public (.pub) associé -- supprimé en best-effort, jamais
    # bloquant si absent (une clé peut avoir été déposée sans .pub).
    try:
        os.remove(key_path + ".pub")
    except OSError:
        pass

    store.delete_key_registry(DB_PATH, key_id)
    return jsonify({"status": "ok", "deleted": True}), 200


@app.route("/keys/generate", methods=["POST"])
def generate_key():
    """Génère une NOUVELLE paire de clés (livraison #277, demandé
    explicitement -- "permettre de générer des clés sans passphrase
    ou avec"). Corps JSON : {"filename", "passphrase" (optionnel,
    défaut ""), "key_type" (optionnel, défaut "ed25519")}.

    ⚠️ Même exigence de montage lecture-écriture que DELETE
    ci-dessus -- voir key_scanner.generate_key pour le détail complet
    (limite assumée sur l'exposition transitoire de la passphrase
    via `-N`, aucune alternative par variable d'environnement
    n'existe côté `ssh-keygen`).

    N'écrit PAS directement dans le registre -- le prochain appel à
    GET /keys (déjà un rescan systématique, voir `list_keys`) la
    détecte et l'enregistre automatiquement, aucune logique
    d'enregistrement dupliquée ici."""
    body = request.get_json(silent=True) or {}
    allowed, error = _check_manage_right(body)
    if not allowed:
        return jsonify({"error": error}), 403

    filename = (body.get("filename") or "").strip()
    if not filename:
        return jsonify({"error": "'filename' requis"}), 400
    passphrase = body.get("passphrase", "")
    key_type = body.get("key_type", "ed25519")

    ok, error = key_scanner.generate_key(SSH_KEYS_DIR, filename, passphrase=passphrase, key_type=key_type)
    if not ok:
        _log.debug("generate_key : échec pour '%s' -- %s", filename, error)
        return jsonify({"error": error}), 400
    return jsonify({"status": "ok", "filename": filename}), 201


# ------------------------------------------------------------------
# Connexions SSH
# ------------------------------------------------------------------
def _redact_connection(row):
    """Jamais exposer `password_encrypted` (même chiffré, aucune
    bonne raison que le client le voie -- défense en profondeur,
    livraison #210) via l'API -- utilisé uniquement pour les réponses
    RENVOYÉES AU CLIENT, jamais pour l'usage INTERNE de ce champ
    (démarrage effectif d'un tunnel/montage, voir plus bas)."""
    if row is None:
        return None
    redacted = dict(row)
    redacted.pop("password_encrypted", None)
    return redacted


@app.route("/connections", methods=["GET"])
def list_connections():
    return jsonify([_redact_connection(c) for c in store.list_connections(DB_PATH)]), 200


@app.route("/connections", methods=["POST"])
def create_connection():
    """`auth_method` (optionnel, défaut "key") -- "key" (comportement
    HISTORIQUE, inchangé) ou "password" (livraison #210, backlog item
    12). En mode mot de passe : `password_username`/`password` requis
    (le mot de passe en clair, chiffré ICI avant stockage -- jamais
    stocké tel quel), `ssh_key_id` ignoré même s'il est fourni par
    erreur. `ssh_user` -- requis SEULEMENT en mode clé -- en mode mot
    de passe, `password_username` porte SEUL ce rôle (jamais deux
    champs redondants à remplir pour la même information -- ambiguïté
    repérée et corrigée avant même de construire l'écran hub)."""
    body = request.get_json(silent=True) or {}
    allowed, error = _check_manage_right(body)
    if not allowed:
        return jsonify({"error": error}), 403
    label = (body.get("label") or "").strip()
    ssh_host = (body.get("ssh_host") or "").strip()
    ssh_user = (body.get("ssh_user") or "").strip()
    ssh_port = int(body.get("ssh_port") or 22)
    actor = (body.get("actor") or "").strip() or None
    auth_method = (body.get("auth_method") or "key").strip()
    if auth_method not in ("key", "password"):
        return jsonify({"error": "'auth_method' doit être 'key' ou 'password'"}), 400
    if not label or not ssh_host:
        return jsonify({"error": "'label' et 'ssh_host' requis"}), 400

    if auth_method == "key":
        if not ssh_user:
            return jsonify({"error": "'ssh_user' requis en authentification par clé"}), 400
        ssh_key_id = body.get("ssh_key_id")
        if not ssh_key_id:
            return jsonify({"error": "'ssh_key_id' requis en authentification par clé"}), 400
        key = store.get_key(DB_PATH, ssh_key_id)
        if key is None:
            return jsonify({"error": "clé SSH introuvable"}), 400
        if not key["enabled"]:
            return jsonify({"error": "cette clé est désactivée -- l'activer avant de l'utiliser dans une connexion"}), 400
        connection_id = store.create_connection(DB_PATH, label, ssh_host, ssh_port, ssh_user, ssh_key_id, created_by=actor)
    else:
        password_username = (body.get("password_username") or "").strip()
        password = body.get("password") or ""
        if not password_username or not password:
            return jsonify({"error": "'password_username' et 'password' requis en authentification par mot de passe"}), 400
        try:
            password_encrypted = ccrypto.encrypt_password(password)
        except ccrypto.CredentialCryptoNotConfigured as exc:
            return jsonify({"error": str(exc)}), 503
        connection_id = store.create_connection(
            DB_PATH, label, ssh_host, ssh_port, password_username, None, created_by=actor,
            auth_method="password", password_username=password_username, password_encrypted=password_encrypted,
        )
    return jsonify(_redact_connection(store.get_connection_row(DB_PATH, connection_id))), 201


@app.route("/connections/<int:connection_id>", methods=["DELETE"])
def delete_connection(connection_id):
    body = request.get_json(silent=True) or {}
    allowed, error = _check_manage_right(body)
    if not allowed:
        return jsonify({"error": error}), 403
    deleted = store.delete_connection(DB_PATH, connection_id)
    if not deleted:
        return jsonify({"error": "suppression refusée -- des tunnels ou montages en dépendent encore, ou connexion introuvable"}), 409
    return jsonify({"status": "ok"}), 200


@app.route("/connections/<int:connection_id>/usage-history", methods=["GET"])
def get_connection_usage_history(connection_id):
    """Historique d'usage (livraison #210, backlog item 12) -- UNE
    ligne par tentative de démarrage (tunnel ou montage), succès ET
    échecs."""
    return jsonify(store.list_credential_usage(DB_PATH, connection_id=connection_id)), 200


# ------------------------------------------------------------------
# Tunnels
# ------------------------------------------------------------------
@app.route("/tunnels", methods=["GET"])
def list_tunnels():
    tunnels = [_reconcile_tunnel(t) for t in store.list_tunnels(DB_PATH)]
    return jsonify(tunnels), 200


@app.route("/tunnels", methods=["POST"])
def create_tunnel():
    body = request.get_json(silent=True) or {}
    allowed, error = _check_manage_right(body)
    if not allowed:
        return jsonify({"error": error}), 403
    connection_id = body.get("connection_id")
    label = (body.get("label") or "").strip()
    remote_host = (body.get("remote_host") or "").strip()
    remote_port = body.get("remote_port")
    local_port = body.get("local_port")
    actor = (body.get("actor") or "").strip() or None
    if not connection_id or not label or not remote_host or not remote_port or not local_port:
        return jsonify({"error": "'connection_id', 'label', 'remote_host', 'remote_port' et 'local_port' requis"}), 400
    if store.get_connection_row(DB_PATH, connection_id) is None:
        return jsonify({"error": "connexion SSH introuvable"}), 400
    tunnel_id, error = store.create_tunnel(
        DB_PATH, connection_id, label, remote_host, int(remote_port), int(local_port), created_by=actor,
    )
    if error:
        return jsonify({"error": error}), 409
    return jsonify(store.get_tunnel(DB_PATH, tunnel_id)), 201


@app.route("/tunnels/<int:tunnel_id>", methods=["DELETE"])
def delete_tunnel(tunnel_id):
    body = request.get_json(silent=True) or {}
    allowed, error = _check_manage_right(body)
    if not allowed:
        return jsonify({"error": error}), 403
    tunnel = store.get_tunnel(DB_PATH, tunnel_id)
    if tunnel is None:
        return jsonify({"error": "tunnel introuvable"}), 404
    tunnel = _reconcile_tunnel(tunnel)
    if tunnel["status"] == "running":
        # Arrêt AUTOMATIQUE avant suppression -- jamais un processus
        # ssh orphelin qui continuerait à tourner sans plus aucune
        # trace en base pour le retrouver/l'arrêter proprement.
        tproc.stop_tunnel_process(tunnel["pid"])
    store.delete_tunnel(DB_PATH, tunnel_id)
    return jsonify({"status": "ok"}), 200


@app.route("/tunnels/<int:tunnel_id>/start", methods=["POST"])
def start_tunnel(tunnel_id):
    body = request.get_json(silent=True) or {}
    allowed, error = _check_manage_right(body)
    if not allowed:
        return jsonify({"error": error}), 403
    tunnel = store.get_tunnel(DB_PATH, tunnel_id)
    if tunnel is None:
        return jsonify({"error": "tunnel introuvable"}), 404
    tunnel = _reconcile_tunnel(tunnel)
    if tunnel["status"] == "running":
        return jsonify({"status": "ok", "message": "déjà en cours d'exécution", "tunnel": tunnel}), 200

    connection = store.get_connection_row(DB_PATH, tunnel["connection_id"])
    if connection is None:
        return jsonify({"error": "connexion SSH associée introuvable"}), 409

    auth_method = connection.get("auth_method") or "key"
    key_path = None
    password = None
    if auth_method == "password":
        # Livraison #210, backlog item 12 -- déchiffré JUSTE AVANT
        # l'usage, jamais conservé en clair plus longtemps que
        # nécessaire pour cet appel.
        try:
            password = ccrypto.decrypt_password(connection["password_encrypted"])
        except ccrypto.CredentialCryptoNotConfigured as exc:
            return jsonify({"error": str(exc)}), 503
        except Exception as exc:  # noqa: BLE001 -- secret_crypto.SecretCryptoError notamment (phrase de passe changée depuis)
            return jsonify({"error": f"déchiffrement du mot de passe échoué : {exc}"}), 500
        ssh_user = connection["password_username"]
    else:
        key = store.get_key(DB_PATH, connection["ssh_key_id"])
        if key is None or not key["enabled"]:
            return jsonify({"error": "clé SSH associée introuvable ou désactivée"}), 409
        key_path = _key_path(key["filename"])
        ssh_user = connection["ssh_user"]

    pid, error = tproc.start_tunnel_process(
        connection["ssh_host"], connection["ssh_port"], ssh_user, key_path,
        tunnel["local_port"], tunnel["remote_host"], tunnel["remote_port"],
        auth_method=auth_method, password=password,
    )
    # UNE SEULE ligne d'historique, écrite APRÈS avoir connu le
    # résultat réel -- jamais une écriture "succès" optimiste suivie
    # d'une correction en cas d'échec (aurait laissé deux lignes,
    # dont une fausse, dans l'historique).
    store.record_credential_usage(DB_PATH, connection["id"], "tunnel", auth_method, success=(error is None), error_message=error)
    if error:
        store.update_tunnel_state(DB_PATH, tunnel_id, "error", pid=None, last_error=error)
        app.logger.warning("Démarrage du tunnel %s échoué : %s", tunnel_id, error)
        return jsonify({"error": error}), 502
    store.update_tunnel_state(DB_PATH, tunnel_id, "running", pid=pid, last_error=None)
    return jsonify(store.get_tunnel(DB_PATH, tunnel_id)), 200


@app.route("/tunnels/<int:tunnel_id>/stop", methods=["POST"])
def stop_tunnel(tunnel_id):
    body = request.get_json(silent=True) or {}
    allowed, error = _check_manage_right(body)
    if not allowed:
        return jsonify({"error": error}), 403
    tunnel = store.get_tunnel(DB_PATH, tunnel_id)
    if tunnel is None:
        return jsonify({"error": "tunnel introuvable"}), 404
    if tunnel["status"] != "running" or tunnel["pid"] is None:
        store.update_tunnel_state(DB_PATH, tunnel_id, "stopped", pid=None, last_error=None)
        return jsonify(store.get_tunnel(DB_PATH, tunnel_id)), 200
    tproc.stop_tunnel_process(tunnel["pid"])
    store.update_tunnel_state(DB_PATH, tunnel_id, "stopped", pid=None, last_error=None)
    store.close_latest_open_usage(DB_PATH, tunnel["connection_id"], "tunnel")
    return jsonify(store.get_tunnel(DB_PATH, tunnel_id)), 200


# ------------------------------------------------------------------
# Montages SSHFS -- action RÉELLE depuis #180 (interface préparée
# seule depuis #159, voir docstring du module).
# ------------------------------------------------------------------
@app.route("/mounts", methods=["GET"])
def list_mounts():
    mounts = [_reconcile_mount(m) for m in store.list_mounts(DB_PATH)]
    return jsonify(mounts), 200


@app.route("/mounts", methods=["POST"])
def create_mount():
    body = request.get_json(silent=True) or {}
    allowed, error = _check_manage_right(body)
    if not allowed:
        return jsonify({"error": error}), 403
    connection_id = body.get("connection_id")
    label = (body.get("label") or "").strip()
    remote_path = (body.get("remote_path") or "").strip()
    local_mount_path = (body.get("local_mount_path") or "").strip()
    actor = (body.get("actor") or "").strip() or None
    if not connection_id or not label or not remote_path or not local_mount_path:
        return jsonify({"error": "'connection_id', 'label', 'remote_path' et 'local_mount_path' requis"}), 400
    if store.get_connection_row(DB_PATH, connection_id) is None:
        return jsonify({"error": "connexion SSH introuvable"}), 400
    # Validé DÈS LA CRÉATION (livraison #180) -- jamais attendre le
    # premier /mount pour signaler un chemin invalide. local_mount_path
    # est un NOM RELATIF, jamais un chemin absolu -- voir
    # _resolve_mount_path/docstring du module.
    if _resolve_mount_path(local_mount_path) is None:
        return jsonify({"error": "'local_mount_path' doit être un nom relatif (jamais de chemin absolu ni de '..')"}), 400
    mount_id, error = store.create_mount(DB_PATH, connection_id, label, remote_path, local_mount_path, created_by=actor)
    if error:
        return jsonify({"error": error}), 409
    return jsonify(store.list_mounts(DB_PATH)), 201


@app.route("/mounts/<int:mount_id>", methods=["DELETE"])
def delete_mount(mount_id):
    body = request.get_json(silent=True) or {}
    allowed, error = _check_manage_right(body)
    if not allowed:
        return jsonify({"error": error}), 403
    mount = store.get_mount(DB_PATH, mount_id)
    if mount is None:
        return jsonify({"error": "montage introuvable"}), 404
    mount = _reconcile_mount(mount)
    if mount["status"] == "mounted":
        # Démontage AUTOMATIQUE avant suppression -- même raisonnement
        # que delete_tunnel : jamais un montage orphelin qui
        # continuerait sans plus aucune trace en base pour le
        # retrouver/le démonter proprement.
        resolved = _resolve_mount_path(mount["local_mount_path"])
        if resolved:
            mproc.stop_mount_process(mount["pid"], resolved)
    deleted = store.delete_mount(DB_PATH, mount_id)
    if not deleted:
        return jsonify({"error": "montage introuvable"}), 404
    return jsonify({"status": "ok"}), 200


@app.route("/mounts/<int:mount_id>/mount", methods=["POST"])
def mount_action(mount_id):
    body = request.get_json(silent=True) or {}
    allowed, error = _check_manage_right(body)
    if not allowed:
        return jsonify({"error": error}), 403
    mount = store.get_mount(DB_PATH, mount_id)
    if mount is None:
        return jsonify({"error": "montage introuvable"}), 404
    mount = _reconcile_mount(mount)
    if mount["status"] == "mounted":
        return jsonify({"status": "ok", "message": "déjà monté", "mount": mount}), 200

    resolved_path = _resolve_mount_path(mount["local_mount_path"])
    if resolved_path is None:
        # Ne devrait plus arriver (validé à la création, #180) --
        # sauf pour une ligne créée AVANT ce correctif, en base depuis
        # #159 avec un chemin qui ne respecterait pas ce format --
        # message clair plutôt qu'une exception plus loin.
        return jsonify({"error": "'local_mount_path' invalide pour ce montage -- le recréer avec un nom relatif"}), 409

    connection = store.get_connection_row(DB_PATH, mount["connection_id"])
    if connection is None:
        return jsonify({"error": "connexion SSH associée introuvable"}), 409

    auth_method = connection.get("auth_method") or "key"
    key_path = None
    password = None
    if auth_method == "password":
        try:
            password = ccrypto.decrypt_password(connection["password_encrypted"])
        except ccrypto.CredentialCryptoNotConfigured as exc:
            return jsonify({"error": str(exc)}), 503
        except Exception as exc:  # noqa: BLE001 -- secret_crypto.SecretCryptoError notamment
            return jsonify({"error": f"déchiffrement du mot de passe échoué : {exc}"}), 500
        ssh_user = connection["password_username"]
    else:
        key = store.get_key(DB_PATH, connection["ssh_key_id"])
        if key is None or not key["enabled"]:
            return jsonify({"error": "clé SSH associée introuvable ou désactivée"}), 409
        key_path = _key_path(key["filename"])
        ssh_user = connection["ssh_user"]

    # Point de montage : créé ici s'il n'existe pas déjà -- sshfs ne
    # le crée JAMAIS lui-même (voir mount_process.start_mount_process).
    try:
        os.makedirs(resolved_path, exist_ok=True)
    except OSError as exc:
        store.update_mount_state(DB_PATH, mount_id, "error", pid=None, last_error=f"création du point de montage échouée : {exc}")
        return jsonify({"error": f"création du point de montage échouée : {exc}"}), 502

    pid, error = mproc.start_mount_process(
        connection["ssh_host"], connection["ssh_port"], ssh_user, key_path,
        mount["remote_path"], resolved_path,
        auth_method=auth_method, password=password,
    )
    store.record_credential_usage(DB_PATH, connection["id"], "mount", auth_method, success=(error is None), error_message=error)
    if error:
        store.update_mount_state(DB_PATH, mount_id, "error", pid=None, last_error=error)
        app.logger.warning("Montage SSHFS %s échoué : %s", mount_id, error)
        return jsonify({"error": error}), 502
    store.update_mount_state(DB_PATH, mount_id, "mounted", pid=pid, last_error=None)
    return jsonify(store.get_mount(DB_PATH, mount_id)), 200


@app.route("/mounts/<int:mount_id>/unmount", methods=["POST"])
def unmount_action(mount_id):
    body = request.get_json(silent=True) or {}
    allowed, error = _check_manage_right(body)
    if not allowed:
        return jsonify({"error": error}), 403
    mount = store.get_mount(DB_PATH, mount_id)
    if mount is None:
        return jsonify({"error": "montage introuvable"}), 404
    resolved_path = _resolve_mount_path(mount["local_mount_path"])
    if mount["status"] != "mounted" or mount["pid"] is None:
        store.update_mount_state(DB_PATH, mount_id, "unmounted", pid=None, last_error=None)
        return jsonify(store.get_mount(DB_PATH, mount_id)), 200
    if resolved_path:
        ok, error = mproc.stop_mount_process(mount["pid"], resolved_path)
        if not ok:
            store.update_mount_state(DB_PATH, mount_id, "error", pid=mount["pid"], last_error=error)
            return jsonify({"error": error}), 502
    store.update_mount_state(DB_PATH, mount_id, "unmounted", pid=None, last_error=None)
    store.close_latest_open_usage(DB_PATH, mount["connection_id"], "mount")
    return jsonify(store.get_mount(DB_PATH, mount_id)), 200


@app.route("/mounts/<int:mount_id>/stats", methods=["GET"])
def mount_stats(mount_id):
    """Supervision d'un montage actif (livraison #182, demandé
    explicitement -- "transforme ça en vraie fonctionnalité de
    supervision") : espace/inodes distants (`get_disk_inode_stats`),
    confirmation que le chemin EST réellement un point de montage
    (`is_mount_point`, signal COMPLÉMENTAIRE à `pid_alive` -- voir
    mount_process.py, les deux peuvent diverger), latence d'un accès
    (`measure_latency`, borné par un timeout -- `?latency=false` pour
    l'ignorer et répondre plus vite si seul l'espace/inodes intéresse).

    Erreur claire (409) si le montage n'est PAS actuellement monté --
    jamais un `statvfs` sur un répertoire vide qui renverrait
    SILENCIEUSEMENT les stats du conteneur LUI-MÊME plutôt que du
    serveur distant (trompeur, voir docstring de
    get_disk_inode_stats)."""
    mount = store.get_mount(DB_PATH, mount_id)
    if mount is None:
        return jsonify({"error": "montage introuvable"}), 404
    mount = _reconcile_mount(mount)
    if mount["status"] != "mounted":
        return jsonify({"error": "ce montage n'est pas actuellement monté -- aucune statistique disponible"}), 409

    resolved_path = _resolve_mount_path(mount["local_mount_path"])
    if resolved_path is None:
        return jsonify({"error": "'local_mount_path' invalide pour ce montage"}), 409

    pid_alive = tproc.is_process_alive(mount["pid"])
    mounted_on_disk = mproc.is_mount_point(resolved_path)

    result = {
        "mount_id": mount_id,
        "status": mount["status"],
        "pid_alive": pid_alive,
        "is_mount_point": mounted_on_disk,
    }
    if not mounted_on_disk:
        # Divergence RÉELLE possible (démonté hors de ce service sans
        # que le processus ait encore été récolté, ex.) -- signalé
        # explicitement plutôt que de tenter statvfs/stat sur un
        # chemin qui n'est peut-être plus un vrai montage.
        result["warning"] = "le chemin n'est plus détecté comme un point de montage actif -- statistiques non calculées"
        return jsonify(result), 200

    try:
        stats = mproc.get_disk_inode_stats(resolved_path)
        result["disk"] = stats["disk"]
        result["inodes"] = stats["inodes"]
    except OSError as exc:
        result["error"] = f"lecture des statistiques échouée : {exc}"
        return jsonify(result), 200

    if request.args.get("latency", "true").strip().lower() != "false":
        result["latency_ms"] = mproc.measure_latency(resolved_path)

    return jsonify(result), 200


# ------------------------------------------------------------------
# Journal PARTAGE (endpoint /logs) -- stocke dans Memcached (voir
# shared/log_buffer.py, livraison #145) -- CE service tourne avec un
# SEUL worker (voir docstring du module), mais reste sur le MÊME
# mécanisme partagé que les autres backends : uniformité, et laisse
# la porte ouverte à plus de workers si ce choix est reconsidéré un
# jour (voir ssh-tunnels/README.md).
# ------------------------------------------------------------------
try:
    from log_buffer import make_shared_log_handler, read_shared_log_buffer
except ImportError:
    make_shared_log_handler = None
    read_shared_log_buffer = None

try:
    from pymemcache.client.base import Client as _MemcacheClient
except ImportError:
    _MemcacheClient = None

MEMCACHED_HOST = os.environ.get("MEMCACHED_HOST", "memcached")
MEMCACHED_PORT = int(os.environ.get("MEMCACHED_PORT", "11211"))


def get_memcache_client():
    return _MemcacheClient((MEMCACHED_HOST, MEMCACHED_PORT), connect_timeout=2, timeout=2)


SERVICE_NAME = "ssh-tunnels-api"
LOG_BUFFER_SIZE = int(os.environ.get("LOG_BUFFER_SIZE", "200"))
LOG_CAPTURE_LEVEL = os.environ.get("LOG_CAPTURE_LEVEL", "WARNING").strip().upper()

if make_shared_log_handler and _MemcacheClient:
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
    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
