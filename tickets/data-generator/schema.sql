-- Module tickets — gestion des tickets + rattachement de temps passé
-- (agenda Google) + génération automatique depuis les incidents de
-- supervision (lien futur avec pixel-grid).

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    login TEXT UNIQUE NOT NULL,
    name TEXT,
    email TEXT,
    group_name TEXT,
    -- Profil portail : 'admin' | 'demandeur' | 'technicien' | 'politique'
    role TEXT NOT NULL DEFAULT 'demandeur'
);

CREATE TABLE IF NOT EXISTS types (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    label TEXT UNIQUE NOT NULL
);

-- "integer" est un mot réservé dans plusieurs dialectes SQL — la colonne
-- de tri numérique s'appelle donc "rank" (même rôle : ordonner les niveaux).
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
    -- Lien futur avec la supervision : source de l'incident ayant
    -- généré ce ticket automatiquement (nullable — tickets créés à la
    -- main n'ont pas de source).
    source_type TEXT,
    source_nom TEXT,
    -- Sous-demande (portail) : ticket enfant d'un ticket parent
    parent_ticket_id INTEGER REFERENCES tickets(id),
    archived_at INTEGER
);

-- Événements calendrier importés (Google iCal secret ou export
-- Thunderbird/Lightning) — stockage brut, avant application des règles.
CREATE TABLE IF NOT EXISTS calendar_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uid TEXT UNIQUE NOT NULL,
    summary TEXT,
    description TEXT,
    start_ts INTEGER NOT NULL,
    end_ts INTEGER,
    source TEXT NOT NULL,  -- 'google_ics' | 'thunderbird_import'
    imported_at TEXT NOT NULL
);

-- Segments de temps rattachés à un ticket — plusieurs par ticket
-- possibles (d'où le Gantt "riche", pas un simple début/fin). Peut
-- venir d'un événement calendrier (calendar_event_id renseigné) ou
-- d'une saisie manuelle (NULL).
-- weight : pour une affectation n événements -> m tickets en mode
-- "réparti", chaque segment ne compte que pour une fraction de sa
-- durée réelle (1.0/m) ; en mode "durée entière", weight reste à 1.0
-- pour chacun (comptage assumé plusieurs fois, ex: réunion couvrant
-- plusieurs sujets).
CREATE TABLE IF NOT EXISTS ticket_time_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id INTEGER NOT NULL REFERENCES tickets(id),
    calendar_event_id INTEGER REFERENCES calendar_events(id),
    start_ts INTEGER NOT NULL,
    end_ts INTEGER NOT NULL,
    weight REAL NOT NULL DEFAULT 1.0,
    -- Attribution par technicien -- voir tickets/api/app.py (SQLITE_SCHEMA)
    -- pour le raisonnement complet. NULL par défaut (imports calendrier,
    -- anciens segments).
    technician_login TEXT,
    created_at TEXT NOT NULL
);

-- Config simple clé/valeur — porte le mot-clé déclencheur ("SAV" par
-- défaut, insensible à la casse) qui signale qu'un événement calendrier
-- est potentiellement lié à un ticket, avant toute recherche de
-- correspondance.
CREATE TABLE IF NOT EXISTS matching_config (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
INSERT OR IGNORE INTO matching_config (key, value) VALUES ('trigger_keyword', 'SAV');

-- Règles de filtrage regex, éditables depuis l'interface — appliquées
-- aux événements calendrier importés pour les rattacher automatiquement.
CREATE TABLE IF NOT EXISTS calendar_filter_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    label TEXT NOT NULL,
    pattern TEXT NOT NULL,               -- expression régulière Python
    target_field TEXT NOT NULL DEFAULT 'summary',  -- summary | description | both
    action TEXT NOT NULL DEFAULT 'both', -- attach_existing | create_ticket | both
    ticket_ref_group TEXT,               -- nom du groupe nommé regex portant l'id ticket, ex: (?P<ticket_id>\d+)
    default_type_id INTEGER REFERENCES types(id),
    default_level_id INTEGER REFERENCES levels(id),
    default_user_id INTEGER REFERENCES users(id),
    priority INTEGER NOT NULL DEFAULT 0, -- ordre d'application, plus petit = appliqué en premier
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_tickets_statut ON tickets (statut_id);
CREATE INDEX IF NOT EXISTS idx_tickets_level ON tickets (level_id);
CREATE INDEX IF NOT EXISTS idx_time_entries_ticket ON ticket_time_entries (ticket_id);
CREATE INDEX IF NOT EXISTS idx_calendar_events_ts ON calendar_events (start_ts);

-- Liste d'exclusion : un événement qui matche l'un de ces motifs
-- (même s'il matche par ailleurs le mot-clé déclencheur) n'est JAMAIS
-- considéré comme un ticket potentiel — véto, pas juste une priorité
-- plus basse.
CREATE TABLE IF NOT EXISTS exclusion_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    label TEXT NOT NULL,
    pattern TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS oauth_credentials (
    provider TEXT PRIMARY KEY,
    refresh_token TEXT NOT NULL,
    access_token TEXT,
    access_token_expires_at INTEGER,
    updated_at TEXT NOT NULL
);

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
    (4, 'Cassé/HS', 'cass[ée]|hors service|\bhs\b', 1, '2026-01-01T00:00:00Z'),
    (5, 'Bloquant', 'bloqu(ant|é)', 1, '2026-01-01T00:00:00Z');

-- Escalade automatique par deadline -- voir app.py (même commentaire
-- complet dans SQLITE_SCHEMA, ne pas laisser diverger).
CREATE TABLE IF NOT EXISTS deadline_escalation_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    threshold_hours INTEGER NOT NULL,
    target_level_id INTEGER NOT NULL REFERENCES levels(id),
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ticket_status_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id INTEGER NOT NULL REFERENCES tickets(id),
    event_type TEXT NOT NULL,
    ts INTEGER NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_status_log_ticket ON ticket_status_log (ticket_id);

-- Fil de discussion par ticket (portail) — forum/chat demandeur <-> technicien
CREATE TABLE IF NOT EXISTS ticket_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id INTEGER NOT NULL REFERENCES tickets(id),
    user_id INTEGER REFERENCES users(id),
    body TEXT NOT NULL,
    created_ts INTEGER NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_messages_ticket ON ticket_messages (ticket_id);
