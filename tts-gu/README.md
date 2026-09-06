# TTS-GU — onglet de visualisation (lecture seule)

Même principe qu'IPAM et Optick (`ipam/README.md`, `optick/README.md`),
appliqué à **tts-gu**, un clone/fork de l'outil de tickets interne
"optick3" dont le schéma a divergé au fil du temps : **racines
indépendantes** à gauche, **arbre radial** au centre, **fiche JSON** à
droite.

## Ce que ce module NE fait PAS

Même garantie de lecture seule à trois niveaux que les deux autres
modules (voir `ipam/README.md`) — en particulier, un compte MySQL
dédié à créer côté serveur avec uniquement `SELECT` :

```sql
CREATE USER 'ttsgu_readonly'@'%' IDENTIFIED BY 'un-mot-de-passe-dedie';
GRANT SELECT ON optick3.* TO 'ttsgu_readonly'@'%';
FLUSH PRIVILEGES;
```

(Le nom de la base reste `optick3` dans ce clone malgré le nom
"tts-gu" — c'est le nom d'hôte/instance, pas celui de la base.)

## Pourquoi ce module n'est PAS un simple clone du module Optick

Le dump fourni pour tts-gu a été comparé structurellement à celui
d'optick3 : **`tts_parent_category` a disparu et `tts_category` n'a
plus de colonne `id_parent`** — la catégorisation est ici à plat, sans
notion de famille. Le module Optick (racines = familles) ne peut donc
pas s'appliquer tel quel.

Hiérarchie retenue pour tts-gu : les **racines sont les domaines**
(`tts_domains`, ids uniques) plutôt que des familles qui n'existent
plus dans ce schéma — c'est le seul regroupement structurant encore
disponible. `tts_category.domain_id` reste une colonne `SET` (une
catégorie peut être taguée de **plusieurs** domaines) : chaque
catégorie apparaît alors sous **chaque** racine correspondante, avec
un comptage de tickets **propre à chaque domaine** (calculé via
`tts_tickets.domain_id`, qui est un entier simple et non ambigu,
contrairement au tag de la catégorie). Une catégorie dont aucun
domaine tagué ne correspond à un domaine connu est regroupée sous une
racine synthétique *« Catégories sans domaine valide »*, jamais
perdue silencieusement.

## Variables `.env`

| Variable | Rôle | Défaut |
|---|---|---|
| `TTSGU_API_PORT` | port exposé du service | `6109` |
| `TTSGU_DB_HOST` | hôte MySQL de tts-gu | *(vide — à renseigner)* |
| `TTSGU_DB_PORT` | port MySQL | `3306` |
| `TTSGU_DB_NAME` | nom de la base | `optick3` |
| `TTSGU_DB_USER` / `TTSGU_DB_PASSWORD` | compte **lecture seule** | *(vide)* |
| `TTSGU_DB_SSL` | connexion chiffrée | `false` |
| `TTSGU_DB_CHARSET` | encodage — même nuance latin1/utf8 que pour Optick, voir `optick/README.md` | `utf8` |
| `TTSGU_CACHE_TTL` | durée de cache (s) | `60` |

```bash
./scripts/run.sh up -d --build tts-gu-api
```

## Fenêtre temporelle (timeline)

Même principe qu'Optick (`optick/README.md`) : recalcul **côté
serveur** des comptages par catégorie sur `open_date`, débattu 300ms
côté front, non mis en cache quand une fenêtre est active.

Nuance propre à ce module : comme une catégorie peut apparaître sous
**plusieurs** racines (domaines), les bornes du curseur (`dateBounds`)
sont scopées au domaine consulté — `WHERE id_category IN (...) AND
domain_id = <ce domaine>` — sauf pour la racine synthétique
`_orphans`, où elles restent non scopées (cohérent avec
`fetch_ticket_totals`, qui agrège tous domaines confondus pour les
catégories orphelines).

## Dépannage

**`cryptography package is required for sha256_password or
caching_sha2_password auth methods`** : voir `ipam/README.md` (même
cause, même correctif — `requirements.txt` déjà à jour, reconstruire
l'image suffit : `docker compose build tts-gu-api`).

## Vérifié depuis cet environnement / non vérifié

**Vérifié** : la logique d'assemblage (`build_forest`) avec un
focus particulier sur le cas propre à ce schéma — une catégorie taguée
de plusieurs domaines apparaît bien sous chaque racine avec des
comptages de tickets distincts et non partagés par erreur entre les
occurrences ; catégories orphelines, domaines sans catégorie, forêt
vide ; et la fenêtre temporelle (requêtes fenêtrées et bornes scopées
par domaine vs non scopées pour `_orphans`, vérifiées via un curseur
factice qui capture le SQL généré) — 32 tests Python. Côté front : 18
tests Node sur la logique pure ; syntaxe validée par le compilateur ;
contrôle croisé exhaustif classes CSS ↔ classes des composants.

**Non vérifié** : aucune connexion MySQL réelle (même limite que les
deux autres modules). Le comportement réel du curseur en glissement
n'a pas non plus pu être vérifié en navigateur.

## Note sur le port 6109

Ce module a été développé pendant qu'un autre onglet ("Zenoss",
`zenoss/`) était ajouté en parallèle sur ce même projet et avait déjà
pris le port `6108` initialement prévu ici — `TTSGU_API_PORT` a donc
été fixé à `6109` pour éviter toute collision. Si ce nom de variable
ou ce port a été modifié depuis par ailleurs, `docker compose config`
confirmera l'affectation réellement active.
