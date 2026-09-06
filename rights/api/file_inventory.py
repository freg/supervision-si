"""
Inventaire des fichiers du hub (livraison #283, demandé explicitement
-- "tout fichier importé, de configuration, généré ou même de secret
doit être listé"). Ce module ne LIT JAMAIS le contenu d'un fichier --
seulement son CHEMIN, sa TAILLE et sa date de modification. Un
fichier "secret" (clé privée, .env) est listé comme EXISTANT, jamais
son contenu ni même un extrait -- lister ≠ exposer.

WATCHED_PATHS -- liste OUVERTE, pas prétendument exhaustive du
premier coup (impossible à garantir sans avoir soi-même audité les
~40 services de ce projet un par un, jamais fait ici). Point de
départ couvrant ce qui est CONNU avec certitude à ce stade (racine du
projet + gateway/ + quelques emplacements déjà documentés ailleurs
dans ce projet comme sensibles) -- à ÉTENDRE au fil de l'eau, pas figé.
"""
import os
import time

# (chemin relatif à PROJECT_ROOT, catégorie, motif -- None = tous les
# fichiers du dossier, non récursif par défaut sauf indication)
# Catégories : "importe" / "configuration" / "genere" / "secret".
WATCHED_PATHS = [
    (".env", "configuration", None),
    (".env.example", "configuration", None),
    ("keycloak/import", "genere", None),
    ("keycloak/backup", "genere", "*.json"),
    ("ssh-tunnels/keys", "secret", None),
    ("pki/ca", "secret", None),
    ("pki/server", "secret", None),
    ("tls-proxy/generated", "genere", None),
    ("apache/generated", "genere", None),
    ("gateway/.env", "configuration", None),
    ("gateway/keycloak/import", "genere", None),
]


def _matches_pattern(filename, pattern):
    if pattern is None:
        return True
    if pattern.startswith("*."):
        return filename.endswith(pattern[1:])
    return filename == pattern


def scan_files(project_root):
    """Parcourt WATCHED_PATHS -- renvoie une liste de dicts
    {identifier, category, size, mtime, exists} -- `identifier` est
    le chemin RELATIF à project_root (jamais un chemin absolu exposé
    tel quel, qui révélerait l'arborescence du serveur hôte).
    `exists=False` pour un chemin surveillé mais absent (normal --
    tous les services n'ont pas forcément généré leurs fichiers au
    moment du scan), jamais une erreur bloquante."""
    results = []
    for rel_path, category, pattern in WATCHED_PATHS:
        full_path = os.path.join(project_root, rel_path)
        if os.path.isfile(full_path):
            results.append(_file_entry(rel_path, full_path, category))
        elif os.path.isdir(full_path):
            try:
                entries = sorted(os.listdir(full_path))
            except OSError:
                continue
            for name in entries:
                if not _matches_pattern(name, pattern):
                    continue
                entry_full = os.path.join(full_path, name)
                if os.path.isfile(entry_full):
                    entry_rel = os.path.join(rel_path, name)
                    results.append(_file_entry(entry_rel, entry_full, category))
        # Chemin surveillé mais absent (ni fichier ni dossier) --
        # signalé quand même, jamais silencieusement omis (demandé
        # explicitement : TOUT fichier surveillé doit être listé,
        # y compris son absence si c'est le cas).
        else:
            results.append({"identifier": rel_path, "category": category, "size": None, "mtime": None, "exists": False})
    return results


def _file_entry(identifier, full_path, category):
    try:
        st = os.stat(full_path)
        return {
            "identifier": identifier,
            "category": category,
            "size": st.st_size,
            "mtime": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(st.st_mtime)),
            "exists": True,
        }
    except OSError:
        return {"identifier": identifier, "category": category, "size": None, "mtime": None, "exists": False}
