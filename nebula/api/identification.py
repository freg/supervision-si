# -*- coding: utf-8 -*-
"""Identification des cibles (#1003, #1004, #1007) -- assemblage : fiche du client (historique) + profil d'activité
(activite.py) + population du site (singularités) + apprentissage des confirmations humaines -> catégorie ET type
(categorie.py). Utilisé par l'historique des clients (filtres et confirmation) et la liste de surveillance.

Deux AXES parallèles (#1007) :
- « categorie » : nature logique / système.
- « type » : forme de l'appareil (tablette, mobile, casque VR, portable, ordinateur fixe, équipement réseau,
  équipement supervision). Les équipements de supervision sont reconnus en plus par leur MAC présente dans la flotte des
  agents (`macs_sup`).

Confirmation humaine (#1004) : une personne confirme ou corrige, PAR AXE, la catégorie ou le type d'un client ; ce
client devient « confirmé » sur cet axe, et ses traits enseignent cette valeur aux autres clients qui les partagent --
leurs certitudes montent ou descendent. Annuler une décision la retire de l'apprentissage."""
import json
import time

import activite
import categorie

POPULATION_TTL_S = 3600
CATEGORIES_TTL_S = 900
JOURS = 14
AXES = ("categorie", "type")
VALEURS = {"categorie": categorie.CATEGORIES, "type": categorie.TYPES}
SCHEMA = """
CREATE TABLE IF NOT EXISTS nebula_axe_decisions (
    site_id TEXT NOT NULL, mac TEXT NOT NULL, axe TEXT NOT NULL DEFAULT 'categorie', categorie TEXT NOT NULL,
    proposee TEXT, confiance_proposee INTEGER, traits TEXT, par TEXT, at INTEGER NOT NULL,
    PRIMARY KEY (site_id, mac, axe));
"""
_cache = {}          # site -> {at, pop, n}
_cats = {}           # site -> {at, par_mac}
_appris = {"at": 0, "par_axe": None}


def _dicts(cur):
    cols = [c[0] for c in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def invalider():
    _cats.clear()
    _appris.update(at=0, par_axe=None)


def _ensure(conn):
    conn.executescript(SCHEMA)
    # #1007 : reprise des décisions de catégorie de #1004 (table nebula_categorie_decisions) vers la table à deux axes
    try:
        if conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='nebula_categorie_decisions'").fetchone() \
           and not conn.execute("SELECT 1 FROM nebula_axe_decisions WHERE axe='categorie' LIMIT 1").fetchone():
            conn.execute("INSERT OR IGNORE INTO nebula_axe_decisions (site_id, mac, axe, categorie, proposee, confiance_proposee, traits, par, at) "
                         "SELECT site_id, mac, 'categorie', categorie, proposee, confiance_proposee, traits, par, at FROM nebula_categorie_decisions")
            conn.commit()
    except Exception:  # noqa: BLE001 -- la reprise n'est jamais bloquante
        pass


def fiche(conn, site_id, mac):
    try:
        r = _dicts(conn.execute("SELECT site_id, mac, ip, name, manufacturer, os, device, port, ssid, vlan, first_seen, last_seen "
                                "FROM nebula_client_seen WHERE site_id = ? AND mac = ?", (site_id, mac)))
        return r[0] if r else None
    except Exception:  # noqa: BLE001 -- pas encore d'historique
        return None


def _apprentissage(conn):
    """-> {axe: {"st": apprentissage, "decisions": {(site, mac): decision}}}."""
    if _appris["par_axe"] is None:
        _ensure(conn)
        decs = _dicts(conn.execute("SELECT site_id, mac, axe, categorie, proposee, confiance_proposee, traits, par, at FROM nebula_axe_decisions"))
        for d in decs:
            try:
                d["traits"] = json.loads(d.get("traits") or "{}")
            except ValueError:
                d["traits"] = {}
        par_axe = {}
        for axe in AXES:
            da = [d for d in decs if (d.get("axe") or "categorie") == axe]
            par_axe[axe] = {"st": categorie.apprentissage(da), "decisions": {(d["site_id"], d["mac"]): d for d in da}}
        _appris.update(par_axe=par_axe, at=time.time())
    return _appris["par_axe"]


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


def categorie_client(conn, site_id, f, now=None, avec_profil=False, profil=None, macs_sup=frozenset()):
    """Les DEUX axes d'un client. Renvoie l'objet de l'axe « catégorie » (compatibilité #1003) enrichi de r["type"]
    (objet de l'axe « type »). `macs_sup` : MAC connues de la flotte des agents."""
    p = profil or activite.profil(conn, site_id, f["mac"], JOURS, now)
    axes = _apprentissage(conn)
    pop = population(conn, site_id, now)
    r = categorie.categoriser(f, p, pop, appris=axes["categorie"]["st"], decision=axes["categorie"]["decisions"].get((site_id, f["mac"])))
    rt = categorie.categoriser_type(f, p, pop, appris=axes["type"]["st"], decision=axes["type"]["decisions"].get((site_id, f["mac"])),
                                    supervision=f.get("mac") in macs_sup)
    r["type"] = rt
    r["population"] = (_cache.get(site_id) or {}).get("n")
    if avec_profil:
        r["profil"] = p
    return r


def categories_site(conn, site_id, now=None, macs_sup=frozenset()):
    """Catégorie ET type de chaque client du site -> {mac: {categorie, confiance, niveau, type, confiance_type, niveau_type}} ; 15 min en cache."""
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
        r = categorie_client(conn, site_id, f, now, macs_sup=macs_sup)
        out[f["mac"]] = {"categorie": r["categorie"], "confiance": r["confiance"], "niveau": r["niveau"],
                         "type": r["type"]["categorie"], "confiance_type": r["type"]["confiance"], "niveau_type": r["type"]["niveau"]}
    _cats[site_id] = {"at": now, "par_mac": out}
    return out


def decider(conn, site_id, mac, cat, par=None, now=None, axe="categorie", macs_sup=frozenset()):
    """Confirme ou corrige la valeur d'un client sur l'axe `axe` (« categorie » ou « type ») ; apprentissage mis à jour."""
    axe = axe if axe in AXES else "categorie"
    if cat not in VALEURS[axe]:
        raise ValueError("%s inconnu%s : %s" % (axe, "e" if axe == "categorie" else "", ", ".join(VALEURS[axe])))
    f = fiche(conn, site_id, mac)
    if not f:
        raise LookupError("client jamais vu sur ce site")
    _ensure(conn)
    conn.execute("DELETE FROM nebula_axe_decisions WHERE site_id = ? AND mac = ? AND axe = ?", (site_id, mac, axe))
    conn.commit()
    invalider()
    r = categorie_client(conn, site_id, f, now, macs_sup=macs_sup)   # proposition SANS la décision (retirée à l'instant)
    base = r if axe == "categorie" else r["type"]
    conn.execute("INSERT INTO nebula_axe_decisions (site_id, mac, axe, categorie, proposee, confiance_proposee, traits, par, at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                 (site_id, mac, axe, cat, base["proposee"], base["confiance"], json.dumps(base["traits"], ensure_ascii=False), par, int(now or time.time())))
    conn.commit()
    invalider()
    return {"axe": axe, "categorie": cat, "proposee": base["proposee"], "correction": base["proposee"] != cat}


def annuler(conn, site_id, mac, axe="categorie"):
    axe = axe if axe in AXES else "categorie"
    _ensure(conn)
    n = conn.execute("DELETE FROM nebula_axe_decisions WHERE site_id = ? AND mac = ? AND axe = ?", (site_id, mac, axe)).rowcount
    conn.commit()
    invalider()
    return n
