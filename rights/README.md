# Droits (livraison #283)

Demandé explicitement, en complément d'une question sur l'absence
des fichiers du hub dans la GED : "une gestion de droit incluant la
visibilité en listing doit être mise en place" + "un nouveau groupe
admin_hub donnera les tous les droits à ses membres et notamment
celui de gérer les droits" + "la gestion des droits devient une
tuile et impacte toutes les api".

## Périmètre de CETTE livraison

Les points 1-3 des spécifications sont livrés : la fondation
(service central de droits), le groupe `admin_hub`, la tuile de
gestion. Le point 4 ("impacte toutes les API") reste un chantier à
poursuivre progressivement -- brancher les ~40 autres services de ce
projet sur `rights-api` un par un, testé à chaque fois, jamais fait
d'un coup (risque réel de régression si bâclé sur autant de services
simultanément). Le point 5 (ENT en "super tuile" avec sous-tuiles
calendrier partagé/webmail/GED/relations) n'est pas encore entamé.

## Architecture

**`rights-api`** -- service central, ne stocke JAMAIS de secret ni
le contenu d'un fichier, uniquement des références (type de ressource
+ identifiant) et des octrois (quel groupe Keycloak peut faire quelle
action sur quelle ressource).

**Court-circuit `admin_hub`** -- dans `store.has_permission()` et
`store.filter_visible()`, TOUJOURS vrai avant toute requête SQL,
jamais contournable par une ligne de permission manquante ou mal
octroyée. Gérer les droits N'EST PAS déclaré comme une permission
séparée -- c'est déjà couvert par le même court-circuit (gérer les
droits est une action sur la ressource "rights", inutile de la
déclarer explicitement).

**Refus par défaut** -- absence d'octroi = refus, jamais l'inverse.
Un octroi PRÉCIS (`resource_id` défini) ne s'applique qu'à cette
ressource ; un octroi LARGE (`resource_id` NULL) s'applique à tout le
type. Les actions sont cloisonnées (`view` n'implique jamais `manage`).

**Modèle de confiance** -- ce service reçoit la liste des GROUPES de
l'appelant directement dans le corps de la requête, jamais un jeton à
décoder lui-même -- même motif que le reste de ce projet (services
internes qui se font confiance sur le réseau Docker, derrière
Keycloak/tls-proxy en frontal). Le hub, authentifié via OIDC,
transmet les groupes déjà présents dans le jeton de l'utilisateur
(mapper `groups` déjà existant côté client `supervision-hub`, jamais
utilisé pour du contrôle d'accès avant cette livraison -- seulement
un affichage de débogage).

## Inventaire de fichiers (`file_inventory.py`)

`WATCHED_PATHS` -- liste OUVERTE, PAS prétendument exhaustive du
premier coup (impossible à garantir sans avoir audité les ~40
services de ce projet un par un, jamais fait ici). Point de départ :
`.env`, imports/sauvegardes Keycloak, clés SSH, certificats PKI,
configuration nginx générée -- à ÉTENDRE au fil de l'eau.

**Règle absolue, vérifiée explicitement par test** : ce module ne LIT
JAMAIS le contenu d'un fichier -- seulement chemin, taille, date de
modification. Un fichier "secret" est listé comme EXISTANT, jamais
son contenu ni un extrait.

Un chemin surveillé mais ABSENT est quand même signalé (`exists:
false`), jamais omis silencieusement -- demandé explicitement ("TOUT
fichier... doit être listé").

## Tuile hub

`RightsView.jsx` -- deux onglets (Fichiers / Permissions), affichée
UNIQUEMENT si `admin_hub` est présent dans les groupes de
l'utilisateur connecté (`App.jsx`, `groups.includes("admin_hub")`).
⚠️ Ceci est un confort d'AFFICHAGE, jamais LA sécurité -- toute action
de gestion (octroyer/révoquer) est de toute façon revérifiée côté
`rights-api` lui-même ; masquer la tuile n'empêcherait pas un appel
direct à l'API sans le groupe, qui serait refusé (403) par le
service, pas par l'absence d'un bouton.

Liste de groupes proposée dans le formulaire d'octroi -- STATIQUE
(reprise de `keycloak/realm-template.json`), PAS récupérée
dynamiquement depuis Keycloak (hors périmètre de cette livraison) --
à garder synchronisée manuellement si de nouveaux groupes sont créés.

## Vérifié réellement

Cœur du système de sécurité testé en profondeur (18 assertions,
store.py) : court-circuit admin_hub, refus par défaut, octroi
précis vs large, cloisonnement des actions, révocation. Scanner de
fichiers testé séparément avec un VRAI contenu de clé privée
factice, confirmant explicitement qu'il ne fuit jamais dans le
résultat. Toutes les routes testées de bout en bout (18 assertions
supplémentaires) : octroi/révocation refusés sans admin_hub,
`/files` filtré par visibilité, aucun contenu de fichier exposé via
l'API. Logique de visibilité de la tuile testée en isolation.
Structure JSX revérifiée.

## Reste à faire

- Brancher progressivement les autres API du projet sur ce service
  (point 4 des spécifications) -- un chantier à part entière, jamais
  fait d'un coup.
- Récupération dynamique des groupes Keycloak (au lieu de la liste
  statique `KNOWN_GROUPS`).
- ENT en "super tuile" avec sous-tuiles (calendrier partagé, webmail
  à définir, GED, relations événement-utilisateur-document-message-
  ticket) -- point 5 des spécifications, pas commencé.
- `WATCHED_PATHS` à étendre au fil de l'eau -- pas encore audité
  service par service.
