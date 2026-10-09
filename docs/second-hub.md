# Second hub et répartition des charges (2026-10-09, livraisons #734-#736)

## Constat (mesures sur super, 9 oct.)
- 4 vCPU, 8,7 Go de RAM, **7 Go de swap utilisés**, charge 10-11 ; 99 conteneurs.
- Gros consommateurs (RAM + swap) : Keycloak ×2 (passerelle + `vault-standalone`), Elasticsearch, Mayan (3 processus
  web, workers celery à 4, PostgreSQL, RabbitMQ), ~90 processus gunicorn.
- Passerelle : 4 ms depuis super. Les 8 s vues depuis l'extérieur viennent du NAT du routeur (voir ticket réseau),
  pas du hub.

## Ce qui est livré
- #734 régime mémoire : API à 1 processus + 4 threads, tas Keycloak borné, Mayan réduit ; nginx HTTP/2 + gzip +
  cache de sessions TLS.
- #735 hub réactif : vues à la demande (2,1 Mo → 368 Ko au premier chargement), préchargement au repos, barre
  d'activité, GET suspendus quand l'onglet est caché.
- #736 hub **pré-compilé dans l'image** (plus de `vite build` à chaque démarrage, configuration lue dans `/env.js`)
  et **second hub** : une bordure (`"edge": true` dans `deploy/nodes.json`) sert le hub en local (`replicas`, défaut
  `["hub"]`) au lieu de le relayer ; seules les API traversent le VPN.

## Répartition conseillée (deploy/nodes.json)
| Nœud | Rôle | Cohortes |
|---|---|---|
| super | interactif + passerelle principale | core, coffre, tickets |
| vm-travail (pve10) | tâches de fond | agents, externes (Elasticsearch), outils (QA, Dependency-Track), ia, donnees (+ Mayan) |
| vm-hub2 | second hub (bordure) | aucune -- `"edge": true` : tls-proxy + hub locaux, relais vers les API |

```
cd ~/SRC/data2/tickets/supervision-si && cp deploy/nodes.example.json deploy/nodes.json   # puis éditer nœuds / cohortes
cd ~/SRC/data2/tickets/supervision-si && python3 deploy/cohorts.py check && python3 deploy/cohorts.py override vm-hub2
cd ~/SRC/data2/tickets/supervision-si && python3 deploy/repartition.py apply --build
```
(ou tour de contrôle → Répartition → Appliquer + reconstruire ; migration avec données : « Migrer une cohorte »).

## Bascule entre les deux hubs
Les deux bordures sont équivalentes (même passerelle, même hub, même Keycloak relayé) : DNS interne à deux
adresses, ou adresse flottante keepalived (#655) devant les deux. Une bordure tombée n'arrête que son entrée.

## Reste
- Constructions d'images hors de super (registre local, super ne fait que tirer) : lot 3.
- Fronts encore en serveur de développement Vite (7) : à pré-compiler comme le hub.
