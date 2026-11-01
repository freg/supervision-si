# -*- coding: utf-8 -*-
"""#743 (item 120, volet 1) : tournées de mesures réparties -- l'ordonnanceur de la supervision distribuée.

Une TOURNÉE confie une sonde lourde ou intrusive (balayage, capture, débit…) à un groupe d'agents ; le central décide
QUI la lance et QUAND, pour que la mesure reste globalement régulière sans que tous les agents tapent en même temps :

  - mode « rotate » : un seul agent par créneau, à tour de rôle ; s'il est hors ligne, le suivant le SUPPLÉE
    (la régularité de la mesure ne dépend plus d'un hôte) ;
  - mode « spread » : chaque agent une fois par période, décalés régulièrement dans la période (pas de rafale).
Garde-fous : heures calmes (aucun lancement), plafond de lancements simultanés par site (le créneau attend son tour,
au plus une demi-période, puis il est noté « sauté »).

Exécution : à l'heure du créneau, une commande `run_plugin` est déposée pour l'agent choisi (relevée par l'agent à son
prochain passage, 60 s par défaut) -- aucune mise à jour d'agent nécessaire. Chaque créneau est tracé (rotation_runs :
prévu, agent, suppléance, commande, état) : c'est la matière des volets 2 et 3 (couverture dans le temps, chronologie).
Fonctions pures (slots, choose_agent, due) testées sans base ni horloge réelle (test_rotation.py)."""
import hashlib
import json
import time

import store

DDL = """
CREATE TABLE IF NOT EXISTS rotation_plans (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, plugin_id TEXT NOT NULL,
    mode TEXT NOT NULL DEFAULT 'rotate', period_seconds INTEGER NOT NULL, agents TEXT NOT NULL DEFAULT '[]',
    quiet_hours TEXT NOT NULL DEFAULT '[]', max_concurrent_per_site INTEGER NOT NULL DEFAULT 1, enabled INTEGER NOT NULL DEFAULT 1,
    notes TEXT DEFAULT '', created_at TEXT, updated_at TEXT);
CREATE TABLE IF NOT EXISTS rotation_runs (id INTEGER PRIMARY KEY AUTOINCREMENT, plan_id INTEGER NOT NULL, slot_start INTEGER NOT NULL,
    agent_id TEXT, substitute_for TEXT, command_id TEXT, status TEXT NOT NULL, detail TEXT, queued_at TEXT, finished_at TEXT,
    UNIQUE (plan_id, slot_start, agent_id));
CREATE INDEX IF NOT EXISTS idx_rotation_runs_plan ON rotation_runs(plan_id, slot_start);
"""
MODES = ("rotate", "spread")
MIN_PERIOD = 300
ACTIVE = ("queued", "waiting")
STALE_SECONDS = 3600


def _age(iso):
    try:
        import calendar
        return time.time() - calendar.timegm(time.strptime(iso, "%Y-%m-%dT%H:%M:%SZ"))
    except (TypeError, ValueError):
        return 0


def init(db_path):
    conn = store._connect(db_path)
    try:
        conn.executescript(DDL)
        conn.commit()
    finally:
        conn.close()


# ------------------------------------------------------------------ calcul pur

def phase(plan_id, period):
    """Décalage stable d'une tournée dans sa période (deux tournées de même période ne démarrent pas ensemble)."""
    h = int(hashlib.sha256(str(plan_id).encode()).hexdigest()[:8], 16)
    return h % max(1, int(period))


def in_quiet(quiet_hours, ts, tz_offset=0):
    """quiet_hours = [[début, fin], …] en heures locales (fin exclue, plage à cheval sur minuit admise)."""
    h = time.gmtime(ts + tz_offset).tm_hour
    for a, b in quiet_hours or []:
        a, b = int(a) % 24, int(b) % 24
        if (a <= h < b) if a < b else (h >= a or h < b):
            return True
    return False


def slots(plan, t0, t1):
    """Créneaux [(début, agent_prévu)] dans ]t0, t1] -- agent_prévu = None en mode rotate (choisi au lancement)."""
    period = int(plan["period_seconds"])
    agents = sorted(plan.get("agents") or [])
    ph = phase(plan["id"], period)
    out = []
    if plan.get("mode") == "spread" and agents:
        step = period / len(agents)
        for i, a in enumerate(agents):
            off = (ph + int(i * step)) % period
            k = (t0 - off) // period + 1
            while k * period + off <= t1:
                out.append((k * period + off, a))
                k += 1
    else:
        k = (t0 - ph) // period + 1
        while k * period + ph <= t1:
            out.append((k * period + ph, None))
            k += 1
    return sorted(out, key=lambda x: (x[0], x[1] or ""))


def choose_agent(plan, slot_start, online):
    """Mode rotate : agent titulaire du créneau = agents triés[k mod n] ; s'il n'est pas en ligne, le suivant en ligne le
    supplée. -> (agent, titulaire_remplacé | None) ; (None, titulaire) si personne n'est en ligne."""
    agents = sorted(plan.get("agents") or [])
    if not agents:
        return None, None
    k = (slot_start - phase(plan["id"], plan["period_seconds"])) // int(plan["period_seconds"])
    titular = agents[k % len(agents)]
    for j in range(len(agents)):
        a = agents[(k + j) % len(agents)]
        if a in online:
            return a, (None if j == 0 else titular)
    return None, titular


def due(plan, last_tick, now, online, busy_by_site, site_of, tz_offset=0):
    """Créneaux à lancer pour ]last_tick, now] -> [{slot, agent, substitute_for, status, detail}] ; status = queue (à
    lancer), skipped (heure calme, personne en ligne, titulaire hors ligne en mode spread) ou wait (site au plafond)."""
    out = []
    period = int(plan["period_seconds"])
    for slot, planned in slots(plan, last_tick, now):
        if in_quiet(plan.get("quiet_hours"), slot, tz_offset):
            out.append({"slot": slot, "agent": planned, "substitute_for": None, "status": "skipped", "detail": "heure calme"})
            continue
        if planned is None:
            agent, sub = choose_agent(plan, slot, online)
        else:
            agent, sub = (planned, None) if planned in online else (None, planned)
        if agent is None:
            out.append({"slot": slot, "agent": sub, "substitute_for": None, "status": "skipped", "detail": "aucun agent en ligne"})
            continue
        site = site_of.get(agent) or ""
        cap = int(plan.get("max_concurrent_per_site") or 0)
        if cap and busy_by_site.get(site, 0) >= cap:
            st = "skipped" if now - slot > period / 2 else "wait"
            out.append({"slot": slot, "agent": agent, "substitute_for": sub, "status": st,
                        "detail": "site %s au plafond (%d)" % (site or "?", cap)})
            continue
        busy_by_site[site] = busy_by_site.get(site, 0) + 1
        out.append({"slot": slot, "agent": agent, "substitute_for": sub, "status": "queue", "detail": None})
    return out


def coverage(runs, plan, t0, t1):
    """Couverture d'une tournée sur ]t0, t1] : créneaux prévus, faits, suppléés, sautés, en échec, taux de réalisation."""
    expected = len(slots(plan, t0, t1))
    inside = [r for r in runs if t0 < r["slot_start"] <= t1]
    c = {"expected": expected, "done": 0, "failed": 0, "skipped": 0, "pending": 0, "substituted": 0}
    for r in inside:
        st = r["status"]
        c["done" if st == "done" else "failed" if st == "failed" else "skipped" if st == "skipped" else "pending"] += 1
        if r.get("substitute_for"):
            c["substituted"] += 1
    c["rate"] = round(c["done"] / expected, 3) if expected else None
    return c


def validate(body, known_plugins=None, known_agents=None):
    """-> (plan normalisé, erreur)."""
    p = {"name": str(body.get("name") or "").strip()[:120], "plugin_id": str(body.get("plugin_id") or "").strip(),
         "mode": body.get("mode") or "rotate", "agents": sorted({str(a) for a in body.get("agents") or [] if a}),
         "quiet_hours": body.get("quiet_hours") or [], "notes": str(body.get("notes") or "")[:500], "enabled": bool(body.get("enabled", True))}
    try:
        p["period_seconds"] = int(body.get("period_seconds") or 0)
        p["max_concurrent_per_site"] = int(body.get("max_concurrent_per_site", 1))
    except (TypeError, ValueError):
        return None, "période et plafond : nombres entiers"
    if not p["name"] or not p["plugin_id"]:
        return None, "nom et sonde requis"
    if p["mode"] not in MODES:
        return None, "mode : rotate ou spread"
    if p["period_seconds"] < MIN_PERIOD:
        return None, "période minimale : %d s" % MIN_PERIOD
    if not p["agents"]:
        return None, "au moins un agent"
    if p["mode"] == "spread" and p["period_seconds"] / len(p["agents"]) < 60:
        return None, "mode spread : au moins 60 s entre deux agents (période trop courte pour %d agents)" % len(p["agents"])
    if known_plugins is not None and p["plugin_id"] not in known_plugins:
        return None, "sonde inconnue : %s" % p["plugin_id"]
    if known_agents is not None and [a for a in p["agents"] if a not in known_agents]:
        return None, "agents inconnus : %s" % ", ".join(a for a in p["agents"] if a not in known_agents)
    try:
        qh = [[int(a) % 24, int(b) % 24] for a, b in p["quiet_hours"]]
    except (TypeError, ValueError):
        return None, "heures calmes : [[début, fin], …]"
    p["quiet_hours"] = qh
    return p, None


# ------------------------------------------------------------------ base et tick

def plan_public(r):
    d = dict(r)
    for k in ("agents", "quiet_hours"):
        d[k] = json.loads(d.get(k) or "[]")
    d["enabled"] = bool(d["enabled"])
    return d


def list_plans(db_path):
    conn = store._connect(db_path)
    try:
        return [plan_public(r) for r in conn.execute("SELECT * FROM rotation_plans ORDER BY name COLLATE NOCASE")]
    finally:
        conn.close()


def get_plan(db_path, pid):
    conn = store._connect(db_path)
    try:
        r = conn.execute("SELECT * FROM rotation_plans WHERE id = ?", (pid,)).fetchone()
        return plan_public(r) if r else None
    finally:
        conn.close()


def save_plan(db_path, p, pid=None):
    conn = store._connect(db_path)
    try:
        vals = (p["name"], p["plugin_id"], p["mode"], p["period_seconds"], json.dumps(p["agents"]), json.dumps(p["quiet_hours"]),
                p["max_concurrent_per_site"], int(p["enabled"]), p["notes"], store.now_iso())
        if pid is None:
            cur = conn.execute("INSERT INTO rotation_plans (name, plugin_id, mode, period_seconds, agents, quiet_hours, max_concurrent_per_site, "
                               "enabled, notes, updated_at, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)", vals + (store.now_iso(),))
            pid = cur.lastrowid
        else:
            conn.execute("UPDATE rotation_plans SET name=?, plugin_id=?, mode=?, period_seconds=?, agents=?, quiet_hours=?, "
                         "max_concurrent_per_site=?, enabled=?, notes=?, updated_at=? WHERE id=?", vals + (pid,))
        conn.commit()
    finally:
        conn.close()
    return get_plan(db_path, pid)


def delete_plan(db_path, pid):
    conn = store._connect(db_path)
    try:
        n = conn.execute("DELETE FROM rotation_plans WHERE id = ?", (pid,)).rowcount
        conn.execute("DELETE FROM rotation_runs WHERE plan_id = ?", (pid,))
        conn.commit()
        return n > 0
    finally:
        conn.close()


def list_runs(db_path, pid, limit=200):
    conn = store._connect(db_path)
    try:
        return [dict(r) for r in conn.execute("SELECT * FROM rotation_runs WHERE plan_id = ? ORDER BY slot_start DESC, id DESC LIMIT ?", (pid, limit))]
    finally:
        conn.close()


def _refresh_runs(conn):
    """Créneaux en cours <- état de leur commande (done / failed), via la table commands."""
    for r in conn.execute("SELECT id, command_id, queued_at FROM rotation_runs WHERE status = 'queued' AND command_id IS NOT NULL").fetchall():
        c = conn.execute("SELECT status, result, acked_at FROM commands WHERE id = ?", (r["command_id"],)).fetchone()
        if c is None or c["status"] == "pending":
            if _age(r["queued_at"]) > STALE_SECONDS:      # agent parti entre-temps : le créneau ne bloque plus son site
                conn.execute("UPDATE rotation_runs SET status = 'failed', detail = 'sans réponse de l''agent', finished_at = ? WHERE id = ?",
                             (store.now_iso(), r["id"]))
            continue
        ok = c["status"] in ("done", "ok", "acked")
        try:
            res = json.loads(c["result"] or "{}")
            ok = bool(res.get("ok", ok))
            err = res.get("error")
        except (TypeError, ValueError):
            err = None
        conn.execute("UPDATE rotation_runs SET status = ?, detail = ?, finished_at = ? WHERE id = ?",
                     ("done" if ok else "failed", (err or "")[:300] or None, c["acked_at"] or store.now_iso(), r["id"]))


def tick(db_path, now=None, online=None, site_of=None, create_command=None, tz_offset=None):
    """Un passage de l'ordonnanceur (appelé toutes les 30 s par le chien de garde du central). Renvoie les créneaux traités."""
    now = int(now if now is not None else time.time())
    if tz_offset is None:
        tz_offset = -time.altzone if time.localtime(now).tm_isdst > 0 else -time.timezone
    if online is None or site_of is None:
        fleet = store.fleet(db_path)
        online = {a["agent_id"] for a in fleet if a.get("online") == "online" and a.get("active", True)}
        site_of = {a["agent_id"]: a.get("site") for a in fleet}
    create_command = create_command or (lambda aid, pid, params: store.create_command(db_path, aid, "run_plugin", params))
    done = []
    conn = store._connect(db_path)
    try:
        _refresh_runs(conn)
        conn.commit()
        state = store.get_setting(db_path, "rotation_last_tick", None)
        last = int(state) if state else now - 60
        last = max(last, now - 3600)                     # central arrêté longtemps : on ne rattrape pas plus d'une heure
        busy = {}
        for r in conn.execute("SELECT agent_id FROM rotation_runs WHERE status = 'queued'").fetchall():
            busy[site_of.get(r["agent_id"]) or ""] = busy.get(site_of.get(r["agent_id"]) or "", 0) + 1
        waiting = conn.execute("SELECT * FROM rotation_runs WHERE status = 'waiting'").fetchall()
        plans = [plan_public(r) for r in conn.execute("SELECT * FROM rotation_plans WHERE enabled = 1")]
    finally:
        conn.close()
    by_id = {p["id"]: p for p in plans}
    items = []
    for w in waiting:                                    # créneaux en attente de place : on retente
        p = by_id.get(w["plan_id"])
        if p is None:
            continue
        site = site_of.get(w["agent_id"]) or ""
        cap = int(p.get("max_concurrent_per_site") or 0)
        if cap and busy.get(site, 0) >= cap:
            if now - w["slot_start"] > p["period_seconds"] / 2:
                items.append((p, {"slot": w["slot_start"], "agent": w["agent_id"], "substitute_for": w["substitute_for"],
                                  "status": "skipped", "detail": "site au plafond pendant une demi-période"}, w["id"]))
            continue
        busy[site] = busy.get(site, 0) + 1
        items.append((p, {"slot": w["slot_start"], "agent": w["agent_id"], "substitute_for": w["substitute_for"], "status": "queue", "detail": None}, w["id"]))
    for p in plans:
        for d in due(p, last, now, online, busy, site_of, tz_offset):
            items.append((p, d, None))
    conn = store._connect(db_path)
    try:
        for p, d, existing in items:
            cid = None
            status = {"queue": "queued", "wait": "waiting"}.get(d["status"], d["status"])
            if d["status"] == "queue":
                c = create_command(d["agent"], p["plugin_id"], {"id": p["plugin_id"], "rotation": p["id"], "slot": d["slot"]})
                cid = (c or {}).get("id")
                if not cid:
                    status, d["detail"] = "skipped", "commande refusée (agent inconnu ?)"
            if existing:
                conn.execute("UPDATE rotation_runs SET status = ?, command_id = ?, detail = ?, queued_at = ? WHERE id = ?",
                             (status, cid, d["detail"], store.now_iso(), existing))
            else:
                conn.execute("INSERT OR IGNORE INTO rotation_runs (plan_id, slot_start, agent_id, substitute_for, command_id, status, detail, queued_at) "
                             "VALUES (?,?,?,?,?,?,?,?)", (p["id"], d["slot"], d["agent"], d["substitute_for"], cid, status, d["detail"], store.now_iso()))
            done.append(dict(d, plan_id=p["id"], status=status, command_id=cid))
        conn.commit()
    finally:
        conn.close()
    store.set_setting(db_path, "rotation_last_tick", now)
    return done
