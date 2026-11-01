# -*- coding: utf-8 -*-
"""#821 : base SQLite de la veille des modèles (à côté de la base de si-agent-api ; MODELES_DB pour la déplacer)."""
import os
import sqlite3


def chemin():
    return os.environ.get("MODELES_DB") or os.path.join(os.path.dirname(os.path.abspath(os.environ.get("SI_AGENT_DB_PATH", "/data/si-agent.db"))), "modeles.db")


def cnx():
    p = chemin()
    os.makedirs(os.path.dirname(os.path.abspath(p)), exist_ok=True)
    c = sqlite3.connect(p, timeout=10)
    c.row_factory = sqlite3.Row
    return c
