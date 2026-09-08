-- Base PostGIS DÉDIÉE au catalogue de positions (livraison #429) --
-- distincte de geo-postgres (staging geo-import) : elle accueille les
-- référentiels volumineux (OSM via osm2pgsql, communes, cache BAN) et
-- doit pouvoir vivre sur un hôte secondaire (GEO_CATALOG_DB_URL).
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS unaccent;
