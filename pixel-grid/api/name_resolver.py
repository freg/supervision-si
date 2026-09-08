"""Résolution d'une localisation à partir d'un NOM d'équipement ou d'un
nom de SITE (livraison #426) -- logique pure, sans Flask ni base, testée par
test_name_resolver.py.

Le besoin : « UPS-Arobase-5 » doit se retrouver sur la position du site
« Arobase 5 » (ou « @5 », ou « Parc/Batiment 5 » si c'est ainsi que la
table geolocations le nomme) et non sur la position de repli. Une référence
orthographiquement OU sémantiquement proche vaut position, automatiquement ;
la correspondance est conservée (table location_matches, voir app.py) et
peut être validée, rejetée ou remplacée par la personne.

Trois mécanismes, dans l'ordre :
  1. alias déclarés (table location_aliases : « @5 » -> « Parc/Batiment 5 ») ;
  2. équivalences sémantiques intégrées (arobase <-> @, tp <-> batiment,
     bat <-> batiment, st <-> saint, cinq <-> 5, 05 -> 5…) ;
  3. proximité orthographique (difflib) entre les jetons du nom -- débarrassé
     des jetons de TYPE (ups, sw, srv, ap…) -- et ceux de chaque localisation
     (chemin complet et dernier segment), avec contrainte sur les NOMBRES : un
     « 5 » côté site exige un « 5 » côté nom, sinon Arobase-5 collerait à
     Arobase-3.
"""

import difflib
import re
import unicodedata

# Score à partir duquel la correspondance est appliquée d'office (statut
# « auto ») ; entre SUGGEST et AUTO elle est proposée (« suggested ») sans
# être utilisée comme position.
AUTO_THRESHOLD = 0.75
SUGGEST_THRESHOLD = 0.5

# Jetons de TYPE d'équipement, ignorés dans le nom (jamais dans le site).
TYPE_TOKENS = {
    "ups", "onduleur", "sw", "switch", "rtr", "router", "routeur", "srv", "server", "serveur",
    "ap", "wifi", "borne", "pc", "poste", "imp", "printer", "imprimante", "nas", "fw", "firewall",
    "pare", "feu", "cam", "camera", "sonde", "probe", "agent", "host", "hote", "vm", "esx", "esxi",
    "lan", "wan", "core", "dist", "acc", "acces", "access", "san", "lb", "proxy", "dns", "dhcp",
    "gw", "gateway", "passerelle", "modem", "box", "ipbx", "pabx", "tel", "phone", "visio",
}

# Équivalences sémantiques : chaque jeton est ramené à une forme canonique.
SEMANTIC = {
    "@": "arobase", "at": "arobase", "arobas": "arobase", "arrobase": "arobase", "arobase": "arobase",
    "tp": "batiment", "batiment": "batiment", "batiment": "batiment", "telep": "batiment",
    "techno": "parc", "parc": "parc", "technopôle": "parc",
    "bat": "batiment", "bât": "batiment", "batiment": "batiment", "bâtiment": "batiment", "bldg": "batiment", "building": "batiment",
    "st": "saint", "saint": "saint", "ste": "sainte", "sainte": "sainte",
    "etg": "etage", "etage": "etage", "étage": "etage", "floor": "etage", "niv": "etage", "niveau": "etage",
    "rdc": "rdc", "rez": "rdc",
    "ag": "agence", "agence": "agence", "site": "site", "salle": "salle", "local": "local",
    "dc": "datacenter", "datacenter": "datacenter", "dsi": "dsi", "siege": "siege", "siège": "siege", "hq": "siege",
    "zero": "0", "un": "1", "une": "1", "deux": "2", "trois": "3", "quatre": "4", "cinq": "5", "six": "6",
    "sept": "7", "huit": "8", "neuf": "9", "dix": "10",
}

# Mots génériques d'une localisation (« Agence Nantes ») : ils pèsent peu,
# c'est « Nantes » qui identifie le lieu.
GENERIC_TOKENS = {"agence", "site", "salle", "local", "secteur", "zone", "bureau", "batiment", "etage", "datacenter"}
GENERIC_WEIGHT = 0.3

_SPLIT = re.compile(r"[^a-z0-9@]+")
_PREFIX_LETTER = re.compile(r"^(bat|etg|niv|bur|salle)([a-z])$")
_NUM = re.compile(r"^[0-9]+$")
_ALNUM_SPLIT = re.compile(r"([0-9]+)")


def strip_accents(s):
    return "".join(c for c in unicodedata.normalize("NFD", s or "") if unicodedata.category(c) != "Mn")


def tokens(text, drop_types=False):
    """Jetons canoniques d'un libellé : minuscules sans accents, « @ »
    isolé, lettres et chiffres collés séparés (« arobase5 » -> arobase, 5),
    nombres sans zéros de tête, équivalences sémantiques appliquées, jetons
    de type retirés si demandé. L'ordre est conservé."""
    s = strip_accents(str(text or "")).lower().replace("@", " @ ")
    out = []
    for raw in _SPLIT.split(s):
        if not raw:
            continue
        for part in _ALNUM_SPLIT.split(raw):
            if not part:
                continue
            if _NUM.match(part):
                part = part.lstrip("0") or "0"
            m = _PREFIX_LETTER.match(part)
            parts = [m.group(1), m.group(2)] if m and part not in SEMANTIC else [part]
            for part in parts:
                part = SEMANTIC.get(part, part)
                if drop_types and part in TYPE_TOKENS:
                    continue
                out.append(part)
    return out


def _numbers(toks):
    return {t for t in toks if _NUM.match(t)}


def _words(toks):
    return [t for t in toks if not _NUM.match(t)]


def _sim(a, b):
    if a == b:
        return 1.0
    if len(a) >= 4 and len(b) >= 4 and (a.startswith(b) or b.startswith(a)):
        return 0.9
    return difflib.SequenceMatcher(None, a, b).ratio()


def score_tokens(name_toks, loc_toks):
    """Score [0, 1] de « loc_toks (la localisation) est désignée par
    name_toks (le nom) ». Chaque mot de la localisation cherche son meilleur
    homologue dans le nom ; les nombres doivent coïncider."""
    if not loc_toks or not name_toks:
        return 0.0
    loc_words, name_words = _words(loc_toks), _words(name_toks)
    loc_nums, name_nums = _numbers(loc_toks), _numbers(name_toks)
    if loc_words:
        joined_name = "".join(name_words)
        weighted, total = 0.0, 0.0
        for lw in loc_words:
            w = GENERIC_WEIGHT if lw in GENERIC_TOKENS else 1.0
            best = max((_sim(lw, nw) for nw in name_words), default=0.0)
            weighted += w * (best if best >= 0.6 else 0.0)  # un mot trop éloigné ne compte pas du tout
            total += w
        words_score = weighted / total if total else 0.0
        # mots de la localisation collés (« saintmalo ») contre le nom collé
        # (« stmalo ») ou l'un de ses jetons : rattrape les abréviations
        specific = "".join(lw for lw in loc_words if lw not in GENERIC_TOKENS)
        if len(specific) >= 5 and name_words:
            glued = max(_sim(specific, joined_name), max(_sim(specific, nw) for nw in name_words))
            if glued >= 0.75:
                words_score = max(words_score, glued * 0.95)
    else:
        words_score = 1.0 if loc_nums and loc_nums <= name_nums else 0.0
    if loc_nums:
        if not name_nums:
            num_factor = 0.5          # « Arobase 5 » pour « UPS-Arobase » : plausible, pas certain
        elif loc_nums <= name_nums:
            num_factor = 1.0
        elif loc_nums & name_nums:
            num_factor = 0.8
        else:
            num_factor = 0.15         # Arobase-5 ne désigne pas Arobase-3
    else:
        num_factor = 1.0
    # jetons du nom non expliqués par la localisation : légère pénalité
    # (un nom qui ne contient QUE le site est plus sûr qu'un nom bavard)
    covered = sum(1 for nw in name_words if any(_sim(nw, lw) >= 0.6 for lw in loc_words))
    extra = max(0, len(name_words) - covered)
    extra_factor = 1.0 - min(0.2, 0.05 * extra)
    return round(words_score * num_factor * extra_factor, 3)


def _loc_variants(localisation):
    """Chemin complet, dernier segment, et segments intermédiaires."""
    parts = [p for p in re.split(r"\s*/\s*", str(localisation or "")) if p]
    variants = [localisation]
    if len(parts) > 1:
        variants.append(parts[-1])
    return variants


def candidates(name, localisations, aliases=None, site=None, limit=5):
    """Candidats triés : [{localisation, score, method, via}].

    `localisations` : itérable de chaînes (clés de la table geolocations,
    « __default__ » exclu) ; `aliases` : {alias: localisation} ; `site` :
    nom de site déclaré sur l'équipement (essayé EN PREMIER, il est plus
    fiable que le nom)."""
    aliases = aliases or {}
    locs = [l for l in localisations if l and l != "__default__"]
    found = {}

    def offer(loc, score, method, via):
        if score <= 0:
            return
        cur = found.get(loc)
        if cur is None or score > cur["score"]:
            found[loc] = {"localisation": loc, "score": score, "method": method, "via": via}

    for via, text in (("site", site), ("nom", name)):
        if not text:
            continue
        drop = via == "nom"
        ntoks = tokens(text, drop_types=drop)
        if not ntoks:
            continue
        joined = "".join(ntoks)
        # 1. alias déclarés (exacts, puis jetons)
        for alias, loc in aliases.items():
            atoks = tokens(alias)
            if not atoks or loc not in locs:
                continue
            if tokens(text) == atoks or ntoks == atoks:
                offer(loc, 1.0, "alias", via)
            elif "".join(atoks) and "".join(atoks) in joined:
                offer(loc, 0.97, "alias", via)
            else:
                offer(loc, round(score_tokens(ntoks, atoks) * 0.97, 3), "alias", via)
        # 2 + 3. équivalences sémantiques (déjà dans tokens) + orthographe
        for loc in locs:
            for variant in _loc_variants(loc):
                ltoks = tokens(variant)
                if not ltoks:
                    continue
                if ltoks == ntoks:
                    offer(loc, 1.0, "exact", via)
                elif "".join(ltoks) in joined and _numbers(ltoks) <= _numbers(ntoks):
                    offer(loc, 0.95 if _numbers(ltoks) or len("".join(ltoks)) >= 5 else 0.8, "contenu", via)
                else:
                    offer(loc, score_tokens(ntoks, ltoks), "proche", via)
    # à score égal : le site déclaré prime sur le nom, un alias déclaré par
    # la personne prime sur une correspondance calculée
    out = sorted(found.values(), key=lambda c: (-c["score"], 0 if c["via"] == "site" else 1, 0 if c["method"] == "alias" else 1, c["localisation"]))
    return out[:limit]


def resolve(name, localisations, aliases=None, site=None):
    """Meilleur candidat + statut proposé : « auto » (>= AUTO_THRESHOLD),
    « suggested » (>= SUGGEST_THRESHOLD) ou None (rien de crédible)."""
    cands = candidates(name, localisations, aliases=aliases, site=site)
    if not cands:
        return None, []
    best = cands[0]
    if best["score"] >= AUTO_THRESHOLD:
        status = "auto"
    elif best["score"] >= SUGGEST_THRESHOLD:
        status = "suggested"
    else:
        return None, cands
    return {**best, "status": status}, cands
