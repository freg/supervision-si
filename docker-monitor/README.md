# docker-monitor-api — contrôle minimal + analyse de logs externalisée

Livraison #376, demandé explicitement : "extraire de portainer.io de
quoi construire un docker qui contrôle les autres stacks/containers à
minima qui lise et analyse les logs de tous les container y compris
lui-même et publie son analyse dans un fichier log externe".

## ⚠️ Sécurité — à lire avant tout déploiement

Ce service monte `/var/run/docker.sock` (le socket Docker de l'hôte)
pour parler à l'API Docker via le SDK officiel (`docker` / docker-py)
-- MÊME principe que Portainer, confirmé par recherche avant cette
livraison (Portainer monte ce même socket, aucune autre voie
documentée pour ce type d'outil).

Un accès à ce socket **ÉQUIVAUT À UN ACCÈS ROOT** sur la machine
hôte : un conteneur qui le détient peut créer un AUTRE conteneur
montant `/` de l'hôte, donc lire/modifier n'importe quel fichier
système -- confirmé par plusieurs sources indépendantes (articles de
sécurité Docker, documentation Portainer elle-même). **Jamais à
exposer publiquement** -- même précaution que `launcher` et
`vault-admin-api` déjà dans ce projet (accès LAN uniquement, jamais
routé par `tls-proxy`, vérifié absent de
`tls-proxy/render_nginx_conf.py`).

Aucun moyen de donner un accès "lecture seule" au socket lui-même (il
est monté tout ou rien). Une alternative existe (`docker-socket-proxy`,
filtre les appels API réellement autorisés) mais volontairement PAS
ajoutée ici : hors du périmètre "à minima" demandé, complexifierait
significativement le déploiement pour un gain hors de portée de cette
livraison.

## ⚠️ Chevauchement partiel avec `launcher` — trouvé en construisant ce service

Ce projet a DÉJÀ un service `launcher` (`launcher/`, livraison
antérieure) qui fait du contrôle start/stop/status PAR GROUPE DE
SERVICES nommé, avec une interface web dédiée ("feux tricolores").

`docker-monitor-api` REFAIT une partie de ce contrôle -- start/stop/
restart, mais PAR CONTENEUR individuel plutôt que par groupe nommé,
et via une interface JSON plutôt qu'une UI web. Gardé quand même,
pour deux raisons : "à minima" était explicitement demandé pour CE
service précis, et une interface JSON reste utile en soi
(consommable par une future tuile hub, par exemple, sans avoir à
parser du HTML). Mais la personne devrait savoir que `launcher`
existe déjà si le contrôle piloté par UI suffit à son besoin --
inutile de faire tourner les deux si un seul répond au besoin réel.

## Ce qui est GENUINEMENT nouveau : l'analyse de logs externalisée

Ni `launcher` ni aucun autre service de ce projet ne fait
d'ANALYSE de logs à travers TOUS les conteneurs -- c'est la partie
réellement nouvelle apportée ici.

Boucle d'arrière-plan (thread, démarré au chargement du module) :
toutes les `DOCKER_MONITOR_INTERVAL_SECONDS` (défaut 60s), pour
CHAQUE conteneur (via `docker_client.containers.list(all=True)` --
inclut CE conteneur lui-même, "y compris lui-même" demandé
explicitement, aucun traitement spécial nécessaire côté API Docker),
récupère les lignes de log nouvelles depuis le dernier passage
(`container.logs(since=<epoch>)`, jamais un ré-examen des mêmes
lignes), cherche des motifs d'erreur/avertissement (`ERROR`,
`CRITICAL`, `Exception`, `Traceback`, `Killed`, `FATAL`, `OOMKilled`,
`WARN`/`WARNING`) -- motifs choisis à partir d'incidents RÉELLEMENT
rencontrés dans ce projet au fil des livraisons (voir CHANGELOG.md :
OOM Killed, erreurs LDAP...), jamais une liste générique improvisée.

Résultat écrit dans un fichier **EXTERNE** (volume monté, survit à un
redémarrage/une reconstruction de ce conteneur) -- toujours en
AJOUT, jamais une réécriture complète. Un conteneur sans anomalie
détectée ne génère AUCUNE ligne (silence = tout va bien), sauf
message générique périodique si absolument rien d'anormal nulle part.

## Pas de tuile hub -- délibérément (tenté puis annulé, livraison #383)

Une tuile hub (`DockerMonitorView.jsx`) a été construite puis
ANNULÉE avant livraison : le hub principal est servi en HTTPS (via
`tls-proxy`), mais ce service n'est délibérément JAMAIS routé par la
passerelle publique (voir avertissement sécurité plus haut) --
accéder à une API HTTP simple depuis une page HTTPS est bloqué par
les navigateurs ("contenu mixte"). Même contrainte que
`vault-admin-api`, qui résout ça avec son PROPRE portail séparé
(`vault-admin-portal`, servi en HTTP direct, jamais intégré au hub)
-- solution qui n'a pas été construite ici, hors du périmètre
"à minima" demandé. Si une interface devient nécessaire plus tard,
suivre CE même motif (portail séparé, HTTP direct sur
`DOCKER_MONITOR_API_PORT`) plutôt qu'une intégration au hub HTTPS.

## Routes

```
GET  /containers                    -- liste tous les conteneurs (id/nom/statut/image, is_self)
POST /containers/<nom>/start
POST /containers/<nom>/stop
POST /containers/<nom>/restart
GET  /containers/<nom>/logs?tail=N  -- logs BRUTS complets (livraison #380), contourne les limites
                                        de pagination d'un visualiseur comme Portainer
GET  /analysis?limit=100            -- dernières lignes du fichier d'analyse externe
GET  /health
GET  /logs
GET  /version
```

**Volontairement absent** : suppression de conteneur, création,
pull d'image -- hors du périmètre "à minima" demandé. Pour ça, un
vrai Portainer (ou un accès direct au socket) reste l'outil approprié.

## Concurrence — UN SEUL worker Gunicorn, pas deux

Contrairement aux 2 workers habituels des autres backends de ce
projet, ce service tourne avec `--workers 1` -- DÉLIBÉRÉMENT : la
boucle d'analyse tournerait en DOUBLE avec 2 workers séparés (2
process Python distincts, chacun démarrant sa propre boucle) --
double écriture dans le fichier d'analyse externe, double charge sur
l'API Docker. Un seul worker reste largement suffisant : ce service
n'est pas pensé pour un trafic HTTP concurrent élevé (outil de
supervision interne, pas une API publique).

## Variables `.env`

`DOCKER_MONITOR_API_PORT` (défaut 6124), `DOCKER_MONITOR_ANALYSIS_DIR`
(dossier hôte RÉEL où le fichier d'analyse est écrit, vide =
`./docker-monitor/analysis`), `DOCKER_MONITOR_INTERVAL_SECONDS`
(défaut 60), `DOCKER_MONITOR_TAIL_LINES` (défaut 200, nombre de
lignes examinées au tout premier passage sur un conteneur jamais vu).

## Vérifié / non vérifié

**Vérifié réellement** : syntaxe Python, logique testée en profondeur
avec un module `docker` (docker-py) ENTIÈREMENT simulé (aucun accès
réseau pour installer le vrai paquet dans l'environnement de
développement) -- listage de conteneurs avec détection correcte de
soi-même, start/stop/restart, 404 sur conteneur inexistant, `/health`
reflétant la connectivité Docker, ANALYSE testée avec des journaux
simulés réalistes (un conteneur sain, un conteneur avec erreurs
LDAP + "Killed" -- correctement détecté et résumé, le sain
correctement absent du fichier d'analyse).

**✅ CONFIRMÉ EN CONDITIONS RÉELLES (2026-09-05, livraison #377)** --
signalé par la personne juste après le déploiement : `docker.from_env()`
joint bien le socket monté (le worker Gunicorn démarre proprement,
aucun plantage au chargement du module), la boucle d'arrière-plan
tourne correctement (13 conteneurs examinés à chaque passage,
intervalle ~60s respecté), le mécanisme incrémental
(`container.logs(since=...)`) fonctionne comme prévu -- le PREMIER
passage a bien examiné l'historique existant (avertissements bénins
trouvés chez `tickets-postgres`/`keycloak`, probablement liés aux
locales manquantes et au mode développement, déjà rencontrés
ailleurs dans ce projet), les passages SUIVANTS ne réexaminent PAS
ces mêmes lignes (sinon ces avertissements réapparaîtraient à chaque
passage, ce qui n'est PAS le cas dans le fichier d'analyse réel
observé). `docker-monitor-api` lui-même n'apparaît jamais avec une
entrée d'anomalie -- attendu, ses propres logs de démarrage Gunicorn
sont propres.

