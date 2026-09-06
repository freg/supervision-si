"""
Validation d'une relation PROPOSÉE contre les VRAIES données
(livraison #241, backlog #5 -- demandé explicitement : "à partir du
schéma et des données (pour conforter la relation)... relier un
champ numérique ou set avec l'id d'une autre table"). Complète
`relation_detector.py` (ne regarde QUE les noms de colonnes) et
`list_detector.py` (ne regarde QUE le MOTIF des valeurs, jamais si
elles correspondent à de VRAIES lignes existantes) -- ici, une
VRAIE requête contre la base confirme (ou infirme) qu'une relation
candidate correspond effectivement à des données réelles.

**Approche VOLONTAIREMENT PORTABLE** (fonctionne MySQL/PostgreSQL/
SQLite SANS code spécifique par moteur) : plutôt que d'éclater une
colonne-liste ("1,2,5") EN SQL (fonctions différentes par moteur --
`SUBSTRING_INDEX` en MySQL, `STRING_TO_ARRAY` en PostgreSQL, rien de
natif en SQLite) ou de CASTer les types pour comparer (`CAST(...AS
CHAR)` MySQL vs `::text` PostgreSQL vs inutile en SQLite dynamiquement
typé), TOUT le travail d'éclatement et de comparaison se fait EN
PYTHON, après deux lectures SQL simples (`SELECT DISTINCT ... LIMIT
N`, syntaxe universelle) -- jamais une requête générée différemment
par moteur.
"""
import re

_SAFE_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

# Cap sur la table CIBLE (livraison #241) -- une relation valide vers
# une table de PLUSIEURS MILLIONS de lignes resterait un cas limite
# rare pour une colonne-id/clé primaire, mais mieux vaut un résultat
# EXPLICITEMENT signalé comme potentiellement incomplet
# (`target_capped`) qu'un chargement qui bloque le service.
MAX_TARGET_VALUES = 100_000


def _validate_identifier(name, kind):
    """Lève ValueError si `name` n'est pas un identifiant SQL simple
    -- jamais interpolé dans une requête sans cette vérification
    (les VALEURS, elles, ne sont JAMAIS interpolées ici -- comparées
    entièrement en Python après lecture, voir docstring du module)."""
    if not _SAFE_IDENTIFIER.match(name):
        raise ValueError(f"{kind} '{name}' contient des caractères non supportés pour cette validation")


def extract_candidate_ids(raw_value, relation_type):
    """Renvoie la liste des identifiants CANDIDATS portés par une
    valeur brute -- une seule valeur pour une relation classique
    ("42" -> ["42"]), plusieurs pour une colonne-liste ("1, 2, 5" ->
    ["1", "2", "5"]). Toujours normalisé en chaîne (voir
    docstring du module -- comparaison texte des deux côtés, jamais
    une hypothèse sur le type SQL réel de la colonne)."""
    if raw_value is None:
        return []
    text = str(raw_value).strip()
    if not text:
        return []
    if relation_type == "list":
        return [part.strip() for part in text.split(",") if part.strip()]
    return [text]


def validate_relation(executor, from_table, from_column, to_table, to_column,
                       relation_type="foreign_key", sample_size=200):
    """`executor` : fonction injectée `sql -> {"columns": [...], "rows": [...], "row_count": N}`
    (voir `app.py` -- en usage réel, un appel à
    `schema_client.execute_sql` déjà lié à une connexion/base
    précises ; jamais un vrai appel HTTP dans un test unitaire).

    Renvoie {checked_count, matched_count, coverage_ratio,
    sample_mismatches, target_capped} -- `coverage_ratio` = `None` si
    `checked_count == 0` (rien à valider -- colonne entièrement
    vide/NULL dans l'échantillon -- jamais une division par zéro ni
    un taux de 100% trompeur sur un échantillon vide).
    `sample_mismatches` : jusqu'à 10 valeurs candidates qui n'ont
    PAS trouvé de correspondance -- utile pour repérer une fausse
    piste (ex. une colonne qui ressemble à une FK mais contient en
    réalité un code métier, pas un id)."""
    _validate_identifier(from_table, "nom de table")
    _validate_identifier(from_column, "nom de colonne")
    _validate_identifier(to_table, "nom de table")
    _validate_identifier(to_column, "nom de colonne")

    sample_sql = f"SELECT DISTINCT {from_column} FROM {from_table} WHERE {from_column} IS NOT NULL LIMIT {int(sample_size)}"
    sample_result = executor(sample_sql)
    raw_values = [row[0] for row in sample_result.get("rows", [])]

    candidate_ids = set()
    for raw in raw_values:
        candidate_ids.update(extract_candidate_ids(raw, relation_type))

    if not candidate_ids:
        return {"checked_count": 0, "matched_count": 0, "coverage_ratio": None, "sample_mismatches": [], "target_capped": False}

    target_sql = f"SELECT DISTINCT {to_column} FROM {to_table} WHERE {to_column} IS NOT NULL LIMIT {MAX_TARGET_VALUES + 1}"
    target_result = executor(target_sql)
    target_rows = target_result.get("rows", [])
    target_capped = len(target_rows) > MAX_TARGET_VALUES
    target_values = {str(row[0]).strip() for row in target_rows[:MAX_TARGET_VALUES]}

    matched = candidate_ids & target_values
    mismatches = sorted(candidate_ids - target_values)[:10]

    return {
        "checked_count": len(candidate_ids),
        "matched_count": len(matched),
        "coverage_ratio": round(len(matched) / len(candidate_ids), 4),
        "sample_mismatches": mismatches,
        "target_capped": target_capped,
    }
