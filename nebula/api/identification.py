# -*- coding: utf-8 -*-
"""Identification des cibles (#1003, #1004) -- assemblage : fiche du client (historique) + profil d'activité (activite.py) +
population du site (singularités) + apprentissage des confirmations humaines -> catégorie (categorie.py). Utilisé par
l'historique des clients (filtres par catégorie et certitude, confirmation) et la liste de surveillance.

Confirmation humaine (#1004) : une personne confirme ou corrige la catégorie d'un client ; ce client est alors
« confirmé », et ses traits (fabricant, système, comportement, VLAN…) enseignent la catégorie aux autres clients qui les
partagent -- leurs certitudes montent ou descendent. Annuler une décision la retire de l'apprentissage."""
import json
import time

import activite
import categorie

POPULATION_TTL_S = 3600
CATEGORIES_TTL_S = 900
JOURS = 14
SCHEMA = """
CREATE TABLE IF NOT EXISTS nebula_categorie_decisions (
    site_id TEXT NOT NULL, mac TEXT NOT NULL, categorie TEXT NOT NULL, proposee TEXT, confiance_proposee INTEGER,
    traits TEXT, par TEXT, at INTEGER NOT NULL, PRIMARY KEY (site_id, mac));
"""
_cache = {}          # site -> {at, pop, n}
_cats = {}           # site -> {at, par_mac}
_appris = {"at": 0, "st": None, "decisions": {}}


def _dicts(cur):
    cols = [c[0] for c in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def invalider():
    _cats.clear()
    _appris.update(at=0, st=None)


def fiche(conn, site_id, mac):
    try:
        r = _dicts(conn.execute("SELECT site_id, mac, ip, name, manufacturer, os, device, port, ssid, vlan, first_seen, last_seen "
                                "FROM nebula_client_seen WHERE site_id = ? AND mac = ?", (site_id, mac)))
        return r[0] if r else None
    except Exception:  # noqa: BLE001 -- pas encore d'historique
        return None


def _apprentissage(conn):
    if _appris["st"] is None:
        conn.executescript(SCHEMA)
        decs = _dicts(conn.execute("SELECT site_id, mac, categorie, proposee, confiance_proposee, traits, par, at FROM nebula_categorie_decisions"))
        for d in decs:
            try:
                d["traits"] = json.loads(d.get("traits") or "{}")
            except ValueError:
                d["traits"] = {}
        _appris.update(st=categorie.apprentissage(decs), decisions={(d["site_id"], d["mac"]): d for d in decs}, at=time.time())
    return _appris["st"], _appris["decisions"]


def population(conn, site_id, now=None):
    now = int(now or time.time())
    c = _cache.get(site_id)
    if c and now - c["at"] < POPULATION_TTL_S:
        return c["pop"]
    try:
        fiches = _dicts(conn.execute("SELECT mac, name, manufacturer, os FROM nebula_client_seen WHERE site_id = ? AND last_seen >= ?", (site_id, now - JOURS * 86400)))
    except Exception:  # noqa: BLE001
        fiches = []
    pop = categorie.population([categorie.traits(f, activite.profil(conn, site_id, f["mac"], JOURS, now)) for f in fiches])
    _cache[site_id] = {"at": now, "pop": pop, "n": len(fiches)}
    return pop


def categorie_client(conn, site_id, f, now=None, avec_profil=False, profil=None):
    p = profil or activite.profil(conn, site_id, f["mac"], JOURS, now)
    st, decs = _apprentissage(conn)
    r = categorie.categoriser(f, p, population(conn, site_id, now), appris=st, decision=decs.get((site_id, f["mac"])))
    r["population"] = (_cache.get(site_id) or {}).get("n")
    if avec_profil:
        r["profil"] = p
    return r


def categories_site(conn, site_id, now=None):
    """Catégorie de chaque client du site (vu depuis 400 jours) -> {mac: {categorie, confiance, niveau}} ; 15 min en cache."""
    now = int(now or time.time())
    c = _cats.get(site_id)
    if c and now - c["at"] < CATEGORIES_TTL_S:
        return c["par_mac"]
    try:
        fiches = _dicts(conn.execute("SELECT site_id, mac, ip, name, manufacturer, os, device, port, ssid, vlan FROM nebula_client_seen WHERE site_id = ?", (site_id,)))
    except Exception:  # noqa: BLE001
        fiches = []
    out = {}
    for f in fiches:
        r = categorie_client(conn, site_id, f, now)
        out[f["mac"]] = {"categorie": r["categorie"], "confiance": r["confiance"], "niveau": r["niveau"]}
    _cats[site_id] = {"at": now, "par_mac": out}
    return out


def decider(conn, site_id, mac, cat, par=None, now=None):
    """Confirme (cat = catégorie proposée) ou corrige (autre catégorie) la catégorie d'un client ; apprentissage mis à jour."""
    if cat not in categorie.CATEGORIES:
        raise ValueError("catégorie inconnue : %s" % ", ".join(categorie.CATEGORIES))
    f = fiche(conn, site_id, mac)
    if not f:
        raise LookupError("client jamais vu sur ce site")
    conn.executescript(SCHEMA)
    conn.execute("DELETE FROM nebula_categorie_decisions WHERE site_id = ? AND mac = ?", (site_id, mac))
    conn.commit()
    invalider()
    r = categorie_client(conn, site_id, f, now)          # proposition SANS décision (celle-ci vient d'être retirée)
    conn.execute("INSERT INTO nebula_categorie_decisions (site_id, mac, categorie, proposee, confiance_proposee, traits, par, at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                 (site_id, mac, cat, r["proposee"], r["confiance"], json.dumps(r["traits"], ensure_ascii=False), par, int(now or time.time())))
    conn.commit()
    invalider()
    return {"categorie": cat, "proposee": r["proposee"], "correction": r["proposee"] != cat}


def annuler(conn, site_id, mac):
    conn.executescript(SCHEMA)
    n = conn.execute("DELETE FROM nebula_categorie_decisions WHERE site_id = ? AND mac = ?", (site_id, mac)).rowcount
    conn.commit()
    invalider()
    return n
