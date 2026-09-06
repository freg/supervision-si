# schema-analyzer — analyse de schémas hérités

Livraison #151-#152, backlog `BACKLOG.md` #5 : "accès et migration/
interfaçage avec de vieilles bases/applis tickets". Décision
d'architecture prise avec la personne **avant** de coder : nouveau
module dédié (onglet + API), pas plaqué sur `dba` ni sur `tickets`.

## Ce que couvre CETTE livraison

**#151 — le "cœur technique" (diagnostic, lecture seule)** :
- **Introspection de schéma** via `dba-api` (voir "Architecture
  d'accès" ci-dessous) -- tables, colonnes, clés primaires.
- **Détection de relations par le NOM des champs**
  (`relation_detector.py`) -- suffixe `_id`/`Id`/`ID` + correspondance
  avec un nom de table (singulier ou pluriel simple).
- **Détection de colonnes-listes** (`list_detector.py`) -- cas
  explicitement signalé par la personne : un champ TEXTE utilisé
  comme liste d'identifiants (ex. `sites: "1,2,5"`), invisible dans le
  TYPE de colonne, détecté en échantillonnant les VALEURS réelles.
- `POST /analyze` -- `{"connection_id": int, "database": str
  (optionnel), "sample_size": int (optionnel, défaut 20)}`. Renvoie
  le schéma, les relations proposées, et les colonnes-listes
  détectées (avec une table cible devinée si possible). **Diagnostic
  FRAIS à chaque appel, rien de persisté.**

**#152 — l'éditeur de relations (persistance + validation manuelle)** :
- Nouvelle table SQLite `relations` (`relations_store.py`, même motif
  que `dba-api`/`prefs-api`) -- chaque relation a un `status`
  (`proposed`/`confirmed`/`rejected`) et une `source`
  (`auto`/`manual`), rattachée à un `(connection_id, database)`
  précis.
- `POST /relations/import-proposals` -- relance l'analyse (même
  logique que `/analyze`) et ENREGISTRE chaque proposition
  (`status="proposed"`, `source="auto"`) -- le PONT explicite entre
  diagnostic et éditeur, jamais automatique. Les relations DÉJÀ
  connues (même rejetées/confirmées entre-temps) ne sont **jamais
  écrasées** par un réimport -- **SIGNALÉ explicitement dans la
  réponse** : `{"imported": [...], "skipped": [...]}`, chaque élément
  de `skipped` porte `existing_id` et `existing_status` (la relation
  qui a bloqué l'import, avec son statut ACTUEL) -- demandé
  explicitement par la personne après la livraison initiale de cet
  endpoint, jamais un simple delta de compteur à déduire soi-même.
- `GET /relations?connection_id=X&database=Y` -- liste toutes les
  relations (proposées, confirmées, rejetées) pour validation.
- `POST /relations` -- création MANUELLE, `status="confirmed"` par
  défaut (une personne qui la saisit directement EST la validation).
- `PUT /relations/<id>` -- mise à jour PARTIELLE, sert aussi bien à
  CORRIGER (colonnes/table) qu'à VALIDER/REJETER (`status`).
- `DELETE /relations/<id>`.

**#154 — export du graphe relationnel (JSON + XML)** :
- `GET /relations/graph?connection_id=X&database=Y&format=json|xml`
  (défaut `json`) -- exporte les tables (noeuds) + les relations
  **CONFIRMÉES uniquement** (arêtes, `graph_export.py`) -- jamais les
  propositions `proposed`/`rejected`, qui ne représentent pas encore
  un schéma validé par une personne. XML produit avec
  `xml.etree.ElementTree` (bibliothèque standard, aucune dépendance
  externe), toujours un document bien formé (vérifié en le
  reparsant).

**Bug réel trouvé et corrigé** (question posée par la personne sur la
visibilité du signal, qui a mené à vérifier le mécanisme sous-jacent) :
la contrainte `UNIQUE` de la table `relations` inclut `database_name`
-- en SQL, NULL n'est JAMAIS égal à un autre NULL, donc pour une
connexion SANS base précise (`database=None`, ex. SQLite côté DBA),
la protection contre l'écrasement était **silencieusement inopérante**
: chaque réimport dupliquait indéfiniment la même relation au lieu
d'être bloqué. Corrigé en normalisant `None` vers une chaîne vide
AVANT stockage/comparaison (`_normalize_database`) -- une chaîne vide
EST comparable pour l'unicité, contrairement à NULL. Vérifié
explicitement (le cas n'était pas couvert par les tests initiaux de
#152).

**Ce module ne stocke/n'applique RIEN d'autre** -- les relations
persistées restent des PROPOSITIONS validées ou non, jamais utilisées
pour modifier quoi que ce soit dans la base analysée elle-même (ça
reste un futur volet du backlog : proposition d'interface d'édition
des données, interface de gestion des affectations).

## Architecture d'accès -- s'appuie sur `dba-api`, ne le duplique pas

`dba-api` expose déjà tout ce qu'il faut en HTTP
(`GET /connections/<id>/tables`, `.../columns`, `.../rows`) --
connexions MySQL/PostgreSQL/SQLite ET import de dump mysqldump déjà
gérés là-bas (`POST /connections/<id>/import-mysql-dump`). Ce module
ne fait donc **aucun accès direct à une base SGBD** : un simple
client HTTP (`schema_client.py`) vers `dba-api`, adresse interne au
réseau Docker (`DBA_API_BASE`, jamais via tls-proxy -- trafic
conteneur-à-conteneur, même motif que `KEYCLOAK_INTERNAL_URL` dans
`prefs-api`).

Conséquence pratique : pour analyser une vieille base tickets, il
faut d'abord créer une connexion dans **DBA** (onglet existant) --
connexion MySQL directe, ou import d'un dump -- puis passer son
`connection_id` à `POST /analyze` ou `POST /relations/import-proposals`
ici.

## Heuristiques -- volontairement simples, limites documentées

- **Relations classiques** (`detect_name_based_relations`) : suffixe
  `_id`/`Id`/`ID` retiré, puis correspondance avec un nom de table
  (variantes de pluriel anglais simple -- ajout/retrait d'un `s`,
  `y`↔`ies`). PAS une vraie lemmatisation -- les pluriels irréguliers
  anglais (ex. `person`/`people`) ni les conventions de nommage
  françaises (ex. `identifiant_client` sans suffixe `_id`) ne sont pas
  couverts. Deux niveaux de confiance : "haute" (correspondance exacte
  au singulier) et "moyenne" (a fallu passer par une variante de
  pluriel).
- **Colonnes-listes** (`detect_list_like_column`) : au moins 3 valeurs
  échantillonnées non vides, au moins 50% ressemblant à une liste
  d'entiers séparés par virgules (`"1,2,5"`) -- jamais un verdict sur
  un échantillon trop petit. Table cible devinée
  (`guess_referenced_table`) : suffixe `_ids`/`_id` retiré puis
  correspondance de pluriel comme ci-dessus, avec un REPLI sur le
  premier segment `snake_case` du nom complet (ex. `sites_concernes`
  → `sites`) -- volontairement permissif, un faux positif occasionnel
  coûte peu (rejeté à la validation manuelle), rater une vraie
  relation coûte plus (jamais proposée du tout). Confiance toujours
  "moyenne" pour une relation-liste importée (`import-proposals`) --
  intrinsèquement moins sûre qu'une clé étrangère classique.

Ces heuristiques ratent des cas réels et proposeront parfois à tort
-- c'est le rôle EXPLICITE de la validation manuelle (`PUT
/relations/<id>`, `status`) de corriger ce qu'elles ratent ou
inventent, jamais un schéma imposé sans confirmation humaine.

## Correctif #174 : message d'erreur muet sur les échecs dba-api

La personne a signalé un `502 Server Error: BAD GATEWAY for url:
http://dba-api:5000/connections/7/tables` -- message totalement
muet, exactement le MÊME piège que `ged/api/mayan_client.py` avant
#163 : `dba-api` renvoie DÉLIBÉRÉMENT un 502 avec le VRAI message du
connecteur externe dans le corps JSON (`{"error": str(exc)}`, voir
`dba/api/app.py`, `list_tables` et routes voisines -- 502 choisi
là-bas pour signaler "erreur du driver externe, pas de ce service"),
mais `raise_for_status()` seul dans `schema_client.py` ne donnait
QUE la ligne de statut générique, jamais ce corps.

Corrigé : `_raise_with_detail` remplace tous les `raise_for_status()`
isolés sur les appels dont l'échec est SURFACÉ à la personne
(`fetch_tables_and_columns` -- jamais sur l'échantillonnage de
lignes de `fetch_full_schema`, volontairement best-effort silencieux
au préalable, aucune raison d'en extraire le détail).

Vérifié en parallèle : les DEUX connecteurs SGBD (`dba/api/connectors/mysql.py`,
`postgres.py`) ont déjà `connect_timeout=5` correctement configuré --
un hôte distant injoignable échoue donc RAPIDEMENT (5s), le scénario
"worker Gunicorn bloqué puis tué, 502 nginx" est peu probable ici ;
le 502 rencontré était bien la réponse DÉLIBÉRÉE de `dba-api` avec
son détail avalé, pas un plantage réseau plus profond.

**Vérifié réellement** : testé contre un mock reproduisant EXACTEMENT
le comportement rapporté (502 + message du connecteur MySQL dans le
corps JSON) -- confirmé que le message réel (nom du serveur distant
compris) est désormais visible jusque dans la réponse HTTP de
`/analyze`. Non-régression du chemin de succès complet retestée (7
cas). `fetch_full_schema` (best-effort intentionnel) confirmé
inchangé.

## Vérifié réellement

Les trois modules purs (`relation_detector.py`, `list_detector.py`)
et le client HTTP (`schema_client.py`) sont testés directement, sans
mock de bas niveau -- `schema_client.py` contre un VRAI petit serveur
Flask simulant `dba-api` (thread réel, vraies requêtes HTTP), y
compris les cas d'erreur (connexion inconnue côté `dba-api`, `dba-api`
totalement injoignable). `relations_store.py` testé directement (CRUD,
isolation par connexion/base, doublons rejetés proprement, réimport
qui n'écrase JAMAIS une décision déjà prise -- y compris explicitement
avec `database=None`, le cas du bug corrigé ci-dessus). L'application
complète (`app.py`) testée de bout en bout de la même façon :
`/analyze`, tout le cycle `/relations` (import, liste, création
manuelle, mise à jour de statut, suppression, isolation), le signal
`skipped`/`existing_status` confirmé visible jusque dans la réponse
HTTP, et `GET /relations/graph` (JSON et XML, XML confirmé **bien
formé en le reparsant réellement**, pas seulement inspecté comme
texte -- et confirmé que seules les relations `confirmed` deviennent
des arêtes, jamais `proposed`/`rejected`), toujours contre le même
serveur Flask factice simulant `dba-api`.

**Non vérifié dans cet environnement** : contre un vrai `dba-api`
réel (pas le serveur Flask factice construit pour ce test) ni une
vraie vieille base tickets -- comme pour tout ce projet, pymysql/
psycopg2/pymemcache réels non installables ici (réseau restreint).

## Validation des relations contre les VRAIES données (livraison #241)

Backlog #5 -- demandé explicitement, en urgence, pendant un test réel
sur un dump : "à partir du schéma et des données (pour conforter la
relation)... relier un champ numérique ou set avec l'id d'une autre
table". Complète `relation_detector.py` (ne regarde QUE les noms de
colonnes) et `list_detector.py` (ne regarde QUE le MOTIF des valeurs,
jamais si elles correspondent à de VRAIES lignes) -- ici, une VRAIE
requête contre la base confirme (ou infirme) qu'une relation
candidate correspond à des données réelles.

Nouveau `relation_validator.py` -- **approche VOLONTAIREMENT
PORTABLE** (MySQL/PostgreSQL/SQLite sans code spécifique par
moteur) : plutôt que d'éclater une colonne-liste EN SQL (fonctions
différentes par moteur) ou de CASTer les types pour comparer
(syntaxe différente par moteur), tout l'éclatement et la comparaison
se font EN PYTHON après deux lectures SQL universelles (`SELECT
DISTINCT ... LIMIT N`). Fonctionne pour une relation classique
(un id par ligne) ET une colonne-liste ("1,2,5" -- réutilise le motif
déjà établi par `list_detector.py`).

Nouvelle route `POST /relations/validate` -- AUCUN effet de bord sur
les relations stockées, pure lecture : renvoie un taux de couverture
(% des valeurs échantillonnées qui correspondent à une ligne
existante de la table cible) + les valeurs SANS correspondance
(utile pour repérer une fausse piste -- une colonne qui ressemble à
une FK mais contient en réalité un code métier). La personne décide
ENSUITE, au vu du résultat, de confirmer/rejeter via les routes
`/relations` existantes -- jamais une confirmation automatique même
à 100% de couverture, même principe que `relation_detector.py`.

Côté hub (`SchemaAnalyzerView.jsx`) : bouton "🔍 Valider les données"
par relation dans l'éditeur, résultat affiché juste en dessous.

**Vérifié réellement** : logique de validation testée en profondeur
-- cas réel (couverture 100%), vrais mismatches détectés et
signalés, colonne-liste correctement éclatée, colonne entièrement
vide (jamais de division par zéro ni un taux trompeur), injection
SQL bloquée par la validation stricte des identifiants (jamais les
valeurs, elles, ne sont interpolées -- toujours comparées en
Python après lecture). Route testée de bout en bout. Structure JSX
revérifiée.

**Reste à faire, noté explicitement plutôt que présumé construit** :
la "vue JSON" avec valeurs RÉSOLUES (afficher, pour une ligne
donnée, la ligne LIÉE complète plutôt qu'un simple lien "aller à" --
voir l'onglet Données existant, #178) -- rejoint le chantier déjà
noté ci-dessous ("interface de gestion -- affectation des relations
sur les données elles-mêmes"), pas encore construit.

## Onglet hub (livraison #156)

`SchemaAnalyzerView.jsx` (bouton d'en-tête 🧬) -- interface complète
pour tout ce qui précède (analyse, éditeur de relations, export),
jusqu'ici accessible seulement via `curl`. Détail complet dans
`hub/README.md`.

## Chantiers pas commencés (voir `BACKLOG.md` #5 pour le détail complet)

- **Proposition d'interface d'édition des données** -- générée depuis
  le graphe relationnel validé.
- **Interface de gestion (affectation des relations)** -- distincte de
  l'éditeur de relations ci-dessus (celui-ci corrige le SCHÉMA
  déduit ; celle-ci gère l'AFFECTATION des relations sur les
  données elles-mêmes), à confirmer précisément avec la personne.

## Correctif : fichier manquant au déploiement (livraison #252)

`relation_validator.py` (validation des relations contre les vraies
données, #241) était importé par `app.py` mais jamais copié par le
`Dockerfile` -- oubli réel, confirmé par les vrais logs `gunicorn`
partagés par la personne (`ModuleNotFoundError`). Corrigé.

## Correctif : sélection graphique dans l'éditeur de relations (livraison #267)

Demandé explicitement : "je n'ai pas trouvé l'interface me
permettant graphiquement d'attribuer à un champ d'une table un lien
relationnel vers l'index d'une autre table".

En creusant : l'éditeur de relations existait déjà bel et bien
("Ajouter une relation manuellement", livré en #152), mais avec
seulement des champs TEXTE LIBRE -- la personne devait taper
exactement le nom de la table et de la colonne, sans rien de
"graphique" à proprement parler. D'où la confusion : le formulaire
existait, mais ne correspondait pas à ce qui était cherché.

Corrigé -- les quatre champs deviennent des menus déroulants,
peuplés directement depuis `analysis.tables` (déjà chargé côté état
du composant dès qu'une analyse a tourné, voir `handleAnalyze` --
AUCUN nouvel appel réseau nécessaire). La colonne cible affiche
explicitement "(clé primaire)" pour les colonnes concernées --
répond directement à "l'index d'une autre table" de la demande.
Choisir une nouvelle table réinitialise la colonne correspondante
(évite une colonne orpheline d'une AUTRE table restée sélectionnée
par erreur).

**Repli sur les champs texte libre conservé** si aucune analyse
n'est encore disponible (la personne arrive sur l'onglet "Relations"
sans avoir d'abord lancé "Analyser cette connexion") -- jamais un
formulaire bloqué en attendant, avec un message explicite invitant à
lancer l'analyse d'abord pour bénéficier des menus déroulants.

**Vérifié réellement** : logique de peuplement des menus testée en
isolation (tables triées, colonnes de la table sélectionnée
correctement extraites, réinitialisation de la colonne au
changement de table, aucune table sélectionnée -> liste vide sans
exception, absence d'analyse -> bascule confirmée sur le repli texte
libre). Structure JSX complète revérifiée.

## Branchement rights-api (livraison #319)

Suite de l'item 38 du backlog. `/analyze` et `/relations/validate`
sont EXPLICITEMENT documentées comme lecture pure (aucun effet de
bord, voir leurs docstrings respectifs) -- jamais gardées. Gardé
UNIQUEMENT sur les 4 routes qui PERSISTENT des relations (`create`/
`update`/`delete_relation` + `import-proposals` en masse) -- une
relation trafiquée pourrait faire croire à tort qu'une colonne
référence une autre, source d'erreurs de compréhension pour
quiconque s'appuie ensuite sur ce schéma déclaré.

OPT-IN via `SCHEMA_ANALYZER_RIGHTS_API_URL`, vide par défaut,
comportement inchangé tant qu'elle n'est pas configurée.

**Vérifié réellement** : comportement opt-in par défaut confirmé,
FAIL CLOSED si `rights-api` injoignable, 403 confirmé sur les 4
routes gardées avec un groupe non autorisé, `/analyze` et
`/relations/validate` confirmées TOUJOURS libres. Non-régression
complète reconfirmée.
