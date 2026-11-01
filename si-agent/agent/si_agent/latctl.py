# -*- coding: utf-8 -*-
"""#775 : mesures de latence des IP publiques du SI, vues d'un point de mesure -- l'agent lui-même, ou un hôte joint
par SSH depuis l'agent (compte personnel, rebond éventuel, sudo facultatif).

Pour chaque cible : ping (perte, aller-retour moyen), temps d'ouverture TCP par port, HTTPS forcé sur l'IP (résolution,
connexion, poignée de main TLS, premier octet, total, code) et HTTPS par le nom tel que le résout le point de mesure,
adresses obtenues pour le nom. Un seul script bash, généré ici à partir de paramètres VALIDÉS (jamais une commande
libre), exécuté localement ou envoyé par `ssh ... bash -s` ; lignes `@@L|cible|mesure|valeur` relues par parse().
Pur : validate, script, ssh_argv, parse (tests : tests/test_latctl.py)."""
import re
import shlex

ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,62}$")
HOST_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.:-]{0,252}$")       # nom, IPv4 ou IPv6
LOGIN_RE = re.compile(r"^[a-z_][a-z0-9_.-]{0,31}$")
JUMP_RE = re.compile(r"^([a-z_][a-z0-9_.-]{0,31}@)?[A-Za-z0-9][A-Za-z0-9.-]{0,252}(:[0-9]{1,5})?$")
KEY_RE = re.compile(r"^/[A-Za-z0-9._/@-]{1,200}$")
MAX_TARGETS = 40
SSH_OPTS = ["-o", "BatchMode=yes", "-o", "ConnectTimeout=10", "-o", "StrictHostKeyChecking=accept-new"]


def q(s):
    return shlex.quote(str(s))


def validate(params):
    """-> ({targets, via}, erreur). targets : [{id, ip, ports: [int], names: [str]}] ; via : None ou
    {login, host, port, jump, sudo, key}."""
    p = params or {}
    tg = p.get("targets")
    if not isinstance(tg, list) or not tg:
        return None, "targets : liste de cibles attendue"
    if len(tg) > MAX_TARGETS:
        return None, "au plus %d cibles par mesure" % MAX_TARGETS
    out = []
    for t in tg:
        if not isinstance(t, dict) or not ID_RE.match(str(t.get("id") or "")):
            return None, "cible sans identifiant valide"
        ip = str(t.get("ip") or "")
        if not HOST_RE.match(ip) or ".." in ip:
            return None, "cible %s : adresse invalide" % t["id"]
        ports = t.get("ports") or []
        if not isinstance(ports, list) or len(ports) > 10 or not all(isinstance(x, int) and 0 < x < 65536 for x in ports):
            return None, "cible %s : ports (10 au plus, entiers)" % t["id"]
        names = t.get("names") or []
        if not isinstance(names, list) or len(names) > 5 or not all(isinstance(n, str) and HOST_RE.match(n) and ".." not in n for n in names):
            return None, "cible %s : noms invalides" % t["id"]
        out.append({"id": t["id"], "ip": ip, "ports": ports, "names": names})
    via = p.get("via")
    if via:
        if not isinstance(via, dict):
            return None, "via : objet attendu"
        login, host = str(via.get("login") or ""), str(via.get("host") or "")
        if not LOGIN_RE.match(login):
            return None, "via.login invalide"
        if not HOST_RE.match(host) or ".." in host:
            return None, "via.host invalide"
        port = via.get("port") or 22
        if not isinstance(port, int) or not 0 < port < 65536:
            return None, "via.port invalide"
        jump = str(via.get("jump") or "")
        if jump and not JUMP_RE.match(jump):
            return None, "via.jump invalide (utilisateur@hôte:port)"
        key = str(via.get("key") or "")
        if key and (not KEY_RE.match(key) or ".." in key):
            return None, "via.key : chemin de clé invalide"
        via = {"login": login, "host": host, "port": port, "jump": jump, "sudo": bool(via.get("sudo")), "key": key}
    return {"targets": out, "via": via or None}, None


def script(plan):
    """Script bash (lecture seule : ping, ouverture TCP, curl) -> lignes @@L|cible|mesure|valeur."""
    lines = ["export LC_ALL=C",
             "for c in ping curl getent timeout; do command -v $c >/dev/null 2>&1 || echo \"@@L|-|missing|$c\"; done",
             "echo \"@@L|-|host|$(hostname)\"",
             "us() { echo $(( $(date +%s%N) / 1000 )); }"]
    W = "%{time_namelookup} %{time_connect} %{time_appconnect} %{time_starttransfer} %{time_total} %{http_code}"
    for t in plan["targets"]:
        i, ip = t["id"], t["ip"]
        lines.append("t=%s; ip=%s" % (q(i), q(ip)))
        lines.append("r=$(ping -n -q -c 4 -i 0.2 -W 1 \"$ip\" 2>/dev/null | tail -2)")
        lines.append("echo \"@@L|$t|ping_loss|$(echo \"$r\" | sed -n 's/.* \\([0-9.]*\\)% packet loss.*/\\1/p')\"")
        lines.append("echo \"@@L|$t|ping_ms|$(echo \"$r\" | sed -n 's/.*= [0-9.]*\\/\\([0-9.]*\\)\\/.*/\\1/p')\"")
        for port in t["ports"]:
            lines.append("s=$(us); if timeout 4 bash -c \"exec 3<>/dev/tcp/$ip/%d\" 2>/dev/null; then echo \"@@L|$t|tcp_%d|$(( $(us) - s ))\"; "
                         "else echo \"@@L|$t|tcp_%d|ERR\"; fi" % (port, port, port))
        for n in t["names"]:
            lines.append("echo \"@@L|$t|https_ip:%s|$(curl -sk --noproxy '*' -o /dev/null --max-time 10 --resolve %s -w '%s' %s 2>/dev/null)\"" % (
                n, q("%s:443:%s" % (n, ip)), W, q("https://%s/" % n)))
            lines.append("echo \"@@L|$t|https_name:%s|$(curl -sk --noproxy '*' -o /dev/null --max-time 10 -w '%s' %s 2>/dev/null)\"" % (n, W, q("https://%s/" % n)))
            lines.append("echo \"@@L|$t|dns:%s|$(getent ahosts %s 2>/dev/null | awk '{print $1}' | sort -u | tr '\\n' ' ')\"" % (n, q(n)))
    return "\n".join(lines) + "\n"


def ssh_argv(via):
    a = ["ssh"] + SSH_OPTS + ["-p", str(via["port"])]
    if via.get("key"):
        a += ["-i", via["key"]]
    if via.get("jump"):
        a += ["-J", via["jump"]]
    return a + ["%s@%s" % (via["login"], via["host"]), "sudo -n bash -s" if via.get("sudo") else "bash -s"]


def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def parse(out):
    """Sortie du script -> {host, missing: [...], targets: {id: {ping_ms, ping_loss, tcp: {port: ms|None}, https: {nom: {...}}}}}.
    Durées en millisecondes ; la poignée TLS = appconnect - connect ; le premier octet = starttransfer - appconnect."""
    res = {"host": None, "missing": [], "targets": {}}
    for line in (out or "").splitlines():
        if not line.startswith("@@L|"):
            continue
        parts = line.split("|", 3)
        if len(parts) < 4:
            continue
        _x, tid, key, val = parts
        val = val.strip()
        if tid == "-":
            if key == "missing":
                res["missing"].append(val)
            elif key == "host":
                res["host"] = val
            continue
        t = res["targets"].setdefault(tid, {"ping_ms": None, "ping_loss": None, "tcp": {}, "https": {}})
        if key == "ping_ms":
            t["ping_ms"] = _f(val)
        elif key == "ping_loss":
            t["ping_loss"] = _f(val)
        elif key.startswith("tcp_"):
            us = _f(val)
            t["tcp"][key[4:]] = round(us / 1000.0, 1) if us is not None else None
        elif key.startswith("https_ip:") or key.startswith("https_name:"):
            how, name = key.split(":", 1)
            v = val.split()
            d = None
            if len(v) == 6 and _f(v[1]) is not None:
                nl, co, ap, st, to = (_f(x) or 0.0 for x in v[:5])
                code = int(v[5]) if v[5].isdigit() else 0
                d = {"dns_ms": round(nl * 1000, 1), "connect_ms": round((co - nl) * 1000, 1) if co else None,
                     "tls_ms": round((ap - co) * 1000, 1) if ap and co else None,
                     "ttfb_ms": round((st - (ap or co)) * 1000, 1) if st else None, "total_ms": round(to * 1000, 1), "code": code,
                     "ok": 0 < code < 500}
            t["https"].setdefault(name, {})["ip" if how == "https_ip" else "name"] = d
        elif key.startswith("dns:"):
            t["https"].setdefault(key[4:], {})["resolved"] = [x for x in val.split() if x]
    return res


def run(params, runner):
    """runner(argv, input, timeout) -> (rc, stdout, stderr). -> {ok, result|error}."""
    plan, err = validate(params)
    if err:
        return {"ok": False, "error": err}
    sh = script(plan)
    timeout = 30 + 25 * len(plan["targets"])
    if plan["via"]:
        rc, out, errt = runner(ssh_argv(plan["via"]), sh, timeout)
        if rc == 255 or (rc != 0 and "@@L|" not in (out or "")):
            return {"ok": False, "error": "connexion SSH %s@%s impossible : %s" % (plan["via"]["login"], plan["via"]["host"], (errt or out or "").strip()[-300:])}
    else:
        rc, out, errt = runner(["bash", "-s"], sh, timeout)
    res = parse(out)
    if not res["targets"]:
        return {"ok": False, "error": "aucune mesure relevée : %s" % (errt or out or "").strip()[-300:]}
    return {"ok": True, "result": res}
