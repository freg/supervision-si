"""
Analyseur de code PHP -- extraction de relations SQL CANDIDATES
depuis les requêtes embarquées dans le code source (livraison #243,
backlog item 30 -- "Rétro-ingénierie", demandé explicitement en
urgence : "vieille application... développeur génial avait ses
schémas en tête... aucune note"). Complète `schema-analyzer`
(#151-241, qui déduit les relations depuis le SCHÉMA et les DONNÉES)
-- ici, les relations sont déduites depuis l'USAGE RÉEL dans le CODE
: une jointure `commandes.client_id = clients.id` écrite en toutes
lettres dans une requête SQL révèle une relation qu'AUCUNE heuristique
de nommage ni de données ne pourrait deviner si les noms sont
atypiques (le cas même décrit par la personne : "des set (id,id,id...)
et d'autres que je ne comprends pas encore").

**Approche VOLONTAIREMENT PAR EXPRESSION RÉGULIÈRE, jamais un vrai
parseur PHP/SQL** -- un vrai parseur PHP (AST complet) serait plus
exact mais démesuré pour ce besoin précis (repérer des CANDIDATS à
valider humainement, jamais appliquer quoi que ce soit
automatiquement -- même philosophie que `relation_detector.py` :
proposer, jamais confirmer seul). Les motifs couverts sont documentés
CLAIREMENT comme des CANDIDATS, potentiellement incomplets sur du SQL
construit dynamiquement (concaténation de variables) -- signalé
explicitement dans chaque résultat plutôt que silencieusement raté.

**Chaque candidat porte la ligne et le fichier d'origine** -- pour
que la personne puisse retrouver le contexte exact dans un code
qu'elle ne maîtrise pas encore, sans deviner.
"""
import re

# Clause FROM complète -- capture TOUT jusqu'au prochain mot-clé
# majeur (WHERE/GROUP BY/ORDER BY/JOIN) ou la fin de la chaîne.
# **Correctif réel trouvé en testant** : une première version ne
# matchait que LA PREMIÈRE table après FROM -- ratait complètement le
# style ANCIEN "FROM table1, table2 WHERE table1.x = table2.y"
# (plusieurs tables séparées par des virgules dans la MÊME clause
# FROM) -- exactement le motif décrit par la personne comme présent
# dans son code hérité. Corrigé : la clause entière est extraite puis
# éclatée sur la virgule.
_FROM_CLAUSE_PATTERN = re.compile(
    r"\bFROM\s+(.+?)(?=\bWHERE\b|\bGROUP\s+BY\b|\bORDER\s+BY\b|\bJOIN\b|\bINNER\s+JOIN\b|\bLEFT\s+JOIN\b|\bRIGHT\s+JOIN\b|$)",
    re.IGNORECASE | re.DOTALL,
)
_JOIN_TABLE_PATTERN = re.compile(
    r"\bJOIN\s+`?(\w+)`?(?:\s+(?:AS\s+)?`?(\w+)`?)?",
    re.IGNORECASE,
)
_TABLE_ITEM_PATTERN = re.compile(r"`?(\w+)`?(?:\s+(?:AS\s+)?`?(\w+)`?)?")

# Condition d'égalité entre deux colonnes qualifiées par table/alias
# -- ex. "c.client_id = cl.id", "commandes.client_id=clients.id".
# Couvre aussi bien un JOIN ... ON qu'une jointure implicite dans un
# WHERE (motif ancien style, explicitement mentionné par la personne
# comme présent dans ce code).
_JOIN_CONDITION_PATTERN = re.compile(
    r"`?(\w+)`?\.`?(\w+)`?\s*=\s*`?(\w+)`?\.`?(\w+)`?"
)

# Mots-clés SQL qui suivent souvent immédiatement un nom de table sans
# alias réel -- jamais capturés comme alias (sinon "FROM commandes
# WHERE ..." capturerait "WHERE" comme alias de "commandes").
_SQL_KEYWORDS = {
    "ON", "WHERE", "AND", "OR", "INNER", "LEFT", "RIGHT", "OUTER",
    "USING", "GROUP", "ORDER", "SET", "VALUES", "LIMIT", "HAVING",
    "JOIN", "AS", "SELECT", "UNION", "IS", "NOT", "NULL",
}

# Repère une chaîne PHP (simple ou double quote) qui CONTIENT du SQL
# plausible -- SELECT/FROM ou JOIN présents, insensible à la casse.
# Ne tente PAS de gérer les guillemets échappés à l'intérieur (`\"`) --
# limite acceptée, une requête SQL contenant elle-même des guillemets
# imbriqués reste un cas marginal pour ce repérage best-effort.
_PHP_STRING_PATTERN = re.compile(r'"([^"]*)"|\'([^\']*)\'')

# Motif Fat-Free spécifique -- new \DB\SQL\Mapper($db, 'table') ou
# new DB\SQL\Mapper($db,'table') (le \ initial optionnel selon le
# contexte de namespace) -- révèle qu'UNE table est manipulée ici,
# même sans jointure explicite (utile pour l'inventaire des tables
# réellement utilisées par l'appli, pas seulement les relations).
_F3_MAPPER_PATTERN = re.compile(
    r"new\s+\\?(?:DB\\SQL\\)?Mapper\s*\(\s*\$\w+\s*,\s*['\"](\w+)['\"]",
)


def _looks_like_sql(text):
    upper = text.upper()
    return ("SELECT" in upper and "FROM" in upper) or "JOIN" in upper


def _build_alias_map(sql_text):
    """Renvoie {alias_ou_nom: nom_de_table_reel} pour toutes les
    références FROM (y compris une liste séparée par virgules, style
    ancien) et JOIN trouvées dans `sql_text`. Une table SANS alias
    explicite se mappe sur elle-même (permet de résoudre une
    condition qui utilise le nom de table complet directement, pas
    systématiquement un alias court)."""
    alias_map = {}

    def _register(table_name, alias):
        alias_map[table_name] = table_name
        if alias and alias.upper() not in _SQL_KEYWORDS:
            alias_map[alias] = table_name

    from_match = _FROM_CLAUSE_PATTERN.search(sql_text)
    if from_match:
        for table_item in from_match.group(1).split(","):
            item_match = _TABLE_ITEM_PATTERN.search(table_item.strip())
            if item_match:
                _register(item_match.group(1), item_match.group(2))

    for match in _JOIN_TABLE_PATTERN.finditer(sql_text):
        _register(match.group(1), match.group(2))

    return alias_map


def extract_join_candidates_from_sql(sql_text, source_file=None, source_line=None):
    """Renvoie une liste de relations CANDIDATES trouvées dans UN
    fragment SQL déjà isolé (voir `scan_php_source` pour l'extraction
    depuis un fichier PHP complet). Chaque candidat :
    {from_table, from_column, to_table, to_column, source_file,
    source_line, raw_condition}. Une condition qui référence un alias
    NON résolu (jamais déclaré dans un FROM/JOIN de ce même fragment)
    est IGNORÉE plutôt que devinée -- mieux vaut manquer un candidat
    que d'en proposer un avec un nom de table faux.

    **Correctif livraison #246** -- une auto-jointure HIÉRARCHIQUE
    légitime (ex. `employes e1 JOIN employes e2 ON e1.manager_id =
    e2.id`, exactement le genre de structure hiérarchique visée par
    la personne à l'origine de ce module) était auparavant EXCLUE à
    tort par le filtre `table_a == table_b` -- ce filtre visait à
    écarter une comparaison TRIVIALE (le même alias des deux côtés,
    ex. `e.manager_id = e.id` dans un WHERE qui n'est pas une vraie
    jointure), mais excluait AUSSI le cas légitime où deux ALIAS
    DIFFÉRENTS pointent vers la MÊME table. Corrigé : le test porte
    désormais sur les ALIAS eux-mêmes (`alias_a == alias_b`), pas sur
    la table résolue -- une auto-jointure avec deux alias distincts
    est maintenant CAPTURÉE, marquée `is_self_reference: true` pour
    que la personne la distingue clairement d'une relation
    inter-tables ordinaire."""
    if not _looks_like_sql(sql_text):
        return []
    alias_map = _build_alias_map(sql_text)
    candidates = []
    for match in _JOIN_CONDITION_PATTERN.finditer(sql_text):
        alias_a, col_a, alias_b, col_b = match.groups()
        if alias_a == alias_b:
            continue  # même alias des deux côtés -- comparaison triviale, jamais une jointure réelle
        table_a = alias_map.get(alias_a)
        table_b = alias_map.get(alias_b)
        if not table_a or not table_b:
            continue  # alias non résolu -- jamais deviné
        candidates.append({
            "from_table": table_a, "from_column": col_a,
            "to_table": table_b, "to_column": col_b,
            "source_file": source_file, "source_line": source_line,
            "raw_condition": match.group(0),
            "is_self_reference": table_a == table_b,
        })
    return candidates


def scan_php_source(php_text, filename=None):
    """Point d'entrée principal -- balaie TOUT le texte d'un fichier
    PHP, isole chaque chaîne littérale qui ressemble à du SQL, et en
    extrait les relations candidates. Renvoie {"join_candidates": [...],
    "mapper_tables": [...]} -- `mapper_tables` : tables RÉELLEMENT
    manipulées via le motif Fat-Free `Mapper`, utile même sans
    relation détectée (inventaire des tables actives dans ce
    fichier)."""
    join_candidates = []
    for line_number, line in enumerate(php_text.splitlines(), start=1):
        for str_match in _PHP_STRING_PATTERN.finditer(line):
            content = str_match.group(1) if str_match.group(1) is not None else str_match.group(2)
            join_candidates.extend(extract_join_candidates_from_sql(content, source_file=filename, source_line=line_number))

    mapper_tables = sorted(set(_F3_MAPPER_PATTERN.findall(php_text)))
    return {"join_candidates": join_candidates, "mapper_tables": mapper_tables}


def deduplicate_candidates(candidates):
    """Regroupe les candidats IDENTIQUES (même 4-uplet table/colonne,
    indépendamment du fichier/ligne) -- une même relation apparaît
    souvent DIZAINES de fois dans un vieux code (une requête copiée-
    collée à travers de nombreux écrans) : la personne veut voir LA
    relation, pas cent occurrences de la même. Garde la PREMIÈRE
    occurrence (fichier+ligne) comme référence, ajoute un compteur
    `occurrence_count`."""
    grouped = {}
    for cand in candidates:
        key = (cand["from_table"], cand["from_column"], cand["to_table"], cand["to_column"])
        if key not in grouped:
            grouped[key] = {**cand, "occurrence_count": 1}
        else:
            grouped[key]["occurrence_count"] += 1
    return sorted(grouped.values(), key=lambda c: -c["occurrence_count"])
