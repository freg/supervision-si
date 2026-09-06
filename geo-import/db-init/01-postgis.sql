-- Extensions PostGIS + outils geomatiques -- appliquees automatiquement
-- au premier demarrage du conteneur (docker-entrypoint-initdb.d).
-- postgis_topology : continuites physiques (fibre) modelisables comme
-- un reseau topologique (noeuds/aretes), pas seulement des lignes
-- independantes -- utile si la personne veut un jour des requetes de
-- type "chemin entre deux baies".
-- fuzzystrmatch : rapprochement flou de libelles (utile si "l'outil de
-- fusion" doit un jour apparier des baies/locaux par nom approximatif
-- plutot que par geometrie exacte).
-- pg_trgm : similarite par trigrammes (similarity(), 0-1) -- l'outil
-- standard PostgreSQL pour "ces deux libelles se ressemblent-ils",
-- plus robuste que la seule distance de Levenshtein sur des noms
-- reordonnes/partiels (ex. "Baie Rue de la Paix" vs "Rue Paix - Baie").
-- Utilise par le moteur de correlation semantique (voir /correlate).
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS postgis_topology;
CREATE EXTENSION IF NOT EXISTS fuzzystrmatch;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
