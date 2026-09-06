# cacti-api — pont lecture seule vers une base Cacti existante

Comme `owncloud-api`/`optick-api`/`zenoss-api`/`ipam-api` : expose en
LECTURE SEULE la base MySQL d'une application Cacti EXISTANTE
(externe à ce projet, jamais créée ni gérée par lui) pour alimenter
un onglet du frontend "Supervision SI". Mêmes trois niveaux de
défense que les autres bridges MySQL de ce projet (utilisateur
MySQL en lecture seule, `run_select()` qui refuse tout ce qui n'est
pas un SELECT, colonnes explicitement choisies plutôt que `SELECT *`)
-- voir `ipam/README.md` pour le détail complet de ces trois niveaux,
jamais reproduit ailleurs par souci de brièveté.

## Historique -- backend prêt depuis longtemps, jamais relié à une interface

Ce module a été construit AVANT d'avoir son propre onglet frontend --
son propre docstring (`cacti/api/app.py`) dit explicitement "pour
alimenter l'onglet Cacti du frontend", mais cet onglet n'a été
construit qu'en **livraison #362**, découvert en vérifiant
systématiquement quels services API du projet n'avaient AUCUN
consommateur frontend évident (même démarche que la découverte
OwnCloud côté hub, livraison #354). Aucun autre README n'existait
pour ce module jusqu'à ce document -- inhabituel pour ce projet, où
chaque module a normalement le sien dès sa création.

## Particularité du schéma : encodage `order_key`

Version de Cacti visée ici est ANCIENNE (~ère 0.8.x -- confirmé par
le commentaire d'origine du code : `MySQL 5.0.32-Debian_7etch12`).
`graph_tree_items` N'A PAS de colonne `parent` (ajoutée dans des
versions plus récentes de Cacti) -- la hiérarchie est encodée dans
`order_key`, une chaîne découpée en segments de 3 chiffres, un
segment par niveau de profondeur : `"001003003001000...0"` = position
1 à la racine, puis 3e enfant, puis 3e enfant, puis 1er enfant (4
niveaux, les segments `"000"` de fin étant retirés). Confirmé par des
exports réels de la communauté Cacti, jamais deviné.

`parse_order_key()` est DÉFENSIF : une valeur mal formée (longueur
non multiple de 3, caractères non numériques, chemin dupliqué, parent
introuvable) ne fait jamais planter la construction de l'arbre --
l'item concerné devient simplement enfant direct de la racine de son
arbre plutôt que d'être perdu silencieusement.

## Hôtes et graphes -- une jointure, jamais des items d'arbre séparés

Un item d'arbre de type `host` n'a pas ses graphes stockés comme
items d'arbre séparés -- Cacti les affiche dynamiquement à partir de
`graph_local` au moment du rendu. Reproduit ici par une jointure
séparée (`fetch_graphs_by_host`), batchée en une seule requête (pas
de N+1 par host), puis attachée comme enfants du nœud `host`
correspondant AVANT de renvoyer l'arbre -- le frontend n'a donc
JAMAIS besoin d'un second appel pour voir les graphes d'un hôte,
contrairement à `owncloud-api` où les enfants se chargent par niveau.

Quatre types de nœuds au total : `tree` (racine), `header` (dossier
pur), `host` (équipement), `graph` (graphe, qu'il soit placé
directement dans l'arbre ou rattaché dynamiquement à un hôte).

## Colonnes jamais lues

`snmp_community`, `snmp_password`, `snmp_auth_protocol`,
`snmp_priv_passphrase`, `snmp_context` sur `host` -- identifiants
d'authentification SNMP, jamais exposés par ce bridge, même en
lecture seule.

## Routes

```
GET /roots
GET /tree/<root_id>
GET /health
GET /logs
```

`/roots` : racines indépendantes (les `graph_tree` eux-mêmes),
`{id, name, description, childSectionCount, subnetCount}` -- panneau
de gauche du frontend. `/tree/<root_id>` : arbre COMPLET enraciné à
cette racine en un seul appel -- jamais de chargement paresseux par
niveau à orchestrer côté frontend, contrairement à `owncloud-api`.
Les deux routes sont mises en cache (`CACTI_CACHE_TTL`, défaut 60s).

## Variables `.env`

`CACTI_DB_HOST`/`_PORT`/`_NAME`/`_USER`/`_PASSWORD`/`_SSL`/
`_CHARSET` -- connexion MySQL, vides par défaut (module inactif tant
que non configuré, comme tous les bridges de ce projet).
`CACTI_CACHE_TTL` (défaut 60s).

## Intégration frontend (livraison #362)

`frontend/src/apps/cactiApi.js` (client), `CactiApp.jsx` (vue),
`frontend/src/components/CactiJsonPanel.jsx` (fiche JSON du nœud
sélectionné) -- onglet "Cacti" dans `TopNav.jsx`.

**Arbre SIMPLE (liste imbriquée dépliable), pas de visualisation
radiale** contrairement à `OptickApp`/`OwncloudApp`
(`OptickRadialTree`/`OwncloudRadialTree`) -- choix délibéré : puisque
`/tree/<root_id>` renvoie déjà tout l'arbre en un seul appel (pas de
chargement paresseux à orchestrer), une liste dépliable suffit à
naviguer dossiers/hôtes/graphes sans le coût de développement d'un
rendu radial complet. Réutilise directement les utilitaires
GÉNÉRIQUES d'`optickLib.js` (`normalizeText`/`findPathToNode`/
`computeRelevantIds`) après avoir vérifié qu'ils ne présument rien de
spécifique à Optick (`raw.domainLabels`, absent des nœuds Cacti, est
lu derrière une garde `Array.isArray(...)` -- gracieusement ignoré).
`CactiJsonPanel.jsx` réutilise également les classes CSS
`optick-json-*` existantes plutôt que d'en dupliquer, avec 4 couleurs
de badge ajoutées pour les types `tree`/`header`/`host`/`graph`.

Nouvelle variable `VITE_CACTI_API_BASE_URL` (`docker-compose.yml`,
service `frontend`) -- même motif que les autres `VITE_*_API_BASE_URL`.

**Vérifié réellement** : syntaxe de tous les fichiers touchés
(`tsc --jsx`), `cactiApi.js` testé en profondeur avec `fetch` simulé
(racines, arbre imbriqué avec hôte+graphe enfant, gestion d'erreur
réseau). **Non vérifié dans cet environnement** : rendu visuel réel
(aucun navigateur ici), et surtout aucune base Cacti réelle
disponible pour confirmer l'algorithme `order_key` contre de vraies
données au-delà des exports communautaires déjà cités.
