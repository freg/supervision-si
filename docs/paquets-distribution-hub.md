# Catalogue des paquets pour la distribution (préalable étape 2)

**Statut :** Proposé (atelier de découpage) · **Date :** 2026-09-27 · **Décideurs :** freg
**Compagnon de** `docs/architecture-clonage-distribution-hub.md` (items 108-110).

Deux niveaux : les **paquets atomiques** (unités de co-localisation obligatoire,
tirées du graphe `depends_on` + datastore/bridge/portal — 53 unités, en annexe)
et les **bundles fonctionnels** ci-dessous, qui regroupent ces paquets pour un
placement réaliste par hôte. Règle : une dépendance vers une base/bridge/portal
= **co-localisation** ; une dépendance vers une autre API = **besoin de joindre**
(route passerelle), pas une fusion.

Colonne « État » : *avec état* = porte un stockage (SQLite/volume/base) ; *sans
état* = seulement du calcul/relais. Elle décide de l'éligibilité à la
**translation automatique de jeton** (raffinement de l'ADR) : sûre d'abord pour
les paquets **sans état** ; les paquets avec état ne migrent qu'après réplication
(étape 3).

## Socle commun (étape 1 — toujours présent sur un nœud de base)

`memcached`, `prefs-api`, `rights-api`, `accounts-api`, `notify-api`,
`services-api` (déploiement/tour), `hub` (front commun), `launcher` — plus le
projet séparé `gateway/` (`keycloak`, `tls-proxy`). C'est la base installable
partout ; elle sert l'UI complète et pilote les livraisons, même si les tuiles
métier tournent ailleurs.

## Bundles fonctionnels (candidats de placement)

### 1. Cœur supervision + ticketing — *avec état* · **garder groupé**
`api` (+`frontend`,`pipeline`,`imap-client-api`,`imap-connectors`) · `tickets-api`
(+`tickets-portal`,`tickets-postgres`) · `projeqtor-app` (+`projeqtor-bridge`,
`projeqtor-db`) · `tasks-api` · `relations-api`.
Fortement interconnecté (projeqtor→tickets ; relations→tickets/tasks/ged/pixel-grid).
Le noyau le plus lié : à laisser d'un bloc sur l'hôte principal.

### 2. Réseau & supervision d'équipements — *avec état* · **1er candidat à déporter (charge)**
`si-agent-api` · `cortex-api` (besoin si-agent) · `network-agent-api` ·
`netprobe-api` · `netmap-orchestrator-api` · `network-explorer` (sans état) ·
`network-equipment-api` (besoin credentials, snmp) · `snmp-api` · `mikrotik-api`
(besoin credentials) · `cisco-api` (besoin credentials) · `nebula-api` (besoin
ged) · `ipam-api` (sans état) · `cacti-api` (sans état) · `zenoss-api` (sans
état) · `optick-api` (sans état) · `service-watch-api` (besoin credentials) ·
`docker-monitor-api` · `rsyslog-listener` (sans état) · `ups-monitor-api` ·
`licenses-api` (besoin credentials, si-agent) · `si-proxy` (+`si-proxy-admin-api`).
La plus grosse famille — c'est elle qu'on déporte pour soulager super (et qui
colle au scénario campus). Besoin transverse : `credentials-api` joignable.

### 3. Coffre-fort & secrets — *avec état* · **sensible, placement contrôlé**
`vault-api` (+`vault-portal`) · `vault-admin-api` (+`vault-admin-portal`) ·
`credentials-api`. `credentials-api` est requis par le bundle Réseau : soit
co-placé avec Réseau, soit gardé joignable depuis lui (route passerelle).

### 4. Documents / GED / fichiers — *avec état*
`ged-api` · `file-manager-api` (besoin ged, ssh-tunnels) · `architecture-api`
(besoin ged, ssh-tunnels) · `ssh-tunnels-api` · `owncloud-api` (sans état) ·
`owncloud-search-api` (besoin elasticsearch) · `elasticsearch` · `memory-api`.
`ged-api` est un point partagé (nebula, relations en dépendent).

### 5. Géo / SIG — *avec état*
`geo-catalog-api` (+`geo-catalog-postgres`, besoin pixel-grid) · `geo-import-api`
(+`geo-postgres`) · `pixel-grid-api` (+`pixel-grid-bridge`,`pixel-grid-postgres`,
besoin api). `pixel-grid` est à la charnière (cœur + géo + relations) : le garder
proche du cœur, ou joignable.

### 6. IA / classification — *avec état* · **hôte dédié (GPU pour ollama)**
`ollama` · `assistant-api` · `classifier-api` · `vigilance-api` (besoin
classifier) · `tts-gu-api` (sans état). `ollama` est lourd (modèles/GPU) : hôte
à part, cohérent avec les paliers matériels Néopays.

### 7. DBA & bases — *avec état*
`dba-api` (+`dba-portal`) · `schema-analyzer-api` (besoin dba).

### 8. Annuaire LDAP — *avec état*
`ldap-admin-api` (+`ldap-admin-portal`).

### 9. Outillage divers — mixte
`backup-restore-api` (avec état) · `glpi-api` (sans état) · `retro-api` (avec
état). Peu couplés : déplaçables individuellement (« ou pas » de paquet).

## Lecture pour l'étape 2

- **Placement initial suggéré** : super garde Socle + bundles 1, 3, 5, 7, 8, 9 ;
  on déporte en priorité le bundle **2 (Réseau)** vers un second hôte (charge),
  puis **6 (IA)** vers l'hôte GPU. Chaque déport = régénérer la conf `tls-proxy`
  (amont `/api/<service>` → `<hôte>:port`), aucun rebuild front.
- **Dépendances inter-bundles à garder joignables** (routes, pas fusions) :
  credentials-api ← Réseau ; ged-api ← Documents/Réseau(nebula) ; si-agent-api ←
  cortex/licenses ; pixel-grid-api ← Géo/cœur(relations) ; tickets-api/tasks-api
  ← projeqtor/relations ; elasticsearch ← owncloud-search ; snmp-api ←
  network-equipment ; classifier-api ← vigilance.
- **Éligibles à la translation dynamique de jeton d'entrée** (sans état) :
  network-explorer, ipam-api, cacti-api, zenoss-api, optick-api, rsyslog-listener,
  glpi-api, owncloud-api, owncloud-search-api, tts-gu-api, relations-api,
  si-proxy-admin-api. Les autres (avec état) attendent la réplication (étape 3).

## Annexe — 53 paquets atomiques (co-localisation obligatoire)

Généré depuis `docker-compose.yml` (arêtes dures : API ↔ sa base/bridge/portal).
Un paquet multi-services ne se sépare jamais ; un paquet mono-service peut bouger
seul.

    api+frontend+imap-client-api+pipeline · pixel-grid-api+bridge+postgres ·
    projeqtor-app+bridge+db · tickets-api+portal+postgres · dba-api+portal ·
    geo-catalog-api+postgres · geo-import-api+postgres · ldap-admin-api+portal ·
    vault-admin-api+portal · vault-api+portal · + 43 paquets mono-service
    (architecture-api, assistant-api, backup-restore-api, cacti-api, cisco-api,
    classifier-api, cortex-api, credentials-api, docker-monitor-api,
    elasticsearch, file-manager-api, ged-api, glpi-api, imap-connectors,
    ipam-api, licenses-api, memory-api, mikrotik-api, nebula-api,
    netmap-orchestrator-api, netprobe-api, network-agent-api,
    network-equipment-api, network-explorer, ollama, optick-api, owncloud-api,
    owncloud-search-api, relations-api, retro-api, rsyslog-listener,
    schema-analyzer-api, service-watch-api, si-agent-api, si-proxy,
    si-proxy-admin-api, snmp-api, ssh-tunnels-api, tasks-api, tts-gu-api,
    ups-monitor-api, vigilance-api, zenoss-api).
