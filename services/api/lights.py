# -*- coding: utf-8 -*-
"""Feu tricolore des services du hub (livraison #584) -- logique PURE.

Pour chaque conteneur du projet compose : son état Docker, le résultat du
test HTTP interne (si un port est exposé) -> une lampe `green` / `orange`
/ `red` (+ `grey` : inconnu) et un texte lisible. Rien n'appelle Docker
ni le réseau ici : testable sans conteneur.
"""

# Conteneurs que « redémarrer les rouges » ne touche jamais (ils portent la
# page ou l'entrée du hub : les redémarrer coupe la session en cours).
PROTECTED = ("tls-proxy", "keycloak", "hub", "services-api")

KIND_LABEL = {"api": "API", "front": "front", "service": "service", "db": "base"}


def project_of(labels):
    return (labels or {}).get("com.docker.compose.project") or ""


def service_of(labels, name=""):
    return (labels or {}).get("com.docker.compose.service") or name


def exposed_port(attrs):
    """Premier port TCP exposé par l'image (ExposedPorts) -> int ou None."""
    ports = ((attrs or {}).get("Config") or {}).get("ExposedPorts") or {}
    nums = []
    for k in ports:
        p, _, proto = str(k).partition("/")
        if proto in ("", "tcp") and p.isdigit():
            nums.append(int(p))
    return min(nums) if nums else None


def guess_kind(service, port, http):
    s = (service or "").lower()
    if any(x in s for x in ("postgres", "mysql", "mariadb", "elasticsearch", "memcached", "redis", "ldap", "-db")):
        return "db"
    if http and http.get("content") == "html":
        return "front"
    if s.endswith("-api") or (http and http.get("content") == "json"):
        return "api"
    if port is None:
        return "service"
    return "front" if any(x in s for x in ("portal", "front", "hub", "app", "www")) else "api"


def classify(state, docker_health, http, port):
    """-> (light, text).
    state : running / exited / restarting / paused / created / dead
    docker_health : healthy / unhealthy / starting / None
    http : {ok, code, ms, error, content, status} ou None (pas de port / pas testé)."""
    if state == "restarting":
        return "orange", "redémarre en boucle"
    if state != "running":
        return "red", "conteneur %s" % (state or "absent")
    if docker_health == "unhealthy":
        return "red", "healthcheck Docker en échec"
    if docker_health == "starting":
        return "orange", "démarrage (healthcheck)"
    if port is None or http is None:
        return "green", "en marche" + (" (healthcheck OK)" if docker_health == "healthy" else "")
    if http.get("error"):
        return "red", "port %s injoignable : %s" % (port, http["error"])
    if http.get("tcp_only"):  # #588 : base, relais TLS, service binaire -- le port répond, ce n'est pas du HTTP
        return "green", "port %s ouvert (protocole non HTTP)" % port
    code = int(http.get("code") or 0)
    ms = int(http.get("ms") or 0)
    if code >= 500:
        return "red", "HTTP %d" % code
    st = str(http.get("status") or "").lower()
    if st in ("degraded", "warning", "warn", "ko", "error"):
        return "orange", "répond mais se déclare « %s »" % st
    if ms > 3000:
        return "orange", "répond lentement (%d ms)" % ms
    if code in (401, 403):
        return "green", "joignable (protégé, HTTP %d)" % code
    if code == 404:
        return "orange", "joignable, ni /health ni / (HTTP 404)"
    return "green", "HTTP %d en %d ms" % (code, ms)


def hard_red(state, docker_health):
    """#588 : panne « dure » (conteneur arrêté / en boucle / healthcheck en
    échec) -- seule base de l'auto-réparation. Un test HTTP en échec sur un
    conteneur en marche n'entraîne jamais un redémarrage automatique."""
    return state not in ("running",) or docker_health == "unhealthy"


def summarize(rows):
    """Compte par lampe + verdict global."""
    counts = {"green": 0, "orange": 0, "red": 0, "grey": 0}
    for r in rows:
        counts[r.get("light") or "grey"] = counts.get(r.get("light") or "grey", 0) + 1
    verdict = "red" if counts["red"] else "orange" if counts["orange"] else "green" if counts["green"] else "grey"
    return {"counts": counts, "verdict": verdict, "total": len(rows)}
