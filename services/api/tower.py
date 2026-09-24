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
KEEP_IF_EXISTS = ("*/data/*", "data/*", "backups/*")                        # créés s'ils manquent, jamais écrasés
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
            {"name": "port", "label": "port HTTPS", "type": "int", "default": 443},
            {"name": "credential", "label": "accès du coffre", "type": "str", "required": True, "default": "default"},
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
        if r.get("light") == "red":
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
