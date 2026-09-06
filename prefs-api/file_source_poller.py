"""
Sondeur des sources de logs FICHIER PLAT (livraison #176, backlog
BACKLOG.md #3, étape 3/4) -- lecture INCRÉMENTALE (position suivie),
rotation gérée (inode changé OU taille inférieure à la position
connue -- couvre à la fois une vraie rotation logrotate ET un mode
"copytruncate", qui garde le même inode mais vide le fichier).

Position de lecture stockée dans MEMCACHED (PAS un dict en mémoire
par processus comme _last_polled de log_sources_poller.py) -- une
lecture de fichier est INHÉRENTEMENT à état, contrairement à un GET
URL (qui répond "le contenu actuel" indépendamment de qui demande) :
avec 2 workers Gunicorn suivant CHACUN sa propre position en
mémoire, CHAQUE ligne nouvelle serait lue par les DEUX workers --
doublon SYSTÉMATIQUE, pas seulement occasionnel comme pour les
sources URL (déjà toléré ailleurs dans ce mécanisme). Coordonnée via
Memcached à la place -- pas d'opération atomique pour autant (même
tolérance qu'ailleurs dans ce mécanisme de DIAGNOSTIC uniquement) :
un doublon RARE en cas de course entre les deux workers reste
acceptable.

Chemins RESTREINTS à un répertoire racine autorisé (voir
_resolve_safe_path) -- jamais un chemin arbitraire fourni tel quel
dans `config.path`, protection contre une traversée de chemin
(`../../etc/passwd`) -- même esprit que ssh-tunnels/SSH_KEYS_DIR
(livraison #159) : un répertoire hôte monté EXPLICITEMENT en lecture
seule (voir docker-compose.yml, HOST_LOG_FILES_DIR), jamais un accès
libre au système de fichiers du conteneur.
"""
import json
import os
import time

from log_sources_poller import _detect_level

_POSITION_KEY_PREFIX = "logsrc:file:pos:"


def _load_position(name, memcache_client_factory):
    client = memcache_client_factory()
    try:
        raw = client.get(_POSITION_KEY_PREFIX + name)
    finally:
        client.close()
    if not raw:
        return None
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError, ValueError):
        return None


def _save_position(name, memcache_client_factory, inode, offset):
    client = memcache_client_factory()
    try:
        client.set(_POSITION_KEY_PREFIX + name, json.dumps({"inode": inode, "offset": offset}))
    finally:
        client.close()


def _resolve_safe_path(base_dir, relative_path):
    """Résout `relative_path` À L'INTÉRIEUR de `base_dir` -- renvoie
    None si le résultat sortirait de ce répertoire (chemin absolu
    fourni, ou traversée via `..`) -- jamais un chemin arbitraire
    accepté tel quel. `os.path.realpath` sur LES DEUX (base et
    candidat) avant comparaison -- résout aussi les liens symboliques,
    jamais contournable par ce biais."""
    if not relative_path or relative_path.startswith("/") or relative_path.startswith("\\"):
        return None
    candidate = os.path.normpath(os.path.join(base_dir, relative_path))
    base_real = os.path.realpath(base_dir)
    candidate_real = os.path.realpath(candidate)
    if candidate_real != base_real and not candidate_real.startswith(base_real + os.sep):
        return None
    return candidate_real


def read_new_lines(path, name, memcache_client_factory, max_bytes_per_poll=1_000_000):
    """Lit les octets NOUVEAUX depuis la dernière position connue,
    renvoie une liste de lignes (str, déjà décodées, jamais vides).

    Lecture en mode BINAIRE (positions exactes, indépendantes de tout
    décodage) -- n'avance la position QUE jusqu'à la dernière ligne
    COMPLÈTE du chunk lu (dernier `\\n` trouvé) : une ligne encore en
    cours d'écriture (pas de `\\n` final dans ce chunk) reste NON
    validée, relue en entier -- combinée aux octets suivants -- au
    prochain cycle. Jamais une ligne coupée en deux moitiés dans le
    tampon de logs.

    `max_bytes_per_poll` plafonne la lecture par cycle -- jamais un
    unique cycle qui engloutirait un fichier de plusieurs Go
    fraîchement apparu ; le reste suit aux cycles suivants."""
    stat = os.stat(path)
    inode = stat.st_ino
    size = stat.st_size

    position = _load_position(name, memcache_client_factory)
    if position is None or position.get("inode") != inode or position.get("offset", 0) > size:
        offset = 0  # jamais vu, rotation (inode différent), ou fichier tronqué (copytruncate)
    else:
        offset = position["offset"]

    if offset >= size:
        return []  # rien de nouveau -- pas d'écriture Memcached inutile

    with open(path, "rb") as fh:
        fh.seek(offset)
        chunk = fh.read(max_bytes_per_poll)

    last_newline = chunk.rfind(b"\n")
    if last_newline == -1:
        return []  # rien de COMPLET pour l'instant, position INCHANGÉE

    committed = chunk[: last_newline + 1]
    new_offset = offset + len(committed)
    _save_position(name, memcache_client_factory, inode, new_offset)

    text = committed.decode("utf-8", errors="replace")
    return [line for line in text.splitlines() if line.strip()]


def poll_file_source(source, memcache_client_factory, append_fn, register_fn, registry_key, buffer_size, base_dir, log_fn=None, read_fn=None):
    """Sonde UNE source fichier, écrit ses lignes dans le tampon
    partagé. Jamais une exception qui remonterait -- un fichier
    absent/illisible/hors du répertoire autorisé est journalisé (si
    `log_fn` fourni) et simplement retenté au prochain cycle.
    `read_fn` injectable pour les tests."""
    name = source["name"]
    config = source.get("config") or {}
    relative_path = config.get("path", "")

    full_path = _resolve_safe_path(base_dir, relative_path)
    if full_path is None:
        if log_fn:
            log_fn("Source de logs '%s' (fichier) : chemin refusé (hors du répertoire autorisé ou absolu) : %r", name, relative_path)
        return

    read = read_fn or read_new_lines
    try:
        lines = read(full_path, name, memcache_client_factory)
    except FileNotFoundError:
        if log_fn:
            log_fn("Source de logs '%s' (fichier) introuvable : %s", name, full_path)
        return
    except OSError as exc:
        if log_fn:
            log_fn("Source de logs '%s' (fichier) illisible : %s", name, exc)
        return

    for line in lines:
        entry = {
            "service": name,
            "timestamp": time.time(),
            "level": _detect_level(line),
            "logger": name,
            "message": line,
        }
        append_fn(name, memcache_client_factory, entry, buffer_size=buffer_size)
    if lines:
        register_fn(memcache_client_factory, registry_key, name)
