# -*- coding: utf-8 -*-
"""Calque du plan d'un site (livraison #973) -- logique pure.

Dessiné dans le hub par-dessus l'image du plan (coordonnées en fractions 0..1 de l'image) :
- formes : polygones fermés {id, type: espace|zone, nom, points: [[x, y], …]} -- un « espace » est une pièce nommée ;
- etiquettes : {id, type: espace|spot|zone|note, texte, x, y} -- un « spot » nomme une borne ou un équipement réseau.
Sert à nommer la pièce d'une borne (#971, déplacements) : borne positionnée sur le plan, ou étiquette « spot » à son nom,
à l'intérieur d'un espace.
"""
import re
import time

TYPES_FORME = ("espace", "zone")
TYPES_ETIQUETTE = ("espace", "spot", "zone", "note")
MAX_FORMES, MAX_ETIQUETTES, MAX_POINTS = 400, 1000, 400


def _frac(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return round(f, 5) if 0 <= f <= 1 else None


def _id(v, i, prefixe):
    s = re.sub(r"[^A-Za-z0-9_-]", "", str(v or ""))[:40]
    return s or "%s%d" % (prefixe, i)


def valider(d):
    """-> (calque, erreur). Les éléments invalides sont refusés avec un message qui les nomme."""
    if not isinstance(d, dict):
        return None, "objet attendu"
    formes, etiquettes = [], []
    for i, f in enumerate(d.get("formes") or []):
        if not isinstance(f, dict):
            return None, "forme %d : objet attendu" % (i + 1)
        t = f.get("type") or "espace"
        if t not in TYPES_FORME:
            return None, "forme %d : type %s inconnu (%s)" % (i + 1, t, ", ".join(TYPES_FORME))
        pts = []
        for p in (f.get("points") or [])[:MAX_POINTS + 1]:
            x, y = (_frac(p[0]), _frac(p[1])) if isinstance(p, (list, tuple)) and len(p) == 2 else (None, None)
            if x is None or y is None:
                return None, "forme %d : point hors du plan (fractions 0..1 attendues)" % (i + 1)
            pts.append([x, y])
        if not 3 <= len(pts) <= MAX_POINTS:
            return None, "forme %d (%s) : 3 à %d points" % (i + 1, f.get("nom") or "sans nom", MAX_POINTS)
        formes.append({"id": _id(f.get("id"), i, "f"), "type": t, "nom": (str(f.get("nom") or "").strip()[:80] or None), "points": pts})
    for i, e in enumerate(d.get("etiquettes") or []):
        if not isinstance(e, dict):
            return None, "étiquette %d : objet attendu" % (i + 1)
        t = e.get("type") or "note"
        if t not in TYPES_ETIQUETTE:
            return None, "étiquette %d : type %s inconnu (%s)" % (i + 1, t, ", ".join(TYPES_ETIQUETTE))
        x, y, txt = _frac(e.get("x")), _frac(e.get("y")), str(e.get("texte") or "").strip()[:120]
        if x is None or y is None or not txt:
            return None, "étiquette %d : texte et position requis" % (i + 1)
        etiquettes.append({"id": _id(e.get("id"), i, "e"), "type": t, "texte": txt, "x": x, "y": y})
    if len(formes) > MAX_FORMES or len(etiquettes) > MAX_ETIQUETTES:
        return None, "calque trop grand (%d formes, %d étiquettes au plus)" % (MAX_FORMES, MAX_ETIQUETTES)
    return {"formes": formes, "etiquettes": etiquettes, "maj": int(time.time()), "par": str(d.get("par") or "")[:80] or None}, None


def dans(x, y, points):
    """Point dans un polygone (règle pair-impair)."""
    dedans = False
    n = len(points)
    for i in range(n):
        x1, y1 = points[i]
        x2, y2 = points[(i + 1) % n]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / ((y2 - y1) or 1e-12) + x1:
            dedans = not dedans
    return dedans


def espace_de(calque, x, y):
    """Nom de l'espace (sinon de la zone) qui contient le point ; le plus petit s'ils s'emboîtent."""
    if x is None or y is None or not calque:
        return None
    aire = lambda pts: abs(sum(pts[i][0] * pts[(i + 1) % len(pts)][1] - pts[(i + 1) % len(pts)][0] * pts[i][1] for i in range(len(pts)))) / 2
    cand = [(0 if f["type"] == "espace" else 1, aire(f["points"]), f["nom"]) for f in calque.get("formes") or []
            if f.get("nom") and dans(x, y, f["points"])]
    return min(cand)[2] if cand else None
