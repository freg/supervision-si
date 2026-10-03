#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Socle commun d'un nœud (livraison #661, étape 1 de docs/architecture-clonage-distribution-hub.md, items 108-110) :
le sous-ensemble de services qui permet à N'IMPORTE QUEL hôte de recevoir et appliquer des déploiements et de servir
l'interface complète, indépendamment des tuiles métier qu'il héberge -- passerelle (tls-proxy), identité (keycloak),
tour de contrôle (services-api : livraisons zip, mise à jour git #659, plan, rebuild), front commun (hub), et le partagé
strictement nécessaire (memcached, prefs-api, rights-api, accounts-api, notify-api). Bibliothèque standard seulement.

  deploy/socle.py list                 services du socle : passerelle, principal, et dépendances compose NON démarrées
  deploy/socle.py up [--build] [+svc…] démarre le socle (gateway up -d, puis run.sh up -d --no-deps des services principaux)
                                       ; `+nom` ajoute une tuile et ses dépendances (ex. +si-agent-api)
  deploy/socle.py status               services du socle en marche / arrêtés (JSON)
  deploy/socle.py check                vérifie la reprise : .env, PKI (ca.crt, ca.key), clés .env manquantes (sync-env)

Le socle se démarre avec --no-deps : les API des tuiles absentes ne sont PAS lancées (le front les affiche indisponibles
ou, en étape 2, la passerelle les route vers le nœud qui les porte)."""
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "deploy"))

SOCLE = ["tls-proxy", "keycloak", "services-api", "hub", "memcached", "prefs-api", "rights-api", "accounts-api", "notify-api"]
REQUIRED_FILES = [".env", "pki/ca/ca.crt", "pki/ca/ca.key"]


def split(socle, info, origin):
    """-> (services passerelle, services principaux, dépendances compose non démarrées) ; passerelle = fermeture
    transitive dans gateway/ (tls-proxy -> keycloak), principal = liste exacte (--no-deps)."""
    gateway, main, skipped = [], [], set()
    for s in socle:
        if s not in info:
            raise RuntimeError("service inconnu du compose : " + s)
        (gateway if origin[s].startswith("gateway/") else main).append(s)
    todo = list(gateway)
    while todo:
        x = todo.pop()
        for d in info[x].get("depends", []):
            if d not in gateway and origin.get(d, "").startswith("gateway/"):
                gateway.append(d); todo.append(d)
    for s in main:
        for d in info[s].get("depends", []):
            if d not in main and d not in gateway:
                skipped.add(d)
    return gateway, main, sorted(skipped)


def extend(socle, extra, info):
    """`+tuile` : la tuile et sa fermeture de dépendances (hors network_mode host) rejoignent le socle."""
    out = list(socle)
    todo = list(extra)
    while todo:
        x = todo.pop()
        if x not in info:
            raise RuntimeError("service inconnu du compose : " + x)
        if x in out or info[x].get("host_network"):
            continue
        out.append(x)
        todo.extend(info[x].get("depends", []))
    return out


def commands(gateway, main, build=False):
    b = ["--build"] if build else []
    cmds = []
    if gateway:
        cmds.append(["./gateway/scripts/run.sh", "up", "-d"] + b + gateway)
    if main:
        cmds.append(["./scripts/run.sh", "up", "-d", "--no-deps"] + b + main)
    return cmds


def check_files(root=ROOT, exists=os.path.exists):
    """Reprise d'un socle sur un autre hôte : fichiers à recopier depuis l'hôte d'origine (jamais dans le dépôt)."""
    missing = [f for f in REQUIRED_FILES if not exists(os.path.join(root, f))]
    hints = {".env": "copier le .env de l'hôte d'origine (secrets communs : Keycloak, jetons internes, SI_NODE_TOKEN) puis python3 scripts/sync-env.py",
             "pki/ca/ca.crt": "copier pki/ca/ (CA interne du hub) depuis l'hôte d'origine : les postes la connaissent déjà ; une CA neuve = nouveaux avertissements",
             "pki/ca/ca.key": "idem (la clé signe le certificat serveur régénéré à chaque run.sh) -- rien à voir avec la CA du bastion si-proxy, qui ne se copie JAMAIS"}
    return [{"file": f, "hint": hints[f]} for f in missing]


def main():
    import cohorts as C
    cmd = sys.argv[1] if len(sys.argv) > 1 else "list"
    services, origin = C.load_services()
    info = C.analyse(services)
    extra = [a[1:] for a in sys.argv[2:] if a.startswith("+")]
    socle = extend(SOCLE, extra, info) if extra else list(SOCLE)
    gateway, main_, skipped = split(socle, info, origin)
    if cmd == "list":
        print(json.dumps({"gateway": gateway, "main": main_, "not_started": skipped}, indent=2, ensure_ascii=False))
        return 0
    if cmd == "check":
        miss = check_files()
        r = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "sync-env.py"), "--check"], cwd=ROOT, capture_output=True, text=True)
        print(json.dumps({"missing": miss, "sync_env": (r.stdout or r.stderr).strip()[-600:], "ok": not miss}, indent=2, ensure_ascii=False))
        return 0 if not miss else 1
    if cmd == "status":
        r = subprocess.run(["./scripts/run.sh", "ps", "--services", "--status", "running"], cwd=ROOT, capture_output=True, text=True)
        g = subprocess.run(["./gateway/scripts/run.sh", "ps", "--services", "--status", "running"], cwd=ROOT, capture_output=True, text=True)
        running = set((r.stdout or "").split()) | set((g.stdout or "").split())
        print(json.dumps({"running": sorted(s for s in gateway + main_ if s in running), "stopped": sorted(s for s in gateway + main_ if s not in running)}, indent=2, ensure_ascii=False))
        return 0
    if cmd == "up":
        miss = check_files()
        if miss:
            print("socle : fichiers manquants avant démarrage :\n - " + "\n - ".join("%s : %s" % (m["file"], m["hint"]) for m in miss), file=sys.stderr)
            return 1
        for c in commands(gateway, main_, "--build" in sys.argv):
            print("▶ " + " ".join(c), flush=True)
            if subprocess.run(c, cwd=ROOT).returncode:
                return 1
        print("socle démarré : %s" % ", ".join(gateway + main_))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
