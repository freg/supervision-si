#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Sauvegarde TOTALE, restauration sur un autre host et régénération de ce
qui est propre à un host (livraison #458).

Demandé : « un mécanisme de backup total et de restore sur un autre host
avec un script de régénération de tout ce qui est unique pour un host
(clés...) ». Trois sous-commandes, appelées par scripts/backup-full.sh,
scripts/restore-full.sh et scripts/regenerate-host.sh :

  inventory   ce qui serait sauvegardé (rien n'est écrit)
  backup      archive chiffrée (AES-256, openssl enc -pbkdf2) contenant :
                manifest.json (host, IP, dépôt, livraison, volumes...),
                repo.bundle (git bundle de toutes les branches),
                env/ (.env, .env.encrypted), pki/ (CA + certs serveur),
                bind/ (tous les dossiers de données montés par les quatre
                compose : ./xxx/data, si-agent/data, ssh-tunnels/keys...),
                volumes/<nom>.tgz (volumes Docker nommés : PostgreSQL,
                Elasticsearch, Keycloak, Mayan, OpenLDAP de test),
                host-side/ (shim si-proxy : /etc/si-proxy, unité systemd),
                sql/ (pg_dump par base, portable, en plus des volumes).
  restore     dépose tout dans un dossier cible (clone depuis le bundle,
                .env, PKI, données, volumes recréés) -- SANS rien démarrer.
  regenerate  ce qui est propre au host : HOST_IP (et toute URL qui la
                contenait dans .env), certificat serveur (CA CONSERVÉE :
                les agents épinglent son empreinte), realm Keycloak, conf
                nginx, cert du relais si-proxy, EXPOSURE.json ; jetons du
                bastion sur demande (--rotate-tokens) -- JAMAIS les sels
                et phrases de chiffrement (*_SALT, *_PASSPHRASE : les
                secrets stockés deviendraient illisibles). Imprime la liste
                de ce qui reste à faire à la main (agents, shim, DNS...).

Ce qui est décidé ici et pourquoi :
  - l'archive est chiffrée par défaut (elle contient .env, la clé de la CA,
    les clés SSH, le coffre) ; --no-encrypt existe pour un support déjà
    chiffré ;
  - les volumes sont copiés tels quels (tar depuis un conteneur alpine),
    et les bases PostgreSQL AUSSI en pg_dump : la copie brute est exacte,
    le dump survit à un changement de version d'image ;
  - la CA n'est jamais régénérée par `regenerate` : la remplacer
    invaliderait l'épinglage de tous les agents et le certificat client de
    freg ; seul le certificat serveur (SAN = HOST_IP) est réémis ;
  - aucune commande destructive : `restore` refuse un dossier cible non
    vide sans --force, `regenerate` sauvegarde .env en .env.avant-regen.
Logique pure (parse, sélection, réécriture de .env, manifeste) testée dans
scripts/test_full_backup.py ; Docker/openssl/git via subprocess seulement.
"""
import argparse
import datetime as _dt
import getpass
import json
import os
import re
import secrets
import shutil
import socket
import subprocess
import sys
import tarfile
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
# (fichier, dossier de projet Compose) : gateway et mayan tournent avec
# --project-directory = racine du dépôt (leurs ./chemins y sont relatifs),
# vault-standalone est un stack autonome dans son dossier.
COMPOSE_FILES = [("docker-compose.yml", ""), ("gateway/docker-compose.yml", ""), ("mayan/docker-compose.yml", ""),
                 ("vault-standalone/docker-compose.yml", "vault-standalone")]
# Montages hôte qui NE sont PAS des données : générés au lancement, ou
# versionnés dans le dépôt (ils reviennent avec le clone).
GENERATED_OR_VERSIONED = ("tls-proxy/generated", "apache/generated", "keycloak/import", "keycloak/themes", "gateway/ldap-seed",
                          "db-init", "data-generator", "CHANGELOG.md", "BACKLOG.md", "/var/run/docker.sock")
# Variables de .env qu'on ne réécrit JAMAIS (rotation interdite : elles
# déchiffrent des secrets déjà stockés).
NEVER_ROTATE = re.compile(r"(_SALT|_PASSPHRASE|_SECRET_KEY|_MASTER_KEY)$")
ROTATABLE_TOKENS = ("SI_PROXY_HOST_TOKEN", "SI_PROXY_CLIENT_TOKEN", "SI_PROXY_ADMIN_TOKEN")
HOST_SIDE_FILES = ["/etc/si-proxy/host.env", "/etc/si-proxy/ca.crt", "/etc/systemd/system/si-proxy-host.service", "/opt/si-proxy"]

_VAR = re.compile(r"\$\{([A-Z0-9_]+)(?::-([^}]*))?\}")


# ---------------------------------------------------------------- pur --
def parse_env(text):
    out = {}
    for line in (text or "").split("\n"):
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        v = v.strip()
        if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
            v = v[1:-1]
        out[k.strip()] = v
    return out


def resolve(value, env):
    return _VAR.sub(lambda m: env.get(m.group(1)) or (m.group(2) or ""), str(value))


def host_mounts_from_compose(text, env, compose_dir=""):
    """Chemins HÔTE des montages `- <hôte>:<conteneur>[:ro]` d'un compose ->
    [{path (relatif à la racine du projet), kind: dir|file|volume}]. Les
    montages générés/versionnés (GENERATED_OR_VERSIONED) sont écartés."""
    out, seen = [], set()
    for line in text.split("\n"):
        m = re.match(r"^\s+- (.+)$", line)
        if not m:
            continue
        spec = re.sub(r"\s+#.*$", "", m.group(1)).strip().strip("'\"")
        resolved = resolve(spec, env)
        parts = resolved.split(":")
        if len(parts) < 2 or not parts[1].startswith("/"):
            continue  # pas un montage hôte:conteneur (port, variable d'env...)
        raw = spec[: spec.index(":" + parts[1])] if (":" + parts[1]) in spec else spec
        host = parts[0].strip()
        if host in (".",) or host.startswith("/var/run"):
            continue
        if not host or host in seen:
            continue
        seen.add(host)
        if any(g in host for g in GENERATED_OR_VERSIONED):
            continue
        if host.startswith("./") or host.startswith("../") or host.startswith("/"):
            path = host if host.startswith("/") else os.path.normpath(os.path.join(compose_dir, host))
            kind = "file" if os.path.splitext(path)[1] in (".sql", ".json", ".crt", ".key", ".md") else "dir"
            out.append({"path": path, "kind": kind, "raw": raw})
        elif re.match(r"^[a-zA-Z0-9_.-]+$", host):
            out.append({"path": host, "kind": "volume", "raw": raw})
    return out


def named_volumes_from_compose(text):
    """Noms déclarés sous `volumes:` (racine) d'un compose."""
    names, in_vol = [], False
    for line in text.split("\n"):
        if re.match(r"^volumes:\s*$", line):
            in_vol = True
            continue
        if in_vol and re.match(r"^[a-zA-Z_]", line):
            in_vol = False
        if in_vol:
            m = re.match(r"^  ([a-zA-Z0-9_.-]+):\s*$", line)
            if m:
                names.append(m.group(1))
    return names


def match_docker_volumes(declared, existing):
    """Volumes Docker existants correspondant aux noms déclarés : nom exact
    ou `<projet>_<nom>` (préfixe Compose). -> [{name, declared}]"""
    out = []
    for name in existing:
        for d in declared:
            if name == d or name.endswith("_" + d):
                out.append({"name": name, "declared": d})
                break
    return out


def project_prefix(volume_name, declared):
    return volume_name[: -len(declared) - 1] if volume_name.endswith("_" + declared) and volume_name != declared else ""


def rewrite_env_for_host(text, old_ip, new_ip, rotate_tokens=False, hub_name=None):
    """Réécrit .env pour un nouveau host : HOST_IP, toute valeur contenant
    l'ancienne IP (URLs publiques, SI_AGENT_PUBLIC_URL...), jetons du bastion
    si demandé. Jamais les sels/phrases. -> (texte, [changements])."""
    changes, out = [], []
    for line in text.split("\n"):
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            out.append(line)
            continue
        k, _, v = line.partition("=")
        key = k.strip()
        newv = v
        if key == "HOST_IP" and new_ip:
            newv = new_ip
        elif old_ip and new_ip and old_ip in v and not NEVER_ROTATE.search(key):
            newv = v.replace(old_ip, new_ip)
        if rotate_tokens and key in ROTATABLE_TOKENS and v.strip():
            newv = secrets.token_hex(24)
        if hub_name and key == "SI_PROXY_HUB_NAME":
            newv = hub_name
        if newv != v:
            changes.append(key)
            out.append(f"{k}={newv}")
        else:
            out.append(line)
    return "\n".join(out), changes


def build_manifest(env, mounts, volumes, git_info, extra=None):
    return {"format": 1, "created_at": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
            "hostname": socket.gethostname(), "host_ip": env.get("HOST_IP", ""), "gateway_port": env.get("GATEWAY_PORT", "6443"),
            "pki_dir": env.get("PKI_DIR", ""), "project_dir": os.path.basename(ROOT), "git": git_info,
            "mounts": mounts, "volumes": volumes, **(extra or {})}


def checklist(manifest, new_ip, changes, rotated):
    """Ce qui reste à faire à la main sur le nouveau host (texte)."""
    old_ip = (manifest or {}).get("host_ip") or "?"
    port = (manifest or {}).get("gateway_port") or "6443"
    lines = [f"Ancien host : {old_ip} -> nouveau : {new_ip or '?'} (.env : {', '.join(changes) or 'aucun changement'})", ""]
    lines += [
        "À faire à la main :",
        f"  1. Agents hôtes (si-agent) et sondes (netprobe) : ils visent l'ancien central https://{old_ip}:{port}/api/... ;",
        "     mettre à jour central_url dans leur agent.json (ou réenrôler depuis la tuile). Leur épinglage de CA reste valide (CA conservée).",
        f"  2. Shim si-proxy du host : sudo ./si-proxy/install-host.sh --relay {new_ip or '<host>'}:6450 --token \"$SI_PROXY_HOST_TOKEN\" --ca si-proxy/certs/ca.crt --shell-user freg",
        "     (jeton " + ("RÉGÉNÉRÉ : reprendre la nouvelle valeur dans .env" if rotated else "inchangé") + ") ; client Mac : --relay avec la nouvelle adresse.",
        "  3. Keycloak : le realm importé contient les anciennes URL -- au prochain gateway/scripts/run.sh, accepter la purge/réimport du realm",
        "     (ou, sans purge, corriger les Valid redirect URIs des clients dans la console).",
        "  4. DNS / pare-feu / redirection de port vers le nouveau host ; navigateurs : la CA est la même, rien à réimporter.",
        "  5. Lancer : ./gateway/scripts/run.sh up -d  puis  ./scripts/run.sh up -d --build  (et mayan/, vault-standalone/ si utilisés).",
        "  6. Contrôler dans la console Bastion (onglet Entrées) l'exposition du nouveau host.",
    ]
    return "\n".join(lines)


# ------------------------------------------------------------- outils --
def sh(cmd, check=True, capture=False, cwd=None):
    r = subprocess.run(cmd, shell=isinstance(cmd, str), check=False, cwd=cwd,
                       stdout=subprocess.PIPE if capture else None, stderr=subprocess.PIPE if capture else None, text=True)
    if check and r.returncode != 0:
        raise SystemExit("commande échouée : %s\n%s" % (cmd, (r.stderr or "") if capture else ""))
    return r.stdout if capture else r.returncode


def docker_ok():
    return shutil.which("docker") is not None and subprocess.run(["docker", "info"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0


def load_env():
    p = os.path.join(ROOT, ".env")
    return parse_env(open(p, encoding="utf-8").read()) if os.path.exists(p) else {}


def collect_mounts(env):
    mounts = []
    for cf, rel_dir in COMPOSE_FILES:
        p = os.path.join(ROOT, cf)
        if not os.path.exists(p):
            continue
        for m in host_mounts_from_compose(open(p, encoding="utf-8").read(), env, rel_dir):
            m["compose"] = cf
            mounts.append(m)
    # PKI : dossier entier (ca/ + server/), qu'il soit dans l'arbre ou externe
    pki = env.get("PKI_DIR") or "pki"
    mounts.append({"path": pki, "kind": "dir", "raw": "PKI_DIR", "compose": "-"})
    # dédoublonnage par chemin, dossiers avant fichiers
    seen, out = set(), []
    for m in mounts:
        if m["kind"] == "volume" or m["path"] in seen:
            continue
        seen.add(m["path"])
        out.append(m)
    return out


def declared_volumes():
    names = []
    for cf, _dir in COMPOSE_FILES:
        p = os.path.join(ROOT, cf)
        if os.path.exists(p):
            names += named_volumes_from_compose(open(p, encoding="utf-8").read())
    return sorted(set(names))


def git_info():
    try:
        branch = sh("git rev-parse --abbrev-ref HEAD", capture=True, cwd=ROOT).strip()
        commit = sh("git rev-parse HEAD", capture=True, cwd=ROOT).strip()
    except SystemExit:
        return {"branch": None, "commit": None}
    dn = os.path.join(ROOT, "shared", "DELIVERY_NUMBER")
    return {"branch": branch, "commit": commit, "delivery": open(dn).read().strip() if os.path.exists(dn) else None}


def abs_path(p):
    return p if os.path.isabs(p) else os.path.join(ROOT, p)


# --------------------------------------------------------- inventory --
def cmd_inventory(args):
    env = load_env()
    mounts = collect_mounts(env)
    vols = declared_volumes()
    existing = sh("docker volume ls --format '{{.Name}}'", capture=True).split() if docker_ok() else []
    matched = match_docker_volumes(vols, existing)
    print("Dépôt : %s (%s)" % (ROOT, json.dumps(git_info())))
    print("HOST_IP : %s · PKI_DIR : %s" % (env.get("HOST_IP", "?"), env.get("PKI_DIR") or "pki/ (dans l'arbre)"))
    print("\nDossiers/fichiers de données (montages hôte des compose) :")
    for m in mounts:
        p = abs_path(m["path"])
        print("  %s %-45s %s" % ("✓" if os.path.exists(p) else "·", m["path"], "" if os.path.exists(p) else "(absent, ignoré)"))
    print("\nVolumes Docker déclarés : %s" % ", ".join(vols))
    print("Volumes Docker présents : %s" % (", ".join(v["name"] for v in matched) or ("aucun" if existing else "docker indisponible ici")))
    print("\nCôté host (shim si-proxy) : %s" % ", ".join(f for f in HOST_SIDE_FILES if os.path.exists(f)) or "rien")
    return 0


# ------------------------------------------------------------ backup --
def _passphrase(args, confirm=False):
    if args.no_encrypt:
        return None
    if args.passphrase_file:
        return open(args.passphrase_file, encoding="utf-8").read().strip()
    if os.environ.get("SI_BACKUP_PASSPHRASE"):
        return os.environ["SI_BACKUP_PASSPHRASE"]
    p = getpass.getpass("Phrase de passe de l'archive : ")
    if confirm and getpass.getpass("Confirmer : ") != p:
        raise SystemExit("phrases différentes")
    if not p:
        raise SystemExit("phrase vide -- utiliser --no-encrypt pour une archive en clair")
    return p


def cmd_backup(args):
    env = load_env()
    mounts = collect_mounts(env)
    vols = declared_volumes()
    use_docker = docker_ok() and not args.no_docker
    existing = sh("docker volume ls --format '{{.Name}}'", capture=True).split() if use_docker else []
    matched = match_docker_volumes(vols, existing)
    stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    name = "supervision-si-backup-%s-%s" % (socket.gethostname(), stamp)
    out_dir = os.path.abspath(args.out)
    os.makedirs(out_dir, exist_ok=True)
    passphrase = _passphrase(args, confirm=True)
    work = tempfile.mkdtemp(prefix="si-backup-")
    stage = os.path.join(work, name)
    os.makedirs(stage)
    # 1. dépôt : bundle de toutes les branches
    print("• dépôt git (bundle)")
    sh(["git", "bundle", "create", os.path.join(stage, "repo.bundle"), "--all"], cwd=ROOT)
    # 2. .env
    os.makedirs(os.path.join(stage, "env"))
    for f in (".env", ".env.encrypted", ".env.encrypted.salt"):
        if os.path.exists(os.path.join(ROOT, f)):
            shutil.copy2(os.path.join(ROOT, f), os.path.join(stage, "env", f))
    # 3. montages hôte (données, PKI, clés, certs si-proxy...)
    print("• dossiers de données (%d montages)" % len(mounts))
    saved_mounts = []
    with tarfile.open(os.path.join(stage, "bind.tar"), "w") as tf:
        for m in mounts:
            p = abs_path(m["path"])
            if not os.path.exists(p):
                continue
            arc = m["path"] if not os.path.isabs(m["path"]) else "ABS" + m["path"]
            tf.add(p, arcname=arc)
            saved_mounts.append({**m, "arcname": arc, "absolute": os.path.isabs(m["path"])})
    # 4. volumes Docker
    saved_vols = []
    if matched:
        os.makedirs(os.path.join(stage, "volumes"))
        for v in matched:
            print("• volume %s" % v["name"])
            sh(["docker", "run", "--rm", "-v", "%s:/v:ro" % v["name"], "-v", "%s:/b" % os.path.join(stage, "volumes"), "alpine",
                "tar", "czf", "/b/%s.tgz" % v["name"], "-C", "/v", "."])
            saved_vols.append(v)
        # pg_dump des PostgreSQL en cours d'exécution (portable)
        if not args.no_sql:
            os.makedirs(os.path.join(stage, "sql"))
            ps = sh("docker ps --format '{{.Names}}\t{{.Image}}'", capture=True)
            for line in ps.splitlines():
                cname, image = (line.split("\t") + [""])[:2]
                if "postgres" in image:
                    print("• pg_dumpall %s" % cname)
                    r = subprocess.run(["docker", "exec", cname, "sh", "-c", "pg_dumpall -U \"${POSTGRES_USER:-postgres}\""],
                                       stdout=open(os.path.join(stage, "sql", cname + ".sql"), "w"), stderr=subprocess.PIPE, text=True)
                    if r.returncode != 0:
                        print("  (échec, ignoré : %s)" % r.stderr.strip()[:120])
    elif use_docker:
        print("• aucun volume Docker correspondant (stack jamais lancé ici ?)")
    else:
        print("• Docker indisponible ou --no-docker : volumes et pg_dump omis")
    # 5. côté host (shim si-proxy)
    hs = [f for f in HOST_SIDE_FILES if os.path.exists(f)]
    if hs:
        print("• côté host : %s" % ", ".join(hs))
        with tarfile.open(os.path.join(stage, "host-side.tar"), "w") as tf:
            for f in hs:
                try:
                    tf.add(f, arcname=f.lstrip("/"))
                except PermissionError:
                    print("  (lecture refusée : %s -- relancer en sudo pour l'inclure)" % f)
    # 6. manifeste
    manifest = build_manifest(env, saved_mounts, saved_vols, git_info(), {"host_side": hs, "encrypted": passphrase is not None, "name": name})
    with open(os.path.join(stage, "manifest.json"), "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=1)
    # 7. archive (+ chiffrement)
    tar_path = os.path.join(work, name + ".tar.gz")
    with tarfile.open(tar_path, "w:gz") as tf:
        tf.add(stage, arcname=name)
    if passphrase:
        final = os.path.join(out_dir, name + ".tar.gz.enc")
        subprocess.run(["openssl", "enc", "-aes-256-cbc", "-pbkdf2", "-salt", "-in", tar_path, "-out", final, "-pass", "stdin"],
                       input=passphrase + "\n", text=True, check=True)
        os.remove(tar_path)
    else:
        final = os.path.join(out_dir, name + ".tar.gz")
        shutil.move(tar_path, final)
    shutil.rmtree(work, ignore_errors=True)
    os.chmod(final, 0o600)
    print("\nArchive : %s (%.1f Mo, %s)" % (final, os.path.getsize(final) / 1e6, "chiffrée AES-256" if passphrase else "EN CLAIR"))
    print("Contenu : bundle git, .env, %d montages, %d volumes, côté host : %d" % (len(saved_mounts), len(saved_vols), len(hs)))
    return 0


# ----------------------------------------------------------- restore --
def cmd_restore(args):
    src = os.path.abspath(args.archive)
    into = os.path.abspath(args.into)
    if os.path.exists(into) and os.listdir(into) and not args.force:
        raise SystemExit("dossier cible non vide : %s (--force pour y déposer quand même)" % into)
    work = tempfile.mkdtemp(prefix="si-restore-")
    tar_path = src
    if src.endswith(".enc"):
        passphrase = _passphrase(args)
        tar_path = os.path.join(work, "archive.tar.gz")
        r = subprocess.run(["openssl", "enc", "-d", "-aes-256-cbc", "-pbkdf2", "-in", src, "-out", tar_path, "-pass", "stdin"],
                           input=(passphrase or "") + "\n", text=True)
        if r.returncode != 0:
            raise SystemExit("déchiffrement échoué (mauvaise phrase ?)")
    with tarfile.open(tar_path, "r:gz") as tf:
        tf.extractall(work)
    stage = next(os.path.join(work, d) for d in os.listdir(work) if os.path.isdir(os.path.join(work, d)))
    manifest = json.load(open(os.path.join(stage, "manifest.json"), encoding="utf-8"))
    print("Archive du %s, host %s (%s), livraison #%s, branche %s" % (manifest["created_at"], manifest["hostname"], manifest["host_ip"],
          manifest["git"].get("delivery"), manifest["git"].get("branch")))
    os.makedirs(into, exist_ok=True)
    # 1. dépôt
    if not os.path.isdir(os.path.join(into, ".git")):
        print("• clone depuis le bundle")
        sh(["git", "clone", "-q", os.path.join(stage, "repo.bundle"), into])
        branch = manifest["git"].get("branch")
        if branch and branch != "HEAD":
            sh(["git", "checkout", "-q", branch], cwd=into)
    else:
        print("• dépôt déjà présent, conservé (fetch du bundle possible : git fetch <bundle> --all)")
    # 2. .env
    for f in os.listdir(os.path.join(stage, "env")):
        shutil.copy2(os.path.join(stage, "env", f), os.path.join(into, f))
        os.chmod(os.path.join(into, f), 0o600)
    print("• .env restauré")
    # 3. montages
    with tarfile.open(os.path.join(stage, "bind.tar")) as tf:
        for member in tf.getmembers():
            if member.name.startswith("ABS/"):
                member.name = member.name[3:]  # chemin absolu d'origine (PKI_DIR externe...)
                dest = "/"
            else:
                dest = into
            if member.name.startswith("/") and not args.absolute:
                # chemins absolus : déposés sous <cible>/_absolute/ sauf --absolute
                member.name = "_absolute" + member.name
                dest = into
            tf.extract(member, dest)
    print("• données restaurées (%d montages%s)" % (len(manifest["mounts"]), "" if args.absolute else " ; chemins absolus sous _absolute/"))
    # 4. volumes Docker
    vdir = os.path.join(stage, "volumes")
    new_prefix = os.path.basename(into)
    if os.path.isdir(vdir):
        if docker_ok() and not args.no_docker:
            for v in manifest["volumes"]:
                old_prefix = project_prefix(v["name"], v["declared"])
                name = v["name"] if not old_prefix else "%s_%s" % (args.project_name or new_prefix, v["declared"])
                if old_prefix and old_prefix not in (new_prefix, args.project_name):
                    print("  (volume %s : préfixe de projet %s -> %s)" % (v["name"], old_prefix, args.project_name or new_prefix))
                print("• volume %s" % name)
                sh(["docker", "volume", "create", name], capture=True)
                sh(["docker", "run", "--rm", "-v", "%s:/v" % name, "-v", "%s:/b:ro" % vdir, "alpine",
                    "sh", "-c", "cd /v && tar xzf /b/%s.tgz" % v["name"]])
        else:
            keep = os.path.join(into, "_volumes-a-restaurer")
            shutil.copytree(vdir, keep, dirs_exist_ok=True)
            print("• Docker indisponible : volumes déposés dans %s (docker volume create X ; docker run --rm -v X:/v -v %s:/b alpine sh -c 'cd /v && tar xzf /b/<nom>.tgz')" % (keep, keep))
    # 5. côté host
    if os.path.exists(os.path.join(stage, "host-side.tar")):
        hs = os.path.join(into, "_host-side")
        with tarfile.open(os.path.join(stage, "host-side.tar")) as tf:
            tf.extractall(hs)
        print("• fichiers côté host déposés dans %s (à replacer en sudo : /etc/si-proxy, unité systemd, /opt/si-proxy -- ou réinstaller via install-host.sh)" % hs)
    if os.path.isdir(os.path.join(stage, "sql")):
        shutil.copytree(os.path.join(stage, "sql"), os.path.join(into, "_sql-dumps"), dirs_exist_ok=True)
        print("• dumps SQL dans _sql-dumps/ (secours : psql -f si un volume ne remonte pas)")
    shutil.copy2(os.path.join(stage, "manifest.json"), os.path.join(into, ".restore-manifest.json"))
    shutil.rmtree(work, ignore_errors=True)
    print("\nRestauration déposée dans %s -- rien n'est démarré. Étape suivante : ./scripts/regenerate-host.sh" % into)
    return 0


# -------------------------------------------------------- regenerate --
def cmd_regenerate(args):
    env_path = os.path.join(ROOT, ".env")
    if not os.path.exists(env_path):
        raise SystemExit(".env absent : restaurer d'abord (ou copier .env.example)")
    text = open(env_path, encoding="utf-8").read()
    env = parse_env(text)
    manifest = {}
    mp = os.path.join(ROOT, ".restore-manifest.json")
    if os.path.exists(mp):
        manifest = json.load(open(mp, encoding="utf-8"))
    old_ip = manifest.get("host_ip") or env.get("HOST_IP", "")
    new_ip = args.host_ip or os.environ.get("HOST_IP") or ""
    if not new_ip:
        r = subprocess.run(["bash", "-c", "source '%s/shared/detect-host-ip.sh' && detect_host_ip" % ROOT], capture_output=True, text=True)
        new_ip = r.stdout.strip()
    if not new_ip:
        raise SystemExit("HOST_IP indétectable : --host-ip <ip>")
    new_text, changes = rewrite_env_for_host(text, old_ip, new_ip, rotate_tokens=args.rotate_tokens)
    print("HOST_IP : %s -> %s ; .env : %s" % (old_ip or "?", new_ip, ", ".join(changes) or "inchangé"))
    if args.dry_run:
        print(checklist(manifest, new_ip, changes, args.rotate_tokens))
        return 0
    if new_text != text:
        shutil.copy2(env_path, env_path + ".avant-regen")
        open(env_path, "w", encoding="utf-8").write(new_text)
        os.chmod(env_path, 0o600)
    env = parse_env(new_text)
    os.environ["HOST_IP"] = new_ip
    steps = [
        ("CA (conservée si présente)", ["bash", os.path.join(ROOT, "pki/scripts/generate-ca.sh")]),
        ("certificat serveur (SAN = nouvelle IP)", ["bash", os.path.join(ROOT, "pki/scripts/generate-server-cert.sh")]),
        ("realm Keycloak", [sys.executable, os.path.join(ROOT, "keycloak/render.py")]),
        ("configuration nginx (passerelle)", [sys.executable, os.path.join(ROOT, "tls-proxy/render_nginx_conf.py")]),
        ("inventaire d'exposition", [sys.executable, os.path.join(ROOT, "scripts/render-exposure.py")]),
    ]
    if os.path.exists(os.path.join(ROOT, "si-proxy/certs/relay.crt")) or args.hub_name:
        hub = args.hub_name or new_ip
        steps.append(("certificat du relais si-proxy (%s)" % hub, ["bash", os.path.join(ROOT, "si-proxy/setup-certs.sh"), hub]))
    for label, cmd in steps:
        if args.skip and any(s in label for s in args.skip):
            print("· %s : sauté" % label)
            continue
        r = subprocess.run(cmd, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        print("%s %s%s" % ("✓" if r.returncode == 0 else "✗", label, "" if r.returncode == 0 else " : " + r.stdout.strip()[-300:]))
    print()
    print(checklist(manifest, new_ip, changes, args.rotate_tokens))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("inventory")
    b = sub.add_parser("backup")
    b.add_argument("--out", default=os.path.join(ROOT, "backups"))
    b.add_argument("--passphrase-file")
    b.add_argument("--no-encrypt", action="store_true")
    b.add_argument("--no-docker", action="store_true")
    b.add_argument("--no-sql", action="store_true")
    r = sub.add_parser("restore")
    r.add_argument("archive")
    r.add_argument("--into", required=True)
    r.add_argument("--passphrase-file")
    r.add_argument("--no-encrypt", action="store_true", help="(ignoré : déduit de l'extension)")
    r.add_argument("--no-docker", action="store_true")
    r.add_argument("--force", action="store_true")
    r.add_argument("--absolute", action="store_true", help="réécrire les chemins absolus (PKI_DIR externe...) à leur place d'origine")
    r.add_argument("--project-name", help="préfixe des volumes Compose sur le nouveau host (défaut : nom du dossier cible)")
    g = sub.add_parser("regenerate")
    g.add_argument("--host-ip")
    g.add_argument("--hub-name", help="nom DNS du hub pour le certificat du relais si-proxy (défaut : l'IP)")
    g.add_argument("--rotate-tokens", action="store_true", help="nouveaux jetons SI_PROXY_* (jamais les sels/phrases)")
    g.add_argument("--skip", action="append", default=[], help="étape à sauter (mot du libellé, ex. Keycloak)")
    g.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    return {"inventory": cmd_inventory, "backup": cmd_backup, "restore": cmd_restore, "regenerate": cmd_regenerate}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
