# -*- coding: utf-8 -*-
"""Archive de déploiement de l'agent servie par le central (livraison #518).

Demandé : « ajouter un lien de téléchargement pour le transfert du paquet sur
l'hôte de l'agent ». L'archive `si-agent-agent-<version>.tar.gz` (produite par
si-agent/make-archive.sh, sans secret ni configuration) est construite dans
l'image de si-agent-api et servie par `GET /package` ; `/package/info` donne
nom, version, taille et SHA-256 pour vérifier le transfert. Logique pure ici,
testée sans Flask (test_package.py)."""
import glob
import hashlib
import os
import re
import shlex

PACKAGE_DIR = os.environ.get("SI_AGENT_PACKAGE_DIR", "/app/package")
_cache = {}


def find_package(directory=None):
    files = sorted(glob.glob(os.path.join(directory or PACKAGE_DIR, "si-agent-agent-*.tar.gz")))
    return files[-1] if files else None


def package_info(path):
    """{name, version, size, sha256} -- SHA-256 mis en cache par (chemin, mtime, taille)."""
    if not path or not os.path.isfile(path):
        return None
    st = os.stat(path)
    key = (path, st.st_mtime, st.st_size)
    if key not in _cache:
        h = hashlib.sha256()
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
        name = os.path.basename(path)
        m = re.match(r"si-agent-agent-(.+)\.tar\.gz$", name)
        _cache.clear()
        _cache[key] = {"name": name, "version": m.group(1) if m else None, "size": st.st_size, "sha256": h.hexdigest()}
    return _cache[key]


def download_command(public_url, info):
    """Ligne à coller sur l'hôte : téléchargement (certificat interne, donc -k :
    c'est le SHA-256 affiché qui fait foi), vérification, extraction, `cd`."""
    if not info:
        return None
    url = (public_url or "https://<VM>:6443/api/si-agent").rstrip("/") + "/package"
    name = info["name"]
    folder = name[: -len(".tar.gz")]
    return "curl -fsSk -o %s %s && echo '%s  %s' | sha256sum -c && tar xzf %s && cd %s" % (
        shlex.quote(name), shlex.quote(url), info["sha256"], name, shlex.quote(name), shlex.quote(folder))
