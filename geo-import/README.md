# Géomatique — staging PostGIS, corrélation, import/fusion shapefiles

## Philosophie — pourquoi cet outil existe (à lire avant de toucher au code)

Reformulé après discussion avec la personne : l'écosystème couvre 25
ans d'applications cloisonnées par métier interne, dont la supervision
ne partage rien entre elles alors que leurs infrastructures se
recouvrent. Certains métiers clés n'ont **aucune documentation
d'architecture** (habitude, auto-protection) — mais les prestations
externes qu'ils ont utilisées, elles, ont souvent été documentées en
phase travaux (plans, CCTP, notes, tickets d'intervention).

**Ce n'est donc pas un ETL.** L'objectif est un outil polymorphe
d'aide à l'**émergence visuelle** de l'architecture du SI — dans
l'esprit data science : attaquer un datalake hétérogène sans le
modifier, produire des vues plus ou moins structurées, laisser le
jugement humain trancher. D'où :
- **Corrélation, pas fusion automatique** — `/correlate` propose des
  candidats classés (sémantique/géographique/temporelle), ne merge
  jamais rien tout seul.
- **Connecteurs progressifs** — brancher un métier de plus est un petit
  ajout (une fonction + une route), jamais une refonte. Toujours via
  l'API HTTP existante du module concerné, jamais un accès direct à sa
  base.
- **Rien n'est jamais modifié à la source** — même principe que "Figer
  cette vue comme source" déjà établi ailleurs dans ce projet.

## Décisions actées (confirmées par la personne, ne pas re-demander)

- **Base PostGIS** : nouvelle base **locale**, entièrement gérée par ce
  projet (écriture incluse) — pas de connexion à une base PostGIS
  externe existante. `geo-postgres` dans `docker-compose.yml`, image
  officielle `postgis/postgis:16-3.4`.
- **Onglet QGIS** : aperçu seul (rendu WMS), pas de bureau interactif.
- **Portée du moteur de corrélation** : reste dans le PostGIS de
  staging pour l'instant (option 1), mais conçu pour que les autres
  métiers y entrent par connecteurs successifs plutôt que par une
  refonte — jamais deviné de schéma sur des systèmes non vérifiables
  depuis cet environnement.

## État d'avancement

**Fait, testé, livré** :
- `geo-postgres` : PostGIS + `postgis_topology` + `fuzzystrmatch` +
  `pg_trgm` (similarité par trigrammes, utilisée par la corrélation
  sémantique — plus robuste que la seule distance de Levenshtein sur
  des libellés réordonnés/partiels).
- `geo-import-api` (port 6113) :
  - Import shapefile (`ogr2ogr`, reprojection WGS84 automatique).
  - **Outil de fusion** (`/fusion`, ancien sens, conservé) : combine
    plusieurs couches sur leurs colonnes communes — utile en soi, mais
    ce n'est plus le cœur de la réponse à "outil de fusion" telle que
    reformulée par la personne.
  - **Moteur de corrélation** (`/correlate`) — trois stratégies :
    - *Sémantique* : `similarity()` (pg_trgm) sur deux colonnes texte,
      score 0–1, seuil réglable.
    - *Géographique* : `ST_DWithin`/`ST_Distance` en géographie (mètres
      réels, pas des degrés), s'appuie sur l'index spatial.
    - *Temporelle* : écart en jours entre deux colonnes date/heure,
      fenêtre réglable.
    - Garde-fou : refuse une corrélation sémantique/temporelle si le
      produit cartésien estimé dépasse `GEO_MAX_CROSS_JOIN_PRODUCT`
      (500 000 par défaut) — la stratégie géographique n'en a pas
      besoin (passe par l'index spatial).
  - **Connecteur `geolocations`** (`/connectors/geolocations/sync`) :
    matérialise la table `geolocations` de pixel-grid-api (déjà
    transversale : Fusion IP/MAC ET OwnCloud y écrivent) en table
    PostGIS interrogeable spatialement — **toujours via l'API HTTP** de
    pixel-grid-api, jamais un accès direct à sa base (dont le backend
    peut être SQLite ou PostgreSQL selon sa config, sans que ça doive
    importer ici). Premier exemple concret du principe "connecteur
    progressif" — le suivant (IPAM, Zenoss...) suivra le même schéma
    sans qu'un système de plugin générique ait été construit par
    anticipation.
- Onglet **"Dépôt shapefiles"** : dépôt, liste des couches, fusion,
  **connecteurs**, **outil de corrélation** (sélection couches A/B +
  stratégie + colonnes/seuils dynamiques + résultats classés).
- **53 tests Python** (`geo-import-api`) + **34 tests Node**
  (`geoImportLib.js`, deux fichiers).

**Reste à faire** (annoncé à la personne, pas encore construit) :
- QGIS Server pour prévisualiser leurs dossiers de projets .qgis
  existants.
- GeoServer pour publier les couches de `geo-postgres` en WMS vers la
  carte principale — la pièce qui répond littéralement à "les avoir
  comme sources à projeter sur notre map".
- Onglet "QGIS" côté frontend.
- Câblage de la carte principale (`MapPanel.jsx`) pour consommer les
  couches WMS de GeoServer.
- Deuxième connecteur (candidat naturel : IPAM ou Zenoss, à discuter).

## Bug réel corrigé — import multi-shapefiles avec sous-dossiers

Remonté par la personne (capture d'écran de l'onglet à l'appui) :
`ERROR 1: Unable to open datasource '/tmp/geoimport_xxx/CHAMBRES_PARC.shp'`
en déposant une archive décrite comme "copie du dossier de travail
QGIS". Deux problèmes cumulés dans la version initiale de `/import` :

1. **Chemins réduits à leur nom de base** dès l'ouverture de
   l'archive — toute structure de sous-dossiers était perdue, alors
   qu'une copie de dossier de travail QGIS place presque toujours ses
   shapefiles dans des sous-dossiers, jamais à plat à la racine.
   `ogr2ogr` était donc appelé sur un chemin qui n'existait pas
   réellement à cet endroit.
2. **Un seul shapefile importé par archive**, choisi arbitrairement
   par ordre alphabétique parmi tous ceux trouvés — alors qu'un
   dossier de travail QGIS complet contient généralement plusieurs
   jeux distincts (un par type d'objet : chambres, fourreaux,
   câbles...), tous à importer, pas un seul au hasard.

**Corrigé** : `validate_shapefile_zip_contents` → `find_shapefile_sets`,
qui travaille sur les chemins relatifs complets (jamais réduits à leur
nom de base) et découvre TOUS les jeux complets de l'archive, où qu'ils
soient nichés. `/import` importe désormais chacun séparément, chacun
gardant son propre nom (le champ "nom de couche" saisi par la personne
ne s'applique que si l'archive ne contient qu'un seul jeu — appliquer
un nom unique à plusieurs couches distinctes n'aurait pas de sens).
Réponse toujours une liste (`imported: [...]`), même pour un import à
une seule couche — un échec sur une couche n'empêche plus les autres
d'aboutir. Testé explicitement contre le scénario exact du bug
(sous-dossier `Reseau_Parc/` contenant `CHAMBRES_PARC` et
`FOURREAUX_PARC`) — voir
`test_route_import_reproduces_reported_bug_scenario_now_fixed`.

Timeout gunicorn relevé de 120s à 300s en conséquence (plusieurs
imports séquentiels dans une même requête peuvent prendre plus de temps
qu'un seul) — limite connue : un dossier de travail QGIS avec beaucoup
de très gros jeux pourrait quand même dépasser cette limite ; pas
traité pour l'instant (nécessiterait un import asynchrone en tâche de
fond, hors périmètre de ce correctif).

## Sécurité — points traités sans qu'on en parle

- **Jamais de nom de table interpolé tel quel dans le SQL** :
  `sanitize_layer_name()` nettoie tout nom de couche fourni (fichier
  déposé ou nom de couche cible de fusion) en identifiant PostgreSQL
  sûr avant tout usage — testé explicitement contre une tentative
  d'injection (`x'; DROP TABLE users; --`).
- **`/fusion` vérifie l'existence réelle de chaque couche source**
  contre `geometry_columns` avant de construire le SQL — jamais un nom
  de couche arbitraire fourni par l'appel API utilisé sans être
  d'abord confirmé comme existant.
- **`gid` régénéré à la fusion** (`row_number() OVER ()`) plutôt que
  de conserver les `gid` d'origine de chaque couche source, qui se
  chevauchent presque toujours (chacune numérotée indépendamment
  depuis 1) — les garder tels quels aurait donné une fausse impression
  de clé unique.
- **Commande `ogr2ogr` construite comme une liste d'arguments**, jamais
  une chaîne shell interpolée — aucun risque d'injection shell même
  sur un nom de fichier ou de couche exotique.

## Vérifié depuis cet environnement / non vérifié

**Vérifié** : toute la logique pure (`find_shapefile_sets` — y compris
la reproduction exacte du scénario du bug rapporté, sous-dossiers
homonymes non confondus, jeux incomplets écartés sans bloquer les
autres —, `sanitize_layer_name` — y compris la tentative d'injection
SQL, `build_ogr2ogr_import_command`, `parse_ogr2ogr_output`,
`build_fusion_sql`, `estimate_join_size`,
`build_semantic/geographic/temporal_correlation_sql`,
`parse_geolocations_response`) et les routes (`ogr2ogr`/`psycopg2`/
`requests` entièrement simulés) — 54 tests Python. `geoImportLib.js` —
34 tests Node.

**Non vérifié** : ni GDAL ni PostgreSQL/PostGIS réels ne sont
disponibles dans cet environnement (pas de réseau, pas d'installation
possible) — la construction de l'image `geo-import-api` (installation
de `gdal-bin` via apt), l'exécution réelle d'`ogr2ogr`, et
l'application effective du script d'initialisation PostGIS
(`geo-import/db-init/01-postgis.sql`) n'ont donc jamais pu être
testées en conditions réelles. Premier geste utile une fois démarré :

```bash
docker compose up -d geo-postgres geo-import-api
curl http://localhost:6113/health
```

## Branchement rights-api (livraison #318)

Suite de l'item 38 du backlog. Ce module est EXPLICITEMENT en
écriture (voir docstring en tête de fichier) -- import de shapefiles,
fusion de couches, synchronisation depuis pixel-grid-api.

Gardé sur `/import` (multipart, `groups` lu depuis `request.form`),
`/fusion` et `/connectors/geolocations/sync` (corps JSON). Jamais sur
`/correlate` -- confirmé PUREMENT lecture (uniquement des `SELECT`,
aucune écriture) malgré le verbe POST utilisé pour transmettre
stratégie/options en corps de requête, ni `/layers`/
`/layers/<x>/columns`.

OPT-IN via `GEO_IMPORT_RIGHTS_API_URL`, vide par défaut,
comportement inchangé tant qu'elle n'est pas configurée.

**Vérifié réellement** : comportement opt-in par défaut confirmé,
FAIL CLOSED si `rights-api` injoignable, 403 confirmé sur les 3
routes gardées (multipart et JSON) avec un groupe non autorisé,
`/correlate` confirmée TOUJOURS libre. Non-régression complète
reconfirmée. Testé avec le stub `psycopg2` déjà présent dans
l'environnement (module non installable ici, même limite déjà
documentée).
