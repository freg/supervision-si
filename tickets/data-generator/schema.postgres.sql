CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    login TEXT UNIQUE NOT NULL,
    name TEXT,
    email TEXT,
    group_name TEXT,
    -- Profil portail : 'admin' | 'demandeur' | 'technicien' | 'politique'
    role TEXT NOT NULL DEFAULT 'demandeur'
);

CREATE TABLE IF NOT EXISTS types (
    id SERIAL PRIMARY KEY,
    label TEXT UNIQUE NOT NULL
);

-- Sites -- voir tickets/api/app.py (SQLITE_SCHEMA) pour le raisonnement
-- complet. Les deux schémas DOIVENT rester synchronisés manuellement
-- (aucun outillage de migration partagé entre SQLite et PostgreSQL
-- dans ce projet).
CREATE TABLE IF NOT EXISTS sites (
    id SERIAL PRIMARY KEY,
    label TEXT UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS levels (
    id SERIAL PRIMARY KEY,
    label TEXT NOT NULL,
    rank INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS statuts (
    id SERIAL PRIMARY KEY,
    label TEXT NOT NULL,
    description TEXT
);

CREATE TABLE IF NOT EXISTS tickets (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    subject TEXT NOT NULL,
    type_id INTEGER REFERENCES types(id),
    description TEXT,
    level_id INTEGER REFERENCES levels(id),
    ts_created BIGINT NOT NULL,
    ts_closed BIGINT,
    last_change BIGINT NOT NULL,
    statut_id INTEGER REFERENCES statuts(id),
    source_type TEXT,
    source_nom TEXT,
    -- Sous-demande (portail) : ticket enfant d'un ticket parent
    parent_ticket_id INTEGER REFERENCES tickets(id),
    archived_at INTEGER
);

CREATE TABLE IF NOT EXISTS calendar_events (
    id SERIAL PRIMARY KEY,
    uid TEXT UNIQUE NOT NULL,
    summary TEXT,
    description TEXT,
    start_ts BIGINT NOT NULL,
    end_ts BIGINT,
    source TEXT NOT NULL,
    imported_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ticket_time_entries (
    id SERIAL PRIMARY KEY,
    ticket_id INTEGER NOT NULL REFERENCES tickets(id),
    calendar_event_id INTEGER REFERENCES calendar_events(id),
    start_ts BIGINT NOT NULL,
    end_ts BIGINT NOT NULL,
    weight REAL NOT NULL DEFAULT 1.0,
    -- Attribution par technicien -- voir tickets/api/app.py (SQLITE_SCHEMA)
    -- pour le raisonnement complet. NULL par défaut (imports calendrier,
    -- anciens segments).
    technician_login TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS matching_config (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
INSERT INTO matching_config (key, value) VALUES ('trigger_keyword', 'SAV') ON CONFLICT (key) DO NOTHING;

CREATE TABLE IF NOT EXISTS calendar_filter_rules (
    id SERIAL PRIMARY KEY,
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

CREATE INDEX IF NOT EXISTS idx_tickets_statut ON tickets (statut_id);
CREATE INDEX IF NOT EXISTS idx_tickets_level ON tickets (level_id);
CREATE INDEX IF NOT EXISTS idx_time_entries_ticket ON ticket_time_entries (ticket_id);
CREATE INDEX IF NOT EXISTS idx_calendar_events_ts ON calendar_events (start_ts);

CREATE TABLE IF NOT EXISTS exclusion_rules (
    id SERIAL PRIMARY KEY,
    label TEXT NOT NULL,
    pattern TEXT NOT NULL,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS oauth_credentials (
    provider TEXT PRIMARY KEY,
    refresh_token TEXT NOT NULL,
    access_token TEXT,
    access_token_expires_at BIGINT,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS priority_keywords (
    id SERIAL PRIMARY KEY,
    label TEXT NOT NULL,
    pattern TEXT NOT NULL,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TEXT NOT NULL
);
INSERT INTO priority_keywords (label, pattern, active, created_at) VALUES
    ('Urgent', 'urgen(t|ce)', TRUE, '2026-01-01T00:00:00Z'),
    ('Critique', 'critique', TRUE, '2026-01-01T00:00:00Z'),
    ('Panne', 'panne', TRUE, '2026-01-01T00:00:00Z'),
    ('Cassé/HS', 'cass[ée]|hors service|\bhs\b', TRUE, '2026-01-01T00:00:00Z'),
    ('Bloquant', 'bloqu(ant|é)', TRUE, '2026-01-01T00:00:00Z')
ON CONFLICT DO NOTHING;

-- Escalade automatique par deadline -- voir app.py (même commentaire
-- complet dans SQLITE_SCHEMA, ne pas laisser diverger).
CREATE TABLE IF NOT EXISTS deadline_escalation_rules (
    id SERIAL PRIMARY KEY,
    threshold_hours INTEGER NOT NULL,
    target_level_id INTEGER NOT NULL REFERENCES levels(id),
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ticket_status_log (
    id SERIAL PRIMARY KEY,
    ticket_id INTEGER NOT NULL REFERENCES tickets(id),
    event_type TEXT NOT NULL,
    ts BIGINT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_status_log_ticket ON ticket_status_log (ticket_id);

-- Fil de discussion par ticket (portail) — forum/chat demandeur <-> technicien
CREATE TABLE IF NOT EXISTS ticket_messages (
    id SERIAL PRIMARY KEY,
    ticket_id INTEGER NOT NULL REFERENCES tickets(id),
    user_id INTEGER REFERENCES users(id),
    body TEXT NOT NULL,
    created_ts BIGINT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_messages_ticket ON ticket_messages (ticket_id);
