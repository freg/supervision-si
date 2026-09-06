# nebula

Connexion et consultation de l'API Zyxel Nebula (livraison #196,
second "besoin immédiat" de la demande GLPI (#192) : "importer les
données d'un site sous nebula.zyxel.com").

## ⚠️ Deux prérequis BLOQUANTS, à réunir AVANT tout test réel

1. **L'organisation Nebula visée doit avoir la licence Nebula Pro
   Pack.** Confirmé explicitement dans la documentation officielle
   ("Zyxel Nebula OpenAPI only supports PRO mode organizations") et
   sur la page produit ("Ensure your Nebula devices are registered
   under a Nebula Professional Pack licensed organization"). Sans
   Pro Pack, tous les appels échoueront systématiquement, quel que
   soit le code -- `GET /test-connection` (voir plus bas) le
   signale explicitement s'il détecte une organisation sans Pro Pack.
2. **La clé d'API n'est PAS en libre-service.** La documentation
   officielle recommande explicitement de contacter le bureau
   régional Zyxel ou d'ouvrir un dossier support NCC Help Center pour
   en obtenir une ("Since Nebula OpenAPI is still in its early
   stages... it is not yet generally available"). Rien dans ce
   module ne peut contourner cette étape administrative.

Sans ces deux prérequis réunis, ce module ne pourra jamais se
connecter réellement, peu importe la configuration.

## Portée de cette livraison

Couvre la **connexion** et la **consultation** (organisations, sites,
appareils d'un site, clients réseau) -- **PAS ENCORE l'import vers
GLPI**, volontairement laissé pour une étape suivante, une fois la
connexion elle-même validée en conditions réelles par la personne.
Empiler un import non testé sur une connexion non testée aurait
démultiplié le risque sans bénéfice réel avant un premier retour
concret.

## ⚠️ Jamais testé contre une vraie API Nebula

Aucun accès réseau externe dans cet environnement de développement,
et les deux prérequis ci-dessus ne peuvent de toute façon pas être
satisfaits depuis ici. Toute la logique (`nebula_client.py`) est
construite à partir de la spécification OpenAPI OFFICIELLE
(https://zyxelnetworks.github.io/NebulaOpenAPI/, consultée le jour
de cette livraison), mais reste à confirmer contre un vrai compte
une fois les prérequis réunis -- commencer par `GET /test-connection`.

## Architecture

- `nebula_client.py` -- client bas niveau. Authentification par CLÉ
  STATIQUE (`X-ZyxelNebula-API-Key`, en-tête sur CHAQUE appel) --
  contrairement à GLPI (#192), PAS de session à ouvrir/fermer.
  Hiérarchie des ressources : Organisation (`orgId`) → Site
  (`siteId`) → Appareil (`devId`).
- `app.py` -- service Flask (`GET /test-connection`, `GET
  /organizations`, `GET /organizations/<id>/sites`, `GET
  /organizations/<id>/sites/<id>/devices`, `GET
  /sites/<id>/clients`, `/logs`, `/health`).

## Endpoint clé pour un futur import

`GET /organizations/{orgId}/sites/devices` (côté Nebula) renvoie
TOUS les appareils de l'organisation, GROUPÉS PAR SITE : `devId`,
`name`, `mac`, `sn` (numéro de série), `model`, `type`
(AP/SW/GW/FIREWALL/WWAN/SCR/GWH/ACCY), `description`, `tags`...
`sn` et `mac` en font une source directement exploitable pour
alimenter un inventaire GLPI, sur le même principe de dédoublonnage
par numéro de série déjà utilisé côté GLPI (#192) -- mais cette
livraison s'arrête à la CONSULTATION (`devices_for_site`), l'import
lui-même reste à construire dans une étape suivante.

L'API Nebula n'a PAS d'endpoint "appareils d'un site" isolé --
uniquement "appareils de toute l'organisation, groupés par site" --
`devices_for_site` filtre donc CÔTÉ CLIENT, jamais un appel
supplémentaire inutile vers l'API.

## Détail amusant mais réel : une faute de frappe dans l'API elle-même

Les endpoints `.../clients` (v2, AP/GW/SW/site) attendent un champ
nommé **`featrues`** dans leur corps de requête -- PAS `features`.
C'est une faute de frappe RÉELLE dans la documentation officielle
Zyxel elle-même, reproduite TELLE QUELLE dans `nebula_client.py`
(voir le commentaire à cet endroit) -- une version "corrigée" ne
serait simplement pas comprise par l'API.

## Format d'erreur

CONFIRMÉ par la documentation officielle (contrairement à GLPI, #192,
où ce format restait une hypothèse défensive) : chaque réponse, y
compris les 200, a la forme `{"status": ..., "message": ...,
"code": ..., "more_info": {}}`. `_raise_with_detail` reste quand
même défensif sur la forme EXACTE (jamais un accès direct à une clé
qui pourrait manquer), mais le format lui-même est documenté, pas
deviné.

## Utilisation

**1. Réunir les deux prérequis** (voir plus haut) AVANT toute chose.

**2. Configurer** (`.env`, voir `.env.example`) : `NEBULA_API_KEY`
(obtenue via le support Zyxel), `NEBULA_BASE_URL` optionnel (endpoint
de staging si Zyxel en fournit un pour le développement).

**3. Tester la connexion** : `GET /api/nebula/test-connection` (une
fois déployé) -- liste les organisations accessibles, avec un
avertissement explicite si l'une d'elles n'a pas la licence Pro Pack.

**4. Consulter** : `GET /api/nebula/organizations/<orgId>/sites`,
puis `GET /api/nebula/organizations/<orgId>/sites/<siteId>/devices`.

## Statut en ligne des appareils (livraison #349, backlog item 49)

Backlog item 49 -- "l'API Nebula supporte-t-elle uptime/nombre de
clients/charge par borne ?", posé comme l'étape la MOINS coûteuse à
vérifier avant tout développement RF/spectre (items 47/50). Réponse
en partie déjà là : `nebula_client.get_online_status` existait déjà
depuis #196 (jamais branché à une route HTTP jusqu'ici) --

```
GET /api/nebula/sites/<siteId>/online-status?type=AP
```

Renvoie `[{"devId", "currentStatus"}, ...]` -- répond directement à
"les bornes plantent-elles réellement ?" pour chaque appareil du
site. `type` optionnel (AP/SW/GW/FIREWALL/WWAN/SCR/GWH/ACCY, voir doc
officielle) filtre CÔTÉ SERVEUR sur l'API elle-même (contrairement à
`/devices`, qui filtre côté client faute d'endpoint dédié -- ici
l'API Nebula le supporte nativement).

**Nombre de clients connectés** : déjà couvert par `GET /api/nebula/
sites/<siteId>/clients` (existant depuis #196) -- le compte se
dérive simplement de la longueur de la liste renvoyée, jamais un
nouvel endpoint nécessaire pour ça.

**"Charge" par borne** : PAS couvert par ce module tel quel --
`get_online_status`/`devices_for_site` ne semblent exposer aucun
champ de charge CPU/mémoire/débit d'après la spécification OpenAPI
consultée (uniquement statut en ligne + identifiants) -- à confirmer
une fois un accès réel à l'API obtenu, jamais présumé qu'un tel champ
existe sans l'avoir vu dans une vraie réponse.

**Ce qui reste RÉELLEMENT hors de portée** (pas du code, un vrai
prérequis administratif) : licence Nebula Pro Pack + clé API obtenue
via le support Zyxel (voir prérequis en tête de ce document) -- sans
ça, aucun test réel possible contre cette route, quel que soit le
code déjà écrit. Aucune polling périodique/stockage historique
construit non plus -- ceci reste un appel À LA DEMANDE, jamais encore
intégré à un système de collecte régulière (probablement le rôle
futur de netprobe une fois cette étape confirmée fonctionnelle).

## Vérifié réellement

`nebula_client.py` testé via mock des réponses HTTP -- **reconstituées
fidèlement d'après les exemples de la spécification OpenAPI
officielle** (format exact de `list_organizations`, `list_sites`,
`devices_for_site` -- y compris le filtrage côté client sur un site
inexistant, jamais une exception --, et `get_site_clients` AVEC la
vraie faute de frappe `featrues` de l'API, vérifiée explicitement
comme n'étant PAS "corrigée" par erreur). Format d'erreur documenté
testé (`{"status", "message", "code"}`). `app.py` testé de bout en
bout, dont l'avertissement Pro Pack (présent quand une organisation
n'est pas en mode PRO, absent sinon). `GET /sites/<siteId>/
online-status` (#349) testé de bout en bout -- transmission correcte
de `site_id`/`type` (query param -> `device_type`), erreur claire
(502, mentionnant explicitement le prérequis Pro Pack) si
`NEBULA_API_KEY` absent.

**Non vérifié dans cet environnement** : tout ce qui nécessite une
VRAIE API Nebula (connexion, données réelles) -- impossible à tester
ici de toute façon (aucun accès réseau externe, et les deux
prérequis ne peuvent pas être satisfaits depuis ce sandbox). À
tester en PRIORITÉ une fois les prérequis réunis et le service
déployé, en commençant par `/test-connection`.

## Import CSV des exports du portail web (livraison #200)

Demandé explicitement -- "note et évolution nebula : import et
présentation des csv sur le modèle ci-joint". Distinct de l'API
OpenAPI (#196, ci-dessus) : l'export CSV est accessible DIRECTEMENT
depuis le portail web Nebula standard, SANS licence Pro Pack ni clé
support -- complémentaire, pas un remplacement.

**Format réel** (déterminé en inspectant les 3 fichiers fournis par
la personne le jour de cette livraison, jamais deviné) : exports
"Overviews > Sites", "Overviews > Devices" et "Clients" du portail
web. Voir `csv_import.py` pour le détail colonne par colonne.
Encodage UTF-8 avec BOM, toutes les valeurs entre guillemets (y
compris les nombres). "Usage" au format libre ("164.07 MB", "16.47
GB", "0 bytes") -- converti en octets pour permettre un tri/agrégat
cohérent, valeur d'origine conservée en parallèle.

**Stockage** : premier stockage PERSISTANT de ce module (jusqu'ici
purement passe-plat vers l'API Nebula) -- SQLite sur un nouveau
volume dédié (`NEBULA_DATA_DIR`, voir `.env.example`). Chaque import
AJOUTE des lignes, jamais un remplacement en place -- permet une vue
dans le temps (statistiques d'usage, apparition/disparition
d'appareils), pas seulement un miroir de l'état courant.

**API** : `POST /import/sites`, `POST /import/devices`, `POST
/import/clients` (fichier en multipart/form-data, champ `file`).
Consultation : `GET /imported/sites`, `.../devices`, `.../clients`
-- par défaut, le DERNIER import connu par clé naturelle (nom pour
les sites, adresse MAC pour appareils/clients) ; `?history=true`
pour tout l'historique des imports.

**Pas encore fait** :
- **Présentation dans le hub** -- ces routes sont consultables (API
  directe), mais il n'existe TOUJOURS aucune tuile/écran hub pour
  Nebula (backend seul depuis #196, confirmé encore vrai ici) --
  reste à construire.
- **L'agent lui-même** -- la personne le décrit explicitement comme
  "à concevoir" : un agent, packagé en conteneur Docker, déployé sur
  un poste local, qui analyserait le réseau et transmettrait
  régulièrement vers "notre tuile nebula" (donc une fois celle-ci
  construite). Rien de spécifié sur SA méthode d'analyse réseau à ce
  stade (à rapprocher de l'item 20 du backlog, tuile "big-brother" --
  tcpdump/agents de collecte -- le même besoin sous deux angles,
  jamais encore réconcilié explicitement avec la personne). Ce que
  cette livraison prépare pour lui : un format d'ingestion déjà
  fonctionnel (les mêmes routes `/import/*` pourraient recevoir des
  données produites par un futur agent, pourvu qu'il les mette au
  même format CSV, ou qu'une route JSON équivalente soit ajoutée le
  moment venu).

**Vérifié réellement** : `csv_import.py` testé contre les TROIS
VRAIS fichiers fournis (18 appareils, 1 site, 100 clients) -- pas
des données synthétiques. Cas réels de qualité de données gérés :
BOM, valeurs vides réelles (Tags absent sur le pare-feu, Template
vide), "0 bytes" correctement distingué d'un format non reconnu.
Routes testées de bout en bout via de VRAIES requêtes HTTP multipart
avec les fichiers fournis -- import, consultation "dernier état",
ré-import du même fichier (confirmé : le dernier état ne double pas,
reste à 18 appareils), historique complet (confirmé : 36 lignes après
2 imports de 18, rien perdu).

## Interface hub (livraison #228)

Onglet "Nebula" dans le hub (`hub/src/NebulaView.jsx` +
`nebulaClient.js`) -- trois sous-onglets (Sites/Appareils/Clients)
avec import CSV par sélection de fichier, et section dédiée pour
déclencher l'import vers GLPI (#208) avec aperçu (`dry_run`)
systématique avant confirmation. Câblé dans la passerelle (routes
`/api/nebula/` et `/api/glpi/`, déjà en place depuis #196/#192) et
`docker-compose.yml` (`VITE_NEBULA_API_BASE_URL`,
`VITE_GLPI_API_BASE_URL`).

**⚠️ Vue INTÉRIMAIRE** -- le backlog (item 16) note explicitement que
la présentation "définitive" sera LA tuile unifiée de l'item 20
(agent réseau fusionné) -- mais cet agent n'existe pas encore. Cette
vue rend utilisables dès maintenant les imports déjà construits, sans
présumer de la forme finale à venir.

**Voie CSV uniquement** -- la voie API directe (`/test-connection`)
n'est pas câblée dans cette vue, pour ne pas présenter un bouton qui
échouerait systématiquement sans les deux prérequis bloquants
(Pro Pack + clé support Zyxel, jamais réunis dans cet environnement).

**Vérifié réellement** : structure JSX revérifiée. **Un point corrigé
avant même de tester** : la forme exacte de la réponse du pont GLPI
supposée initialement à tort (compteurs `created`/`updated`/`skipped`)
-- vérifiée contre le vrai code (`nebula_import.py`) : ce sont en
réalité des LISTES de messages descriptifs (`created`,
`skipped_existing`, `errors`, `warnings`), jamais des compteurs --
corrigé avant de livrer. Logique de construction d'URL et de calcul
du résumé (comptage par longueur de liste, y compris avec des clés
absentes de la réponse) testée en isolation.

## Validation du type de fichier + annulation d'un import (livraison #235)

**Bug réel signalé par la personne au premier usage** : importer un
export CSV Devices via l'onglet Sites du hub ne provoquait AUCUNE
erreur -- les deux formats ont une colonne "Name" (le nom de
l'appareil devient interprété comme un nom de site), des données
FAUSSES étaient insérées silencieusement.

**Corrigé en deux temps** :
- `csv_import.detect_csv_type()` (nouveau) -- détecte le type réel
  d'un fichier à partir de colonnes VRAIMENT distinctives (vérifiées
  contre les 3 formats réels documentés en tête de ce module) :
  "Device type" n'existe que pour Devices, "Connected to" que pour
  Clients, absence de "MAC address" + présence de "Offline devices"/
  "Template"/"Devices" pour Sites. `_import_csv_route` refuse
  désormais l'import AVANT toute insertion si le fichier ne
  correspond pas au type attendu par l'onglet actif -- message
  actionnable indiquant le bon onglet à utiliser.
- `DELETE /imported/<type>` (nouveau) -- annule un import.
  `?imported_at=X` (le timestamp renvoyé par l'import lui-même)
  cible UN SEUL lot précis -- le cas le plus courant, annuler ce
  qu'on vient d'importer par erreur ; sans paramètre, vide tout
  l'historique de ce type.

Côté hub (`NebulaView.jsx`) : bouton renommé "Importer un CSV des
{type}" (précis par onglet, plus jamais un bouton générique
ambigu), bouton "Annuler cet import" affiché juste après un import
réussi.

**Vérifié réellement** : `detect_csv_type` testé contre les 3
en-têtes RÉELS documentés (pas des suppositions), en particulier
confirmé que l'export Devices n'est JAMAIS confondu avec Sites
malgré la colonne "Name" commune aux deux. Route testée de bout en
bout : import Devices via `/import/sites` REFUSÉ avec 0 ligne
insérée (le scénario exact rencontré), import correct accepté,
annulation ciblée testée (le lot visé disparaît, les autres types
restent intacts), type inconnu rejeté proprement.

## Archivage GED + suppression par sélection (livraison #237)

Demandé explicitement -- "tu as bien ajouté annuler l'import... mais
pas supprimer... une sélection et un bouton, un archivage des
imports (fichiers à rendre visible dans l'espace fichiers du
hub/ged)".

**Archivage** : nouvelle table `nebula_import_batches` (un lot = un
import), et `_archive_csv_to_ged()` qui pousse le fichier CSV
original vers `ged-api` (`POST /documents`, liaison polymorphe
`linked_type="nebula-import"` déjà existante côté GED, #158) --
BEST-EFFORT, jamais bloquant : un échec d'archivage n'empêche jamais
l'import des données (déjà réussi à ce stade), signalé clairement
(`ged_archive_error`) plutôt que masqué.

**Suppression par sélection** : nouvelles routes `GET
/import-batches?type=X` (historique des lots, triés du plus récent
au plus ancien) et `DELETE /import-batches` (corps
`{"batch_ids": [...]}`, plusieurs lots à la fois). Supprime les
LIGNES importées mais garde VOLONTAIREMENT le fichier archivé dans
la GED -- l'archivage sert justement à conserver une trace même
après suppression des données parsées.

Côté hub (`NebulaView.jsx`) : section "Historique des imports"
dépliable, tableau avec case à cocher par lot, statut d'archivage
GED visible (✅/⚠️), bouton "Supprimer la sélection".
`GED_API_INTERNAL_URL` ajouté à `docker-compose.yml`.

**Un vrai piège trouvé en testant** : `ORDER BY imported_at DESC`
seul ne distingue pas deux imports survenus dans la même SECONDE
(résolution de `now_iso()`) -- l'ordre devenait arbitraire dans ce
cas. Corrigé avec `id DESC` en critère secondaire, qui reflète
toujours l'ordre réel d'insertion.

**Vérifié réellement** : archivage GED réussi ET en échec testés
(jamais bloquant pour l'import lui-même dans les deux cas), liaison
polymorphe vérifiée (bon `linked_type`/`linked_id`), suppression par
sélection testée (lot ciblé disparaît avec ses lignes, les autres
lots restent intacts, lot inexistant signalé sans planter), tri
stable confirmé même avec deux imports dans la même seconde.

## Correctif réel : crash React sur l'aperçu GLPI (livraison #288)

Signalé par la personne en plein test réel : le bouton d'aperçu
("dry-run") du pont Nebula → GLPI menait à un écran vide, avec dans
la console "Objects are not valid as a React child (found: object
with keys {detail, itemtype, key, name})".

Cause : `NebulaView.jsx` intègre depuis #228 un raccourci de prévisualisation
vers GLPI (`glpiPreview.created.map(...)`), construit à une époque où
`created` était toujours une liste de CHAÎNES. La livraison #269
(ajout de cases à cocher côté `GlpiInventoryView.jsx`) a changé la
forme de `created` EN MODE APERÇU UNIQUEMENT vers des objets
`{key, name, itemtype, detail}` -- `GlpiInventoryView.jsx` a été
adapté à cette nouvelle forme à ce moment-là, mais `NebulaView.jsx`,
qui consomme la MÊME route, ne l'a jamais été -- un oubli de
propagation du changement à tous les consommateurs existants.

Corrigé : `NebulaView.jsx` gère désormais les deux formes (chaîne en
import réel, objet en aperçu) -- jamais un objet rendu directement,
toujours reformaté en texte lisible. `errors`/`skipped_existing`
restent des chaînes dans les deux modes (vérifié côté
`glpi/api/network_agent_import.py`), aucun changement nécessaire
pour ces deux-là.

**Vérifié réellement** : logique de formatage testée en isolation
pour les deux formes (chaîne, objet avec/sans détail) -- jamais un
objet renvoyé directement comme enfant React. `GlpiInventoryView.jsx`
revérifié en parallèle -- déjà correct depuis #269, pas de correctif
nécessaire là.

**Leçon retenue** : changer la forme d'une réponse API partagée par
PLUSIEURS vues frontend exige de vérifier TOUS les consommateurs
existants, pas seulement celui visé par le changement -- une
recherche `grep` sur le nom du champ concerné (`created`) aurait
trouvé les deux dès #269.

## Branchement rights-api (livraison #314)

Suite de l'item 38 du backlog. Ce module ne configure JAMAIS Nebula
lui-même (connexion et consultation seulement) -- les routes
d'écriture ici touchent UNIQUEMENT le cache LOCAL (import de CSV
exportés depuis Nebula, suppression de lots importés). Un import
falsifié ou une suppression pourrait quand même induire en erreur.

Gardé sur les 3 routes d'import CSV (mutualisées via
`_import_csv_route`, `groups` lu depuis `request.form` -- multipart,
jamais un corps JSON) et les 2 routes de suppression (`groups` lu
depuis le corps JSON) -- jamais la consultation.

OPT-IN via `NEBULA_RIGHTS_API_URL`, vide par défaut, comportement
inchangé tant qu'elle n'est pas configurée.

**Vérifié réellement** : comportement opt-in par défaut confirmé,
FAIL CLOSED si `rights-api` injoignable, 403 confirmé sur les 5
routes gardées (multipart et JSON) avec un groupe non autorisé,
lecture confirmée non affectée. Non-régression complète reconfirmée.
