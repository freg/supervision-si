# -*- coding: utf-8 -*-
"""Catalogue de positions (livraison #429, backlog 67) -- logique PURE :
interprétation géographique la plus précise parmi des références, et
estimation en % de justesse. Aucune base, aucun réseau ; testée par
test_catalog.py.

Une POSITION = un lieu nommé du SI (aujourd'hui : une localisation de la
table geolocations de pixel-grid, demain n'importe quel objet à placer).
Ses RÉFÉRENCES = ce que les référentiels en disent : coordonnées déjà
saisies, adresse BAN / Géoplateforme, centroïde de commune, objet OSM
(base locale osm2pgsql ou Nominatim), point d'intérêt. L'INTERPRÉTATION =
la référence la plus précise et la plus concordante ; la JUSTESSE = un
score 0-100 qui combine la précision de la référence retenue, le score du
géocodeur, l'accord entre références (distance) et une décision humaine.
"""
import math
import re
import unicodedata

# Précision d'une référence, de la plus fine à la plus grossière -- la
# valeur est le rayon d'incertitude typique en mètres.
PRECISION_RADIUS_M = {
    "manual": 5, "validated": 5, "housenumber": 15, "poi": 30, "osm": 40, "street": 150,
    "site": 200, "locality": 800, "municipality": 3000, "commune": 3000, "postcode": 4000,
    "stored": 60, "default": 100000, "unknown": 50000,
}
PRECISION_ORDER = ["manual", "validated", "housenumber", "poi", "osm", "street", "site", "locality", "municipality", "commune", "postcode", "stored", "unknown", "default"]
PRECISION_LABELS = {
    "manual": "corrigée à la main", "validated": "validée", "housenumber": "adresse (numéro)", "poi": "point d'intérêt",
    "osm": "objet OpenStreetMap", "street": "rue", "site": "site", "locality": "lieu-dit", "municipality": "commune",
    "commune": "commune (code postal)", "postcode": "code postal", "stored": "coordonnées saisies", "unknown": "inconnue", "default": "position de repli",
}
_POSTAL = re.compile(r"(?<!\d)(\d{5})(?!\d)")


def strip_accents(s):
    return "".join(c for c in unicodedata.normalize("NFD", s or "") if unicodedata.category(c) != "Mn")


def normalize(s):
    return re.sub(r"\s+", " ", strip_accents(str(s or "")).lower().replace("/", " ").replace("_", " ").replace("-", " ")).strip()


def leaf(label):
    """Dernier segment d'un chemin « Parc/Batiment 5 » -> « Batiment 5 »."""
    parts = [p.strip() for p in str(label or "").split("/") if p.strip()]
    return parts[-1] if parts else str(label or "")


def postal_code(label):
    m = _POSTAL.search(str(label or ""))
    return m.group(1) if m else None


def haversine_m(lat1, lon1, lat2, lon2):
    if None in (lat1, lon1, lat2, lon2):
        return None
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def ban_precision(feature_type):
    return {"housenumber": "housenumber", "street": "street", "locality": "locality", "municipality": "municipality", "poi": "poi"}.get(feature_type, "unknown")


def interpret(refs, decision=None):
    """`refs` : [{source, precision, lat, lon, score (0-1, optionnel), label}]
    `decision` : {status: validated|corrected, lat, lon} ou None.

    Renvoie {best, lat, lon, precision, confidence (0-100), agreement,
    reasons: [...]}. Une décision humaine l'emporte toujours (justesse
    100 pour « corrected », 95 pour « validated »)."""
    reasons = []
    usable = [r for r in refs or [] if r.get("lat") is not None and r.get("lon") is not None]
    if decision and decision.get("status") in ("validated", "corrected") and decision.get("lat") is not None:
        conf = 100 if decision["status"] == "corrected" else 95
        return {"best": {"source": "human", "precision": "manual" if decision["status"] == "corrected" else "validated", "lat": decision["lat"], "lon": decision["lon"], "label": "décision humaine"},
                "lat": decision["lat"], "lon": decision["lon"], "precision": "manual" if decision["status"] == "corrected" else "validated",
                "confidence": conf, "agreement": _agreement(decision["lat"], decision["lon"], usable), "reasons": ["décision humaine (%s)" % decision["status"]]}
    if not usable:
        return {"best": None, "lat": None, "lon": None, "precision": "unknown", "confidence": 0, "agreement": [], "reasons": ["aucune référence géographique"]}

    def rank(r):
        return (PRECISION_ORDER.index(r.get("precision") if r.get("precision") in PRECISION_ORDER else "unknown"), -(r.get("score") or 0))

    # La référence la plus précise l'emporte... SAUF si elle contredit
    # (> 10 km) des coordonnées saisies par une personne sans être sûre
    # d'elle (score < 0,8) : un géocodage approximatif ne déplace pas un
    # lieu connu à l'autre bout du pays -- il est listé, pas retenu.
    ranked = sorted(usable, key=rank)
    stored = [r for r in usable if r.get("precision") == "stored"]
    skipped = []
    best = None
    for cand in ranked:
        if stored and cand.get("precision") != "stored" and (cand.get("score") is None or float(cand.get("score")) < 0.8):
            d = min(haversine_m(cand["lat"], cand["lon"], s["lat"], s["lon"]) for s in stored)
            if d is not None and d > 10000:
                skipped.append((cand, d))
                continue
        best = cand
        break
    if best is None:
        best = ranked[0]
    for cand, d in skipped:
        reasons.append("%s (%s) écartée : à %.0f km des coordonnées saisies avec un score faible" % (cand.get("source"), PRECISION_LABELS.get(cand.get("precision"), cand.get("precision")), d / 1000))
    agreement = _agreement(best["lat"], best["lon"], [r for r in usable if r is not best])
    # base : précision de la référence retenue
    radius = PRECISION_RADIUS_M.get(best.get("precision"), 50000)
    base = {"manual": 100, "validated": 95, "housenumber": 85, "poi": 80, "osm": 75, "street": 65, "site": 65, "locality": 50,
            "municipality": 40, "commune": 40, "postcode": 30, "stored": 60, "unknown": 20, "default": 5}.get(best.get("precision"), 20)
    reasons.insert(0, "référence retenue : %s (%s)" % (best.get("source"), PRECISION_LABELS.get(best.get("precision"), best.get("precision"))))
    # score du géocodeur, s'il en donne un
    score = best.get("score")
    if score is not None:
        base = base * (0.6 + 0.4 * max(0.0, min(1.0, float(score))))
        reasons.append("score du géocodeur %.2f" % float(score))
    # accord des autres références : chacune à moins de 3 rayons confirme, au-delà de 10 km contredit
    confirms = [a for a in agreement if a["distance_m"] is not None and a["distance_m"] <= 3 * max(radius, PRECISION_RADIUS_M.get(a["precision"], 50000))]
    contradicts = [a for a in agreement if a["distance_m"] is not None and a["distance_m"] > 10000]
    if confirms:
        base = min(100, base + 8 * len(confirms))
        reasons.append("%d référence(s) concordante(s) : %s" % (len(confirms), ", ".join(a["source"] for a in confirms)))
    if contradicts:
        base = base * (0.6 ** len(contradicts))
        reasons.append("%d référence(s) contradictoire(s) à plus de 10 km : %s" % (len(contradicts), ", ".join("%s (%.0f km)" % (a["source"], a["distance_m"] / 1000) for a in contradicts)))
    if best.get("precision") == "stored" and not confirms:
        reasons.append("coordonnées saisies sans référence indépendante")
    return {"best": best, "lat": best["lat"], "lon": best["lon"], "precision": best.get("precision"), "confidence": int(round(max(0, min(100, base)))),
            "agreement": agreement, "reasons": reasons}


def _agreement(lat, lon, others):
    out = []
    for r in others:
        out.append({"source": r.get("source"), "precision": r.get("precision"), "label": r.get("label"),
                    "distance_m": haversine_m(lat, lon, r.get("lat"), r.get("lon"))})
    return sorted(out, key=lambda a: (a["distance_m"] is None, a["distance_m"] or 0))


def commune_query(label):
    """Ce qu'on demande au référentiel des communes : code postal si le
    libellé en contient un, sinon rien (une commune ne se devine pas)."""
    return postal_code(label)


def geocode_query(label):
    """Requête envoyée au géocodeur : dernier segment, sans le code postal
    ni les séparateurs techniques, gardé tel quel sinon (un nom de site
    reste un nom de site)."""
    q = leaf(label)
    q = _POSTAL.sub(" ", q)
    q = re.sub(r"[_\-]+", " ", q)
    return re.sub(r"\s+", " ", q).strip()
