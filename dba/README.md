# DBA — Administration multi-SGBD

Nouveau front séparé (`dba/api/` + `dba/portal/`, entrée unique par
chemin comme le reste du projet : `/dba/` pour l'interface, `/api/dba/`
pour l'API). Connexions à des bases **externes à ce projet** —
PostgreSQL, MySQL, SQLite — pour lier et gérer l'écosystème DBA plus
large de la personne. Priorité annoncée : MySQL en premier.

## Distinct de l'onglet "Gestion base" existant — pas un remplacement

Le frontend Supervision SI a déjà un onglet "🗄️ Gestion base" qui édite
les tables DE CE PROJET, sur liste blanche stricte (voir
`frontend/src/apps/...`). Décidé explicitement avec la personne : ce
nouvel outil **s'ajoute à côté**, il ne le remplace pas — deux usages
différents :
- **Gestion base** (existant) : les bases internes à ce projet
  uniquement, liste blanche de tables/colonnes éditables, pensé pour
  la maintenance courante de ce projet précis.
- **DBA** (nouveau) : n'importe quelle base PostgreSQL/MySQL/SQLite
  déclarée par la personne, y compris des bases de PRODUCTION hors de
  ce projet — SQL libre, aucune liste blanche, gestion de schéma
  complète.

## Portée : parcourir + SQL libre (couvre la gestion de schéma)

Décidé avec la personne : "administration" va jusqu'à parcourir/éditer
des lignes **et** exécuter du SQL libre **et** gérer le schéma. Pas
de formulaires séparés pour CREATE/ALTER/DROP TABLE — un `CREATE
TABLE`, un `ALTER TABLE ADD COLUMN`, un `DROP TABLE` ne sont que des
instructions SQL : l'onglet "⌨️ SQL" les couvre nativement, sans
dupliquer la logique. L'onglet "📋 Parcourir" reste un raccourci de
confort pour le cas courant (voir les lignes d'une table), pas une
limite de ce que l'outil peut faire.

## Architecture des connecteurs — un fichier par moteur

`dba/api/connectors/` : `base.py` (interface commune, `DBConnector`),
`sqlite.py`, `postgres.py`, `mysql.py`, `__init__.py` (registre,
`get_connector()`). Ajouter un futur moteur (ex. un jour MSSQL) = un
nouveau fichier implémentant `DBConnector` + une ligne dans le
registre — jamais toucher à `app.py` lui-même pour ça.

**MySQL via PyMySQL**, pas `mysqlclient` — pur Python, aucune
dépendance de compilation côté image Docker (`mysqlclient` a besoin de
`libmariadb-dev` ou équivalent). Choix délibéré vu que MySQL est le
moteur prioritaire de cette demande : le garder simple à construire
compte plus que la performance marginale de l'autre option.

**Dialecte des identifiants** : guillemets doubles pour
postgres/sqlite (`"table"`), BACKTICKS pour MySQL (`` `table` ``) —
différence réelle entre moteurs, source d'erreur classique si copié
tel quel d'un connecteur à l'autre. Chaque connecteur a sa propre
fonction `_quote_ident()`, jamais partagée entre moteurs pour cette
raison précise.

## Décisions de sécurité, assumées et documentées

**Mots de passe de connexion stockés EN CLAIR** dans `dba.db` (la base
locale de cet outil, pas les bases administrées elles-mêmes) — même
posture que le reste du projet ("outil interne, réseau de confiance").
Jamais renvoyés dans une réponse JSON de listing (`_connection_row_public`
les retire systématiquement), mais présents en clair sur le disque. À
reconsidérer sérieusement si cet outil venait à sortir du réseau
interne, ou à gérer des bases de production sensibles au-delà d'un
usage interne de confiance.

**Aucune authentification sur ce front lui-même** — même posture que
Supervision SI (`frontend/`), pas de client OIDC Keycloak créé pour
`dba-portal`. La protection réelle est la **visibilité de la carte
hub**, volontairement plus stricte que les autres : groupe
`administrateurs` **seulement**, contrairement à "Administration
Keycloak" qui inclut aussi `techniciens` (voir `hub/src/lib.js`) —
cet outil stocke des identifiants et permet du SQL libre destructeur
sur des bases externes, une sensibilité différente d'une console
Keycloak majoritairement consultée en lecture par les techniciens.
**Rien n'empêche quelqu'un connaissant l'URL directe d'y accéder sans
passer par le hub** — même limite documentée partout ailleurs dans ce
projet (voir `hub/README.md`, "PAS garanti").

**Confirmation avant exécution** côté interface (pas backend) pour
toute requête SQL contenant `DROP`/`DELETE`/`TRUNCATE`/`ALTER TABLE`
— simple recherche de sous-chaîne, pas un vrai parseur SQL, ne
prétend pas tout détecter (ex. un `DELETE` dans une sous-requête d'un
`SELECT` déclencherait quand même la confirmation, un faux positif
sans gravité). Un filet de sécurité pour une frappe malheureuse, pas
une garantie.

**Plafond dur de 500 lignes** sur `/tables/<table>/rows` (`browse_rows`)
— jamais un dump complet accidentel d'une table de production
volumineuse depuis l'onglet Parcourir. Le SQL libre, lui, n'a pas ce
plafond — la personne y écrit explicitement sa requête, y compris son
propre `LIMIT` si besoin.

## Vérifié réellement vs. non vérifiable dans cet environnement

**33 tests Python, bout en bout réel** sur SQLite (le seul moteur
testable sans serveur externe dans cet environnement de
développement) : CRUD des connexions, mot de passe jamais renvoyé,
cycle complet test/databases/tables/columns/rows avec pagination,
SQL libre (SELECT, DDL via ALTER TABLE, INSERT), erreur SQL propre
(400, pas un 500), routage du registre de connecteurs.

**PostgreSQL et MySQL : code écrit et relu, syntaxe validée
(`py_compile`), mais AUCUNE connexion réelle testée** — aucun serveur
Postgres/MySQL externe accessible depuis cet environnement de
développement (pas de réseau sortant), et les bibliothèques
`psycopg2`/`PyMySQL` elles-mêmes n'ont pas pu être installées ici pour
vérifier leur API exacte. Le code suit fidèlement les API
documentées de ces bibliothèques (déjà utilisée ailleurs dans ce
projet pour psycopg2 — `tickets-postgres`, `geo-import` — mais
nouvelle pour PyMySQL), mais **le premier vrai test contre un serveur
MySQL/Postgres réel reste à faire par la personne**, pas supposé
fonctionner à l'aveugle.

## Import de sauvegarde mysqldump (`--all-databases`)

Bouton "📥 Importer un dump (mysqldump)" sur chaque connexion MySQL
(onglet Connexions). S'appuie sur le client `mysql` officiel plutôt
que de reparser le SQL nous-mêmes — un fichier de sauvegarde peut
contenir des points-virgules dans des littéraux de chaîne, des
commentaires, des changements de `DELIMITER` pour les routines
stockées... le client officiel gère déjà tout ça correctement, le
réinventer serait fragile pour un outil censé restaurer des données
réelles.

**Sécurité des identifiants** : jamais en argument de ligne de
commande (visible via `ps aux`), jamais en variable d'environnement
`MYSQL_PWD` (déconseillée par MySQL lui-même) — passés via
`--defaults-extra-file`, un fichier temporaire à permissions
restrictives (0600), supprimé immédiatement après usage, **y compris
en cas d'erreur**. Vérifié explicitement : le mot de passe
n'apparaît jamais dans les arguments de la commande construite.

**Voie synchrone** : la requête HTTP reste ouverte pendant toute la
durée de l'import (jusqu'à 30 minutes avant abandon) — pas de barre
de progression fine, pas de file d'attente asynchrone. Pour une très
grosse sauvegarde qui dépasserait ce délai, une vraie tâche de fond
serait nécessaire — pas construit dans cette première version, à
voir si le besoin se confirme.

**Non vérifié contre un vrai serveur MySQL** dans cet environnement
de développement — aucun client `mysql`, aucun serveur accessible,
pas de réseau sortant pour en installer un. La logique de gestion des
fichiers temporaires, permissions et nettoyage est testée
réellement (19 tests) ; l'invocation du client `mysql` lui-même ne
l'est que par simulation.

## Connexion(s) par défaut pré-configurées (`HUB_SGBD_*`)

Retour réel : d'abord envisagé comme un import direct des identifiants
IPAM/Optick/Zenoss/OwnCloud/Cacti déjà présents dans `.env` — écarté
par la personne (ces comptes sont réservés à leurs modules
respectifs). À la place : un bloc `.env` dédié
(`HUB_SGBD_MYSQL_*`/`HUB_SGBD_POSTGRES_*`), amorcé au démarrage de
`dba-api`.

**Idempotent, reconnu par un libellé réservé** ("MySQL (HUB_SGBD,
.env)" / "PostgreSQL (HUB_SGBD, .env)") — un redémarrage du conteneur
ne duplique jamais cette connexion, mais met à jour ses identifiants
si le `.env` a changé entre-temps. Une connexion créée à la main par
la personne (libellé différent) n'est jamais touchée par l'amorçage.
Vide (comme dans `.env` par défaut) = rien d'amorcé, comportement
inchangé.

## Correctif réel : authentification MySQL 8 (`cryptography`)

Rencontré au premier vrai test : `'cryptography' package is required
for sha256_password or caching_sha2_password auth methods` — PyMySQL
ne gère pas nativement les méthodes d'authentification par défaut de
MySQL 8+ sans ce paquet supplémentaire. Ajouté à
`dba/api/requirements.txt`.

## Chantiers pas commencés

- Édition de ligne individuelle depuis l'onglet Parcourir (actuellement lecture seule — la modification passe par l'onglet SQL, un `UPDATE` explicite)
- Export des résultats (CSV/JSON)
- Historique des requêtes exécutées

## Bug réel — couleurs codées en dur, invisibles en thème sombre

Signalé par capture d'écran : le libellé d'une connexion (ligne
sélectionnée) devenait presque illisible en thème sombre.

**Cause** : `.dba-conn-item.selected { background: #eff6ff }` --
bleu très clair codé en dur, jamais adapté au thème. Le texte
(couleur du thème, claire par nécessité sur fond sombre) se
retrouvait sur un fond accidentellement clair -- texte clair sur
fond clair, contraste quasi nul.

**Trouvées au passage, même motif** : les couleurs de succès/échec
du test de connexion et de l'import mysqldump (`#166534`/`#b91c1c`
en ligne dans `App.jsx`), et `.dba-success` dans `dba.css`
(`#166534`/`#f0fdf4`) -- toutes remplacées par `var(--ok)`/
`var(--danger)`/`var(--ok-bg)`/`var(--danger-bg)`.

**`--ok-bg` ajoutée à `shared/theme.css`** (les deux thèmes) --
manquait alors que `--danger-bg` existait déjà, asymétrie qui a
permis à ce bug de se glisser. Bénéficie à tous les fronts partageant
ce thème, pas seulement DBA.

Recherché explicitement dans les autres fronts (hub, tickets, coffre,
portail admin coffre) -- aucune occurrence du même motif trouvée
ailleurs, semble isolé à DBA.

## Bug réel — erreur 413 systématique sur l'import mysqldump

Signalé par capture d'écran : "Erreur 413" à chaque tentative
d'import d'un dump.

**Cause** : 413 = "Payload Too Large", une erreur de PROXY, pas de
l'application. `dba/api/app.py` autorise déjà `MAX_CONTENT_LENGTH =
2 Go` côté Flask -- mais `tls-proxy` (la passerelle unique devant
tous les fronts) n'avait **aucune** directive `client_max_body_size`
dans sa configuration nginx générée (`tls-proxy/render_nginx_conf.py`)
-- nginx retombe alors sur sa limite par défaut, **1 Mo**, bien en
dessous de tout dump de base de données réel. Le goulot
d'étranglement était invisible tant qu'on ne teste pas avec un
fichier réellement volumineux.

**Corrigé** : `client_max_body_size 2G;` ajoutée au bloc `server` du
gabarit nginx (`HEADER_TEMPLATE`), alignée sur la limite Flask déjà
en place. Bénéficie aussi aux autres imports volumineux du projet
(export/import JSON tickets, restauration coffre-fort...).
`vault-standalone/tls-proxy/render_nginx_conf.py` importe ce même
gabarit **par référence directe** (pas une copie) -- corrigé
automatiquement pour les deux instances par ce seul changement,
vérifié en générant réellement les deux configurations.

Vérifié : rendu réel du fichier généré (`--check` puis génération
complète) sur les deux instances, directive bien présente au bon
endroit dans chaque cas.

## Bug réel — "SSL is required, but the server does not support it" (MySQL)

Signalé par capture d'écran : erreur systématique 2026 sur certaines
connexions MySQL.

**Cause** : certains serveurs MySQL/MariaDB annoncent la capacité SSL
sans la supporter pleinement -- PyMySQL tente alors le chiffrement de
façon opportuniste (`ssl` non spécifié dans `_connect()` jusqu'ici,
comportement par défaut de la bibliothèque).

**Corrigé** : `ssl_disabled=True` ajouté à `pymysql.connect()`
(`dba/api/connectors/mysql.py`) -- paramètre officiel et documenté de
PyMySQL (confirmé via sa documentation, pas une extrapolation), force
explicitement l'absence de SSL quelle que soit l'annonce du serveur.

**Non vérifié dans cet environnement** : aucun serveur MySQL/MariaDB
réel disponible ici pour tester la connexion effectivement corrigée
-- seule la syntaxe est validée. Le paramètre est confirmé exact et
documenté côté PyMySQL, mais le comportement réel reste à vérifier
par la personne en conditions réelles.

**Suite réelle** : l'erreur persistait sur l'import mysqldump après
ce premier correctif -- **chemin de code entièrement séparé**
(client `mysql` en ligne de commande, voir `import_mysql_dump()`,
jamais PyMySQL) que le premier correctif ne couvrait pas. Corrigé :
`--ssl-mode=DISABLED` ajouté à la commande `mysql` construite (flag
standard MySQL 5.7.11+/MariaDB, même principe que `ssl_disabled=True`
côté PyMySQL). Vérifié réellement cette fois : nouveau test explicite
sur le contenu exact de la commande construite (19 tests au total sur
cette route, tous passants) -- toujours pas de vrai serveur MySQL
disponible ici pour une vérification bout en bout, mais la commande
elle-même est maintenant garantie correcte.

## Modification d'une connexion — interface ajoutée

Demandé explicitement : le backend (`PUT /connections/<id>`) était
déjà générique et complet depuis le départ, seule l'interface
manquait -- aucune capacité de modification, uniquement "Tester" et
"Supprimer".

**Point important géré correctement** : le mot de passe n'est
**jamais** renvoyé par l'API (`_connection_row_public` le retire
systématiquement, seul un booléen `has_password` indique s'il y en a
un) -- le formulaire d'édition ne le préremplit donc jamais, un champ
laissé vide signifie "conserver le mot de passe actuel", jamais un
écrasement accidentel par une chaîne vide. Vérifié réellement.

Formulaire d'édition replié sous chaque connexion (bouton "✏️
Modifier"/"✕ Annuler"), mêmes champs que la création, adaptés selon
le moteur (SQLite : chemin de fichier ; MySQL/PostgreSQL : hôte/port/
utilisateur/mot de passe/base).

Vérifié réellement : 8 tests sur la route backend (déjà existante,
jamais testée jusqu'ici) -- dont la garantie la plus importante,
modifier le libellé seul ne touche jamais au mot de passe déjà
enregistré. Classes CSS déjà toutes couvertes par le style existant,
aucun ajout nécessaire. Non-régression complète.

## Édition de cellule avec validation par ligne

Demandé explicitement (capture d'écran de la vue "Données") : modifier
le contenu d'un champ directement dans le tableau parcouru, avec un
mécanisme de validation/annulation qui bloque la navigation tant que
le choix n'est pas fait.

**Backend** : `update_row(table, pk_column, pk_value, updates,
database=None)` ajouté aux trois connecteurs (SQLite, MySQL,
PostgreSQL) -- requêtes TOUJOURS paramétrées pour les valeurs (jamais
d'interpolation directe, contrairement à `execute_sql` qui exécute du
SQL déjà écrit par la personne) ; seuls les noms (table/colonnes/clé
primaire) passent par l'échappement d'identifiant du dialecte
(backticks MySQL, guillemets doubles Postgres/SQLite). Nouvelle
route `PUT /connections/<id>/tables/<table>/rows` -- colonnes à
modifier validées contre le VRAI schéma de la table (via
`get_table_columns`) avant toute écriture, jamais une colonne
inconnue ou la clé primaire elle-même passée telle quelle au
connecteur.

**Interface** : cliquer une cellule (hors clé primaire) passe TOUTE
LA LIGNE en mode édition -- chaque champ modifiable devient un champ
de saisie, avec "✓ Valider"/"✕ Annuler" dans une colonne dédiée.
Pendant l'édition : pagination et sélecteurs de connexion/base/table
tous désactivés, impossible de démarrer l'édition d'une autre ligne
tant que celle en cours n'est pas résolue -- la navigation est bien
bloquée jusqu'au choix, demandé explicitement. Mise à jour locale
immédiate après validation, jamais un rechargement complet de la
page pour une seule ligne modifiée.

Vérifié réellement : 50 tests sur ce chantier (8 sur `update_row`
SQLite avec une vraie base, dont la garantie qu'une valeur contenant
une tentative d'injection SQL est stockée telle quelle, jamais
exécutée ; 12 sur la construction des requêtes MySQL/Postgres avec un
curseur simulé, dialecte d'échappement vérifié pour chacun ; 10 sur
la route backend complète avec une vraie connexion SQLite bout en
bout, dont le refus explicite de modifier la clé primaire). Classes
CSS toutes vérifiées présentes. Non-régression complète.

**Non vérifié dans cet environnement** : rendu visuel réel, aucun
navigateur ici -- et bien sûr aucune vraie connexion MySQL/PostgreSQL
disponible pour confirmer `update_row` en conditions réelles sur ces
deux moteurs (seule la construction des requêtes est garantie
correcte).

## Alerte de fermeture d'onglet — premier morceau d'une proposition plus large

Demandé explicitement, en marge d'une proposition d'évolution bien
plus large (coquille à onglets pour l'ensemble du hub, historique
versionné, rémanence complète -- voir échange en session, non
retranscrite ici faute d'un endroit dédié pour le moment). Discuté
ouvertement : les points 1-3 de cette proposition impliquent une
refonte architecturale de grande ampleur (chaque application du
projet est aujourd'hui un site web indépendant, pas un composant
d'une seule application) -- volontairement mis de côté pour l'instant.
Seul le point 4 (alerte de fermeture) est isolé, faisable
immédiatement, application par application.

**`shared/useUnsavedChangesWarning.js`** (nouveau, copié comme
`theme.css`/`preferences.js` au moment du build) -- hook React
générique, s'appuie sur l'évènement natif `beforeunload` : avertit
la personne si elle ferme l'onglet, recharge la page, ou navigue vers
une autre URL alors qu'une modification est en cours. Couvre
uniquement "fermeture/navigation hors de l'application" -- jamais la
navigation interne entre écrans d'une même application (déjà gérée
autrement, voir l'édition de cellule ci-dessus : les sélecteurs sont
désactivés pendant l'édition, empêchant cette navigation-là plutôt
que de simplement avertir dessus).

Câblé dans `BrowseTab` : `useUnsavedChangesWarning(isEditing)` --
réutilise l'état déjà existant de l'édition de cellule, aucune
nouvelle variable d'état nécessaire.

Vérifié réellement : 6 tests sur la logique du gestionnaire
d'évènement (reproduction fidèle du comportement, `beforeunload`
n'étant pas déclenchable dans un environnement Node sans navigateur),
dont la forme "fonction" (réévaluée à chaque tentative de fermeture,
pas figée à la création). Non-régression complète.

**Non vérifié dans cet environnement** : comportement réel de la
boîte de dialogue native du navigateur, aucun navigateur disponible
ici -- le texte affiché est de toute façon imposé par chaque
navigateur pour des raisons de sécurité, jamais personnalisable.

**Prêt à être réutilisé** par les autres applications du projet
(`shared/`, même mécanisme de copie au build) -- dès qu'un écran a
un état "modification en cours" clair, l'ajouter est immédiat.

## Ajout, suppression, sélection multiple, duplication de lignes

Demandé explicitement, en prolongement direct de l'édition de
cellule -- liste d'évolutions notée par la personne comme "mineures",
priorisée et découpée avec son accord avant de commencer.

**Backend** : `insert_row(table, values, pk_column=None, database=None)`
et `delete_rows(table, pk_column, pk_values, database=None)` ajoutés
aux trois connecteurs, toujours paramétrés pour les valeurs.
PostgreSQL utilise `RETURNING <clé>` pour récupérer la nouvelle clé
générée -- psycopg2 n'a pas de `lastrowid` natif contrairement à
sqlite3/PyMySQL. Deux nouvelles routes : `POST .../rows` (ajout) et
`DELETE .../rows` (suppression en lot, `pk_values` en corps de
requête). **La "duplication" ne nécessite aucune route séparée** :
l'interface envoie simplement les valeurs de la ligne à copier (sans
sa clé primaire, jamais transmise) à la route d'ajout normale, qui
génère une nouvelle clé comme pour n'importe quel ajout.

**Interface** : case à cocher par ligne + "tout sélectionner" dans
l'en-tête (n'apparaît que si la table a une clé primaire identifiable
-- sans elle, ni sélection ni édition n'ont de sens fiable). Barre
d'outils flottante dès qu'une sélection existe, avec "📋 Dupliquer"
et "🗑️ Supprimer" (confirmation demandée pour les deux, la
suppression étant irréversible). Bouton "+ Ajouter une ligne" ouvre
un formulaire inline en tête de tableau, même esprit que l'édition
de cellule. **`isBusy` généralisé** (édition OU ajout en cours) --
la navigation (page, table, connexion) reste bloquée pendant l'une
comme l'autre, et l'alerte de fermeture d'onglet (voir plus haut)
couvre désormais les deux cas, pas seulement l'édition.

Vérifié réellement : 35 tests sur ce chantier (10 sur `insert_row`/
`delete_rows` SQLite avec une vraie base, dont l'injection SQL
vérifiée sur une valeur insérée ; 12 sur la construction des
requêtes MySQL/Postgres avec un curseur simulé, dont la clause
`RETURNING` spécifique à Postgres ; 13 sur les deux routes complètes
avec une vraie connexion SQLite bout en bout, dont le refus explicite
de fournir la clé primaire à l'ajout, et la duplication réelle
vérifiée -- deux lignes identiques sauf leur id). Syntaxe complète
validée, équilibre de toutes les balises HTML critiques vérifié,
classes CSS toutes présentes. Non-régression complète sur l'ensemble
du module DBA.

**Non vérifié dans cet environnement** : rendu visuel réel, aucun
navigateur ici -- et toujours aucune vraie connexion MySQL/PostgreSQL
disponible pour confirmer ces deux méthodes en conditions réelles sur
ces moteurs (seule la construction des requêtes est garantie
correcte).

**Reste dans la liste plus large, pas encore commencé** : modification
du schéma de table (ALTER TABLE — ajout/modification/suppression de
colonne), traité séparément vu son ampleur propre (syntaxe très
différente selon SQLite/MySQL/Postgres).

## Modification de schéma (ALTER TABLE) — ajout, renommage, modification, suppression de colonne

Demandé explicitement, traité séparément des lignes vu son ampleur
propre (syntaxe très différente selon le moteur).

**Backend** : `add_column`/`drop_column`/`rename_column`/
`modify_column` ajoutés aux trois connecteurs. Types SQL bruts
(ex. `VARCHAR(200)`) transmis tels quels, jamais interprétés --
la personne écrit dans le vocabulaire du moteur qu'elle connaît déjà.

**Version SQLite vérifiée dans cet environnement : 3.45.1** --
largement au-dessus des versions minimales nécessaires (`DROP
COLUMN` depuis 3.35.0/2021, `RENAME COLUMN` depuis 3.25.0/2018),
donc les trois opérations fonctionnent nativement sur les trois
moteurs. **`MODIFY COLUMN` (changer le type ou la nullabilité)
reste hors de portée pour SQLite** -- ce moteur n'a tout simplement
pas d'`ALTER COLUMN` natif. Plutôt qu'une reconstruction de table
risquée (CREATE + COPY + DROP + RENAME) jugée disproportionnée pour
une évolution notée comme mineure, une `NotImplementedError`
explicite est levée (renvoyée en 501, pas un 500 générique) -- à
faire à la main via la console SQL si vraiment nécessaire sur
SQLite.

MySQL et PostgreSQL divergent nettement l'un de l'autre sur ce point
précis : MySQL combine type et nullabilité dans une seule clause
`MODIFY COLUMN` (et exige de re-préciser le type même pour ne
changer QUE la nullabilité -- une requête `SHOW COLUMNS`
supplémentaire est faite si besoin pour le retrouver) ; PostgreSQL
les sépare en deux instructions indépendantes (`ALTER COLUMN TYPE`
puis `SET`/`DROP NOT NULL`), chacune exécutée seulement si demandée.

Trois nouvelles routes : `POST .../columns` (ajout), `DELETE
.../columns/<nom>` (suppression), `PUT .../columns/<nom>`
(renommage et/ou modification -- tous les champs optionnels, la
clé primaire jamais accessible par ces trois routes, même prudence
que pour l'édition/suppression de lignes).

**Interface** : panneau "colonnes" existant enrichi -- bouton "+
Ajouter une colonne" (formulaire inline : nom, type SQL,
nullable), actions ✏️/🗑️ par colonne (absentes sur la clé
primaire), édition inline du renommage/type/nullabilité avec
validation/annulation.

Vérifié réellement : 41 tests sur ce chantier (10 sur SQLite avec
une vraie base -- données PRÉSERVÉES à travers un renommage,
suppression confirmée sans toucher aux autres colonnes, erreur
explicite et distincte pour `modify_column` ; 17 sur la construction
exacte des requêtes MySQL/Postgres avec curseur simulé, dont la
divergence MODIFY/deux-instructions vérifiée précisément pour
chaque moteur ; 14 sur les trois routes complètes avec une vraie
connexion SQLite bout en bout, dont le refus explicite de toucher
à la clé primaire par ces trois chemins). Syntaxe complète validée,
équilibre de toutes les balises HTML critiques vérifié, classes CSS
toutes présentes. Non-régression complète sur l'ensemble du module.

**Non vérifié dans cet environnement** : rendu visuel réel, aucun
navigateur ici -- et toujours aucune vraie connexion MySQL/PostgreSQL
disponible pour confirmer ces méthodes en conditions réelles sur ces
deux moteurs.

## Bug réel — boutons d'édition invisibles sur une table large

Signalé après test : sur une table avec beaucoup de colonnes, les
boutons "✓ Valider"/"✕ Annuler" (et "✏️"/"🗑️" côté colonnes)
nécessitaient un défilement horizontal pour être vus.

**Corrigé** :
- `.dba-row-actions`/`.dba-row-actions-col` (cellule ET en-tête)
  passent en `position: sticky; right: 0` -- restent TOUJOURS
  visibles quelle que soit la largeur de la table, plus jamais
  dépendants du défilement. `background: inherit` -- reprend la
  couleur de la ligne (normale, en édition, ou sélectionnée), jamais
  une couleur fixe qui détonnerait selon l'état de la ligne. Légère
  ombre portée pour marquer visuellement la séparation avec le
  contenu défilant.
- `.dba-main` élargi (1200px → 1600px) -- de l'espace inutilisé à
  gauche/droite alors que les tables de données bénéficient
  directement de plus de largeur.

Vérifié : syntaxe (tsc), équilibre CSS, classes toutes présentes.
Non-régression complète.

**Non vérifié dans cet environnement** : rendu visuel réel, aucun
navigateur ici -- le comportement `position: sticky` à l'intérieur
d'un conteneur à défilement horizontal est un motif CSS standard et
largement supporté, mais mérite votre confirmation sur une vraie
table large.

## Catalogue SGBD -- extension au portail (livraison #229)

Backlog item 11 -- complète la version déjà livrée côté hub (#221,
`hub/src/SchemaAnalyzerView.jsx`). Nouvel onglet "🗂️ Catalogue SGBD"
directement dans CE portail (`dba/portal/src/App.jsx`,
`sshTunnelsApi.js`) -- même logique de référence croisée par hôte+port
(`127.0.0.1`/`localhost` + port local d'un tunnel), volontairement
DUPLIQUÉE plutôt que partagée entre les deux codebases frontend (le
hub et ce portail sont deux applis Vite distinctes, sans module
commun entre elles à ce jour).

Nouveau `sshTunnelsApi.js` -- même convention de réponse
`{ok, status, data}` que `api.js` de ce portail (pas le motif
`{error}` du hub), pour rester cohérent avec le reste de CE codebase.

**Sécurité** : `dba-api` stocke le mot de passe des connexions en
clair (caractéristique déjà existante, pas introduite ici) -- vérifié
explicitement que ce champ n'apparaît nulle part dans le nouvel
onglet, seul `label` est utilisé.

`VITE_SSH_TUNNELS_API_BASE_URL` ajouté au service `dba-portal` dans
`docker-compose.yml` -- les routes passerelle (`/api/ssh-tunnels/`,
`/dba/`) existaient déjà, rien à modifier côté `tls-proxy`.

**Vérifié réellement** : logique de correspondance hôte/port testée
en isolation avec les mêmes cas limites que la version hub (connexion
directe jamais confondue avec un tunnel, `127.0.0.1`/`localhost`
tous deux reconnus), gestion d'erreur testée. Structure JSX
revérifiée. Recherche textuelle explicite confirmant l'absence du
mot de passe.

## Branchement rights-api (livraison #292)

Suite au backlog item 38, quatrième service branché après
ssh-tunnels-api (#289), ldap-admin-api (#290), vault-admin-api
(#291). Candidat particulièrement sensible : `/connections/<id>/sql`
exécute du SQL LIBRE contre des bases EXTERNES à ce projet,
potentiellement de production. Aucune décision explicite préexistante
trouvée dans ce module contraire à ce branchement (contrairement à
vault/LDAP) -- procédé directement.

**12 routes protégées** : `POST/PUT/DELETE /connections`,
`POST /connections/<id>/test`, `PUT/POST/DELETE .../rows`,
`POST/DELETE/PUT .../columns`, `POST /sql`,
`POST /import-mysql-dump`. Les routes de consultation (liste des
connexions, bases, tables, colonnes, lignes) restent ouvertes.

**Cas particulier** : `import-mysql-dump` reçoit un envoi MULTIPART
(fichier), jamais de corps JSON comme les autres routes -- `groups`
extrait d'un champ de formulaire ordinaire (valeurs séparées par des
virgules), pas du body JSON habituel.

Même motif que les trois services précédents pour le reste : gating
au niveau du SERVICE ENTIER, FAIL CLOSED, OPT-IN via
`DBA_RIGHTS_API_URL`.

**Vérifié réellement** : `_check_manage_right` testé en isolation
(FAIL CLOSED confirmé). Câblage réel testé sur les 12 routes
(refusé) et sur `/sql` (autorisé -- confirmé qu'on retombe sur le
comportement normal, jamais un 403 une fois le droit accordé).
Non-régression des routes de consultation reconfirmée.
