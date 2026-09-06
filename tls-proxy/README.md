# Proxy TLS (`tls-proxy/`) — entrée unique pour toute la plateforme

**Depuis la livraison #135, le service `tls-proxy` (avec `keycloak` et
`keycloak-backup`) vit dans `gateway/docker-compose.yml`, un stack
Docker SÉPARÉ du reste de la plateforme — voir `gateway/README.md`
pour le raisonnement complet. Tout ce qui suit ici (schéma de chemins,
résolution DNS dynamique, génération de la config) reste inchangé --
seul l'EMPLACEMENT du service a changé.**

Un seul conteneur nginx (image officielle, aucun `Dockerfile`), qui
termine le TLS sur **un seul port public** (`GATEWAY_PORT`, défaut
`6443`) et route en interne par **chemin** vers les 15 services de la
plateforme — 11 APIs Flask, 3 fronts React, Keycloak.

## Comment on en est arrivé là

Décidé en cours de session, en deux temps :
1. D'abord un port public par service (15 ports) — fonctionnel,
   testé, mais Apache (le vrai point d'entrée réseau) aurait eu besoin
   de 15 `VirtualHost`.
2. La personne a proposé une entrée unique côté Docker plutôt que 15
   ports à gérer côté bordure réseau — décision actée, ce README
   documente l'architecture qui en résulte. L'ancien schéma à 15 ports
   reste consultable dans l'historique git si besoin d'y revenir.

## Schéma de chemins

| Chemin | Service | Type |
|---|---|---|
| `/` | `hub` | SPA (Vite) |
| `/app/` | `frontend` (Supervision SI) | SPA (Vite) |
| `/tickets/` | `tickets-portal` | SPA (Vite) |
| `/auth/` | `keycloak` | Keycloak |
| `/api/supervision/` | `api` | API Flask |
| `/api/pixel-grid/` | `pixel-grid-api` | API Flask |
| `/api/tickets/` | `tickets-api` | API Flask |
| `/api/ipam/` | `ipam-api` | API Flask |
| `/api/optick/` | `optick-api` | API Flask |
| `/api/zenoss/` | `zenoss-api` | API Flask |
| `/api/tts-gu/` | `tts-gu-api` | API Flask |
| `/api/owncloud/` | `owncloud-api` | API Flask |
| `/api/cacti/` | `cacti-api` | API Flask |
| `/api/owncloud-search/` | `owncloud-search-api` | API Flask |
| `/api/geo-import/` | `geo-import-api` | API Flask |

Généré par `render_nginx_conf.py` (liste `SERVICES` dans le script —
modifier là, jamais `generated/services.conf` à la main).

## Deux comportements de proxy différents — important pour ne pas casser en modifiant

**APIs Flask** : le préfixe est **retiré** avant transmission
(`proxy_pass http://service:port/;` — le `/` final compte). Le
backend ne voit jamais `/api/ipam/`, seulement ce qui suit — cohérent
avec des routes Flask écrites `/health`, `/subnets`, etc., sans aucune
notion de préfixe.

**SPA (Vite) et Keycloak** : le préfixe est **conservé**
(`proxy_pass http://service:port;` — pas de `/` final). Ces
services doivent connaître leur propre préfixe de leur côté pour
générer des URLs cohérentes :
- Vite : option `base` dans chaque `vite.config.js`
  (`frontend/`, `hub/`, `tickets/portal/`) — déjà réglée
  (`/app/`, `/`, `/tickets/` respectivement).
- Keycloak : `KC_HTTP_RELATIVE_PATH=/auth/` (`docker-compose.yml`).
  **Bug réel rencontré et corrigé en testant** : Keycloak derrière un
  proxy ne déduit pas tout seul son adresse publique — sans
  `KC_HOSTNAME`/`KC_PROXY_HEADERS`, il génère ses URLs de redirection
  (`AuthorizationCode` etc.) à partir de la connexion interne qu'il
  voit (HTTP simple, port du conteneur), pas de ce que voit
  réellement le navigateur. Observé concrètement : redirection vers
  `http://<ip>/auth/...` (sans port, en HTTP) au lieu de
  `https://<ip>:6443/auth/...`. Corrigé via `KC_HOSTNAME` (adresse
  publique complète et explicite, construite dynamiquement depuis
  `HOST_IP`/`GATEWAY_PORT`), `KC_PROXY_HEADERS=xforwarded` (fait
  confiance aux en-têtes `X-Forwarded-*` que nginx transmet déjà),
  `KC_HTTP_ENABLED=true` et `KC_HOSTNAME_STRICT=false`.
- **`redirect_uri` — second bug réel, rencontré une fois le précédent
  corrigé** : `window.location.origin` en JavaScript ne contient
  JAMAIS de chemin (juste schéma+hôte+port), quelle que soit la page.
  Pour le hub (racine `/`) : `redirect_uri` envoyé sans `/` final,
  incompatible avec le motif Keycloak `.../*` qui exige un `/` avant
  le reste — `Paramètre invalide : redirect_uri`. Pour le portail
  tickets (sous `/tickets/`) : écart plus large encore, `origin` seul
  omettait le préfixe entièrement. Corrigé des deux côtés :
  `hub/src/authConfig.js`/`tickets/portal/src/authConfig.js`
  construisent désormais explicitement `${origin}/` et
  `${origin}/tickets/` respectivement (jamais `origin` nu) ; en plus,
  côté Keycloak, `redirectUris` inclut maintenant l'origine exacte
  (sans wildcard) en plus du motif `/*`, en défense en profondeur.

## ⚠️ Partie la plus fragile de cette architecture — non vérifiée en conditions réelles

Le relais d'API Flask est un schéma nginx extrêmement standard, peu
de risque. **Les 3 SPA Vite et Keycloak sont une autre histoire** :
- Le HMR (rechargement à chaud) de Vite passe par une connexion
  **WebSocket** qui doit, elle aussi, survivre à la fois au préfixe de
  chemin et à la terminaison TLS en amont. Chaque `vite.config.js`
  déclare `server.hmr.protocol: "wss"` et `clientPort: GATEWAY_PORT`
  (lu depuis `process.env.GATEWAY_PORT`, jamais codé en dur) pour que
  le client HMR sache où reconnecter son WebSocket à travers le proxy
  — configuration standard documentée par Vite pour ce cas de figure,
  mais **jamais testée avec un vrai navigateur ici**.
- `KC_HTTP_RELATIVE_PATH` est une fonctionnalité Keycloak réelle et
  documentée, mais également jamais exercée en conditions réelles
  depuis cet environnement.

**Premier test à faire, avant tout le reste** : ouvrir le hub
(`https://<host>:6443/`), vérifier que la page se charge correctement
(pas d'erreur 404 sur des assets JS/CSS — signe que `base` n'est pas
bien pris en compte), puis tenter une vraie connexion Keycloak
(`/auth/`) de bout en bout. Si le HMR Vite pose problème en
développement actif (rechargement à chaud qui ne fonctionne plus),
c'est cette configuration `server.hmr` qu'il faut revisiter en premier
— l'application reste utilisable sans HMR (rechargement manuel de la
page), ce n'est qu'un confort de développement, pas une panne
bloquante.

## Lancement

Automatique via `./scripts/run.sh up -d --build` (config régénérée
avant chaque `docker compose`, comme le realm Keycloak). À la main :
```bash
python3 tls-proxy/render_nginx_conf.py
docker compose up -d --build tls-proxy
```

## Déboguer un service précisément

Les 15 services ne publient plus leur port sur l'hôte — seul
`tls-proxy` le fait, sur `GATEWAY_PORT`. Pour cibler un backend
directement sans passer par nginx :
```bash
docker compose exec ipam-api curl http://localhost:5000/health
```
Ou via nginx, avec le bon chemin :
```bash
curl -k https://localhost:6443/api/ipam/health
```
(`-k` : ignore la vérification de certificat, utile sans avoir
installé la CA — voir `pki/README.md`.)

## Résolution DNS dynamique (livraison #134) — prérequis à la séparation Keycloak/tls-proxy

Changement DÉLIBÉRÉ, demandé par la personne comme prérequis à un
chantier plus large (backlog : sortir Keycloak + `tls-proxy` du stack
principal vers un cycle de vie indépendant, pour qu'une application
externe -- trb140-sms-relay -- dépendant de Keycloak ne subisse plus
les redémarrages fréquents du reste du stack).

**Le problème réel, rencontré DEUX fois dans ce projet** : un
`proxy_pass http://service:port;` LITTÉRAL force nginx à résoudre le
nom UNE SEULE FOIS, au chargement de la config -- si UN SEUL des noms
référencés (aujourd'hui 22) n'est pas encore résolvable à cet instant
précis (conteneur pas encore créé, pas juste "pas prêt"), **nginx
refuse de démarrer ENTIÈREMENT**, pas seulement pour ce service.
Rencontré : l'incident du 2026-08-26 (dépendances manquantes dans
`depends_on`), et le bug `keycloak_admin.py` jamais copié dans l'image
`prefs-api` (livraison #125). Sortir Keycloak/tls-proxy dans leur
propre stack Compose aurait aggravé ce risque : `depends_on` ne
fonctionne pas entre deux fichiers `docker-compose.yml` distincts,
donc plus AUCUN ordre de démarrage garanti entre tls-proxy et les 21
services qu'il route.

**Corrigé à la racine** : résolution DYNAMIQUE, à la CONNEXION
(jamais au chargement) -- `resolver 127.0.0.11 valid=10s;` (résolveur
DNS interne de Docker, une seule fois au niveau du `server {}`) +
une VARIABLE dans chaque `proxy_pass` (`set $backend service:port;
proxy_pass http://$backend;`). nginx démarre désormais TOUJOURS, même
si un service référencé n'existe pas encore -- 502 le temps qu'il
apparaisse, jamais un refus de démarrer. Bénéfice : réduit ce risque
pour la configuration ACTUELLE (stack unique) aussi, pas seulement en
vue de la séparation à venir.

**Piège nginx identifié et compensé** : `proxy_pass` avec une
variable ne fait PLUS le retrait automatique de préfixe qu'un
`proxy_pass .../;` LITTÉRAL faisait (le "/" final ne joue ce rôle
qu'en écriture statique) -- sans compensation, les 15 APIs auraient
reçu leur propre préfixe (`/api/xxx/`) en plus de leurs routes
internes. Compensé par un `rewrite ^{path}(.*)$ /$1 break;` explicite,
ajouté UNIQUEMENT pour les locations de type "api" -- jamais pour
"spa"/"keycloak", qui veulent au contraire CONSERVER le préfixe
(comportement inchangé pour elles, aucun `rewrite` ajouté).

**`vault-standalone` a sa PROPRE copie séparée** de ce générateur
(`vault-standalone/tls-proxy/render_nginx_conf.py`, ~100 lignes,
routant vers 3 services seulement) -- **pas touchée ici**, hors
périmètre de cette demande, et risque nettement moindre dans ce
contexte (ses 3 services vivent dans le MÊME fichier Compose,
toujours démarrés ensemble). À reprendre séparément si un jour jugé
utile, pas oublié mais pas fait.

Vérifié réellement : syntaxe Python (`ast.parse`), génération réelle
du fichier (`render_nginx_conf.py`, sans `--check`) puis vérification
SYSTÉMATIQUE et EXHAUSTIVE du contenu généré pour les 22 services --
accolades équilibrées, `resolver` présent exactement une fois, chaque
location "api" (15) confirmée avec son `rewrite` exact ET l'absence
de tout `/` final résiduel sur `proxy_pass`, chaque location "spa"/
"keycloak" (7) confirmée SANS `rewrite` et avec les en-têtes WebSocket
toujours présents, aucun `proxy_pass` résiduel de l'ancien style
(host:port en dur). **Non vérifié dans cet environnement, faute de
binaire nginx installable ici (dépôts Ubuntu inaccessibles depuis ce
bac à sable, 403)** : la syntaxe nginx elle-même n'a JAMAIS été
validée par `nginx -t` ni par un nginx réellement démarré -- un test
`docker compose up -d --build tls-proxy` suivi d'un accès réel via
navigateur reste la première vraie validation à faire, avant de
poursuivre vers la séparation des stacks elle-même.

## Bug réel trouvé en production (livraison #136) — 500 systématique sur toutes les APIs

Rapporté par la personne, sur la version #134 : `GET
/api/<service>/logs` retournait un **500** (pas 502) sur les 11 APIs
Flask, de façon identique et simultanée. Un 500 (pas 502) signifiait
que nginx atteignait bien chaque backend -- le problème n'était donc
PAS "backend injoignable", mais "ce que nginx transmet au backend est
faux".

**Cause réelle** : `proxy_pass http://$backend;` -- une variable NUE,
sans rien après -- laisse une ambiguïté nginx documentée mais jamais
vérifiable ici faute de binaire nginx installable dans cet
environnement (dépôts Ubuntu bloqués, voir plus haut) : transmet-elle
`$uri` (reflète le `rewrite` qui retire le préfixe) ou `$request_uri`
(l'original, JAMAIS modifié, préfixe compris) ? En pratique :
`$request_uri` -- chaque API recevait donc son PROPRE préfixe
(`/api/supervision/logs`) en plus de ses routes internes (`/logs`),
une route que Flask ne connaît pas. Le `rewrite ... break;` (livraison
#134) n'avait donc servi à RIEN en pratique -- exactement le risque
que la docstring du module signalait déjà comme non vérifiable ici.

**Corrigé** : plus aucune ambiguïté à trancher sans pouvoir tester --
`proxy_pass http://$backend$uri$is_args$args;` explicite. `$uri`
reflète TOUJOURS les `rewrite` (c'est sa définition documentée, sans
détour possible) ; `$is_args`/`$args` sont le couple standard nginx
pour reconstruire la chaîne de requête. Appliqué aux DEUX types de
location (API et SPA/Keycloak), pas seulement celui qui plantait --
la même ambiguïté existait potentiellement aussi côté SPA/Keycloak,
juste invisible puisque `$uri`/`$request_uri` ne diffèrent JAMAIS
quand il n'y a aucun `rewrite` (le cas de ces locations).

Vérifié réellement : régénération du fichier, vérification
EXHAUSTIVE et systématique des 22 locations -- forme explicite
présente partout, plus AUCUNE occurrence de l'ancienne forme ambiguë
nulle part dans le fichier généré. **Toujours non vérifié dans cet
environnement** : la syntaxe nginx elle-même, ni le comportement réel
(nginx toujours pas installable ici). Cette fois, la correction élimine
l'ambiguïté elle-même plutôt que de trancher un pari sur son
interprétation -- `$uri`/`$is_args`/`$args` sont chacun documentés
sans équivoque, contrairement au comportement d'un `proxy_pass` à
variable nue.

**Ce correctif s'est avéré INSUFFISANT à lui seul** -- voir la
section suivante pour la vraie cause complète, restée cachée jusqu'à
obtenir une vraie trace nginx.

## Bug réel trouvé en production (livraison #146) — la vraie cause complète du 500

Le 500 a PERSISTÉ après #136, malgré un correctif juste et nécessaire
sur le fond. Deux tentatives de diagnostic à l'aveugle (#134, #136)
sans jamais pouvoir observer un vrai nginx tourner dans cet
environnement -- la personne a fini par fournir les VRAIES traces du
conteneur `tls-proxy` (`docker compose logs`), la seule preuve qui a
permis de trouver le vrai problème :

```
[warn] using uninitialized "backend" variable, ... request: "GET /api/prefs/health HTTP/1.1"
[error] no host in upstream "/health", ... request: "GET /api/prefs/health HTTP/1.1"
```

**Cause réelle** : dans `API_LOCATION_TEMPLATE`, `rewrite ^{path}(.*)$
/$1 break;` était placé AVANT `set $backend {service}:{container_port};`.
Or `break` interrompt tout le traitement des directives de la phase
de réécriture nginx pour cette requête -- pas seulement les `rewrite`
suivants, TOUTES les directives qui suivraient dans le même bloc, y
compris un `set`. Avec cet ordre, `set $backend` ne s'exécutait donc
JAMAIS -- `$backend` restait perpétuellement non initialisée,
`proxy_pass http://$backend$uri$is_args$args;` échouait
systématiquement (host vide dans l'URL cible) sur TOUTE route "api"
(15 sur 15), jamais "spa"/"keycloak" (`SPA_LOCATION_TEMPLATE`, sans
`rewrite` du tout -- son `set` a TOUJOURS été au bon endroit, depuis
le début). Explique entièrement, rétrospectivement, pourquoi le hub
et l'authentification Keycloak ont TOUJOURS fonctionné pendant toute
cette période, alors que chaque appel `/api/*` échouait sans
exception -- signalé dès le tout premier rapport de panne.

**Corrigé** : inversion simple de l'ordre -- `set` doit TOUJOURS
précéder `rewrite ... break;`, jamais le suivre. Piège nginx connu et
documenté (pas propre à ce projet) que les deux tentatives
précédentes n'avaient pas identifié, faute de pouvoir observer le
comportement réel d'un nginx en fonctionnement.

Vérifié réellement : régénération du fichier, vérification
EXHAUSTIVE et systématique des 15 locations "api" -- `set $backend`
confirmé AVANT `rewrite` dans chacune (position textuelle vérifiée
programmatiquement, pas une relecture visuelle), forme `proxy_pass`
explicite de #136 toujours présente. **Non vérifié dans cet
environnement, comme pour les deux tentatives précédentes** : le
comportement réel d'un vrai nginx (toujours pas installable ici) --
cette fois la correction s'appuie sur une preuve DIRECTE (les vraies
traces d'erreur du conteneur, pas une hypothèse depuis le code
source), mais reste à confirmer en conditions réelles par un nouveau
déploiement.

## Étape suivante — Apache (point d'entrée réseau, machine séparée)

Voir `apache/README.md` — devenu trivial avec cette architecture (un
seul `VirtualHost` à générer au lieu de 15).

## Vérifié depuis cet environnement / non vérifié

**Vérifié** : `render_nginx_conf.py --check` (15 chemins mappés,
détection de conflit de chemin), génération réelle de
`generated/services.conf` (15 `location` confirmés par comptage,
comportement retrait/conservation du préfixe confirmé par lecture
directe du fichier généré pour un exemple de chaque type), syntaxe
des 3 `vite.config.js` modifiés validée par `node --check`.

**Non vérifié** : aucun nginx, Vite ou navigateur réel disponible
dans cet environnement — le HMR à travers le préfixe/TLS, le
comportement réel de `KC_HTTP_RELATIVE_PATH`, et le chargement
correct des assets Vite avec `base` configuré n'ont jamais tourné en
conditions réelles. Voir la section "partie la plus fragile"
ci-dessus pour la marche à suivre en cas de souci.

## Résolution statique pour les services en `network_mode: host` (livraison #238)

Nouveau troisième `kind` dans `SERVICES` : `"api-static"`. Réservé
aux services qui ne sont PAS sur le réseau Docker partagé (typiquement
`network_mode: host`, voir `network-agent-api` dans
`../docker-compose.yml`, backlog item 20). Utilise
`API_LOCATION_TEMPLATE_STATIC` -- un `proxy_pass` LITTÉRAL (résolu au
chargement de la config via le résolveur système, qui consulte
`/etc/hosts`) au lieu du motif `set $backend` + `resolver 127.0.0.11`
utilisé par tous les autres services (`"api"`/`"spa"`/`"keycloak"`).

**Pourquoi ce troisième gabarit était nécessaire** (vérifié AVANT de
coder, pas après un échec) : le résolveur DYNAMIQUE de nginx
(`resolver 127.0.0.11`, le mécanisme conçu en #134/#146 pour que
nginx démarre même si un service référencé n'existe pas encore) ne
consulte JAMAIS `/etc/hosts` -- confirmé par la documentation nginx/
Docker et un incident réel équivalent chez un tiers
(nginx-proxy-manager#5344). Un `extra_hosts: host.docker.internal`
(voir `../gateway/docker-compose.yml`) serait donc resté SANS EFFET
avec le gabarit dynamique existant. Perdre la ré-résolution à chaud
(le service pourrait changer d'adresse sans reload de nginx) est un
compromis SANS RISQUE réel ici : la cible (l'hôte via
`host.docker.internal`) est toujours présente dès que Docker tourne
-- contrairement à un conteneur applicatif, jamais garanti prêt au
démarrage de nginx (raison d'être du gabarit dynamique pour tous les
autres services). Ce compromis n'est PAS généralisable à d'autres
routes sans le même raisonnement.

**Vérifié réellement** : configuration régénérée et inspectée --
`proxy_pass http://host.docker.internal:5000$uri$is_args$args;`
confirmé LITTÉRAL. Non-régression : les 30 autres routes gardent
leur résolution dynamique (`set $backend`) inchangée.

## Correctif : `host.docker.internal` ne fonctionne pas avec le résolveur dynamique (livraison #239)

**L'hypothèse de #238 était FAUSSE, corrigée par un vrai retour de
déploiement** : même un `proxy_pass` LITTÉRAL (`API_LOCATION_TEMPLATE_STATIC`)
passe par `resolver 127.0.0.11` dès qu'il est déclaré dans le bloc
`server` englobant -- la distinction "littéral = résolution système
au chargement, via `/etc/hosts`" ne s'applique PAS ici. `nginx`
renvoyait `host.docker.internal could not be resolved (3: Host not
found)` en conditions réelles.

**Corrigé** : `resolve_host_ip(env)` (nouveau, même motif que
`resolve_gateway_port`) résout l'entrée `"__HOST_IP__"` du service en
network_mode:host vers la VRAIE adresse IP de l'hôte (`HOST_IP`, déjà
configuré ailleurs dans ce projet) -- une IP littérale ne nécessite
AUCUNE résolution DNS, contournant le problème entièrement plutôt que
de chercher un autre nom à faire résoudre par un résolveur qui ne
verra de toute façon jamais `/etc/hosts`.

**Vérifié réellement** : `proxy_pass http://192.0.2.10:15000...`
confirmé avec un `HOST_IP` réaliste, repli sur `127.0.0.1` sans
`HOST_IP` testé, non-régression des 30 autres routes confirmée.
