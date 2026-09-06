# IPAM — onglet de visualisation (lecture seule)

Nouvel onglet du frontend principal : **racines indépendantes** à
gauche, **arbre radial** au centre, **fiche JSON** du nœud sélectionné
à droite — construits à partir de la base MySQL de ton **application
phpipam existante**.

## Ce que ce module NE fait PAS

Il ne crée, ne modifie ni ne remplace rien de phpipam. Il se contente
de **lire** sa base pour la mettre en forme visuellement. Trois
niveaux de garantie que `ipam-api` reste strictement lecture seule :

1. Aucune route `POST`/`PUT`/`DELETE` n'existe dans `ipam/api/app.py`.
2. Chaque requête passe par `run_select()`, qui refuse tout texte ne
   commençant pas par `SELECT`.
3. **La vraie garantie doit venir du serveur MySQL** : le compte utilisé
   doit n'avoir que le privilège `SELECT`, jamais un compte applicatif
   complet de phpipam. Exemple, à exécuter sur le serveur MySQL de
   phpipam :

   ```sql
   CREATE USER 'ipam_readonly'@'%' IDENTIFIED BY 'un-mot-de-passe-dedie';
   GRANT SELECT ON phpipam.* TO 'ipam_readonly'@'%';
   FLUSH PRIVILEGES;
   ```

   (Restreindre l'hôte `'%'` à l'IP du serveur qui exécutera `ipam-api`
   si possible.)

## Hiérarchie utilisée

phpipam organise déjà les données en arbre à deux niveaux emboîtés :

- **`sections`** — nichées entre elles via `masterSection` (0 = section
  de tête = **racine indépendante**, celles listées à gauche).
- **`subnets`** — nichés entre eux via `masterSubnetId` (0 = rattaché
  directement à sa section), chaque subnet portant sa `sectionId`.

`ipam-api` assemble les deux en un seul arbre par racine, avec deux
enrichissements à peu de frais : le **nombre d'IP utilisées** par
subnet (`ipaddresses` groupé par `subnetId`, une seule requête) et la
résolution `vlanId`/`vrfId` → nom (jointures simples). Les tables
d'authentification et de configuration de phpipam (`users`,
`settings*`, `api`, `loginAttempts`...) ainsi que la colonne
`permissions` (ACL JSON interne) ne sont **jamais lues**.

## Variables `.env`

| Variable | Rôle | Défaut |
|---|---|---|
| `IPAM_API_PORT` | port exposé du service | `6106` |
| `IPAM_DB_HOST` | hôte MySQL de phpipam | *(vide — à renseigner)* |
| `IPAM_DB_PORT` | port MySQL | `3306` |
| `IPAM_DB_NAME` | nom de la base | `phpipam` |
| `IPAM_DB_USER` / `IPAM_DB_PASSWORD` | compte **lecture seule** (voir GRANT ci-dessus) | *(vide)* |
| `IPAM_DB_SSL` | connexion chiffrée | `false` |
| `IPAM_CACHE_TTL` | durée de cache (s) des résultats, via le memcached déjà présent | `60` |

```bash
./scripts/run.sh up -d --build ipam-api
```

L'onglet apparaît dans le frontend principal dès que `ipam-api`
répond ; un bandeau s'affiche dans l'onglet si la base est injoignable
ou non configurée (`/health`), sans faire planter le reste du
frontend.

## Défensif face à des données réelles imparfaites

Une vraie base phpipam en production peut contenir des incohérences
(parent supprimé, boucle accidentelle). `build_forest()` ne perd
jamais un nœud silencieusement :
- un `masterSection`/`masterSubnetId` pointant vers un id inexistant
  → le nœud redevient racine ;
- un cycle (A parent de B parent de A) → détecté et coupé, le nœud qui
  romprait le cycle est marqué `"cycle": true` dans sa fiche JSON ;
- un subnet dont la `sectionId` ne correspond à aucune section
  → regroupé sous une racine synthétique *« Sous-réseaux sans section
  valide »*, plutôt que d'être ignoré.

## Fenêtre temporelle (timeline)

Un sélecteur à deux poignées indépendantes (début/fin), au-dessus de
l'arbre, filtre par `editDate` (sections et subnets portent tous deux
cette colonne). **Filtrage purement côté client** : l'arbre d'une
racine est déjà chargé intégralement en un seul appel (contrairement
à OwnCloud), donc élargir ou resserrer la fenêtre ne déclenche aucune
requête réseau — seul l'affichage (nœuds estompés) change.

Même réflexe de conception que pour OwnCloud (`owncloud/README.md`) :
une section dont le *propre* `editDate` tombe dans la fenêtre ne fait
**pas** remonter ses subnets si ceux-ci ont un `editDate` hors
fenêtre — la date de modification d'une section n'est qu'une
conséquence mécanique du dernier changement en son sein, pas un
regroupement voulu. Seuls les ancêtres d'un nœud qui matche restent
visibles, pour situer où il se trouve.

Se combine avec la recherche texte par intersection.

**Bouton "⤵ Réduire à la sélection"** (à côté de "↺ Toute la
période", visible dès qu'une fenêtre temporelle est active) : bascule
entre estomper (comportement par défaut ci-dessus) et **retirer**
vraiment les nœuds hors sélection — même mécanique que "actifs
seulement" juste en dessous, mais appliquée à `relevantIds` plutôt
qu'à `state`. Ne duplique rien : réutilise directement `pruneToRelevant`
et le `frozenPreview` déjà calculés pour "Figer cette vue comme
source" (voir plus bas) — un simple changement de ce qui est passé à
`IpamRadialTree` (arbre élagué au lieu de l'arbre complet estompé),
pas un nouveau calcul. Reste réactif au curseur temporel (et à la
recherche texte, si active) : ce n'est pas un instantané figé comme
"Figer cette vue", juste un mode d'affichage différent du même filtre
déjà en place. Se désactive automatiquement si la fenêtre temporelle
est effacée, pour ne jamais laisser un état "réduit" sans justification.

## Zoom avec point focal (molette, clic droit)

Sur l'arbre radial : molette (haut = avant, bas = arrière), clic droit
seul = zoom avant, Ctrl/Cmd+clic droit = zoom arrière — même
convention Ctrl/Cmd que `CoordinateTool` dans `MapPanel.jsx`, pour
rester cohérent avec le reste du projet plutôt que d'inventer un
geste différent. Bouton "⟲ 100%" en haut à droite dès que le zoom
n'est pas à son niveau par défaut.

**"Avec point focal"** : le point sous le curseur reste visuellement
fixe pendant le zoom (le reste de l'arbre se rapproche/s'éloigne de
lui) — pas un zoom générique centré sur l'origine. Calcul isolé dans
une fonction pure (`computeZoomTransform`, `frontend/src/lib/
svgZoom.js`), testée directement contre cette propriété (un point
donné retombe exactement au même endroit après transformation, à
10⁻⁹ près) plutôt que seulement contre le calcul en confiance — 15
tests Node, y compris la saturation aux bornes de zoom (jamais de
dérapage cumulatif de la position une fois la limite atteinte, un
piège classique de ce genre de calcul si on continue à utiliser le
facteur demandé au lieu du facteur réellement appliqué après bornage).

Écouteur de molette posé nativement (`addEventListener("wheel", ...,
{ passive: false })`) plutôt que via la prop `onWheel` de React — pour
garantir que `preventDefault()` bloque bien le défilement de page
pendant qu'on zoome, indépendamment de la façon dont React pose ses
propres écouteurs par ailleurs.

Le zoom se réinitialise au changement de **racine** (nouvel arbre
choisi à gauche), mais **pas** en basculant "réduire à la sélection"
ci-dessus ou en ajustant le curseur temporel — uniquement suivi via
l'id de la racine, pas la référence de l'arbre affiché, pour ne pas
perdre le cadrage choisi à chaque ajustement mineur du filtre.

## Arbre non rémanent ("actifs seulement")

Une case à cocher au-dessus de l'arbre bascule entre la vue habituelle
(tout) et une vue élaguée ne montrant que les subnets actifs
(`subnets.state === 1`, convention phpipam : 0=hors ligne,
1=en ligne/actif, 2=non surveillé). Contrairement aux filtres
texte/temporel (qui estompent), cette bascule **retire** vraiment les
nœuds inactifs de l'arbre — géométrie du rendu radial recalculée sur
un arbre réellement plus petit. Une section qui devient vide après
élagage disparaît aussi, sauf la racine elle-même (toujours visible,
même vide, puisque c'est le point d'entrée choisi).

## Panneau d'aperçu sur l'onglet Supervision

`GET /stats` (comptages globaux : sections, subnets par état) est
appelé **directement depuis le navigateur** par un petit panneau du
premier onglet (Supervision SI, colonne synthèse) — aucun import,
aucune copie de données, aucun passage par le service `api` principal.
C'est littéralement le même service que celui utilisé par l'onglet
IPAM, juste une requête HTTP de plus vers la même URL déjà exposée en
CORS (`VITE_IPAM_API_BASE_URL`). Composant : `IpamOverviewPanel.jsx`.

## Figer une vue comme source (photo à l'instant T)

Le bouton « 📸 Figer cette vue comme source » réduit l'arbre affiché
(élagage "actifs seulement" + recherche + fenêtre temporelle
confondus, via `pruneToRelevant`) et l'enregistre comme une source
JSON ordinaire de l'onglet Supervision, en réutilisant **le mécanisme
d'injection déjà existant** (`ingestSource`, le même que le bouton
"➕ Injecter" du panneau de gauche) — pas un nouveau système parallèle.

C'est une **photo figée**, pas une vue vivante : une fois enregistrée,
elle ne se remet jamais à jour toute seule, exactement comme un
fichier importé à la main. Pour une vue actualisée, il suffit de
refaire "Figer" avec les nouveaux réglages (nom généré automatiquement
avec horodatage, jamais de collision). Nom du fichier :
`ipam_<racine>_<horodatage>`.

## Fusion IP/MAC

`GET /ip_list` expose les adresses individuelles connues (ip, mac,
nom d'hôte, contexte subnet — colonnes volontairement restreintes :
ni `owner`, ni `note` texte libre, ni les champs d'administration
système). Consommé par l'onglet **Fusion IP/MAC**, qui corrèle ces
entrées avec celles d'autres sources (actuellement Zenoss)
**côté navigateur**, par simple égalité d'IP — aucun service
intermédiaire, aucune donnée dupliquée en base.

**Point de vigilance non résolu ici** : phpipam a historiquement
stocké `ipaddresses.ip_addr` soit en notation pointée
(`"10.0.0.1"`), soit en entier décimal encodant l'IPv4 sur 32 bits
(`"167772161"`), selon la version — **jamais vérifié en conditions
réelles depuis cet environnement**. `normalize_ip_addr()` détecte et
convertit les deux formats vers la notation pointée ; une valeur qui
ne correspond à aucun des deux (IPv6, valeur corrompue) est renvoyée
telle quelle plutôt que de planter — elle ne participera simplement
pas à la corrélation. Premier geste utile une fois branché : vérifier
que les IP affichées dans `/ip_list` ont un sens (notation pointée
plausible), pas des grands nombres bruts.

## Dépannage

**`cryptography package is required for sha256_password or
caching_sha2_password auth methods`** : MySQL 8+ et les MariaDB
récents utilisent `caching_sha2_password` par défaut — `pymysql` a
besoin du paquet `cryptography` en plus pour cette méthode
d'authentification, absent du `requirements.txt` initial. Corrigé
(présent désormais) ; pour une instance déjà construite, reconstruire
l'image suffit :

```bash
docker compose build ipam-api && docker compose up -d ipam-api
```

**Bug réel trouvé et corrigé (remonté par la personne, capture
d'écran de l'onglet Fusion IP/MAC à l'appui)** : la colonne "Subnet"
affichait `175374352/28` au lieu de `10.116.0.16/28`. `subnets.subnet`
côté phpipam est stocké en entier 32 bits (convention `INET_ATON`) —
exactement le même risque déjà anticipé et géré pour
`ipaddresses.ip_addr` par `normalize_ip_addr` (voir juste au-dessus,
"décimal et notation pointée"), mais **jamais étendu au champ
`subnet`**, ni dans `build_forest` (arbre principal IPAM) ni dans
`build_ip_entries` (`/ip_list`, Fusion IP/MAC) — les deux étaient
concernés. Calcul vérifié précisément contre les 3 lignes réelles de
la capture (`175374352` = `10.116.0.16`, borne du `/28` contenant
`10.116.0.23` ; `175374408` = `10.116.0.72` ; `175374448` =
`10.116.0.112`). Corrigé via `format_subnet_address()`, appliqué aux
deux points d'usage — 10 tests Python, dont les 3 valeurs exactes de
la capture. Reconstruire suffit, même commande que ci-dessus.

## Vérifié depuis cet environnement / non vérifié

**Vérifié** : la logique d'assemblage de l'arbre (`build_forest`,
comptage de descendants, coupe de cycles, gestion des orphelins), la
conversion `datetime`→epoch d'`editDate`, le résumé d'états
(`summarize_subnet_states`), la normalisation IP/MAC
(`normalize_ip_addr`, `normalize_mac`, `build_ip_entries` — décimal
et notation pointée, formats de MAC variés, valeurs hors format
jamais perdues), et désormais `format_subnet_address` (valeurs
décimales réelles converties correctement, chaîne déjà formatée
laissée intacte, valeur hors plage IPv4 dégradée sur sa représentation
brute plutôt que de planter) — 60 tests Python (50 existants + 10
nouveaux). Côté front : 59 tests Node sur la logique pure (filtrage de
l'arbre par recherche, fenêtre temporelle avec propagation
ancêtres-seulement, élagage "actifs seulement", fil d'ariane, calcul
de taux d'occupation, coloration JSON), et désormais `computeZoomTransform`
(point focal exactement fixe après transformation, saturation aux
bornes sans dérapage cumulatif — 15 tests, `frontend/src/lib/svgZoom.js`)
— 74 tests Node (59 existants + 15 nouveaux) ; syntaxe de tous les
fichiers `.jsx`/`.js` validée par le compilateur TypeScript.

**Non vérifié** : aucune connexion réelle à MySQL n'a pu être testée
depuis cet environnement (ni réseau, ni serveur MySQL disponibles ici)
— `pymysql` sera installé normalement par `requirements.txt` au build
Docker, mais le chemin `get_connection()` → `pymysql.connect(...)`
n'a été exercé qu'à travers un bouchon de test qui vérifie seulement
que le module s'importe, jamais une vraie requête. Le rendu du
frontend dans un navigateur n'a pas non plus pu être vérifié
(`npm install` impossible ici) — en particulier le zoom molette/clic
droit et le bouton "réduire à la sélection", qui reposent sur de vrais
événements DOM (`getScreenCTM`, `wheel`, `contextmenu`) jamais
exercés en dehors de leur logique de calcul pure. Premier geste utile
une fois branché réellement : `curl http://localhost:6106/health`.
