#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Images construites HORS des nœuds de production (livraison #738, lot 3 du second hub).

Un nœud « constructeur » (`"builder": true` dans deploy/nodes.json) construit les images et les pousse dans un
registre local (registry:2, deploy/registry/) ; les autres nœuds ne font que les tirer : plus de construction sur la
VM du hub pendant les mises à jour. Activé par SI_REGISTRY dans .env (ex. 10.99.0.3:5005), sinon rien ne change.

  images.py override                  écrit deploy/generated/images.override.yml : image <registre>/supervision-si/<service>:<tag>
                                      pour chaque service construit (build:) ; tag = commit git courant (SI_IMAGE_TAG sinon)
  images.py build [services…]         (constructeur) construit puis pousse les images (2 en parallèle au plus)
  images.py pull  [services…]         (autres nœuds) tire les images du commit courant

run.sh ajoute images.override.yml à COMPOSE_FILE quand SI_REGISTRY est défini ; node_agent.py apply tire au lieu de
construire. Registre en HTTP sur le VPN : déclarer "insecure-registries" dans /etc/docker/daemon.json de chaque nœud.
"""
import os
import re
import subprocess
import sys

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "deploy", "generated", "images.override.yml")
REG_RE = re.compile(r"^[A-Za-z0-9.-]+(:\d{2,5})?$")


def load_env(path=os.path.join(ROOT, ".env")):
    env = {}
    try:
        for line in open(path, encoding="utf-8"):
            m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$", line.rstrip("\n"))
            if m:
                env[m.group(1)] = m.group(2).strip().strip('"').strip("'")
    except OSError:
        pass
    env.update({k: v for k, v in os.environ.items() if k.startswith("SI_")})
    return env


def registry(env=None):
    r = ((env if env is not None else load_env()).get("SI_REGISTRY") or "").strip().rstrip("/")
    if r and not REG_RE.match(r):
        raise ValueError("SI_REGISTRY invalide : %s (attendu hôte:port)" % r)
    return r


def git_tag(root=ROOT):
    try:
        return subprocess.run(["git", "rev-parse", "--short=12", "HEAD"], cwd=root, capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "latest"


def built_services(compose):
    """Services construits par le dépôt (clé build:) -> liste triée."""
    return sorted(s for s, v in (compose.get("services") or {}).items() if (v or {}).get("build"))


def image_override(compose, reg, tag, project="supervision-si"):
    """Override compose : une image par service construit, dans le registre, au tag du commit."""
    return {"services": {s: {"image": "%s/%s/%s:%s" % (reg, project, s, tag)} for s in built_services(compose)}}


def compose_files():
    files = [os.path.join(ROOT, "docker-compose.yml")]
    node = os.path.join(ROOT, "deploy", "generated", "node.override.yml")
    if os.path.isfile(node):
        files.append(node)
    return files


def write_override(env=None):
    reg = registry(env)
    if not reg:
        raise SystemExit("SI_REGISTRY non défini : construction locale inchangée")
    with open(os.path.join(ROOT, "docker-compose.yml"), encoding="utf-8") as fh:
        compose = yaml.safe_load(fh) or {}
    tag = (env or load_env()).get("SI_IMAGE_TAG") or git_tag()
    ov = image_override(compose, reg, tag)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write("# GÉNÉRÉ par deploy/images.py override -- registre %s, tag %s\n" % (reg, tag))
        yaml.safe_dump(ov, fh, sort_keys=False, width=200)
    return OUT, tag, len(ov["services"])


def compose_cmd(args):
    files = compose_files() + [OUT]
    cmd = ["docker", "compose"]
    for f in files:
        cmd += ["-f", f]
    return cmd + args


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    cmd = argv[0] if argv else "override"
    if cmd == "override":
        path, tag, n = write_override()
        print("%s : %d image(s), tag %s" % (path, n, tag))
        return 0
    if cmd in ("build", "pull"):
        write_override()
        env = dict(os.environ, COMPOSE_PARALLEL_LIMIT=os.environ.get("COMPOSE_PARALLEL_LIMIT", "2"))
        services = argv[1:]
        if cmd == "build":
            subprocess.run(compose_cmd(["build"] + services), cwd=ROOT, env=env, check=True)
            subprocess.run(compose_cmd(["push", "--ignore-push-failures"] + services), cwd=ROOT, env=env, check=True)
        else:
            subprocess.run(compose_cmd(["pull", "--ignore-pull-failures", "--quiet"] + services), cwd=ROOT, env=env, check=True)
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
