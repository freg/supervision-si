"""
API du module tickets — indépendant, même principe dual-backend que
pixel-grid (DB_BACKEND=sqlite|postgres).

Pipeline d'import calendrier : ICS (upload ou URL secrète Google) ->
parse_ics() -> pour chaque événement nouveau (uid inconnu), applique
les règles de filtrage actives (par priorité) -> rattache à un ticket
existant ou en crée un, avec un segment de temps (ticket_time_entries).
"""
import json
import logging
import os
import re
import sqlite3
import threading
import time
from datetime import datetime, timezone

import requests
from flask import Flask, jsonify, request, redirect
from flask_cors import CORS

from ics_parser import parse_ics
from filter_engine import apply_rules_to_event
from suggestion_engine import suggest_candidates, event_matches_any_pattern, extract_significant_words, analyze_title_matches, strip_accents
from nlp_helper import best_candidate_name, mine_candidate_identifiers
import google_oauth
from safe_json import safe_json
import secrets
import backup_manager
import db_explorer
import sql_console
# Import DÉFENSIF -- version_endpoint.py n'existe que dans le
# conteneur Docker réel (copié depuis shared/ au build, comme
# theme.css/preferences.js pour les fronts). Sans ce garde, tout
# test qui importe ce module directement (sans passer par le build
# complet) casserait au chargement -- bug réel rencontré : plusieurs
# harnais de test existants, sans rapport avec /version, important
# app.py directement.
try:
    from version_endpoint import register_version_route
except ImportError:
    register_version_route = None

app = Flask(__name__)
CORS(app)
if register_version_route:
    register_version_route(app, "tickets-api")

_log = logging.getLogger("tickets_app")

# Branchement rights-api -- livraison #324, item 38 du backlog,
# GROS CHANTIER (85 routes) -- traité en PLUSIEURS PASSES distinctes,
# jamais d'un coup, chaque passe testée et documentée séparément.
# PREMIÈRE PASSE (#324) : le cluster console DB/SQL -- de loin le
# plus dangereux du module (comparable ou supérieur à dba-api /sql,
# déjà signalé "particulièrement sensible" dans ce projet) --
# restauration de sauvegarde (VIDE la base actuelle), édition brute
# de n'importe quelle ligne de n'importe quelle table (bypass toute
# validation métier), exécution SQL arbitraire (SELECT comme
# DROP/DELETE/UPDATE). Gardé : POST /backups, POST
# /backups/<file>/restore, PUT /db/tables/<table>/rows/<id>, POST
# /db/sql/execute. JAMAIS /db/sql/check -- confirmé PUREMENT lecture
# dans son propre commentaire (EXPLAIN, rollback systématique,
# "vérifié empiriquement"), ni aucune route GET de ce cluster
# (/db/tables, /db/tables/<t>/columns, /db/relationships,
# /db/tables/<t>/rows).
RIGHTS_API_URL = os.environ.get("RIGHTS_API_URL", "").rstrip("/") or None


def _check_manage_right(body):
    """Même motif FAIL CLOSED que les branchements précédents
    (#289-292, #308-321) -- jamais fail-open, y compris pour
    admin_hub si rights-api est injoignable."""
    if not RIGHTS_API_URL:
        return True, None
    groups = body.get("groups") or []
    try:
        resp = requests.post(
            f"{RIGHTS_API_URL}/check",
            json={"groups": groups, "resource_type": "tickets-api", "resource_id": None, "action": "manage"},
            timeout=5,
        )
    except requests.RequestException as exc:
        _log.debug("_check_manage_right : rights-api injoignable, refus par prudence -- %s", exc)
        return False, "service de droits injoignable -- action refusée par prudence"
    if resp.status_code != 200:
        _log.debug("_check_manage_right : rights-api a répondu %s", resp.status_code)
        return False, "service de droits indisponible -- action refusée par prudence"
    try:
        allowed = resp.json().get("allowed", False)
    except ValueError:
        return False, "réponse du service de droits illisible -- action refusée par prudence"
    if not allowed:
        _log.debug("_check_manage_right : refusé pour les groupes %s", groups)
    return allowed, None if allowed else "droit 'manage' sur tickets-api requis (groupe admin_hub, ou un octroi explicite)"

DB_BACKEND = os.environ.get("DB_BACKEND", "sqlite").strip().lower()
DB_PATH = os.environ.get("TICKETS_DB_PATH", "/data/tickets.db")

if DB_BACKEND == "postgres":
    import psycopg2
    PG_CONFIG = {
        "host": os.environ.get("PGHOST", "localhost"),
        "port": os.environ.get("PGPORT", "6544"),
        "user": os.environ.get("PGUSER", "tickets"),
        "password": os.environ.get("PGPASSWORD", "tickets"),
        "dbname": os.environ.get("PGDATABASE", "tickets"),
    }
    PLACEHOLDER = "%s"
else:
    PLACEHOLDER = "?"

# Sauvegarde/restauration versionnée -- voir backup_manager.py pour le
# raisonnement complet. Sous-dossier du MÊME volume déjà monté pour
# tickets.db (TICKETS_DATA_DIR) -- jamais un nouveau montage séparé,
# survit aux mêmes redéploiements que la base elle-même.
BACKUP_DIR = os.path.join(os.path.dirname(DB_PATH) if DB_BACKEND != "postgres" else "/data", "backups")
BACKUP_RETENTION_COUNT = int(os.environ.get("TICKETS_BACKUP_RETENTION_COUNT", "30"))
BACKUP_PERIODIC_INTERVAL_HOURS = float(os.environ.get("TICKETS_BACKUP_PERIODIC_INTERVAL_HOURS", "24"))


def run_backup(trigger):
    """Point d'entrée unique appelé par les routes ET le thread
    périodique -- jamais deux façons différentes de construire les
    paramètres de backup_manager.create_backup()."""
    return backup_manager.create_backup(
        BACKUP_DIR, trigger, DB_BACKEND,
        db_path=DB_PATH if DB_BACKEND != "postgres" else None,
        pg_config=PG_CONFIG if DB_BACKEND == "postgres" else None,
        retention_count=BACKUP_RETENTION_COUNT,
    )


def get_connection():
    if DB_BACKEND == "postgres":
        return psycopg2.connect(**PG_CONFIG)
    conn = sqlite3.connect(DB_PATH)
    # SQLite n'applique PAS les contraintes de clé étrangère par défaut
    # (contrairement à PostgreSQL) — sans ce PRAGMA, DELETE sur une ligne
    # référencée ailleurs réussirait silencieusement et laisserait des
    # références orphelines. Un vrai bug trouvé en testant.
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# Schéma SQLite intégré ici (copie de tickets/data-generator/schema.sql,
# à garder synchronisée) — le backend postgres, lui, applique
# automatiquement schema.postgres.sql au premier démarrage via
# /docker-entrypoint-initdb.d/ (pas besoin de ce mécanisme côté API).
# Sans cette auto-initialisation, un tout premier démarrage sur SQLite
# se retrouve avec un fichier .db vide et AUCUNE table — bug réel signalé.
SQLITE_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    login TEXT UNIQUE NOT NULL,
    name TEXT,
    email TEXT,
    group_name TEXT,
    -- Profil portail : 'admin' | 'demandeur' | 'technicien' | 'politique'.
    -- Les demandeurs historiques (module interne) restent 'demandeur'.
    role TEXT NOT NULL DEFAULT 'demandeur'
);

CREATE TABLE IF NOT EXISTS types (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    label TEXT UNIQUE NOT NULL
);

-- Sites -- demandé explicitement, table de référence pour l'import en
-- masse depuis un fichier texte (un site par ligne) et le nouveau
-- champ tickets.site_id (voir ensure_site_column()). UNIQUE, même
-- raisonnement que types.label : l'import déduplique naturellement
-- via cette contrainte plutôt qu'une vérification applicative séparée.
CREATE TABLE IF NOT EXISTS sites (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    label TEXT UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS levels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    label TEXT NOT NULL,
    rank INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS statuts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    label TEXT NOT NULL,
    description TEXT
);

CREATE TABLE IF NOT EXISTS tickets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER REFERENCES users(id),
    subject TEXT NOT NULL,
    type_id INTEGER REFERENCES types(id),
    description TEXT,
    level_id INTEGER REFERENCES levels(id),
    ts_created INTEGER NOT NULL,
    ts_closed INTEGER,
    last_change INTEGER NOT NULL,
    statut_id INTEGER REFERENCES statuts(id),
    source_type TEXT,
    source_nom TEXT,
    -- Sous-demande (portail) : ticket enfant rattaché à un ticket parent.
    -- Un ticket enfant reste un ticket normal partout ailleurs.
    parent_ticket_id INTEGER REFERENCES tickets(id),
    -- "Suppression" admin (portail) : jamais un vrai DELETE, juste un
    -- masquage réversible des vues normales — voir ensure_archived_column().
    archived_at INTEGER
);

CREATE TABLE IF NOT EXISTS calendar_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uid TEXT UNIQUE NOT NULL,
    summary TEXT,
    description TEXT,
    start_ts INTEGER NOT NULL,
    end_ts INTEGER,
    source TEXT NOT NULL,
    imported_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ticket_time_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id INTEGER NOT NULL REFERENCES tickets(id),
    calendar_event_id INTEGER REFERENCES calendar_events(id),
    start_ts INTEGER NOT NULL,
    end_ts INTEGER NOT NULL,
    weight REAL NOT NULL DEFAULT 1.0,
    -- Attribution par technicien -- backlog (timeline personnelle),
    -- livraison #115. Login LDAP/Keycloak (même identifiant que
    -- partout ailleurs dans ce module), PAS de FK vers users.id --
    -- même raisonnement que collections.created_by côté coffre-fort :
    -- rester lisible même si le compte est un jour supprimé. NULL par
    -- défaut -- toujours le cas pour les segments importés depuis un
    -- calendrier (le connecteur OAuth/ICS est actuellement "mono-
    -- opérateur", jamais rattaché à un technicien précis -- voir
    -- calendar_import_upload/oauth_google_start) et pour tout segment
    -- créé avant ce chantier -- jamais une valeur inventée.
    technician_login TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS matching_config (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
INSERT OR IGNORE INTO matching_config (key, value) VALUES ('trigger_keyword', 'SAV');

CREATE TABLE IF NOT EXISTS calendar_filter_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    label TEXT NOT NULL,
    pattern TEXT NOT NULL,
    target_field TEXT NOT NULL DEFAULT 'summary',
    action TEXT NOT NULL DEFAULT 'both',
    ticket_ref_group TEXT,
    default_type_id INTEGER REFERENCES types(id),
    default_level_id INTEGER REFERENCES levels(id),
    default_user_id INTEGER REFERENCES users(id),
    priority INTEGER NOT NULL DEFAULT 0,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Liste d'exclusion : un événement qui matche l'un de ces motifs
-- (même s'il matche par ailleurs le mot-clé déclencheur) n'est JAMAIS
-- considéré comme un ticket potentiel — véto, pas juste une priorité
-- plus basse. Utile pour une réunion récurrente qui mentionne "SAV"
-- dans son titre sans être elle-même un ticket.
CREATE TABLE IF NOT EXISTS exclusion_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    label TEXT NOT NULL,
    pattern TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);

-- Jetons OAuth2 (Google Calendar pour l'instant, provider distingue si
-- d'autres s'ajoutent plus tard). Une seule ligne par provider.
CREATE TABLE IF NOT EXISTS oauth_credentials (
    provider TEXT PRIMARY KEY,
    refresh_token TEXT NOT NULL,
    access_token TEXT,
    access_token_expires_at INTEGER,
    updated_at TEXT NOT NULL
);

-- Mots-clés d'urgence — booste le tri (mode "urgence") sans jamais
-- exclure ni décider automatiquement, juste une aide au classement
-- visuel dans la revue.
CREATE TABLE IF NOT EXISTS priority_keywords (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    label TEXT NOT NULL,
    pattern TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);
INSERT OR IGNORE INTO priority_keywords (id, label, pattern, active, created_at) VALUES
    (1, 'Urgent', 'urgen(t|ce)', 1, '2026-01-01T00:00:00Z'),
    (2, 'Critique', 'critique', 1, '2026-01-01T00:00:00Z'),
    (3, 'Panne', 'panne', 1, '2026-01-01T00:00:00Z'),
    (4, 'Cassé/HS', 'cass[ée]|hors service|\\bhs\\b', 1, '2026-01-01T00:00:00Z'),
    (5, 'Bloquant', 'bloqu(ant|é)', 1, '2026-01-01T00:00:00Z');

-- Escalade automatique par deadline — indépendante du niveau
-- d'urgence initial du ticket (tickets.deadline_ts, ajoutée par
-- ensure_deadline_column()) : à mesure que l'échéance approche, le
-- niveau du ticket peut MONTER (jamais descendre) vers target_level_id
-- si le temps restant passe sous threshold_hours. Plusieurs seuils
-- possibles (ex. 48h -> Urgent, 4h -> Bloquant) ; le seuil franchi le
-- plus urgent (rang de niveau le plus élevé) l'emporte à chaque
-- évaluation. Voir apply_deadline_escalations().
CREATE TABLE IF NOT EXISTS deadline_escalation_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    threshold_hours INTEGER NOT NULL,
    target_level_id INTEGER NOT NULL REFERENCES levels(id),
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);

-- Historique ouverture/fermeture — le champ ts_closed seul ne dit pas
-- COMBIEN de fois un ticket a été rouvert, juste son état actuel.
-- Journalisé à chaque transition détectée sur ts_closed (voir
-- create_ticket / update_ticket).
CREATE TABLE IF NOT EXISTS ticket_status_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id INTEGER NOT NULL REFERENCES tickets(id),
    event_type TEXT NOT NULL,  -- 'opened' | 'closed' | 'reopened'
    ts INTEGER NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_status_log_ticket ON ticket_status_log (ticket_id);

-- Fil de discussion par ticket (portail) — sert à la fois de forum
-- (questions du demandeur) et de chat demandeur <-> technicien. Un seul
-- fil chronologique par ticket, l'auteur porte le rôle via users.role.
CREATE TABLE IF NOT EXISTS ticket_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id INTEGER NOT NULL REFERENCES tickets(id),
    user_id INTEGER REFERENCES users(id),
    body TEXT NOT NULL,
    created_ts INTEGER NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_messages_ticket ON ticket_messages (ticket_id);

CREATE INDEX IF NOT EXISTS idx_tickets_statut ON tickets (statut_id);
CREATE INDEX IF NOT EXISTS idx_tickets_level ON tickets (level_id);
CREATE INDEX IF NOT EXISTS idx_time_entries_ticket ON ticket_time_entries (ticket_id);
CREATE INDEX IF NOT EXISTS idx_calendar_events_ts ON calendar_events (start_ts);
"""


def ensure_schema():
    """Auto-initialisation — seul le backend SQLite en a besoin ici
    (postgres applique déjà schema.postgres.sql au premier démarrage
    du conteneur pixel-grid-postgres-like tickets-postgres)."""
    if DB_BACKEND != "sqlite":
        return
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.executescript(SQLITE_SCHEMA)
        conn.commit()
    finally:
        conn.close()


def ensure_weight_column():
    """
    Migration douce : les bases créées avant l'ajout de la colonne
    'weight' (répartition n événements -> m tickets) ne l'ont pas —
    l'ajoute si absente, sans jamais faire échouer le démarrage.
    """
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("ALTER TABLE ticket_time_entries ADD COLUMN weight REAL NOT NULL DEFAULT 1.0")
        conn.commit()
    except Exception:
        conn.rollback()
    finally:
        conn.close()


def ensure_technician_login_column():
    """
    Migration douce : les bases créées avant l'attribution par
    technicien (backlog, livraison #115) n'ont pas la colonne
    technician_login sur ticket_time_entries -- l'ajoute si absente,
    même patron que ensure_weight_column ci-dessus (ALTER TABLE
    fonctionne identiquement sur les deux backends via get_connection,
    l'exception "colonne déjà existante" est simplement absorbée).
    """
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("ALTER TABLE ticket_time_entries ADD COLUMN technician_login TEXT")
        conn.commit()
    except Exception:
        conn.rollback()
    finally:
        conn.close()


def ensure_matching_config():
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(f"SELECT 1 FROM matching_config WHERE key = {PLACEHOLDER}", ["trigger_keyword"])
        if cur.fetchone() is None:
            cur.execute(
                f"INSERT INTO matching_config (key, value) VALUES ({PLACEHOLDER}, {PLACEHOLDER})",
                ["trigger_keyword", "SAV"],
            )
            conn.commit()
    except Exception:
        conn.rollback()
    finally:
        conn.close()


VALID_ROLES = ("admin", "demandeur", "technicien", "politique")


def ensure_role_column():
    """
    Migration douce : les bases créées avant le portail n'ont pas la
    colonne users.role — l'ajoute avec 'demandeur' par défaut (le sens
    historique de cette table : les demandeurs des tickets).
    """
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'demandeur'")
        conn.commit()
    except Exception:
        conn.rollback()
    finally:
        conn.close()


def ensure_parent_ticket_column():
    """Migration douce : tickets.parent_ticket_id (sous-demandes portail)."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("ALTER TABLE tickets ADD COLUMN parent_ticket_id INTEGER REFERENCES tickets(id)")
        conn.commit()
    except Exception:
        conn.rollback()
    finally:
        conn.close()


def ensure_archived_column():
    """Migration douce : tickets.archived_at — "suppression" côté
    portail admin, au sens décidé avec la personne : rien n'est jamais
    vraiment effacé, un ticket archivé est juste masqué des vues
    normales (/queue exclut archived_at IS NOT NULL par défaut) et
    reste réversible (désarchivage = remettre à NULL, même mécanique
    que ts_closed pour la fermeture/réouverture)."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("ALTER TABLE tickets ADD COLUMN archived_at INTEGER")
        conn.commit()
    except Exception:
        conn.rollback()
    finally:
        conn.close()


def ensure_acted_by_column():
    """Migration douce : tickets.acted_by_user_id et
    ticket_messages.acted_by_user_id — "pour le compte de" (personnel
    qui saisit à la place d'un demandeur, ex. appel téléphonique).
    user_id reste le PROPRIÉTAIRE (le ticket/message apparaît comme
    normalement chez le demandeur) ; acted_by_user_id, quand renseigné,
    trace qui l'a RÉELLEMENT saisi — jamais un remplacement de user_id,
    toujours une trace additionnelle. NULL = saisi par le propriétaire
    lui-même, le cas normal, l'immense majorité des lignes."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("ALTER TABLE tickets ADD COLUMN acted_by_user_id INTEGER")
        conn.commit()
    except Exception:
        conn.rollback()
    finally:
        conn.close()
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("ALTER TABLE ticket_messages ADD COLUMN acted_by_user_id INTEGER")
        conn.commit()
    except Exception:
        conn.rollback()
    finally:
        conn.close()


def ensure_deadline_column():
    """Migration douce : tickets.deadline_ts — échéance optionnelle,
    indépendante du niveau d'urgence initial. Voir
    apply_deadline_escalations() pour la montée automatique de niveau
    à mesure que l'échéance approche."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("ALTER TABLE tickets ADD COLUMN deadline_ts INTEGER")
        conn.commit()
    except Exception:
        conn.rollback()
    finally:
        conn.close()


def ensure_statut_type_column():
    """Migration douce : statuts.type -- catégorise UNIQUEMENT les
    statuts représentant un travail ACTIF (en_cours/en_pause/
    en_attente, voir tickets/README.md pour le raisonnement complet
    -- décidé avec la personne après plusieurs allers-retours). Les
    statuts de clôture (résolu/livré/abandonné...) n'ont
    délibérément PAS de type -- ils accompagnent la fermeture
    manuelle (ts_closed), jamais un remplacement de ce mécanisme déjà
    existant et testé (fermeture/réouverture avec historique). NULL =
    statut non catégorisé (le cas normal pour tout statut de
    clôture, ou tant qu'un admin n'a pas encore configuré celui-ci)."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("ALTER TABLE statuts ADD COLUMN type TEXT")
        conn.commit()
    except Exception:
        conn.rollback()
    finally:
        conn.close()


def ensure_pending_validation_column():
    """Migration douce : tickets.pending_validation -- livraison
    #273, demandé explicitement : "branche la création auto [de
    ticket depuis un événement calendrier], ajoute un écran de
    validation des tickets automatique". 0 (défaut) pour TOUT ticket
    créé par les voies normales (jamais touché par cette migration
    pour l'existant) ; 1 UNIQUEMENT pour un ticket créé
    automatiquement depuis /calendar/create_ticket, en attente de
    confirmation humaine avant d'être traité comme un ticket
    pleinement réel -- même esprit que le moteur de suggestion
    (suggestion_engine.py) : jamais d'exécution automatique
    silencieuse, la décision finale reste humaine."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("ALTER TABLE tickets ADD COLUMN pending_validation INTEGER DEFAULT 0")
        conn.commit()
    except Exception:
        conn.rollback()
    finally:
        conn.close()


CALENDAR_STATUTS = [
    # (label, type) -- type=None pour un statut de clôture (même
    # convention que create_statut()/VALID_STATUT_TYPES ci-dessous).
    ("Clos", None),
    ("En cours", "en_cours"),
    ("Planifié", "en_attente"),
]


def ensure_calendar_statuts():
    """Migration douce -- livraison #284, demandé explicitement :
    statut automatique selon le moment de l'événement calendrier
    source ("Clos"/"En cours"/"Planifié" -- créés SI NÉCESSAIRE,
    jamais en double si déjà présents sous ce libellé exact,
    jamais un doublon créé à chaque redémarrage)."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT label FROM statuts")
        existing = {row[0] for row in cur.fetchall()}
        for label, statut_type in CALENDAR_STATUTS:
            if label not in existing:
                cur.execute(
                    f"INSERT INTO statuts (label, description, type) VALUES ({PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER})",
                    [label, "Créé automatiquement (#284, statut selon événement calendrier source)", statut_type],
                )
        conn.commit()
    except Exception:
        conn.rollback()
    finally:
        conn.close()


def ensure_status_changes_table():
    """Migration douce -- livraison #284, demandé explicitement :
    "les changements de statut doivent être loggés et ouvrir une
    fenêtre de validation... les historiques et les logs sont
    permanents". Table DISTINCTE de `ticket_status_log` (déjà
    existante, #… -- portée différente et déjà utilisée ailleurs :
    seulement 3 event_type fixes 'opened'/'closed'/'reopened', pour
    des métriques précises comme le compte de réouvertures -- jamais
    détournée ici pour un usage différent). `ticket_status_changes`
    trace CHAQUE changement (ancien statut -> nouveau), avec
    `validated_at` NULL tant qu'il n'est pas passé par la fenêtre de
    validation groupée -- jamais supprimée après validation (demandé
    explicitement : permanent), seulement marquée comme validée."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS ticket_status_changes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id INTEGER NOT NULL REFERENCES tickets(id),
                old_statut_id INTEGER REFERENCES statuts(id),
                new_statut_id INTEGER REFERENCES statuts(id),
                reason TEXT,
                changed_by TEXT,
                changed_at TEXT NOT NULL,
                validated_at TEXT
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_status_changes_ticket ON ticket_status_changes(ticket_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_status_changes_pending ON ticket_status_changes(validated_at)")
        conn.commit()
    except Exception:
        conn.rollback()
    finally:
        conn.close()


def ensure_first_in_progress_column():
    """Migration douce : tickets.first_in_progress_ts -- horodatage de
    la "prise en charge", posé UNE SEULE FOIS (la première fois qu'un
    ticket passe à un statut de type "en_cours", voir
    statuts.type ci-dessus), jamais réécrit ensuite même si le statut
    change à nouveau plus tard. Perspective 2 du "élastique de temps"
    (voir hub/src/settingsClient.js) -- temps depuis la prise en
    charge, jusqu'ici en attente faute de ce signal fiable."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("ALTER TABLE tickets ADD COLUMN first_in_progress_ts INTEGER")
        conn.commit()
    except Exception:
        conn.rollback()
    finally:
        conn.close()


def ensure_site_column():
    """Migration douce : tickets.site_id -- demandé explicitement,
    référence vers la nouvelle table sites (voir SQLITE_SCHEMA/
    schema.postgres.sql). La TABLE sites elle-même est créée via
    CREATE TABLE IF NOT EXISTS (ensure_schema, ré-exécuté à chaque
    démarrage en SQLite) -- cette migration-ci ne concerne que la
    COLONNE sur tickets, qui existe déjà et ne serait donc jamais
    retouchée par un simple CREATE TABLE IF NOT EXISTS."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("ALTER TABLE tickets ADD COLUMN site_id INTEGER")
        conn.commit()
    except Exception:
        conn.rollback()
    finally:
        conn.close()


def apply_deadline_escalations():
    """Fait MONTER le niveau d'urgence des tickets dont la deadline
    approche, selon les seuils configurés (deadline_escalation_rules)
    — ne descend JAMAIS un niveau déjà supérieur (une urgence déjà
    justifiée autrement, manuellement ou via mots-clés, n'est jamais
    rabaissée par ce mécanisme). Appelée au début de /queue (déjà
    interrogée en boucle par la vue technicien) plutôt qu'une tâche de
    fond séparée — le volume de tickets de ce projet rend ce coût
    négligeable à chaque appel."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT threshold_hours, target_level_id FROM deadline_escalation_rules WHERE active = 1")
        rules = cur.fetchall()
        if not rules:
            return

        cur.execute("SELECT id, rank FROM levels")
        rank_by_level = {row[0]: row[1] for row in cur.fetchall()}
        resolved_rules = [(r[0], r[1], rank_by_level.get(r[1], -1)) for r in rules]

        now = now_ts()
        cur.execute(
            "SELECT id, level_id, deadline_ts FROM tickets WHERE deadline_ts IS NOT NULL AND ts_closed IS NULL"
        )
        rows = cur.fetchall()
        for ticket_id, level_id, deadline_ts in rows:
            if deadline_ts is None:
                continue
            hours_remaining = (deadline_ts - now) / 3600.0
            current_rank = rank_by_level.get(level_id, -1)
            # Parmi les règles dont le seuil est franchi (échéance assez
            # proche), la plus urgente (rang de niveau le plus élevé) l'emporte.
            applicable = [r for r in resolved_rules if hours_remaining <= r[0]]
            if not applicable:
                continue
            best = max(applicable, key=lambda r: r[2])
            if best[2] > current_rank:
                cur.execute(
                    f"UPDATE tickets SET level_id = {PLACEHOLDER}, last_change = {PLACEHOLDER} WHERE id = {PLACEHOLDER}",
                    [best[1], now, ticket_id],
                )
        conn.commit()
    finally:
        conn.close()


def ensure_admin_user():
    """
    Amorçage du portail : s'il n'existe AUCUN utilisateur de rôle
    'admin', en crée un (login 'admin') — sinon impossible d'accéder à
    la vue d'administration au tout premier lancement. Si un login
    'admin' existe déjà avec un autre rôle, on n'y touche PAS (pas
    d'action automatique silencieuse sur des données existantes — le
    rôle se change explicitement via la gestion des utilisateurs).
    """
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(f"SELECT 1 FROM users WHERE role = {PLACEHOLDER} LIMIT 1", ["admin"])
        if cur.fetchone() is not None:
            return
        cur.execute(f"SELECT 1 FROM users WHERE login = {PLACEHOLDER}", ["admin"])
        if cur.fetchone() is not None:
            return
        cur.execute(
            f"INSERT INTO users (login, name, role) VALUES ({PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER})",
            ["admin", "Administrateur", "admin"],
        )
        conn.commit()
    except Exception:
        conn.rollback()
    finally:
        conn.close()


try:
    ensure_schema()
    ensure_weight_column()
    ensure_technician_login_column()
    ensure_matching_config()
    ensure_role_column()
    ensure_parent_ticket_column()
    ensure_archived_column()
    ensure_acted_by_column()
    ensure_deadline_column()
    ensure_statut_type_column()
    ensure_first_in_progress_column()
    ensure_pending_validation_column()
    ensure_site_column()
    ensure_calendar_statuts()
    ensure_status_changes_table()
    ensure_admin_user()
except Exception as exc:  # noqa: BLE001 — la base peut ne pas être prête au tout premier démarrage
    app.logger.warning("Migration au démarrage reportée : %s", exc)


def compute_keyword_matches(text, keyword_rules):
    """text : sujet+description concaténés d'un ticket. keyword_rules :
    [{label, pattern}] déjà filtrées sur active par l'appelant. Renvoie
    les libellés dont le pattern matche (recherche insensible à la
    casse, PAS ancrée — un mot-clé n'importe où dans le texte compte).
    Ne lève jamais : un pattern regex invalide (saisi par un humain via
    la gestion des mots-clés) est ignoré plutôt que de faire échouer
    tout le calcul de la file — même philosophie défensive que le reste
    du moteur de suggestion (event_matches_any_pattern)."""
    if not text:
        return []
    matches = []
    for rule in keyword_rules:
        try:
            if re.search(rule["pattern"], text, re.IGNORECASE):
                matches.append(rule["label"])
        except re.error:
            continue
    return matches


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def now_ts():
    return int(datetime.now(timezone.utc).timestamp())


def determine_calendar_statut_label(event_start_ts, event_end_ts, reference_ts):
    """Livraison #284, demandé explicitement -- statut selon le
    moment de l'événement calendrier source PAR RAPPORT à
    `reference_ts` (l'instant de création OU de consultation, au
    choix de l'appelant -- cette fonction reste PURE, jamais elle-même
    consciente de QUAND elle est appelée) :
    - événement déjà TERMINÉ à cet instant -> "Clos"
    - instant DANS la fenêtre [début, fin] -> "En cours"
    - événement pas encore commencé -> "Planifié"

    `event_end_ts` peut être None (événement sans heure de fin connue)
    -- repli sur `event_start_ts` comme fin effective, MÊME motif déjà
    établi ailleurs dans ce fichier (voir /calendar/assign,
    /calendar/create_ticket) plutôt qu'une nouvelle convention."""
    effective_end = event_end_ts if event_end_ts is not None else event_start_ts
    if reference_ts > effective_end:
        return "Clos"
    if reference_ts < event_start_ts:
        return "Planifié"
    return "En cours"


def row_to_dict(cur, row):
    columns = [desc[0] for desc in cur.description]
    return dict(zip(columns, row))


# ============================================================
# CRUD simple — users / types / levels / statuts
# ============================================================

def simple_list_endpoint(table, order_by="id"):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(f"SELECT * FROM {table} ORDER BY {order_by}")
        rows = cur.fetchall()
        return jsonify([row_to_dict(cur, r) for r in rows])
    finally:
        conn.close()


@app.route("/users", methods=["GET"])
def list_users():
    return simple_list_endpoint("users", "login")


@app.route("/users", methods=["POST"])
def create_user():
    """Protégée par rights-api (#325)."""
    body = request.get_json(silent=True) or {}
    allowed, error = _check_manage_right(body)
    if not allowed:
        return jsonify({"error": error}), 403
    role = body.get("role") or "demandeur"
    if role not in VALID_ROLES:
        return jsonify({"error": f"rôle invalide '{role}' (attendus : {list(VALID_ROLES)})"}), 400
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            f"INSERT INTO users (login, name, email, group_name, role) VALUES ({PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER})",
            [body.get("login"), body.get("name"), body.get("email"), body.get("group_name"), role],
        )
        conn.commit()
        new_id = cur.lastrowid if DB_BACKEND == "sqlite" else _pg_lastval(cur)
        return jsonify({"status": "ok", "id": new_id}), 201
    finally:
        conn.close()


# ------------------------------------------------------------------
# Import direct des membres d'un groupe Keycloak comme comptes locaux
# -- réutilise KEYCLOAK_SERVICE_CLIENT_ID/SECRET (livraison #361,
# compte de SERVICE de bootstrap -- voir keycloak/README.md pour le
# raisonnement complet du passage depuis l'utilisateur de bootstrap),
# joint Keycloak par son nom de service Docker interne (jamais via
# tls-proxy : trafic conteneur-à-conteneur, pas navigateur).
# ------------------------------------------------------------------
KEYCLOAK_INTERNAL_URL = os.environ.get("KEYCLOAK_INTERNAL_URL", "http://keycloak:8080/auth")
KEYCLOAK_REALM = os.environ.get("KEYCLOAK_REALM", "supervision-si")
KEYCLOAK_SERVICE_CLIENT_ID = os.environ.get("KEYCLOAK_SERVICE_CLIENT_ID", "supervision-si-service")
KEYCLOAK_SERVICE_CLIENT_SECRET = os.environ.get("KEYCLOAK_SERVICE_CLIENT_SECRET", "change-me")


def _keycloak_admin_token():
    """Jeton admin Keycloak (grant client_credentials, compte de
    service de bootstrap, realm master) — mêmes identifiants que
    keycloak-backup/backup-loop.sh et group_memberships.py, réutilisés
    ici plutôt que dupliqués dans une nouvelle variable."""
    resp = requests.post(
        f"{KEYCLOAK_INTERNAL_URL}/realms/master/protocol/openid-connect/token",
        data={
            "client_id": KEYCLOAK_SERVICE_CLIENT_ID,
            "client_secret": KEYCLOAK_SERVICE_CLIENT_SECRET,
            "grant_type": "client_credentials",
        },
        timeout=10,
    )
    resp.raise_for_status()
    return safe_json(resp, "authentification admin Keycloak")["access_token"]


def _keycloak_group_members(token, group_name):
    """Membres (représentation Keycloak brute) d'un groupe realm nommé
    `group_name` — lève ValueError si le groupe n'existe pas (jamais
    une KeyError/IndexError opaque plus loin). Deux appels : recherche
    du groupe par nom exact, puis liste de ses membres."""
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.get(
        f"{KEYCLOAK_INTERNAL_URL}/admin/realms/{KEYCLOAK_REALM}/groups",
        params={"search": group_name, "exact": "true"},
        headers=headers,
        timeout=10,
    )
    resp.raise_for_status()
    matching = [g for g in safe_json(resp, "recherche du groupe Keycloak") if g.get("name") == group_name]
    if not matching:
        raise ValueError(f"groupe Keycloak '{group_name}' introuvable")
    group_id = matching[0]["id"]

    resp = requests.get(
        f"{KEYCLOAK_INTERNAL_URL}/admin/realms/{KEYCLOAK_REALM}/groups/{group_id}/members",
        params={"max": 1000},
        headers=headers,
        timeout=10,
    )
    resp.raise_for_status()
    return safe_json(resp, "liste des membres du groupe Keycloak")


def _keycloak_member_to_user_fields(member):
    """Convertit une représentation Keycloak brute (dict JSON de
    l'API Admin) en (login, name, email) prêts pour l'insertion locale
    — pure, testable sans appel réseau. login = username Keycloak
    (l'attribut LDAP uid), JAMAIS l'email (voir keycloak/README.md :
    loginWithEmailAllowed=false, l'identifiant partout dans ce projet
    reste le nom d'utilisateur, pas l'email)."""
    login = (member.get("username") or "").strip()
    first = (member.get("firstName") or "").strip()
    last = (member.get("lastName") or "").strip()
    name = f"{first} {last}".strip() or None
    email = member.get("email") or None
    return login, name, email


@app.route("/users/import-keycloak-group", methods=["POST"])
def import_keycloak_group_users():
    """Importe les membres d'un groupe Keycloak (par défaut
    "demandeurs") comme comptes locaux role=demandeur — ignore les
    logins déjà présents localement (JAMAIS d'écrasement d'un compte
    existant, ex. un rôle déjà monté à la main par un admin, ou un
    compte devenu technicien depuis).

    Protégée par rights-api (#325)."""
    body = request.get_json(silent=True) or {}
    allowed, error = _check_manage_right(body)
    if not allowed:
        return jsonify({"error": error}), 403
    group_name = (body.get("group") or "demandeurs").strip()

    try:
        token = _keycloak_admin_token()
        members = _keycloak_group_members(token, group_name)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 404
    except requests.RequestException as exc:
        return jsonify({"error": f"Keycloak injoignable : {exc}"}), 502

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT login FROM users")
        existing_logins = {row[0].lower() for row in cur.fetchall() if row[0]}

        created, skipped = [], []
        for member in members:
            login, name, email = _keycloak_member_to_user_fields(member)
            if not login:
                continue
            if login.lower() in existing_logins:
                skipped.append(login)
                continue
            cur.execute(
                f"INSERT INTO users (login, name, email, group_name, role) VALUES ({PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER})",
                [login, name, email, group_name, "demandeur"],
            )
            created.append(login)
            existing_logins.add(login.lower())
        conn.commit()
        return jsonify({"created": created, "skipped": skipped, "total_in_group": len(members)}), 200
    finally:
        conn.close()


@app.route("/types", methods=["GET"])
def list_types():
    return simple_list_endpoint("types", "label")


@app.route("/types", methods=["POST"])
def create_type():
    """Protégée par rights-api (#325)."""
    body = request.get_json(silent=True) or {}
    allowed, error = _check_manage_right(body)
    if not allowed:
        return jsonify({"error": error}), 403
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(f"INSERT INTO types (label) VALUES ({PLACEHOLDER})", [body.get("label")])
        conn.commit()
        new_id = cur.lastrowid if DB_BACKEND == "sqlite" else _pg_lastval(cur)
        return jsonify({"status": "ok", "id": new_id}), 201
    finally:
        conn.close()


@app.route("/sites", methods=["GET"])
def list_sites():
    return simple_list_endpoint("sites", "label")


@app.route("/sites", methods=["POST"])
def create_site():
    """Protégée par rights-api (#325)."""
    body = request.get_json(silent=True) or {}
    allowed, error = _check_manage_right(body)
    if not allowed:
        return jsonify({"error": error}), 403
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(f"INSERT INTO sites (label) VALUES ({PLACEHOLDER})", [body.get("label")])
        conn.commit()
        new_id = cur.lastrowid if DB_BACKEND == "sqlite" else _pg_lastval(cur)
        return jsonify({"status": "ok", "id": new_id}), 201
    finally:
        conn.close()


def decode_uploaded_text(raw_bytes):
    """Décode un fichier texte uploadé en essayant plusieurs
    encodages dans l'ordre -- demandé explicitement, fichier français
    probablement créé sous Windows (CP1252/Latin-1), jamais garanti
    en UTF-8. UTF-8 essayé en premier (le plus courant aujourd'hui),
    puis CP1252 (surensemble de Latin-1, encodage Windows français le
    plus répandu), puis Latin-1 en dernier recours -- celui-ci ne
    lève JAMAIS d'erreur (accepte n'importe quel octet), donc toujours
    un résultat, même si le texte produit est imparfait pour un
    encodage vraiment exotique non prévu ici."""
    for encoding in ("utf-8", "cp1252", "latin-1"):
        try:
            return raw_bytes.decode(encoding), encoding
        except UnicodeDecodeError:
            continue
    return raw_bytes.decode("latin-1", errors="replace"), "latin-1 (avec octets remplacés)"


@app.route("/sites/import-text", methods=["POST"])
def import_sites_from_text():
    """Import en masse depuis un fichier texte -- un site par ligne,
    demandé explicitement. Déduplique via la contrainte UNIQUE sur
    sites.label (voir SQLITE_SCHEMA) -- une ligne déjà présente est
    silencieusement ignorée (comptée dans `skipped`), jamais une
    erreur qui interromprait tout l'import pour une seule ligne en
    double.

    Protégée par rights-api (#325) -- `groups` lu depuis
    `request.form` (multipart, jamais un corps JSON ici)."""
    allowed, error = _check_manage_right({"groups": request.form.getlist("groups")})
    if not allowed:
        return jsonify({"error": error}), 403
    if "file" not in request.files:
        return jsonify({"error": "fichier requis (champ 'file')"}), 400
    raw_bytes = request.files["file"].read()
    text, encoding_used = decode_uploaded_text(raw_bytes)

    lines = [line.strip() for line in text.splitlines()]
    labels = [line for line in lines if line]  # jamais les lignes vides

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT label FROM sites")
        existing = {row[0] for row in cur.fetchall()}

        created, skipped = [], []
        for label in labels:
            if label in existing:
                skipped.append(label)
                continue
            cur.execute(f"INSERT INTO sites (label) VALUES ({PLACEHOLDER})", [label])
            created.append(label)
            existing.add(label)
        conn.commit()
        return jsonify({
            "created": created, "skipped": skipped, "total_lines": len(labels),
            "encoding_used": encoding_used,
        }), 200
    finally:
        conn.close()


@app.route("/sites/<int:row_id>", methods=["PUT"])
def update_site(row_id):
    return update_reference_row("sites", row_id)


@app.route("/sites/<int:row_id>", methods=["DELETE"])
def delete_site(row_id):
    return delete_reference_row("sites", row_id)


@app.route("/levels", methods=["GET"])
def list_levels():
    return simple_list_endpoint("levels", "rank")


@app.route("/levels", methods=["POST"])
def create_level():
    """Protégée par rights-api (#325)."""
    body = request.get_json(silent=True) or {}
    allowed, error = _check_manage_right(body)
    if not allowed:
        return jsonify({"error": error}), 403
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            f"INSERT INTO levels (label, rank) VALUES ({PLACEHOLDER}, {PLACEHOLDER})",
            [body.get("label"), body.get("rank")],
        )
        conn.commit()
        new_id = cur.lastrowid if DB_BACKEND == "sqlite" else _pg_lastval(cur)
        return jsonify({"status": "ok", "id": new_id}), 201
    finally:
        conn.close()


@app.route("/deadline-escalation-rules", methods=["GET"])
def list_deadline_escalation_rules():
    """Enrichi du libellé du niveau cible — plus lisible côté
    interface qu'un simple target_level_id numérique."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """SELECT r.id, r.threshold_hours, r.target_level_id, r.active, r.created_at,
                      l.label AS target_level_label
               FROM deadline_escalation_rules r
               LEFT JOIN levels l ON l.id = r.target_level_id
               ORDER BY r.threshold_hours ASC"""
        )
        return jsonify([row_to_dict(cur, r) for r in cur.fetchall()]), 200
    finally:
        conn.close()


@app.route("/deadline-escalation-rules", methods=["POST"])
def create_deadline_escalation_rule():
    """Protégée par rights-api (#325)."""
    body = request.get_json(silent=True) or {}
    allowed, rights_error = _check_manage_right(body)
    if not allowed:
        return jsonify({"error": rights_error}), 403
    threshold_hours = body.get("threshold_hours")
    target_level_id = body.get("target_level_id")
    if threshold_hours is None or target_level_id is None:
        return jsonify({"error": "threshold_hours et target_level_id requis"}), 400
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(f"SELECT 1 FROM levels WHERE id = {PLACEHOLDER}", [target_level_id])
        if cur.fetchone() is None:
            return jsonify({"error": f"niveau {target_level_id} introuvable"}), 400
        cur.execute(
            f"""INSERT INTO deadline_escalation_rules (threshold_hours, target_level_id, active, created_at)
                VALUES ({PLACEHOLDER},{PLACEHOLDER},{PLACEHOLDER},{PLACEHOLDER})""",
            [threshold_hours, target_level_id, 1 if body.get("active", True) else 0, now_iso()],
        )
        conn.commit()
        new_id = cur.lastrowid if DB_BACKEND == "sqlite" else _pg_lastval(cur)
        return jsonify({"status": "ok", "id": new_id}), 201
    finally:
        conn.close()


@app.route("/deadline-escalation-rules/<int:row_id>", methods=["PUT"])
def update_deadline_escalation_rule(row_id):
    return update_reference_row("deadline_escalation_rules", row_id)


@app.route("/deadline-escalation-rules/<int:row_id>", methods=["DELETE"])
def delete_deadline_escalation_rule(row_id):
    return delete_reference_row("deadline_escalation_rules", row_id)


@app.route("/statuts", methods=["GET"])
def list_statuts():
    return simple_list_endpoint("statuts", "id")


@app.route("/statuts", methods=["POST"])
def create_statut():
    """Protégée par rights-api (#325)."""
    body = request.get_json(silent=True) or {}
    allowed, error = _check_manage_right(body)
    if not allowed:
        return jsonify({"error": error}), 403
    statut_type = body.get("type") or None
    if statut_type is not None and statut_type not in VALID_STATUT_TYPES:
        return jsonify({"error": f"type invalide (attendu : {', '.join(VALID_STATUT_TYPES)}, ou absent pour un statut de clôture)"}), 400
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            f"INSERT INTO statuts (label, description, type) VALUES ({PLACEHOLDER}, {PLACEHOLDER}, {PLACEHOLDER})",
            [body.get("label"), body.get("description"), statut_type],
        )
        conn.commit()
        new_id = cur.lastrowid if DB_BACKEND == "sqlite" else _pg_lastval(cur)
        return jsonify({"status": "ok", "id": new_id}), 201
    finally:
        conn.close()


# ============================================================
# Édition/suppression génériques des tables de référence — mêmes 4
# colonnes autorisées par table, pour l'onglet de gestion de la base.
# ============================================================
REFERENCE_TABLES = {
    "users": ["login", "name", "email", "group_name", "role"],
    "types": ["label"],
    "levels": ["label", "rank"],
    "statuts": ["label", "description", "type"],
    "sites": ["label"],
    "deadline_escalation_rules": ["threshold_hours", "target_level_id", "active"],
}

# Seules ces trois valeurs représentent un travail ACTIF -- voir
# ensure_statut_type_column() pour le raisonnement complet. Toute
# autre valeur (y compris None/absent) reste un statut non catégorisé,
# typiquement un statut de clôture (résolu/livré/abandonné...).
VALID_STATUT_TYPES = ("en_cours", "en_pause", "en_attente")


def update_reference_row(table, row_id, body=None):
    """`body` optionnel -- permet à un appelant (ex. update_statut) de
    fournir un corps déjà validé/normalisé, plutôt que de reparser
    request.get_json() une seconde fois avec le risque de diverger de
    ce qui a réellement été validé. Comportement par défaut inchangé
    pour tous les autres appelants (types/levels/users/règles
    d'escalade), qui continuent de fournir `None`.

    Protégée par rights-api (#325) -- une seule garde ici couvre les
    6 routes PUT qui passent par cette fonction commune (users/types/
    levels/statuts/sites/deadline_escalation_rules)."""
    if body is None:
        body = request.get_json(silent=True) or {}
    allowed, error = _check_manage_right(body)
    if not allowed:
        return jsonify({"error": error}), 403
    columns = REFERENCE_TABLES[table]
    fields_to_update = {k: v for k, v in body.items() if k in columns}
    if not fields_to_update:
        return jsonify({"error": f"aucun champ valide fourni (attendus : {columns})"}), 400

    set_clause = ", ".join(f"{col} = {PLACEHOLDER}" for col in fields_to_update)
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            f"UPDATE {table} SET {set_clause} WHERE id = {PLACEHOLDER}",
            [*fields_to_update.values(), row_id],
        )
        conn.commit()
        return jsonify({"status": "ok"}), 200
    finally:
        conn.close()


def delete_reference_row(table, row_id):
    """Protégée par rights-api (#325) -- une seule garde ici couvre
    les 6 routes DELETE qui passent par cette fonction commune."""
    body = request.get_json(silent=True) or {}
    allowed, error = _check_manage_right(body)
    if not allowed:
        return jsonify({"error": error}), 403
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(f"DELETE FROM {table} WHERE id = {PLACEHOLDER}", [row_id])
        conn.commit()
        return jsonify({"status": "ok"}), 200
    except Exception as exc:  # noqa: BLE001 — probable violation de clé étrangère
        conn.rollback()
        return jsonify({"error": f"suppression impossible, probablement encore référencé ailleurs : {exc}"}), 409
    finally:
        conn.close()


@app.route("/users/<int:row_id>", methods=["PUT"])
def update_user(row_id):
    return update_reference_row("users", row_id)


@app.route("/users/<int:row_id>", methods=["DELETE"])
def delete_user(row_id):
    return delete_reference_row("users", row_id)


@app.route("/types/<int:row_id>", methods=["PUT"])
def update_type(row_id):
    return update_reference_row("types", row_id)


@app.route("/types/<int:row_id>", methods=["DELETE"])
def delete_type(row_id):
    return delete_reference_row("types", row_id)


@app.route("/levels/<int:row_id>", methods=["PUT"])
def update_level(row_id):
    return update_reference_row("levels", row_id)


@app.route("/levels/<int:row_id>", methods=["DELETE"])
def delete_level(row_id):
    return delete_reference_row("levels", row_id)


@app.route("/statuts/<int:row_id>", methods=["PUT"])
def update_statut(row_id):
    body = request.get_json(silent=True) or {}
    if "type" in body:
        statut_type = body.get("type") or None  # normalise "" (select vide) -> None
        if statut_type is not None and statut_type not in VALID_STATUT_TYPES:
            return jsonify({"error": f"type invalide (attendu : {', '.join(VALID_STATUT_TYPES)}, ou absent pour un statut de clôture)"}), 400
        body = {**body, "type": statut_type}
    return update_reference_row("statuts", row_id, body=body)


@app.route("/statuts/<int:row_id>", methods=["DELETE"])
def delete_statut(row_id):
    return delete_reference_row("statuts", row_id)


# ============================================================
# Tickets
# ============================================================

@app.route("/tickets", methods=["POST"])
def create_ticket():
    body = request.get_json(silent=True) or {}
    ts = now_ts()
    parent_id = body.get("parent_ticket_id")
    conn = get_connection()
    try:
        cur = conn.cursor()
        if parent_id is not None:
            cur.execute(f"SELECT 1 FROM tickets WHERE id = {PLACEHOLDER}", [parent_id])
            if cur.fetchone() is None:
                return jsonify({"error": f"ticket parent {parent_id} introuvable"}), 400
        cur.execute(
            f"""INSERT INTO tickets
                (user_id, subject, type_id, description, level_id, ts_created, last_change, statut_id, source_type, source_nom, parent_ticket_id, acted_by_user_id, deadline_ts, site_id)
                VALUES ({PLACEHOLDER},{PLACEHOLDER},{PLACEHOLDER},{PLACEHOLDER},{PLACEHOLDER},{PLACEHOLDER},{PLACEHOLDER},{PLACEHOLDER},{PLACEHOLDER},{PLACEHOLDER},{PLACEHOLDER},{PLACEHOLDER},{PLACEHOLDER},{PLACEHOLDER})""",
            [
                body.get("user_id"), body.get("subject"), body.get("type_id"),
                body.get("description"), body.get("level_id"), ts, ts,
                body.get("statut_id"), body.get("source_type"), body.get("source_nom"),
                parent_id, body.get("acted_by_user_id"), body.get("deadline_ts"), body.get("site_id"),
            ],
        )
        conn.commit()
        ticket_id = cur.lastrowid if DB_BACKEND == "sqlite" else _pg_lastval(cur)

        cur.execute(
            f"INSERT INTO ticket_status_log (ticket_id, event_type, ts, created_at) VALUES ({PLACEHOLDER},{PLACEHOLDER},{PLACEHOLDER},{PLACEHOLDER})",
            [ticket_id, "opened", ts, now_iso()],
        )
        conn.commit()
        return jsonify({"status": "ok", "id": ticket_id}), 201
    finally:
        conn.close()


def _pg_lastval(cur):
    cur.execute("SELECT lastval()")
    return cur.fetchone()[0]


@app.route("/tickets/<int:ticket_id>", methods=["PUT"])
def update_ticket(ticket_id):
    """
    Édition libre des champs d'un ticket — y compris ts_closed
    explicitement (fermeture/réouverture), puisque "fermé" n'est pas un
    statut figé dans le schéma (statuts.label est libre).
    """
    body = request.get_json(silent=True) or {}
    editable = ["user_id", "subject", "type_id", "description", "level_id", "statut_id", "ts_closed", "archived_at", "deadline_ts", "site_id"]
    fields_to_update = {k: v for k, v in body.items() if k in editable}
    if not fields_to_update:
        return jsonify({"error": f"aucun champ valide fourni (attendus : {editable})"}), 400

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            f"SELECT id, ts_closed, archived_at, first_in_progress_ts FROM tickets WHERE id = {PLACEHOLDER}",
            [ticket_id],
        )
        row = cur.fetchone()
        if row is None:
            return jsonify({"error": "ticket introuvable"}), 404
        previous_ts_closed = row[1]
        previous_archived_at = row[2]
        previous_first_in_progress_ts = row[3]

        # "Prise en charge" -- posée UNE SEULE FOIS, la première fois
        # qu'un ticket passe à un statut de type "en_cours" (voir
        # ensure_statut_type_column()). Jamais réécrite ensuite, même
        # si le statut change à nouveau plus tard (le champ reste le
        # marqueur du DÉBUT du travail actif, pas de l'état courant).
        # Calculé AVANT set_clause pour pouvoir ajouter ce champ à la
        # même requête UPDATE, une seule écriture atomique.
        if "statut_id" in fields_to_update and previous_first_in_progress_ts is None:
            new_statut_id = fields_to_update["statut_id"]
            if new_statut_id is not None:
                cur.execute(f"SELECT type FROM statuts WHERE id = {PLACEHOLDER}", [new_statut_id])
                statut_row = cur.fetchone()
                if statut_row is not None and statut_row[0] == "en_cours":
                    fields_to_update["first_in_progress_ts"] = now_ts()

        fields_to_update["last_change"] = now_ts()
        set_clause = ", ".join(f"{col} = {PLACEHOLDER}" for col in fields_to_update)

        cur.execute(
            f"UPDATE tickets SET {set_clause} WHERE id = {PLACEHOLDER}",
            [*fields_to_update.values(), ticket_id],
        )

        # Journalise la transition SEULEMENT si ts_closed a réellement
        # changé d'état (pas à chaque édition quelconque du ticket).
        if "ts_closed" in fields_to_update:
            new_ts_closed = fields_to_update["ts_closed"]
            if previous_ts_closed is None and new_ts_closed is not None:
                event_type, event_ts = "closed", new_ts_closed
            elif previous_ts_closed is not None and new_ts_closed is None:
                event_type, event_ts = "reopened", now_ts()
            else:
                event_type = None

            if event_type:
                cur.execute(
                    f"INSERT INTO ticket_status_log (ticket_id, event_type, ts, created_at) VALUES ({PLACEHOLDER},{PLACEHOLDER},{PLACEHOLDER},{PLACEHOLDER})",
                    [ticket_id, event_type, event_ts, now_iso()],
                )

        # Même principe pour archived_at — même table de journal, pour
        # garder une seule chronologie par ticket plutôt que d'en créer
        # une deuxième.
        if "archived_at" in fields_to_update:
            new_archived_at = fields_to_update["archived_at"]
            if previous_archived_at is None and new_archived_at is not None:
                archive_event = "archived"
            elif previous_archived_at is not None and new_archived_at is None:
                archive_event = "unarchived"
            else:
                archive_event = None

            if archive_event:
                cur.execute(
                    f"INSERT INTO ticket_status_log (ticket_id, event_type, ts, created_at) VALUES ({PLACEHOLDER},{PLACEHOLDER},{PLACEHOLDER},{PLACEHOLDER})",
                    [ticket_id, archive_event, now_ts(), now_iso()],
                )

        conn.commit()
        return jsonify({"status": "ok"}), 200
    finally:
        conn.close()


@app.route("/tickets/<int:ticket_id>", methods=["GET"])
def get_ticket(ticket_id):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            f"""SELECT t.*, si.label AS site_label
                FROM tickets t
                LEFT JOIN sites si ON t.site_id = si.id
                WHERE t.id = {PLACEHOLDER}""",
            [ticket_id],
        )
        row = cur.fetchone()
        if row is None:
            return jsonify({"error": "ticket introuvable"}), 404
        ticket = row_to_dict(cur, row)

        cur.execute(
            f"SELECT * FROM ticket_time_entries WHERE ticket_id = {PLACEHOLDER} ORDER BY start_ts",
            [ticket_id],
        )
        entries_rows = cur.fetchall()
        ticket["time_entries"] = [row_to_dict(cur, r) for r in entries_rows]
        ticket["total_seconds"] = sum((e["end_ts"] - e["start_ts"]) * e.get("weight", 1.0) for e in ticket["time_entries"])

        # Champs additifs pour le portail (l'existant ne les lit pas) :
        # évolution (journal ouvert/fermé/rouvert), sous-demandes, volume du fil.
        cur.execute(
            f"SELECT event_type, ts FROM ticket_status_log WHERE ticket_id = {PLACEHOLDER} ORDER BY ts, id",
            [ticket_id],
        )
        ticket["status_log"] = [row_to_dict(cur, r) for r in cur.fetchall()]
        cur.execute(
            f"SELECT id, subject, ts_created, ts_closed, statut_id FROM tickets WHERE parent_ticket_id = {PLACEHOLDER} ORDER BY ts_created",
            [ticket_id],
        )
        ticket["children"] = [row_to_dict(cur, r) for r in cur.fetchall()]
        cur.execute(
            f"SELECT COUNT(*) FROM ticket_messages WHERE ticket_id = {PLACEHOLDER}",
            [ticket_id],
        )
        ticket["message_count"] = cur.fetchone()[0]
        return jsonify(ticket)
    finally:
        conn.close()


@app.route("/tickets/<int:ticket_id>/time_entries", methods=["POST"])
def add_time_entry(ticket_id):
    """`technician_login` optionnel -- absent/None pour tout appelant
    qui ne le fournit pas encore (ex. affectation calendrier en masse,
    /calendar/assign, jamais touchée par ce chantier -- voir
    ticket_time_entries.technician_login, commentaire du schéma).
    Jamais validé contre la table users : même raisonnement que
    collections.created_by côté coffre-fort, un login qui n'existe
    plus ne doit jamais empêcher la lecture/l'écriture d'un segment
    déjà créé."""
    body = request.get_json(silent=True) or {}
    start_ts, end_ts = body.get("start_ts"), body.get("end_ts")
    if start_ts is None or end_ts is None:
        return jsonify({"error": "start_ts et end_ts requis"}), 400
    technician_login = body.get("technician_login") or None

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            f"""INSERT INTO ticket_time_entries (ticket_id, calendar_event_id, start_ts, end_ts, technician_login, created_at)
                VALUES ({PLACEHOLDER},{PLACEHOLDER},{PLACEHOLDER},{PLACEHOLDER},{PLACEHOLDER},{PLACEHOLDER})""",
            [ticket_id, body.get("calendar_event_id"), start_ts, end_ts, technician_login, now_iso()],
        )
        cur.execute(
            f"UPDATE tickets SET last_change = {PLACEHOLDER} WHERE id = {PLACEHOLDER}",
            [now_ts(), ticket_id],
        )
        conn.commit()
        return jsonify({"status": "ok"}), 201
    finally:
        conn.close()


@app.route("/time_entries", methods=["GET"])
def list_time_entries():
    """Segments de temps, filtrable par technicien -- pour la
    timeline PERSONNELLE du technicien (backlog, livraison #115),
    distincte du Gantt (voir /tickets/parallel, ticket-centrique).
    Sans `technician_login`, renvoie TOUS les segments (y compris
    ceux jamais attribués -- imports calendrier, anciens segments) :
    l'appelant est responsable de filtrer, ce comportement permissif
    par défaut évite de dupliquer la logique de filtre ici. Jointure
    légère avec tickets (sujet seulement, pas de statut/niveau -- ce
    n'est qu'une liste chronologique, pas un tableau de bord)."""
    technician_login = request.args.get("technician_login")
    conditions = []
    params = []
    if technician_login:
        conditions.append(f"tte.technician_login = {PLACEHOLDER}")
        params.append(technician_login)
    where_sql = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            f"""
            SELECT tte.id, tte.ticket_id, tte.start_ts, tte.end_ts, tte.technician_login,
                   t.subject AS ticket_subject
            FROM ticket_time_entries tte
            JOIN tickets t ON t.id = tte.ticket_id
            {where_sql}
            ORDER BY tte.start_ts DESC
            """,
            params,
        )
        entries = [row_to_dict(cur, r) for r in cur.fetchall()]
        return jsonify({"entries": entries}), 200
    finally:
        conn.close()


@app.route("/queue", methods=["GET"])
def technician_queue():
    """
    Vue file d'attente pour l'équipe technique : triée par priorité
    (rank du niveau) puis par temps d'attente écoulé (le plus ancien
    d'abord), filtrable par type/demandeur/statut.

    Les tickets archivés sont exclus par défaut de TOUS les états
    (open/closed/all) — "archived_at" est un masquage, pas un statut ;
    state=archived les affiche À L'EXCLUSION des autres (vue dédiée),
    include_archived=true lève l'exclusion sans changer state.
    """
    apply_deadline_escalations()
    type_id = request.args.get("type_id")
    user_id = request.args.get("user_id")
    statut_id = request.args.get("statut_id")
    source_type = request.args.get("source_type")
    state = request.args.get("state")
    include_archived = request.args.get("include_archived") == "true"
    if state is None:
        # Compatibilité ascendante avec l'ancien paramètre all=true.
        state = "all" if request.args.get("all") == "true" else "open"

    conditions, params = ["1=1"], []
    if type_id:
        conditions.append(f"t.type_id = {PLACEHOLDER}")
        params.append(type_id)
    if source_type:
        conditions.append(f"t.source_type = {PLACEHOLDER}")
        params.append(source_type)
    if user_id:
        conditions.append(f"t.user_id = {PLACEHOLDER}")
        params.append(user_id)
    if statut_id:
        conditions.append(f"t.statut_id = {PLACEHOLDER}")
        params.append(statut_id)
    if state == "open":
        conditions.append("t.ts_closed IS NULL")
    elif state == "closed":
        conditions.append("t.ts_closed IS NOT NULL")
    elif state == "archived":
        conditions.append("t.archived_at IS NOT NULL")
    # state == "all" -> aucune condition supplémentaire sur ts_closed

    if state != "archived" and not include_archived:
        conditions.append("t.archived_at IS NULL")

    where_sql = " AND ".join(conditions)

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            f"""
            SELECT t.*, l.rank AS level_rank, l.label AS level_label,
                   ty.label AS type_label, s.label AS statut_label, u.login AS user_login,
                   si.label AS site_label,
                   (SELECT COUNT(*) FROM ticket_time_entries tte WHERE tte.ticket_id = t.id) AS segment_count,
                   (SELECT COUNT(*) FROM ticket_status_log tsl WHERE tsl.ticket_id = t.id AND tsl.event_type = 'reopened') AS reopen_count
            FROM tickets t
            LEFT JOIN levels l ON t.level_id = l.id
            LEFT JOIN types ty ON t.type_id = ty.id
            LEFT JOIN statuts s ON t.statut_id = s.id
            LEFT JOIN users u ON t.user_id = u.id
            LEFT JOIN sites si ON t.site_id = si.id
            WHERE {where_sql}
            ORDER BY l.rank DESC, t.ts_created ASC
            """,
            params,
        )
        rows = cur.fetchall()
        tickets = [row_to_dict(cur, r) for r in rows]
        now = now_ts()

        # Score mots-clés — EN PLUS du tri urgence/attente ci-dessus,
        # jamais à la place : expose keyword_score/keyword_matches sans
        # changer l'ORDER BY existant, le tri par mots-clés est un choix
        # explicite côté vue technicien (voir tickets/portal), pas un
        # nouveau comportement par défaut imposé partout.
        cur.execute("SELECT label, pattern, active FROM priority_keywords")
        keyword_rules = [{"label": r[0], "pattern": r[1]} for r in cur.fetchall() if r[2]]

        for t in tickets:
            t["wait_seconds"] = now - t["ts_created"]
            text = " ".join(filter(None, [t.get("subject"), t.get("description")]))
            t["keyword_matches"] = compute_keyword_matches(text, keyword_rules)
            t["keyword_score"] = len(t["keyword_matches"])

        # Récidive ("ticket identique") : combien d'AUTRES tickets du
        # même demandeur partagent un sujet significativement proche —
        # signale un problème qui revient sous forme de nouveaux tickets
        # plutôt que de réouvertures du même. Heuristique par mots
        # partagés (même moteur que les suggestions calendrier),
        # volontairement simple.
        cur.execute("SELECT id, user_id, subject FROM tickets")
        all_tickets = [{"id": r[0], "user_id": r[1], "subject": r[2] or ""} for r in cur.fetchall()]
        words_by_id = {t["id"]: extract_significant_words(t["subject"]) for t in all_tickets}

        for t in tickets:
            own_words = words_by_id.get(t["id"], set())
            count = 0
            if own_words:
                for other in all_tickets:
                    if other["id"] == t["id"] or other["user_id"] != t["user_id"]:
                        continue
                    if own_words & words_by_id.get(other["id"], set()):
                        count += 1
            t["similar_tickets_count"] = count

        return jsonify({"tickets": tickets})
    finally:
        conn.close()


# ============================================================
# Règles de filtrage calendrier
# ============================================================

@app.route("/filter_rules", methods=["GET"])
def list_filter_rules():
    return simple_list_endpoint("calendar_filter_rules", "priority")


@app.route("/filter_rules", methods=["POST"])
def create_filter_rule():
    """Protégée par rights-api (#326)."""
    body = request.get_json(silent=True) or {}
    allowed, error = _check_manage_right(body)
    if not allowed:
        return jsonify({"error": error}), 403
    ts = now_iso()
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            f"""INSERT INTO calendar_filter_rules
                (label, pattern, target_field, action, ticket_ref_group,
                 default_type_id, default_level_id, default_user_id, priority, active, created_at, updated_at)
                VALUES ({PLACEHOLDER},{PLACEHOLDER},{PLACEHOLDER},{PLACEHOLDER},{PLACEHOLDER},
                        {PLACEHOLDER},{PLACEHOLDER},{PLACEHOLDER},{PLACEHOLDER},{PLACEHOLDER},{PLACEHOLDER},{PLACEHOLDER})""",
            [
                body.get("label"), body.get("pattern"), body.get("target_field", "summary"),
                body.get("action", "both"), body.get("ticket_ref_group"),
                body.get("default_type_id"), body.get("default_level_id"), body.get("default_user_id"),
                body.get("priority", 0), 1 if body.get("active", True) else 0, ts, ts,
            ],
        )
        conn.commit()
        return jsonify({"status": "ok"}), 201
    finally:
        conn.close()


@app.route("/filter_rules/<int:rule_id>", methods=["DELETE"])
def delete_filter_rule(rule_id):
    """Protégée par rights-api (#326)."""
    body = request.get_json(silent=True) or {}
    allowed, error = _check_manage_right(body)
    if not allowed:
        return jsonify({"error": error}), 403
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(f"DELETE FROM calendar_filter_rules WHERE id = {PLACEHOLDER}", [rule_id])
        conn.commit()
        return jsonify({"status": "ok"}), 200
    finally:
        conn.close()


# ============================================================
# Liste d'exclusion — véto sur le déclenchement, même si le mot-clé
# matche par ailleurs (ex: réunion récurrente mentionnant "SAV" dans
# son titre sans être elle-même un ticket).
# ============================================================

@app.route("/exclusion_rules", methods=["GET"])
def list_exclusion_rules():
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, label, pattern, active FROM exclusion_rules ORDER BY id")
        rows = cur.fetchall()
        return jsonify([
            {"id": r[0], "label": r[1], "pattern": r[2], "active": bool(r[3])} for r in rows
        ]), 200
    finally:
        conn.close()


@app.route("/exclusion_rules", methods=["POST"])
def create_exclusion_rule():
    """Protégée par rights-api (#326)."""
    body = request.get_json(silent=True) or {}
    allowed, error = _check_manage_right(body)
    if not allowed:
        return jsonify({"error": error}), 403
    label, pattern = body.get("label"), body.get("pattern")
    if not label or not pattern:
        return jsonify({"error": "label et pattern requis"}), 400
    try:
        re.compile(pattern)
    except re.error as exc:
        return jsonify({"error": f"expression régulière invalide : {exc}"}), 400

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            f"INSERT INTO exclusion_rules (label, pattern, active, created_at) VALUES ({PLACEHOLDER},{PLACEHOLDER},{PLACEHOLDER},{PLACEHOLDER})",
            [label, pattern, True, now_iso()],
        )
        conn.commit()
        new_id = cur.lastrowid if DB_BACKEND == "sqlite" else _pg_lastval(cur)
        return jsonify({"status": "ok", "id": new_id}), 201
    finally:
        conn.close()


@app.route("/exclusion_rules/<int:rule_id>", methods=["DELETE"])
def delete_exclusion_rule(rule_id):
    """Protégée par rights-api (#326)."""
    body = request.get_json(silent=True) or {}
    allowed, error = _check_manage_right(body)
    if not allowed:
        return jsonify({"error": error}), 403
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(f"DELETE FROM exclusion_rules WHERE id = {PLACEHOLDER}", [rule_id])
        conn.commit()
        return jsonify({"status": "ok"}), 200
    finally:
        conn.close()


# ============================================================
# Mots-clés d'urgence — n'excluent ni ne décident rien, servent juste
# de signal pour le tri "urgence" de l'écran de revue.
# ============================================================

@app.route("/priority_keywords", methods=["GET"])
def list_priority_keywords():
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, label, pattern, active FROM priority_keywords ORDER BY id")
        rows = cur.fetchall()
        return jsonify([
            {"id": r[0], "label": r[1], "pattern": r[2], "active": bool(r[3])} for r in rows
        ]), 200
    finally:
        conn.close()


@app.route("/priority_keywords", methods=["POST"])
def create_priority_keyword():
    """Protégée par rights-api (#326)."""
    body = request.get_json(silent=True) or {}
    allowed, error = _check_manage_right(body)
    if not allowed:
        return jsonify({"error": error}), 403
    label, pattern = body.get("label"), body.get("pattern")
    if not label or not pattern:
        return jsonify({"error": "label et pattern requis"}), 400
    try:
        re.compile(pattern)
    except re.error as exc:
        return jsonify({"error": f"expression régulière invalide : {exc}"}), 400

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            f"INSERT INTO priority_keywords (label, pattern, active, created_at) VALUES ({PLACEHOLDER},{PLACEHOLDER},{PLACEHOLDER},{PLACEHOLDER})",
            [label, pattern, True, now_iso()],
        )
        conn.commit()
        new_id = cur.lastrowid if DB_BACKEND == "sqlite" else _pg_lastval(cur)
        return jsonify({"status": "ok", "id": new_id}), 201
    finally:
        conn.close()


@app.route("/priority_keywords/<int:rule_id>", methods=["DELETE"])
def delete_priority_keyword(rule_id):
    """Protégée par rights-api (#326)."""
    body = request.get_json(silent=True) or {}
    allowed, error = _check_manage_right(body)
    if not allowed:
        return jsonify({"error": error}), 403
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(f"DELETE FROM priority_keywords WHERE id = {PLACEHOLDER}", [rule_id])
        conn.commit()
        return jsonify({"status": "ok"}), 200
    finally:
        conn.close()


# ============================================================
# Import calendrier — pipeline complet
# ============================================================

def get_active_rules(cur):
    cur.execute(f"SELECT * FROM calendar_filter_rules WHERE active = {PLACEHOLDER} ORDER BY priority ASC", [1])
    return [row_to_dict(cur, r) for r in cur.fetchall()]


def find_ticket_by_id_factory(cur):
    def find_ticket_by_id(ref):
        try:
            ticket_id = int(ref)
        except (TypeError, ValueError):
            return None
        cur.execute(f"SELECT id FROM tickets WHERE id = {PLACEHOLDER}", [ticket_id])
        row = cur.fetchone()
        return row[0] if row else None
    return find_ticket_by_id


def import_parsed_events(events: list[dict], source: str) -> dict:
    """
    Stocke des événements déjà parsés (dédupliqués par uid) — n'exécute
    aucun rattachement ni création automatique, quelle que soit la
    source (fichier ICS, URL ICS, ou API Google Calendar). La décision
    revient toujours à l'écran de revue.
    Chaque event : {"uid", "summary", "description", "start_ts", "end_ts"}.
    """
    conn = get_connection()
    summary = {"total_events": len(events), "imported": 0, "already_known": 0}

    try:
        cur = conn.cursor()
        for event in events:
            cur.execute(f"SELECT id FROM calendar_events WHERE uid = {PLACEHOLDER}", [event["uid"]])
            if cur.fetchone() is not None:
                summary["already_known"] += 1
                continue

            cur.execute(
                f"""INSERT INTO calendar_events (uid, summary, description, start_ts, end_ts, source, imported_at)
                    VALUES ({PLACEHOLDER},{PLACEHOLDER},{PLACEHOLDER},{PLACEHOLDER},{PLACEHOLDER},{PLACEHOLDER},{PLACEHOLDER})""",
                [event["uid"], event["summary"], event["description"], event["start_ts"], event["end_ts"], source, now_iso()],
            )
            summary["imported"] += 1

        conn.commit()
        return summary
    finally:
        conn.close()


def import_ics_events(raw_ics: str, source: str) -> dict:
    return import_parsed_events(parse_ics(raw_ics), source)


@app.route("/settings", methods=["GET"])
def get_settings():
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT key, value FROM matching_config")
        return jsonify(dict(cur.fetchall())), 200
    finally:
        conn.close()


@app.route("/settings", methods=["POST"])
def update_settings():
    """Protégée par rights-api (#328) -- matching_config alimente le
    moteur de détection automatique calendrier->ticket (trigger_keyword
    notamment), même famille que filter_rules/exclusion_rules/
    priority_keywords déjà gardées en passe 3."""
    body = request.get_json(silent=True) or {}
    allowed, error = _check_manage_right(body)
    if not allowed:
        return jsonify({"error": error}), 403
    conn = get_connection()
    try:
        cur = conn.cursor()
        for key, value in body.items():
            if key == "groups":  # jamais une clé de configuration -- uniquement pour la vérification des droits ci-dessus
                continue
            if DB_BACKEND == "postgres":
                cur.execute(
                    "INSERT INTO matching_config (key, value) VALUES (%s, %s) "
                    "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value",
                    [key, str(value)],
                )
            else:
                cur.execute(
                    "INSERT OR REPLACE INTO matching_config (key, value) VALUES (?, ?)",
                    [key, str(value)],
                )
        conn.commit()
        return jsonify({"status": "ok"}), 200
    finally:
        conn.close()


@app.route("/calendar/suggest_name", methods=["POST"])
def suggest_name_for_events():
    """
    Pré-remplissage : à partir d'un ou plusieurs événements (typiquement
    la sélection courante dans l'écran de revue), propose UN candidat
    login/nom plausible — heuristique, pas une certitude, à valider par
    l'humain avant création.
    """
    body = request.get_json(silent=True) or {}
    event_ids = body.get("event_ids") or []
    if not event_ids:
        return jsonify({"error": "event_ids requis"}), 400

    conn = get_connection()
    try:
        cur = conn.cursor()
        placeholders = ",".join([PLACEHOLDER] * len(event_ids))
        cur.execute(f"SELECT summary, description FROM calendar_events WHERE id IN ({placeholders})", event_ids)
        events = [{"summary": r[0], "description": r[1]} for r in cur.fetchall()]

        cur.execute(f"SELECT value FROM matching_config WHERE key = {PLACEHOLDER}", ["trigger_keyword"])
        row = cur.fetchone()
        trigger_keyword = row[0] if row else "SAV"

        candidate = best_candidate_name(events, trigger_keyword)
        return jsonify({"candidate": candidate}), 200
    finally:
        conn.close()


# ============================================================
# Édition générique depuis la vue "Toutes les tables" — micro-
# corrections rapides, sans passer par les formulaires dédiés. Liste
# blanche stricte (table + colonnes) pour éviter tout risque
# d'injection via un nom de colonne arbitraire. ticket_status_log
# (journal d'audit) et oauth_credentials (jetons techniques) sont
# volontairement exclus — pas de correction manuelle pertinente.
# ============================================================
RAW_EDITABLE_TABLES = {
    "users": {"pk": "id", "columns": ["login", "name", "email", "group_name", "role"]},
    "types": {"pk": "id", "columns": ["label"]},
    "levels": {"pk": "id", "columns": ["label", "rank"]},
    "statuts": {"pk": "id", "columns": ["label", "description"]},
    "tickets": {"pk": "id", "columns": ["subject", "description", "user_id", "type_id", "level_id", "statut_id", "ts_closed"]},
    "calendar_events": {"pk": "id", "columns": ["summary", "description", "start_ts", "end_ts"]},
    "calendar_filter_rules": {"pk": "id", "columns": ["label", "pattern", "target_field", "action", "priority"]},
    "exclusion_rules": {"pk": "id", "columns": ["label", "pattern"]},
    "priority_keywords": {"pk": "id", "columns": ["label", "pattern"]},
    "ticket_time_entries": {"pk": "id", "columns": ["start_ts", "end_ts", "weight"]},
    "matching_config": {"pk": "key", "columns": ["value"]},
}

# Sous-ensemble de RAW_EDITABLE_TABLES déjà protégé par une garde
# rights-api sur SA route dédiée -- voir #325 (users/types/levels/
# statuts, via update_reference_row), #326 (calendar_filter_rules/
# exclusion_rules/priority_keywords), #328 (matching_config, via
# /settings). Les autres (tickets/calendar_events/
# ticket_time_entries) restent délibérément ouvertes -- cœur ticket
# self-service, voir passe 3 (#326).
PROTECTED_RAW_TABLES = {
    "users", "types", "levels", "statuts",
    "calendar_filter_rules", "exclusion_rules", "priority_keywords",
    "matching_config",
}


@app.route("/raw_tables/<table_name>/<row_id>", methods=["PUT"])
def update_raw_table_row(table_name, row_id):
    """Édition générique par table+colonnes en liste blanche
    (RAW_EDITABLE_TABLES) -- UN SEUL point d'accès qui recouvre à la
    fois des tables déjà protégées ailleurs (users/types/levels/
    statuts/calendar_filter_rules/exclusion_rules/priority_keywords/
    matching_config, gardées en passes 2/3/5) ET des tables
    délibérément laissées ouvertes (tickets/calendar_events/
    ticket_time_entries, cœur ticket self-service, voir passe 3).

    Protégée par rights-api (#329) -- CONDITIONNELLEMENT, selon la
    table ciblée uniquement, jamais en bloc : sans ça, cette route
    contournerait silencieusement toute la protection déjà posée
    route par route sur les tables PROTECTED_RAW_TABLES (ex.
    PUT /raw_tables/users/5 échapperait à la garde de PUT /users/5).
    Reste cohérente avec CHAQUE décision déjà prise -- jamais
    re-décidée ici indépendamment."""
    config = RAW_EDITABLE_TABLES.get(table_name)
    if not config:
        return jsonify({"error": f"table '{table_name}' non éditable depuis cette vue"}), 400

    body = request.get_json(silent=True) or {}
    if table_name in PROTECTED_RAW_TABLES:
        allowed, error = _check_manage_right(body)
        if not allowed:
            return jsonify({"error": error}), 403
    fields_to_update = {k: v for k, v in body.items() if k in config["columns"]}
    if not fields_to_update:
        return jsonify({"error": f"aucun champ valide fourni (attendus : {config['columns']})"}), 400

    set_clause = ", ".join(f"{col} = {PLACEHOLDER}" for col in fields_to_update)
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            f"UPDATE {table_name} SET {set_clause} WHERE {config['pk']} = {PLACEHOLDER}",
            [*fields_to_update.values(), row_id],
        )
        conn.commit()
        return jsonify({"status": "ok"}), 200
    finally:
        conn.close()


@app.route("/terms/synthesis", methods=["GET"])
def term_synthesis():
    """
    Vue associative : pour un terme donné (ex: un nom propre repéré par
    l'analyse en lot, "Alpha"), synthétise tout ce qui s'y rapporte —
    tickets (sujet ou description), temps total passé, demandeurs
    impliqués, plus les événements calendrier non encore affectés qui
    en parlent aussi (aperçu de ce qui reste à traiter).
    """
    term = (request.args.get("term") or "").strip()
    if not term:
        return jsonify({"error": "paramètre 'term' requis"}), 400
    normalized_term = strip_accents(term.lower())

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT t.*, l.label AS level_label, ty.label AS type_label,
                   s.label AS statut_label, u.login AS user_login
            FROM tickets t
            LEFT JOIN levels l ON t.level_id = l.id
            LEFT JOIN types ty ON t.type_id = ty.id
            LEFT JOIN statuts s ON t.statut_id = s.id
            LEFT JOIN users u ON t.user_id = u.id
        """)
        all_tickets = [row_to_dict(cur, r) for r in cur.fetchall()]
        matching_tickets = [
            t for t in all_tickets
            if normalized_term in strip_accents((t.get("subject") or "").lower())
            or normalized_term in strip_accents((t.get("description") or "").lower())
        ]

        for t in matching_tickets:
            cur.execute(
                f"SELECT start_ts, end_ts, weight FROM ticket_time_entries WHERE ticket_id = {PLACEHOLDER}",
                [t["id"]],
            )
            entries = cur.fetchall()
            t["total_seconds"] = sum((e[1] - e[0]) * e[2] for e in entries)

        cur.execute("""
            SELECT ce.*, GROUP_CONCAT(tte.id) AS assigned
            FROM calendar_events ce
            LEFT JOIN ticket_time_entries tte ON tte.calendar_event_id = ce.id
            GROUP BY ce.id
        """ if DB_BACKEND == "sqlite" else """
            SELECT ce.*, STRING_AGG(tte.id::text, ',') AS assigned
            FROM calendar_events ce
            LEFT JOIN ticket_time_entries tte ON tte.calendar_event_id = ce.id
            GROUP BY ce.id
        """)
        all_events = [row_to_dict(cur, r) for r in cur.fetchall()]
        matching_events = []
        for e in all_events:
            is_assigned = bool(e.pop("assigned", None))
            if is_assigned:
                continue
            if normalized_term in strip_accents((e.get("summary") or "").lower()) or normalized_term in strip_accents((e.get("description") or "").lower()):
                matching_events.append(e)

        open_count = sum(1 for t in matching_tickets if t["ts_closed"] is None)
        dates = [t["ts_created"] for t in matching_tickets]

        return jsonify({
            "term": term,
            "tickets": matching_tickets,
            "unassigned_events": matching_events,
            "synthesis": {
                "total_tickets": len(matching_tickets),
                "open_count": open_count,
                "closed_count": len(matching_tickets) - open_count,
                "total_seconds": sum(t["total_seconds"] for t in matching_tickets),
                "distinct_users": sorted({t["user_login"] for t in matching_tickets if t.get("user_login")}),
                "earliest_ts": min(dates) if dates else None,
                "latest_ts": max(dates) if dates else None,
            },
        }), 200
    finally:
        conn.close()


@app.route("/calendar/title_matches", methods=["GET"])
def calendar_title_matches():
    """
    Analyse indépendante du mot-clé déclencheur : cherche, pour chaque
    événement non affecté, le ticket ouvert avec lequel il partage le
    plus de mots significatifs (>= 3 caractères, mot-clé déclencheur
    exclu). Propose d'ajouter l'événement comme nouvelle plage de temps
    sur ce ticket — utile pour les titres qu'un déclenchement classique
    ne capte pas (ex: "SMS" seul, alors qu'un ticket "SAV Didier/SMS"
    existe déjà).
    """
    min_score = int(request.args.get("min_score", 1))

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT ce.*, GROUP_CONCAT(tte.ticket_id) AS assigned_ticket_ids
            FROM calendar_events ce
            LEFT JOIN ticket_time_entries tte ON tte.calendar_event_id = ce.id
            GROUP BY ce.id
        """ if DB_BACKEND == "sqlite" else """
            SELECT ce.*, STRING_AGG(tte.ticket_id::text, ',') AS assigned_ticket_ids
            FROM calendar_events ce
            LEFT JOIN ticket_time_entries tte ON tte.calendar_event_id = ce.id
            GROUP BY ce.id
        """)
        all_events = [row_to_dict(cur, r) for r in cur.fetchall()]
        events = [e for e in all_events if not e.get("assigned_ticket_ids")]

        cur.execute("SELECT id, subject, description, ts_closed FROM tickets")
        candidate_tickets = [
            {"id": r[0], "subject": r[1], "description": r[2], "is_closed": r[3] is not None}
            for r in cur.fetchall()
        ]

        cur.execute(f"SELECT value FROM matching_config WHERE key = {PLACEHOLDER}", ["trigger_keyword"])
        row = cur.fetchone()
        trigger_keyword = row[0] if row else None

        matches = analyze_title_matches(events, candidate_tickets, trigger_keyword, min_score)
        return jsonify({"matches": matches, "total_events_analyzed": len(events)}), 200
    finally:
        conn.close()


@app.route("/calendar/mine_candidates", methods=["GET"])
def mine_candidates():
    """
    Analyse en lot : fréquence des tokens candidats (login/nom
    plausibles) sur TOUS les événements importés — pour repérer d'un
    coup d'œil les personnes qui reviennent souvent sans encore avoir
    de fiche utilisateur. Heuristique (position + fréquence + exclusion
    de mots-outils), pas un vrai NER — présenter comme des suggestions
    à valider, jamais comme des faits.
    """
    limit = min(int(request.args.get("limit", 15)), 50)

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT summary, description FROM calendar_events")
        all_events = [{"summary": r[0], "description": r[1]} for r in cur.fetchall()]

        cur.execute("SELECT pattern FROM exclusion_rules WHERE active = 1" if DB_BACKEND == "sqlite" else "SELECT pattern FROM exclusion_rules WHERE active = TRUE")
        exclusion_patterns = [r[0] for r in cur.fetchall()]
        events = [e for e in all_events if not event_matches_any_pattern(e, exclusion_patterns)[0]]

        cur.execute(f"SELECT value FROM matching_config WHERE key = {PLACEHOLDER}", ["trigger_keyword"])
        row = cur.fetchone()
        trigger_keyword = row[0] if row else "SAV"

        cur.execute("SELECT login, name FROM users")
        known_users = [{"login": r[0], "name": r[1]} for r in cur.fetchall()]

        candidates = mine_candidate_identifiers(events, trigger_keyword, known_users, top_n=limit)
        return jsonify({"total_events_analyzed": len(events), "candidates": candidates}), 200
    finally:
        conn.close()


@app.route("/calendar/events", methods=["GET"])
def list_calendar_events():
    """
    Écran de revue : liste les événements calendrier avec leur statut
    d'affectation (déjà rattaché à un/des ticket(s), ou pas encore) et,
    pour les non-affectés, les suggestions calculées à la volée
    (toujours avec les règles/mot-clé actuels, jamais figées à
    l'import).
    """
    only = request.args.get("only", "unassigned")  # unassigned | assigned | all

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT ce.*, GROUP_CONCAT(tte.ticket_id) AS assigned_ticket_ids
            FROM calendar_events ce
            LEFT JOIN ticket_time_entries tte ON tte.calendar_event_id = ce.id
            GROUP BY ce.id
            ORDER BY ce.start_ts DESC
        """ if DB_BACKEND == "sqlite" else """
            SELECT ce.*, STRING_AGG(tte.ticket_id::text, ',') AS assigned_ticket_ids
            FROM calendar_events ce
            LEFT JOIN ticket_time_entries tte ON tte.calendar_event_id = ce.id
            GROUP BY ce.id
            ORDER BY ce.start_ts DESC
        """)
        rows = cur.fetchall()
        events = [row_to_dict(cur, r) for r in rows]

        for e in events:
            raw_ids = e.pop("assigned_ticket_ids", None)
            e["assigned_ticket_ids"] = [int(x) for x in raw_ids.split(",")] if raw_ids else []

        if only == "assigned":
            events = [e for e in events if e["assigned_ticket_ids"]]
        elif only == "unassigned":
            events = [e for e in events if not e["assigned_ticket_ids"]]

        if only != "assigned":
            cur.execute(f"SELECT value FROM matching_config WHERE key = {PLACEHOLDER}", ["trigger_keyword"])
            trigger_row = cur.fetchone()
            trigger_keyword = trigger_row[0] if trigger_row else "SAV"

            cur.execute("SELECT id, login FROM users")
            users = [{"id": r[0], "login": r[1]} for r in cur.fetchall()]

            cur.execute("SELECT id, subject, description, user_id, ts_closed FROM tickets")
            candidate_tickets = [
                {"id": r[0], "subject": r[1], "description": r[2], "user_id": r[3], "is_closed": r[4] is not None}
                for r in cur.fetchall()
            ]

            rules = get_active_rules(cur)
            find_ticket_by_id = find_ticket_by_id_factory(cur)

            cur.execute("SELECT pattern FROM exclusion_rules WHERE active = 1" if DB_BACKEND == "sqlite" else "SELECT pattern FROM exclusion_rules WHERE active = TRUE")
            exclusion_patterns = [r[0] for r in cur.fetchall()]

            for e in events:
                if e["assigned_ticket_ids"]:
                    e["suggestions"] = []
                    e["triggered"] = False
                    e["excluded"] = False
                    continue

                is_excluded, matched_pattern = event_matches_any_pattern(e, exclusion_patterns)
                if is_excluded:
                    # Véto : même si le mot-clé déclencheur matche par
                    # ailleurs, cet événement n'est jamais un candidat
                    # ticket (ex: réunion récurrente mentionnant "SAV").
                    e["suggestions"] = []
                    e["triggered"] = False
                    e["excluded"] = True
                    e["excluded_reason"] = matched_pattern
                    continue

                e["excluded"] = False
                rule_decision = apply_rules_to_event(e, rules, find_ticket_by_id)
                fuzzy = suggest_candidates(e, trigger_keyword, users, candidate_tickets)
                suggestions = []
                if rule_decision and rule_decision["action"] == "attach":
                    matched_ticket = next((t for t in candidate_tickets if t["id"] == rule_decision["ticket_id"]), None)
                    suggestions.append({
                        "ticket_id": rule_decision["ticket_id"], "confidence": "haute", "reason": "référence explicite",
                        "is_closed": bool(matched_ticket and matched_ticket["is_closed"]),
                    })
                for c in fuzzy["candidates"]:
                    if not any(s["ticket_id"] == c["ticket_id"] for s in suggestions):
                        suggestions.append({"ticket_id": c["ticket_id"], "confidence": "suggérée", "reason": f"score {c['score']}", "is_closed": c["is_closed"]})
                e["suggestions"] = suggestions
                # Distingue "mot-clé pas déclenché du tout" de "déclenché
                # mais aucun ticket ouvert à proposer" — les deux donnaient
                # suggestions=[] côté interface, impossible à distinguer.
                e["triggered"] = fuzzy["triggered"] or bool(rule_decision)
                # Livraison #284, demandé explicitement -- "une mini
                # liste de mots-clés trouvés" pour affichage au survol.
                # ⚠️ Aujourd'hui UN SEUL mot-clé déclencheur configuré
                # (`trigger_keyword`, ex. "SAV") -- jamais plusieurs
                # mots distincts en pratique tant que ce mécanisme
                # reste mono-mot-clé ; exposé ici tel quel, jamais une
                # liste inventée pour faire comme si.
                e["matched_keywords"] = [trigger_keyword] if fuzzy["triggered"] and trigger_keyword else []

                # Demandeur potentiel — priorité au login détecté par le
                # moteur de suggestion (fiable, correspond à un utilisateur
                # réel), sinon repli sur l'heuristique NLP (candidat texte,
                # non garanti exister comme utilisateur).
                if fuzzy["matched_user_id"] is not None:
                    matched_login = next((u["login"] for u in users if u["id"] == fuzzy["matched_user_id"]), None)
                    e["requester_hint"] = matched_login
                else:
                    e["requester_hint"] = best_candidate_name([e], trigger_keyword)

            cur.execute("SELECT pattern FROM priority_keywords WHERE active = 1" if DB_BACKEND == "sqlite" else "SELECT pattern FROM priority_keywords WHERE active = TRUE")
            priority_patterns = [r[0] for r in cur.fetchall()]
            for e in events:
                e["priority_match"] = event_matches_any_pattern(e, priority_patterns)[0] if not e.get("excluded") else False
                e.setdefault("requester_hint", None)

        # Tri — le défaut ("pertinence") remonte les événements avec
        # suggestion en tête, plus récents d'abord dans chaque groupe.
        sort_mode = request.args.get("sort", "relevance")

        def relevance_rank(e):
            if e.get("suggestions"):
                return 0
            if e.get("triggered") and not e.get("excluded"):
                return 1
            return 2

        if sort_mode == "oldest":
            events.sort(key=lambda e: e["start_ts"])
        elif sort_mode == "requester":
            events.sort(key=lambda e: ((e.get("requester_hint") or "~").lower(), -e["start_ts"]))
        elif sort_mode == "urgency":
            events.sort(key=lambda e: (not e.get("priority_match", False), -e["start_ts"]))
        else:  # "relevance", défaut
            events.sort(key=lambda e: (relevance_rank(e), -e["start_ts"]))

        return jsonify({"events": events, "sort": sort_mode}), 200
    finally:
        conn.close()


@app.route("/calendar/assign", methods=["POST"])
def assign_events_to_tickets():
    """
    Affectation n événements -> m tickets. mode='full' : chaque
    événement compte pour sa durée entière sur CHAQUE ticket sélectionné
    (comptage multiple assumé). mode='split' : la durée de chaque
    événement est répartie également entre les tickets sélectionnés
    (weight = 1/m par segment).
    """
    body = request.get_json(silent=True) or {}
    event_ids = body.get("event_ids") or []
    ticket_ids = body.get("ticket_ids") or []
    mode = body.get("mode", "full")
    reopen = bool(body.get("reopen"))  # jamais automatique — l'utilisateur doit cocher explicitement

    if not event_ids or not ticket_ids:
        return jsonify({"error": "event_ids et ticket_ids requis (au moins un de chaque)"}), 400
    if mode not in ("full", "split"):
        return jsonify({"error": "mode doit être 'full' ou 'split'"}), 400

    weight = 1.0 if mode == "full" else 1.0 / len(ticket_ids)

    conn = get_connection()
    try:
        cur = conn.cursor()

        # Étend automatiquement à tout autre événement NON ENCORE
        # AFFECTÉ partageant exactement le même titre (insensible à la
        # casse/espaces) — traiter un événement traite aussi ses
        # doublons à la volée, sans repasser par la sélection manuelle.
        placeholders = ",".join([PLACEHOLDER] * len(event_ids))
        cur.execute(f"SELECT summary FROM calendar_events WHERE id IN ({placeholders})", event_ids)
        target_summaries = {(r[0] or "").strip().lower() for r in cur.fetchall()} - {""}

        auto_added = []
        if target_summaries:
            cur.execute("""
                SELECT ce.id, ce.summary FROM calendar_events ce
                LEFT JOIN ticket_time_entries tte ON tte.calendar_event_id = ce.id
                WHERE tte.id IS NULL
            """)
            existing_ids = set(event_ids)
            for row in cur.fetchall():
                candidate_id, candidate_summary = row
                if candidate_id in existing_ids:
                    continue
                if (candidate_summary or "").strip().lower() in target_summaries:
                    event_ids.append(candidate_id)
                    existing_ids.add(candidate_id)
                    auto_added.append(candidate_id)

        created = 0
        reopened_ticket_ids = []
        for event_id in event_ids:
            cur.execute(f"SELECT start_ts, end_ts FROM calendar_events WHERE id = {PLACEHOLDER}", [event_id])
            row = cur.fetchone()
            if row is None:
                continue
            start_ts, end_ts = row
            end_ts = end_ts if end_ts is not None else start_ts

            for ticket_id in ticket_ids:
                cur.execute(
                    f"""INSERT INTO ticket_time_entries (ticket_id, calendar_event_id, start_ts, end_ts, weight, created_at)
                        VALUES ({PLACEHOLDER},{PLACEHOLDER},{PLACEHOLDER},{PLACEHOLDER},{PLACEHOLDER},{PLACEHOLDER})""",
                    [ticket_id, event_id, start_ts, end_ts, weight, now_iso()],
                )
                cur.execute(f"UPDATE tickets SET last_change = {PLACEHOLDER} WHERE id = {PLACEHOLDER}", [now_ts(), ticket_id])
                created += 1

        if reopen:
            # Réouverture explicite uniquement — jamais automatique. Ne
            # touche que les tickets réellement fermés parmi ceux
            # sélectionnés, et journalise la transition (cohérent avec
            # PUT /tickets/<id>, pour que le compteur 🔁 reste exact).
            for ticket_id in set(ticket_ids):
                cur.execute(f"SELECT ts_closed FROM tickets WHERE id = {PLACEHOLDER}", [ticket_id])
                row = cur.fetchone()
                if row and row[0] is not None:
                    cur.execute(f"UPDATE tickets SET ts_closed = NULL WHERE id = {PLACEHOLDER}", [ticket_id])
                    cur.execute(
                        f"INSERT INTO ticket_status_log (ticket_id, event_type, ts, created_at) VALUES ({PLACEHOLDER},{PLACEHOLDER},{PLACEHOLDER},{PLACEHOLDER})",
                        [ticket_id, "reopened", now_ts(), now_iso()],
                    )
                    reopened_ticket_ids.append(ticket_id)

        conn.commit()
        return jsonify({
            "status": "ok", "time_entries_created": created, "mode": mode, "weight_per_entry": weight,
            "events_assigned": len(event_ids), "auto_added_duplicates": len(auto_added),
            "reopened_ticket_ids": reopened_ticket_ids,
        }), 200
    finally:
        conn.close()


@app.route("/tickets/parallel", methods=["GET"])
def tickets_parallel():
    """
    Vue tickets parallèles/timeline — axe temporel partagé.
    group_by=ticket (défaut) : une ligne par ticket (vue "individuelle").
    group_by=user|type|level : une ligne par valeur de cette dimension,
    combinant les segments de TOUS les tickets qui la partagent — pour
    une vue "globale" par demandeur/type/niveau plutôt que par ticket
    isolé.
    """
    ticket_ids_param = request.args.get("ticket_ids")
    group_by = request.args.get("group_by", "ticket")
    user_id = request.args.get("user_id")
    if group_by not in ("ticket", "user", "type", "level"):
        return jsonify({"error": "group_by doit être ticket, user, type ou level"}), 400

    conn = get_connection()
    try:
        cur = conn.cursor()
        base_select = """
            SELECT t.id, t.subject, t.user_id, t.type_id, t.level_id,
                   u.login, ty.label, l.label
            FROM tickets t
            LEFT JOIN users u ON t.user_id = u.id
            LEFT JOIN types ty ON t.type_id = ty.id
            LEFT JOIN levels l ON t.level_id = l.id
        """
        if ticket_ids_param:
            ids = [int(x) for x in ticket_ids_param.split(",") if x.strip()]
            placeholders = ",".join([PLACEHOLDER] * len(ids))
            cur.execute(f"{base_select} WHERE t.id IN ({placeholders})", ids)
        elif user_id:
            # Gantt "mes tickets" (portail demandeur) : ouverts ET fermés
            # — l'historique complet du traitement, pas seulement ce qui
            # est encore ouvert (contrairement au comportement par défaut
            # sans filtre, pensé pour la vue technicien/direction).
            cur.execute(f"{base_select} WHERE t.user_id = {PLACEHOLDER} AND t.archived_at IS NULL ORDER BY t.id", [user_id])
        else:
            cur.execute(f"{base_select} WHERE t.ts_closed IS NULL AND t.archived_at IS NULL ORDER BY t.id")
        ticket_rows = cur.fetchall()

        segments_by_ticket = {}
        for row in ticket_rows:
            tid = row[0]
            cur.execute(
                f"SELECT start_ts, end_ts, weight FROM ticket_time_entries WHERE ticket_id = {PLACEHOLDER} ORDER BY start_ts",
                [tid],
            )
            segments_by_ticket[tid] = [{"start_ts": r[0], "end_ts": r[1], "weight": r[2]} for r in cur.fetchall()]

        if group_by == "ticket":
            tickets = [
                {"id": r[0], "subject": r[1], "time_entries": segments_by_ticket[r[0]]}
                for r in ticket_rows
            ]
        else:
            dim_id_idx, dim_label_idx = {"user": (2, 5), "type": (3, 6), "level": (4, 7)}[group_by]
            groups = {}
            for row in ticket_rows:
                dim_id = row[dim_id_idx]
                key = dim_id if dim_id is not None else "none"
                if key not in groups:
                    groups[key] = {
                        "id": key,
                        "subject": row[dim_label_idx] or "(non défini)",
                        "time_entries": [],
                        "ticket_ids": [],
                    }
                groups[key]["time_entries"].extend(segments_by_ticket[row[0]])
                groups[key]["ticket_ids"].append(row[0])
            for g in groups.values():
                g["time_entries"].sort(key=lambda e: e["start_ts"])
            tickets = sorted(groups.values(), key=lambda g: g["subject"])

        return jsonify({"tickets": tickets, "group_by": group_by}), 200
    finally:
        conn.close()


@app.route("/calendar/create_ticket", methods=["POST"])
def calendar_create_ticket():
    """Création AUTOMATIQUE d'un ticket depuis un événement calendrier
    (livraison #273, demandé explicitement : "branche la création
    auto"). Le ticket créé porte `pending_validation=1` -- JAMAIS
    traité comme un ticket pleinement réel tant qu'un humain ne l'a
    pas confirmé via POST /tickets/<id>/validate (même esprit que
    suggestion_engine.py : "la décision finale reste humaine").

    Sujet = résumé de l'événement, description = description de
    l'événement. Demandeur DEVINÉ via `best_candidate_name` (le même
    mécanisme heuristique déjà utilisé pour /calendar/suggest_name)
    -- une correspondance EXACTE (login ou nom, insensible à la
    casse/accents) avec un utilisateur CONNU seulement ; sinon
    `user_id` reste NULL, à compléter manuellement lors de la
    validation (jamais une correspondance approximative appliquée
    silencieusement)."""
    body = request.get_json(silent=True) or {}
    event_id = body.get("event_id")
    if not event_id:
        return jsonify({"error": "'event_id' requis"}), 400

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(f"SELECT * FROM calendar_events WHERE id = {PLACEHOLDER}", [event_id])
        event_row = cur.fetchone()
        if event_row is None:
            return jsonify({"error": "événement introuvable"}), 404
        event = row_to_dict(cur, event_row)

        cur.execute(f"SELECT value FROM matching_config WHERE key = {PLACEHOLDER}", ["trigger_keyword"])
        trigger_row = cur.fetchone()
        trigger_keyword = trigger_row[0] if trigger_row else "SAV"

        candidate_name = best_candidate_name([event], trigger_keyword)
        user_id = None
        if candidate_name:
            candidate_key = strip_accents(candidate_name.lower())
            cur.execute("SELECT id, login FROM users")
            for row in cur.fetchall():
                if strip_accents((row[1] or "").lower()) == candidate_key:
                    user_id = row[0]
                    break

        ts = now_ts()
        # Statut initial selon le moment de l'événement source par
        # rapport à MAINTENANT (livraison #284, demandé explicitement).
        statut_label = determine_calendar_statut_label(event["start_ts"], event.get("end_ts"), ts)
        cur.execute(f"SELECT id FROM statuts WHERE label = {PLACEHOLDER}", [statut_label])
        statut_row = cur.fetchone()
        statut_id = statut_row[0] if statut_row else None

        cur.execute(
            f"""INSERT INTO tickets
                (user_id, subject, description, ts_created, last_change, source_type, source_nom, pending_validation, statut_id)
                VALUES ({PLACEHOLDER},{PLACEHOLDER},{PLACEHOLDER},{PLACEHOLDER},{PLACEHOLDER},{PLACEHOLDER},{PLACEHOLDER},{PLACEHOLDER},{PLACEHOLDER})""",
            [user_id, event["summary"] or "(sans titre)", event.get("description"), ts, ts, "calendar_auto", candidate_name, 1, statut_id],
        )
        conn.commit()
        ticket_id = cur.lastrowid if DB_BACKEND == "sqlite" else _pg_lastval(cur)

        # Statut initial journalisé mais déjà VALIDÉ -- couvert par la
        # validation de la création du ticket elle-même (#273, écran
        # de validation existant) : jamais une double validation pour
        # le MÊME geste. Seules les recalculs ULTÉRIEURS (voir
        # /tickets/<id>/recalculate_status plus bas) entrent
        # réellement dans la file d'attente de validation groupée.
        cur.execute(
            f"""INSERT INTO ticket_status_changes
                (ticket_id, old_statut_id, new_statut_id, reason, changed_by, changed_at, validated_at)
                VALUES ({PLACEHOLDER},{PLACEHOLDER},{PLACEHOLDER},{PLACEHOLDER},{PLACEHOLDER},{PLACEHOLDER},{PLACEHOLDER})""",
            [ticket_id, None, statut_id, f"auto: création, événement '{statut_label.lower()}'", "auto:calendar_create_ticket", now_iso(), now_iso()],
        )
        conn.commit()

        # Rattache l'événement au nouveau ticket -- même mécanisme que
        # /calendar/assign (mode 'full'), MÊME repli end_ts -> start_ts
        # si l'événement n'a pas de fin connue (motif déjà établi
        # là-bas, repris ici à l'identique -- bug réel trouvé en
        # testant : end_ts et created_at sont NOT NULL, oubliés dans
        # une première version de cette route).
        end_ts = event.get("end_ts") if event.get("end_ts") is not None else event["start_ts"]
        cur.execute(
            f"""INSERT INTO ticket_time_entries (ticket_id, calendar_event_id, start_ts, end_ts, weight, created_at)
                VALUES ({PLACEHOLDER},{PLACEHOLDER},{PLACEHOLDER},{PLACEHOLDER},{PLACEHOLDER},{PLACEHOLDER})""",
            [ticket_id, event_id, event["start_ts"], end_ts, 1.0, now_iso()],
        )
        conn.commit()

        return jsonify({"status": "ok", "ticket_id": ticket_id, "guessed_user_id": user_id, "guessed_name": candidate_name, "assigned_statut": statut_label}), 201
    finally:
        conn.close()


@app.route("/tickets/pending_validation", methods=["GET"])
def list_pending_validation_tickets():
    """Écran de validation (livraison #273, demandé explicitement :
    "ajoute un écran de validation des tickets automatique") -- liste
    UNIQUEMENT les tickets créés automatiquement et pas encore
    confirmés."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM tickets WHERE pending_validation = 1 ORDER BY ts_created DESC")
        tickets = [row_to_dict(cur, r) for r in cur.fetchall()]
        return jsonify({"tickets": tickets}), 200
    finally:
        conn.close()


@app.route("/tickets/<int:ticket_id>/validate", methods=["POST"])
def validate_ticket(ticket_id):
    """Confirme un ticket créé automatiquement -- corps JSON optionnel
    pour CORRIGER le demandeur/type/niveau/statut deviné avant
    confirmation définitive (ex. {"user_id": 5}) -- jamais requis,
    l'appelant peut aussi valider tel quel."""
    body = request.get_json(silent=True) or {}
    editable = ["user_id", "type_id", "level_id", "statut_id"]
    fields_to_update = {k: v for k, v in body.items() if k in editable}

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(f"SELECT pending_validation FROM tickets WHERE id = {PLACEHOLDER}", [ticket_id])
        row = cur.fetchone()
        if row is None:
            return jsonify({"error": "ticket introuvable"}), 404
        if row[0] != 1:
            return jsonify({"error": "ce ticket n'est pas en attente de validation"}), 400

        fields_to_update["pending_validation"] = 0
        fields_to_update["last_change"] = now_ts()
        set_clause = ", ".join(f"{col} = {PLACEHOLDER}" for col in fields_to_update)
        cur.execute(f"UPDATE tickets SET {set_clause} WHERE id = {PLACEHOLDER}", [*fields_to_update.values(), ticket_id])
        conn.commit()
        return jsonify({"status": "ok"}), 200
    finally:
        conn.close()


@app.route("/tickets/<int:ticket_id>", methods=["DELETE"])
def delete_pending_ticket(ticket_id):
    """Suppression RÉELLE -- livraison #284, demandé explicitement
    ("retour en arrière" sur un ticket auto-créé = "supprime").
    SCOPÉE aux tickets encore `pending_validation=1` UNIQUEMENT --
    jamais un vrai DELETE sur un ticket déjà confirmé/réel (même
    prudence que partout ailleurs dans ce projet, voir
    tickets/README.md -- l'exception ici est délibérée et étroite :
    annuler un geste qui n'a jamais été confirmé n'est pas supprimer
    une donnée réelle)."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(f"SELECT pending_validation FROM tickets WHERE id = {PLACEHOLDER}", [ticket_id])
        row = cur.fetchone()
        if row is None:
            return jsonify({"error": "ticket introuvable"}), 404
        if row[0] != 1:
            return jsonify({"error": "ce ticket est déjà validé -- suppression réelle refusée, utiliser l'archivage (PUT archived_at)"}), 400
        cur.execute(f"DELETE FROM ticket_time_entries WHERE ticket_id = {PLACEHOLDER}", [ticket_id])
        cur.execute(f"DELETE FROM ticket_status_changes WHERE ticket_id = {PLACEHOLDER}", [ticket_id])
        cur.execute(f"DELETE FROM tickets WHERE id = {PLACEHOLDER}", [ticket_id])
        conn.commit()
        return jsonify({"status": "ok", "deleted": True}), 200
    finally:
        conn.close()


@app.route("/tickets/import-external", methods=["POST"])
def import_external_ticket():
    """Création d'un ticket À VALIDER depuis un système EXTERNE
    (livraison #484, demandé explicitement : les demandes ProjeQtOr
    doivent arriver « dans la liste des imports à valider », même file
    que les imports calendrier #273). Appelé par projeqtor-bridge sur
    le réseau Docker interne, jamais par un navigateur.

    MÊMES règles que /calendar/create_ticket : pending_validation=1
    tant qu'un humain n'a pas confirmé via /tickets/<id>/validate.

    Déduplication ICI (et pas chez l'appelant) : un ticket déjà connu
    pour le même (source_type, source_nom) renvoie 409 SANS rien
    créer — la source de vérité anti-doublon vit dans cette base, pas
    dans un fichier d'état d'un service tiers qui peut se perdre.
    """
    body = request.get_json(silent=True) or {}
    subject = (body.get("subject") or "").strip()
    source_type = (body.get("source_type") or "").strip()
    source_nom = (body.get("source_nom") or "").strip()
    if not subject or not source_type or not source_nom:
        return jsonify({"error": "'subject', 'source_type' et 'source_nom' requis"}), 400

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            f"SELECT id FROM tickets WHERE source_type = {PLACEHOLDER} AND source_nom = {PLACEHOLDER}",
            [source_type, source_nom],
        )
        existing = cur.fetchone()
        if existing is not None:
            return jsonify({"status": "connu", "ticket_id": existing[0]}), 409

        ts = now_ts()
        cur.execute(
            f"""INSERT INTO tickets
                (user_id, subject, description, ts_created, last_change, source_type, source_nom, pending_validation)
                VALUES ({PLACEHOLDER},{PLACEHOLDER},{PLACEHOLDER},{PLACEHOLDER},{PLACEHOLDER},{PLACEHOLDER},{PLACEHOLDER},{PLACEHOLDER})""",
            [None, subject, body.get("description"), ts, ts, source_type, source_nom, 1],
        )
        conn.commit()
        ticket_id = cur.lastrowid if DB_BACKEND == "sqlite" else _pg_lastval(cur)
        return jsonify({"status": "ok", "ticket_id": ticket_id, "pending_validation": 1}), 201
    finally:
        conn.close()


@app.route("/tickets/<int:ticket_id>/recalculate_status", methods=["POST"])
def recalculate_ticket_status(ticket_id):
    """Livraison #284, demandé explicitement -- réévalue le statut
    d'un ticket issu du calendrier "à la consultation" : appelé
    explicitement par l'appelant (jamais un déclenchement magique en
    arrière-plan -- l'interface décide QUAND une "consultation"
    compte, par exemple à l'ouverture de l'écran de Validation ou de
    la vue Calendrier). Contrairement au statut INITIAL (posé à la
    création, déjà validé de facto via #273), un recalcul qui change
    RÉELLEMENT le statut entre dans la file d'attente de validation
    groupée (`validated_at` NULL) -- jamais appliqué directement à
    `tickets.statut_id` avant validation."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            f"""SELECT t.statut_id, tte.calendar_event_id
                FROM tickets t
                LEFT JOIN ticket_time_entries tte ON tte.ticket_id = t.id
                WHERE t.id = {PLACEHOLDER}
                ORDER BY tte.id LIMIT 1""",
            [ticket_id],
        )
        row = cur.fetchone()
        if row is None:
            return jsonify({"error": "ticket introuvable"}), 404
        current_statut_id, event_id = row
        if event_id is None:
            return jsonify({"error": "ce ticket n'est rattaché à aucun événement calendrier -- rien à recalculer"}), 400

        cur.execute(f"SELECT start_ts, end_ts FROM calendar_events WHERE id = {PLACEHOLDER}", [event_id])
        event_row = cur.fetchone()
        if event_row is None:
            return jsonify({"error": "événement source introuvable"}), 404
        start_ts, end_ts = event_row

        new_label = determine_calendar_statut_label(start_ts, end_ts, now_ts())
        cur.execute(f"SELECT id FROM statuts WHERE label = {PLACEHOLDER}", [new_label])
        statut_row = cur.fetchone()
        new_statut_id = statut_row[0] if statut_row else None

        if new_statut_id == current_statut_id:
            return jsonify({"status": "ok", "changed": False, "statut": new_label}), 200

        cur.execute(
            f"""INSERT INTO ticket_status_changes
                (ticket_id, old_statut_id, new_statut_id, reason, changed_by, changed_at, validated_at)
                VALUES ({PLACEHOLDER},{PLACEHOLDER},{PLACEHOLDER},{PLACEHOLDER},{PLACEHOLDER},{PLACEHOLDER},{PLACEHOLDER})""",
            [ticket_id, current_statut_id, new_statut_id, f"auto: consultation, événement '{new_label.lower()}'", "auto:recalculate_status", now_iso(), None],
        )
        conn.commit()
        return jsonify({"status": "ok", "changed": True, "statut": new_label, "pending_validation": True}), 200
    finally:
        conn.close()


@app.route("/status-changes/pending", methods=["GET"])
def list_pending_status_changes():
    """Écran de validation GROUPÉE (livraison #284, demandé
    explicitement : "ouvrir une fenêtre de validation pour
    l'ensemble des modif (pas à chacune)") -- liste TOUS les
    changements en attente à la fois, jamais un par un."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """SELECT sc.*, t.subject AS ticket_subject,
                      os.label AS old_label, ns.label AS new_label
               FROM ticket_status_changes sc
               JOIN tickets t ON t.id = sc.ticket_id
               LEFT JOIN statuts os ON os.id = sc.old_statut_id
               LEFT JOIN statuts ns ON ns.id = sc.new_statut_id
               WHERE sc.validated_at IS NULL
               ORDER BY sc.changed_at"""
        )
        changes = [row_to_dict(cur, r) for r in cur.fetchall()]
        return jsonify({"changes": changes}), 200
    finally:
        conn.close()


@app.route("/status-changes/validate_all", methods=["POST"])
def validate_all_status_changes():
    """Applique TOUS les changements en attente à la fois (jamais un
    écran par changement, demandé explicitement) -- pour chacun :
    applique new_statut_id sur le ticket, marque le changement comme
    validé (`validated_at`, JAMAIS supprimé -- permanent, demandé
    explicitement)."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, ticket_id, new_statut_id FROM ticket_status_changes WHERE validated_at IS NULL")
        pending = cur.fetchall()
        validated_at = now_iso()
        for change_id, ticket_id, new_statut_id in pending:
            cur.execute(f"UPDATE tickets SET statut_id = {PLACEHOLDER}, last_change = {PLACEHOLDER} WHERE id = {PLACEHOLDER}", [new_statut_id, now_ts(), ticket_id])
            cur.execute(f"UPDATE ticket_status_changes SET validated_at = {PLACEHOLDER} WHERE id = {PLACEHOLDER}", [validated_at, change_id])
        conn.commit()
        return jsonify({"status": "ok", "applied": len(pending)}), 200
    finally:
        conn.close()


@app.route("/calendar/import", methods=["POST"])
def calendar_import_upload():
    """Import par upload direct d'un fichier .ics (ex: export Thunderbird/Lightning).

    Protégée par rights-api (#327) -- `groups` lu depuis les
    paramètres de requête (`?groups=...`), jamais le corps JSON ni un
    formulaire ici : cette route accepte soit un fichier multipart,
    soit le contenu ICS brut directement en corps de requête (voir
    ci-dessous), aucun des deux ne garantit un canal standard pour
    transmettre les groupes."""
    allowed, error = _check_manage_right({"groups": request.args.getlist("groups")})
    if not allowed:
        return jsonify({"error": error}), 403
    if "file" in request.files:
        raw_ics = request.files["file"].read().decode("utf-8", errors="replace")
    else:
        raw_ics = request.get_data(as_text=True)
    if not raw_ics.strip():
        return jsonify({"error": "fichier .ics vide ou absent"}), 400

    summary = import_ics_events(raw_ics, source="thunderbird_import")
    return jsonify(summary), 200


# ============================================================
# Connecteur OAuth2 Google Calendar — alternative à l'adresse secrète
# iCal. Non testé contre un vrai compte Google (pas de réseau/compte
# disponible pendant le développement) — voir google_oauth.py.
# ============================================================
_pending_oauth_state = {"value": None}  # outil mono-opérateur, pas de session multi-utilisateur


@app.route("/oauth/google/status", methods=["GET"])
def oauth_google_status():
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(f"SELECT 1 FROM oauth_credentials WHERE provider = {PLACEHOLDER}", ["google"])
        connected = cur.fetchone() is not None
    finally:
        conn.close()
    return jsonify({"configured": google_oauth.is_configured(), "connected": connected}), 200


@app.route("/oauth/google/start", methods=["GET"])
def oauth_google_start():
    """Protégée par rights-api (#330) -- `groups` lu depuis les
    paramètres de requête (`?groups=...`), jamais un corps JSON :
    cette route est une REDIRECTION navigateur initiée par un clic,
    aucun corps de requête possible. Résout la limite documentée en
    passe 4 (#327) -- connecter un compte Google différent
    redéfinit la SOURCE calendrier pour tout le monde, arguablement
    plus consequential qu'un simple import déjà gardé. Protéger cette
    route protège indirectement /oauth/google/callback aussi : son
    contrôle CSRF (`state`) exige qu'un `/start` autorisé ait déjà eu
    lieu -- un appel direct au callback sans state valide échoue de
    toute façon, avec ou sans rights-api."""
    allowed, error = _check_manage_right({"groups": request.args.getlist("groups")})
    if not allowed:
        return jsonify({"error": error}), 403
    if not google_oauth.is_configured():
        return jsonify({"error": "GOOGLE_OAUTH_CLIENT_ID / GOOGLE_OAUTH_CLIENT_SECRET non configurés"}), 400
    state = secrets.token_urlsafe(24)
    _pending_oauth_state["value"] = state
    return redirect(google_oauth.build_authorization_url(state))


@app.route("/oauth/google/callback", methods=["GET"])
def oauth_google_callback():
    error = request.args.get("error")
    if error:
        return f"<p>Autorisation refusée ou échouée côté Google : {error}</p>", 400

    code = request.args.get("code")
    state = request.args.get("state")
    if not code:
        return "<p>Paramètre 'code' manquant dans la redirection Google.</p>", 400
    if state != _pending_oauth_state["value"]:
        return "<p>État OAuth invalide (CSRF ?) — relance le flux depuis /oauth/google/start.</p>", 400
    _pending_oauth_state["value"] = None

    try:
        tokens = google_oauth.exchange_code_for_tokens(code)
    except Exception as exc:  # noqa: BLE001 — requests.RequestException ou JSON invalide
        return f"<p>Échec de l'échange du code contre un jeton : {exc}</p>", 502

    refresh_token = tokens.get("refresh_token")
    if not refresh_token:
        return (
            "<p>Google n'a renvoyé aucun refresh_token — arrive si un consentement a déjà été "
            "donné précédemment sans révocation. Révoque l'accès dans "
            "<a href='https://myaccount.google.com/permissions' target='_blank'>myaccount.google.com/permissions</a> "
            "puis relance /oauth/google/start.</p>"
        ), 400

    expires_at = int(time.time()) + int(tokens.get("expires_in", 3600))
    conn = get_connection()
    try:
        cur = conn.cursor()
        if DB_BACKEND == "postgres":
            cur.execute(
                "INSERT INTO oauth_credentials (provider, refresh_token, access_token, access_token_expires_at, updated_at) "
                "VALUES (%s,%s,%s,%s,%s) ON CONFLICT (provider) DO UPDATE SET "
                "refresh_token = EXCLUDED.refresh_token, access_token = EXCLUDED.access_token, "
                "access_token_expires_at = EXCLUDED.access_token_expires_at, updated_at = EXCLUDED.updated_at",
                ["google", refresh_token, tokens.get("access_token"), expires_at, now_iso()],
            )
        else:
            cur.execute(
                "INSERT OR REPLACE INTO oauth_credentials (provider, refresh_token, access_token, access_token_expires_at, updated_at) "
                "VALUES (?,?,?,?,?)",
                ["google", refresh_token, tokens.get("access_token"), expires_at, now_iso()],
            )
        conn.commit()
    finally:
        conn.close()

    return "<p>✅ Agenda Google connecté. Tu peux fermer cet onglet et retourner sur Supervision SI.</p>", 200


def _get_valid_google_access_token():
    """Renvoie un access_token valide (rafraîchi si besoin), ou None si aucune connexion établie."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            f"SELECT refresh_token, access_token, access_token_expires_at FROM oauth_credentials WHERE provider = {PLACEHOLDER}",
            ["google"],
        )
        row = cur.fetchone()
        if row is None:
            return None
        refresh_token, access_token, expires_at = row

        if access_token and expires_at and expires_at > int(time.time()) + 60:
            return access_token

        tokens = google_oauth.refresh_access_token(refresh_token)
        new_access_token = tokens["access_token"]
        new_expires_at = int(time.time()) + int(tokens.get("expires_in", 3600))
        cur.execute(
            f"UPDATE oauth_credentials SET access_token = {PLACEHOLDER}, access_token_expires_at = {PLACEHOLDER}, updated_at = {PLACEHOLDER} WHERE provider = {PLACEHOLDER}",
            [new_access_token, new_expires_at, now_iso(), "google"],
        )
        conn.commit()
        return new_access_token
    finally:
        conn.close()


@app.route("/calendar/import_google_api", methods=["POST"])
def import_google_api():
    """Protégée par rights-api (#327)."""
    body = request.get_json(silent=True) or {}
    allowed, error = _check_manage_right(body)
    if not allowed:
        return jsonify({"error": error}), 403
    access_token = _get_valid_google_access_token()
    if access_token is None:
        return jsonify({"error": "Agenda Google non connecté — passe par /oauth/google/start d'abord"}), 400

    try:
        events = google_oauth.fetch_calendar_events(access_token)
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": f"échec de récupération des événements : {exc}"}), 502

    summary = import_parsed_events(events, source="google_oauth_api")
    return jsonify(summary), 200


@app.route("/calendar/import_url", methods=["POST"])
def calendar_import_url():
    """Import depuis une URL (adresse secrète iCal de Google).

    Protégée par rights-api (#327)."""
    import requests

    body = request.get_json(silent=True) or {}
    allowed, error = _check_manage_right(body)
    if not allowed:
        return jsonify({"error": error}), 403
    url = body.get("url")
    if not url:
        return jsonify({"error": "paramètre 'url' requis"}), 400

    try:
        # Certains serveurs (dont parfois Google) répondent différemment
        # sans User-Agent explicite — le client par défaut de `requests`
        # peut se faire bloquer/rediriger silencieusement.
        response = requests.get(
            url, timeout=30,
            headers={"User-Agent": "Mozilla/5.0 (compatible; supervision-si-tickets/1.0)"},
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        return jsonify({"error": f"échec de récupération de l'URL : {exc}"}), 502

    raw_text = response.text
    summary = import_ics_events(raw_text, source="google_ics")

    # Diagnostic si rien n'a été trouvé — la requête a réussi (sinon on
    # serait déjà sorti ci-dessus), mais le contenu récupéré n'était
    # peut-être pas du vrai ICS (page de connexion, redirection HTML...).
    if summary["total_events"] == 0:
        summary["diagnostic"] = {
            "http_status": response.status_code,
            "content_type": response.headers.get("Content-Type", "inconnu"),
            "content_length": len(raw_text),
            "looks_like_ics": "BEGIN:VCALENDAR" in raw_text,
            "content_preview": raw_text[:300],
        }

    return jsonify(summary), 200


# ============================================================
# Export / import JSON de toute la base
# ============================================================
# Ordre parents -> enfants pour l'insertion (respecte les clés
# étrangères) ; l'ordre inverse est utilisé pour la suppression en
# mode "replace".
# ============================================================
# Portail multi-profils (front tickets/portal) — même API, même base.
# Aucune authentification (comme le reste du projet) : le portail
# identifie par login et route l'interface selon users.role. Ce n'est
# PAS une barrière de sécurité, juste une séparation d'usages.
# ============================================================

@app.route("/portal/profile", methods=["GET"])
def portal_profile():
    """Résout un login (insensible à la casse, espaces tolérés) vers
    l'utilisateur et son rôle. 404 si inconnu — le portail propose
    alors la création d'un compte demandeur uniquement."""
    login = (request.args.get("login") or "").strip()
    if not login:
        return jsonify({"error": "paramètre login requis"}), 400
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(f"SELECT * FROM users WHERE LOWER(login) = LOWER({PLACEHOLDER})", [login])
        row = cur.fetchone()
        if row is None:
            return jsonify({"error": f"login '{login}' inconnu"}), 404
        return jsonify(row_to_dict(cur, row)), 200
    finally:
        conn.close()


@app.route("/tickets/<int:ticket_id>/messages", methods=["GET"])
def list_ticket_messages(ticket_id):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(f"SELECT 1 FROM tickets WHERE id = {PLACEHOLDER}", [ticket_id])
        if cur.fetchone() is None:
            return jsonify({"error": "ticket introuvable"}), 404
        cur.execute(
            f"""SELECT m.id, m.ticket_id, m.user_id, m.body, m.created_ts, m.created_at, m.acted_by_user_id,
                       u.login AS author_login, u.name AS author_name, u.role AS author_role,
                       a.login AS acted_by_login, a.name AS acted_by_name
                FROM ticket_messages m
                LEFT JOIN users u ON u.id = m.user_id
                LEFT JOIN users a ON a.id = m.acted_by_user_id
                WHERE m.ticket_id = {PLACEHOLDER}
                ORDER BY m.created_ts, m.id""",
            [ticket_id],
        )
        return jsonify([row_to_dict(cur, r) for r in cur.fetchall()]), 200
    finally:
        conn.close()


@app.route("/tickets/<int:ticket_id>/messages", methods=["POST"])
def post_ticket_message(ticket_id):
    body = request.get_json(silent=True) or {}
    text = (body.get("body") or "").strip()
    if not text:
        return jsonify({"error": "message vide"}), 400
    user_id = body.get("user_id")
    acted_by_user_id = body.get("acted_by_user_id")
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(f"SELECT 1 FROM tickets WHERE id = {PLACEHOLDER}", [ticket_id])
        if cur.fetchone() is None:
            return jsonify({"error": "ticket introuvable"}), 404
        if user_id is not None:
            cur.execute(f"SELECT 1 FROM users WHERE id = {PLACEHOLDER}", [user_id])
            if cur.fetchone() is None:
                return jsonify({"error": f"utilisateur {user_id} introuvable"}), 400
        if acted_by_user_id is not None:
            cur.execute(f"SELECT 1 FROM users WHERE id = {PLACEHOLDER}", [acted_by_user_id])
            if cur.fetchone() is None:
                return jsonify({"error": f"utilisateur {acted_by_user_id} (acted_by) introuvable"}), 400
        ts = now_ts()
        cur.execute(
            f"""INSERT INTO ticket_messages (ticket_id, user_id, body, created_ts, created_at, acted_by_user_id)
                VALUES ({PLACEHOLDER},{PLACEHOLDER},{PLACEHOLDER},{PLACEHOLDER},{PLACEHOLDER},{PLACEHOLDER})""",
            [ticket_id, user_id, text, ts, now_iso(), acted_by_user_id],
        )
        # Un message est une activité réelle sur le ticket.
        cur.execute(
            f"UPDATE tickets SET last_change = {PLACEHOLDER} WHERE id = {PLACEHOLDER}",
            [ts, ticket_id],
        )
        conn.commit()
        new_id = cur.lastrowid if DB_BACKEND == "sqlite" else _pg_lastval(cur)
        return jsonify({"status": "ok", "id": new_id}), 201
    finally:
        conn.close()


@app.route("/tickets/<int:ticket_id>/children", methods=["GET"])
def list_ticket_children(ticket_id):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(f"SELECT 1 FROM tickets WHERE id = {PLACEHOLDER}", [ticket_id])
        if cur.fetchone() is None:
            return jsonify({"error": "ticket introuvable"}), 404
        cur.execute(
            f"""SELECT t.*, u.login AS user_login, s.label AS statut_label
                FROM tickets t
                LEFT JOIN users u ON u.id = t.user_id
                LEFT JOIN statuts s ON s.id = t.statut_id
                WHERE t.parent_ticket_id = {PLACEHOLDER}
                ORDER BY t.ts_created""",
            [ticket_id],
        )
        return jsonify([row_to_dict(cur, r) for r in cur.fetchall()]), 200
    finally:
        conn.close()


# --- Statistiques (vue politique + éditeur admin) ---

STATS_DIMENSIONS = {
    # group_by -> (table jointe, alias, colonne FK sur tickets, colonne label)
    "user":   ("users",   "u", "user_id",   "u.login"),
    "type":   ("types",   "y", "type_id",   "y.label"),
    "level":  ("levels",  "l", "level_id",  "l.label"),
    "statut": ("statuts", "s", "statut_id", "s.label"),
}
STATS_MEASURES = ("count", "time")
STATS_STATES = ("open", "closed", "all")


def _stats_state_condition(state):
    if state == "open":
        return "t.ts_closed IS NULL"
    if state == "closed":
        return "t.ts_closed IS NOT NULL"
    return "1=1"


@app.route("/stats/aggregate", methods=["GET"])
def stats_aggregate():
    """
    Agrégat générique whitelisté — la brique de l'éditeur de
    statistiques : group_by (user|type|level|statut) × measure
    (count = nombre de tickets, time = temps pondéré en secondes)
    × state (open|closed|all). Aucun nom de table/colonne ne vient
    de la requête : tout passe par les dictionnaires ci-dessus.
    """
    group_by = request.args.get("group_by", "statut")
    measure = request.args.get("measure", "count")
    state = request.args.get("state", "all")
    if group_by not in STATS_DIMENSIONS:
        return jsonify({"error": f"group_by invalide (attendus : {list(STATS_DIMENSIONS)})"}), 400
    if measure not in STATS_MEASURES:
        return jsonify({"error": f"measure invalide (attendus : {list(STATS_MEASURES)})"}), 400
    if state not in STATS_STATES:
        return jsonify({"error": f"state invalide (attendus : {list(STATS_STATES)})"}), 400

    table, alias, fk, label_col = STATS_DIMENSIONS[group_by]
    state_cond = _stats_state_condition(state)
    conn = get_connection()
    try:
        cur = conn.cursor()
        if measure == "count":
            cur.execute(
                f"""SELECT COALESCE({label_col}, '(non défini)') AS label, COUNT(t.id) AS value
                    FROM tickets t
                    LEFT JOIN {table} {alias} ON {alias}.id = t.{fk}
                    WHERE {state_cond}
                    GROUP BY {label_col}
                    ORDER BY value DESC"""
            )
        else:  # time — somme pondérée des segments, par dimension
            cur.execute(
                f"""SELECT COALESCE({label_col}, '(non défini)') AS label,
                           COALESCE(SUM((e.end_ts - e.start_ts) * e.weight), 0) AS value
                    FROM tickets t
                    LEFT JOIN {table} {alias} ON {alias}.id = t.{fk}
                    LEFT JOIN ticket_time_entries e ON e.ticket_id = t.id
                    WHERE {state_cond}
                    GROUP BY {label_col}
                    ORDER BY value DESC"""
            )
        rows = [row_to_dict(cur, r) for r in cur.fetchall()]
        return jsonify({"group_by": group_by, "measure": measure, "state": state, "rows": rows}), 200
    finally:
        conn.close()


@app.route("/stats/summary", methods=["GET"])
def stats_summary():
    """Synthèse d'ensemble pour la vue politique : volumes ouverts/
    fermés, temps total pondéré, répartitions par statut et niveau.
    Tickets archivés exclus (masqués des vues opérationnelles, même
    principe que /queue)."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM tickets WHERE ts_closed IS NULL AND archived_at IS NULL")
        open_count = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM tickets WHERE ts_closed IS NOT NULL AND archived_at IS NULL")
        closed_count = cur.fetchone()[0]
        cur.execute("SELECT COALESCE(SUM((end_ts - start_ts) * weight), 0) FROM ticket_time_entries")
        total_seconds = cur.fetchone()[0]
        cur.execute(
            """SELECT COALESCE(s.label, '(non défini)') AS label, COUNT(t.id) AS value
               FROM tickets t LEFT JOIN statuts s ON s.id = t.statut_id
               WHERE t.archived_at IS NULL
               GROUP BY s.label ORDER BY value DESC"""
        )
        by_statut = [row_to_dict(cur, r) for r in cur.fetchall()]
        cur.execute(
            """SELECT COALESCE(l.label, '(non défini)') AS label, COUNT(t.id) AS value
               FROM tickets t LEFT JOIN levels l ON l.id = t.level_id
               WHERE t.ts_closed IS NULL AND t.archived_at IS NULL
               GROUP BY l.label ORDER BY value DESC"""
        )
        open_by_level = [row_to_dict(cur, r) for r in cur.fetchall()]
        return jsonify({
            "open": open_count, "closed": closed_count, "total": open_count + closed_count,
            "total_seconds": total_seconds,
            "by_statut": by_statut, "open_by_level": open_by_level,
        }), 200
    finally:
        conn.close()


@app.route("/stats/reopenings", methods=["GET"])
def stats_reopenings():
    """Vue "réouvertures" (direction) : un ticket par ligne parmi ceux
    rouverts au moins une fois, avec le compte et la date de la
    dernière réouverture — pas juste reopen_count (déjà dans /queue),
    ici l'objet même de l'écran plutôt qu'un détail parmi d'autres.
    S'appuie entièrement sur ticket_status_log, déjà alimenté par
    update_ticket() à chaque transition ts_closed — rien de nouveau à
    journaliser, juste à l'agréger différemment."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """SELECT t.id, t.subject, u.login AS user_login, t.ts_closed, t.archived_at,
                      COUNT(tsl.id) AS reopen_count, MAX(tsl.ts) AS last_reopened_ts
               FROM ticket_status_log tsl
               JOIN tickets t ON t.id = tsl.ticket_id
               LEFT JOIN users u ON u.id = t.user_id
               WHERE tsl.event_type = 'reopened'
               GROUP BY t.id, t.subject, u.login, t.ts_closed, t.archived_at
               ORDER BY reopen_count DESC, last_reopened_ts DESC"""
        )
        rows = [row_to_dict(cur, r) for r in cur.fetchall()]
        return jsonify({"tickets": rows}), 200
    finally:
        conn.close()


TABLE_ORDER = [
    "users", "types", "levels", "statuts", "matching_config",
    "exclusion_rules", "priority_keywords", "oauth_credentials",
    "tickets", "calendar_events", "calendar_filter_rules",
    "ticket_time_entries", "ticket_status_log", "ticket_messages",
]
SERIAL_ID_TABLES = [t for t in TABLE_ORDER if t not in ("matching_config", "oauth_credentials")]  # clés texte, pas de séquence


@app.route("/export", methods=["GET"])
def export_database():
    conn = get_connection()
    try:
        cur = conn.cursor()
        dump = {}
        for table in TABLE_ORDER:
            cur.execute(f"SELECT * FROM {table}")
            dump[table] = [row_to_dict(cur, r) for r in cur.fetchall()]
        return jsonify(dump), 200
    finally:
        conn.close()


def reset_pg_sequence(cur, table):
    cur.execute(f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), COALESCE((SELECT MAX(id) FROM {table}), 1))")


@app.route("/import", methods=["POST"])
def import_database():
    """
    mode=merge (défaut) : upsert par id — insère les nouveaux
    enregistrements, met à jour ceux dont l'id existe déjà, ne touche
    pas au reste de la base.
    mode=replace : vide entièrement les tables concernées avant de
    réinsérer — destructeur, à utiliser sciemment (restauration
    complète depuis une sauvegarde).

    Protégée par rights-api (#328) -- même sévérité que le cluster
    console DB/SQL de la passe 1 (mode=replace VIDE toute la base ;
    même mode=merge permet d'injecter des lignes arbitraires dans
    n'importe quelle table via JSON brut, bypass toute validation
    métier des routes typées normales)."""
    body = request.get_json(silent=True)
    allowed, error = _check_manage_right(body if isinstance(body, dict) else {})
    if not allowed:
        return jsonify({"error": error}), 403
    mode = request.args.get("mode", "merge")
    if mode not in ("merge", "replace"):
        return jsonify({"error": "mode doit être 'merge' ou 'replace'"}), 400

    if not isinstance(body, dict):
        return jsonify({"error": "corps JSON invalide — attendu : objet {table: [lignes...]}"}), 400
    body = {k: v for k, v in body.items() if k != "groups"}  # jamais une table -- uniquement pour la vérification des droits ci-dessus

    unknown_tables = set(body.keys()) - set(TABLE_ORDER)
    if unknown_tables:
        return jsonify({"error": f"table(s) inconnue(s) : {sorted(unknown_tables)}"}), 400

    conn = get_connection()
    try:
        cur = conn.cursor()

        if mode == "replace":
            # Vide TOUTES les tables, pas seulement celles présentes dans
            # le JSON fourni — sinon une table absente du dump (ex: on
            # importe seulement users/types/levels) garderait ses lignes
            # existantes, qui peuvent référencer les parents en train
            # d'être supprimés (violation de clé étrangère). "replace"
            # = restauration complète, pas remplacement table par table.
            for table in reversed(TABLE_ORDER):
                cur.execute(f"DELETE FROM {table}")

        counts = {}
        for table in TABLE_ORDER:
            rows = body.get(table)
            if not rows:
                continue

            columns = list(rows[0].keys())
            col_list = ", ".join(columns)
            placeholders = ", ".join([PLACEHOLDER] * len(columns))

            if DB_BACKEND == "postgres":
                update_clause = ", ".join(f"{c} = EXCLUDED.{c}" for c in columns if c != "id")
                key_col = "key" if table == "matching_config" else "id"
                conflict_action = f"DO UPDATE SET {update_clause}" if update_clause else "DO NOTHING"
                query = (
                    f"INSERT INTO {table} ({col_list}) VALUES ({placeholders}) "
                    f"ON CONFLICT ({key_col}) DO {conflict_action}"
                )
            else:
                query = f"INSERT OR REPLACE INTO {table} ({col_list}) VALUES ({placeholders})"

            for row in rows:
                cur.execute(query, [row.get(c) for c in columns])
            counts[table] = len(rows)

        if DB_BACKEND == "postgres":
            for table in SERIAL_ID_TABLES:
                if table in body and body[table]:
                    reset_pg_sequence(cur, table)

        conn.commit()
        return jsonify({"status": "ok", "mode": mode, "rows_imported": counts}), 200
    except Exception as exc:  # noqa: BLE001
        conn.rollback()
        return jsonify({"error": f"échec de l'import : {exc}"}), 400
    finally:
        conn.close()


# ------------------------------------------------------------------
# Journal en memoire (endpoint /logs) -- capture les WARNING et plus
# graves de CE service pour l'agregateur de logs du frontend (onglet
# Logs + bandeau pied de page). Ne capture PAS le corps des requetes
# ni de donnee metier -- seulement ce que ce fichier journalise deja
# lui-meme (app.logger.warning/error) plus les exceptions non gerees
# que Flask/Werkzeug journalisent nativement en ERROR. Tampon
# circulaire en memoire, borne (LOG_BUFFER_SIZE, defaut 200), jamais
# persiste sur disque -- perdu au redemarrage du conteneur, attendu
# pour un outil de diagnostic a chaud, pas un historique long terme.
# Seuil par defaut WARNING (pas INFO) : evite de capturer le bruit des
# logs d'acces Werkzeug (une ligne par requete HTTP, y compris le
# polling de /logs lui-meme), qui noierait le signal utile.
# ------------------------------------------------------------------
# Client Memcached -- livraison #145, nécessaire au tampon de logs
# PARTAGÉ ci-dessous (ce service tourne avec 2 workers Gunicorn,
# processus séparés, mémoire NON partagée). Recréé à chaque appel
# (même motif établi ailleurs dans ce projet, voir api/app.py) --
# évite de garder une connexion morte si Memcached redémarre.
from pymemcache.client.base import Client as _MemcacheClient

MEMCACHED_HOST = os.environ.get("MEMCACHED_HOST", "memcached")
MEMCACHED_PORT = int(os.environ.get("MEMCACHED_PORT", "11211"))


def get_memcache_client():
    return _MemcacheClient((MEMCACHED_HOST, MEMCACHED_PORT), connect_timeout=2, timeout=2)


# Journal PARTAGE (endpoint /logs) -- stocke dans Memcached (voir
# shared/log_buffer.py pour le raisonnement complet) -- PAS un tampon
# en memoire de processus.
try:
    from log_buffer import make_shared_log_handler, read_shared_log_buffer
except ImportError:
    make_shared_log_handler = None
    read_shared_log_buffer = None

SERVICE_NAME = "tickets-api"
LOG_BUFFER_SIZE = int(os.environ.get("LOG_BUFFER_SIZE", "200"))
LOG_CAPTURE_LEVEL = os.environ.get("LOG_CAPTURE_LEVEL", "WARNING").strip().upper()

if make_shared_log_handler:
    import logging as _logging
    _log_handler = make_shared_log_handler(
        SERVICE_NAME, get_memcache_client, buffer_size=LOG_BUFFER_SIZE, capture_level=LOG_CAPTURE_LEVEL,
    )
    _logging.getLogger().addHandler(_log_handler)


@app.route("/logs", methods=["GET"])
def get_logs():
    limit = request.args.get("limit", type=int)
    entries = read_shared_log_buffer(SERVICE_NAME, get_memcache_client, limit=limit, buffer_size=LOG_BUFFER_SIZE) if read_shared_log_buffer else []
    return jsonify({"service": SERVICE_NAME, "entries": entries}), 200


@app.route("/backups", methods=["GET"])
def list_backups():
    files = backup_manager.list_backup_files(BACKUP_DIR)
    entries = []
    for f in files:
        path = os.path.join(BACKUP_DIR, f)
        try:
            size = os.path.getsize(path)
        except OSError:
            size = None
        entries.append({"filename": f, "size_bytes": size})
    return jsonify(entries), 200


@app.route("/backups", methods=["POST"])
def create_backup_route():
    """Déclenchement manuel -- les deux AUTRES déclencheurs (périodique,
    avant action risquée) appellent run_backup() directement, jamais
    cette route (pas de raison d'y faire un aller-retour HTTP interne).

    Protégée par rights-api (#324)."""
    body = request.get_json(silent=True) or {}
    allowed, error = _check_manage_right(body)
    if not allowed:
        return jsonify({"error": error}), 403
    try:
        filename = run_backup("manuel")
        return jsonify({"status": "ok", "filename": filename}), 201
    except Exception as exc:  # noqa: BLE001 — pg_dump/sqlite peuvent échouer de multiples façons
        return jsonify({"error": f"sauvegarde échouée : {exc}"}), 500


@app.route("/backups/<path:filename>/restore", methods=["POST"])
def restore_backup_route(filename):
    """Restauration -- DESTRUCTIF, vide la base actuelle puis rejoue le
    dump choisi. Le nom de fichier est vérifié par backup_manager
    AVANT tout accès disque (voir is_safe_backup_filename) -- jamais
    une confiance aveugle dans ce qui arrive dans l'URL.

    Protégée par rights-api (#324)."""
    body = request.get_json(silent=True) or {}
    allowed, error = _check_manage_right(body)
    if not allowed:
        return jsonify({"error": error}), 403
    try:
        backup_manager.restore_backup(
            BACKUP_DIR, filename, DB_BACKEND,
            db_path=DB_PATH if DB_BACKEND != "postgres" else None,
            pg_config=PG_CONFIG if DB_BACKEND == "postgres" else None,
        )
        return jsonify({"status": "ok"}), 200
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": f"restauration échouée : {exc}"}), 500


def _should_run_periodic_backup():
    """Évite les sauvegardes périodiques en double si plusieurs
    workers gunicorn tournent en parallèle (voir --workers dans le
    Dockerfile/CMD) -- chaque worker est un PROCESSUS SÉPARÉ qui
    importe app.py indépendamment, donc démarre sa PROPRE boucle
    périodique sans ce garde-fou. Contrôle simple par fichier : si une
    sauvegarde 'périodique' existe déjà, créée depuis moins que
    l'intervalle configuré (avec une marge de 10%), ce worker-ci n'en
    recrée pas une deuxième. Légère fenêtre de course possible si
    deux workers vérifient exactement au même instant -- accepté
    (au pire une sauvegarde en trop, jamais une perte de données),
    plutôt qu'un vrai verrou distribué, hors de proportion ici."""
    files = backup_manager.list_backup_files(BACKUP_DIR)
    periodic_files = [f for f in files if f.endswith("-periodique.sql")]
    if not periodic_files:
        return True
    most_recent_path = os.path.join(BACKUP_DIR, periodic_files[0])
    try:
        age_seconds = time.time() - os.path.getmtime(most_recent_path)
    except OSError:
        return True
    return age_seconds >= (BACKUP_PERIODIC_INTERVAL_HOURS * 3600 * 0.9)


def _periodic_backup_loop():
    """Boucle d'arrière-plan -- sauvegarde toutes les
    BACKUP_PERIODIC_INTERVAL_HOURS heures, indépendamment de toute
    action. Jamais bloquante pour le reste de l'application (thread
    daemon, démarré une seule fois au chargement du module) ; une
    erreur de sauvegarde est journalisée mais ne fait jamais planter
    la boucle elle-même -- la prochaine tentative aura lieu au
    prochain intervalle normalement."""
    while True:
        time.sleep(BACKUP_PERIODIC_INTERVAL_HOURS * 3600)
        try:
            if _should_run_periodic_backup():
                run_backup("periodique")
        except Exception as exc:  # noqa: BLE001
            app.logger.warning("Sauvegarde périodique échouée : %s", exc)


if os.environ.get("TICKETS_BACKUP_DISABLE_PERIODIC") != "true":
    _backup_thread = threading.Thread(target=_periodic_backup_loop, daemon=True)
    _backup_thread.start()


@app.route("/db/tables", methods=["GET"])
def db_list_tables():
    """Liste des tables réelles -- fondation de l'éditeur générique et
    de l'arborescence des relations."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        return jsonify(db_explorer.list_all_tables(cur, DB_BACKEND)), 200
    finally:
        conn.close()


@app.route("/db/tables/<table>/columns", methods=["GET"])
def db_table_columns(table):
    conn = get_connection()
    try:
        cur = conn.cursor()
        known = db_explorer.list_all_tables(cur, DB_BACKEND)
        if not db_explorer.is_known_table(table, known):
            return jsonify({"error": "table inconnue"}), 404
        columns = db_explorer.table_columns(cur, table, DB_BACKEND)
        return jsonify({
            "columns": columns,
            "primary_key": db_explorer.primary_key_column(columns),
            "editable_columns": db_explorer.editable_columns(columns),
        }), 200
    finally:
        conn.close()


@app.route("/db/relationships", methods=["GET"])
def db_relationships():
    """Arborescence des relations (déclarées et probables) de toute la
    base -- voir db_explorer.py pour le raisonnement complet."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        return jsonify(db_explorer.all_relationships(cur, DB_BACKEND)), 200
    finally:
        conn.close()


@app.route("/db/tables/<table>/rows", methods=["GET"])
def db_list_rows(table):
    """Lignes paginées d'une table -- limit plafonné pour ne jamais
    renvoyer une table entière par erreur (ex. ticket_status_log,
    potentiellement volumineuse)."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        known = db_explorer.list_all_tables(cur, DB_BACKEND)
        if not db_explorer.is_known_table(table, known):
            return jsonify({"error": "table inconnue"}), 404

        limit = request.args.get("limit", type=int) or 50
        limit = max(1, min(limit, 500))
        offset = request.args.get("offset", type=int) or 0
        offset = max(0, offset)

        cur.execute(f"SELECT COUNT(*) FROM {table}")
        total = cur.fetchone()[0]

        columns = db_explorer.table_columns(cur, table, DB_BACKEND)
        pk = db_explorer.primary_key_column(columns)
        order_clause = f"ORDER BY {pk}" if pk else ""
        cur.execute(f"SELECT * FROM {table} {order_clause} LIMIT {PLACEHOLDER} OFFSET {PLACEHOLDER}", [limit, offset])
        rows = [row_to_dict(cur, r) for r in cur.fetchall()]

        return jsonify({"rows": rows, "total": total, "limit": limit, "offset": offset}), 200
    finally:
        conn.close()


@app.route("/db/tables/<table>/rows/<row_id>", methods=["PUT"])
def db_update_row(table, row_id):
    """Édition générique d'une ligne -- JAMAIS la clé primaire (voir
    db_explorer.editable_columns), sauvegarde automatique AVANT toute
    écriture (demandé explicitement en prévention -- voir
    backup_manager.py/tickets/README.md).

    Protégée par rights-api (#324)."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        known = db_explorer.list_all_tables(cur, DB_BACKEND)
        if not db_explorer.is_known_table(table, known):
            return jsonify({"error": "table inconnue"}), 404

        columns = db_explorer.table_columns(cur, table, DB_BACKEND)
        pk = db_explorer.primary_key_column(columns)
        if pk is None:
            return jsonify({"error": "cette table n'a pas de clé primaire identifiable, édition impossible"}), 400
        editable = set(db_explorer.editable_columns(columns))

        body = request.get_json(silent=True) or {}
        allowed, rights_error = _check_manage_right(body)
        if not allowed:
            return jsonify({"error": rights_error}), 403
        fields_to_update = {k: v for k, v in body.items() if k in editable}
        if not fields_to_update:
            return jsonify({"error": f"aucun champ éditable valide fourni (attendus : {sorted(editable)})"}), 400

        try:
            run_backup("avant-edition")
        except Exception as exc:  # noqa: BLE001 — jamais bloquer l'édition si la sauvegarde échoue, mais le signaler clairement
            app.logger.warning("Sauvegarde avant édition échouée (édition annulée par prudence) : %s", exc)
            return jsonify({"error": f"sauvegarde de sécurité impossible, édition annulée par prudence : {exc}"}), 500

        set_clause = ", ".join(f"{col} = {PLACEHOLDER}" for col in fields_to_update)
        cur.execute(
            f"UPDATE {table} SET {set_clause} WHERE {pk} = {PLACEHOLDER}",
            [*fields_to_update.values(), row_id],
        )
        if cur.rowcount == 0:
            conn.rollback()
            return jsonify({"error": "ligne introuvable"}), 404
        conn.commit()
        return jsonify({"status": "ok"}), 200
    finally:
        conn.close()


@app.route("/db/sql/check", methods=["POST"])
def db_sql_check():
    """Test de syntaxe -- EXPLAIN, ne modifie JAMAIS réellement les
    données (vérifié empiriquement, voir sql_console.py). Jamais de
    sauvegarde nécessaire ici, contrairement à /db/sql/execute."""
    body = request.get_json(silent=True) or {}
    conn = get_connection()
    try:
        cur = conn.cursor()
        result = sql_console.check_syntax(cur, body.get("sql", ""))
        conn.rollback()  # défensif -- EXPLAIN ne devrait rien laisser en attente, mais jamais de commit accidentel ici
        return jsonify(result), 200
    finally:
        conn.close()


@app.route("/db/sql/execute", methods=["POST"])
def db_sql_execute():
    """Exécution RÉELLE -- sauvegarde automatique AVANT toute requête
    qui n'est PAS un SELECT (demandé explicitement, même principe que
    /db/tables/<table>/rows/<id> -- voir run_backup ci-dessus). La
    confirmation explicite pour les requêtes non-SELECT est de la
    responsabilité de l'interface (voir AdminView.jsx) -- cette route
    exécute ce qu'on lui demande, elle ne redemande jamais elle-même.

    Protégée par rights-api (#324)."""
    body = request.get_json(silent=True) or {}
    allowed, error = _check_manage_right(body)
    if not allowed:
        return jsonify({"error": error}), 403
    sql = body.get("sql", "")

    if not sql_console.is_select_statement(sql):
        try:
            run_backup("avant-sql")
        except Exception as exc:  # noqa: BLE001
            app.logger.warning("Sauvegarde avant SQL échouée (exécution annulée par prudence) : %s", exc)
            return jsonify({"error": f"sauvegarde de sécurité impossible, exécution annulée par prudence : {exc}"}), 500

    conn = get_connection()
    try:
        cur = conn.cursor()
        try:
            result = sql_console.execute_sql(cur, sql)
        except Exception as exc:  # noqa: BLE001 — n'importe quelle erreur d'exécution (syntaxe, contrainte, etc.)
            conn.rollback()
            return jsonify({"error": str(exc)}), 400
        conn.commit()
        return jsonify(result), 200
    finally:
        conn.close()


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "backend": DB_BACKEND}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
