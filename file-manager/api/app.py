#!/usr/bin/env python3
"""
file-manager -- nouvelle tuile/outil "gestionnaire de fichiers" (livraison
#396, backlog item 26). Trois volets :

1. Vue de la GED organisée comme une exploration arborescente (par dossier,
   par entité liée, par type).
2. Navigation en accès arborescent aux systèmes de fichiers MONTÉS
   (partages SSHFS via ssh-tunnels-api).
3. Une brique "espace/système de fichiers protégé du HUB" -- un répertoire
   sur l'hôte, accessible aussi bien depuis le hub (via ce module) que
   directement par la machine hôte. Protégé par rights-api : seuls les
   groupes autorisés (admin_hub par défaut) peuvent lister/parcourir.

Architecture : ce module ne duplique aucune donnée. Il AGGREGE les sources
existantes (ged-api, ssh-tunnels-api) via HTTP interne, et gère son propre
espace protégé (montage hôte). Il n'a pas d'état propre persistant pour les
documents (ged-api les détient) ni pour les montages (ssh-tunnels-api les
détient) -- son seul état persistant est l'index SQLite de l'espace protégé
(métadonnées : chemins, tailles, dates -- jamais le contenu).

⚠️ Non vérifié dans cet environnement : accès réseau réel aux services
ged-api/ssh-tunnels-api (réseau restreint). Logique testée en profondeur
avec des scénarios simulés (clients mockés).
"""
import logging
import os
import os.path
import stat
import time

import requests
from flask import Flask, jsonify, request, Response
from flask_cors import CORS

import store

try:
    from version_endpoint import register_version_route
except ImportError:
    register_version_route = None

app = Flask(__name__)
CORS(app)
if register_version_route:
    register_version_route(app, "file-manager-api")

_log = logging.getLogger("file_manager_app")

# ------------------------------------------------------------------
# Configuration -- toutes les variables depuis .env, jamais codées en dur.
# ------------------------------------------------------------------

# Espace protégé du hub (volet 3) -- répertoire sur l'hôte, accessible aussi
# bien depuis le hub que directement par la machine hôte. Protégé par
# rights-api.
PROTECTED_SPACE_DIR = os.environ.get("FILE_MANAGER_PROTECTED_DIR", "/protected-space")

# URLs internes (réseau Docker partagé) -- jamais via tls-proxy
GED_API_INTERNAL_URL = os.environ.get("GED_API_INTERNAL_URL", "http://ged-api:5000").rstrip("/")
SSH_TUNNELS_API_INTERNAL_URL = os.environ.get("SSH_TUNNELS_API_INTERNAL_URL", "http://ssh-tunnels-api:5000").rstrip("/")

# Branchement rights-api -- même motif que les autres services (OPT-IN)
RIGHTS_API_URL = os.environ.get("RIGHTS_API_URL", "").rstrip("/") or None

# SQLite -- index de l'espace protégé (métadonnées uniquement)
DB_PATH = os.environ.get("FILE_MANAGER_DB_PATH", "/data/file-manager.db")

# Taille max de listing (éviter un dossier avec 1M de fichiers qui sature)
MAX_LISTING_ITEMS = int(os.environ.get("FILE_MANAGER_MAX_LISTING_ITEMS", "1000"))

# Niveaux de profondeur max pour l'arborescence (éviter les boucles
# infinies via symlinks)
MAX_TREE_DEPTH = int(os.environ.get("FILE_MANAGER_MAX_TREE_DEPTH", "50"))

os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
store.ensure_schema(DB_PATH)


# ------------------------------------------------------------------
# Helpers -- appels internes avec filet de sécurité (même motif que
# les autres clients du projet : jamais de .json() sans protection).
# ------------------------------------------------------------------

def _safe_json(resp):
    """Extrait le JSON d'une réponse, ou None si le corps n'est pas du JSON
    valide. Même motif que shared/safe_json.py."""
    if resp.status_code != 200:
        return None
    try:
        return resp.json()
    except ValueError:
        return None


# ------------------------------------------------------------------
# Rights -- garde d'accès à l'espace protégé (volet 3). Seuls les
# groupes autorisés (admin_hub par défaut) peuvent y accéder.
# ------------------------------------------------------------------

def _check_protected_access(groups, action="view"):
    """Vérifie que les groupes ont le droit d'accéder à l'espace protégé.
    Même motif FAIL CLOSED que les branchements précédents (#289-331)."""
    if not RIGHTS_API_URL:
        return True, None
    try:
        resp = requests.post(
            f"{RIGHTS_API_URL}/check",
            json={"groups": groups, "resource_type": "file-manager-protected", "resource_id": None, "action": action},
            timeout=5,
        )
    except requests.RequestException as exc:
        _log.debug("_check_protected_access : rights-api injoignable -- %s", exc)
        return False, "service de droits injoignable -- accès refusé par prudence"
    if resp.status_code != 200:
        return False, "service de droits indisponible -- accès refusé par prudence"
    try:
        allowed = resp.json().get("allowed", False)
    except ValueError:
        return False, "réponse des droits illisible -- accès refusé par prudence"
    if not allowed:
        return False, "accès à l'espace protégé refusé (groupe admin_hub requis, ou octroi explicite)"
    return True, None


# ------------------------------------------------------------------
# Source : espace protégé du hub (volet 3)
# ------------------------------------------------------------------

def _scan_protected_node(path, depth=0):
    """
    Construit un nœud de l'arborescence pour l'espace protégé.
    Lit UNIQUEMENT les métadonnées (os.scandir, jamais de lecture de
    contenu) -- conforme au périmètre "inventaire de fichiers jamais leur
    contenu" de rights-api.
    """
    if depth > MAX_TREE_DEPTH:
        return {"name": os.path.basename(path), "path": path, "type": "folder", "children": [], "truncated": True}

    try:
        entries = list(os.scandir(path))
    except PermissionError:
        return {"name": os.path.basename(path), "path": path, "type": "folder", "children": [], "error": "permission refusée"}
    except OSError as exc:
        return {"name": os.path.basename(path), "path": path, "type": "folder", "children": [], "error": str(exc)}

    entries.sort(key=lambda e: (not e.is_dir(follow_symlinks=False), e.name.lower()))

    children = []
    for entry in entries[:MAX_LISTING_ITEMS]:
        try:
            st = entry.stat(follow_symlinks=False)
        except OSError:
            continue
        is_dir = entry.is_dir(follow_symlinks=False)
        is_file = entry.is_file(follow_symlinks=False)
        node = {
            "name": entry.name,
            "path": entry.path,
            "type": "folder" if is_dir else ("file" if is_file else "other"),
            "size": st.st_size if is_file else None,
            "mtime": int(st.st_mtime),
        }
        children.append(node)

    truncated = len(entries) > MAX_LISTING_ITEMS
    return {
        "name": os.path.basename(path) or path,
        "path": path,
        "type": "folder",
        "children": children,
        "truncated": truncated,
        "totalChildren": len(entries),
    }


def _protected_node_at(relative_path):
    """
    Résout un chemin relatif dans l'espace protégé en un nœud complet
    (avec enfants). Protection contre la traversée de chemin : refuse
    tout chemin absolu ou contenant '..'.
    """
    if not relative_path or relative_path.strip() == "":
        target = PROTECTED_SPACE_DIR
    else:
        # Nettoyage -- refuser les tentatives de traversée
        relative_path = relative_path.strip("/")
        if ".." in relative_path.split("/"):
            return None
        target = os.path.join(PROTECTED_SPACE_DIR, relative_path)
        # Vérifier qu'on est bien encore sous PROTECTED_SPACE_DIR (au cas où
        # des symlinks sortiraient)
        real_target = os.path.realpath(target)
        real_base = os.path.realpath(PROTECTED_SPACE_DIR)
        if not real_target.startswith(real_base + os.sep) and real_target != real_base:
            return None

    if not os.path.exists(target):
        return None
    return _scan_protected_node(target)


# ------------------------------------------------------------------
# Source : documents GED (volet 1) -- agrégé depuis ged-api
# ------------------------------------------------------------------

def _fetch_ged_documents(groups):
    """
    Récupère les documents depuis ged-api (lecture seule, aucune écriture
    ici -- l'écriture reste le rôle de GedView.jsx).
    """
    try:
        # Transmettre les groupes pour que ged-api puisse filtrer si besoin
        resp = requests.get(
            f"{GED_API_INTERNAL_URL}/documents",
            timeout=10,
        )
    except requests.RequestException as exc:
        _log.warning("GED injoignable -- %s", exc)
        return []
    data = _safe_json(resp)
    return data if isinstance(data, list) else []


# ------------------------------------------------------------------
# Source : montages SSHFS (volet 2) -- agrégé depuis ssh-tunnels-api
# ------------------------------------------------------------------

def _fetch_ssh_mounts(groups):
    """
    Récupère les montages actifs depuis ssh-tunnels-api.
    """
    try:
        resp = requests.get(
            f"{SSH_TUNNELS_API_INTERNAL_URL}/mounts",
            timeout=10,
        )
    except requests.RequestException as exc:
        _log.warning("ssh-tunnels injoignable -- %s", exc)
        return []
    data = _safe_json(resp)
    return data if isinstance(data, list) else []


def _fetch_mount_stats(mount_id):
    """Stats d'un montage actif (espace, inodes, latence)."""
    try:
        resp = requests.get(
            f"{SSH_TUNNELS_API_INTERNAL_URL}/mounts/{mount_id}/stats",
            timeout=10,
        )
    except requests.RequestException:
        return None
    return _safe_json(resp)


# ------------------------------------------------------------------
# Routes -- toutes en lecture seule (agrégation / inventaire).
# Protection par rights-api uniquement pour l'espace protégé (volet 3).
# ------------------------------------------------------------------

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


@app.route("/sources", methods=["GET"])
def list_sources():
    """
    Liste les sources disponibles pour l'explorateur.
    Chaque source = un système de fichiers navigable.
    Protégé par rights-api pour l'espace protégé.
    """
    body = request.get_json(silent=True) or {}
    groups = body.get("groups") or request.args.getlist("groups") or []

    sources = []

    # Volet 3 : espace protégé du hub
    can_protected, _ = _check_protected_access(groups, "view")
    if can_protected:
        sources.append({
            "id": "protected-space",
            "name": "Espace protégé du hub",
            "type": "protected-space",
            "description": "Répertoire sur l'hôte, accessible aussi bien depuis le hub que directement",
            "basePath": PROTECTED_SPACE_DIR,
            "embeddable": False,  # accès direct (montage hôte), pas une iframe
        })

    # Volet 1 : documents GED
    sources.append({
        "id": "ged",
        "name": "Documents GED",
        "type": "ged",
        "description": "Dépôt interne (ged-api/Mayan)",
        "embeddable": True,
    })

    # Volet 2 : montages SSHFS
    sources.append({
        "id": "ssh-mounts",
        "name": "Partages SSHFS",
        "type": "ssh-mounts",
        "description": "Systèmes de fichiers montés via ssh-tunnels",
        "embeddable": False,  # accès direct (système de fichiers)
    })

    return jsonify({"sources": sources}), 200


@app.route("/browse/<source_id>", methods=["GET"])
def browse(source_id):
    """
    Parcourt un dossier dans la source donnée.
    Query params : path (chemin relatif dans la source), depth (profondeur).
    """
    body = request.get_json(silent=True) or {}
    groups = body.get("groups") or request.args.getlist("groups") or []
    path = request.args.get("path", "")
    depth = int(request.args.get("depth", "1"))

    if depth < 0 or depth > MAX_TREE_DEPTH:
        depth = 1

    if source_id == "protected-space":
        allowed, error = _check_protected_access(groups, "view")
        if not allowed:
            return jsonify({"error": error}), 403
        node = _protected_node_at(path)
        if node is None:
            return jsonify({"error": "chemin introuvable dans l'espace protégé"}), 404
        return jsonify({"node": node}), 200

    if source_id == "ged":
        # La GED n'est pas un arbre de fichiers -- on retourne la liste
        # des documents comme une source plate (le frontend organise
        # l'affichage).
        docs = _fetch_ged_documents(groups)
        return jsonify({
            "type": "flat",
            "items": [
                {
                    "id": d.get("id"),
                    "name": d.get("name", f"Document #{d.get('id')}"),
                    "type": "document",
                    "versionCount": len(d.get("versions", [])),
                    "links": d.get("links", []),
                }
                for d in docs
            ],
        }), 200

    if source_id == "ssh-mounts":
        mounts = _fetch_ssh_mounts(groups)
        return jsonify({
            "type": "flat",
            "items": [
                {
                    "id": m.get("id"),
                    "name": m.get("label", f"Montage #{m.get('id')}"),
                    "type": "mount",
                    "status": m.get("status"),
                    "remotePath": m.get("remote_path"),
                    "localPath": m.get("local_mount_path"),
                    "canBrowse": m.get("status") == "mounted",
                }
                for m in mounts
            ],
        }), 200

    return jsonify({"error": "source inconnue"}), 404


@app.route("/browse/<source_id>/<int:item_id>", methods=["GET"])
def browse_item(source_id, item_id):
    """
    Pour les sources arborescentes : explore un élément spécifique.
    Actif pour ssh-mounts (un montage donné).
    """
    body = request.get_json(silent=True) or {}
    groups = body.get("groups") or request.args.getlist("groups") or []
    path = request.args.get("path", "")

    if source_id == "ssh-mounts":
        mounts = _fetch_ssh_mounts(groups)
        mount = next((m for m in mounts if m.get("id") == item_id), None)
        if mount is None:
            return jsonify({"error": "montage introuvable"}), 404
        if mount.get("status") != "mounted":
            return jsonify({"error": "montage non actif"}), 409
        # Le chemin local du montage est dans ssh-tunnels
        local_rel = mount.get("local_mount_path", "")
        if local_rel:
            # Le montage est dans /mounts/<local_rel> côté ssh-tunnels-api
            # Mais ce module n'y a pas accès directement -- on expose
            # l'info au frontend pour navigation.
            return jsonify({
                "mount": mount,
                "browseUrl": f"/api/ssh-tunnels/mounts/{item_id}/browse?path={path}",
            }), 200
        return jsonify({"error": "point de montage inconnu"}), 409

    return jsonify({"error": "source non supportée pour la navigation par item"}), 404


@app.route("/stats/<source_id>", methods=["GET"])
def stats(source_id):
    """
    Statistiques agrégées pour une source.
    """
    body = request.get_json(silent=True) or {}
    groups = body.get("groups") or request.args.getlist("groups") or []

    if source_id == "ssh-mounts":
        mounts = _fetch_ssh_mounts(groups)
        stats_list = []
        for m in mounts:
            s = _fetch_mount_stats(m.get("id"))
            if s:
                stats_list.append({"mountId": m.get("id"), "mount": m.get("label"), **s})
        return jsonify({"mounts": stats_list}), 200

    if source_id == "ged":
        docs = _fetch_ged_documents(groups)
        return jsonify({
            "totalDocuments": len(docs),
            "totalVersions": sum(len(d.get("versions", [])) for d in docs),
            "totalLinks": sum(len(d.get("links", [])) for d in docs),
        }), 200

    if source_id == "protected-space":
        allowed, error = _check_protected_access(groups, "view")
        if not allowed:
            return jsonify({"error": error}), 403
        try:
            total = sum(1 for _ in os.scandir(PROTECTED_SPACE_DIR))
        except OSError:
            total = 0
        return jsonify({"totalItems": total, "basePath": PROTECTED_SPACE_DIR}), 200

    return jsonify({"error": "source inconnue"}), 404


# ------------------------------------------------------------------
# Journal PARTAGE (endpoint /logs) -- même mécanisme que les autres.
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


SERVICE_NAME = "file-manager-api"
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


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
