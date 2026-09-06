# Vigilance -- automates d'analyse cyber-vigilance/santé du parc (livraison #262)

Backlog item 34, suite du module `classifier/` (#260). Demandé
explicitement, en confirmant une proposition concrète faite en
retour :

> pourrait être : pour la catégorie "client DHCP dynamique" [...]
> OUI j'aime c'est tout à fait le genre d'analyse que je veux, sois
> créatif et si possible cible les éléments de cyber vigilance et de
> santé du parc et du réseau

## Ce module NE COLLECTE RIEN lui-même

Il CROISE, en lecture, ce qui existe déjà :
- **`network-agent`** (#250-251, #256) -- appareils, échanges entre
  appareils, services par appareil, historique de présence/volume.
- **`classifier`** (#260) -- catégorie sémantique d'un nom d'hôte
  (prénom, équipement d'infrastructure, client DHCP dynamique...).

La seule donnée PROPRE à ce module est le JOURNAL des signaux
détectés -- chaque passage d'analyse qui trouve quelque chose
d'anormal crée une ligne, jamais recalculé à la volée à chaque
consultation (permet de voir une TENDANCE : "signalé depuis 3 jours"
a plus de valeur qu'un simple "signalé maintenant").

## Trois premiers signaux -- ciblés sur les clients DHCP dynamiques

La catégorie la plus risquée par nature : des appareils NON
identifiés individuellement, potentiellement invités/BYOD/WiFi.

1. **Contact avec de l'infrastructure** (`critical`) -- un client
   DHCP qui échange du trafic avec un appareil classé "équipement
   d'infrastructure" (NMS, onduleur, serveur...) -- un invité ne
   devrait normalement jamais parler DIRECTEMENT à ce type
   d'équipement. Signal de violation de segmentation potentielle.
2. **Diversité de services élevée** (`warning`) -- un client DHCP
   utilisant plus de `VIGILANCE_SERVICE_DIVERSITY_THRESHOLD` services/
   ports distincts (défaut 10) s'écarte du profil "invité normal"
   (HTTP/HTTPS/DNS, peu de ports).
3. **Croissance de volume anormale** (`warning`) -- un client DHCP
   dont le volume cumulé progresse de plus de
   `VIGILANCE_VOLUME_GROWTH_PERCENT_THRESHOLD` % (défaut 200%) entre
   le premier et le dernier relevé d'historique -- usage intensif
   inattendu pour un profil normalement transitoire.

## Comment ça tourne

Thread de fond, un passage toutes les
`VIGILANCE_ANALYSIS_INTERVAL_SECONDS` (30 min par défaut) -- analyse
TOUS les segments connus (via `network-agent` `/sites`). Déclenchement
manuel possible via `POST /analyze` (tout de suite, sans attendre le
prochain passage périodique). Rétention bornée
(`VIGILANCE_RETENTION_DAYS`, 30 jours par défaut, même motif que
`network-agent`/#251 et `memory`/#259).

Chaque étape est BEST-EFFORT explicite -- une source indisponible
(network-agent ou classifier) réduit ce que l'analyse peut détecter,
ne la fait jamais planter entièrement.

## Vérifié réellement

Testé en profondeur avec un scénario réaliste reproduisant les vraies
données de la personne (nms.intranet, dhcp139.intranet en contact
avec nms, dhcp144.intranet au profil normal) : les TROIS signaux
correctement détectés pour l'appareil anormal (dhcp139), et confirmé
qu'AUCUN signal n'est levé pour l'appareil au profil normal
(dhcp144) -- la distinction la plus importante à vérifier pour un
outil de ce type (jamais de faux-positif sur un cas normal). Détails
textuels de chaque signal vérifiés exacts (nom de l'équipement
contacté, pourcentage de croissance). Cas limites testés : aucun
client DHCP dans le segment (0 signal, jamais une erreur),
network-agent injoignable (0 signal proprement, jamais un crash).
Routes API testées de bout en bout, y compris le déclenchement
manuel. Dockerfile vérifié avec le script de contrôle systématique
développé en #252 -- aucun fichier manquant. Structure JSX complète
revérifiée.

## Reste à faire

- **Seuils NON validés sur un vrai réseau chargé** -- les valeurs par
  défaut (10 services, +200% de croissance) sont un point de départ
  raisonnable, pas des valeurs éprouvées. À ajuster une fois de
  premiers résultats réels observés.
- ~~Signaux supplémentaires~~ -- **un quatrième LIVRÉ EN #266**
  ("infrastructure silencieuse", voir plus haut). D'autres pistes
  restent envisageables pour une prochaine tranche, toujours dans
  l'esprit "cyber vigilance/santé du parc" : appareils DHCP dont le
  nom change souvent (une même MAC qui alterne entre plusieurs noms
  dhcpNNN au fil des baux), fenêtres d'activité inhabituelles
  (trafic DHCP en pleine nuit), croisement avec `architecture-api`
  pour situer géographiquement un signal (quel bâtiment/salle).
- **Autres catégories que `client_dhcp_dynamique`** -- rien n'empêche
  d'étendre ces signaux (ou d'en ajouter de nouveaux) à d'autres
  catégories du dictionnaire (ex. un équipement d'infrastructure qui
  cesse subitement d'émettre du trafic pourrait aussi être un signal
  de santé du parc à part entière).
- **Pas de notification proactive** -- consultation uniquement dans
  la tuile hub pour l'instant, aucune alerte poussée (email, etc.).

## Quatrième signal : infrastructure silencieuse (livraison #266)

Reprise d'une piste explicitement notée "reste à faire" dès la
livraison initiale (#262) : "un équipement d'infrastructure qui
cesse subitement d'émettre du trafic pourrait aussi être un signal
de santé du parc à part entière".

**Infrastructure silencieuse** (`critical`) -- un appareil classé
`equipement_infrastructure` dont le dernier trafic observé
(`last_seen`, croisé depuis `network-agent`) remonte à plus de
`VIGILANCE_SILENCE_THRESHOLD_HOURS` (24h par défaut). Contrairement
aux trois premiers signaux (ciblés sur les clients DHCP dynamiques),
celui-ci cible les équipements d'infrastructure -- un NMS, un
onduleur ou un serveur a normalement une activité RÉGULIÈRE
(supervision, heartbeat, trafic de service) ; un silence prolongé
peut signaler une panne, une coupure réseau, OU un signe de
compromission (arrêt délibéré pour échapper à la détection).

**Un vrai bug trouvé et corrigé en testant ce nouveau signal** :
`analyze_segment` avait un retour anticipé (`if not dhcp_macs: return
0`) qui empêchait TOUTE analyse dès qu'un segment n'avait aucun
client DHCP connu -- correct pour les signaux 1-3 (qui EN dépendent
tous), mais bloquait AUSSI le nouveau signal 4, qui lui est
INDÉPENDANT des clients DHCP. Corrigé en restructurant : les signaux
1-3 restent conditionnés à la présence de clients DHCP, le signal 4
s'exécute désormais TOUJOURS.

**Vérifié réellement** : signal 4 testé isolément (segment avec
SEULEMENT de l'infrastructure, AUCUN client DHCP) -- confirme que le
correctif fonctionne, le signal se déclenche bien là où il échouait
silencieusement avant (0 signal au lieu de 1). Non-régression
complète des quatre signaux TESTÉS ENSEMBLE sur un scénario complet
(infrastructure silencieuse + client DHCP anormal sur les trois
premiers signaux + client DHCP au profil normal) -- confirmé que
les 4 types de signaux se déclenchent correctement simultanément,
et que le client au profil normal n'est TOUJOURS jamais signalé à
tort, quel que soit le nombre de signaux actifs. Date au format
inattendu gérée sans exception (jamais une erreur qui interromprait
toute l'analyse pour un appareil). Structure JSX revérifiée.

## Branchement rights-api (livraison #321)

Suite de l'item 38 du backlog. Une seule route d'écriture dans ce
module -- `/analyze` déclenche un passage IMMÉDIAT (hors du rythme
périodique déjà en place) et PERSISTE les signaux détectés. Sans
garde, n'importe qui aurait pu déclencher des passages répétés à
volonté (bruit dans l'historique des signaux, charge supplémentaire
sur `network-agent-api` en cascade).

OPT-IN via `VIGILANCE_RIGHTS_API_URL`, vide par défaut, comportement
inchangé tant qu'elle n'est pas configurée.

**Vérifié réellement** : comportement opt-in par défaut confirmé,
FAIL CLOSED si `rights-api` injoignable, 403 confirmé pour un groupe
non autorisé, `/signals` confirmée non affectée. Non-régression
complète reconfirmée.
