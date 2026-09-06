import logging
import time

import pymysql

from .base import DBConnector

# Traces DEBUG (livraison #223, audit rétroactif). RÈGLE ABSOLUE : le
# mot de passe de connexion (stocké en clair côté base locale, voir
# base.py) n'apparaît JAMAIS dans une trace.
_log = logging.getLogger("dba_mysql_connector")


class MySQLConnector(DBConnector):
    """conn_info attendu : host, port, username, password,
    database_name. PyMySQL plutôt que mysqlclient : pur Python, pas de
    dépendance de compilation côté image Docker (mysqlclient a besoin
    de libmariadb-dev ou équivalent, PyMySQL non) -- prioritaire dans
    cette demande ("avant tout mysql"), donc le moteur le plus
    important à garder simple à construire/maintenir."""

    def _connect(self, database=None):
        host, port = self.conn_info["host"], int(self.conn_info.get("port") or 3306)
        _log.debug("_connect : démarré (%s:%s, base=%s, jamais le mot de passe ici)", host, port, database or self.conn_info.get("database_name"))
        start = time.monotonic()
        try:
            conn = pymysql.connect(
                host=host,
                port=port,
                user=self.conn_info["username"],
                password=self.conn_info.get("password") or "",
                database=database or self.conn_info.get("database_name") or None,
                connect_timeout=5,
                # Corrigé après un bug réel signalé (capture d'écran) :
                # "ERROR 2026 (HY000): TLS/SSL error: SSL is required, but
                # the server does not support it" -- certains serveurs
                # MySQL/MariaDB annoncent la capacité SSL sans réellement
                # la supporter pleinement, et PyMySQL tente alors le
                # chiffrement de façon opportuniste. ssl_disabled=True
                # (paramètre documenté de pymysql.connect(), pas un
                # bricolage) force explicitement l'absence de SSL, quelle
                # que soit l'annonce du serveur -- demandé explicitement.
                ssl_disabled=True,
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
        conn = self._connect(database=None)  # pas de base précise pour lister -- accès au serveur seul
        try:
            cur = conn.cursor()
            cur.execute("SHOW DATABASES")
            # Exclut les bases système MySQL internes, jamais pertinentes
            # pour un usage DBA applicatif ici.
            system_dbs = {"information_schema", "mysql", "performance_schema", "sys"}
            return [row[0] for row in cur.fetchall() if row[0] not in system_dbs]
        finally:
            conn.close()

    def list_tables(self, database=None):
        conn = self._connect(database)
        try:
            cur = conn.cursor()
            cur.execute("SHOW TABLES")
            return [row[0] for row in cur.fetchall()]
        finally:
            conn.close()

    def get_table_columns(self, table, database=None):
        conn = self._connect(database)
        try:
            cur = conn.cursor()
            cur.execute(f"SHOW COLUMNS FROM {_quote_ident(table)}")
            # SHOW COLUMNS : (Field, Type, Null, Key, Default, Extra)
            return [
                {
                    "name": row[0],
                    "type": row[1],
                    "nullable": row[2] == "YES",
                    "primary_key": row[3] == "PRI",
                }
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
            columns = [d[0] for d in cur.description]
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
                columns = [d[0] for d in cur.description]
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
            cur.execute(
                f"INSERT INTO {_quote_ident(table)} ({col_names}) VALUES ({placeholders})",
                list(values.values()),
            )
            conn.commit()
            return cur.lastrowid or None
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
            # RENAME COLUMN -- syntaxe MySQL 8.0+ (l'ancienne syntaxe
            # CHANGE exige de re-préciser le type complet, jamais
            # connu ici lors d'un simple renommage -- MySQL 8 est la
            # référence assumée pour ce projet, voir dba/README.md).
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
            # MODIFY -- syntaxe MySQL, combine type ET nullabilite en
            # UNE seule clause (contrairement a Postgres, deux
            # instructions separees). Type actuel repris tel quel si
            # non fourni (MySQL exige de re-preciser le type complet
            # dans MODIFY, meme pour ne changer QUE la nullabilite).
            if new_type is None:
                cur.execute(f"SHOW COLUMNS FROM {_quote_ident(table)} WHERE Field = %s", [column_name])
                row = cur.fetchone()
                new_type = row[1] if row else "TEXT"
            null_clause = " NOT NULL" if nullable is False else (" NULL" if nullable is True else "")
            cur.execute(f"ALTER TABLE {_quote_ident(table)} MODIFY COLUMN {_quote_ident(column_name)} {new_type}{null_clause}")
            conn.commit()
        finally:
            conn.close()


def _quote_ident(name):
    """Échappe un identifiant MySQL — BACKTICKS, pas des guillemets
    doubles comme postgres/sqlite (différence de dialecte réelle,
    source d'erreur classique si copié tel quel depuis les deux autres
    connecteurs). Ne protège qu'un nom de table, jamais une valeur."""
    return "`" + name.replace("`", "``") + "`"
