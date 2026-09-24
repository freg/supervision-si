# Services du hub — feu tricolore et redémarrage (services-api, #584)

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
