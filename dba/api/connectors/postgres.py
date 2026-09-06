import logging
import time

import psycopg2

from .base import DBConnector

# Traces DEBUG (livraison #223, audit rétroactif). RÈGLE ABSOLUE : le
# mot de passe de connexion n'apparaît JAMAIS dans une trace.
_log = logging.getLogger("dba_postgres_connector")


class PostgresConnector(DBConnector):
    """conn_info attendu : host, port, username, password,
    database_name (base par défaut -- browse_rows/list_tables peuvent
    cibler une AUTRE base du même serveur via le paramètre
    `database`, une vraie reconnexion à chaque fois : psycopg2 ne
    permet pas de changer de base sur une connexion déjà ouverte)."""

    def _connect(self, database=None):
        host, port = self.conn_info["host"], self.conn_info.get("port") or 5432
        target_db = database or self.conn_info["database_name"]
        _log.debug("_connect : démarré (%s:%s, base=%s, jamais le mot de passe ici)", host, port, target_db)
        start = time.monotonic()
        try:
            conn = psycopg2.connect(
                host=host,
                port=port,
                user=self.conn_info["username"],
                password=self.conn_info.get("password") or "",
                dbname=target_db,
                connect_timeout=5,
            )
        except Exception as exc:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            _log.debug("_connect : ÉCHEC après %d ms -- %s", elapsed_ms, exc)
            raise
        elapsed_ms = int((time.monotonic() - start) * 1000)
        _log.debug("_connect : succès en %d ms", elapsed_ms)
        return conn

    def test_connection(self):
        try:
            conn = self._connect()
            conn.close()
            return True, "Connexion réussie"
        except Exception as exc:  # noqa: BLE001 — test délibérément permissif
            return False, str(exc)

    def list_databases(self):
        conn = self._connect()
        try:
            cur = conn.cursor()
            cur.execute("SELECT datname FROM pg_database WHERE datistemplate = false ORDER BY datname")
            return [row[0] for row in cur.fetchall()]
        finally:
            conn.close()

    def list_tables(self, database=None):
        conn = self._connect(database)
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public' ORDER BY table_name"
            )
            return [row[0] for row in cur.fetchall()]
        finally:
            conn.close()

    def get_table_columns(self, table, database=None):
        conn = self._connect(database)
        try:
            cur = conn.cursor()
            cur.execute(
                """SELECT c.column_name, c.data_type, c.is_nullable,
                          COALESCE(pk.is_pk, false) AS is_pk
                   FROM information_schema.columns c
                   LEFT JOIN (
                       SELECT kcu.column_name, true AS is_pk
                       FROM information_schema.table_constraints tc
                       JOIN information_schema.key_column_usage kcu
                         ON tc.constraint_name = kcu.constraint_name
                       WHERE tc.table_name = %s AND tc.constraint_type = 'PRIMARY KEY'
                   ) pk ON pk.column_name = c.column_name
                   WHERE c.table_name = %s
                   ORDER BY c.ordinal_position""",
                [table, table],
            )
            return [
                {"name": row[0], "type": row[1], "nullable": row[2] == "YES", "primary_key": bool(row[3])}
                for row in cur.fetchall()
            ]
        finally:
            conn.close()

    def browse_rows(self, table, database=None, limit=50, offset=0):
        conn = self._connect(database)
        try:
            qtable = _quote_ident(table)
            cur = conn.cursor()
            cur.execute(f"SELECT COUNT(*) FROM {qtable}")
            total_count = cur.fetchone()[0]
            cur.execute(f"SELECT * FROM {qtable} LIMIT %s OFFSET %s", [limit, offset])
            columns = [d.name for d in cur.description]
            rows = [list(r) for r in cur.fetchall()]
            return {"columns": columns, "rows": rows, "total_count": total_count}
        finally:
            conn.close()

    def execute_sql(self, sql, database=None):
        conn = self._connect(database)
        try:
            cur = conn.cursor()
            cur.execute(sql)
            if cur.description is not None:
                columns = [d.name for d in cur.description]
                rows = [list(r) for r in cur.fetchall()]
                return {"columns": columns, "rows": rows, "row_count": len(rows)}
            conn.commit()
            return {"affected_rows": cur.rowcount}
        finally:
            conn.close()

    def update_row(self, table, pk_column, pk_value, updates, database=None):
        conn = self._connect(database)
        try:
            cur = conn.cursor()
            set_clause = ", ".join(f"{_quote_ident(col)} = %s" for col in updates)
            cur.execute(
                f"UPDATE {_quote_ident(table)} SET {set_clause} WHERE {_quote_ident(pk_column)} = %s",
                [*updates.values(), pk_value],
            )
            conn.commit()
            return cur.rowcount
        finally:
            conn.close()

    def insert_row(self, table, values, pk_column=None, database=None):
        conn = self._connect(database)
        try:
            cur = conn.cursor()
            cols = list(values.keys())
            col_names = ", ".join(_quote_ident(c) for c in cols)
            placeholders = ", ".join(["%s"] * len(cols))
            sql = f"INSERT INTO {_quote_ident(table)} ({col_names}) VALUES ({placeholders})"
            # RETURNING -- psycopg2 n'a pas de lastrowid natif (contrairement
            # à sqlite3/PyMySQL), seul moyen standard de récupérer la
            # nouvelle clé sans une requête séparée.
            if pk_column:
                sql += f" RETURNING {_quote_ident(pk_column)}"
            cur.execute(sql, list(values.values()))
            new_id = cur.fetchone()[0] if pk_column else None
            conn.commit()
            return new_id
        finally:
            conn.close()

    def delete_rows(self, table, pk_column, pk_values, database=None):
        conn = self._connect(database)
        try:
            cur = conn.cursor()
            placeholders = ", ".join(["%s"] * len(pk_values))
            cur.execute(
                f"DELETE FROM {_quote_ident(table)} WHERE {_quote_ident(pk_column)} IN ({placeholders})",
                list(pk_values),
            )
            conn.commit()
            return cur.rowcount
        finally:
            conn.close()

    def add_column(self, table, column_name, column_type, nullable=True, database=None):
        conn = self._connect(database)
        try:
            cur = conn.cursor()
            null_clause = "" if nullable else " NOT NULL"
            cur.execute(f"ALTER TABLE {_quote_ident(table)} ADD COLUMN {_quote_ident(column_name)} {column_type}{null_clause}")
            conn.commit()
        finally:
            conn.close()

    def drop_column(self, table, column_name, database=None):
        conn = self._connect(database)
        try:
            cur = conn.cursor()
            cur.execute(f"ALTER TABLE {_quote_ident(table)} DROP COLUMN {_quote_ident(column_name)}")
            conn.commit()
        finally:
            conn.close()

    def rename_column(self, table, old_name, new_name, database=None):
        conn = self._connect(database)
        try:
            cur = conn.cursor()
            cur.execute(f"ALTER TABLE {_quote_ident(table)} RENAME COLUMN {_quote_ident(old_name)} TO {_quote_ident(new_name)}")
            conn.commit()
        finally:
            conn.close()

    def modify_column(self, table, column_name, new_type=None, nullable=None, database=None):
        if new_type is None and nullable is None:
            return  # rien a faire -- jamais une requete SQL vide
        conn = self._connect(database)
        try:
            cur = conn.cursor()
            # Postgres -- DEUX instructions separees (type et
            # nullabilite ne partagent jamais la meme clause ALTER
            # COLUMN, contrairement a MySQL) -- chacune executee
            # seulement si demandee.
            if new_type is not None:
                cur.execute(f"ALTER TABLE {_quote_ident(table)} ALTER COLUMN {_quote_ident(column_name)} TYPE {new_type}")
            if nullable is True:
                cur.execute(f"ALTER TABLE {_quote_ident(table)} ALTER COLUMN {_quote_ident(column_name)} DROP NOT NULL")
            elif nullable is False:
                cur.execute(f"ALTER TABLE {_quote_ident(table)} ALTER COLUMN {_quote_ident(column_name)} SET NOT NULL")
            conn.commit()
        finally:
            conn.close()


def _quote_ident(name):
    """Échappe un identifiant Postgres (guillemets doubles, doublés si
    présents) -- même limite documentée que sqlite.py : ne protège
    qu'un nom de table, jamais une valeur (les valeurs passent
    toujours par des requêtes paramétrées %s)."""
    return '"' + name.replace('"', '""') + '"'
