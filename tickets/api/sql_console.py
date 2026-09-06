"""
Console SQL directe -- dernier morceau du gestionnaire de base de
données. Fonctions pures/testables (curseur injecté), séparées des
routes -- même discipline que backup_manager.py/db_explorer.py.

SÉCURITÉ -- vérifié EMPIRIQUEMENT avant d'écrire ce module (pas
supposé) :
- `EXPLAIN <sql>` ne modifie JAMAIS réellement les données, même sur
  DELETE/DROP TABLE -- confirmé avec un vrai SQLite (voir la session
  de travail, transcript). C'est le mécanisme du "test de syntaxe".
- `cur.execute()` (SQLite, PAS `executescript()`) refuse nativement
  d'exécuter plusieurs instructions empilées ("SELECT 1; DROP TABLE
  x;") -- une protection native contre ce type d'injection, jamais
  besoin de la redévelopper. Non re-testé pour PostgreSQL dans cet
  environnement (aucun serveur disponible) -- voir tickets/README.md
  pour cette réserve.
"""


def is_select_statement(sql):
    """La requête est-elle un SELECT ? Détermine si une sauvegarde
    est nécessaire avant exécution (tout ce qui N'EST PAS un SELECT)
    et si une confirmation explicite doit être demandée côté
    interface. Heuristique simple (premier mot, insensible à la
    casse) -- suffisante ici, jamais un vrai parseur SQL complet."""
    stripped = (sql or "").strip()
    if not stripped:
        return False
    first_word = stripped.split(None, 1)[0].upper()
    return first_word == "SELECT"


def check_syntax(cur, sql):
    """Teste la syntaxe SANS JAMAIS exécuter réellement -- EXPLAIN,
    voir la note de sécurité en tête de fichier. Retourne un dict
    {ok, error} -- jamais une exception qui remonterait jusqu'à
    l'appelant, cette fonction absorbe l'erreur de syntaxe pour la
    restituer proprement."""
    if not (sql or "").strip():
        return {"ok": False, "error": "requête vide"}
    try:
        cur.execute(f"EXPLAIN {sql}")
        cur.fetchall()  # vide le curseur, jamais laisser un résultat en attente
        return {"ok": True, "error": None}
    except Exception as exc:  # noqa: BLE001 — n'importe quelle erreur de syntaxe, peu importe le moteur
        return {"ok": False, "error": str(exc)}


def execute_sql(cur, sql):
    """Exécution RÉELLE -- appelée uniquement après confirmation
    explicite côté interface pour tout ce qui n'est pas un SELECT
    (voir is_select_statement). Renvoie soit des lignes de résultat
    (cur.description non vide -- SELECT ou équivalent), soit un
    nombre de lignes affectées (INSERT/UPDATE/DELETE). Ne fait
    JAMAIS le commit elle-même -- la responsabilité de la transaction
    reste à l'appelant (route), pour rester une brique simple à
    tester isolément."""
    cur.execute(sql)
    if cur.description is not None:
        columns = [d[0] for d in cur.description]
        rows = cur.fetchall()
        return {"kind": "rows", "columns": columns, "rows": [list(r) for r in rows]}
    return {"kind": "affected", "affected_rows": cur.rowcount}
