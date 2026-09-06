# Design partagé — thème clair/foncé + préférences

`shared/theme.css` et `shared/preferences.js` — copiés (Dockerfile
`COPY`) dans chacun des 4 fronts au moment du build, pas un paquet npm
partagé (pas d'outillage monorepo dans ce projet, volontairement
gardé simple). Contextes de build changés en conséquence dans
`docker-compose.yml` (`context: .` + `dockerfile: <app>/Dockerfile`,
plutôt que le raccourci `build: ./<app>`) — nécessaire pour que chaque
Dockerfile puisse `COPY shared/...` depuis la racine du dépôt.

## Deux familles de jetons de couleur, jamais mélangées

**Hub / portail tickets / DBA** : ces trois fronts partageaient déjà
quasiment les mêmes variables avant cette unification (`--bg`,
`--panel`, `--border`, `--text`, `--muted`, `--accent`, `--danger`,
`--ok`) — convergence à faible risque vers un socle commun unique
(`shared/theme.css`). Chaque front a eu son propre bloc `:root {...}`
**retiré** de son CSS local (`hub.css`, `portal.css`, `dba.css`) pour
laisser `theme.css` en être l'unique source — sinon collision entre
deux définitions de la même variable.

**Supervision SI (`frontend/`)** : langage de conception délibérément
différent (tableau de bord dense, sombre par défaut, police IBM Plex)
— décision prise de lui donner sa **propre** paire clair/foncé dans sa
**propre** famille de variables (`--color-bg`, `--color-panel`...)
plutôt que de le forcer dans le moule des 3 autres (risque réel de
casser des styles fins non audités un par un dans un fichier CSS de
plus de 5000 lignes). Les jetons de mise en page (`--col-left-width`)
et de typographie (`--font-mono`) restent définis une seule fois dans
`frontend/src/index.css` — ils ne sont pas liés au thème, jamais
dupliqués dans `theme.css`.

Application : `document.documentElement.dataset.theme = "light"|"dark"`
active le bloc `:root[data-theme="..."]` correspondant. Sans attribut
posé (avant que la préférence soit chargée), c'est le bloc `:root` de
base qui s'applique — choisi pour correspondre à ce que chaque front
affichait déjà **avant** cette unification (clair pour les 3 premiers,
sombre pour Supervision SI), pour ne jamais surprendre quelqu'un avec
un thème différent au tout premier chargement.

## Préférences : deux modes, selon ce que chaque front sait de son utilisateur

Décidé avec la personne : **liées au compte** pour hub et portail
tickets (les deux seuls fronts qui connaissent une identité Keycloak
aujourd'hui), **locales au navigateur** pour DBA et Supervision SI
(pas d'authentification aujourd'hui, décidé plutôt que d'en ajouter
juste pour ce besoin cosmétique).

- `createAccountThemeStore({ apiBase })` — charge/persiste via le
  nouveau service `prefs-api` (`GET`/`PUT /preferences?user=<login>`).
  `load(username)`/`set(theme, username)` prennent l'identité en
  paramètre explicite plutôt que figée au constructeur : elle n'est
  connue qu'APRÈS authentification.
- `createLocalThemeStore()` — `localStorage`, propre à ce navigateur,
  clé `supervision-si:theme`.

Les deux exposent la **même interface** (`get()`, `set()`, `onChange()`)
— le bouton de bascule (dupliqué par front, volontairement simple,
🌙/☀️ dans chaque en-tête) n'a jamais besoin de savoir lequel des deux
modes est actif.

## `prefs-api` — nouveau service

Un blob JSON par utilisateur (`login`), pensé dès le départ pour
accueillir d'autres préférences que le thème plus tard (densité
d'affichage, langue...) sans changement de schéma — un `PUT` partiel
ne renseignant que `theme` ne détruit jamais une autre clé déjà
enregistrée (fusion superficielle, testée explicitement). `GET` sur un
utilisateur jamais vu renvoie les valeurs par défaut avec un `200`,
jamais un `404` — l'absence de préférences enregistrées est le cas
normal (première visite), pas une erreur.

Comme le reste du projet, cette API ne vérifie aucun jeton — le
`login` transmis est celui déjà connu du front appelant
(`profile.preferred_username` via Keycloak), même posture de confiance
que partout ailleurs.

`PREFS_DATA_DIR` (`.env`, optionnel) : même logique que
`TICKETS_DATA_DIR`/`DBA_DATA_DIR` — sort `prefs.db` de l'arborescence
du projet, à l'abri d'un déploiement qui supprime puis réextrait tout.

## Vérifié réellement

- **21 tests Node** sur `shared/preferences.js` (DOM/localStorage/fetch
  simulés) : les deux modes, notification des abonnés, valeurs
  invalides/corrompues jamais fatales, API injoignable jamais fatale.
- **12 tests Python** sur `prefs-api` : isolation stricte entre
  utilisateurs, fusion superficielle sur `PUT` partiel, jamais de 404
  sur un nouvel utilisateur, réécriture ultérieure fonctionnelle.
- Syntaxe validée (`tsc --noEmit`) sur les 4 fronts après câblage,
  YAML `docker-compose.yml` validé avec les nouveaux contextes de
  build, générateur `tls-proxy` revérifié.
- **Non vérifiable dans cet environnement de développement** : le
  rendu visuel réel des deux thèmes (pas de navigateur ici) — la
  logique est testée, l'apparence reste à confirmer par la personne
  au premier vrai test.

## Chantiers pas commencés

- Le reste de l'"homogénéisation du design" au sens large (espacements,
  typographie des composants, gabarits de formulaires) — cette session
  a posé la fondation (couleurs partagées + thème clair/foncé
  fonctionnel), pas encore une passe complète composant par composant
  sur les 4 fronts.
- Aucune autre préférence que le thème n'est encore exposée dans
  l'interface (le mécanisme le permet, rien ne l'utilise encore).

## Numéro de version affiché — `VERSION.json`, `version_endpoint.py`

Demandé après une confusion réelle, deux fois de suite : la personne
ne savait plus si le front/l'API en face d'elle reflétait bien sa
dernière livraison. `scripts/run.sh` génère `shared/VERSION.json` à
chaque lancement, copié comme les autres fichiers partagés.

**Hash du CONTENU réel des fichiers, jamais un horodatage brut** —
retour réel corrigé en cours de route : un simple horodatage change à
chaque `--build`, même sur une version strictement inchangée (habitude
de la personne : toujours reconstruire par prudence). Le hash, lui,
reste identique tant que rien n'a changé, quel que soit le nombre de
rebuilds — c'est LE test qui compte le plus ici (vérifié explicitement :
stable sans changement, différent avec un vrai changement, insensible
aux dossiers `data/` runtime exclus du calcul).

**Affiché** : badge discret en bas à droite, **même motif dans les 6
fronts** (hub, portail tickets, DBA, coffre-fort, Supervision SI,
gestion OpenLDAP) pour toujours savoir où regarder peu importe
l'application ouverte.

**Interrogeable** : route `/version` sur les 6 API les plus actives
cette session (`api`, `tickets-api`, `dba-api`, `vault-api`,
`vault-admin-api`, `prefs-api`) — pas encore sur les intégrations en
lecture seule jamais retouchées (IPAM, Zenoss, Optick, OwnCloud,
Cacti, TTS-GU, recherche) — extensible pareil plus tard si voulu, le
motif (`shared/version_endpoint.py`, une ligne d'import + une ligne
d'enregistrement) est mécanique.

### Numéro de livraison incrémental — `shared/DELIVERY_NUMBER`

Demandé explicitement, en complément du hash de contenu ci-dessus :
un hash ne permet pas de voir d'un coup d'œil "est-ce plus récent que
ce que j'ai testé avant ?" (deux hashes n'ont aucun ordre visuel
évident) -- confusion réelle rencontrée en conditions réelles
("version -1" testée sans certitude sur ce que ça désignait
précisément).

**`shared/DELIVERY_NUMBER`** : un simple fichier texte contenant un
nombre, committé dans le dépôt -- **jamais recalculé
automatiquement**, contrairement au hash de contenu (qui est une pure
fonction de l'état des fichiers). Incrémenté manuellement à chaque
livraison, par la personne qui livre -- un compteur, pas une mesure.
Numérotation démarrée à 105 pour rester dans la continuité de
l'historique du projet (104 entrées déjà dans `CHANGELOG.md` à ce
moment-là), plutôt que de repartir de 1 pour un projet déjà mature.

`scripts/run.sh` le lit tel quel (jamais ne le modifie) et l'inclut
dans `VERSION.json` sous la clé `delivery_number` -- absent (fichier
manquant, déploiement antérieur à ce mécanisme) : `"?"` explicite,
jamais une erreur. Badge affiché mis à jour en conséquence : `#105`
plutôt que `v.{hash}` comme texte principal -- le hash de contenu
reste disponible dans l'info-bulle pour une vérification précise si
besoin, mais le numéro incrémental est ce qui se compare le plus
facilement d'un coup d'œil.

**Bug réel rencontré et corrigé** : l'import de `version_endpoint`
était d'abord obligatoire — cassait silencieusement tout autre
harnais de test important `app.py` directement sans passer par le
build Docker complet (où ce fichier partagé n'existe pas encore).
Rendu défensif (`try/except ImportError`) : `/version` répond 404
proprement si le fichier est absent, le reste de l'API continue de
fonctionner normalement — jamais un import cassant tout le module.

**Vérifié réellement** : 3 tests bash sur la stabilité du hash
(scripts/run.sh), 8 tests sur `version_endpoint.py` (absent, présent,
JSON invalide), 18 tests d'intégration sur les 6 backends avec les
fichiers présents, **18 tests supplémentaires sur le cas dégradé**
(sans les fichiers — celui qui a réellement cassé quelque chose),
syntaxe validée sur les 5 fronts (`tsc`) et les 6 backends
(`py_compile`).

## `safe_json.py` -- erreurs systématiquement explicites (livraison #287)

Demandé explicitement : "rend systématiquement les erreurs plus
explicites, ça doit être le comportement général des remontées
d'erreur". Généralisé depuis un correctif réel (#286,
`glpi/api/glpi_client.py`) : un appel HTTP qui renvoie un code 2xx
mais un corps NON-JSON (page HTML d'un proxy, panne intermédiaire,
mauvaise URL, service tiers indisponible derrière un load-balancer...)
plante avec une JSONDecodeError/ValueError brute et inexploitable dès
que le code appelant fait `resp.json()` sans filet -- même après
avoir déjà vérifié le code HTTP lui-même.

`safe_json(resp, context)` -- renvoie `resp.json()`, ou lève une
RuntimeError avec un aperçu du VRAI corps de réponse (tronqué à 300
caractères) au lieu d'un traceback Python brut. Pensé pour les
appels INTERNES (service à service) où une RuntimeError générique
suffit -- les clients de systèmes TIERS (`glpi_client.py`,
`mayan_client.py`, `nebula_client.py`, `google_oauth.py`,
`schema_client.py`) gardent chacun leur propre variante locale
(`_safe_json`), liée à leur classe d'erreur spécifique
(`GlpiError`, `MayanError`, `NebulaError`...) -- jamais unifiée de
force avec ce module partagé, pour ne pas perdre le typage
d'erreur déjà en place.

**Audit rétroactif mené sur les 16 fichiers de ce projet appelant
`.json()` sur une réponse HTTP** -- la majorité (11) était déjà
protégée par un `except ValueError` existant (bonne discipline déjà
en place). 5 vrais trous trouvés et corrigés : `glpi_client.py`
(#286, le déclencheur), `mayan_client.py`, `nebula_client.py`,
`zenoss_connector.py`, `google_oauth.py`, `schema_client.py`,
`architecture/api/app.py` (localisation Zenoss), `glpi/api/app.py`
(enrichissement classifier best-effort), `pipeline/main.py` (isolé
du chemin de succès, pour qu'un corps non-JSON ne fasse jamais
remonter un push HTTP réussi comme un échec), `tickets/api/app.py`
(appels admin Keycloak).

**Vérifié réellement** : chaque correctif testé avec une VRAIE
simulation de réponse 2xx + corps non-JSON, confirmant le message
d'erreur détaillé ET la non-régression du cas de succès. Le chemin
volontairement silencieux de `schema_client.py`
(`fetch_full_schema`, échantillonnage de lignes) vérifié pour rester
silencieux même sur une erreur JSON désormais couverte -- pas
remplacé par une exception qui aurait contredit son intention
documentée.

## Couverture complète de `/version` (livraison #298)

Suggestion de la personne ("les modules doivent pouvoir être
interrogé et donner leur version de déploiement... et de code") --
vérification a révélé que le mécanisme `version_endpoint.py`
existait déjà depuis longtemps, mais que **8 services** n'étaient
jamais câblés dessus : `owncloud-api`, `pixel-grid-api`, `ipam-api`,
`cacti-api`, `geo-import-api`, `tts-gu-api`, `optick-api`,
`zenoss-api`. Corrigé pour les 8 -- import défensif +
`register_version_route(app, "...")` dans `app.py`, ET les deux
lignes `COPY shared/version_endpoint.py .` / `COPY shared/VERSION.json .`
manquantes dans chaque `Dockerfile` (sans elles, le câblage Python
aurait échoué au démarrage réel, faute du fichier présent dans
l'image).

**Vérifié réellement** : les 8 modules s'importent sans erreur,
`/version` testé directement sur 2 d'entre eux (`cacti-api`,
`zenoss-api`), les 8 `Dockerfile` vérifiés systématiquement pour la
présence des deux nouvelles lignes `COPY`.

Couverture désormais complète -- tous les services `*/api/app.py` et
`*/admin-api/app.py` de ce projet exposent `/version`.
