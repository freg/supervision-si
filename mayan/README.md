# mayan — stack Mayan EDMS (séparé)

Livraison #158, "allons-y pour Mayan EDMS" -- GED tierce adoptée
après une recherche rapide (voir `ged/README.md` pour le raisonnement
complet, décision initialement DÉFÉRÉE en #157 "on travaillera cet
aspect plus tard").

## Pourquoi un stack SÉPARÉ (même motif que `gateway/`/`vault-standalone/`)

Mayan EDMS est un système LOURD (4 conteneurs : l'appli, PostgreSQL,
Redis, RabbitMQ) avec un cycle de vie indépendant des ~20 services
applicatifs du stack principal, en évolution constante. Le séparer
évite de gonfler le stack principal pour un composant optionnel, et
lui laisse son propre rythme de redémarrage/mise à jour -- même
raisonnement que Keycloak/tls-proxy (`gateway/`).

Réseau Docker **PARTAGÉ** avec le stack principal (`supervision-si-net`,
créé de façon idempotente par n'importe quel `run.sh` de ce projet) --
`ged-api` (stack principal) doit joindre Mayan par son nom Docker
interne (`mayan-app`), ce qui ne fonctionne QUE sur le même réseau.

## 4 conteneurs, TOUS nécessaires

Vérifié directement contre le `docker-compose.yml` OFFICIEL de Mayan
EDMS (`https://github.com/mayan-edms/mayan-edms/blob/master/docker/docker-compose.yml`,
miroir de GitLab, consulté 2026-09-01) -- certaines sources
secondaires laissent penser à tort que PostgreSQL+Redis suffisent :

- **mayan-app** -- l'application elle-même (Django/Gunicorn).
- **mayan-postgresql** -- base de données.
- **mayan-redis** -- résultats Celery + gestionnaire de verrous.
- **mayan-rabbitmq** -- courtier de tâches Celery (AMQP, câblé en
  dur dans le modèle de conteneur du fichier officiel, PAS
  remplaçable par Redis dans cette configuration).

Adapté (simplifié) depuis le fichier officiel : retrait du mécanisme
`profiles:` Docker Compose (pas utilisé ailleurs dans ce projet,
préféré une liste de services ORDINAIRE pour rester cohérent) ;
retrait des services optionnels non nécessaires ici (elasticsearch --
Mayan utilise Whoosh par défaut sans lui ; traefik -- ce projet a
déjà `tls-proxy`/`gateway` pour ça ; workers séparés/mountindex/
celery_beat séparé -- le service "app" seul suffit pour un usage
modeste).

## Démarrage

```bash
./scripts/run-all.sh mayan up -d --build
# ou directement :
./mayan/scripts/run.sh up -d --build
```

Contrairement à Keycloak (`gateway/`), **aucune dance d'import
manuel** -- Mayan gère sa propre initialisation (base + compte admin)
via `MAYAN_AUTOADMIN_USERNAME`/`PASSWORD`/`EMAIL` (voir `.env.example`,
section "Mayan EDMS"). Premier démarrage plus long que les suivants.

Accès web : `http://<HOST_IP>:${MAYAN_PORT:-8100}` (port publié
DIRECTEMENT sur l'hôte pour l'instant, réseau de confiance -- pas
encore routé via `tls-proxy`, seul `ged-api` en interne consomme
l'API pour l'instant). À reconsidérer si un accès direct navigateur à
l'interface web de Mayan devient utile.

## ⚠️ Non vérifié dans cet environnement

Comme tout ce qui touche Docker dans ce projet, **aucune partie de ce
déploiement n'a pu être testée ici** (aucun moteur Docker disponible)
-- construit avec le plus grand soin à partir du fichier officiel,
mais à vérifier en PRIORITÉ une fois déployé :
- Que les 4 conteneurs démarrent et restent en bonne santé.
- Que le tag d'image (`MAYAN_DOCKER_IMAGE_TAG`, défaut `s4.11`)
  existe toujours sur Docker Hub au moment du déploiement -- les
  séries `sN.NN` évoluent, confirmer/ajuster si besoin.
- Que le compte admin auto-créé fonctionne bien pour se connecter
  (web ET API REST via `ged-api`, voir `ged/README.md`).

## Chantiers pas commencés

- Routage via `tls-proxy` si un accès web direct depuis l'extérieur
  devient utile (actuellement direct sur l'hôte).
- Workers Celery dédiés / `elasticsearch` si le volume de documents
  finit par le justifier (retirés de cette première livraison pour
  rester simple).
