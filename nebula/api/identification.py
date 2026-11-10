# -*- coding: utf-8 -*-
"""Identification des cibles (#1003) -- assemblage : fiche du client (historique) + profil d'activité (activite.py) +
population du site (singularités, en cache 1 h) -> catégorie (categorie.py). Utilisé par l'historique des clients et la
liste de surveillance."""
import time

import activite
import categorie

POPULATION_TTL_S = 3600
JOURS = 14
_cache = {}


def fiche(conn, site_id, mac):
    try:
        cur = conn.execute("SELECT mac, ip, name, manufacturer, os, device, port, ssid, vlan, first_seen, last_seen "
                           "FROM nebula_client_seen WHERE site_id = ? AND mac = ?", (site_id, mac))
        r = cur.fetchone()
        return dict(zip([c[0] for c in cur.description], r)) if r else None
    except Exception:  # noqa: BLE001 -- pas encore d'historique
        return None


def population(conn, site_id, now=None):
    now = int(now or time.time())
    c = _cache.get(site_id)
    if c and now - c["at"] < POPULATION_TTL_S:
        return c["pop"]
    try:
        cur = conn.execute("SELECT mac, name, manufacturer, os FROM nebula_client_seen WHERE site_id = ? AND last_seen >= ?", (site_id, now - JOURS * 86400))
        cols = [d[0] for d in cur.description]
        fiches = [dict(zip(cols, r)) for r in cur.fetchall()]
    except Exception:  # noqa: BLE001
        fiches = []
    pop = categorie.population([categorie.traits(f, activite.profil(conn, site_id, f["mac"], JOURS, now)) for f in fiches])
    _cache[site_id] = {"at": now, "pop": pop, "n": len(fiches)}
    return pop


def categorie_client(conn, site_id, f, now=None, avec_profil=False):
    p = activite.profil(conn, site_id, f["mac"], JOURS, now)
    r = categorie.categoriser(f, p, population(conn, site_id, now))
    r["population"] = (_cache.get(site_id) or {}).get("n")
    if avec_profil:
        r["profil"] = p
    return r
