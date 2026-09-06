#!/usr/bin/env python3
"""
Génère la config nginx du proxy TLS de l'instance ISOLÉE du coffre-fort.

    python3 vault-standalone/tls-proxy/render_nginx_conf.py            # écrit generated/services.conf
    python3 vault-standalone/tls-proxy/render_nginx_conf.py --check    # affiche le mapping sans écrire

Réutilise les gabarits nginx (API_LOCATION_TEMPLATE, SPA_LOCATION_TEMPLATE,
HEADER_TEMPLATE) de tls-proxy/render_nginx_conf.py PAR IMPORT (chemin
explicite, voir vault-standalone/keycloak/render.py pour le
raisonnement complet sur pourquoi jamais par nom de module) -- même
mise en forme que le proxy principal, juste une table SERVICES
beaucoup plus courte (3 entrées au lieu de 19 : ce que porte
effectivement cette instance, rien du reste du hub).
"""
import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
STANDALONE_ROOT = os.path.dirname(HERE)
PROJECT_ROOT = os.path.dirname(STANDALONE_ROOT)
OUT_DIR = os.path.join(HERE, "generated")
OUT = os.path.join(OUT_DIR, "services.conf")

_main_path = os.path.join(PROJECT_ROOT, "tls-proxy", "render_nginx_conf.py")
_spec = importlib.util.spec_from_file_location("supervision_si_main_tls_proxy_render", _main_path)
_main_render = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_main_render)

parse_env = _main_render.parse_env
API_LOCATION_TEMPLATE = _main_render.API_LOCATION_TEMPLATE
SPA_LOCATION_TEMPLATE = _main_render.SPA_LOCATION_TEMPLATE
HEADER_TEMPLATE = _main_render.HEADER_TEMPLATE
FOOTER = _main_render.FOOTER

# (variable .env ; nom du service docker-compose ; port CONTENEUR
# interne ; chemin public ; type) -- mêmes chemins que le stack
# principal (/vault/, /api/vault/, /auth/) : vault/portal/vite.config.js
# a son "base" figé à "/vault/", partagé tel quel entre les deux
# stacks (voir keycloak/render.py de ce dossier pour le même
# raisonnement côté redirectUris).
SERVICES = [
    ("VAULT_STANDALONE_API_PORT", "vault-api-standalone", 5000, "/api/vault/", "api"),
    ("VAULT_STANDALONE_PORTAL_PORT", "vault-portal-standalone", 5173, "/vault/", "spa"),
    ("VAULT_STANDALONE_KEYCLOAK_PORT", "keycloak-standalone", 8080, "/auth/", "keycloak"),
]


def resolve_gateway_port(env):
    raw = os.environ.get(
        "VAULT_STANDALONE_GATEWAY_PORT", env.get("VAULT_STANDALONE_GATEWAY_PORT", "")
    ).strip()
    return raw if raw else "7443"


def build_config(env):
    gateway_port = resolve_gateway_port(env)
    locations = []
    summary = [f"  Port unique (VAULT_STANDALONE_GATEWAY_PORT) : {gateway_port}", ""]
    seen_paths = {}
    for var_name, service, container_port, path, kind in SERVICES:
        if path in seen_paths:
            raise ValueError(f"conflit de chemin : {path} déjà utilisé par {seen_paths[path]}")
        seen_paths[path] = service

        template = API_LOCATION_TEMPLATE if kind == "api" else SPA_LOCATION_TEMPLATE
        locations.append(template.format(path=path, service=service, container_port=container_port))
        summary.append(f"  {path:<20} -> {service}:{container_port}  ({kind}, {var_name} historique)")

    config = HEADER_TEMPLATE.format(gateway_port=gateway_port) + "\n".join(locations) + FOOTER
    return config, summary


def main():
    check_only = "--check" in sys.argv
    # MÊME .env que le hub -- voir docker-compose.yml de ce dossier.
    env = parse_env(os.path.join(PROJECT_ROOT, ".env"))

    try:
        config, summary = build_config(env)
    except ValueError as exc:
        print(f"ERREUR : {exc}", file=sys.stderr)
        return 1

    if check_only:
        print("Rendu vérifié (aucune écriture) :")
        print("\n".join(summary))
        return 0

    os.makedirs(OUT_DIR, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write(config)
    print(f"Config nginx isolée rendue -> {os.path.relpath(OUT, STANDALONE_ROOT)}")
    print("\n".join(summary))
    return 0


if __name__ == "__main__":
    sys.exit(main())
