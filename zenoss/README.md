# Zenoss — onglet de visualisation (lecture seule)

Même principe que les onglets IPAM/Optick (voir `ipam/README.md` pour
le détail des garanties de lecture seule), appliqué à la base
**"events"** de Zenoss existante : **racines indépendantes** à gauche,
**arbre radial** au centre, **fiche JSON** à droite.

Deux modes, sélectionnables par un bandeau d'onglets en haut de
l'écran :
- **Classification** (historique, `/roots` + `/tree`) — arbre par
  `eventClass`, coloré par sévérité active.
- **Localisation** (nouveau, `/location_roots` + `/location_tree`) —
  inventaire physique par `Location`, voir section dédiée plus bas.

Les deux modes sont indépendants : changer de mode réinitialise la
racine sélectionnée, l'arbre et le filtre (les ids de racine et la
forme de l'arbre diffèrent entre les deux).

## Particularité de ce schéma : pas de colonne parent/enfant

Contrairement à IPAM (`masterSubnetId`) et Optick (`id_parent`), ce
schéma ne contient **aucune clé de hiérarchie**. La table `status`
(événements actifs) et `history` (événements clos) portent chacune
une colonne `eventClass` — la classification d'événement Zenoss,
stockée comme un simple **chemin texte** façon système de fichiers
(ex. `/App/Fail/Http`, `/Net/Perf`, `/Unknown`).

L'arbre est donc **reconstruit en découpant ces chemins sur `/`**, pas
en suivant des clés étrangères : chaque segment devient un nœud, les
**racines indépendantes** sont les premiers segments distincts
rencontrés (`App`, `Net`, `Unknown`...). Un chemin vide ou absent est
traité comme `/Unknown` (la valeur par défaut de la colonne dans ce
schéma) ; les doubles slashes ou slash final sont normalisés sans
perte d'information puisqu'il s'agit d'un affichage agrégé, jamais
d'une écriture.

Chaque nœud porte ses **propres** comptages (pas cumulés) :
- `activeCount` / `activeBySeverity` — événements actifs (`status`) de
  cette classe précise, avec répartition par sévérité Zenoss standard
  (Critical/Error/Warning/Info/Debug/Clear) ;
- `historyCount` — événements clos (`history`) de cette classe.

Le panneau des racines (gauche) affiche des **totaux cumulés** sur
tout le sous-arbre (calculés séparément), pour distinguer d'un coup
d'œil "combien d'événements dans cette branche" de "combien
précisément sur ce nœud".

## Colonnes jamais lues (mode Classification)

`message`, `summary`, `ipAddress`, `device`, `Location`, `Systems`,
`manager`, `agent`, `ownerid` — le contenu individuel d'un événement
(potentiellement sensible : adresse IP, nom de machine, texte libre)
n'est **jamais** exposé par `/tree` et `/roots` (mode Classification).
Seuls des chemins de classification et des comptages agrégés le sont
— aucun événement individuel n'est lisible via ces deux routes.

Deux exceptions délibérées et scopées existent ailleurs dans ce
fichier — `/ip_list` et `/location_roots` + `/location_tree` — voir
leurs sections dédiées ci-dessous pour le détail exact de ce qu'elles
lisent et pourquoi. `message`, `summary`, `manager`, `agent`,
`ownerid` restent exclus **partout**, sans aucune exception.

## Variables `.env`

| Variable | Rôle | Défaut |
|---|---|---|
| `ZENOSS_API_PORT` | port exposé du service | `6108` |
| `ZENOSS_DB_HOST` | hôte MySQL de la base events | *(vide — à renseigner)* |
| `ZENOSS_DB_PORT` | port MySQL | `3306` |
| `ZENOSS_DB_NAME` | nom de la base | `events` |
| `ZENOSS_DB_USER` / `ZENOSS_DB_PASSWORD` | compte **lecture seule** | *(vide)* |
| `ZENOSS_DB_SSL` | connexion chiffrée | `false` |
| `ZENOSS_DB_CHARSET` | encodage de connexion | `utf8` |
| `ZENOSS_CACHE_TTL` | durée de cache (s) | `60` |

```sql
CREATE USER 'zenoss_readonly'@'%' IDENTIFIED BY 'un-mot-de-passe-dedie';
GRANT SELECT ON events.* TO 'zenoss_readonly'@'%';
FLUSH PRIVILEGES;
```

```bash
./scripts/run.sh up -d --build zenoss-api
```

## Fenêtre temporelle (timeline)

Le schéma fourni (`zenoss_events_schema.dump`) confirme `firstTime`/
`lastTime` en colonnes **indexées** sur `status` et `history` — la
fenêtre y est donc a priori performante même sur un historique
volumineux. Même principe qu'Optick/TTS-GU : un chemin de classe
n'est pas une entité individuellement datée mais un agrégat
d'événements, donc **recalcul côté serveur** (`WHERE firstTime
BETWEEN ...`) plutôt qu'un filtrage visuel, débattu 300ms côté front.

Axe retenu : `firstTime` (première occurrence de ce dédoublonnage
d'événement), pas `lastTime` — cohérent avec le choix "apparu pendant
cette fenêtre" fait côté tickets, pas "actif pendant cette fenêtre".

Les bornes du curseur (`dateBounds`) sont calculées par une requête
`UNION ALL` sur `status` et `history` réunis, scopée aux chemins de
classe de la racine consultée (racine et tous ses descendants,
intermédiaires compris) — portent sur l'ensemble de la racine,
indépendamment de la fenêtre active.

## Fusion IP/MAC — exception délibérée au périmètre "jamais lu"

`GET /ip_list` expose `ipAddress` et `device` (nom de machine),
agrégés par IP : nombre d'événements actifs, sévérité maximale
(`status`), volume d'événements historiques (`history`). **Ces deux
colonnes étaient jusqu'ici explicitement exclues** (voir l'en-tête de
`zenoss/api/app.py`) — l'exception est scopée à ce seul endpoint,
demandée explicitement pour corréler les sources réseau entre elles
dans l'onglet **Fusion IP/MAC** (avec IPAM actuellement). `/tree` et
`/roots` continuent à ne renvoyer que des comptages agrégés par
classification, jamais d'IP ni de nom de machine. `message`,
`summary`, `Location`, `Systems`, `manager`, `agent`, `ownerid`
restent exclus partout, y compris de `/ip_list`.

Zenoss ne stocke pas d'adresse MAC dans ce schéma (`status`/`history`
n'ont pas de colonne dédiée) — sa contribution à la fusion se limite à
IP + nom de machine + contexte d'alertes, le MAC venant exclusivement
d'IPAM quand disponible.

## Inventaire physique — deuxième exception délibérée au périmètre "jamais lu"

`GET /location_roots` et `GET /location_tree/<root_id>` (mode
**Localisation**) lisent `device`, `Location`, `ipAddress` et
`Systems` sur `history` — **ces quatre colonnes étaient jusqu'ici
explicitement exclues** (voir l'en-tête de `zenoss/api/app.py`).
Demandé explicitement pour reconstruire une hiérarchie de
localisation physique (site → sous-site → équipement), dans le même
esprit que le besoin ayant motivé Fusion IP/MAC. `message`, `summary`,
`manager`, `agent`, `ownerid` restent exclus ici aussi.

**Même principe de reconstruction par chemin texte** que la
classification (pas de clé de hiérarchie dans ce schéma) : `Location`
est découpée sur `/`, chaque segment devient un nœud de type
`"location"`, les racines indépendantes sont les premiers segments
distincts. Un `Location` vide/absent est regroupé sous la racine
`"Sans localisation"` plutôt que d'être perdu silencieusement.

**Les devices sont des feuilles**, pas des comptages : chaque device
devient un nœud de type `"device"`, enfant du nœud de localisation le
plus profond qui le concerne, avec pour `raw` : `ip` (première IP
rencontrée), `systems` (tags `Systems`, découpés sur `|`, fusionnés
si le même device apparaît plusieurs fois pour la **même** Location),
et `roleGuess` (étiquette indicative — voir plus bas). Si le même
device apparaît sous une Location **différente** d'une ligne à
l'autre (`history` est un historique, pas un état unique — un
équipement peut avoir changé de site), il ressort comme deux nœuds
distincts plutôt que d'être fusionné : un déplacement réel n'est pas
une duplication à corriger.

**`roleGuess`** (`distribution`/`acces`/`radio`/`liaison_radio_FH`/
`onduleur`/`switch_elec_local`/`inconnu`) est une **heuristique de
nommage** (regex sur les conventions Cisco et préfixes observés sur ce
déploiement précis — `LOCATION_ROLE_HINTS` dans `zenoss/api/app.py`),
**pas une donnée de topologie réelle** : ce schéma ne contient aucune
table de routes, d'interfaces ou de voisinage (confirmé lors de
l'introspection — pas de table `IpInterface`/`IpRouteEntry`/CDP/LLDP
dans ce dump). À ajuster si un autre inventaire suit une convention de
nommage différente ; à ne jamais présenter côté front comme une
certitude.

**Filtre optionnel** `?ip_prefix=192.168.` sur les deux routes (ex.
pour se limiter à un plan d'adressage précis, comme la requête
d'origine `WHERE ipAddress LIKE '192.168.%'`) — absent par défaut
(aucun filtre, tout `history` est lu).

**Pas de fenêtre temporelle** sur ce mode (contrairement à la
classification) : `Location`/`Systems`/`ipAddress` ne sont pas
horodatées par ligne dans le besoin exprimé — simplification
délibérée pour cette v1, le curseur temporel n'apparaît donc pas dans
ce mode (`dateBounds` toujours `null`).

**Cascade façon traceroute — hors de portée avec ce schéma** : la
hiérarchie de localisation n'est PAS un graphe de dépendance réseau
(qui uplinke vers qui). Ce schéma ne contient aucune donnée
permettant de la reconstruire automatiquement ; le catalogue complet
des équipements et leurs relations réelles vivent dans la ZODB de
Zenoss (Zope Object Database), hors de cette base MySQL "events" —
confirmé pour ce schéma lors de l'introspection (aucune table
interface/route/voisinage), et cohérent avec le connecteur legacy
Zenoss 2.5.2 du projet (`connectors/zenoss_legacy/`), qui fait le même
constat pour une version antérieure du produit.

## Dépannage

**`cryptography package is required for sha256_password or
caching_sha2_password auth methods`** : voir `ipam/README.md` (même
cause, même correctif — `requirements.txt` déjà à jour, reconstruire
l'image suffit : `docker compose build zenoss-api`).

## Vérifié depuis cet environnement / non vérifié

**Vérifié** : la reconstruction de l'arbre depuis des chemins texte
(normalisation, nœuds intermédiaires ayant leurs propres comptages,
chemin présent seulement en historique, racine isolée), la fenêtre
temporelle (`collect_class_paths`, requêtes fenêtrées et bornes
`UNION ALL` vérifiées via un curseur factice qui capture le SQL
généré), la corrélation Fusion IP/MAC (`build_ip_activity_entries`
— regroupement par (ip, device), sévérité max correctement retenue
sur plusieurs lignes, comptage historique rattaché sans erreur si
absent), et l'inventaire physique (`build_location_tree` —
normalisation de `Location`, fusion des tags `Systems` pour un même
(device, Location), non-fusion d'un même device sous deux `Location`
différentes, panier "Sans localisation", heuristique `roleGuess`,
comptages cumulés via `count_location_descendants`, filtre
`ip_prefix`, routes `/location_roots`/`/location_tree` avec connexion
DB simulée en échec) — 62 tests Python (40 existants, non-régression
confirmée + 22 nouveaux). Côté front : 16 tests Node existants
(filtrage, fil d'ariane, sévérité dominante pour la coloration,
coloration JSON, formatage de dates — tous réutilisés tels quels par
le mode Localisation, aucun n'étant spécifique à la classification) ;
contrôle croisé classes CSS ↔ classes réellement utilisées ; diff
structurel ligne à ligne de `ZenossLocationTree.jsx` contre
`ZenossRadialTree.jsx` (déjà vérifié) pour limiter le risque d'erreur
de syntaxe sur le nouveau composant.

**Non vérifié** : aucune connexion MySQL réelle (ni réseau ni serveur
disponibles ici) — même limite que pour IPAM/Optick. Le comportement
réel du curseur en glissement n'a pas non plus pu être vérifié en
navigateur. **Syntaxe JSX des fichiers frontend modifiés/créés
(`ZenossApp.jsx`, `ZenossLocationTree.jsx`, `ZenossJsonPanel.jsx`,
`zenossApi.js`) non validée par un compilateur réel** (pas d'accès
réseau pour installer les outils de build ici) — contrairement aux
sessions précédentes qui avaient pu s'appuyer sur "la syntaxe validée
par le compilateur", cette vérification-là reste à faire à votre
premier `docker compose build frontend`. Le volume réel de
l'inventaire physique (nombre de devices/Locations distincts sur la
base complète, sans filtre `ip_prefix`) n'a pas pu être mesuré non
plus. Premier geste utile une fois branché :
`curl http://localhost:6108/health`, puis
`curl http://localhost:6108/location_roots`.

## Nouvelle route : localisation d'un équipement précis (livraison #268)

`GET /device_location` (`device` ou `ip`, requête ciblée directement
sur les colonnes déjà utilisées par `/location_roots`/`/location_tree`
-- jamais un parcours de l'arbre complet) -- demandé pour permettre à
`architecture-api` (#253) de répondre à "les lieux d'intervention"
sans devoir reconstruire/mettre en cache tout l'arbre de localisation
côté ce nouveau module. `result: null` (jamais un 404) si
l'équipement n'apparaît dans aucun événement connu -- normal, pas une
erreur de recherche. Voir `architecture/README.md` pour le
raisonnement complet côté appelant.

**Vérifié réellement** : recherche par nom, par IP, aucun résultat,
base injoignable -- testés en profondeur avec un cursor MySQL simulé
(vraie connexion toujours impossible dans cet environnement, réseau
restreint, même réserve que le reste de ce module).
