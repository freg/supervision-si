# ADR — Clonage et distribution du hub (items 108-110)

**Statut :** Proposé (cadrage, aucune ligne de code)
**Date :** 2026-09-27
**Décideurs :** freg
**Rattachement :** items 108 (réplication), 109 (répartition tuiles/API/charges),
110 (agent miroir portail). Briques existantes : pile autonome #517, services-api
+ tour de contrôle #584/#586, passerelle `tls-proxy`, Keycloak séparé (`gateway/`),
item 97 (site miroir client, analyse).

## Contexte : ce qui existe déjà (vérifié)

- **76 services** dans un seul `docker-compose.yml` (projet principal), plus un
  projet compose **séparé** `gateway/` (Keycloak + `tls-proxy`), même realm,
  cycle de vie indépendant.
- **Un seul point d'entrée public** : `tls-proxy` sur `GATEWAY_PORT` (6443),
  routage **par chemin** (`/api/<service>`), `proxy_pass http://<service>:port`
  via une **variable** + résolveur DNS Docker (démarre même si un service manque).
- **Le front (hub) n'appelle jamais un service en direct** : chaque
  `VITE_*_API_BASE_URL` vaut `https://HOST_IP:GATEWAY_PORT/api/<service>`, baké
  au build. Conséquence centrale : **déplacer une API sur un autre hôte = changer
  l'amont `proxy_pass` de la passerelle, sans reconstruire le front.**
- **Gestion des déploiements déjà en place** (`services-api` + `tower.py`) :
  livraison zip → analyse (fichiers modifiés/ajoutés) → `plan_for_changes` qui
  remonte des fichiers aux **services impactés** (via contextes de build +
  sources des Dockerfile) → application ciblée (rebuild/restart des seuls
  services touchés), `restart`, `rebuild`, `gateway/reload`. `.env` et registres
  locaux jamais écrasés ; garde-fou `DELIVERY_NUMBER`.
- **État** dispersé : chaque API porte son propre stockage (SQLite dans un
  dossier de données) ou une base dédiée (`geo-postgres`, `pixel-grid-postgres`,
  `projeqtor-db`, `elasticsearch`). Le realm Keycloak est l'état d'auth commun.
- **Précédent de bascule** : pile autonome #517 = `si-agent-api` (même image,
  mêmes données) sur une autre VM + un **aiguillage** nginx sur super qui renvoie
  vers cette VM. Modèle directement réutilisable pour la distribution.

## Décision : trois étapes (celles de freg), du plus sûr au plus lourd

### Étape 1 — Socle commun : gestion des déploiements + front commun

**Objectif** : un « nœud de base » installable partout, autonome, qui porte tout
ce qu'il faut pour recevoir et appliquer des déploiements et servir l'interface,
indépendamment des tuiles métier qu'il héberge ou non.

Composants du socle : `tls-proxy` (entrée + routage), **`keycloak`** (auth),
**`services-api` + tour de contrôle** (livraisons, plan, rebuild/restart,
gateway-reload), **`hub`** (front commun), et le strict nécessaire partagé
(`memcached`, `prefs-api`, `rights-api`, `accounts-api`/`notify-api` selon le
périmètre d'auth). Le socle sait : recevoir un zip, calculer un plan, écrire les
fichiers, (re)construire/redémarrer, recharger la passerelle — pour **les
services qu'il héberge**.

Point clé déjà acquis : le front étant commun et adressant tout via la
passerelle, un nœud de base peut servir l’UI complète même s'il ne fait
tourner qu'une partie des API — les tuiles dont l'API est ailleurs pointent la
passerelle, qui route vers le bon hôte (préparé en étape 2).

**Ce qu'il reste à faire** : packager le socle en un profil compose dédié
(sous-ensemble des 76 services), documenter la reprise du `.env` et de
`pki/ca/ca.crt`, et faire de `services-api` le point d'entrée unique de la
livraison sur chaque nœud (déjà le cas côté super).

| Dimension | Évaluation |
|-----------|------------|
| Complexité | Faible-moyenne (assemblage de briques existantes) |
| Risque | Faible (aucun état métier déplacé) |
| Réutilise | services-api/tower, gateway, hub, profils compose |

### Étape 2 — Déploiement partiel par paquets cohérents de dépendance

**Objectif** : découper les 76 services en **paquets** déployables, cohérents par
dépendance, et placer chaque paquet sur l'hôte voulu ; la passerelle du socle
route chaque `/api/<service>` vers l'hôte qui porte le paquet.

Exemples de paquets liés (à ne pas séparer) : `geo-catalog-api`+`geo-catalog-postgres` ;
`geo-import-api`+`geo-postgres` ; `pixel-grid-api`+`pixel-grid-bridge`+`pixel-grid-postgres` ;
`projeqtor-app`+`projeqtor-bridge`+`projeqtor-db` ; la famille réseau
(`network-agent-api`, `netprobe-api`, `netmap-orchestrator-api`, `network-explorer`,
`si-agent-api`…). « Ou pas » : un service sans dépendance forte (une API SQLite
autonome) est un paquet à lui seul et bouge seul.

**Mécanisme** :
1. Déclarer un **placement** : `paquet -> hôte` (fichier de conf versionné, lu par
   `services-api`). Un paquet = une liste de services + son ordre `depends_on`.
2. `tower.plan_for_changes` cible déjà les services impactés par une livraison ;
   on lui ajoute le **filtre de placement** (n'appliquer sur un nœud que les
   paquets qui lui sont assignés) et la **génération de la conf passerelle
   multi-hôtes** (`proxy_pass` vers `service:port` en local, ou `<hôte>:port` à
   distance selon le placement).
3. Une **IHM** dans la tour de contrôle : voir les paquets, leur hôte, leur
   charge, déplacer un paquet (rebuild sur la cible, bascule de la route,
   arrêt sur la source). Sur le modèle de l'aiguillage #517.

Options de routage inter-hôtes :

| Option | Pour | Contre |
|--------|------|--------|
| **A. Passerelle re-pointée** (proxy_pass vers `<hôte>:port`) | Aucun rebuild front ; s'appuie sur l'existant ; granularité par service | Le port du paquet distant doit être joignable (réseau/pare-feu, ou tunnel type #159/bastion) |
| B. Une passerelle par hôte + fédération | Isolation forte par nœud | Double routage, plus de conf, latence |
| C. Réseau overlay (Swarm/Nebula) | Adressage transparent | Dépendance à un orchestrateur, écart avec le compose actuel |

**Retenu : A**, cohérent avec l'entrée unique par chemin et l'aiguillage #517 ;
le tunnel (bastion/SSH sortant, item déjà cadré #159) couvre les hôtes non
directement joignables — dont le cas « pas de route » (Proxmox campus).

| Dimension | Évaluation |
|-----------|------------|
| Complexité | Moyenne (placement + conf passerelle générée + IHM) |
| Risque | Moyen (une route mal générée coupe une tuile — d'où plan + aperçu avant application, déjà la culture de la tour) |
| Prérequis | Étape 1 |

### Étape 3 — Miroir complet (réplication + bascule/reprise)

**Objectif** : un second hôte porte une **copie complète** (services **et état**),
prêt à prendre le relais ; bascule et retour arrière maîtrisés.

Le code se réplique déjà trivialement (livraison zip / git). **Le vrai chantier
est l'état.** Trois familles, à combiner selon le service :

| Option | Portée | Pour | Contre |
|--------|--------|------|--------|
| **A. Réplication stockage (ZFS send/recv)** | Dossiers de données + volumes en bloc | Un seul mécanisme pour tout l'état ; les Proxmox sont déjà en ZFS | Réplication asynchrone (RPO = intervalle d'envoi) ; cohérence à la bascule à cadrer |
| B. Par API (export/import applicatif) | Chaque API sait sauver/restaurer (backup-restore-api existe déjà) | Cohérent applicativement ; sélectif | À implémenter par API ; plus lent |
| C. Réplication base-à-base | Postgres (streaming), Elasticsearch (snapshots) | Réplication chaude, RPO faible | Un mécanisme par moteur ; ne couvre pas les SQLite |

**Realm Keycloak** : export/import du realm (déjà pratiqué : `keycloak-backup`,
export partiel avant chaque écriture #98) + realm identique sur le miroir.

**Bascule** : réutiliser l'aiguillage #517 (nginx sur l'entrée qui renvoie vers le
miroir), piloté depuis la tour de contrôle ; retour arrière = re-pointage inverse.
Décider **actif/passif** (miroir froid, bascule manuelle — le plus simple et
suffisant ici) vs actif/actif (hors périmètre, conflits d'état).

**Retenu (proposition)** : **actif/passif**, état par **ZFS send/recv** pour le gros
(dossiers de données, bases) complété par **export realm Keycloak**, bascule par
aiguillage. Les API qui exposent déjà un export (backup-restore) servent de
vérification de cohérence.

| Dimension | Évaluation |
|-----------|------------|
| Complexité | Élevée (réplication d'état + bascule + tests de reprise) |
| Risque | Élevé (cohérence, split-brain si actif/actif — écarté) |
| Prérequis | Étapes 1 et 2 |

## Mécanismes dynamiques d'équilibrage (à noter — raffinement 108/109)

Passer d'un placement **statique** (fichier de conf) à un équilibrage
**dynamique** : les clones se partagent les services selon la charge réelle,
sous contrôle. Trois pièces, en boucle fermée.

1. **Jeton de responsabilité par service (élection + notification)** — pour chaque
   service, un **jeton** (bail/lease) désigne le **clone responsable** à l'instant
   T ; c'est la source de vérité de « qui sert ce service ». L'attribution
   (élection) est **notifiée** (via `notify-api`, événement `service.elected`), et
   c'est ce jeton qui pilote la régénération de la conf passerelle (route vers le
   porteur du jeton). Le bail est **borné dans le temps** (renouvellement) pour
   qu'un clone muet perde le service au lieu de le bloquer. Garde-fou
   **anti-split-brain** : un seul jeton par service à la fois (coordination via
   `services-api` comme arbitre, ou un verrou partagé) — jamais deux porteurs.

2. **Analyse permanente de charge et de temps de réponse** — mesure continue, par
   service **et** par clone : charge (CPU/mémoire/nb requêtes) et **temps de
   réponse** (latence, file d'attente). Étend le feu tricolore de la tour de
   contrôle (#584/#586) et s'appuie sur les sondes/observabilité déjà en place.
   C'est l'entrée de décision : où un service tourne-t-il le mieux, quel clone
   sature.

3. **Translation automatique du jeton sur charge déséquilibrée** — quand la
   mesure révèle un déséquilibre durable (seuil + **hystérésis** pour éviter le
   battement), le jeton d'un service **migre** vers un clone moins chargé :
   démarrage sur la cible → bascule de la route (passerelle) → arrêt sur la
   source. Automatique, mais **journalisé, notifié et réversible**, avec un
   interrupteur manuel (comme l'auto-heal de la tour : activable/désactivable).

**Contrainte d'état (lien étape 3)** : translater librement un jeton n'est sûr que
pour un service **sans état** (ou en lecture). Un service **avec état** ne peut
migrer que si son état est **co-localisé ou répliqué** au préalable — donc la
translation automatique vise d'abord les **paquets sans état** ; les paquets avec
état restent en placement contrôlé tant que l'étape 3 (réplication) ne les couvre
pas. Le jeton ne doit jamais désigner un clone dont l'état n'est pas à jour.

## Analyse des compromis (transversale)

- **L'entrée unique par chemin + front adressant la passerelle** est ce qui rend
  la distribution possible sans toucher au front : tout se joue dans la conf
  générée de `tls-proxy` et le placement. C'est le pivot des trois étapes.
- **`services-api`/`tower` est déjà l'organe de déploiement** : on l'étend
  (placement, conf multi-hôtes) plutôt que de créer un système parallèle.
- **L'état est le seul vrai verrou** (étape 3) ; étapes 1-2 ne déplacent que du
  code et des routes, donc peu risquées et livrables tôt.
- **Agent miroir portail (110)** : une fois l'étape 1 packagée, l'« agent miroir »
  = le socle (front commun + services-api) déployé par l'agent si-agent
  (Linux/Windows), exactement comme #517 mais empaqueté pour installation en un
  geste. Il devient le portail de secours / lecture locale d'un site sans route
  (cas Proxmox campus).

## Conséquences

- Devient plus facile : servir l'UI partout (étape 1) ; alléger super en sortant
  des paquets lourds (étape 2) ; survivre à la perte d'un hôte (étape 3).
- Devient plus difficile : la conf passerelle devient générée/multi-hôtes (source
  de panne si mal calculée → aperçu obligatoire) ; l'état réparti impose une
  discipline de réplication et des tests de reprise réguliers.
- À revisiter : joignabilité réseau inter-hôtes (tunnels/bastion #159) ;
  cohérence de bascule (RPO/RTO cibles à fixer avec freg).

## Prochaines actions

1. [x] Découpage en **paquets** — fait : `docs/paquets-distribution-hub.md` (53 paquets atomiques + 9 bundles fonctionnels, état et liens inter-bundles). Reste à **valider le placement initial** proposé.
2. [x] Étape 1 : `deploy/socle.py` (list / up --no-deps / status / check), `deploy/README-socle.md` (reprise `.env`/PKI), tests — fait #661.
3. [~] Étape 2 : placement = `deploy/nodes.json` × `deploy/cohorts.json` (#513) ; filtre de placement dans `plan_for_changes` (`tower.filter_plan`) et IHM « Répartition » de la tour (affectation, apply, migration avec données) — fait #662. Reste : paquets plus fins que les cohortes (53 paquets atomiques) et conf passerelle multi-hôtes sans relais (option A) si les relais #513 ne suffisent pas.
4. [ ] Étape 3 : PoC ZFS send/recv d'un dossier de données + export/import realm ;
   fixer RPO/RTO ; procédure de bascule/retour via aiguillage.
5. [ ] Étape 1 packagée → dériver l'**agent miroir portail** (110).
6. [ ] Jeton de responsabilité par service (bail borné, élection, notif `service.elected`, arbitrage anti-split-brain).
7. [ ] Télémétrie continue charge + temps de réponse par service/clone (extension tour de contrôle).
8. [ ] Translation automatique de jeton sur déséquilibre (seuil + hystérésis, journal/notif/réversible, interrupteur) — d'abord paquets sans état.
