# -*- coding: utf-8 -*-
"""#776 : tuile « Proxys d'entrée » -- couple de proxys interchangeables (deux VM chez l'hébergeur, deux nœuds
différents) qui renvoient des noms (HTTPS par SNI) ou des ports publics vers des serveurs INTERNES, pilotés du hub.

- Les deux proxys reçoivent les mêmes routes (commande `edge` de l'agent 0.5.74 : si_agent/edgectl.py fabrique et
  vérifie la configuration HAProxy, recharge, garde l'ancienne) ; leur empreinte de configuration doit être identique.
- Redirection dynamique : chaque route a des serveurs internes CANDIDATS ; « basculer » change le serveur actif et
  réapplique sur les deux proxys.
- DNS : `dns_mode` = `both` (le nom pointe vers les deux proxys) ou `active` (vers le proxy actif seulement, l'autre en
  secours). Contrôle automatique toutes les `check_minutes` : serveurs FAISANT AUTORITÉ de la zone (ce qui est publié)
  et résolveurs publics (ce que voient les clients). Écart publié -> alerte « DNS à configurer » qui dit QUEL serveur
  DNS modifier (fournisseur, serveurs de la zone), l'enregistrement exact à poser et ce qui est en place aujourd'hui ;
  écart seulement chez les résolveurs -> « propagation en cours » (durée de cache).
Pur : validate_route, expected_ips, dns_check_route, proxy_problems ; l'état vit en base (aucun fil d'exécution)."""
import json
import re
import secrets
import time

import dnsq

try:   # copie de si_agent/edgectl.py dans l'image (source unique, comme protocol / plugins)
    import si_agent_edgectl as edgectl
except ImportError:   # tests : dépôt
    import os
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "agent"))
    from si_agent import edgectl

SCHEMA = (
    "CREATE TABLE IF NOT EXISTS edge_settings (k TEXT PRIMARY KEY, v TEXT)",
    "CREATE TABLE IF NOT EXISTS edge_proxies (id TEXT PRIMARY KEY, label TEXT, agent TEXT NOT NULL, public_ip TEXT NOT NULL, node TEXT, "
    "enabled INTEGER NOT NULL DEFAULT 1, updated_at TEXT, updated_by TEXT)",
    "CREATE TABLE IF NOT EXISTS edge_routes (id TEXT PRIMARY KEY, mode TEXT NOT NULL, name TEXT, front_port INTEGER, backend TEXT NOT NULL, "
    "http_backend TEXT, candidates TEXT NOT NULL DEFAULT '[]', send_proxy INTEGER NOT NULL DEFAULT 0, enabled INTEGER NOT NULL DEFAULT 1, "
    "notes TEXT, updated_at TEXT, updated_by TEXT)",
    "CREATE TABLE IF NOT EXISTS edge_state (proxy_id TEXT PRIMARY KEY, at REAL, data TEXT)",
    "CREATE TABLE IF NOT EXISTS edge_dns (route_id TEXT PRIMARY KEY, at REAL, state TEXT, data TEXT, alerted TEXT)",
    "CREATE TABLE IF NOT EXISTS edge_runs (id INTEGER PRIMARY KEY AUTOINCREMENT, proxy_id TEXT NOT NULL, kind TEXT NOT NULL, slot INTEGER NOT NULL, "
    "agent_id TEXT, command_id TEXT, status TEXT NOT NULL, error TEXT, queued_at REAL, finished_at REAL, UNIQUE (proxy_id, kind, slot))",
    "CREATE TABLE IF NOT EXISTS edge_log (id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT, who TEXT, action TEXT, detail TEXT)",
)
DEFAULTS = {"pair_label": "proxys-entree", "dns_mode": "both", "active_proxy": None, "check_minutes": 10, "status_minutes": 5,
            "resolvers": list(dnsq.PUBLIC), "ttl": 300}
ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,40}$")
IP_RE = re.compile(r"^(\d{1,3}\.){3}\d{1,3}$")
STALE_S = 900


def init(conn):
    for s in SCHEMA:
        conn.execute(s)


def _now_iso():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _log(conn, who, action, detail=""):
    conn.execute("INSERT INTO edge_log (at, who, action, detail) VALUES (?, ?, ?, ?)", (_now_iso(), (who or "?")[:64], action, str(detail)[:1000]))


# ---------------------------------------------------------------- pur

def validate_route(b):
    """Route du hub -> (route, erreur) ; `candidates` = serveurs internes possibles (le serveur actif en fait partie)."""
    b = dict(b or {})
    b.setdefault("id", re.sub(r"[^a-z0-9_-]+", "-", str(b.get("name") or "").lower()).strip("-")[:40] or None)
    rts, err = edgectl.validate([b])
    if err:
        return None, err
    r = rts[0]
    cands = b.get("candidates") or []
    if isinstance(cands, str):
        cands = [x for x in re.split(r"[\s,;]+", cands) if x]
    norm = []
    for c in cands:
        hp = edgectl._hostport(c, 443 if r["mode"] == "sni" else int(r["backend"].rsplit(":", 1)[1]))
        if not hp:
            return None, "candidat invalide : %s" % c
        norm.append("%s:%d" % hp)
    if r["backend"] not in norm:
        norm.insert(0, r["backend"])
    r.update(candidates=norm[:10], notes=str(b.get("notes") or "")[:500])
    return r, None


def expected_ips(settings, proxies):
    live = [p for p in proxies if p["enabled"]]
    if settings.get("dns_mode") == "active":
        act = next((p for p in live if p["id"] == settings.get("active_proxy")), live[0] if live else None)
        return [act["public_ip"]] if act else []
    return sorted(p["public_ip"] for p in live)


def dns_check_route(route, expected, resolvers, dq=dnsq, ttl=300):
    """-> {state: ok|a_configurer|propagation|erreur, zone, provider, ns: [...], public: [...], message, records}."""
    name = route.get("name")
    out = {"name": name, "expected": expected, "zone": None, "provider": None, "ns": [], "public": [], "records": [], "message": ""}
    if not name or not expected:
        out.update(state="erreur", message="nom ou adresses de proxys manquants")
        return out
    exp = sorted(expected)
    try:
        auth = dq.authoritative(name, resolvers[0] if resolvers else "1.1.1.1", q=dq.query)
    except (OSError, ValueError) as exc:
        out.update(state="erreur", message="zone introuvable (%s)" % exc)
        return out
    out.update(zone=auth["zone"], provider=dq.provider_of([n["name"] for n in auth["ns"]]))
    if not auth["ns"]:
        out.update(state="erreur", message="zone de %s introuvable : nom non délégué ?" % name)
        return out
    bad = []
    for ns in auth["ns"]:
        row = {"name": ns["name"], "ip": ns["ip"]}
        if not ns["ip"]:
            row.update(error="adresse du serveur inconnue")
        else:
            try:
                r = dq.resolve_at(ns["ip"], name, rd=False, q=dq.query, follow=resolvers[0] if resolvers else None)
                row.update(addresses=r["addresses"], cname=r["cname"], ttl=r["ttl"], ok=r["addresses"] == exp)
                if not row["ok"]:
                    bad.append(row)
            except (OSError, ValueError) as exc:
                row.update(error=str(exc))
        out["ns"].append(row)
    for srv in resolvers or []:
        try:
            r = dq.resolve_at(srv, name, rd=True, q=dq.query)
            out["public"].append({"server": srv, "addresses": r["addresses"], "cname": r["cname"], "ttl": r["ttl"], "ok": r["addresses"] == exp})
        except (OSError, ValueError) as exc:
            out["public"].append({"server": srv, "error": str(exc)})
    out["records"] = ["%s. %d IN A %s" % (name, ttl, ip) for ip in exp]
    answered = [n for n in out["ns"] if "addresses" in n]
    if not answered:
        out.update(state="erreur", message="aucun serveur faisant autorité n'a répondu")
    elif bad:
        cur = bad[0]
        now_txt = ("CNAME vers %s" % cur["cname"]) if cur.get("cname") else (", ".join(cur.get("addresses") or []) or "aucun enregistrement")
        out.update(state="a_configurer",
                   message="DNS à configurer chez %s (serveurs de la zone %s : %s) : %s doit pointer vers %s ; aujourd'hui : %s%s."
                   % (out["provider"], out["zone"], ", ".join(n["name"] for n in auth["ns"]), name, " et ".join(exp), now_txt,
                      " -- supprimer d'abord le CNAME" if cur.get("cname") else ""))
    elif any(not p.get("ok") for p in out["public"] if "addresses" in p):
        late = [p for p in out["public"] if "addresses" in p and not p["ok"]]
        out.update(state="propagation", message="publié correctement ; %s voit encore l'ancienne valeur (cache, jusqu'à %s s)"
                   % (", ".join(p["server"] for p in late), max([p.get("ttl") or 0 for p in late] or [0])))
    else:
        out.update(state="ok", message="%s pointe vers %s partout" % (name, " et ".join(exp)))
    return out


def proxy_problems(proxy, state, run, routes, ref_digest):
    """État d'un proxy -> [{code, title, detail, solution}]."""
    pb = []
    st = (state or {}).get("status") or {}
    err = (run or {}).get("error") or ""
    if "commande inconnue : edge" in err:
        pb.append({"code": "agent-ancien", "title": "Agent trop ancien sur %s" % proxy["label"], "detail": "Il faut l'agent 0.5.74 ou plus récent.",
                   "solution": {"label": "Mettre l'agent à jour depuis la maison", "where": "maison (Linux)",
                                "command": "curl -fsSL https://raw.githubusercontent.com/freg/supervision-si/dev/deploy/migration/agent-ssh.sh -o /tmp/agent-ssh.sh && bash /tmp/agent-ssh.sh root@%s" % proxy["public_ip"]}})
    elif err == "SILENCE":
        pb.append({"code": "silence", "title": "%s ne répond pas" % proxy["label"], "detail": "Commande non prise depuis 15 min : agent arrêté ou VM injoignable.",
                   "solution": {"label": "Vérifier l'agent sur la VM", "where": proxy["label"], "command": "systemctl status si-agent haproxy --no-pager | head -12"}})
    elif err.startswith("AGENT INCONNU"):
        pb.append({"code": "agent-inconnu", "title": "Agent %s inconnu du hub" % proxy["agent"], "detail": "Corriger l'agent du proxy ou installer l'agent sur la VM.",
                   "solution": {"label": "Fiche du proxy : choisir l'agent dans la liste", "where": "hub"}})
    elif err:
        pb.append({"code": "apply", "title": "Configuration refusée sur %s" % proxy["label"], "detail": err,
                   "solution": {"label": "Lire le contrôle de haproxy ci-dessous, corriger la route, puis « Appliquer aux deux »", "where": "hub",
                                "command": ((run or {}).get("check") or "")[:1500] or None}})
    if state and not st.get("active"):
        pb.append({"code": "haproxy", "title": "HAProxy arrêté ou absent sur %s" % proxy["label"], "detail": "service : %s" % st.get("service"),
                   "solution": {"label": "Installer / démarrer HAProxy sur la VM", "where": proxy["label"],
                                "command": "apt-get install -y haproxy && systemctl enable --now haproxy && journalctl -u haproxy -n 20 --no-pager"}})
    if state and st.get("active") and ref_digest and st.get("digest") != ref_digest:
        pb.append({"code": "ecart", "title": "Configuration de %s différente de celle attendue" % proxy["label"],
                   "detail": "Les deux proxys doivent porter la même configuration pour être interchangeables.",
                   "solution": {"label": "Appliquer aux deux proxys", "kind": "apply"}})
    down = [b for b, ms in (st.get("backends") or {}).items() if ms is None]
    if down:
        pb.append({"code": "interne", "title": "Serveur(s) interne(s) injoignable(s) depuis %s" % proxy["label"], "detail": ", ".join(down),
                   "solution": {"label": "Vérifier le tunnel vers le LAN (WireGuard) depuis la VM", "where": proxy["label"],
                                "command": "wg show; " + "; ".join("timeout 3 bash -c 'exec 3<>/dev/tcp/%s/%s' && echo %s ok || echo %s KO" % (b.rsplit(":", 1)[0], b.rsplit(":", 1)[1], b, b) for b in down[:5])}})
    return pb


# ---------------------------------------------------------------- base

def settings(conn):
    s = dict(DEFAULTS)
    for k, v in conn.execute("SELECT k, v FROM edge_settings"):
        try:
            s[k] = json.loads(v)
        except ValueError:
            pass
    return s


def set_settings(conn, b, by):
    init(conn)
    out = {}
    b = b or {}
    if "dns_mode" in b:
        if b["dns_mode"] not in ("both", "active"):
            return None, "dns_mode : both ou active"
        out["dns_mode"] = b["dns_mode"]
    if "active_proxy" in b:
        if b["active_proxy"] and not conn.execute("SELECT 1 FROM edge_proxies WHERE id = ?", (b["active_proxy"],)).fetchone():
            return None, "proxy actif inconnu"
        out["active_proxy"] = b["active_proxy"] or None
    for k, lo, hi in (("check_minutes", 2, 1440), ("status_minutes", 1, 60), ("ttl", 60, 86400)):
        if k in b:
            try:
                v = int(b[k])
            except (TypeError, ValueError):
                return None, "%s : entier" % k
            if not lo <= v <= hi:
                return None, "%s entre %d et %d" % (k, lo, hi)
            out[k] = v
    if "pair_label" in b:
        if not re.match(r"^[A-Za-z0-9_.-]{1,40}$", str(b["pair_label"])):
            return None, "nom du couple invalide"
        out["pair_label"] = b["pair_label"]
    if "resolvers" in b:
        rs = b["resolvers"] if isinstance(b["resolvers"], list) else re.split(r"[\s,;]+", str(b["resolvers"]))
        rs = [x for x in rs if x]
        if not rs or not all(IP_RE.match(x) for x in rs):
            return None, "résolveurs : adresses IPv4"
        out["resolvers"] = rs[:5]
    for k, v in out.items():
        conn.execute("INSERT INTO edge_settings (k, v) VALUES (?, ?) ON CONFLICT(k) DO UPDATE SET v = excluded.v", (k, json.dumps(v)))
    if out:
        _log(conn, by, "reglages", ", ".join("%s=%s" % kv for kv in out.items()))
        if "dns_mode" in out or "active_proxy" in out:
            conn.execute("UPDATE edge_dns SET at = 0")   # contrôle DNS au prochain passage
    return settings(conn), None


def proxies(conn):
    init(conn)
    return [{"id": r[0], "label": r[1], "agent": r[2], "public_ip": r[3], "node": r[4] or "", "enabled": bool(r[5]), "updated_at": r[6], "updated_by": r[7]}
            for r in conn.execute("SELECT id, label, agent, public_ip, node, enabled, updated_at, updated_by FROM edge_proxies ORDER BY id")]


def routes(conn):
    init(conn)
    out = []
    for r in conn.execute("SELECT id, mode, name, front_port, backend, http_backend, candidates, send_proxy, enabled, notes, updated_at, updated_by FROM edge_routes ORDER BY mode, name, front_port"):
        x = {"id": r[0], "mode": r[1], "name": r[2] or "", "backend": r[4], "candidates": json.loads(r[6] or "[]"), "send_proxy": bool(r[7]),
             "enabled": bool(r[8]), "notes": r[9] or "", "updated_at": r[10], "updated_by": r[11]}
        if r[1] == "sni":
            x["http_backend"] = r[5]
        else:
            x["front_port"] = r[3]
        out.append(x)
    return out


def save_proxy(conn, b, by):
    init(conn)
    b = b or {}
    pid, agent, ip = str(b.get("id") or "").strip(), str(b.get("agent") or "").strip(), str(b.get("public_ip") or "").strip()
    if not ID_RE.match(pid):
        return None, "identifiant du proxy invalide (minuscules, chiffres, - _)"
    if not re.match(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,62}$", agent):
        return None, "agent de la VM requis"
    if not IP_RE.match(ip):
        return None, "IP publique IPv4 requise"
    n = conn.execute("SELECT COUNT(*) FROM edge_proxies WHERE id != ?", (pid,)).fetchone()[0]
    if n >= 2:
        return None, "un couple = deux proxys (en retirer un d'abord)"
    p = {"id": pid, "label": str(b.get("label") or pid)[:80], "agent": agent, "public_ip": ip, "node": str(b.get("node") or "")[:80], "enabled": bool(b.get("enabled", True))}
    other = conn.execute("SELECT node FROM edge_proxies WHERE id != ?", (pid,)).fetchone()
    conn.execute("INSERT INTO edge_proxies (id, label, agent, public_ip, node, enabled, updated_at, updated_by) VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET "
                 "label=excluded.label, agent=excluded.agent, public_ip=excluded.public_ip, node=excluded.node, enabled=excluded.enabled, updated_at=excluded.updated_at, updated_by=excluded.updated_by",
                 (pid, p["label"], agent, ip, p["node"], int(p["enabled"]), _now_iso(), by))
    _log(conn, by, "proxy", "%s (%s, %s)" % (pid, agent, ip))
    conn.execute("UPDATE edge_dns SET at = 0")
    warn = "les deux proxys sont sur le même nœud (%s) : ils ne sont plus indépendants" % p["node"] if other and p["node"] and other[0] == p["node"] else None
    return dict(p, warning=warn), None


def save_route(conn, b, by):
    r, err = validate_route(b)
    if err:
        return None, err
    init(conn)
    dup = conn.execute("SELECT id FROM edge_routes WHERE id != ? AND ((mode = 'sni' AND name = ? AND ? = 'sni') OR (mode = 'tcp' AND front_port = ? AND ? = 'tcp'))",
                       (r["id"], r.get("name"), r["mode"], r.get("front_port"), r["mode"])).fetchone()
    if dup:
        return None, "nom ou port déjà pris par la route %s" % dup[0]
    conn.execute("INSERT INTO edge_routes (id, mode, name, front_port, backend, http_backend, candidates, send_proxy, enabled, notes, updated_at, updated_by) "
                 "VALUES (?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET mode=excluded.mode, name=excluded.name, front_port=excluded.front_port, "
                 "backend=excluded.backend, http_backend=excluded.http_backend, candidates=excluded.candidates, send_proxy=excluded.send_proxy, "
                 "enabled=excluded.enabled, notes=excluded.notes, updated_at=excluded.updated_at, updated_by=excluded.updated_by",
                 (r["id"], r["mode"], r.get("name"), r.get("front_port"), r["backend"], r.get("http_backend"), json.dumps(r["candidates"]),
                  int(r["send_proxy"]), int(r["enabled"]), r["notes"], _now_iso(), by))
    conn.execute("DELETE FROM edge_dns WHERE route_id = ?", (r["id"],))
    _log(conn, by, "route", "%s : %s -> %s" % (r["id"], r.get("name") or r.get("front_port"), r["backend"]))
    return r, None


def delete(conn, what, oid, by):
    init(conn)
    table = {"route": "edge_routes", "proxy": "edge_proxies"}[what]
    n = conn.execute("DELETE FROM %s WHERE id = ?" % table, (oid,)).rowcount
    if what == "route":
        conn.execute("DELETE FROM edge_dns WHERE route_id = ?", (oid,))
    else:
        conn.execute("DELETE FROM edge_state WHERE proxy_id = ?", (oid,))
    _log(conn, by, "suppression", "%s %s" % (what, oid))
    return n > 0


def switch_backend(conn, route_id, backend, by):
    """Redirection dynamique : le serveur interne actif d'une route devient `backend` (un de ses candidats)."""
    rt = next((r for r in routes(conn) if r["id"] == route_id), None)
    if not rt:
        return None, "route inconnue"
    if backend not in rt["candidates"]:
        return None, "serveur interne hors des candidats de la route"
    rt["backend"] = backend
    if rt["mode"] == "sni":
        rt["http_backend"] = "%s:80" % backend.rsplit(":", 1)[0]
    r, err = save_route(conn, rt, by)
    if err:
        return None, err
    _log(conn, by, "bascule", "%s -> %s" % (route_id, backend))
    return r, None


def agent_routes(conn):
    """Routes telles que les proxys les reçoivent (champs d'edgectl seulement)."""
    keys = ("id", "mode", "name", "front_port", "backend", "http_backend", "send_proxy", "enabled")
    return [{k: r[k] for k in keys if k in r} for r in routes(conn)]


def ref_digest(conn):
    rts, err = edgectl.validate(agent_routes(conn))
    return edgectl.digest(edgectl.render(rts, settings(conn)["pair_label"])) if not err else None


def resolve_agent(conn, name):
    r = conn.execute("SELECT agent_id FROM agents WHERE agent_id = ? OR lower(hostname) = lower(?) OR lower(label) = lower(?) "
                     "OR lower(hostname) LIKE lower(?) || '.%' ORDER BY (agent_id = ?) DESC, last_seen_at DESC LIMIT 1",
                     (name, name, name, name, name)).fetchone()
    return r[0] if r else None


def _enqueue(conn, agent_id, params):
    cid = "c-" + secrets.token_hex(6)
    t = time.time()
    conn.execute("INSERT INTO commands (id, agent_id, type, params, created_at) VALUES (?, ?, 'edge', ?, ?)",
                 (cid, agent_id, json.dumps(params, ensure_ascii=False), time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(t)) + ".%06dZ" % int((t % 1) * 1e6)))
    return cid


def _send(conn, proxy, kind, slot, now):
    if conn.execute("SELECT 1 FROM edge_runs WHERE proxy_id = ? AND kind = ? AND slot = ?", (proxy["id"], kind, slot)).fetchone():
        return False
    aid = resolve_agent(conn, proxy["agent"])
    if not aid:
        conn.execute("INSERT OR IGNORE INTO edge_runs (proxy_id, kind, slot, status, error, queued_at, finished_at) VALUES (?, ?, ?, 'failed', ?, ?, ?)",
                     (proxy["id"], kind, slot, "AGENT INCONNU : %s" % proxy["agent"], now, now))
        return False
    cid = _enqueue(conn, aid, {"action": kind, "label": settings(conn)["pair_label"], "routes": agent_routes(conn)})
    conn.execute("INSERT OR IGNORE INTO edge_runs (proxy_id, kind, slot, agent_id, command_id, status, queued_at) VALUES (?, ?, ?, ?, ?, 'queued', ?)",
                 (proxy["id"], kind, slot, aid, cid, now))
    return True


def apply_all(conn, by, now=None):
    init(conn)
    now = now or time.time()
    n = sum(1 for p in proxies(conn) if p["enabled"] and _send(conn, p, "apply", -int(now * 1000), now))
    _log(conn, by, "appliquer", "%d proxy(s)" % n)
    return n


def collect(conn, now):
    for rid, pid, kind, cst, res, queued in conn.execute(
            "SELECT r.id, r.proxy_id, r.kind, c.status, c.result, r.queued_at FROM edge_runs r LEFT JOIN commands c ON c.id = r.command_id WHERE r.status = 'queued'").fetchall():
        try:
            data = json.loads(res or "{}") or {}
        except ValueError:
            data = {}
        if cst in ("done", "failed"):
            res_ = data.get("result") or {}
            st = res_.get("status")
            if st:
                conn.execute("INSERT INTO edge_state (proxy_id, at, data) VALUES (?, ?, ?) ON CONFLICT(proxy_id) DO UPDATE SET at = excluded.at, data = excluded.data",
                             (pid, now, json.dumps({"status": st, "digest": res_.get("digest") or st.get("digest"), "kind": kind})))
            err = None if cst == "done" else str(data.get("error") or res_.get("error") or "échec")
            conn.execute("UPDATE edge_runs SET status = ?, finished_at = ?, error = ? WHERE id = ?",
                         ("done" if cst == "done" else "failed", now, (err + ("\n" + res_["check"] if res_.get("check") else "")) if err else None, rid))
        elif queued and now - queued > STALE_S:
            conn.execute("UPDATE edge_runs SET status = 'failed', finished_at = ?, error = 'SILENCE' WHERE id = ?", (now, rid))


def check_dns(conn, now, dq=dnsq, event=None, force=False):
    """Contrôle DNS des routes nommées dont le dernier contrôle a plus de check_minutes. -> nombre contrôlé.
    #797 : jamais de requête réseau ni d'événement pendant une écriture ouverte. Les requêtes DNS (3 s par résolveur)
    tenaient le verrou de la base, et `event` écrit par une autre connexion : attente de 30 s sur soi-même, puis
    « database is locked » pour tout le central (agents, journal des chantiers…)."""
    st = settings(conn)
    exp = expected_ips(st, proxies(conn))
    todo = []
    for r in routes(conn):
        if not r["enabled"] or not r.get("name"):
            continue
        row = conn.execute("SELECT at, state, alerted FROM edge_dns WHERE route_id = ?", (r["id"],)).fetchone()
        if row and not force and now - (row[0] or 0) < st["check_minutes"] * 60:
            continue
        todo.append((r, row[2] if row else None))
    if not todo:
        return 0
    if conn.in_transaction:
        conn.commit()
    pending = []
    for r, alerted in todo:
        res = dns_check_route(r, exp, st["resolvers"], dq, st["ttl"])      # réseau : aucune écriture ouverte
        if event and res["state"] != alerted and (res["state"] in ("a_configurer", "erreur") or alerted in ("a_configurer", "erreur")):
            sev = "warning" if res["state"] in ("a_configurer", "erreur") else "info"
            pending.append(("edge-dns", sev, ("%s : %s" % (r["name"], res["message"])) if res["state"] != "ok" else "%s : DNS conforme (%s)" % (r["name"], res["message"]),
                            {"route": r["id"], "state": res["state"], "zone": res["zone"], "provider": res["provider"], "records": res["records"]}))
            alerted = res["state"]
        elif res["state"] in ("ok", "propagation") and alerted not in ("a_configurer", "erreur"):
            alerted = res["state"]
        conn.execute("INSERT INTO edge_dns (route_id, at, state, data, alerted) VALUES (?, ?, ?, ?, ?) ON CONFLICT(route_id) DO UPDATE SET "
                     "at = excluded.at, state = excluded.state, data = excluded.data, alerted = excluded.alerted",
                     (r["id"], now, res["state"], json.dumps(res), alerted))
        conn.commit()
    for ev in pending:      # après validation : l'événement s'écrit par sa propre connexion
        event(*ev)
    return len(todo)


def tick(conn, now=None, dq=dnsq, event=None):
    init(conn)
    now = now or time.time()
    collect(conn, now)
    st = settings(conn)
    slot = int(now // (st["status_minutes"] * 60))
    for p in proxies(conn):
        if p["enabled"]:
            _send(conn, p, "status", slot, now)
    n = check_dns(conn, now, dq, event)
    conn.execute("DELETE FROM edge_runs WHERE queued_at < ?", (now - 7 * 86400,))
    return n


def view(conn, now=None):
    init(conn)
    now = now or time.time()
    collect(conn, now)
    st, pl, rl = settings(conn), proxies(conn), routes(conn)
    ref = ref_digest(conn)
    agents = [{"agent_id": r[0], "name": r[1] or r[0], "last_seen_at": r[2]} for r in conn.execute("SELECT agent_id, hostname, last_seen_at FROM agents ORDER BY hostname")]
    out_p = []
    for p in pl:
        s = conn.execute("SELECT at, data FROM edge_state WHERE proxy_id = ?", (p["id"],)).fetchone()
        state = json.loads(s[1]) if s else None
        run = conn.execute("SELECT kind, status, error, finished_at FROM edge_runs WHERE proxy_id = ? AND status != 'queued' ORDER BY finished_at DESC LIMIT 1", (p["id"],)).fetchone()
        run_d = {"kind": run[0], "status": run[1], "error": run[2], "finished_at": run[3]} if run else None
        if run_d and run_d["error"] and "\n" in run_d["error"]:
            run_d["error"], run_d["check"] = run_d["error"].split("\n", 1)
        out_p.append(dict(p, state=state, state_at=s[0] if s else None, run=run_d, identical=bool(state and ref and (state.get("status") or {}).get("digest") == ref),
                          problems=proxy_problems(p, state, run_d, rl, ref)))
    dns = {r[0]: {"at": r[1], "state": r[2], "data": json.loads(r[3])} for r in conn.execute("SELECT route_id, at, state, data FROM edge_dns")}
    out_r = []
    for r in rl:
        reach = {p["id"]: ((p.get("state") or {}).get("status") or {}).get("backends", {}).get(r["backend"]) for p in out_p}
        out_r.append(dict(r, dns=dns.get(r["id"]), reach=reach))
    log = [{"at": x[0], "who": x[1], "action": x[2], "detail": x[3]} for x in conn.execute("SELECT at, who, action, detail FROM edge_log ORDER BY id DESC LIMIT 50")]
    return {"settings": st, "expected_ips": expected_ips(st, pl), "ref_digest": ref, "proxies": out_p, "routes": out_r, "agents": agents, "log": log, "now": now}


def preview(conn):
    rts, err = edgectl.validate(agent_routes(conn))
    return {"error": err, "config": edgectl.render(rts, settings(conn)["pair_label"]) if not err else None}
