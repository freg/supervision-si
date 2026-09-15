# Déploiement réparti — plusieurs hôtes, cohortes, VPN, migration (livraison #509)

Demande : « la charge devient trop importante sur la VM hôte du hub ;
répartir les conteneurs sur plusieurs hôtes ; un gestionnaire de
répartition/migration qui déploie une tuile et sa cohorte de
dépendances/ressources sur un nouvel hôte en respectant isolation et
dépendances ». Moyens : deux Proxmox sur site (2-3 VM lourdes chacun),
un Proxmox libre chez OVH, lien VPN inter-Proxmox au moins pour OVH.
Choix libres, à revoir après les premiers tests.

## Choix

**Docker Swarm plutôt qu'un orchestrateur maison.** Il est déjà dans
Docker Engine, il reprend le `docker-compose.yml` existant (déployé en
pile), son réseau overlay chiffré conserve les **noms de services**
(donc tls-proxy, `http://xxx-api:5000`, memcached : rien à changer dans
le code), et le **placement par label** exprime exactement « cette
cohorte sur ce nœud ». Migrer = déplacer un label et redéployer.

**Cohortes** (`deploy/cohorts.json`) : 8 groupes couvrant les 73
services — `core` (passerelle TLS, Keycloak/LDAP, hub, coffre des accès,
bastion : reste sur le manager, seul nœud à porter la PKI et les ports
publiés), `supervision`, `tickets`, `externes`, `donnees`, `reseau`,
`agents`, `coffre` (isolée : ne dépend que de `core`). Chaque cohorte
est **épinglée** à un nœud (label `si.cohort.<nom>=true`) parce que ses
données sont des bind mounts locaux (`./x/data`) : pas de stockage
partagé, donc pas de réplication, mais un placement stable et une
migration qui déplace les dossiers.

**VPN WireGuard** en maillage entre toutes les VM (pas seulement OVH) :
c'est aussi le réseau de contrôle et de données de Swarm
(`--advertise-addr` / `--data-path-addr` sur l'adresse wg0), chiffré
même sur le LAN. Le nœud OVH a un endpoint public, les VM du site
derrière NAT initient vers lui (keepalive) et se parlent en direct entre
elles. Zones `local` / `ovh` : une cohorte n'est placée chez OVH que si
sa zone le dit (candidate : `agents`, pour des agents externes).

**Registre d'images privé** sur le manager (`registry:2`, volume
`deploy/registry/`, joignable par le VPN) : `docker stack deploy` ne
construit pas, on construit sur le manager comme aujourd'hui et on
pousse.

**Hors Swarm** : `network-agent-api` (`network_mode: host`, non supporté
par les services Swarm) reste lancé avec compose sur le nœud de la
cohorte `reseau`, joint par `HOST_IP` comme aujourd'hui.

## Bordure : tls-proxy sur super et son jumeau OVH (#510)

Décision : « le proxy hub reste sur super et peut avoir un jumeau sur
une VM OVH (DNS et NAT obligent) ». `tls-proxy` est un **service de
bordure** (`edge_services` dans `cohorts.json`) : mode global sur chaque
nœud `si.edge=true` — super (entrée LAN, nom interne) et `vm-ovh`
(entrée publique, nom public). Les deux instances résolvent les mêmes
backends par leur nom sur l'overlay ; la cohorte `core` ne bouge pas.
Sur le nœud OVH : `pki/` copié depuis le manager avec un certificat
serveur portant le nom public (`TLS_EXTRA_SAN`), et le frontal public
existant (`scripts/front-reverse-proxy.sh`, réécriture d'origine
`INTERNAL_ORIGIN`, `KEYCLOAK_EXTRA_ORIGINS`) posé devant cette instance
locale plutôt que devant super à travers le VPN. DNS : nom public →
OVH, nom LAN → super.

## Outils

- `cohorts.py report | check | stack` — cartographie (dépendances
  déduites de `depends_on` et des URL `http://<service>` des
  variables, volumes, mode réseau), contrôle (chaque service dans une
  cohorte et une seule, isolation respectée), génération de
  `deploy/generated/stack.yml` (build retiré, image
  `${SI_REGISTRY}/si/<service>:${SI_TAG}`, contraintes de placement,
  ports publiés en mode host sur le nœud, ports liés à 127.0.0.1
  retirés).
- `nodes.example.json` → `nodes.json` (ignoré par git) : nœuds, zones,
  adresses VPN, endpoint OVH, cohortes par nœud.
- `wg-mesh.sh` — génère `generated/wg/<nœud>.conf` (clés incluses,
  dossier ignoré) à copier dans `/etc/wireguard/wg0.conf`.
- `swarm-init.sh manager|worker|labels` — initialisation sur le VPN,
  jonction des workers, labels depuis `nodes.json`.
- `build-push.sh` — registre + construction + push.
- `deploy.sh` — check → stack → `docker stack deploy` (variables du
  `.env` exportées : Swarm ne lit pas `.env`).
- `migrate.sh <cohorte> <nœud>` — arrêt des services de la cohorte,
  copie des dossiers de données par SSH sur le VPN (même chemin de dépôt
  sur chaque nœud), déplacement du label, redéploiement.

## Mise en route (ordre)

1. VM : une par cohorte lourde (proposition dans `nodes.example.json` :
   manager = super, `vm-donnees` (supervision, tickets, donnees),
   `vm-reseau` (reseau, externes), `vm-ovh` (agents)). Même dépôt au même
   chemin, même `.env`, Docker installé.
2. `wg-mesh.sh`, WireGuard sur chaque VM, `ping` des adresses wg.
3. `swarm-init.sh manager <wg>` sur super, `worker` sur les autres,
   `labels`.
4. `daemon.json` insecure-registries sur chaque nœud, `build-push.sh`.
5. `deploy.sh` ; `docker stack ps si` ; `network-agent-api` par compose
   sur `vm-reseau`.
6. Test de migration : `migrate.sh externes vm-donnees` (cohorte sans
   données propres, sans risque), puis retour.

## Limites connues et suites (BACKLOG 75)

Non exécuté ici (pas de Swarm ni de VM dans l'environnement de
développement) : scripts relus, `cohorts.py` exécuté sur le dépôt réel
(73 services, 8 cohortes, 52 dépendances croisées, stack générée), à
tester sur une première VM. Keycloak/tls-proxy vivent dans
`gateway/docker-compose.yml` : la stack les inclut ; `gateway/scripts/run.sh`
(realm, groupes) reste à jouer sur le manager. Ports UDP (rsyslog) et
TCP publiés : sur le nœud de la cohorte seulement (pas de mesh ingress,
volontaire). Suites : tuile hub « Répartition » par-dessus l'API Swarm
(charge des nœuds, cohortes, bouton migrer), stockage partagé (NFS) pour
lever l'épinglage, `configure` des sauvegardes totales par nœud.
