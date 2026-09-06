# OwnCloud/Nextcloud — onglet de visualisation (lecture seule)

Même famille que les onglets IPAM/Optick/TTS-GU/Zenoss (voir
`ipam/README.md` pour le détail des garanties de lecture seule),
appliqué à la base MySQL d'une instance **ownCloud/Nextcloud
existante** — mais avec une **architecture différente**, imposée par
le volume réel de données.

## Différence architecturale : pas d'arbre complet

La table `oc_filecache` du schéma fourni est à `AUTO_INCREMENT ≈
2 473 859` — environ **2,5 millions de lignes**. Charger un arbre
complet en un seul appel, comme le font IPAM/Optick/TTS-GU/Zenoss (au
plus quelques milliers de lignes en jeu), y serait irresponsable :
réponse gigantesque, base mise à genoux pour une simple ouverture
d'onglet.

Ce module renvoie donc **un nœud + ses enfants directs à la fois**
(`GET /children/<storage>/<fileid>`), à charge pour le frontend de
déplier l'arbre **progressivement au clic**, en accumulant l'état
côté client. Cette gestion d'état (`frontend/src/apps/owncloudLib.js`
— `mergeChildren()` / `buildRenderTree()`) garantit une chose
précise : re-déplier un dossier parent ne fait **jamais** perdre le
dépliage déjà fait plus bas dans un de ses enfants.

Un point sur un nœud (`hasUnloadedChildren`) signale un dossier non
encore déplié — cliquer dessus déclenche l'appel `/children`
correspondant et fusionne le résultat dans l'arbre déjà construit.

## Racines indépendantes = les storages

`oc_storages` (un stockage = un point de montage racine, ex. le
répertoire d'un utilisateur ou un stockage externe monté). Chaque
racine porte `itemCount`/`totalSize` (agrégat `oc_filecache` groupé
par `storage`, une seule requête) et `rootFileId` (la ligne
`path_hash = md5('')` de ce storage) — c'est cet id que le frontend
utilise pour son tout premier appel à `/children`.

`oc_storages.id` est parfois un identifiant technique illisible (hash,
notation `object::user:...` selon le backend de stockage) — `name`
résout un nom humain quand c'est possible (voir section suivante),
avec repli sur cet identifiant brut sinon. `storageId` (nouveau champ)
reste toujours l'identifiant technique brut, quel que soit `name` —
visible en info-bulle sur chaque racine côté frontend.

## Intégration hub et détection des chemins trop longs (livraison #354)

Demandé explicitement (2026-09-05) : "vérifie bien que la tuile ged
donne un accès séparé visuellement d'un coté à la ged externe et au
dépôt interne, car par la ged externe on ne doit pas toucher aux
fichiers internes" -- **CE dépôt (OwnCloud) n'avait jusqu'ici AUCUNE
interface dans le hub** (`hub/src/`), uniquement dans "Supervision
SI" (`frontend/`, `OwncloudApp.jsx` -- arbre radial, chronologie de
versions, bien plus riche). Ajout d'une version SIMPLE, native au hub
-- sous-onglets "OwnCloud"/"Recherche" de la tuile GED
(`hub/src/GedView.jsx`), clairement séparés visuellement du dépôt
interne (Mayan) par une bordure orange et une bannière permanente
"lecture seule -- dépôt EXTERNE". Un lien vers "Supervision SI" est
affiché pour qui veut l'expérience plus complète -- jamais dupliquée
ici, juste référencée (pas de lien profond possible : le routage
interne de ce frontend est un simple état React, `useState`, jamais
piloté par une URL).

Voir `hub/src/ownCloudClient.js`, `hub/src/OwnCloudTreeView.jsx`
(navigation fil d'ariane, même contrat `/roots`+`/children` que
`frontend/src/apps/owncloudApi.js`, confirmé identique) et
`hub/src/OwnCloudSearchView.jsx` (recherche, voir
`owncloud/search-api/README.md`).

**Chemins trop longs pour Windows et autres (#354)** -- suite d'une
discussion sur les problèmes de synchronisation des drives (priorité
signalée par la personne) : ce point précis est actionnable SANS
nouvel accès (contrairement au reste du sujet synchronisation, qui
reste À CLARIFIER -- voir section dédiée plus bas). Nouvelle route :

```
GET /long-paths?threshold=260&limit=200
```

`threshold` (défaut 260, la limite CLASSIQUE Windows `MAX_PATH` --
Windows 10/11 supportent des chemins plus longs SI le mode "chemin
long" est activé côté système, jamais présumé activé ici) : longueur
au-delà de laquelle un chemin est signalé. Renvoie
`{threshold, results: [{fileid, storage, path, pathLength}]}` --
`storage` est l'id technique brut, à croiser côté frontend avec les
racines déjà chargées via `/roots` pour afficher un nom humain
(jamais une seconde résolution serveur pour la même information).

⚠️ **Requête COÛTEUSE** -- `WHERE LENGTH(path) > ...` n'a AUCUN index
exploitable sur `oc_filecache` (~2,5M lignes) : balaie la table
ENTIÈRE à chaque appel non caché. Mise en cache sur
`OWNCLOUD_LONG_PATH_CACHE_TTL` (défaut 900s, bien plus long que
`OWNCLOUD_CACHE_TTL`) -- les chemins ne changent pas à la minute,
inutile de réinterroger une requête aussi coûteuse à chaque clic.
Déclenchée EXPLICITEMENT côté hub (bouton "Rechercher"), jamais
chargée automatiquement à l'ouverture de l'onglet.

## Sujet plus large : supervision des erreurs de synchronisation (#354, PAS COMMENCÉ)

Demandé explicitement, marqué comme LA priorité par la personne
("erreur de synchronisation des drives... ça c'est la priorité, c'est
ce qui gêne le plus les utilisateurs") -- **volontairement PAS
construit ici**, plusieurs points restent À CLARIFIER avant tout
cadrage technique :

1. **Où vivent réellement ces erreurs ?** Sur la plupart des
   architectures ownCloud/Nextcloud, les erreurs de sync détectées
   côté client desktop (conflit, permission refusée, chemin trop
   long) restent LOCALES à chaque poste (journal local du client),
   JAMAIS remontées au serveur par défaut. Ce module n'a accès qu'à
   la base MySQL serveur (lecture seule) -- si une app
   "Activité"/"Notifications" est installée côté ownCloud
   (généralement visible dans son administration), elle POURRAIT
   exposer une table lisible -- à confirmer avant de présumer quoi
   que ce soit.
2. **Agent de supervision de l'hôte** -- demandé explicitement,
   "brancher sur le superviseur du ownCloud pour relier les pics de
   charge système et l'activité ownCloud". Rejoint directement les
   items 44/45 du backlog (déjà notés "à clarifier", jamais cadrés)
   -- questions posées à la personne, réponses en attente : OS de la
   machine hôte, accès de déploiement disponible, mécanisme
   push/pull pour la remontée des métriques.

Voir BACKLOG.md pour le suivi complet de ces deux points.

## Colonnes jamais lues (et une exception délibérée)

Email, quota, authentification, partages nominatifs — tout le reste
de `oc_accounts`. Seul `oc_mounts.mount_point` est utilisé par
ailleurs, à titre d'exemple descriptif (un chemin, pas une donnée
personnelle).

**EXCEPTION délibérée et scopée**, demandée explicitement :
`oc_accounts.display_name` (+ `oc_mounts.user_id` comme clé de
jointure) est lu par `/roots`, uniquement pour remplacer l'identifiant
technique de storage par un nom humain dans la liste des racines
(voir `fetch_display_names()` dans `owncloud/api/app.py`). Rien
d'autre n'est lu sur `oc_accounts` — pas d'email, pas de quota, pas de
champ d'authentification.

**Hypothèse de schéma non vérifiée depuis cet environnement** (pas de
vrai MySQL disponible ici) : `oc_accounts.display_name` a été confirmé
par la personne, mais ni le nom exact de la table `oc_accounts` ni la
colonne de jointure `user_id` n'ont pu être vérifiés contre le schéma
réel. Si ça ne correspond pas, l'échec est capturé et journalisé
(`app.logger.warning`, voir les logs du conteneur `owncloud-api`) et
l'affichage retombe silencieusement sur l'identifiant technique brut
(comportement d'avant cet ajout) — jamais un 503 sur tout l'onglet
pour une hypothèse de schéma erronée sur un seul champ d'agrément.

## Variables `.env`

| Variable | Rôle | Défaut |
|---|---|---|
| `OWNCLOUD_API_PORT` | port exposé du service | `6110` |
| `OWNCLOUD_DB_HOST` | hôte MySQL de l'instance | *(vide — à renseigner)* |
| `OWNCLOUD_DB_PORT` | port MySQL | `3306` |
| `OWNCLOUD_DB_NAME` | nom de la base | `owncloud` |
| `OWNCLOUD_DB_USER` / `OWNCLOUD_DB_PASSWORD` | compte **lecture seule** | *(vide)* |
| `OWNCLOUD_DB_SSL` | connexion chiffrée | `false` |
| `OWNCLOUD_DB_CHARSET` | encodage — `utf8mb4` par défaut (noms de fichiers modernes, emojis compris) | `utf8mb4` |
| `OWNCLOUD_CACHE_TTL` | durée de cache (s) | `60` |

```sql
CREATE USER 'owncloud_readonly'@'%' IDENTIFIED BY 'un-mot-de-passe-dedie';
GRANT SELECT ON owncloud.* TO 'owncloud_readonly'@'%';
FLUSH PRIVILEGES;
```

```bash
./scripts/run.sh up -d --build owncloud-api
```

## Fenêtre temporelle (timeline)

Un sélecteur à deux poignées indépendantes (début/fin) au-dessus de
l'arbre filtre par `mtime` (date de dernière modification). **Porte
uniquement sur les nœuds déjà chargés côté client** — cohérent avec
l'architecture par dépliage : élargir la fenêtre ne va jamais chercher
en base des fichiers non encore explorés, ce serait une fonctionnalité
différente (un nouvel endpoint de recherche par date, avec la question
ouverte de savoir si `mtime` est indexé sur 2,5M lignes — à vérifier
avant de s'y engager si le besoin s'en fait sentir).

Point de conception à noter : un dossier dont le mtime tombe dans la
fenêtre **ne fait pas remonter tous ses fichiers**, contrairement à la
recherche texte (où trouver un dossier par son nom justifie de montrer
son contenu). Le mtime d'un dossier n'est qu'une conséquence mécanique
du dernier changement en son sein, pas un regroupement voulu — seuls
les fichiers dont le *propre* mtime est dans la fenêtre sont retenus,
avec leurs ancêtres affichés pour situer où ils se trouvent. Ce choix
a été vérifié par un test dédié (un cas qui, avec l'implémentation
naïve initiale, faisait apparaître à tort un fichier hors fenêtre
simplement parce que son dossier parent matchait lui-même).

Se combine avec la recherche texte par intersection : un nœud doit
satisfaire les deux filtres actifs pour rester en pleine visibilité.

## Géocodage (panneau à droite, sous la fiche JSON)

Réutilise l'infrastructure déjà construite pour Pixel Grid plutôt que
d'en dupliquer une copie : même endpoint `GET /geocode` (service
BAN/Géoplateforme), même table `geolocations` partagée (déjà pensée
comme générique — voir pixel-grid/README.md, section "Fusion IP/MAC"
et `register_ips`). `OwncloudGeocodePanel.jsx` importe directement
`geocodeAddress`/`upsertGeolocation` depuis `pixelGridApi.js` —
composition cross-module déjà en usage dans ce projet (`FusionApp.jsx`
fait de même avec IPAM/Zenoss/Pixel Grid).

**Base uniquement métadonnées** (nom du nœud sélectionné, ou nom du
dossier parent le plus proche si c'est un fichier — `guessLocationQuery`
dans `owncloudLib.js`) : jamais le contenu du document. C'est une
**suggestion de départ éditable**, jamais géocodée automatiquement à
la sélection — la personne modifie le texte si besoin avant de
chercher, puis choisit explicitement d'enregistrer (même principe
partout dans ce projet : aucune action automatique silencieuse).

## Filtre "nœuds récurrents" et bascule Arbre/Timeline versions

Bandeau au-dessus de l'arbre : une case "Masquer les dossiers
récurrents (files, files_trashbin, files_versions)" — ces trois noms
reviennent à l'identique en tête de **chaque** storage/utilisateur,
du bruit répété quand on explore plusieurs racines à la suite. Décoché
par défaut (rien ne change tant que la personne ne l'active pas
explicitement). `pruneRecurringRootChildren()` dans `owncloudLib.js`
agit **uniquement sur les enfants directs de la racine affichée** —
jamais en profondeur, pour ne jamais retirer par erreur un dossier
utilisateur qui porterait par coïncidence l'un de ces noms plus bas
dans l'arbre.

Deux onglets dans le panneau central : **🌐 Arbre** (existant) et
**🕒 Timeline versions** (nouveau) — reconstruit, à partir des seuls
nœuds déjà chargés côté client (même contrainte que le reste de ce
module par dépliage), l'historique de chaque fichier versionné.
Convention ownCloud confirmée en conditions réelles (capture d'écran
fournie par la personne) : une version de `files/<chemin>` est stockée
sous `files_versions/<chemin>.v<timestamp unix>` — `parseVersionPath()`
extrait le chemin d'origine et l'horodatage, `buildVersionTimeline()`
regroupe par fichier et trie par date décroissante. Chaque fichier
suivi s'affiche avec un point par version sur un axe temporel commun
(pas un axe par fichier) ; cliquer un point sélectionne cette version
précise dans la fiche JSON, comme un nœud de l'arbre normal.

**Nœuds visuellement distincts** : les dossiers sont désormais des
losanges (carré à 45°), les fichiers restent des cercles —
`OwncloudRadialTree.jsx`. Distinction par la **forme**, pas seulement
la couleur (reste lisible en niveaux de gris/daltonisme).

## Filtre à termes combinables + vue arbre classique

Demandé : filtrer sur plusieurs motifs à la fois (ex. `*.zip` +
"analyse"), chacun en inclusion ou exclusion, combinés au choix par ET
ou OU — plus une vue arbre classique (liste indentée) en alternative
au radial.

**`nodeMatchesGlob()`** (`owncloudLib.js`) — motif avec joker `*`,
volontairement PAS une regex complète (pas de `?`, pas de classes de
caractères). Sans `*` : sous-chaîne classique, rétrocompatible avec
l'ancien filtre simple (`"analyse"` matche tout nom qui EN CONTIENT).
Avec `*` : ancré sur le nom ENTIER (`"*.zip"` doit se **terminer** par
`.zip`, jamais juste le contenir au milieu).

**`buildCombinedGlobPredicate(terms, combineMode)`** — modèle
volontairement uniforme : "exclure" est traité comme une NÉGATION du
terme lui-même, puis tous les termes sont combinés par ET ou OU selon
`combineMode`. Généralise proprement à n'importe quel nombre de
termes, pas seulement deux, sans cas particulier à coder. Réutilise
telle quelle la mécanique de propagation ancêtres/descendants déjà en
place (`computeRelevantIdsByPredicate`) — aucune duplication.

**`OwncloudFilterTerms.jsx`** — un terme par défaut (usage courant,
identique à l'ancien champ simple), "+ Critère" en ajoute d'autres.
Chaque terme : bouton inclure/exclure (vert/rouge), champ de motif,
retirer. Bascule ET/OU entre les termes successifs.

**`OwncloudClassicTree.jsx`** — liste indentée verticale, MÊME
interface de props que `OwncloudRadialTree` (`tree`, `selectedId`,
`onSelectNode`, `relevantIds`) pour permuter librement entre les deux
sans rien changer côté `OwncloudApp.jsx`. Pas de repli/dépliage LOCAL
séparé — montre exactement ce qui est chargé, comme le radial
(cohérence en changeant de vue). Bascule ◎ Radial / ☰ Classique dans
le bandeau, à côté des onglets Arbre/Timeline versions.

Vérifié réellement : 23 tests sur la logique pure (glob avec/sans
joker, échappement des caractères spéciaux, ET/OU, inclure+exclure
combinés, propagation ancêtres/descendants, l'état initial par défaut
qui désactive bien tout filtrage).

## Dictionnaire des dossiers récurrents — trois catégories distinctes

Deux itérations sur ce chantier. La première généralisait le pruning à
toute profondeur mais mélangeait tout dans une seule liste. Retour
réel de la personne : il faut distinguer **trois phénomènes**, jamais
mélangés :

1. **Structure ownCloud CONNUE** (`files`, `files_trashbin`,
   `files_versions`, `cache`, `thumbnails`, `uploads` —
   `KNOWN_OWNCLOUD_STRUCTURAL_NAMES`) — apparaît à l'identique sous
   CHAQUE racine par construction du logiciel, jamais par choix d'un
   utilisateur. Connue D'AVANCE, jamais "détectée" par comptage —
   compter un nom qu'on sait déjà systématique n'a aucun sens.
   Toujours affichée, individuellement masquable.
2. **Dossiers utilisateur récurrents** — conventions de nommage
   authentiquement DÉCOUVERTES en observant ce qui revient sur **au
   moins 2 racines différentes** (`Archive`, `Trash`...). Jamais
   connues d'avance, jamais confondues avec la catégorie 1.
3. **Uniques** — vus une seule fois pour l'instant, PAS encore prouvés
   récurrents. Retour explicite : "1 occurrence c'est pas récurrent" —
   liste séparée, moins mise en avant visuellement, plutôt que mélangés
   à la catégorie 2.

**`countDirectoryNamesIn()`** exclut désormais la structure connue
(catégorie 1) de son comptage — jamais polluer le dictionnaire
dynamique avec ce qu'on sait déjà systématique.

**`splitOccurrencesByThreshold()`** (seuil par défaut : 2) — sépare le
dictionnaire accumulé en `recurring`/`unique` selon ce seuil.

**`mergeOccurrenceCounts()`** — accumulé au fil du chargement, jamais
remis à zéro en changeant de racine (contrairement à `nodesById`) : le
but même de ce dictionnaire est de repérer ce qui REVIENT d'un compte
à l'autre, impossible à voir en ne regardant qu'une seule racine à la
fois.

**`pruneNodesByNames()`** — agit à N'IMPORTE QUELLE profondeur, pas
seulement les enfants directs de la racine ; MÊME mécanisme pour les
trois catégories (peu importe D'OÙ vient un nom masqué, le retirer de
l'arbre fonctionne pareil).

**`OwncloudRecurringPanel.jsx`** — panneau repliable, trois sections
distinctes (titres différenciés), code couleur par intensité sur la
catégorie 2 uniquement (rouge ≥10 occurrences, bleu 3-9). Rien de
masqué par défaut, même philosophie que l'ancien mécanisme.

Vérifié réellement : 16 tests sur la logique pure d'origine (pruning,
accumulation), 13 tests sur la nouvelle séparation en trois
catégories (exclusion de la structure connue, seuil, tri), 5 tests
d'intégration bout en bout mis à jour pour refléter le nouveau
comportement (noms utilisateur réels plutôt que la structure connue,
devenue non pertinente pour ce scénario).

## Tri des racines (colonne de gauche)

Demandé : nombre d'éléments décroissant par défaut, plus pratique
pour repérer les gros comptes qu'un ordre d'arrivée API sans
signification particulière. `sortRoots()` dans `owncloudLib.js` — deux
modes (`count-desc` par défaut, `alpha` en alternative), toujours une
copie renvoyée, jamais de mutation du tableau reçu. 9 tests réels.

## Feuille de route — croisement avec Tickets/Optick/TTS-GU et relations réseau

Discuté explicitement avec la personne (pas une supposition) :
l'objectif à terme est de repérer, dans les documents déposés, tout ce
qui se rapporte à une IP/un système/une localisation déjà connue
ailleurs dans la plateforme (relations réseau : routes, support
physique, routage dynamique, proxy, voisinage), et de relier les
documents aux tickets correspondants (rapports, procédures, cahiers
des charges).

**Décision actée** : ça se fera en deux étapes.
1. **Maintenant, sur les métadonnées seules** (nom, chemin, dates) —
   le géocodage ci-dessus en est le premier morceau livré. Repérer des
   motifs IP/ticket dans les noms de fichiers/dossiers serait la suite
   logique dans ce même esprit, mais n'a pas encore été construit.
2. **Contenu réel des documents — la voie retenue est Elasticsearch**,
   pas un accès direct aux fichiers. La personne met en place côté
   ownCloud l'app `search_elastic` (indexation via Tika, résultats
   filtrés par permissions) — répond à la question d'accès "élégant et
   sécurisé" du point 1 sans que ce module lise jamais lui-même le
   contenu binaire d'un fichier. Le proxy `owncloud/search-api/`
   (nouveau service, port 6112) et l'onglet **Recherche** du frontend
   sont déjà construits et testés (30 tests Python + 21 Node), prêts à
   se brancher dès que l'instance Elasticsearch existe côté personne —
   voir `owncloud/search-api/README.md` pour la mise en place du
   connecteur et le détail de conception (schéma jamais supposé en
   dur, sécurité de la traduction de requête et du rendu des extraits).

QGIS (`.qgs`/`.qgz`, XML) et AutoCAD (`.dwg`/`.dxf`) sont mentionnés
comme formats à terme — non évalués techniquement pour l'instant :
QGIS est probablement abordable (XML lisible), AutoCAD nettement moins
(`.dwg` est un format propriétaire fermé ; `.dxf` s'ouvre avec des
bibliothèques comme `ezdxf`). La personne a signalé qu'il existe aussi
des visionneuses et outils de transcodage open source/API pour ces
deux formats — à évaluer le moment venu, pas encore fait.

## Dépannage

**`cryptography package is required for sha256_password or
caching_sha2_password auth methods`** : voir `ipam/README.md` (même
cause, même correctif — `requirements.txt` déjà à jour, reconstruire
l'image suffit : `docker compose build owncloud-api`).

**`TypeError: Object of type Decimal is not JSON serializable` sur
`/roots`** : `SUM()` sur une colonne entière (`size`) renvoie un
`decimal.Decimal` côté pymysql — MySQL type le résultat d'un `SUM` en
DECIMAL, indépendamment du type de la colonne d'origine. Ce type
n'est pas sérialisable tel quel par `json.dumps`. Corrigé
(`fetch_storage_aggregates` convertit désormais explicitement en
`int`) ; reconstruire l'image suffit :
`docker compose build owncloud-api && docker compose up -d owncloud-api`.
Bug jamais détectable depuis cet environnement de développement (ni
réseau, ni vrai serveur MySQL disponibles ici — mes bouchons de test
renvoient toujours des `int` Python natifs, jamais un `Decimal`
comme le ferait un vrai pymysql) : remonté et corrigé seulement après
un premier test en conditions réelles. Les autres modules ont été
audités par précaution (`grep SUM(/AVG(` sur les 6) : Optick et
TTS-GU utilisent le même motif `SUM(CASE...)` mais l'enveloppaient
déjà dans `int(...)`, aucun autre module n'a d'agrégat non protégé.

## Vérifié depuis cet environnement / non vérifié

**Vérifié** : `format_file_row` (dossier vs fichier, racine sans nom,
mimetype inconnu, conversion booléenne), `run_select`, et la
résolution `display_name` (`fetch_display_names` — filtrage des
`user_id` vides, correspondance trouvée, absente, `display_name` vide/
null ignoré, dégradation propre sur erreur de schéma sans faire
planter `/roots`, distinction entre une erreur DB (rattrapée) et un
bug de programmation qui doit continuer à se propager) — 26 tests
Python (15 existants + 11 nouveaux). `guessLocationQuery` (dossier
sélectionné, fichier -> dossier parent le plus proche, remonte si un
parent intermédiaire n'a pas de nom, racine sans nom, aucun nœud) — 7
tests Node. Côté front (reste) : `mergeChildren`/`buildRenderTree`
(dépliage préservé sur re-fusion, arbre partiellement chargé),
recherche, fil d'ariane, `fmtBytes`, coloration JSON, fenêtre
temporelle (propagation ancêtres-seulement, combinaison avec la
recherche texte, bornes qui s'élargissent avec le dépliage) — 40 tests
Node. Contrôle croisé exhaustif classes CSS ↔ classes des composants
(a détecté et corrigé un manque réel cette fois — pas le faux positif
habituel du wrapper : la couleur des fichiers reposait entièrement sur
des variantes de charge héritées du gabarit dupliqué, retirées sans
règle de base de repli ; corrigé avant livraison).

**Bug réel trouvé et corrigé depuis (remonté par la personne, export
console à l'appui)** : `OwncloudRadialTree.jsx` était le seul des 6
composants d'arbre radial du projet à ne pas importer `d3` —
`Uncaught ReferenceError: d3 is not defined` au clic sur un dossier,
qui démontait toute l'application faute d'error boundary (React le
signalait explicitement dans la console). Un oubli isolé : les 5
autres composants (`ZenossRadialTree`, `IpamRadialTree`,
`OptickRadialTree`, `TtsguRadialTree`, `RadialTree`) l'importaient
déjà correctement — vérifié après coup qu'aucun des 6 n'a la même
lacune désormais.

**Filtre nœuds récurrents / timeline versions / symbole dossiers**
(retouches démo) : `pruneRecurringRootChildren` (retire les 3 noms par
défaut, épargne un sous-dossier homonyme plus profond, arbre non muté,
liste vide -> inchangé) et `parseVersionPath`/`buildVersionTimeline`
(chemin réel de la capture d'écran fournie, chemin `files/` normal
rejeté, suffixe non numérique rejeté, marqueur avec préfixe accepté,
tri décroissant, état partiel/vide sans exception) — 18 tests Node.
Le changement de symbole (losange dossiers) est un changement de rendu
SVG pur, non testable côté Node — revu visuellement dans le code, pas
en navigateur (voir "Non vérifié" ci-dessous).

**Non vérifié** : aucune connexion MySQL réelle (même limite que les
autres modules). L'assemblage final (page, panneau JSON, câblage
docker-compose/.env/navigation) a été complété et vérifié
syntaxiquement, mais jamais exécuté dans un navigateur. La résolution
`display_name` en particulier repose sur une hypothèse de schéma
(`oc_accounts.display_name` + jointure par `oc_mounts.user_id`)
confirmée pour le nom de colonne par la personne, mais pas vérifiée
contre le schéma réel pour le nom de table/clé de jointure — voir la
section "Colonnes jamais lues" plus haut pour le comportement de repli
si l'hypothèse est fausse. `OwncloudGeocodePanel.jsx` n'a fait l'objet
d'aucun appel réel au service BAN/Géoplateforme depuis cet
environnement — même limite déjà documentée côté `pixel-grid/README.md`.
