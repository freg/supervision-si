# Supervision WiFi — Campus Alpha : vérification de la proposition et état construit

Livraisons #405 → #408 (2026-09-06). Demandé : « dans l'historique tu
trouveras un document d'audit du wifi du site alpha et ton homologue m'a
fait une première proposition, peux tu reprendre ce travail le vérifier et
entreprendre les développements nécessaires ; dans le backlog il y a un
agent à déployer ; prépare une image raspi0W comme sonde wifi ; idem pour un
agent sur raspi3b pour collecter ».

## Ce qui a été relu

- La transcription de la session #295-306 : votre note « sonde spécifique
  wifi (à mettre au point) » (symptômes : flotte hétérogène, forte demande
  au démarrage, mobiles rapides, bornes qui plantent, débit à zéro pendant
  longtemps, services distants saturés, connexions interrompues, signaux
  perturbés) et le rapport `Audit-WiFi-Alpha.pdf` — **confidentiel, non
  conservé** : seule l'analyse de mon homologue en subsiste (relevé RF
  ponctuel, densité élevée d'émetteurs, recommandation du rapport lui-même
  d'aller vers des sondes continues et du SNMP).
- La note d'architecture « Supervision WiFi continue — Campus Alpha »
  (docx, hors dépôt) : quatre couches corrélées — RF, infrastructure,
  expérience client, backend/WAN — et l'alternative sparrow-wifi/HackRF au
  Sidekick.
- Les items 45, 47, 48, 49, 50, 51 du backlog, #385 (iperf3, limite BSSID)
  et la reformulation de l'item 47 : « voyons ce qu'on peut déjà faire sans
  RF simplement avec un client wifi et la couche IP et le snmp ».

## Verdict sur la proposition

L'architecture en quatre couches tient : chaque symptôme de votre note a
une couche qui peut le distinguer, et la corrélation dans le temps est
bien ce qui manque à un relevé ponctuel. Rien à contredire sur le fond.
Quatre points ont été corrigés ou précisés en construisant :

1. **Le Pi Zero W était sous-estimé.** La note le cantonnait à
   « ping/iperf périodique + lecture RSSI ». Sans mode moniteur, un client
   WiFi ordinaire voit déjà, via `iw` : son BSSID (donc ses changements de
   borne = **itinérance**), son canal, son signal, ses débits négociés, les
   compteurs d'erreurs du pilote, et **toutes les bornes visibles avec leur
   canal et leur signal** — c'est-à-dire l'occupation des canaux vue de
   chaque point de mesure et le plus fort voisin co-canal. Cela couvre la
   part *WiFi* de « signaux perturbés par des émetteurs sur les mêmes
   canaux ». La part *non-WiFi* (four, émetteur propriétaire) reste
   l'affaire du HackRF (item 50, matériel non reçu).
2. **La limite « BSSID hors de portée » de #385 n'était pas une limite du
   projet, mais du conteneur.** Un agent natif sur le Pi la lève. C'est
   fait : tâche `wifi_link` toutes les 30 s, détection des changements de
   borne dans le hub (itinérance sans coupure / après coupure /
   reconnexion sur la même borne).
3. **Le Pi 3B n'était pas dans la note** ; vous l'ajoutez comme collecteur
   de site. C'est le bon rôle : Alpha est joint en VPN, et le WAN/VPN est
   justement une des couches à diagnostiquer. Un collecteur local sur
   Ethernet garde les mesures **sur place**, consultables par le
   technicien même VPN coupé, et les relaie quand il revient.
4. **sparrow-wifi comme agent des Pi (option 1 de l'item 48) est écarté**
   pour le Zero W : il n'apporte rien sans mode moniteur, pèse sur un ARMv6
   à 512 Mo, et la couche « expérience client » exige un client
   *ordinaire*, pas un scanner. Il garde toute sa place sur le mini PC
   avec le HackRF (item 50), en système séparé pour l'instant.

Ce qui reste **non tranché**, volontairement, faute de données réelles :
la vue de corrélation multi-couches et le guidage technicien (item 51).
L'onglet « Sondes WiFi » en est le socle (ce que chaque sonde voit, quand),
pas la corrélation elle-même — elle se conçoit sur de vraies séries.

## Ce qui est construit

| Livraison | Quoi | Où |
|---|---|---|
| #405 | Agent (sonde Pi Zero W) et collecteur (Pi 3B), stdlib, file store-and-forward, HMAC, tâches tirées | `netprobe/agent/` — README détaillé, 58 tests |
| #406 | Central : flotte, secrets, provisionnement, flotte signée pour le collecteur, ingestion signée et dédupliquée, lectures | `netprobe/api/agents_store.py`, routes `/agents*`, `/fleet` — 8 tests |
| #407 | Hub : onglet « 📶 Sondes WiFi » (flotte, dernières mesures, courbe de signal, itinérance, édition des tâches) | `hub/src/NetprobeAgentsTab.jsx`, `netprobeAgents.js` — 7 tests, build Vite réel |
| #408 | Constructeur d'images (Zero W sonde / 3B collecteur) sur l'image officielle, premier démarrage automatique | `netprobe/agent/image/` — testé sur image synthétique + provisionnement réel |

Couche par couche, par rapport à la note :

| Couche | Question | État |
|---|---|---|
| RF légère | signal, canal, bornes visibles, voisins co-canal, itinérance | **construit** (`wifi_link`, `wifi_scan`) |
| RF lourde | trames de désassociation, spectre non-WiFi | attend RTL8812AU / HackRF (items 47, 50) |
| Infrastructure | la borne va-t-elle bien ? | API Nebula bloquée sur licence (49) ; SNMP direct dispo (`snmp-api`, `/traffic-rate` #384) — pas relié aux sondes ici |
| Expérience client | débit réel, DNS, HTTP vers un service de référence, depuis chaque point | **construit** (`ping`, `dns`, `http`, `iperf3`) |
| Backend / WAN | le service distant est-il lent même hors WiFi ? | **construit** : mêmes tâches depuis le collecteur (Ethernet) — à déclarer comme sonde avec `interface` inutile, ou smokeping central existant |
| Santé des sondes | sous-tension, température, charge du Pi | **construit** (`sys`) — une sonde mal alimentée « voit » un mauvais WiFi |

## Mise en route (ordre recommandé)

1. Déployer #405-#408 sur la VM (`run.sh up -d --build` — netprobe-api et hub reconstruits).
2. Hub → Sondes réseau → « 📶 Sondes WiFi » → « + » : créer `alpha-collecteur-01` (collecteur) puis `alpha-sonde-01`, `-02`… (sondes), site `alpha`.
3. Construire l'image du collecteur (adresse fixe, `--ca` = AC de la PKI du projet, `--central-url`), la flasher sur le 3B, le brancher en Ethernet sur le LAN Alpha. Vérifier `http://IP:6127/api/v1/status` : `last_central_contact` non nul = le VPN et la signature fonctionnent.
4. Construire les images des sondes (`--collector-url http://IP-du-3B:6127`, SSID/clé du WiFi de production), les flasher, les poser aux points stratégiques (zones faibles du rapport, zones de plainte). Dans le hub, chaque sonde passe en « vue il y a N s ».
5. Laisser tourner **au moins une journée** avant toute conclusion, puis regarder par sonde : courbe de signal, changements de borne (surtout « après coupure »), ping vers la passerelle, voisins co-canal. C'est là que la vue de corrélation (item 51) se dessinera sur du réel.

## Non vérifié — à dire clairement

Aucun Raspberry Pi, aucune carte WiFi, aucune borne Alpha dans
l'environnement de développement. Les sorties d'`iw` utilisées dans les
tests sont des captures représentatives, pas les vôtres ; le premier
démarrage des images n'a jamais été observé (voir `netprobe/agent/image/README.md`
pour les points à regarder au premier essai). Tout le reste — protocole,
files, chaîne HTTP sonde → collecteur, routes du central, construction des
images, build du hub — a été exécuté pour de vrai.
