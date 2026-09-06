"""
docker-monitor-api -- contrôle minimal des conteneurs + analyse de
logs publiée dans un fichier EXTERNE. Livraison #376, demandé
explicitement : "extraire de portainer.io de quoi construire un
docker qui contrôle les autres stacks/containers à minima qui lise et
analyse les logs de tous les container y compris lui-même et publie
son analyse dans un fichier log externe".

⚠️ SÉCURITÉ, À LIRE AVANT TOUT DÉPLOIEMENT -- ce service monte
`/var/run/docker.sock` (le socket Docker de l'hôte) pour parler à
l'API Docker via le SDK officiel (`docker` / docker-py) -- MÊME
principe que Portainer, confirmé par recherche avant cette livraison
(Portainer monte ce même socket pour gérer Docker, aucune autre voie
documentée). Un accès à ce socket ÉQUIVAUT À UN ACCÈS ROOT sur la
machine hôte : un conteneur qui le détient peut créer un AUTRE
conteneur montant `/` de l'hôte, donc lire/modifier N'IMPORTE QUEL
fichier système -- confirmé par plusieurs sources indépendantes
(articles de sécurité Docker, documentation Portainer elle-même).
AUCUN moyen de donner un accès "lecture seule" au socket lui-même (il
est monté tout ou rien) -- une alternative existe (docker-socket-proxy,
filtre les appels API réellement autorisés) mais volontairement PAS
ajoutée ici : hors du périmètre "à minima" demandé, complexifierait
significativement le déploiement pour un gain hors de portée de cette
livraison. À reconsidérer si ce service est un jour exposé au-delà
d'un usage interne de confiance.

⚠️ CONCURRENCE -- CE service tourne avec **UN SEUL worker Gunicorn**
(`--workers 1`), contrairement aux 2 workers habituels des autres
backends de ce projet -- DÉLIBÉRÉMENT : la boucle d'analyse
périodique (thread d'arrière-plan démarré au chargement du module)
tournerait en DOUBLE avec 2 workers séparés (2 process Python
distincts, chacun démarrant sa propre boucle) -- double écriture dans
le fichier d'analyse externe, double charge sur l'API Docker. Un seul
worker reste largement suffisant : ce service n'est pas pensé pour un
trafic HTTP concurrent élevé (outil de supervision interne, pas une
API publique).
"""
import os
import re
import time
import threading
import logging
from datetime import datetime, timezone

from flask import Flask, jsonify, request
from flask_cors import CORS
import docker
import docker.errors

app = Flask(__name__)
CORS(app)

SERVICE_NAME = "docker-monitor-api"

from version_endpoint import register_version_route
register_version_route(app, SERVICE_NAME)

# --- Client Docker (SDK officiel docker-py, PAS de sous-processus
# `docker` -- jamais un binaire externe à empaqueter, juste le socket
# monté -- confirmé être l'approche de Portainer lui-même). ---
docker_client = docker.from_env()

# --- Fichier d'analyse EXTERNE (volume monté -- survit à un
# redémarrage de CE conteneur, contrairement à un fichier interne). ---
ANALYSIS_LOG_PATH = os.environ.get("DOCKER_MONITOR_ANALYSIS_LOG", "/analysis/docker-monitor-analysis.log")
ANALYSIS_INTERVAL_SECONDS = int(os.environ.get("DOCKER_MONITOR_INTERVAL_SECONDS", "60"))
# Nombre de lignes de log les plus RÉCENTES examinées au tout premier
# passage sur un conteneur (jamais vu avant) -- borné volontairement,
# jamais un téléchargement de l'historique complet qui grossirait sans
# fin avec le temps. Les passages SUIVANTS utilisent `since=<epoch>`
# (voir analyze_container_logs) -- uniquement les lignes VRAIMENT
# nouvelles depuis le dernier passage, jamais un ré-examen répété des
# mêmes lignes.
ANALYSIS_TAIL_LINES = int(os.environ.get("DOCKER_MONITOR_TAIL_LINES", "200"))

# Motifs recherchés dans les nouvelles lignes de logs -- choisis à
# partir d'incidents RÉELLEMENT rencontrés dans ce projet au fil des
# livraisons (OOM "Killed", erreurs LDAP, tracebacks Python...),
# jamais une liste générique improvisée sans rapport avec ce qui a
# réellement posé problème ici.
ERROR_PATTERNS = [
    re.compile(r"\bERROR\b"),
    re.compile(r"\bCRITICAL\b"),
    re.compile(r"\bException\b"),
    re.compile(r"\bTraceback\b"),
    re.compile(r"\bKilled\b"),
    re.compile(r"\bFATAL\b"),
    re.compile(r"\bOOMKilled\b", re.IGNORECASE),
]
WARN_PATTERNS = [
    re.compile(r"\bWARN(ING)?\b"),
]

# Horodatage UNIX du dernier log EXAMINÉ, par conteneur (clé = ID
# complet) -- en mémoire du processus SEUL (un seul worker, voir
# docstring du module) -- perdu si ce conteneur redémarre, comportement
# ACCEPTÉ : le passage suivant retombe sur ANALYSIS_TAIL_LINES,
# jamais un plantage, juste un ré-examen borné des dernières lignes.
_last_seen_since = {}


def self_container_id():
    """Identifiant de CE conteneur -- HOSTNAME vaut l'ID court du
    conteneur par défaut sous Docker (documenté par Docker lui-même,
    jamais une coïncidence)."""
    return os.environ.get("HOSTNAME", "")


def analyze_container_logs(container):
    """Récupère les nouvelles lignes de logs de `container` depuis le
    dernier passage, compte erreurs/avertissements, renvoie un résumé
    (dict) ou None si rien de neuf/rien d'anormal. JAMAIS de plantage
    sur un conteneur injoignable/arrêté entre-temps -- renvoie un
    résumé d'erreur pour CE conteneur, la boucle appelante continue
    avec les autres."""
    name = container.name
    since = _last_seen_since.get(container.id)
    try:
        if since is None:
            raw = container.logs(tail=ANALYSIS_TAIL_LINES, timestamps=False)
        else:
            raw = container.logs(since=since, timestamps=False)
    except Exception as exc:  # noqa: BLE001
        return {"container": name, "error": f"logs injoignables : {exc}"}

    _last_seen_since[container.id] = int(time.time())

    if not raw:
        return None
    lines = raw.decode("utf-8", errors="replace").splitlines()
    if not lines:
        return None

    error_count = 0
    warn_count = 0
    sample_errors = []
    for line in lines:
        if any(p.search(line) for p in ERROR_PATTERNS):
            error_count += 1
            if len(sample_errors) < 3:
                sample_errors.append(line[:300])
        elif any(p.search(line) for p in WARN_PATTERNS):
            warn_count += 1

    if error_count == 0 and warn_count == 0:
        return None

    return {
        "container": name,
        "lines_examined": len(lines),
        "errors": error_count,
        "warnings": warn_count,
        "samples": sample_errors,
    }


def _format_finding(f):
    if "error" in f:
        return f"[{f['container']}] {f['error']}"
    parts = (
        f"[{f['container']}] {f['errors']} erreur(s), {f['warnings']} "
        f"avertissement(s) sur {f['lines_examined']} ligne(s) examinée(s)"
    )
    if f["samples"]:
        parts += " -- exemples : " + " | ".join(f["samples"])
    return parts


def _write_analysis_line(message):
    """Ajoute UNE ligne horodatée au fichier d'analyse EXTERNE --
    toujours un append, JAMAIS une réécriture complète (le fichier
    grossit avec le temps -- volontairement PAS de rotation
    automatique ici, hors du périmètre "à minima" demandé -- à la
    personne de le faire tourner/purger selon ses propres
    contraintes)."""
    timestamp = datetime.now(timezone.utc).isoformat()
    try:
        os.makedirs(os.path.dirname(ANALYSIS_LOG_PATH), exist_ok=True)
        with open(ANALYSIS_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(f"{timestamp} {message}\n")
    except OSError as exc:
        # Ne peut pas remonter cette erreur nulle part d'autre que le
        # logger Python normal de ce service -- le fichier EST la
        # seule sortie prévue pour l'analyse, une panne d'écriture ici
        # reste silencieuse pour la personne sauf à consulter /logs de
        # ce service lui-même (tampon partagé, voir plus bas).
        logging.getLogger(__name__).error("Échec écriture fichier d'analyse : %s", exc)


def run_analysis_cycle():
    """Un passage complet : TOUS les conteneurs, y compris CE
    conteneur lui-même -- docker-py le voit comme n'importe quel
    autre conteneur de la liste, aucun traitement spécial nécessaire
    côté API Docker, juste ne JAMAIS l'exclure par erreur (demandé
    explicitement : "y compris lui-même")."""
    try:
        containers = docker_client.containers.list(all=True)
    except Exception as exc:  # noqa: BLE001
        _write_analysis_line(f"ERREUR : impossible de lister les conteneurs -- {exc}")
        return

    findings = []
    for container in containers:
        result = analyze_container_logs(container)
        if result:
            findings.append(result)

    if findings:
        for f in findings:
            _write_analysis_line(_format_finding(f))
    else:
        _write_analysis_line(f"Aucune anomalie détectée sur ce passage ({len(containers)} conteneur(s) examiné(s)).")


def _background_loop():
    while True:
        run_analysis_cycle()
        time.sleep(ANALYSIS_INTERVAL_SECONDS)


_analysis_thread = threading.Thread(target=_background_loop, daemon=True)
_analysis_thread.start()


# ------------------------------------------------------------------
# Contrôle "à minima" -- lister/démarrer/arrêter/redémarrer un
# conteneur. JAMAIS de suppression/création/pull d'image ici (hors du
# périmètre "à minima" demandé) -- pour ça, un vrai Portainer (ou un
# accès direct au socket) reste l'outil approprié.
# ------------------------------------------------------------------
@app.route("/containers", methods=["GET"])
def list_containers():
    try:
        containers = docker_client.containers.list(all=True)
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": str(exc)}), 503
    self_id = self_container_id()
    return jsonify({
        "containers": [
            {
                "id": c.id[:12],
                "name": c.name,
                "status": c.status,
                "image": c.image.tags[0] if c.image.tags else c.image.id[:12],
                "is_self": bool(self_id) and c.id.startswith(self_id),
            }
            for c in containers
        ]
    }), 200


def _find_container(name_or_id):
    try:
        return docker_client.containers.get(name_or_id)
    except docker.errors.NotFound:
        return None
    except Exception:  # noqa: BLE001
        return None


@app.route("/containers/<name>/start", methods=["POST"])
def start_container(name):
    c = _find_container(name)
    if c is None:
        return jsonify({"error": "conteneur introuvable"}), 404
    try:
        c.start()
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": str(exc)}), 500
    return jsonify({"status": "ok"}), 200


@app.route("/containers/<name>/stop", methods=["POST"])
def stop_container(name):
    c = _find_container(name)
    if c is None:
        return jsonify({"error": "conteneur introuvable"}), 404
    # ⚠️ Un conteneur peut s'arrêter LUI-MÊME via cette route (aucun
    # garde-fou spécifique) -- si la personne demande explicitement
    # d'arrêter "docker-monitor-api", ça s'arrête, point -- documenté,
    # jamais empêché en douce.
    try:
        c.stop()
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": str(exc)}), 500
    return jsonify({"status": "ok"}), 200


@app.route("/containers/<name>/restart", methods=["POST"])
def restart_container(name):
    c = _find_container(name)
    if c is None:
        return jsonify({"error": "conteneur introuvable"}), 404
    try:
        c.restart()
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": str(exc)}), 500
    return jsonify({"status": "ok"}), 200


@app.route("/containers/<name>/logs", methods=["GET"])
def container_raw_logs(name):
    """Logs BRUTS complets d'un conteneur (livraison #380, demandé
    explicitement -- "c'était le but du moniteur" : contourner les
    limites de pagination/scrollback d'un visualiseur de logs comme
    Portainer, en passant directement par l'API Docker via ce
    service. Pas d'analyse ici, juste le texte brut tel que Docker
    le renvoie -- l'analyse résumée reste sur /analysis."""
    c = _find_container(name)
    if c is None:
        return jsonify({"error": "conteneur introuvable"}), 404
    tail = request.args.get("tail", 1000, type=int)
    try:
        raw = c.logs(tail=tail, timestamps=True)
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": str(exc)}), 500
    return raw.decode("utf-8", errors="replace"), 200, {"Content-Type": "text/plain; charset=utf-8"}


@app.route("/analysis", methods=["GET"])
def get_analysis():
    """Dernières lignes du fichier d'analyse externe -- pratique pour
    consulter depuis une interface sans avoir à aller lire le fichier
    directement sur l'hôte."""
    limit = request.args.get("limit", 100, type=int)
    try:
        with open(ANALYSIS_LOG_PATH, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except FileNotFoundError:
        return jsonify({"lines": []}), 200
    return jsonify({"lines": [line.rstrip("\n") for line in lines[-limit:]]}), 200


@app.route("/health", methods=["GET"])
def health():
    try:
        docker_client.ping()
        docker_ok = True
    except Exception:  # noqa: BLE001
        docker_ok = False
    return jsonify({
        "status": "ok" if docker_ok else "degraded",
        "docker": "ok" if docker_ok else "injoignable (socket monté ? démon accessible ?)",
    }), 200


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


LOG_BUFFER_SIZE = int(os.environ.get("LOG_BUFFER_SIZE", "200"))
LOG_CAPTURE_LEVEL = os.environ.get("LOG_CAPTURE_LEVEL", "WARNING").strip().upper()

if make_shared_log_handler:
    _log_handler = make_shared_log_handler(
        SERVICE_NAME, get_memcache_client, buffer_size=LOG_BUFFER_SIZE, capture_level=LOG_CAPTURE_LEVEL,
    )
    logging.getLogger().addHandler(_log_handler)


@app.route("/logs", methods=["GET"])
def get_logs():
    limit = request.args.get("limit", type=int)
    entries = read_shared_log_buffer(SERVICE_NAME, get_memcache_client, limit=limit, buffer_size=LOG_BUFFER_SIZE) if read_shared_log_buffer else []
    return jsonify({"service": SERVICE_NAME, "entries": entries}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
