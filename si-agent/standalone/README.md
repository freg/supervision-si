# Agents hôtes en mode autonome (livraison #517)

Demande : « le hub même allégé met à genoux le Proxmox et la VM super ;
déployer la gestion des agents en mode indépendant mais compatible, en
gardant la liste des agents et les données remontées, avec un bouchon
à la place de Keycloak et une authentification locale / mode dégradé ;
les IP et le NAT ne bougent pas : un proxy sur super aiguille vers une
VM d'un autre Proxmox ».

## Ce que c'est

Deux petites piles compose, indépendantes du hub :

- **la pile autonome** (`si-agent/standalone/docker-compose.yml`, sur une
  VM légère) : `si-agent-api` (même image et MÊME dossier de données que
  sous le hub), un `memcached` (journal partagé, 64 Mo), et `front`, un
  nginx qui sert l'interface « Agents hôtes » **en statique** (la tuile
  du hub, `hub/src/SiAgentView.jsx`, construite par Vite au build de
  l'image : aucun serveur de développement à l'exécution) et remplace
  Keycloak par une **auth basique locale** (identifiant / mot de passe du
  `.env`). Les agents, eux, restent authentifiés par leur signature HMAC
  et n'ont jamais d'auth basique.
- **l'aiguillage** (`si-agent/standalone/edge/`, sur super) : un nginx
  seul sur le port de la passerelle (6443) avec le certificat de
  `pki/server`, qui renvoie tout vers la VM autonome. Les agents
  continuent d'appeler `https://<super>:6443/api/si-agent/…` sans rien
  changer (même CA épinglée, même chemin).

Ce qui est préservé : la liste des agents, les mesures, risques,
inventaires, sondes, commandes, événements -- tout ce que si-agent-api
sait faire, sur les mêmes données (`SI_AGENT_DATA_DIR`).

## Mise en place

Sur la VM autonome (Docker, `python3` inutile) : dépôt au même chemin,
copie du `.env` de super (il contient `HOST_IP` = super, que les agents
joignent ; `PKI_DIR` absolu de préférence), copie de `pki/ca/ca.crt`
seul (jamais `ca.key`) et du dossier de données des agents
(`si-agent/data` ou `SI_AGENT_DATA_DIR`) -- ou son déplacement définitif
sur cette VM, c'est elle qui l'héberge désormais.

```
# .env : SI_STANDALONE_USER=admin  SI_STANDALONE_PASSWORD=…  SI_STANDALONE_HTTP_PORT=6480
si-agent/standalone/run.sh up -d --build
si-agent/standalone/run.sh ps
```

Sur super (hub et passerelle arrêtés : `./scripts/run.sh down`,
`./gateway/scripts/run.sh down`) :

```
# .env : SI_STANDALONE_UPSTREAM=<ip de la VM autonome>:6480
si-agent/standalone/run.sh edge up -d
```

Interface : `https://<super>:6443/agents/` (identifiant local). Les agents
reprennent leurs dépôts à la première mesure suivante.

## Retour au hub

Quand le hub revient (mode réparti #513, cohorte `agents` affectée à
cette VM dans `deploy/nodes.json`) : `run.sh edge down` sur super,
`run.sh down` sur la VM, puis l'installeur / `repartition.py apply` :
compose relance `si-agent-api` sur le même dossier de données et
tls-proxy relaie `/api/si-agent/` vers la VM. Rien à migrer.

## Limites

Mode dégradé assumé : un seul identifiant local (htpasswd, `openssl
passwd -apr1`), pas de rôles ; le relais d'exploration (captures vers
network-agent-api) et les notifications par les canaux du hub ne
fonctionnent que si ces services tournent ; entre super et la VM le
trafic est en HTTP clair (LAN ou VPN) -- mettre l'aiguillage sur la VM
elle-même si ce lien traverse un réseau non maîtrisé.
