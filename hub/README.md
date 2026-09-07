# Hub SI (portail d'accès)

Portail d'entrée séparé (port `SUPERVISION_HUB_PORT=6174`, le trou
resté dans la numérotation entre le frontend interne — 6173 — et le
portail tickets — 6175 — comblé maintenant). Connexion Keycloak/LDAP
obligatoire, puis une carte par front du projet.

## Pourquoi ce nouveau front plutôt qu'un onglet de plus

La personne a explicitement demandé "un nouveau portail général pour
TOUT le projet", distinct du portail tickets — pas une extension du
portail tickets lui-même (dont le chantier Keycloak reste par
ailleurs en pause, voir `tickets/README.md`). Un front séparé plutôt
qu'un ajout à l'un des deux existants, parce qu'aucun des deux n'a
vocation à être "la porte d'entrée de l'autre" — ni Supervision SI ni
le portail tickets ne devrait dépendre de l'autre pour démarrer.

## Fronts listés — un seul par application déployée séparément

`buildFrontsList()` (`src/lib.js`) liste actuellement 2 fronts :
Supervision SI (le frontend React principal, avec TOUS ses onglets
internes — carte, arbres radiaux, IPAM, Zenoss, Fusion, géomatique...)
et le portail tickets. **Une carte par front séparément déployé,
jamais une carte par onglet interne** — les modules internes de
Supervision SI ne sont pas des fronts distincts, ils vivent tous
derrière la même carte "Supervision SI". Ajouter un futur troisième
front (ex. un jour un vrai portail QGIS séparé) se fait en une entrée
dans cette fonction, jamais en dupliquant la logique de connexion.

## Client OIDC — déjà défini côté Keycloak, rien à créer

`supervision-hub` dans `keycloak/realm-template.json`, même schéma que
les deux autres clients déjà présents (Authorization Code + PKCE
S256, mapper d'audience `supervision-apis`). Ce hub est le **premier
front du projet à réellement consommer Keycloak** — `supervision-frontend`
et `tickets-portal` existent côté realm depuis plus longtemps mais
n'ont toujours aucun code applicatif qui s'y connecte.

Bibliothèque : `react-oidc-context` (enrobe `oidc-client-ts`),
Authorization Code + PKCE géré automatiquement par la bibliothèque
via `response_type: "code"` sur un client public — voir
`src/authConfig.js` pour la configuration complète, `src/App.jsx`
pour l'usage (`useAuth()` : `isLoading`/`error`/`isAuthenticated`/
`user`/`signinRedirect()`/`signoutRedirect()`).

## Sécurité — ce que ce portail garantit, et ce qu'il NE garantit PAS

**Garanti** : pour voir la liste des fronts et leurs liens, il faut
s'authentifier avec succès contre l'annuaire LDAP de l'entreprise via
Keycloak.

**PAS garanti** : cliquer une carte ouvre l'URL de l'application
cible **directement**, sans jeton, sans en-tête d'autorisation, sans
rien — exactement comme si la personne avait tapé l'URL elle-même
dans un nouvel onglet. Ni Supervision SI ni le portail tickets ne
vérifient quoi que ce soit à l'arrivée. C'est cohérent avec l'état
actuel du reste du projet ("outil interne, réseau de confiance",
répété dans plusieurs autres README) — mais ça veut dire concrètement
que **ce hub est une porte d'entrée organisée, pas une garantie que
les applications elles-mêmes sont protégées**. Quelqu'un connaissant
directement l'URL de Supervision SI ou du portail tickets peut y
accéder sans jamais passer par ce hub. Ce message est affiché
explicitement dans l'interface du hub elle-même (pas seulement ici),
pour ne jamais laisser une fausse impression de sécurité de bout en
bout.

Pistes pour fermer cet écart, non commencées (à discuter avant de s'y
lancer, pas une évidence unique) :
- Faire consommer Keycloak par `supervision-frontend` et
  `tickets-portal` eux-mêmes (leurs clients existent déjà côté
  realm) — chacun re-authentifierait alors sa propre session (avec
  SSO transparent puisque même realm : pas de nouvelle saisie de mot
  de passe si déjà connecté via le hub).
- Faire vérifier un jeton bearer par les APIs backend elles-mêmes
  (`supervision-apis`, déjà défini côté realm en bearer-only) —
  plus lourd, touche potentiellement une vingtaine de services Flask.

## Variables d'environnement (injectées par docker-compose, jamais codées en dur)

- `VITE_KEYCLOAK_URL` / `VITE_KEYCLOAK_REALM` — pour construire
  `authority` (`{URL}/realms/{REALM}`).
- `VITE_SUPERVISION_FRONTEND_URL` / `VITE_TICKETS_PORTAL_URL` — URLs
  des deux fronts listés, côté **navigateur** (HOST_IP), jamais les
  noms de service Docker internes (inatteignables depuis l'extérieur
  du réseau Docker).

## Démarrage

```bash
# Realm Keycloak déjà à jour (supervision-hub y figure) si render.py
# a tourné après ce changement :
python3 keycloak/render.py
docker compose up -d --build keycloak hub
```

Puis `http://<hôte>:6174` — connexion Keycloak, puis les cartes.

## Bugs réels rencontrés en test réel (personne, machine physique)

**1. Realm jamais importé — dossier `keycloak/import/` vide au premier
démarrage.** `keycloak/import/` est ignoré par git (contient un secret,
le mot de passe de bind LDAP en clair une fois rendu). Sur une machine
neuve, ce dossier n'existe pas tant que `python3 keycloak/render.py`
n'a jamais tourné. Docker, sur un bind mount vers un chemin hôte
inexistant, **crée silencieusement un dossier vide** plutôt que
d'échouer — Keycloak importe alors zéro fichier et conclut
`Import finished successfully` (techniquement vrai, rien à importer),
laissant uniquement le realm `master` par défaut. Symptôme trompeur :
aucune erreur nulle part, juste `supervision-si` absent du sélecteur
de realm. **`python3 keycloak/render.py` doit avoir tourné AVANT le
tout premier démarrage de Keycloak** (`scripts/run.sh` le fait
automatiquement — un `docker compose up` direct sans passer par ce
script ne le fait pas).

**2. `Crypto.subtle is available only in secure contexts (HTTPS)`.**
PKCE (Authorization Code + PKCE, tel que configuré côté Keycloak) a
besoin de `crypto.subtle` pour hacher le code verifier — une API que
les navigateurs **désactivent volontairement** sur tout site chargé
en HTTP simple, sauf exception pour `localhost`. Accéder au hub via
une IP LAN (`http://192.168.x.x:6174`) déclenche systématiquement
cette erreur, même avec Keycloak et LDAP parfaitement fonctionnels
par ailleurs — non anticipé en construisant ce hub, découvert en test
réel.
- **Pour tester rapidement, sans changer l'infra** : un tunnel SSH
  fait passer l'accès par `localhost` du point de vue du navigateur
  (exception explicitement prévue par les navigateurs) :
  ```bash
  ssh -L 6174:localhost:6174 -L 6180:localhost:6180 <user>@<ip-vm>
  ```
  puis `http://localhost:6174` depuis le poste qui a ouvert le tunnel.
- **Pour un vrai déploiement multi-utilisateurs** : un reverse proxy
  HTTPS devant le hub (et Keycloak) sera nécessaire — même un
  certificat auto-signé suffit, le "contexte sécurisé" du navigateur
  dépend du protocole, pas de la confiance réelle dans le certificat.
  Pas encore construit.

## Cartes conditionnelles selon les groupes Keycloak (pas les rôles)

**Bug Keycloak documenté de longue date (KEYCLOAK-3469), rencontré en
conditions réelles** : les rôles realm assignés **directement** à un
utilisateur remontent bien dans `realm_access.roles` du jeton, mais
ceux **hérités via l'appartenance à un groupe** ne remontent pas
toujours de façon fiable — malgré `fullScopeAllowed: true` sur les
clients. Observé concrètement : un compte membre de 5 groupes
Keycloak, dont l'appartenance était correctement affichée (claim
`groups`, mapper dédié), sans qu'aucun rôle correspondant n'apparaisse
dans `realm_access.roles` — ni la carte "Supervision SI", ni le
sélecteur de vues du portail tickets ne fonctionnaient.

**Corrigé en pivotant toute la logique de visibilité sur les GROUPES
Keycloak eux-mêmes, jamais sur les rôles calculés** — `GROUP_TO_ROLE`
(`hub/src/lib.js` et `tickets/portal/src/lib.js`, mêmes clés,
volontairement dupliqué plutôt que partagé pour garder chaque front
indépendant) traduit les noms de groupes réels
(`administrateurs`/`demandeurs`/`techniciens`/`direction`/`supervision`)
en rôles applicatifs. `realm_access.roles` reste affiché dans le
panneau 🔍, à titre de comparaison seulement — jamais utilisé pour une
décision d'accès.

Règles de visibilité, décidées avec la personne :
- **Supervision SI** : groupe `supervision` (indépendant des 4 rôles
  du portail tickets — quelqu'un peut avoir accès à l'un sans
  l'autre).
- **Portail tickets** : tout le monde, aucune condition.
- **Administration Keycloak** : groupe `administrateurs` OU `techniciens`.

`buildFrontsList()` accepte `groups` (bruts, claim `groups` du jeton) — la carte "Administration Keycloak" pointe vers la console
**scopée au realm `supervision-si`** (`/auth/admin/supervision-si/console/`),
jamais la console `master`. Point à garder en tête, affiché aussi
explicitement dans l'interface : avoir un rôle applicatif dans
`supervision-si` ne donne PAS automatiquement de droits Keycloak au
niveau réalm — la carte est un lien, l'accès réel dépend de droits de
gestion de realm accordés séparément dans Keycloak (rôles du client
`realm-management`, ex. `realm-admin`, assignés à la personne).

Lien "🏠 retour au hub" ajouté dans les autres fronts (`frontend`,
`tickets-portal`) — voir leurs README respectifs. **Bug de
découvrabilité rencontré et corrigé** : icône seule d'abord, jamais
repérée par la personne — libellé texte ajouté des deux côtés
("🏠 Hub"), et côté `frontend` spécifiquement, sorti d'une barre de
navigation entièrement masquée par défaut (n'apparaissait qu'au
survol), repositionné en élément fixe toujours visible.

## Vérifié depuis cet environnement / non vérifié

**Vérifié** : `buildFrontsList`/`formatUserRoles` (`src/lib.js`) —
11 tests Node (liste vide sans URL fournie, filtrage des rôles
techniques Keycloak comme `offline_access` non affichés, libellés
alignés sur les 4 rôles réalm). `keycloak/render.py --check` confirme
les 3 clients rendus sans jeton `__..__` résiduel. YAML de
`docker-compose.yml` validé (22 services, `hub` présent, `depends_on:
keycloak` correct).

**Non vérifié depuis cet environnement (pas de réseau ici)** : le
flux OIDC complet — redirection, retour, échange de jeton — **a
depuis été vérifié en conditions réelles par la personne** (LDAP
répond, réalm importé, tunnel SSH pour contourner la contrainte
HTTPS de `crypto.subtle`) — voir "Bugs réels rencontrés" ci-dessus.

## Page de paramètres — fondation pour tout le projet

Demandé explicitement : commencer une interface de paramétrage
transversale à toutes les applications, avec deux niveaux d'accès --
les administrateurs ont tous les droits sur tout, chacun a la main
sur ses propres préférences personnelles.

**Fondation posée** (`prefs-api`) : `app_settings` (nouvelle table,
paramétrage GLOBAL par application, fusion superficielle sûre --
jamais d'écrasement d'un paramètre par un autre) vient compléter
`preferences` (déjà existante, paramétrage PERSONNEL, même garantie
de fusion). Aucune vérification de rôle côté serveur sur
`app_settings` -- même posture de confiance que le reste du projet,
c'est le FRONT qui décide qui voit l'interface d'édition (groupe
Keycloak `administrateurs`).

**Interface** (`hub/src/App.jsx`, nouveau `SettingsView`) : bouton
"⚙️" dans l'en-tête du hub, bascule vers une page à deux sections --
"🌐 Général" (visible aux administrateurs uniquement) et
"👤 Mes préférences" (tout le monde, contenu selon le profil).
Premier cas d'usage concret : le rappel d'activité technicien
(message, fréquence, durée d'affichage) -- valeurs par défaut
éditables par un admin, personnalisables par chaque technicien
(l'override personnel l'emporte toujours sur le défaut applicatif,
`effectiveTechReminderConfig` centralise cette règle de priorité,
jamais recalculée à deux endroits).

**Logique de rappel/snooze centralisée** (`hub/src/settingsClient.js`,
`shouldShowReminder`) : gère l'activation/désactivation, le "ne plus
demander pour N minutes" (horodatage) et le "ne plus demander jusqu'à
reconnexion" (drapeau, remis à zéro par l'appelant à la connexion --
volontairement une fonction PURE qui ne fait que lire l'état, jamais
deviner un événement de connexion elle-même).

Vérifié réellement : 39 tests au total sur cette fondation (dont la
garantie la plus importante -- écrire les préférences du rappel
technicien ne touche JAMAIS au thème déjà enregistré dans le même
blob). Non-régression complète sur le hub et prefs-api existants.

**Reste à construire** (suite du chantier, pas encore livré) : le
widget de rappel lui-même (minuterie de fréquence + popup avec liste
des tickets + minuterie d'auto-fermeture), le démarrage réel du suivi
de temps depuis ce rappel (appel vers tickets-api), et les liens
"⚙️" sur les autres fronts (coffre, DBA, etc.).

## Widget de rappel — les deux minuteries, le suivi de temps réel

Suite directe de la fondation ci-dessus. `hub/src/ReminderWidget.jsx`
-- intégré au hub lui-même (`<div className="hub-shell">`, hors de
la bascule grille/paramètres), s'affiche par-dessus n'importe quel
onglet.

**tickets-api n'a pas de notion de segment OUVERT** (`POST
/time_entries` exige `start_ts` ET `end_ts` dès la création) -- le
suivi "en direct" fonctionne donc par **clôture différée** : à chaque
confirmation d'activité, clôt la période depuis la DERNIÈRE
confirmation (quel que soit le ticket suivi pendant ce temps) et
démarre le suivi du nouveau choix. `computeSegmentToSubmit`/
`nextSession` (`settingsClient.js`) centralisent cette mécanique,
testée avec un cycle complet (première confirmation jamais rien à
soumettre, confirmation du même ticket, changement d'activité --
vérifié que la période précédente se clôt bien sur l'ANCIEN ticket,
jamais le nouveau). Session persistée dans un namespace séparé des
préférences déclaratives -- survit à un rechargement de page.

**Deux minuteries séparées**, demandé explicitement : celle de
fréquence (`setInterval`, déclenche l'ouverture du popup) et celle
de durée d'affichage (`setTimeout`, ferme automatiquement si aucune
réaction -- sans jamais rien soumettre dans ce cas, la session en
cours continue simplement d'être suivie).

**Snooze** : "60 minutes" (horodatage) et "jusqu'à reconnexion"
(drapeau, remis à zéro au montage du widget -- on vient justement de
se reconnecter). Popup avec liste des tickets ouverts (même route que
la file technicien, `/queue?state=open`), lien vers le portail
tickets par ticket.

`VITE_TICKETS_API_BASE_URL` ajouté au service `hub` (absent
jusqu'ici) -- nécessaire pour interroger la file et soumettre les
segments directement depuis le hub.

Vérifié réellement : 17 tests supplémentaires sur cette tranche (56
au total sur tout le chantier paramétrage/rappel). Non-régression
complète. **Non vérifié** : le rendu visuel réel du popup et le
déclenchement effectif des minuteries dans un vrai navigateur --
aucun disponible dans cet environnement, la logique métier (la partie
la plus risquée de se tromper) est en revanche testée à fond.

**Reste** : les liens "⚙️" sur les autres fronts (coffre, DBA,
etc.) -- dernier morceau de la demande initiale.

## Liens "⚙️ Paramètres" — tous les fronts couverts

Dernier morceau de la demande initiale. Lien "⚙️ Paramètres" ajouté
à côté du lien "🏠 Hub" déjà existant sur **tous** les fronts :
`tickets/portal`, `vault/portal`, `vault/admin-portal` (les deux
écrans, connexion et connecté -- origine séparée, URL absolue comme
pour ses liens Hub/Coffre-fort déjà en place), `dba/portal`, et
`frontend` (Supervision SI -- le lien vivait dans `TopNav.jsx`, pas
`App.jsx`, repéré après une recherche plus large).

**Lien profond** : `/?view=settings` plutôt que juste `/` -- le hub
lit ce paramètre d'URL au montage (`useState` avec initialiseur) pour
ouvrir directement la page de paramètres, sans clic supplémentaire
une fois arrivé. Limite mineure assumée, non vérifiée en conditions
réelles : ce paramètre pourrait ne pas survivre à un aller-retour
complet vers Keycloak si la personne n'était PAS déjà authentifiée
sur ce navigateur (le flux OIDC peut réécrire l'URL) -- dans la
pratique, si elle vient de naviguer avec succès sur un autre front,
elle est déjà authentifiée globalement (`signinSilent`), donc ce cas
limite ne devrait quasiment jamais se produire.

**Demande notée pour plus tard, pas commencée** (voir `BACKLOG.md`
à la racine) : un gestionnaire de base de données généralisé
(arborescence des relations, édition par tableaux, SQL direct avec
test de syntaxe) -- à clarifier avec la personne si c'est une
évolution du module DBA existant ou un outil séparé, avant de
commencer.

Vérifié : syntaxe (tsc) sur les 5 fronts modifiés, non-régression
complète sur tout le chantier (56+ tests déjà existants, aucun
nouveau test pour cette tranche -- changements purement
structurels/JSX, sans nouvelle logique testable).

## Groupe local demandeurs — premier réglage "métier" au-delà du rappel

Premier point de la file de demandes établie après ce chantier. Le
mécanisme d'import (`/users/import-keycloak-group`, tickets-api)
acceptait déjà un paramètre `group` générique -- import "demandeurs"
(LDAP) codé en dur côté interface. Désormais complété par un second
groupe LOCAL, configurable.

**Renommage assumé** avant d'ajouter ce nouveau champ :
`DEFAULT_TECH_REMINDER_SETTINGS`/`mergeTechReminderSettings` →
`DEFAULT_TICKETS_APP_SETTINGS`/`mergeTicketsAppSettings` -- ce blob
`app_settings` de l'application "tickets" allait accueillir bien plus
que le seul rappel d'activité au fil du temps ("je peux laisser
libre cours à mes idées d'évolution"), jamais un nom qui devienne
trompeur à mesure que la liste grandit.

**Nouveau champ** `local_requester_group` dans la même page
"⚙️ Paramètres" du hub, sous-section "Import des demandeurs" (même
panneau "🌐 Général", même bouton "Enregistrer" que le rappel --
même blob). Vide par défaut = comportement inchangé (import
"demandeurs" seul).

**Côté portail tickets** (`AdminView.jsx`) : le bouton d'import lit
désormais ce paramètre (appel direct à `prefs-api`, même URL déjà
utilisée pour le thème) et importe le groupe local EN PLUS de
"demandeurs", jamais à la place. Un échec sur le groupe local (mal
nommé, etc.) ne fait jamais perdre le succès déjà acquis sur
"demandeurs" -- affiché comme partiel. `mergeImportResults`
(`lib.js`) fusionne et dédoublonne les deux résultats pour un
affichage combiné.

Vérifié réellement : 5 tests sur `mergeImportResults` (dont la
déduplication -- un même login jamais compté deux fois si les deux
imports le voient), 2 tests supplémentaires sur le nouveau champ
`local_requester_group`. Non-régression complète, y compris le test
backend existant sur l'import Keycloak (rôle changé à la main
toujours préservé au réimport).

## Vue "Historique du projet" — CHANGELOG.md/BACKLOG.md dans le hub

Chantier suivant de la file. Demandé explicitement : rendre visibles
dans une interface (plutôt que des fichiers texte à ouvrir
manuellement) ce que `CHANGELOG.md` et `BACKLOG.md` contiennent déjà.

**Servis EN DIRECT, jamais une copie figée** : ces fichiers changent
à chaque livraison -- `prefs-api` les lit depuis des volumes montés
en LECTURE SEULE, directement depuis la racine du dépôt
(`docker-compose.yml`, nouvelles routes `GET /changelog`/
`GET /backlog`). Toujours le contenu réel du moment, sans jamais
nécessiter un rebuild de ce service.

**Rendu markdown maison** (`hub/src/markdown.js`) plutôt qu'une
bibliothèque externe (aucune utilisée ailleurs dans ce projet) --
couvre exactement ce qu'utilisent ces deux fichiers : titres
(`#`/`##`/`###`), **gras**, `code inline`, listes à puces,
paragraphes. Fonctions pures (parsing texte → blocs de données),
testées à fond y compris contre les **deux vrais fichiers complets**
du dépôt (82 Ko pour `CHANGELOG.md`), pas seulement des extraits
construits à la main.

**Interface** : nouveau bouton "📜" dans l'en-tête du hub, à côté de
"⚙️ Paramètres" (même famille d'écran "méta" sur le projet, comme
suggéré). Deux sous-onglets (Historique des évolutions / Backlog).
Lien profond `?view=history` supporté, même mécanisme que
`?view=settings` déjà en place.

Vérifié réellement : 34 tests sur cette tranche (20 sur le parseur
markdown avec un extrait représentatif de `CHANGELOG.md`, validé
séparément contre les deux fichiers réels complets du dépôt sans
aucune exception ; 6 sur les nouvelles routes `prefs-api` avec de
vrais fichiers temporaires, y compris le cas d'un fichier manquant ;
2 sur les fonctions client ; classes CSS vérifiées une par une par
script automatisé). Non-régression complète sur tout le hub et
`prefs-api`.

**Non vérifié dans cet environnement** : rendu visuel réel, aucun
navigateur disponible ici.

## Bug réel — mise en page trop étroite, deux styles incohérents

Signalé par capture d'écran : "le skin par défaut fait cohabiter deux
designs incompatibles" -- une barre pleine largeur en haut, puis une
colonne étroite (environ 1/5 de l'écran) avec des cadres surchargés
en dessous. La vue "Historique" (`CHANGELOG.md`) en était l'exemple
le plus caricatural.

**Cause** : `.hub-settings` limitait le conteneur à `max-width: 640px`
-- pensé à l'origine pour la page "⚙️ Paramètres" (des champs de
formulaire courts n'ont pas besoin de toute la largeur), mais réutilisé
tel quel par "📜 Historique" pour du contenu de prose qui, lui,
devrait clairement profiter de l'espace disponible sur un écran large.

**Corrigé** :
- Conteneur élargi (640px → 1400px).
- Nouvelle classe `.hub-settings-grid` -- les sections s'organisent
  désormais en grille CSS (`repeat(auto-fit, minmax(360px, 1fr))`)
  qui se réorganise en lignes selon la largeur disponible, plutôt
  qu'empilées verticalement dans une colonne fixe quel que soit
  l'espace libre -- demandé explicitement ("les cadres s'organisent
  en lignes sur la largeur de l'écran"). Avec une seule section (cas
  de "Historique"), elle occupe naturellement toute la largeur ; avec
  plusieurs (cas de "Paramètres" -- "🌐 Général" et "👤 Mes
  préférences"), elles se placent côte à côte si la largeur le
  permet, sinon repassent en colonne sur un écran étroit.
- Largeur du texte markdown légèrement augmentée (780px → 900px) pour
  mieux profiter de l'espace tout en restant confortable à lire (une
  ligne de texte trop large devient difficile à suivre).

Vérifié : syntaxe (tsc), équilibre des balises `<div>` (29 ouvertes/
29 fermées), classes CSS toutes définies, non-régression complète sur
le hub. **Non vérifié dans cet environnement** : rendu visuel réel,
aucun navigateur disponible ici -- à confirmer par la personne, en
particulier la réorganisation en lignes sur un écran large.

## Coquille à onglets — étape 1 de la proposition d'évolution

Demandé explicitement, discuté et cadré ouvertement avant de coder :
la proposition initiale (onglets façon navigateur, contexte par
onglet, historique versionné, rémanence complète) a été découpée en
étapes. Ceci est la première -- la coquille elle-même. Le protocole
de communication (`postMessage`) entre chaque application et la
coquille, et la mémorisation des onglets ouverts, restent des
chantiers séparés, pas encore commencés.

**Architecture retenue** : chaque onglet est une `<iframe>` pointant
vers une application du hub -- possible sans complication cross-origin
puisque toutes vivent déjà sous la même entrée unique par chemin
(`tls-proxy`). Vérifié explicitement : aucun en-tête
`X-Frame-Options`/`Content-Security-Policy` nulle part dans le projet
qui bloquerait cette intégration.

**`hub/src/tabs.js`** (pur, testé sans React) -- `createTab`
(identifiant via `crypto.randomUUID()`, plusieurs onglets sur la
même application possibles, jamais fusionnés), `openTab`,
`closeTab` (renvoie `{tabs, activeTabId}` -- fermer l'onglet actif
détermine forcément lequel devient actif ensuite, même convention
que la plupart des navigateurs : l'onglet qui glisse à la place du
fermé devient actif ; aucun onglet restant -- `activeTabId` devient
`null`, jamais une exception).

**`hub/src/TabShell.jsx`** -- barre d'onglets, sélecteur "+"
(uniquement les applications `embeddable: true`, voir `lib.js`),
fermeture par onglet. **Toutes les iframes ouvertes restent montées
en permanence** (`key` stable par onglet), seule leur visibilité CSS
change selon l'onglet actif -- les démonter à chaque bascule aurait
perdu le travail en cours dans les onglets inactifs, contraire à
l'objectif même de cette coquille.

**`embeddable` ajouté à chaque front** (`lib.js`, `buildFrontsList`)
-- `false` pour Keycloak (refuse lui-même l'intégration en iframe,
protection native) et l'administration du coffre-fort (origine
différente, port LAN direct) : ces deux-là restent des liens
classiques dans la grille, jamais proposés comme onglet.

Nouveau bouton "🗂️" dans l'en-tête, à côté de ⚙️/📜. Lien profond
`?view=tabs` supporté, même mécanisme que `?view=settings`/`?view=history`.

**Compromis assumé et documenté** : la barre d'adresse du navigateur
reste sur l'URL du hub quel que soit l'onglet actif à l'intérieur --
normal pour ce type de coquille, mais à savoir avant de s'en servir.

Vérifié réellement : 27 tests sur cette tranche (20 sur la logique
de gestion des onglets, dont plusieurs onglets simultanés sur la
même application, et les trois cas de fermeture d'un onglet actif --
au milieu, à droite, à gauche ; 7 sur le nouveau champ `embeddable`
pour les 7 applications du hub). Classes CSS toutes vérifiées
présentes. Non-régression complète.

**Non vérifié dans cet environnement** : rendu visuel réel et
comportement effectif de l'intégration en iframe, aucun navigateur
disponible ici -- c'est le point le plus important à confirmer en
conditions réelles pour ce chantier.

## Trois bugs réels signalés en testant la coquille à onglets

**1. Page Paramètres — la largeur élargie n'était pas vraiment
appliquée.** Cause : `.hub-settings-section` combine toujours la
classe `.hub-card` (`className="hub-card hub-settings-section"`) --
`.hub-card` plafonne à 420px pour l'écran de connexion, et cette
propriété n'était jamais redéclarée par `.hub-settings-section`,
donc jamais réellement écrasée malgré l'élargissement du conteneur
parent lors du chantier précédent. **Corrigé** : `max-width: none`
ajouté explicitement.

**2. Le "+" de la coquille à onglets ne faisait visiblement rien.**
Cause : le menu déroulant se rendait bel et bien, mais était
invisible -- `.hub-tabbar` (le conteneur parent direct du bouton "+")
a `overflow-x: auto` pour permettre le défilement horizontal des
onglets, ce qui recadre implicitement aussi tout débordement
vertical de ses enfants (`overflow-y` devient `auto` dès que
`overflow-x` est fixé, même sans le déclarer explicitement) -- le
menu, positionné `absolute` juste en dessous du bouton, était donc
systématiquement coupé. **Corrigé** : le menu est désormais rendu en
dehors de `.hub-tabbar`, positionné par rapport à `.hub-tabshell`
(qui n'a pas ce recadrage). Décalage fixe plutôt que calculé en JS --
correct dans le cas courant, approximatif si de nombreux onglets sont
déjà ouverts (amélioration possible plus tard si besoin réel).

**3. Dans l'application Supervision SI elle-même, "🏠 Hub" et
"⚙️ Paramètres" étaient littéralement superposés.** Signalé lors du
test de la coquille (bien que préexistant, pas introduit par elle) :
les deux liens partageaient EXACTEMENT la même classe
(`top-nav-hub-link-fixed`), donc la même position fixe (`top: 8px;
left: 8px`) -- aucun décalage entre eux. Le bouton de thème, juste à
côté, débordait à son tour sur ce qui chevauchait déjà, masquant
également le libellé de l'application et une partie du menu de
navigation amovible. **Corrigé** : les trois éléments regroupés dans
un conteneur flexible commun (`top-nav-fixed-controls`) -- espacement
naturel entre eux, jamais besoin de deviner des décalages en pixels
fixes pour des textes de longueurs variables.

Vérifié : syntaxe (tsc) sur les trois fichiers touchés (hub et
frontend), équilibre CSS des deux feuilles de style modifiées,
classes toutes vérifiées présentes. Non-régression complète sur les
tests du hub.

**Non vérifié dans cet environnement** : rendu visuel réel, aucun
navigateur disponible ici -- ces trois corrections méritent
particulièrement votre confirmation en conditions réelles, notamment
le point 3 (application Supervision SI, jamais retouchée avant
aujourd'hui dans le cadre de ce travail).

## Bug réel — le menu masquable était toujours derrière les contrôles fixes

Signalé une deuxième fois après le premier correctif : celui-ci ne
réglait que le chevauchement ENTRE 🏠/⚙️/🌙, jamais leur chevauchement
avec le menu de navigation lui-même (`nav.top-nav`, dans l'application
Supervision SI). Cause : le menu démarre à `top: 0` avec seulement
`1rem` de marge gauche -- exactement la même bande verticale que les
contrôles fixes (`top: 8px`, aussi à gauche) -- ses premiers boutons
(Supervision SI, Pixel Grid...) se retrouvaient donc masqués dessous
dès que le menu apparaissait au survol.

**Corrigé** : marge gauche généreuse (`padding-left: 300px`) sur le
menu, pour qu'il démarre nettement après le groupe de contrôles
fixes. Filet de sécurité ajouté au passage : défilement horizontal
sur le menu si les 13 boutons ne tiennent plus dans l'espace réduit
sur un écran plus étroit, plutôt qu'un retour à la ligne disgracieux
(`flex-shrink: 0` + `white-space: nowrap` sur chaque bouton, pour que
ce soit bien le conteneur qui défile, jamais le texte qui se
comprime).

Vérifié : équilibre CSS, syntaxe. **Non vérifié dans cet
environnement** : rendu visuel réel, aucun navigateur disponible ici
-- ce point a déjà nécessité deux passes, mérite particulièrement
votre confirmation.

## Protocole postMessage coquille <-> application embarquée (backlog #1)

`beforeunload` (déjà construit, `shared/useUnsavedChangesWarning.js`)
ne couvre que "fermer/recharger TOUT le navigateur" -- fermer un
ONGLET précis dans la coquille (`✕` sur un onglet, `handleCloseTab`)
ne déclenche jamais cet évènement natif : ce n'est qu'un retrait de
l'iframe du DOM / masquage CSS, jamais une navigation.

**Protocole** (`tabs.js`) : chaque application embarquée qui appelle
déjà `useUnsavedChangesWarning(hasUnsavedChanges)` envoie désormais
AUSSI un `postMessage({ type: "supervision-si:unsaved-changes", value
}, window.location.origin)` à `window.parent` à chaque changement de
cet état -- `targetOrigin` explicite (jamais `"*"`), toutes les
applications vivent sous la même origine derrière tls-proxy.
`TabShell.jsx` écoute, vérifie `event.origin` D'ABORD, valide la
forme du message (`isValidUnsavedChangesMessage`), puis retrouve
QUEL onglet a envoyé le message par comparaison de RÉFÉRENCE entre
`event.source` et le `.contentWindow` de chaque iframe montée
(`findTabIdForWindow`) -- jamais par URL/titre, deux onglets peuvent
être ouverts sur la MÊME application (voir `createTab`) et doivent
rester distingués.

**Dégradation propre** : seule `dba/portal` appelle actuellement ce
hook -- toute autre application (jamais encore câblée) ne signale
simplement rien, `unsavedTabIds[tabId]` reste `undefined`/faux, fermer
son onglet se comporte exactement comme avant ce chantier. Étendre ce
signalement à d'autres modules reste un chantier séparé, pas fait ici
(la demande portait sur LE PROTOCOLE, pas sur le câblage de chaque
application une par une).

**Interface** : fermeture d'un onglet dont `unsavedTabIds[tabId]` est
vrai -> `window.confirm(...)` avant de fermer réellement (même esprit
que la boîte de dialogue native de `beforeunload`, cohérent
visuellement plutôt qu'un nouveau composant modal). Petit point
indicateur (`.hub-tab-unsaved-dot`, couleur `--accent` jamais
`--danger` -- indicatif, pas bloquant) affiché directement sur
l'onglet concerné, visible même sans tenter de le fermer.

Vérifié réellement : logique pure testée via Node
(`isValidUnsavedChangesMessage` -- formes invalides, messages d'un
type différent ; `findTabIdForWindow` -- fenêtre inconnue, liste
vide, **et le cas important de deux onglets ouverts sur la même
application**, distingués correctement par référence de fenêtre).
Syntaxe (`tsc --jsx`) sur `TabShell.jsx`/`tabs.js` et sur
`shared/useUnsavedChangesWarning.js`, classe CSS vérifiée présente,
accolades CSS équilibrées. **Non vérifié dans cet environnement** :
comportement réel du `postMessage` entre une vraie iframe et son
parent (aucun navigateur disponible ici) -- ce chantier touche
directement de la communication inter-fenêtres, mérite
particulièrement un test en conditions réelles (ouvrir DBA dans un
onglet, modifier une cellule, tenter de fermer cet onglet précis).

## Mémorisation des onglets ouverts (backlog #2)

"À la réouverture" -- interprété comme survivant à un rechargement ou
une fermeture du NAVIGATEUR sur le MÊME appareil, pas un réglage de
compte à synchroniser entre appareils. Choix assumé plutôt que
tranché avec la personne (fork jugé mineur, pas de vraie
divergence d'architecture -- contrairement à la question posée pour
le coffre-fort sur "obligatoire bloquant ou indicatif") : localStorage,
même principe que le thème (`shared/preferences.js`) -- si la personne
veut plutôt une synchronisation multi-appareils via `prefs-api`, c'est
un changement de mécanisme de stockage assez direct à faire depuis
cette base (voir `serializeOpenTabs`/`restoreOpenTabs`, déjà séparées
de tout accès localStorage).

**Logique pure** (`tabs.js`) : `serializeOpenTabs(tabs, activeTabId)`
réduit la liste vivante à `{appIds, activeIndex}` -- jamais les URLs/
titres (re-résolus depuis `fronts` à la restauration, plus frais
qu'une copie figée) ni les `id` générés (aléatoires, sans valeur d'une
session à l'autre) ; l'onglet actif est repéré par POSITION, cohérent
avec la régénération des `id`. `restoreOpenTabs(stored, fronts)`
reconstruit une liste FRAÎCHE (nouveaux `id` via `createTab`) --
toute application stockée mais absente de `fronts` (retirée,
renommée, ou permission de rôle perdue depuis, `fronts` étant déjà
filtré par rôle en amont) est simplement OMISE, jamais une exception ;
l'index actif se recale tout seul si des applications manquantes le
précédaient.

**Interface** (`TabShell.jsx`) : chargement UNE SEULE FOIS au montage
via une ref mémoïsée (`initialOpenTabsRef`) -- piège réel évité en
construisant ceci : appeler la fonction de chargement séparément dans
CHAQUE `useState(() => ...)` (un pour `tabs`, un pour `activeTabId`)
génère de NOUVEAUX id à chaque appel (`createTab`), l'`activeTabId`
du second appel ne correspondrait alors à AUCUN `id` du premier --
onglet "actif" fantôme, aucun onglet visuellement marqué actif. Un
seul calcul, stocké dans une ref, les deux `useState` lisent la MÊME
valeur. Sauvegarde à chaque changement (ouverture, fermeture, bascule)
via un effet dédié, jamais bloquant si le stockage est indisponible.

Vérifié réellement : logique pure testée via Node -- aller-retour
complet (sérialiser puis restaurer redonne un état équivalent),
application manquante omise avec recalage correct de l'index actif,
onglet actif lui-même manquant, formes stockées corrompues/
inattendues (jamais une exception), et le cas important de DEUX
onglets ouverts sur la même application (restaurés séparément avec
des `id` distincts, le bon reste actif). Syntaxe (`tsc --jsx`),
correspondance setters `useState` déclarés/utilisés, accolades
équilibrées. **Non vérifié dans cet environnement** : comportement
réel de `localStorage` et de la ref mémoïsée à travers un vrai cycle
de montage/démontage React, aucun navigateur disponible ici --
mérite un test réel (ouvrir plusieurs onglets, recharger la page du
hub, vérifier qu'ils reviennent dans le même ordre avec le bon actif).

## Bug corrigé — un ticket confirmé depuis le rappel n'apparaissait jamais "en cours"

Constaté sur la version #105, remonté avec deux évolutions liées
(Gantt/timeline technicien, voir tickets/README.md). Diagnostic
détaillé avant de construire quoi que ce soit :

- **Clôture différée** (`settingsClient.js`, déjà documentée) : chaque
  confirmation clôt la période depuis la DERNIÈRE confirmation, jamais
  celle du ticket qu'on vient de choisir -- `tickets-api` n'a pas de
  notion de segment ouvert. Avec exactement 2 confirmations, seul le
  1ᵉʳ ticket a un segment réellement soumis. **Comportement voulu**,
  pas un bug -- mais source de confusion réelle (voir note ajoutée
  ci-dessous).
- **Le vrai bug** : confirmer un ticket ne touchait JAMAIS son statut.
  Or "en cours" (`tickets/api/app.py`, `first_in_progress_ts`, panneau
  "🔧 En cours depuis" de l'écran technicien) ne se déclenche QUE sur
  un changement de statut vers un type "en_cours" -- jamais sur la
  seule présence d'un segment de temps. Question ciblée posée avant de
  construire (bascule automatique ou juste indicatif ?) -- réponse :
  bascule automatique.

**Corrigé** (`settingsClient.js` + `ReminderWidget.jsx`) :
`pickAutoInProgressStatutId(statuts, currentStatutId)` -- pure, ne
bascule JAMAIS si le statut actuel est déjà de type "en_cours"
(peuvent être PLUSIEURS, jamais écraser un choix déjà actif ni spammer
l'historique), choix déterministe s'il faut basculer (premier par
`id`, aucune autre priorité dans le schéma), `null` si aucun n'est
configuré (dégrade proprement). `handleConfirm` appelle `PUT
/tickets/<id>` (réutilise TEL QUEL la route déjà utilisée par l'écran
technicien -- `first_in_progress_ts`/`ticket_status_log` déjà gérés
là-bas, aucune logique dupliquée). Statuts chargés une fois au montage
(config qui change rarement), aucun nouvel endpoint backend nécessaire
(`GET /statuts` retournait déjà `type`).

**Complément** : note ajoutée dans le popup ("le temps du ticket
choisi sera comptabilisé au prochain rappel") pour que la clôture
différée ne soit plus silencieuse -- n'a jamais changé le mécanisme
lui-même (design assumé, contrainte du schéma), juste rendu visible.

Vérifié réellement : logique pure (`pickAutoInProgressStatutId`)
testée via Node -- statut déjà bon, plusieurs statuts "en_cours"
configurés (le premier choisi, jamais un déjà-actif écrasé), aucun
configuré, listes vides/undefined, comparaison robuste string/number
sur les id. Syntaxe (`tsc --jsx`), setters cohérents, accolades
équilibrées, classe CSS présente. **Non vérifié dans cet
environnement** : comportement réel (la personne devra confirmer que
"🔧 En cours depuis" affiche bien le ticket après une confirmation, et
que le Gantt politique affiche le segment du 1ᵉʳ ticket comme attendu
-- ce second point n'a pas nécessité de changement de code, la route
`/tickets/parallel` étant déjà basée sur le temps saisi, pas le
statut).

## Timeline du hub — rappels, changements d'activité, mouvements d'onglets, tickets créés (chantier en cours, par étapes)

Proposition de la personne, **cadrée avant de coder** (même esprit que
la coquille à onglets en son temps) : timeline verticale ancrée à
droite en mode onglets, fenêtre glissante (demi-journée par défaut,
granularité paramétrable), différenciant rappels sans réaction,
changements de tâche, mouvements entre onglets, tickets créés (avec
compteur si plusieurs au même endroit).

**Vrai point de bifurcation posé avant de construire** : rémanence à
travers un rechargement de page, ou juste "depuis que cet onglet du
navigateur est ouvert" ? Réponse : **rémanente, côté serveur/infra**.

**Étape 1 (backend) livrée** : nouvelle table `hub_events` dans
`prefs-api` (pas un nouveau service ni pixel-grid-api -- voir
raisonnement ci-dessous), `POST /events` (dépose un événement) et
`GET /events` (fenêtre glissante, `login`/`since`/`until`/`limit`).
4 catégories connues (`VALID_HUB_EVENT_CATEGORIES`) : `rappel_sans_reaction`,
`changement_activite`, `mouvement_onglet`, `ticket_cree` -- une
catégorie hors de cette liste est rejetée (400), jamais stockée
silencieusement (l'affichage différencié côté client dépendra
entièrement de ces 4 valeurs). `ts` toujours posé côté serveur,
jamais transmis par l'appelant.

**Pourquoi `prefs-api` plutôt que `pixel-grid-api`** : pixel-grid a
DÉJÀ un schéma générique quasi identique (`events` : ts/valeur/nom/
type/data) qui semblait au premier abord un candidat naturel à
réutiliser -- mais son accès API est **délibérément lecture seule**
pour cette table précise (`get_connection()` ouvre SQLite en
`mode=ro`, commentaire explicite : "l'écriture n'est faite que par le
générateur... jamais par ce service"). Ce chantier aurait dû violer
cette limite volontaire plutôt que la généraliser -- `prefs-api`, déjà
le service "hub-wide, cross-cutting" (préférences, réglages globaux,
déjà consommé par le rappel technicien), s'est avéré le bon
réutilisation sans ce conflit.

**Scope personnel, pas un journal partagé** : chaque événement porte
un `login` (optionnel côté schéma, mais toujours renseigné par les
émetteurs prévus) -- 3 des 4 catégories sont déjà intrinsèquement
liées à une session PERSONNELLE (le rappel d'activité, la coquille à
onglets d'un navigateur précis) ; la 4e ("ticket créé") a été gardée
cohérente avec ça plutôt que de la rendre globale à part. **Choix fait
sans reposer la question à la personne** (contrairement au fork
rémanence/pas rémanence, jugé suffisamment tranché par la cohérence
avec les 3 autres catégories) -- à confirmer/corriger si ce n'est pas
ce qui était voulu.

Vérifié réellement : `app.test_client()` (base isolée) -- les 4
catégories valides acceptées, catégorie inconnue rejetée, `login`
optionnel, `ts` toujours celui du serveur (jamais celui fourni),
filtrage par login (aucune fuite entre logins), filtrage since/until
(fenêtre glissante), login inconnu -> liste vide jamais une erreur,
JSON `data` correctement reparsé. **Non-régression explicite** sur
`/preferences`, `/app-settings`, `/changelog`, `/backlog`, `/health`
(aucun touché par ce chantier, tous revérifiés). Syntaxe (`ast.parse`).

**Étapes restantes, dans l'ordre** :
1. Émission des 4 événements depuis leurs points d'origine respectifs
   (`ReminderWidget.jsx` pour rappel_sans_reaction/changement_activite,
   `TabShell.jsx` pour mouvement_onglet, les 3 points de création de
   ticket côté `tickets/portal` pour ticket_cree) -- jamais bloquant
   pour l'action qui déclenche l'événement.
2. Le composant de timeline lui-même (rendu visuel, granularité
   paramétrable, marqueurs différenciés, compteur si plusieurs
   événements regroupés) -- le morceau le plus visuel, à construire et
   à faire confirmer en conditions réelles vu l'absence de navigateur
   dans cet environnement.

### Étape 2 (émission) livrée en #119

Nouveau module partagé `shared/hubEvents.js` (`postHubEvent`) -- copié
au build dans `hub/` ET `tickets/portal/` (les deux Dockerfile
modifiés en conséquence), même mécanisme que `shared/preferences.js`.
Jamais bloquant : chaque appel est `try/catch` silencieux, un échec ne
doit jamais empêcher l'action réelle (fermer un rappel, changer
d'onglet, créer un ticket).

- **`rappel_sans_reaction`** (`ReminderWidget.jsx`) -- émis
  SEULEMENT sur la fermeture AUTOMATIQUE (timeout), jamais sur
  "Fermer"/snooze (des actions explicites, une forme de réaction même
  sans choisir de ticket) -- "sans réaction/fermeture" (demandé tel
  quel) ne colle qu'au cas où rien n'a été touché du tout.
- **`changement_activite`** (même fichier, `handleConfirm`) -- émis
  seulement si la confirmation change RÉELLEMENT de ticket par
  rapport à la session en cours (reconfirmer le même ticket, ou la
  toute première confirmation sans session précédente, n'émet rien).
- **`mouvement_onglet`** (`TabShell.jsx`) -- émis à l'ouverture d'une
  nouvelle application (devient l'onglet actif) ET à la bascule vers
  un onglet déjà ouvert, jamais sur un clic sur l'onglet DÉJÀ actif
  (aucun changement réel). `TabShell` gagne deux nouvelles props
  (`login`, `prefsApiBase`), transmises depuis `App.jsx`.
- **`ticket_cree`** (`tickets/portal`, 3 points : incident projet
  dans `AdminView.jsx`, demande ET sous-demande dans
  `DemandeurView.jsx`) -- attribué au **véritable acteur**
  (`actedBy?.login || me.login` dans `DemandeurView.jsx` -- même
  raisonnement que `acted_by_user_id` déjà existant : un technicien
  qui usurpe la vue demandeur reste tracé comme auteur réel, jamais
  le demandeur pour le compte de qui il agit).

Vérifié réellement : syntaxe (`tsc --jsx`) sur les 5 fichiers React
touchés et le nouveau module partagé, correspondance setters
`useState` déclarés/utilisés sur chacun (tous les écarts identifiés
sont des faux positifs déjà connus ou triviaux -- `setInterval`/
`setTimeout` natifs, `localStorage.setItem`, une variable locale
`settings` qui commence par "set" sans être un setter d'état, un
alias `setBlocks` préexistant qui redirige vers l'un ou l'autre
setter selon l'onglet actif), accolades JSX équilibrées sur les 5
fichiers. Les deux gardes anti-doublon (`tabId === activeTabId`,
`session?.currentTicketId !== ticketId`) sont des conditions triviales
à une ligne, revues manuellement plutôt que testées séparément --
la logique de session sous-jacente (`computeSegmentToSubmit`/
`nextSession`) était déjà testée via Node lors d'une livraison
précédente. **Non vérifié dans cet environnement** : comportement
réel de bout en bout (émission -> stockage -> lecture), aucun
navigateur ni service réellement démarré ici -- mérite un test en
conditions réelles avant l'étape 3 (rien à afficher encore, mais
`GET /events?login=...` côté `prefs-api` peut déjà être interrogé
directement pour vérifier que les événements arrivent bien).

### Étape 3 (composant de timeline) livrée en #120

**Choix de conception assumé, pas vérifiable visuellement dans cet
environnement** : plutôt qu'une timeline PROPORTIONNELLE (position en
pixels calculée à partir du temps écoulé, comme le Gantt de l'écran
politique tickets), une liste chronologique GROUPÉE PAR CRÉNEAU
("bucket") -- plus robuste à construire et vérifier sans navigateur,
plus lisible aussi en cas de rafale d'événements. `hubTimelineLib.js`
(logique pure, testée séparément) :

- `granularityWindowSeconds(granularity)` -- fenêtre glissante (1h à
  1 mois), "demi-jour" par défaut (demandé explicitement).
- `granularityBucketSeconds(granularity)` -- taille des créneaux de
  regroupement, croît avec la fenêtre choisie (5 min sur "heure",
  1 jour sur "mois") -- jamais des centaines de lignes illisibles sur
  une longue fenêtre.
- `groupEventsByBucket(events, bucketSeconds)` -- regroupe par
  créneau PUIS par catégorie -- un marqueur par catégorie présente
  dans le créneau, avec un COMPTEUR si plusieurs événements du même
  type y tombent (demandé explicitement : "un petit chiffre s'il y en
  a plusieurs dans le même delta temps"). Défensif sur des événements
  malformés (jamais une exception qui casserait tout l'affichage).

`HubTimeline.jsx` : rafraîchie toutes les 60s (même esprit que le
rafraîchissement léger déjà utilisé dans `TechnicienView.jsx`),
sélecteur de granularité qui recharge la fenêtre. Rendue en colonne
DROITE fixe dans `TabShell.jsx` (`.hub-tabshell-body`, nouveau
conteneur en ligne enveloppant `.hub-tab-content` ET la timeline --
"à droite en bordure d'écran" demandé explicitement, jamais un panneau
flottant par-dessus le contenu). 4 couleurs de fond distinctes par
catégorie (jamais la SEULE couleur pour porter l'information -- icône
+ info-bulle restent le signal principal).

Vérifié réellement : `hubTimelineLib.js` testé via Node -- fenêtres/
granularités connues et inconnues (retombe sur le défaut), regroupement
simple, **le cas important du compteur** (plusieurs événements du même
type dans le même créneau), tri du plus récent au plus ancien,
événements malformés (`null`/`undefined`/champs manquants -- jamais
une exception, silencieusement ignorés), listes vides,
`bucketSeconds <= 0` (jamais une division par zéro). Syntaxe
(`tsc --jsx`) sur les 6 fichiers touchés, correspondance setters
`useState`, accolades JS/CSS équilibrées, les 4 classes de couleur par
catégorie vérifiées présentes (construites dynamiquement par template
literal dans le JSX -- confirmé que les 4 clés de
`HUB_EVENT_CATEGORY_META` correspondent EXACTEMENT aux 4 suffixes de
classe CSS). **Bug trouvé et corrigé pendant la vérification
croisée** : `.hub-timeline-marker-icon` référencée dans le JSX sans
règle CSS correspondante -- ajoutée.

**Non vérifié dans cet environnement, à confirmer en conditions
réelles** : rendu visuel complet (aucun navigateur disponible ici) --
en particulier la largeur de la colonne (260px, choisie sans pouvoir
juger de l'équilibre réel avec l'iframe active), la lisibilité des
info-bulles sur les marqueurs, et le choix de conception "liste
groupée" plutôt que "timeline proportionnelle" (facile à faire
évoluer plus tard si la vision plus visuelle/proportionnelle manque
en pratique).

**Chantier considéré terminé pour cette itération** -- les 3 étapes
annoncées (backend, émission, composant) sont livrées. D'éventuels
ajustements (largeur, granularités supplémentaires, style visuel)
resteront des retouches ciblées plutôt qu'un nouveau chantier à
recadrer entièrement.

### Timeline masquable (livraison #130)

Retouche ciblée demandée après coup, comme anticipé ci-dessus.
Nouveau bouton 🕒 dans la barre d'onglets (`TabShell.jsx`), à droite
(poussé par `margin-left: auto`, scrolle avec le reste de la barre en
cas de nombreux onglets ouverts -- même comportement que le bouton
"+" déjà là, pas une exception). État mémorisé PAR APPAREIL
(`localStorage`, clé `supervision-si:hub:timeline-visible`) -- même
principe que la mémorisation des onglets ouverts (livraison #112),
pas un réglage de compte synchronisé entre appareils. Visible par
défaut (comportement inchangé tant que la personne n'a jamais touché
au bouton) ; masquer libère l'espace pour `.hub-tab-content`
naturellement (flex: 1 sur l'unique enfant restant de
`.hub-tabshell-body`, aucun CSS supplémentaire nécessaire pour ça).

Vérifié réellement : syntaxe (`tsc --jsx`), accolades CSS/JSX
équilibrées, classe présente des deux côtés. Logique de chargement de
la préférence testée via Node -- rien de stocké (visible par défaut),
valeur stockée `true`/`false` respectée, JSON corrompu (retombe sur
visible, jamais une exception), valeur inattendue non strictement
`true` (`"1"`) traitée comme masquée plutôt qu'un `truthy` approximatif.
**Non vérifié dans cet environnement** : rendu visuel réel, aucun
navigateur disponible ici.

## Gestion d'URI externes (liens simples, sans SSO) — backlog #2 traité

Scope volontairement simple, décidé avec la personne (voir BACKLOG.md
#3 pour la piste SSO envisagée plus tard, mais explicitement jugée
prématurée) : une liste d'URI ajoutées par les administrateurs, avec
une visibilité par rôle, présentées dans le hub comme des applications
internes -- mais restant de simples liens externes (nouvel onglet du
navigateur), jamais de pont d'authentification.

**Backend** (`prefs-api`) : nouvelle table `external_links`
(`name`/`url`/`description`/`embeddable`/`allowed_roles`) + CRUD
complet (`GET/POST /external-links`, `PUT/DELETE /external-links/<id>`).
`allowed_roles` : JSON, liste de rôles applicatifs (mêmes clés que
`hub/src/lib.js`, `ROLE_LABELS`) -- liste VIDE ou absente = visible de
tout le monde, même défaut que les entrées internes du hub sans
condition de rôle (ex. portail tickets). AUCUNE vérification de rôle
côté serveur (même posture de confiance que le reste de cette API) :
`GET /external-links` renvoie TOUJOURS tout, le filtrage réel se fait
côté hub au moment de l'affichage. Rôles invalides filtrés
silencieusement (jamais stockés), `name`/`url` jamais vidés par une
mise à jour partielle avec une valeur blanche (retombe sur l'existant).

**Hub** : `buildFrontsList` (`hub/src/lib.js`) gagne un paramètre
`externalLinks` -- fusionne les liens (filtrés par rôle, même logique
`hasValue(roles, ...)` que les entrées internes) avec les fronts
internes existants, chaque entrée marquée `external: true` pour rester
distinguable. Chargés dans `App.jsx` AVANT les retours anticipés
(contrainte des règles de hooks React -- l'authentification n'étant
pas nécessaire pour cette donnée publique/non sensible, chargée dès le
montage). Nouvel écran d'administration `ExternalLinksAdminView`
(bouton 🔗 dans l'en-tête, admin uniquement) : tableau + formulaire
d'ajout/édition replié par défaut (même motif "+" que partout ailleurs
dans le projet), cases à cocher par rôle (dérivées de `ROLE_LABELS`,
jamais une liste dupliquée). Après création/édition/suppression,
rafraîchit la liste PARTAGÉE avec `App.jsx` (`onLinksChanged`) --
jamais besoin de changer d'onglet pour voir un nouveau lien apparaître
dans la grille du hub.

Vérifié réellement : `app.test_client()` (base isolée) -- validation
création (name/url requis), rôle invalide filtré silencieusement,
`allowed_roles` mal typé (jamais une exception, comportement de repli
sûr), mise à jour PARTIELLE (un seul champ modifié, les autres
inchangés), `name`/`url` jamais vidés par une valeur blanche, lien
introuvable (404), suppression idempotente (jamais une erreur sur un
id déjà supprimé), non-régression explicite sur tout le reste de
`prefs-api`. Scénario de migration dédié (base simulant l'ancien
schéma, préférence existante préservée, nouvelle table utilisable
immédiatement). `buildFrontsList` testé via Node **en important
directement le vrai fichier `lib.js`** (ESM natif, pas une
reproduction copiée) -- visibilité sans/avec `allowed_roles`, rôle
multiple (OR, pas AND), entrées malformées (jamais une exception),
et surtout **non-régression confirmée sur tous les fronts internes**
existants (mêmes ids générés avec les mêmes groupes qu'avant ce
chantier). Syntaxe (`tsc --jsx`, `ast.parse`), classes CSS toutes
présentes, setters cohérents, accolades JS/CSS équilibrées.

**Non vérifié dans cet environnement** : rendu visuel réel, aucun
navigateur disponible ici -- en particulier la mise en page du
formulaire replié/l'alignement du tableau, et le comportement de
`embeddable: true` sur un lien externe réel (l'iframe échouera
silencieusement -- espace vide -- si l'appli visée refuse en réalité
d'être embarquée malgré la case cochée ; aucun message d'erreur n'est
prévu pour ce cas précis, à surveiller en conditions réelles).

## Tuiles de la grille d'accueil — design plus compact

Demande explicite : description sur une seule ligne, lien "Ouvrir →"
retiré (redondant, toute la tuile est déjà cliquable), rembourrage
haut/bas divisé par 2, densité de la grille doublée, zone centrale
plus large.

- **Description** : `white-space: nowrap` + `text-overflow: ellipsis`
  -- coupée avec "…" plutôt qu'un retour à la ligne qui agrandirait
  la tuile de façon imprévisible.
- **"Ouvrir →"** : retiré du JSX ET de `hub.css` (`.hub-front-link`,
  plus aucune autre référence dans le projet).
- **Rembourrage** : `.hub-front-card` passe de 28px (hérité de
  `.hub-card`) à `14px 20px` -- haut/bas divisé par 2 comme demandé ;
  gauche/droite aussi réduit (28px -> 20px), pas demandé tel quel
  mais nécessaire en pratique pour laisser assez de place au texte
  dans une tuile désormais bien plus étroite (sans ça, même un titre
  correct aurait débordé sur 2-3 lignes de façon disgracieuse). Les
  titres LONGS peuvent toujours passer sur 2 lignes -- pas de
  troncature comme la description, tronquer un nom d'appli risquerait
  de rendre deux applis indiscernables l'une de l'autre.
- **Densité** : `grid-template-columns` minmax 260px -> 180px.
- **Zone centrale plus large** : `.hub-main` passe de `max-width: 900px`
  à `1400px`. **Choix assumé** sur l'interprétation "colonnes gauche/
  droite" de la demande : cet écran n'a AUJOURD'HUI aucune colonne
  latérale réelle, juste une marge vide au-delà de l'ancien plafond --
  plutôt qu'inventer des colonnes qui n'existent pas, le plafond a
  simplement été remonté largement. `width: 100%` (déjà présent) fait
  que ça ne change RIEN sur petit écran (le plafond ne s'applique
  jamais), et utilise bien plus d'espace sur grand écran -- l'effet
  visuel demandé. Si de vraies colonnes latérales apparaissent un
  jour sur cet écran, ce plafond mériterait d'être revu.

Vérifié réellement : syntaxe (`tsc --jsx`), accolades CSS équilibrées,
`hub-front-link` confirmé absent des deux fichiers (JSX et CSS) après
retrait, ordre de cascade CSS vérifié (`.hub-front-card` après
`.hub-card` dans le fichier -- la spécificité égale se départage par
l'ordre, les nouvelles valeurs remplacent bien celles héritées).
**Non vérifié dans cet environnement** : rendu visuel réel, aucun
navigateur disponible ici -- en particulier le nombre de colonnes
réellement obtenu à différentes largeurs d'écran, et la lisibilité
des titres longs sur 2 lignes à 180px de large.

## Personnalisation de l'accueil (chantier en cours, par étapes)

Demande large, cadrée avant de coder (même esprit que les autres gros
chantiers du projet) : masquer/afficher chaque tuile, les réorganiser
en position et en groupes ("cadres" titrés), avec à la fois des
contrôles explicites (menu déroulant + flèches, choisi par la
personne pour rester fiable/vérifiable) ET du glisser-déposer en
couche additionnelle (beaucoup d'utilisateurs Mac). Le tout **par
utilisateur** (pas un réglage admin comme `external_links`).

### Étape 1 (pied de page) livrée en #132

Restructuration de l'écran d'accueil : la grille de tuiles défile
désormais **indépendamment** dans sa propre zone
(`.hub-grid-scroll`), et un pied de page fixe (`.hub-footer`) reste
toujours en bas de l'écran, masquable via un bouton toujours visible
(même replié, le bouton reste atteignable). État mémorisé PAR
APPAREIL (`localStorage`, clé `supervision-si:hub:footer-note-visible`)
-- même principe que la timeline masquable (livraison #130).

**Scopé volontairement à CET écran uniquement** -- `.hub-shell`
lui-même n'a pas été touché (reste en flux de page normal pour les
autres vues : paramètres, historique, liens externes, coquille à
onglets). `.hub-grid-view` calcule sa propre hauteur en autonomie
(`calc(100vh - 60px)`, même formule déjà utilisée par
`.hub-tabshell`, hauteur de `.hub-header` déjà validée là-bas) plutôt
que de capper `.hub-shell` globalement -- un changement plus large
aurait risqué de faire déborder/couper le contenu des autres écrans,
qui n'ont pas ce défilement interne et n'ont jamais été vérifiés avec.

Vérifié réellement : syntaxe (`tsc --jsx`), accolades CSS/JSX
équilibrées, `.hub-note` confirmée absente des deux fichiers après
remplacement, toutes les nouvelles classes présentes des deux côtés.
Logique de chargement de la préférence testée via Node -- défaut
visible, valeur stockée respectée, JSON corrompu (jamais une
exception). **Non vérifié dans cet environnement** : rendu visuel
réel (aucun navigateur disponible ici), en particulier si
`calc(100vh - 60px)` correspond exactement à la vraie hauteur de
`.hub-header` (approximation à partir du CSS, jamais mesurée en
conditions réelles).

### Étape 2 (modèle de données + fusion + rendu en cadres) livrée en #133

Nouveau fichier `hub/src/hubLayoutLib.js` -- logique PURE (jamais
d'accès réseau), séparée de l'I/O (`fetchHubLayout`/`saveHubLayout`,
ajoutées à `settingsClient.js`). `hubLayout` stocké dans le blob
`/preferences` déjà existant côté `prefs-api` -- **aucun changement
de schéma nécessaire**, `PUT /preferences` fait déjà une fusion
superficielle côté serveur (voir `prefs-api/app.py`,
`put_preferences`) qui préserve les autres clés (`theme`, etc.) sans
y toucher, explicitement pensée pour ce genre d'extension future.

Forme : `{ groups: [{id, title, order}], tiles: { [frontId]:
{groupId, order, hidden} } }`. `applyHubLayout(fronts, hubLayout)`
regroupe/trie/filtre pour l'affichage -- DÉFENSIF sur toute forme
malformée (absent, `groupId` fantôme pointant vers un cadre supprimé,
types corrompus) : retombe TOUJOURS sur un affichage sensé plutôt
qu'une exception qui viderait la grille. **Choix assumé** : un cadre
sans aucune tuile visible n'est pas affiché sur l'accueil (pas de
cadre vide qui ferait du bruit visuel) -- l'écran de personnalisation
(étape 3, pas encore livrée) devra lire `hubLayout.groups`
DIRECTEMENT pour permettre de gérer un cadre encore vide.

Côté `App.jsx` : `hubLayout` chargé AVANT les retours anticipés (même
contrainte des règles de hooks que `externalLinks`), mais dépend du
login -- lu directement depuis `auth.user?.profile` (jamais la
variable `profile` dérivée plus bas dans le composant, pas encore
fiable à ce stade). La grille se rend désormais en tuiles sans cadre
(comportement actuel, inchangé par défaut) suivies des cadres
créés par l'utilisateur, chacun avec son titre en ligne haute --
partagent le même balisage de tuile (`renderFrontTile`, factorisé,
jamais deux copies à faire dériver l'une de l'autre).

**Aucun changement de comportement visible pour l'instant** -- sans
l'écran de personnalisation (étape 3), `hubLayout` reste toujours
vide pour tout le monde, `applyHubLayout` retombe systématiquement
sur "tout en tuiles sans cadre, ordre naturel" (vérifié explicitement
par les tests). Intégration sûre et inerte en attendant l'écran qui
permettra réellement de créer des cadres.

Vérifié réellement : syntaxe (`tsc --jsx`) sur les 4 fichiers touchés,
accolades CSS/JSX équilibrées, classes présentes des deux côtés,
setters cohérents (`setHubLayout` passé directement à `.then()`, même
motif déjà établi que `setExternalLinks`). `applyHubLayout` testée en
profondeur via Node (import direct du vrai fichier, ESM natif) -- 17
vérifications : comportement par défaut inchangé (hubLayout absent/
null), masquage d'une tuile, regroupement avec tri par ordre DANS un
cadre, plusieurs cadres triés par leur PROPRE ordre (pas l'ordre de
déclaration), **groupId fantôme** (cadre supprimé entretemps, retombe
en sans-cadre plutôt que perdre la tuile), **cadre devenu vide**
(toutes ses tuiles masquées, absent du résultat), entrées `fronts`
malformées, `hubLayout.groups`/`hubLayout.tiles` corrompus (mauvais
type) -- toujours un repli propre, jamais une exception.

### Étape 3 (écran "Personnaliser l'accueil" + glisser-déposer) livrée en #140

Livre les 2 points qui restaient d'un coup -- l'écran ET le
glisser-déposer partagent la même infrastructure, les séparer aurait
été artificiel. Nouveau fichier `hub/src/PersonalizeHomeView.jsx`,
accessible à TOUT utilisateur authentifié via un nouveau bouton 🎨
dans l'en-tête (pas réservé aux administrateurs, contrairement à
"Liens externes" 🔗).

**Nouvelles mutations pures** ajoutées à `hub/src/hubLayoutLib.js`
(`createGroup`, `renameGroup`, `deleteGroup`, `setTileGroup`,
`setTileHidden`, `moveTile`, `moveGroup`) -- chacune prend le
`hubLayout` actuel et renvoie un NOUVEAU `hubLayout`, jamais de
mutation en place. Piège identifié et traité explicitement :
`moveTile`/`setTileGroup`/`setTileHidden` doivent JAMAIS réinitialiser
silencieusement la position d'une tuile jamais personnalisée --
`getEffectiveTileState` (interne, même repli qu'`applyHubLayout`)
résout son état RÉEL (position naturelle dans `fronts` si jamais
touchée) avant toute mutation, et `moveTile` reconstruit le panier
ENTIER (tuiles personnalisées ET pas encore touchées) pour trouver la
bonne voisine à échanger.

**Contrôles EXPLICITES** (flèches ▲▼, menu déroulant "Cadre",
case à cocher "Visible") restent la méthode fiable pour TOUT --
**glisser-déposer** (API HTML5 native, `draggable`/`dragover`/`drop`)
en couche ADDITIONNELLE, réservé au cas le plus courant (assigner une
tuile à un cadre en la glissant dessus, ou vers "◻ Sans cadre" pour
l'en retirer) -- jamais un remplacement, jamais un second mécanisme
séparé à maintenir : les deux appellent EXACTEMENT les mêmes
fonctions de mutation (`setTileGroup`). Chaque action ENREGISTRE
IMMÉDIATEMENT (`saveHubLayout`, déjà existant depuis l'étape 2),
mise à jour optimiste avant même la confirmation réseau -- pas de
bouton "Enregistrer" séparé à penser à cliquer.

Vérifié réellement : les 7 mutations testées en profondeur via Node
(import direct des vrais fichiers) -- 21 vérifications, dont les cas
les plus subtils : `moveTile` fonctionne MÊME sur des tuiles jamais
personnalisées (ordre naturel reconstruit correctement, pas seulement
parmi les tuiles déjà suivies), `deleteGroup` ne perd JAMAIS de
tuiles (repassent sans cadre), `setTileHidden`/`setTileGroup`
préservent l'état existant d'une tuile qu'on modifie pour la première
fois (jamais réinitialisé), déjà au bord d'un panier/de la liste des
cadres -- `hubLayout` renvoyé inchangé, jamais une exception. Un vrai
bug de PORTÉE trouvé et corrigé PENDANT l'écriture des tests eux-mêmes
(pas dans le code) -- réutilisation accidentelle d'un `groupId` issu
d'un autre `hubLayout` que celui testé, corrigé en isolant chaque
scénario. Syntaxe (`tsc --jsx`) sur les 3 fichiers touchés, accolades
CSS/JSX équilibrées sur 4 fichiers, toutes les classes CSS et
variables de thème présentes/réelles des deux côtés, bouton 🎨
confirmé HORS du bloc `isAdmin(groups) &&` (accessible à tous, comme
demandé).

**Non vérifié dans cet environnement** : rendu visuel réel (aucun
navigateur ici), et en particulier le glisser-déposer lui-même --
l'API HTML5 native (`dataTransfer`, `onDragOver`/`onDrop`) n'a jamais
pu être exercée par un vrai geste de souris/tactile, seule la LOGIQUE
qu'elle déclenche (`setTileGroup`, déjà testée) a pu l'être. Si le
glisser-déposer a un souci visuel/tactile une fois testé, les
contrôles explicites (menu déroulant, flèches) restent pleinement
fonctionnels en repli -- c'est précisément pourquoi ils n'ont jamais
été remplacés.

## Horloge permanente navigateur/serveur (livraison #137)

Demandé explicitement : "tout semble désynchronisé sous docker" --
affichage permanent (pas masquable, contrairement au pied de page de
la grille, étape 1 ci-dessus) en bas à droite, à côté du badge de
version (`.status-badges`, conteneur commun -- l'ancien
`.version-badge` autonome en est devenu un simple enfant flex, sans
changement de comportement pour lui).

`prefs-api` (`/health`) renvoie désormais `server_time` (epoch Unix,
`time.time()`) en plus de `status`. Choix assumé : comparaison contre
**une seule** référence serveur (prefs-api, déjà utilisé ailleurs par
le hub -- aucune nouvelle dépendance réseau), pas les ~15 APIs. Utile
pour le cas le plus probable (horloge du démon/VM Docker désynchronisée
de celle du navigateur, ce que partagent alors TOUS les conteneurs
Linux -- ils lisent la même horloge noyau que l'hôte, jamais chacun la
leur) ; comparer plusieurs services resterait pertinent pour un
scénario de dérive PROPRE À UN conteneur (plus rare), pas fait ici,
facile à étendre si besoin en ajoutant `server_time` à d'autres
`/health`.

Horloge navigateur : tique chaque seconde. Heure serveur : sondée
toutes les 30s (pas chaque seconde, inutile de solliciter prefs-api à
cette fréquence pour un simple repère visuel) puis EXTRAPOLÉE entre
deux sondages (avance elle aussi chaque seconde à l'affichage, pas de
saut visible toutes les 30s).

**Seuil relevé à 15 minutes (livraison #255)** -- demandé
explicitement, la personne a constaté que la barre affichait
systématiquement deux horloges quasi identiques ("16:35:44 ·
16:35:44") : "quand les valeurs sont proches pas besoin d'afficher
les 2, mettons une dérive acceptable de 15mn". Corrigé -- SOUS ce
seuil, une SEULE horloge affichée (les deux sont considérées "la
même heure" pour un usage pratique) ; la seconde horloge et l'écart
(⚠ +Xs / -Xs) ne s'affichent QUE si le seuil est dépassé, un vrai
signal plutôt qu'un bruit visuel sur deux valeurs quasi identiques.
L'ancien seuil de 3s (#137) rendait la seconde horloge visible en
PERMANENCE (un aller-retour réseau normal dépasse presque toujours
3s), jamais l'effet recherché à l'origine. L'info-bulle (survol)
continue de montrer les deux valeurs même quand synchronisées, pour
qui voudrait vérifier en détail.

Vérifié réellement : `/health` testé avec `app.test_client()`
(`server_time` bien présent, type numérique). Logique de calcul
(dérive, extrapolation) testée via Node -- synchro parfaite,
avance/retard de 10s détectés dans le bon sens, dérive de 2s sous le
seuil PAS signalée (évite le bruit), extrapolation entre deux
sondages vérifiée précisément (avance de 20s sans nouveau fetch),
absence d'heure serveur (échec réseau) -> jamais `NaN` ni une
exception. **Nouveau seuil (#255) testé explicitement** : 899s (juste
sous 15mn) -> une seule horloge, 900s pile -> désynchronisé (les
deux), 1h -> désynchronisé, valeur `null` gérée sans exception.
Syntaxe (`tsc --jsx`), accolades CSS/JSX équilibrées, classes et
variables CSS toutes présentes/réelles. **Non vérifié dans cet
environnement** : rendu visuel réel, et surtout la VRAIE
désynchronisation rapportée par la personne -- ce correctif donne un
outil pour la CONSTATER clairement, pas une garantie qu'il en révèle
la cause exacte (horloge VM Docker vs hôte reste l'hypothèse la plus
probable, jamais confirmée depuis cet environnement).

## Indicateurs de présence Keycloak/gateway/vault-standalone (livraison #138)

Demandé explicitement, à côté de l'horloge et de la version (pied de
page, `.status-badges`) -- deux points colorés, même vocabulaire
visuel que les "feux tricolores" de `launcher` (voir
`docker-compose.yml`, service `launcher`).

**Choix assumé, expliqué dans le code** : "Keycloak" et "gateway"
partagent EXACTEMENT le même indicateur, pas deux points qui
clignoteraient toujours pareil sans le dire -- `tls-proxy` est un
simple relais nginx sans logique applicative propre à sonder, et sa
disponibilité est de toute façon prouvée par le simple fait que le
hub ait pu se charger (il passe forcément par lui). Vérifier
séparément n'ajouterait aucune information réelle.

**Vérification faite CÔTÉ SERVEUR** (`prefs-api`, nouvelle route
`GET /status`), pas depuis le navigateur -- évite ENTIÈREMENT les
soucis CORS et de certificat auto-signé non approuvé par CE
navigateur pour `vault-standalone` (stack totalement isolé, son
propre certificat, jamais partagé). `vault-standalone` sondé via son
port PUBLIÉ sur l'hôte (comme le ferait un navigateur), jamais le
réseau Docker interne -- aucun autre chemin ne l'atteint depuis
`prefs-api`, réseaux Docker séparés. `verify_tls=False` pour cette
sonde précisément (jamais pour un appel qui échangerait de vraies
données) -- son certificat auto-signé propre n'est pas forcément dans
la chaîne de confiance de ce conteneur.

**Piège évité** : `HOST_IP` (déjà utilisé ailleurs pour composer des
URLs) n'était jamais exposé tel quel dans l'environnement de
`prefs-api` -- ajouté explicitement, avec un repli EXPLICITEMENT
DIFFÉRENT de celui utilisé côté navigateur. Côté navigateur,
`localhost` par défaut a un sens (la machine de la personne). Côté
conteneur, `localhost` désignerait le conteneur LUI-MÊME, jamais la
machine hôte -- `VAULT_STANDALONE_HOST_IP` (si renseignée) puis
`HOST_IP` (repli), `localhost` en tout dernier recours uniquement.

Les deux sondes (`keycloak`, `vault_standalone`) tournent en
PARALLÈLE (`ThreadPoolExecutor`, stdlib) -- jamais l'une après
l'autre, sans quoi un service injoignable ajouterait bêtement son
délai d'attente complet (jusqu'à 3s) à celui du suivant. Sondage
front toutes les 30s (même cadence que l'horloge, effet séparé --
pas fusionnées dans le même appel, `/health` reste un contrôle
minimal rapide, `/status` fait des appels réseau externes plus
coûteux).

Vérifié réellement : `/status` testé avec `app.test_client()` --
répond 200 même quand rien n'est réellement joignable (repli propre,
jamais une exception), `gateway` reflète bien exactement `keycloak`,
les deux sondes tournent bien en parallèle (temps mesuré très
inférieur à la somme des deux délais max). `_check_reachable()`
testée contre de VRAIS serveurs HTTP locaux (`http.server`) : 200 ->
`True`, 503 -> `False` (erreur serveur, pas "présent et sain"), port
fermé -> `False` proprement, timeout très court -> toujours un
booléen, jamais un blocage. Syntaxe (`tsc --jsx`, `ast.parse`),
accolades CSS/JSX équilibrées, classes et variables CSS toutes
présentes/réelles. **Non vérifié dans cet environnement** : rendu
visuel réel, et la sonde `vault_standalone` contre une VRAIE instance
`vault-standalone` (jamais démarrée ici, aucun Docker disponible) --
en particulier si son certificat auto-signé pose un souci différent
de celui anticipé.

## Gestionnaire de logs (livraison #139)

Demandé explicitement ("un excellent moyen pour optimiser en
déploiement et en fonctionnement") -- venu en pleine panne réelle
(500 systématique du 01/09, toujours en cours d'investigation à cette
livraison), ironie du calendrier plutôt qu'un choix de moment. Trois
présentations, toutes validées par la personne, construites et
livrées dans l'ordre demandé : tableau de bord, par service, vue
combinée -- simples sous-onglets d'un même écran (même motif que
`HistoryView`), pas trois écrans séparés. Nouveau bouton 📋 dans
l'en-tête, accessible à tout utilisateur authentifié.

**Prérequis traité en premier** : sur les 15 APIs routées, 4
n'avaient pas encore l'endpoint `/logs` (`dba-api`, `ldap-admin-api`,
`prefs-api`, `vault-api`) -- ajouté en reprenant EXACTEMENT le motif
déjà établi par `api/app.py` (tampon circulaire en mémoire, seuil
WARNING par défaut, `SERVICE_NAME` suivant la convention déjà en
place -- nom du service Docker + `-api`). Sans ce prérequis, le menu
déroulant "par service" aurait eu des trous.

**Chemins RELATIFS** (`/api/<segment>/logs`), pas d'URL absolue par
service -- le hub tourne déjà sur la MÊME origine que les 15 APIs
(même `tls-proxy`), inutile de dupliquer 13 nouvelles variables
`VITE_*_API_BASE_URL` alors que le navigateur résout déjà
correctement un chemin relatif contre l'origine courante. Nouveaux
fichiers : `hub/src/logsLib.js` (logique PURE -- liste des 15
services, fusion multi-services triée par horodatage, résumé par
service) et `hub/src/logsClient.js` (I/O, sondage des 15 services EN
PARALLÈLE via `Promise.all`, jamais l'un après l'autre). "Tableau de
bord" et "vue combinée" partagent la MÊME requête réseau sous-jacente
-- jamais deux sondages séparés pour la même donnée.

**Défensif de bout en bout, par nécessité** : cet outil doit justement
rester utilisable QUAND des services sont en panne -- un service
injoignable (`undefined` dans le résultat) est explicitement distingué
d'un service sain sans erreur récente (`reachable: false` vs
`total: 0`), jamais confondu. L'ordre du tableau de bord suit
`LOG_SERVICES`, jamais réordonné par le nombre d'erreurs -- un
service qui redevient sain ne doit pas sauter de position.

Vérifié réellement : les 4 nouveaux endpoints `/logs` -- syntaxe
Python sur les 4 fichiers, motif testé de façon ISOLÉE (WARNING
capturé avec formatage correct, INFO bien filtré sous le seuil,
`limit=0` sans erreur) car `dba-api`/`vault-api` n'ont pas pu être
importés directement ici (`psycopg2` absent, pas de vraie base
SQLite -- limites de cet environnement, sans rapport avec l'ajout
lui-même) ; `ldap-admin-api`/`prefs-api` testés directement avec
succès. `logsLib.js` testée en profondeur via Node (import du vrai
fichier) -- fusion triée, résumé avec distinction
injoignable/sans-erreur, ordre stable, toutes les entrées malformées
gérées sans exception. `logsClient.js` testée avec un vrai `fetch`
simulé -- parallélisme RÉELLEMENT mesuré (15 appels concurrents,
~12ms au lieu de ~150ms si séquentiel), service en panne isolé sans
casser les 14 autres. Syntaxe (`tsc --jsx`) sur les 4 fichiers JS,
accolades équilibrées sur les 5 fichiers touchés, toutes les classes
CSS et variables de thème présentes/réelles des deux côtés.

**Non vérifié dans cet environnement** : rendu visuel réel (aucun
navigateur ici), et surtout le comportement contre les VRAIS 15
services en conditions réelles -- en particulier utile pour
diagnostiquer la panne 500 en cours au moment de cette livraison,
pas encore confirmé si cet outil lui-même fonctionnera correctement
tant que cette panne n'est pas résolue (le gestionnaire de logs
dépend des mêmes 15 APIs qui sont actuellement affectées).

## Retours de test #139/#140 (livraison #141)

Deux retours après le premier vrai test du gestionnaire de logs.

**Écran trop étroit sur grand écran** : `.hub-settings` (partagé avec
Paramètres/Historique/Liens externes/Personnaliser) plafonne à 1400px
-- suffisant pour un formulaire, pas pour un tableau dense de 15
lignes sur un grand écran. Nouvelle classe `.hub-settings-wide`
(1800px), composée avec `.hub-settings` (pas un remplacement) et
réservée à CET écran uniquement -- les écrans formulaire n'ont pas ce
besoin et deviendraient juste inconfortablement étirés.

**Le hub ne journalisait pas ses propres erreurs de liaison** : quand
un indicateur de présence bascule, ou qu'un service devient
injoignable depuis le gestionnaire de logs lui-même, rien n'en gardait
trace -- signalé comme "utile actuellement" pendant un test où tout
apparaissait injoignable sans savoir depuis quand ni pourquoi.

Nouvelle route `POST /hub-log` sur `prefs-api` -- réutilise le MÊME
tampon que `/logs` (pas un 16e service séparé, `prefs-api` est déjà
la "base arrière" du hub pour tout le reste). Nouveau
`hub/src/hubLogClient.js` : `logPresenceTransitions` compare l'état
précédent au nouveau et journalise UNE ligne **par transition
seulement** (jamais à chaque sondage) -- sans ça, un vrai incident
prolongé (tous les services injoignables pendant 10 minutes, sondage
toutes les 15-30s) remplirait le tampon de 200 entrées de messages
identiques en quelques minutes, chassant tout le reste, y compris les
vraies erreurs applicatives qu'on cherche justement à voir. Câblé à
DEUX endroits : `App.jsx` (indicateurs de présence Keycloak/gateway,
vault-standalone) et `LogsManagerView.jsx` (accès aux 15 APIs, à la
fois "tableau de bord"/"vue combinée" -- ref partagé, 15 clés
suivies -- et "par service" -- ref SÉPARÉ, pour ne jamais perdre le
suivi des 14 autres services au changement d'onglet). Chaque endroit
utilise un `useRef` (jamais un second `useState`) : doit être lu de
façon SYNCHRONE au sondage suivant pour détecter la transition,
un état React se lirait "en retard" (rendu suivant).

Vérifié réellement : `/hub-log` testée avec `app.test_client()` --
niveau WARNING/ERROR bien capturés, préfixe `[hub]` présent
(distingue une entrée venant du navigateur des warnings internes de
`prefs-api` lui-même), message vide → 400 sans rien ajouter au
tampon, corps non-JSON → 400 proprement, jamais une exception 500.
`logPresenceTransitions` testée en profondeur via Node -- premier
sondage sans previous → rien journalisé (l'état de départ n'est pas
une transition), aucun changement → rien journalisé, un seul service
qui bascule → une seule ligne, 15 qui basculent en même temps →
exactement 15 lignes, **état stable rejoué plusieurs fois de suite
(même si tout reste injoignable) → aucune ligne supplémentaire**
(le point qui comptait le plus à vérifier). Syntaxe (`tsc --jsx`,
`ast.parse`) sur tous les fichiers touchés, accolades équilibrées,
classe CSS présente des deux côtés.

**Non vérifié dans cet environnement** : rendu visuel réel de l'écran
élargi, et surtout le comportement RÉEL en conditions de panne
prolongée -- la logique anti-bruit est testée unitairement mais
jamais observée sur un vrai flux d'événements réseau réel.

## Sources de logs externes -- push API (livraison #142, étape 1/4)

Backlog "suivre des logs de toutes sortes" (fichier plat, rsyslog/UDP,
URL, push) -- traité dans l'ordre choisi par la personne, en commençant
par le push, le plus simple, prolongeant `/hub-log` déjà en place.

**Nouvelles routes sur `prefs-api`** : `POST /push-log` (dépôt
générique, body `{source, level?, message, logger?}`), `GET
/push-log/sources` (sources connues), `GET /push-log/<source>` (même
forme que `GET /logs`, `{service, entries}`). Un tampon circulaire
PAR SOURCE, en mémoire, borné (`PUSHED_LOG_BUFFER_SIZE`, défaut 200) --
même philosophie que les 15 services internes (outil de diagnostic à
chaud, pas un historique long terme, perdu au redémarrage). Une
source n'est PAS déclarée à l'avance : elle apparaît implicitement dès
son premier push, sous le nom choisi par l'émetteur -- distinct de
`/hub-log` (réservé au hub lui-même, message toujours préfixé `[hub]`,
tampon PARTAGÉ avec les warnings internes de `prefs-api`) qui reste
inchangé à côté.

**Généralisation nécessaire côté hub** : `LOG_SERVICES` (15 services
fixes, connus à l'avance) ne suffit plus -- `mergeLogEntries`/
`summarizeLogEntries` (`hub/src/logsLib.js`) et `fetchAllServiceLogs`
(`hub/src/logsClient.js`) prennent désormais la liste de services en
PARAMÈTRE OBLIGATOIRE plutôt qu'un repli implicite sur `LOG_SERVICES`
-- pour ne jamais oublier silencieusement les sources externes dans
un appel. `LogsManagerView.jsx` construit la liste COMBINÉE (15 fixes
+ sources découvertes via `GET /push-log/sources`, sondées séparément
toutes les 30s) et l'utilise PARTOUT (menu déroulant "par service",
tableau de bord, vue combinée) -- une source externe se comporte
EXACTEMENT comme un service interne dans les 3 présentations, aucune
branche spéciale. `id` préfixé `push:` (jamais de collision possible
avec les 15 id fixes, même si une source externe portait par malheur
le même nom qu'un service interne).

**Limite connue, acceptée** : la liste des sources externes est
re-sondée toutes les 30s et produit une NOUVELLE référence à chaque
fois (même si son contenu est identique) -- ça redéclenche l'effet de
l'onglet "par service" un peu plus souvent que strictement
nécessaire quand cet onglet est actif. Sans conséquence fonctionnelle
(juste un rafraîchissement un peu plus fréquent que les 15s prévus),
pas corrigé pour l'instant -- corriger proprement demanderait de
comparer le CONTENU de la liste plutôt que sa référence, complexité
pas justifiée pour ce gain.

Vérifié réellement : les 3 nouvelles routes testées avec
`app.test_client()` -- création implicite d'une source au premier
push, isolation confirmée entre plusieurs sources ET entre les
sources externes et les warnings internes de `prefs-api` (jamais
mélangés), défensifs (source/message vide, source trop longue, limite
excessive plafonnée). Généralisation testée en profondeur via Node --
non-régression complète sur les 15 services fixes (résultats
identiques à avant, juste avec le paramètre explicite), source
externe correctement intégrée dans la fusion/le résumé/le sondage
parallèle. Syntaxe (`tsc --jsx`, `ast.parse`), accolades équilibrées,
setters cohérents.

**Non vérifié dans cet environnement** : rendu visuel réel, et surtout
le VRAI usage -- personne n'a encore poussé de log externe réel
(script cron, autre outil) contre une instance réellement démarrée.

### Étapes restantes (backlog "logs de toutes sortes")

2. **URL** -- sondage périodique côté serveur (`prefs-api`) d'une
   adresse HTTP, format de réponse à définir.
3. **Fichier plat** (`/var/log/...`) -- montage de volume Docker
   explicite + lecture incrémentale (position suivie, rotation gérée).
4. **rsyslog distant/UDP** -- le plus lourd des quatre : un service
   d'écoute réseau à part entière (port dédié à documenter dans
   `.env`), pas une route Flask classique.

## Couverture LOG_SERVICES complétée (livraison #351)

En reprenant le backlog item 8 ("archiver TOUS les logs"), découverte
en creusant : **`LOG_SERVICES` (`hub/src/logsLib.js`) avait pris du
retard depuis longtemps** -- seuls `glpi`/`nebula` avaient été
ajoutés au fil des livraisons (#192/#196), mais 12 services créés
PLUS RÉCEMMENT n'avaient JAMAIS rejoint cette liste : architecture,
classifier, memory, netprobe, network-agent, relations, retro,
rights, snmp, tasks, vigilance, backup-restore. Conséquence RÉELLE,
pas seulement théorique : leurs logs étaient invisibles dans le
gestionnaire de logs du hub depuis leur création respective --
aucune ligne d'erreur remontée nulle part pour ces services dans
cette vue, silencieusement.

Ajoutés (voir `hub/src/logsLib.js`, ordre alphabétique par libellé
préservé). `pixel-grid-bridge` et `vault-admin-api` restent EXCLUS de
cette liste précise, volontairement -- aucun chemin HTTP atteignable
depuis le navigateur pour eux (le premier est un script en
arrière-plan sans serveur HTTP, le second n'est jamais routé par la
passerelle publique) -- couverts côté archivage persistant
uniquement (voir `prefs-api/log_archiver.py`, qui lit Memcached
directement).

**Découverte connexe, plus large** : ce même recoupement a révélé
DEUX systèmes d'archivage persistant PARALLÈLES pour ce même tampon
de logs -- `prefs-api/log_archiver.py` (livraison #198, antérieur) ET
`memory-api` (livraison #259, plus complet -- repopulation,
statistiques, garbage collector). **Fusionnés en #353** (demandé
explicitement par la personne) -- `log_archiver.py` supprimé,
`memory-api` reste la SEULE source d'archivage persistant. Voir
`memory/README.md` pour le détail complet de la fusion (l'écart de
fonctionnalité trouvé et comblé avant suppression, la refonte
since/until).

**❌ ERREUR CORRIGÉE (2026-09-05)** : cette section affirmait à tort
"aucune interface hub ne consulte l'historique persisté" -- en
vérifiant SEULEMENT `LogsManagerView.jsx` (qui, lui, n'interroge
effectivement que le tampon Memcached en direct) sans vérifier
`MemoryView.jsx`, qui appelle déjà `/stats`/`/services`/`/entries`
(`memory-api`) depuis la création même de cette tuile (#259) -- voir
`hub/src/memoryClient.js`, filtres service/niveau déjà en place.
Backlog item 52 corrigé dans le même sens.

## Aide du hub (livraison #143)

Demandé explicitement : "une aide qui s'enrichit des readme et des
exemples". Nouveau bouton ❓ dans l'en-tête, écran à deux colonnes
(liste filtrable des documents + contenu rendu) -- même mécanisme de
rendu markdown que "Historique du projet" (`parseMarkdown`/
`MarkdownDocument`, déjà en place pour `CHANGELOG.md`/`BACKLOG.md`).

**"S'enrichit" au sens littéral** : `GET /docs` (nouvelle route sur
`prefs-api`) redécouvre EN DIRECT, à chaque appel, tous les fichiers
nommés EXACTEMENT `README.md` dans le dépôt monté -- un nouveau
document ajouté n'importe où (nouveau module, nouvelle sous-section)
apparaît dans l'aide sans le moindre code à modifier ici. **"Les
exemples"** : déjà abondamment présents DANS les README existants
(commandes curl, extraits JSON, procédures pas à pas) -- les afficher
couvre les deux demandes à la fois, pas de base d'exemples séparée à
maintenir en parallèle qui risquerait de diverger du code réel.

**Point de sécurité important, traité avec le plus grand soin** :
pour permettre cette découverte automatique, `prefs-api` monte
désormais la RACINE ENTIÈRE du dépôt en lecture seule
(`docker-compose.yml`, chemin `/project-root`, séparé de `/data` qui
reste writable pour `prefs.db`) -- ce qui inclut potentiellement
`.env`, les clés PKI, les realms Keycloak exportés (avec de vrais
secrets dedans). La SEULE protection entre "monté en lecture" et
"lisible depuis cette API" est une liste blanche stricte côté serveur
(`prefs-api/app.py`, `_discover_readmes`/`get_doc`) : (1) seuls les
fichiers nommés EXACTEMENT `README.md` sont jamais découverts --
aucun secret de ce projet ne porte ce nom ; (2) des dossiers connus
pour contenir du contenu généré/sensible (`.git`, `node_modules`,
`data`, `pki/ca`, `pki/server`, `keycloak/import`, `keycloak/backup`,
les dossiers `generated/`...) sont explicitement exclus de la
découverte, en défense en profondeur -- pas la protection
principale ; (3) toute lecture revalide le chemin demandé contre une
REDÉCOUVERTE EN DIRECT (jamais une liste mise en cache qui pourrait
diverger), PLUS une normalisation qui refuse tout chemin sortant de
la racine montée même si la liste blanche avait un trou quelque part.

Vérifié réellement, avec un soin particulier vu les enjeux : arborescence
de test FICTIVE construite exprès (README à plusieurs profondeurs +
`.env`/clés PKI factices/realm exporté avec un faux secret dedans) --
confirmé que SEULS les 3 vrais README sont découverts, que `node_modules`
est bien exclu même quand il contient un `README.md` réel, que toute
LECTURE DIRECTE d'un fichier sensible (même en le nommant explicitement
dans l'URL) échoue en 404, ET que 3 variantes de tentative de traversée
de chemin (`../`, multi-niveaux, encodée en `%2e%2e%2f`) échouent
proprement. Rejoué ENSUITE contre la VRAIE arborescence du projet :
exactement 23 README découverts, zéro suspect, lecture réelle de
`hub/README.md` confirmée (81 970 caractères). Syntaxe (`tsc --jsx`,
`ast.parse`, YAML), accolades équilibrées, classes CSS présentes des
deux côtés.

**Non vérifié dans cet environnement** : rendu visuel réel (aucun
navigateur ici), et le comportement du montage Docker lui-même en
conditions réelles (jamais de vrai conteneur démarré ici).

## Onglet Analyse de schémas (livraison #156)

Interface pour `schema-analyzer-api` (#151-#154, jusqu'ici accessible
seulement via `curl`) -- `SchemaAnalyzerView.jsx`, bouton d'en-tête
🧬. S'appuie sur `dba-api` en LECTURE SEULE (juste lister les
connexions existantes pour le sélecteur, `DBA_API_BASE_URL`) -- créer
ou modifier une connexion reste le rôle de l'onglet DBA (portail
séparé), jamais dupliqué ici.

Trois sous-onglets une fois une analyse lancée (même motif que
`LogsManagerView` -- sous-onglets d'un même écran, pas des écrans
séparés) :
- **Schéma** -- tables/colonnes (repliables) + colonnes-listes
  détectées, avec la table cible devinée si `list_detector.py` en a
  trouvé une.
- **Relations** -- l'éditeur : bouton "Importer les propositions
  détectées" (`POST /relations/import-proposals`), tableau de toutes
  les relations avec boutons Confirmer/Rejeter/Supprimer, formulaire
  d'ajout manuel. Les propositions ne sont JAMAIS appliquées sans
  validation explicite.
- **Export** -- liens de téléchargement direct (`<a href>`, pas un
  `fetch` chargé en mémoire) vers `GET /relations/graph` en JSON et
  en XML -- relations CONFIRMÉES uniquement.

**Vérifié réellement** : `schemaAnalyzerClient.js` testé avec un
`fetch` simulé en Node (bonnes URLs/méthodes/corps de requête pour
chaque fonction, préservation du message d'erreur RÉEL renvoyé par le
serveur plutôt qu'un message générique, listes vides plutôt qu'une
exception en cas d'échec réseau). Structure JSX de
`SchemaAnalyzerView.jsx` vérifiée par un contrôle d'équilibre
accolades/parenthèses/balises (après correction d'un faux positif dû
aux flèches `=>` des gestionnaires d'événements, confondues avec une
fin de balise par une première version du script de vérification).

**Non vérifié dans cet environnement** : compilation Vite réelle
(`npm install` bloqué ici, réseau restreint -- même limite que
`pip`/`pymemcache` ailleurs dans ce projet) ni rendu visuel dans un
vrai navigateur -- seulement une vérification structurelle du JSX,
pas une compilation.

## GED promue en tuile de front (livraison #172)

Demandé explicitement : "GED devrait être au même niveau que les
applis du hub" -- première étape volontairement simple ("on
commence par le plus facile") : une tuile sur l'accueil, au même
rang visuel que Supervision SI/Portail tickets/DBA/Coffre-fort, qui
bascule vers `GedView.jsx` -- pas encore un vrai front "façon
portail" (URL dédiée, plein écran), explicitement mis de côté pour
plus tard ("on y reviendra").

**Pourquoi pas via `buildFrontsList` (`lib.js`)** : ce mécanisme
suppose une URL de portail EXTERNE pour chaque front -- `GedView.jsx`
vit À L'INTÉRIEUR du hub (un `viewMode` interne, pas un portail
séparé). La tuile GED est donc ajoutée directement dans `App.jsx`,
avec `onClick: () => setViewMode("ged")` au lieu de `url` --
concaténée dans le tableau `fronts` APRÈS `buildFrontsList`, pour
bénéficier de la MÊME personnalisation (réordonnancement/regroupement
via "Personnaliser l'accueil") que les autres fronts, jamais une
tuile à part figée.

`renderFrontTile` (`App.jsx`) rendait jusqu'ici toujours un `<a
href>` -- accepte désormais aussi `f.onClick`, rendu comme un
`<button>` stylé identiquement (`.hub-front-tile-button`, `hub.css`
-- reprend `font`/`cursor`/`width` que `<button>` n'hérite pas par
défaut contrairement à `<a>`, le reste vient déjà de `.hub-card`/
`.hub-front-card`, spécificité de classe > style par défaut du
navigateur).

**Vérifié réellement** : confirmé que `applyHubLayout`
(`hubLayoutLib.js`) ne dépend QUE de `front.id` (jamais de `url`),
donc compatible sans modification avec une tuile `onClick`.
Structure JSX de `App.jsx` vérifiée par un contrôle d'équilibre
accolades/parenthèses/balises après l'ajout.

**Non vérifié dans cet environnement** : rendu visuel réel (aucun
navigateur ici) -- en particulier le style du `<button>` face aux
tuiles `<a>` existantes, où un écart PEUT exister malgré la
réinitialisation CSS ajoutée.

## Sous-onglets OwnCloud/Recherche dans la tuile GED (livraison #354-355)

Demandé explicitement : séparation VISUELLE entre dépôt interne
(ged-api/Mayan, écriture) et dépôt EXTERNE (OwnCloud, lecture seule)
au sein de la même tuile GED, plus recherche Elasticsearch et
détection des chemins trop longs pour Windows. Voir
`owncloud/README.md` pour le détail technique complet (routes
backend, requête coûteuse `/long-paths` et son cache dédié, sujet
plus large "supervision des erreurs de synchronisation" resté À
CLARIFIER -- backlog item 53).

`GedView.jsx` gagne 2 nouveaux sous-onglets ("☁️ OwnCloud", "🔍
Recherche") en plus de "📁 Dépôt interne" (contenu existant, inchangé)
-- bordure orange + bannière permanente "lecture seule -- dépôt
EXTERNE" sur les deux nouveaux, jamais une simple différence de
libellé. Nouveaux fichiers : `ownCloudClient.js`,
`OwnCloudTreeView.jsx` (navigation fil d'ariane, pas un arbre imbriqué
complet -- l'API ne fournit que les enfants DIRECTS d'un nœud à la
fois), `OwnCloudSearchView.jsx` (clauses construites dynamiquement
depuis le vrai mapping Elasticsearch, jamais des champs supposés en
dur). `frontendUrl` (Supervision SI) transmis en prop pour un lien
vers l'expérience plus riche déjà existante là-bas (arbre radial,
chronologie de versions) -- jamais dupliquée ici, cette version reste
volontairement plus simple.

Deux nouvelles variables `VITE_OWNCLOUD_API_BASE_URL`/
`VITE_OWNCLOUD_SEARCH_API_BASE_URL` (`docker-compose.yml`, service
`hub`) -- même motif que les autres `VITE_*_API_BASE_URL`.

**Vérifié réellement** : syntaxe de tous les fichiers (`tsc --jsx`),
`ownCloudClient.js` testé en profondeur avec `fetch` simulé (4
fonctions, dont gestion d'erreur réseau -- tableau vide plutôt qu'une
exception). **Non vérifié dans cet environnement** : rendu visuel
réel (aucun navigateur ici, ni accès à une vraie instance
OwnCloud/Elasticsearch).

## Refonte de la navigation d'en-tête (livraison #173)

Demandé explicitement : "je n'aime pas trop le bandeau d'icônes
actuel... il y en a trop... hiérarchie d'inclusion, les liens
devraient être dans paramétrage". Le bandeau (11 icônes en une
rangée après l'ajout de GED en #172) devient un **menu horizontal en
texte** :

- **Directement visibles** : Aide, Logs, Analyse de schémas,
  Onglets, Historique — chacun `active` (fond accentué) quand
  `viewMode` correspond, même motif visuel que `.tabs` ailleurs
  dans ce projet.
- **Regroupés sous "Paramètres ▾"** (hiérarchie d'inclusion demandée
  explicitement) : Paramètres généraux, Personnaliser l'accueil,
  Liens externes (admin uniquement), Diagnostic (jeton Keycloak).
  Le déclencheur `Paramètres ▾` n'ouvre QUE le sous-menu, ne navigue
  jamais lui-même directement -- un choix explicite à l'intérieur
  navigue (ou bascule `showDebug` pour Diagnostic, comportement
  inchangé, juste déplacé).
- **GED retirée du menu** -- devenue redondante avec la tuile
  d'accueil (#172), retrait qui répond directement à "il y en a
  trop" en réduisant le compte plutôt qu'en le déplaçant seulement.
- **Inchangés** : identité (👤 nom/rôles), bascule de thème (🌙/☀️,
  gardée en icône -- un simple bouton à deux états, pas vraiment un
  "lien de menu"), Se déconnecter.

Nouvelles classes CSS (`hub.css`) : `.hub-nav` (menu horizontal,
boutons sans cadre par défaut), `.hub-nav-dropdown`/
`.hub-nav-dropdown-panel` (sous-menu positionné en absolu sous son
déclencheur).

**Vérifié réellement** : structure JSX de `App.jsx` vérifiée par un
contrôle d'équilibre accolades/parenthèses/balises après la refonte
complète de l'en-tête. Confirmé que `--text` (utilisée dans le
nouveau CSS) existe bien pour les deux thèmes (`shared/theme.css`).

**Non vérifié dans cet environnement** : rendu visuel réel (aucun
navigateur ici) -- en particulier le comportement du sous-menu
"Paramètres" (pas de fermeture automatique au clic EN DEHORS du
menu, seulement en choisissant un élément à l'intérieur ou en
recliquant le déclencheur -- comportement volontairement simple pour
cette première version, à améliorer si ça gêne à l'usage).

## Onglet Données de schema-analyzer (livraison #178) — APPROXIMATION

Backlog `BACKLOG.md` #5, "Proposition d'interface d'édition des
données, générée à partir du graphe relationnel validé" -- demande
restée **vague**, jamais confirmée précisément avec la personne.
Sous ce nouveau mode de travail (noter les approximations et aller
jusqu'au bout plutôt que de s'arrêter), voici l'interprétation
retenue et ce qui a été construit en conséquence.

**Interprétation retenue** : un navigateur/éditeur de LIGNES par
table, appuyé DIRECTEMENT sur le CRUD déjà existant de `dba-api`
(`GET`/`PUT`/`POST`/`DELETE /rows`, jamais reconstruit) --
schema-analyzer n'apporte que l'enrichissement propre à son rôle :
les relations CONFIRMÉES permettent un "aller à la ligne liée" (clic
sur une valeur de colonne engagée dans une relation confirmée).

**Ce qui EST construit** : nouveau sous-onglet "Données" dans
`SchemaAnalyzerView.jsx` -- sélecteur de table, pagination (25
lignes/page), édition de cellule en ligne (clic → champ, `Entrée`
valide, `Échap` annule), ajout de ligne (formulaire généré depuis les
colonnes non-clé), suppression multiple (cases à cocher), "aller à
la ligne liée" pour toute colonne source d'une relation confirmée.

**Approximation technique notable** : `dba-api` n'expose pas de
requête filtrée paramétrée (`WHERE colonne = valeur`) sur
`/rows` -- seulement pagination par `limit`/`offset`. "Aller à la
ligne liée" s'appuie donc sur l'endpoint `/sql` déjà existant
(`executeSql`, `hub/src/schemaAnalyzerClient.js`), avec un
échappement SQL BASIQUE (`sqlLiteral` -- guillemets simples
doublés, SQL92 standard) plutôt qu'une vraie requête paramétrée. Un
vrai filtre `WHERE` paramétré côté `dba-api` serait plus robuste --
pas construit ici pour rester dans le périmètre de
`schema-analyzer` plutôt que de modifier `dba-api`, mais **à
reconsidérer si cette approche s'avère fragile en usage réel**.

**Ce qui n'a PAS été tenté** : le second volet du même item backlog
("Interface de gestion — affectation des relations", distincte de
l'éditeur de schéma) reste **flou** même après cette interprétation
-- traité séparément (voir `BACKLOG.md` #5 et le changelog de
livraisons suivantes).

## Onglet Affectation de schema-analyzer (livraison #5)

Backlog `BACKLOG.md` #5 -- "Interface de gestion (affectation des
relations)". Distinct de l'éditeur de relations (qui corrige le
SCHÉMA déduit) : ici, on gère l'AFFECTATION des relations sur les
données elles-mêmes.

**Ce qui EST construit** : nouveau sous-onglet "Affectation" dans
`SchemaAnalyzerView.jsx` -- sélecteur de table, navigateur de lignes
(50 lignes/page, pagination), clic sur une ligne pour résoudre TOUTES
ses relations confirmées (affichage des lignes cibles), et bouton
"Modifier l'affectation" pour changer la valeur d'une FK/colonne-liste
(protégé par rights-api).

**Backend** : nouveau module `relation_resolver.py` (fonctions PURES)
+ 2 routes (`POST /relations/resolve-row` pour la résolution, `POST
/relations/assign` pour l'affectation). L'écriture réelle délègue à
dba-api (PUT /rows) -- schema-analyzer ne fait que préparer l'appel.

**Vérifié réellement** : logique de résolution testée en profondeur
(16 tests) -- résolution FK classique + colonne-liste, valeur
orpheline, ligne introuvable, colonne-liste avec correspondance
partielle, ignore les relations non confirmées et les valeurs vides.
Logique d'affectation testée (5 tests) -- cascade complète
validation -> résolution -> assignation, refus sans relation
confirmée. Structure JSX revérifiée.

**Vérifié réellement** : nouvelles fonctions du client
(`fetchTableColumnsForEdit`, `fetchTableRows`, `updateTableRow`,
`insertTableRow`, `deleteTableRows`, `executeSql`) testées avec un
`fetch` simulé en Node (bonnes URLs/méthodes/corps, préservation des
messages d'erreur réels de `dba-api`). `sqlLiteral` testée
spécifiquement contre une tentative d'injection SQL (neutralisée).
Structure JSX de `SchemaAnalyzerView.jsx` vérifiée par un contrôle
d'équilibre accolades/parenthèses/balises après l'ajout (conséquent).
Nouvelle classe CSS générique `.hub-table` (pas seulement pour cet
onglet).

**Non vérifié dans cet environnement** : rendu visuel réel (aucun
navigateur ici), et surtout le "aller à la ligne liée" contre un VRAI
`dba-api`/SGBD (le chemin `executeSql` n'a été testé qu'au niveau du
client JS, pas de bout en bout contre un vrai backend ici).

## Écran Cyber (livraison #187)

Demandé explicitement : un écran "au même niveau que Logs" (menu
horizontal), une matrice en premier, "à destination en premier lieu
des politiques et des béotiens" -- design volontairement simple,
code couleur explicite, jargon technique réservé à l'onglet "Suivi".

**Deux onglets** : "Matrice" (par défaut, lecture seule -- grille
probabilité × gravité 3×3, vert/orange/rouge selon un score
probabilité×gravité, chaque point cliquable pour voir sa
description en clair) ; "Suivi" (liste complète groupée par statut,
statut modifiable, notes d'avancement éditables au survol/perte de
focus, ajout d'un nouveau point).

**Backend** : nouvelles routes `/cyber-risks` (CRUD complet) ajoutées
à `prefs-api` (pas un nouveau service dédié -- CRUD simple, sans
besoin technique particulier, cohérent avec son rôle de "paramétrage
transversal"). Départ automatique avec les 14 risques déjà identifiés
dans `docs/cyber-risques-resume.md` (#186), reformulés en langage
accessible -- n'insère qu'une seule fois (jamais de doublon au
redémarrage, jamais d'écrasement d'un statut déjà modifié).

**Nouveau jeton de thème** : `--warning`/`--warning-bg` ajoutés à la
Famille 1 (`shared/theme.css`, hub/tickets/DBA) -- absent jusqu'ici,
nécessaire pour une matrice à 3 niveaux. Jamais emprunté à la
Famille 2 (réservée à Supervision SI/`frontend/`, "jamais mélangées"
selon l'en-tête du fichier).

**Vérifié réellement** : CRUD testé de bout en bout contre une vraie
base SQLite (14 risques de départ confirmés, pas de doublon au
second appel, mise à jour PARTIELLE confirmée -- seul le champ
transmis change, création/suppression, validation des champs
requis). Logique de classement (probabilité×gravité -> couleur)
testée avec les 14 risques RÉELS un par un, résultat conforme à la
matrice attendue. Structure JSX de `CyberView.jsx` et `App.jsx`
vérifiée par contrôle d'équilibre.

**Non vérifié dans cet environnement** : rendu visuel réel (aucun
navigateur ici) -- en particulier la lisibilité de la matrice pour
un public non technique, l'objectif premier de cet écran, ne peut se
juger que devant un vrai écran.

## Écran Cyber -- évolution ISO/IEC 27001 (livraison #193)

Demandé explicitement, avec un lien vers l'article Wikipedia ISO/IEC
27001 (consulté avant de coder) : "la matrice devra présenter 2
aspects : le HUB et ses risques, les impacts risques du HUB sur le
SI supervisé, avec une vue mixte".

**Ancrage ISO/IEC 27001** : la norme exige d'examiner les risques
"en tenant compte des menaces, vulnérabilités ET IMPACTS" -- la
distinction demandée (HUB / SI supervisé) EST cette dimension
d'impact, rendue explicite plutôt qu'implicite. Interprétation
retenue, volontairement pragmatique (jamais une implémentation
complète d'un SMSI/ISMS -- hors de portée d'un écran de dashboard,
la norme couvre politiques/procédures/audits/rôles, pas seulement
une matrice) : chaque risque porte désormais un `scope` -- `"hub"`
(risque INTRINSÈQUE à supervision-si lui-même) ou `"si_supervise"`
(impact d'un risque du hub SUR les systèmes qu'il gère -- bases de
données, annuaire, équipements réseau... -- le hub comme VECTEUR,
pas comme cible).

**Vue mixte** : filtre à trois positions au-dessus de la matrice
("Vue mixte" / "🏠 HUB seul" / "🔗 SI supervisé seul"), "Vue mixte"
par défaut -- montre les DEUX catégories dans la MÊME grille
probabilité×gravité, chaque point préfixé de son icône de portée
(🏠/🔗) pour rester distinguable sans dédoubler la matrice.

**Backend** : nouvelle colonne `scope` sur `cyber_risks`
(`prefs-api`), validée contre `("hub", "si_supervise")` à la
création/mise à jour. **Migration critique** : la personne utilise
déjà l'écran depuis #187 -- `ensure_cyber_risks_scope_column()`
ajoute la colonne SANS TOUCHER aux statuts/notes d'avancement déjà
saisis, et RECLASSE les 14 risques de départ CONNUS par leur libellé
exact (jamais par position). Répartition retenue pour ces 14 (à
ajuster via l'onglet Suivi si le classement ne convient pas) : 8
HUB / 6 SI supervisé -- voir `prefs-api/app.py`,
`_INITIAL_CYBER_RISKS_SCOPE_BY_LABEL`, pour le détail ligne par
ligne. Un risque ajouté PAR LA PERSONNE depuis #187 (donc absent de
cette liste) garde le défaut `"hub"` de la colonne, jamais réécrit
par la migration.

**Vérifié réellement** : migration testée contre une base SIMULANT
EXACTEMENT l'état réel de la personne (schéma #187 sans `scope`,
avec un statut "en_cours" et des notes d'avancement déjà saisis sur
un risque) -- confirmé que la migration préserve statut/notes
intacts tout en reclassant correctement le scope, reste idempotente
si relancée. Validation testée (scope invalide refusé à la création
ET à la mise à jour, sans corrompre la ligne existante en cas de
refus). Client JS (`cyberRisksClient.js`) : bug réel trouvé et
corrigé en testant -- `createCyberRisk` ne déstructurait pas `scope`,
qui aurait été silencieusement perdu à l'envoi malgré sa présence
dans le formulaire. Logique de filtrage (mixte/hub/si_supervise)
testée en isolation. Structure JSX revérifiée après édition.

**Non vérifié dans cet environnement** : rendu visuel réel -- en
particulier si la double icône (portée + statut) sur chaque point de
la matrice reste lisible sans surcharger l'affichage pour un public
non technique, l'objectif premier de cet écran.

## Documents de gouvernance versionnés (livraison #195)

Demandé explicitement -- "les deux documents (charte et notice) sont
à présenter versionnés dans l'aide et dans iso27000". Nouvelle table
`governance_documents` sur `prefs-api`, distincte du mécanisme
`/docs` existant (README.md, markdown affiché en ligne) : ce sont
des fichiers BINAIRES (`.docx`) à TÉLÉCHARGER, avec `version` et
`updated_at` affichés.

**Contenu lu depuis de VRAIS fichiers** au démarrage --
`PROJECT_ROOT_PATH/docs/*.docx` (même montage lecture seule déjà
utilisé par `_discover_readmes`, aucun nouveau volume), encodé en
base64 et stocké en base -- jamais le contenu binaire codé en dur
dans le code source. Départ automatique (`ensure_governance_documents_seeded`)
UNE SEULE fois, comme pour les 14 risques cyber (#187) -- jamais un
écrasement d'une version déjà mise à jour depuis.

**Bug réel trouvé et corrigé en testant** (même piège que `now_iso()`
précédemment, #187) : `PROJECT_ROOT_PATH` était utilisé dans le bloc
`try` de démarrage AVANT sa propre ligne de définition, plus bas dans
le fichier -- `NameError` au tout premier démarrage. Corrigé en
déplaçant la DÉFINITION plus tôt (juste après `DB_PATH`), le
commentaire de sécurité détaillé restant à sa place d'origine.

**API** : `GET /governance-documents` (liste, SANS le contenu --
potentiellement volumineux, inutile pour un simple affichage),
`GET /governance-documents/<id>/download` (téléchargement, avec
`Content-Disposition` portant le nom de fichier d'origine).

**Affichage** : un même panneau "📄 Documents..." dans `AideView`
("Documents officiels") ET dans `CyberView` ("Documents ISO/IEC
27000", visible quel que soit l'onglet actif) -- chaque document :
nom cliquable (téléchargement direct), version, date de mise à jour.

**Vérifié réellement** : départ testé contre le VRAI dépôt
(`PROJECT_ROOT_PATH` pointé sur le vrai projet) -- confirmé que les
2 documents réels sont chargés. Téléchargement vérifié OCTET PAR
OCTET (hash SHA256) contre les fichiers originaux sur disque --
contenu identique confirmé, pas seulement "une réponse 200". Départ
idempotent sur ré-appel. Non-régression complète de `/docs` (le
mécanisme existant) retestée après le déplacement de
`PROJECT_ROOT_PATH`. Structure JSX de `App.jsx` (AideView) et
`CyberView.jsx` revérifiée après édition.

**Non vérifié dans cet environnement** : rendu visuel réel des deux
nouveaux panneaux (aucun navigateur ici).

## Clarification du tableau de bord des logs (livraison #197)

Doute réel remonté par la personne : "les logs sont verts et à 0
alors qu'il y a des logs" au premier chargement de l'écran
`LogsManagerView.jsx`. Revue du code : le "Chargement…" est bien
affiché tant que les vraies données n'arrivent pas (`!summary`),
aucun bug trouvé dans cette logique.

**Hypothèse retenue** (la plus probable, pas confirmée par un test
réel) : le tableau ne compte QUE les événements ≥ WARNING
(`LOG_CAPTURE_LEVEL=WARNING`, livraison #145) -- un service sans
souci récent affiche donc LÉGITIMEMENT 0/0, vert -- correct, mais
visuellement indiscernable d'un chargement en cours ou d'un
problème au premier coup d'œil, surtout si la personne sait par
ailleurs (ex. `docker compose logs`) que ce service produit bien des
entrées -- simplement des entrées de niveau INFO, jamais remontées
dans ce tampon partagé par conception.

**Corrigé** : l'état "0 événement confirmé" est désormais rendu
EXPLICITE plutôt que silencieux -- une note sous "🟢 joignable"
("aucun événement ≥ warning récemment") quand c'est le cas, plus une
phrase d'explication générale au-dessus du tableau.

**Non confirmé** : si c'est bien CE que la personne a observé (vs.
un autre écran, ou un cas réellement différent) -- à valider avec
elle une fois testé en conditions réelles.

## Troisième document de gouvernance : PRA secrets de démarrage (livraison #203)

Réponse au point 4 de l'urgence matrice de risque ("le coffre-fort
est-il sécurisé pour ça ? risque de boucle avec Keycloak non monté ?
quelles procédures possibles / PRA à décrire dans le volet cyber"),
enrichie par la réponse de la personne sur la garde de la clé
maîtresse : "une passe phrase et un SMS avec code au travers de la
partie non authentifiée de la passerelle sms, plus une alerte mail
sur des adresses non personnelles".

`docs/pra-secrets-demarrage.docx` -- procédure à 3 canaux (phrase de
passe + SMS via la route machine de la passerelle SMS Teltonika
TRB140 + alerte courriel institutionnelle), scénarios de reprise
(personne indisponible, Keycloak indisponible, perte de la phrase de
passe elle-même -- **irrécupérable, aucune porte dérobée**).

**Vérifié réellement contre le vrai code de la passerelle SMS**
(fournie par la personne) avant rédaction, jamais présumé : la route
`/send` accepte bien une clé de service (`RELAY_API_KEY`) ou des
identifiants applicatifs avec le droit "send", INDÉPENDAMMENT de
Keycloak -- confirme l'hypothèse de conception. Point corrigé après
vérification : la fonction d'envoi de courriel du projet
(`email_sender.py`) existe bel et bien, mais est strictement interne
à la redistribution des SMS reçus -- PAS exposée comme service
réutilisable. Le canal courriel de cette procédure reste donc à
construire (capacité propre à ce projet, ou extension de la
passerelle SMS -- pas encore tranché).

**Migration** : `ensure_governance_document_present(name)`, fonction
GÉNÉRALE (pas spécifique au PRA) pour ajouter un document précis à
une base déjà peuplée sans toucher aux documents existants ni créer
de doublon -- testée contre une base simulant l'état réel déjà
déployé (2 documents sans le PRA) : confirmé, le troisième document
s'ajoute proprement, `created_at` des deux autres documents inchangé,
contenu téléchargé identique octet pour octet au fichier réel,
migration rejouée sans effet (idempotente).

## Vue graphique de l'architecture du projet (livraison #207)

2e volet de la demande "transparence" (le 1er, l'historique versionné
de la matrice de risques, a été livré en #199) : "une vue graphique
de l'architecture large du projet incluant : les ressources/
supports, les clés de conf et chemins, les stacks et les projets
liés externes (Passerelle SMS, ...)".

`docs/architecture-projet.svg` -- généré par script Python
(`docs/architecture-projet.svg` lui-même est le résultat, le script
générateur n'est pas conservé dans le dépôt -- fichier statique,
regénérable à la main si l'architecture évolue significativement).
Quatre régions du stack principal (interfaces, modules métier,
sécurité/secrets, données/stockage), le stack `gateway/` séparé
(Keycloak/tls-proxy), et sept systèmes EXTERNES clairement
distingués (bordure pointillée) : GLPI existant, Zyxel Nebula,
passerelle SMS Teltonika TRB140, annuaire LDAP/AD, GED Mayan, bases
de données distantes, équipements réseau supervisés.

**Bug réel trouvé et corrigé avant même de livrer** : les deux
premières régions généraient un débordement de texte hors de leur
cadre (calcul de hauteur trop court pour le nombre de lignes réelles)
-- repéré en CONVERTISSANT le SVG en image et en le regardant
réellement (jamais fait confiance aux coordonnées calculées sans
vérification visuelle), corrigé en recalculant les hauteurs
précisément à partir du nombre de lignes réel.

**Nouvelle route** `GET /architecture-diagram` (`prefs-api`) -- sert
le fichier SVG avec le vrai type MIME (`image/svg+xml`), lu depuis
`PROJECT_ROOT_PATH/docs/` (même montage que le mécanisme `/docs`
existant). Chemin FIXE, jamais fourni par le client -- aucune
surface d'attaque par chemin ici, contrairement à `/docs/<path>`.
Affiché dans un nouvel onglet "Architecture" de l'écran Cyber, via
un simple `<img>`.

**Vérifié réellement** : SVG converti en image et inspecté visuellement
à deux reprises (avant et après correction du débordement). Route
testée -- type MIME correct, contenu identique octet pour octet au
fichier réel sur disque.

**Non vérifié dans cet environnement** : rendu réel dans le
navigateur du hub (aucun navigateur ici) -- l'image a été vérifiée
via conversion LibreOffice, pas via un rendu SVG de navigateur
(généralement plus permissif, risque résiduel faible).

## Détection et aperçu du HTML dans DBA (livraison #214)

Backlog item 7. Contexte donné par la personne : les tickets
d'anciennes gestions (importés en dump MySQL dans DBA) sont rédigés
en HTML -- affichés tels quels jusqu'ici (balises brutes),
illisibles en l'état. Demande explicite : détecter le HTML dans
N'IMPORTE QUEL champ (pas une liste de colonnes connues à l'avance),
proposer un affichage rendu (fiche ou fenêtre volante).

**Décision prise pour avancer** (le déclencheur exact -- "bouton par
cellule ? icône dans l'en-tête ?" -- était resté à discuter) : une
icône "📄 Aperçu" apparaît directement dans la cellule dès qu'un
contenu de type HTML y est détecté, à côté d'un extrait de texte brut
(balises retirées, tronqué à 40 caractères) -- clic sur l'icône ouvre
une fenêtre volante (fiche) centrée, avec le rendu HTML complet.

`hub/src/htmlContentUtils.js` -- détection par expression régulière
(présence d'une balise HTML plausible), assainissement LÉGER fait
main avant tout rendu (`dangerouslySetInnerHTML`) : scripts et styles
retirés entièrement (contenu compris), `<iframe>`/`<object>`/`<embed>`
retirés, attributs `on*` (gestionnaires d'évènements) retirés,
`javascript:` neutralisé.

**⚠️ Assainissement volontairement léger, pas une bibliothèque de
référence** -- `npm install dompurify` tenté, **npm est inaccessible
dans cet environnement de développement** (403 même en simple
consultation via `npm view`, pas seulement à l'installation) -- pas
de DOMPurify ni équivalent éprouvé disponible ici. Proportionné au
contexte réel : données INTERNES déjà importées dans la propre base
de la personne, affichées uniquement à elle-même dans son propre
outil d'administration -- pas une défense contre un contenu
réellement hostile. Si ce contenu pouvait un jour provenir d'une
source moins fiable, à remplacer par une vraie bibliothèque
d'assainissement plutôt que d'étendre cette fonction ad hoc.

**Vérifié réellement** : détection et assainissement testés de façon
exhaustive -- un vrai bug trouvé et corrigé en testant (les balises
auto-fermantes comme `<br/>` n'étaient PAS détectées, la première
version de l'expression régulière ne prévoyait pas le `/` sans espace
avant le `>`). Script/style retirés avec leur contenu (pas juste les
balises), attributs `on*` retirés sur n'importe quel élément,
`javascript:` neutralisé en conservant la structure du lien,
`iframe` retiré entièrement, entrées non-chaîne (`null`/`undefined`)
gérées sans exception. Aperçu tronqué testé avec un exemple réaliste
de ticket. Structure JSX revérifiée après intégration.

**Non vérifié dans cet environnement** : rendu visuel réel (aucun
navigateur ici).

## Catalogue SGBD -- tunnels SSH ↔ connexions DBA (livraison #221)

Backlog item 11. Demande explicite (deux volets) : faire apparaître
les tunnels SSH vers MySQL comme des sources utilisables dans DBA et
l'analyse de schémas, avec contrôle (ouvrir/fermer) et historique.

**Décisions prises pour avancer** (l'item listait 3 aspects "à
trancher ensemble") :
- **Périmètre** : Analyse de schémas uniquement pour cette livraison
  (les deux modules explicitement nommés étaient DBA et Analyse de
  schémas -- ce dernier reçoit déjà `dbaApiBase` ET `sshTunnelsApiBase`
  en props depuis `App.jsx`, ce qui en fait le point d'intégration le
  plus naturel).
- **Modèle de données** : RÉFÉRENCE CROISÉE, jamais une fusion --
  aucune modification du schéma `dba-api` existant (table
  `connections`, en production). Le rapprochement se fait par
  correspondance hôte+port (`127.0.0.1`/`localhost` + le port local
  du tunnel) -- aucune référence stockée explicitement entre les deux
  systèmes.
- **Historique** : réutilise TEL QUEL l'historique d'usage déjà
  construit pour SSH (`ssh_credential_usage_history`, #210) --
  aucune nouvelle table.

Nouvelle section "🗂️ Catalogue SGBD" en haut de
`SchemaAnalyzerView.jsx` (masquée par défaut, chargée à la demande) :
liste des tunnels SSH avec leur statut, les connexions DBA qui
utilisent chacun (le cas échéant), boutons démarrer/arrêter (routes
`ssh-tunnels-api` déjà existantes), historique consultable par
tunnel.

**Sécurité** : `dba-api` stocke le mot de passe des connexions EN
CLAIR (caractéristique déjà existante de ce module, pas introduite
ici) -- vérifié explicitement que ce champ n'apparaît NULLE PART dans
le nouveau catalogue, seul `label` est utilisé pour identifier une
connexion correspondante.

**Vérifié réellement** : logique de correspondance hôte/port testée
en isolation avec des cas limites (connexion directe au même port
jamais confondue avec un tunnel, `127.0.0.1` et `localhost` tous deux
reconnus, robustesse au type du port -- chaîne vs nombre). Structure
JSX revérifiée après intégration. Recherche textuelle explicite
confirmant l'absence du mot de passe dans toute la section ajoutée.

**Reste à faire** : extension au module DBA lui-même (pas fait ici),
"d'autres" modules non précisés par la personne, historique du
PARAMÉTRAGE (pas seulement de l'usage -- pas construit, aucun
mécanisme équivalent n'existe encore pour ça).

## Réorganisation de l'en-tête (livraison #236)

Demandé explicitement -- "il y a trop d'outils maintenant" : 12
boutons plats accumulés au fil des livraisons (#227-233 notamment)
rendaient la barre de navigation illisible.

Structure demandée par la personne, appliquée telle quelle : deux
boutons PERMANENTS (Aide, Onglets), trois menus déroulants par
catégorie -- Général (Logs, Cyber, Historique), Réseau (Tunnels SSH,
SNMP, Nebula, GLPI Inventory, Exploration réseau), Data (Analyse de
schémas). Le menu "Paramètres" (#173) reste inchangé, pas mentionné
par la personne donc pas touché à part son mécanisme interne.

**Point à confirmer par la personne** : "Client IMAP" n'était
mentionné dans AUCUNE des trois catégories demandées -- placé par
défaut sous "Général" (ni réseau bas niveau, ni analyse de données),
signalé explicitement comme un choix par défaut, pas une certitude.

Réutilise TEL QUEL le motif de menu déroulant déjà en place pour
"Paramètres" (`hub-nav-dropdown`/`hub-nav-dropdown-panel`, CSS
inchangé, déjà générique). Remplace `showSettingsMenu` (booléen
unique) par `openNavMenu` (chaîne unique parmi les 4 menus, ou
`null`) -- un seul menu ouvert à la fois désormais, au lieu de
pouvoir ouvrir "Paramètres" indépendamment d'un futur second menu
(qui n'existait pas encore avant cette livraison).

**Vérifié réellement** : les 12 destinations de navigation
originales toutes retrouvées dans la nouvelle structure (aucune
oubliée). Structure JSX complète revérifiée (accolades, parenthèses,
balises). Logique d'état testée en isolation : bascule d'un menu à
l'autre (un seul actif à la fois), calcul de la classe "active" du
déclencheur (reste actif tant qu'une vue de sa catégorie est
affichée, même menu fermé), fermeture automatique du menu à la
sélection d'un item.

## Correctif : conteneur de défilement borné pour les vues .hub-settings (livraison #257)

Bug récurrent signalé explicitement, capture d'écran à l'appui : "le
design du footer a toujours le même souci, la page déborde sur le
footer au lieu de rester en dessous et de proposer le défilement".

Cause réelle : les vues utilisant `.hub-settings`/`.hub-settings-wide`
(Exploration réseau, Architecture réseau, Sauvegardes, etc.) rendent
comme enfants DIRECTS de `.hub-shell`, juste après `.hub-header`
(désormais sticky, #250) -- sans AUCUN conteneur borné entre les
deux. Un panneau `position: sticky; bottom: 0` (ex.
`.na-footer-panel`, Exploration réseau) a besoin d'un ANCÊTRE avec
une hauteur BORNÉE et son propre défilement pour avoir la marge de
manœuvre nécessaire à réellement se figer -- sans ça, il reste un
bloc normal du flux de la page, poussé hors champ par tout contenu
qui grandit (ex. #256, un tableau avec beaucoup de points de
service), jamais visible sans défiler la page ENTIÈRE jusqu'à lui.

Corrigé : `.hub-settings` reçoit désormais `flex: 1; overflow-y:
auto; min-height: 0` -- MÊME motif déjà éprouvé pour `.hub-grid-scroll`
(la grille d'accueil), qui n'avait jamais ce problème. Devient ainsi
sa propre zone de défilement bornée, à l'intérieur de laquelle un
panneau sticky peut réellement se figer au bas de LA ZONE VISIBLE,
comme prévu à l'origine. Affecte TOUTES les vues utilisant
`.hub-settings`, pas seulement Exploration réseau -- cohérent avec
"toujours le même souci" signalé par la personne, un correctif
central plutôt qu'un rustine par vue.

**Non vérifié dans cet environnement** : rendu visuel réel (aucun
navigateur disponible ici) -- structure CSS/JSX revérifiée, le
raisonnement s'appuie sur le motif `.hub-grid-scroll` déjà
fonctionnel en production, mais le comportement exact reste à
confirmer par la personne après déploiement.

## Correctif du correctif : le vrai fond du problème de défilement (livraison #258)

Le correctif #257 ci-dessus était **incomplet** -- confirmé par une
capture d'écran réelle montrant une page de PLUSIEURS MILLIERS DE
PIXELS de haut, le problème toujours présent après déploiement.

Cause exacte : `flex: 1` sur `.hub-settings` n'a d'effet que si le
PARENT flex (`.hub-shell`) a lui-même une hauteur BORNÉE -- or
`.hub-shell` n'a que `min-height: 100vh` (un plancher, jamais un
plafond), donc rien n'empêchait la page entière de continuer à
grandir avec son contenu, quel que soit le `overflow-y: auto` posé
sur `.hub-settings`.

Envisagé de border `.hub-shell` lui-même (`height: 100vh`) --
**écarté** : un commentaire déjà présent sur `.hub-grid-view`
prévenait explicitement que `.hub-shell` n'avait JAMAIS été touché
pour cette raison précise ("les autres vues... n'ont pas été
vérifiées avec un défilement interne forcé", livraison #132).
Modifier `.hub-shell` aurait risqué de casser des vues jamais
auditées pour ce comportement -- un changement bien plus large que
nécessaire pour corriger UN symptôme précis.

Corrigé en reprenant le motif DÉJÀ VALIDÉ de `.hub-grid-view`
lui-même (#132) -- hauteur EXPLICITE `calc(100vh - 60px)` (60px =
hauteur de `.hub-header`, déjà confirmée exacte ailleurs, voir
`.hub-tabshell`) plutôt qu'un `flex: 1` dépendant d'un parent
lui-même jamais borné. Fonctionne INDÉPENDAMMENT de la hauteur de
`.hub-shell`, jamais besoin d'y toucher -- le même filet de sécurité
qui protégeait déjà la grille d'accueil s'applique maintenant
identiquement à toutes les vues `.hub-settings`.

**Non vérifié dans cet environnement** (toujours aucun navigateur
disponible ici) -- mais cette fois le raisonnement s'appuie sur un
calcul EXPLICITE et déjà éprouvé en production (`.hub-grid-view`),
pas sur une supposition non vérifiée comme en #257. Reste à confirmer
par la personne après déploiement.

## Exploration réseau promue en tuile d'accueil (livraison #265)

Demandé explicitement : "peux tu transformer l'explorateur réseau en
tuile ?" -- même mécanisme que GED (#172) : ajoutée au tableau
`fronts` avec un `onClick` interne (`setViewMode("network-agent")`)
plutôt qu'une URL externe, puisque `NetworkAgentView.jsx` vit lui
aussi à l'intérieur du hub. Conditionnée à
`NETWORK_AGENT_API_BASE_URL` configurée -- jamais une tuile morte si
le service n'est pas déployé, même garde que GED.

Retirée du menu déroulant "Réseau" où elle vivait jusqu'ici -- même
convention que GED, qui n'apparaît elle aussi dans AUCUN menu une
fois promue en tuile (un seul point d'accès, jamais deux chemins
redondants vers la même vue).

Vérifié réellement : logique de construction du tableau `fronts`
testée en isolation (tuile ajoutée seulement si l'URL est
configurée, jamais de tuile morte). Structure JSX complète
revérifiée.

## Tuile ENT : premier pas vers la "super tuile" -- onglet GED ajouté (livraison #334)

Backlog item 38, point 2 -- "la tuile ENT devient une super tuile"
avec des sous-tuiles dédiées : calendrier partagé, webmail (la
personne elle-même note "à voir", pas encore décidé), GED, et une
vue "relations" transversale (backlog, cadrage encore à construire).

**Premier morceau concret** : `GedView.jsx` (interface complète pour
`ged-api`, déjà construite et déjà utilisée comme tuile autonome
depuis #167) ajoutée comme quatrième onglet de `EntView.jsx`, aux
côtés de Calendrier/Tâches/Validation déjà en place -- confirmé par
la personne comme réponse au "dépôt de fichiers interne" mentionné
dans les spécifications, pour le webmail éventuel. Réutilisée TELLE
QUELLE, aucune reconstruction -- même composant, mêmes props
(`gedApiBase`, `login`, `ticketsPortalUrl`) que son usage existant en
tuile séparée.

`App.jsx` : `EntView` reçoit désormais aussi `gedApiBase`
(`GED_API_BASE_URL`, déjà défini) et `login`
(`profile.preferred_username`, déjà utilisé ailleurs dans ce fichier)
-- aucune nouvelle variable d'environnement, aucun nouveau calcul,
juste deux props supplémentaires transmises à un composant qui les
attendait déjà.

**Webmail délibérément PAS ajouté** -- explicitement noté "à voir"
par la personne dans le backlog d'origine, jamais présumé décidé.

**Vue "relations" transversale -- PAS ENCORE COMMENCÉE.** Modèle
clarifié par la personne (2026-09-04) : relation DIRECTE = marqueur
commun identique entre deux éléments (chaîne identique dans un champ
nom/label, adresse IP, proximité géographique, proximité sémantique) ;
relation INDIRECTE = un attribut associé à un élément direct ou à un
ENSEMBLE -- deux éléments d'un même ensemble (formé par des relations
directes) sont en relation indirecte l'un avec l'autre. Chantier à
part entière, touchant potentiellement tickets/calendrier/GED/tâches
-- à traiter par passes successives, même méthode que le chantier
rights-api (#289-331), jamais en bloc.

**Vérifié réellement** : structure JSX de `EntView.jsx` et `App.jsx`
revérifiée (accolades/parenthèses équilibrées, aucune balise non
refermée) après l'ajout de l'onglet.

## Tuile ENT : premier pas sur la vue "relations" -- nouveau service dédié (livraison #335)

Suite du point 2 de l'item 38 -- modèle clarifié par la personne le
2026-09-04 (voir la section précédente pour son énoncé complet).
Voir `relations/README.md` pour le détail architectural complet
(service SANS ÉTAT propre, portée de cette première passe, limite
structurelle découverte par test sur les relations indirectes).

Sixième onglet de `EntView.jsx` -- `RelationsView.jsx`, volontairement
minimal pour cette première passe : un formulaire type d'entité +
identifiant, affichage des relations directes (avec le marqueur qui
les justifie) et indirectes en listes simples. Pas de graphe visuel,
pas de navigation cliquable d'une entité à l'autre pour l'instant.

Nouveau service `relations-api` (port standard, routé via la
passerelle nginx à `/api/relations/` -- ajouté dès cette première
livraison, jamais laissé pour plus tard, piège déjà rencontré pour
netprobe-api en #301). `App.jsx`/`EntView.jsx` reçoivent
`relationsApiBase` (`VITE_RELATIONS_API_BASE_URL`, nouvelle variable).

**Vérifié réellement** : voir `relations/README.md` pour le détail
complet des tests (moteur de calcul en isolation, application de
bout en bout avec les trois services amont simulés). Structure JSX
de `RelationsView.jsx` et `EntView.jsx` revérifiée après
l'intégration.

## Vue "relations" : intégration directe depuis le Calendrier (livraison #339)

Suite du "reste à faire" de `relations/README.md` -- premier bouton
"voir les relations" (🔗) intégré directement dans une vue existante,
plutôt que de laisser la vue Relations comme un formulaire isolé où
il faut ressaisir manuellement type+identifiant.

`EntView.jsx` porte désormais l'état de navigation
(`relationsTarget`) et un callback `viewRelations(type, id)` transmis
aux onglets enfants -- change d'onglet vers "Relations" ET
pré-remplit sa cible en un seul geste. `CalendarView.jsx` reçoit ce
callback (`onViewRelations`, prop optionnelle -- rétrocompatible si
absente) et affiche un bouton 🔗 sur chaque ligne de la file
d'attente (tickets) ET chaque ligne de la liste d'événements
calendrier -- les deux premiers types d'entités que `relations-api`
sait déjà interroger.

`RelationsView.jsx` accepte désormais `initialEntityType`/
`initialEntityId` -- déclenche la recherche automatiquement à
l'arrivée (jamais besoin de re-cliquer "Chercher"), via un
`useEffect` dépendant explicitement de ces deux valeurs (jamais du
simple changement d'onglet, pour ne pas relancer une recherche déjà
affichée si la personne navigue ailleurs puis revient sans repasser
par un bouton).

**Reste à faire** : mêmes boutons pour GED et Tâches (les deux
autres types d'entités connus de `relations-api`, pas encore
intégrés dans leurs vues respectives -- `GedView.jsx`/`KanbanView.jsx`
n'ont pas encore reçu ce callback).

**Vérifié réellement** : structure JSX de `RelationsView.jsx`,
`EntView.jsx` et `CalendarView.jsx` revérifiée (accolades/parenthèses
équilibrées, aucune balise non refermée) après l'intégration.
Confirmé qu'aucun autre composant du hub n'utilise `CalendarView`
en dehors d'`EntView.jsx` -- le nouveau prop optionnel
(`onViewRelations`) reste rétrocompatible partout ailleurs.

## Graphique du cycle réseau interactif + menu Réseau complété (livraison #399)

**Graphique** (`NetworkCycleView.jsx`) — zoom molette ancré sous le curseur,
déplacement au glisser, boutons `+`/`−`/`⟲`, infobulles détaillées au survol
des nœuds, rafraîchissement manuel et automatique (30 s) avec horodatage.
Toute la logique non-React vit dans `src/networkCycleGraph.js` (12 tests Node
dans `tests/networkCycleGraph.test.mjs`) — même motif que `ldapTree.js`.
Détail des pièges traités (facteur de zoom recalculé après bornage, échelle
commune aux deux axes du déplacement, absence de `setPointerCapture` pour ne
pas casser le clic sur un nœud, molette en écoute non passive, infobulle
bornée à cause de `overflow: hidden`) : voir `docs/cycle-agile-reseau.md`.

**Menu Réseau ▾** (`App.jsx`) — « Exploration réseau » et « Sondes réseau »
n'existaient QUE comme tuiles d'accueil. Rapatriées dans le menu (mêmes
`viewMode`, jamais une vue dupliquée) et **conditionnées à leur variable
d'API**, contrairement aux sept autres entrées : `NetworkAgentView` et
`NetprobeView` appellent leur API dès le montage sans garde-fou sur une base
absente, une entrée non conditionnée mènerait donc à un écran d'erreur réseau
plutôt qu'à un « non configuré ». La liste des `viewMode` qui allument le menu
a été complétée (`network-agent`, `netprobe`).

**Correction de thème `--hub-danger`** — variable **jamais définie** : les 32
usages du hub retombaient tous sur leur repli en dur (`#c0392b` / `#fdecea`)
et restaient donc identiques en thème sombre. Remplacés par `var(--danger)` /
`var(--danger-bg)` dans 15 fichiers. Les replis valaient exactement les
valeurs du thème clair : rendu clair inchangé, seul le sombre est corrigé.
Même famille de bug que les couleurs en dur trouvées trois fois dans DBA — à
`grep` systématiquement (`grep -rn -- "var(--[a-z-]*, #" hub/src`) avant de
considérer un module terminé.


## Charte d'icônes du hub (livraison #410)

`src/icons.js` (pur, 6 tests dans `tests/icons.test.mjs`) décrit trois jeux
d'icônes pour les cinq étapes du cycle agile — *Emoji sobres* (défaut :
🧭 🕸️ 📦 📊 📚), *Symboles monochromes* (⎈ ⌕ ⇪ ∿ ✎, couleur de l'étape,
suivent le thème) et *Pictogrammes au trait* (SVG 24×24 dessinés pour le
projet) — ainsi que les icônes écartées avec leur raison (🚀, 🧠) et les
alternatives étudiées. `src/StepIcon.jsx` les dessine : `StepIcon` en HTML
(boutons, titres), `SvgStepIcon` dans un `<svg>` (nœuds du graphique). Le
sélecteur « Icônes » du cycle agile bascule le jeu en direct ; préférence
locale au navigateur (`localStorage` `hub.cycle.iconSet`, lecture tolérante
à un stockage absent ou plein).

Règles et extension aux autres tuiles : `docs/charte-icones-hub.md`. Règle
qui compte le plus : **la couleur porte l'identité, jamais l'état** — l'état
passe par la pastille et les variables `--ok/--warning/--danger/--muted`,
lisibles sur les deux thèmes.

Vérification : au-delà des tests Node et du build Vite, le rendu a été
regardé pour de vrai dans Chromium (Playwright) via un harnais qui monte
`NetworkCycleView` seul devant un faux back-end — clair et sombre, menu et
graphique, trois jeux, aucune erreur console. Le harnais n'est pas dans le
dépôt (voir backlog 59, « frontend autonome ») ; il est décrit dans le
CHANGELOG #410.

## Cycle agile : disposition en deux zones (livraison #411)

Menu en haut (barre d'étapes ou schéma -- seule chose que les onglets
Classique / Graphique changent), détail de l'étape en bas, toujours présent.
Le clic sur un nœud du schéma déplie le détail dessous au lieu de quitter le
schéma. Trois états du menu (`src/networkCycleLayout.js`, 6 tests) : réduit
par défaut, grand, masqué avec languette de réouverture ; préférence locale
au navigateur (`hub.cycle.layout`). Voir `docs/cycle-agile-reseau.md`.

## Exploration réseau : filtres des visualisations de flux (livraison #412)

`src/networkFlowFilters.js` (pur, 9 tests) : détection de l'hôte de
supervision (MAC puis IP de l'interface de capture, exposées par
`/capture/status`), passerelles par rôle deviné, masquage des flux hôte ↔
routeur, tranche de pourcentage sur la part de chaque flux dans le volume
total (base stable). Les boutons de section ouverts sont en surbrillance
(`.na-section-toggle.active`). Voir le CHANGELOG #412.

## Zoom et échelle des graphiques (livraison #413)

`src/components/ZoomableChart.jsx` enveloppe tout graphique SVG : boutons
+ / − / ⟲, Ctrl + molette (loupe sous le curseur), double-clic (×2),
glisser (déplacer). Logique pure dans `src/chartZoom.js` (viewBox d'origine
quelconque, `preserveAspectRatio` meet ou none). `src/chartScales.js` :
échelles linéaire / racine / log et gain, partagées par `alluvialLayout.js`,
`weightedRadialLayout.js` et `networkAgentHistory.js`. Règle : un graphique
ne sait rien du zoom ; il rend dans son viewBox, l'enveloppe fait le reste.
Nouveau graphique = l'envelopper, jamais réécrire un zoom local.

## Flux : fenêtre temporelle, volume, sous-réseau (livraison #414)

Trois filtres de plus dans `src/networkFlowFilters.js` (14 tests) : volume
absolu min/max en Ko, sous-réseau (/16 → /28, flux internes ou touchant,
arithmétique IPv4 maison), et la période du tableau appliquée aux flux via
`fetchLinks(apiBase, segmentId, { startIso, endIso })` →
`/links?start&end`. Voir le CHANGELOG #414.
