"""
Détection de colonnes TEXTE utilisées comme liste d'identifiants
(livraison #151, backlog BACKLOG.md #5) -- cas explicitement signalé
par la personne : une relation qui ne se voit PAS dans le type de
colonne (un simple VARCHAR/TEXT), seulement dans son CONTENU (ex. une
colonne "sites" contenant la chaîne "1,2,5"). Invisible à
relation_detector.py (qui ne regarde que les NOMS de colonnes) --
nécessite d'échantillonner les VALEURS réelles.

Fonctions PURES : reçoivent un échantillon de valeurs déjà récupéré
(voir schema_client.py) -- ne font aucun accès réseau ni base,
testables directement.
"""
import re

# "1,2,5" ou "1, 2, 5" -- au moins DEUX nombres séparés par une
# virgule (une valeur seule comme "5" est juste... une valeur, pas une
# liste -- ne doit jamais être signalée comme telle).
_ID_LIST_PATTERN = re.compile(r"^\s*\d+\s*(,\s*\d+\s*)+$")


def looks_like_id_list(value):
    """True si `value` (chaîne) ressemble à une liste d'identifiants
    séparés par des virgules."""
    if not isinstance(value, str):
        return False
    return bool(_ID_LIST_PATTERN.match(value))


def detect_list_like_column(sample_values, min_ratio=0.5, min_samples=3):
    """`sample_values` : liste de valeurs échantillonnées pour UNE
    colonne (peut contenir None/chaîne vide -- valeurs NULL/absentes,
    exclues du calcul). Renvoie un dict {"is_list_like": bool,
    "ratio": float, "sample_size": int} -- jamais un verdict positif
    sur un échantillon trop petit (`min_samples`, défaut 3) : une
    seule valeur qui ressemble à une liste par hasard ne doit pas
    suffire à conclure. `min_ratio` (défaut 50%) : une colonne dont
    SEULEMENT quelques valeurs ressemblent par coïncidence à une liste
    ne doit pas être signalée -- la MAJORITÉ des valeurs non-nulles
    échantillonnées doivent correspondre au motif."""
    non_empty = [v for v in sample_values if v is not None and v != ""]
    sample_size = len(non_empty)
    if sample_size < min_samples:
        return {"is_list_like": False, "ratio": 0.0, "sample_size": sample_size}
    matching = sum(1 for v in non_empty if looks_like_id_list(v))
    ratio = matching / sample_size
    return {"is_list_like": ratio >= min_ratio, "ratio": round(ratio, 3), "sample_size": sample_size}
