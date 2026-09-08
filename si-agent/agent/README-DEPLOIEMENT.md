# si-agent — déploiement sur un hôte Linux

Archive autonome (`si-agent-agent-<version>.tar.gz`) : l'agent, ses
plugins livrés, et DEUX façons de l'installer. Prérequis communs : un
identifiant d'agent et son secret, **enrôlés sur le hub** (tuile Agents
hôtes → Enrôler un agent → bouton *Installation* : la commande complète
s'affiche, avec l'URL du central et l'empreinte de la CA).

```bash
tar xzf si-agent-agent-*.tar.gz && cd si-agent-agent-*/
```

## Variante 1 — conteneur Docker (l'hôte a Docker)

```bash
sudo ./docker/deploy-docker.sh --agent srv-01 --secret 'SECRET' \
     --central https://VM:6443/api/si-agent --site siege --ca-fingerprint <sha256>
```

Construit l'image sur place (`python:3.12-slim` + iproute2, procps,
util-linux, journalctl), écrit `/etc/si-agent/agent.json` (600) sur
l'hôte, lance le conteneur `si-agent` (`--restart unless-stopped`,
`--network host --pid host`, `/` de l'hôte monté en lecture seule sous
`/host`, file et plugins persistants dans `/var/lib/si-agent`). Ce que
l'agent voit ainsi : le vrai OS, les vrais disques, processus, ports,
connexions, voisins ARP, routes, journal, comptes, sessions. Ce qu'il ne
voit pas : les unités systemd en échec (signalé « partial : systemctl »),
sauf si le bus D-Bus de l'hôte est joignable (monté automatiquement s'il
existe, à confirmer). `DOCKER_SOCK=1 sudo ./docker/deploy-docker.sh …`
monte aussi le socket Docker en lecture seule pour le plugin
`docker-containers`.

```bash
docker logs -f si-agent                                     # traces
docker exec si-agent python3 -m si_agent.agent --status     # file, blocage, derniers risques
docker exec si-agent python3 -m si_agent.agent --collect    # collecte à blanc (hôte, risques, réseau, matériel)
sudo touch /etc/si-agent/BLOCKED                            # blocage local d'urgence des sondes
sudo ./docker/deploy-docker.sh                              # mise à jour (config conservée)
docker rm -f si-agent                                       # arrêt
```

## Variante 2 — service systemd (sans Docker)

```bash
sudo ./install.sh --agent srv-01 --secret 'SECRET' \
     --central https://VM:6443/api/si-agent --site siege --ca-fingerprint <sha256>
```

Python 3 système, aucune dépendance ; copie dans `/opt/si-agent`, plugins
dans `/var/lib/si-agent/plugins`, service `si-agent.service`. Prérequis
utiles : `iproute2` (ip, ss), util-linux (lscpu, lsblk, last).

```bash
systemctl status si-agent ; journalctl -u si-agent -f
PYTHONPATH=/opt/si-agent python3 -m si_agent.agent --status
PYTHONPATH=/opt/si-agent python3 -m si_agent.agent --collect
```

## Options communes

`--ca /chemin/ca.crt` (certificat fourni) ou `--ca-fingerprint <sha256>`
(récupéré du central et vérifié par empreinte, recommandé) ou
`--insecure` (dépannage seulement, signalé au central) ;
`--enable-plugin network-neighbors` (balayage ping, trafic actif,
désactivé par défaut) ; `--log-level DEBUG`.

## Réseau

L'hôte doit joindre le central en sortie sur le port de la passerelle TLS
(6443 par défaut) ; rien en entrée. Un sous-réseau isolé/filtré joignable
par route directe convient : la vue réseau passive de l'agent le montre
(sous-réseaux attachés, passerelle et son état ARP, routes directes,
pairs).

## Si la ligne reste « jamais vu » sur le hub

`docker exec si-agent python3 -m si_agent.agent --once -v` (ou
`PYTHONPATH=/opt/si-agent python3 -m si_agent.agent --once -v`) montre la
requête et la réponse : 401 = secret ou identifiant ; erreur TLS =
empreinte / certificat ; délai = filtrage réseau vers le port 6443.
