# Démo Numeria — runbook de préparation sur site

Objectif de la démo : montrer, sur les données réelles du campus, ce que la
supervision repère d'anormal — routes, résolution de noms, itinérance Wi-Fi,
engorgement, pertes de connexion, comportements agressifs, décrochages,
hachages. Support de lecture : la tuile **Agents hôtes** et son nouvel onglet
**Observabilité réseau** (#643), plus la **bande passante** de la tuile
Proxmox (#644).

Contrainte réseau clé : **le Proxmox campus n'a pas de route vers le hub
super.** Tout se joue donc sur le LAN campus, autour du **minipc pc-numeria**
qui tient le rôle de **central local** (pile autonome `si-agent/standalone`,
même image et mêmes données que sous le hub, + un front nginx qui sert
l'interface Agents hôtes). On lit les relevés sur place, sur ce minipc.

## 0. Prudence (à garder sous la main tout du long)

Kill switch d'un agent, du plus doux au plus radical :

    touch /var/lib/si-agent/BLOCKED          # bloque les sondes, garde l'agent
    systemctl stop si-agent                  # arrête l'agent
    systemctl disable --now si-agent         # + ne repart pas au boot

Depuis le hub/central : tuile Agents hôtes → onglet Flotte → « Blocage
général » (arrêt d'urgence de toutes les sondes, tous agents).

Principe : un coup d'avance. On active une chose à la fois, on regarde un
cycle, on garde le moyen d'annuler avant de passer à la suite.

## 1. Central local sur le minipc pc-numeria

Prérequis : Docker présent, dépôt au même chemin, `.env` copié depuis super
(contient `HOST_IP`, `PKI_DIR`), `pki/ca/ca.crt` seul, dossier de données
des agents. Puis, depuis la racine du dépôt sur le minipc :

    cd ~/…/supervision-si/si-agent/standalone && ./run.sh

Le front écoute sur `SI_STANDALONE_HTTP_PORT` (défaut **6480**). UI locale :
`http://<ip-minipc-campus>:6480/agents/` (auth basique locale, identifiant /
mot de passe du `.env`, `SI_STANDALONE_PASSWORD`). Vérifier que la page
Agents hôtes s'affiche et que la santé de l'API est verte.

## 2. Jeton d'enrôlement (sur le central LOCAL, pas le super)

UI locale du minipc → tuile **Agents hôtes** → onglet **Déploiement** →
**Créer le jeton**, site `numeria`, **central_url = l'URL campus du minipc**
(`https://<ip-minipc>:6480/api/si-agent` selon la conf), surtout pas le
super. La ligne générée pointera les agents vers le minipc. L'enrôlement
lui-même (`/api/v1/enroll`) passe en HMAC, sans auth basique.

## 3. Sondes réseau sur pc-numeria (agent déjà en place)

Depuis l'onglet **Catalogue de sondes** (affecter au poste pc-numeria), avec
ces arguments :

- `dns-observe` : `--names numeria.keepic.net,www.campus-numeria.fr,detectportal.firefox.com --expected-gateway`
  (le résolveur légitime d'un segment est sa passerelle ; le firewall
  172.16.x.1 a une patte par VLAN et fait passerelle ET DNS).
- `resource-access` : `--names-map 51.15.207.13=numeria-keepic,5.135.23.164=campus-numeria`
  (vue réseau réelle seulement si pc-numeria est passerelle ou sur un port
  miroir ; sinon flux de ce poste).
- `path-probe` : `--ifaces auto --connections numeria`.
- `wifi-probe` : défaut.

Laisser tourner un cycle, puis lire l'onglet **Observabilité réseau** :
divergences DNS triées par gravité (dont `dns-not-gateway`) + détail « qui
résout quoi », et accès ressources (constats + ressources agrégées).

## 4. Agent sur le Proxmox campus — install PRUDENTE

La ligne pipe du hub lance `install.sh` **sans** `--no-detect` ; or sur un
hôte PVE, `install.sh` **auto-active le plugin proxmox** (#524). On veut le
plugin **éteint** au départ. Donc install manuelle, plugin proxmox off :

    cd /tmp
    # récupérer l'archive de l'agent depuis le minipc (dépôt local du minipc,
    # ou /package derrière l'auth basique du front) ; puis :
    tar xzf si-agent.tgz && cd si-agent-*/
    SI_AGENT_ENROLL_TOKEN='<jeton>' SI_AGENT_CENTRAL='https://<ip-minipc>:6480/api/si-agent' \
      SI_AGENT_SITE='numeria' ./install.sh --no-detect

Vérifier : `systemctl status si-agent`, `journalctl -u si-agent -n 50`,
empreinte CPU/mémoire au repos. L'agent doit apparaître dans la flotte du
central local sous son nom de machine.

## 5. Plugin proxmox : activation surveillée

Quand l'agent est stable et l'impact nul : UI locale → fiche de l'agent
Proxmox → activer le plugin **proxmox** (lecture seule : `pvesh get`,
`zpool list/status`, `rrddata`). Regarder **un** cycle : charge de l'hôte,
warnings de la mesure. La **bande passante** (nœud + par VM, tranche
horaire, fenêtre unitaire estimée) s'affiche dans la tuile Proxmox (#644) ;
si `rrddata` pèse ou manque, elle se dégrade en warning sans bloquer.

Kill switch identique (`BLOCKED` / `systemctl stop`).

## 6. Inventaire VM (avant/à côté du plugin)

Script fourni `proxmox-vm-inventory.sh` (lecture seule + connect TCP léger),
à lancer en root sur le Proxmox : liste `VMID · nom · statut · OS · IP ·
ports ouverts`. `NOSCAN=1` pour OS/IP seuls, sans scan.

## Ce qu'on montre le lendemain après-midi

Sur l'UI locale du minipc, onglet **Observabilité réseau** : les divergences
DNS par segment (l'incident vidéo assistants OK / contrôleur d'écrans KO), le
`dns-not-gateway` s'il y a lieu, les ressources externes réellement
contactées. Tuile **Proxmox** : VM, IP/MAC, et **bande passante par tranche
horaire** pour l'engorgement. Sondes `path-probe` / `wifi-probe` pour
itinérance, décrochages, comportements agressifs.
