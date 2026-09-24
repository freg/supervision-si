# Tour de contrôle du hub — services-api (#584, #586)

Sous-tuile **Paramètres → Services du hub** (menu Paramètres → « Services du
hub (feu tricolore) », lien `?view=services`). Pour chaque conteneur du
projet compose : état Docker, healthcheck s'il existe, requête HTTP interne
sur le premier port exposé (`/health` puis `/`), classée en trois lampes :

| lampe | cas |
|---|---|
| vert | en marche et joignable (HTTP 2xx, ou 401/403 = protégé), ou sans port et en marche |
| orange | redémarre en boucle, healthcheck en démarrage, réponse lente (> 3 s), `status: degraded`, HTTP 404 sur `/health` et `/` |
| rouge | arrêté / en erreur, healthcheck en échec, HTTP 5xx, port injoignable |

Actions : **Tout vérifier** (ignore le cache), **Redémarrer** / **Démarrer**
par service, **Redémarrer les rouges** (jamais `tls-proxy`, `keycloak`,
`hub`, `services-api` — ils portent la page ou l'entrée), **Journal**
(dernières lignes du conteneur). Filtre « début de mot d'abord »,
« problèmes seulement ».

## Sécurité

Le socket Docker est monté (= root sur l'hôte, comme docker-monitor-api
#376 volontairement hors passerelle). Ici la route `/api/services/` est
publiée, mais chaque appel exige un **jeton Keycloak vérifié** (RS256 /
JWKS, `si-proxy/admin/auth.py` partagé) et un utilisateur de
`SERVICES_ADMIN_USERS` (défaut `freg`). Périmètre : conteneurs du projet
(label compose) seulement ; start / restart uniquement — ni stop, ni
suppression, ni image ; variables d'environnement jamais lues. Chaque
redémarrage est journalisé avec l'utilisateur.

## Configuration

```
SERVICES_ADMIN_USERS=freg          # utilisateurs Keycloak admis (virgules)
SERVICES_HTTP_TIMEOUT=4            # s, requête interne
SERVICES_CACHE_SECONDS=20          # cache de l'inventaire
```

```bash
cd <dépôt> && ./scripts/run.sh up -d --build services-api tls-proxy hub
```

## API (jeton requis sauf /health)

`GET /services[?refresh=1]` → `{project, at, summary{counts, verdict}, protected, services:[{service, container, status, docker_health, started_at, restart_count, port, http, kind, light, text, protected}]}` ;
`POST /services/<s>/restart` ; `POST /services/restart-red` ; `GET /services/<s>/logs?tail=80`.

Tests : `services/api/test_lights.py` (classement pur), `test_app.py`
(jeton, inventaire, redémarrages, protégés, journal — Docker simulé) ;
hub `tests/servicesLights.test.mjs`.


## Tour de contrôle (#586)

Paramètres → **🗼 Tour de contrôle** (`?view=control`, onglet par
`&tab=services|deliveries|configs|auto|journal`). Tout se fait depuis le hub :

- **Services** : le feu tricolore ci-dessus + **Reconstruire** (build + relance
  du service, job) ; bouton **↻ Passerelle** (re-rendu nginx + relance de
  tls-proxy, pour une nouvelle route `/api/…`).
- **Livraisons & jobs** : déposer le zip (`git archive`) → analyse fichier par
  fichier (ajouté / modifié / inchangé ; **jamais écrasés** : `.env`,
  `*.local.json`, clés ; **conservés** si déjà présents : `*/data/*`,
  `backups/*` ; entrées dangereuses `..`/absolues rejetées) → **plan** :
  `sync-env.py` si `.env.example` a changé, `run.sh up -d --build` des services
  dont une source COPY/ADD de leur Dockerfile a changé, `run.sh up -d` des
  services en marche si `docker-compose.yml` a changé (compose ne recrée que
  ce qui a bougé), `run.sh restart` pour un fichier monté, rechargement de la
  passerelle si `tls-proxy/` ou `gateway/` ont changé — **seulement parmi les
  services en marche** (un profil allégé n'est jamais étendu en douce ; les
  autres sont listés « non démarrés »). Application **automatique** (réglage)
  ou bouton ; retour arrière (numéro plus ancien) confirmé.
- **Jobs** : exécutés par un conteneur **runner** détaché (même image, socket
  Docker, dépôt monté au même chemin, `HOST_IP` transmis) → il survit à la
  reconstruction de services-api, du hub ou de la passerelle. Journal en
  direct, code retour ; `services/data/jobs/`.
- **Configurations** : registres JSON (Cisco `cisco/switches.local.json`,
  MikroTik `mikrotik/routers.local.json`) — tableau éditable d'après le schéma,
  **import JSON** (fusion par nom ou remplacement), export, validation côté
  serveur (noms, ports, choix, doublons), ancienne version gardée dans
  `services/data/config-history/`. Relus à chaque appel par cisco-api /
  mikrotik-api : aucun redémarrage.
- **Automatismes** : auto-réparation (service rouge N vérifications de suite →
  relance, plafond par heure, puis abandon signalé ; jamais les protégés),
  application auto des livraisons, services **non surveillés** (gris, jamais
  relancés). `services/data/settings.json`.
- **Journal** : réglages, configurations, livraisons, jobs, auto-réparation
  (`services/data/events.jsonl`).

Montage : `${PWD}:${PWD}` (lancer `run.sh` depuis la racine du dépôt, comme
toujours) ; `SERVICES_PROJECT_DIR=${PWD}`, `SERVICES_HOST_IP=${HOST_IP}`,
`SERVICES_EXTRA_PROJECTS=supervision-si-gateway` (tls-proxy, keycloak dans le
feu), `SERVICES_HEAL_INTERVAL=60`. Les fichiers écrits prennent le
propriétaire du dépôt.

API supplémentaires : `GET/PUT /settings`, `GET /events`, `GET /configs`,
`GET/PUT /configs/<id>`, `POST /deliveries` (multipart `file`),
`GET /deliveries`, `POST /deliveries/<id>/apply {allow_downgrade}`,
`GET /jobs`, `GET /jobs/<id>`, `POST /services/<s>/rebuild`,
`POST /gateway/reload`. Tests : `test_tower.py` (pur),
`test_app.py::TestTower` (zip réel, plan, runner simulé, réglages,
auto-réparation), hub `tests/towerLib.test.mjs`.

**Premier passage** (la tour ne peut pas s'installer elle-même) :

```bash
cd ~/SRC/data2/tickets/supervision-si && ./scripts/run.sh up -d --build services-api hub && ./gateway/scripts/run.sh up -d --force-recreate tls-proxy
```

Ensuite, plus besoin de `scp` / `rsync` : les livraisons se déposent dans la tour.


## Santé de l'hôte (#593)

Après un `/var` saturé qui tronquait les fichiers du hub : la tour mesure
l'hôte toutes les minutes — **espace disque** de chaque partition (racine
de l'hôte montée en lecture seule sous `/host`, bind récursif), **charge**
(1 / 5 / 15 min vs CPU) et **mémoire** (`/proc` du noyau hôte), plus
`docker system df` (images inutilisées, cache de build, conteneurs,
volumes). Seuils : disque orange ≥ 85 % ou < 1 Go libre, rouge ≥ 95 % ou
< 200 Mo ; charge orange ≥ nb CPU (1 min), rouge ≥ 2 × CPU (5 min) ;
mémoire orange ≥ 90 %, rouge ≥ 97 %.

- **Bandeau d'alerte** en haut de toutes les pages du hub (`/host/public`,
  sans jeton : lampe + texte seulement), lien vers la tour, masquable
  jusqu'au prochain changement d'état.
- Tour → Services : carte **Hôte du hub** (barres par partition, charge,
  mémoire, Docker) et **🧹 Nettoyer images + cache** (`images.prune` sans
  filtre dangling = toutes les images sans conteneur, `prune_builds` ;
  option conteneurs arrêtés hors projet ; **jamais les volumes**),
  journalisé et notifié (`tower.host.prune`).
- Notifications `tower.host.disk` (critique) et `tower.host.load` à chaque
  changement d'état, jamais répétées ; retour au vert notifié.

Pour les autres hôtes (agents), les métriques disque / charge existent déjà
dans si-agent (#503) ; la tour ne couvre que l'hôte du hub.
