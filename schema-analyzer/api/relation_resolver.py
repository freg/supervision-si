"""
Résolution et affectation des relations sur les DONNÉES elles-mêmes
(livraison #5, backlog BACKLOG.md -- "Interface de gestion (affectation
des relations)"). Distinct de l'éditeur de relations (qui corrige le
SCHÉMA déduit) -- ici, on gère l'AFFECTATION des relations sur les
lignes existantes : pour une ligne donnée d'une table, résoudre les
valeurs liées (la "vue JSON avec valeurs résolues" demandée en #241)
ET permettre de modifier l'affectation (changer la cible d'une clé
étrangère, ou gérer les entrées d'une colonne-liste).

Fonctions PURES : reçoivent un `executor` injecté (sql -> résultat),
jamais d'accès réseau/base direct -- testables sans mock complexe.
"""
import requests

from relation_validator import extract_candidate_ids


def resolve_foreign_key(executor, from_value, to_table, to_column,
                        relation_type="foreign_key"):
    """Résout UNE valeur de clé étrangère : renvoie la (ou les) ligne(s)
    de la table cible correspondant à cette valeur.

    `executor` : fonction `sql -> {"columns": [...], "rows": [...], "row_count": N}`
    (injectée -- voir app.py).

    Renvoie {"columns": [...], "rows": [...], "row_count": N} -- liste vide
    si aucune correspondance (valeur orpheline). Valeur None/chaîne vide
    -> liste vide sans requête."""
    if from_value is None or from_value == "":
        return {"columns": [], "rows": [], "row_count": 0}

    # Extraction des identifiants candidats (1 pour FK classique,
    # plusieurs pour colonne-liste)
    candidate_ids = extract_candidate_ids(from_value, relation_type)
    if not candidate_ids:
        return {"columns": [], "rows": [], "row_count": 0}

    # Construction d'un IN clause -- valeurs échappées en texte (comparaison
    # texte uniforme, même motif que relation_validator.py)
    placeholders = ", ".join(f"'{v}'" for v in candidate_ids)
    sql = f"SELECT * FROM {to_table} WHERE {to_column} IN ({placeholders})"
    result = executor(sql)
    return {
        "columns": result.get("columns", []),
        "rows": result.get("rows", []),
        "row_count": result.get("row_count", len(result.get("rows", []))),
    }


def resolve_row_relations(executor, tables, relations, from_table, pk_column, pk_value):
    """Pour UNE ligne de `from_table`, résout TOUTES les relations
    CONFIRMÉES dont elle est la source -- la "vue JSON avec valeurs
    résolues" (demandée en #241).

    `tables` : dict {nom_table: {"columns": [...]}} -- le schéma introspecté.
    `relations` : liste de relations (depuis relations_store) -- seules les
    `confirmed` sont résolues.

    Renvoie {"row": {col: val}, "resolved": {col_name: {"relation": {...},
    "target": {"columns": [...], "rows": [...], "row_count": N}}}} --
    `resolved` ne contient que les colonnes ayant une relation confirmée
    ET une valeur non-vide.
    """
    # Ligne source
    row_sql = f"SELECT * FROM {from_table} WHERE {pk_column} = '{pk_value}'"
    row_result = executor(row_sql)
    if not row_result.get("rows"):
        return None

    columns = row_result.get("columns", [])
    row_values = row_result["rows"][0]
    row = {col: val for col, val in zip(columns, row_values)}

    # Relations confirmées pour cette table
    confirmed = [r for r in relations
                 if r.get("status") == "confirmed" and r.get("from_table") == from_table]

    resolved = {}
    for rel in confirmed:
        from_col = rel["from_column"]
        if from_col not in row or row[from_col] is None or row[from_col] == "":
            continue
        target = resolve_foreign_key(
            executor, row[from_col], rel["to_table"], rel["to_column"],
            relation_type=rel.get("relation_type", "foreign_key"),
        )
        resolved[from_col] = {
            "relation": {
                "from_table": rel["from_table"],
                "from_column": rel["from_column"],
                "to_table": rel["to_table"],
                "to_column": rel["to_column"],
                "relation_type": rel.get("relation_type", "foreign_key"),
            },
            "target": target,
        }

    return {"row": row, "resolved": resolved}


def assign_foreign_key(dba_api_base, connection_id, database, table, pk_column,
                       pk_value, column, new_value):
    """Modifie la valeur d'une clé étrangère sur une ligne existante --
    l'"affectation" demandée par l'item backlog. Délègue l'écriture
    réelle à dba-api (PUT /rows) -- ce module ne fait que préparer
    l'appel, jamais d'accès direct à la base.

    Renvoie {"status": "ok"} ou {"error": "..."}. Best-effort : un
    échec de dba-api est propagé tel quel (message réel jamais avalé)."""
    params = f"?database={database}" if database else ""
    url = f"{dba_api_base}/connections/{connection_id}/tables/{table}/rows{params}"
    resp = requests.put(url, json={"pk_value": pk_value, "updates": {column: new_value}})
    if resp.status_code == 200:
        return {"status": "ok"}
    try:
        body = resp.json()
        return {"error": body.get("error", f"erreur HTTP {resp.status_code}")}
    except ValueError:
        return {"error": f"erreur HTTP {resp.status_code}"}
