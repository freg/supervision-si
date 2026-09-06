# Squelette — Surcouche de supervision SI

## Installation rapide (livraison #374)

Demandé explicitement (2026-09-05) après une session de déploiement
particulièrement difficile : "une archive et un script qui déploie
sans intervention manuelle avec une config complète d'exemples et une
évaluation initiale de l'environnement pour cadrer les services
déployés qui s'adapte à l'os".

```bash
./install.sh
```

Ce script, à la racine du projet :
- vérifie Docker présent/démarré (message clair sinon, jamais un
  plantage silencieux) ;
- détecte la mémoire RÉELLEMENT disponible pour Docker (`docker info`
  -- reflète l'allocation de la VM Docker Desktop sur macOS, la RAM
  hôte réelle sur Linux natif, une seule commande valable sur les
  deux OS) ;
- choisit un périmètre de déploiement adapté (gateway+main minimal,
  gateway+main complet, ou tous les stacks) selon cette mémoire
  détectée -- seuils par PRUDENCE, pas une science exacte, voir
  `install.sh` pour le détail et le raisonnement complet ;
- génère `.env` automatiquement si absent (sans danger sur une
  première installation, `.env.example` sert de config complète
  d'exemples déjà présente) ;
- déploie SANS AUCUNE INVITE INTERACTIVE -- vérifié : les garde-fous
  destructifs de ce projet (purge Keycloak, placeholder LDAP) sont
  tous gated derrière un état PRÉEXISTANT, qui ne peut PAS exister sur
  un premier déploiement.

Pour ajuster le périmètre déployé après coup (documents réels via
Mayan, coffre-fort isolé, un service précis), voir le résumé affiché
en fin de script, ou directement `./scripts/run-all.sh` (sans
argument liste les cibles disponibles).

## Architecture

Chemin de bout en bout minimal, avant d'ajouter les vraies sources,
le frontend React/Leaflet et Elasticsearch (plus tard, si besoin).

## Architecture

```
pipeline/  -->  push HTTP  -->  api/  -->  Memcached (cache rapide)
                                      \-->  fichiers /app/data (persistance/fallback)

frontend/  -->  GET /data/<source>  -->  api/   (polling toutes les 10s)
```

- **`pipeline/`** : calcule les données d'une source (ici un GeoJSON factice)
  et les pousse vers l'API toutes les 30s. Aucune connaissance du stockage :
  responsabilité unique = calculer + pousser.
- **`api/`** : seul point d'écriture. Reçoit le push, écrit le fichier
  (source de vérité) puis peuple Memcached (chemin rapide). En lecture,
  sert Memcached en priorité, fallback fichier si le cache est vide/down.
- **`memcached`** : cache, pas de port exposé à l'hôte (accès interne only).
- **`frontend/`** : React + Vite + Leaflet, 3 colonnes (sources / carte /
  synthèse). Interroge l'API en `GET /data/<source>` toutes les 10s.
  Cliquer un élément sur la carte l'affiche dans la colonne de synthèse.
  Le bouton flottant « 📅 Calendrier » ouvre un panneau au-dessus de la
  carte pour sélectionner des dates ; la colonne de droite se scinde en
  Synthèse + Corbeille de sélection (voir ci-dessous).

## Vue calendrier et sélection

Détecte génériquement les dates/timestamps présents dans le contenu JSON
de chaque source (ISO 8601 *et* timestamps Unix, secondes ou
millisecondes — aucun nom de champ supposé), avec un filtre par
mots-clés optionnel (recherché dans le nom de la source **et** dans tout
le contenu JSON, en OU).

- **Couleur des cellules** : présence simple — vert si aucune
  correspondance ce jour-là, rouge dès qu'il y en a au moins une.
- **Navigation** : clic sur un mois (vue année) = zoom vers ce mois.
- **Sélection** : clic sur un jour (vue mois) = coche/décoche ce jour.
  Cumulable à travers plusieurs mois et années différentes — la
  sélection ne se réinitialise pas en naviguant.
- **Mots-clés** : expression libre avec opérateurs `OR` / `AND`
  (majuscules ou minuscules), précédence standard — `AND` se lie plus
  fort que `OR`. Ex : `incident OR panne AND regions` matche si
  "incident" est présent seul, ou si "panne" **et** "regions" sont tous
  les deux présents. Champ vide = tout matche (carte blanche).
  **Portée exacte** : grep textuel simple sur le nom de la source + le
  contenu JSON sérialisé (`json.dumps`), en minuscules — aucune
  interprétation de structure (clé vs valeur), voir `match_keywords()`
  dans `app.py`.
- **Mode Compteur** (onglet à côté de « Présence ») : au lieu d'une
  simple présence, agrège une **étiquette JSON** par jour :
  - `frequence` (sans `=`) : somme la valeur numérique de ce champ, où
    qu'il apparaisse dans le JSON, rattachée au jour trouvé **dans le
    même objet** (recherche non récursive d'une date parmi les champs
    frères — v1, pas de remontée vers les objets englobants si absente).
  - `type=incident` (avec `=`) : compte les occurrences où ce champ vaut
    exactement cette valeur, même règle de datation.
  - **Couleur** : décidée automatiquement par l'API selon le volume sur
    la période affichée — binaire (vert/rouge) si le maximum quotidien
    est < 3, tricolore (vert/orange/rouge) sinon. Valeur affichée en
    tout petit dans le coin de chaque cellule non vide.
- **Deux façons d'alimenter la corbeille**, qui se combinent :
  - Sélection de dates dans le calendrier → ajoute automatiquement les
    sources ayant une correspondance sur l'une des dates + mots-clés.
  - Case à cocher directement sur une source dans la colonne de gauche →
    l'ajoute sans passer par le calendrier.
- **Corbeille** (colonne de droite, section « Sélection ») : se remplit
  et se vide automatiquement pour refléter l'union des deux voies
  ci-dessus. Chaque source y est dépliable en arbre JSON avec case à
  cocher par nœud (racine comprise) : décocher un nœud désélectionne
  tout son sous-arbre ; les descendants d'un nœud décoché ne sont pas
  ré-activables individuellement tant que leur parent reste décoché
  (modèle volontairement simple pour ce squelette — voir
  `JsonTree.jsx`). Le bouton « ✕ » sur l'en-tête d'une source la retire
  de la corbeille — si elle reste par ailleurs matchée par la sélection
  de dates en cours, elle peut réapparaître (le retrait ne coupe que la
  voie manuelle).
- **Cohérence carte/corbeille** : si la source affichée sur la carte est
  aussi présente dans la corbeille, seules les features encore cochées
  dans son arbre JSON s'affichent — décocher une feature dans la
  corbeille la fait disparaître de la carte (et inversement). Ne
  s'applique qu'aux sources de type `FeatureCollection` (tableau
  `features`).
- **Arbre radial** (sous la corbeille) : visualisation D3 (façon
  [Observable radial tree](https://observablehq.com/@d3/radial-tree/2))
  de la hiérarchie actuellement sélectionnée — un nœud décoché dans la
  corbeille, et donc tout son sous-arbre, est simplement absent de
  l'arbre plutôt que grisé. Profondeur limitée à 4 niveaux (au-delà,
  résumé en « … ») pour rester lisible avec des sources volumineuses.
  **Interactif** : cliquer un nœud le désélectionne (comme décocher dans
  l'arbre JSON de la corbeille) — puisque seuls les nœuds sélectionnés
  sont affichés, un clic ne peut que retirer, jamais ré-ajouter
  individuellement un nœud (même limite que l'arbre JSON de la corbeille,
  pour rester cohérent). **Coloration** : un nœud est bleu si tout son
  sous-arbre d'origine est encore intégralement sélectionné, orange s'il
  a perdu au moins un descendant (élagué ailleurs dans la corbeille) —
  cet état orange se propage vers les nœuds parents jusqu'à la racine
  (nœuds **et** liens), pour visualiser d'un coup d'œil où une sélection
  a été raccourcie, même en vue réduite/racine.
- **Panneau de survol** : survoler n'importe quel nœud (à tout moment,
  quel que soit l'état de navigation ou d'aperçu) affiche un panneau
  HTML dans le coin le plus proche — nom du nœud + tableau `clé/valeur`
  de son contenu JSON, sur 1 à 2 niveaux de profondeur (les valeurs
  objets/tableaux imbriqués sont résumées, ex: `{3}` pour 3 clés,
  `[5]` pour 5 éléments). Remplace l'ancienne loupe en texte SVG,
  illisible à l'échelle de l'arbre compact.
- **Zoom clic droit** : clic droit sur l'arbre (menu contextuel du
  navigateur désactivé à cet effet) zoome, centré sur le point cliqué.
  Un contrôle de niveau de zoom apparaît alors (curseur + bouton
  « ↺ Réinitialiser ») pour ajuster ou revenir à l'échelle normale.
- **Premier clic / second clic** : cliquer un nœud dans la vue normale
  (filtrée) ouvre un **aperçu de contexte** — une chaîne simple depuis la
  racine de la source jusqu'au nœud cliqué (un segment par niveau, sans
  ramification), puis, seulement à partir de ce nœud, son sous-arbre
  complet en aval s'il en a un (nœuds non sélectionnés en gris plutôt
  qu'absents). Cliquer une **feuille** donne donc une simple ligne ;
  cliquer un **nœud intermédiaire** donne la ligne jusqu'à lui, puis un
  petit arbre en bout de chaîne. Ce premier clic **ne modifie rien**.
  C'est le **second clic**, sur un nœud à l'intérieur de cet aperçu, qui
  bascule réellement sa présence dans la sélection — que ce nœud soit
  déjà sélectionné (retrait simple) ou non (réintégration précise, qui
  préserve l'état des branches voisines plutôt que de tout rallumer, voir
  `computeReinclusion()` dans `JsonTree.jsx`). Après le second clic,
  l'aperçu se referme et on repasse en navigation normale. Un bouton
  « ← Retour » permet aussi de sortir de l'aperçu sans rien changer.
- **Agrandissement sur la carte** : bouton « ⤢ Agrandir sur la carte »
  au-dessus de l'arbre radial (colonne de droite) — l'affiche en grand
  (rayon plus large, donc plus lisible) en overlay **ancré en bas** de
  la carte, pour laisser le haut visible. Coexiste avec le calendrier
  (ancré en haut) sans chevauchement si les deux sont ouverts en même
  temps. Bouton « ✕ Réduire » dans l'overlay, ou lien « réduire » dans
  la colonne de droite, pour revenir à la taille compacte.
- **Homogénéité des 3 colonnes** : la case à cocher de la colonne des
  sources reflète maintenant l'état réel dans la corbeille (pas
  seulement la sélection manuelle) — cochée si la source y est
  entièrement sélectionnée, **indéterminée** (tiret) si elle y est
  partiellement sélectionnée (via une date du calendrier + mots-clés,
  ou après un décochage fin dans l'arbre JSON), vide si absente. Cliquer
  la case bascule entre absente et entièrement présente — pour un
  contrôle plus fin, décocher des nœuds individuels dans la corbeille ou
  l'arbre radial.
- Seules les sources **enregistrées** (pas les propositions non
  confirmées) sont prises en compte dans l'analyse.

```bash
# Exemples d'appels directs à l'API
curl "http://localhost:6103/calendar/summary?level=year&period=2026"
curl "http://localhost:6103/calendar/summary?level=month&period=2026-08&keywords=incident%20OR%20panne"
curl "http://localhost:6103/calendar/sources?dates=2026-08-07,2026-03-12&keywords=incident%20AND%20regions"
```

## Données d'exemple

`samples/carte_loyers.geojson` — inspiré du dataset officiel [« Carte des
loyers »](https://www.data.gouv.fr/datasets/carte-des-loyers-indicateurs-de-loyers-dannonce-par-commune-en-2025)
(ANIL / ministère de la Transition écologique, Licence Ouverte 2.0).
Champs (`INSEE_CO`, `loypredm2`, `IPm2`, `IPm2_1`, `TYPPRED`, `nbobs_com`,
`nbobs_mail`, `R2_adj`) conformes au schéma réel du dataset, communes et
coordonnées réelles. **Valeurs de loyer illustratives** — le CSV source
(4,5 Mo) est protégé par `robots.txt` et n'a pas pu être téléchargé pour
extraire les vrais chiffres 2025 ; les valeurs ici sont plausibles mais
inventées, à ne pas citer comme officielles.

```bash
curl -X POST http://localhost:6103/ingest/carte_loyers \
  -H "Content-Type: application/json" \
  --data-binary @samples/carte_loyers.geojson
```

`samples/batiments_occupation.geojson` — bâtiments avec typologie de
logements et **population estimée par déduction**, comme demandé
(nombre d'étages × logements par étage × répartition F1-F5 × occupation
moyenne par typologie). Inspiré de la structure BDNB (data.gouv.fr)
pour la description des bâtiments — mais ce niveau de détail réel
(nombre de pièces par logement individuel) provient normalement des
**Fichiers fonciers DGFiP, à accès restreint aux acteurs publics** (voir
échange précédent) : ces valeurs sont donc entièrement déduites, pas
extraites d'un fichier officiel individuel. Le modèle d'occupation
moyenne utilise tes deux valeurs (F1 = 1,2 / F5 = 2,6) avec F2/F3/F4
interpolés (1,8 / 2,3 / 2,5) — à ajuster si tu as une vraie table de
référence. Géométrie en point (centroïde), pas l'emprise réelle du
bâtiment (viendrait de `cadastre.data.gouv.fr`, non téléchargée ici).

```bash
curl -X POST http://localhost:6103/ingest/batiments_occupation \
  -H "Content-Type: application/json" \
  --data-binary @samples/batiments_occupation.geojson
```

Alternative sans `curl` : bouton **« ➕ Injecter un fichier »** en haut
de la colonne des sources (frontend) — sélectionne un `.json`/`.geojson`
local, nom de source pré-rempli depuis le nom de fichier (éditable),
pousse via `/ingest/<source>` directement depuis le navigateur.

## Configuration des ports

Tous les ports exposés à l'hôte sont centralisés dans `.env` (à la
racine, lu automatiquement par Docker Compose — pas besoin de
`--env-file` ni d'export manuel) :

| Variable | Défaut | Service |
|---|---|---|
| `SUPERVISION_API_PORT` | 6103 | API principale |
| `SUPERVISION_FRONTEND_PORT` | 6173 | Frontend (Vite) |
| `PIXEL_GRID_API_PORT` | 6104 | API du module pixel-grid |
| `PIXEL_GRID_POSTGRES_PORT` | 6543 | PostgreSQL du module pixel-grid |

Ces valeurs évitent volontairement les ports courants (5000-5001,
8000, 3000, 5432/5433, 9443, 9922, 3366...) déjà pris par d'autres
services dans certains environnements (ex: docker-registry). Pour
changer un port, modifie `.env` — un seul endroit, tout le reste
(`docker-compose.yml`, le frontend) le lit depuis là.

## Menu horizontal et module pixel-grid

Un menu auto-masquant (survoler le tout haut de l'écran pour le faire
apparaître) permet de basculer entre **Supervision SI**, **Pixel Grid**,
**Géolocalisation** et **Tickets** (voir `pixel-grid/README.md` et
`tickets/README.md` pour le détail de chaque module). Un service dédié
synchronise en continu les données pixel-grid vers la liste des sources
ci-dessus (`pixelgrid_<type>`) —
elles apparaissent automatiquement dans la colonne de gauche, aucune
action manuelle nécessaire une fois `pixel-grid-bridge` démarré.

## Lancer le squelette

### Lanceur — vue d'état et start/stop/restart par module

Une fois le stack construit (`run.sh`/`run-all.sh` ci-dessus), pour le
piloter au quotidien sans retaper `docker compose` à chaque fois,
façon `apachectl`/`service` :

```bash
./scripts/launcher.sh status              # vue d'ensemble de tous les modules
./scripts/launcher.sh status vault        # un seul module
./scripts/launcher.sh start vault         # démarre un module précis
./scripts/launcher.sh stop tickets
./scripts/launcher.sh restart hub
./scripts/launcher.sh start all           # tout démarrer/arrêter d'un coup
./scripts/launcher.sh                     # liste les modules connus
```

15 modules, regroupant les 31 services de `docker-compose.yml` selon
leurs dépendances RÉELLEMENT déclarées (`depends_on`), pas une
supposition sur les noms -- vérifié service par service avant
d'écrire la cartographie. `status` affiche un tableau avec l'état de
chaque module (actif/partiel/arrêté) et le détail par conteneur.

Ne duplique jamais la logique de `docker compose` -- ce script
ORGANISE les appels et PRÉSENTE le résultat, rien de plus. Le
formatage du tableau (`scripts/launcher_status.py`) est séparé de la
coquille bash pour rester testable sans Docker.

### Plusieurs stacks (gateway + GED + principal + instance isolée du coffre-fort)

Ce projet est composé de **quatre** stacks Docker Compose distincts,
chacun avec son propre `run.sh` : `gateway/` (Keycloak + tls-proxy --
l'entrée unique, PORT `GATEWAY_PORT`), `mayan/` (GED tierce, adoptée
en #158), le stack principal (`scripts/run.sh`, les ~20 services
applicatifs), et `vault-standalone/` (instance isolée du coffre-fort,
optionnelle). Plutôt que de se souvenir où aller, un point d'entrée
central délègue vers le bon script :

```bash
./scripts/run-all.sh gateway up -d --build            # Keycloak + tls-proxy
./scripts/run-all.sh mayan up -d --build               # GED (Mayan EDMS)
./scripts/run-all.sh main up -d --build                # stack principal
./scripts/run-all.sh vault-standalone up -d --build    # instance isolée (optionnel)
./scripts/run-all.sh all up -d --build                 # les quatre, DANS CET ORDRE
./scripts/run-all.sh all down                          # arrête les quatre
./scripts/run-all.sh                                   # liste les cibles disponibles
```

**`all` est la commande à utiliser pour un premier démarrage complet**
-- sans `gateway/` démarré, RIEN n'écoute sur `GATEWAY_PORT` (aucun
service applicatif n'est alors joignable, même si le stack principal
lui-même tourne parfaitement) ; sans `mayan/`, la GED (`ged-api`)
répond une erreur 502 sur toute tentative de créer/lire un document.
Piège réel rencontré (2026-09-05) : `./scripts/run.sh up -d --build`
seul (stack principal uniquement, sans `gateway/`) donne l'impression
que "rien ne se passe" -- le stack principal démarre bel et bien,
mais silencieusement inutilisable tant que `gateway/` n'est pas AUSSI
lancé séparément.

Ne duplique JAMAIS la logique de chaque `run.sh` (détection HOST_IP,
rendu Keycloak/PKI/nginx, garde-fous LDAP...) -- une simple
délégation. Avec `all`, arrêt au premier échec plutôt que de
continuer sur une cible suivante dans un état incertain. Ordre choisi
délibérément : `gateway` en premier (les services applicatifs s'y
fient), `mayan` juste après (initialisation plus longue au premier
démarrage, autant lui laisser le temps avant que `ged-api` ne le
sollicite), `main` ensuite, `vault-standalone` en dernier (optionnel,
indépendant des trois autres).

**Piège réel rencontré** : `scripts/run.sh` (stack principal, pas le
point d'entrée central) ne comprend PAS "all"/"main"/"vault-standalone"/
"gateway" comme sous-commandes -- ce sont des CIBLES de `run-all.sh`.
Les appeler par erreur sur `run.sh` (`./scripts/run.sh all up -d
--build` au lieu de `./scripts/run-all.sh all up -d --build`)
transmettait silencieusement "all" à `docker compose`, qui échouait
avec un message Docker peu clair ("unknown docker command").
`scripts/run.sh` détecte maintenant ce cas précis et redirige vers la
bonne commande.

**Mémoire Docker Desktop limitée -- signalé en conditions réelles**
(2026-09-05, Mac 8 Go de RAM totale, 4 Go alloués à Docker Desktop) :
lancer les quatre cibles simultanément peut suffire à épuiser la VM
Docker Desktop et faire tuer un conteneur par OOM (souvent Keycloak,
son étape de build étant particulièrement gourmande -- voir
`keycloak/README.md`) -- même AVEC une limite mémoire de conteneur
individuelle fixée, un OOM au niveau SYSTÈME (pas seulement cgroup)
peut survenir si la demande cumulée de tous les conteneurs dépasse ce
qui est réellement alloué à la VM. Sur une machine à mémoire limitée,
préférer démarrer uniquement `gateway` + `main` (l'essentiel pour
utiliser le hub) plutôt que `all`, en laissant `mayan`/
`vault-standalone` de côté jusqu'à en avoir spécifiquement besoin.
Augmenter l'allocation mémoire de Docker Desktop (Réglages →
Ressources → Mémoire) reste la solution la plus robuste si la RAM
physique de la machine le permet -- en laissant toujours au moins
quelques Go pour macOS lui-même, sans quoi c'est tout le système qui
devient peu réactif.

**Encore plus ciblé, DANS le stack `main` lui-même (livraison
#367)** : `./scripts/chantier.sh build --minimal` ne déploie qu'un
sous-ensemble curé (hub + tickets/tâches/GED opérationnels), au lieu
des ~20 services du stack main au complet -- voir la section
dédiée ci-dessous.

### Redéploiement rapide du stack "en chantier" (`scripts/chantier.sh`)

Demandé explicitement (livraison #149) : pendant le développement,
Keycloak/le proxy TLS (`gateway/`) changent rarement une fois en
place, alors que les ~20 services applicatifs (`main`) sont
redéployés à CHAQUE livraison -- inutile de les faire redémarrer à
chaque fois, et un `down`/`up --build` involontaire sur `gateway/`
romprait l'authentification de tout le monde pour rien. Simple
raccourci sur `scripts/run.sh`, qui ne gère DÉJÀ que le stack `main`
(voir plus haut) -- ne duplique aucune logique.

Depuis la livraison #162 : `build` recharge AUSSI automatiquement
`tls-proxy` (régénère sa config + `docker compose restart`, jamais
via `gateway/scripts/run.sh` -- pas de prompt Keycloak déclenché par
erreur). `tls-proxy` lit sa config depuis un fichier monté en
VOLUME, jamais reconstruit par un simple changement d'image -- une
nouvelle route ajoutée à un module restait donc invisible tant
qu'on n'y pensait pas explicitement (bug réel rencontré 2 fois,
schema-analyzer puis ged). Échec de ce rechargement NON BLOQUANT
(`gateway/` peut être arrêté) -- un avertissement, jamais un `build`
principal qui échoue à cause de ça.

```bash
./scripts/chantier.sh down             # arrête SEULEMENT le stack main
./scripts/chantier.sh down -v          # idem + supprime les volumes
./scripts/chantier.sh build            # reconstruit + relance SEULEMENT le stack main, puis recharge tls-proxy
./scripts/chantier.sh build prefs-api  # reconstruit + relance un seul service, puis recharge tls-proxy
./scripts/chantier.sh build --minimal  # SOUS-ENSEMBLE curé -- voir ci-dessous
```

**`--minimal` (livraison #367)** -- demandé explicitement, machine à
mémoire limitée (voir section dédiée plus haut) : déploie SEULEMENT
`memcached tickets-postgres hub prefs-api tickets-api tasks-api
ged-api` -- pensé pour "hub ET ses fonctionnalités les plus utilisées
(tickets, tâches, GED) opérationnelles" (réponse exacte de la
personne), au lieu des ~20 services du stack main au complet.
Combinable avec un service supplémentaire explicite (`--minimal
relations-api`) -- s'AJOUTE à la liste minimale, jamais à sa place :
usage prévu pour tester la livraison EN COURS sans redéployer tout
le stack. ⚠️ `ged-api` répond mais ne stocke/lit aucun document réel
sans la stack `mayan` SÉPARÉE (`./scripts/run-all.sh mayan up -d
--build`) -- avertissement affiché à l'usage.

**⚠️ Engagement de maintenance, demandé explicitement** : cette liste
n'est PAS figée une fois pour toutes -- à CHAQUE livraison qui ajoute
ou modifie un service destiné à être testé "à la carte", se demander
si la liste `MINIMAL_SERVICES` (`scripts/chantier.sh`, en tête du
fichier) a besoin d'un ajout, ou a minima rappeler dans le message de
livraison la commande `--minimal <service>` à utiliser pour tester
CETTE livraison précise. Ne jamais présumer que la liste reste
pertinente sans y repenser.

`gateway/` et `vault-standalone/` restent intacts et en
fonctionnement dans tous les cas (jamais reconstruits ni arrêtés) --
SEUL `tls-proxy` est rechargé (config + redémarrage, jamais
reconstruit) après `build`, voir ci-dessus. `build` = toujours
`up -d --build` (jamais un simple `docker compose build` qui
laisserait les anciens conteneurs tourner avec l'ancienne image --
le cycle normal de redéploiement en développement est TOUJOURS
"reconstruire ET relancer").

**Compatibilité macOS (bash 3.2)** -- corrigé livraison #340. macOS
fournit par défaut bash 3.2 (2007, dernière version compatible GPLv2
avant qu'Apple ne cesse de suivre les versions GPLv3) -- un tableau
VIDE (`ARGS=()`) suivi d'une expansion `"${ARGS[@]}"` sous
`set -u` (`nounset`, activé en tête de ce script) y déclenche
`unbound variable`, contrairement à bash 4+ (Linux, ou bash installé
via Homebrew) où cette même expansion renvoie simplement zéro
argument sans erreur. Touchait `./scripts/chantier.sh build --all`
(sans autre argument) -- corrigé en testant `${#ARGS[@]}` (le
COMPTAGE d'éléments, jamais affecté par ce piège même en bash 3.2)
avant de tenter l'expansion elle-même. Sur macOS, `brew install bash`
donne accès à une version récente si vous préférez éviter ce genre
de piège à l'avenir plutôt que de compter sur ce correctif ponctuel.

### Premier démarrage rapide (`scripts/generate-env.sh`)

Demandé explicitement (2026-09-05) : un moyen de tester le stack sans
remplir à la main les ~237 variables de `.env.example`. Génère un
`.env` complet à la racine -- détecte automatiquement `HOST_IP`
(IP LAN réelle -- macOS via `ipconfig`, Linux via `ip route`/
`hostname -I`) et `COMPOSE_PROJECT_NAME` (nom du dossier courant),
génère aléatoirement les secrets INTERNES à ce docker-compose
(mot de passe admin Keycloak, secret de service prefs-api, mot de
passe admin Mayan, passphrase+sel SSH_TUNNELS et SNMP, mot de passe
de l'annuaire LDAP de test) -- tout le reste reprend `.env.example`
tel quel.

```bash
./scripts/generate-env.sh
```

Les identifiants générés (admin Keycloak, admin Mayan, annuaire
LDAP) sont sauvegardés à part dans `.env.generated-secrets.txt`
(jamais versionné, mêmes permissions restreintes que `.env`) -- pour
s'y reconnecter après coup sans avoir à les extraire de `.env` à la
main.

**Se connecter au hub une fois le stack démarré** (voir section
suivante) : un annuaire LDAP de TEST (`openldap-test`, livraison
#348, voir `gateway/README.md`) fournit 3 comptes -- `alice`/`bob`/
`admin_test`, même mot de passe `password` pour les trois. Sans lui,
AUCUNE connexion n'était possible (Keycloak n'a aucun utilisateur
local humain défini par défaut). Assigner le rôle `admin_hub` à
`admin_test` dans la console Keycloak pour tester les fonctions
réservées (rôles LDAP désactivés par défaut, attribution manuelle).

**Reste volontairement NON configuré** (le stack démarre quand même,
ces modules répondent une erreur claire tant qu'ils ne sont pas
renseignés à la main -- voir le README de chaque module) : tout ce
qui pointe vers un système EXTERNE réel et préexistant -- bases
MySQL des modules pont (IPAM/Optick/Zenoss/TTS-GU/OwnCloud/Cacti --
lecture seule sur une base existante, jamais créée par ce projet),
GLPI, Nebula, un compte IMAP réel, Google OAuth, network-agent
(nécessite une interface réseau réelle à capturer), TRB140. Un
secret généré aléatoirement ne correspondrait à aucun de ces
systèmes réels -- impossible à deviner à leur place.

`vault-standalone/` (stack séparé, sa propre configuration
indépendante) reste hors du périmètre de ce script -- voir
`vault-standalone/README.md` si besoin.

Une fois TOUT le stack démarré (voir section suivante --
`./scripts/run-all.sh all up -d --build`, pas `scripts/run.sh` seul),
peupler quelques données d'exemple dans les modules natifs (tickets,
tâches, architecture réseau, SNMP, classifier, GED) :

```bash
python3 scripts/seed-sample-data.py
```

Voir `scripts/README-seed.md` pour la portée exacte (modules couverts
et pourquoi les systèmes pont externes réels ne le sont pas).

### Stack unique (principal)

⚠️ **Cette section décrit `scripts/run.sh` SEUL, qui ne démarre QUE
le stack principal** -- pour un PREMIER démarrage complet et
réellement fonctionnel (Keycloak/tls-proxy + GED + stack principal),
utiliser `./scripts/run-all.sh all up -d --build` (voir section
précédente) à la place. Piège réel rencontré (2026-09-05) : lancer
`./scripts/run.sh` seul démarre bien le stack principal, mais sans
`gateway/` (jamais inclus ici) RIEN n'écoute sur `GATEWAY_PORT` --
aucun service applicatif n'est alors joignable depuis l'extérieur,
même si ce stack tourne parfaitement de son côté.

Si le navigateur tourne sur la même machine que Docker :
```bash
docker compose up --build
```

Si le navigateur est sur une autre machine que Docker (VM, accès distant
par IP) — cas fréquent en environnement de dev à distance — utilise le
script qui détecte et injecte automatiquement l'IP courante :
```bash
./scripts/run.sh up --build
```
Ça évite de modifier `VITE_API_BASE_URL` à la main à chaque fois que
l'IP change (redémarrage de VM en DHCP, changement de réseau...).
Si la détection automatique ne convient pas à ta configuration (VPN,
plusieurs interfaces réseau), force la valeur toi-même :
```bash
HOST_IP=192.168.1.42 ./scripts/run.sh up --build
```

Puis ouvrir `http://<HOST_IP ou localhost>:6173` pour le frontend.

**Cas rencontré en conditions réelles** : `docker compose build` échouant
sur `COPY shared/VERSION.json .` (tous les services, même erreur) alors
que `run.sh` affichait bien "Version (hash du contenu) : ..." avant
l'échec, et que le fichier existait au bon endroit une fois vérifié
manuellement (`ls -la ./shared/VERSION.json`). Mécanisme exact non
identifié avec certitude dans cet environnement précis (`HERE_DIR`
n'est référencé nulle part ailleurs dans `docker-compose.yml` ni les
Dockerfiles) -- mais `export HERE_DIR` (déjà dans `scripts/run.sh`,
ajouté après ce retour) a résolu le problème. Si un souci similaire
survient malgré cet export déjà présent, vérifier que la commande est
bien lancée depuis la racine du projet (`docker compose` s'appuie sur
le répertoire de travail courant pour trouver `docker-compose.yml`,
jamais sur `HERE_DIR`).

## Découverte des sources

Deux façons pour une source d'exister :

- **`POST /ingest/<source>`** — chemin de confiance. La source est
  auto-enregistrée immédiatement, comme avant.
- **Dépôt manuel d'un fichier `.json`** dans le volume `api_data` (par
  exemple `cp mes_donnees.json <volume>/regions.json`) — détecté au scan
  (`GET /sources`), mais **proposé** plutôt qu'activé automatiquement.
  Le frontend affiche ces propositions dans une section dédiée avec un
  bouton "Ajouter" (nouveau fichier) ou "Prendre en compte" (fichier déjà
  actif mais modifié en dehors du chemin `/ingest`).

Un fichier déposé à la main n'a pas besoin d'avoir l'enveloppe
`{source, updated_at, data}` — l'API la reconstruit à la lecture à partir
du contenu brut et de la date de modification du fichier.

```bash
# Exemple : POST classique (chemin de confiance, auto-enregistré)
curl -X POST http://localhost:5000/ingest/regions \
  -H "Content-Type: application/json" \
  --data-binary @regions.geojson

# Exemple : dépôt manuel (détecté, proposé, à confirmer dans l'UI
# ou via l'API)
curl -X POST http://localhost:5000/sources/regions/register
```

```bash
# Vérifier que l'API répond
curl http://localhost:5000/health

# Après ~30s (premier cycle du pipeline), lire la donnée poussée
curl http://localhost:5000/data/supervision_demo
```

Réponse attendue une fois le pipeline passé :
```json
{"status": "ok", "source": "supervision_demo", "updated_at": "...", "data": {...GeoJSON...}}
```

Avant le premier push, ou si tu coupes le pipeline :
```json
{"status": "unavailable", "source": "supervision_demo"}
```
(code HTTP 503 — état explicite, pas de silence ambigu, comme décidé).

## Bannette d'interaction — "verser" une sélection comme source

Première tranche d'un chantier plus large (accompagnement visuel
inter-onglets, gestion de couches sur la carte, graphe de dépendances
amont/aval) demandé par la personne — séquencé volontairement en
plusieurs livraisons plutôt que tout d'un bloc, celle-ci pose le socle
côté données.

**Le registre des sources porte désormais une origine**
(`external` par défaut — dépôt de fichier ou `/ingest`, comportement
inchangé — ou `selection`, nouveau) via `POST /sources/from-selection`.
Contrairement à `/ingest` (chemin de confiance, auto-enregistré), une
source versée depuis une sélection reste **proposée** jusqu'à
promotion explicite — une sélection ad hoc n'a pas la même légitimité
immédiate qu'un flux poussé par un système externe. L'origine est
**préservée** à travers une promotion (`register`) — testé
explicitement.

Côté interface, "Sélection" (la corbeille existante, éphémère,
perdue au rechargement) gagne un bouton **"📥 Verser vers la
bannette"** qui la persiste comme nouvelle source, dans une section
dédiée de la colonne des sources ("Bannette d'interaction"), distincte
des "Propositions" classiques (dépôt externe détecté au scan) —
promouvable en source pérenne, ou écartable, comme n'importe quelle
proposition.

**Simplification assumée pour cette première version** : "Verser"
envoie les données **brutes** (non filtrées) de chaque source de la
corbeille — pas encore le filtrage fin par nœud désélectionné
(`deselectedPaths`, utilisé par ailleurs pour l'arbre radial et la
carte). Reproduire cette logique récursive correctement sans jamais
pouvoir la vérifier visuellement dans cet environnement de
développement était un risque jugé trop réel pour cette livraison —
prévu pour une prochaine tranche, une fois cette brique testée en
conditions réelles.

**Vérifié réellement** : 20 tests Python (le chemin `/ingest`
existant continue d'auto-enregistrer exactement comme avant, une
sélection versée reste non enregistrée avec la bonne origine, la
promotion préserve l'origine, l'assainissement du nom empêche tout
chemin traversant, un cycle suppression/restauration ne touche jamais
à l'origine d'une source externe).

**Encore à faire** (chantiers suivants, pas cette session) : le
filtrage fin par sélection avant envoi ; multi-sélection dans Fusion
(aujourd'hui une seule ligne à la fois) pour pouvoir aussi y verser
depuis ce module ; gestion de couches sur la carte ; le composant
d'aperçu réduit + volume/emprise (le "où en suis-je dans l'ensemble"
demandé par la personne) — volontairement reporté à une fois qu'il y
aura de vraies données de bannette à représenter plutôt que construit
à vide ; le graphe de dépendances amont/aval lui-même, qui s'appuiera
sur cette bannette une fois alimentée en conditions réelles.

## Outil de coordonnées (carte)

Pied de page persistant sous la carte :
- **Survol** : latitude/longitude de la position de la souris, mise à
  jour en continu.
- **Capture** : Ctrl+clic (ou Cmd+clic sur Mac) ou **clic droit**
  (menu contextuel du navigateur désactivé sur la carte à cet effet)
  → stocke la coordonnée dans le champ juste à côté, en lecture seule
  mais sélectionnable (clic dedans = tout sélectionné) et copiable via
  le bouton **📋 Copier**.

Pensé pour l'onglet Géolocalisation : repère un lieu sur la carte,
capture ses coordonnées, colle-les dans le champ latitude/longitude du
lieu correspondant.

## Robustesse de l'affichage GeoJSON sur la carte

**Bug réel corrigé** : sélectionner dans la colonne des sources une
source dont le contenu n'est pas un GeoJSON valide (un arbre figé
Zenoss/IPAM/Optick, un JSON de tickets...) faisait planter
`react-leaflet` avec `Uncaught Error: Invalid GeoJSON object`, une
erreur synchrone non rattrapée par React qui démontait **toute
l'application**, pas seulement la carte (confirmé par l'export console
fourni, avec le message React "Consider adding an error boundary").

Double protection ajoutée :
- `lib/geojson.js` (`isValidGeoJson`) — vérification de forme (un
  `type` GeoJSON reconnu, `features`/`geometries` présents si
  pertinent) **avant** de monter `<GeoJSON>` ; une source non-géo
  affiche désormais un bandeau explicite dans la carte au lieu de
  planter. 14 tests Node, dont les cas réels ayant causé le bug (arbre
  Zenoss classification et localisation).
- `components/ErrorBoundary.jsx` — filet générique réutilisable
  enroulé autour de `<GeoJSON>`, pour tout ce qui passerait la
  vérification de forme mais resterait malformé plus profondément
  (une géométrie individuelle invalide, par exemple) — n'a pas encore
  servi mais suit directement la suggestion de React dans l'erreur
  d'origine.

## Téléchargement et suppression douce des sources

Colonne des sources (gauche) :
- **⬇️ par source** : télécharge son JSON complet (`{source, updated_at, data}`).
- **⬇️ Tout** (en-tête) : télécharge un seul fichier combiné
  `{nom_source: contenu, ...}` pour toutes les sources actives —
  n'inclut que ce qui est déjà chargé côté frontend (pas de requête
  réseau supplémentaire).
- **🗑️ par source** : suppression **douce** — la source disparaît de la
  liste active, mais son fichier reste intact sur disque
  (`DELETE /sources/<source>`, testé : les données restent lisibles via
  `/data/<source>` même après suppression).
- **🗑️ Sources supprimées** (en-tête) : déplie la liste des sources
  supprimées, chacune avec un bouton **↩️ Restaurer**
  (`POST /sources/<source>/restore`) qui la fait réapparaître à
  l'identique (état de sélection non conservé, à reconstruire).

```bash
curl -X DELETE http://localhost:6103/sources/regions
curl http://localhost:6103/sources/deleted
curl -X POST http://localhost:6103/sources/regions/restore
```

## Points volontairement non traités à ce stade

- **Validation du schéma GeoJSON** en entrée de `/ingest/<source>` — à durcir
  une fois le contrat de données par source stabilisé.
- **Elasticsearch** — écarté du squelette initial, à ajouter en service
  supplémentaire si la colonne de synthèse a besoin de recherche full-text.
- **Conversion des notebooks Jupyter** en scripts de `aggregate_source_data()`
  dans `pipeline/main.py` — actuellement un placeholder.
- **CORS ouvert à toute origine** sur l'API (`CORS(app)`) — à restreindre à
  l'origine réelle du frontend avant tout déploiement en prod.
- **Analyse calendaire recalculée à chaque requête** (pas de cache) — reparcourt
  toutes les sources enregistrées à chaque appel de `/calendar/summary` ou
  `/calendar/day`. Acceptable pour ce squelette, à revoir si le volume de
  données grossit significativement.
- **Mots-clés non persistés** côté serveur — reconfigurés à chaque
  session frontend.
- **Syntaxe mots-clés simplifiée** : pas de parenthésage, pas de
  guillemets pour les phrases, un terme = un mot. `AND` a toujours
  priorité sur `OR` (pas de regroupement explicite possible en v1).
- **Détection de dates par heuristique** (regex ISO 8601 + bornes de
  plausibilité pour les timestamps Unix) — peut manquer des formats de
  date non standards, ou occasionnellement confondre un grand nombre
  avec un timestamp (faux positif rare vu les bornes choisies).
- **Retrait manuel d'une source de la corbeille** persiste jusqu'au
  prochain changement de sélection de dates ou de mots-clés — si la
  sélection est ensuite modifiée puis annulée à l'identique, la source
  peut réapparaître (le retrait n'est pas mémorisé en soi, seul le
  recalcul déclenché par un changement l'est).
- **Modèle de sélection fine (arbre JSON)** : décocher un nœud
  désélectionne tout son sous-arbre ; on ne peut pas re-cocher un
  descendant individuellement tant que son parent reste décoché — il
  faut recocher le parent d'abord. Simplification volontaire pour ce
  squelette, à faire évoluer si un usage réel le justifie.
- **Sélection géographique (dessin de zone sur la carte)** : pas encore
  implémentée. Le même principe de corbeille pourrait s'étendre à une
  sélection spatiale dans une prochaine itération.
- **Colonne de synthèse minimale** : affiche les propriétés brutes de
  l'élément sélectionné, sans mise en forme métier — à enrichir une fois
  les vraies sources (tickets, docs, emails) branchées.

## IPAM, Optick, TTS-GU, Zenoss et OwnCloud — onglets de visualisation en lecture seule

Cinq onglets du frontend principal, même principe : **racines
indépendantes** à gauche, **arbre radial** au centre, **fiche JSON**
du nœud sélectionné à droite — construits à partir de bases MySQL
d'applications **existantes**, externes à ce projet.

- **IPAM** (`ipam/`) — phpipam : sections (racines) → subnets
  (nichés), enrichis du nombre d'IP utilisées et des noms VLAN/VRF.
- **Optick** (`optick/`) — outil de tickets interne : familles de
  catégories (racines) → catégories, enrichies du nombre de tickets.
- **TTS-GU** (`tts-gu/`) — clone d'optick3 au schéma divergent (plus
  de notion de famille) : domaines (racines) → catégories, une
  catégorie taguée de plusieurs domaines apparaissant sous chacun.
- **Zenoss** (`zenoss/`) — base "events" : aucune clé de hiérarchie en
  base, l'arbre est reconstruit en découpant les chemins de
  classification d'événements (`eventClass`, ex. `/App/Fail/Http`).
- **OwnCloud** (`owncloud/`) — seul module à ne PAS charger un arbre
  complet (table à ~2,5M lignes) : dépliage à la demande, un nœud +
  ses enfants directs par appel, état accumulé côté client.

**IPAM, en plus** : une case "actifs seulement" élague l'arbre pour
ne garder que les subnets réellement en ligne (`subnets.state`),
contrairement aux autres filtres qui estompent sans retirer. Un petit
panneau sur le premier onglet (Supervision SI) appelle `ipam-api`
**directement depuis le navigateur** (aucun import, aucun
intermédiaire) pour afficher un résumé global.

Garantie commune de lecture seule (trois niveaux, détaillés dans le
README de chaque module) : aucune route d'écriture dans le code, un
garde-fou qui refuse toute requête SQL non-`SELECT`, et surtout un
compte MySQL dédié à créer côté serveur avec uniquement le privilège
`SELECT` (exemple de `GRANT` fourni dans chaque README). Variables
`.env` : `IPAM_DB_*` / `OPTICK_DB_*` / `TTSGU_DB_*` / `ZENOSS_DB_*` /
`OWNCLOUD_DB_*`.

**Fenêtre temporelle** : un sélecteur à deux poignées indépendantes
(curseur générique `TimelineRangeSlider.jsx`, débattu via
`useDebouncedValue`) filtre l'arbre par date, avec deux architectures
selon la nature de la donnée — détaillées dans le README de chaque
module :
- **IPAM et OwnCloud** — filtrage **côté client** (les nœuds sont
  individuellement datés : `editDate`, `mtime`).
- **Optick, TTS-GU et Zenoss** — **recalcul côté serveur** (les nœuds
  sont des agrégats de tickets/événements, pas des entités
  individuellement datées).

```bash
./scripts/run.sh up -d --build ipam-api optick-api
```

## Fusion IP/MAC (`FusionApp.jsx`)

Nouvel onglet — **tableau** de corrélation par adresse IP entre les
sources qui en connaissent (actuellement IPAM et Zenoss ; Cacti
s'ajoutera naturellement une fois construit). Volontairement une
table et non un arbre radial : une corrélation entre sources
indépendantes n'est pas une hiérarchie, un tableau filtrable/triable
s'y prête mieux.

Aucun nouveau service : le frontend appelle **directement**
`ipam-api` (`/ip_list`) et `zenoss-api` (`/ip_list`, nouveau — voir
`zenoss/README.md` pour l'exception délibérée et scopée à ce seul
endpoint sur des colonnes jusqu'ici jamais lues) et fusionne les deux
côté navigateur, par égalité d'IP — même principe que le panneau
d'aperçu IPAM sur l'onglet Supervision : pas d'import, pas de service
intermédiaire, pas de copie de données.

Le MAC ne vient que d'IPAM (Zenoss n'en stocke pas dans ce schéma) ;
une case permet de ne garder que les adresses vues par plusieurs
sources à la fois.

### Géolocalisation IP généralisée

Bouton « 🌍 Géolocaliser ces IP » sur cet onglet — généralise le
système de géolocalisation déjà construit pour les équipements
pixel-grid (`geolocations`, dans `pixel-grid/api/app.py`) plutôt que
d'en reconstruire un : sa clé (`localisation`) a toujours été un
texte libre, jamais structurellement liée à pixel-grid — une IP n'est
qu'une autre sorte de clé, aucun changement de schéma.

Deux mécanismes bien distincts, jamais confondus :
- **IP privées** (la quasi-totalité en pratique — RFC1918, infra
  interne) : pas de position géographique publique par définition, ce
  n'est pas une limite technique contournable. Entrée ajoutée "en
  attente", à placer à la main dans l'onglet Géolocalisation, exactement
  comme pour un équipement pixel-grid aujourd'hui.
- **IP publiques** (rares dans un contexte d'infra interne, mais
  possibles — VPN, DMZ) : résolution automatique via un service GeoIP
  externe (`GEOIP_PROVIDER_URL`, ip-api.com par défaut — gratuit, sans
  clé, 45 requêtes/minute, remplaçable).

Classification private/public en double, jamais mélangée : côté
serveur (Python, module standard `ipaddress`, IPv4 et IPv6 — c'est
elle qui décide réellement d'appeler ou non le service externe,
revérifiée juste avant l'appel réseau lui-même) et côté client (JS,
IPv4 seulement, purement informative pour l'affichage avant de lancer
une géolocalisation). Nouvel endpoint `POST
/geolocations/register_ips` sur pixel-grid-api : ne touche jamais une
entrée déjà connue, qu'elle soit manuelle ou déjà résolue.

### Filtres dédiés, géocodage par code postal, bouton carte

Deux champs de filtre supplémentaires dans la barre d'outils, en plus
de la recherche globale existante : un dédié à la colonne "Nom(s)
d'hôte", un dédié à "Alertes actives" (`rowMatchesHostname`/
`rowMatchesAlert` dans `fusionLib.js`) — se combinent en ET avec la
recherche globale et la case "vues par plusieurs sources".

Bouton "🏘️ Géocoder via code postal" — complète la géolocalisation IP
ci-dessus pour les lignes qui y échappent structurellement (IP
privées) : extrait un code postal à 5 chiffres du nom d'hôte (ex.
`BIO17-17300-ISLANDE-RB3011`), résout son centroïde de commune via
`GET /commune_centroid` (pixel-grid-api, voir `pixel-grid/README.md`),
écrit dans la même table `geolocations` partagée. Écriture en lot
sans confirmation par ligne — même précédent déjà établi par le
bouton "🌍 Géolocaliser ces IP" juste à côté, pas une nouvelle
philosophie.

Sur chaque position résolue (quelle que soit la méthode), un bouton
🗺️ recentre et zoome la carte de l'onglet Supervision SI. Mécanisme
cross-onglet : `App.jsx` porte l'état `mapFocusRequest`, `FusionApp`
le pose via `onGoToMap` (qui bascule aussi l'onglet actif), `MapPanel`
le consomme au montage suivant via un composant `useMap()` dédié
(`MapFocusHandler`) puis prévient l'appelant pour vider la demande —
même famille de pattern que le réticule de sélection déjà en place
sur cette carte.

**Colonnes réglables** : visibilité, largeur, et une colonne toujours
accessible sans défilement — trois retouches liées à un même souci
remonté par la personne (capture d'écran à l'appui : la colonne
Position — pourtant déjà sticky à ce moment-là — restait hors du
cadre visible parce que la barre de défilement horizontale, bien que
fonctionnelle, était peu visible sur son système).

- **Scrollbar toujours visible et stylée** (`.fusion-table-wrap`,
  `scrollbar-width: auto` + `::-webkit-scrollbar` explicite) — au lieu
  de dépendre du réglage "masquer jusqu'au survol" de l'OS, souvent
  activé par défaut et peu découvrable.
- **"⚙ Colonnes"** (bouton dans la barre d'outils) : une case à
  cocher par colonne pour la masquer/réafficher — `FUSION_COLUMNS`
  (liste centrale nom/libellé/largeur par défaut dans `fusionLib.js`)
  est l'unique source de vérité ; en-tête, cellules et panneau de
  colonnes en dérivent tous les trois, jamais une liste dupliquée qui
  pourrait diverger. `renderCell(row, key)` centralise également le
  rendu de chaque colonne — ajouter/retirer une colonne à l'avenir se
  fait à un seul endroit.
- **Largeur ajustable** par glisser sur une poignée en bord de
  colonne (`table-layout: fixed` + `<colgroup>`, seule façon fiable de
  contrôler des largeurs de colonnes indépendamment en HTML). Calcul
  de la nouvelle largeur isolé dans une fonction pure
  (`computeResizedWidth`, bornée 60–600px) — 20 tests Node au total
  sur `fusionLib.js` pour cette partie (bornage, bascule de
  visibilité, préservation de l'ordre des colonnes visibles).
- La colonne actuellement en **dernière position visible** (Position,
  sauf si masquée) reste collée à droite — recalculé en JS selon ce
  qui est réellement affiché (`visibleColumns`), pas un simple
  `:last-child` CSS qui se tromperait dès qu'une colonne est masquée.

**Bug réel trouvé et corrigé au passage** (capture d'écran de cet
onglet à l'appui) : la colonne Subnet affichait un entier brut
(`175374352/28`) au lieu d'une notation pointée (`10.116.0.16/28`) —
voir `ipam/README.md`, section Dépannage, pour le détail complet
(`subnets.subnet` stocké en décimal côté phpipam, jamais reconverti).

## "Figer cette vue comme source" — généralisé aux 5 modules

Chaque onglet de visualisation (IPAM, Optick, TTS-GU, Zenoss,
OwnCloud) a désormais un bouton « 📸 Figer cette vue comme source » :
il réduit l'arbre affiché à ce que les filtres actifs retiennent
(recherche texte + fenêtre temporelle + spécificités du module,
ex. "actifs seulement" pour IPAM) et l'enregistre comme une **photo
figée à l'instant T** — une source JSON ordinaire de l'onglet
Supervision, immédiatement utilisable dans la corbeille, l'arbre JSON
et l'arbre radial existants, exactement comme un fichier importé à la
main (même mécanisme : `POST /ingest/<source>`).

Toujours une photo, jamais une vue vivante qui se remettrait à jour —
choix délibéré (voir la discussion dans `ipam/README.md`). Pour
OwnCloud (dépliage à la demande), la photo ne porte que sur ce qui a
déjà été exploré, jamais sur des données non encore chargées.

Pièces partagées entre les 5 modules plutôt que dupliquées :
`frontend/src/lib/treeFreeze.js` (réduction de l'arbre, nommage
unique horodaté) et `frontend/src/components/FreezeSnapshotButton.jsx`
(le bouton lui-même) — un seul endroit à faire évoluer.

## "Charger comme source" depuis la carte externe (IPAM)

La carte IPAM du panneau de gauche (onglet Supervision, section
"Sources externes") a un second bouton, distinct de la navigation
vers l'onglet : « 📥 Charger comme source ». Contrairement à « Figer
cette vue » (une racine à la fois, filtrée, depuis l'onglet IPAM
lui-même), celui-ci récupère **toutes** les racines indépendantes
d'IPAM et l'arbre complet de chacune, les combine en un seul JSON, et
l'enregistre — même mécanisme `POST /ingest`, toujours en appel
direct à `ipam-api` depuis le navigateur, aucun intermédiaire.

Différence de nommage assumée : nom **stable** (`ipam`, pas
d'horodatage) plutôt qu'une photo ponctuelle — recharger met à jour
la même source en place. Une racine dont l'arbre n'a pu être récupéré
(erreur réseau ponctuelle) reste présente dans le résultat avec son
erreur explicite, jamais silencieusement absente.

## Garde-fou différentiel sur `/ingest` (préparation du futur mode push)

Les données du projet restent aujourd'hui statiques, mises à jour par
import (manuel, ou le push périodique du `pipeline`, toutes les 30s
par défaut). Un futur mode où les services pousseraient directement
vers `/ingest` rendra le "temps réel" pertinent — préparé dès
maintenant par un garde-fou sur ce même endpoint, déjà actif
aujourd'hui (protège aussi l'usage manuel actuel : double-clic,
script qui boucle) :

- **Différentiel** : un contenu identique à la dernière écriture pour
  cette source n'est pas réécrit (`{"status": "unchanged"}`, 200) —
  pas de disque, pas de Memcached, pas d'horodatage bougé pour rien.
- **Anti-rafale** : un contenu changé mais arrivé trop tôt après la
  dernière écriture acceptée pour cette source est refusé
  (`{"status": "throttled", "retry_after_ms": N}`, HTTP 429) plutôt
  que d'empiler des écritures rapprochées — l'appelant sait combien de
  temps attendre avant de réessayer.

Seuil configurable (`DIFF_WATCHDOG_MIN_INTERVAL_MS`, 2000 ms par
défaut — trente fois sous l'intervalle du pipeline actuel, aucun
impact sur lui). État partagé entre les workers Gunicorn (2 par
défaut) via Memcached, jamais un simple dict en mémoire de processus
qui serait invisible d'un worker à l'autre ; dégradé pour toujours
laisser passer si Memcached est indisponible (mieux vaut un doublon
accepté qu'une donnée perdue pour un souci d'infra annexe).

**Ce qui n'est PAS construit** : aucun service ne pousse encore
réellement en continu — c'est le chantier annoncé pour plus tard, une
fois l'interface stabilisée. Le garde-fou est prêt à l'accueillir sans
rien changer côté `/ingest` le jour venu.

## Logs — onglet centralisé + bandeau pied de page (`LogsApp.jsx`/`LogFooter.jsx`)

Chacun des **9 services Flask** du projet (`api`, `pixel-grid-api`,
`tickets-api`, `ipam-api`, `optick-api`, `zenoss-api`, `tts-gu-api`,
`owncloud-api`, `cacti-api`) expose désormais `GET /logs` : un tampon
circulaire **en mémoire** (`LOG_BUFFER_SIZE`, 200 par défaut), qui
capture WARNING et plus grave (`LOG_CAPTURE_LEVEL`, configurable) —
pas les logs d'accès HTTP routine, qui noieraient le signal. Jamais
persisté sur disque : perdu au redémarrage du conteneur, attendu pour
un outil de diagnostic à chaud, pas un historique long terme.

**Hors périmètre délibéré** : `pipeline` et `pixel-grid-bridge` sont
des scripts de fond (boucle `while True`, pas de serveur HTTP) — pas
de `/logs` pour eux, leurs logs restent visibles via
`docker compose logs pipeline` / `docker compose logs pixel-grid-bridge`.
`tickets/portal` (frontend séparé pour demandeurs/techniciens) n'a pas
reçu le bandeau — outil de diagnostic interne, pas pertinent pour ce
public.

Côté frontend (`frontend/src/apps/logsApi.js` interroge les 9 en
parallèle, jamais bloqué par un service en panne — `logsLib.js` fait
la fusion/tri/priorisation, pure et testée) :
- **Onglet Logs** (`LogsApp.jsx`) — table complète, filtrable par
  service/niveau, pause du rafraîchissement (15s par défaut), signale
  les services injoignables sans masquer les autres.
- **Bandeau pied de page** (`LogFooter.jsx`), persistant sur tous les
  onglets — replié : 2 lignes, priorité aux ERROR/CRITICAL les plus
  récentes (sinon les plus récentes tout court) ; déplié (clic) :
  jusqu'à 30 entrées + lien direct vers l'onglet Logs complet. Une
  pastille rouge affiche le nombre d'erreurs/critiques actives sur la
  fenêtre chargée, visible même replié.

```bash
curl http://localhost:6108/logs?limit=10   # exemple : zenoss-api seul
```

## Géomatique — staging PostGIS, import/fusion shapefiles (`geo-import/`)

**En cours, pas terminé** — voir `geo-import/README.md` pour l'état
d'avancement complet et ce qui reste à construire (QGIS Server,
GeoServer, onglet de prévisualisation QGIS, câblage vers la carte
principale). Déjà livré et testé : base PostGIS de staging locale
(`geo-postgres`, décision actée avec la personne — pas de connexion à
une base externe), service `geo-import-api` (dépôt shapefile → import
`ogr2ogr` avec reprojection WGS84 automatique → outil de fusion de
couches), onglet **Dépôt shapefiles**.

## Recherche — contenu OwnCloud via Elasticsearch (`SearchApp.jsx`)

Nouveau service `owncloud-search-api` (port 6112) + onglet **Recherche** :
assistant de construction de requêtes contre l'Elasticsearch alimenté
par l'app ownCloud `search_elastic` (indexation Tika des PDF/Office,
externe à ce projet — connecteur à mettre en place côté personne).
Champs de recherche **jamais codés en dur** : découverts en direct sur
le mapping réel de l'index (`/mapping`). Traduction sécurisée d'une
spec structurée en DSL Elasticsearch côté serveur, jamais de requête
brute transmise depuis le frontend — voir
`owncloud/search-api/README.md` pour le détail complet (mise en place
du connecteur, contrainte de version Elasticsearch 5.6.x, sécurité du
rendu des extraits de contenu).

## SSO — Keycloak + LDAP (`keycloak/`)

Service `keycloak` (port 6180) avec realm **supervision-si** pré-peuplé
(4 rôles alignés sur le portail tickets, clients OIDC PKCE des trois
fronts, client d'audience pour les APIs) et **fédération LDAP
paramétrée entièrement dans `.env`** — voir `keycloak/README.md`.
Le realm est rendu depuis `.env` par `python3 keycloak/render.py`
(fait automatiquement par `scripts/run.sh`).

## Hub d'accès (`hub/`) — port 6174

Nouveau portail d'entrée séparé, **premier front du projet à
réellement consommer Keycloak** (les deux autres clients OIDC
existaient côté realm sans code applicatif branché dessus). Connexion
LDAP obligatoire, puis une carte par front déployé séparément
(Supervision SI, portail tickets). Sécurité honnête à connaître avant
de compter dessus : ce portail protège l'accès *au hub*, pas encore
les applications vers lesquelles il ouvre — voir `hub/README.md`
pour le détail complet et les pistes pour fermer cet écart plus tard.

## HTTPS — toute la plateforme, entrée unique, autorité de certification interne

Environnement sans accès internet/Let's Encrypt : `pki/` génère une
**CA interne** (une fois pour toutes, `pki/README.md` — avec les
procédures d'installation sur les postes clients, Windows/macOS/
Linux/Firefox, l'étape qui compte vraiment) et un certificat serveur
(régénéré à chaque lancement, aligné sur `HOST_IP` courant).

`tls-proxy/` (nginx, config générée depuis `.env`) termine le TLS et
route par **chemin** vers les 15 services de la plateforme, sur **un
seul port public** (`GATEWAY_PORT`, défaut 6443) — architecture
proposée par la personne en cours de session, actée : réduit la
surface exposée côté bordure réseau (Apache) à un seul port au lieu
de 15. Schéma : `/` → hub, `/app/` → Supervision SI, `/tickets/` →
portail tickets, `/auth/` → Keycloak, `/api/<nom>/` → chaque API —
voir `tls-proxy/README.md` pour le détail complet, et surtout sa
section sur la partie la plus fragile de ce changement (Vite `base`
+ HMR à travers le préfixe, `KC_HTTP_RELATIVE_PATH` — jamais vérifiés
en conditions réelles ici, faute de navigateur).

Automatique via `./scripts/run.sh` (CA/certificat/config nginx/realm
Keycloak tous régénérés avant chaque `docker compose`). Aucun des 15
services ne publie plus son port directement sur l'hôte — seul
`tls-proxy` le fait désormais, sur ce port unique.

**Apache (point d'entrée réseau existant, machine séparée à
plusieurs pattes)** : `apache/` génère sa config — **un seul
`VirtualHost`** désormais (devenu trivial avec l'entrée unique), TLS
terminé par Apache lui-même, relais **en HTTPS** vers `tls-proxy`
(jamais en clair : Apache et la machine Docker communiquent à travers
un vrai réseau, pas une boucle locale) — voir `apache/README.md` pour
la checklist complète.

## Suivi des clés `.env` (`ENV_CHANGELOG.md`)

Pour fusionner rapidement un `.env` existant contre une nouvelle
livraison sans repasser par un diff complet à chaque fois — liste, du
plus récent au plus ancien, les clés ajoutées/modifiées à chaque
session qui touche `.env`, avec le pourquoi. `.env.example` reste la
référence exhaustive des valeurs par défaut.

## Publication (GitHub / Framagit)

Dépôt git initialisé, à pousser vers les deux forges — voir
`PUBLISHING.md` (identité des commits, création des dépôts vides,
`scripts/publish_remotes.sh`, licence à choisir). `.env` et le realm
rendu ne sont pas versionnés (secrets) ; `.env.example` sert de
référence.

## Tampon de logs partagé via Memcached (livraison #145)

Découvert en investigant une panne réelle du 01/09 : les 15 APIs +
`prefs-api` tournent TOUTES avec 2 workers Gunicorn (processus
séparés, mémoire NON partagée) -- or tout le mécanisme de logs
(`/logs`, `/hub-log`, `/push-log`, livraisons #139-#142) était un
simple tampon EN MÉMOIRE PAR PROCESSUS : une entrée capturée par un
worker restait invisible si la lecture suivante (un simple sondage du
gestionnaire de logs) atterrissait sur l'autre worker.

**Choix assumé** : les 2 workers restent à 2 (jamais réduits à 1) --
corrige la cause directement (l'absence de mémoire partagée) sans
sacrifier la concurrence. Implémenté via Memcached, déjà présent dans
le projet (8 des 15 backends l'utilisaient déjà pour du cache de
requêtes) -- nouveau module central `shared/log_buffer.py` (copié
dans chaque backend au build, même motif que
`shared/version_endpoint.py`), lecture-modification-écriture avec CAS
(compare-and-swap) -- jamais un read-modify-write naïf qui perdrait
des entrées sous écriture concurrente des deux workers, exactement le
scénario corrigé. `/push-log` (sources externes, #142) avait la même
faille jumelle (dictionnaire Python en mémoire) -- corrigée en même
temps plutôt que laissée derrière.

**Conséquence collatérale** : 9 des 15 backends (`ipam`, `zenoss`,
`optick`, `owncloud`, `cacti`, `tts-gu`, `owncloud-search`,
`pixel-grid`, `geo-import`) avaient un contexte de build Docker
cantonné à leur propre dossier, sans accès à `shared/` -- élargi à la
racine du projet (`context: .`) pour permettre
`COPY shared/log_buffer.py .`, même motif que les backends qui
utilisaient déjà `version_endpoint.py`.

Vérifié réellement, service par service (14 sur 15, `vault-api`
bloqué par un bug préexistant sans rapport, voir vault/README.md) :
un vrai warning émis via le logger de l'application, lu via `/logs`,
ET confirmé visible depuis une connexion Memcached INDÉPENDANTE
simulant un second worker Gunicorn -- la preuve directe que le
problème d'origine est résolu. Le cœur de la logique CAS
(`shared/log_buffer.py`) testé avec une collision RÉELLEMENT simulée
entre deux écritures concurrentes : les deux entrées survivent,
aucune n'écrase l'autre. `pymemcache` et un vrai serveur Memcached ne
sont pas installables dans cet environnement (réseau restreint) --
un stub fonctionnel a été construit pour ces tests (un vrai petit
serveur en mémoire, pas un mock qui ne fait rien), mais le
comportement contre un VRAI Memcached en conditions réelles reste
**non vérifié ici**.

## Logs de toutes sortes — étape 2/4 : sources URL (livraison #147)

Backlog `BACKLOG.md` #3, ordre choisi par la personne (push d'abord
en #142, URL ensuite). Nouvelle table `log_sources` dans `prefs-api`
(SQLite), UNIFIÉE pour les 4 types à venir (`url` fonctionnel,
`file`/`rsyslog` acceptés par le CRUD mais encore inertes -- évite
une migration à chaque étape). CRUD complet
(`GET`/`POST`/`PUT`/`DELETE /log-sources`), sans interface
d'administration pour l'instant -- à configurer via l'API directement
(curl ou équivalent) ; une interface est le prolongement naturel,
pas encore construite.

Sondage en tâche de fond (`prefs-api/log_sources_poller.py`, thread
démon démarré au chargement du module) -- relit `log_sources` à
chaque cycle (10s), respecte l'`interval_seconds` propre à chaque
source. Formats `jsonl` (une entrée JSON par ligne) et `plain` (une
ligne = un message, niveau déduit par mots-clés **français ET
anglais** -- ERROR/ERREUR/CRITICAL/CRITIQUE → ERROR,
WARN/ATTENTION/AVERTISSEMENT → WARNING, sinon INFO ; choix assumé,
pas confirmé avec la personne). Écrit dans le MÊME tampon Memcached
partagé que `/push-log` (`shared/log_buffer.py`, #145) et
s'enregistre dans le MÊME registre de sources -- le hub affiche donc
les sources URL automatiquement, sans AUCUNE modification côté
frontend.

Tourne dans chaque worker Gunicorn (2 workers) -- double sondage
possible de la même URL si les deux workers sont dus au même moment,
choix assumé (le tampon partagé absorbe ça sans incohérence de
lecture, juste une entrée occasionnellement dupliquée).

Vérifié réellement, de bout en bout : CRUD testé (20 cas, dont
défensifs), détection de niveau bilingue testée (découverte en cours
de test que "ERREUR" français ne contient pas "ERROR" anglais --
corrigé, pas seulement le test), et un VRAI thread de fond démarré,
avec un vrai cycle de sondage attendu (12s), confirmant qu'un échec
réseau réel (domaine `.invalid`, RFC 2606) est correctement journalisé
sans jamais planter le thread.

## Logs de toutes sortes — étape 3/4 : sources fichier plat (livraison #176)

Backlog `BACKLOG.md` #3, construite en autonomie pendant une absence
de la personne. Le CRUD `log_sources` acceptait déjà `type="file"`
depuis #147 (schéma anticipé, resté inerte) -- validation réelle
ajoutée (`config.path` RELATIF, `interval_seconds`, jamais un chemin
absolu ni une traversée `..`, refusé dès la création).

Nouveau `prefs-api/file_source_poller.py` -- lecture INCRÉMENTALE
(position suivie), **coordonnée via Memcached** (pas un dict en
mémoire par processus comme le suivi des sources URL) : une lecture
de fichier est intrinsèquement à état, contrairement à un GET URL --
avec 2 workers Gunicorn suivant chacun sa PROPRE position, chaque
ligne nouvelle serait lue en double SYSTÉMATIQUEMENT, pas seulement
occasionnellement comme pour les URL. N'avance la position lue que
jusqu'à la dernière ligne COMPLÈTE (dernier `\n` du chunk) -- une
ligne encore en cours d'écriture est relue en entier au cycle
suivant, jamais coupée en deux dans le tampon de logs. Rotation
détectée (inode différent OU taille < position connue, cette
dernière condition couvrant aussi `logrotate` en mode
"copytruncate", qui garde le même inode mais vide le fichier) --
repart alors de zéro.

Chemins RESTREINTS à un répertoire racine monté EXPLICITEMENT en
lecture seule (`LOG_FILES_HOST_DIR` dans `.env`, repli
`./prefs-api/log-files/`) -- même motif que `SSH_TUNNELS_KEYS_DIR`
(#159). Résolution via `os.path.realpath` sur le chemin ET la base
avant comparaison -- résout aussi les liens symboliques, un lien
pointant hors du répertoire autorisé est refusé comme n'importe quel
autre chemin hors périmètre (utile pour suivre un vrai fichier
ailleurs sur l'hôte sans dupliquer son contenu).

Dispatch intégré au MÊME sondeur que les sources URL
(`log_sources_poller.poll_all_due_sources`, désormais générique par
`type`) plutôt qu'une boucle de fond séparée -- `poll_file_fn`/
`base_dir` injectés, jamais un import en dur (`file_source_poller.py`
reste optionnel, une source "file" reste silencieusement inerte si
le module ou `LOG_FILES_BASE_DIR` sont absents, jamais une
exception). Toujours SANS interface d'administration (comme les
sources URL) -- configuration via l'API directement.

Vérifié réellement : lecture incrémentale testée sur un VRAI fichier
disque (13 cas) -- ligne complète vs incomplète jamais coupée,
rotation ET copytruncate, traversée de chemin refusée y compris via
un LIEN SYMBOLIQUE pointant hors du répertoire autorisé. Dispatch
testé (source URL non régressée, source fichier bien sondée, aucune
exception si le module fichier est indisponible). CRUD `/log-sources`
retesté de bout en bout pour `type="file"` (création, validation,
listing, mise à jour).

## Logs de toutes sortes — étape 4/4 : rsyslog distant/UDP (livraison #177)

Backlog `BACKLOG.md` #3, **DERNIÈRE étape** de l'initiative --
construite en autonomie. Nouveau service SÉPARÉ `rsyslog-listener/`
(pas une extension de `prefs-api` comme les étapes précédentes) :
syslog est un protocole réseau UDP **brut**, jamais HTTP -- ne peut
pas transiter par `tls-proxy` comme tout le reste de ce projet. Port
UDP exposé DIRECTEMENT sur l'hôte (`RSYSLOG_LISTENER_PORT`, `.env`)
-- une machine distante y pousse ses logs directement.

`rsyslog-listener/syslog_parser.py` -- logique PURE, distingue RFC
3164 (BSD, ancien) de RFC 5424 (moderne) via le marqueur de VERSION
("1") juste après le PRI. Sévérité syslog (0-7) mappée sur les 3
niveaux déjà en place ailleurs (0-3→ERROR, 4→WARNING, 5-7→INFO). Une
ligne hors des deux formats reconnus retombe en "brut", jamais
perdue. UN SEUL worker Gunicorn (`rsyslog-listener/Dockerfile`) --
même raisonnement que `ssh-tunnels-api` (#159) : un port UDP ne peut
être *bound* que par un seul processus.

Même tampon/registre Memcached partagés que les 3 étapes précédentes
(`shared/log_buffer.py`, #145) -- le hub affiche cette source
automatiquement, aucune modification frontend (juste une entrée
ajoutée à `LOG_SERVICES`, `hub/src/logsLib.js`, pour les logs
INTERNES du service lui-même, distincts du flux syslog relayé).
Enregistrement de la source THROTTLÉ (5 min, pas à chaque paquet).
Détail complet dans `rsyslog-listener/README.md`.

Vérifié réellement : parseur testé contre les exemples CANONIQUES
des deux RFC (17 cas, dont sévérités limites, tag avec PID, vrai
caractère BOM distinct du texte littéral "BOM" de l'exemple RFC
5424, ligne malformée). `listener.py` testé contre un VRAI socket UDP
local (thread réel, paquets envoyés depuis un client séparé).
`app.py` testé de bout en bout avec le VRAI thread démarré au
chargement du module -- un paquet UDP réel envoyé depuis l'extérieur
du processus Flask confirmé visible dans `/logs` ET dans le tampon
partagé ET le registre de sources.

**Initiative "logs de toutes sortes" TERMINÉE, 4/4 étapes livrées**
(push #142, URL #147, fichier plat #176, rsyslog/UDP #177). **Non
vérifié dans cet environnement** : contre un vrai serveur
rsyslog/syslog-ng distant (réseau restreint ici) -- à tester en
priorité une fois déployé.
