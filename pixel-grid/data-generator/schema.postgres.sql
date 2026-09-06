-- Équivalent PostgreSQL de schema.sql (SQLite). Appliqué automatiquement
-- au premier démarrage du conteneur via /docker-entrypoint-initdb.d/
-- (mécanisme standard de l'image officielle postgres).

CREATE TABLE IF NOT EXISTS events (
    id BIGSERIAL PRIMARY KEY,
    ts BIGINT NOT NULL,            -- timestamp Unix (secondes, UTC)
    valeur DOUBLE PRECISION NOT NULL,
    nom TEXT NOT NULL,
    type TEXT NOT NULL,
    data TEXT
);

CREATE INDEX IF NOT EXISTS idx_events_type_ts ON events (type, ts);

CREATE TABLE IF NOT EXISTS type_meta (
    type TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    config_json TEXT NOT NULL
);

-- parent_localisation/location_type : hiérarchie bâtiment → étage →
-- pièce → point d'accès, ajoutée pour le coffre-fort -- voir
-- schema.sql (variante SQLite) pour le détail complet du
-- raisonnement, identique ici.
CREATE TABLE IF NOT EXISTS geolocations (
    localisation TEXT PRIMARY KEY,
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    parent_localisation TEXT,
    location_type TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
    login TEXT PRIMARY KEY,
    group_name TEXT,
    config_json TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
