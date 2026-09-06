"""
Interface commune à tous les connecteurs SGBD (postgres, mysql,
sqlite pour l'instant — d'autres pourront s'ajouter plus tard sans
toucher au reste de l'API, seul un nouveau fichier connectors/*.py à
enregistrer dans registry.py).

Chaque connecteur reçoit un dict de connexion (voir schéma de la table
`connections` dans app.py) et implémente ces méthodes. Aucune méthode
ne doit lever d'exception non gérée vers l'appelant HTTP — chaque
route API attrape les erreurs spécifiques au driver et les traduit en
message clair, mais les connecteurs eux-mêmes peuvent laisser
remonter les exceptions du driver (psycopg2.Error, pymysql.Error,
sqlite3.Error...) : c'est app.py qui les traduit, pas les connecteurs.

DÉCISION DE SÉCURITÉ, assumée et documentée (voir dba/README.md) :
les mots de passe de connexion sont stockés EN CLAIR dans la base
locale de cet outil, comme tout le reste de ce projet ("outil interne,
réseau de confiance", même posture que tickets_ap/OwnCloud/etc.) — pas
de chiffrement pour l'instant. À reconsidérer si cet outil venait à
être exposé au-delà du réseau interne.
"""

from abc import ABC, abstractmethod


class DBConnector(ABC):
    def __init__(self, conn_info):
        """conn_info : dict avec au moins 'engine', plus selon le
        moteur — host/port/username/password/database_name (postgres,
        mysql) ou file_path (sqlite)."""
        self.conn_info = conn_info

    @abstractmethod
    def test_connection(self):
        """Renvoie (True, message) si la connexion réussit, (False,
        message d'erreur) sinon — ne lève jamais d'exception, c'est le
        seul endroit où les erreurs de connexion doivent être
        systématiquement attrapées à la source plutôt que dans app.py,
        puisque c'est explicitement un test de robustesse."""
        raise NotImplementedError

    @abstractmethod
    def list_databases(self):
        """Liste des bases accessibles sur ce serveur. Pour SQLite
        (un fichier = une base), renvoie une liste à un seul élément
        (le nom du fichier) — jamais une liste vide, pour rester
        cohérent avec l'usage (sélectionner une base) côté interface."""
        raise NotImplementedError

    @abstractmethod
    def list_tables(self, database=None):
        """Liste des tables (et vues) de la base indiquée -- ou de la
        base par défaut de la connexion si `database` est None."""
        raise NotImplementedError

    @abstractmethod
    def get_table_columns(self, table, database=None):
        """Liste de dicts {name, type, nullable, primary_key} pour
        chaque colonne de `table`, dans l'ordre du schéma."""
        raise NotImplementedError

    @abstractmethod
    def browse_rows(self, table, database=None, limit=50, offset=0):
        """Dict {columns: [...], rows: [[...], ...], total_count: N}
        -- total_count via un COUNT(*) séparé, pour une vraie
        pagination côté interface plutôt qu'un simple "encore une
        page ?" approximatif."""
        raise NotImplementedError

    @abstractmethod
    def execute_sql(self, sql, database=None):
        """Exécute du SQL libre (SELECT ou non). Renvoie
        {columns: [...], rows: [...], row_count: N} pour un SELECT,
        {affected_rows: N} pour un INSERT/UPDATE/DELETE/DDL. Peut
        lever l'exception native du driver -- app.py la traduit."""
        raise NotImplementedError

    @abstractmethod
    def update_row(self, table, pk_column, pk_value, updates, database=None):
        """Met à jour UNE ligne, identifiée par pk_column=pk_value --
        `updates` : {colonne: nouvelle_valeur}. Requête TOUJOURS
        paramétrée pour les valeurs (jamais d'interpolation directe,
        contrairement à execute_sql qui exécute du SQL déjà écrit par
        la personne) -- seuls les NOMS (table/colonnes/clé primaire)
        sont interpolés via l'échappement d'identifiant du dialecte,
        jamais les valeurs elles-mêmes. Renvoie le nombre de lignes
        affectées (0 = ligne introuvable entre-temps, jamais une
        exception pour ce cas normal -- l'appelant décide quoi en
        faire)."""
        raise NotImplementedError

    @abstractmethod
    def insert_row(self, table, values, pk_column=None, database=None):
        """Insère UNE nouvelle ligne -- `values` : {colonne: valeur},
        jamais la clé primaire (auto-générée par le SGBD dans le cas
        courant -- une clé primaire fournie explicitement resterait
        possible côté appelant si un jour nécessaire, mais l'usage
        prévu ici est un formulaire d'ajout où elle est absente).
        `pk_column` optionnel -- nécessaire côté PostgreSQL
        (`RETURNING`, pas de `lastrowid` natif comme SQLite/MySQL)
        pour connaître la nouvelle clé, ignoré ailleurs. Requête
        toujours paramétrée pour les valeurs. Renvoie la nouvelle clé
        primaire si le driver la connaît, sinon None -- jamais une
        exception pour ce cas, l'appelant recharge la page au besoin
        plutôt que de dépendre de cette valeur."""
        raise NotImplementedError

    @abstractmethod
    def delete_rows(self, table, pk_column, pk_values, database=None):
        """Supprime PLUSIEURS lignes d'un coup, identifiées par
        pk_column IN (pk_values) -- demandé explicitement (sélection
        multiple, opérations en lot). Requête toujours paramétrée.
        Renvoie le nombre de lignes réellement supprimées (peut être
        inférieur à len(pk_values) si certaines avaient déjà disparu
        entre-temps -- jamais une exception pour ce cas normal)."""
        raise NotImplementedError

    @abstractmethod
    def add_column(self, table, column_name, column_type, nullable=True, database=None):
        """Ajoute une colonne à une table existante -- demandé
        explicitement (modification de schéma). `column_type` : type
        SQL brut du dialecte cible (ex. "VARCHAR(200)", "INTEGER") --
        jamais interprété/traduit par ce connecteur, la personne
        écrit le type dans le vocabulaire du moteur qu'elle connaît
        déjà. Nom de colonne/table via l'échappement d'identifiant du
        dialecte, jamais une valeur paramétrable ici (DDL, pas DML --
        aucun driver ne supporte les noms en paramètres liés)."""
        raise NotImplementedError

    @abstractmethod
    def drop_column(self, table, column_name, database=None):
        """Supprime une colonne -- syntaxe standard disponible dans
        les trois moteurs (SQLite depuis 3.35.0/2021, vérifié présent
        dans l'image utilisée ici)."""
        raise NotImplementedError

    @abstractmethod
    def rename_column(self, table, old_name, new_name, database=None):
        """Renomme une colonne -- syntaxe standard disponible dans
        les trois moteurs (SQLite depuis 3.25.0/2018)."""
        raise NotImplementedError

    @abstractmethod
    def modify_column(self, table, column_name, new_type=None, nullable=None, database=None):
        """Modifie le TYPE et/ou la NULLABILITÉ d'une colonne
        existante -- `new_type`/`nullable` chacun optionnel (fournir
        l'un, l'autre, ou les deux). SQLite : PAS DE SUPPORT NATIF
        (aucun ALTER COLUMN, contrairement à MySQL/Postgres) -- lève
        une NotImplementedError explicite plutôt qu'une tentative de
        reconstruction de table (CREATE + COPY + DROP + RENAME),
        jugée disproportionnée pour ce qui reste une évolution
        mineure ; à faire à la main via la console SQL si vraiment
        nécessaire sur SQLite."""
        raise NotImplementedError
