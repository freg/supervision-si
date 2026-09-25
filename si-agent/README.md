# si-agent — agent hôte Linux, moteur de sondes et central (livraisons #420 à #422)

Demandé : « une sonde linux… un agent qui permette d'auditer le host et sa
zone réseau… déployer des sondes futures en python ou en shell/bash », précisé
par « l'agent host surveille le host (cpu, disque, mémoire, log, risques
internes) et il sert de machine-moteur pour la gestion de plugin/sonde ».
Décision de la personne : **nouveau paquet `si-agent`**, distinct de
`netprobe/agent` (sonde réseau Raspberry Pi) — les deux partagent seulement
le protocole signé et la file locale (copiés, voir `sync-shared.sh`).

Backlog 63. #420 = **l'agent** (`agent/`, côté hôte) ; #421 = le **central**
`si-agent-api` (`api/`) et la tuile hub **« Agents hôtes »** (menu Réseau,
`VITE_SI_AGENT_API_BASE_URL`). Le contrat entre les deux est le protocole
décrit plus bas, vérifié par une chaîne réelle agent ↔ central en test.

## Ce que fait l'agent

Une boucle Python 3 sans dépendance (Debian/Ubuntu/Raspberry Pi OS, Python
système), service systemd, qui :

1. **Surveille l'hôte** toutes les `host_interval_seconds` (60 s) — mesure
   `host` : système (OS, noyau, modèle CPU/Raspberry, uptime, redémarrage
   requis), CPU (% sur l'intervalle, charges 1/5/15), mémoire et swap,
   disques (montages réels seulement, pseudo-fs écartés), unités systemd en
   échec, ports en écoute avec processus et exposition (`ss -Hlntup`), erreurs
   du journal sur 24 h (`journalctl -p err`, sinon `/var/log/syslog`),
   comptes (sudoers, shells interactifs, UID 0 hors root). Une source
   absente (pas de `ss`, pas de `systemctl`) est listée dans `partial` et la
   mesure passe `ok: false` — jamais silencieux.
2. **Évalue les risques internes** (`risks`, `si_agent/risks.py`) : constats
   purs et lisibles — `disk-full`/`disk-high`, `memory-high`, `swap-high`,
   `load-high`, `reboot-required`, `recent-boot`, `service-failed`,
   `port-exposed` (liste courte de ports sensibles : Telnet, FTP, SMB, RDP,
   VNC, bases sans authentification par défaut…), `uid0-account`,
   `log-errors`. Seuils dans `DEFAULT_THRESHOLDS`, surchargés par
   `risk_thresholds` de la configuration locale puis par le central.
3. **Inventorie** (`inventory`, toutes les heures) : outils présents
   (`nmap`, `tcpdump`, `iperf3`, `snmpwalk`, `smartctl`, `vcgencmd`…),
   plugins installés, version de l'agent.
4. **Exécute les sondes (plugins)** — shell ou Python — chacune à son
   rythme, mesure `plugin:<id>`.
5. **Met en file** toutes les mesures dans SQLite (`/var/lib/si-agent/queue.db`)
   et les **envoie signées** au central par lots ; panne réseau = rien de
   perdu, envoi à la reconnexion.
6. **Se pilote depuis le central** : configuration versionnée (intervalle,
   seuils, plugins à installer/retirer) et commandes acquittées.
7. **Découvre passivement son réseau** (#428, `si_agent/netview.py`, mesure
   `netview` toutes les `netview_interval_seconds` = 300 s) : interfaces et
   adresses, routes (passerelle par défaut, **routes directes** vers d'autres
   sous-réseaux -- le cas « sous-réseau isolé/filtré mais accessible par
   route directe »), voisins ARP/NDP déjà résolus par le noyau, connexions
   établies groupées par pair (IP, ports, processus, local/routé), DNS.
   **Jamais un paquet émis** : le balayage reste dans le plugin
   `network-neighbors`, désactivé par défaut.
8. **Revue de l'hôte** (#428, `si_agent/review.py`) : `hardware` dans
   l'inventaire (constructeur/modèle DMI ou Raspberry, n° de série, BIOS,
   CPU via `lscpu`, mémoire installée, disques physiques via `lsblk`,
   cartes réseau et vitesse, virtualisation via `systemd-detect-virt`) ;
   `activity` dans la mesure `host` (processus les plus gourmands en CPU et
   en mémoire, nombre de processus, sessions ouvertes `who`, dernières
   connexions `last`, services systemd actifs, mises à jour en attente).

Dans le futur tableau de bord, l'agent est pensé pour se retrouver aussi
dans l'inventaire GLPI (backlog 63, « agents glpi »).

## Plugins / sondes

Un plugin = un dossier `<plugins_dir>/<id>/` avec `manifest.json` et son
script :

```json
{"id": "network-neighbors", "version": "1", "runner": "shell",
 "entry": "network_neighbors.sh", "interval_seconds": 3600,
 "timeout_seconds": 120, "args": [], "enabled": false,
 "description": "…", "sha256": "…", "signature": "…", "source": "bundled"}
```

Le script est lancé par `bash` ou `python3`, délai borné, sortie standard
attendue en **JSON** (sinon conservée en texte brut tronqué), code de
retour ≠ 0 = mesure en erreur. `id` = minuscules/chiffres/`-`/`_`, `entry`
= nom de fichier simple (jamais un chemin), intervalle ≥ 30 s.

**Activation** : `enabled` du manifeste décide, la configuration locale
(`"plugins": {"network-neighbors": {"enabled": true}}` dans `agent.json`)
l'emporte — le technicien sur place garde la main même sur un plugin
poussé par le central.

**Deux origines, deux niveaux de confiance** :

- `bundled` : livrés avec le paquet (`agent/plugins/`), copiés par
  `install.sh`, **désactivés** par défaut ;
- `central` : reçus du central. **Jamais écrits sur le disque sans
  vérification** : `sha256` du corps reçu = manifeste, et `signature` =
  HMAC-SHA256(secret de l'agent, `id\nversion\nsha256`). Même secret que
  l'authentification des mesures : seul le central qui connaît cet agent
  peut lui pousser du code (les plugins tournent avec les droits du
  service, root).

Plugins livrés (exemples des deux runners, désactivés) :

- `network-neighbors` (shell) — « la zone réseau » : voisins ARP/NDP
  (`ip neigh`), sous-réseaux locaux, balayage ping du /24 principal
  (`SI_NEIGHBORS_SWEEP=0` pour se limiter aux voisins déjà vus).
- `docker-containers` (python) — conteneurs de l'hôte : état, image,
  redémarrages, ports publiés (socket Docker requis).
- `capture-relay` (python, privilégié, #436) — **relais d'exploration
  réseau** : capture tcpdump bornée (60 s, 1,5 Mo, en-têtes seulement :
  snaplen 96) sur l'interface de la route par défaut, rendue en JSON
  (`pcap_base64`, `cidr`, `packets`, `truncated`) ; le central la verse dans
  network-agent-api (`POST /capture/upload`, `NETWORK_AGENT_API_URL`) --
  site de l'agent, segment = nom d'hôte -- où elle est traitée comme une
  capture locale (appareils, liens, services, IP distantes, sous-réseaux).
  Réglages par les `args` du manifeste (`--seconds`, `--max-bytes`,
  `--snaplen`, `--interface`). Toutes les 15 min par défaut, **désactivé**
  (trafic réel observé) : à activer par hôte depuis le catalogue ou
  `--enable-plugin capture-relay`. En conteneur (deploy-docker.sh),
  `--network host` suffit (tcpdump dans l'image).
- `proxmox` (python, privilégié, #487-488) — **hyperviseur Proxmox VE** :
  VM/CT (état, CPU, RAM, disques), snapshots (âge), backups (dernier
  par VM), stockages, pools ZFS (santé, capacité, erreurs). Adressage
  IP des VM par qemu-guest-agent quand il répond, interfaces LXC
  natives sinon — aucune IP inventée, le hub recoupe par ailleurs.
  **Apprentissage par exploration (#488)** : pour chaque VM en marche
  avec IP connue, balayage TCP connect BORNÉ (ports courants, 0,4 s,
  16 fils — jamais un nmap), sondes TLS (certificat lu même auto-signé
  ou expiré : CN, SAN, jours restants — la validité est un constat,
  pas un filtre) et HTTP (statut, Server, titre, redirection), PTR,
  puis **URLs entrantes apprises** (SAN, CN, PTR, hôtes de redirection)
  avec résolution DNS interne : un nom qui résout vers l'IP de la VM
  est une URL entrante probable ; un nom qui ne résout pas est un trou
  DNS rapporté, pas masqué. Collecte locale par `pvesh` (aucun mot de
  passe stocké) + `zpool` ; toutes les 30 min, désactivé par défaut :
  **activé automatiquement par `install.sh` sur un hôte Proxmox VE**
  (`/etc/pve` + `pvesh` : plugin `proxmox` et sondes en root, #524 ;
  `--no-detect` pour l'éviter), sinon `--enable-plugin proxmox
  --plugins-user root` ou catalogue central. Le central sert la synthèse sur `GET /proxmox` ;
  la supervision SI affiche chaque VM (type « VM / conteneur »)
  fusionnée par IP, et la tuile hub **Proxmox** (thématique Réseau)
  l'arbre hôte → VM avec services et URLs appris. Le host Proxmox
  lui-même est déjà supervisé par la mesure `host` de l'agent — ce
  plugin ne couvre que le spécifique PVE.
- `wifi-probe` (python, privilégié, #525) — **sonde Wi-Fi « expérience
  client »**, première sonde de la famille *explorer* : le poste qui porte
  l'agent est associé comme un utilisateur au SSID à observer (interface
  Wi-Fi **sans route par défaut**, l'Ethernet reste le chemin vers le
  central : `nmcli connection modify <c> ipv4.never-default yes`). Chaque
  minute : lien (`iw link` / `station dump` : borne, canal, RSSI, débits
  négociés, retransmissions et échecs sur le delta du passage précédent),
  occupation du canal (`survey dump`, y compris le trafic des autres),
  voisinage (`iw scan` : bornes par canal, co-canal, élément *BSS Load* des
  balises = stations et utilisation vues par la borne), chemin (`ping -I`
  vers la passerelle du Wi-Fi : latence, gigue, pertes) et, si `iperf3` est
  présent et l'argument `--iperf HOTE` donné dans le manifeste, un flux UDP
  de 20 Mbit/s type cast (gigue, pertes). Constats sans action : non
  associé, signal faible, retransmissions, canal saturé, débit négocié bas,
  gigue/pertes, borne chargée, 2,4 GHz. Fiche agent → section « Wi-Fi vu du
  poste » avec historique des passages (pires valeurs, bornes utilisées).
  v2 (#526, premier retour terrain) : trafic généré avant la lecture du
  lien (au repos le pilote annonce 6 Mbit/s), passerelle lue dans l'option
  DHCP `routers` (le Wi-Fi n'a pas de route par défaut), co-canal compté
  par borne et non par SSID, pas d'alerte débit sans échantillon de trafic.
  v3 (#529) : liste des radios visibles avec leur *BSS Load* à chaque scan
  (utilisation des canaux par borne dans le temps, volet « Bornes vues du
  poste » de la fiche agent), constat « canal occupé sans client ».
  Requiert `iw`, `ping`, `ip` ; état entre deux passages dans
  `/var/lib/si-agent/wifi-probe.state.json`. Activation : `--enable-plugin
  wifi-probe` ou depuis la fiche agent.
- `path-probe` (python, privilégié, #527) — **sonde « chemin de service »**,
  deuxième sonde *explorer* : rejoue chaque minute, par interface IPv4 du
  poste, ce qu'un utilisateur subit quand il dit « je n'ai plus Internet »,
  dans l'ordre où ça casse -- **bail** (adresse, serveur DHCP, passerelle et
  DNS reçus, âge / durée du bail ; adresse statique signalée), **passerelle**
  (ping court : latence, pertes), **DNS distribués** (requête UDP/53 vers
  CHAQUE serveur reçu du DHCP : un serveur mort parmi d'autres est un
  constat, un seul serveur distribué en est un autre), **DNS publics**
  (8.8.8.8, 1.1.1.1 : sortie UDP/53), **HTTP réel** (GET d'une page de test
  connue ; portail captif / interception détectés sur la redirection ou le
  contenu) et **HTTPS** (certificat vérifié ; certificat invalide =
  interception). Sockets liés à l'adresse de l'interface ; interface sans
  route par défaut (Wi-Fi d'observation) : table de routage dédiée posée le
  temps du passage (`ip rule from <ip> lookup 250+i`) puis retirée. Option
  `--connections wifi-a,wifi-b` dans le manifeste : à chaque passage la
  sonde active la connexion NetworkManager suivante, donc un **vrai échange
  DHCP sur chaque SSID à tour de rôle** (la sonde `wifi-probe` mesure alors
  le SSID actif, son historique reste lisible par SSID). Autres arguments :
  `--name` (nom résolu, défaut `www.google.com`), `--public-dns`, `--http`,
  `--https` (`none` pour désactiver). Constats sans action : pas d'adresse,
  activation échouée, passerelle injoignable / pertes / lente, aucun DNS
  distribué, DNS unique, DNS distribué muet, tous muets, DNS publics coupés,
  HTTP/HTTPS en échec, portail captif, résolution ou page lente. Fiche agent
  → section « Chemin de service vu du poste » : tableau par chemin (bail,
  passerelle, chaque DNS avec sa latence, publics, HTTP, HTTPS, état),
  constats, historique par chemin (passages sans adresse, DNS muet, HTTP en
  échec, pires latences). Requiert `ip`, `ping`, `nmcli` (`iw` pour le
  SSID) ; état dans `/var/lib/si-agent/path-probe.state.json`. Activation :
  `--enable-plugin path-probe` ou depuis la fiche agent.
- Constats des sondes → notifications (#530) : le central compare les
  constats warning/critical de chaque mesure `plugin:wifi-probe` /
  `plugin:path-probe` avec la précédente ; nouveaux constats → événement
  `probe-alert` (sévérité la pire), constats disparus → `probe-recovered`
  (info) ; ces événements suivent le circuit de notification habituel
  (`SI_AGENT_NOTIFY_*`, `SECRETS_ALERT_*`). Un constat persistant n'est pas
  répété.

## Installation

```bash
cd si-agent/agent
sudo ./install.sh --agent srv-01 --secret 'SECRET' \
     --central https://VM:6443/api/si-agent --site siege \
     [--ca ca.crt | --ca-fingerprint <sha256> | --insecure] \
     [--enable-plugin network-neighbors] [--plugins-user nobody] [--log-level DEBUG]
```

Copie le paquet dans `/opt/si-agent`, les plugins dans
`/var/lib/si-agent/plugins`, écrit `/etc/si-agent/agent.json` (mode 600),
installe et démarre `si-agent.service`. Sur place :

```bash
PYTHONPATH=/opt/si-agent python3 -m si_agent.agent --status    # file, plugins, derniers risques
PYTHONPATH=/opt/si-agent python3 -m si_agent.agent --collect   # une collecte hôte + risques, affichée, sans envoi
PYTHONPATH=/opt/si-agent python3 -m si_agent.agent --once      # un passage complet (config, collecte, plugins, envoi)
PYTHONPATH=/opt/si-agent python3 -m si_agent.agent --block "incident" # blocage général local (ou : touch /etc/si-agent/BLOCKED)
```

### Relais d'exploration réseau (#436)

Voir le plugin `capture-relay` ci-dessus. Chaîne vérifiée ici : plugin réel
(tcpdump 5 s dans le conteneur) → agent → central réel
(`NETWORK_AGENT_API_URL`) → network-agent-api réel : site « cloud »,
segment « vm », l'hôte avec son IP et la passerelle comptée comme relais
(228 paquets) sans IP usurpée (#427). Backlog 63 (e) livré ; le
`docker/Dockerfile` de l'agent embarque tcpdump.

### Archive de déploiement et variante conteneur (#430)

**#518 : l'archive est construite dans l'image de si-agent-api et servie par
`GET /api/si-agent/package`** (`/package/info` : nom, version, taille,
SHA-256). Dans la tuile, la fiche d'un agent donne le lien de
téléchargement et une ligne `curl … && sha256sum -c && tar xzf … && cd …`
à coller sur l'hôte avant la commande d'installation. En local,
`si-agent/make-archive.sh [dossier]` produit `si-agent-agent-<version>.tar.gz`
(paquet, plugins, `install.sh` + systemd, `docker/`, `README-DEPLOIEMENT.md`,
sans secret). Sur un hôte qui a Docker :

```bash
sudo ./docker/deploy-docker.sh --agent srv-01 --secret 'SECRET' --central https://VM:6443/api/si-agent --site siege --ca-fingerprint <sha256>
```

Image construite sur place (`python:3.12-slim` + iproute2, procps,
util-linux, journalctl), conteneur `si-agent` en `--network host --pid host`
avec `/` de l'hôte monté en lecture seule sous `/host`
(`SI_AGENT_HOST_ROOT` : `/etc`, `/var`, `/boot` sont lus là, les montages
de l'hôte seuls sont comptés, `journalctl -D /host/var/log/journal`),
`/etc/si-agent` et `/var/lib/si-agent` persistants, `utmp`/`wtmp` et le bus
D-Bus montés s'ils existent, socket Docker avec `DOCKER_SOCK=1`. Le bouton
*Installation* de la tuile affiche les deux commandes. Limite : sans bus
D-Bus joignable, `systemctl --failed` est indisponible (partial). Vérifié
ici : collecte avec `/` re-monté sous `/host` (OS, disques sans préfixe,
journal, comptes) ; non vérifié : `docker build`/`run` réels.

### Premier hôte réel : un Linux dans un sous-réseau isolé/filtré (#428)

1. Sur le hub, tuile **Agents hôtes → Enrôler un agent** : identifiant
   (ex. `srv-isole-01`), site. Le bouton **Installation** de la ligne affiche
   la commande complète (secret, URL du central, empreinte de la CA).
   `SI_AGENT_PUBLIC_URL` doit être l'URL du central **telle que l'hôte la
   joint** (l'hôte est derrière un filtrage : seul le port de la passerelle
   TLS, 6443 par défaut, doit être ouvert de l'hôte vers la VM, en sortie).
2. Copier le dossier `si-agent/agent/` sur l'hôte (`scp -r`, clé USB…), puis
   la commande d'installation en root. Prérequis : Python 3 système,
   `iproute2` (`ip`, `ss`), systemd ; `lscpu`/`lsblk` (util-linux) et
   `last` (util-linux ou wtmpdb) pour la revue -- absents, ils sont
   simplement listés dans `partial`.
3. Vérifier sur place, avant même que le central réponde :
   `PYTHONPATH=/opt/si-agent python3 -m si_agent.agent --collect` (JSON :
   `host`, `risks`, `netview`, `hardware`) puis `--status` (file, blocage,
   derniers risques) et `journalctl -u si-agent -f`.
4. Sur le hub : la ligne passe « en ligne » au premier lot reçu ; sections
   **Réseau vu de l'hôte** (sous-réseaux attachés, passerelle et son état
   ARP, routes directes, pairs, voisins), **Matériel**, **Activité**. Si
   « jamais vu » : `--once -v` sur l'hôte montre la requête et la réponse
   (401 = secret ou identifiant, erreur TLS = `--ca-fingerprint` ou `--ca`,
   délai = filtrage réseau vers 6443).
5. Après validation, activer si voulu le plugin `network-neighbors`
   (balayage ping, trafic actif) depuis le catalogue du central ou
   `--enable-plugin network-neighbors` à l'installation.

`agent.json` : `agent_id`, `secret`, `central_url` (obligatoires), `site`,
`host_interval_seconds` 60, `inventory_interval_seconds` 3600,
`netview_interval_seconds` 300 (#428),
`poll_config_seconds` 300, `commands_poll_seconds` 60, `flush_seconds` 30,
`batch_size` 100, `queue_path`, `plugins_dir`, `risk_thresholds`, `plugins`
(surcharges locales), `ca_file`, `insecure` ; #422 : `state_path`,
`block_file`, `require_signed_responses` (true), `plugins_user` (nobody),
`plugin_max_memory_mb` (4096, espace d'adressage), `log_level`, `log_file`.

## Protocole attendu du central (contrat pour `si-agent-api`, #421)

Toutes les requêtes portent les en-têtes signés de netprobe
(`X-Netprobe-Id`, `X-Netprobe-Timestamp`, `X-Netprobe-Signature`,
HMAC-SHA256 de méthode + chemin + horodatage + empreinte du corps, sans fenêtre de temps stricte : rejeu neutralisé par la déduplication des mesures) — `si_agent/protocol.py`
est une **copie** de `netprobe/agent/netprobe_agent/protocol.py`, vérifiée
identique par `sync-shared.sh --check` et par un test.

| Méthode | Chemin (`/api/v1`) | Rôle |
|---|---|---|
| GET | `/agents/<id>/config` | `{version, host_interval_seconds, risk_thresholds, plugins: [{manifest, body}], remove_plugins: [id]}` — appliqué si `version` change |
| GET | `/agents/<id>/commands` | `{commands: [{id, type, params}]}` ; types `collect_now`, `run_plugin`, `enable_plugin`, `disable_plugin`, `remove_plugin`, `flush` |
| POST | `/agents/<id>/commands/<cid>/ack` | `{ok, result?, error?}` |
| POST | `/agents/<id>/measurements` | `{measurements: [{agent_id, task, at, ok, data, error}]}` → 200/201 `{accepted}` ; 400 = lot rejeté (journalisé, abandonné) ; autre = conservé en file, nouvel essai |

Tâches : `host` (avec `activity` depuis #428), `risks` (`{risks: [...], summary}`),
`netview` (#428), `inventory` (avec `hardware` depuis #428), `plugin:<id>`
(`data._plugin` = id, version, durée).

## Central `si-agent-api` (livraison #421)

Flask + SQLite (`SI_AGENT_DATA_DIR`, défaut `./si-agent/data`), port
`SI_AGENT_API_PORT` 6129, routé par tls-proxy sur `/api/si-agent/` (le
préfixe est retiré ; les agents signent `/api/v1/...`). Même motif que
netprobe pour les sondes Pi : un secret par agent, généré à l'enrôlement,
stocké en clair (la vérification HMAC l'exige), renvoyé seulement par
`POST /agents`, `POST /agents/<id>/rotate-secret` et `GET /agents/<id>/install`
(commande d'installation prête à coller, avec `SI_AGENT_PUBLIC_URL`).

Face tableau de bord (non signée, LAN + passerelle comme les autres API) :

| Route | Rôle |
|---|---|
| `GET /status` | compteurs (agents, contact, risques, catalogue) |
| `GET /fleet[?site=]` | flotte + résumé de la dernière mesure `host` (CPU, mémoire, disque max, uptime, partiel), dernier `risks`, état `online/offline/never`, commandes en attente, sondes affectées |
| `GET /risks[?site=]` | tous les constats courants, à plat, triés par sévérité |
| `GET/POST /agents`, `GET/PUT/DELETE /agents/<id>` | enrôlement (`agent_id`, `site`, `label`, `host_interval_seconds`, `risk_thresholds`, `notes`), réglages poussés, désactivation (= refus des requêtes signées), suppression (`?purge=true` efface les mesures) |
| `GET /agents/<id>/latest`, `GET /agents/<id>/measurements?task&limit&since` | dernière mesure par tâche, historique |
| `GET /agents/<id>/config-preview` | ce que l'agent recevra (sans corps ni signatures) et la version attendue ; `GET /agents/<id>` dit si elle est appliquée (`config_applied`) |
| `GET/POST /plugins`, `GET /plugins/<id>[?body=true]`, `DELETE /plugins/<id>` | catalogue de sondes (manifeste validé par la **même** fonction que l'agent, copie de `plugins.py`) ; retirer du catalogue = `remove_plugins` pour les agents affectés |
| `GET /agents/<id>/plugins`, `PUT/DELETE /agents/<id>/plugins/<pid>` | affectation (`{enabled}`) |
| `GET/POST /agents/<id>/commands`, `GET /commands/<cid>` | commandes (`collect_now`, `flush`, `run_plugin`, `enable_plugin`, `disable_plugin`, `remove_plugin` + `params.id`) et leur acquittement (`done`/`failed`, résultat) |

Face agents (signée) : les quatre routes du contrat ci-dessus. Version de
configuration = empreinte des réglages + plugins affectés (id, version,
activation, sha256) + plugins centraux à retirer : l'agent ne réapplique
que si elle change. Mesures dédupliquées sur (agent, tâche, instant) ; une
mesure portant un autre `agent_id` que le signataire est rejetée. Purge
des mesures au-delà de `SI_AGENT_RETENTION_DAYS` (la dernière de chaque
tâche est toujours gardée) ; `offline` après `SI_AGENT_OFFLINE_SECONDS`
(au moins 3 intervalles de collecte) sans contact.

## Tuile hub « Agents hôtes » (livraison #421)

Trois onglets. **Flotte** : tableau trié (critiques, hors ligne,
avertissements, ok, jamais vus) avec jauges CPU / mémoire / disque max,
contact, risques, sondes affectées ; enrôlement (secret + commande
d'installation affichés une fois, retrouvables par « Installation »,
rotation du secret) ; détail par agent en sections repliables : risques,
système (OS, noyau, machine, uptime, charges, mémoire, comptes, outils),
disques, ports (exposés d'abord), services en échec, journal, sondes
(catalogue affectées ↔ présentes sur l'hôte d'après l'inventaire,
activation côté central, retrait, exécution), commandes (envoi, états,
résultats acquittés), réglages poussés (intervalle, seuils JSON).
**Risques** : constats de toute la flotte, clic → l'agent. **Catalogue de
sondes** : création / modification (identifiant, version, runner, entrée,
intervalle, délai, arguments, script dans un éditeur), validation miroir
de `validate_manifest` avant envoi, retrait.

Logique pure dans `hub/src/siAgent.js` (`hub/tests/siAgent.test.mjs`),
client `siAgentClient.js`, vue `SiAgentView.jsx`.

## Découverte passive et revue de l'hôte dans la tuile (livraison #428)

Détail d'un agent, trois sections nouvelles : **Réseau vu de l'hôte**
(sous-réseaux attachés, passerelle par défaut et son état ARP -- « aucune »
signale un sous-réseau isolé --, routes directes vers d'autres sous-réseaux
avec l'état ARP de leur passerelle, DNS, interfaces, pairs des connexions
établies avec ports/processus/portée locale ou routée, voisins ARP/NDP
avec alerte sur ceux hors des sous-réseaux attachés), **Matériel**
(machine, carte/BIOS, CPU, mémoire installée, disques physiques, cartes
réseau, virtualisation, sources absentes) et **Activité** (processus par
CPU et par mémoire, sessions, dernières connexions, services actifs, mises
à jour). Les mesures viennent telles quelles de l'agent (`latest.netview`,
`latest.inventory.data.hardware`, `latest.host.data.activity`).

`GET /netview` (#432) : dernière vue réseau passive de chaque agent
(résumé, voisins, interfaces, DNS) -- reprise par Supervision SI
(propositions « vu par un agent », liens agent ↔ pair).

## Sécurisation du déploiement et du contrôle des sondes (livraison #422)

Demandé : « sécuriser le déploiement et le contrôle des sondes, ssl, logs
verbeux, notifications et présenter une synthèse des événements sur le
hub, ajouter une commande de blocage général et une autre individuelle ».
Logique partagée dans `si_agent/control.py` (copié dans le central).

**Réponses signées.** Le protocole netprobe authentifie l'agent, pas le
central : configuration et commandes n'étaient protégées que par TLS. Le
central signe désormais chaque réponse de la face agents (en-têtes
`X-Netprobe-Response-Timestamp` / `-Signature`, HMAC du secret de l'agent
sur l'horodatage + SHA-256 du corps) ; l'agent refuse (événement
`central-response-rejected`, critique) toute réponse non signée ou
altérée — un central usurpé ne fait rien exécuter, même derrière
`insecure`. Rejeu neutralisé : `issued_at` monotone pour la
configuration, identifiants de commandes mémorisés (`state.json`).
`require_signed_responses: false` seulement pour un central ancien.

**Sondes confinées.** Environnement minimal (jamais celui du service),
session propre (le délai tue tout le groupe de processus), priorité
abaissée, limites CPU / mémoire (`max_memory_mb`, 4096 Mo d'espace d'adressage par défaut depuis #577 : 512 faisait planter les binaires Go) /
fichiers, umask 077, et abandon des privilèges vers `plugins_user`
(`nobody`) quand l'agent est root — sauf sonde `privileged: true`, drapeau
**couvert par la signature** du central et journalisé ; les sondes livrées
`docker-containers` est privilégiée (socket Docker), `network-neighbors`
non. Les sondes installées avant #422 sont normalisées (0755) au démarrage.

**Blocage général et individuel.** Trois sources, la plus restrictive
gagne : configuration du central (`blocked`, manifeste `blocked`),
commandes immédiates (`block_all` / `unblock_all` / `block_plugin` /
`unblock_plugin`), et sur place le fichier `/etc/si-agent/BLOCKED` ou
`--block` / `--unblock`. Bloqué = plus aucune sonde exécutée ni installée,
la surveillance de l'hôte et les remontées continuent (on voit toujours
l'agent, qui déclare son état dans l'inventaire). Côté central : `POST
/block` (toute la flotte, réglage global + commande à chaque agent),
`/unblock`, `POST /agents/<id>/block|unblock`, `PUT
/agents/<id>/plugins/<pid> {blocked, reason}` ; la tuile a le bouton rouge
« Blocage général », un bandeau tant qu'il est actif, « Bloquer » par
agent, une case « bloquée » par sonde.

**TLS.** `GET /ca` sert le certificat de l'autorité interne
(`pki/ca/ca.crt` monté en lecture seule) ; la commande d'installation
porte `--ca-fingerprint <sha256>` : `install.sh` récupère la CA du central
(sans vérification à ce seul moment) et ne l'installe que si l'empreinte
correspond — amorçage sûr sans copier de fichier. `--insecure` reste un
mode de dépannage : signalé au central (événement `tls-insecure`) et dans
la tuile. HTTP clair : avertissement, réservé au test.

**Traces verbeuses.** Agent : `log_level` / `--verbose` (requêtes avec
statut et durée, lancement et résultat de chaque sonde, commandes,
drapeaux), `log_file` en rotation en plus de journald. Central :
`SI_AGENT_LOG_LEVEL` (DEBUG = chaque requête d'agent), refus toujours
journalisés (WARNING + événement `auth-refused`, une fois par 10 min par
motif), journal partagé `/logs`. Jamais un secret dans une trace.

**Journal d'événements.** Table `events` : événements REMONTÉS par les
agents (mesure `event` : démarrage, configuration appliquée / rejouée,
sonde installée / refusée / retirée / en échec / bloquée, blocage,
commande rejouée ou inconnue, TLS non vérifié, réponse du central
rejetée…) et événements DU central (enrôlement, suppression, rotation de
secret, catalogue, affectations, blocages, commandes en échec, refus
d'authentification, agent hors ligne / de retour — chien de garde toutes
les 30 s). `GET /events?agent&severity&min_severity&kind&since&limit`,
`GET /events/summary?hours=24`. Onglet « Événements » de la tuile
(filtres sévérité / agent / sécurité / texte, clic → l'agent) et
**bandeau de synthèse sur l'accueil du hub** (blocage général, critiques,
avertissements, agents hors ligne / bloqués sur 24 h, derniers
événements notables ; clic → la tuile).

**Notifications.** `notify.py` : un événement ≥ `SI_AGENT_NOTIFY_MIN_SEVERITY`
part vers les canaux configurés — SMS et courriel par la copie de
`shared/secrets_alert.py` (canaux du PRA #206, variables `SECRETS_ALERT_*`),
webhook `SI_AGENT_NOTIFY_WEBHOOK_URL` (POST JSON `{text, event}`) — en
thread, best-effort, anti-tempête `SI_AGENT_NOTIFY_COOLDOWN_SECONDS` par
(genre, agent) ; résultat mémorisé sur l'événement (colonne « Notifié »),
`POST /notifications/test` et bouton « tester » dans la tuile.

## Vers GLPI (livraison #437)

La tuile GLPI Inventory exporte les hôtes de la flotte vers GLPI
(`Computer` : nom, série, fabricant/modèle/lieu, commentaire matériel)
et compare la flotte aux agents GLPI Agent -- voir `glpi/README.md`,
section « Agents hôtes (si-agent) ↔ GLPI ». glpi-api lit `/fleet` et
`/agents/<id>/latest` (`SI_AGENT_API_URL`).

Correctif du même jour, trouvé au premier hôte réel : le montage de la CA
dans `docker-compose.yml` ignorait `PKI_DIR` (`.env`) -- Docker créait un
**dossier** `./pki/ca/ca.crt` et la tuile affichait « CA interne non
montée ». Le montage est maintenant `${PKI_DIR:-./pki}/ca/ca.crt`. Si le
dossier parasite existe : `docker compose stop si-agent-api && sudo rmdir
pki/ca/ca.crt && docker compose up -d --force-recreate si-agent-api`.

## Montages en lecture seule et supports amovibles (livraison #442)

Retour du poste réel : « le montage readonly vu comme un disque plein met
du rouge critique, pas bon si ça cache d'autres soucis réels ». Un ISO
GParted monté sous `/media/…` à 100 % ouvrait `disk-full` critique.
`collect_disks` porte maintenant `readonly` (option `ro` du montage) et
`removable` (`/media/`, `/run/media/`, `/mnt/usb`, `/cdrom`, `/run/live/`,
ou iso9660 / udf / squashfs ; sous Windows : lecteur amovible) ; `risks` :
un montage en lecture seule n'est jamais un risque de remplissage, un
support amovible plein donne au plus une information (`removable-full`).
Toujours listés dans la tuile, avec les puces « lecture seule » et
« amovible ». Agent 0.4.1.

## Agent Windows 10 / 11 (livraison #440, backlog 63)

Demande : « pour le second test il me faut un agent Windows 10/11 ». Même
paquet `si_agent` (Python 3 stdlib seule), même protocole HMAC, même file
locale, mêmes mesures : sous Windows (`sys.platform == "win32"`),
`agent.py` prend ses collecteurs dans `si_agent/winhost.py`, qui lance UN
script PowerShell 5.1 par mesure (`si_agent/win/host.ps1`, `activity.ps1`,
`hardware.ps1`, `netview.ps1` -- chacun imprime un objet JSON, chaque
section protégée, sources absentes en `partial`) et traduit le résultat
dans la forme que le central, `risks.py` et la tuile connaissent (fonctions
`map_*` pures). Chemins Windows par défaut (`%ProgramData%\si-agent`),
`os.geteuid` absent géré, pas de `killpg`, sondes `python` (Python de
l'agent) et **`powershell`** (nouveau runner), sonde `shell` refusée
proprement ; `control.plugin_env(base_env=…)` ne garde que les variables
système. Risques ajoutés : Defender (inactif, temps réel, signatures),
pare-feu par profil, mises à jour en attente ; message « service Windows
automatique arrêté ». Installation : `windows/install.ps1` (Python trouvé
ou distribution *embeddable* téléchargée, CA vérifiée par empreinte,
`agent.json` protégé par ACL, tâche planifiée SYSTEM au démarrage,
relancée) et `uninstall.ps1` ; commande affichée dans la tuile
(`install_command_windows`). Tuile : ligne « Windows » (Defender, pare-feu,
correctif, BitLocker, version d'affichage), logiciels installés dans
Matériel, libellés des nouveaux risques. Agent **0.4.0**. Détail et
commandes : `agent/README-DEPLOIEMENT.md`, variante 3.

Vérifié : 8 tests `test_winhost` (traductions sur des sorties
représentatives, risques, `quser` localisé, sonde powershell, environnement
réduit) dont l'**exécution réelle des 4 scripts sous PowerShell 7 Linux**
(syntaxe, enchaînement, JSON ; sources Windows absentes → partial) ;
`install.ps1` / `uninstall.ps1` analysés par le parseur PowerShell ; agent
Windows simulé dans le central réel → rendu Chromium de la tuile.
**Non vérifié : un Windows réel** (Windows PowerShell 5.1, noms de
propriétés CIM, droits du compte SYSTEM, durée des scripts, téléchargement
de la distribution embarquée, tâche planifiée) -- premier poste de test à
venir.

Premier retour du poste de test (#446) : « le PowerShell ouvre en lecture
quand je passe par le shell, et par l'Explorateur en double-clic il me
pose toutes les questions ». Ce sont deux comportements de Windows, pas de
l'agent : l'association de fichier des `.ps1` est le **Bloc-notes**
(double-clic, ou nom du script tapé dans `cmd`), et « Exécuter avec
PowerShell » lance le script **sans paramètres** (les trois obligatoires
sont alors demandés, puis l'absence de droits fait échouer) ; s'y ajoute
la politique d'exécution *Restricted* par défaut d'un poste. Réponse :
la commande affichée par la tuile devient `powershell -NoProfile
-ExecutionPolicy Bypass -File .\windows\install.ps1 …` (guillemets
doubles, compris par PowerShell et `cmd` ; la politique n'est contournée
que pour cette commande), et l'archive gagne **`windows\install.cmd`** /
`uninstall.cmd` : lanceurs qui demandent l'élévation UAC puis appellent le
script avec la même politique -- mêmes arguments depuis `cmd` ou
PowerShell, ou en double-clic sans argument (identifiant, secret, URL,
site, empreinte demandés dans une fenêtre administrateur qui reste
ouverte). Agent **0.4.2**. Vérifié : commande et guillemets (test API) ;
non vérifié : les `.cmd` sur un Windows réel (pas de `cmd.exe` ici).

Suite immédiate (#447), « un install.cmd complet qui reste muet avec
juste un OK à la fin, pour déployer sans autre intervention qu'un
double-clic » : `GET /agents/<id>/install.cmd` renvoie un `.cmd` généré
par le central, propre à l'agent -- identifiant, secret, URL du central et
empreinte de la CA inclus, élévation UAC automatique, `install.ps1` lancé
en `-NonInteractive` avec sa sortie dans `%TEMP%\si-agent-install.log`,
« OK - agent … installe et demarre » puis fermeture après 10 s et
**effacement du fichier** (il porte le secret) ; en erreur, journal
affiché, fenêtre conservée. ASCII seul (page de code OEM de `cmd.exe`),
caractères `" % ! ^ & < > |` refusés dans les valeurs, 409 sans CA interne
(pas de `-Insecure` silencieux). La réponse `/install` porte
`install_cmd_available` et la tuile affiche le lien de téléchargement.
Vérifié : test API (409 / 404 / contenu, CRLF, ASCII), rendu de la tuile ;
non vérifié : exécution sur un Windows réel.

Premier essai réel du `.cmd` (#449) : « ça se lance bien mais ça bloque
sur si_agent\agent.py introuvable ». `install.ps1` ne regardait qu'à côté
de `windows\` (`Split-Path -Parent $PSScriptRoot`). Il cherche désormais
la racine de l'archive (`si_agent\agent.py`) dans le dossier parent du
script, le dossier du script, le dossier courant, et deux niveaux de
sous-dossiers en dessous -- archive décompressée dans un dossier du même
nom, `.cmd` déposé un cran trop haut --, `SI_AGENT_SRC` pour forcer un
chemin ; l'erreur liste ce qui a été vu dans chaque dossier (visible dans
le journal du `.cmd`), et les deux `.cmd` se placent d'abord dans leur
propre dossier (`cd /d "%~dp0"`). Agent **0.4.3**. Vérifié : `Find-Src`
exécutée sous PowerShell 7 depuis cinq emplacements (racine, `windows\`,
un cran trop haut, dossier imbriqué, dossier vide → erreur explicite) ;
non vérifié : le poste Windows réel (retour attendu).

Retours suivants du même poste (#450) : (1) `agent.py` seul disparaissait à
l'extraction -- **Bitdefender** (édition entreprise, quarantaine
silencieuse, sans exception locale possible) ; à retenir pour le parc :
exclusion de stratégie sur `C:\Program Files\si-agent` et
`C:\ProgramData\si-agent` dans GravityZone, ou nom de la détection pour
adapter le code. (2) Passé ce cap, la récupération de la CA échouait sous
Windows PowerShell 5.1 : « la connexion sous-jacente a été fermée : une
erreur inattendue s'est produite lors de l'envoi » -- un ScriptBlock donné
en `ServerCertificateValidationCallback` est appelé par .NET sur un autre
thread et casse l'envoi. `install.ps1` passe désormais un vrai délégué C#
(`Add-Type`), force TLS 1.2 et lit `/ca` avec `WebClient` ; PowerShell 7
garde `-SkipCertificateCheck`. Vérifié : délégué + `WebClient` contre un
serveur HTTPS auto-signé (CA lue, échec sans le délégué). Agent **0.4.4**.

## Agent macOS (livraison #451, backlog 63)

Demande : « un agent Mac de supervision ». Même paquet `si_agent`, même
protocole HMAC, mêmes mesures (`host`, `activity`, `hardware`, `netview`,
`inventory`) que Linux et Windows -- seule la source change. Contrairement
à Windows (#440, scripts PowerShell), macOS a un vrai shell et le paquet
tourne déjà en Python : `si_agent/machost.py` lance directement les
commandes natives et traduit leur sortie dans les formes connues du central
et de la tuile.

- **`machost.py`** (pur + collecteurs, 17 tests) : `host` -- système
  (`sw_vers`, `sysctl hw.model/ncpu/kern.boottime`, `uname`), CPU (`top -l 1`
  + `vm.loadavg`), mémoire (`hw.memsize` + `vm_stat` + `vm.swapusage`),
  disques (`df -k` recoupé avec `mount` pour type et lecture seule ;
  **les volumes APFS scellé `/` et `/System/Volumes/Data` sont fusionnés en
  une seule entrée `/`** portant l'usage réel, pour ne pas compter deux fois
  ni afficher le système scellé comme un disque « plein » -- même esprit que
  #442), services (`launchctl list` : échecs = code de sortie non nul),
  ports en écoute (`lsof -nP -iTCP -sTCP:LISTEN`), journal (`log show`
  messages d'erreur, 15 min), comptes (`dscl` groupe admin + utilisateurs
  uid ≥ 500, `stat /dev/console`) ; `activity` (`ps`, `who`, `last`,
  `softwareupdate -l`) ; `hardware` (`system_profiler SPHardwareDataType`
  + `networksetup`) ; `netview` (`ifconfig`, `netstat -rn`, `arp -an`,
  `netstat -an -p tcp`, `scutil --dns`). `risks.py` : message dédié
  « service launchd en échec » (l'exposition de port, le disque plein hors
  lecture seule/amovible et les seuils CPU/mémoire sont génériques).
- **Installation** : `install-macos.sh` (même contrat que `install.sh` :
  `--ca-fingerprint` amorçage GET /ca vérifié SHA-256, `--ca`, `--insecure`)
  installe le paquet dans `/usr/local/opt/si-agent`, la configuration dans
  `/usr/local/etc/si-agent/agent.json` (mode 600), et un **LaunchDaemon**
  `fr.exemple.si-agent` (compte root, au démarrage, relancé) ;
  `uninstall-macos.sh` (`--keep-data`). Commande affichée dans la tuile
  (`install_command_macos`). Agent **0.5.0**.

Vérifié : 17 tests `test_machost.py` (tous les parseurs sur sorties
représentatives + `collect_all` de bout en bout) ; chaîne réelle : mesures
`host`/`risks`/`netview`/`inventory` produites depuis des sorties macOS
réalistes, ingérées dans le central réel, **rendu Chromium de la tuile**
(macOS 14.6.1, mémoire 92,7 % → risque « mémoire saturée », service launchd
en échec, disque APFS `/` 35 % + partage SMB distant 78 % non signalé
« plein », matériel Apple M2, réseau) ; non-régression Windows/Linux vérifiée.
**Non vérifié : un Mac réel** (noms de propriétés `system_profiler`, format
exact de `df`/`ifconfig` selon la version, LaunchDaemon) -- premier poste de
test à venir.

## Montages illisibles ou invisibles (livraison #438)

Premier retour du premier hôte réel : « l'agent ne voit pas tous les types
de montage, notamment sshfs ». Causes trouvées : `collect_disks` IGNORAIT
tout montage dont `statvfs` échoue (FUSE refuse root sans `allow_other`,
NFS périmé), et le conteneur ne voit pas un montage fait sur l'hôte après
son démarrage (pas de propagation). Maintenant : chaque montage est listé
avec `remote` (sshfs, NFS, CIFS, rclone…), `visible` et `error` (tailles à
null), `partial` contient `mounts:<n>` ; en conteneur la table de montage
de l'hôte (`/proc/1/mounts`, --pid host) révèle les montages invisibles ;
`deploy-docker.sh` monte `/` en `ro,rslave` (agent 0.3.2). La tuile
affiche « illisible — raison » ou « invisible du conteneur » à la place
de la jauge, et une puce « distant ».

**#439, sans changer la configuration de l'hôte** (retour : « un simple
`mount` le liste sans avoir de droit ») : vérifié avec un vrai sshfs, FUSE
ne renvoie pas « accès refusé » à root mais des **tailles nulles**, d'où
le montage escamoté. L'agent root mesure maintenant un FUSE en se
présentant comme l'utilisateur du montage (`user_id=` dans
`/proc/mounts`, fork + setuid + statvfs : `host.statvfs_isolated`), et
tout système distant avec un délai de 5 s (sshfs figé → « sans réponse »,
la collecte continue). `measured_as` sur l'entrée, « (uid N) » dans la
tuile. Agent 0.3.3. Marche à suivre : `README-DEPLOIEMENT.md`, section
« Montages réseau et FUSE ».

## Stockage de l'hôte Linux : volumes, partitions, systèmes de fichiers (livraison #503)

Demandé : « compléter l'agent linux sur la gestion de Z{volume/partition/fs} ».
La mesure `host` embarque désormais une section `storage`
(`si_agent/storage.py`), quatre couches facultatives (outil absent =
couche absente, jamais une erreur ; `available` dit lesquelles ont
répondu) :

| Couche | Source | Contenu |
|---|---|---|
| blocs | `lsblk -J -b` | disques, partitions, LVM, md, zvols : type, taille, FS, montage, parent, modèle, HDD/SSD, amovible |
| LVM | `pvs` / `vgs` / `lvs --reportformat json` | PV, VG (taille, libre), LV (genre linear/thin/thin-pool/raid…, pool, origine, **occupation données/métadonnées des thin pools**) |
| RAID logiciel | `/proc/mdstat` | niveau, membres, actifs/total, **dégradé**, reconstruction en cours |
| ZFS | `zpool list/status`, `zfs list` | pools (santé, alloué/libre, **capacité**, fragmentation, erreurs par disque, **dernier scrub**), datasets et zvols (utilisé, disponible, quota/volsize, compression), **snapshots agrégés par dataset** (nombre, espace, plus ancien, plus récent — jamais la liste brute) |

Risques dérivés (`risks.evaluate_storage`) : pool ZFS `FAULTED/UNAVAIL`
ou `DEGRADED` → critique ; capacité ZFS ≥ 80 % avertissement, ≥ 90 %
critique (seuils plus bas que les FS : copy-on-write) ; erreurs
d'E/S/checksum → avertissement ; scrub > 35 jours ou jamais → info ;
dataset ≥ 90 % de son quota → avertissement ; thin pool LVM ≥ 85/95 %
→ avertissement/critique ; md dégradé → critique, resync → info. Seuils
surchargeables par `risk_thresholds` comme les autres. Tuile Agents
hôtes : section **Stockage** (pools, datasets/zvols, LVM, RAID, arbre
des blocs). Tests : `tests/test_storage.py` (parseurs sur sorties
représentatives, collecte contre faux runner, risques).

## Proxmox : disponibilité, sauvegardes, accès, journaux internes (livraison #504)

Plugin `proxmox` **v3** (voir aussi #487, #488) — « superviser l'état /
disponibilité des VM, un suivi des backup/snapshot, le log des accès VM
(ssh, http/https) et la récupération des logs internes » :

- **Disponibilité** : le central garde chaque passage du plugin
  (30 min) ; `GET /proxmox/history?agent_id=&hours=168` donne par VM le
  taux de relevés « en marche », les transitions d'état ; à chaque
  mesure reçue, un **événement** est journalisé quand une VM change
  d'état (arrêt d'une VM en marche = avertissement, reprise = info,
  VM apparue/disparue = info) — visibles dans le journal de la tuile
  Agents hôtes et notifiés comme les autres.
- **Sauvegardes** : en plus du dernier fichier par VM (#487), les
  **tâches vzdump** (`/nodes/<n>/tasks?typefilter=vzdump`, 200
  dernières : résultat OK / erreur / en cours, durée, utilisateur, par
  VM ou job global) et les **jobs planifiés** (`/cluster/backup` :
  planning, stockage, VM couvertes, actif). Par VM : 5 dernières
  exécutions, dernier résultat, jobs qui la couvrent ; par hyperviseur :
  OK / échecs sur 24 h. Snapshots inchangés (liste avec âge).
- **Accès** (fenêtre 24 h) : journal `pveproxy` (`/var/log/pveproxy/
  access.log`, fin bornée à 2 Mo) → par VM : **sessions console**
  (vncproxy/termproxy/spice), modifications (POST/PUT/DELETE),
  consultations, utilisateurs, adresses, dernier accès ; pour
  l'hyperviseur : requêtes, utilisateurs, adresses, **401**. SSH de
  l'hyperviseur (`journalctl -u ssh`) : acceptés par utilisateur@IP,
  refus par IP, dernier accepté. Échecs d'authentification
  `pvedaemon`/`pveproxy` (journal).
- **Journaux internes des VM** : pour chaque VM en marche avec
  qemu-guest-agent (`agent/exec` + `exec-status`, borné à 10 s) ou
  chaque conteneur (`pct exec`), lecture du journal **sshd**
  (`journalctl _COMM=sshd`, repli `auth.log`/`secure`) et des journaux
  **web** (nginx/apache, format combiné) — 300 lignes, résumés
  (acceptés/refusés/utilisateurs inconnus, requêtes par classe de
  statut, clients, chemins) + **extrait brut** (16 Ko max par journal)
  consultable dans la tuile. **Tourniquet de 15 VM par passage** pour
  borner la durée ; rien n'est jamais écrit dans l'invité ; une VM
  sans agent ou dont l'agent interdit `exec` est signalée, pas
  bloquante. Aucun mot de passe : tout passe par `pvesh`/`pct` en
  root local.
- Tuile **Proxmox** : colonnes Dispo. 7 j, Sauvegarde (dernier fichier
  + résultat de la dernière tâche, série d'échecs), Accès 24 h ; fiche
  dépliée avec transitions d'état, exécutions de sauvegarde, accès
  (utilisateurs, adresses, dernière console), journaux internes (SSH,
  web, extraits). En tête d'hyperviseur : sauvegardes 24 h, accès et
  SSH de l'hôte.

Manifeste : `timeout_seconds` 600 (journaux invités). Tests :
`test_proxmox_plugin.py` (UPID, tâches, jobs, journal pveproxy avec
fenêtre, sshd, web, tourniquet, disponibilité, exec borné, collecte
complète contre faux `pvesh`/`pct`/`journalctl`), `test_si_agent_api.py`
(disponibilité et événements sur mesures successives), Node
(`proxmoxLib.test.mjs`).

## Tests

```bash
cd si-agent/agent && python3 -m unittest            # 40 tests (agent), dont netview/review (#428), montages (#438-#439), Windows (#440, pwsh si présent)
./sync-shared.sh --check                              # copies protocol/localqueue à jour
cd ../api && python3 -m unittest                      # 9 tests (central), dont la chaîne réelle agent ↔ central
cd ../../hub && node --test tests/siAgent.test.mjs    # 10 tests (logique de la tuile)
```

Collecteurs sur des contenus `/proc`, `ss`, `journalctl`, `passwd` réels
capturés ; risques ; moteur de plugins (signature, exécution **réelle** de
scripts bash et Python, plugins livrés) ; boucle de l'agent contre un faux
central (configuration versionnée, plugin signé poussé, plugin non signé
refusé, commandes acquittées, panne réseau → file puis rattrapage) ; refus
401 ; copies partagées identiques.

## Vérifié / non vérifié

**Vérifié** : les 16 tests ; collecte réelle `--collect` sur un conteneur
Ubuntu 24.04 (`partial: ["ss"]` correctement signalé, disque à 88 % →
`disk-high`) ; `--once` avec le plugin `network-neighbors` réel (JSON
valide, mesures en file, central injoignable journalisé) ; `--status`
depuis un autre processus (derniers risques relus dans la file).

**Vérifié (#421)** : tests du central, dont le VRAI agent contre le VRAI
central (client Flask signé) : configuration poussée et appliquée, plugin
du catalogue signé, installé et exécuté avec arguments, mesures reçues,
commande acquittée, retrait du catalogue → désinstallation, corps altéré
en base → refusé par l'agent ; puis la même chaîne **par HTTP réel**
(central Flask sur 6302, agent en `--once` depuis le conteneur) ; rendus
Chromium de la tuile (flotte, détail, catalogue, enrôlement, thème
sombre) sur ces données réelles ; builds Vite hub ; `docker-compose.yml`
valide, sources `COPY` du Dockerfile présentes (contrôle #409), route
tls-proxy rendue.

**Vérifié (#422)** : 22 tests agent (réponse non signée / altérée /
mauvais secret refusée, rejeu de configuration et de commande, blocage
général et individuel par commande / configuration / fichier local avec
persistance après redémarrage, drapeau `privileged` non signé refusé,
exécution RÉELLE confinée : `nobody`, environnement minimal, délai qui tue
le groupe) ; 9 tests central (réponses signées, blocage de flotte puis
individuel en chaîne réelle avec deux agents, chien de garde hors ligne /
en ligne avec webhook RÉEL reçu, seuil et anti-tempête, `/ca` avec une
vraie CA et empreinte dans la commande d'installation) ; chaîne par HTTP
réel (agent `--once` en DEBUG, sonde exécutée en `nobody`, blocage
général → commande + configuration, déblocage, blocage d'une sonde,
notifications webhook reçues) ; migration du schéma sur la base existante
de #421 ; rendus Chromium (bandeau de blocage, journal, synthèse sur
l'accueil en thème sombre).

**Non vérifié** : `install.sh` (`--ca-fingerprint` testé seulement par son
extrait Python contre le vrai `/ca`) et le service systemd sur une vraie
machine ; Raspberry Pi ; build Docker ; passerelle TLS réelle ; canaux SMS
et courriel réels (fonctions du PRA réutilisées telles quelles).

## Antivirus Windows / macOS (livraison #520)

Demande SAV : « un contrôle / alerte sur les antivirus des Windows et des
Mac ». Section `antivirus` de la mesure `host`, même forme sur les deux
plateformes (`si_agent/antivirus.py`, logique pure testée) :
`{products: [{name, enabled, up_to_date, source}], primary, status, platform}`
avec `status` = ok · disabled · outdated · none · unknown.

- **Windows** : `host.ps1` interroge le Centre de sécurité
  (`root/SecurityCenter2`, `AntiVirusProduct`) -- tout antivirus installé y
  est enregistré (Defender, Bitdefender GravityZone, ESET…) avec un
  `productState` codé (actif / à jour), décodé côté agent ; Defender reste
  lu par `Get-MpComputerStatus` (#440). Si le Centre de sécurité est
  illisible (serveurs), Defender seul fait foi ; rien de lisible = section
  absente, jamais « aucun antivirus » à tort.
- **macOS** : pas de registre commun -- produits reconnus par leurs
  fichiers et leurs démons (`ps -axo comm`) : Bitdefender, Microsoft
  Defender, Sophos, ESET, Kaspersky, Avast, Malwarebytes, SentinelOne,
  CrowdStrike, ClamAV ; protections système : XProtect (version, âge du
  bundle), Gatekeeper (`spctl --status`), SIP (`csrutil status`).
- **Risques** : `antivirus-none` (warning), `antivirus-off` (critical),
  `antivirus-outdated` (warning), `antivirus-state-unknown` (info),
  `gatekeeper-off`, `sip-off` (warning), `xprotect-old` (info, > 60 j).
  Defender seul garde ses risques détaillés de #440 (pas de doublon).
- **Tuile** : ligne « Antivirus » dans la section Système de chaque agent.

Agent **0.5.1**.

## Auto-mise à jour contrôlée depuis le central (livraison #522)

Demandé : « que les agents soient en mesure de s'auto mettre à jour, que
dans le front on voie l'état des mises à jour, avec un contrôle sur le
déploiement : un premier qui bêta-teste, puis activation volontaire de
l'administrateur ; auto-installation mais déploiement contrôlé depuis le
central ».

- **Version cible** = l'archive construite dans l'image de si-agent-api
  (#518, `GET /package`) : mettre à jour les agents = reconstruire
  si-agent-api avec les nouvelles sources.
- **Réglages** (`GET/PUT /updates`, réglage `updates`) : `beta_agents`
  (identifiants servis en premier), `general_enabled` (activation par
  l'administrateur pour tous les autres), `auto` (planification dès
  qu'un agent éligible dépose son inventaire ; sinon bouton « Appliquer
  maintenant », `POST /updates/apply`), `retry_after_s` (6 h avant de
  réessayer un échec). Statuts : up-to-date · newer · unknown · pending ·
  started · failed · eligible · not-eligible.
- **Commande `update`** (acquittée, comme les autres) : `{version, sha256,
  url}` ; l'agent télécharge par son TLS habituel (central de secours
  compris), vérifie le SHA-256, extrait (chemins et liens contrôlés),
  lance l'installeur de sa plateforme en `--upgrade` / `-Upgrade`
  (configuration, secret, CA et sondes conservés) **détaché** de son
  processus (`systemd-run` sous Linux, nouvelle session sous macOS,
  processus détaché sous Windows), acquitte « installation lancée »,
  puis au redémarrage signale `agent-updated` ou `agent-update-failed`
  (marqueur `update-pending.json`). La nouvelle version apparaît à
  l'inventaire suivant.
- **Tuile** Agents hôtes → onglet « Mises à jour » : version servie, état
  par agent, cases « bêta », activation générale (confirmation), auto,
  « Appliquer maintenant », mise à jour unitaire.

Non vérifié en réel : le redémarrage détaché sous macOS (LaunchDaemon) et
Windows (tâche planifiée) ; sous Linux `systemd-run` isole l'installeur
du service qu'il redémarre. Agent **0.5.3** ; **0.5.4** (#524) : `install.sh`
détecte un hôte Proxmox VE et redémarre toujours le service. **0.5.5** (#525) :
sonde `wifi-probe` ; **0.5.6** (#526) : sonde v2 ; **0.5.7** (#527) : sonde
`path-probe` ; **0.5.8** (#528) : `--upgrade` macOS/Windows conserve la
configuration (elle était effacée) ; **0.5.9** (#529) : wifi-probe v3.

## Publication locale d'un tableau de santé (livraison #547, agent 0.5.10)

Demandé : le responsable du site veut un tableau de bord de l'état de
santé du réseau ; « l'agent mini-PC (sur le réseau du campus) devrait
porter un service web qui le publie ».

Principe : le **central prépare le contenu** (tableau de santé Nebula de
nebula-api, #546 : phrases, disponibilité, incidents, une ligne par
équipement, sans identifiant interne), l'**agent le relève** toutes les
`interval_seconds` par son canal signé (`GET /api/v1/agents/<id>/publish`,
réponse signée comme la configuration) et le **sert sur le LAN du site**
sur `http://<agent>:<port>/` (page « État du réseau » dans la charte
Simple, sans dépendance) et `/board.json`. Aucune clé Nebula sur le poste,
deux chemins en lecture seule, page marquée « information ancienne » au
delà de cinq minutes sans relevé. Le serveur s'arrête si la publication est
désactivée ou si l'agent est bloqué.

Réglage par agent (remplacé en bloc), depuis le central :

```
curl -sk -X PUT https://localhost:6443/api/si-agent/agents/<agent_id> -H "Content-Type: application/json" \
  -d '{"publish": {"enabled": true, "port": 8081, "title": "Réseau du campus", "site_id": "", "hours": 24, "interval_seconds": 60}}'
```

`site_id` vide = tous les sites Nebula ; `port` 1024–65535 (ouvrir le port
sur le pare-feu local du poste si besoin). `NEBULA_API_URL` sur
si-agent-api (compose). Logique pure `agent/si_agent/publish.py`,
`api/publish.py` ; tests `agent/tests/test_publish.py`,
`api/test_si_agent_api.py`. Depuis le hub (#549), la même page se voit
sans être sur le site : fiche de l'agent → « voir la page telle que
publiée » (`GET /agents/<id>/publish/preview`, même gabarit et même
contenu, calculé par le central). Suites : autres contenus publiables
(état des services de l'espace Simple, demandes en attente), réglage
dans la tuile Agents hôtes.

## Lien vers le hub sur la page publiée (livraison #559, agent 0.5.11)

Réglage `publish.hub_url` (http(s), 200 caractères max) : la page servie
par l'agent affiche « Tableau de bord complet (connexion demandée) → »
vers cette adresse, par exemple `https://<hub>/?view=nebula` (le hub ouvre
directement la tuile ; la personne se connecte avec son compte et ne voit
que ce que la matrice des droits lui accorde). Le lien voyage dans le
contenu signé, comme le reste.

## Page publiée : exports et historique par thématique (livraison #564, agent 0.5.12)

La page servie par l'agent gagne deux boutons — **Exporter CSV**
(équipements et historique, `;` et UTF-8 BOM pour Excel) et **Imprimer /
PDF** (mise en page d'impression, « enregistrer en PDF » du navigateur) — et
une section **Historique par thématique** (Passerelle, Commutateurs, Bornes
Wi-Fi, Autres) listant les changements d'état de la fenêtre. Le central
joint au contenu signé les transitions nebula-api (`/sites/<id>/transitions`)
avec la thématique déduite du modèle (`publish.device_theme`).

## Sonde « postes Windows » (livraison #567, plugin `windows-probe`)

Famille explorer, à activer sur l'agent placé sur le réseau du site
(Agents hôtes → l'agent → Sondes → windows-probe ; `--targets auto` = les
/24 du poste, ou `--targets 192.0.2.0/24,198.51.100.7`). Toutes les 5 min :
ports SMB 445, RDP 3389, AnyDesk 7070, VNC 5900, WinRM 5985/5986, SSH 22,
HTTP(S) ; NetBIOS node status (nom, groupe/domaine, MAC) ; négociation SMB2
(dialecte, signature exigée) et essai SMB1 ; demande de connexion RDP
(NLA / TLS). Aucune authentification, aucune action ; 254 hôtes en ~10 s.
Constats → événements du central (#530) : `smb1_enabled`, `rdp_without_nla`
(warning), `smb_signing_optional`, `vnc_open`, `netbios_silent` (info).
Central : `GET /windows-hosts?site=` (fusion entre agents). Hub : tuile
Nebula → Campus → **Accès Windows** (rapprochement avec les fiches matériel
par MAC ou nom, liens RDP (.rdp), AnyDesk (`anydesk:`), partage (`smb://`,
`\\ip` à copier), VNC, SSH, WinRM). Tests : `test_windows_probe.py`.

## Sonde « annonces réseau » (livraison #568, plugin `broadcast-probe`)

Famille explorer, privilégiée (socket brut `AF_PACKET` ; sans privilège ou
sous Windows : écoute UDP mDNS / SSDP / LLMNR / NetBIOS / WS-Discovery).
Toutes les 5 min, une minute d'écoute **passive** des trames diffusées et
multidiffusées du segment : ARP (dont gratuit), DHCP (offres, serveurs),
NetBIOS (enregistrements de noms), mDNS/Bonjour (noms, services `_ipp`,
`_googlecast`, `_ndi`…), SSDP/UPnP (NOTIFY, SERVER), LLMNR, WS-Discovery,
LLDP/CDP (voisins, ports), STP (racine, changements de topologie), IPv6
(RA, ND, MLD), IGMP, VRRP/HSRP, multicast applicatif (AnyDesk, Dropbox,
Steam, Art-Net, MikroTik, Ubiquiti…). Résultat : protocoles (trames,
émetteurs), annonceurs (MAC, IP, noms, services, rythme), constats →
événements (#530) : `dhcp_multiple` (critique), `arp_conflict`,
`stp_topology_change`, `stp_multiple_roots`, `storm` (warning), `ipv6_ra`,
`broadcast_rate` (info). Ne voit que le VLAN du poste : une sonde par VLAN
à écouter. Central : `GET /broadcasts?site=`. Hub : Nebula → Campus →
**Annonces réseau**. Tests : `test_broadcast_probe.py`.

## Contrôle des VM Proxmox depuis le hub (livraison #572, agent 0.5.13)

Tuile Proxmox → cliquer une VM → barre **Actions** : démarrer, arrêt propre
(ACPI, 120 s), redémarrer, couper, reset, reprendre ; snapshot (créer,
revenir, supprimer). Chaque action = commande `vm_action`
(`{vmid, action, kind: qemu|lxc, snapname?}`) signée, relevée par l'agent de
l'hôte (≈ 1 min), exécutée par `qm` / `pct` (`si_agent/vmctl.py`, tests
`test_vmctl.py` : ligne de commande construite depuis des paramètres
validés, jamais interpolés), résultat renvoyé au central et suivi dans le
hub ; événement `command-vm` à chaque action. L'agent doit tourner en root
sur l'hôte (comme la sonde proxmox) ; agent bloqué = action refusée. Pas
besoin de l'interface web Proxmox ni du port 8006 : tout passe par le
canal agent → central.

## Mise à jour restée sans effet (livraison #576, agent 0.5.14)

Symptôme : commande `update` « done · acquittée », l'agent reste en
ancienne version, rien dans les événements. Deux causes corrigées :
(1) le central testait le statut `acked` alors qu'il note `done` /
`failed` — une mise à jour lancée retombait en « à planifier » et était
renvoyée à chaque passage sans jamais signaler l'échec ; l'état
**« installeur lancé, sans effet »** apparaît désormais après 15 min ;
(2) l'installeur tournait détaché sans journal : sa sortie va maintenant
dans `update-<horodatage>.log` à côté de `state.json` de l'agent
(`/var/lib/si-agent/` ; Windows : dossier de données de l'agent) ; si
l'agent tourne toujours 15 min après le lancement, il émet
`agent-update-failed` avec la fin de ce journal ; un lancement impossible
(binaire, droits) est refusé tout de suite dans le résultat de la commande.
Pour passer les agents encore en 0.5.x sur cette version, une fois à la
main : Linux `sudo /opt/si-agent/... install.sh --upgrade` depuis l'archive
servie (`/api/si-agent/package`), Windows `install.ps1 -Upgrade` en
administrateur ; ensuite le journal dira pourquoi les précédentes
échouaient.

## Mise à jour automatique : cause réelle (livraison #577, agent 0.5.15)

Journaux des postes après passage manuel en 0.5.14 : l'installeur lancé par
`systemd-run` ne trouvait pas le script — le service tourne avec
`PrivateTmp=true`, l'archive était extraite dans le `/tmp` privé de l'agent,
invisible depuis l'unité transitoire. Depuis 0.5.15 l'archive s'extrait dans
`/var/lib/si-agent/update/` (dossier d'état, partagé). Une version courante
plus récente que la cible du marqueur compte comme réussie (plus de faux
`agent-update-failed` après un passage manuel). `plugin_max_memory_mb`
passe à 4096 : la limite est un espace d'adressage (RLIMIT_AS) et 512 Mo
faisait planter les binaires Go (sonde docker-containers : « failed to
reserve page summary memory »).

## Inventaire logiciel et installation / désinstallation (livraison #595, agent 0.5.16)

Sonde `software-inventory` (bundled, **désactivée par défaut**, 6 h) :
liste des logiciels installés — Linux (dpkg / rpm, flatpak, snap), macOS
(`/Applications`, Homebrew), Windows (clés `Uninstall` 64 / 32 bits et
utilisateur, Office click-to-run) — nom, version, éditeur, date, source,
plus les comptes ouvrant des sessions. Lecture seule. Central :
`GET /software-inventory?site=` (dernier relevé par agent) ; consommé par
`licenses-api` (tuile Licences logicielles, voir `licenses/README.md`).
Commande `software_action` `{action: install|uninstall, package, manager?}`
(`si_agent/swctl.py`, tests `test_swctl.py`) : apt-get / dnf / brew /
winget / choco, gestionnaire déduit de l'OS, nom de paquet validé
(`PKG_RE`), jamais de shell, `DEBIAN_FRONTEND=noninteractive`, délai 15
min, sortie tronquée renvoyée au central ; événement `command-software`.
Windows : l'agent tourne en service (session 0) où `winget` peut manquer —
préférer `choco` ou installer winget pour le compte système.

## Filtres d'alertes (livraison #607)

Demandé : « les alertes agents sont inutiles pour une partie des cas ; une
case à cocher sur chaque agent pour activer / désactiver un filtrage ; des
groupes de filtres ; classer / catégoriser les alertes ; paramétrage fin ;
besoin immédiat : filtrer les postes de travail éteints hors des heures de
travail (8 h 30 – 18 h) ». `api/alertfilters.py` (pur, 4 tests) : chaque
`kind` d'événement a une **catégorie** (disponibilité, sécurité, sondes,
mises à jour, commandes, flotte, captures, risques, autres) ; un **groupe**
= règles {catégories et/ou genres, `when` toujours / hors / pendant les
heures ouvrées, jours, début, fin, action filtrer / laisser passer} ; un
agent = `filter_enabled` + `filter_group`. Groupes par défaut : « Postes
de travail (heures ouvrées) » (disponibilité hors lun.–ven. 08:30–18:00,
fuseau `SI_AGENT_ALERT_TZ`) et « Silencieux ». Un événement filtré est
conservé (`muted`, `muted_by`) mais absent du bandeau, de la synthèse
(`muted` compté à part), de la liste par défaut (`?include_muted=1`) et des
notifications. Routes : `GET/PUT /alert-filters`, `POST /alert-filters/test`
(« un hors-ligne à telle heure serait-il filtré ? »), `PUT /agents/<id>`
(`filter_enabled`, `filter_group`). Tuile : onglet **Filtres d'alertes**
(tableau par agent avec case + groupe, éditeur de groupes, test à blanc),
case « Filtrer les alertes » dans les réglages de l'agent, « afficher les
filtrées » dans le journal.

## Poste : redémarrage, réveil, lanceurs, chien de garde (livraison #613, agent 0.5.17)

Demandé : « un agent Windows capable de gérer un reboot Windows et si
possible un wake-on-LAN ; accès à la liste des lanceurs d'application au
démarrage ; watchdog appli ». Section **Poste** de la fiche agent (bouton
« Poste » dans les sections), sur toute plateforme sauf mention.

- **Alimentation** — commande `power_action` {action: reboot|shutdown|cancel,
  delay_seconds, message, force}. Windows `shutdown.exe /r|/s /t N /c
  "message" [/f]`, Linux/macOS `shutdown -r|-h +M`. Refus si une session
  est ouverte sur la console (utilisateur affiché) sauf `force`. Acquittée
  avant l'exécution, événement `command-power` (warning). `si_agent/powerctl.py`.
- **Réveil réseau** — commande `wol` {mac, broadcast?, port?} envoyée à **un
  autre agent en ligne du même site** (le paquet magique ne traverse pas les
  routeurs) ; le MikroTik du site peut aussi le faire (`/tool wol`). MAC
  préremplie depuis la vue réseau de l'agent visé. Le poste doit avoir le
  Wake-on-LAN activé (BIOS + carte) ; le seul retour est l'agent qui revient
  en ligne.
- **Lanceurs au démarrage** (Windows) — mesure `startup` toutes les 30 min
  (`win/startup.ps1`) : clés Run / RunOnce machine et utilisateur (y compris
  WOW6432Node), dossiers Démarrage, tâches planifiées à l'ouverture de session
  ou au démarrage (hors \Microsoft\), services automatiques hors Windows.
  État activé/désactivé lu dans `Explorer\StartupApproved` (même source que le
  Gestionnaire des tâches). Commande `startup_action` {kind, scope, name,
  enable} : Run / dossier → valeur StartupApproved (02 = activé, 03 =
  désactivé, l'entrée n'est jamais supprimée), tâche → `schtasks /Change
  /Enable|/Disable`, service → `sc config start= auto|disabled` (effet au
  prochain démarrage). Refusés : tâches \Microsoft\, services système
  (wuauserv, WinDefend, mpssvc, BFE, Dhcp, Dnscache, EventLog, RpcSs,
  Winmgmt, TermService, si-agent…). `si_agent/startupctl.py`.
- **Chien de garde applicatif** — commande `watchdog_config`
  {interval_seconds, apps: [{id, label, process, command, cwd, hours, days,
  cooldown_seconds, max_restarts_per_hour, enabled}]}, persistée dans
  `state.json` et rappelée dans la mesure `inventory`. Toutes les
  `interval_seconds` (15–3600) l'agent liste les processus (`tasklist` /
  `ps`) ; application absente dans sa plage → relance détachée (jamais
  attendue, jamais rattachée à l'agent), au plus `max_restarts_per_hour` par
  heure et à `cooldown_seconds` d'écart ; quota atteint ou pas de commande →
  événement `app-down` (critical, une fois) ; retour → `app-recovered`.
  Mesure `watchdog` (état par application). Catégorie d'alertes
  « Applications surveillées » (#607) pour les grouper ou les filtrer.
  `si_agent/watchdog.py`.

Vérifié réellement : 13 tests (`test_winctl.py` : lignes de commande,
bornes, refus console, paquet magique, StartupApproved, protections,
cycle relance → repos → quota → retour, fenêtres horaires, analyse de
`tasklist`), non-régression agent (80 tests) et central ; JSX compilé.
**Non vérifié sur un Windows réel** : `startup.ps1` (PowerShell 5.1,
`Get-ScheduledTask`, COM WScript.Shell pour les .lnk) et la valeur binaire
StartupApproved sur Windows 11 — à confirmer sur le poste de test comme en
#446.

## Déploiement en masse et introspection (livraison #616, agent 0.5.18)

Demandé pour la démonstration Numeria : « les sondes Windows pour un maximum
de PC » et « un banc de test lourd pour vérifier l'impact d'une sonde sur la
charge et la stabilité : introspection ».

**Enrôlement par jeton de site** (onglet *Déploiement* de la tuile Agents) :
un jeton `enr-…` par site (libellé, URL du central vue des postes, usages
max, validité, sondes activées à l'enrôlement). La même ligne s'exécute sur
tous les postes — Windows : `powershell -NoProfile -ExecutionPolicy Bypass
-Command "iex (iwr -UseBasicParsing '<central>/deploy/windows?token=…').Content"`
(PowerShell administrateur, GPO de démarrage, Intune, PsExec) ; Linux :
`curl -fsSL '<central>/deploy/linux?token=…' | sudo bash`. Le script
d'amorçage télécharge l'archive (`GET /package`), lance l'installeur avec
`-EnrollToken` : `POST /api/v1/enroll` {token, hostname, platform} crée
l'agent nommé d'après la machine (`slug_agent_id`) et délivre son secret —
jamais dans la ligne ni dans le script. Relancer la ligne sur un poste déjà
enrôlé redonne un secret neuf (déploiement GPO rejoué) ; un poste enrôlé par
un autre jeton est refusé. Jetons révocables, bornés en usages et en durée ;
événements `enroll-token-created` / `-revoked`, `agent-enrolled`.
CA : par un nom public (frontal Let's Encrypt) l'installeur prend le magasin
système (`-SystemCa`) ; par l'adresse LAN du hub il épingle la CA du projet
comme avant (`_pin_internal_ca`). Frontal : `si-agent/deploy/` et
`si-agent/api/v1/enroll` sont exemptés de la vérification de jeton A0
(docs/acces-public-frontal.md). `store.py` : table `enroll_tokens`,
colonnes `agents.enrolled_by` / `hostname` (3 tests).

**Introspection** (`si_agent/introspect.py`, 4 tests) : mesure `agent-self`
toutes les 60 s — temps CPU du processus de l'agent ET de ses enfants (les
sondes) rapporté au temps écoulé (% d'un cœur, % machine), mémoire
résidente (Linux /proc, Windows GetProcessMemoryInfo, macOS getrusage),
durée min / moyenne / max et échecs de chaque collecte et sonde, taille de
la file, charge de l'hôte ; fenêtre glissante de 120 points avec résumé.
Flotte : colonne *Impact agent* (moyenne % cœur, mémoire). Fiche agent →
Poste → *Empreinte de l'agent* : détail, coût par tâche.

**Banc de charge** : commande `bench` {minutes 1–60, factor 2–20, stop} —
collectes et sondes à cadence forcée (intervalle ÷ factor, plancher 15 s),
introspection toutes les 30 s, événements `bench-started` / `-finished`
(avec la synthèse) / `-stopped` ; la fiche compare « en banc » et « hors
banc ». C'est la réponse chiffrée à « quel est l'impact d'une sonde ».

Vérifié réellement : tests agent (80) et central ; JSX compilé. Non vérifié
sur Windows réel : `-EnrollToken` sous Windows PowerShell 5.1 (chemin
WebClient), `GetProcessMemoryInfo`. `tests/test_updater.test_run_update`
échouait déjà avant cette livraison (lambda à 2 arguments) — à reprendre.

## Audit d'application web depuis le poste (livraison #617)

Demandé : « un module sur sonde Windows permettant d'auditer un
dysfonctionnement partiel d'application web ». Sonde `web-audit` (famille
explorer, Python stdlib, Windows / Linux / macOS, non privilégiée) : pour
chaque URL (`--urls a,b` dans le catalogue, ou `web-audit.txt` dans
`%ProgramData%\si-agent` / `/etc/si-agent`), décompose l'accès tel que le
poste le subit — DNS, TCP, TLS (version, expiration), premier octet,
téléchargement, code, redirections — puis chaque script / style / image /
cadre de la page avec son code et sa durée. Constats : `dns-failed`,
`connect-failed`, `tls-failed`, `http-error`, `http-client-error`,
`slow-ttfb`, `slow-total`, `sub-errors`, `sub-slow`, `cert-expiring`,
`redirect-chain`, `empty-body`, `mixed-content`. Sans authentification : une
application derrière une connexion renvoie sa page de connexion (302/401),
déjà une information. Hub : section « Audit d'application web » dans la
fiche agent (détail dépliable par URL) et onglet **Audit web** de la tuile :
matrice URL × poste (`GET /web-audit?site=`) — colonne rouge = l'application,
ligne rouge = le poste ou son segment. 4 tests (analyse HTML, constats,
serveur HTTP local réel, ligne de commande).
