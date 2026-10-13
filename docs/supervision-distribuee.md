# Supervision réseau distribuée — cadrage (item 120, 2026-10-13)

Demande : organiser la supervision réseau en système distribué ; observer diffusions et évolutions de charge dans le
temps (synchronicité, succession, effets de bord) ; suppléance des mesures (mesures lourdes ou intrusives décalées
mais globalement régulières par répartition) ; vue de couverture (zones actives sur carte, vue glissante dans le
temps) ; vue architecturale (théorique / mesurée / déclarée / nommage : rôles, dépendances, interactions, familles) ;
déplacements dans l'espace (« rooming »).

Décisions (13 oct.) : commencer par l'**ordonnanceur réparti** ; carte **au choix** plans de bâtiments (intérieur) ou
OSM (sites) ; déplacements = **tous** : clients Wi-Fi entre bornes, équipements changés de port / VLAN, VM et services
migrés.

## Ce qui existe déjà (à réutiliser, pas à refaire)

| Brique | Rôle dans la cible |
|---|---|
| si-agent : sondes `wifi-probe`, `path-probe`, `broadcast-probe`, `windows-probe`, `gtb-netwatch`, `network-neighbors`, `capture-relay` | capteurs locaux, chaque mesure horodatée et rattachée à un agent / site |
| netprobe : smokeping, nmap, iperf3, sondes Raspberry | mesures actives (latence, ports, débit) |
| network-agent-api : captures, segments | trafic passif (diffusions, ARP, mDNS…) |
| Équipements réseau (SNMP, import Zenoss, MikroTik, Cisco) | tables MAC / ARP / VLAN des switchs et routeurs |
| Cortex (rôles, lieux, apprentissage) | graphe des rôles et dépendances |
| Proxmox / PBS (agents) | VM, CT, hôtes, migrations |
| Plans SVG du campus, Leaflet / OSM | fonds de carte |

## Volet 1 — ordonnanceur réparti et suppléance (tranche 1 FAITE #743)

**Tournée** = une sonde + un groupe d'agents + une période. Le central décide qui la lance et quand :
- *à tour de rôle* (`rotate`) : un agent par créneau, titulaire = rang du créneau ; hors ligne → le suivant en ligne
  **supplée** ; la mesure reste régulière quel que soit l'hôte ;
- *réparti* (`spread`) : chaque agent une fois par période, décalés de période / n (pas de rafale) ;
- phase stable par tournée (deux tournées de même période ne partent pas ensemble), heures calmes, plafond de
  lancements simultanés par site (attente au plus une demi-période, puis « sauté ») ;
- exécution par commande `run_plugin` (aucune mise à jour d'agent), créneaux tracés : prévu, agent, suppléance, commande,
  état ; couverture sur 24 h (prévus / faits / suppléés / sautés / échecs).

Tranches suivantes du volet 1 :
- 1b : budget de charge par agent (CPU / réseau mesurés par l'empreinte #616) pour choisir le moins chargé à égalité ;
  cibles réparties (une liste de cibles découpée entre agents : chacun balaie sa part, rotation des parts) ;
- 1c : mesures netprobe (nmap, iperf3) dans les mêmes tournées.

## Volet 2 — observer dans le temps : diffusions, charge, synchronicité

- Série commune : toutes les mesures ramenées à (instant, agent, site, zone, grandeur, valeur), fenêtres de 1 min.
- Synchronicité : corrélation croisée entre séries (même grandeur sur plusieurs agents, ou grandeurs différentes) avec
  décalage → « la charge monte sur A puis 40 s après sur B » ; propagation d'une diffusion (tempête ARP / mDNS, boucle)
  suivie de segment en segment.
- Succession / effets de bord : après un événement (redémarrage, sauvegarde, migration, tournée lourde), écart des
  autres séries par rapport à leur profil horaire (#530) ; un effet attribué à notre propre mesure intrusive est
  signalé comme tel (les créneaux de tournées sont connus).

## Volet 3 — couverture : zones actives et vue glissante

- Zone = lieu Cortex (bâtiment / étage / salle ou site) ; chaque agent, borne, switch, client y est rattaché.
- Carte au choix : plan SVG de l'étage (zones colorées par activité, bornes, clients) ou OSM (sites, liens entre sites).
- Curseur temporel : rejouer la carte sur une fenêtre glissante (dernière heure, journée, semaine), pas de 1 à 15 min ;
  « trous » de couverture visibles (zone sans mesure fraîche, tournée sautée).

## Volet 4 — vue architecturale : déclaré, théorique, mesuré, nommé

- Quatre sources superposées sur le même graphe : *déclaré* (IPAM, fiches matériels/services, registres), *théorique*
  (règles : rôles et dépendances attendues), *mesuré* (flux vus, ports, ARP/MAC, chemins), *nommage* (DNS, noms d'hôtes,
  conventions) ; écarts mis en évidence (service mesuré non déclaré, déclaré jamais vu, nom trompeur).
- Rôles, familles (même modèle / même rôle), interactions (qui parle à qui, à quelle fréquence).
- Déplacements : client Wi-Fi d'une borne à l'autre (MAC hachée pour les sites clients), équipement changé de port ou de
  VLAN (tables MAC des switchs), VM / CT / service migré (Proxmox, bascules de rôle #654) ; chronologie par objet.

## Ordre proposé

1. #743 tournées (fait) → 1b charge et cibles réparties.
2. Série commune + corrélations (volet 2), indispensable aux deux vues.
3. Couverture sur plan / OSM avec curseur temporel (volet 3).
4. Graphe déclaré / mesuré / nommé et déplacements (volet 4).
