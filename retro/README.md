# Rétro-ingénierie (livraison #243)

Backlog item 30, demandé explicitement EN URGENCE : "une vieille
application de gestion développée avec fatfree en php, une demande
de modification des données mais sans outil de structuration
hiérarchique, mon prédécesseur développeur génial avait ses schémas
en tête et faisait le travail de préparation des données en sql à la
main... dans un environnement sans historique... et sans note".

Complète `schema-analyzer` (#151-241, qui déduit des relations
depuis le SCHÉMA introspecté et les DONNÉES réelles) -- ici, les
relations CANDIDATES sont déduites depuis l'USAGE RÉEL dans le CODE
SOURCE : une jointure SQL écrite en toutes lettres révèle une
relation qu'aucune heuristique de nommage (`relation_detector.py`)
ni de motif de valeur (`list_detector.py`) ne pourrait deviner si les
noms sont atypiques -- exactement le cas décrit par la personne :
"des jointures faciles avec id->tbl_id, d'autres moins avec des set
(id,id,id...) et d'autres que je ne comprends pas encore".

## Portée de cette première livraison

**Volet 1 demandé ("déterminer les relations dans une base SQL")
LIVRÉ** -- analyse du code PHP par expression régulière.

**Volet 2 demandé ("proposer un schéma fonctionnel de l'interface")
PAS COMMENCÉ** -- hors de portée de cette première livraison,
construite en urgence pour répondre au besoin immédiat (comprendre
les relations de données avant une modification pressante). À
cadrer séparément le moment venu.

## Approche technique -- décisions prises pour avancer

**Expression régulière, JAMAIS un vrai parseur PHP/SQL** -- un
véritable parseur (AST complet) serait plus exact mais démesuré pour
ce besoin précis : repérer des CANDIDATS à valider humainement,
jamais appliquer quoi que ce soit automatiquement (même philosophie
que `relation_detector.py` : proposer, jamais confirmer seul). Les
motifs couverts :
- Jointure explicite moderne : `FROM table1 t1 JOIN table2 t2 ON
  t1.col1 = t2.col2`.
- Jointure implicite ANCIEN STYLE (plusieurs tables séparées par des
  virgules dans le FROM, condition dans le WHERE) -- **trouvaille
  réelle en testant** : une première version ne capturait QUE la
  première table après `FROM`, ratant complètement ce motif pourtant
  explicitement décrit par la personne comme présent dans son code.
  Corrigé : la clause FROM entière est extraite puis éclatée sur la
  virgule.
- Motif Fat-Free `Mapper` (`new \DB\SQL\Mapper($db, 'table')`) --
  révèle les tables réellement manipulées, même sans jointure.

**Un alias jamais déclaré dans le FROM/JOIN du même fragment est
IGNORÉ, jamais deviné** -- mieux vaut manquer un candidat que d'en
proposer un avec un nom de table faux.

**Déduplication avec compteur d'occurrences** -- une même relation
apparaît souvent des dizaines de fois dans un vieux code (requête
copiée-collée à travers de nombreux écrans) : la personne veut voir
LA relation avec sa fréquence, pas cent lignes identiques.

**Limites connues, documentées plutôt que silencieuses** :
- SQL construit dynamiquement (concaténation de variables PHP dans
  la requête) échappe entièrement à ce repérage -- seul du SQL
  écrit en dur dans une chaîne littérale est vu.

**Correctif livraison #246 -- auto-jointure hiérarchique** : une
relation comme `employes e1 JOIN employes e2 ON e1.manager_id =
e2.id` -- exactement le genre de structure hiérarchique visée par la
personne à l'origine de ce module -- était auparavant EXCLUE à tort
(le filtre visait à écarter une comparaison triviale, le même alias
des deux côtés, mais excluait aussi ce cas légitime de deux alias
DIFFÉRENTS pointant vers la même table). Corrigé : le test porte
désormais sur les alias eux-mêmes, pas sur la table résolue -- une
auto-jointure légitime est capturée et marquée `is_self_reference:
true`, affichée avec le badge "🔀 hiérarchique" côté hub, pour la
distinguer clairement d'une relation inter-tables ordinaire.

## API

`POST /scan` (multipart/form-data, champ `file`) -- une archive ZIP
du code source PHP. Chaque fichier `.php` est balayé. Protection
"zip slip" (chemin d'archive qui sortirait du dossier) -- structurellement
écartée de toute façon, ce service ne décompresse jamais sur disque,
tout est lu en mémoire directement depuis l'archive. Bornes de
sécurité : 5000 fichiers PHP max, 200 Mo décompressés max.

## Vérifié réellement

Testé en profondeur avec des fragments PHP/SQL réalistes et variés :
jointure moderne avec alias, jointure ancien style avec virgules
(motif corrigé après un premier échec de test), motif Fat-Free
Mapper, alias non résolu jamais deviné, piège "WHERE confondu avec
un alias" (jamais le cas), déduplication avec compteur, texte non-SQL
jamais un faux positif, ligne/fichier d'origine exacts sur plusieurs
requêtes différentes. Route `/scan` testée de bout en bout avec une
vraie archive ZIP construite en mémoire (fichiers PHP + non-PHP
mélangés, ZIP invalide, tentative de chemin hors archive). Structure
JSX de `RetroView.jsx` vérifiée. **Livraison #246** : auto-jointure
hiérarchique testée (deux alias distincts sur la même table,
capturée et marquée), comparaison triviale (même alias) confirmée
toujours exclue, motif ancien style avec virgules testé aussi pour
ce cas, non-régression complète des relations ordinaires et de la
déduplication reconfirmée avec le nouveau champ `is_self_reference`.

## Extension : structures de données depuis les vues (livraison #245)

Demandé explicitement, juste après le volet 1 : "j'aimerais disposer
d'un outil qui me permette d'importer du php et des vues d'écran en
html puis d'en déduire une partie des structures de données".

**Vérifié via recherche AVANT de coder** (jamais deviné) : la
syntaxe réelle du moteur de gabarits Fat-Free natif --
`{{@variable}}` (espaces optionnels), avec `<repeat group="{{@array}}"
value="{{@item}}">` pour les boucles -- confirmée par la
documentation officielle F3 ("item contains the array of data
retrieved from the database table... accessed using the column name
as the array key").

Nouveau `html_view_scanner.py`, trois signaux distincts :
- **Champs de formulaire** (`name="..."` sur input/select/textarea
  dans un `<form>`) -- le signal le plus fiable, un formulaire de
  saisie correspond quasi toujours directement aux colonnes d'une
  table.
- **Accès aux champs en gabarit F3 natif** (`{{@item.champ}}` ou
  `{{@item['champ']}}`).
- **Accès aux champs en PHP brut affiché** (`<?= $row['champ'] ?>`
  ou `<?php echo $row->champ; ?>`) -- les applications Fat-Free plus
  anciennes utilisent souvent des vues PHP classiques plutôt que le
  moteur natif ; la personne a signalé explicitement que le code
  varie "selon les époques de l'évolution".

**Restreint VOLONTAIREMENT aux motifs d'AFFICHAGE** (echo/`<?=`),
jamais tout accès PHP à un tableau/objet -- un tableau PHP sert à
mille choses (config, session...) sans rapport avec une structure de
données métier ; se limiter à ce qui est réellement affiché à
l'écran garde le signal propre, quitte à manquer des champs jamais
affichés nulle part.

`/scan` balaie désormais aussi `.phtml`/`.html`/`.htm` en plus de
`.php` (une vue Fat-Free peut être écrite dans n'importe laquelle de
ces extensions selon l'époque) -- LES DEUX scanners (SQL + vues)
tournent sur CHAQUE fichier retenu, un fichier `.php` pouvant
contenir à la fois une requête SQL et du HTML affiché directement
(mélange courant en PHP ancien style).

Les résultats de plusieurs écrans sont FUSIONNÉS par variable de
gabarit (`merge_template_field_results`) -- une même variable
(ex. `@client`) apparaît généralement dans plusieurs écrans (liste,
fiche, formulaire d'édition...), chacun n'en révélant qu'une partie ;
fusionner donne la structure la plus complète possible.

Côté hub : nouvelles sections "Structures de champs déduites des
vues" et "Formulaires trouvés" dans `RetroView.jsx`.

**Vérifié réellement** : testé avec des fragments réalistes couvrant
les trois signaux, y compris un fichier MÉLANGEANT les deux styles
de gabarit (F3 natif ET PHP brut affiché dans le même texte --
exactement le cas "évolution du code" décrit par la personne), la
fusion de plusieurs écrans révélant progressivement une structure
complète, un formulaire sans aucun champ nommé correctement ignoré,
et le motif tableau `entite[champ]` visible tel quel. Route `/scan`
retestée de bout en bout avec une archive mélangeant `.php`/`.html`/
`.phtml`. Non-régression du motif Fat-Free `Mapper` confirmée.

## Envoi direct vers l'éditeur de relations (livraison #247)

Ferme la boucle "repérer ici, confirmer là-bas" -- sélectionner une
connexion DBA (optionnel, en haut de l'écran) fait apparaître un
bouton "→ Envoyer" sur chaque relation candidate du tableau, qui la
crée directement comme relation PROPOSÉE dans `schema-analyzer`
(`POST /relations`, `source="manual"`, réutilise `createRelation`
déjà existant côté hub). Plus besoin de recopier à la main table/
colonne/table/colonne dans l'éditeur -- la validation contre les
vraies données ("🔍 Valider les données", #241) se fait ensuite
là-bas normalement.

**Aucune confirmation automatique** -- la relation créée reste au
statut "proposée", exactement comme une relation détectée par
`relation_detector.py` : la personne la confirme/rejette elle-même
après avoir vu le résultat de la validation contre les données.

Statut par ligne affiché immédiatement (✔ envoyée / ⚠️ échec avec le
message, ex. relation déjà existante) -- jamais un envoi silencieux
dont le résultat resterait invisible.

## Second volet : schéma fonctionnel de l'application (livraison #248)

Le volet demandé à l'origine, jamais commencé jusqu'ici : "proposer
un schéma fonctionnel de l'interface -- reconstituer, à partir du
code, la structure/l'organisation fonctionnelle de l'application
(écrans, actions, flux)".

Nouveau `route_scanner.py` -- extrait les routes déclarées via
`$f3->route(...)` OU `F3::route(...)` (les deux syntaxes,
historiquement coexistantes dans F3, voir la note de version
ci-dessous), regroupées par CONTRÔLEUR : la vue d'ensemble "quels
écrans/actions gère ce contrôleur" demandée. Pour chaque route :
méthode(s) HTTP, chemin, alias éventuel, jetons de paramètre d'URL
(`@id`), et le handler (méthode d'instance `Classe->methode`,
méthode statique `Classe::methode`, fonction globale, ou "closure
inline" signalée sans tenter d'en extraire le corps -- fragile à
capturer fidèlement par expression régulière, la personne retrouve
le détail directement au fichier:ligne indiqué).

**⚠️ Version de Fat-Free NON CONFIRMÉE pour cette application** --
la personne pense qu'il s'agit de la lignée 2.x, sans certitude
("il me semble"). Recherché explicitement avant de coder : F3 a
historiquement proposé À LA FOIS un appel STATIQUE (`F3::route(...)`,
vu dans du code datant de 2011-2012) ET un appel par INSTANCE
(`$f3->route(...)`, la forme la plus documentée aujourd'hui) --
**les deux syntaxes semblent avoir coexisté sur une large part de
l'historique F3**, pas strictement l'une en 2.x et l'autre en 3.x
comme d'abord supposé -- ce scanner couvre donc les deux sans
distinction de version. Le nom de la classe ORM (`DB\SQL\Mapper`)
et la structure de base de `route()` semblent également stables.
**Aucune documentation officielle spécifique à la lignée 2.x n'a pu
être trouvée** (le site officiel n'archive plus, semble-t-il, que
3.6 et versions ultérieures) -- les résultats réels sur le code de
la personne restent le meilleur signal pour confirmer ou ajuster
cette couverture, pas une simulation supplémentaire dans cet
environnement.

Côté hub : nouvelle section "Schéma fonctionnel -- écrans et
actions", routes affichées groupées par contrôleur.

**Vérifié réellement** : toutes les variantes documentées testées --
handler par méthode d'instance et statique, plusieurs méthodes HTTP
séparées par `|`, jeton de paramètre d'URL dans le chemin, alias de
route (bien distingué du jeton de paramètre malgré la même syntaxe
`@`), closure inline signalée sans tenter d'extraction, ancien style
`F3::route`, troisième argument de cache TTL ignoré proprement,
regroupement par contrôleur, fonction globale sans classe. Route
`/scan` retestée de bout en bout avec les trois scanners actifs
simultanément sur la même archive, non-régression confirmée.

## Reste à faire

- Jamais testé contre une vraie archive de code Fat-Free réelle
  (uniquement des fragments construits pour les tests) -- portée et
  limites à confirmer au premier usage réel.
- Version de Fat-Free non confirmée (lignée 2.x supposée, sans
  certitude) -- à ajuster selon ce que révèlent les premiers
  résultats réels.
- Config-file de routage (`.cfg`, section `[routes]`, syntaxe INI
  `GET /chemin = Contrôleur->méthode`) -- une AUTRE façon de
  déclarer des routes dans F3, distincte de l'appel `route()` PHP,
  jamais couverte ici.
- Flux entre écrans (navigation, enchaînement des actions) --
  seules les routes elles-mêmes sont extraites, jamais les liens
  entre elles.

## Parcours applicatifs -- rétro-ingénierie dynamique (livraison #441, volet 2)

Demande : « continuer dans le reverse engineering d'appli web (évolution de
notre SI) : un plugin Firefox, un agent relais et une API type QA qui suit
mon parcours dans l'appli web ; ça s'intègre avec la partie analyse bdd ».
C'est le **volet 2** du backlog 30 (« schéma FONCTIONNEL de l'interface »),
abordé par l'usage réel plutôt que par le seul code.

Trois pièces :

1. **Extension Firefox** `retro/browser-extension/` (README dédié) :
   écrans, DOM utile (formulaires, tableaux, en-têtes), clics, saisies
   (noms et longueurs, jamais un mot de passe), envois, requêtes HTTP
   (page, XHR, redirections, clés de formulaire), repères. Variante
   Chromium (MV3) avec les mêmes sources.
2. **Agent relais** `retro/relay/relay.py` (Python 3 seul) sur le poste :
   reçoit les événements de l'extension en local (127.0.0.1:6320), les met
   dans une file SQLite, les expédie par lots à retro-api avec le jeton
   `RETRO_RELAY_TOKEN` (`X-Relay-Token`) et la CA interne ; rejoue après une
   coupure, dans l'ordre (`seq`). Crée / termine les parcours, pose des
   repères ; l'extension adopte le parcours courant du relais.
3. **retro-api, routes « parcours »** (retro-api a maintenant un volume
   `/data`, SQLite `retro.db`) : `GET/POST /apps` (application : libellé, URL
   de base, connexion DBA + base), `POST /scan?app=<libellé>` conserve le
   scan de code comme référence (avec, nouveaux, `classes` {classe:
   fichier} et `file_tables` {fichier: tables Mapper}), `GET /journeys`,
   `POST /journeys`, `GET /journeys/<id>` (étapes + carte), `POST
   /journeys/<id>/events` (relais, jeton, idempotent sur `seq`), `/end`,
   `/annotate`, `DELETE`, `POST /journeys/<id>/queries/collect` (« analyse
   bdd » : lit `mysql.general_log` entre le début et la fin du parcours via
   dba-api -- prérequis MySQL : `SET GLOBAL general_log='ON',
   log_output='TABLE'` pendant le test), `GET /apps/<libellé>/map` (carte
   agrégée sur tous les parcours).

Logique pure `journeys.py` : une **étape** commence quand le navigateur
envoie la requête d'une page (`request` main_frame -- c'est là que le
serveur, donc le SQL, travaille) ou à un repère ; le `navigation` qui suit
la complète. Un POST suivi d'une redirection donne deux étapes (l'action,
puis la page). Les URL sont normalisées (`/client/42` → `/client/{n}`) et
rapprochées des routes Fat-Free du scan (`/client/@id`, jetons et `*`) →
contrôleur → fichier (classe → fichier) → tables (jointures + Mapper de ce
fichier) ; les requêtes du journal SQL sont rattachées à la dernière étape
commencée avant elles (paramètre `skew` pour un décalage d'horloge base /
navigateur) → tables réellement lues / écrites par écran. La **carte
fonctionnelle** liste chaque écran avec route, fichiers, formulaires
(champs ↔ champs de gabarit du scan), tables « code », tables « base »,
et la matrice écrans × tables (● concordant, ◐ code seul, ◑ base seule).

Tuile Rétro-ingénierie, section « Parcours applicatifs » : applications,
parcours, étapes annotables, collecte du SQL, schéma fonctionnel. Motif
Mapper élargi (`$this->db`, `$f3->get('DB')`) : constaté manquant sur le
premier code parcouru.

**Vérifié** : 7 tests `retro/api/test_journeys.py` (logique + routes avec
faux dba-api), 2 tests du relais (file, panne du central et rejeu, fin),
3 tests de l'extension (fonctions pures), 2 tests hub ; **chaîne réelle**
extension (Chromium MV3, Playwright) → relais → retro-api → application
factice Flask (liste, fiche, saisie, POST + 302, XHR, repère), scan d'un
code F3 factice, collecte du journal via un faux dba-api → étapes et carte
attendues, rendu Chromium de la tuile ; compose YAML. **Non vérifié** :
Firefox réel (manifeste V2), un vrai `mysql.general_log` via dba-api réel,
build Docker de retro-api.

## Rejeu, sous-parcours, comparaison (livraison #443)

Questions posées : « où et sous quelle forme est stockée la navigation ? une
interface pour rejouer et ajouter des sous-parcours ? ». Stockage : SQLite
`retro.db` sur le volume `/data` (`apps`, `journeys`, `events` -- une ligne
par événement brut, JSON tel que reçu, ordre `seq` --, `queries`) ; étapes
et carte recalculées à la lecture.

- **Arbre de parcours** : `journeys.parent_id` + `branch_step` (sous-parcours
  qui part de l'étape N du parent) et `kind` (`recorded` | `replay`),
  migration automatique. Dans la tuile, bouton « Sous-parcours à partir
  d'ici » sur une étape → parcours enfant en cours ; dans le navigateur on
  revient à cet écran, puis popup de l'extension → « Reprendre » (le relais
  l'adopte, `POST /journeys/<id>/adopt`). Liste indentée.
- **Rejouer pas à pas** (storyboard) : pour chaque étape, ce que l'écran
  montrait (en-têtes, formulaires et champs, colonnes des tableaux),
  actions, requêtes SQL, trace du rejeu, annotation.
- **Rejeu réel** : `GET /journeys/<id>/script` dérive des étapes un script
  `navigate` / `click` / `fill` / `submit` / `expect` / `mark` (`navigate`
  seulement pour un écran atteint sans action ni redirection ; un clic sur
  le bouton d'envoi n'est pas doublé d'un `submit` ; `fill` sans valeur
  enregistrée → le rejeu s'arrête sur le champ, la personne saisit puis
  « Continuer »). `POST /journeys/<id>/replay` crée le parcours enfant
  (`kind=replay`) et renvoie le script ; le relais (`POST /replay`) le
  transmet à l'extension, dont l'arrière-plan exécute action par action
  dans l'onglet (attente des chargements, `expect` GET vérifié par l'URL
  normalisée, `expect` POST par la requête réellement vue) en enregistrant
  le rejeu comme n'importe quel parcours, plus une trace `replay-action`
  par action. `GET /journeys/<a>/compare/<b>` aligne les deux parcours
  étape par étape (écran, méthode, statut, titre, champs, en-têtes,
  colonnes, requêtes secondaires, tables SQL) ; la tuile l'affiche pour
  tout rejeu, sous le storyboard.

Vérifié : 8 tests API, relais, 4 tests extension, 3 hub ; **rejeu réel** dans
Chromium via le popup de l'extension sur l'application factice (valeurs
enregistrées) : 8 actions exécutées, rejeu comparé à l'origine 5/5 étapes
identiques ; rendu Chromium. Non vérifié : Firefox réel.

## Interface générée au design du hub (livraison #444, phase 2)

Demande : « de ce parcours, générer une interface avec le design/charte
du hub pour offrir les mêmes fonctionnalités ». Deux pièces :

- **`retro/api/ui_spec.py`** (pur, 3 tests + route) : étapes de tous les
  parcours + carte fonctionnelle + colonnes réelles des tables (dba-api,
  connexion de l'application) → une **spécification** : par écran, genre
  (`list` : tableau vu ; `form` : formulaire POST ≥ 2 champs ; `detail` ;
  `action` : écran POST transitoire ; `other`), titre (premier en-tête vu),
  **table principale** (écritures SQL de l'action du formulaire 0,9 →
  journal SQL de l'écran 0,8 → tables du code 0,5/0,35), **colonnes** de
  liste (en-têtes des tableaux vus rapprochés des colonnes réelles :
  exact 1,0, sans séparateurs 0,9, inclusion ≤ 0,85, jetons ≤ 0,6 ; les
  préfixes `txt`, `f_`, `champ_`… et les accents sont neutralisés),
  **champs** de formulaire rapprochés de même (clé primaire et jetons CSRF
  écartés), liens (clics vers un autre écran), actions (POST + tables
  écrites), points « à compléter ». `GET /apps/<label>/ui-spec`
  (enregistrée ; `?regenerate=1` recalcule en conservant les choix
  marqués `*_manual`), `PUT /apps/<label>/ui-spec`.
- **`hub/src/GeneratedAppView.jsx`** (+ `generatedApp.js`, 1 test) : dans
  la tuile Rétro-ingénierie, bouton « Application générée » : navigation
  entre les écrans (charte du hub), **listes** branchées sur la table réelle
  via dba-api (filtre, pagination 50, « Nouveau »), **fiches** : ouvrir une
  ligne → formulaire dont les champs sont ceux du parcours, rattachés aux
  colonnes → `PUT/POST rows` de dba-api (clé primaire jamais modifiée,
  colonnes validées côté serveur). Onglet **Spécification** : titre, genre,
  table (liste des tables connues), masquage, avec pour chaque rattachement
  sa source et sa confiance ; enregistré aussitôt, survit à une
  régénération.

Ce que les parcours n'ont pas montré (règles métier du PHP, écrans jamais
visités, champs sans colonne) n'est pas inventé : « à compléter ». Une
exportation de la spec en module React autonome est possible ensuite (le
rendu est déjà générique).

Vérifié : 3 tests `test_ui_spec.py` (rapprochement, genres, table, choix
manuels conservés, routes avec faux dba-api) ; chaîne réelle : spec
générée depuis les parcours réels de l'application factice + faux dba-api
(tables clients/journal/villes/produits), rendu Chromium : liste Clients
(Nom, Ville → ville_id), ouverture d'une ligne, modification de l'email
**écrite dans la table** via dba-api. Non vérifié : une vraie application
(la richesse des écrans dépend des parcours enregistrés).
