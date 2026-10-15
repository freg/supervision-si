# -*- coding: utf-8 -*-
"""#769 : récapitulatif de l'activité des CT / VM de tous les Proxmox (écran « Activité des VM ») -- assemblage PUR
de la dernière mesure plugin:guest-usage de chaque agent, complétée par l'inventaire de la tuile Infra (invités non
relevés), et fiche de paramétrage par CT / VM (comptes unix, compte MySQL, URL HTTPS / ownCloud, IP à ignorer).

La fiche ne contient JAMAIS de mot de passe : un champ dont le nom évoque un secret est refusé, et la fiche indique à
la place le nom de l'entrée du coffre-fort (chiffré de bout en bout, illisible par le serveur). La sonde n'en a pas
besoin : root du nœud entre dans l'invité. Testé dans test_z_guestusage.py."""
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
            "web": w, "login": lg, "mysql": my, "profile": profile or {}}


def assemble(reports, inventory_vms, profiles):
    """reports : [(agent_id, hostname, at, data)] de plugin:guest-usage ; inventory_vms : vms de infra.overview ;
    profiles : {(node, vmid): fiche}. -> {rows, nodes, errors, totals}. Un même invité vu par deux agents : mesure la plus récente."""
    rows, nodes, errors = {}, {}, []
    for aid, host, at, d in sorted(reports, key=lambda r: r[2] or ""):
        for n in (d or {}).get("nodes") or []:
            name = n.get("name") or "?"
            nodes[name] = {"name": name, "zone": n.get("zone"), "ok": bool(n.get("ok")), "error": n.get("error"), "at": at,
                           "agent_id": aid, "agent": host or aid, "guests": len(n.get("guests") or [])}
            if not n.get("ok") or n.get("error"):
                errors.append({"node": name, "agent_id": aid, "agent": host or aid, "error": n.get("error")})
            for g in n.get("guests") or []:
                if g.get("vmid") is None:
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
