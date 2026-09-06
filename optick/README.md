# Optick — onglet de visualisation (lecture seule)

Même principe que l'onglet IPAM (`ipam/README.md`), appliqué à
l'outil de gestion de tickets interne existant **optick** : **racines
indépendantes** (familles de catégories) à gauche, **arbre radial**
(familles → catégories) au centre, **fiche JSON** à droite.

## Ce que ce module NE fait PAS

Comme pour IPAM : il ne crée, ne modifie ni ne remplace rien
d'optick, il ne fait que lire sa base MySQL pour la visualiser. Mêmes
trois niveaux de garantie de lecture seule (voir `ipam/README.md`
pour le détail) — en particulier, le compte MySQL utilisé doit
n'avoir que le privilège `SELECT` :

```sql
CREATE USER 'optick_readonly'@'%' IDENTIFIED BY 'un-mot-de-passe-dedie';
GRANT SELECT ON optick3.* TO 'optick_readonly'@'%';
FLUSH PRIVILEGES;
```

## Hiérarchie utilisée

Le schéma fourni organise les tickets en deux niveaux fixes :

- **`tts_parent_category`** (« familles ») — **racines indépendantes**
  (pas de nesting entre elles, toutes sont des racines).
- **`tts_category`** — rattachées à une famille via `id_parent`.
- **`tts_tickets`** — rattachés à une catégorie via `id_category`, mais
  **jamais affichés individuellement** dans l'arbre : leur volume réel
  rendrait un arbre radial illisible (même choix que pour les adresses
  IP côté IPAM). Chaque catégorie porte à la place un **comptage
  agrégé** (`ticketCount`, `openTicketCount` — tickets encore ouverts,
  `close_date = 0`), calculé en une seule requête groupée.

Contrairement à IPAM, il n'y a **aucun risque de cycle** dans ce
schéma (une catégorie ne peut être imbriquée que sous une famille, pas
sous une autre catégorie) — la logique d'assemblage est donc plus
simple, mais garde le même réflexe défensif : une catégorie dont
`id_parent` ne correspond à aucune famille existante est regroupée
sous une racine synthétique *« Catégories sans famille valide »*
plutôt que d'être perdue silencieusement.

**Résolution des domaines** : `domain_id` (colonne MySQL `SET`, ex.
`"1,3,5"`) est décodé et résolu en libellés via `tts_domains` — visible
dans la fiche JSON des familles et catégories, sans jointure SQL sur
un type SET (décodage fait côté Python).

**Tables jamais lues** : `tts_users` (comptes applicatifs), `tts_contacts`,
`tts_notes`, `tts_attachments`, `tts_notify`, `TTS_system`, et le
contenu individuel de `tts_tickets` (sujet, description) — seul le
comptage agrégé par catégorie est exposé.

## Variables `.env`

| Variable | Rôle | Défaut |
|---|---|---|
| `OPTICK_API_PORT` | port exposé du service | `6107` |
| `OPTICK_DB_HOST` | hôte MySQL d'optick | *(vide — à renseigner)* |
| `OPTICK_DB_PORT` | port MySQL | `3306` |
| `OPTICK_DB_NAME` | nom de la base | `optick3` |
| `OPTICK_DB_USER` / `OPTICK_DB_PASSWORD` | compte **lecture seule** | *(vide)* |
| `OPTICK_DB_SSL` | connexion chiffrée | `false` |
| `OPTICK_DB_CHARSET` | encodage de connexion — le dump fourni mélange `SET NAMES utf8` en tête et des colonnes `character set latin1` (base MySQL 5.0 ancienne) ; si les accents ressortent mal formés une fois branché, essayer `latin1` | `utf8` |
| `OPTICK_CACHE_TTL` | durée de cache (s), via le memcached déjà présent | `60` |

```bash
./scripts/run.sh up -d --build optick-api
```

## Fenêtre temporelle (timeline)

Un sélecteur à deux poignées indépendantes filtre `/tree` par
`open_date` — mais **contrairement à IPAM/OwnCloud, ce n'est pas un
filtrage visuel côté client**. Une catégorie n'est pas une entité
individuellement datée mais un agrégat de tickets : changer la
fenêtre déclenche donc un **recalcul côté serveur** des comptages
(`WHERE open_date BETWEEN ...`), débattu à 300ms côté front pour ne
pas déclencher une requête à chaque pixel de glissement
(`useDebouncedValue`, générique).

Sémantique retenue, à faire évoluer si le besoin réel diffère : un
ticket compte dans la fenêtre s'il a été **ouvert** pendant celle-ci
(`open_date`), pas s'il était simplement *actif* pendant la fenêtre
(ce qui inclurait des tickets ouverts avant mais toujours en cours) —
ce second calcul serait une jointure plus complexe
(`open_date <= end AND (close_date = 0 OR close_date >= start)`), pas
construite ici faute d'un besoin exprimé.

Les bornes du curseur (`dateBounds`, renvoyées par `/tree`) portent
sur **l'ensemble** des tickets de la racine consultée, indépendamment
de la fenêtre active — pour pouvoir toujours rouvrir le curseur après
l'avoir resserré. Sans fenêtre active, la réponse reste mise en cache
comme avant ; avec une fenêtre, jamais mise en cache (combinaisons non
bornées), toujours recalculée — les volumes de tickets en jeu restent
modestes, contrairement aux 2,5M lignes d'OwnCloud.

## Dépannage

**`cryptography package is required for sha256_password or
caching_sha2_password auth methods`** : voir `ipam/README.md` (même
cause, même correctif — `requirements.txt` déjà à jour, reconstruire
l'image suffit : `docker compose build optick-api`).

## Vérifié depuis cet environnement / non vérifié

**Vérifié** : la logique d'assemblage de l'arbre (`build_forest`,
décodage `domain_id`, comptage de descendants, gestion des
catégories orphelines), et la fenêtre temporelle (`collect_category_ids`,
requêtes SQL fenêtrées vérifiées via un curseur factice qui capture
le texte et les paramètres SQL générés, `fetch_date_bounds`) — 29
tests Python. Côté front : 19 tests Node sur la logique pure
(filtrage, fil d'ariane, taux de tickets ouverts, coloration JSON,
formatage de dates) ; syntaxe validée par le compilateur TypeScript ;
contrôle croisé exhaustif classes CSS ↔ classes réellement utilisées
par les composants (a détecté et corrigé un bug de nommage introduit
pendant la duplication du CSS depuis le module IPAM — les sélecteurs
`.optick-radial-node-family/category` et `.optick-load-*` ne
correspondaient pas encore aux classes émises par le composant avant
cette vérification).

**Non vérifié** : aucune connexion réelle à MySQL (ni réseau ni
serveur disponibles ici) — même limite que pour IPAM. Le rendu dans un
navigateur n'a pas non plus pu être testé, y compris le comportement
du curseur en glissement réel (débattu 300ms, vérifié par lecture du
code plutôt qu'en conditions réelles). Premier geste utile une
fois branché : `curl http://localhost:6107/health`, puis vérifier
que les caractères accentués des noms de familles/catégories
s'affichent correctement (sinon, essayer `OPTICK_DB_CHARSET=latin1`).
