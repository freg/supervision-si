#!/usr/bin/env python3
"""Formate l'état des conteneurs en tableau groupé par module.

Lit sur stdin la sortie de `docker compose ps -a --format json`
(un objet JSON par ligne -- format JSON Lines de Docker Compose v2),
la regroupe par MODULE (voir MODULE_SERVICES) et affiche un tableau
lisible, façon `apachectl status`/`service --status-all`.

Séparé de launcher.sh (bash) délibérément : aucune dépendance à
Docker pour être testé -- on peut lui fournir de fausses lignes JSON
directement et vérifier le tableau produit, exactement comme
run-all.sh est testé avec de faux scripts.
"""
import json
import sys

# Module -> liste de services docker-compose.yml qui le composent.
# Construit à partir des dépendances RÉELLEMENT déclarées
# (depends_on), pas d'une supposition sur les noms -- vérifié service
# par service avant d'écrire cette table.
MODULE_SERVICES = {
    "gateway": ["tls-proxy"],
    "keycloak": ["keycloak", "keycloak-backup"],
    "hub": ["hub"],
    "supervision": ["api", "frontend", "pipeline", "memcached"],
    "pixel-grid": ["pixel-grid-postgres", "pixel-grid-api", "pixel-grid-bridge"],
    "tickets": ["tickets-postgres", "tickets-api", "tickets-portal"],
    "dba": ["dba-api", "dba-portal"],
    "vault": ["vault-api", "vault-portal", "vault-admin-api", "vault-admin-portal"],
    "ipam": ["ipam-api"],
    "optick": ["optick-api"],
    "zenoss": ["zenoss-api"],
    "tts-gu": ["tts-gu-api"],
    "owncloud": ["owncloud-api", "owncloud-search-api", "elasticsearch"],
    "cacti": ["cacti-api"],
    "geo-import": ["geo-postgres", "geo-import-api"],
    "prefs": ["prefs-api"],
    "launcher": ["launcher"],
}

# Service -> module, l'inverse de la table ci-dessus (calculé une
# fois, pas à chaque appel).
SERVICE_TO_MODULE = {svc: mod for mod, services in MODULE_SERVICES.items() for svc in services}


def parse_containers(lines):
    """Parse le JSON Lines de `docker compose ps -a --format json` --
    une ligne vide ou invalide est ignorée (jamais bloquant), plutôt
    que de faire planter tout l'affichage pour une seule ligne
    corrompue."""
    containers = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            containers.append(json.loads(line))
        except (json.JSONDecodeError, TypeError):
            continue
    return containers


def group_by_module(containers):
    """Regroupe les conteneurs par module -- un conteneur dont le nom
    de service n'est répertorié dans AUCUN module connu est placé
    dans un module "(non répertorié)" plutôt que d'être silencieusement
    ignoré (visible pour les futurs services jamais ajoutés à
    MODULE_SERVICES, plutôt qu'un oubli invisible)."""
    grouped = {mod: [] for mod in MODULE_SERVICES}
    grouped["(non répertorié)"] = []
    for c in containers:
        service = c.get("Service", "")
        module = SERVICE_TO_MODULE.get(service, "(non répertorié)")
        grouped[module].append(c)
    return grouped


def module_summary(containers_in_module):
    """Résumé d'un module -- 'actif' si TOUS ses conteneurs tournent,
    'partiel' si certains seulement, 'arrêté' si aucun (ou module non
    démarré du tout -- liste vide)."""
    if not containers_in_module:
        return "arrêté", "○"
    states = [c.get("State", "") for c in containers_in_module]
    if all(s == "running" for s in states):
        return "actif", "●"
    if any(s == "running" for s in states):
        return "partiel", "◐"
    return "arrêté", "○"


def format_table(containers, only_modules=None):
    """`only_modules` -- si fourni, n'affiche QUE ces modules (cas
    "status <module>" : les autres modules n'ont simplement pas été
    interrogés côté `docker compose ps`, les afficher comme "arrêté"
    serait FAUX -- ils pourraient très bien tourner sans qu'on le
    sache). Sans ce paramètre, tous les modules connus sont affichés
    (cas "status" complet, sans filtre)."""
    grouped = group_by_module(containers)
    modules_to_show = only_modules if only_modules is not None else (list(MODULE_SERVICES) + ["(non répertorié)"])
    lines = []
    lines.append(f"{'MODULE':<14} {'ÉTAT':<10} CONTENEURS")
    lines.append("-" * 70)
    for module in modules_to_show:
        in_module = grouped.get(module, [])
        if module == "(non répertorié)" and not in_module:
            continue  # rien à signaler si tout est répertorié
        summary, icon = module_summary(in_module)
        detail_parts = []
        for c in in_module:
            state = c.get("State", "?")
            health = c.get("Health", "")
            label = f"{c.get('Service', '?')} ({state}{', ' + health if health else ''})"
            detail_parts.append(label)
        detail = ", ".join(detail_parts) if detail_parts else "(non démarré)"
        lines.append(f"{module:<14} {icon} {summary:<8} {detail}")
    return "\n".join(lines)


if __name__ == "__main__":
    containers = parse_containers(sys.stdin)
    # Argument optionnel : nom(s) de module déjà filtré(s) côté
    # `docker compose ps` (voir launcher.sh) -- n'affiche que ceux-là.
    only = sys.argv[1:] if len(sys.argv) > 1 else None
    print(format_table(containers, only_modules=only))
