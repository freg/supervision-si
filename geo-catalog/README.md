# geo-catalog — catalogue de positions (livraison #429, backlog 67)

Demande : « charger les données d'OSM et de data.gouv.fr ; une interface
qui liste la ou les données de référence (fiches avec agrégation ou
extraction), l'interprétation / référence géographique la plus précise,
la position longitude/latitude, l'estimation en % de véracité/justesse, un
bouton Corriger, un bouton Valider → un catalogue de positions et de liens
vers des objets positionnés sur chacune. Penser au volume de la base OSM :
il faut pouvoir la déplacer vers un hôte secondaire. »

## Architecture

- **`geo-catalog-postgres`** : base PostGIS **dédiée** (postgis, pg_trgm,
  unaccent), distincte de `geo-postgres` (staging de geo-import). Elle
  reçoit les référentiels volumineux : OSM (osm2pgsql), communes, cache de
  géocodage, et le catalogue lui-même. Volume nommé `geo_catalog_pg_data`
  ou dossier `GEO_CATALOG_DATA_DIR` (disque dédié).
- **`geo-catalog-api`** (Flask, `/api/geo-catalog/`) : synchronisation,
  interprétation, décisions, référentiels. Ne parle aux autres modules que
  par HTTP (pixel-grid) et à la base par `GEO_CATALOG_DB_URL`.
- **Hub, tuile « Catalogue de positions »** (`hub/src/GeoCatalogView.jsx`,
  logique pure `geoCatalog.js`, 2 tests).

## Le modèle

Une **position** = un lieu nommé du SI (aujourd'hui : chaque localisation
de la table `geolocations` de pixel-grid, clé `geolocation:<nom>` ;
`__default__` exclu). Pour chaque position :

- ses **références** (`catalog_refs`) : coordonnées saisies
  (`geolocations`), adresse ou point d'intérêt **BAN / Géoplateforme**
  (data.gouv.fr, index `address` et `poi`, en cache), **commune** (code
  postal dans le libellé → référentiel des communes chargé en base depuis
  geo.api.gouv.fr, ou nom de commune proche par pg_trgm), **OSM** (tables
  osm2pgsql locales par pg_trgm, sinon Nominatim si `GEO_CATALOG_NOMINATIM_URL`,
  1 requête/s), et la **décision humaine** (`human`) ;
- l'**interprétation** (`catalog.interpret`, pur, 7 tests) : la référence
  la plus précise (numéro > POI > OSM > rue > site > lieu-dit > commune >
  code postal > saisie), sauf qu'un géocodage peu sûr (score < 0,8) à plus
  de 10 km de coordonnées saisies est écarté (listé, pas retenu) ; la
  **justesse** 0-100 combine la précision retenue, le score du géocodeur,
  les références concordantes (+8 chacune) et contradictoires (× 0,6
  chacune) ; les raisons sont conservées en clair ;
- son **statut** : `auto` (interprétation appliquée à chaque synchro),
  `validated` (95 %), `corrected` (100 %, lat/lon de la personne) — une
  décision n'est jamais recalculée, `reset` y renonce ;
- ses **objets rattachés** (`catalog_links`) : les correspondances nom →
  lieu de #426 (`supervised`, sujets `ip:` / `name:` / `site:` du hub) et la
  hiérarchie parent/enfant des géolocalisations.

## Routes

`GET /health`, `GET /status` (compteurs, communes, tables OSM, cache,
dernière synchro, hôte de la base), `POST /sync` `{only?: [...]}`,
`GET /positions?status=&q=&min_confidence=&max_confidence=`,
`GET /positions/<id>` (références, objets, voisines à 500 m),
`PUT /positions/<id>/validate|correct|reset` (`{lat, lon, note}` pour
corriger), `PUT /positions/<id>/refs/<rid>/use` (retenir une référence),
`POST /positions/<id>/push` (recopie dans `geolocations` de pixel-grid,
donc dans Supervision SI, la carte, le pont), `POST /referentials/communes/load`,
`GET /referentials/lookup?label=` (essai à blanc). Les écritures passent le
droit *manage* (`GEO_CATALOG_RIGHTS_API_URL`, fail-closed comme partout).

## Référentiels

- **Communes** (data.gouv.fr / geo.api.gouv.fr) : bouton « Charger les
  communes » (≈ 35 000 lignes, centre et codes postaux) — sans chargement,
  le code postal est résolu à la demande et mis en cache.
- **BAN / Géoplateforme** : en ligne, à la demande, en cache
  (`ref_geocode_cache`) ; `GEOCODE_PROVIDER_URL` pour un miroir.
- **OSM** : `geo-catalog/scripts/import-osm.sh <extrait.osm.pbf | URL Geofabrik>`
  importe un extrait avec osm2pgsql (conteneur jetable) dans la base du
  catalogue — prendre l'extrait le plus petit qui couvre le parc (région,
  département : 1 à 5 Go ; la France entière : dizaines de Go, heures
  d'import). Sans base locale, Nominatim en ligne si configuré.

## Déplacer la base sur un hôte secondaire

1. Sur l'hôte secondaire : un PostGIS (ex. `docker run -d --name geo-catalog-postgres -e POSTGRES_DB=geocat -e POSTGRES_USER=geocat -e POSTGRES_PASSWORD=… -v /disque/geocat:/var/lib/postgresql/data -p 5432:5432 postgis/postgis:16-3.4`), puis `geo-catalog/db-init/01-extensions.sql`.
2. Transfert : `docker exec geo-catalog-postgres pg_dump -U geocat -Fc geocat > geocat.dump` sur la VM, `pg_restore -U geocat -d geocat geocat.dump` sur l'hôte secondaire (ou déplacer directement le dossier du volume, base arrêtée).
3. `.env` : `GEO_CATALOG_DB_URL=postgresql://geocat:…@hote-secondaire:5432/geocat`, puis `docker compose up -d geo-catalog-api` et `docker compose stop geo-catalog-postgres`. Les imports OSM suivants : `import-osm.sh … --db "$GEO_CATALOG_DB_URL"`.

## Tests

```bash
cd geo-catalog/api && python3 -m unittest test_catalog                       # logique pure (7)
GEO_CATALOG_TEST_DB_URL=postgresql://geocat:geocat@localhost:6547/geocat \
  python3 -m unittest test_geo_catalog_api                                  # 6 tests contre un vrai PostGIS (tables recréées !)
cd ../../hub && node --test tests/geoCatalog.test.mjs
```

## Vérifié / non vérifié

Vérifié : logique pure ; routes contre un **vrai PostGIS 16 / PostGIS 3.4**
(schéma, synchro, interprétation, décisions, reprise d'une référence,
recopie vers pixel-grid simulée, communes, recherche pg_trgm, voisines) ;
chaîne réelle geo-catalog-api ↔ pixel-grid-api (Flask réel) ↔ tuile hub
(rendu Chromium clair/sombre) avec un faux géocodeur et un faux
référentiel des communes (pas d'accès aux services publics depuis
l'environnement de développement) ; build Vite du hub ; compose YAML.
Non vérifié : appels réels à data.geopf.fr / geo.api.gouv.fr, Nominatim,
import osm2pgsql, builds Docker, déplacement réel de la base.
