# Architecture réseau -- vue et outil de parcours (livraison #253)

Nouveau chantier, demandé explicitement après une pause sur
Rétro-ingénierie ("mon souci de rétro ingénierie urgente est réglé...
ça sera utile dans l'avenir, on y reviendra donc pause pour ça") :

> quand un équipement remonte dans la supervision zenoss je dois
> pouvoir identifier les interfaces en amont, en aval et les accès
> pour agir sur l'équipement, je dois aussi identifier les lieux
> d'intervention si des déplacements sont nécessaires, je dois
> pouvoir trouver les documentations liées aux contrats, aux
> spécifications techniques et aux paramètres spécifiques

> quand un dysfonctionnement type effet de bord et étranglement
> comme de la saturation, des abus de protocole, des attaques par
> déni de service ou autre.... idem

Deux scénarios de déclenchement (alerte Zenoss, dysfonctionnement
réseau) qui convergent vers le MÊME besoin : à partir d'un
équipement, retrouver en un seul endroit sa topologie, ses accès,
ses lieux d'intervention et sa documentation.

## Ce que ce module NE DUPLIQUE PAS -- croisé à la lecture

Une reconnaissance a été faite AVANT de coder quoi que ce soit, pour
ne jamais avoir deux sources de vérité qui divergent :

- **Localisation physique** -- déjà dans `zenoss-api`
  (`/location_tree`, colonnes `Location`/`Systems`). **PAS ENCORE
  croisée** dans cette première tranche -- structure en ARBRE côté
  Zenoss (pas de route "localisation de CET équipement" directe),
  nécessiterait de parcourir/mettre en cache tout l'arbre, jugé hors
  de portée pour un premier jet. Voir "Reste à faire" plus bas.
- **Accès de gestion (SSH)** -- déjà dans `ssh-tunnels-api`
  (`ssh_connections`). Croisé EN DIRECT par correspondance
  d'adresse IP (`GET /connections` renvoie une liste plate,
  filtrable simplement -- contrairement à Zenoss).
- **Documents liés** (contrats, spécifications, paramètres) --
  réutilise le mécanisme de liaison POLYMORPHE déjà existant côté
  GED (`document_links`, `linked_type`/`linked_id`, #158) --
  `linked_type="equipment"` ici, jamais une nouvelle table de
  liaison dupliquée.

## Ce que ce module apporte -- la pièce manquante

La **topologie amont/aval** elle-même. `network-agent` (#250)
enregistre déjà des échanges entre appareils, mais ce sont des
paires "qui a PARLÉ à qui" observées sur le trafic RÉEL -- ça ne dit
JAMAIS quelle interface est "en amont" ou "en aval" d'une autre dans
une hiérarchie réseau. Cette hiérarchie est une connaissance MÉTIER
(comment le réseau est réellement câblé/configuré), pas quelque
chose de fiable à déduire automatiquement du trafic -- saisie ici
explicitement.

## Modèle de données

`arch_equipment` (nom, IP, MAC, type, notes) → `arch_interfaces`
(un port physique/logique par équipement, niveau de détail libre) →
`arch_links` (lien DIRECTIONNEL entre deux interfaces, `upstream_*`
est en amont de `downstream_*`).

## La route centrale

`GET /equipment/<id>/overview` -- en UN SEUL appel : l'équipement,
ses voisins amont/aval (avec l'équipement distant complet, pas
seulement un id -- navigation directe possible), ses accès SSH
croisés par IP, ses documents liés croisés depuis la GED. Chaque
croisement est BEST-EFFORT et signale sa propre erreur SANS faire
échouer les autres -- une source indisponible ne masque jamais ce
que les autres ont pu fournir.

## Vérifié réellement

Testé en profondeur avec un scénario réaliste (routeur → switch →
serveur) : voisins amont/aval corrects depuis les TROIS positions
(le sommet, le milieu, l'extrémité), suppression en cascade
(équipement → interfaces → liens orphelins), recherche par nom ET
par IP, lien dupliqué rejeté proprement (contrainte UNIQUE, jamais
un 500 nu), mise à jour avec un champ inconnu ignorée sans jamais
l'interpoler dans le SQL. Route `/overview` testée de bout en bout
avec GED et ssh-tunnels simulés -- y compris le cas GED injoignable,
confirmé que ssh-tunnels continue de fonctionner malgré tout.
Logique de direction du lien (amont/aval) côté hub testée en
isolation. Structure JSX complète revérifiée. Dockerfile vérifié
avec le script de contrôle systématique développé en #252 (aucun
fichier manquant).

## Reste à faire

- ~~Croisement Zenoss (localisation/lieux d'intervention)~~
  **LIVRÉ EN #268** -- nouvelle route ciblée `GET /device_location`
  côté `zenoss-api` (requête directe sur `device`/`ipAddress`, jamais
  un parcours de tout l'arbre -- plus simple que prévu au départ).
  Essaie par NOM d'abord, puis par IP. Section "📍 Lieu
  d'intervention" côté hub. **Les QUATRE volets de la demande
  d'origine (#253) sont désormais tous livrés** : topologie
  amont/aval, accès, lieux d'intervention, documentation.
- ~~Import/rapprochement automatique avec `network-agent`~~
  **LIVRÉ EN #263** -- `POST /import/network-agent`, idempotent
  (matché par adresse MAC, jamais de doublon), synchronise
  seulement l'IP sur un réimport (nom/type/notes personnalisés
  par la personne JAMAIS écrasés). Bouton "⤵ Importer depuis
  Exploration réseau" côté hub. **Import GLPI VOLONTAIREMENT non
  entamé** -- confirmé par la personne (2026-09-03) : "glpi n'est pas
  encore utilisé il est presque vide" -- rien à en tirer tant que
  cet inventaire n'est pas réellement peuplé, jamais une priorité
  tant que cette situation ne change pas.
- **Interface de saisie plus riche** pour les interfaces/liens --
  fonctionnelle mais minimale (formulaires simples), pourrait
  gagner en ergonomie une fois le modèle de données confirmé à
  l'usage.
- **Vue graphique** (pas seulement une liste amont/aval textuelle) --
  rejoint l'idée de graphe d'architecture réseau/inspiration
  Tkined-Scotty déjà discutée -- pas construite dans cette première
  tranche.

## Import automatique depuis Exploration réseau (livraison #263)

`POST /import/network-agent` -- corps JSON optionnel
`{"segment_id": N}` (sans corps, importe tous les segments connus).

**IDEMPOTENT** -- matché par adresse MAC, jamais de doublon sur des
imports répétés. Un équipement DÉJÀ PRÉSENT (même MAC) voit
SEULEMENT son IP mise à jour si elle a changé (plausible via DHCP) --
son NOM, TYPE et NOTES restent INTACTS, potentiellement personnalisés
par la personne après un premier import, JAMAIS écrasés par un
réimport. Un NOUVEL équipement est créé avec le nom d'hôte comme nom
(ou l'adresse MAC si aucun nom d'hôte connu), et une note signalant
son origine ("Importé automatiquement depuis Exploration réseau").

Bouton "⤵ Importer depuis Exploration réseau" côté hub, à côté de la
recherche/création manuelle.

**Vérifié réellement** : testé avec un scénario reproduisant les
vraies données de la personne -- premier import (création), réimport
identique (rien ne change, jamais de doublon), personnalisation
manuelle du nom/notes APRÈS import puis réimport (confirmé préservée,
jamais écrasée), changement d'IP simulé (confirmé synchronisé, MAIS
le nom personnalisé reste intact malgré tout). Appareil sans adresse
MAC géré défensivement (jamais rencontré en pratique, network-agent
exige toujours une MAC). Route testée de bout en bout, y compris
l'URL réellement appelée (HOST_IP, pas le nom de service Docker --
network-agent-api tourne en network_mode: host) et les cas d'échec
(network-agent injoignable, URL non configurée) -- toujours un 502
propre, jamais un crash. Structure JSX revérifiée.

## Croisement de localisation Zenoss (livraison #268)

Complète les quatre volets de la demande d'origine (#253) --
dernier restant, volontairement différé jusqu'ici faute d'une route
adaptée côté `zenoss-api` (localisation exposée uniquement sous
forme d'ARBRE, `/location_tree`, pas de recherche directe par
équipement).

**Plus simple que prévu à l'origine** : la localisation d'UN
équipement précis n'a en réalité jamais eu besoin de parcourir tout
l'arbre -- une requête SQL CIBLÉE directement sur les colonnes
`device`/`Location`/`ipAddress`/`Systems` (déjà utilisées par
`fetch_location_rows` pour CONSTRUIRE l'arbre) suffit. Nouvelle route
`GET /device_location` côté `zenoss-api` (`device` OU `ip`, au moins
l'un des deux). `architecture-api` l'appelle par NOM d'abord (le nom
de l'équipement dans ce registre), puis par IP si rien trouvé --
best-effort, comme les autres croisements de ce module.

Section "📍 Lieu d'intervention" côté hub, entre la topologie et les
accès de gestion (même ordre que la demande d'origine : "les
interfaces... et les accès... les lieux d'intervention... la
documentation").

**Vérifié réellement** : route `/device_location` testée en
profondeur côté `zenoss-api` (recherche par nom, par IP, aucun
résultat -> `None` proprement jamais un 404, base injoignable -> 503
propre). Croisement testé côté `architecture-api` -- localisation
trouvée et affichée correctement, ET confirmé que `zenoss-api`
injoignable ne fait JAMAIS échouer les AUTRES croisements (GED,
ssh-tunnels) de la même vue d'ensemble. Non-régression complète des
deux services reconfirmée. Structure JSX revérifiée.

## Branchement rights-api (livraison #316)

Suite de l'item 38 du backlog. Ce module ne configure JAMAIS
d'équipement réel -- topologie amont/aval DÉCLARÉE, documentation
pure. Une donnée trafiquée n'endommage aucun équipement, mais
pourrait égarer un technicien en plein dépannage (mauvais lien/
équipement affiché comme source d'un incident).

Gardé sur les 8 routes d'ÉCRITURE (créer/modifier/supprimer un
équipement, import depuis network-agent, créer/supprimer une
interface, créer/supprimer un lien topologique) -- jamais la
lecture.

OPT-IN via `ARCHITECTURE_RIGHTS_API_URL`, vide par défaut,
comportement inchangé tant qu'elle n'est pas configurée.

**Vérifié réellement** : comportement opt-in par défaut confirmé,
FAIL CLOSED si `rights-api` injoignable, 403 confirmé sur les 8
routes gardées avec un groupe non autorisé, lecture confirmée non
affectée. Non-régression complète reconfirmée.
