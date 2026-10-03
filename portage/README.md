# Portage PHP → Python (module du hub, livraison #650)

Interface de création d'un **projet de portage** d'une application PHP du parc : fiche (nom, type monolithe
ou Fat-Free, charset, préfixe de tables, compte de test), import du **code** (archive zip/tgz) et des **données**
(dump SQL chargé dans la MariaDB dédiée `portage-db`), puis exécution des étapes de l'IA de portage et revue de ses
rapports : PORT_SPEC avec sa colonne « décision » éditable (porter / simplifier / différer / abandonner, conservée
entre deux exécutions et appliquée à la génération des écrans : les unités mortes ou différées répondent 410),
schéma mesuré, fumée du port généré, journal, archive du port.

## Décisions

- **L'IA de portage (`portage-kit`) est un projet git indépendant, jamais copié ici.** `portage-api` la monte en
  lecture seule (`PORTAGE_KIT_DIR`, défaut `./portage/kit`, ignoré par git) et l'installe au démarrage. Sans ce
  volume, l'API démarre, la création et les imports fonctionnent, `/run` répond 503 avec le message à afficher.
  Mise en place : `cd ~/SRC/data2/tickets/supervision-si && git clone <dépôt portage-kit> portage/kit`.
- Les applications portées et leurs données **ne sont pas dans ce dépôt** non plus : `portage/data/` est ignoré.
- `portage-db` n'est joignable que depuis le réseau Docker ; une base `port_<projet>` par projet, recréée à chaque
  chargement de dump ; supprimée avec le projet.
- Une seule exécution à la fois par projet, dans un thread de `portage-api` (`gunicorn --workers 1`).
- L'anonymisation reste une étape explicite du kit, jamais automatique.

## API (`/api/portage/`)

`GET/POST /projects`, `GET/PUT/DELETE /projects/<slug>`, `POST /projects/<slug>/code` (multipart `file`),
`POST /projects/<slug>/dump` (multipart `file`, chargé aussitôt sauf `load=0`), `POST /projects/<slug>/load-dump`,
`POST /projects/<slug>/run` `{steps:[inventory schema scaffold routes install migrate smoke]}` (202, suivi par
`GET /projects/<slug>` : `run_status`, `log_tail`), `GET /projects/<slug>/report/<port_spec|schema|smoke|log|yml|inventory|schema_graph>`,
`GET/PUT /projects/<slug>/decisions`, `GET /projects/<slug>/archive` (zip du port généré + rapports).

## Vérifié / non vérifié

- `portage/api/test_portage.py` (app.test_client) : fiche, archive avec dossier racine unique remonté, détection
  Fat-Free, yml produit, refus (slug en double, archive avec `../`, kit absent, décision inconnue), décisions
  aller-retour, suppression. Chaîne complète (`inventory → smoke`) validée avec le vrai kit et une vraie MariaDB
  sur l'application d'exemple du kit (hors de ce dépôt).
- Front : `hub/tests/portageLib.test.mjs` (4 tests), syntaxe `@babel/parser`. Pas de rendu navigateur vérifié
  (`npm run build` impossible depuis le shell).
- Non vérifié : build de l'image `portage/api/Dockerfile`, nginx (`client_max_body_size 2G` déjà en place).
