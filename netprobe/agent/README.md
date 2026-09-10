# netprobe-agent — sondes distribuées et collecteur de site

Livraison #405 (backlog items 45, 47, 48). Demandé explicitement le
2026-09-06 : « dans le backlog il y a un agent à déployer, reprend cette
partie ; prépare une image raspi0W comme sonde wifi ; idem pour un agent
sur raspi3b pour collecter ». Fait suite à la note d'architecture
« Supervision WiFi continue — Campus Alpha » (#303, quatre couches
corrélées) et à la reformulation de l'item 47 : « voyons ce qu'on peut
déjà faire sans RF simplement avec un client wifi et la couche IP et le
snmp ».

## Ce que ça construit

```
 Pi Zero W (sonde)          Pi 3B (collecteur, Ethernet)        VM centrale
 ┌──────────────────┐  WiFi  ┌──────────────────────┐   VPN   ┌───────────────┐
 │ netprobe_agent   │ ─────► │ netprobe_agent       │ ──────► │ netprobe-api  │
 │   .agent (probe) │ HTTP   │   .collector         │ HTTPS   │  /agents/...  │
 │ tâches : wifi_   │ signé  │ file locale SQLite   │ signé   │  hub : onglet │
 │ link, wifi_scan, │        │ statut consultable   │         │  Sondes WiFi  │
 │ ping, dns, http, │ ◄───── │ sur place            │ ◄────── │  (flotte,     │
 │ iperf3, sys      │ tâches │ flotte en cache      │ flotte  │   tâches)     │
 │ file locale      │        │                      │         │               │
 └──────────────────┘        └──────────────────────┘         └───────────────┘
```

Un seul paquet Python (`netprobe_agent/`, **bibliothèque standard
uniquement**), deux rôles :

- **Sonde** (`agent.py`, Pi Zero W) — exécute des tâches périodiques et
  pousse les mesures vers le collecteur du site. Tâches disponibles
  (`tasks.py`) : `wifi_link` (BSSID, SSID, canal, signal, débits
  négociés, compteurs d'erreurs du pilote), `wifi_scan` (bornes visibles,
  occupation par canal, plus fort voisin co-canal), `ping`, `dns`, `http`,
  `iperf3` (si installé), `sys` (charge, température, sous-tension du Pi).
- **Collecteur** (`collector.py`, Pi 3B) — reçoit, dédoublonne, garde en
  local, sert à chaque sonde sa liste de tâches, relaie vers le central.

Les deux ont une **file locale store-and-forward** (`localqueue.py`,
SQLite en WAL) : une coupure WiFi ou VPN ne perd aucune mesure — c'est
précisément ce qu'on veut dater et mesurer.

## Questions ouvertes du backlog, tranchées ici

Ces choix étaient explicitement laissés ouverts (items 45 et 48). Défauts
raisonnables, annoncés, révisables :

| Question | Choix | Pourquoi |
|---|---|---|
| Agent sparrow-wifi réutilisé ou agent netprobe propre ? | **Agent propre** | Le Pi Zero W (ARMv6 monocœur, 512 Mo) ne fait pas de mode moniteur et sparrow-wifi n'apporte rien sans lui ; la couche « expérience client » veut un client WiFi *ordinaire*. sparrow-wifi + HackRF restent le volet RF sur le mini PC (item 50), séparé. |
| Enregistrement d'un agent | **Provisionné à la construction de l'image** (identifiant + secret générés par le central, voir `image/`) | Pas de découverte automatique : une sonde inconnue ne peut rien écrire. |
| Récupération de la configuration | **Tirée par la sonde** auprès du collecteur (`GET /api/v1/agents/<id>/tasks`, toutes les 5 min), lui-même synchronisé avec le central | On change une cible depuis le hub, jamais en reflashant — « un interprète minimal qui s'enrichit des tâches reçues ». Sans collecteur : dernières tâches connues, sinon `default_tasks`. |
| Remontée des données | **Push par lots** sonde → collecteur → central, avec file locale à chaque étage | Le sens push évite d'exposer un port sur les sondes ; la file rend la coupure observable au lieu de la subir. |
| Authentification | **HMAC-SHA256 par appareil** sur méthode + chemin + horodatage + empreinte du corps (`protocol.py`) ; identité prise de la signature, jamais du corps | Sans fenêtre temporelle stricte : un Pi Zero W n'a pas d'horloge et démarre avec une heure fausse ; le rejeu est neutralisé par la déduplication (agent, tâche, instant). |
| Traçabilité | Chaque mesure porte `agent_id`, `task`, `at` ; le collecteur note dernier contact et IP par sonde | « Quel agent a mesuré quoi, quand » — exigence de l'item 48. |

## Ce que ça lève par rapport à #385

`iperf3_probe.py` (#385) notait le suivi de BSSID/itinérance « hors de
portée » parce que le conteneur central ne voit pas l'état WiFi de
l'hôte. **Un agent natif sur le Pi le voit** : `wifi_link` toutes les 30 s
donne le BSSID courant — ses changements dans le temps sont le suivi
d'itinérance demandé. `wifi_scan` donne en plus, sans matériel RF,
l'occupation des canaux vue de chaque point de mesure et le plus fort
voisin sur *notre* canal (candidat interférence WiFi ; les émetteurs
non-WiFi restent l'affaire du HackRF, item 50).

## Lancer / tester

```bash
cd netprobe/agent
python3 -m unittest discover -s tests -t .      # 58 tests, aucune dépendance
python3 -m netprobe_agent.agent --config examples/agent.json --once -v
python3 -m netprobe_agent.collector --config examples/collector.json -v
```

Sur un Pi (installé par l'image, voir `image/`) : services systemd
`netprobe-agent` / `netprobe-collector`, code dans `/opt/netprobe-agent`,
configuration dans `/etc/netprobe-agent/agent.json` ou
`/etc/netprobe-collector/{collector,fleet}.json`, files dans `/var/lib/`.
`python3 -m netprobe_agent.agent --status` affiche l'état local.

Routes du collecteur (LAN du site) : `GET /health`, `GET /api/v1/status`
(sondes vues, file, dernier contact central), `GET /api/v1/latest?task=`
(dernières mesures, consultables **sur place** même VPN coupé), et, signées,
`GET /api/v1/agents/<id>/tasks`, `POST /api/v1/agents/<id>/measurements`.

## Vérifié réellement / non vérifié

**Vérifié** (58 tests) : analyseurs sur des sorties réelles d'`iw`/`ping`
(dont un vrai bug trouvé : un SSID vide — borne masquée — faisait capturer
la ligne suivante comme nom de réseau, `\s*` avalant le saut de ligne) ;
signature/vérification et toutes les altérations (corps, chemin, méthode,
secret, horodatage) ; file locale (déduplication, lots, purge qui ne touche
jamais aux mesures non envoyées, base corrompue mise de côté) ; tâches avec
sous-processus simulés (binaire absent, scan « busy », bornes de
paramètres, sous-tension du Pi) ; boucle de la sonde (échéances, tâches
tirées du collecteur avec repli local, store-and-forward, lot 400
abandonné) ; collecteur (identité prise de la signature, relais par lots
vers le central, flotte persistée) ; **chaîne HTTP réelle** sonde →
collecteur sur 127.0.0.1 avec le vrai client urllib signé.

Deuxième défaut de conception attrapé par les tests : l'instant `at` d'une
mesure était pris de l'horloge murale dans `run_task`, alors qu'il fait
partie de la clé de déduplication — deux exécutions dans la même seconde
se seraient écrasées. Il vient désormais de l'horloge de l'agent.

**Non vérifié ici** : aucun Raspberry Pi, aucune carte WiFi — les sorties
d'`iw` sont des captures représentatives (brcmfmac/mt76), pas celles de
VOS bornes ; comportement de `iw scan` sous trafic soutenu (le pilote
répond « busy », géré mais jamais observé) ; consommation réelle sur Pi
Zero W ; TLS vers le central (le collecteur parle HTTPS à tls-proxy via
urllib — certificat auto-signé à faire accepter, voir `image/README.md`).
