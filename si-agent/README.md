# si-agent — agent hôte Linux et moteur de sondes (livraison #420)

Demandé : « une sonde linux… un agent qui permette d'auditer le host et sa
zone réseau… déployer des sondes futures en python ou en shell/bash », précisé
par « l'agent host surveille le host (cpu, disque, mémoire, log, risques
internes) et il sert de machine-moteur pour la gestion de plugin/sonde ».
Décision de la personne : **nouveau paquet `si-agent`**, distinct de
`netprobe/agent` (sonde réseau Raspberry Pi) — les deux partagent seulement
le protocole signé et la file locale (copiés, voir `sync-shared.sh`).

Backlog 63. Cette livraison = **l'agent seul** (v0, côté hôte). Le central
`si-agent-api` et la tuile hub « Agents » sont la livraison suivante ; le
protocole attendu du central est décrit ci-dessous pour qu'il soit
construit contre ce contrat.

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

## Installation

```bash
cd si-agent/agent
sudo ./install.sh --agent srv-01 --secret 'SECRET' \
     --central https://VM:6443/api/si-agent --site siege \
     [--ca ca.crt | --insecure] [--enable-plugin network-neighbors]
```

Copie le paquet dans `/opt/si-agent`, les plugins dans
`/var/lib/si-agent/plugins`, écrit `/etc/si-agent/agent.json` (mode 600),
installe et démarre `si-agent.service`. Sur place :

```bash
PYTHONPATH=/opt/si-agent python3 -m si_agent.agent --status    # file, plugins, derniers risques
PYTHONPATH=/opt/si-agent python3 -m si_agent.agent --collect   # une collecte hôte + risques, affichée, sans envoi
PYTHONPATH=/opt/si-agent python3 -m si_agent.agent --once      # un passage complet (config, collecte, plugins, envoi)
```

`agent.json` : `agent_id`, `secret`, `central_url` (obligatoires), `site`,
`host_interval_seconds` 60, `inventory_interval_seconds` 3600,
`poll_config_seconds` 300, `commands_poll_seconds` 60, `flush_seconds` 30,
`batch_size` 100, `queue_path`, `plugins_dir`, `risk_thresholds`, `plugins`
(surcharges locales), `ca_file`, `insecure`.

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

Tâches : `host`, `risks` (`{risks: [...], summary}`), `inventory`,
`plugin:<id>` (`data._plugin` = id, version, durée).

## Tests

```bash
cd si-agent/agent && python3 -m unittest            # 16 tests
./sync-shared.sh --check                              # copies protocol/localqueue à jour
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

**Non vérifié** : `install.sh` et le service systemd sur une vraie machine
(pas de systemd ici) ; Raspberry Pi ; `journalctl` avec de vraies erreurs ;
le central lui-même (n'existe pas encore — #421).
