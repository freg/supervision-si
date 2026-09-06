"""
Détection de relations par le NOM des champs (livraison #151, backlog
BACKLOG.md #5) -- coeur technique du module d'analyse de schémas
hérités. Fonctions PURES : ne font aucun accès réseau ni base, reçoivent
un schéma DÉJÀ introspecté (voir schema_client.py pour la récupération
via dba-api) -- testables directement, sans mock HTTP ni base réelle.

Propose des relations, ne les CONFIRME jamais -- validation manuelle
humaine obligatoire (voir BACKLOG.md #5, "proposition automatique et
validation manuelle" demandé explicitement). Chaque proposition porte
un niveau de confiance et une raison explicite, jamais une affirmation
silencieuse.

Heuristique VOLONTAIREMENT SIMPLE (suffixe _id/Id/ID + pluriel anglais
basique) -- ne couvre pas les pluriels irréguliers anglais, ni les
conventions de nommage françaises (ex. "client_id" fonctionne,
"identifiant_client" ne serait pas détecté). Documenté comme limite
connue plutôt que silencieusement absent -- l'éditeur de relations
(étape suivante du backlog) existe précisément pour corriger ce que
cette heuristique rate ou propose à tort.
"""
import re

# Suffixes courants de clé étrangère -- ordre sans importance, tous
# testés, le premier qui matche la fin du nom de colonne est retenu.
FK_SUFFIXES = ("_id", "Id", "ID", "id")


def strip_fk_suffix(column_name):
    """Retire un suffixe de clé étrangère du nom de colonne, renvoie
    le nom "de base" candidat (ex. "client_id" -> "client"). None si
    aucun suffixe reconnu, ou si le nom EST le suffixe lui-même (ex.
    juste "id" -- rien à en tirer comme nom de table candidat)."""
    for suffix in FK_SUFFIXES:
        if column_name.endswith(suffix) and len(column_name) > len(suffix):
            base = column_name[: -len(suffix)].rstrip("_")
            if base:
                return base
    return None


def pluralize_candidates(base_name):
    """Variantes plausibles pour matcher un nom de table -- casse et
    pluriel anglais simple (ajout d'un "s", retrait d'un "s" final,
    "y"<->"ies"). PAS une vraie lemmatisation -- les pluriels
    irréguliers anglais (ex. "person"/"people") ne sont pas couverts,
    limite assumée et documentée en tête de module."""
    lower = base_name.lower()
    candidates = {lower, lower + "s"}
    if lower.endswith("s"):
        candidates.add(lower[:-1])
    if lower.endswith("y"):
        candidates.add(lower[:-1] + "ies")
    if lower.endswith("ies"):
        candidates.add(lower[:-3] + "y")
    return candidates


def guess_referenced_table(name_hint, table_names):
    """Essaie de deviner à quelle table `name_hint` pourrait faire
    référence -- réutilisé pour les colonnes-LISTES (list_detector.py) :
    une colonne "sites_concernes" ou "site_ids" n'a pas forcément le
    suffixe classique "_id" d'une clé étrangère simple, donc pas
    couverte par strip_fk_suffix/detect_name_based_relations ci-dessus.
    Débarrasse `name_hint` d'un suffixe pluriel de liste ("_ids") s'il
    y en a un, puis tente les mêmes variantes de pluriel que pour une
    clé étrangère classique. Renvoie le nom de table réel (casse
    d'origine) ou None si aucune correspondance."""
    table_names_lower = {name.lower(): name for name in table_names}
    hint = name_hint
    for suffix in ("_ids", "_id"):
        if hint.lower().endswith(suffix):
            hint = hint[: -len(suffix)]
            break
    for cand in pluralize_candidates(hint):
        if cand in table_names_lower:
            return table_names_lower[cand]
    # Repli : le PREMIER segment snake_case du nom complet (ex.
    # "sites_concernes" -> "sites") -- une colonne-liste nommée par un
    # mot composé commence souvent par le nom (singulier ou pluriel)
    # de ce à quoi elle fait référence. Testé UNIQUEMENT si le nom
    # complet n'a rien donné -- reste permissif à dessein : ceci
    # n'est qu'une PROPOSITION à valider manuellement (voir
    # detect_name_based_relations ci-dessus, même principe), jamais
    # appliquée automatiquement -- un faux positif occasionnel coûte
    # peu (rejeté à la validation), rater une vraie relation coûte
    # plus (jamais proposée du tout).
    first_segment = name_hint.split("_")[0]
    if first_segment.lower() != hint.lower():
        for cand in pluralize_candidates(first_segment):
            if cand in table_names_lower:
                return table_names_lower[cand]
    return None


def get_primary_key(tables, table_name):
    """Renvoie le nom de la colonne clé primaire de `table_name` --
    "id" par repli si aucune PK n'est déclarée dans le schéma
    introspecté (même raisonnement que dans
    detect_name_based_relations ci-dessous). None si la table
    n'existe pas dans `tables`."""
    tinfo = tables.get(table_name)
    if tinfo is None:
        return None
    pk_cols = [c["name"] for c in tinfo.get("columns", []) if c.get("primary_key")]
    return pk_cols[0] if pk_cols else "id"


def detect_name_based_relations(tables):
    """`tables` : dict {nom_table: {"columns": [{"name": str,
    "primary_key": bool}, ...]}} -- le schéma déjà introspecté (voir
    schema_client.fetch_full_schema).

    Renvoie une liste de relations PROPOSÉES (jamais confirmées),
    chacune : {"from_table", "from_column", "to_table", "to_column",
    "confidence" ("haute"|"moyenne"), "reason"}. Une relation
    "haute confiance" : le nom de colonne est EXACTEMENT
    "<table_cible>_id" (au singulier). "moyenne" : une variante
    (pluriel, casse différente) a été nécessaire pour matcher.

    Ne propose JAMAIS une colonne comme référence à sa PROPRE table
    (une colonne "id" qui EST la clé primaire n'est jamais proposée
    comme pointant vers elle-même), ni une relation vers une table
    inconnue (candidat qui ne correspond à AUCUNE table du schéma --
    silencieusement ignoré, pas une proposition à faible confiance
    pour autant : mieux vaut ne rien proposer qu'inventer une cible)."""
    table_names_lower = {name.lower(): name for name in tables}

    pk_by_table = {}
    for tname, tinfo in tables.items():
        pk_cols = [c["name"] for c in tinfo.get("columns", []) if c.get("primary_key")]
        # Repli sur "id" si aucune PK déclarée dans le schéma introspecté
        # (arrive avec certains vieux schémas MyISAM sans contrainte
        # explicite) -- une hypothèse raisonnable, pas une certitude,
        # mais laisser le champ vide serait moins utile pour la
        # validation manuelle qui suit.
        pk_by_table[tname] = pk_cols[0] if pk_cols else "id"

    proposals = []
    for tname, tinfo in tables.items():
        for col in tinfo.get("columns", []):
            cname = col["name"]
            if col.get("primary_key"):
                continue
            base = strip_fk_suffix(cname)
            if not base:
                continue
            matched_table = None
            exact_singular_match = False
            for cand in pluralize_candidates(base):
                if cand in table_names_lower and table_names_lower[cand] != tname:
                    matched_table = table_names_lower[cand]
                    exact_singular_match = cand == base.lower()
                    break
            if not matched_table:
                continue
            proposals.append({
                "from_table": tname,
                "from_column": cname,
                "to_table": matched_table,
                "to_column": pk_by_table[matched_table],
                "confidence": "haute" if exact_singular_match else "moyenne",
                "reason": (
                    f"'{cname}' se termine par un suffixe de clé étrangère et correspond "
                    f"au nom de la table '{matched_table}'"
                ),
            })
    return proposals
