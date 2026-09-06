"""Registre des connecteurs -- un seul endroit à modifier pour ajouter
un futur moteur (ex. un jour MSSQL, Oracle...) : un nouveau fichier
connectors/xxx.py implémentant DBConnector, une ligne ici."""

from .sqlite import SQLiteConnector
from .postgres import PostgresConnector
from .mysql import MySQLConnector

CONNECTORS = {
    "sqlite": SQLiteConnector,
    "postgres": PostgresConnector,
    "mysql": MySQLConnector,
}


def get_connector(conn_info):
    """conn_info : dict incluant 'engine'. Lève ValueError si le
    moteur n'est pas reconnu -- jamais un KeyError opaque plus loin."""
    engine = conn_info.get("engine")
    cls = CONNECTORS.get(engine)
    if cls is None:
        raise ValueError(f"moteur '{engine}' non pris en charge (attendus : {list(CONNECTORS)})")
    return cls(conn_info)
