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
