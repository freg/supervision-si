# api (service central de centralisation)

Point d'écriture unique (Memcached + fichiers) et point de découverte
des fichiers du dossier `data` -- voir le docstring en tête de
`api/app.py` pour le détail complet des trois façons pour une source
d'exister (`POST /ingest/<source>`, dépôt manuel + confirmation,
sélection ad hoc "versée" via `POST /sources/from-selection`).

Pas de README dédié jusqu'ici -- l'un des services les plus anciens
du projet, apparemment jamais couvert par la convention "toujours un
README par module" adoptée plus tard. Ce fichier ne couvre pour
l'instant que le branchement rights-api ; le reste du fonctionnement
reste documenté uniquement dans les docstrings d'`api/app.py`.

## Branchement rights-api (livraison #320)

Suite de l'item 38 du backlog.

**DÉCOUVERTE CRITIQUE avant d'agir** : `POST /ingest/<source>` (le
"chemin de confiance" documenté en tête de fichier) est appelé PAR
D'AUTRES SERVICES en conteneur-à-conteneur -- `imap-client-api`
(résultats d'interprétation), `pixel-grid/bridge/bridge.py`,
`pipeline/main.py`, `connectors/zenoss_legacy/zenoss_connector.py`.
AUCUN de ces appelants n'a de contexte utilisateur/groupes Keycloak
à transmettre -- ce sont des pipelines automatisés, pas des actions
déclenchées par une personne connectée. Le garder aurait cassé ces
flux dès l'activation de `rights-api` -- **`/ingest` reste
DÉLIBÉRÉMENT et DÉFINITIVEMENT jamais gardé**, indépendamment de
toute décision future sur les autres routes de ce fichier.

Gardé UNIQUEMENT sur les 4 routes de gestion des sources
(`from-selection`, `register`, `delete`, `restore`) -- confirmé
qu'aucun autre service Python ni aucun composant du hub ne les
appelle actuellement (même situation que `revoke_collection_access`/
`reset_user` en #308) -- pas un risque exploité aujourd'hui via
l'interface, mais un vrai trou pour un appel API direct.

OPT-IN via `CENTRAL_API_RIGHTS_API_URL`, vide par défaut,
comportement inchangé tant qu'elle n'est pas configurée.

**Vérifié réellement** : comportement opt-in par défaut confirmé,
FAIL CLOSED si `rights-api` injoignable, 403 confirmé sur les 4
routes gardées avec un groupe non autorisé, `/ingest` confirmé
TOUJOURS fonctionnel -- y compris quand `rights-api` est actif ET
injoignable simultanément (double vérification explicite, étant
donné les conséquences réelles d'une régression sur cette route).
Non-régression complète reconfirmée.
