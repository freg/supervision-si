# Recherche OwnCloud — proxy Elasticsearch en lecture seule

Onglet **Recherche** du frontend, assisté par ce service
(`owncloud-search-api`, port `6112`) qui interroge en lecture seule
l'Elasticsearch alimenté par l'app ownCloud
[`search_elastic`](https://github.com/owncloud/search_elastic)
— **externe à ce projet**, à mettre en place côté personne (voir
section "Mise en place du connecteur" plus bas).

## Pourquoi un service dédié plutôt qu'un appel direct du frontend vers Elasticsearch

Même principe de défense en profondeur que les autres modules
(`ipam/README.md` pour le détail) : le frontend ne parle jamais
directement à Elasticsearch. `/search` traduit une **spec structurée**
(`{field, operator, value}` + combinateur ET/OU) en requête DSL côté
serveur — **jamais de DSL Elasticsearch brut transmis depuis le
frontend**. Chaque champ est validé contre le mapping réel de l'index
avant traduction ; un champ inconnu est silencieusement ignoré, jamais
transmis tel quel. Les seuls opérateurs possibles sont
`contains`/`phrase`/`equals`/`exists`/`gte`/`lte` (voir
`ALLOWED_OPERATORS` dans `app.py`) — aucun type `script`/`script_score`
n'est atteignable par construction.

## Version Elasticsearch — point d'attention

`search_elastic` **requiert spécifiquement Elasticsearch 5.6.x** (6.x
non supporté par cette app, confirmé via sa documentation et l'image
Docker `extremeshok/docker-elasticsearch-owncloud` que vous avez
identifiée, qui embarque le plugin `ingest-attachment` — extraction de
texte via Apache Tika pour PDF/DOCX/XLSX/PPTX/ODT/ODS). C'est pour
cette raison que ce service utilise `requests` sur l'API REST HTTP
brute plutôt que le client Python officiel `elasticsearch` : ce client
exige une version majeure alignée avec le serveur, et un client récent
(8.x) casserait sur un serveur aussi ancien.

**Aucune donnée de l'index n'a pu être inspectée depuis cet
environnement** (pas d'accès réseau, l'index n'existe pas encore côté
personne au moment où ceci est écrit). Le schéma réel (noms de champs)
n'est **jamais supposé en dur** : `/mapping` interroge
`GET <index>/_mapping` sur Elasticsearch et le frontend construit son
sélecteur de champs à partir de cette réponse — s'adapte
automatiquement à ce que `search_elastic` indexe réellement,
`ingest-attachment` (extraction Tika) inclus.

`parse_mapping_response()` gère les deux formats de réponse
possibles : celui avec "mapping type" intermédiaire propre à
ES 5.x/6.x (`{mappings: {doc: {properties: {...}}}}`, la version
attendue ici) et le format sans type d'ES 7+ (`{mappings: {properties:
{...}}}`), sans supposer lequel avant d'avoir vraiment vu une réponse
réelle.

## Mise en place du connecteur

### Côté Elasticsearch — déjà prêt dans ce projet

Un service `elasticsearch` a été ajouté à `docker-compose.yml`
(`elasticsearch/Dockerfile` : image officielle
`docker.elastic.co/elasticsearch/elasticsearch:5.6.16` + plugin
`ingest-attachment` installé en `--batch`, seul pré-requis documenté
par `search_elastic`). Rien à configurer, juste à lancer :

```bash
docker compose build elasticsearch
docker compose up -d elasticsearch
# attendre le healthcheck (jusqu'a ~60s au demarrage) :
docker compose ps elasticsearch
curl http://localhost:9200/_cluster/health
```

`xpack.security.enabled=false` : réseau Docker interne uniquement,
jamais exposé publiquement — évite la complexité du mot de passe
`changeme` par défaut de l'image officielle pour un usage interne.
Données persistées dans le volume nommé `elasticsearch_data` (survit
aux redémarrages du conteneur).

**Non testé depuis cet environnement** (pas de Docker ici) : la
construction de l'image, le démarrage réel du conteneur, et
l'installation effective du plugin n'ont pas pu être vérifiés en
conditions réelles — seule la syntaxe (Dockerfile, YAML du
docker-compose validé avec PyYAML) a pu l'être. Si `vm.max_map_count`
sur la machine hôte est trop bas (`sysctl vm.max_map_count`),
Elasticsearch peut refuser de démarrer — limite connue et documentée
de ce type d'image, pas spécifique à ce projet ; augmenter avec
`sudo sysctl -w vm.max_map_count=262144` si besoin (voir la doc
Elastic officielle pour la persistance après redémarrage).

**Bug réel rencontré et corrigé (remonté par la personne, logs à
l'appui)** : `elasticsearch-1 | library initialization failed -
unable to allocate file descriptor table - out of memory` en boucle,
`exited with code 139` — **rien à voir avec la RAM disponible**
(doubler la RAM de la VM, 8 Go → 20 Go, n'avait rien changé, signal
cohérent avec la vraie cause). Le conteneur héritait du `ulimit
nofile` de l'hôte Docker (souvent `unlimited` selon la config
systemd de la machine) ; la JVM tente d'allouer une table de
descripteurs de fichiers dimensionnée pour cette limite au démarrage
et échoue immédiatement — avant même qu'Elasticsearch ne loggue quoi
que ce soit. Documenté sur de nombreuses images JVM en Docker
(Elasticsearch, Neo4j, Oracle, Kafka...), toujours la même cause,
toujours le même correctif : fixer explicitement `nofile` dans le
conteneur plutôt que d'hériter de l'hôte — ajouté dans
`docker-compose.yml` (`ulimits.nofile: soft/hard 65536`, à côté du
`memlock` déjà présent). Aucun rebuild nécessaire, juste :

```bash
docker compose up -d elasticsearch
docker compose logs -f elasticsearch   # doit demarrer normalement cette fois
```

### Côté ownCloud — hors de ce docker-compose, à faire sur votre serveur

**Ça, je ne peux pas l'exécuter à votre place** : votre instance
ownCloud est externe à ce projet (comme sa base MySQL déjà lue par
`owncloud/api`), je n'y ai aucun accès. Voici la procédure exacte
(tirée de la documentation officielle de `search_elastic`) :

```bash
# Sur le serveur ownCloud, PAS dans ce docker-compose :
cd /chemin/vers/owncloud/apps
git clone https://github.com/owncloud/search_elastic.git
cd search_elastic
composer install --no-dev
cd ../..
php occ app:enable search_elastic
```

Puis dans l'interface ownCloud : **Réglages → Admin → Recherche**.
Renseignez l'URL Elasticsearch — **attention, PAS la même valeur que
côté `owncloud-search-api`** : votre serveur ownCloud est hors du
réseau Docker de ce projet, il doit joindre l'instance par le **port
exposé sur l'hôte**, pas par le nom DNS interne :

```
http://<IP-de-la-machine-qui-fait-tourner-ce-docker-compose>:9200
```

(`http://elasticsearch:9200` ne résout QUE depuis les conteneurs de
CE projet — inutilisable depuis votre serveur ownCloud externe.)

Cliquez **"Setup index"**, notez le nom d'index qui apparaît, puis
lancez une première indexation (voir la doc `search_elastic` pour
`occ fulltextsearch:index` ou équivalent selon la version — hors
périmètre de ce service).

### Dernière étape — refermer la boucle côté ce projet

Une fois l'index créé et peuplé côté ownCloud, renseignez son nom
exact dans `.env` à la racine de CE projet :

```bash
ELASTICSEARCH_INDEX=nom_de_l_index_note_a_l_etape_precedente
docker compose up -d owncloud-search-api   # recharge la variable
curl http://localhost:6112/mapping          # doit lister les vrais champs
```

## Sécurité au-delà de la traduction de requête

- `size`/`from` bornés côté serveur (`MAX_RESULT_SIZE=100`), quelle
  que soit la valeur demandée par le frontend.
- Nombre de clauses par requête plafonné (`MAX_CLAUSES=20`).
- Résultat renvoyé au frontend : uniquement `_id`/`_score`/`_source`/
  `highlight` tels que renvoyés par Elasticsearch — ce service
  n'ajoute ni ne filtre aucun champ (c'est `search_elastic`, pas ce
  proxy, qui décide de ce qui est indexé et donc de ce qui peut
  apparaître dans un résultat).
- Côté frontend, les fragments de highlight (qui contiennent du texte
  extrait de documents totalement non fiables — PDF/Word arbitraires)
  ne sont **jamais rendus via `dangerouslySetInnerHTML`**.
  `parseHighlightFragment()` (`searchLib.js`) découpe le fragment sur
  les seuls délimiteurs `<em>`/`</em>` connus (ceux par défaut
  d'Elasticsearch) et rend chaque morceau comme texte React normal
  (échappé automatiquement) — un `<script>` ou toute autre balise
  présente dans le contenu réel d'un document reste un texte inerte,
  jamais interprété par le navigateur. Testé explicitement (voir
  `test_searchLib.mjs`, cas "contenu malveillant").

## Vérifié depuis cet environnement / non vérifié

**Vérifié** : `parse_mapping_response` (formats ES 7+ et ES 5.x/6.x
avec type intermédiaire, alias/nom d'index différent, mapping
malformé), `build_query_clause`/`build_search_body` (chaque opérateur,
champ inconnu rejeté, opérateur inconnu rejeté — y compris un
garde-fou explicite qu'aucun opérateur autorisé ne contient jamais
"script" —, combinateur ET/OU, bornage taille, clauses invalides
silencieusement écartées sans faire échouer les valides),
`format_search_results` (format de `total` ancien et récent, résultat
malformé), routes `/health`/`/mapping`/`/search` (Elasticsearch
entièrement simulé, y compris la vérification que le corps JSON
réellement envoyé à `_search` correspond au DSL attendu) — 30 tests
Python. Côté front : `isClauseComplete`/`countCompleteClauses`,
`parseHighlightFragment` (y compris le cas de sécurité "contenu
malveillant" ci-dessus), `firstHighlightFragment` — 21 tests Node.

**Non vérifié** : aucune connexion Elasticsearch réelle — ni le
service `elasticsearch` de ce projet (jamais démarré depuis cet
environnement, voir la section dédiée plus haut) ni l'app
`search_elastic` côté ownCloud (pas encore installée côté personne au
moment où ceci est écrit). Le format exact du mapping réel une fois
`search_elastic` effectivement indexé n'a donc pas pu être observé —
seulement déduit de sa documentation. Premier geste utile une fois les
deux côtés branchés : `curl http://localhost:6112/mapping` pour voir
les champs réels, avant même d'utiliser l'onglet.
