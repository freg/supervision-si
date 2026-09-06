import sqlite3

from .base import DBConnector


class SQLiteConnector(DBConnector):
    """conn_info attendu : {'file_path': '/chemin/vers/fichier.db'}.
    Un fichier = une base, pas de notion de bases multiples sur un
    même "serveur" comme postgres/mysql."""

    def _connect(self):
        return sqlite3.connect(self.conn_info["file_path"])

    def test_connection(self):
        try:
            conn = self._connect()
            conn.execute("SELECT 1")
            conn.close()
            return True, "Connexion réussie"
        except Exception as exc:  # noqa: BLE001 — test délibérément permissif
            return False, str(exc)

    def list_databases(self):
        # Un fichier = une base ; le nom affiché est le chemin lui-même.
        return [self.conn_info["file_path"]]

    def list_tables(self, database=None):
        conn = self._connect()
        try:
            cur = conn.execute(
                "SELECT name FROM sqlite_master WHERE type IN ('table','view') AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )
            return [row[0] for row in cur.fetchall()]
        finally:
            conn.close()

    def get_table_columns(self, table, database=None):
        conn = self._connect()
        try:
            cur = conn.execute(f"PRAGMA table_info({_quote_ident(table)})")
            return [
                {
                    "name": row[1],
                    "type": row[2] or "TEXT",
                    "nullable": row[3] == 0,
                    "primary_key": row[5] > 0,
                }
                for row in cur.fetchall()
            ]
        finally:
            conn.close()

    def browse_rows(self, table, database=None, limit=50, offset=0):
        conn = self._connect()
        try:
            qtable = _quote_ident(table)
            cur = conn.execute(f"SELECT COUNT(*) FROM {qtable}")
            total_count = cur.fetchone()[0]
            cur = conn.execute(f"SELECT * FROM {qtable} LIMIT ? OFFSET ?", [limit, offset])
            columns = [d[0] for d in cur.description]
            rows = [list(r) for r in cur.fetchall()]
            return {"columns": columns, "rows": rows, "total_count": total_count}
        finally:
            conn.close()

    def execute_sql(self, sql, database=None):
        conn = self._connect()
        try:
            cur = conn.execute(sql)
            if cur.description is not None:
                columns = [d[0] for d in cur.description]
                rows = [list(r) for r in cur.fetchall()]
                return {"columns": columns, "rows": rows, "row_count": len(rows)}
            conn.commit()
            return {"affected_rows": cur.rowcount}
        finally:
            conn.close()

    def update_row(self, table, pk_column, pk_value, updates, database=None):
        conn = self._connect()
        try:
            set_clause = ", ".join(f"{_quote_ident(col)} = ?" for col in updates)
            cur = conn.execute(
                f"UPDATE {_quote_ident(table)} SET {set_clause} WHERE {_quote_ident(pk_column)} = ?",
                [*updates.values(), pk_value],
            )
            conn.commit()
            return cur.rowcount
        finally:
            conn.close()

    def insert_row(self, table, values, pk_column=None, database=None):
        conn = self._connect()
        try:
            cols = list(values.keys())
            col_names = ", ".join(_quote_ident(c) for c in cols)
            placeholders = ", ".join(["?"] * len(cols))
            cur = conn.execute(
                f"INSERT INTO {_quote_ident(table)} ({col_names}) VALUES ({placeholders})",
                list(values.values()),
            )
            conn.commit()
            return cur.lastrowid
        finally:
            conn.close()

    def delete_rows(self, table, pk_column, pk_values, database=None):
        conn = self._connect()
        try:
            placeholders = ", ".join(["?"] * len(pk_values))
            cur = conn.execute(
                f"DELETE FROM {_quote_ident(table)} WHERE {_quote_ident(pk_column)} IN ({placeholders})",
                list(pk_values),
            )
            conn.commit()
            return cur.rowcount
        finally:
            conn.close()

    def add_column(self, table, column_name, column_type, nullable=True, database=None):
        conn = self._connect()
        try:
            # NOT NULL jamais applique cote SQLite specifiquement --
            # une contrainte NOT NULL sur ADD COLUMN exige une valeur
            # par defaut explicite des que la table a deja des lignes
            # (sans quoi SQLite refuse), ce que cette interface simple
            # ne demande pas encore. Toujours nullable ici, meme si
            # nullable=False est demande -- documente clairement,
            # jamais un echec confus a la place.
            conn.execute(f"ALTER TABLE {_quote_ident(table)} ADD COLUMN {_quote_ident(column_name)} {column_type}")
            conn.commit()
        finally:
            conn.close()

    def drop_column(self, table, column_name, database=None):
        conn = self._connect()
        try:
            conn.execute(f"ALTER TABLE {_quote_ident(table)} DROP COLUMN {_quote_ident(column_name)}")
            conn.commit()
        finally:
            conn.close()

    def rename_column(self, table, old_name, new_name, database=None):
        conn = self._connect()
        try:
            conn.execute(
                f"ALTER TABLE {_quote_ident(table)} RENAME COLUMN {_quote_ident(old_name)} TO {_quote_ident(new_name)}"
            )
            conn.commit()
        finally:
            conn.close()

    def modify_column(self, table, column_name, new_type=None, nullable=None, database=None):
        raise NotImplementedError(
            "SQLite ne permet pas de modifier le type ou la nullabilité d'une colonne existante "
            "(pas d'ALTER COLUMN) -- reconstruction manuelle de la table nécessaire, voir la console SQL"
        )


def _quote_ident(name):
    """Échappe un identifiant SQLite (guillemets doubles, doublés si
    présents à l'intérieur) -- ne protège PAS contre une injection SQL
    dans une VALEUR (ça, c'est le rôle des requêtes paramétrées,
    utilisées partout où c'est une valeur plutôt qu'un nom de table).
    Un nom de table ne peut pas être paramétré nativement par le
    driver -- c'est le seul endroit légitime pour de l'interpolation
    de chaîne dans ce module."""
    return '"' + name.replace('"', '""') + '"'
