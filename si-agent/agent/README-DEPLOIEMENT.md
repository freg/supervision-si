# si-agent — déploiement sur un hôte Linux ou Windows

Archive autonome (`si-agent-agent-<version>.tar.gz`) : l'agent, ses
plugins livrés, et TROIS façons de l'installer (Docker, systemd, Windows). Prérequis communs : un
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

## Variante 3 — Windows 10 / 11 (livraison #440)

Même archive (décompressée avec l'Explorateur, 7-Zip ou `tar xzf` qui
existe sous Windows 10+), PowerShell **en administrateur** :

```powershell
Set-Location .\si-agent-agent-<version>\
.\windows\install.ps1 -Agent 'pc-compta' -Secret 'SECRET' -Central 'https://VM:6443/api/si-agent' -Site 'siege' -CaFingerprint <sha256>
```

(la commande exacte, secret et empreinte compris, est affichée par le
bouton *Installation* de la tuile). Si PowerShell refuse d'exécuter le
script : `Set-ExecutionPolicy -Scope Process Bypass` puis relancer.

Ce que fait `install.ps1` : cherche **Python 3.8+** (`py`, `python` --
l'alias du Store est ignoré) et, s'il n'y en a pas, télécharge la
distribution *embeddable* de python.org (~11 Mo, aucune installation
système, `-PythonUrl` pour un miroir, `-NoDownload` pour refuser) dans
`C:\Program Files\si-agent\python` ; copie `si_agent\` et `plugins\`
dans `C:\Program Files\si-agent` ; récupère la CA du central et la
vérifie par empreinte (`-Ca C:\chemin\ca.crt` pour un certificat
fourni, `-Insecure` en dépannage) ; écrit `C:\ProgramData\si-agent\agent.json`
(lecture réservée à SYSTEM et aux administrateurs) ; enregistre une
**tâche planifiée `si-agent`** (compte SYSTEM, au démarrage, relancée
chaque minute si elle s'arrête, sans limite de durée) et la lance. Pas de
service Windows à proprement parler : la tâche planifiée fait la même
chose sans dépendance (pywin32, NSSM) -- un vrai service reste possible
plus tard si le besoin apparaît.

Ce que l'agent remonte sous Windows (scripts PowerShell 5.1 livrés dans
`si_agent\win\`, un par mesure, lisibles et exécutables à la main) :
système (édition, build, version d'affichage, domaine, redémarrage en
attente), CPU, mémoire et fichier d'échange, lecteurs locaux / amovibles /
réseau (les lecteurs réseau mappés par un utilisateur ne sont pas visibles
du compte SYSTEM : c'est normal), services automatiques arrêtés, ports en
écoute, erreurs des journaux Système et Application (24 h),
administrateurs et comptes locaux, Windows Update (redémarrage en attente,
dernier correctif, mises à jour en attente), Defender (activé, temps réel,
âge des signatures), pare-feu par profil, BitLocker sur C: ; activité :
processus (CPU sur 1 s, mémoire), sessions (`quser` et sessions de
connexion), dernières ouvertures de session (journal Sécurité, 4624),
services en cours ; inventaire : fabricant, modèle, n° de série, UUID,
BIOS, carte mère, CPU, disques physiques (NVMe/SSD/HDD, santé), cartes
réseau, GPU, **logiciels installés** (registre, 400 premiers) ; vue
réseau passive : adaptateurs, adresses, routes, voisins ARP/NDP,
connexions établies avec le processus, DNS. Risques ajoutés : Defender
inactif / temps réel désactivé / signatures anciennes, profil de pare-feu
désactivé, mises à jour en attente.

Sondes sous Windows : `runner: "python"` (le Python de l'agent) ou
`runner: "powershell"` (nouveau) ; une sonde `shell` (bash) est refusée
avec un message clair. Pas de confinement setuid/rlimit : environnement
réduit aux variables système, dossier de la sonde, délai qui tue le
processus. Commandes utiles :

```powershell
Get-ScheduledTask si-agent | Get-ScheduledTaskInfo          # état, dernier lancement
Get-Content C:\ProgramData\si-agent\agent.log -Wait          # traces
& 'C:\Program Files\si-agent\python\python.exe' -m si_agent.agent --config C:\ProgramData\si-agent\agent.json --collect   # collecte à blanc (depuis C:\Program Files\si-agent)
New-Item C:\ProgramData\si-agent\BLOCKED                   # blocage local des sondes
.\windows\uninstall.ps1 [-KeepData]                        # désinstallation
```

⚠️ Écrit et exécuté sous PowerShell 7 Linux (syntaxe, enchaînement,
JSON) et testé sur des sorties représentatives, **pas encore sur un
Windows réel** : le premier poste dira ce qui manque (noms de propriétés
CIM, droits, temps d'exécution des scripts).

## Options communes

`--ca /chemin/ca.crt` (certificat fourni) ou `--ca-fingerprint <sha256>`
(récupéré du central et vérifié par empreinte, recommandé) ou
`--insecure` (dépannage seulement, signalé au central) ;
`--enable-plugin network-neighbors` (balayage ping, trafic actif,
désactivé par défaut) ; `--log-level DEBUG`.

## Montages réseau et FUSE (sshfs, NFS, CIFS…)

Depuis 0.3.2 (#438) l'agent liste TOUS les montages de l'hôte, y compris
ceux qu'il ne peut pas mesurer, avec la raison :

- **sshfs / FUSE** : un montage FUSE n'est lisible que par l'utilisateur
  qui l'a monté (sauf `allow_other`/`allow_root`) ; aux autres, root
  compris, il renvoie des tailles nulles. Depuis 0.3.3 (#439) l'agent, s'il
  est root (service systemd et conteneur : c'est le cas), le mesure en se
  présentant comme cet utilisateur (`user_id=` des options de montage) --
  **rien à changer sur l'hôte**, la tuile indique « (uid N) » à côté du
  type. Seul un agent non root a besoin de `-o allow_root` (et de
  `user_allow_other` dans `/etc/fuse.conf`) ; sinon le montage apparaît
  « illisible » avec la raison, jamais silencieusement absent. Les
  systèmes distants sont mesurés avec un délai de 5 s : un serveur qui ne
  répond plus donne « sans réponse », sans bloquer la collecte.
- **« invisible du conteneur »** (déploiement Docker) : le montage a été
  fait sur l'hôte après le démarrage du conteneur. `deploy-docker.sh`
  monte maintenant `/` en `rslave` pour que les nouveaux montages se
  propagent ; un conteneur lancé avec l'ancien script doit être relancé
  (`deploy-docker.sh` à nouveau, mêmes paramètres, ou
  `docker restart si-agent`).
- **NFS « périmé »** : serveur injoignable (stale file handle).

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
