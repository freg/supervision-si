# -*- coding: utf-8 -*-
"""#776 : couple de proxys d'entrée interchangeables (deux VM chez l'hébergeur, sur deux nœuds différents) -- HAProxy
piloté par le hub.

Chaque proxy reçoit la MÊME liste de routes ; il fabrique LUI-MÊME sa configuration HAProxy à partir de champs validés
(jamais un texte de configuration venu du réseau : pas d'`external-check`, pas de Lua). Routes :
  - `sni`  : HTTPS en passage direct sur 443, aiguillé par le nom demandé (SNI) vers un serveur interne -- les
             certificats restent sur les serveurs internes ; le port 80 du même nom suit vers le port 80 interne
             (renouvellement Let's Encrypt http-01, redirections) ;
  - `tcp`  : un port public -> un serveur interne (SSH, autre service).
Option `send_proxy` : en-tête PROXY vers le serveur interne (adresse réelle du client ; Apache : RemoteIPProxyProtocol).
Appliquer = écrire à côté, `haproxy -c`, sauvegarder l'ancienne, remplacer, recharger ; un rechargement en échec remet
l'ancienne. État = service actif, empreinte de la configuration (les deux proxys doivent avoir la même), joignabilité de
chaque serveur interne VUE DU PROXY. Pur : validate, render, digest (tests : tests/test_edgectl.py)."""
import hashlib
import os
import re
import socket
import time

CFG = "/etc/haproxy/haproxy.cfg"
NAME_RE = re.compile(r"^(?=.{1,253}$)([A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z]{2,63}$")
HOST_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.:-]{0,252}$")
ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,40}$")
MODES = ("sni", "tcp")
RESERVED = (80, 443)
MAX_ROUTES = 200


def _hostport(s, default_port):
    s = str(s or "").strip()
    m = re.match(r"^\[([0-9A-Fa-f:]+)\]:(\d{1,5})$", s) or re.match(r"^([^:\s]+):(\d{1,5})$", s)
    host, port = (m.group(1), int(m.group(2))) if m else (s, default_port)
    if not HOST_RE.match(host) or ".." in host or not 0 < port < 65536:
        return None
    return host, port


def validate(routes):
    """-> (routes normalisées, erreur). Route : {id, mode, name?, front_port?, backend, http_backend?, send_proxy?, enabled?}."""
    if not isinstance(routes, list) or len(routes) > MAX_ROUTES:
        return None, "routes : liste (200 au plus)"
    out, names, ports, ids = [], set(), set(), set()
    for r in routes:
        if not isinstance(r, dict):
            return None, "route invalide"
        rid, mode = str(r.get("id") or ""), str(r.get("mode") or "sni")
        if not ID_RE.match(rid) or rid in ids:
            return None, "identifiant de route invalide ou en double : %s" % rid
        if mode not in MODES:
            return None, "route %s : mode sni ou tcp" % rid
        be = _hostport(r.get("backend"), 443 if mode == "sni" else 0)
        if not be or not be[1]:
            return None, "route %s : serveur interne hôte:port" % rid
        x = {"id": rid, "mode": mode, "backend": "%s:%d" % be, "send_proxy": bool(r.get("send_proxy")), "enabled": bool(r.get("enabled", True))}
        if mode == "sni":
            name = str(r.get("name") or "").lower().strip(".")
            if not NAME_RE.match(name) or name in names:
                return None, "route %s : nom public invalide ou en double" % rid
            names.add(name)
            hb = _hostport(r.get("http_backend") or "%s:80" % be[0], 80)
            if not hb:
                return None, "route %s : serveur HTTP interne invalide" % rid
            x.update(name=name, http_backend="%s:%d" % hb)
        else:
            try:
                fp = int(r.get("front_port"))
            except (TypeError, ValueError):
                return None, "route %s : port public requis" % rid
            if not 0 < fp < 65536 or fp in RESERVED or fp in ports:
                return None, "route %s : port public invalide, réservé (80, 443) ou en double" % rid
            ports.add(fp)
            x.update(front_port=fp, name=str(r.get("name") or "").lower()[:253])
        ids.add(rid)
        out.append(x)
    return out, None


def render(routes, label="edge"):
    """Configuration HAProxy complète (déterministe : même routes -> même texte sur les deux proxys)."""
    act = [r for r in routes if r["enabled"]]
    sni = sorted((r for r in act if r["mode"] == "sni"), key=lambda r: r["name"])
    tcp = sorted((r for r in act if r["mode"] == "tcp"), key=lambda r: r["front_port"])
    L = ["# Généré par si-agent (edgectl, #776) -- NE PAS MODIFIER À LA MAIN : le hub le réécrit.",
         "# proxy : %s" % re.sub(r"[^A-Za-z0-9_.-]", "-", label), "global", "    log /dev/log local0", "    maxconn 20000",
         "    stats socket /run/haproxy/admin.sock mode 660 level admin", "    stats timeout 30s", "",
         "defaults", "    log global", "    mode tcp", "    option tcplog", "    timeout connect 5s", "    timeout client 1h", "    timeout server 1h", ""]
    if sni:
        L += ["frontend fe_https", "    bind :443", "    tcp-request inspect-delay 5s", "    tcp-request content accept if { req.ssl_hello_type 1 }"]
        L += ["    use_backend be_%s if { req.ssl_sni -i %s }" % (r["id"], r["name"]) for r in sni]
        L += ["", "frontend fe_http", "    bind :80", "    mode http", "    option httplog", "    timeout client 30s"]
        L += ["    use_backend bh_%s if { hdr(host),field(1,:) -i %s }" % (r["id"], r["name"]) for r in sni]
        L += ["    http-request deny deny_status 404", ""]
        for r in sni:
            L += ["backend be_%s" % r["id"], "    server s1 %s check%s" % (r["backend"], " send-proxy-v2" if r["send_proxy"] else ""), "",
                  "backend bh_%s" % r["id"], "    mode http", "    timeout server 60s", "    server s1 %s check%s" % (r["http_backend"], " send-proxy-v2" if r["send_proxy"] else ""), ""]
    for r in tcp:
        L += ["frontend ft_%s" % r["id"], "    bind :%d" % r["front_port"], "    default_backend be_%s" % r["id"], "",
              "backend be_%s" % r["id"], "    server s1 %s check%s" % (r["backend"], " send-proxy-v2" if r["send_proxy"] else ""), ""]
    if not sni and not tcp:
        L += ["# aucune route active", "frontend fe_vide", "    bind 127.0.0.1:9", "    tcp-request connection reject", ""]
    return "\n".join(L) + "\n"


def digest(text):
    return hashlib.sha256((text or "").encode()).hexdigest()[:16]


def _reach(hostport, timeout=3.0):
    host, port = hostport.rsplit(":", 1)
    t = time.time()
    try:
        with socket.create_connection((host.strip("[]"), int(port)), timeout=timeout):
            return round((time.time() - t) * 1000, 1)
    except OSError:
        return None


def status(runner, routes=None, cfg=CFG, reach=_reach):
    try:
        with open(cfg) as fh:
            cur = fh.read()
    except OSError:
        cur = ""
    rc, out, _e = runner(["systemctl", "is-active", "haproxy"])
    res = {"active": out.strip() == "active", "service": out.strip() or "absent", "digest": digest(cur) if cur else None,
           "managed": cur.startswith("# Généré par si-agent"), "backends": {}}
    for r in routes or []:
        for k in ("backend", "http_backend"):
            if r.get(k) and r[k] not in res["backends"]:
                res["backends"][r[k]] = reach(r[k])
    return res


def apply(routes, runner, label="edge", cfg=CFG, reach=_reach):
    """-> {ok, digest, changed, error?, check?}. Réécrit seulement si le texte change."""
    rts, err = validate(routes)
    if err:
        return {"ok": False, "error": err}
    text = render(rts, label)
    try:
        with open(cfg) as fh:
            cur = fh.read()
    except OSError:
        cur = ""
    if cur == text:
        st = status(runner, rts, cfg, reach)
        if not st["active"]:
            runner(["systemctl", "restart", "haproxy"])
            st = status(runner, rts, cfg, reach)
        return {"ok": st["active"], "changed": False, "digest": digest(text), "status": st,
                "error": None if st["active"] else "haproxy ne démarre pas (journalctl -u haproxy)"}
    if cur and not cur.startswith("# Généré par si-agent") and not os.path.exists(cfg + ".avant-si"):
        with open(cfg + ".avant-si", "w") as fh:   # configuration d'origine gardée une fois pour toutes
            fh.write(cur)
    new = cfg + ".si-new"
    with open(new, "w") as fh:
        fh.write(text)
    rc, out, errt = runner(["haproxy", "-c", "-f", new])
    if rc != 0:
        return {"ok": False, "error": "configuration refusée par haproxy -c", "check": (errt or out)[-1500:]}
    if cur:
        with open(cfg + ".si-prev", "w") as fh:
            fh.write(cur)
    os.replace(new, cfg)
    rc, out, errt = runner(["systemctl", "reload-or-restart", "haproxy"])
    if rc != 0:
        if cur:
            with open(cfg, "w") as fh:
                fh.write(cur)
            runner(["systemctl", "reload-or-restart", "haproxy"])
        return {"ok": False, "error": "rechargement de haproxy en échec, ancienne configuration remise", "check": (errt or out)[-1500:]}
    return {"ok": True, "changed": True, "digest": digest(text), "status": status(runner, rts, cfg, reach)}


def run(params, runner, cfg=CFG, reach=_reach):
    action = str((params or {}).get("action") or "status")
    label = str((params or {}).get("label") or "edge")
    if action == "apply":
        return apply((params or {}).get("routes") or [], runner, label, cfg, reach)
    if action == "status":
        rts, err = validate((params or {}).get("routes") or [])
        return {"ok": True, "status": status(runner, rts or [], cfg, reach), "expected_digest": digest(render(rts, label)) if rts is not None else None}
    if action == "render":
        rts, err = validate((params or {}).get("routes") or [])
        return {"ok": not err, "error": err, "config": render(rts, label) if rts is not None else None}
    return {"ok": False, "error": "action : apply, status ou render"}
