# Licences logicielles par site (livraison #595)

Demandé : « un gestionnaire de licences logicielles par site : recueillir
les infos sur le réseau et les postes ; mettre au point une série de
gestionnaires utilisant les accès sur les sites des vendeurs ; gérer une
grille d'affectation poste / utilisateur ; mettre en place un installeur /
désinstalleur depuis une tuile du hub ». Les tableurs d'inventaire fournis
(matrice logiciel × personnes, export Microsoft 365, comparatif) ont servi
de **structure** : aucun nom, aucune donnée réelle dans le dépôt.

## Les quatre volets

1. **Recueil sur les postes** — sonde `software-inventory` de l'agent
   (si-agent ≥ 0.5.16, désactivée par défaut, toutes les 6 h) : Linux
   (dpkg / rpm, flatpak, snap), macOS (`/Applications`, Homebrew), Windows
   (clés `Uninstall` 64 / 32 bits et utilisateur, Office click-to-run) + les
   comptes qui ouvrent des sessions. Central : `GET /software-inventory`
   (dernier relevé par agent, filtre `site`). Activation : Agents hôtes →
   l'agent → Sondes → `software-inventory` (le hub y mène par lien).
2. **Gestionnaires vendeurs** — `licenses/api/vendors.py` : **Microsoft 365
   par Microsoft Graph** (`subscribedSkus` + `users?$select=assignedLicenses`
   : SKU, quantité, consommé, utilisateurs) avec une application Entra ID
   (`Organization.Read.All`, `User.Read.All`, type application) dont le
   secret client est le mot de passe d'un accès du coffre (#498) : le
   compte vendeur ne stocke que le **nom** de l'accès, révélé par
   `credentials-api` le temps de la synchronisation. Autres éditeurs sans
   API : « export du vendeur » (fichier déposé dans l'import) ou saisie
   manuelle. Ajouter un vendeur = une fonction `sync_<vendeur>(config,
   secret)` renvoyant `[{sku, label, quantity, consumed, users}]`.
3. **Grille d'affectation** — `GET /grid` : lignes = utilisateurs et postes
   (attributions + inventaires), colonnes = logiciels sous contrat, case =
   `{assigned, contract_id, installed}` ; un clic attribue (contrat choisi :
   compatible avec le sujet et non plein) ou retire ; dépassement signalé et
   notifié (`licenses.gap`).
4. **Installeur / désinstalleur** — `POST /actions` `{agent_id, action:
   install|uninstall, package, manager?, confirm: <agent_id>}` → commande
   `software_action` à l'agent du poste (`si_agent/swctl.py` : apt-get, dnf,
   brew, winget, choco ; ligne de commande construite depuis des paramètres
   validés, `PKG_RE`, jamais de shell), état suivi (`pending → done |
   failed`, sortie tronquée), journal et notification `licenses.action`.
   Confirmation par l'identifiant de l'agent, comme les VM (#572).

## Modèle

- `software` : nom, éditeur, catégorie, **motifs** de reconnaissance
  (sous-chaînes ou `re:`) dans les noms relevés, **paquets** par gestionnaire
  (`{winget, apt, brew, dnf}`) pour pré-remplir l'installeur.
- `contracts` : logiciel, **site**, libellé, type (`per-user`, `per-device`,
  `subscription`, `perpetual`, `site`, `free`), quantité (0 = illimité),
  début / fin, coût / an, renouvellement, compte vendeur + SKU, référence.
- `assignments` : contrat × (`user` | `host`) sujet, site, date, note
  (`import`, `vendeur`, libre) ; unique par contrat et sujet.
- `vendor_accounts`, `actions`, `events`.

Écarts (`GET /gaps`, `rules.gaps`) : installé sans contrat, expiré, expire
bientôt (`LICENSES_EXPIRING_DAYS`, 60 j), sur-attribué, sur-installé (par
poste), payé inutilisé, licences disponibles, attribué mais non installé,
installé mais non attribué. Rapprochement (`rules.match_installations`) :
motifs du catalogue sur nom / éditeur relevés, bruit système exclu
(runtimes, mises à jour, paquets dpkg / rpm sans motif explicite).

## Utilisateurs par site (#597)

Toute l'authentification passe par le LDAP (Keycloak fédéré) ; certaines
applications ont en plus leur propre table. La table `users` de
licenses-api suit ce modèle : **l'annuaire fait référence** (`POST
/users/sync` lit les comptes Keycloak via `accounts-api /users` : login, nom,
adresse, activé → lignes `directory = 1`, source `ldap`), les personnes
venues d'un import ou d'un vendeur sont des **infos** (`directory = 0`,
source `import` / `vendeur` / `manual`) rattachées automatiquement au compte
LDAP dès qu'il existe — par login, adresse, « Prénom Nom » ↔ `prenom.nom`,
« M. NOM », initiales uniques ou alias déclarés (`rules.resolve_person`) ;
les attributions suivent le rattachement. Le **site** est renseigné dans
la tuile (colonne éditable) ou par l'import (site du formulaire) et n'est
jamais écrasé par la synchronisation. La grille d'un site liste tous ses
utilisateurs, attribués ou non. `GET /users?site=`, `POST /users`
(ajout / modification, alias), `DELETE /users/<login>` (refusé s'il reste
des attributions).

### Analyse croisée avec l'annuaire (#598)

Automatique (`LICENSES_DIRECTORY_INTERVAL`, 3600 s ; bouton « Synchroniser
l'annuaire » pour forcer) : présence de chaque compte et **groupes**
relevés depuis l'annuaire. Groupe(s) `LICENSES_FORMER_GROUPS` (défaut
`anciens`, à créer dans Comptes / LDAP et y placer les personnes parties) :
membre + licences attribuées = 🚫 alerte rouge dans la table, écart
critique `user-former` dans le tableau de bord et notification
`licenses.gap` (une par changement de liste) ; compte disparu de
l'annuaire = ⚠ `user-missing` (jamais supprimé, ses attributions restent
visibles) ; compte désactivé = ⛔ `user-disabled` ; personne hors annuaire
avec licences = ℹ `user-unknown`. Filtre « alertes seulement ».

### Fiches ownCloud (#600)

Le ownCloud principal (ancienne version) tient les **fiches utilisateurs**
(fichier texte par personne : identifiant, adresse, clés de licence,
comptes…) et un sous-dossier « anciens utilisateurs ». Connecteur
`licenses/api/owncloud.py` : WebDAV `remote.php/webdav` (ownCloud 8 à 10,
Nextcloud), PROPFIND + GET, lecture seule, Basic avec un **accès du
coffre** (utilisateur + mot de passe ownCloud, jamais stocké ici).
Paramétrage dans la tuile (Utilisateurs → carte « Fiches ownCloud » :
adresse, dossier, accès, sous-dossier des anciens, TLS, période ; « Tester
la connexion », « Lire les fiches ») ; `GET/PUT /owncloud`,
`POST /owncloud/test`, `POST /owncloud/sync`. Chaque fiche est rapprochée
d'un utilisateur (adresse, puis nom) ou créée « info » (source `owncloud`)
; mémorisé : résumé **masqué** (champs, clés `••••LMNO`, logiciels
détectés, date), jamais le texte ; fiche dans le sous-dossier des anciens →
alerte « ancien (fiche ownCloud) » et écart critique si licences
attribuées, plus `user-former-active` (fiche ancien mais compte LDAP
actif hors groupe anciens) — croisement LDAP ↔ ownCloud ↔ attributions.
Texte complet : `POST /users/<login>/fiche` (administrateur, journalisé
`fiche-read`, jamais conservé). Relecture automatique dans le fil
d'analyse croisée (`interval`, 6 h par défaut).

### Compte administrateur Microsoft 365 (#602)

Type de compte vendeur `microsoft-account` : pas d'inscription d'application.
Deux façons de s'authentifier, toutes deux avec le client public « Microsoft
Graph PowerShell » (`vendors.PUBLIC_CLIENT_ID`, pré-consenti dans la plupart
des tenants, permissions déléguées `Organization.Read.All` +
`User.Read.All`) :

- **connexion par code** (recommandée, compatible MFA) : `POST
  /vendors/<n>/connect` renvoie un code ; la personne l'entre sur
  microsoft.com/devicelogin avec le compte administrateur ; le hub
  interroge `/connect/status` puis mémorise le **jeton de rafraîchissement**
  dans `settings` (base hors dépôt, jamais renvoyé par l'API ;
  `/disconnect` l'efface) ;
- **e-mail + mot de passe** : accès du coffre (utilisateur = e-mail) → flux
  ROPC. Microsoft le refuse dès que l'authentification multifacteur est
  exigée (AADSTS50076 — obligatoire pour les comptes administrateurs depuis
  2025) ou si le tenant a désactivé ce flux : le message renvoie alors vers
  la connexion par code.

Synchronisation : mêmes données que l'application Entra (SKU, quantités,
utilisateurs). Les **factures** ne sont pas exposées par l'API Microsoft :
elles restent sur le portail (lien « gérer chez le vendeur ») et s'importent
par le format « contrats ».

### Chez le vendeur (#598)

Chaque compte vendeur porte un lien **« gérer chez le vendeur ↗ »** vers le
portail d'administration des licences (défaut par type : Microsoft 365 →
centre d'administration, page Licences ; `config.url` pour le remplacer ou
pour un vendeur sans API) ; les contrats liés à un compte affichent le même
lien. Le hub ne se connecte pas au portail à la place de la personne : la
lecture passe par l'API (Graph), les gestes d'achat / résiliation restent
sur le portail avec le compte administrateur du client.

## Import des tableurs (`POST /import`, multipart `file`, `site`, `dry_run`)

Formats détectés : **contrats** (#602 : « Logiciel | Éditeur | Site | Libellé |
Type | Quantité | Début | Fin | Coût / an | Compte vendeur | SKU | Référence |
Notes | Personnes », une ligne par contrat, type en mot (utilisateur, poste,
abonnement, perpétuelle, site, gratuit) ; ré-import = mise à jour du contrat
de même logiciel + site + libellé ou référence), **matrice** (en-tête « Logiciel | Éditeur | Licence |
Date Fin | personne… » ; les noms des personnes sur la ligne d'en-tête ou
la ligne du dessus (en-têtes fusionnés) ; **toute marque non vide** compte —
croix, « n », « oui », 1, date — sauf « non / 0 / - » ; une colonne
« Personnes / Utilisateurs » listant des noms est aussi lue), **export Microsoft 365**
(colonnes « Nom complet », « Nom d'utilisateur », « Licences » séparées par
`+`), **comparatif** (licences en lignes × initiales en colonnes). `.xlsx`
(openpyxl) ou `.csv` (séparateur détecté). Analyse d'abord (plan : logiciels, personnes reconnues → login, personnes
absentes de l'annuaire signalées), puis import : logiciels et contrats manquants créés sur le site, personnes
attribuées ; ré-import idempotent.

## Droits, sécurité

Lecture libre depuis le hub (comme les autres tuiles) ; **toute écriture**
exige un jeton Keycloak vérifié (`si-proxy/admin/auth.py`, groupe
`LICENSES_ADMIN_GROUPS`, défaut `administrateurs`). Aucun secret en base :
comptes vendeurs → nom d'accès du coffre. L'API est routée par tls-proxy
(`/api/licenses/`). Base SQLite `licenses/data/licenses.sqlite` (**à
sauvegarder**, hors dépôt).

## Tuile « Licences logicielles » (Données & référentiels)

Sélecteur de site en tête ; onglets : Tableau de bord (écarts triés,
totaux par logiciel avec lampe), Contrats & catalogue (formulaires, import),
Grille d'affectation (sujets × logiciels, sticky, ✓ attribué / ● installé),
Postes & installations (postes relevés, détail filtrable, « vus mais absents
du catalogue » en un clic, installer / désinstaller avec confirmation,
actions suivies), Vendeurs (comptes, synchronisation), Journal. Note
design : en-têtes fixés, corps qui défilent, filtre début de mot, pied fixe.

## Déploiement

```
cd ~/SRC/data2/tickets/supervision-si
./scripts/run.sh up -d --build licenses-api si-agent-api hub
./gateway/scripts/run.sh up -d --force-recreate tls-proxy
```

Puis : mettre les agents des postes en 0.5.16 (Agents hôtes → Mises à
jour), activer la sonde `software-inventory` sur chacun ; dans la tuile,
importer les tableurs existants (Analyser puis Importer) ; créer le compte
vendeur Microsoft 365 (accès du coffre = secret client) et synchroniser.

## Tests

`cd licenses/api && python3 -m unittest test_rules test_vendors test_app`
(13 : rapprochement, écarts, imports, grille, Graph simulé, garde Keycloak,
contrats / attributions, actions vers un central simulé). Agent :
`test_software_inventory.py` (4), `test_swctl.py` (3). Hub :
`tests/licensesLib.test.mjs` (4).

## Non vérifié

Sur super : relevés réels Windows (PowerShell inline), synchronisation
Graph avec une vraie application, `winget` sous le service agent (session 0
: winget n'est pas toujours disponible hors session utilisateur ; repli
`choco` conseillé), import des trois tableurs réels (structure seule
testée).
