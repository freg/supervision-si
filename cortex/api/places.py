# -*- coding: utf-8 -*-
"""Cortex, étape 3 (livraison #464) : LIEUX et POSITIONS -- logique pure.

Une entité a une position mémorisée avec sa PROVENANCE et sa CONFIANCE,
résolue par une échelle explicite (chaque barreau est un principe de
principles.py) :

    pos-declared      coordonnées portées par l'appareil lui-même (network-agent)
    pos-validated     correspondance nom -> localisation validée / manuelle (pixel-grid)
    pos-place         lieu déclaré de l'entité (site, bâtiment, salle) qui a des coordonnées
    pos-geolocation   table des géolocalisations, par nom ou par IP
    pos-resolved-name correspondance automatique ou suggérée (pixel-grid)
    pos-propagated    par relation : client -> sa borne, hôte -> sa passerelle (même site), onduleur -> son site
    pos-neighbor      moyenne pondérée des voisins positionnés (chaîne conservée)
    pos-fallback      position de repli (__default__)

La hiérarchie de lieux (site > bâtiment > étage > salle > baie) vient des
géolocalisations (parent_localisation / location_type), des appareils
network-agent (building / room / zone) et du catalogue geo-catalog
(positions validées / corrigées). Un lieu sans coordonnées hérite de
celles de son parent (principe place-hierarchy).

Rien ici ne lit le réseau : les collecteurs passent les listes.
"""
import math
import re

PLACE_KINDS = ("site", "batiment", "etage", "salle", "baie", "lieu")
_TYPE_ALIAS = {"site": "site", "agence": "site", "building": "batiment", "batiment": "batiment", "bâtiment": "batiment",
               "floor": "etage", "etage": "etage", "étage": "etage", "room": "salle", "salle": "salle", "local": "salle",
               "rack": "baie", "baie": "baie", "zone": "lieu", "lieu": "lieu", "commune": "lieu", "ville": "lieu"}
# ordre de précision croissante : une salle est plus précise qu'un site
PRECISION = {"lieu": 0, "site": 1, "batiment": 2, "etage": 3, "salle": 4, "baie": 5}
SUPERVISING_SOURCES = {"si-agent", "netprobe", "ups", "vigilance", "snmp", "orchestrator"}


def norm(s):
    return re.sub(r"\s+", " ", str(s or "").strip().lower())


def place_key(kind, name):
    return "%s:%s" % (kind, norm(name))


def _valid(lat, lon):
    try:
        lat, lon = float(lat), float(lon)
    except (TypeError, ValueError):
        return False
    return -90 <= lat <= 90 and -180 <= lon <= 180 and not (lat == 0 and lon == 0)


# ---------------------------------------------------------------- lieux
def places_from_geolocations(geolocations):
    """pixel-grid /geolocations -> lieux (avec parent et type quand déclarés)."""
    out = []
    for g in geolocations or []:
        loc = g.get("localisation")
        if not loc or loc == "__default__":
            continue
        kind = _TYPE_ALIAS.get(norm(g.get("location_type")), "lieu") if g.get("location_type") else "lieu"
        parent = g.get("parent_localisation")
        out.append({"key": place_key(kind, loc), "kind": kind, "name": loc, "parent": ("lieu:%s" % norm(parent)) if parent else None,
                    "lat": g.get("latitude") if _valid(g.get("latitude"), g.get("longitude")) else None,
                    "lon": g.get("longitude") if _valid(g.get("latitude"), g.get("longitude")) else None,
                    "source": "geolocations", "principle": "pos-geolocation", "aliases": ["lieu:%s" % norm(loc)]})
    return out


def places_from_network_agent(sites, devices):
    """Sites network-agent (nom, coordonnées éventuelles) + bâtiments / salles
    déclarés sur les appareils -> lieux ; et lieu déclaré par appareil
    (-> {id appareil: clé du lieu le plus précis})."""
    out, by_device = {}, {}
    seg_site = {}
    for s in sites or []:
        k = place_key("site", s.get("name"))
        out[k] = {"key": k, "kind": "site", "name": s.get("name"), "parent": None,
                  "lat": s.get("latitude") if _valid(s.get("latitude"), s.get("longitude")) else None,
                  "lon": s.get("longitude") if _valid(s.get("latitude"), s.get("longitude")) else None,
                  "source": "network-agent", "principle": "referential", "aliases": ["lieu:%s" % norm(s.get("name"))]}
        for seg in s.get("segments") or []:
            seg_site[seg.get("id")] = s.get("name")
    for d in devices or []:
        site = seg_site.get(d.get("network_segment_id"))
        chain = []
        if site:
            chain.append(place_key("site", site))
        if d.get("building"):
            k = place_key("batiment", "%s/%s" % (site or "?", d["building"]))
            out.setdefault(k, {"key": k, "kind": "batiment", "name": d["building"], "parent": chain[-1] if chain else None, "lat": None, "lon": None,
                               "source": "network-agent", "principle": "referential", "aliases": []})
            chain.append(k)
        if d.get("room"):
            k = place_key("salle", "%s/%s/%s" % (site or "?", d.get("building") or "-", d["room"]))
            out.setdefault(k, {"key": k, "kind": "salle", "name": d["room"], "parent": chain[-1] if chain else None, "lat": None, "lon": None,
                               "source": "network-agent", "principle": "referential", "aliases": []})
            chain.append(k)
        if chain:
            by_device[d.get("id")] = chain[-1]
    return list(out.values()), by_device


def places_from_geo_catalog(positions):
    """geo-catalog /positions : la position la plus sûre par localisation
    (validée / corrigée > interprétée avec confiance)."""
    out = []
    for p in positions or []:
        label = p.get("label") or (p.get("key") or "").split(":", 1)[-1]
        if not label:
            continue
        lat, lon = (p.get("decided_lat"), p.get("decided_lon")) if p.get("status") in ("validated", "corrected") else (p.get("lat"), p.get("lon"))
        if not _valid(lat, lon):
            continue
        conf = 0.95 if p.get("status") in ("validated", "corrected") else min(0.9, (p.get("confidence") or 50) / 100.0)
        out.append({"key": "lieu:%s" % norm(label), "kind": "lieu", "name": label, "parent": None, "lat": lat, "lon": lon,
                    "source": "geo-catalog", "principle": "pos-validated" if conf >= 0.95 else "pos-geolocation", "confidence": conf,
                    "aliases": [], "links": [l.get("object_id") for l in (p.get("links") or []) if l.get("object_type") == "supervised"]})
    return out


def merge_places(*lists):
    """Fusion par clé ET par alias (« lieu:bureau » et « site:bureau » sont
    le même lieu quand ils portent le même nom) ; coordonnées prises
    quand manquantes ; le parent le plus précis gagne."""
    out, alias = {}, {}
    for lst in lists:
        for p in lst:
            k = alias.get(p["key"], p["key"])
            for a in p.get("aliases") or []:
                if a in out and k not in out:
                    k = a
            cur = out.get(k)
            if not cur:
                out[k] = dict(p)
                out[k]["sources"] = [p.get("source")]
                out[k]["links"] = list(p.get("links") or [])
                for a in p.get("aliases") or []:
                    alias[a] = k
                alias[p["key"]] = k
                continue
            if cur.get("lat") is None and p.get("lat") is not None:
                cur["lat"], cur["lon"], cur["principle"] = p["lat"], p["lon"], p.get("principle")
            if not cur.get("parent") and p.get("parent"):
                cur["parent"] = p["parent"]
            if PRECISION.get(p.get("kind"), 0) > PRECISION.get(cur.get("kind"), 0):
                cur["kind"] = p["kind"]
            if p.get("source") not in cur["sources"]:
                cur["sources"].append(p.get("source"))
            for l in p.get("links") or []:
                if l not in cur["links"]:
                    cur["links"].append(l)
            for a in p.get("aliases") or []:
                alias[a] = k
            alias[p["key"]] = k
    # même type + même nom + même site racine = même lieu (« Local technique »
    # déclaré par une géolocalisation sous « siege » et par network-agent
    # sous siege/B1) : on garde la chaîne la plus profonde
    def root_of(k):
        seen = set()
        while k and k not in seen:
            seen.add(k)
            p = out.get(alias.get(k, k))
            if not p or not p.get("parent"):
                return alias.get(k, k)
            k = p["parent"]
        return k
    def depth_of(k):
        d, seen = 0, set()
        while k and k not in seen:
            seen.add(k); d += 1
            p = out.get(alias.get(k, k))
            k = p.get("parent") if p else None
        return d
    groups = {}
    for k, p in list(out.items()):
        if p.get("kind") in ("site", "lieu"):
            continue
        groups.setdefault((p["kind"], norm(p.get("name")), root_of(k)), []).append(k)
    for keys in groups.values():
        if len(keys) < 2:
            continue
        keys.sort(key=lambda k: -depth_of(k))
        keep = out[keys[0]]
        for k in keys[1:]:
            other = out.pop(k)
            if keep.get("lat") is None and other.get("lat") is not None:
                keep["lat"], keep["lon"], keep["principle"] = other["lat"], other["lon"], other.get("principle")
            for src in other.get("sources") or []:
                if src not in keep["sources"]:
                    keep["sources"].append(src)
            for l in other.get("links") or []:
                if l not in keep["links"]:
                    keep["links"].append(l)
            alias[k] = keys[0]
            for a, v in list(alias.items()):
                if v == k:
                    alias[a] = keys[0]
    # héritage : un lieu sans coordonnées prend celles de son parent
    for p in out.values():
        seen, cur = set(), p
        while cur.get("lat") is None and cur.get("parent") and cur["parent"] not in seen:
            seen.add(cur["parent"])
            parent = out.get(alias.get(cur["parent"], cur["parent"]))
            if not parent:
                break
            if parent.get("lat") is not None:
                p["lat"], p["lon"], p["principle"], p["inherited_from"] = parent["lat"], parent["lon"], "place-hierarchy", parent["key"]
                break
            cur = parent
    return list(out.values()), alias


def place_chain(places_by_key, key, alias=None):
    """[site, bâtiment, salle…] du plus large au plus précis."""
    alias = alias or {}
    chain, seen = [], set()
    k = alias.get(key, key)
    while k and k not in seen and k in places_by_key:
        seen.add(k)
        chain.append(places_by_key[k])
        k = places_by_key[k].get("parent")
        k = alias.get(k, k) if k else None
    return list(reversed(chain))


# ---------------------------------------------------------------- positions
def _subjects(e):
    s = [e["key"]]
    if e.get("ip"):
        s.append("ip:%s" % e["ip"])
    if e.get("mac"):
        s.append("mac:%s" % e["mac"])
    if e.get("name"):
        s.append("name:%s" % norm(e["name"]))
    return s


def resolve_positions(entities, relations, places, alias, geolocations=None, matches=None, entity_places=None, max_depth=3):
    """-> {clé entité: {lat, lon, place, provenance, principle, confidence, chain, source}}.
    `entity_places` : {clé entité: clé de lieu déclaré} (network-agent).
    Les barreaux de l'échelle sont essayés dans l'ordre ; le premier qui
    répond fixe la position ET sa provenance."""
    by_key = {p["key"]: p for p in places}
    geo = {norm(g.get("localisation")): g for g in (geolocations or []) if _valid(g.get("latitude"), g.get("longitude"))}
    mt = {}
    for m in matches or []:
        if m.get("subject") and _valid(m.get("latitude"), m.get("longitude")):
            mt[m["subject"]] = m
    entity_places = entity_places or {}
    out = {}

    def place_pos(pk):
        p = by_key.get(alias.get(pk, pk))
        if p and p.get("lat") is not None:
            return p
        return None

    for e in entities:
        k = e["key"]
        subs = _subjects(e)
        # 1. déclarée par l'appareil
        g = e.get("geo") or {}
        if _valid(g.get("lat"), g.get("lon")):
            out[k] = {"lat": float(g["lat"]), "lon": float(g["lon"]), "place": entity_places.get(k), "provenance": "déclarée",
                      "principle": "pos-declared", "confidence": 0.95, "chain": [], "source": g.get("source") or "network-agent"}
            continue
        # 2. correspondance validée / manuelle
        m = next((mt[s] for s in subs if s in mt and mt[s].get("status") in ("validated", "manual")), None)
        if m:
            out[k] = {"lat": float(m["latitude"]), "lon": float(m["longitude"]), "place": alias.get("lieu:%s" % norm(m["localisation"]), "lieu:%s" % norm(m["localisation"])),
                      "provenance": "validée", "principle": "pos-validated", "confidence": 0.9, "chain": [], "source": "pixel-grid",
                      "evidence": "%s ≈ %s (%s)" % (m["subject"], m["localisation"], m["status"])}
            continue
        # 3. lieu déclaré (salle > bâtiment > site) puis site textuel
        pk = entity_places.get(k)
        p = place_pos(pk) if pk else None
        if not p and e.get("site"):
            p = place_pos(place_key("site", e["site"])) or place_pos("lieu:%s" % norm(e["site"]))
        if p:
            out[k] = {"lat": p["lat"], "lon": p["lon"], "place": p["key"], "provenance": "lieu déclaré", "principle": "pos-place",
                      "confidence": 0.85 if p.get("principle") != "place-hierarchy" else 0.75, "chain": [], "source": ",".join(p.get("sources") or []),
                      "evidence": "lieu %s (%s)" % (p["name"], p["kind"]) + (" hérité de %s" % p["inherited_from"] if p.get("inherited_from") else "")}
            continue
        # 4. géolocalisations par nom / IP
        gg = next((geo[s] for s in (norm(e.get("name")), norm(e.get("ip"))) if s and s in geo), None)
        if gg:
            out[k] = {"lat": float(gg["latitude"]), "lon": float(gg["longitude"]), "place": alias.get("lieu:%s" % norm(gg["localisation"]), "lieu:%s" % norm(gg["localisation"])),
                      "provenance": "géolocalisation", "principle": "pos-geolocation", "confidence": 0.8, "chain": [], "source": "pixel-grid",
                      "evidence": "table des géolocalisations (%s)" % gg["localisation"]}
            continue
        # 5. correspondance automatique / suggérée
        m = next((mt[s] for s in subs if s in mt and mt[s].get("status") in ("auto", "suggested")), None)
        if m:
            out[k] = {"lat": float(m["latitude"]), "lon": float(m["longitude"]), "place": alias.get("lieu:%s" % norm(m["localisation"]), "lieu:%s" % norm(m["localisation"])),
                      "provenance": "résolue par le nom", "principle": "pos-resolved-name", "confidence": 0.6 if m.get("status") == "auto" else 0.5, "chain": [], "source": "pixel-grid",
                      "evidence": "%s ≈ %s (%s, score %s)" % (m["subject"], m["localisation"], m.get("method") or "?", m.get("score"))}
    # 6. propagation par relation (une passe, depuis les positions sûres)
    sites_of = {e["key"]: e.get("site") for e in entities}
    prop = {}
    for r in relations or []:
        a, b, kind = r.get("a"), r.get("b"), r.get("kind")
        if kind == "uplink" and b not in out and a in out and b not in prop:          # client <- sa borne (a = borne)
            prop[b] = (a, "borne / switch d'accès", r)
        elif kind == "gateway_of" and b not in out and a in out and b not in prop and sites_of.get(a) == sites_of.get(b):
            prop[b] = (a, "passerelle par défaut (même site)", r)
        elif kind == "powers" and a not in out and b in out and a not in prop:        # onduleur -> hôte alimenté
            prop[a] = (b, "hôte alimenté", r)
    for k, (frm, why, r) in prop.items():
        p = out[frm]
        out[k] = {"lat": p["lat"], "lon": p["lon"], "place": p.get("place"), "provenance": "propagée", "principle": "pos-propagated",
                  "confidence": round(min(0.7, p["confidence"] * 0.8), 3), "chain": [{"via": r.get("kind"), "from": frm, "why": why, "from_provenance": p["provenance"]}],
                  "source": "cortex", "evidence": "%s de %s" % (why, frm)}
    # 7. voisinage : moyenne pondérée, profondeur bornée, chaîne conservée
    neigh = {}
    for r in relations or []:
        if r.get("kind") in ("flow", "talks_to", "neighbor", "same_site", "uplink", "gateway_of"):
            neigh.setdefault(r["a"], []).append((r["b"], r))
            neigh.setdefault(r["b"], []).append((r["a"], r))
    keys = [e["key"] for e in entities]
    for depth in range(1, max_depth + 1):
        added = []
        for k in keys:
            if k in out:
                continue
            ns = [(o, r) for o, r in neigh.get(k, []) if o in out]
            if not ns:
                continue
            sw = lat = lon = 0.0
            chain = []
            for o, r in ns:
                p = out[o]
                w = max(0.05, float(r.get("weight") or 0.1)) * (1.0 if p["principle"] != "pos-neighbor" else 0.5)
                sw += w; lat += p["lat"] * w; lon += p["lon"] * w
                chain.append({"via": r.get("kind"), "from": o, "from_provenance": p["provenance"], "weight": round(w, 3)})
            added.append((k, {"lat": lat / sw, "lon": lon / sw, "place": None, "provenance": "déduite du voisinage", "principle": "pos-neighbor",
                              "confidence": round(0.5 / depth, 3), "chain": chain, "source": "cortex", "depth": depth,
                              "evidence": "moyenne de %d voisin(s) positionné(s)" % len(ns)}))
        if not added:
            break
        for k, p in added:
            out[k] = p
    # 8. repli
    d = next((g for g in (geolocations or []) if g.get("localisation") == "__default__" and _valid(g.get("latitude"), g.get("longitude"))), None)
    if d:
        for k in keys:
            if k not in out:
                out[k] = {"lat": float(d["latitude"]), "lon": float(d["longitude"]), "place": None, "provenance": "repli", "principle": "pos-fallback",
                          "confidence": 0.1, "chain": [], "source": "pixel-grid", "evidence": "position de repli (__default__)"}
    return out


def work_queue(entities, positions):
    """File de travail : entités sans position ou en repli, groupées par site."""
    out = {}
    for e in entities:
        p = positions.get(e["key"])
        if p and p["principle"] != "pos-fallback":
            continue
        site = e.get("site") or "(sans site)"
        out.setdefault(site, []).append({"key": e["key"], "name": e.get("name"), "ip": e.get("ip"), "kind": e.get("kind"),
                                         "status": "repli" if p else "sans position", "sources": [o.get("source") for o in e.get("origins") or []]})
    return [{"site": s, "count": len(v), "entities": v} for s, v in sorted(out.items(), key=lambda kv: -len(kv[1]))]


def is_supervised(entity):
    return any((o.get("source") in SUPERVISING_SOURCES) for o in entity.get("origins") or [])


# ---------------------------------------------------------------- fiche d'intervention
_SEV_W = {"critical": 3, "warning": 2, "info": 1}


def intervention_sheet(entity, position, places_by_key, alias, relations, incidents, events, entities_by_key, positions, notes=None, bastion_targets=None, tickets_url=None):
    """« Où aller et avec quoi » pour une entité en défaut."""
    k = entity["key"]
    chain = place_chain(places_by_key, position["place"], alias) if position and position.get("place") else []
    if not chain and entity.get("site"):
        chain = place_chain(places_by_key, place_key("site", entity["site"]), alias)
    notes = notes or {}
    site_note = next((notes.get(p["key"]) for p in reversed(chain) if notes.get(p["key"])), None)
    upstream, downstream = [], []
    site_key = "site:%s" % norm(entity.get("site")) if entity.get("site") else None
    for r in relations or []:
        if site_key and r.get("kind") == "powers_site" and r.get("b") == site_key and r.get("a") != k:
            o = entities_by_key.get(r["a"], {"key": r["a"]})
            upstream.append({"key": r["a"], "name": o.get("name") or r["a"], "kind": "powers_site", "state": _state_of(r["a"], events), "why": "onduleur du site (supposé)"})
            continue
        if r.get("b") == k and r.get("kind") in ("gateway_of", "uplink", "powers_site", "powers"):
            o = entities_by_key.get(r["a"], {"key": r["a"]})
            upstream.append({"key": r["a"], "name": o.get("name") or o.get("ip") or r["a"], "kind": r.get("kind"), "state": _state_of(r["a"], events), "why": r.get("evidence")})
        if r.get("a") == k and r.get("kind") in ("gateway_of", "uplink", "powers_site", "powers"):
            o = entities_by_key.get(r["b"], {"key": r["b"]})
            downstream.append({"key": r["b"], "name": o.get("name") or o.get("ip") or r["b"], "kind": r.get("kind")})
    inc = [{"key": i["key"], "title": i.get("title"), "severity": i.get("severity"), "state": i.get("state"), "root": i.get("root")}
           for i in incidents or [] if k in (i.get("entities") or []) or i.get("root") == k]
    same_place = []
    if position and position.get("place"):
        for ok, op in positions.items():
            if ok != k and op.get("place") == position["place"]:
                oe = entities_by_key.get(ok, {})
                same_place.append({"key": ok, "name": oe.get("name") or oe.get("ip") or ok, "kind": oe.get("kind"), "role": (oe.get("hints") or [{}])[0].get("role") if oe.get("hints") else None})
    bastion = None
    if bastion_targets is not None:
        bastion = {"available": bool(entity.get("ip") and entity["ip"] in set(bastion_targets)), "via": "si-proxy : shell sur le hub, CONNECT vers le LAN depuis le Mac autorisé"}
    ticket = None
    if tickets_url:
        ticket = "%s?subject=%s" % (tickets_url.rstrip("/"), (entity.get("name") or k).replace(" ", "+"))
    return {"entity": {"key": k, "name": entity.get("name"), "ip": entity.get("ip"), "mac": entity.get("mac"), "kind": entity.get("kind"), "site": entity.get("site"),
                       "vendor": entity.get("vendor"), "description": entity.get("description")},
            "where": [{"kind": p["kind"], "name": p["name"], "key": p["key"]} for p in chain],
            "position": position, "contact": site_note.get("contact") if site_note else None, "access": site_note.get("access") if site_note else None,
            "notes": site_note.get("notes") if site_note else None,
            "upstream": upstream, "downstream": downstream[:20], "incidents": inc, "same_place": same_place[:30],
            "bastion": bastion, "ticket_url": ticket, "supervised": is_supervised(entity)}


def _state_of(key, events):
    worst = None
    for ev in events or []:
        if ev.get("entity") == key and ev.get("state") in ("open", "acked"):
            if worst is None or _SEV_W.get(ev.get("severity"), 0) > _SEV_W.get(worst, 0):
                worst = ev.get("severity")
    return worst or "ok"


# ---------------------------------------------------------------- couches carto (GeoJSON)
def _feat(lon, lat, props, geom="Point", coords=None):
    return {"type": "Feature", "geometry": {"type": geom, "coordinates": coords if coords is not None else [lon, lat]}, "properties": props}


def layers(entities, positions, incidents, relations, places_by_key):
    """Couches activables sur une carte :
    incidents (halos pondérés), density (par lieu), unsupervised (vues par
    la découverte seule), dependencies (lignes amont -> aval), positions
    (toutes les entités positionnées, provenance en propriété)."""
    by_key = {e["key"]: e for e in entities}
    pos_feats, unsup, dens = [], [], {}
    for k, p in positions.items():
        e = by_key.get(k, {"key": k})
        props = {"key": k, "name": e.get("name") or k, "kind": e.get("kind"), "site": e.get("site"), "provenance": p["provenance"],
                 "principle": p["principle"], "confidence": p["confidence"], "place": p.get("place")}
        pos_feats.append(_feat(p["lon"], p["lat"], props))
        if not is_supervised(e) and p["principle"] != "pos-fallback":
            unsup.append(_feat(p["lon"], p["lat"], {**props, "reason": "vue seulement par la découverte (%s)" % ", ".join(sorted({o.get("source") or "?" for o in e.get("origins") or []}))}))
        pk = p.get("place") or ("site:%s" % norm(e.get("site")) if e.get("site") else None)
        if pk:
            d = dens.setdefault(pk, {"count": 0, "lat": p["lat"], "lon": p["lon"], "supervised": 0, "incidents": 0})
            d["count"] += 1
            d["supervised"] += 1 if is_supervised(e) else 0
    inc_feats = []
    for i in incidents or []:
        if i.get("state") == "closed":
            continue
        root = i.get("root")
        p = positions.get(root) or next((positions[x] for x in (i.get("entities") or []) if x in positions), None)
        if not p:
            continue
        w = _SEV_W.get(i.get("severity"), 1)
        n = len(i.get("entities") or [])
        inc_feats.append(_feat(p["lon"], p["lat"], {"key": i["key"], "title": i.get("title"), "severity": i.get("severity"), "state": i.get("state"),
                                                    "entities": n, "weight": w, "radius": 8 + 4 * w + 2 * min(n, 10), "root": root,
                                                    "confidence": i.get("confidence")}))
        pk = p.get("place")
        if pk and pk in dens:
            dens[pk]["incidents"] += 1
    dens_feats = []
    for pk, d in dens.items():
        pl = places_by_key.get(pk, {})
        dens_feats.append(_feat(d["lon"], d["lat"], {"place": pk, "name": pl.get("name") or pk.split(":", 1)[-1], "kind": pl.get("kind"), "count": d["count"],
                                                     "supervised": d["supervised"], "unsupervised": d["count"] - d["supervised"], "incidents": d["incidents"],
                                                     "radius": 6 + 3 * math.sqrt(d["count"])}))
    dep_feats = []
    for r in relations or []:
        if r.get("kind") in ("gateway_of", "uplink", "powers_site", "powers") and r["a"] in positions and r["b"] in positions:
            pa, pb = positions[r["a"]], positions[r["b"]]
            if abs(pa["lat"] - pb["lat"]) < 1e-9 and abs(pa["lon"] - pb["lon"]) < 1e-9:
                continue   # même point : rien à tracer
            dep_feats.append(_feat(None, None, {"kind": r["kind"], "a": r["a"], "b": r["b"], "a_name": by_key.get(r["a"], {}).get("name") or r["a"],
                                                "b_name": by_key.get(r["b"], {}).get("name") or r["b"], "principle": r.get("principle"), "weight": r.get("weight")},
                                  geom="LineString", coords=[[pa["lon"], pa["lat"]], [pb["lon"], pb["lat"]]]))
    unpositioned = [e["key"] for e in entities if e["key"] not in positions]
    fc = lambda f: {"type": "FeatureCollection", "features": f}  # noqa: E731
    return {"positions": fc(pos_feats), "incidents": fc(inc_feats), "density": fc(dens_feats), "unsupervised": fc(unsup), "dependencies": fc(dep_feats),
            "summary": {"positioned": len(positions), "unpositioned": len(unpositioned), "incidents": len(inc_feats), "unsupervised": len(unsup),
                        "places": len(dens_feats), "dependencies": len(dep_feats),
                        "by_provenance": _count(positions.values(), "provenance")}}


def _count(items, field):
    out = {}
    for it in items:
        out[it.get(field) or "?"] = out.get(it.get(field) or "?", 0) + 1
    return out
