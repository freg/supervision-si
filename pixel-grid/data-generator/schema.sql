-- Schéma du module pixel-grid — stockage optimisé pour l'agrégation par
-- plage de temps (année/mois/jour/heure/minute), volumes de l'ordre du
-- million de points par type.

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts INTEGER NOT NULL,       -- timestamp Unix (secondes, UTC)
    valeur REAL NOT NULL,      -- champ fixe : valeur décimale
    nom TEXT NOT NULL,         -- champ fixe : nom de la métrique/équipement
    type TEXT NOT NULL,        -- champ fixe : catégorie (ex: "etat", "niveau")
    data TEXT                  -- champ libre : sous-arbre JSON sérialisé
);

-- Index composite : les requêtes d'agrégation filtrent toujours par type
-- puis par plage de ts — cet ordre correspond au pattern de requête réel.
CREATE INDEX IF NOT EXISTS idx_events_type_ts ON events (type, ts);

-- Métadonnées par type — nécessaire pour que l'API d'agrégation sache
-- comment colorer les cellules (kind, seuils) sans redéduire ça des
-- données elles-mêmes. Remplie/mise à jour par generate.sh.
CREATE TABLE IF NOT EXISTS type_meta (
    type TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    config_json TEXT NOT NULL
);

-- Table de géolocalisation — associe un chemin "Localisation" (ex:
-- "/Parc/Liaison FH Nord/Nord") à des coordonnées.
-- Détection automatique des nouveaux chemins (latitude/longitude NULL
-- au départ) via scan_geolocations.py ou POST /geolocations/scan ;
-- remplissage des coordonnées manuel (édition via l'onglet dédié).
--
-- parent_localisation/location_type : hiérarchie bâtiment → étage →
-- pièce → point d'accès, ajoutée pour le coffre-fort (recherche de
-- codes par localisation) -- volontairement NULLABLE, une
-- localisation existante (équipement réseau géocodé, par exemple)
-- reste valide sans hiérarchie, à la racine. parent_localisation
-- référence localisation elle-même (auto-référence) -- pas de vraie
-- contrainte FK ici (SQLite/Postgres l'acceptent techniquement, mais
-- le reste du projet ne l'impose pas systématiquement sur ce genre de
-- champ optionnel, cohérence avec l'existant).
CREATE TABLE IF NOT EXISTS geolocations (
    localisation TEXT PRIMARY KEY,
    latitude REAL,
    longitude REAL,
    parent_localisation TEXT,
    location_type TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Ébauche minimale pour une future gestion multi-utilisateur — pas
-- d'authentification pour l'instant, juste la structure + un seul
-- utilisateur "admin" en attendant. config_json accueillera les
-- préférences par utilisateur/groupe le moment venu.
CREATE TABLE IF NOT EXISTS users (
    login TEXT PRIMARY KEY,
    group_name TEXT,
    config_json TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
