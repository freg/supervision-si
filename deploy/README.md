# Déploiement réparti — plusieurs hôtes, cohortes, VPN, migration (livraisons #509, #513)

Demande : « la charge devient trop importante sur la VM hôte du hub ;
répartir les conteneurs sur plusieurs hôtes ; un mécanisme de migration
géré par un module indépendant sur chaque nœud, qui déploie une tuile et
sa cohorte de dépendances/ressources sur un nouvel hôte en respectant
isolation et dépendances, sans perte de données ». Moyens : deux Proxmox
sur site (2-3 VM lourdes chacun), un Proxmox libre chez OVH, VPN
inter-Proxmox au moins pour OVH.

## Choix (#513 : compose par nœud, plus de Swarm)

La première version (#509) reposait sur Docker Swarm. À l'essai, chaque
pas se battait contre les hypothèses du `docker-compose.yml` existant :
volumes nommés recréés vides sous un autre préfixe, bind mounts
relatifs résolus ailleurs, réseau `supervision-si-net` créé en bridge
par les run.sh alors que Swarm veut un overlay, passerelle lancée deux
fois. Swarm n'apportait rien d'utilisé (chaque cohorte est de toute
façon épinglée à un nœud, ports en mode hôte, données locales) et
imposait une seconde façon de lancer le système. Il est retiré.

**Chaque nœud lance compose tel quel**, avec le dépôt, le même `.env`
et un **override généré** (`deploy/cohorts.py override <nœud>` →
`deploy/generated/node.override.yml`, ajouté automatiquement par
`scripts/run.sh`) :

- les services **locaux** (ceux des cohortes que `deploy/nodes.json`
  affecte au nœud) sont publiés sur l'**adresse VPN** du nœud, à un port
  stable par service (`20000 + 10 × rang + rang du port interne`) ;
- chaque service **distant** utilisé ici (dépendances `depends_on`,
  URL `scheme://<service>:port` et `*_HOST=<service>` dans
  l'environnement, backends de tls-proxy sur une bordure) reçoit un
  **relais** : conteneur `relay-<service>` (socat) dont l'**alias DNS**
  sur le réseau compose est le nom du service, qui renvoie vers
  l'adresse VPN de son nœud. Rien ne change dans le code ni dans
  `docker-compose.yml` : `http://credentials-api:5000` continue de
  marcher, il aboutit sur l'autre VM ;
- la passerelle (Keycloak, tls-proxy, annuaire de test :
  `gateway/docker-compose.yml`) reste sur le nœud `core` ; une bordure
  (`edge: true`) lance seulement `tls-proxy` (jumeau OVH, #510), qui
  joint Keycloak et tous les backends par relais ; Keycloak est publié
  sur le VPN via `deploy/generated/gateway.override.yml`.

**Cohortes** (`deploy/cohorts.json`) : 11 groupes couvrant les 89
services (#689 : `groupware`, `outils`, `ia` ajoutées ; un test vérifie que
tout service du compose est dans une cohorte) — `core`, `supervision`, `tickets`, `externes`,
`donnees`, `reseau` (`network-agent-api` en réseau hôte, lancé à part
sur le nœud), `agents`, `coffre` (isolée : ne dépend que de `core`).

**VPN WireGuard** maillé (`deploy/wg-mesh.sh`), sous-réseau dédié
(`10.99.0.0/24` dans l'exemple) : les VM du site initient vers
l'endpoint public d'OVH (NAT), keepalive. Les agents et les ports de
service ne sont exposés que sur l'adresse VPN.

## Module par nœud : `deploy/node_agent.py`

Bibliothèque standard Python, tourne sur l'hôte (service systemd
`si-node-agent`, installé par `scripts/install.sh` profil `node`),
écoute sur l'adresse VPN, jeton `SI_NODE_TOKEN` (même `.env` partout).

| appel | effet |
|---|---|
| `GET /status` | nœud, cohortes, services en marche, plan (relais manquants) |
| `POST /apply {nodes, build}` | remplace `deploy/nodes.json`, régénère l'override, `compose up -d --no-deps` des services locaux + relais, arrête ce qui n'est plus affecté ici |
| `POST /stop {cohort}` | arrête une cohorte (données conservées) |
| `GET /export/<cohorte>` | flux tar.gz : bind mounts (`bind/<chemin relatif>`, `abs/<chemin>`) et volumes nommés (`volume/<nom>.tar`, via `alpine tar`) |
| `POST /import/<cohorte> {from}` | va chercher l'export sur le nœud source et le restaure (mêmes chemins, volumes créés) |

En ligne de commande : `node_agent.py apply|stop|export|import|status`.

## Gestionnaire : `deploy/repartition.py` (manager)

```
deploy/repartition.py status                  chaque nœud : agent, services, relais
deploy/repartition.py plan                    ce que chaque nœud lancerait
deploy/repartition.py apply [--build]         pousse nodes.json partout et applique (core d'abord)
deploy/repartition.py migrate tickets vm-donnees [--yes]
```

`migrate` : vérifie zone (`local`/`ovh`), isolation et `manager`
(`core` reste sur super sauf `--force`) ; arrête la cohorte sur le nœud
source ; fait copier les données par les agents (source → cible, sur
le VPN) ; met à jour `nodes.json` ; `apply` sur tous les nœuds (les
relais des autres nœuds sont re-pointés). Si la copie échoue :
`nodes.json` inchangé, cohorte relancée sur la source. Sauvegarde
totale conseillée avant (tuile Sauvegarde).

## Mise en place

1. `deploy/nodes.json` depuis l'exemple (noms, adresses VPN, cohortes,
   `edge`), **identique** sur tous les nœuds ; `deploy/wg-mesh.sh` →
   configurations WireGuard, `wg-quick up wg0` partout.
2. Sur chaque VM : même dépôt au même chemin, même `.env`
   (`SI_NODE_TOKEN` généré par le premier `install.sh`), Docker,
   `python3-yaml`. `sudo scripts/install.sh` → profil `node` : override,
   passerelle si `core`, images des services locaux construites par
   lots, agent systemd, `apply`, état. Une bordure OVH copie `pki/`
   depuis le manager (`TLS_EXTRA_SAN` = nom public).
3. Depuis le manager : `deploy/repartition.py status`, puis `apply`
   après toute modification de `nodes.json`.

Limites connues : un service joint par une variable `*_HOST` sans port
voisin `*_PORT` ni URL ni table tls-proxy n'a pas de port interne connu
(listé « SANS RELAIS » par `override`) ; les relais sont du TCP brut
(pas de TLS entre nœuds : le VPN chiffre) ; `network-agent-api`
(réseau hôte) explore le LAN du nœud qui le porte.

## Recette : une troisième VM locale pour délester super (#689)

Cohortes à déplacer en premier (les plus lourdes, sans rôle d'entrée) : `outils` (QA/Chromium, portage + MariaDB,
vulnérabilités, Dependency-Track), puis `donnees` ou `externes`. `core` reste sur super.

1. VM Debian 13 sur le Proxmox local (4 vCPU / 8-16 Go / 100 Go), Docker, `python3-yaml`, `jq`, `wireguard-tools`,
   même dépôt au même chemin (`git clone`), **même `.env`** que super (copie).
2. `deploy/nodes.json` (copie de l'exemple, identique partout) : `super` (manager, `core`, `coffre` + le reste) et
   `vm-outils` (worker, `outils`) ; `lan_address` = adresse LAN de chaque VM, `endpoint` = `<lan>:51820` pour les deux
   (même site : trafic direct), `wg_address` dans `10.99.0.0/24`.
3. Sur super : `deploy/wg-mesh.sh` puis copier `deploy/generated/wg/<nœud>.conf` vers `/etc/wireguard/wg0.conf` de
   chaque VM et `systemctl enable --now wg-quick@wg0` (les ports des services ne sont publiés que sur le VPN).
4. Sur chaque VM : `sudo scripts/install.sh` → profil `node` (agent de nœud systemd, override, construction).
5. Sur super : `deploy/repartition.py status`, puis `deploy/repartition.py migrate outils vm-outils --yes`
   (arrêt sur super, copie des données par les agents, relais re-pointés). Sauvegarde totale avant.

