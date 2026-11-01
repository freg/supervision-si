# -*- coding: utf-8 -*-
"""Catalogue d'images de conteneurs pour la tuile Orchestration (les deux hubs) : sélection de départ (images
officielles courantes, avec leur port) et recherche sur Docker Hub (dépôts, puis étiquettes avec leurs architectures).
Lecture seule, sans compte ; réponses gardées 10 min en mémoire. Pur et testé : resumer_recherche, resumer_tags, normaliser."""
import json
import re
import threading
import time
import urllib.parse
import urllib.request

HUB = "https://hub.docker.com/v2"
CACHE_S = 600
_NOM = re.compile(r"^[a-z0-9]+([._-][a-z0-9]+)*(/[a-z0-9]+([._-][a-z0-9]+)*)?$")
# Sélection de départ : (image, port du conteneur, usage)
SELECTION = [
    ("nginx", 80, "serveur web / proxy"), ("httpd", 80, "serveur web Apache"), ("traefik/whoami", 80, "test : renvoie la requête"),
    ("redis", 6379, "cache clé-valeur"), ("postgres", 5432, "base PostgreSQL (POSTGRES_PASSWORD requis)"),
    ("mariadb", 3306, "base MariaDB (MARIADB_ROOT_PASSWORD requis)"), ("mongo", 27017, "base MongoDB"),
    ("rabbitmq", 5672, "file de messages"), ("eclipse-mosquitto", 1883, "broker MQTT"),
    ("grafana/grafana", 3000, "tableaux de bord"), ("prom/prometheus", 9090, "métriques"), ("louislam/uptime-kuma", 3001, "surveillance de disponibilité"),
    ("portainer/portainer-ce", 9000, "gestion Docker"), ("python", None, "langage Python"), ("node", None, "Node.js"),
    ("alpine", None, "base minimale"), ("debian", None, "base Debian"), ("ubuntu", None, "base Ubuntu"), ("busybox", None, "outils de base"),
    ("ollama/ollama", 11434, "modèles IA locaux"), ("open-webui/open-webui", 8080, "interface pour Ollama"), ("vaultwarden/server", 80, "gestionnaire de mots de passe"),
]
PORTS = {i: p for i, p, _ in SELECTION}
_cache, _verrou = {}, threading.Lock()


def normaliser(depot):
    """« nginx » -> « library/nginx » (API des étiquettes) ; None si le nom est invalide."""
    d = str(depot or "").strip().lower()
    if not _NOM.match(d):
        return None
    return d if "/" in d else "library/" + d


def resumer_recherche(doc):
    out = []
    for r in (doc or {}).get("results") or []:
        nom = r.get("repo_name") or ""
        if nom.startswith("library/"):
            nom = nom[8:]
        out.append({"image": nom, "description": (r.get("short_description") or "")[:200], "etoiles": r.get("star_count") or 0,
                    "telechargements": r.get("pull_count") or 0, "officielle": bool(r.get("is_official")), "port": PORTS.get(nom)})
    return sorted(out, key=lambda x: (not x["officielle"], -x["telechargements"]))


def resumer_tags(doc):
    out = []
    for t in (doc or {}).get("results") or []:
        archs = sorted({("%s/%s" % (i.get("architecture"), i["variant"]) if i.get("variant") else i.get("architecture"))
                        for i in t.get("images") or [] if i.get("os") in (None, "linux") and i.get("architecture") not in (None, "unknown")})
        out.append({"tag": t.get("name"), "maj": t.get("last_updated"), "taille": t.get("full_size"), "architectures": archs})
    return out


def _get(url):
    with _verrou:
        c = _cache.get(url)
        if c and time.time() - c[0] < CACHE_S:
            return c[1]
    req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "hub-orchestration/1"})
    with urllib.request.urlopen(req, timeout=12) as r:
        doc = json.loads(r.read().decode())
    with _verrou:
        _cache[url] = (time.time(), doc)
        if len(_cache) > 300:
            for k in sorted(_cache, key=lambda k: _cache[k][0])[:100]:
                _cache.pop(k, None)
    return doc


def rechercher(q):
    q = str(q or "").strip()[:80]
    if not q:
        return [{"image": i, "description": u, "etoiles": None, "telechargements": None, "officielle": "/" not in i, "port": p} for i, p, u in SELECTION]
    return resumer_recherche(_get("%s/search/repositories/?%s" % (HUB, urllib.parse.urlencode({"query": q, "page_size": 25}))))


def etiquettes(depot):
    d = normaliser(depot)
    if not d:
        raise ValueError("nom d'image invalide")
    return resumer_tags(_get("%s/repositories/%s/tags?page_size=30&ordering=last_updated" % (HUB, d)))
