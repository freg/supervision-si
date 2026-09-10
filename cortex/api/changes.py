# -*- coding: utf-8 -*-
"""« Ce qui a changé » (livraison #463) -- logique PURE : compare l'état
avant / après une collecte (entités, rôle dominant, relations, passerelle
par défaut) et produit des changements datés, chacun avec le principe
change-since. Les disparitions ne sont comptées que pour les sources
lues avec succès (limite connue du principe)."""


def snapshot(entities, relations, routes, roles_of):
    """État comparable : {entities: {clé: (kind, rôle dominant, site)}, relations: {sig}, gateways: {hôte: via}}"""
    ents = {}
    for e in entities:
        roles = roles_of(e) if roles_of else []
        ents[e["key"]] = (e.get("kind"), roles[0]["role"] if roles else None, e.get("site"), {o.get("source") for o in (e.get("origins") or [])})
    rels = {(r["a"], r["b"], r["kind"]) for r in relations}
    gws = {r["host"]: r.get("via") for r in routes if r.get("kind") == "default"}
    return {"entities": ents, "relations": rels, "gateways": gws}


def compute_changes(before, after, failed_sources=(), names=None):
    names = names or {}
    n = lambda k: names.get(k, k)  # noqa: E731
    out = []
    be, ae = before.get("entities", {}), after.get("entities", {})
    for k, (kind, role, site, sources) in ae.items():
        if k not in be:
            out.append({"kind": "entity-new", "subject": k, "message": "nouvelle entité %s (%s%s)" % (n(k), kind or "?", ", " + site if site else ""), "principle": "change-since"})
        else:
            bkind, brole, bsite, _ = be[k]
            if role and brole and role != brole:
                out.append({"kind": "role-changed", "subject": k, "message": "%s : rôle dominant %s → %s" % (n(k), brole, role), "principle": "change-since"})
            elif role and not brole:
                out.append({"kind": "role-new", "subject": k, "message": "%s : rôle %s" % (n(k), role), "principle": "change-since"})
            if site and bsite and site != bsite:
                out.append({"kind": "site-changed", "subject": k, "message": "%s : site %s → %s" % (n(k), bsite, site), "principle": "change-since"})
    for k, (kind, role, site, sources) in be.items():
        if k not in ae and not (sources & set(failed_sources)):
            out.append({"kind": "entity-gone", "subject": k, "message": "%s n'est plus vue par aucune source" % n(k), "principle": "change-since"})
    br, ar = before.get("relations", set()), after.get("relations", set())
    for a, b, kind in sorted(ar - br):
        out.append({"kind": "relation-new", "subject": a, "message": "nouvelle relation %s —%s→ %s" % (n(a), kind, n(b)), "principle": "change-since"})
    for a, b, kind in sorted(br - ar):
        out.append({"kind": "relation-gone", "subject": a, "message": "relation disparue %s —%s→ %s" % (n(a), kind, n(b)), "principle": "change-since"})
    bg, ag = before.get("gateways", {}), after.get("gateways", {})
    for h, via in ag.items():
        if h in bg and bg[h] and via and bg[h] != via:
            out.append({"kind": "gateway-changed", "subject": h, "message": "%s : passerelle par défaut %s → %s" % (n(h), bg[h], via), "principle": "change-since"})
    return out
