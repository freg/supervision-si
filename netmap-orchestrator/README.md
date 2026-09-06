# netmap-orchestrator — orchestrateur d'analyse et de supervision réseau

Livraison #388. Demandé explicitement après recentrage du volet
Nebula : "le besoin d'analyse et de supervision d'un environnement
réseau comme celui contrôlé par nebula est prioritaire... construire
et compléter en continu une liste des ip/adresses MAC/entrée dns/
ports... seconde liste les interactions/flux relevés dans le temps
des connexions et des volumes/nombre de paquets échangés".

## ⚠️ Découverte importante : les deux listes existent déjà

En creusant `network-agent-api` avant de coder quoi que ce soit,
confirmé que ce module couvre DÉJÀ, intégralement :

- **Liste 1 (appareils)** — `na_devices` : IP + MAC + **hostname
  (DNS)** + `first_seen` (jamais réécrit) + `last_seen` (mis à jour
  en continu) + compteurs cumulatifs. `na_device_services` : ports
  par appareil, même logique first/last_seen.
- **Liste 2 (flux)** — `na_device_links` : qui parle à qui, volumes
  (`bytes_total`)/paquets (`packet_count`), first/last_seen.
  `na_device_link_services` : la même chose PAR SERVICE. Tables
  `na_history_snapshots`/`na_device_presence_history`/
  `na_link_history` : relevés périodiques pour le suivi dans le
  temps (rémanence déjà construite en #251).

Ce module **NE DUPLIQUE RIEN** de tout ça -- il LIT ces données via
l'API HTTP de `network-agent-api` (`network_agent_client.py`) et
applique des règles pour en tirer des **suggestions d'étapes
suivantes**, qui est la partie réellement nouvelle demandée.

## Ce que fait ce module

Un passage périodique (5 min par défaut, `NETMAP_ORCHESTRATOR_INTERVAL_SECONDS`)
récupère les appareils/services connus depuis `network-agent-api`,
applique chaque règle (`rules/*.py`), et enregistre/met à jour des
**suggestions** en base -- jamais dupliquées (une ligne par
(règle, sujet), voir `store.py`), le statut évolue dans le temps
(`open` -> `dismissed`/`done`, réouverte automatiquement si la
condition qui l'a créée se reproduit après une clôture).

### Règles livrées (scénario de départ, volontairement simple)

- **`no_services`** — appareil connu depuis plus de 30 min, aucun
  service détecté par la capture passive -- suggère un scan actif
  (`netprobe_nmap_scan`) avec l'IP en contexte.
- **`new_device`** — appareil apparu il y a moins de 15 min --
  purement informatif, pour une revue humaine.
- **`snmp_candidate`** — trafic observé sur le port 161 (SNMP) --
  suggère un enregistrement comme cible dans `snmp-api`
  (`snmp_register_target`).

Architecture DÉLIBÉRÉMENT calquée sur `netprobe/api/analyzer_engine.py`
(#307) : chaque règle est une fonction PURE (`analyze(context) ->
findings`, aucun effet de bord), l'orchestration (récupération des
données, écriture en base) reste dans `engine.py` -- une règle en
échec n'empêche jamais les autres de tourner.

**Ce module ne lance rien lui-même** -- une suggestion contient le
contexte nécessaire (`suggested_action`/`action_params`, ex.
`{"ip_address": "..."}`) pour qu'une personne (ou une automatisation
future) déclenche l'action réelle via le module concerné
(`netprobe-api`, `snmp-api`...).

## Accessible via la passerelle (livraison #389) + interface hub (livraison #391)

Contrairement à `docker-monitor-api` (#376, jamais routé via
`tls-proxy` -- accès au socket Docker, équivaut à un accès root sur
l'hôte), rien ne justifie de garder celui-ci hors passerelle -- ce
module lit seulement `network-agent-api` en HTTP, aucun privilège
particulier. Routé sur `/api/netmap-orchestrator/` (voir
`tls-proxy/render_nginx_conf.py`). Port direct (6125) conservé EN
PLUS, pratique pour un test rapide en `curl` sans passer par le
certificat auto-signé de la passerelle.

**Interface hub construite (#391)** -- `hub/src/NetmapOrchestratorView.jsx`
+ `hub/src/netmapOrchestratorClient.js` (menu "Réseau" -> "Orchestrateur
réseau") : filtrage par statut (ouvertes/rejetées/traitées/toutes),
bouton "Lancer une analyse maintenant" (`POST /run`), tableau des
suggestions avec message/règle/action suggérée/contexte, boutons
rejeter/marquer traité/rouvrir par ligne. N'exécute AUCUNE action
elle-même -- affiche le contexte (`suggested_action`/`action_params`)
pour une action manuelle via le module concerné.

## Routes

```
GET  /rules                          -- règles enregistrées
POST /run                            -- déclenche un passage immédiat (toutes les règles)
POST /run/<nom>                      -- déclenche UNE règle précise
GET  /suggestions?status=&rule_name= -- liste, filtrable
GET  /suggestions/<id>
POST /suggestions/<id>/status        -- {"status": "open"|"dismissed"|"done"}
GET  /summary                        -- comptage par statut
GET  /health
GET  /logs
GET  /version
```

## Concurrence — UN SEUL worker Gunicorn

Même raisonnement que `docker-monitor-api` (#376) : la boucle de
fond (passage périodique des règles) tournerait en double avec 2
workers séparés -- écritures concurrentes sur la même base SQLite,
appels redondants à `network-agent-api`.

## Reste à construire (prochaines itérations, "cycle permanent de retour")

Demandé explicitement pour les rendus visuels -- **volontairement
PAS construit dans cette première livraison**, fondation d'abord :

- **Graphe alluvial** (flux TCP/IP/UDP) -- à partir de
  `na_device_links`/`na_device_link_services`, déjà tout le nécessaire
  (source, destination, volume, protocole/port).
- **Radial tree augmenté** (liens d'épaisseur proportionnelle au
  volume) -- extension du rendu radial déjà existant (Optick), à
  partir des mêmes données de liens.
- Vues déjà existantes à réutiliser comme point de départ : radial
  tree (Optick), pixel-grid (#153+).

Ce module expose déjà toutes les données brutes nécessaires via
`network-agent-api` (jamais besoin d'attendre CE module pour
commencer le travail de visualisation) -- l'orchestrateur ajoute la
couche "suggestions d'étapes", les visualisations restent un chantier
séparé, itératif.

## Vérifié réellement

`store.py` testé en profondeur (création, mise à jour sans doublon,
préservation de `action_params` sur une mise à jour qui n'en fournit
pas de nouveaux -- un vrai bug trouvé et corrigé en testant --,
rejet puis réouverture automatique, comptage par statut).
`engine.py` testé avec `network_agent_client` mocké (3 règles
déclenchées correctement sur des données réalistes, aucun doublon
après un second passage). Routes Flask testées de bout en bout
(12 scénarios -- règles, déclenchement, suggestions, changement de
statut, cas d'erreur).

**Non vérifié dans cet environnement** : l'appel réseau réel contre
un vrai `network-agent-api` (aucune instance disponible ici).
