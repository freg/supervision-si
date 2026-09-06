# Risques cyber — supervision-si — état intermédiaire

Vue d'ensemble rapide, pas une analyse exhaustive (à refaire en fin
de conception, comme convenu). Périmètre : les ~20 services du
stack principal + gateway/vault-standalone/mayan, tels que
développés à ce jour (livraison #185).

## Tableau des risques

| # | Risque | Modules concernés | Probabilité | Impact | Statut |
|---|---|---|---|---|---|
| R1 | Pas de segmentation réseau — un seul réseau Docker partagé par ~25 conteneurs | Tout le stack | Moyenne | Élevé | Non traité |
| R2 | Pas d'authentification entre APIs internes — n'importe quel conteneur du réseau peut appeler n'importe quelle API interne | Toutes les `*-api` | Moyenne | Élevé | Non traité |
| R3 | Port SSHFS forwardé lié à `0.0.0.0` (#184) — tout conteneur compromis atteint les bases distantes via un tunnel actif | `ssh-tunnels`, `dba-api` | Faible | Élevé | Partiellement traité (nécessaire au fonctionnement, compensé par R2 si traité) |
| R4 | `.env` en clair sur disque — tous les secrets (mots de passe DB, admin Mayan, bind LDAP...) en clair | Tout le stack | Moyenne | Élevé | Non traité |
| R5 | Clés SSH privées sur disque, montées en lecture seule mais jamais chiffrées | `ssh-tunnels` | Faible | Élevé | Partiellement traité (accès restreint, pas de chiffrement) |
| R6 | Conteneur avec privilèges élevés (`SYS_ADMIN`, `apparmor:unconfined`) pour le montage FUSE | `ssh-tunnels-api` | Faible | Élevé | Accepté (nécessaire à la fonctionnalité, documenté) |
| R7 | Filtrage SQL basique (`sqlLiteral`), pas de requête paramétrée native, sur `/sql` | `schema-analyzer`, `dba-api` | Moyenne | Moyen | Partiellement traité (échappement basique, testé contre une injection simple) |
| R8 | Logs sans rémanence (Memcached volatil) — aucune trace après redémarrage, pas de piste d'audit | Tout le stack | Élevée | Moyen | Backlog noté (#8), non cadré |
| R9 | Logs potentiellement porteurs de données sensibles (messages d'erreur avec identifiants/chemins) sans filtrage avant stockage partagé | Tout le stack | Moyenne | Moyen | Non traité |
| R10 | GED tierce (Mayan EDMS) — surface d'attaque d'un logiciel externe, jamais auditée par nos soins | `ged`, `mayan` | Faible | Moyen | Non évalué |
| R11 | Authentification par mot de passe SSH prévue (backlog #12) — mots de passe intrinsèquement plus faibles que des clés | `ssh-tunnels` | — | — | Backlog noté, pas construit |
| R12 | Futur module SNMP (backlog #13) — SNMP v1/v2c repose sur des "communautés" en clair, faciles à deviner | Futur module SNMP | — | — | Backlog noté, à concevoir avec SNMPv3 dès le départ |
| R13 | Dépendances tierces (Flask, pymysql, psycopg2...) épinglées en version mais jamais scannées pour vulnérabilités connues | Tout le stack | Moyenne | Moyen | Non traité |
| R14 | rsyslog-listener expose un port UDP DIRECTEMENT sur l'hôte (hors `tls-proxy`) — pas d'authentification native au protocole syslog, source spoofable | `rsyslog-listener` | Moyenne | Faible | Accepté (contrainte du protocole, documenté) |

## Matrice de risque (probabilité × impact)

```
              Impact faible   Impact moyen      Impact élevé
Probabilité   
élevée                        R8
moyenne                       R7, R9, R13       R1, R2, R4
faible         R14            R10               R3, R5, R6
```

**À traiter en priorité** (probabilité moyenne+, impact élevé) :
**R1, R2, R4** — l'absence de segmentation réseau et d'authentification
inter-services touche TOUT le stack et amplifie mécaniquement tous
les autres risques (un seul conteneur compromis devient un accès
généralisé).

## Proposition de tableau de bord de surveillance

Un onglet hub dédié (mode déjà éprouvé — `SshTunnelsView`/`GedView`),
un indicateur par risque, vert/orange/rouge :

| Risque | Ce qui serait surveillé | Source technique |
|---|---|---|
| R1/R2 | Nombre d'appels inter-conteneurs par service, alerte sur un appel depuis un service inattendu | Nécessiterait un log d'accès par API (pas encore construit) |
| R3 | Tunnels SSH actifs + liste des conteneurs y ayant effectivement accès | `GET /tunnels` (déjà existant) |
| R4 | Détection de clés `.env` sensibles définies vs attendues, jamais leur VALEUR | Extension de `check-env.py` (déjà existant, jamais lu de valeur) |
| R5 | Âge des clés SSH, dernière rotation | Nouveau champ sur `ssh_keys` (pas encore construit) |
| R6 | Rappel visuel permanent des conteneurs à privilèges élevés | Liste statique, à afficher |
| R7 | Nombre de requêtes `/sql` par période, échantillon des dernières requêtes | Log applicatif existant, filtrage à ajouter |
| R8 | Ancienneté du plus vieux log encore en mémoire (indicateur de la fenêtre de rétention réelle) | `shared/log_buffer.py` (déjà existant) |
| R9 | Recherche de motifs sensibles (mot de passe, token) dans les logs récents | Nouveau, à construire |
| R10 | Version de Mayan déployée vs dernière version stable connue | Sondage manuel ou API Mayan |
| R13 | Liste des dépendances + CVE connues (ex. via `pip-audit`/`safety`) | Nouvel outil à intégrer, pas de service existant |
| R14 | Volume de paquets syslog reçus par période, sources distinctes | `rsyslog-listener` (déjà existant) |

**Nature de cette proposition** : une esquisse pour orienter la
conception, pas un cahier des charges figé — plusieurs lignes
demandent des mécanismes qui n'existent pas encore (log d'accès
inter-services, audit de dépendances). À affiner ensemble au moment
de construire, comme pour le reste du backlog.

## Rattachement aux 4 thèmes ISO/CEI 27001:2022 (Annexe A)

Enrichissement demandé explicitement (2026-09-04) -- recherche
externe faite avant d'écrire quoi que ce soit (voir citations plus
bas). L'Annexe A de la norme (93 mesures depuis la révision du
25 octobre 2022, qui a remplacé les 114 mesures de la version 2013
-- **transition achevée le 31 octobre 2025, les certificats
2013 ne sont plus valides depuis cette date**) organise les mesures
en QUATRE thèmes : Organisationnelles (37), Personnes (8),
Physiques (14), Technologiques (34).

⚠️ Rattachement fait au niveau du THÈME seulement (pas un numéro de
mesure précis pour chaque ligne) -- la recherche menée confirme la
structure en 4 thèmes et quelques mesures NOUVELLES précises
(A.5.7 renseignement sur les menaces, A.5.23 sécurité du cloud,
A.8.11 masquage des données, A.8.28 codage sécurisé), mais pas le
détail exhaustif des 93 mesures -- jamais un numéro inventé faute de
l'avoir vérifié.

| Risque | Thème(s) ISO 27001:2022 | Repère |
|---|---|---|
| R1 (pas de segmentation réseau) | Technologique | sécurité des réseaux |
| R2 (pas d'authentification inter-API) | Technologique | gestion des accès |
| R3 (port SSHFS lié à 0.0.0.0) | Technologique | sécurité des réseaux |
| R4 (`.env` en clair) | Technologique | cryptographie/secrets |
| R5 (clés SSH non chiffrées) | Technologique | cryptographie |
| R6 (conteneur privilégié) | Technologique | sécurité des configurations |
| R7 (filtrage SQL basique) | Technologique | codage sécurisé (proche d'A.8.28, mesure NOUVELLE en 2022) |
| R8 (logs sans rémanence) | Technologique + Organisationnelle | journalisation + gestion des incidents |
| R9 (logs porteurs de données sensibles) | Technologique | proche d'A.8.11 masquage des données (mesure NOUVELLE en 2022) |
| R10 (GED tierce, Mayan) | Organisationnelle | relations fournisseurs |
| R11 (auth. par mot de passe, backlog) | Technologique + Personnes | gestion des accès + sensibilisation |
| R12 (futur SNMP) | Technologique | sécurité des réseaux |
| R13 (dépendances non scannées) | Technologique | gestion des vulnérabilités techniques |
| R14 (rsyslog UDP exposé) | Technologique | sécurité des réseaux |

**Observation issue de ce rattachement** -- la quasi-totalité des
risques déjà notés touche le thème Technologique ; PRESQUE AUCUN ne
couvre les thèmes Personnes ou Organisationnelle (gouvernance,
rôles/responsabilités, sensibilisation, relations fournisseurs au-delà
de R10) -- cohérent avec la nature de ce tableau (risques de
l'infrastructure elle-même), mais signale un angle mort si l'objectif
devient une vision ISO 27001 complète : la charte d'usage du SI
(`charte-usage-si.docx`) et la notice de sensibilisation couvrent en
partie ce manque côté Personnes, aucun document ne couvre pour
l'instant la gouvernance/Organisationnelle (politique de sécurité
formalisée, rôles et responsabilités définis, gestion des
fournisseurs au-delà du seul cas Mayan).

**Sources consultées** (recherche du 2026-09-04, à revérifier
périodiquement comme tout ce qui touche une norme vivante) :
Kertos, DQS Global, ISMS.online -- convergentes sur la structure
93 mesures / 4 thèmes et la date de fin de transition.
