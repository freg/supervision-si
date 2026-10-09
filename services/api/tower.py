# -*- coding: utf-8 -*-
"""Tour de contrôle du hub (livraison #586) -- logique PURE, testable sans
Docker ni fichiers réels :

- livraisons : chemins sûrs d'une archive (zip slip), fichiers protégés
  (.env, registres locaux) ou conservés (données), classement
  ajouté / modifié / inchangé ;
- plan : d'après les fichiers modifiés, quels services reconstruire
  (sources COPY/ADD de leur Dockerfile), redémarrer (montages), quelle
  passerelle recharger -- seulement parmi les services EN MARCHE (un
  profil allégé ne doit jamais tout démarrer) ;
- configurations JSON (registres Cisco / MikroTik) : schéma, validation,
  fusion par nom ;
- auto-réparation : décision de redémarrage des services rouges, avec
  seuil et plafond horaire.
"""
import fnmatch
import posixpath
import re

# -- livraisons ----------------------------------------------------------------
PROTECTED = (".env", "*.local.json", "*/certs/*.key", "services/data/*")   # jamais écrasés
KEEP_IF_EXISTS = ("*/data/*", "data/*", "backups/*", "gateway/ldap-seed/*")                        # créés s'ils manquent, jamais écrasés
IGNORED_FOR_PLAN = ("shared/VERSION.json", "shared/EXPOSURE.json", "shared/DELIVERY_NUMBER", "CHANGELOG.md", "BACKLOG.md")
SERVICE_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,62}$")


def norm(path):
    p = posixpath.normpath(str(path or "").replace("\\", "/"))
    while p.startswith("./"):
        p = p[2:]
    return "" if p in (".", "/") else p


def strip_prefix(names):
    """Préfixe commun d'archive (git archive --prefix=projet/) à retirer, ou ""."""
    firsts = {n.split("/", 1)[0] for n in names if n}
    if len(firsts) == 1 and all("/" in n for n in names if n):
        return firsts.pop() + "/"
    return ""


def safe_member(name, prefix=""):
    """Nom d'entrée d'archive -> chemin relatif sûr, ou None (répertoire,
    absolu, remontée « .. », vide)."""
    if not name or name.endswith("/"):
        return None
    if prefix and name.startswith(prefix):
        name = name[len(prefix):]
    if name.startswith("/") or re.match(r"^[A-Za-z]:", name):
        return None
    parts = name.replace("\\", "/").split("/")
    if any(p == ".." for p in parts):
        return None
    rel = norm(name)
    return rel or None


def classify(rel, new_sha, local_sha):
    """-> added | changed | unchanged | protected | kept."""
    if any(fnmatch.fnmatch(rel, p) for p in PROTECTED):
        return "protected"
    if local_sha is None:
        return "added"
    if local_sha == new_sha:
        return "unchanged"
    if any(fnmatch.fnmatch(rel, p) for p in KEEP_IF_EXISTS):
        return "kept"
    return "changed"


# -- plan de reconstruction ------------------------------------------------------
def _join_continuations(text):
    return re.sub(r"\\\s*\n", " ", text or "")


def dockerfile_sources(text):
    """Chemins sources (relatifs au contexte) des COPY/ADD d'un Dockerfile,
    sans les copies inter-étapes (--from=) ; un motif est ramené à son
    dossier. « . » = tout le contexte."""
    out = []
    for line in _join_continuations(text).splitlines():
        m = re.match(r"^\s*(COPY|ADD)\s+(.*)$", line, re.I)
        if not m:
            continue
        rest = m.group(2).strip()
        if re.search(r"--from=", rest):
            continue
        if rest.startswith("["):
            try:
                import json
                items = json.loads(rest)
            except ValueError:
                continue
        else:
            items = [t for t in rest.split() if not t.startswith("--")]
        for src in items[:-1]:
            if re.match(r"^[a-z]+://", src):
                continue
            g = re.search(r"[*?\[]", src)
            if g:
                src = posixpath.dirname(src[:g.start()]) or "."
            out.append(src)
    return out


def service_paths(services, base_dir, read_file):
    """compose `services` -> {service: {"build": [préfixes], "mounts": [préfixes]}}
    (chemins relatifs à la racine du projet). `base_dir` = dossier du fichier
    compose relatif à la racine ; `read_file(rel)` -> texte ou None."""
    out = {}
    for name, svc in (services or {}).items():
        svc = svc or {}
        build, mounts = [], []
        b = svc.get("build")
        if b:
            if isinstance(b, str):
                b = {"context": b}
            ctx = norm(posixpath.join(base_dir, b.get("context") or "."))
            dockerfile = norm(posixpath.join(ctx, b.get("dockerfile") or "Dockerfile"))
            build.append(dockerfile)
            for src in dockerfile_sources(read_file(dockerfile) or ""):
                build.append(norm(posixpath.join(ctx, src)))
        for v in svc.get("volumes") or []:
            src = v.split(":", 1)[0] if isinstance(v, str) else (v or {}).get("source", "")
            if isinstance(v, dict) and v.get("type") not in (None, "bind"):
                continue
            if not src or "$" in src or not (src.startswith("./") or src.startswith("../") or src == "."):
                continue
            mounts.append(norm(posixpath.join(base_dir, src)))
        out[name] = {"build": sorted(set(build)), "mounts": sorted(set(mounts))}
    return out


def _under(prefix, rel):
    return prefix == "" or rel == prefix or rel.startswith(prefix + "/")


def relevant_changes(changed):
    return [r for r in changed if r not in IGNORED_FOR_PLAN and not r.lower().endswith(".md")]


def plan_for_changes(changed, main_paths, running, main_compose="docker-compose.yml", gateway_running=True):
    """-> {steps:[{label, cmd}], rebuild, restart, not_running, compose_changed, gateway}.
    `running` = services du stack principal actuellement en marche."""
    rel = relevant_changes(changed)
    running = set(running or [])
    rebuild, restart = set(), set()
    for svc, p in (main_paths or {}).items():
        if any(_under(pre, r) for pre in p["build"] for r in rel):
            rebuild.add(svc)
        elif any(_under(pre, r) for pre in p["mounts"] for r in rel):
            restart.add(svc)
    compose_changed = main_compose in changed
    gateway = any(r.startswith("tls-proxy/") or r.startswith("gateway/") for r in rel)
    not_running = sorted((rebuild | restart) - running)
    rebuild_r = sorted(rebuild & running)
    restart_r = sorted((restart & running) - rebuild)
    steps = []
    if ".env.example" in changed:
        steps.append({"label": "clés .env manquantes (sync-env)", "cmd": "python3 scripts/sync-env.py"})
    if rebuild_r:
        steps.append({"label": "reconstruire %d service(s)" % len(rebuild_r), "cmd": "./scripts/run.sh up -d --build " + " ".join(rebuild_r)})
    if compose_changed and running:
        steps.append({"label": "appliquer docker-compose.yml aux services en marche", "cmd": "./scripts/run.sh up -d " + " ".join(sorted(running))})
    if restart_r:
        steps.append({"label": "redémarrer %d service(s) (fichiers montés)" % len(restart_r), "cmd": "./scripts/run.sh restart " + " ".join(restart_r)})
    if gateway and gateway_running:
        steps.append({"label": "recharger la passerelle (tls-proxy)", "cmd": "./gateway/scripts/run.sh up -d --force-recreate tls-proxy"})
    return {"steps": steps, "rebuild": rebuild_r, "restart": restart_r, "not_running": not_running,
            "compose_changed": compose_changed, "gateway": gateway, "relevant": len(rel)}


def rebuild_steps(services):
    names = [s for s in services if SERVICE_RE.match(s)]
    return [{"label": "reconstruire " + ", ".join(names), "cmd": "./scripts/run.sh up -d --build " + " ".join(names)}] if names else []


GATEWAY_RELOAD = [{"label": "recharger la passerelle (tls-proxy)", "cmd": "./gateway/scripts/run.sh up -d --force-recreate tls-proxy"}]


# -- configurations JSON ---------------------------------------------------------
NAME_RE = r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$"  # = cisco/app.py
CONFIGS = {
    "cisco": {
        "label": "Équipements Cisco", "path": "cisco/switches.local.json", "example": "cisco/switches.json", "key": "switches",
        "consumer": "cisco-api (relu à chaque appel)",
        "fields": [
            {"name": "name", "label": "nom", "type": "str", "required": True, "pattern": NAME_RE},
            {"name": "host", "label": "hôte / IP", "type": "str", "required": True},
            {"name": "platform", "label": "plateforme", "type": "choice", "choices": ["ios", "nxos"], "default": "ios"},
            {"name": "transport", "label": "transport", "type": "choice", "choices": ["ssh", "telnet"], "default": "ssh"},
            {"name": "port", "label": "port", "type": "int"},
            {"name": "credential", "label": "accès du coffre", "type": "str", "required": True, "default": "cisco"},
            {"name": "enable_credential", "label": "accès enable", "type": "str"},
            {"name": "site", "label": "site", "type": "str"},
            {"name": "description", "label": "description", "type": "str"},
        ],
    },
    "mikrotik": {
        "label": "Routeurs MikroTik", "path": "mikrotik/routers.local.json", "example": "mikrotik/routers.json", "key": "routers",
        "consumer": "mikrotik-api (relu à chaque appel)",
        "fields": [
            {"name": "name", "label": "nom", "type": "str", "required": True, "pattern": NAME_RE},
            {"name": "host", "label": "hôte / IP", "type": "str", "required": True},
            {"name": "transport", "label": "transport", "type": "choice", "choices": ["rest", "ssh"], "default": "rest"},
            {"name": "port", "label": "port (443 REST / 22 SSH)", "type": "int"},
            {"name": "credential", "label": "accès du coffre", "type": "str", "required": True, "default": "default"},
            {"name": "site", "label": "site", "type": "str"},
            {"name": "description", "label": "description", "type": "str"},
        ],
    },
}


def items_of(kind, data):
    spec = CONFIGS[kind]
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and isinstance(data.get(spec["key"]), list):
        return data[spec["key"]]
    raise ValueError("JSON attendu : {\"%s\": [...]} ou une liste" % spec["key"])


def validate_config(kind, data):
    """-> (document normalisé, erreurs, avertissements)."""
    spec = CONFIGS[kind]
    errors, warnings, out, seen = [], [], [], set()
    try:
        items = items_of(kind, data)
    except ValueError as exc:
        return None, [str(exc)], []
    fields = {f["name"]: f for f in spec["fields"]}
    for i, it in enumerate(items, 1):
        if not isinstance(it, dict):
            errors.append("ligne %d : objet attendu" % i)
            continue
        row = {}
        for k in it:
            if k not in fields:
                warnings.append("ligne %d : champ inconnu « %s » ignoré" % (i, k))
        for f in spec["fields"]:
            v = it.get(f["name"])
            if isinstance(v, str):
                v = v.strip()
            if v in (None, ""):
                if f.get("required") and f.get("default") is None:
                    errors.append("ligne %d : « %s » obligatoire" % (i, f["label"]))
                    continue
                if f.get("default") is not None and f.get("required"):
                    v = f["default"]
                else:
                    continue
            if f["type"] == "int":
                try:
                    v = int(v)
                    if not 1 <= v <= 65535:
                        raise ValueError
                except (TypeError, ValueError):
                    errors.append("ligne %d : « %s » doit être un port (1-65535)" % (i, f["label"]))
                    continue
            elif f["type"] == "choice":
                v = str(v).lower()
                if v not in f["choices"]:
                    errors.append("ligne %d : « %s » doit valoir %s" % (i, f["label"], " / ".join(f["choices"])))
                    continue
            else:
                v = str(v)
                if f.get("pattern") and not re.match(f["pattern"], v):
                    errors.append("ligne %d : « %s » invalide (%s)" % (i, f["label"], v))
                    continue
                if f["name"] == "host" and re.search(r"\s", v):
                    errors.append("ligne %d : hôte avec des espaces" % i)
                    continue
            row[f["name"]] = v
        if "name" in row:
            if row["name"] in seen:
                errors.append("ligne %d : nom « %s » en double" % (i, row["name"]))
            seen.add(row["name"])
        out.append(row)
    return {spec["key"]: out}, errors, warnings


def merge_items(existing, incoming, key="name", mode="merge"):
    """Fusion par `key` : les entrées importées remplacent celles de même nom,
    les autres sont gardées (mode « merge ») ou retirées (« replace »)."""
    existing = [e for e in existing or [] if isinstance(e, dict)]
    incoming = [e for e in incoming or [] if isinstance(e, dict)]
    if mode == "replace":
        return list(incoming), {"added": len(incoming), "updated": 0, "unchanged": 0, "removed": len(existing)}
    idx = {e.get(key): i for i, e in enumerate(existing)}
    out = list(existing)
    stats = {"added": 0, "updated": 0, "unchanged": 0, "removed": 0}
    for e in incoming:
        k = e.get(key)
        if k in idx:
            if out[idx[k]] == e:
                stats["unchanged"] += 1
            else:
                out[idx[k]] = e
                stats["updated"] += 1
        else:
            idx[k] = len(out)
            out.append(e)
            stats["added"] += 1
    return out, stats


# -- auto-réparation -------------------------------------------------------------
def heal_decide(state, rows, now, threshold=3, max_per_hour=3, ignored=()):
    """-> (services à redémarrer, nouvel état, événements). Un service rouge
    `threshold` vérifications de suite est redémarré, au plus `max_per_hour`
    fois par heure ; au-delà : abandon signalé une fois (intervention humaine)."""
    state = {k: dict(v) for k, v in (state or {}).items()}
    todo, events = [], []
    ignored = set(ignored or ())
    for r in rows or []:
        s = r.get("service")
        if not s or s in ignored or r.get("protected"):
            continue
        st = state.setdefault(s, {"reds": 0, "restarts": [], "gave_up": False})
        if r.get("light") == "red" and r.get("hard", True):  # #588 : jamais sur un simple test HTTP en échec
            st["reds"] = st.get("reds", 0) + 1
            if st["reds"] >= threshold:
                recent = [t for t in st.get("restarts", []) if now - t < 3600]
                st["restarts"] = recent
                if len(recent) < max_per_hour:
                    todo.append(s)
                    st["restarts"].append(now)
                    st["reds"] = 0
                    events.append({"event": "heal-restart", "service": s, "text": r.get("text")})
                elif not st.get("gave_up"):
                    st["gave_up"] = True
                    events.append({"event": "heal-gave-up", "service": s, "text": "%d redémarrages en une heure sans retour au vert : intervention requise" % len(recent)})
        else:
            if st.get("gave_up"):
                events.append({"event": "heal-recovered", "service": s, "text": r.get("text")})
            st["reds"], st["gave_up"] = 0, False
    return todo, state, events


# -- #659 : mise à jour depuis le dépôt git (GitHub) ------------------------------
def mask_remote(url):
    """URL du dépôt sans identifiant ni jeton (https://user:token@host/… -> https://host/…)."""
    return re.sub(r"^(\w+://)[^@/]+@", r"\1", str(url or "").strip())


def remote_hint(url):
    """Pourquoi le runner ne pourra pas tirer : dépôt SSH (pas de clé dans le conteneur) ou pas de remote."""
    u = str(url or "").strip()
    if not u:
        return "aucun dépôt distant (origin) : git remote add origin https://github.com/<compte>/supervision-si.git"
    if u.startswith("git@") or u.startswith("ssh://"):
        return "dépôt distant en SSH : le conteneur n'a pas de clé -- passer en HTTPS (git remote set-url origin https://github.com/<compte>/supervision-si.git)"
    return None


def parse_log(text):
    """`git log --format=%h%x09%s HEAD..origin/x` -> [{hash, subject}]."""
    out = []
    for line in (text or "").splitlines():
        if "\t" in line:
            h, s = line.split("\t", 1)
            out.append({"hash": h.strip(), "subject": s.strip()[:160]})
    return out


# Fichiers suivis mais RÉGÉNÉRÉS par run.sh à chaque lancement (hash du contenu, inventaire d'exposition) : jamais un motif
# de refus, remis à la version du dépôt avant le pull (run.sh les réécrira).
GENERATED = ("shared/VERSION.json", "shared/EXPOSURE.json")


def registry_steps(steps):
    """#738 : images construites par le nœud constructeur -- d'abord la construction là-bas, puis chaque « up --build »
    local devient « tirer les images » + « up --no-build » (la passerelle, projet à part, reste construite ici)."""
    out = [{"label": "construire et pousser les images sur le nœud constructeur (registre local)", "cmd": "python3 deploy/node_agent.py build-images"}]
    for st in steps:
        m = re.match(r"^\./scripts/run\.sh up -d --build (.+)$", st["cmd"])
        if m:
            out.append({"label": st["label"] + " -- images tirées du registre", "cmd": "python3 deploy/images.py pull " + m.group(1)})
            out.append({"label": st["label"] + " -- relance sans construction", "cmd": "./scripts/run.sh up -d --no-build " + m.group(1)})
        else:
            out.append(st)
    return out


def git_update_plan(mode, changed, main_paths, running, gateway_running=True, nodes=0, agents=False, branch="main", start_new=(), registry=False):
    """Étapes du job : `git pull --ff-only`, puis
    - central : plan ciblé (plan_for_changes) sur les fichiers modifiés entre HEAD et origin ;
    - cascade : reconstruction de TOUS les services en marche (+ passerelle), puis les autres nœuds du déploiement
      réparti (deploy/node_agent.py update-all) ; les agents hôtes sont mis à jour par le central à la fin du job
      (si-agent-api /updates/apply, commande `update` aux agents éligibles).
    -> {steps, plan, agents}."""
    if not re.match(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,100}$", branch or ""):
        branch = "main"
    steps = [{"label": "remettre les fichiers générés (VERSION.json, EXPOSURE.json) à la version du dépôt", "cmd": "git checkout -- " + " ".join(GENERATED)},
             {"label": "tirer le dépôt (origin/%s, avance rapide seulement)" % branch, "cmd": "git pull --ff-only origin %s" % branch}]
    plan = plan_for_changes(changed, main_paths, running, gateway_running=gateway_running)
    if mode == "cascade":
        if ".env.example" in changed:
            steps.append({"label": "clés .env manquantes (sync-env)", "cmd": "python3 scripts/sync-env.py"})
        names = sorted(s for s in (running or []) if SERVICE_RE.match(s))
        if names:
            steps.append({"label": "reconstruire les %d service(s) en marche" % len(names), "cmd": "./scripts/run.sh up -d --build " + " ".join(names)})
        if gateway_running:
            steps.append({"label": "reconstruire la passerelle (tls-proxy)", "cmd": "./gateway/scripts/run.sh up -d --build tls-proxy"})
        if nodes and nodes > 1:
            steps.append({"label": "mettre à jour les %d autre(s) nœud(s) du déploiement réparti" % (nodes - 1), "cmd": "python3 deploy/node_agent.py update-all"})
    else:
        steps += plan["steps"]
    # #666 : services définis mais jamais démarrés ici (nouveaux modules) -- lancés seulement sur demande explicite
    new_names = sorted(s for s in (start_new or []) if SERVICE_RE.match(s) and s not in (running or []))
    if new_names:
        steps.append({"label": "démarrer %d nouveau(x) service(s)" % len(new_names), "cmd": "./scripts/run.sh up -d --build " + " ".join(new_names)})
    if registry:   # #738
        head = steps[:2]
        steps = head + registry_steps(steps[2:])
    return {"steps": steps, "plan": plan, "agents": bool(agents), "started": new_names, "registry": bool(registry)}


# -- #662 : répartition (nœuds / cohortes, #513) pilotée depuis la tour ---------------------------------------------------
NODE_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


def validate_nodes(nodes, cohorts):
    """nodes.json candidat -> (normalisé, erreur). Noms uniques, adresse VPN, cohortes connues et affectées au plus une fois,
    la cohorte manager reste sur un nœud (le manager)."""
    known = {c["name"]: c for c in (cohorts or {}).get("cohorts", [])}
    if not isinstance(nodes, dict) or not isinstance(nodes.get("nodes"), list) or not nodes["nodes"]:
        return None, "nodes : liste de nœuds attendue"
    seen_nodes, seen_cohorts, out = set(), {}, []
    for n in nodes["nodes"]:
        name = str(n.get("name") or "").strip()
        if not NODE_NAME_RE.match(name):
            return None, "nom de nœud invalide : %r" % name
        if name in seen_nodes:
            return None, "nœud en double : " + name
        seen_nodes.add(name)
        wg = str(n.get("wg_address") or "").strip()
        if not re.fullmatch(r"\d{1,3}(\.\d{1,3}){3}", wg):
            return None, "nœud %s : wg_address (adresse VPN) requise" % name
        cs = [str(c).strip() for c in (n.get("cohorts") or []) if str(c).strip()]
        for c in cs:
            if c not in known:
                return None, "nœud %s : cohorte inconnue %s" % (name, c)
            if c in seen_cohorts:
                return None, "cohorte %s affectée à %s et %s" % (c, seen_cohorts[c], name)
            seen_cohorts[c] = name
        out.append(dict(n, name=name, wg_address=wg, cohorts=cs, zone=str(n.get("zone") or "local"), edge=bool(n.get("edge")), role=str(n.get("role") or "worker")))
    managers = [c for c, v in known.items() if v.get("manager")]
    for c in managers:
        if c not in seen_cohorts:
            return None, "la cohorte manager %s doit être affectée à un nœud" % c
    unassigned = sorted(c for c in known if c not in seen_cohorts)
    return dict(nodes, nodes=out), (None if not unassigned else None)  # cohortes non affectées = tolérées (signalées par l'IHM)


def placed_here(nodes, cohorts, me):
    """Services placés sur le nœud `me` d'après nodes.json / cohorts.json, ou None si pas de répartition (nœud inconnu)."""
    mine = next((n for n in (nodes or {}).get("nodes", []) if n.get("name") == me), None)
    if not mine:
        return None
    svcs = set()
    for c in (cohorts or {}).get("cohorts", []):
        if c["name"] in (mine.get("cohorts") or []):
            svcs.update(c.get("services") or [])
    return svcs


def filter_plan(plan, placed):
    """Plan de reconstruction restreint aux services placés ici (None = tout) ; les autres sont listés dans `not_here`."""
    if placed is None or not plan:
        return plan
    out = dict(plan)
    out["not_here"] = sorted(s for s in (plan.get("rebuild") or []) + (plan.get("restart") or []) if s not in placed)
    if not out["not_here"]:
        return out
    keep = lambda names: [s for s in names if s in placed]  # noqa: E731
    out["rebuild"], out["restart"] = keep(plan.get("rebuild") or []), keep(plan.get("restart") or [])
    steps = []
    for st in plan.get("steps") or []:
        m = re.match(r"^(\./scripts/run\.sh (?:up -d --build|restart) )(.+)$", st["cmd"])
        if m:
            names = keep(m.group(2).split())
            if not names:
                continue
            st = dict(st, cmd=m.group(1) + " ".join(names), label=re.sub(r"\d+ service", "%d service" % len(names), st["label"]))
        steps.append(st)
    out["steps"] = steps
    return out
