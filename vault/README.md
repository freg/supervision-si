# Coffre-fort de codes/secrets — chiffrement de bout en bout

Codes d'accès (contrôles d'accès, équipements sécurisés) destinés au
personnel de maintenance, avec extension prévue vers un coffre de
mots de passe complet. Sujet d'une nature différente du reste de ce
projet — décidé explicitement avec la personne après avoir pesé la
complexité contre la sensibilité réelle (conséquences physiques en
cas de fuite, pas juste une gêne opérationnelle).

## État d'avancement — fondation posée, pas encore d'interface

Cette session a construit et testé à fond les **deux couches les
plus critiques** (cryptographie + stockage), volontairement avant
toute interface — chaque décision au-dessus (modèle de collections,
révocation, récupération) avait besoin d'être posée solidement en
premier. **Aucun front, aucun lien hub, aucun câblage Docker-Compose
n'existe encore** — prochaine étape.

## Chiffrement de bout en bout — le choix fondateur

**Le serveur ne voit et ne stocke jamais rien en clair.** Aucune clé
capable de déchiffrer quoi que ce soit ne lui est jamais transmise —
vérifié structurellement (`vault/api/app.py` n'importe aucune
bibliothèque de chiffrement, testé via l'arbre syntaxique réel, pas
une recherche de texte qui se ferait polluer par les commentaires
explicatifs).

### Schéma de chiffrement hybride (`shared/vaultCrypto.js`)

Le problème que ça résout : plusieurs personnes, chacune avec son
propre mot de passe maître **jamais transmis au serveur**, doivent
accéder à des sous-ensembles différents de secrets (accès fin décidé
avec la personne — par site/équipement/groupe) sans que le serveur
détienne jamais de quoi déchiffrer quoi que ce soit.

1. Chaque **utilisateur** a sa propre paire de clés RSA-OAEP (2048
   bits). La clé privée est chiffrée avec une clé dérivée de son mot
   de passe maître (PBKDF2-SHA256, 600 000 itérations — recommandation
   OWASP actuelle, pas un nombre arbitraire) avant d'être envoyée au
   serveur. La clé publique est stockée en clair (c'est son rôle).
2. Chaque **collection** (site, équipement, groupe...) a sa propre
   clé symétrique AES-256, générée aléatoirement.
3. Donner accès à quelqu'un = "envelopper" la clé de collection avec
   SA clé publique RSA — une petite entrée par (collection,
   utilisateur), jamais besoin de rechiffrer les secrets eux-mêmes
   pour accorder un accès.
4. Chaque **secret** (libellé ET valeur, les deux chiffrés — même un
   libellé comme "Porte principale, Bâtiment A" peut être sensible)
   est chiffré avec la clé AES de sa collection.

**Accès fin par groupe Keycloak — limite cryptographique réelle** :
en chiffrement asymétrique, on ne peut pas "envelopper une clé pour
un groupe" — chaque personne a besoin de sa propre enveloppe
individuelle. Un groupe Keycloak pourra servir de raccourci pratique
côté interface ("ajouter tout le monde de ce groupe d'un coup") une
fois construit, mais créera toujours une entrée individuelle par
personne en dessous — pas un vrai contournement de cette limite,
juste une commodité d'interface.

### Détection de mot de passe incorrect — "gratuite", pas une vérification séparée

AES-GCM inclut une étiquette d'authentification : déchiffrer avec la
mauvaise clé fait échouer `crypto.subtle.decrypt()` avec une
exception, jamais un déchiffrement silencieux vers des données
corrompues. **Aucune vérification de mot de passe séparée n'existe ni
ne doit être ajoutée** — un second chemin de vérification, plus
faible, serait une régression de sécurité classique dans ce genre de
système.

### Récupération en cas de mot de passe oublié

Contrepartie assumée du chiffrement de bout en bout : sans copie de
secours, un mot de passe maître oublié rend le coffre définitivement
irrécupérable, par personne, pas même un administrateur — propriété
voulue, pas un défaut. Une **clé de récupération** (256 bits
d'entropie aléatoire) enveloppe une **deuxième copie indépendante**
de la même clé privée — affichée une seule fois à la création du
compte, à imprimer/conserver en lieu sûr par la personne, jamais
stockée nulle part sous une forme exploitable. Les deux chemins
(mot de passe et clé de récupération) mènent à la même clé privée
fonctionnelle — vérifié explicitement.

### Révocation d'accès — limite connue et assumée

Supprimer un accès (`DELETE /collections/<id>/access/<login>`)
empêche cette personne d'obtenir la clé de collection **à l'avenir**,
mais ne peut rien contre une copie déjà récupérée avant la révocation
— le serveur ne sait même pas ce qui a été mis en cache côté client,
propriété inhérente au chiffrement de bout en bout. Une révocation
réellement étanche demanderait de faire tourner la clé de collection
et rechiffrer tous les secrets qu'elle protège — pas fait dans cette
version, à construire si le besoin devient concret.

## Vérifié réellement — 66 tests, avec la vraie API Web Crypto

**30 tests Node** (`shared/vaultCrypto.js`) — utilisant
`globalThis.crypto.subtle`, la même implémentation W3C Web Crypto que
celle du navigateur (disponible nativement en Node ≥ 19, aucune
simulation) :
- Cycle complet création/verrouillage/déverrouillage de compte
- **Mauvais mot de passe → échec** (la propriété de sécurité la plus
  fondamentale de tout le système)
- Scénario multi-utilisateur complet : Alice crée, partage avec Bob,
  **Eve (jamais autorisée) ne peut déchiffrer ni l'enveloppe d'Alice
  ni celle de Bob**, même en essayant avec sa propre clé privée
  valide
- Altération d'un secret chiffré → détectée et rejetée (intégrité
  AES-GCM), jamais un déchiffrement corrompu silencieux
- Aucune réutilisation de nonce (IV) entre deux chiffrements
- Clé de récupération : déverrouillage alternatif fonctionnel,
  mauvaise clé de récupération → échec, les deux chemins mènent à la
  même clé privée utilisable

**36 tests Python** (`vault/api/app.py`) :
- CRUD utilisateurs, collections, accès, secrets
- **Contrôle d'accès = la requête elle-même** : une collection sans
  accès accordé n'apparaît tout simplement jamais dans les résultats,
  jamais un filtre appliqué après coup
- Révocation testée : effective, jamais de fuite vers un tiers non
  concerné
- Mises à jour partielles non destructives (modifier une valeur ne
  touche jamais le libellé chiffré à côté)
- **Confirmation structurelle** (analyse de l'arbre syntaxique Python
  réel, pas une recherche de texte) : aucune bibliothèque de
  chiffrement importée dans ce fichier

## Interface web — parcours complet, branché et testé

Suite directe de la fondation (chiffrement + stockage). Cette tranche
livre le reste :

- **Client OIDC `vault-portal`** (Keycloak, même mécanique PKCE que
  hub/portail tickets) — l'authentification identifie QUI se
  connecte, mais ne donne PAS accès aux secrets eux-mêmes : ça reste
  entièrement séparé, protégé par le mot de passe maître, jamais
  connu de Keycloak ni du serveur.
- **`vault/portal/src/vaultOps.js`** — couche d'orchestration
  (chiffrement + appels réseau), séparée des composants React pour
  rester testable : création de compte, déverrouillage (mot de passe
  ou clé de récupération), changement de mot de passe, création de
  collection, octroi d'accès, création/déchiffrement de secret.
- **Interface complète** : création de compte avec affichage unique
  de la clé de récupération (case à cocher "j'ai conservé cette clé"
  avant de continuer — jamais un simple bouton "OK" qu'on presse sans
  y penser), déverrouillage, liste des collections, détail d'une
  collection (secrets cachés par défaut, révélables un par un, ajout,
  gestion des accès).
- **Câblage complet** : `docker-compose.yml` (services `vault-api` +
  `vault-portal`), routage `tls-proxy`, variables `.env`, lien réel
  depuis le hub (`VITE_VAULT_PORTAL_URL`, plus la condition "pas
  encore de front" retirée, comme prévu la dernière fois).

**Vérifié réellement** : 21 nouveaux tests sur `vaultOps.js` (Node,
avec la vraie API Web Crypto ET un simulateur d'API en mémoire assez
complet pour tester un vrai enchaînement multi-appels) — notamment un
scénario complet à deux utilisateurs réels (Bob déchiffre correctement
un secret créé par Alice après avoir reçu l'accès), et qu'un
changement de mot de passe invalide bien l'ancien tout en laissant la
clé de récupération intacte. Cumulé avec la fondation : **87 tests
réels** sur l'ensemble du coffre (30 cryptographie + 36 stockage + 21
orchestration).

**Non vérifié dans cet environnement de développement** : le rendu
visuel réel (pas de navigateur ici) — la logique est testée à fond,
l'apparence et l'ergonomie concrète restent à confirmer par la
personne au premier vrai test.

## Recherche par localisation — fondation du modèle de données

Chantier en cours, demandé pour recentrer l'app autour de sa vraie
raison d'être : retrouver un code par sa localisation géographique
(bâtiment/étage/pièce/point d'accès), pas juste une liste de secrets
classés en collections abstraites. Cette tranche pose le **modèle de
données uniquement** (backend + schéma), avant tout écran — décidé
explicitement avec la personne vu l'ampleur du sujet.

**Décision de sécurité assumée, explicite** : le lien entre un secret
et sa localisation est stocké **en clair** (`secrets.localisation`) —
jamais le libellé ni la valeur du secret, qui restent chiffrés de
bout en bout comme avant. Compromis choisi avec la personne : le
serveur peut voir "tel bâtiment a des codes", jamais lesquels ni pour
quoi — au bénéfice d'une recherche/arbre de navigation rapide côté
serveur, plutôt que de tout déchiffrer côté client juste pour
construire un arbre de navigation.

**Corrélation label ↔ localisation : OBLIGATOIREMENT côté client.**
Le libellé d'un secret est chiffré de bout en bout — le serveur ne le
voit jamais. Toute logique de corrélation (analyser le libellé,
proposer une localisation correspondante) doit donc tourner dans le
navigateur, après déchiffrement, en comparant localement aux données
géographiques (non sensibles, elles) récupérées depuis l'API
Supervision SI. Pas encore construite dans cette tranche — la
fondation de données est en place pour l'accueillir.

**Hiérarchie bâtiments/étages/pièces/points d'accès** : extension des
géolocalisations *existantes* de Supervision SI (`pixel-grid`),
partagée entre les deux outils plutôt que dupliquée — voir
`pixel-grid/README.md`. Referencée depuis le coffre par une simple
chaîne de texte (`secrets.localisation`), jamais une vraie contrainte
FK inter-services (bases séparées).

**"Partage à tous" par défaut** : nouveau champ `collections.is_public`.
**Limite cryptographique assumée, dite clairement** : accorder l'accès
à une collection exige TOUJOURS que quelqu'un qui a déjà la clé en
clair fasse l'enveloppement pour le nouveau venu — personne ne peut se
l'auto-accorder, propriété du chiffrement de bout en bout. "Partage à
tous" fonctionne donc pour tous ceux qui ont un compte **au moment de
la création du code** ; un nouvel arrivant plus tard nécessite un
geste (même automatisé, via `maître_clefs` par exemple) de quelqu'un
qui a déjà accès — pas encore construit.

**Suivi d'usage** (`secrets.access_count`, `last_accessed_at`) pour le
futur "top 10 des codes utilisés" — un compteur simple incrémenté via
`POST /secrets/<id>/record-access`, appelé quand la VALEUR (pas
juste le libellé) est révélée. Ne révèle jamais ce qu'est le secret,
juste qu'il a été consulté.

**Nouvelles routes** : `GET /users` (logins + clés publiques,
nécessaire pour envelopper une collection publique à l'intention de
tout le monde), `POST /secrets/<id>/record-access`.

**Vérifié réellement** : 20 tests sur les nouvelles routes/colonnes
vault-api (comptes, collections publiques, localisation, suivi
d'usage, préservation du contenu chiffré lors d'une mise à jour de
localisation seule).

## Écran de recherche par localisation — le premier écran, enfin livré

Suite de "fondation du modèle de données" — la personne a signalé
l'écran manquant, jamais construit après la pose du modèle (les
urgences LDAP/boutons ont pris le pas). Rattrapé : `VaultView` a
désormais deux onglets, **🔍 Recherche** (nouveau, PAR DÉFAUT — priorité
explicitement demandée) et **📁 Collections** (existant, préservé tel
quel).

**Trois colonnes, comme demandé** :
- **Gauche** : arbre bâtiments/étages/pièces/points d'accès (`pixel-grid`,
  lecture seule) + champ de recherche sur les noms de localisation.
  Onglet "🗺️ Carte" visiblement présent mais désactivé ("bientôt") —
  nécessiterait Leaflet, absent de ce front, jamais ajouté en douce
  sans le dire.
- **Centre** : liste des codes, filtrable par libellé, triable
  (alphabétique par défaut, plus utilisés, récemment consultés).
- **Droite** : top 10 par usage réel (`access_count`).

**Trou comblé au passage** : `POST /secrets/<id>/record-access`
existait côté backend depuis la pose du modèle de données, mais
jamais appelé nulle part — le "top 10" serait resté vide pour
toujours. Câblé maintenant aux deux endroits où une valeur est
révélée (l'écran de collection existant ET ce nouvel écran).

**Chargement** : `loadAllDecryptedSecretLabels()` (`vaultOps.js`)
parcourt TOUTES les collections accessibles, déverrouille chacune,
déchiffre chaque libellé — nécessaire puisque cet écran n'est plus
organisé par collection. Une collection dont la clé échoue à se
déverrouiller est ignorée plutôt que de faire échouer tout le
chargement, signalée honnêtement à la personne plutôt que cachée.

**Logique pure séparée** (`vaultSearchLib.js`, autonome, comme
`owncloudLib.js`) : construction de l'arbre depuis la liste plate des
géolocalisations, recherche de descendants (cliquer un bâtiment montre
aussi ses étages/pièces), filtres, tri, top N. 30 tests réels sur
cette logique + 9 sur le chargement agrégé (dont le cas central :
une collection corrompue n'empêche jamais le reste de charger).

**Reste** : le mode Carte (dépendance Leaflet à ajouter), l'écran
d'ajout/modif avec corrélation assistée, l'écran de partage. Le "tri
par préférence utilisateur, à imaginer/paramétrer" reste pour l'instant
un sélecteur simple (3 modes) — pas encore persisté par compte comme
le thème (`prefs-api`) pourrait le permettre.

## Changer le mot de passe — trou d'interface comblé

`vaultOps.js:changePassword()` existait déjà (probablement depuis la
construction initiale du coffre) mais n'était appelée nulle part dans
`App.jsx` — aucun bouton, aucun écran, impossible à atteindre. Ajouté :
bouton "🔑 Mot de passe" dans l'en-tête (visible une fois déverrouillé
seulement), ouvre une modale (nouveau motif `.vault-modal-overlay`,
premier du genre dans ce front).

Pas de ressaisie du mot de passe ACTUEL demandée dans la modale : la
clé privée est déjà déchiffrée en mémoire à ce stade (le coffre est
déverrouillé), la repreuve serait redondante — `changePassword()`
n'a d'ailleurs même pas besoin de l'ancien mot de passe. Même règle de
longueur qu'à la création (12 caractères min.).

**Propriété de sécurité centrale, vérifiée réellement** : la clé
privée RSA elle-même ne change JAMAIS lors d'un changement de mot de
passe — seule son enveloppe est reconstruite. Tous les accès déjà
accordés à des collections restent valides sans aucune action
supplémentaire, et la clé de récupération continue de fonctionner
exactement pareil (jamais touchée par cette opération). 7 tests réels,
dont la comparaison directe des octets bruts de la clé RSA obtenue par
le nouveau mot de passe contre celle obtenue par la clé de
récupération — confirmé : rigoureusement la même clé.

## Modèles de fiche — évolution du chantier précédent

Découle directement des champs multiples : pouvoir enregistrer une
structure de champs créée à la volée (ex. "Carte SIM" -> PUK/PIN/
Numéro) comme **modèle** réutilisable, puis parcourir les secrets
**par modèle**.

**`secret_templates`** (nouvelle table) -- nom + liste de libellés de
champs, **EN CLAIR** : pure métadonnée de structure, jamais de
contenu de secret (même raisonnement que `keyword`/`localisation`).
**Globaux**, pas liés à une collection -- un modèle "Carte SIM" a du
sens à travers tout le coffre.

**`secrets.template_id`** -- référence LOGIQUE (comme `localisation`),
jamais une vraie contrainte FK : supprimer un modèle ne doit jamais
casser les secrets qui le référençaient, juste leur faire perdre le
regroupement. Testé explicitement.

**Interface** : dans le formulaire d'ajout/édition, sélecteur "Utiliser
un modèle…" (préremplit les libellés, contenu vide à saisir) et bouton
"💾 Enregistrer comme modèle" (extrait les libellés ACTUELS, jamais le
contenu). Dans l'écran de recherche, nouvel onglet "📋 Modèles" --
**portée volontairement différente des mots-clés** : compte seulement
ce qui est déjà chargé/accessible, pas étendu à toutes les collections
comme `GET /keywords`. Choix assumé : parcourir par modèle est un
outil d'organisation, pas le même besoin d'urgence cross-accès qui
avait motivé l'exception pour les mots-clés. Le filtre par modèle se
compose avec le filtre par localisation (ex. "cartes SIM du
Bâtiment A" -- les deux peuvent s'appliquer en même temps).

Vérifié réellement : 16 tests backend (dont le point important --
suppression d'un modèle sans casser les secrets), 3 tests de
migration douce, 6 tests frontend bout en bout, 14 tests sur le
filtrage/comptage par modèle. Non-régression complète sur tout le
coffre-fort (44 tests au total sur ce chantier).

## Champs multiples et observations — retours d'un utilisateur final

Chantier "A" d'une série de retours après tests réels : codes à
plusieurs champs (login/mot de passe), champs personnalisés ajoutables,
observations horodatées en liste.

**Simplification agréable trouvée en concevant** : le contenu "valeur"
d'un secret est déjà un blob chiffré opaque pour le serveur (E2E) --
changer CE QUI est sérialisé dedans (une liste de champs plutôt qu'une
chaîne simple) **ne nécessite donc aucun changement de schéma côté
vault-api**. Uniquement `vaultFieldsLib.js` (nouveau, logique pure de
sérialisation) et l'interface qui l'utilise.

**Rétrocompatibilité assumée, jamais de migration en masse** (impossible
de toute façon : le serveur ne peut rien déchiffrer pour transformer
quoi que ce soit) -- `parseFields()` accepte aussi bien le nouveau
format (JSON, liste de `{label, content}`) que l'ancien (simple
chaîne) : un ancien secret jamais réédité reste lisible tel quel,
traité comme un unique champ implicite sans libellé affiché,
exactement comme avant ce chantier. Testé explicitement contre des cas
piège (une ancienne valeur qui ressemble PAR COÏNCIDENCE à du JSON,
ex. `"[1,2,3]"` ou `"true"`) -- jamais explosée en faux champs.

**Observations** (`secret_observations`, nouvelle table) -- liste
horodatée, CHIFFRÉE comme le libellé/les champs (demande explicite :
"tout est chiffré"). Contrairement à `secret_history` : vraie
contrainte FK avec `ON DELETE CASCADE` -- une observation n'a aucun
sens sans le secret qu'elle documente (jamais une trace d'audit à
préserver après coup, juste des notes de terrain), supprimer le secret
supprime logiquement ses observations. Testé explicitement : la
cascade fonctionne, contrairement à l'historique qui, lui, survit
volontairement (voir plus bas).

Interface : "🔑 Identifiants" en préréglage pratique (ajoute Login +
Mot de passe d'un coup), "+ Ajouter un champ" pour toute structure
personnalisée. Affichage : un seul champ sans libellé montre juste le
contenu (comme avant), plusieurs champs affichent chacun avec son
libellé. Bouton "💬 Observations" à côté de "🕒 Historique", même
principe (un secret ouvert à la fois, jamais les deux zones dépliées
ensemble).

Vérifié réellement : 13 tests sur les observations (backend, dont la
cascade), 18 tests sur la logique de champs (dont la rétrocompatibilité
avec des cas piège), 8 tests bout en bout avec la vraie cryptographie.
Non-régression complète sur tout le coffre-fort.

**Reste** (retours du même utilisateur, chantiers séparés) : interface
responsive, survol-copie, copie partielle par sélection/mot ; le
super-utilisateur maître_système à accès permanent sur toutes les
collections.

## Archivage et retour en arrière — dernier chantier de la liste

Le plus gros morceau de la série de retours, traité en deux temps
(backend puis frontend).

**`secret_versions`** (nouvelle table) -- contrairement à
`secret_history` (jamais le contenu, volontaire), conserve un
**instantané chiffré complet** à chaque modification, capturé AVANT
d'appliquer le changement. Les deux tables coexistent pour des usages
différents -- `secret_history` reste le journal léger (dashboard,
audit), `secret_versions` sert uniquement la restauration.

**Suppression devenue archivage** -- `DELETE /secrets/<id>` ne
détruit plus jamais rien, marque `is_archived=1`. Visible par TOUS
les membres de la collection (demandé explicitement), restaurable
par le PROPRIÉTAIRE uniquement (`created_by`, vérification logique
côté serveur -- pas une garantie, `vault-api` ne vérifie aucun jeton,
caractéristique déjà connue de toute cette API).

**Retour en arrière** -- restaurer une ancienne version capture
D'ABORD l'état actuel dans une NOUVELLE version avant de l'écraser :
un retour en arrière reste toujours lui-même annulable, jamais une
opération à sens unique.

**`last_changed_by`** (nouvelle colonne) -- distinct de `created_by`
(qui ne change jamais), permet l'indicateur "✏️ modifié par X" sans
charger tout l'historique de chaque secret juste pour ça.

**Deux vrais bugs trouvés en testant** :
1. Le CASCADE de suppression des observations (`secret_observations`,
   livraison précédente) supposait une vraie suppression -- devenu
   incompatible avec l'archivage (rien n'est plus réellement
   supprimé). Comportement corrigé : les observations survivent
   désormais à un archivage, la contrainte CASCADE reste au niveau
   SQL pour une éventuelle future purge.
2. **`deleteJson()` (client API) n'a jamais accepté de corps de
   requête** -- `archived_by` n'était donc jamais réellement envoyé
   au serveur, l'archivage aurait échoué à 100% en production malgré
   des tests bien écrits sur le papier. Trouvé grâce au test
   frontend bout en bout (pas le test backend, qui appelle Flask
   directement sans passer par ce client) -- illustre pourquoi les
   deux niveaux de test comptent.

Vérifié réellement : 30 tests backend (versions, archivage,
restauration, autorisations propriétaire, cas limites), 12 tests
frontend bout en bout avec la vraie cryptographie. Non-régression
complète sur tout le coffre-fort (42 tests au total sur ce chantier,
confirmés stables sur 3 passages complets après les deux corrections).

**Toute la liste de retours utilisateur est maintenant traitée.**

## Survol-copie et copie partielle

Deux derniers points de la liste, traités ensemble (même composant).

**`CopyableValue.jsx`** (nouveau, réutilisable) -- remplace l'affichage
brut d'une valeur déchiffrée partout où elle apparaît : texte
NATIVEMENT sélectionnable (curseur début/fin, double-clic sur un mot
-- comportement du navigateur, rien à coder pour ça, juste ne jamais
le bloquer avec `user-select: none`), bouton de copie qui apparaît au
survol de la ligne (jamais totalement invisible au repos -- repérable
au clavier/tactile, où il n'y a pas de survol souris), et **liste de
mots cliquables** en dessous si la valeur contient plusieurs mots
(copie individuelle -- utile pour communiquer une phrase de passe mot
par mot, au téléphone par exemple).

**Bug réel trouvé en construisant ça** : le modal de révélation de
l'écran de recherche affichait encore la valeur BRUTE
(`revealedValue.value` tel quel) -- jamais mis à jour depuis l'ajout
des champs multiples. Une fiche à plusieurs champs (login/mot de
passe, par exemple) y aurait affiché du JSON brut au lieu des champs
proprement séparés. Corrigé au passage : réutilise `FieldsDisplay`
(le même composant que l'onglet Collections), plus de divergence
entre les deux écrans de révélation.

Vérifié réellement : 7 tests sur le découpage en mots (espaces
multiples/de bord, un seul mot, tabulations/retours à la ligne).
`navigator.clipboard` (API du navigateur) jamais testable dans ce
bac à sable -- vérifié par relecture attentive, jamais bloquant en
cas d'échec (la sélection manuelle reste toujours disponible).
Non-régression complète sur tout le coffre-fort.

**Chantier restant de la liste initiale** : archivage/versions avec
retour en arrière (le plus gros morceau) et interface responsive
(écrans hors recherche, jamais retouchés).

## Sélecteur de localisation, masquage par défaut, is_read_only

Trois points de la liste de retours, traités ensemble (deux touchent
la même infrastructure de localisation, le troisième était rapide une
fois `is_system_master` déjà en place).

**Masquage par défaut des localisations sans code** (écran de
recherche) -- `filterTreeToUsedOnly()` (nouveau, `vaultSearchLib.js`) :
retire un nœud SEULEMENT si NI lui NI aucun de ses descendants n'a de
code, préservant le contexte de navigation (même esprit que
`filterLocationTree`). Case à cocher "Montrer aussi les localisations
sans code" pour tout révéler -- jamais perdu, juste pas la vue de
départ.

**Vrai sélecteur de localisation** (onglet Collections) -- le champ
était un simple texte libre depuis le début, jamais un vrai choix
dans la hiérarchie. `LocationTreeNode` extrait de
`VaultSearchScreen.jsx` dans son propre fichier (fonctionne aussi
bien enrichi que brut, aucun changement nécessaire), réutilisé par le
nouveau `LocationPicker.jsx`. **Toujours la hiérarchie complète, jamais
filtrée par usage** -- contrairement à l'écran de recherche : il faut
pouvoir choisir un lieu qui n'a encore aucun code.

**`is_read_only` appliqué côté interface** -- masque : formulaire
d'ajout de secret, bouton "✏️ Modifier", formulaire d'ajout
d'observation (la liste reste visible, lisible), formulaire d'octroi
d'accès (la liste des accès existants reste visible), formulaire de
nouvelle collection, panneau de rattrapage maître_système. Révélation/
historique/consultation des observations restent toujours accessibles
-- seules les actions d'ÉCRITURE sont masquées. **Rappel important,
déjà documenté à la fondation des rôles** : `vault-api` ne vérifie
aucun jeton côté serveur -- ceci masque l'interface, ce n'est pas une
garantie de sécurité serveur.

Vérifié réellement : 8 tests sur le masquage par défaut (dont la
préservation d'un ancêtre ayant un descendant utilisé, et le cas
frère masqué à côté d'un frère conservé). Le reste (sélecteur,
`is_read_only`) vérifié par relecture attentive + vérification
renforcée (setters/imports) + syntaxe -- comportement d'interface
conditionnelle, pas de logique pure nouvelle à isoler en tests. Non-
régression complète sur tout le coffre-fort (24 fichiers de test).

## Bug réel bloquant — portail admin servi en HTTP, Web Crypto indisponible

Signalé en plein test réel : mot de passe systématiquement refusé sur
`vault-admin-portal`, alors que le même mot de passe fonctionnait sur
`vault-portal`.

**Cause trouvée** en suivant la trace réseau du navigateur jusqu'au
bout : la requête `GET /users/<login>` réussissait parfaitement (le
compte était bien trouvé, avec les bonnes données) -- l'échec venait
du DÉCHIFFREMENT lui-même (`deriveMasterKey`/`unwrapPrivateKey`,
`crypto.subtle`). Ce portail est servi en **HTTP simple**
(`http://<ip>:6120`, jamais derrière la passerelle HTTPS) -- or l'API
Web Crypto est **volontairement indisponible par les navigateurs hors
"contexte sécurisé"** (HTTPS ou `localhost`). Depuis la refonte
"débloquer un compte" (voir plus haut), ce portail utilise la même
cryptographie que le coffre principal -- chaque tentative de
déverrouillage échouait donc silencieusement, l'exception générique
étant mal interprétée en "mot de passe incorrect" plutôt que "la
primitive cryptographique n'existe pas ici".

**Corrigé** : `vite.config.js` sert désormais en HTTPS, réutilisant
le certificat déjà généré pour la passerelle principale (montage du
même `pki/server/` que `tls-proxy`) -- un certificat n'encode jamais
de port, valide malgré le port différent (6120 au lieu de 6443).
Repli propre sur HTTP simple si jamais le certificat n'est pas monté
(avertissement affiché au démarrage du conteneur), pour ne jamais
empêcher ce portail de démarrer.

**Accès change** : désormais `https://<ip>:6120` (pas `http://`) --
comme pour la passerelle principale, le navigateur affichera un
avertissement de certificat auto-signé à accepter une fois.

Vérifié réellement : logique de repli testée dans les deux cas
(certificat absent -- comportement de ce bac à sable ; certificat
présent -- lecture correcte simulée). Le comportement RÉEL du serveur
Vite en HTTPS (que le navigateur accepte bien la connexion et que
`crypto.subtle` devienne disponible) reste à confirmer en conditions
réelles, aucun navigateur disponible dans cet environnement.

**Confirmé résolu** par test réel après déploiement.

**Régression trouvée dans la foulée** : le lien vers ce portail
depuis le Hub (`VITE_VAULT_ADMIN_PORTAL_URL`) pointait encore vers
`http://` -- oubli de ma part en corrigeant le portail lui-même sans
chercher toutes les autres références à son URL dans le projet.
Corrigé.

## Séquestre maître_clefs jamais initialisé sur le déploiement réel

Retour de test réel, découvert en creusant un message d'erreur
trompeur : "Vous n'êtes pas membre de maitre_clefs" s'affichait pour
`francois`, alors que la console Keycloak confirmait bien son
appartenance au groupe.

**Cause trouvée** en examinant le code : `usurpMaitrePrincipal` ne
vérifie JAMAIS le groupe Keycloak -- il vérifie uniquement un accès
CRYPTOGRAPHIQUE explicite à une collection spéciale de séquestre,
accordé via `grantAccess`, un mécanisme complètement indépendant du
groupe. Le message d'erreur, lui, parlait à tort du groupe Keycloak.

**En creusant plus loin avec la personne** (requêtes SQL directes,
sans avoir besoin du mot de passe de qui que ce soit -- l'existence
d'un accès est une métadonnée en clair) : la collection de séquestre
**n'avait jamais été créée du tout** sur ce déploiement.
`createMasterKeyEscrow()` existait bien dans le code, testée
extensivement dans des scénarios isolés, mais **jamais reliée à un
bouton accessible nulle part** -- un amorçage jamais exposé
concrètement.

**Corrigé** :
- Message d'erreur reformulé pour ne plus mentionner le groupe
  Keycloak à tort.
- Nouvelle route `GET /escrow-status` (vault-admin-api, LAN + acteur)
  -- une question volontairement publique (juste un booléen, aucune
  donnée sensible), qui distingue "personne n'a jamais initialisé le
  séquestre" de "il existe, vous n'y avez juste pas accès" -- les deux
  se réparent différemment.
- `bootstrapMasterKeyEscrow(password, alsoGrantToLogin)` (vaultOps.js)
  -- amorce en un seul appel à partir du mot de passe de
  `maitre_principal` directement (jamais via usurpation, circulaire
  tant que le séquestre n'existe pas). Point corrigé après relecture :
  sans `alsoGrantToLogin`, la personne qui vient de fournir le mot de
  passe n'aurait PAS eu accès elle-même (seul le compte
  `maitre_principal` l'a, auto-octroyé à sa propre création) -- elle
  aurait dû refaire une étape séparée.
- Nouvelle section "🔑 Initialiser le séquestre" dans le portail admin
  -- affichée uniquement quand le séquestre n'existe vraiment pas
  encore, avec accès immédiat après amorçage.

Vérifié réellement, bout en bout, avec la vraie cryptographie :
amorçage depuis zéro, mauvais mot de passe refusé proprement, et
**accès immédiat à l'usurpation pour la personne qui vient d'amorcer**,
sans étape séparée. Constante `ESCROW_COLLECTION_NAME` dupliquée
manuellement entre Python et JS (aucun outillage monorepo dans ce
projet) -- comparaison caractère par caractère vérifiée, y compris
l'emoji. Non-régression complète sur tout le coffre-fort.

**Suite demandée** : pouvoir étendre l'accès au séquestre à d'autres
comptes de confiance directement depuis ce portail, sans repasser par
l'onglet Collections du coffre normal -- `grantEscrowAccess(targetLogin,
myLogin, myPrivateKey)` (réutilise `grantAccess` tel quel sur la
collection de séquestre, aucune logique dupliquée), nouvelle section
dans "🔓 Débloquer un compte" (visible dès que le compte connecté a
lui-même l'accès). Reste un octroi cryptographique NORMAL -- ne
contourne jamais la protection, rend juste triviale son extension.
Testé réellement : avant l'octroi, la cible ne peut pas usurper ;
après, elle le peut réellement ; un compte sans accès lui-même ne
peut jamais en accorder à un autre ; cible inexistante refusée
proprement.

## Portail admin — liens de navigation et sélecteur de thème

Retour explicite, avec un vrai oubli trouvé au passage : les liens
Hub/Coffre-fort ajoutés lors d'une livraison précédente avaient été
PERDUS lors de la réécriture complète du fichier pour la refonte
"débloquer un compte" -- jamais recopiés depuis l'ancienne version.

Corrigé, sur les DEUX écrans (connexion ET une fois connecté, pas
seulement le second comme avant) :
- Liens "🏠 Hub" et "🔐 Coffre-fort" (URLs absolues, ce portail vivant
  sur sa propre origine).
- Sélecteur de thème clair/foncé (☀️/🌙), même mécanisme que les 3
  autres fronts de la "famille 1" (`shared/theme.css`/
  `shared/preferences.js`, copiés au build). `admin.css` converti des
  couleurs codées en dur vers les variables CSS partagées.
  **Limite assumée** : la synchronisation croisée immédiate entre
  fronts (via `localStorage`) ne fonctionne PAS avec ce portail --
  origine différente (port 6120, séparé de la passerelle) --
  `localStorage` est isolé par origine. Seule la persistance par
  compte (`prefs-api`) traverse cette limite, pas la synchronisation
  en temps réel entre onglets.

Vérifié : syntaxe (tsc), équilibre CSS, setters cohérents.

## Réinitialiser un compte sans perdre les collections

Suite directe de la refonte précédente -- demande explicite : pouvoir
réinitialiser un accès sans perdre les données liées.

**Bug de conception réel découvert en construisant ça** :
`collections.created_by` portait une contrainte FK stricte,
contrairement à `secrets.created_by`/`secret_history.changed_by`
(volontairement non contraints, pour la même raison). Supprimer un
compte ayant créé UNE SEULE collection échouait avec `IntegrityError`
-- empêchant très concrètement ce que cette évolution devait permettre.
Corrigé à deux niveaux : le schéma de base (nouvelles installations)
et une vraie migration structurelle,
`ensure_collections_created_by_not_fk()`, qui retire la contrainte
sur les installations déjà en place -- s'exécute automatiquement au
démarrage, comme la migration UUID dont elle reprend exactement la
même technique (reconstruction de table, transaction atomique,
idempotente).

**Le principe qui rend ça possible** : redonner accès à une
collection ne nécessite jamais l'ancienne clé perdue -- il faut que
quelqu'un qui a DÉJÀ accès (autre membre, ou maître_système via
l'escrow) réattribue l'accès au NOUVEAU trousseau, avec le mécanisme
d'octroi déjà existant. **La vraie limite, assumée et documentée
dans l'interface** : ça ne fonctionne que pour les collections où
quelqu'un a encore accès au moment de la réinitialisation -- une
collection dont la personne réinitialisée était seule membre devient
définitivement perdue, propriété du chiffrement de bout en bout, pas
une limite de cet outil.

**Flux en trois temps** (portail admin, section "🔄 Réinitialiser un
compte") :
1. Aperçu AVANT toute suppression -- liste les collections de la
   personne, marque clairement lesquelles VOUS pourrez réattribuer
   (vous y avez accès) vs lesquelles seraient perdues.
2. Confirmation -- `DELETE /users/<login>` (vault-api), capture la
   liste des collections concernées avant tout nettoyage.
3. Une fois que la personne a recréé son compte : réattribution en
   masse via le mécanisme d'octroi normal (`grantAccess`), rien de
   spécial -- un compte réinitialisé redevient un simple nouveau
   membre.

Vérifié réellement, avec la vraie cryptographie de bout en bout :
scénario complet où le NOUVEAU compte (trousseau totalement
différent) déchiffre RÉELLEMENT ses anciennes collections après
réattribution -- pas une comparaison d'octets. Migration testée sur
une base simulant une installation déjà en place (contrainte
présente, puis absente après migration automatique au démarrage,
données intactes). 34 tests réels au total sur ce chantier,
non-régression complète sur tout le coffre-fort.

## Portail admin — refonte autour du vrai besoin (débloquer un compte)

Retour de test réel : le portail précédent (juste un tableau de
rôles) ne répondait pas au vrai besoin -- confusion sur le champ
"nom" (ne filtrait rien, servait seulement à la journalisation sans
que ce soit clair), et surtout : **aucun moyen concret de débloquer un
compte ayant perdu mot de passe ET clé de récupération**, alors que
c'était décrit comme l'utilité première de cet écran.

**Découverte en creusant** : toute la mécanique cryptographique
nécessaire existait déjà, construite lors d'une session antérieure
mais jamais reliée à une interface -- `usurpMaitrePrincipal()` (un
membre de `maitre_clefs`, déjà déverrouillé avec SA PROPRE clé,
retrouve et déchiffre la clé privée séquestrée de `maître_principal`
sans jamais connaître son mot de passe) et
`decryptArchivedRecoveryKey()` (déchiffre la clé de récupération
archivée d'un compte, avec la clé récupérée ci-dessus). Il ne
manquait que l'écran.

**Refonte** :
- **Connexion unique** (login + mot de passe du compte de
  l'administrateur lui-même) remplace le champ "nom" isolé --
  identifie la personne (journalisation) ET, si elle est membre de
  `maitre_clefs`, déverrouille la capacité de révélation. Le mot de
  passe ne quitte jamais le navigateur, exactement comme l'écran de
  déverrouillage du coffre lui-même.
- **"🔓 Débloquer un compte"** (nouvelle section) -- liste les comptes
  ayant une clé de récupération archivée, bouton "🔑 Afficher la clé"
  par compte (déchiffrement client-side), puis copie presse-papiers.
  La personne bloquée utilise ensuite cette clé elle-même via l'écran
  de déverrouillage normal -- ses collections ne sont jamais touchées.
- **Rôles** conservés en second panneau, avec un vrai filtre de
  recherche (répond à la confusion "taper un nom ne fait rien") et un
  badge 🔑 sur les comptes ayant une clé archivée. Note ajoutée sous
  le tableau : "Contrôle des récupérations" reste un simple marqueur
  pour l'instant -- la vraie capacité dépend du groupe Keycloak
  `maitre_clefs`, pas de cette case.
- `vaultOps.js`/`api.js`/`vaultCrypto.js` désormais copiés depuis
  `vault-portal` (source canonique) au moment du build -- jamais un
  fork dupliqué, toute correction faite côté coffre se répercute ici
  automatiquement.

Vérifié réellement : test bout en bout avec la vraie cryptographie,
scénario complet (maître_principal → escrow → membre maitre_clefs →
usurpation → révélation → **la victime se reconnecte RÉELLEMENT avec
la clé révélée**, pas juste une comparaison d'octets), plus le cas
négatif (un compte sans accès à l'escrow ne peut rien révéler). Non-
régression complète sur tout le coffre-fort.

**Reste de ce retour** (le coffre-fort lui-même, pas ce portail) :
champ URL, révélation momentanée + copie sans révéler, bouton effacer
presse-papiers, ajout d'observation pendant la consultation,
historique/versions à fusionner (création = version 0), partage
visible en lecture et déclenchable en édition -- chantier séparé à
venir.

## Portail admin — retour vers le hub et le coffre-fort

Retour réel après premier test : `vault-admin-portal` était un
cul-de-sac -- aucun lien de retour vers le hub, aucun accès au coffre
lui-même une fois dessus.

`href="/"` (motif utilisé par `vault-portal`, servi SOUS le même
gateway) ne suffit pas ici -- ce portail vit sur son propre port LAN,
origine différente. URLs ABSOLUES injectées via `docker-compose.yml`
(`VITE_HUB_URL`, `VITE_VAULT_PORTAL_URL`), affichées en haut d'écran,
ouvertes dans un nouvel onglet (revenir "en arrière" dans le même
onglet perdrait le contexte d'administration en cours).

Vide = lien masqué plutôt qu'un lien cassé, même philosophie que le
reste du projet.

## Lien vers l'administration du coffre-fort depuis le hub

Manquait après la livraison du portail admin -- ajouté au hub, même
motif que les autres liens conditionnels (Administration Keycloak,
DBA) : visible pour les groupes Keycloak `administrateurs` ou
`maitre_clefs` (groupe déjà existant, utilisé par le mécanisme
d'escrow des clés de récupération -- voir plus bas), invisible pour
tout le monde d'autre.

**Découverte importante en cherchant où l'accrocher** : le groupe
Keycloak `maitre_clefs` existe déjà et sert à un mécanisme
D'ESCROW DIFFÉRENT des nouveaux rôles `is_recovery_controller`/
`is_system_master` (base du coffre) -- deux systèmes "contrôle de
récupération" qui coexistent sans se parler pour l'instant :
- Le groupe Keycloak `maitre_clefs` détermine qui reçoit
  automatiquement l'accès à une collection d'escrow spéciale à la
  création de compte (voir `vaultOps.js`,
  `MASTER_KEY_ESCROW_COLLECTION_NAME`).
- `is_recovery_controller` (nouveau, base du coffre) est pour
  l'instant un simple marqueur, pas encore branché à une capacité
  concrète.

Pas réconcilié dans cette livraison -- signalé ici pour que ce ne
soit jamais découvert par surprise plus tard. Un chantier à part si
la personne le souhaite.

Vérifié réellement : 5 tests sur la visibilité conditionnelle du
nouveau lien (admin, maitre_clefs, aucun des deux, URL absente).
Non-régression complète sur le hub.

## Tableau de bord maître_système

Dernière pièce du chantier "rôles" : la partie "afficher pour
transmission orale" en réalité **rien à construire** -- le
maître_système, ayant accès permanent à chaque collection via
l'escrow, utilise simplement l'écran de recherche existant pour
trouver et révéler n'importe quel code, exactement comme un
utilisateur normal. Simplification reconnue plutôt que dupliquer une
interface qui existe déjà.

Ce qui manquait réellement : une **vue d'ensemble à travers tout le
coffre**, jamais possible pour un utilisateur normal (limité à ce
qu'il a accès). Nouvel onglet "📊 Tableau de bord", visible
uniquement si `is_system_master` (même compte connecté récupéré via
l'appel déjà existant à `GET /users/{login}`, aucun aller-retour
réseau de plus).

**`GET /history`** (nouvelle route vault-api) -- journal à travers
TOUT le coffre, ordre décroissant (le plus récent en premier,
contrairement à l'historique par secret). Jamais le contenu, comme
toujours -- juste qui/quand/motif/quel secret (par id, pas par
libellé).

**Stats et libellés du journal : calculés côté CLIENT**, jamais le
serveur -- techniquement impossible autrement (libellés chiffrés).
Réutilise `loadAllDecryptedSecretLabels` (déjà construit pour l'écran
de recherche) pour déchiffrer tout ce à quoi le maître_système a
accès, puis calcule stats/top10/journal annoté à partir de cette
liste en mémoire.

**Note transparente** : `GET /users/{login}` (route publique,
utilisée par quiconque veut accorder un accès à quelqu'un) expose
`SELECT *`, donc aussi les rôles de la personne consultée -- mineur
(pas une clé, pas un contenu), mais autant le documenter honnêtement
plutôt que de le passer sous silence.

Vérifié réellement : 5 tests sur le journal global (dont le
croisement de plusieurs secrets/collections différents et l'ordre
chronologique correct), 11 tests sur les statistiques et
l'association libellé/journal. Non-régression complète.

## Rattrapage et écran de gestion des rôles

Suite immédiate de la fondation ci-dessus.

**Rattrapage** (`backfillSystemMasterAccess`, `vaultOps.js`) —
comble le trou signalé : accorde l'accès maître_système aux
collections EXISTANTES qui ne l'ont pas encore. Ne peut être fait QUE
par quelqu'un ayant déjà accès (le maître_système ne peut évidemment
pas se l'accorder lui-même pour une collection à laquelle il n'a pas
encore accès). Bouton "↻ Rattraper l'accès maître_système" dans
l'onglet Collections. Idempotent -- relancer plusieurs fois ne
duplique jamais rien, testé explicitement.

**`vault-admin-portal`** (nouveau service) -- interface pour la
gestion des rôles, jusqu'ici seulement accessible par `curl` direct
contre `vault-admin-api`. Même raisonnement de sécurité que l'API
qu'elle sert : **jamais routée par la passerelle publique** (absente
de `tls-proxy/render_nginx_conf.py`), port exposé directement sur
l'hôte (`VAULT_ADMIN_PORTAL_LAN_PORT`, 6120 par défaut). Aucune
cryptographie ici -- ne manipule que des métadonnées de rôle
(booléens), toute la protection réelle reste dans `vault-admin-api`
(LAN + acteur déclaré + journalisation, inchangé). Un nom saisi une
fois en haut d'écran sert d'acteur journalisé pour chaque case
cochée/décochée.

Vérifié réellement : 11 tests sur le rattrapage avec la vraie
cryptographie (dont l'idempotence et la confirmation que le
maître_système peut effectivement déchiffrer après rattrapage).
Interface du nouveau portail validée en syntaxe (tsc) et équilibre
CSS -- jamais exécutée dans ce bac à sable (aucun outil de build
React/Vite disponible ici, mêmes limites que d'habitude pour tout ce
qui touche à la compilation front). Non-régression complète sur tout
le coffre-fort.

## Rôles — fondation du maître_système (chantier en cours)

Premier chantier d'une nouvelle série de retours. Trois capacités
**indépendantes et cumulables** (décision explicite après discussion —
jamais un rôle unique) ajoutées aux comptes coffre :

- **`is_read_only`** — ne peut jamais créer/modifier/supprimer,
  uniquement consulter. Appliqué **côté interface uniquement** pour
  l'instant : `vault-api` ne vérifie aucun jeton serveur sur ses
  routes (caractéristique déjà existante de toute l'architecture),
  donc ceci n'est pas une garantie de sécurité serveur.
- **`is_recovery_controller`** — contrôle des clés de récupération
  archivées (mécanisme `maître_clefs` existant). Ponctuel et ciblé.
- **`is_system_master`** — accès **permanent** : co-destinataire
  systématique de la clé de **chaque** collection dès sa création.

**Décision de sécurité prise avec la personne** : `is_recovery_controller`
et `is_system_master` restent volontairement **séparés**, jamais
fusionnés en un seul rôle tout-puissant — une même personne peut
cumuler les deux si voulu, mais le système les traite comme deux
capacités indépendantes (réduit ce qu'il y a à perdre si un compte
est un jour compromis).

**Escrow systématique** (`createCollection`, `vaultOps.js`) — chaque
nouvelle collection enveloppe désormais aussi sa clé pour tout compte
`is_system_master`, en plus du créateur. Testé avec la vraie
cryptographie : la clé de collection déchiffrée par le maître_système
est confirmée identique (mêmes octets bruts) à celle du créateur —
même secret, deux enveloppes.

**Gestion des rôles** (`vault-admin-api`, nouvelles routes
`GET /users` et `POST /users/<login>/roles`) — volontairement **pas**
dans `vault-api` (public) : assigner ou retirer un accès permanent
est une action sensible, même garde-fou LAN + acteur déclaré +
journalisation que le reste de cette API.

Vérifié réellement : 9 tests sur le filtrage par rôle côté vault-api,
15 tests sur la gestion des rôles côté vault-admin-api (garde-fous
LAN/acteur, mise à jour partielle sans réinitialiser les autres
rôles), 8 tests bout en bout sur l'escrow avec la vraie
cryptographie. Non-régression complète sur tout le coffre-fort.

**Reste à construire** (chantiers séparés, ampleur propre à chacun) :
- **Rattrapage** : les collections créées AVANT qu'un maître_système
  existe n'ont pas cette escrow rétroactivement -- nécessite qu'un
  membre déjà existant régénère l'octroi, pas quelque chose que le
  maître_système peut faire lui-même (il n'a justement pas encore
  accès).
- Écran de déchiffrement pour transmission orale + tableau de bord
  (stats + journal d'événements).
- Écran de gestion des rôles (l'interface elle-même -- les routes
  backend existent, rien pour les appeler encore côté portail).
- Application de `is_read_only` côté interface (masquer les actions
  de création/modification/suppression).
- Sélecteur de localisation + masquage des localisations inutilisées
  par défaut en recherche.
- Archivage/versions avec possibilité de retour en arrière.

## Écran de recherche — largeur et densité (retour utilisateur)

Deux bugs réels signalés après capture d'écran : tout l'écran de
recherche concentré dans une colonne de 720px (les 2/3 de l'écran
vides), et chaque fiche prenant 3 lignes (un seul libellé lisible à
la fois sans faire défiler).

**Largeur** — `.vault-main` (conteneur racine des écrans du coffre)
avait une largeur maximale de 720px, pensée pour les formulaires
étroits (connexion, ajout de collection), jamais adaptée à
l'agencement à 3 colonnes de l'écran de recherche. `VaultView`
notifie désormais son mode actif au composant parent
(`onViewModeChange`), qui applique `.vault-main-wide` (1400px)
uniquement quand la recherche est affichée -- les formulaires restent
resserrés et centrés comme avant, rien de changé pour eux.

**Densité** — chaque fiche de la colonne centrale passe d'un
empilement vertical (libellé, localisation, collection sur 3 lignes)
à une **seule ligne** : libellé qui s'étire et tronque si besoin,
localisation/collection toujours visibles à droite. Environ 3× plus
de fiches visibles sans défiler, dans le même espace.

## Priorité aux localisations réellement utilisées

Demandé après le chantier précédent : la localisation saisie dans un
code doit apparaître dans l'arbre du coffre-fort **en priorité** sur
les autres — l'arbre ne connaissait jusqu'ici QUE les géolocalisations
existantes (`pixel-grid`), jamais ce qui est réellement saisi dans les
codes.

**`enrichLocationTreeWithUsage()`** (`vaultSearchLib.js`) — deux
effets combinés :
1. **Jamais invisible** : une localisation saisie dans un code mais
   ABSENTE de la hiérarchie connue (nom pas encore créé côté
   géolocalisations) remonte quand même dans l'arbre, marquée "(non
   répertoriée)", en tête de liste.
2. **Priorité au sein de l'arbre connu** : à chaque niveau, les nœuds
   ayant au moins un code passent avant ceux qui n'en ont aucun
   (toujours alphabétique en cas d'égalité) — jamais noyé parmi des
   dizaines de lieux géolocalisés sans rapport avec le coffre.

**Bug évité, trouvé en écrivant les tests** : `collectLocationDescendants`
(retrouver les codes d'une localisation sélectionnée) était toujours
appelée sur l'arbre BRUT, qui ne connaît pas les nœuds "non
répertoriés" ajoutés par l'enrichissement — sélectionner l'un d'eux
n'aurait jamais retrouvé aucun code. Corrigé avant de livrer : appelée
désormais sur l'arbre enrichi.

Compteur visible par nœud (badge), lieux ayant des codes en gras.
Vérifié réellement : 14 tests, dont le scénario exact demandé
(localisation inconnue → visible en tête → ses codes bien retrouvés
en cliquant dessus).

## Modification, historique qui/quand/motif, mot-clé de navigation

Demandé après les premiers tests réels : pouvoir modifier un secret
existant, avec un historique détaillé (qui/quand/motif), plus une
localisation et un mot-clé personnalisé, tous deux modifiables et
historicisés.

**Décision de sécurité revue en cours de route** — le mot-clé était
d'abord conçu **chiffré**, comme le libellé/la valeur (même raisonnement
que pour éviter qu'il révèle du contexte sensible). Retour explicite
de la personne : c'est **contradictoire avec l'objectif même du
champ** — aider quelqu'un à retrouver un code EN URGENCE, y compris
avant d'avoir accès à la collection concernée, via une navigation par
mot-clé. Impossible si chiffré : personne ne peut parcourir ce qu'il
ne peut pas déchiffrer. Corrigé : le mot-clé est désormais **en
clair**, comme la localisation — seul ce niveau de catégorisation
devient visible, jamais le libellé exact ni la valeur, qui restent
chiffrés comme toujours. "Tout ne doit pas être visible" (dixit la
personne), juste assez pour savoir où chercher.

**`secret_history`** (nouvelle table) — qui/quand/motif, **jamais le
contenu avant/après** : pas un diff des blobs chiffrés (il faudrait de
toute façon les déchiffrer pour être lisible), juste la trace de
l'événement. Une entrée automatique à la création, une à chaque
modification (`changed_by` obligatoire, sans quoi la route refuse la
modification — impossible de modifier sans laisser de trace).

**Bug réel trouvé et corrigé** : la contrainte de clé étrangère sur
`secret_history.secret_id` empêchait de supprimer un secret ayant un
historique (`IntegrityError`). Retirée volontairement — devenue une
référence LOGIQUE, pas une vraie contrainte SQL : un historique doit
justement pouvoir SURVIVRE à la suppression de son sujet ("ce secret a
existé, a été modifié par X, supprimé par Y"), jamais bloquer cette
suppression.

**`GET /keywords`** — navigation par mot-clé À TRAVERS TOUTES les
collections, peu importe l'accès de la personne qui interroge. Expose
uniquement mot-clé + nom de la collection (savoir où chercher / qui
contacter), jamais le libellé exact ni la valeur. Testé explicitement
avec le scénario réel : Alice retrouve un mot-clé d'une collection de
Bob à laquelle elle n'a jamais eu accès. Nouvel onglet "🏷️ Mots-clés"
dans l'écran de recherche, à côté de l'arbre de localisation.

Interface : formulaire d'édition avec motif obligatoire (localisation
et mot-clé modifiables au passage), affichage de l'historique par
secret (bouton dédié, un secret ouvert à la fois).

Vérifié réellement : 26 tests sur l'historique/la suppression avec
historique existant, 15 tests bout en bout sur le mot-clé en clair et
la navigation cross-collection, 2 tests de migration douce. Toute la
suite existante du coffre rejouée sans régression — y compris un test
préexistant qu'il a fallu adapter (`changed_by` désormais obligatoire
pour toute modification, un changement d'API voulu).

## Instance isolée — fondation UUID (migration des identifiants)

Premier chantier vers un coffre déployable de façon isolée (Docker
stack séparé, synchronisable avec le hub principal — export du hub /
import depuis l'isolée, l'isolée ayant le dernier mot en cas de
conflit). Décisions prises avec la personne avant de commencer :
identifiants UUID (pas d'auto-incrément), aller-retour ponctuel (pas
une synchronisation continue), Keycloak simplifié mais gardant la
fédération LDAP existante (visible depuis internet, pas de mot de
passe séparé à gérer).

**Le problème résolu** : `collections.id`/`secrets.id` étaient des
entiers auto-incrémentés, **locaux à chaque base**. Deux instances
créant chacune "leur" collection #47 au même moment produiraient une
collision silencieuse et indétectable à la fusion — jamais un conflit
de contenu qu'on peut trancher, une vraie corruption. Migrés vers des
UUID v4 (`TEXT`), générés côté **serveur** (`uuid.uuid4()`, pas côté
client) — même garantie d'unicité globale, sans toucher au frontend
pour la génération (`vaultOps.js` n'a jamais fait d'hypothèse sur le
format de l'ID, aucun changement nécessaire là).

**Migration structurelle** (`ensure_uuid_ids()`, `vault/api/app.py`) —
reconstruction complète de `collections`/`secrets`/`collection_access`
avec le nouveau schéma, **en préservant toutes les relations** (chaque
secret retrouve le bon nouvel UUID de SA collection d'origine, jamais
mélangé). Idempotente (base déjà migrée = rien ne se passe), tourne
automatiquement au démarrage.

**Deux bugs réels trouvés par les tests, avant qu'ils ne touchent des
données réelles** :
1. Connexion sans `row_factory = sqlite3.Row` -- `dict(row)` plantait
   sur un simple tuple.
2. Fermetures de connexion redondantes entre les sorties anticipées
   et le `finally`.

**Une découverte plus sérieuse** : le module `sqlite3` de Python ne
place PAS les instructions `CREATE`/`DROP`/`ALTER TABLE` dans la
transaction annulable par défaut — un `rollback()` n'aurait rien
défait en cas de panne en plein milieu de la reconstruction, malgré
les apparences. Isolé et confirmé par un test dédié avant d'écrire le
correctif (`isolation_level=None` + `BEGIN` explicite). **Vérifié en
simulant une vraie panne en plein milieu de la migration** : la base
reste alors EXACTEMENT comme avant, aucune table temporaire oubliée.

**7 routes** (`/collections/<id>/access`, `/secrets`,
`/record-access`...) passées de `<int:...>` à des identifiants texte
simples.

Vérifié réellement : 25 tests dédiés à la migration (cas normal,
idempotence, base très ancienne sans les colonnes ajoutées depuis,
base vide, base fraîche, **panne simulée en plein milieu**), plus
toute la suite de tests existante du coffre-fort (vaultOps, maître_clefs,
changement de mot de passe, écran de recherche...) rejouée sans
aucune régression.

**Reste** : le stack Docker isolé lui-même (Keycloak simplifié +
LDAP, vault-api, vault-admin-api, vault-portal, rien d'autre), et le
mécanisme d'export/import avec priorité à l'instance isolée en cas de
conflit.

## Deux bugs réels corrigés après capture d'écran

**IP réseau dans l'arbre de localisation** — le géocodage réseau
(équipements scannés automatiquement, table `geolocations` partagée
avec `pixel-grid`) et la vraie hiérarchie bâtiment/étage/pièce
cohabitent dans la même table. Retour précis de la personne : le
critère n'est PAS "a une hiérarchie ou pas" (une entrée orpheline
peut très bien être un nom abrégé ou un numéro d'équipement légitime,
jamais à exclure pour cette seule raison) — c'est "ressemble à une
IP ou pas". `looksLikeIpAddress()` (`vaultSearchLib.js`) exclut
précisément les entrées au format `\d+.\d+.\d+.\d+`, jamais autre
chose. 14 tests réels, dont la conservation explicite des orphelines
légitimes à côté de l'exclusion des IP.

**"Déchiffrement impossible" à la révélation** — bug réel, retrouvé en
relisant `loadAllDecryptedSecretLabels()` très attentivement : la
fonction construit un objet "secret" transformé pour la liste
(libellé déjà déchiffré, pratique pour trier/filtrer sans re-déchiffrer
à chaque rendu) mais **jetait les champs chiffrés bruts de la
VALEUR** dans ce même objet. Cliquer pour révéler cherchait ces
champs sur l'objet transformé — absents, échec systématique.
`encrypted_value_iv`/`encrypted_value_ciphertext` désormais conservés
en plus du libellé déjà déchiffré ; nouvelle fonction
`decryptSecretValueOnly()` (ne redéchiffre jamais inutilement le
libellé une deuxième fois, contrairement à `decryptSecret()` qui
exige aussi les champs `encrypted_label_*`). 4 tests reproduisant
EXACTEMENT le scénario rapporté (création → chargement pour l'écran
de recherche → révélation), plus une vérification ajoutée au test
d'agrégation existant pour ne plus jamais régresser dessus.

## Reste à construire

- Application Android — reportée volontairement (voir échange avec la
  personne : aucun SDK Android, émulateur, ni moyen de compiler/tester
  un APK dans cet environnement de développement ; livrer du code non
  vérifiable pour un coffre-fort de codes d'accès serait plus
  dangereux qu'utile)
- Rotation de clé de collection à la révocation (voir la limite déjà
  documentée plus haut — pas construit dans cette version)
- Édition/suppression de secrets existants (création et lecture
  fonctionnent, la modification n'est pas encore câblée côté
  interface — la route API `PUT /secrets/<id>` existe déjà)

## Observations dans le popup de recherche + ajout unifié par "+"

Demandé en priorité par la personne pour son premier client/collègue
en attente.

**Mini-tableau d'observations** (popup "🔓 <libellé>" ouvert depuis
"🔍 Recherche") -- jusqu'ici les observations n'existaient que côté
écran Collections. Réutilise intégralement le mécanisme déjà
existant et testé (`addSecretObservation`/`fetchSecretObservations`,
`vaultOps.js`) -- `secret.collectionKey` est déjà porté par chaque
résultat de recherche (`loadAllDecryptedSecretLabels`), aucun nouveau
déchiffrement à construire. Toujours affiché (pas de bascule
masquer/montrer, contrairement à l'écran Collections) -- ce popup
est déjà centré sur un seul secret. Chargement des observations
indépendant de la révélation de la valeur : un échec de déchiffrement
du mot de passe n'empêche jamais de consulter/ajouter des
observations.

**Ajout unifié par bouton "+"** -- demandé explicitement, en
remplacement des panneaux "Nouvelle collection"/"Ajouter un secret"
jusqu'ici toujours visibles. "+" à droite de "Vos collections (n)"
et de "Secrets (n)", formulaire replié par défaut, fermé
automatiquement après une création réussie. Même motif CSS
(`.vault-panel-header-row`/`.vault-add-btn`) aux deux endroits, pour
rester cohérent visuellement.

Vérifié : syntaxe (tsc) sur `App.jsx` en entier, équilibre CSS.
**Non vérifié dans cet environnement** : rendu visuel réel, aucun
navigateur disponible ici -- la logique (chargement, ajout,
réinitialisation des formulaires) suit exactement les mêmes motifs
que le code déjà existant et éprouvé en conditions réelles.

**Reste noté dans `BACKLOG.md`** : une page "Observations" dédiée
(vue d'ensemble des codes avec/sans observation) -- mise en page à
clarifier avec la personne avant de commencer.

## Bug réel — modale de révélation trop étroite, débordement CSS

Signalé par deux captures d'écran : la modale de révélation d'un
secret (recherche) était plafonnée à 420px (`.vault-card`, pensée à
l'origine pour un écran de connexion centré) -- bien trop étroit pour
afficher confortablement champs et tableau d'observations. Une
observation contenant un jeton long sans espace (ex. un hash Docker
sha256) ne pouvait jamais se couper (`white-space: pre-wrap` seul ne
coupe qu'aux espaces existants), forçant tout le tableau à déborder.

**Corrigé** :
- `.vault-modal` élargie explicitement (`max-width: min(92vw, 1100px)`,
  spécificité `.vault-card.vault-modal` > `.vault-card` seul).
- `overflow-wrap: break-word` ajouté sur la première colonne du
  tableau d'observations -- coupe en dernier recours un mot trop long
  pour tenir, sans jamais casser un texte normal avec de vraies
  espaces.
- Vue Collections également élargie (`vault-main-wide`, jusque-là
  réservée à `search`/`dashboard`, restait plafonnée à 720px) --
  demandé explicitement ("le skin à élargir là aussi"). L'ajout
  d'observations y était déjà fonctionnel (gated par `!isReadOnly`),
  seule la largeur manquait.

Vérifié : syntaxe (tsc), équilibre CSS, classes toutes définies.
Non-régression confirmée sur les tests observations existants (fichier
`vaultCrypto.js` temporairement copié depuis `shared/` pour ce test,
absent par défaut de ce bac à sable -- normalement fourni au build).
**Non vérifié dans cet environnement** : rendu visuel réel, aucun
navigateur disponible ici.

## Remplacement du "Top 10" par une liste complète triée par usage

Demandé explicitement : "j'ai abusivement employé l'expression [Top
10]... ce qui est nécessaire c'est une liste ordonnée de tous les
codes par ordre décroissant d'utilisation". Plus une préférence
personnelle sur les colonnes affichées, et une préférence marquée
pour les vues tableaux défilables horizontalement.

**`vaultSearchLib.js`** : `topUsedSecrets(secrets, n=10)` renommée
`usedSecretsByFrequency(secrets, n)` -- `n` désormais optionnel
(absent = tous les codes déjà utilisés, sans plafond). Le tableau de
bord (`DashboardScreen.jsx`) garde volontairement un résumé limité à
10 (cohérent avec l'usage d'un tableau de bord -- vue d'ensemble
rapide, pas exhaustive) ; seul l'écran de recherche, ciblé par la
capture d'écran d'origine, reçoit la liste complète.

**Interface** : le widget "🔥 Top 10 utilisés" devient "📊 Utilisation
des codes" -- un vrai tableau (`<table>`), défilable horizontalement
si nécessaire (`overflow-x: auto`), colonnes Libellé/Utilisations
toujours visibles, Collection/Localisation/Dernier accès
optionnelles via des cases à cocher. Colonne de droite élargie
(260px → 380px) pour réduire le besoin de défilement dans le cas
courant.

**Préférence personnelle sur les colonnes** : stockage LOCAL simple
(`localStorage`, même principe que `createLocalThemeStore`) plutôt
qu'une extension de `prefs-api` -- une préférence purement
cosmétique, jamais sensible ni utile d'un appareil à l'autre, ne
justifiait pas la complexité d'un aller-retour serveur. Repli propre
sur "tout visible" si absente ou corrompue, jamais une exception si
`localStorage` est indisponible (navigation privée, quota).

Vérifié réellement : 9 tests supplémentaires (3 sur le nouveau
comportement "sans limite" de `usedSecretsByFrequency`, dont le
tri décroissant sur l'ensemble ; 6 sur la préférence de colonnes, y
compris JSON corrompu et `localStorage` indisponible). Test existant
(`test_vault_search_lib.mjs`) mis à jour pour le renommage. Classes
CSS toutes vérifiées présentes. Non-régression complète (tous les
tests liés à la recherche/dashboard/observations relancés).

**Non vérifié dans cet environnement** : rendu visuel réel, aucun
navigateur disponible ici.

## Page "Observations" — chantier initialement en backlog, clarifié puis livré

Demandé le 2026-08-26, mis en backlog faute de mise en page claire
("au centre et à gauche" restait ambigu). Repris le 2026-08-28 :
plutôt que d'essayer de recoller les morceaux du texte d'origine, la
personne a confirmé vouloir un vrai **redesign** -- proposition faite
et validée avant de construire : un tableau unique, filtrable/
triable, avec détail dépliable par ligne, plutôt que plusieurs zones
séparées.

**Backend** : nouvelle route `POST /secrets/observations-summary` --
résumé agrégé (nombre + date la plus récente) pour un ENSEMBLE de
secrets en une seule requête (évite un aller-retour en N+1 par
secret). Jamais le texte des observations ici (chiffré, inutile pour
un résumé -- juste compter/dater côté serveur, sans déchiffrement).
POST plutôt que GET avec paramètres de requête -- la liste
d'identifiants peut dépasser vite la limite pratique d'une URL.

**Logique pure** (`vaultSearchLib.js`) : `mergeSecretsWithObservationsSummary`
(fusionne secrets déchiffrés + résumé, jamais de mutation),
`filterSecretsByObservationPresence` (tous/avec/sans), 
`sortSecretsByObservationCriteria` (récence/nombre/alphabétique --
les jamais-observés toujours en dernier au tri par récence, quel que
soit le sens).

**Interface** (`ObservationsScreen.jsx`, nouvel onglet "📝
Observations") : tableau unique, filtrable et triable, colonnes
Libellé/Collection/Localisation/Nombre d'observations/Plus récente.
Cliquer une ligne la déplie et charge (déchiffre) ses observations
complètes, la plus récente en premier -- chargement différé au dépli
uniquement, jamais tout déchiffré d'un coup pour l'ensemble du
tableau. Même esprit tableau/défilement horizontal que "Utilisation
des codes", motif apprécié explicitement par la personne.

Vérifié réellement : 39 tests sur ce chantier (11 sur la route
backend avec de vraies données SQLite, dont la vérification explicite
qu'aucun contenu chiffré ne fuit dans un résumé censé n'être que des
métadonnées ; 11 sur les trois fonctions pures ; classes CSS toutes
vérifiées présentes une par une). Bug corrigé en cours de route :
fragment `<>` sans `key` dans une boucle `.map()` (React l'interdit),
remplacé par `<Fragment key={...}>`. Non-régression complète
(recherche, dashboard, observations, rôles, filtre "déjà utilisés",
maître des clés, versions -- tous relancés).

**Non vérifié dans cet environnement** : rendu visuel réel, aucun
navigateur disponible ici -- l'interaction de dépli de ligne mérite
particulièrement d'être confirmée en conditions réelles.

## Bug réel — encore de l'espace perdu malgré l'élargissement précédent

Signalé de nouveau après le premier élargissement (720px → 1400px) :
toujours de l'espace inutilisé sur un écran suffisamment large,
`.vault-main-wide` restait plafonné à une valeur fixe (1400px) qui
finit par redevenir trop étroite sur un grand moniteur.

**Corrigé** : plafond fixe retiré au profit d'une largeur relative à
la fenêtre (`max-width: 97vw`) -- s'aligne vraiment sur le bord de
l'écran, demandé explicitement, plutôt qu'une valeur fixe qui reste
toujours en retard sur la taille réelle de l'écran.

Vérifié : équilibre CSS. **Non vérifié dans cet environnement** :
rendu visuel réel, aucun navigateur disponible ici.

## Ajout de collection/secret depuis l'écran de Recherche

Demandé explicitement (backlog #1) : jusqu'ici, créer une collection
ou un secret n'était possible que depuis l'écran "📁 Collections", en
naviguant jusqu'à la bonne collection -- pas pratique quand on est
déjà en train de chercher/parcourir depuis l'écran "🔍 Recherche".

**Aucune logique parallèle** : réutilise `createCollection`,
`createSecret`, `unlockCollectionKey` (déjà utilisés par l'écran
Collections, `vaultOps.js`, inchangés) et le même composant de
formulaire `FieldsEditor` (modèles, préréglage login/mot de passe,
enregistrement comme modèle). `FieldsEditor` était jusqu'ici défini
directement dans `App.jsx`, non exporté -- extrait dans son propre
fichier `FieldsEditor.jsx` pour permettre cette réutilisation sans
créer d'import circulaire entre `App.jsx` et `VaultSearchScreen.jsx`
(le second est déjà importé par le premier).

**Interface** (`VaultSearchScreen.jsx`) : deux formulaires repliés
par défaut, mêmes boutons "+" que partout ailleurs dans le
coffre-fort, dans l'en-tête de la colonne centrale (résultats) :
- **📁+ Nouvelle collection** -- identique au formulaire de l'écran
  Collections. Après création, prévient le parent (`onCollectionsChanged`,
  nouvelle prop) pour que la liste de l'onglet Collections reste
  synchronisée sans avoir à changer d'onglet.
- **🔑+ Nouveau secret** -- recharge la liste COMPLÈTE des
  collections accessibles à chaque ouverture du formulaire (via
  `fetchCollectionsForUser`), pas seulement celles ayant déjà un
  secret : `allSecrets` (voir `loadAllDecryptedSecretLabels`) ne
  liste que des secrets existants, une collection tout juste créée
  et encore vide en serait absente sinon. La clé de la collection
  choisie n'est déverrouillée qu'au moment de la sélection/soumission
  (jamais toutes les clés d'un coup juste pour peupler la liste
  déroulante). Après création réussie, rechargement discret de
  `allSecrets` (`reloadSecretsAfterChange`) pour que le nouveau
  secret apparaisse immédiatement dans les résultats de recherche.

Formulaires masqués si `isReadOnly` (nouvelle prop, propagée depuis
`VaultView`), comme partout ailleurs dans le coffre-fort.

Vérifié : syntaxe (`tsc --jsx`) sur les trois fichiers touchés
(`App.jsx`, `VaultSearchScreen.jsx`, `FieldsEditor.jsx`) ; classes CSS
utilisées toutes vérifiées présentes une par une dans `vault.css` ;
correspondance setters `useState` déclarés ↔ appelés vérifiée sur les
deux fichiers (aucun état orphelin). **Non vérifié dans cet
environnement** : aucun test automatisé réellement exécuté (pas de
`node_modules`/harnais Node dans ce dépôt, pas d'accès réseau pour
`npm install`) ni rendu visuel réel -- seules la syntaxe et la
cohérence statique ont été contrôlées. Ce chantier mériterait
particulièrement un test manuel en conditions réelles avant de le
considérer acquis.

## Présentation "révéler"/"historique"/"versions" en tableau

Backlog #2. Demandé : passer la présentation "révéler"/"historique" en
tableau à 2 colonnes (labels/contenus), avec une 3e colonne
(timestamp) pour l'historique -- clarifié avec la personne (question
ciblée posée avant de construire, les deux écrans ont des garanties
différentes) : "les deux écrans" concernés sont en réalité **Versions**
(⏱️, a déjà le contenu -- restauration) et **Historique** (🕒, jamais
le contenu -- choix de conception assumé, alimente aussi le tableau de
bord CROISÉ TOUTES COLLECTIONS du maître_système via
`fetchGlobalHistory`).

**Décision prise, à confirmer avec la personne si elle voulait
davantage** : les TROIS présentations (révéler, versions, historique)
sont maintenant de vrais `<table>`, mais **le contenu n'a PAS été
ajouté à Historique** -- l'écran Versions couvre déjà exactement ce
besoin (label/contenu/date, restaurable), y dupliquer l'aurait recréé
en parallèle (voir `disciplined-engineering`, principe #6) tout en
touchant un choix de sécurité documenté (`secret_history` jamais
décrypté ni stocké en clair côté serveur, portée délibérément limitée
pour le tableau de bord cross-collection). Si la personne veut
réellement le contenu dans Historique aussi (fusion des deux écrans,
ou duplication assumée), ce sera un vrai chantier de schéma
(`secret_history` en base) à cadrer séparément.

**`FieldsDisplay`** (révéler, utilisé à la fois dans la ligne de
secret de l'écran Collections et dans le popup de révélation de
l'écran Recherche) : tableau Libellé/Contenu, cas "simple" (un seul
champ sans libellé) inchangé (affiche juste le contenu, comme avant).

**Versions** : une ligne PAR CHAMP (un secret multi-champs = plusieurs
lignes pour la même version), colonnes Libellé/Contenu + Modifié
le/Motif/Action affichées seulement sur la première ligne du groupe
(pas de `rowSpan`, jamais utilisé ailleurs dans ce module -- répétition
évitée plutôt qu'une complexité CSS inhabituelle ici). **Bug réel
corrigé au passage** : le contenu d'une version n'était jamais reparsé
via `parseFields` avant affichage -- un secret multi-champs affichait
donc du JSON brut sérialisé dans l'ancienne présentation en liste,
jamais remarqué faute d'avoir eu un secret multi-champs modifié depuis
l'introduction des champs multiples. Vérifié réellement : logique pure
(`parseFields`/`serializeFields`/`isSimpleSingleField`) testée via Node
avec des cas réels (ancien format simple chaîne, nouveau format
multi-champs round-trip, un seul champ AVEC libellé explicite, chaîne
vide/undefined, JSON valide mais de forme inattendue -- jamais
d'exception, retombe proprement sur le texte brut).

**Historique** : tableau Action/Auteur/Date/Motif -- toutes les
colonnes réellement disponibles, sans inventer une colonne "Contenu"
vide.

Vérifié : syntaxe (`tsc --jsx`), toutes les classes CSS utilisées
présentes une par une, logique pure testée (voir ci-dessus), aucune
classe CSS orpheline laissée par l'ancienne présentation (`grep`
vérifié). **Non vérifié dans cet environnement** : rendu visuel réel,
aucun navigateur disponible ici -- la disposition du tableau
"révéler" DANS la ligne flex du secret (`.vault-secret-row`, écran
Collections) mérite particulièrement une confirmation (largeur du
tableau non forcée à 100% délibérément pour ce contexte, contrairement
à Versions/Historique qui sont dans un bloc pleine largeur).

## Format (modèle) associé à une collection

Backlog #1 (le plus gros morceau du backlog coffre-fort). Le système
de modèles était global uniquement (visible/utilisable depuis
n'importe quelle collection), sans notion de champ obligatoire.
Question ciblée posée avant de construire ("obligatoire" bloquant ou
indicatif ?) -- réponse : **indicatif seulement, jamais bloquant à
l'enregistrement d'un secret**. Décision qui a simplifié tout le
design : aucune validation côté serveur à ajouter, juste un ordre
d'affichage (obligatoires en premier) et un marqueur visuel.

**Backend** (`vault-api`) : `secret_templates` gagne deux colonnes via
migration douce (`ensure_secrets_new_columns`, jamais une recréation) :
`collection_id` (nullable -- `NULL` = modèle global, comportement
historique inchangé) et `required_labels` (JSON, sous-ensemble de
`field_labels`, filtré côté serveur pour rester cohérent -- jamais une
valeur fantôme stockée si le client envoie un libellé qui n'existe
pas dans les champs). `GET /templates` accepte `?collection_id=` :
retourne les modèles globaux + ceux de CETTE collection, jamais ceux
d'une autre (testé explicitement, voir plus bas). Référence LOGIQUE
vers `collections.id`, même raisonnement que `secrets.template_id`
(une collection supprimée ne doit jamais faire planter la lecture
d'un modèle qui la référençait).

**Frontend** :
- `vaultFieldsLib.js` : deux nouvelles fonctions pures --
  `defaultRequiredLabels` (coche Login/Mot de passe par défaut à la
  création d'un nouveau format, demandé explicitement, insensible à
  la casse) et `orderFieldsRequiredFirst` (tri STABLE, obligatoires en
  premier, jamais de réordonnancement surprise au sein d'un même
  groupe).
- `FieldsEditor.jsx` : le panneau "💾 Enregistrer comme modèle" gagne
  une case "obligatoire" par champ (visible seulement pendant cet
  enregistrement) et un choix de portée (cette collection / globale,
  affiché seulement si `collectionName` est fourni par l'appelant).
  En dehors de ce panneau, un marqueur "*" (couleur `--accent`, jamais
  une couleur d'alerte -- indicatif, pas une erreur) s'affiche à côté
  d'un champ dont le libellé correspond à un `requiredLabels` transmis
  par l'appelant (format déjà appliqué).
- Écran **Collections** (`CollectionDetail`) : modèles chargés scopés
  à la collection ouverte (`fetchTemplates(collection.id)`).
  Application d'un modèle (ajout ou édition) réordonne les champs et
  mémorise les obligatoires pour le marqueur visuel ; à l'ouverture de
  l'édition d'un secret déjà lié à un modèle, ses obligatoires sont
  retrouvés s'il existe encore (référence logique, jamais une
  exception s'il a été supprimé depuis).
- Écran **Recherche** (formulaire d'ajout construit précédemment,
  backlog #1 de la livraison #106) : les modèles proposés sont
  RECHARGÉS à chaque changement de collection choisie dans le menu
  déroulant (`addFormTemplates`, distinct de `allTemplates` qui reste
  volontairement global pour l'onglet "📋 Modèles", un parcours
  cross-collection différent) -- jamais les modèles d'une collection
  non sélectionnée proposés par erreur. Même case obligatoire/portée
  disponible ici aussi.

Vérifié réellement :
- **Backend** : `app.test_client()`, base de test isolée. Création
  globale (comportement historique confirmé inchangé), création
  scopée avec `required_labels`, filtrage silencieux d'un libellé
  obligatoire incohérent (absent de `field_labels`), **isolation
  stricte entre collections** (la collection B ne voit jamais un
  modèle scopé à A), validations existantes toujours en place. Un
  **second scénario dédié à la migration** : base simulant l'ANCIEN
  schéma (sans les nouvelles colonnes) avec un vrai modèle existant
  dedans -- confirmé après migration que ce modèle n'est jamais perdu
  ni corrompu, et qu'un nouveau modèle scopé peut être créé
  immédiatement sur cette même base migrée.
- **Logique pure** (`defaultRequiredLabels`/`orderFieldsRequiredFirst`) :
  testée via Node, cas limites (casse, espaces de bord, listes vides/
  undefined, tri stable au sein d'un même groupe).
- Syntaxe (`tsc --jsx`) sur les 5 fichiers touchés, classes CSS toutes
  vérifiées présentes, correspondance setters `useState`
  déclarés/utilisés sur les 3 fichiers React.

**Non vérifié dans cet environnement** : rendu visuel réel, aucun
navigateur disponible ici -- le panneau d'enregistrement de modèle
(case obligatoire + choix de portée) mérite particulièrement une
confirmation en conditions réelles. **Non fait, à noter** : la liste
de parcours par modèle (onglet "📋 Modèles", écran Recherche)
n'affiche pas encore visuellement la portée (global/collection) d'un
modèle -- omission mineure assumée pour contenir la portée de ce
chantier, pas un oubli caché.

## Ajout d'observation directement depuis l'onglet "📝 Observations"

Backlog. Jusqu'ici, ajouter une observation n'était possible que
depuis un secret ouvert/révélé (écran Collections ou popup de
révélation en Recherche) -- jamais depuis cet écran dédié, alors
qu'une ligne dépliée montre déjà les observations existantes.

**Réutilise `addSecretObservation` tel quel** (`vaultOps.js`, même
fonction que les deux autres endroits) -- la clé de collection est
déjà disponible sur chaque secret (`loadAllDecryptedSecretLabels`
l'attache systématiquement), aucun déverrouillage supplémentaire
nécessaire. Formulaire (input + "+ Ajouter") affiché dans la ligne de
détail dépliée, masqué en mode lecture seule (nouvelle prop
`isReadOnly`, propagée depuis `VaultView`, absente jusqu'ici sur cet
écran). Réinitialisé à chaque dépli/repli de ligne -- jamais un texte
d'une ligne qui traîne sur une autre.

**Mise à jour optimiste après ajout** : recharge uniquement les
observations de LA ligne concernée (pas tout le tableau), et met à
jour le résumé (`summary`, colonnes Observations/Plus récente)
LOCALEMENT à partir de la liste rechargée -- jamais un
`fetchObservationsSummary` complet sur tous les secrets pour une
seule ligne modifiée, même esprit que le reste du projet
(`FieldsEditor`, etc.).

Vérifié réellement : syntaxe (`tsc --jsx`), classe CSS présente,
correspondance setters `useState` déclarés/utilisés (aucun faux
positif cette fois), accolades JSX équilibrées. Logique de mise à
jour locale du résumé testée via Node -- première observation d'un
secret qui n'en avait aucune, secret qui en avait déjà, et surtout
**non-régression vérifiée explicitement sur les AUTRES secrets du
tableau** (jamais écrasés par erreur lors de la mise à jour ciblée).
**Non vérifié dans cet environnement** : rendu visuel réel, aucun
navigateur disponible ici.

## Branchement rights-api sur vault-admin-api (livraison #291)

Suite au backlog item 38, troisième service branché après
ssh-tunnels-api (#289) et ldap-admin-api (#290). **Confirmé
explicitement par la personne** avant de coder : même évolution que
pour LDAP, pas une contradiction avec "toute la protection réelle
reste dans vault-admin-api (LAN + acteur déclaré + journalisation)"
-- une couche supplémentaire, pour réserver la gestion des rôles
(dont `is_system_master`, accès PERMANENT à chaque collection) à une
catégorie d'utilisateurs plus précise.

**Portée volontairement limitée** à `POST /users/<login>/roles` --
les routes de lecture de l'archive de récupération gardent leur
protection cryptographique de fond (voir "TROIS COUCHES DE
PROTECTION" dans `vault/admin-api/app.py`), jamais touchées ici :
même si un appelant contournait rights-api, ce qu'il obtiendrait
resterait un blob chiffré inutilisable sans la clé privée du compte
maître_principal.

**Ordre de vérification** : `require_lan_and_actor` (garde-fou
existant, journalise CHAQUE tentative, autorisée ou refusée) reste
en PREMIER -- contrairement à ldap-admin-api où le droit se
vérifie avant tout le reste, ici préserver la journalisation
systématique déjà documentée comme importante ("un accès refusé est
en soi un signal à ne pas perdre") prime. Le droit `rights-api` est
vérifié ENSUITE, avant l'écriture réelle en base.

**⚠️ Manque réel, signalé clairement plutôt que passé sous
silence** : contrairement à ssh-tunnels-api et ldap-admin-api (routés
par le hub, qui transmet fidèlement les groupes Keycloak de la
personne connectée), `vault-admin-portal` n'est **pas** authentifié
via Keycloak -- juste un nom en texte libre saisi en haut d'écran,
jamais vérifié contre un compte réel. **Activer `RIGHTS_API_URL`
sans adapter aussi le portail bloquerait TOUT LE MONDE** dès
l'activation (aucun octroi ne matchera jamais un groupe vide). Le
backend est prêt et testé ; donner à `vault-admin-portal` un moyen
réel de transmettre des groupes (authentification Keycloak à part
entière, ou un mécanisme plus léger à définir) reste un chantier
séparé, PAS commencé ici -- noté au backlog.

**Vérifié réellement** : `_check_manage_right` testé en isolation
(gating désactivé, autorisé, refusé, FAIL CLOSED). Câblage réel
testé sur `set_user_roles` -- confirmé qu'un refus n'écrit RIEN en
base (rôle inchangé), et que la même action réussit une fois le
droit accordé. Non-régression des routes de lecture reconfirmée
(jamais gatées).

## Authentification Keycloak de vault-admin-portal (livraison #293)

Comble le manque signalé en #291 (backlog item 42) : `vault-admin-portal`
gagne une authentification Keycloak réelle, rendant enfin utilisable
en pratique le gating rights-api construit en #291.

**Découverte importante en cours de route** : contrairement à ce que
laissait penser la description initiale ("un nom en texte libre"),
le champ `login`/`password` existant sert en réalité à **dériver une
vraie clé privée cryptographique** (`unlockWithPassword`) pour
débloquer certaines fonctions ("débloquer un compte") -- pas du
texte libre sans conséquence. Keycloak s'ajoute donc EN PLUS,
délibérément jamais en remplacement de ce mécanisme existant, laissé
totalement intact.

**Client Keycloak `vault-admin-portal`** ajouté à
`keycloak/realm-template.json` (même structure que `vault-portal` :
Authorization Code + PKCE S256, mapper de groupes) -- SEULEMENT dans
le realm du déploiement PRINCIPAL, jamais dans celui de
`vault-standalone` (confirmé : aucun portail admin n'y existe,
seulement l'API, toujours accessible par appel direct avec des
groupes fournis à la main).

**Nouvelle variable de gabarit** `VAULT_ADMIN_PORTAL_PUBLIC_URL`
(`keycloak/render.py`) -- SANS chemin `/vault`, contrairement à
`VAULT_PUBLIC_URL` : ce portail tourne sur un port DIRECT dédié
(`VAULT_ADMIN_PORTAL_LAN_PORT`), jamais routé par tls-proxy.

**Porte de connexion Keycloak** ajoutée dans `App.jsx`, APRÈS tous
les hooks React existants (règles de hooks respectées -- jamais un
retour anticipé avant qu'ils aient tous été appelés), AVANT le garde
de déverrouillage par mot de passe existant. Les groupes Keycloak
VÉRIFIÉS sont désormais transmis à `POST /users/.../roles` (le seul
endpoint protégé par #291) -- le login `vault` (texte saisi,
toujours utilisé pour l'audit et le déverrouillage crypto) n'a
aucune notion de groupe, jamais utilisé pour cela.

**Vérifié réellement** : rendu complet du realm testé -- le nouveau
client se substitue correctement (`https://localhost:6120` par
défaut, sans chemin), aucun jeton `__...__` non substitué nulle
part dans le realm entier après ce changement. Structure JSX de
`App.jsx` revérifiée (accolades/parenthèses équilibrées, aucune
balise non refermée). Confirmé qu'aucun hook n'est appelé après le
nouveau garde de connexion.

## Branchement rights-api -- scope volontairement étroit (livraison #308)

Suite de l'item 38 du backlog ("brancher rights-api sur les ~40
autres API du projet") -- `vault-api` (le coffre-fort lui-même,
distinct de `vault-admin-api` déjà branché en #291) restait le
service le plus sensible parmi ceux cités à l'origine (coffre-fort,
clés SSH, LDAP) sans branchement.

**Ce module a une posture différente du reste du projet** (voir le
docstring en tête de `vault/api/app.py`) : le chiffrement de bout en
bout borne déjà la confidentialité même sans vérification d'identité
réseau. Plutôt qu'un branchement en bloc, chaque route a été examinée
individuellement :

- **`revoke_collection_access`** (DELETE) et **`reset_user`** (DELETE)
  -- GARDÉES. Aucune des deux n'implique la moindre clé de
  chiffrement : une simple suppression en base suffit à l'action.
  Sans garde, n'importe qui aurait pu couper l'accès de quelqu'un
  d'autre, ou effacer intégralement un compte (accès + archive de
  clé de récupération), sans rien avoir besoin de déchiffrer.
  Confirmé qu'aucune des deux n'a d'appelant actuel dans le portail
  (`vault/portal/src/App.jsx`) -- pas un risque exploité aujourd'hui
  via l'interface, mais un vrai trou pour un appel API direct.
- **`grant_collection_access`** -- DÉLIBÉRÉMENT PAS gardée. Cette
  route exige déjà de connaître la clé RÉELLE de la collection
  (`collectionKey` en mémoire côté client, voir
  `vaultOps.js:grantAccess`) pour produire un `wrapped_key` valide --
  un gate `rights-api` supplémentaire n'y fermerait aucune brèche
  réelle, seulement de la friction sur un usage légitime déjà borné
  par le chiffrement lui-même.
- **`create_user`, `create_collection`, `rotate-password`
  (changement de mot de passe)** -- DÉLIBÉRÉMENT PAS gardées,
  confirmé self-service : l'utilisateur agit sur SON PROPRE compte
  ou SA PROPRE collection, jamais au nom d'un tiers (vérifié via le
  contexte d'appel dans `App.jsx` -- `changePassword(login, ...)`
  appelé avec le `login` de l'utilisateur CONNECTÉ, jamais un login
  arbitraire).

OPT-IN comme tous les branchements précédents -- `VAULT_API_RIGHTS_API_URL`
vide par défaut, comportement inchangé tant qu'elle n'est pas
configurée.

**Vérifié réellement** : comportement opt-in par défaut confirmé,
FAIL CLOSED si `rights-api` injoignable (y compris pour `admin_hub`),
403 confirmé sur les deux routes gardées avec un groupe non autorisé,
et confirmation explicite que `grant_collection_access` reste à 404
(jamais 403) -- preuve que la non-garde délibérée est respectée.

## Reste à faire

- Le déverrouillage par mot de passe existant et Keycloak restent
  deux portes SÉPARÉES à franchir l'une après l'autre -- jamais
  fusionnées. Si la personne souhaite un jour les unifier (le login
  Keycloak devenant aussi la source du login vault), ce serait un
  chantier séparé, pas fait ici.
- `vault-admin-portal` n'a pas été testé dans un vrai navigateur
  (aucun outil de build React/Vite disponible dans cet environnement,
  même limite que d'habitude) -- vérification visuelle réelle à
  faire par la personne après déploiement.
