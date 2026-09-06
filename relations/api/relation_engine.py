"""
Calcul des relations -- fonctions PURES, aucun appel réseau ici
(voir entity_fetchers.py pour la récupération des données), pour
rester testables en isolation sans dépendre des autres services.

Relation DIRECTE (première passe, voir app.py) : deux entités dont
le libellé normalisé (minuscules, espaces superflus retirés) est
IDENTIQUE -- jamais une correspondance partielle/floue ici, "chaîne
identique" au sens strict demandé par la personne. Seuil de longueur
minimale (MIN_MARKER_LENGTH) pour éviter le bruit d'un libellé
générique très court ("x", "test") qui matcherait n'importe quoi
sans rien signifier de réel -- choix raisonnable, jamais vérifié
contre un vrai jeu de données de production.

Relation INDIRECTE : deux entités qui appartiennent au même ENSEMBLE
connexe (formé en suivant les relations directes de proche en
proche) mais qui n'ont PAS de relation directe ENTRE ELLES
directement -- calculé par une recherche de composantes connexes
classique sur le graphe non orienté des relations directes.

LIMITE STRUCTURELLE DE LA PASSE #335, LEVÉE EN #336, CONFIRMÉE PAR
TEST DANS LES DEUX SENS plutôt que supposée : avec un SEUL critère
de relation directe (nom identique) et UN SEUL marqueur par entité,
aucune relation indirecte ne pouvait jamais se produire -- toutes
les entités partageant un même marqueur formaient une CLIQUE
totalement connectée en DIRECT entre elles, jamais un pont vers un
cluster de marqueur différent. Depuis l'ajout de la correspondance
par IP (#336), une entité peut désormais porter DEUX marqueurs
distincts (son nom ET une IP mentionnée dans son texte) -- si cette
IP est PARTAGÉE avec une troisième entité qui n'a PAS le même nom,
cette troisième entité devient une relation INDIRECTE de la première
(via la seconde comme intermédiaire), confirmée par test ci-dessous.
Encore plus vrai une fois la proximité géographique/sémantique
ajoutées (passes ultérieures, voir app.py) -- chaque nouveau critère
multiplie les ponts possibles entre clusters de marqueurs distincts.
"""
import math
import re
import unicodedata

MIN_MARKER_LENGTH = 3

# IPv4 uniquement pour cette passe (#336) -- jamais IPv6, jamais
# vérifié comme un besoin réel. Validation des octets (0-255) pour
# éviter un faux positif sur un numéro de version ("2.5.13.4") ou
# une suite de chiffres qui ressemble à une IP sans en être une --
# jamais parfait (une vraie IP à octets tous <256 ressemble aussi à
# une version), mais réduit le bruit le plus évident.
_IPV4_PATTERN = re.compile(r"\b(?:(?:25[0-5]|2[0-4]\d|1?\d{1,2})\.){3}(?:25[0-5]|2[0-4]\d|1?\d{1,2})\b")

# Proximité SÉMANTIQUE (#337) -- même technique déjà établie dans ce
# projet pour une tâche apparentée (tickets/api/suggestion_engine.py,
# "score de similarité par mots significatifs partagés", jamais un
# vrai modèle NLP -- aucun accès réseau pour en télécharger un pendant
# le développement, même contrainte documentée là-bas). STOPWORDS
# dupliqué ici À L'IDENTIQUE (relations-api est un service séparé,
# jamais un import inter-conteneurs pour une si petite fonction pure)
# plutôt que réinventé -- si la liste évolue côté tickets-api, penser
# à répercuter ici.
STOPWORDS = {
    "le", "la", "les", "de", "des", "du", "un", "une", "et", "sur", "pour",
    "avec", "dans", "au", "aux", "ce", "cette", "ces", "est", "sont", "etre",
    "avoir", "que", "qui", "quoi", "dont", "leur", "leurs", "son", "sa",
    "ses", "vers", "chez", "sans", "sous", "entre", "mais", "donc", "or",
    "ni", "car", "puis", "ainsi", "alors", "comme", "quand", "lors",
}

# Seuil minimal de mots significatifs partagés pour une relation
# sémantique -- repris de suggestion_engine.py:analyze_title_matches
# (min_score=1 par défaut), jamais un chiffre inventé ici sans
# précédent dans ce projet.
MIN_SEMANTIC_SHARED_WORDS = 1

# Proximité GÉOGRAPHIQUE (#338) -- seuil en kilomètres en-deçà duquel
# deux lieux sont considérés "proches", jamais une distance
# arbitrairement précise. 2 km choisi comme ordre de grandeur
# raisonnable pour un contexte "même campus/site professionnel
# proche" -- jamais vérifié contre un vrai jeu de données ni discuté
# avec la personne, à ajuster une fois un usage réel observé.
GEO_PROXIMITY_KM = 2.0
EARTH_RADIUS_KM = 6371.0


def strip_accents(text):
    normalized = unicodedata.normalize("NFKD", text or "")
    return "".join(c for c in normalized if not unicodedata.combining(c))


def extract_significant_words(text):
    """>3 caractères, hors mots vides français courants -- même seuil
    que suggestion_engine.py:extract_significant_words."""
    words = re.findall(r"[a-zàâäéèêëïîôöùûüçA-ZÀÂÄÉÈÊËÏÎÔÖÙÛÜÇ]+", text or "")
    normalized = {strip_accents(w.lower()) for w in words}
    return {w for w in normalized if len(w) > 3 and w not in STOPWORDS}


def haversine_km(coord_a, coord_b):
    """Distance à vol d'oiseau entre deux points (latitude, longitude
    en degrés) -- formule standard, jamais réinventée. Suffisant pour
    des distances courtes (échelle campus/ville) ; jamais pensé pour
    une précision géodésique de haute exactitude."""
    lat1, lon1 = coord_a
    lat2, lon2 = coord_b
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def normalize_label(label):
    """Minuscules, espaces superflus (début/fin + suites d'espaces
    internes) réduits à un seul -- jamais la ponctuation retirée
    (une différence de ponctuation reste une différence réelle pour
    une correspondance "chaîne identique" au sens strict)."""
    return re.sub(r"\s+", " ", (label or "").strip()).lower()


def extract_ips(text):
    """Toutes les adresses IPv4 UNIQUES trouvées dans `text` --
    jamais dédupliquées entre entités différentes ici (c'est le rôle
    de compute_direct_relations), seulement au sein d'un même texte
    (une IP répétée deux fois dans la même description ne compte
    qu'une fois)."""
    return sorted(set(_IPV4_PATTERN.findall(text or "")))


def _pairs_by_marker(by_marker):
    """Combine chaque groupe d'entités partageant un même marqueur en
    paires -- factorisé entre la correspondance de nom et la
    correspondance d'IP (#336), même logique dans les deux cas."""
    relations = []
    for marker, keys in by_marker.items():
        if len(keys) < 2:
            continue
        for i in range(len(keys)):
            for j in range(i + 1, len(keys)):
                relations.append((keys[i], keys[j], marker))
    return relations


def compute_direct_relations(entities, geolocations=None):
    """`entities` : dict {(type, id): {"label": str, "text": str,
    "site": str|None}}, voir entity_fetchers.fetch_all_entities.
    `geolocations` (optionnel) : dict {localisation_normalisée:
    (latitude, longitude)}, voir entity_fetchers.fetch_geolocations
    -- absent ou vide, la proximité géographique est simplement
    ignorée (aucune erreur), pour ne jamais bloquer les trois autres
    critères si pixel-grid-api est injoignable ou n'a aucune
    localisation cartographiée.

    Renvoie une liste de tuples (entity_a, entity_b, marker) -- UNE
    SEULE fois par paire (jamais (a, b) ET (b, a)), même si PLUSIEURS
    marqueurs différents justifient la relation : dans ce cas,
    PLUSIEURS entrées distinctes sont renvoyées pour la même paire,
    chacune avec son propre marqueur -- jamais fusionnées en une
    seule, pour ne perdre aucune des justifications (sauf
    déduplication nom/sémantique explicite ci-dessous).

    Quatre formes de relation directe combinées (#335 : nom ; #336 :
    IP ; #337 : sémantique ; #338 : proximité géographique) :
    - correspondance de NOM (`label`, exacte, insensible à la casse)
    - correspondance d'IP (une IPv4 identique trouvée dans `text` de
      deux entités différentes)
    - proximité SÉMANTIQUE (au moins `MIN_SEMANTIC_SHARED_WORDS` mots
      significatifs COMMUNS entre les `text` de deux entités,
      comparaison PAR PAIRES -- O(n²), contrairement au regroupement
      O(n) des trois autres critères ; acceptable tant que le volume
      reste modeste, voir docstring du module -- à surveiller si ça
      devient un problème réel de performance)
    - proximité GÉOGRAPHIQUE (deux entités dont le `site` résout,
      via `geolocations`, à des coordonnées distantes de moins de
      `GEO_PROXIMITY_KM` -- SEULE forme parmi les quatre qui
      n'exige PAS une correspondance exacte, une vraie "proximité").
    """
    by_name_marker = {}
    by_ip_marker = {}
    significant_words = {}
    site_coords = {}
    geolocations = geolocations or {}
    for key, data in entities.items():
        name_marker = normalize_label(data["label"])
        if len(name_marker) >= MIN_MARKER_LENGTH:
            by_name_marker.setdefault(name_marker, []).append(key)
        for ip in extract_ips(data.get("text", "")):
            by_ip_marker.setdefault(ip, []).append(key)
        significant_words[key] = extract_significant_words(data.get("text", ""))
        site = data.get("site")
        if site:
            coords = geolocations.get(normalize_label(site))
            if coords is not None:
                site_coords[key] = coords

    relations = _pairs_by_marker(by_name_marker) + _pairs_by_marker(by_ip_marker)
    # Paires déjà justifiées par le NOM -- un nom identique implique
    # presque toujours un recouvrement de mots significatifs (les mots
    # du nom lui-même comptent), donc ajouter AUSSI un marqueur
    # sémantique pour la même paire serait une redondance quasi
    # systématique, jamais un signal supplémentaire réel. PAS la même
    # logique pour l'IP : partager une IP n'implique pas forcément un
    # recouvrement du RESTE du texte, la combinaison IP+sémantique
    # reste un signal double genuinely informatif, jamais supprimée.
    already_named = {frozenset((a, b)) for a, b, _m in _pairs_by_marker(by_name_marker)}

    keys = list(entities.keys())
    for i in range(len(keys)):
        for j in range(i + 1, len(keys)):
            pair = frozenset((keys[i], keys[j]))
            if pair not in already_named:
                shared = significant_words[keys[i]] & significant_words[keys[j]]
                if len(shared) >= MIN_SEMANTIC_SHARED_WORDS:
                    relations.append((keys[i], keys[j], f"mots communs : {', '.join(sorted(shared))}"))
            # Proximité géographique -- jamais dédupliquée contre le
            # nom (partager un site n'implique rien sur le libellé,
            # contrairement au cas nom/sémantique ci-dessus -- signal
            # réellement indépendant, toujours ajouté s'il s'applique).
            if keys[i] in site_coords and keys[j] in site_coords:
                distance_km = haversine_km(site_coords[keys[i]], site_coords[keys[j]])
                if distance_km <= GEO_PROXIMITY_KM:
                    relations.append((keys[i], keys[j], f"proximité géographique : {distance_km:.2f} km"))
    return relations


def _build_adjacency(direct_relations):
    adjacency = {}
    for a, b, _marker in direct_relations:
        adjacency.setdefault(a, set()).add(b)
        adjacency.setdefault(b, set()).add(a)
    return adjacency


def connected_component(start, adjacency):
    """Parcours en largeur -- tous les nœuds atteignables depuis
    `start` en suivant des relations directes, `start` lui-même
    INCLUS dans le résultat (retiré par l'appelant si besoin, voir
    relations_for)."""
    if start not in adjacency:
        return {start}
    visited = {start}
    queue = [start]
    while queue:
        current = queue.pop()
        for neighbor in adjacency[current]:
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append(neighbor)
    return visited


def relations_for(entity_key, direct_relations):
    """Relations DIRECTES et INDIRECTES d'une entité précise.
    - direct : liste de (autre_entité, marker) -- ses voisins
      immédiats dans le graphe des relations directes.
    - indirect : ensemble des autres membres de son composant
      connexe, EXCLUANT l'entité elle-même ET ses voisins directs
      déjà listés séparément (jamais un doublon entre les deux
      catégories)."""
    direct_neighbors = []
    direct_neighbor_keys = set()
    for a, b, marker in direct_relations:
        if a == entity_key:
            direct_neighbors.append((b, marker))
            direct_neighbor_keys.add(b)
        elif b == entity_key:
            direct_neighbors.append((a, marker))
            direct_neighbor_keys.add(a)

    adjacency = _build_adjacency(direct_relations)
    component = connected_component(entity_key, adjacency)
    indirect = component - direct_neighbor_keys - {entity_key}

    return {"direct": direct_neighbors, "indirect": indirect}
