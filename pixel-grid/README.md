# Module pixel-grid — grille temporelle dense (année → minute)

Module indépendant (pas de dépendance à l'API de supervision existante),
comme demandé. Stockage SQLite dédié + génération de gros volumes en
bash/awk + API d'agrégation qui ne renvoie jamais plus que ce qui tient
à l'écran.

## Interface

Livrée — accessible depuis l'app principale via le menu horizontal
auto-masquant (survol du haut de l'écran), onglet **Pixel Grid**.

- Sélection du **type** (boutons, un par type trouvé en base).
- **Niveau** (année/mois/jour/heure/minute) : auto-choisi à l'ouverture
  selon l'étendue réelle des données (`span_days` de `/meta`), modifiable
  à la main à tout moment.
- **Taille de cellule** : 2, 3 ou 4px.
- **Clic sur une cellule** = zoom vers le niveau suivant, borné à la
  fenêtre de cette cellule (ex: cliquer un jour affiche ses 24 heures).
  Fil d'Ariane cliquable pour remonter ; bouton « 🏠 Vue auto » pour
  revenir à la vue initiale.
- **Survol** : la couleur est toujours visible (cellule), la valeur
  précise apparaît en infobulle native + dans un bandeau sous la grille
  (les cellules de 2-4px ne peuvent pas afficher de texte lisible en
  elles-mêmes).

Utilise le nouvel endpoint `/aggregate_range` (voir plus bas) — pas
`/aggregate`, qui reste calé sur un calendrier classique (fusionnerait
les mêmes mois de plusieurs années entre eux, inadapté à une mosaïque
couvrant toute la plage).

## Données réelles — parseur d'e-mails d'alerte Zenoss

En attendant une liaison directe Zenoss ↔ API (voir `connectors/zenoss_legacy/`),
`parse_zenoss_emails.py` convertit un export texte de tes e-mails
d'alerte (template de notification standard Zenoss) en CSV compatible
avec les loaders existants — **testé contre un vrai extrait de ton
backlog**, y compris les cas piégeux (messages contenant eux-mêmes des
deux-points comme *"exceeded: current value..."*, entrées tronquées
par l'affichage Thunderbird sans `Severite` visible, `Composants` vide).

**Format attendu** : sélectionne tes e-mails d'alerte dans Thunderbird,
copie-colle dans un fichier texte (c'est ce que tu as fait pour me les
montrer — même procédure).

**Règle de conversion** : chaque e-mail devient une ligne — `valeur=1`
pour une alerte active (horodatée à *"Alert generated at"*), `valeur=0`
pour une résolution *"clear:"* (horodatée à *"Event Cleared At"*, le
moment où **ce mail précis** est parti). Type `alerte_zenoss_email`,
`kind=integer_enum` — réutilise directement la logique de coloration
par taux déjà en place, aucune adaptation de l'API nécessaire.

```bash
cd pixel-grid/data-generator

python3 parse_zenoss_emails.py mon_export.txt alertes.csv
# Affiche un résumé : nombre d'entrées, alertes actives vs résolutions,
# blocs non reconnus (rares — uniquement si le format diffère du
# template standard)

# SQLite
./load_sqlite.sh alertes.csv configs/alerte_zenoss_email.json timeseries.db

# ou PostgreSQL
./load_postgres.sh alertes.csv configs/alerte_zenoss_email.json
```

Le type `alerte_zenoss_email` apparaît ensuite comme un bouton
sélectionnable dans l'onglet Pixel Grid, au même titre que `etat` et
`niveau`.

**Limite connue** : les horodatages du texte n'indiquent pas de fuseau
— traités tels quels comme UTC. Si tes mails sont en heure locale et
que ça compte pour ton usage (ex: distinguer une alerte de jour vs de
nuit), il faudra ajuster `parse_timestamp()` dans le script.

## Calendrier partagé -- trois sources connectées (livraisons #218-219)

Backlog item 10 -- "calendrier partagé, présentant TOUTES les données
liées à un utilisateur ET une date/heure... agréger des données de
PLUSIEURS SOURCES (tickets, documents `ged`, activité tunnels SSH...)".
**Les trois sources nommées explicitement sont maintenant toutes
connectées.**

**Décisions de portée prises pour avancer** (l'item listait 3 aspects
"à trancher ensemble") :
- Réutilise pixel-grid TEL QUEL -- **découverte en vérifiant** :
  pixel-grid n'a PAS d'API d'ingestion temps réel ("l'écriture ne
  passe que par `generate.sh`", voir "Limites connues" plus bas dans
  ce README) -- un export PAR LOT, à rejouer périodiquement, même
  motif que `parse_zenoss_emails.py`, pas un flux continu.
- **La dimension "utilisateur" reste PARTIELLEMENT hors portée
  (mise à jour #371 : filtrage réel désormais construit, voir
  ci-dessous)** -- vérifié à l'origine : la table `users` de
  pixel-grid n'est qu'une ébauche structurelle. En revanche, chaque
  export ci-dessous utilise déjà l'utilisateur RÉEL (technicien,
  personne qui a lié un document...) comme `nom` -- exploite
  directement la "Vue timeline équipement" déjà en place (clic sur un
  nom = SA timeline complète).

### Filtrage réel par nom sur la grille (livraison #371)

Demandé explicitement (backlog item 10, "reste à faire" cité
plusieurs sessions) : jusqu'ici, la SEULE façon de voir l'activité
d'UNE personne était de cliquer un événement dans le panneau de
détail puis consulter SA timeline séparément -- jamais de filtre sur
la grille principale elle-même.

`/aggregate` et `/aggregate_range` (`pixel-grid/api/app.py`) acceptent
désormais un paramètre optionnel `nom` -- ajoute `AND nom = ?` à la
clause `WHERE` déjà construite pour `type`/plage temporelle, un seul
point d'ajout partagé par les deux "kind" (`integer_enum`/
`continuous`). Absent = comportement inchangé (agrège tous les noms
ensemble, comme avant cette livraison).

Côté frontend (`PixelGridApp.jsx`) : liste des noms distincts
rechargée à chaque changement de type (`fetchDevices`, déjà existant,
jamais dupliqué), sélecteur "Filtrer : Tous / nom (N points)..." dans
la barre d'outils -- la grille entière se recolore pour NE montrer que
l'activité de la personne/l'équipement choisi, sans changer de vue ni
perdre le niveau de zoom courant.

**Reste HORS de portée, volontairement** (second point de l'item 10
du backlog) : mode de coloration "activité" distinct du "taux
d'erreur" existant -- ce dernier reste réutilisé tel quel pour
l'instant, potentiellement trompeur visuellement pour une lecture en
mode "présence/activité" plutôt qu'"incidents".
**✅ LIVRÉ en #371** -- calculé ENTIÈREMENT côté client
(`PixelGridApp.jsx`), à partir de `total` (déjà présent sur chaque
bucket, aucun champ ni appel serveur supplémentaire). Bouton
"Erreurs / Activité" dans la barre d'outils. Échelle RELATIVE au
maximum observé dans la vue courante (pas un seuil absolu -- un même
total signifie "beaucoup" sur une vue clairsemée et "peu" sur une vue
dense), 4 paliers (`none`/`low`/`medium`/`high`), palette BLEUE
volontairement distincte du vert/orange/rouge existant pour qu'aucune
des deux échelles ne soit confondue avec l'autre.

### 1. Activité tunnels SSH (`export_ssh_tunnel_activity.py`, #218)

Lit `ssh_credential_usage_history` (#210) -- chaque tentative RÉUSSIE
devient une paire ouverture(1)/fermeture(0). Échecs exclus (jamais un
"valeur=1" fantôme pour une connexion jamais établie).

### 2. Segments de temps sur tickets (`export_ticket_time_entries.py`, #219)

Lit `ticket_time_entries` (#115) PLUTÔT que `tickets` directement --
cette table a déjà `start_ts`/`end_ts` PRÉCIS et `technician_login`,
exactement la combinaison utilisateur+plage horaire demandée.
`nom` = login du technicien (ou `non_attribue`).

### 3. Liens de documents GED (`export_document_links.py`, #219)

Lit `document_links` (métadonnées LOCALES de `ged-api`) -- les
documents eux-mêmes vivent dans Mayan (système externe), et
`mayan_client.py` n'a AUCUNE fonction de liste de documents
(seulement `get_document(id)`, un à la fois) -- lister tous les
documents demanderait une nouvelle capacité côté Mayan, pas construite
ici. `document_links` a en revanche `linked_by`/`linked_at`, suffisant
pour ce besoin sans le moindre appel réseau à Mayan. **Différence de
modélisation** : un lien est un événement PONCTUEL (pas de fin) --
une seule ligne `valeur=1` par lien, jamais de `valeur=0`
correspondant -- pixel-grid l'affiche "EN COURS" (son comportement
par défaut pour un `valeur=1` non résolu), imprécis sémantiquement
pour un instant, mais exploitable visuellement.

```bash
cd pixel-grid/data-generator
python3 export_ssh_tunnel_activity.py /chemin/ssh-tunnels.db activite_ssh.csv
python3 export_ticket_time_entries.py /chemin/tickets.db activite_tickets.csv
python3 export_document_links.py /chemin/ged.db activite_ged.csv
./load_sqlite.sh activite_ssh.csv configs/activite_tunnel_ssh.json timeseries.db
./load_sqlite.sh activite_tickets.csv configs/activite_ticket_temps.json timeseries.db
./load_sqlite.sh activite_ged.csv configs/activite_document_ged.json timeseries.db
```

### Automatisation (`run_all_exports.sh`, livraison #220)

Orchestre les trois exports + chargements en un seul appel --
support SQLite ET PostgreSQL (`PIXEL_GRID_BACKEND`, même variable que
`.env.example`, défaut `postgres`). Chaque source est INDÉPENDANTE --
une base absente ou un échec d'export n'empêche jamais les deux
autres de s'exécuter.

```bash
./run_all_exports.sh
# ou avec des chemins personnalisés :
SSH_TUNNELS_DB=/autre/chemin/ssh-tunnels.db ./run_all_exports.sh
```

Pensé pour une tâche cron (jamais un ordonnanceur intégré à ce
script -- ce projet n'en a nulle part ailleurs) :
```
*/30 * * * * /chemin/vers/supervision-si/pixel-grid/data-generator/run_all_exports.sh >> /var/log/pixel-grid-export.log 2>&1
```

**⚠️ Bug bash RÉEL trouvé et corrigé en testant** : la première
version appelait `run_one ... || true` pour qu'un échec d'une source
n'arrête pas les deux autres -- mais dès qu'un appel de FONCTION est
suivi de `||`, bash désactive `errexit` (`set -e`) pour TOUTE la
durée de cet appel, **y compris À L'INTÉRIEUR du corps de la
fonction**. Résultat : un export Python en échec (base corrompue)
laissait quand même le CHARGEUR être appelé juste après, sur un CSV
absent ou incomplet -- confirmé en testant avec une base SQLite
volontairement corrompue. Corrigé par une vérification EXPLICITE du
code de sortie (`if ! python3 ...`) plutôt que de compter sur la
propagation implicite de `set -e`.

**Vérifié réellement** (`jq`/`sqlite3` CLI absents de cet
environnement de développement -- testé avec des chargeurs SIMULÉS
pour isoler la logique d'orchestration) : les 3 bases absentes ->
aucune erreur bloquante, message clair pour chacune ; 2 présentes +
1 absente -> exactement les 2 bonnes sources chargées ; **le cas
critique** (1 base corrompue) -> confirmé qu'AUCUN chargement
n'est tenté pour la source en échec, les deux autres s'exécutent
normalement.

**Limite connue, commune aux trois** : la coloration par "taux
d'erreur" existante reste utilisée telle quelle -- pensée pour des
ALERTES (taux élevé = problème), pas pour de l'ACTIVITÉ légitime.
Pourrait produire une coloration trompeuse -- pas de mode "niveau
d'activité" séparé pour l'instant, laissé pour la passe
d'optimisation à venir.

**Vérifié réellement, pour les trois exports** : testés contre des
bases simulant le VRAI schéma de chaque service (dont les cas
limites : segment non attribué à un technicien, lien de document sans
utilisateur). Testés en sous-processus réel (CLI complet), format
CSV exact vérifié ligne par ligne. Un point de rigueur corrigé avant
même de tester (#218) : la conversion de date initiale utilisait
`time.mktime` (sensible au fuseau local), remplacée par
`calendar.timegm`.

**Reste à faire** : filtrage RÉEL par utilisateur dans l'interface de
pixel-grid (nécessite de l'étendre, jamais fait ici), mode de
coloration "activité" distinct du "taux d'erreur".

## Géolocalisation

Détection **automatique** des chemins `Localisation` (champ du sous-arbre
`data`, ex: `/Parc/Liaison FH Nord/Nord`) jamais vus,
ajoutés comme entrées en attente (coordonnées vides) — appelée
automatiquement après chaque chargement (`load_sqlite.sh`/`load_postgres.sh`),
ou à la demande depuis l'onglet **Géolocalisation** du menu.

**Coordonnées saisies à la main**, avec assistance au géocodage
depuis fin août 2026 (voir sous-section dédiée juste en dessous) —
avant ça, aucune assistance n'existait (pas d'accès à un service
externe depuis l'environnement Claude au moment où l'onglet a été
construit). L'onglet liste tous les lieux connus (point rouge = en
attente, vert = coordonnées renseignées), édition directe
latitude/longitude par ligne, suppression individuelle.

### Assistance au géocodage (boutons 🔍 et 🌍 par ligne)

Deux aides indépendantes, aucune des deux n'écrit jamais les
coordonnées toute seule — le bouton 💾 existant reste le seul geste
qui enregistre, cohérent avec "aucune action automatique silencieuse" :

- **🔍 Chercher** — interroge `GET /geocode` (nouvel endpoint de cette
  API), qui relaie vers un service de géocodage externe configurable
  (BAN/Géoplateforme par défaut, gratuit, sans clé — voir
  `GEOCODE_PROVIDER_URL`/`GEOCODE_INDEX`/`GEOCODE_TIMEOUT_SECONDS`
  dans `.env`). Affiche une liste de candidats cliquables (libellé,
  ville, coordonnées) sous la ligne ; cliquer un candidat remplit les
  champs latitude/longitude, sans sauvegarder. `GEOCODE_INDEX=poi` par
  défaut (lieux nommés) plutôt que `address` (adresses postales
  structurées) — cohérent avec la nature des `Localisation` de ce
  module (noms de site, pas des adresses avec numéro de voie) ; à
  ajuster via `.env` si vos données réelles s'y prêtent mieux.
  L'ancienne URL `api-adresse.data.gouv.fr` est dépréciée
  (décommissionnement prévu fin janvier 2026 selon la doc officielle)
  — `data.geopf.fr/geocodage` est la bonne URL actuelle.
- **🌍 (lien externe)** — ouvre un service cartographique externe
  paramétrable (Google Maps par défaut, `VITE_GEOCODE_EXTERNAL_URL_
  TEMPLATE` dans `.env` du frontend, gabarit avec `{q}`) dans un
  nouvel onglet, pour une vérification visuelle manuelle rapide sans
  passer par un appel API.

```bash
# Exemple d'appel direct à l'API (sans passer par l'interface)
curl "http://localhost:6104/geocode?q=Parc%20Nord&limit=3"
```

### Centroïde de commune par code postal (`GET /commune_centroid`)

Utilisé par l'onglet **Fusion IP/MAC** (bouton "🏘️ Géocoder via code
postal") — pas par cet onglet Géolocalisation lui-même, mais vit ici
avec le reste du géocodage plutôt que dans un module dédié. Extrait un
code postal français à 5 chiffres d'un nom d'hôte (ex.
`BIO17-17300-ISLANDE-RB3011` → `17300`, `extractPostalCodeFromRow`
dans `fusionLib.js`), résout son centroïde via l'API officielle
**Découpage Administratif** (`geo.api.gouv.fr`, gratuite, sans clé,
`COMMUNE_PROVIDER_URL`/`COMMUNE_TIMEOUT_SECONDS` dans `.env`). Un code
postal français peut couvrir plusieurs communes (petites communes
rurales rattachées au bureau de poste d'un bourg voisin) —
`parse_commune_response` retient celle de plus grande population,
approximation par défaut de "la ville principale de ce code postal".
`centre` (le champ utilisé) est le point retenu par l'IGN — chef-lieu
si le centroïde mathématique tombe hors de la zone habitée principale
— pas un centroïde géométrique brut, plus utile cartographiquement.

Écrit directement dans `geolocations` (même table partagée, même
`upsertGeolocation` que le reste) — un bouton de lot, comme le
"🌍 Géolocaliser ces IP" déjà existant pour les IP publiques, pas une
confirmation par ligne : cohérent avec ce précédent déjà établi dans
ce même onglet, pas une nouvelle philosophie.

```bash
curl "http://localhost:6104/commune_centroid?code_postal=17300"
```

**Nuance à connaître** : supprimer un lieu ne l'exclut pas définitivement
— si les données le contiennent toujours, un nouveau scan le repropose.
C'est voulu (le scan reflète l'état réel des données), mais peut
surprendre si tu t'attendais à un "ignorer définitivement".

```bash
# Scan manuel, backend sqlite
python3 scan_geolocations.py --backend sqlite --db-file timeseries.db --type alerte_zenoss_email

# Scan manuel, backend postgres (nécessite psycopg2 installé côté hôte :
# pip install psycopg2-binary --break-system-packages)
export PGHOST=localhost PGPORT=6543 PGUSER=pixelgrid PGPASSWORD=pixelgrid PGDATABASE=pixelgrid
python3 scan_geolocations.py --backend postgres --type alerte_zenoss_email
```

## Prochaine étape

Les 4 vues (couple début/fin d'alerte, timeline équipement,
simultanéité, carto) ne sont pas encore construites — on commence par
la **timeline équipement**. La géolocalisation ci-dessus est le
préalable pour la vue carto qui suivra.

## Pont vers Supervision SI

Un service dédié (`pixel-grid-bridge`) synchronise **automatiquement et
en continu** (toutes les `BRIDGE_INTERVAL_SECONDS`, 60s par défaut) les
événements pixel-grid vers l'API de supervision — ils apparaissent
ensuite dans la colonne des sources de l'app principale (carte, arbre
JSON, calendrier, mots-clés) **sans rien coder côté frontend**, le
mécanisme générique existant s'applique tel quel.

- **Fenêtre glissante récente** (`BRIDGE_WINDOW_DAYS`, 30 jours par
  défaut) plutôt que tout l'historique — les types synthétiques ont
  ~1M points sur 2 ans, inadapté à un chargement direct côté navigateur.
  Plafond de sécurité supplémentaire (`BRIDGE_MAX_POINTS_PER_TYPE`,
  5000) par type et par cycle.
- **Une source par type** : `pixelgrid_<type>` (ex: `pixelgrid_alerte_zenoss_email`).
- **Résolution géographique** : localisation de l'événement (`data.localisation`)
  cherchée dans la table de géolocalisation ; à défaut, repli sur la
  **position par défaut** (entrée spéciale `__default__`, éditable dans
  l'onglet Géolocalisation, pré-remplissable via `PIXEL_GRID_DEFAULT_LAT`/
  `PIXEL_GRID_DEFAULT_LON` dans `.env`). Sans position par défaut
  configurée, les événements sans localisation connue sont ignorés ce
  cycle (pas de point fantôme à 0,0).
- **Remplace intégralement** la source à chaque cycle (comme le fait
  déjà `pipeline/` pour `supervision_demo`), pas de fusion incrémentale.

## Ébauche multi-utilisateur

Table `users` (login, group, config_json), un seul utilisateur `admin`
pour l'instant — pas d'authentification, juste la structure prête pour
plus tard. Pas d'interface associée à ce stade (hors scope explicite,
"en attendant").

## Vue timeline équipement

Accessible depuis la colonne de détail : clique le nom (📈) d'un
équipement dans la liste d'événements bruts d'une cellule — bascule
sur sa timeline complète (toute l'historique, pas seulement la fenêtre
cliquée).

- **Types `integer_enum`** (ex: `alerte_zenoss_email`) : les événements
  `valeur=1`/`valeur=0` sont **appariés automatiquement** en incidents
  début/fin (`valeur=1` ouvre, le `valeur=0` suivant referme). Un
  incident sans résolution trouvée reste marqué **« EN COURS »**
  (hachures rouges sur la barre). Barre horizontale proportionnelle en
  haut + liste détaillée en dessous (plus récent en premier).
- **Types `continuous`** (ex: `niveau`) : pas de notion d'incident,
  simple graphique en barres de la valeur dans le temps.
- **`GET /devices?type=X`** liste les équipements connus d'un type
  (utilisé en interne, pas encore de sélecteur dédié dans l'UI —
  seul le clic depuis la colonne de détail ouvre une timeline pour
  l'instant).

## Hiérarchie de localisation (`parent_localisation`, `location_type`)

Extension de `geolocations` pour le coffre-fort (recherche de codes
par localisation, voir `vault/README.md`) — bâtiment → étage → pièce →
point d'accès, une localisation référençant sa parente par son nom
(`parent_localisation`, auto-référence sur `geolocations.localisation`
elle-même). Deux colonnes NULLABLES, **rétrocompatibles** : une
localisation existante (équipement réseau géocodé) reste valide sans
hiérarchie, à la racine.

**Migration douce au démarrage** (`ensure_geolocations_hierarchy_columns`,
`pixel-grid/api/app.py`) — ce service n'a normalement AUCUNE logique
de schéma (table créée une fois par le générateur de données, voir
`data-generator/schema.sql`) : exception volontaire pour cet ajout
précis, `ALTER TABLE` seulement si la colonne n'existe pas déjà,
jamais une recréation qui perdrait les données réelles déjà en place.

`POST /geolocations` accepte désormais `parent_localisation`/
`location_type`, avec `COALESCE` côté mise à jour : ne pas les fournir
(ex. mise à jour des seules coordonnées) **préserve** la hiérarchie
déjà en place, jamais un écrasement silencieux vers `NULL`.

Vérifié réellement : 14 tests (migration sur une base simulant la
production existante, préservation des données, idempotence,
COALESCE, rétrocompatibilité pour les localisations sans hiérarchie).

## Ce qui a été vérifié depuis cet environnement (Claude)

Contrairement au frontend React (que je ne peux pas exécuter), le
backend Python/SQLite a pu être **réellement testé** ici :

- La logique du générateur (probabilités, fenêtres d'incident, seuils)
  a été rejouée en Python sur un échantillon représentatif — chiffres
  cohérents avec la configuration (voir détail plus bas).
- L'API Flask a été testée avec son client de test, sur une base SQLite
  construite en local (35 041 lignes, un point toutes les 30 min sur 2
  ans — pas le million de points complet, juste assez pour valider les
  requêtes d'agrégation à tous les niveaux).
- **Un vrai bug a été trouvé et corrigé pendant ce test** : la
  coloration initiale ("une seule erreur dans la cellule → rouge")
  rendait tous les mois rouges dès que le volume de points par cellule
  dépassait quelques centaines — noyant le signal au lieu de le faire
  ressortir. Corrigé en coloration par **taux** d'erreur (configurable,
  voir `seuil_taux_attention` / `seuil_taux_alerte` dans
  `configs/etat_example.json`), qui se comporte naturellement comme
  avant à grain fin (1 point = 0% ou 100%) tout en restant informatif à
  grain grossier.
- **`/aggregate_range`** (ajouté pour la mosaïque de l'interface) testé
  de la même façon : 730 cellules distinctes sur 2 ans au niveau jour
  (pas de fusion entre années), rejet correct d'une requête minute×2ans
  (~1M cellules estimées, plafond à 5000), non-régression de
  `/aggregate` confirmée après l'ajout.
- **`parse_zenoss_emails.py`** testé contre un extrait réel de ton
  backlog (pas un exemple inventé) : 7/7 entrées correctement extraites
  après deux corrections trouvées en testant (regex sur `Composants`
  vide qui avalait le reste de la ligne ; `Severite` rendu optionnel
  pour récupérer les entrées tronquées par l'affichage). Chaîne
  complète revérifiée bout en bout : CSV → SQLite → `/aggregate_range`,
  coloration cohérente (rouge sur les jours avec alertes actives, vert
  sinon).
- **Colonne de détail** (`/events`) testée contre les mêmes vraies
  données : liste correcte des événements bruts d'une plage.
- **Géolocalisation** testée en cycle complet : scan (5 nouveaux lieux
  détectés sur les vraies alertes), édition, re-scan idempotent (0
  doublon), suppression. Un vrai bug trouvé et corrigé en testant :
  les endpoints d'écriture utilisaient la même connexion SQLite en
  lecture seule que le reste de l'API (`mode=ro`, décidé plus tôt
  volontairement) — ajouté une connexion en écriture séparée,
  réservée à ces 3 endpoints.
- **`GET /geocode`** (assistance au géocodage, ajouté ensuite) : 17
  tests Python, `requests.get` simulé (jamais d'appel réseau réel vers
  le service BAN/Géoplateforme depuis cet environnement). Couvre le
  cas nominal, le 429/`Retry-After`, l'erreur réseau, le JSON
  illisible, le parsing défensif d'une réponse malformée (résultat
  ignoré plutôt qu'exception), et le bornage de `limit`. **Un vrai bug
  trouvé et corrigé en testant** : `limit=0` explicite tombait dans le
  piège Python `0 or 5` (zéro est falsy) et était silencieusement
  remplacé par la valeur par défaut au lieu d'être borné à 1.
  **Non vérifié** : aucun appel réel au service externe (pas de réseau
  ici) — la forme de réponse GeoJSON/geocodejson attendue est basée
  sur la documentation officielle (cartes.gouv.fr) et le format
  "geocodejson" standard de l'écosystème BAN, pas sur une réponse
  observée en direct.
- **`GET /commune_centroid`** (centroïde de commune, Fusion IP/MAC) :
  15 tests Python — `parse_commune_response` (commune la plus peuplée
  retenue parmi plusieurs candidates, liste vide, forme inattendue,
  coordonnées malformées, `population` absente traitée comme la plus
  basse plutôt que de planter), `commune_centroid_for_postal_code`
  (aucun appel réseau sur code postal vide, succès, aucune
  correspondance traité comme un résultat normal — pas une erreur —,
  panne réseau, erreur HTTP), route (paramètre manquant, succès, panne
  amont -> 502, aucune correspondance -> 200 avec `commune: null`).
  **Non vérifié** : aucun appel réel à `geo.api.gouv.fr` depuis cet
  environnement — forme de réponse basée sur la documentation
  officielle (guides.etalab.gouv.fr, geo.api.gouv.fr) et un exemple
  de structure vu via une recherche web, pas une réponse observée en
  direct pour un des codes postaux réels du parc.
- **Pont pixel-grid → Supervision SI** testé bout en bout, avec les
  deux vraies API en mémoire (clients de test Flask, sans réseau réel
  mais code identique à la prod) : événements réels → résolution
  géographique (mappée + repli par défaut) → GeoJSON → push
  `/ingest` → relecture `/data` → apparition dans `/sources`. Les 18
  alertes réelles ressortent avec les bonnes coordonnées, celles sans
  lieu connu utilisent bien la position par défaut avec le indicateur
  `position_par_defaut: true` pour les distinguer.
- **Appariement d'incidents** (`/timeline`) testé sur un cas
  synthétique à 3 cycles dont un non résolu : 3 incidents détectés,
  durées exactes (100s, 50s), le troisième correctement marqué "en
  cours" (pas de `valeur=0` de résolution dans les données). Revérifié
  aussi sur un vrai équipement du backlog réel.

**Non vérifiable depuis ici** : le script bash lui-même n'a pas pu être
exécuté tel quel (pas d'accès réseau pour installer `jq`/`sqlite3` dans
cet environnement) — sa syntaxe est validée (`bash -n`), sa logique est
identique à ce qui a été testé en Python, mais l'exécution réelle du
pipeline bash → awk → sqlite3 reste à valider chez toi.

**Backend PostgreSQL** : pas de serveur PostgreSQL disponible dans cet
environnement non plus (même contrainte réseau) — impossible de tester
une vraie connexion ou d'exécuter les requêtes. J'ai vérifié à la main
la construction des requêtes générées (`to_char(to_timestamp(ts) AT
TIME ZONE 'UTC', 'MM')` etc. — syntaxe standard, relue avec attention)
et confirmé la non-régression du backend SQLite après ce remaniement,
mais le chemin PostgreSQL en conditions réelles reste entièrement à
valider de ton côté.

## Procédure recommandée

**Backend SQLite** (par défaut) :
```bash
cd pixel-grid/data-generator

./generate.sh configs/etat_example.json sqlite timeseries.db
./generate.sh configs/niveau_example.json sqlite timeseries.db

sqlite3 timeseries.db "SELECT type, COUNT(*) FROM events GROUP BY type;"
```
```bash
docker compose up --build pixel-grid-api
curl "http://localhost:6104/aggregate?type=etat&level=year"
```

**Backend PostgreSQL** (port **6543**, configurable via `.env` —
volontairement décalé de 5432/5433, trop communs, pour éviter tout
conflit avec un PostgreSQL déjà présent sur ta machine) :
```bash
# Démarre le serveur (le schéma s'applique automatiquement au premier
# lancement, via /docker-entrypoint-initdb.d/)
docker compose up -d pixel-grid-postgres

cd pixel-grid/data-generator
export PGHOST=localhost PGPORT=6543 PGUSER=pixelgrid PGPASSWORD=pixelgrid PGDATABASE=pixelgrid
./generate.sh configs/etat_example.json postgres
./generate.sh configs/niveau_example.json postgres

psql -c "SELECT type, COUNT(*) FROM events GROUP BY type;"
```
```bash
PIXEL_GRID_BACKEND=postgres docker compose up --build pixel-grid-api
curl "http://localhost:6104/aggregate?type=etat&level=year"
# /health confirme le backend actif : {"status":"ok","backend":"postgres"}
```

Les deux backends exposent exactement la même API — seul `DB_BACKEND`
change côté conteneur `pixel-grid-api`.

Partage-moi ce que ça donne (en particulier le temps de génération réel
sur ~1M points sur les deux backends, et si la coloration te semble
juste sur les vraies données) avant qu'on construise l'interface
(grille 2-4px + menu horizontal auto-masquant).

## Format des données

Champs fixes par point, comme spécifié :
- `timestamp` (stocké en epoch Unix, colonne `ts`)
- `valeur` (décimal)
- `nom`
- `type`
- `data` (sous-arbre JSON libre — ici `{"service": "...", "os": "..."}`
  pour le premier usage réseau/informatique)

Deux `kind` supportés pour l'instant, chacun avec sa propre logique de
coloration :
- `integer_enum` (type "état") : -1/0/1, coloration par taux d'erreur.
- `continuous` (type "niveau") : réel borné, coloration par seuils
  bas/moyen/haut sur la moyenne de la cellule.

## Limites connues de ce v0

- **Le schéma PostgreSQL ne s'applique qu'une seule fois** (mécanisme
  `/docker-entrypoint-initdb.d/` de l'image officielle — ne s'exécute
  qu'à la toute première création du volume `pixel_grid_pg_data`). Si
  une table est ajoutée au schéma plus tard (comme `geolocations`)
  alors que le volume existe déjà, elle n'apparaît pas toute seule —
  réapplique le schéma à la main (idempotent, sans perte de données) :
  ```bash
  psql -c "$(cat pixel-grid/data-generator/schema.postgres.sql)"
  ```

- **Agrégation recalculée à chaque requête** (pas de cache), comme pour
  le reste du projet — à surveiller si le volume grossit encore ou si
  l'usage devient intensif.
- **API en lecture seule** (`mode=ro`) — l'écriture ne passe que par
  `generate.sh`. Pas de mécanisme d'ingestion incrémentale/temps réel
  pour l'instant (contrairement au reste de l'app qui a son pipeline
  push).
- **Coloration "pire cas" toujours disponible en théorie mais retirée**
  au profit du taux — si un usage précis nécessite explicitly signaler
  "au moins un incident, peu importe le taux", il faudra un mode de
  coloration séparé plutôt que de réintroduire l'ancien comportement
  par-dessus (qui redeviendrait inutile au global comme observé).
- **Pas encore d'interface** — volontairement, pour valider cette base
  avant de construire la grille et la navigation par-dessus.

## Branchement rights-api (livraison #317)

Suite de l'item 38 du backlog. Coordonnées de carte pour la
visualisation -- une entrée trafiquée ne configure rien de réel mais
peut égarer la lecture d'une carte (mauvais lieu affiché).

Gardé sur les 4 routes d'ÉCRITURE (créer/modifier une géolocalisation,
la supprimer, scanner les événements pour en détecter de nouvelles,
enregistrer une liste d'IP) -- jamais la lecture/agrégation.

OPT-IN via `PIXEL_GRID_RIGHTS_API_URL`, vide par défaut,
comportement inchangé tant qu'elle n'est pas configurée.

**Vérifié réellement** : comportement opt-in par défaut confirmé,
FAIL CLOSED si `rights-api` injoignable, 403 confirmé sur les 4
routes gardées avec un groupe non autorisé, lecture confirmée non
affectée. Non-régression complète reconfirmée.
