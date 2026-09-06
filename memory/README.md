# Mémoire -- rémanence du tampon de logs Memcached (livraison #259)

Backlog item 32, demandé explicitement : "api/service de rémanence
du memcached... un outil à faible impact et simplement supervisé qui
va récupérer les kv du memcached régulièrement et les stocke en
base... avec un mécanisme de repopulation du memcached et avec un
garbage collector ou un timeout de remise en ligne, avec une
interface d'accès et de calcul pour naviguer dans les historiques et
calculer dessus... à relier aux autres données" -- puis explicitement
"en faire une tuile pas simplement un outil".

## Portée VOLONTAIREMENT SCOPÉE

**PAS un "tout Memcached" générique** -- raison technique réelle,
vérifiée avant de coder : Memcached N'OFFRE PAS de "lister les clés
existantes" (limitation native, contrairement à Redis). Sans une
liste de clés connue à l'avance, "récupérer les kv du memcached" de
façon générique n'est tout simplement pas réalisable.

Ce module se scope donc au **tampon de logs partagé**
(`shared/log_buffer.py`, #145), la SEULE utilisation de Memcached
dans ce projet dont les clés sont énumérables de façon fiable, via
DEUX sources combinées :
1. **Services internes CONNUS** (`KNOWN_SERVICE_NAMES` dans `app.py`
   -- 28 services recensés directement dans le code de chaque
   backend, `grep SERVICE_NAME = "..."` sur tout le projet). Liste
   FIXE, à tenir à jour manuellement si un nouveau service rejoint
   le projet (voir "Maintenance" plus bas).
2. **Sources `/push-log` externes** -- lues via le registre déjà
   existant `pushed_log_sources` (construit en #145 pour exactement
   cette même raison), jamais devinées.

**Le cache de requêtes court de `zenoss-api`** (`ZENOSS_CACHE_TTL`,
60s par défaut) est DÉLIBÉRÉMENT hors de portée -- recalculable à la
demande depuis la vraie source, fondamentalement différent en nature
du tampon de logs (historique diagnostique).

## Les quatre volets demandés

1. **Collecte périodique** -- thread de fond, un passage toutes les
   `MEMORY_COLLECTION_INTERVAL_SECONDS` (5 min par défaut, "faible
   impact" -- jamais chaque seconde). Lit le tampon de CHAQUE service
   connu, persiste SEULEMENT les entrées plus récentes que le dernier
   repère de collecte connu pour ce service (évite de retraiter
   jusqu'à 200 entrées à chaque passage) -- la contrainte UNIQUE en
   base reste un filet de sécurité, jamais le mécanisme principal de
   dédoublonnage.
2. **Repopulation** -- si le tampon Memcached d'un service est VIDE
   (cas le plus probable : Memcached vient de redémarrer, "perdu
   seulement si Memcached LUI-MÊME redémarre" selon
   `shared/log_buffer.py`) ALORS QUE de l'historique existe déjà en
   base, réinjecte les `MEMORY_REPOPULATE_COUNT` entrées les plus
   récentes (50 par défaut) -- évite qu'un gestionnaire de logs
   affiche un tampon vide juste après un redémarrage de Memcached.
3. **Rétention ("garbage collector")** -- purge des entrées
   persistées plus vieilles que `MEMORY_RETENTION_DAYS` (30 jours par
   défaut), même motif que `network-agent`/#251
   (`purge_old_snapshots`). Compare sur la date de COLLECTE (pas
   d'émission) -- une entrée ancienne mais collectée récemment (après
   une longue interruption) reste conservée le temps de rétention
   plein.
4. **Interface d'accès et de calcul** -- tuile hub "Mémoire" : tableau
   de statistiques PAR SERVICE (le "calcul" demandé -- total et
   répartition par niveau, service le plus bavard en tête) +
   navigateur d'historique filtrable (service/niveau).

## Maintenance -- ajouter un nouveau service

Si un nouveau backend rejoint ce projet avec son propre
`SERVICE_NAME`, l'ajouter manuellement à `KNOWN_SERVICE_NAMES` dans
`memory/api/app.py` -- sinon son tampon de logs ne sera jamais
collecté (Memcached ne peut pas être interrogé pour "quels services
existent", voir portée ci-dessus).

⚠️ **Dérive réelle trouvée et corrigée en #351** -- exactement le
piège décrit ci-dessus, matérialisé en pratique : 8 services ajoutés
au projet après cette livraison (#259) n'avaient jamais rejoint
`KNOWN_SERVICE_NAMES`, leurs logs silencieusement jamais archivés
(classifier-api, vigilance-api, tasks-api, rights-api, netprobe-api,
relations-api, vault-admin-api, pixel-grid-bridge). Trouvé en
recoupant systématiquement (script Python, pas un comptage visuel)
la liste réelle des services de `docker-compose.yml` contre
`KNOWN_SERVICE_NAMES` -- réflexe à reproduire périodiquement plutôt
que d'attendre qu'on s'en aperçoive par accident. Certains des 8
n'avaient même AUCUN câblage au tampon partagé lui-même (pas
seulement absents de cette liste) -- câblage complet ajouté à chacun
en même temps.

## Vérifié réellement

Testé en profondeur avec le stub Memcached fonctionnel déjà présent
dans cet environnement (état partagé en mémoire, simulant un vrai
serveur) : dédoublonnage confirmé sur plusieurs passages de collecte
successifs (0 nouvelle entrée sur un tampon inchangé, seules les
entrées réellement nouvelles insérées sur un tampon qui avance),
calcul de statistiques par service et par niveau confirmé exact,
rétention testée (purge les entrées, CONSERVE le repère de collecte
pour éviter de tout re-collecter inutilement).

**Repopulation testée avec un VRAI aller-retour Memcached** -- clé
supprimée (simulation de redémarrage), confirmé le tampon vide,
repopulation déclenchée, confirmé le tampon reconstruit dans le bon
ordre chronologique depuis l'historique persisté ; et confirmé
qu'AUCUNE repopulation n'a lieu quand le tampon n'est pas vide
(jamais un écrasement de données fraîches par de l'historique).

Dockerfile vérifié avec le script de contrôle systématique développé
en #252 -- aucun fichier manquant dès la première livraison de ce
module. Structure JSX complète revérifiée.

## Fusion avec prefs-api/log_archiver.py (livraison #353)

Demandé explicitement par la personne après la découverte documentée
en #351-352 : deux systèmes d'archivage persistant tournaient en
parallèle sur le MÊME tampon Memcached source --
`prefs-api/log_archiver.py` (livraison #198, antérieur) et ce module
(#259, plus complet). **`log_archiver.py` SUPPRIMÉ** (fichier retiré,
route `/persisted-logs` retirée de `prefs-api/app.py`, thread
d'archivage arrêté, `Dockerfile` de prefs-api nettoyé -- ligne `COPY
log_archiver.py` qui aurait cassé le build sinon, trouvée et corrigée
avant vérification finale) -- `memory-api` reste désormais la SEULE
source d'archivage persistant pour ce projet.

**Un seul écart de fonctionnalité trouvé avant suppression**, comblé
AVANT de retirer l'ancien système : `log_archiver.query_persisted_logs`
filtrait sur `since`/`until` (timestamps Unix, colonne `timestamp` =
horodatage RÉEL du log), alors que `list_entries`/
`compute_stats_by_service` ici ne filtraient QUE sur `since_iso`
(chaîne ISO, colonne `collected_at` = quand CE service a archivé
l'entrée -- sémantique DIFFÉRENTE, pas juste un format différent).
Redessiné : `since`/`until` (timestamps Unix, filtrant sur
`entry_timestamp`, colonne déjà INDEXÉE) sur les deux fonctions,
reprenant exactement la sémantique de l'ancien système -- changement
sûr, `since_iso` n'était consommé par AUCUNE interface avant cette
fusion (aucun appelant existant à préserver, confirmé en cherchant
dans tout le hub avant de toucher à cette signature).

Vérifié réellement : `list_entries`/`compute_stats_by_service`
retestés en profondeur après la refonte (since seul, until seul,
fenêtre combinée, filtre service+since, stats since, sans filtre --
6 cas), routes HTTP `/entries`/`/stats` retestées avec les nouveaux
paramètres. `prefs-api` retesté après suppression complète de
`log_archiver.py` : `/logs` (tampon partagé, jamais touché) toujours
fonctionnel, `/persisted-logs` correctement absent (404), `/push-log`
non affecté.

**❌ ERREUR CORRIGÉE (2026-09-05)** : ce paragraphe affirmait à tort
qu'aucune interface hub ne consultait l'historique persisté -- en
vérifiant SEULEMENT `LogsManagerView.jsx` (qui, lui, n'interroge
effectivement que le tampon Memcached en direct) sans vérifier
`MemoryView.jsx`, qui appelle déjà `/stats`/`/services`/`/entries`
depuis la création même de cette tuile (#259) -- voir plus haut dans
ce même document ("Les quatre volets demandés"). Rien à construire
sur ce point, l'interface existe et fonctionne déjà.

## Reste à faire

- "À relier aux autres données" -- le nom de service est affiché tel
  quel (cohérent avec les autres tuiles de ce hub), mais aucune
  navigation cliquable directe vers la tuile correspondante n'a été
  construite -- à ajouter si utile après un premier usage réel.
- Le "calcul" reste simple (comptages) -- des agrégations dans le
  temps (tendances par jour/semaine) pourraient être ajoutées si
  besoin, une fois l'historique suffisamment garni pour que ça ait
  du sens.
- `KNOWN_SERVICE_NAMES` est une liste statique -- jamais synchronisée
  automatiquement si un service est retiré du projet (resterait
  interrogé sans jamais avoir de tampon, sans conséquence négative
  mais pas idéal non plus).
