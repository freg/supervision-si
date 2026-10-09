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

## Images construites hors de super (#738)
Un nœud `"builder": true` (ex. la VM de travail sur pve10) construit et pousse les images dans un registre local ;
les autres nœuds, dont super, ne font que les tirer (tag = commit git). Les fronts et le hub étant pré-compilés avec
une configuration lue à l'exécution (#736-#737), une même image sert tous les nœuds.
```
# sur le constructeur (adresse VPN/LAN 10.99.0.3 par exemple) :
cd ~/SRC/data2/tickets/supervision-si/deploy/registry && SI_REGISTRY_BIND=10.99.0.3 docker compose up -d
# sur CHAQUE nœud (registre HTTP, joignable seulement par le VPN/LAN) :
echo '{"insecure-registries": ["10.99.0.3:5005"]}' | sudo tee /etc/docker/daemon.json && sudo systemctl restart docker
cd ~/SRC/data2/tickets/supervision-si && echo 'SI_REGISTRY=10.99.0.3:5005' >> .env
# deploy/nodes.json : "builder": true sur le constructeur ; puis depuis super :
cd ~/SRC/data2/tickets/supervision-si && python3 deploy/node_agent.py build-images && python3 deploy/images.py pull && ./scripts/run.sh up -d --no-build
```
La mise à jour depuis la tour (git, mode central ou cascade) suit ce chemin automatiquement quand `SI_REGISTRY` est
défini : construction sur le constructeur, puis « tirer + relancer sans construire » ici. La passerelle (tls-proxy,
image nginx légère) et les services clonés d'instances (#731) restent construits sur leur nœud.

## Reste
- Portail d'administration du coffre (HTTPS propre au serveur Vite) : non pré-compilé.
