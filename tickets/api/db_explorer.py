"""
Introspection générique de la base tickets -- fondation partagée par
l'éditeur générique de lignes et l'arborescence des relations
(gestionnaire de base de données, demandé explicitement comme
possiblement généralisable à d'autres applications plus tard, même
philosophie que le système de paramétrage).

Toutes les fonctions prennent un CURSEUR déjà ouvert en paramètre
(jamais une connexion créée en interne) -- restent testables avec un
vrai SQLite en mémoire, sans dépendre de get_connection()/DB_BACKEND
au niveau du module.

SÉCURITÉ -- point critique : tout nom de table venant d'une requête
HTTP DOIT être validé contre la liste RÉELLEMENT introspectée
(list_all_tables) AVANT tout usage dans une chaîne SQL interpolée
(PRAGMA table_info(<table>) ne supporte pas les paramètres liés côté
SQLite) -- voir is_known_table(), appelée systématiquement par les
routes avant tout accès.
"""


def list_all_tables(cur, db_backend):
    """Tables RÉELLES uniquement (jamais les tables internes SQLite
    comme sqlite_sequence, ni les vues) -- introspection dynamique,
    jamais une liste codée en dur, pour rester correcte même si de
    nouvelles tables sont ajoutées plus tard sans repasser ici."""
    if db_backend == "postgres":
        cur.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_type = 'BASE TABLE' "
            "ORDER BY table_name"
        )
    else:
        cur.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type = 'table' AND name NOT LIKE 'sqlite_%' "
            "ORDER BY name"
        )
    return [row[0] for row in cur.fetchall()]


def is_known_table(table, known_tables):
    """Garde-fou de sécurité -- un nom de table venant d'une requête
    HTTP DOIT passer par ici avant tout usage dans une chaîne SQL
    interpolée. `known_tables` doit venir de list_all_tables() (jamais
    une liste inventée), passé en paramètre pour rester pure/testable
    sans requête réelle à chaque vérification."""
    return table in known_tables


def table_columns_sqlite(cur, table):
    """Colonnes d'une table SQLite, avec repérage de la clé primaire
    -- jamais éditable depuis l'éditeur générique (trop risqué,
    pourrait orpheliner silencieusement des clés étrangères). `table`
    DOIT déjà avoir été validée par is_known_table() par l'appelant --
    cette fonction ne revalide pas, pour rester une brique simple à
    tester isolément."""
    cur.execute(f"PRAGMA table_info({table})")
    return [
        {"name": row[1], "type": row[2], "is_primary_key": bool(row[5])}
        for row in cur.fetchall()
    ]


def table_columns_postgres(cur, table):
    """Équivalent PostgreSQL -- deux requêtes information_schema
    (colonnes, puis clé primaire), jointes en Python plutôt qu'en SQL
    pour rester lisible. Non testée avec un vrai serveur PostgreSQL
    dans cet environnement (aucun disponible) -- voir tickets/README.md
    pour cette réserve, comme pour backup_manager.py."""
    cur.execute(
        "SELECT column_name, data_type FROM information_schema.columns "
        "WHERE table_name = %s ORDER BY ordinal_position",
        [table],
    )
    columns = [{"name": r[0], "type": r[1], "is_primary_key": False} for r in cur.fetchall()]

    cur.execute(
        "SELECT ku.column_name FROM information_schema.table_constraints tc "
        "JOIN information_schema.key_column_usage ku ON tc.constraint_name = ku.constraint_name "
        "WHERE tc.table_name = %s AND tc.constraint_type = 'PRIMARY KEY'",
        [table],
    )
    pk_columns = {r[0] for r in cur.fetchall()}
    for col in columns:
        if col["name"] in pk_columns:
            col["is_primary_key"] = True
    return columns


def table_columns(cur, table, db_backend):
    if db_backend == "postgres":
        return table_columns_postgres(cur, table)
    return table_columns_sqlite(cur, table)


def primary_key_column(columns):
    """La clé primaire d'une table, déduite de sa liste de colonnes
    (voir table_columns) -- None si aucune trouvée (table sans clé
    primaire déclarée, rare mais possible). Suppose une clé primaire
    à colonne UNIQUE -- les clés composites ne sont pas gérées par
    l'éditeur générique (aucune table de ce projet n'en a une)."""
    for col in columns:
        if col["is_primary_key"]:
            return col["name"]
    return None


def editable_columns(columns):
    """Colonnes éditables depuis l'éditeur générique -- tout SAUF la
    clé primaire. Jamais permettre l'édition directe d'un id, quel
    que soit le contexte -- risque de rupture silencieuse de
    l'intégrité référentielle bien plus élevé que pour n'importe
    quel autre champ."""
    return [c["name"] for c in columns if not c["is_primary_key"]]


def declared_foreign_keys_sqlite(cur, table):
    """Relations DÉCLARÉES (avec REFERENCES dans le CREATE TABLE) pour
    une table SQLite -- "contraintes" au sens de la demande ("y
    compris contraintes ou non"). `table` DOIT déjà être validée par
    l'appelant, même raisonnement que table_columns_sqlite."""
    cur.execute(f"PRAGMA foreign_key_list({table})")
    return [
        {"from_column": row[3], "to_table": row[2], "to_column": row[4], "declared": True}
        for row in cur.fetchall()
    ]


def infer_undeclared_relationships(table, columns, known_tables):
    """Relations PROBABLES mais NON déclarées -- heuristique par
    convention de nommage (une colonne `xxx_id` dont le préfixe
    pluralisé correspond à une table connue), demandé explicitement
    ("y compris contraintes ou non"). Jamais garanti à 100% --
    sert à REPÉRER le schéma visuellement, pas à valider son
    intégrité."""
    inferred = []
    for col in columns:
        name = col["name"]
        if not name.endswith("_id"):
            continue
        prefix = name[: -len("_id")]
        # Essai direct (ex. "user_id" -> "users"), puis sans le 's'
        # final au cas où le préfixe serait déjà au pluriel.
        candidates = [prefix + "s", prefix]
        target_table = next((c for c in candidates if c in known_tables), None)
        if target_table and target_table != table:
            inferred.append({"from_column": name, "to_table": target_table, "to_column": "id", "declared": False})
    return inferred


def table_relationships(cur, table, columns, known_tables, db_backend):
    """Combine relations déclarées ET probables (non déclarées) --
    jamais la même colonne comptée deux fois si elle a déjà une FK
    déclarée."""
    declared = declared_foreign_keys_sqlite(cur, table) if db_backend != "postgres" else []
    declared_from_columns = {r["from_column"] for r in declared}
    remaining_columns = [c for c in columns if c["name"] not in declared_from_columns]
    inferred = infer_undeclared_relationships(table, remaining_columns, known_tables)
    return declared + inferred


def all_relationships(cur, db_backend):
    """Relations de TOUTE la base -- une entrée par relation détectée
    (déclarée ou probable), avec la table d'origine incluse. Base de
    l'arborescence des relations."""
    tables = list_all_tables(cur, db_backend)
    result = []
    for table in tables:
        columns = table_columns(cur, table, db_backend)
        for rel in table_relationships(cur, table, columns, tables, db_backend):
            result.append({"from_table": table, **rel})
    return result
