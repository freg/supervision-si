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


# -- santé de l'hôte (#593) : charge, mémoire, espace disque ---------------------
DISK_WARN, DISK_CRIT = 85, 95
MEM_WARN, MEM_CRIT = 90, 97


def disk_light(pct, free_bytes):
    """Pourcentage utilisé + octets libres -> lampe. Un disque presque plein
    mais avec beaucoup de place absolue reste orange ; < 200 Mo = rouge."""
    if pct >= DISK_CRIT or free_bytes < 200 * 1024 * 1024:
        return "red"
    if pct >= DISK_WARN or free_bytes < 1024 * 1024 * 1024:
        return "orange"
    return "green"


def load_light(load1, load5, cpus):
    c = max(1, cpus or 1)
    if load5 >= 2 * c:
        return "red"
    if load1 >= c:
        return "orange"
    return "green"


def mem_light(pct):
    return "red" if pct >= MEM_CRIT else "orange" if pct >= MEM_WARN else "green"


def host_summary(disks, load, cpus, mem_pct):
    """-> {light, text, problems[]} ; le pire l'emporte."""
    order = {"green": 0, "orange": 1, "red": 2}
    worst, problems = "green", []
    for d in disks or []:
        l = disk_light(d.get("pct", 0), d.get("free", 0))
        d["light"] = l
        if l != "green":
            problems.append("%s : %d %% utilisé (%s libre)" % (d.get("mount"), d.get("pct", 0), human(d.get("free", 0))))
        worst = max(worst, l, key=lambda x: order[x])
    if load:
        l = load_light(load[0], load[1] if len(load) > 1 else load[0], cpus)
        if l != "green":
            problems.append("charge %.2f / %.2f pour %d CPU" % (load[0], load[1] if len(load) > 1 else load[0], cpus))
        worst = max(worst, l, key=lambda x: order[x])
    if mem_pct is not None:
        l = mem_light(mem_pct)
        if l != "green":
            problems.append("mémoire à %d %%" % mem_pct)
        worst = max(worst, l, key=lambda x: order[x])
    text = "hôte en bonne santé" if not problems else "; ".join(problems)
    return {"light": worst, "text": text, "problems": problems}


def human(n):
    n = float(n or 0)
    for unit in ("o", "Ko", "Mo", "Go", "To"):
        if n < 1024 or unit == "To":
            return ("%.1f %s" if unit not in ("o", "Ko") else "%.0f %s") % (n, unit)
        n /= 1024.0
    return "%.1f To" % n


def hypervisor_summary(pve, vm_name):
    """#594 : mesure Proxmox (si-agent-api /proxmox, un hyperviseur) + nom de la
    VM du hub -> {node, vm, storages, zfs, light, text} ou None si la VM n'y est pas."""
    vms = pve.get("vms") or []
    vm = next((v for v in vms if str(v.get("name") or "").lower() == str(vm_name or "").lower()), None)
    if vm is None:
        return None
    order = {"green": 0, "orange": 1, "red": 2}
    worst, problems = "green", []
    used_storages = {d.get("storage") for d in ((vm.get("disk_options") or {}).get("disks") or []) if d.get("storage")}
    storages = []
    for st in pve.get("storages") or []:
        total, used = st.get("total") or 0, st.get("used") or 0
        pct = int(round(100.0 * used / total)) if total else None
        light = disk_light(pct, (st.get("avail") or 0)) if pct is not None else "grey"
        rel = st.get("storage") in used_storages
        storages.append({"storage": st.get("storage"), "type": st.get("type"), "used": used, "total": total, "avail": st.get("avail"), "pct": pct, "light": light, "hosts_vm": rel})
        if rel and light != "green":
            problems.append("stockage %s : %s %% utilisé" % (st.get("storage"), pct))
            worst = max(worst, light, key=lambda x: order[x])
    pools = []
    for z in pve.get("zfs") or []:
        cap = z.get("capacity")
        health = (z.get("health") or "").upper()
        light = "red" if health and health != "ONLINE" else disk_light(cap or 0, z.get("free") or 0)
        pools.append({"pool": z.get("pool"), "capacity": cap, "free": z.get("free"), "size": z.get("size"), "health": health or "?", "light": light})
        if light != "green":
            problems.append("pool %s : %s %% (%s)" % (z.get("pool"), cap, health or "?"))
            worst = max(worst, light, key=lambda x: order[x])
    node = pve.get("node") or {}
    mt, mu = node.get("mem_total") or 0, node.get("mem_used") or 0
    mem_pct = int(round(100.0 * mu / mt)) if mt else None
    if mem_pct is not None and mem_light(mem_pct) != "green":
        problems.append("mémoire de l'hyperviseur à %d %%" % mem_pct)
        worst = max(worst, mem_light(mem_pct), key=lambda x: order[x])
    return {"node": node.get("name") or pve.get("hostname"), "pveversion": node.get("pveversion"), "agent_id": pve.get("agent_id"), "at": pve.get("at"),
            "mem_pct": mem_pct, "mem_total": mt,
            "vm": {"vmid": vm.get("vmid"), "name": vm.get("name"), "status": vm.get("status"), "maxdisk": vm.get("maxdisk"), "maxmem": vm.get("maxmem"),
                   "disks": (vm.get("disk_options") or {}).get("disks") or [], "snapshots": len(vm.get("snapshots") or [])},
            "storages": storages, "zfs": pools, "light": worst, "text": "; ".join(problems) or "hyperviseur en bonne santé"}
