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
`plugin_max_memory_mb` (512), `log_level`, `log_file`.

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
abaissée, limites CPU / mémoire (`max_memory_mb`, 512 Mo par défaut) /
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
