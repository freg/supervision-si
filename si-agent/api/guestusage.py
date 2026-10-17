# -*- coding: utf-8 -*-
"""#769 : récapitulatif de l'activité des CT / VM de tous les Proxmox (écran « Activité des VM ») -- assemblage PUR
de la dernière mesure plugin:guest-usage de chaque agent, complétée par l'inventaire de la tuile Infra (invités non
relevés), et fiche de paramétrage par CT / VM (comptes unix, compte MySQL, URL HTTPS / ownCloud, IP à ignorer).

La fiche ne contient JAMAIS de mot de passe : un champ dont le nom évoque un secret est refusé, et la fiche indique à
la place le nom de l'entrée du coffre-fort (chiffré de bout en bout, illisible par le serveur). La sonde n'en a pas
besoin : root du nœud entre dans l'invité. Testé dans test_z_guestusage.py.

#771 : activité réelle DANS LE TEMPS. Chaque mesure guest-usage porte un bloc « days » (par jour : web des humains,
connexions, MySQL, RRD ; par semaine : RRD année). ingest_daily() l'accumule dans guest_daily (appelé à la réception,
store.ingest_measurements) : l'historique s'allonge au-delà de la rotation des journaux des invités. activity() en
tire, par invité : mois par mois, dernière activité RÉELLE par service, « inactif depuis », classe (actif, faible,
dormant, inactif, inconnu) ; la fiche porte la décision (garder, migrer, archiver, arrêter, à étudier) et le suivi de
migration (cible, date prévue, état) -- liste pour les décideurs."""
import datetime as dt
import json
import re

SCHEMA = """CREATE TABLE IF NOT EXISTS guest_profiles (node TEXT NOT NULL, vmid INTEGER NOT NULL, data TEXT NOT NULL,
updated_at TEXT, updated_by TEXT, PRIMARY KEY (node, vmid))"""

SECRET_KEY = re.compile(r"pass|pwd|secret|token|credential|private|mot.?de.?passe", re.I)
UNIX = re.compile(r"^[a-z_][a-z0-9_.-]{0,31}\$?$")
MYSQL_USER = re.compile(r"^[A-Za-z0-9_.@%-]{1,80}$")
URL = re.compile(r"^https?://[^\s\"'<>]{1,300}$")
IP = re.compile(r"^[0-9A-Fa-f:.]{2,45}(/\d{1,3})?$")
PATH = re.compile(r"^/[A-Za-z0-9_./-]{1,200}$")

FIELDS = {   # clé -> (type, contrôle, libellé)
    "unix_accounts": ("list", UNIX, "comptes unix"),
    "mysql_user": ("str", MYSQL_USER, "compte MySQL"),
    "mysql_defaults_file": ("str", PATH, "fichier d'options MySQL dans l'invité"),
    "https_urls": ("list", URL, "URL HTTPS"),
    "owncloud_url": ("str", URL, "URL ownCloud"),
    "owncloud_user": ("str", MYSQL_USER, "compte ownCloud"),
    "vault_ref": ("str", re.compile(r"^[^\n\r]{1,120}$"), "entrée du coffre-fort"),
    "ignore_ips": ("list", IP, "IP à ignorer"),
    "role": ("str", re.compile(r"^[^\n\r]{1,80}$"), "rôle"),
    # #771 : décision et suivi de migration
    "decision": ("str", re.compile(r"^(garder|migrer|archiver|arreter|a_etudier)$"), "décision"),
    "decision_reason": ("str", re.compile(r"^[^\n\r]{1,300}$"), "motif de la décision"),
    "decision_by": ("str", re.compile(r"^[^\n\r]{1,80}$"), "décidé par"),
    "target": ("str", re.compile(r"^[^\n\r]{1,120}$"), "cible de migration"),
    "planned_for": ("str", re.compile(r"^\d{4}-\d{2}-\d{2}$"), "date prévue"),
    "migration_status": ("str", re.compile(r"^(a_planifier|planifiee|en_cours|faite|annulee)$"), "état de la migration"),
    "notes": ("str", re.compile(r"^[\s\S]{1,1000}$"), "notes"),
}


def _items(v):
    if isinstance(v, list):
        return [str(x).strip() for x in v if str(x).strip()]
    return [x.strip() for x in re.split(r"[,;\s]+", str(v or "")) if x.strip()]


def normalize_profile(body):
    """Corps reçu -> (fiche, erreur). Champs inconnus ignorés ; tout champ « secret » refusé (ranger au coffre-fort)."""
    if not isinstance(body, dict):
        return None, "fiche attendue (objet JSON)"
    bad = sorted(k for k in body if SECRET_KEY.search(str(k)))
    if bad:
        return None, "aucun mot de passe dans la fiche (%s) : le ranger dans le coffre-fort et indiquer le nom de l'entrée (vault_ref)" % ", ".join(bad)
    out = {}
    for k, (kind, rx, label) in FIELDS.items():
        if k not in body or body[k] in (None, "", []):
            continue
        if kind == "list":
            vals = _items(body[k])
            wrong = [x for x in vals if not rx.match(x)]
            if wrong:
                return None, "%s invalide : %s" % (label, ", ".join(wrong[:3]))
            out[k] = vals[:30]
        else:
            v = str(body[k]).strip()
            if v and not rx.match(v):
                return None, "%s invalide : %s" % (label, v[:60])
            if v:
                out[k] = v
    return out, None


def _dicts(v):
    """Liste d'objets attendue ; toute autre forme (mesure malformée) -> liste vide."""
    return [x for x in v if isinstance(x, dict)] if isinstance(v, list) else []


def _num(v):
    return v if isinstance(v, (int, float)) else None


def row_from(node, zone, at, agent_id, g, profile):
    w, lg, my = g.get("web") or None, g.get("login") or None, g.get("mysql") or None
    return {"key": "%s/%s" % (node, g.get("vmid")), "node": node, "zone": zone, "vmid": g.get("vmid"), "name": g.get("name") or "",
            "type": g.get("type"), "status": g.get("status"), "at": at, "agent_id": agent_id, "collected": bool(g.get("collected")),
            "error": g.get("error"), "os": g.get("os"), "source": "guest-usage",
            "cpu": {"now": _num(g.get("cpu_now")), "avg24": _num(g.get("cpu_avg24")), "max24": _num(g.get("cpu_max24")),
                    "avg7d": _num(g.get("cpu_avg7d")), "ncpu": g.get("ncpu"), "series": g.get("cpu_series") or []},
            "net24": {"in": g.get("netin24"), "out": g.get("netout24")},
            "web": w, "login": lg, "mysql": my, "internal": g.get("internal") if isinstance(g.get("internal"), dict) else None,
            "offline": bool(g.get("offline")), "offline_notes": [str(x)[:200] for x in (g.get("offline_notes") or [])][:20] if isinstance(g.get("offline_notes"), list) else [],
            "profile": profile or {}}


def assemble(reports, inventory_vms, profiles, activity_map=None):
    """reports : [(agent_id, hostname, at, data)] de plugin:guest-usage ; inventory_vms : vms de infra.overview ;
    profiles : {(node, vmid): fiche}. -> {rows, nodes, errors, totals}. Un même invité vu par deux agents : mesure la plus récente."""
    rows, nodes, errors = {}, {}, []
    for aid, host, at, d in sorted(reports, key=lambda r: r[2] or ""):
        for n in _dicts((d if isinstance(d, dict) else {}).get("nodes")):
            name = n.get("name") or "?"
            nodes[name] = {"name": name, "zone": n.get("zone"), "ok": bool(n.get("ok")), "error": n.get("error"), "at": at,
                           "agent_id": aid, "agent": host or aid, "guests": len(n.get("guests") or [])}
            if not n.get("ok") or n.get("error"):
                errors.append({"node": name, "agent_id": aid, "agent": host or aid, "error": n.get("error")})
            for g in _dicts(n.get("guests")):
                if not isinstance(g.get("vmid"), int):
                    continue
                r = row_from(name, n.get("zone"), at, aid, g, profiles.get((name, int(g["vmid"]))))
                rows[r["key"]] = r
    for v in inventory_vms or []:   # invités connus de la tuile Infra mais pas (encore) relevés par guest-usage
        if v.get("vmid") is None or v.get("node") is None:
            continue
        key = "%s/%s" % (v["node"], v["vmid"])
        if key in rows:
            continue
        rows[key] = dict(row_from(v["node"], v.get("zone"), None, None, {"vmid": v["vmid"], "name": v.get("name"), "type": v.get("type"),
                                                                          "status": v.get("status"), "cpu_now": v.get("cpu_pct"), "ncpu": v.get("ncpu")},
                                  profiles.get((v["node"], int(v["vmid"])))), source="inventaire")
    for r in rows.values():   # #771 : activité dans le temps
        r["activity"] = (activity_map or {}).get((r["node"], int(r["vmid"]))) if r.get("vmid") is not None else None
    out = sorted(rows.values(), key=lambda r: (r["node"], r["vmid"] or 0))
    return {"rows": out, "nodes": sorted(nodes.values(), key=lambda n: n["name"]), "errors": errors,
            "totals": {"guests": len(out), "collected": sum(1 for r in out if r["collected"]), "running": sum(1 for r in out if r["status"] == "running"),
                       "profiles": sum(1 for r in out if r["profile"]), "web": sum(1 for r in out if r["web"]), "mysql": sum(1 for r in out if r["mysql"])}}


def load_profiles(conn):
    conn.execute(SCHEMA)
    out = {}
    for r in conn.execute("SELECT node, vmid, data, updated_at, updated_by FROM guest_profiles"):
        try:
            d = json.loads(r["data"] or "{}")
        except ValueError:
            d = {}
        d["_updated_at"], d["_updated_by"] = r["updated_at"], r["updated_by"]
        out[(r["node"], int(r["vmid"]))] = d
    return out


def save_profile(conn, node, vmid, profile, at, by):
    conn.execute(SCHEMA)
    if profile:
        conn.execute("INSERT INTO guest_profiles (node, vmid, data, updated_at, updated_by) VALUES (?, ?, ?, ?, ?) "
                     "ON CONFLICT(node, vmid) DO UPDATE SET data = excluded.data, updated_at = excluded.updated_at, updated_by = excluded.updated_by",
                     (node, vmid, json.dumps(profile, ensure_ascii=False), at, by))
    else:
        conn.execute("DELETE FROM guest_profiles WHERE node = ? AND vmid = ?", (node, vmid))
    conn.commit()


# ---------------------------------------------------------------- #771 : historique quotidien

DAILY_SCHEMA = """CREATE TABLE IF NOT EXISTS guest_daily (node TEXT NOT NULL, vmid INTEGER NOT NULL, metric TEXT NOT NULL,
day TEXT NOT NULL, data TEXT NOT NULL, updated_at TEXT, PRIMARY KEY (node, vmid, metric, day))"""
DAY = re.compile(r"^\d{4}-\d{2}-\d{2}$")
METRICS = {   # métrique -> (clé du bloc days, champs gardés, fusion)
    "web": ("web", ("req", "bytes", "bot", "bot_bytes", "visitors", "owncloud"), "max"),
    "login": ("login", ("logins", "users"), "max"),
    "mysql": ("mysql", ("connections", "questions", "bytes"), "max"),
    "ssh": ("ssh", ("logins", "users"), "max"),        # #777 : activité interne
    "sudo": ("sudo", ("cmds",), "max"),
    "mail": ("mail", ("sent",), "max"),
    "files": ("files", ("files",), "max"),
    "rrd": ("rrd", ("cpu", "netin", "netout", "diskread", "diskwrite"), "replace"),
    "rrdw": ("rrd_weeks", ("cpu", "netin", "netout", "diskread", "diskwrite"), "replace"),
}
# seuils d'une journée « réellement active » (humains seulement : robots, supervision et sonde déjà écartés)
ACTIVE = {"web": lambda d: (d.get("visitors") or 0) >= 1 and (d.get("req") or 0) >= 3,
          "login": lambda d: (d.get("logins") or 0) >= 1,
          "mysql": lambda d: (d.get("connections") or 0) >= 1 or (d.get("questions") or 0) >= 50,
          "ssh": lambda d: (d.get("logins") or 0) >= 1,      # #777 : connexion SSH acceptée, commande sudo
          "sudo": lambda d: (d.get("cmds") or 0) >= 1}
# #777 : signes INDIRECTS (peuvent venir d'une tâche automatique) : datés à part, sans compter pour la classe d'activité
INDIRECT = {"files": lambda d: (d.get("files") or 0) >= 1, "mail": lambda d: (d.get("sent") or 0) >= 1}
CLASSES = (("actif", 7), ("faible", 30), ("dormant", 180))


def merge_day(old, new, mode):
    """Fusion d'un jour déjà connu : « max » (un relevé partiel ne fait jamais baisser un jour complet), « replace » (RRD)."""
    if mode == "replace" or not old:
        return dict(new)
    out = dict(old)
    for k, v in new.items():
        if isinstance(v, (int, float)):
            out[k] = max(v, out[k]) if isinstance(out.get(k), (int, float)) else v
    return out


def daily_rows(data):
    """Mesure guest-usage -> [(node, vmid, metric, day, {champs numériques})] ; valeurs non numériques écartées."""
    out = []
    for n in _dicts((data if isinstance(data, dict) else {}).get("nodes")):
        if not n.get("ok") or not n.get("name"):
            continue
        for g in _dicts(n.get("guests")):
            days, vmid = g.get("days") or {}, g.get("vmid")
            if not isinstance(days, dict) or not isinstance(vmid, int):
                continue
            for metric, (key, fields, _m) in METRICS.items():
                for d in _dicts(days.get(key)):
                    day = d.get("week" if metric == "rrdw" else "day")
                    if not isinstance(day, str) or not DAY.match(day):
                        continue
                    vals = {f: d[f] for f in fields if isinstance(d.get(f), (int, float)) and not isinstance(d.get(f), bool)}
                    if vals:
                        out.append((str(n["name"])[:64], vmid, metric, day, vals))
    return out


def ingest_daily(conn, data, at):
    """Accumule les jours d'une mesure guest-usage (fusion par jour). -> nombre de jours écrits."""
    conn.execute(DAILY_SCHEMA)
    n = 0
    for node, vmid, metric, day, vals in daily_rows(data):
        r = conn.execute("SELECT data FROM guest_daily WHERE node = ? AND vmid = ? AND metric = ? AND day = ?", (node, vmid, metric, day)).fetchone()
        try:
            old = json.loads(r[0]) if r else None
        except ValueError:
            old = None
        new = merge_day(old, vals, METRICS[metric][2])
        if new != old:
            conn.execute("INSERT OR REPLACE INTO guest_daily (node, vmid, metric, day, data, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                         (node, vmid, metric, day, json.dumps(new), at))
            n += 1
    return n


def summarize(series, today):
    """series : {metric: {day: {...}}} d'UN invité -> résumé d'activité dans le temps.
    {first_day, coverage_days, last_active: {web, login, mysql}, last_any, idle_days, class, months: [...]}"""
    last = {}
    for m, test in ACTIVE.items():
        act = [d for d, v in (series.get(m) or {}).items() if test(v)]
        last[m] = max(act) if act else None
    seen = sorted({d for m in ("web", "login", "mysql", "ssh", "sudo", "mail", "files") for d in (series.get(m) or {})})
    last_ind = {}
    for m, test in INDIRECT.items():
        act = [d for d, v in (series.get(m) or {}).items() if test(v)]
        last_ind[m] = max(act) if act else None
    rrd_seen = sorted(set(series.get("rrd") or {}) | set(series.get("rrdw") or {}))
    first = min([x for x in (seen[:1] + rrd_seen[:1]) if x], default=None)
    last_any = max([v for v in last.values() if v], default=None)
    idle = (dt.date.fromisoformat(today) - dt.date.fromisoformat(last_any)).days if last_any else None
    if last_any:
        cls = next((c for c, lim in CLASSES if idle <= lim), "inactif")
    else:
        cls = "inactif" if seen else "inconnu"     # relevé sans aucune journée active : inactif sur toute la période connue
    months = {}

    def mo(day):
        return months.setdefault(day[:7], {"month": day[:7], "req": 0, "bytes": 0, "visitor_days": 0, "bot": 0, "active_days": 0,
                                           "logins": 0, "mysql_conn": 0, "mysql_q": 0, "mysql_bytes": 0, "_cpu": [], "_wcpu": [],
                                           "net": 0, "_wnet": 0, "_days": set(), "ssh_logins": 0, "sudo": 0, "mail_sent": 0, "files": 0})
    for d, v in (series.get("web") or {}).items():
        m = mo(d)
        m["req"] += v.get("req") or 0
        m["bytes"] += v.get("bytes") or 0
        m["visitor_days"] += v.get("visitors") or 0
        m["bot"] += v.get("bot") or 0
    for d, v in (series.get("login") or {}).items():
        mo(d)["logins"] += v.get("logins") or 0
    for d, v in (series.get("mysql") or {}).items():
        m = mo(d)
        m["mysql_conn"] += v.get("connections") or 0
        m["mysql_q"] += v.get("questions") or 0
        m["mysql_bytes"] += v.get("bytes") or 0
    for d, v in (series.get("ssh") or {}).items():
        mo(d)["ssh_logins"] += v.get("logins") or 0
    for d, v in (series.get("sudo") or {}).items():
        mo(d)["sudo"] += v.get("cmds") or 0
    for d, v in (series.get("mail") or {}).items():
        mo(d)["mail_sent"] += v.get("sent") or 0
    for d, v in (series.get("files") or {}).items():
        mo(d)["files"] += v.get("files") or 0
    for mtr, test in ACTIVE.items():
        for d, v in (series.get(mtr) or {}).items():
            if test(v):
                mo(d)["_days"].add(d)
    for d, v in (series.get("rrd") or {}).items():
        m = mo(d)
        if v.get("cpu") is not None:
            m["_cpu"].append(v["cpu"])
        m["net"] += (v.get("netin") or 0) + (v.get("netout") or 0)
    for d, v in (series.get("rrdw") or {}).items():
        m = mo(d)
        if v.get("cpu") is not None:
            m["_wcpu"].append(v["cpu"])
        m["_wnet"] += (v.get("netin") or 0) + (v.get("netout") or 0)
    out = []
    for k in sorted(months):
        m = months[k]
        cpu = m["_cpu"] or m["_wcpu"]
        m["cpu"] = round(sum(cpu) / len(cpu), 2) if cpu else None
        m["net"] = m["net"] or m["_wnet"] or 0
        m["active_days"] = len(m["_days"])
        out.append({x: y for x, y in m.items() if not x.startswith("_")})
    li = max([v for v in last_ind.values() if v], default=None)
    return {"first_day": first, "coverage_days": len(seen), "last_active": last, "last_any": last_any, "idle_days": idle,
            "last_indirect": last_ind, "last_indirect_any": li,
            "class": cls, "months": out[-25:]}


def load_series(conn, since):
    """-> {(node, vmid): {metric: {day: {...}}}} depuis le jour « since »."""
    conn.execute(DAILY_SCHEMA)
    out = {}
    for r in conn.execute("SELECT node, vmid, metric, day, data FROM guest_daily WHERE day >= ?", (since,)):
        try:
            v = json.loads(r[4])
        except ValueError:
            continue
        out.setdefault((r[0], int(r[1])), {}).setdefault(r[2], {})[r[3]] = v
    return out


def activity(conn, today=None, days=800):
    """Résumé d'activité de tous les invités ayant un historique : {(node, vmid): summarize(...)}."""
    today = today or dt.date.today().isoformat()
    since = (dt.date.fromisoformat(today) - dt.timedelta(days=days)).isoformat()
    return {k: summarize(v, today) for k, v in load_series(conn, since).items()}


def history(conn, node, vmid, since):
    """Série quotidienne d'UN invité (écran de détail) : {metric: [{day, ...}]}."""
    conn.execute(DAILY_SCHEMA)
    out = {}
    for r in conn.execute("SELECT metric, day, data FROM guest_daily WHERE node = ? AND vmid = ? AND day >= ? ORDER BY day", (node, vmid, since)):
        try:
            out.setdefault(r[0], []).append(dict(json.loads(r[2]), day=r[1]))
        except ValueError:
            continue
    return out
