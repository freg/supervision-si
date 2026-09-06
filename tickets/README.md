# Module tickets

Gestion de tickets indépendante (API + frontend propres, même principe
que `pixel-grid/`) — file d'attente technicien filtrable/triable,
rattachement de temps passé depuis un agenda Google (via règles regex
configurables), Gantt enrichi (plusieurs segments par ticket, pas
juste début/fin).

## Schéma

Tes 5 tables demandées (`users`, `tickets`, `types`, `levels`,
`statuts`) + 3 ajoutées pour le rattachement calendrier :

- `calendar_events` — événements ICS importés, stockage brut
- `calendar_filter_rules` — règles regex configurables (voir plus bas)
- `ticket_time_entries` — segments de temps par ticket (calendrier ou saisie manuelle)

Deux notes de nommage : `level.integer` → `level.rank` (mot réservé
dans plusieurs dialectes SQL), et `tickets.user` → `tickets.user_id`
(convention FK explicite).

`tickets.source_type`/`source_nom` existent déjà pour le lien futur
avec la supervision — un incident pixel-grid pourra y référencer sa
source d'origine lors d'une génération automatique de ticket (pas
encore construit, cf. Limites ci-dessous).

## Import calendrier — deux chemins, un seul parseur

L'adresse secrète iCal de Google et un export Thunderbird/Lightning
produisent tous les deux du `.ics` standard — un seul parseur
(`ics_parser.py`, sans dépendance externe, RFC 5545 de base) gère les
deux :

- `POST /calendar/import_url` `{"url": "https://calendar.google.com/calendar/ical/.../private-xxx/basic.ics"}`
- `POST /calendar/import` — upload direct d'un fichier `.ics`

Import **idempotent** (basé sur l'UID de l'événement). **L'import ne
fait plus que stocker les événements bruts** — aucun rattachement ni
création automatique. La décision revient toujours à un humain, via
l'écran de revue.

## Écran de revue et suggestion (pas d'automatisme silencieux)

Reflète la pratique réelle décrite : un mot-clé déclencheur ("SAV" par
défaut, insensible à la casse, configurable) signale qu'un événement
est potentiellement lié à un ticket ; le login du demandeur mentionné
dans le texte restreint la recherche à ses tickets ouverts ; un score
de mots partagés (accents normalisés — "accès"/"acces" matchent)
classe les candidats.

Deux mécanismes combinés, visibles côte à côte dans la revue :
- 🎯 **Haute confiance** : référence explicite trouvée via une règle
  regex configurée (ex: `#(?P<ticket_id>\d+)` sur "traitement ticket
  #123") — l'engine de règles existant (`filter_engine.py`), repensé
  pour ne plus qu'émettre des suggestions.
- 💡 **Suggérée** : correspondance floue (mot-clé + login + mots
  partagés), pas une certitude.

L'écran liste les événements non affectés, chacun avec ses suggestions
cliquables (affectation rapide 1-vers-1) ou sélectionnables en masse
pour une affectation n événements → m tickets.

## Affectation n × m, deux modes au choix

- **Durée entière chacun** : chaque événement compte pour sa durée
  complète sur *chaque* ticket sélectionné (comptage multiple assumé —
  ex: une réunion couvrant plusieurs sujets).
- **Répartie également** : la durée de chaque événement est divisée
  par le nombre de tickets sélectionnés (`weight = 1/m` par segment).

Le choix se fait à chaque affectation, pas un réglage global.
`ticket_time_entries.weight` porte cette pondération ; `total_seconds`
d'un ticket = `Σ (end_ts - start_ts) × weight`.

## Vue tickets parallèles

Timeline horizontale à axe temporel **partagé** entre tous les tickets
ouverts (une ligne par ticket), avec un marqueur vertical + étiquette
pour chaque entrée calendrier distincte — pour repérer visuellement ce
qui s'est passé en parallèle sur plusieurs tickets.

## Gestion de la base (🗄️)

Onglet dédié : édition en ligne des tables de référence (`users`,
`types`, `levels`, `statuts` — créer/modifier/supprimer), édition
complète des tickets (y compris fermeture/réouverture explicite via
`ts_closed`), et export/import JSON de toute la base.

**Export** (`GET /export`) : un objet `{table: [lignes...]}` pour les
9 tables. **Import** (`POST /import?mode=...`), deux modes :
- `merge` (défaut) : upsert par id — ajoute les nouveaux
  enregistrements, met à jour ceux dont l'id existe déjà, ne touche
  pas au reste.
- `replace` : vide **toute** la base avant de réimporter — pas
  seulement les tables présentes dans le fichier (sinon les tickets
  existants, absents d'un import partiel, se retrouveraient à
  référencer des utilisateurs/types/niveaux sur le point d'être
  supprimés). Destructeur, à utiliser sciemment.

## Création à la volée des références manquantes

Chaque sélecteur demandeur/type/niveau/statut (formulaire "Nouveau
ticket" et écran de revue) porte un bouton **+** — bascule vers un
mini-formulaire de création inline, sélectionne automatiquement la
nouvelle entrée une fois créée. Composant réutilisable
(`CreatableSelect.jsx`), pas besoin de passer par l'onglet Gestion
base pour un ajout ponctuel.

**Écran de revue** : quand aucun ticket ne correspond (liste vide ou
simplement aucune correspondance satisfaisante), un bouton "➕ Aucun
ticket ne correspond — en créer un" ouvre le même mini-formulaire.
Le ticket créé est automatiquement ajouté à la sélection côté
tickets — reste à cocher le(s) événement(s) et cliquer "Affecter"
comme d'habitude (pas de court-circuit du flux normal).

## Assistance heuristique (pas un vrai NLP)

⚠️ **Précision importante** : pas de modèle de langue, pas d'analyse
syntaxique, pas de reconnaissance d'entités nommées — aucun accès à
un tel outil pendant le développement (pas de réseau pour en installer
un). Ce qui suit est un classement par **position + fréquence +
exclusion de mots-outils** (`nlp_helper.py`) : utile pour accélérer,
mais ça se trompe parfois — présenté comme des candidats à valider,
jamais comme des faits.

- **Pré-remplissage à la création** : en sélectionnant un ou plusieurs
  événements dans l'écran de revue, le champ "demandeur" du
  mini-formulaire de création de ticket se pré-remplit avec le
  candidat le plus plausible (en général le token juste après le
  mot-clé déclencheur).
- **🔍 Analyser les imports** : bouton dans l'écran de revue — analyse
  tous les événements calendrier importés, classe les tokens
  candidats par fréquence, marque ceux qui correspondent déjà à un
  utilisateur connu (✓), propose un bouton **+** de création rapide
  pour les autres.

**Bug d'ambiguïté trouvé et corrigé** : l'API ne distinguait pas "le
mot-clé/regex n'a rien déclenché" de "déclenché, mais aucun ticket
ouvert à proposer" — les deux donnaient `suggestions: []`, strictement
identique côté interface. Si tu n'as **aucun ticket ouvert** au
moment de l'import, absolument tout événement matché par ton mot-clé
ressortait comme "rien" à l'écran, même en cas de déclenchement
parfaitement correct. Corrigé : un champ `triggered` explicite
distingue maintenant les deux cas, avec un message dédié côté
interface ("⚡ mot-clé détecté, mais aucun ticket ouvert à proposer")
plutôt qu'un silence ambigu.

## Liste d'exclusion (véto)

Distincte des règles de rattachement : un événement qui matche l'un
de ces motifs regex n'est **jamais** considéré comme un ticket
potentiel, même s'il matche par ailleurs le mot-clé déclencheur — ex:
une réunion récurrente "Réunion SAV mensuelle" qui contient "SAV"
sans être elle-même un ticket. Configurable dans l'onglet ⚙️ Règles
calendrier (nouvelle section en bas). L'écran de revue affiche
"🚫 exclu (règle : ...)" distinctement de "⚡ déclenché mais rien à
proposer", pour qu'on sache toujours ce qui s'est passé.

L'analyse en lot (mining) respecte aussi l'exclusion — un événement
vétoté ne contribue plus aux candidats proposés.

## Suggestions visibles à la création (pas cachées derrière "+")

En sélectionnant un événement dans l'écran de revue, deux suggestions
apparaissent désormais **directement visibles**, pas juste accessibles
via le bouton "+" :
- **💡 <prénom> ?** à côté du champ demandeur — clique pour
  sélectionner un utilisateur existant du même nom, ou pré-remplir sa
  création.
- **💡 utiliser : "..."** sous le champ Sujet — reprend le titre
  complet de l'événement sélectionné en un clic.

Ajout de termes techniques à la liste d'exclusion des candidats
(`sms`, `sim`, `nms`, `plateforme`, `google`, `meet`, `glpi`, `ged`,
`wifi`, `https`, `dev`, `rapport`, `urgence`, `supervision`...) —
observés dans un vrai extrait de données, filtrés pour laisser
ressortir les vrais prénoms plutôt que le vocabulaire technique
récurrent.

## Connecteur OAuth2 Google Calendar (alternative à l'adresse secrète iCal)

⚠️ **Non testé contre un vrai compte Google** — aucun réseau ni compte
disponible pendant le développement. Les endpoints Google utilisés
(autorisation, échange de jeton, API Calendar) sont stables et bien
documentés, mais un test réel reste à faire avant usage en production.

**Ce que tu dois faire toi-même** (rien de tout ça n'est faisable
depuis l'environnement de développement) :
1. Créer un projet dans [Google Cloud Console](https://console.cloud.google.com)
2. Activer l'**API Google Calendar** pour ce projet
3. Créer des identifiants **OAuth 2.0** (type "Application Web")
4. Ajouter l'URI de redirection **exactement** :
   `http://localhost:6105/oauth/google/callback` (ou l'IP/port réels
   si tu accèdes à distance — doit correspondre EXACTEMENT à
   `GOOGLE_OAUTH_REDIRECT_URI` dans `.env`)
5. Copier l'identifiant client et le secret dans `.env` :
   ```
   GOOGLE_OAUTH_CLIENT_ID=...
   GOOGLE_OAUTH_CLIENT_SECRET=...
   ```
6. Redémarrer `tickets-api`, puis clique **"🔗 Connecter mon agenda
   Google"** dans le panneau d'import — consentement Google, puis
   retour automatique.

Une fois connecté, le jeton de rafraîchissement est stocké en base
(table `oauth_credentials`) — plus besoin de reconsentement à chaque
import, contrairement à l'adresse secrète iCal qui reste valide mais
n'offre pas ce mécanisme de rafraîchissement automatique de session.

**Différences avec l'import ICS** : passe par l'API JSON native de
Google (pas de fichier `.ics` à parser), développe automatiquement les
événements récurrents en occurrences individuelles
(`singleEvents=true`), gère la pagination (>2500 événements). Les uid
sont préfixés `google_api_` pour ne jamais entrer en collision avec un
import ICS du même agenda.

**Connecteur OAuth2 Google Calendar** : toute la logique testable sans
réseau vérifiée — construction de l'URL d'autorisation (paramètres
corrects), conversion des événements API (horodatés et jour entier),
gestion des cas limites (client non configuré, callback sans code,
état CSRF invalide, refresh_token absent). La redirection réelle vers
Google (302, bonne URL) vérifiée via le client de test Flask. **Les
appels réseau réels (échange de code, rafraîchissement de jeton, appel
à l'API Calendar) n'ont pas pu être testés** — aucun compte Google
disponible.

## Tri de l'écran de revue

Quatre modes, sélectionnables en haut de la liste des événements :

- **Pertinence** (défaut) : événements avec suggestion en tête (haute
  confiance puis suggérée), plus récents d'abord dans chaque groupe —
  remplace l'ancien tri "juste par date" qui noyait les vrais
  candidats parmi des événements sans rapport.
- **Oubliés** : le plus ancien en premier — pour rattraper ce qui
  traîne depuis longtemps sans être traité.
- **Demandeur** : groupé par demandeur détecté (login connu si le
  moteur de suggestion en a trouvé un, sinon le meilleur candidat
  heuristique), le plus récent d'abord dans chaque groupe.
- **Urgence** : les événements matchant un mot-clé d'urgence (🔥) en
  tête. Liste éditable dans ⚙️ Règles calendrier (nouvelle section) —
  seedée avec Urgent, Critique, Panne, Cassé/HS, Bloquant, mais
  librement modifiable/complétable. Ne décide ni n'exclut rien,
  purement indicatif pour ce tri.

Chaque événement affiche maintenant, quand disponible, 👤 le demandeur
détecté et 🔥 s'il matche un mot-clé d'urgence — visible quel que soit
le mode de tri actif.

**Tri de la revue** : les 4 modes testés sur un jeu de données varié
(événement récent sans rapport, événement ancien urgent, événement
milieu bien matché, événement d'un autre demandeur) — chaque tri
produit exactement l'ordre attendu, vérifié ligne par ligne.

**Fausse alerte auto-corrigée pendant le développement** : en
vérifiant le motif regex du mot-clé "Cassé/HS" (`\bhs\b`), une
extraction de sous-chaîne imprécise dans mon propre test m'a fait
croire à un double-échappement de backslash (bug qui n'existait pas).
Revérifié avec un test direct sur la vraie valeur en base après
exécution réelle du schéma (pas une extraction approximative) : un
seul backslash de chaque côté, comportement correct confirmé
caractère par caractère.

## Vision alternative — 🗂️ Tableau Kanban

Proposition libre, complémentaire à la liste triable : une colonne par
statut (+ "Non classé" pour les tickets sans statut), cartes affichant
niveau/type/demandeur/badges de reprise, déplacement d'un ticket vers
un autre statut via un sélecteur en bas de carte (pas de drag & drop —
plus simple et fiable). Montre **tous** les tickets, ouverts et
fermés, contrairement à la liste principale (ouverts par défaut).

## Timeline/Gantt — vision par dimension, pas seulement par ticket

La vue 📊 Tickets parallèles s'enrichit d'un sélecteur de vision :
- **Par ticket** (comportement d'origine) : une ligne par ticket ouvert.
- **Par demandeur** : une ligne par utilisateur, combinant les segments
  de TOUS ses tickets — pour voir la charge de travail d'une personne
  dans son ensemble, fragmentée ou pas.
- **Par type** / **Par niveau** : même principe, agrégé par type de
  ticket ou par niveau de priorité.

Nouveau paramètre `group_by` sur `GET /tickets/parallel`
(`ticket`|`user`|`type`|`level`) — testé sur les 4 modes avec un
scénario à 3 tickets/2 demandeurs/2 types/2 niveaux, vérifié que les
segments se combinent correctement par groupe.

## Colonne "Reprises" enrichie (liste principale)

Trois signaux, affichés en badges compacts :
- **⏱️ Plages horaires** : nombre de segments de temps distincts
  (`ticket_time_entries`) — un ticket travaillé en plusieurs fois.
- **🔁 Réouvertures** : nombre de fois où `ts_closed` est passé de
  renseigné à `NULL`. Nécessite une vraie table d'historique
  (`ticket_status_log`) — le schéma précédent n'avait qu'un
  instantané, impossible de compter les transitions passées. Journalisé
  automatiquement à la création (`opened`) et à chaque changement
  détecté de `ts_closed` (`closed`/`reopened`) via `PUT /tickets/<id>`.
- **♻️ Récidive** : nombre d'AUTRES tickets du même demandeur au sujet
  significativement proche (même heuristique de mots partagés que les
  suggestions calendrier) — signale un problème qui revient sous forme
  de nouveaux tickets plutôt que de réouvertures du même.

**Limite assumée sur la récidive** : comparaison en O(n²) sur tous les
tickets à chaque appel de `/queue` — correct pour un volume modeste
(usage interne), à revoir si le nombre de tickets devient très
important.

**Réouvertures et récidive** testées avec un scénario complet :
ticket avec 3 plages horaires + 1 fermeture + 1 réouverture (journal
vérifié transition par transition, y compris qu'une édition qui ne
touche pas `ts_closed` n'ajoute rien au journal) ; ticket B au sujet
proche du ticket A (même demandeur) correctement compté en récidive
réciproque, ticket C au sujet différent correctement exclu.

**Groupement de la vue parallèle** testé sur les 4 modes avec un jeu
de données à 3 tickets croisant 2 demandeurs/2 types/2 niveaux —
chaque regroupement vérifié exact (ex: demandeur avec 2 tickets ->
ses segments bien combinés en une seule ligne).

## Écran de revue — doublons et équilibrage

**Regroupement des doublons** : les événements au titre strictement
identique (insensible à la casse/espaces — ex: "SAV Didier/SMS" répété
à chaque reprise) sont fusionnés en une seule carte, avec compteur
(`×N`), plage de dates couverte, durée totale, et détail dépliable des
occurrences individuelles. Case à cocher unique qui sélectionne tout
le groupe d'un coup ; les suggestions et l'affectation rapide agissent
sur l'ensemble du groupe (même titre = mêmes suggestions garanties,
calculées dans le même appel serveur). Testé isolément en JS sur les
cas limites (casse/espaces différents, résumés vides qui ne doivent
**jamais** se regrouper entre eux, ordre du tri serveur préservé).

**Équilibrage tickets reconnus / tickets à créer** : le formulaire de
création n'est plus caché derrière un bouton — toujours visible,
~62% de l'espace par défaut, avec la liste des tickets reconnus en
dessous. Limite glissable entre les deux (glisser la barre grise) pour
rééquilibrer selon le besoin du moment.

## Gestion de la base — colonne JSON

Nouvelle disposition à 2 colonnes : les tables éditables à gauche
(inchangées), une colonne JSON à droite divisée en deux :

- **Vue générale** : hiérarchie construite à la volée depuis les
  tickets déjà chargés (aucun appel serveur supplémentaire) —
  Demandeur→Tickets, Niveau→Demandeur→Tickets, Type→Demandeur→Tickets,
  Statut→Demandeur→Tickets. Testé isolément en JS, y compris le cas
  "sans demandeur" regroupé sous `(non défini)`.
- **Contexte** : clique n'importe quelle ligne à gauche (utilisateur,
  type, niveau, statut, ticket) pour voir son JSON ici. Pour les
  tables de référence : la fiche + ses tickets associés. Pour un
  ticket : le détail complet via `GET /tickets/<id>` (inclut les
  segments de temps).

## Bug corrigé — écran noir sur "Vue parallèle" (par demandeur/type/niveau)

**Signalé** : "gestion des tickets → vue parallèle → par demandeur
écran noir, idem type et niveau".

**Cause confirmée** : `Math.min(...tableau)` / `Math.max(...tableau)`
(opérateur de décomposition) plantent silencieusement
(`RangeError: Maximum call stack size exceeded`) sur de grands
tableaux — un piège JavaScript connu, la limite dépend du moteur mais
se situe typiquement autour de 100 000+ éléments. Sans limite de
gestion d'erreur (error boundary) React, ce genre de plantage casse
tout le rendu — d'où l'écran noir sans message visible. Confirmé en
test isolé (reproduction du crash avec 200 000 éléments).

**Trouvé et corrigé dans 6 endroits** (le même motif s'était propagé
à chaque nouvelle vue Gantt/timeline construite sur ce modèle) :
`TicketsParallelView.jsx` (le cas signalé), le regroupement de
doublons tout juste ajouté dans `CalendarReviewView.jsx` (justement à
risque avec beaucoup d'occurrences comme "SAV Didier/SMS"),
`TicketDetailView.jsx` (Gantt individuel d'un ticket), et
`TimelineView.jsx` (2 occurrences, timeline équipement pixel-grid).
Remplacé partout par `.reduce()`, qui n'a pas cette limite — résultat
identique vérifié sur un cas normal, absence de crash vérifiée sur un
tableau à 200 000 éléments.

## Retours de test — 6 correctifs

**1. Sélection par surbrillance de ligne** (écran de revue, colonne
Événements) : la case à cocher est remplacée par un clic sur la ligne
entière. Clic simple = mono-tâche (remplace la sélection, comme dans
la pratique réelle décrite) ; `Ctrl`/`Cmd`+clic = ajoute/retire ce
groupe sans remplacer (mode lot conservé pour qui en a besoin).
Bordure + fond distincts sur la ligne sélectionnée, ✅ explicite.

**2. Avertissement demandeur manquant** : badge ⚠️ dans la liste
principale des tickets, avertissement doux (non bloquant) dans les
deux formulaires de création si le sujet est rempli sans demandeur
sélectionné.

**3. Bug corrigé — demandeur créé (+) non appliqué au ticket** : la
liste déroulante recevait la valeur sélectionnée *avant* que l'option
correspondante n'existe dans ses choix (fenêtre de latence pendant le
rechargement complet awaité). Corrigé dans les deux formulaires
(`CalendarReviewView` et `NewTicketForm`/`TicketsApp`) par mise à jour
locale immédiate de la liste (users/types/levels/statuts) avant tout
rechargement réseau. `NewTicketForm` ne possédant pas cet état
localement (reçu en props), son interface a changé :
`onRefreshReferences` → `onReferenceCreated(table, item)`, le parent
appliquant la mise à jour optimiste. Séquence vérifiée en isolation
(JS) : l'option existe bien avant que la sélection ne s'applique.

**4. Vue parallèle vide — diagnostiqué, pas un bug de la vue** :
export JSON réel fourni analysé — `ticket_time_entries: 0` malgré 4
tickets créés et 507 événements importés. La vue affichait fidèlement
l'absence de données. Deux tickets au même sujet ("SAVPaulOwnCloud")
créés à ~2 minutes d'écart, tous deux refermés ensuite, corroborent
l'hypothèse : le bug #3 a probablement interrompu le flux d'affectation
avant le clic final sur "Affecter". `/calendar/assign` revérifié
fonctionnel par un test direct (2 segments correctement créés).

**5. Enregistrement en lot avec confirmation** (gestion de la base) :
bouton "💾 Tout enregistrer (N)" par table, avec confirmation,
enregistrant toutes les lignes modifiées d'un coup. Séparation
mutation pure (`onUpdateRaw`) / déclenchement du rafraîchissement
(`onSaved`) — un seul rechargement, quel que soit le nombre de lignes
sauvegardées (testé : 3 lignes, 1 seul rechargement déclenché).
L'enregistrement individuel par ligne reste disponible et n'affecte
pas les autres lignes en cours d'édition.

**6. Position de page fixe après validation** : la cause réelle était
que la zone de contenu (tables + colonne JSON) était entièrement
démontée puis recréée à chaque rechargement — perdant sa position de
défilement par construction. Corrigé : le "Chargement…" plein écran
ne s'affiche plus qu'au tout premier chargement ; les rechargements
suivants ne redémontent plus le contenu. Restauration explicite du
défilement ajoutée en filet de sécurité.

## Retours de test — 3 retouches

**1. Suggestion demandeur — un seul clic désormais** : cliquer 💡 sur
une suggestion sans correspondance existante crée directement
l'utilisateur (au lieu d'ouvrir un formulaire pré-rempli qu'il fallait
ensuite re-valider séparément — une opération de trop). En cas
d'échec, repli sur le formulaire manuel pour réessayer.

**2. Balayage automatique des doublons à l'affectation** : côté
serveur, `/calendar/assign` étend désormais automatiquement la
sélection à tout autre événement **non encore affecté** partageant
exactement le même titre (insensible à la casse/espaces) que l'un des
événements explicitement choisis — traiter un événement traite aussi
ses doublons à la volée, sans repasser par une sélection manuelle.
Réponse enrichie de `events_assigned` et `auto_added_duplicates`,
affichés dans l'interface ("🧹 + N événement(s) au même titre affecté(s)
automatiquement"). Filet de sécurité serveur — fonctionne même si le
regroupement visuel du frontend n'a pas capturé tous les doublons
(import échelonné, etc.). Testé avec espaces/casse différents et un
sujet non-doublon correctement préservé (pas de sur-affectation).

**3. Entrée = validation** (gestion de la base) : dans les tables
éditables, appuyer sur Entrée dans le champ "nouveau" crée la ligne et
garde le focus sur le même champ — pratique pour enchaîner la saisie
de plusieurs libellés. Entrée dans un champ d'édition existant
enregistre cette ligne. Appliqué aussi au formulaire de création
inline de `CreatableSelect` (Entrée = créer, Échap = annuler), pour
une cohérence sur tout le module.

## 📚 Toutes les tables (gestion de la base)

Nouveau bouton repliable, réutilise l'export existant (déjà complet et
testé) — chaque table (13 au total, y compris `calendar_events`,
`ticket_time_entries`, `exclusion_rules`, `priority_keywords`,
`ticket_status_log`, `oauth_credentials`...) affichée en tableau
lecture seule, colonnes déduites automatiquement, repliable
individuellement pour ne pas surcharger l'écran.

**Bug trouvé et corrigé au passage** : 4 tables ajoutées lors de
sessions récentes (`exclusion_rules`, `priority_keywords`,
`ticket_status_log`, `oauth_credentials`) n'avaient jamais été
ajoutées à la liste `TABLE_ORDER` de l'export/import — elles étaient
donc invisibles à l'export malgré leur existence réelle en base.
Corrigé, ordre vérifié pour respecter les dépendances de clé étrangère
(`ticket_status_log` après `tickets`), testé en aller-retour complet
(export des 13 tables → réimport sans erreur).

## 🔗 Correspondances de titres (écran de revue)

Nouvelle analyse, indépendante du mot-clé déclencheur — cherche, pour
chaque événement non affecté, le ticket ouvert avec lequel il partage
le plus de mots significatifs (**≥ 3 caractères**, contre > 3 pour
l'analyse de candidats-noms existante — les acronymes courts comme
SMS/VPN/GED sont justement les mots les plus parlants ici, alors qu'ils
sont bruit pour l'extraction de prénoms). Le mot-clé déclencheur est
exclu du calcul pour éviter les faux-positifs (deux titres qui
partagent juste "SAV" ne doivent pas matcher pour autant).

Chaque correspondance propose un bouton "➕ Ajouter ce segment" —
affecte directement l'événement au ticket suggéré (mode durée
entière), sans repasser par la sélection manuelle.

Testé précisément sur l'exemple donné : événement "SMS" seul contre
ticket "SAV Didier/SMS" → correspondance trouvée sur le mot "sms" ;
un événement "SAV fred..." contenant le mot-clé mais aucun mot
partagé avec un ticket d'un autre demandeur → correctement ignoré (pas
de faux-positif sur "SAV" seul) ; plusieurs tickets candidats → le
meilleur score l'emporte.

## 🔎 Synthèse par terme

Cliquer un jeton dans "🔍 Analyser les imports" (ou taper directement
un terme dans le nouveau champ de recherche) ouvre une synthèse :
nombre de tickets mentionnant ce terme (sujet ou description), répartition
ouverts/fermés, temps total passé, demandeurs impliqués, plus les
événements calendrier non affectés qui en parlent aussi (aperçu de ce
qui reste à traiter). Utile pour les noms propres de projets/clients
(comme "Alpha" repéré par l'analyse en lot) autant que pour les
prénoms. Recherche insensible à la casse et aux accents, testée avec
un scénario à 3 tickets (2 mentionnant le terme, 1 sans rapport
correctement exclu) et un événement calendrier non affecté associé.

## Vue "Toutes les tables" — éditable pour les micro-corrections

Chaque cellule éditable (liste blanche stricte côté serveur — table +
colonnes, protégée contre l'injection via nom de colonne arbitraire)
se modifie directement en place, sauvegarde automatique en quittant le
champ ou sur Entrée — pas de bouton "enregistrer" séparé, pensé pour
de petites corrections ponctuelles. Couvre désormais aussi les tables
sans formulaire dédié (`calendar_events`, `calendar_filter_rules`,
`exclusion_rules`, `priority_keywords`, `ticket_time_entries`,
`matching_config`).

**Volontairement en lecture seule** : `ticket_status_log` (journal
d'audit — l'éditer viderait son sens) et `oauth_credentials` (jetons
techniques — une édition à la main casserait la connexion Google).

**Précaution prise en testant** : les colonnes booléennes (`active`
sur `exclusion_rules`/`priority_keywords`/`calendar_filter_rules`) ont
été délibérément exclues de l'édition libre — un champ texte y
enregistrerait la chaîne `"true"` au lieu de l'entier `1`, cassant
silencieusement les filtres `WHERE active = 1` utilisés ailleurs dans
le code. Ces colonnes restent gérables via les écrans dédiés existants
(suppression = désactivation effective).

## Tickets fermés — visibilité et reconnaissance

**Voir les tickets fermés** : le filtre "État" (liste principale) est
désormais séparé du filtre "Statut" (libellé libre) — trois options
indépendantes : Ouverts seulement (défaut) / Fermés seulement / Tous.
Badge 🔒 sur chaque ticket fermé dans le tableau. Nouveau paramètre
`state=open|closed|all` sur `/queue`, l'ancien `all=true` reste
fonctionnel (alias de `state=all`).

**Reconnaissance à la revue** : le moteur de suggestion et l'analyse
de correspondance de titres cherchent désormais aussi bien les
tickets ouverts que fermés — un événement calendrier correspondant à
un ticket déjà clos (ex: "le ticket clos de Paul sur OwnCloud")
ressort comme suggestion, marquée 🔒, plutôt que d'être ignoré. À
score égal, un ticket ouvert reste priorisé sur un fermé. Panneau
"Tickets reconnus" de l'écran de revue : bascule "inclure les fermés"
pour aussi les voir dans la sélection manuelle (les suggestions, elles,
les proposent déjà sans cette bascule).

**Réouverture — explicite uniquement, jamais automatique** : affecter
une nouvelle plage à un ticket fermé ne le rouvre PAS par défaut (la
plage est quand même ajoutée, le ticket reste fermé — comportement
volontairement conservateur). Case à cocher "🔓 rouvrir aussi..."
visible seulement quand la sélection contient un ticket fermé
(détectée via la liste manuelle ET les suggestions, pour ne rien
manquer même si "inclure les fermés" n'est pas coché). La transition
est journalisée comme toute réouverture (alimente le compteur 🔁
existant).

**Vérification approfondie du segment créé** (suite à une question
précise sur le sujet) : testé que le segment ajouté reprend toujours
exactement les horaires réels de l'événement ical traité — sur
affectation directe, avec réouverture, après un aller-retour complet
export/import de la base, et via le chemin "Correspondances de
titres" pour un événement sans le mot-clé déclencheur. Aucun écart
trouvé dans les 4 scénarios.

## Ce qui a été vérifié depuis cet environnement (Claude)

**Bug trouvé pendant l'implémentation de la liste d'exclusion** : un
`str_replace` imprécis a remplacé uniquement la ligne de signature de
`event_has_trigger` par une nouvelle fonction, laissant le corps de
l'ancienne fonction orphelin (sans `def`), rattaché par erreur à la
fin de la nouvelle. `ast.parse` ne l'a pas détecté (pas une erreur de
syntaxe — juste du code mort après un `return`), mais l'import
plantait au premier appel (`NameError: event_has_trigger n'est pas
défini`). Corrigé en reconstruisant proprement les deux fonctions
séparément, revérifié avant de livrer.

**Cycle complet du véto testé** : événement SAV réel toujours
déclenché après ajout d'une règle d'exclusion ciblant une réunion
récurrente distincte ; la réunion elle-même correctement vétée avec
son motif exposé ; regex invalide refusée proprement (400, pas de
crash) ; suppression fonctionnelle ; mining vérifié pour exclure les
tokens d'un événement vétoté.

**Assistance heuristique** testée sur un corpus varié construit à la
main : extraction correcte du token suivant le déclencheur
(`"SAV fred - panne"` → `fred` en tête), meilleur candidat sur une
sélection multi-événements, analyse en lot distinguant correctement
un utilisateur déjà connu (`fred`, fréquence 2, marqué connu) de
nouveaux candidats (`marie`, `julien`). Testé aussi via l'API réelle
(client de test Flask + vraies lignes en base) : `/calendar/mine_candidates`
et `/calendar/suggest_name` tous deux vérifiés, y compris cas limite
(id d'événement inexistant → pas d'erreur, candidat `null`).

**Bug signalé et corrigé** : le mot-clé déclencheur était comparé en
sous-chaîne littérale, pas en expression régulière — `SAV.*` cherchait
donc les caractères `S-A-V-.-*` tels quels, absents de
`"SAVDevFuturopolis"`. Incohérent avec le reste de l'app (les règles
de filtrage utilisent déjà de vraies regex). Corrigé : le mot-clé est
désormais traité comme une regex insensible à la casse (`SAV` continue
de fonctionner tel quel comme avant), avec repli sûr sur une recherche
de sous-chaîne si le motif est invalide. Revérifié sur le cas signalé
+ non-régression sur les 4 scénarios déjà testés + robustesse à un
motif cassé.

**Limite annexe repérée en testant** (pas corrigée, juste documentée) :
le classement par mots partagés découpe sur les frontières non-
alphabétiques — un titre collé sans espace (`"SAVDevFuturopolis"`) ne
partage aucun mot avec un ticket au même sujet mais espacé
(`"SAV DevFuturopolis"`). Le déclenchement fonctionne quand même, seul
le classement des candidats en pâtit. Pas corrigé sans le demander
(un découpage plus agressif type CamelCase risquerait de créer des
faux positifs ailleurs).

**Deux bugs de déploiement trouvés en conditions réelles** (pas
détectables par mes propres tests, qui n'utilisent pas Docker) :
- **`Dockerfile` incomplet** : `suggestion_engine.py` créé après coup
  mais jamais ajouté à la liste des fichiers copiés dans l'image —
  `ModuleNotFoundError` au démarrage du conteneur. Corrigé.
- **Aucune auto-initialisation SQLite** : contrairement à PostgreSQL
  (schéma appliqué automatiquement par l'image officielle au premier
  démarrage), rien ne créait les tables pour le backend SQLite —
  pourtant le défaut du module (`TICKETS_BACKEND=sqlite`). Corrigé :
  le schéma est maintenant intégré dans `app.py` et appliqué
  automatiquement au démarrage de l'API (idempotent, `CREATE TABLE IF
  NOT EXISTS` — aucun risque sur une base déjà peuplée). Revérifié sur
  un fichier `.db` totalement absent (scénario exact du premier
  démarrage) : création d'utilisateur immédiate, sans étape manuelle.

**Deux vrais bugs trouvés en testant l'onglet de gestion :**
- **SQLite n'applique pas les clés étrangères par défaut**
  (contrairement à PostgreSQL) — `DELETE /levels/1` réussissait
  silencieusement même référencé par un ticket, laissant une
  référence orpheline. Corrigé (`PRAGMA foreign_keys = ON` sur chaque
  connexion) ; revérifié : suppression désormais bloquée (409) quand
  une ligne est encore référencée, autorisée sinon.
- **Mode `replace` de l'import** ne vidait que les tables présentes
  dans le JSON fourni — un import partiel (ex: seulement
  users/types/levels) plantait car les tickets existants (non
  mentionnés, donc non supprimés) référençaient encore les lignes en
  cours de suppression. Corrigé : `replace` vide toujours les 9
  tables, quel que soit le contenu du fichier importé.

Cycle complet revérifié après corrections : édition de référence,
édition de ticket (fermeture explicite), export, import merge (ajout
+ modification sans perte), import replace (base entièrement
rechargée depuis un dump minimal).

Pipeline testé bout en bout avec un vrai fichier `.ics` construit à la
main (line folding RFC 5545, 4 événements). Après la refonte de la
liaison agenda/ticket :

- **Moteur de suggestion** (`suggestion_engine.py`) : 4 cas testés
  isolément — déclenchement par mot-clé (insensible à la casse),
  non-déclenchement en son absence, restriction aux tickets du
  demandeur détecté, matching par mots seuls sans demandeur. **Un
  vrai bug trouvé et corrigé en testant** : "accès" (ticket) et
  "acces" (événement, sans accent) ne matchaient pas — normalisation
  des accents ajoutée (`unicodedata.normalize`).
- **Écran de revue** : suggestions haute confiance (référence
  explicite via règle regex) correctement priorisées au-dessus des
  suggestions floues, sur un calendrier de test à 4 scénarios réels
  (SAV+login+mot partagé, SAV seul, SAV+login sans mot partagé,
  aucun SAV).
- **Affectation n×m** : les deux modes vérifiés — "durée entière"
  (weight=1.0, comptage multiple confirmé sur le total) et "répartie"
  (weight=1/m, total pondéré correct : 2700s/2 tickets = 1350s
  chacun).
- **Non-régression** : test de fumée complet sur base fraîche après
  toutes les modifications (seed, file d'attente, revue vide, vue
  parallèle) — rien de cassé.

**Non vérifié** : aucune vraie URL secrète Google ni vraie synchro
Thunderbird/Lightning disponibles depuis cet environnement — seul le
format `.ics` généré à la main a pu être testé. À valider avec un
vrai agenda avant usage réel.

## 🎫 Portail tickets multi-profils (`tickets/portal/`)

Second frontend, spécialisé gestion des tickets, **sur la même API et
la même base** que le module interne (service `tickets-portal`, port
`TICKETS_PORTAL_PORT=6175`) — compatibilité totale : tout ce qui se
fait au portail est immédiatement visible dans l'outil interne, et
réciproquement. Quatre profils, routés par `users.role`
(`admin` | `demandeur` | `technicien` | `politique`, défaut
`demandeur`) :

- **Demandeur (client)** : crée sa demande (→ ticket,
  `source_type='portal'`), suit son évolution (frise du journal
  ouvert/fermé/rouvert), ajoute des **sous-demandes** et dialogue
  façon forum/chat.
- **Technicien** : file d'attente filtrable (état/type/statut/
  demandeur — réutilise `/queue`), édition statut/niveau/type,
  fermeture/réouverture explicite avec confirmation, saisie manuelle
  de segments de temps, fil de discussion avec les demandeurs.
- **Politique** : synthèse chiffrée (`/stats/summary`), **Gantt
  filtrable** par ticket/demandeur/type/niveau (réutilise
  `/tickets/parallel`), gestion des priorités (niveau) et
  clôture/réouverture des demandes.
- **Admin** : utilisateurs & rôles, base (export/import JSON complet,
  volumes par table), **incidents sur le projet lui-même**
  (`source_type='projet'`), **éditeur de statistiques** (dimension ×
  mesure × périmètre via `/stats/aggregate`, whitelisté), état des
  connecteurs (OAuth Google, mot-clé déclencheur, comptages de
  règles).

**Identification par login, sans mot de passe** — comme le reste du
projet (aucune authentification) : c'est une séparation d'usages, PAS
une barrière de sécurité. Un login inconnu ne peut créer qu'un compte
**demandeur** ; les autres rôles s'attribuent via la vue admin (ou
l'édition de la table `users` du module interne). Au premier
démarrage, un utilisateur `admin` (rôle admin) est amorcé
automatiquement s'il n'existe aucun admin — sans jamais toucher un
login `admin` existant d'un autre rôle.

**Extensions backend** (toutes additives, migrations douces
automatiques au démarrage) : colonne `users.role`, colonne
`tickets.parent_ticket_id` (sous-demande = ticket enfant, ticket
normal partout ailleurs), table `ticket_messages` (un fil
chronologique par ticket, auteur joint avec son rôle,
`last_change` avancé à chaque message), endpoints
`/portal/profile`, `/tickets/<id>/messages` (GET/POST),
`/tickets/<id>/children`, `/stats/aggregate`, `/stats/summary`,
filtre `source_type` sur `/queue`, et champs additifs sur
`GET /tickets/<id>` (`status_log`, `children`, `message_count`).
Export/import : 14 tables désormais (`ticket_messages` incluse).

**Vérifié depuis cet environnement** : 59 tests backend (amorçage,
rôles et validations, sous-demandes, fil de messages et ses cas
limites, statistiques exactes — 5400 s pondérées contrôlées à la
main —, filtre source_type, export/import aller-retour complet en
mode replace, clés étrangères actives sur les messages, fumée sur 15
endpoints existants, **migration d'une base à l'ancien format** :
colonnes ajoutées, admin amorcé, anciens tickets intacts et
messages postables dessus) + 20 tests Node sur la logique pure du
portail (bornes Gantt en `.reduce()` — vérifié sans crash sur
200 000 segments, le piège connu du projet —, géométrie des segments,
filtres accents/casse, formats de durée).

**Non vérifié / choix assumés** : rendu navigateur non testé depuis
cet environnement (pas de `npm install` possible — syntaxe validée
par compilateur TypeScript sur chaque fichier) ; la sauvegarde de
préréglages de statistiques n'existe pas encore (l'éditeur compose à
la volée) ; le rattachement calendrier→ticket reste dans l'écran de
revue interne (le portail technicien saisit du temps manuellement).

## Portail — réouvertures, archivage, mots-clés, et le chaînon Keycloak

Reprise du portail multi-profils avec un nouveau cahier des charges
(liste triable par colonne, Gantt "mes tickets" pour le demandeur,
vue réouvertures pour la direction, suppression/archivage pour
l'admin, priorisation mots-clés pour le technicien, authentification
Keycloak/OpenLDAP). Découverte importante en reprenant : la quasi-
totalité existait déjà (portail 4 profils, Gantt direction, tri
urgence+attente, `priority_keywords`, réalm Keycloak avec client OIDC
`tickets-portal` déjà configuré et fédération LDAP prête) — construit
dans une session antérieure non visible dans la conversation où cette
reprise a eu lieu. Décidé avec la personne : le rôle "politique" garde
son nom (déjà dans Keycloak/DB/code), et "suppression" = archivage —
rien n'est jamais vraiment effacé, tout reste réversible.

**Backend, additif** :
- `tickets.archived_at` (migration douce comme les autres colonnes du
  portail) — masque un ticket des vues normales sans jamais l'effacer.
  Même mécanique que `ts_closed` pour la journalisation
  (`ticket_status_log`, événements `archived`/`unarchived`).
- `/queue` : exclut les archivés par défaut sur **tous** les états
  (`open`/`closed`/`all`), nouveau `state=archived` (vue dédiée),
  `include_archived=true` pour lever l'exclusion sans changer l'état.
- `/queue` expose désormais `keyword_score`/`keyword_matches` par
  ticket (`compute_keyword_matches()`, réutilise `priority_keywords`
  déjà en base, jusque-là seulement exploitée par le rattachement
  calendrier) — **le tri SQL existant (rang de niveau puis
  ancienneté) n'a pas changé**, vérifié par un test dédié : c'est un
  éclairage supplémentaire, pas un remplacement, comme demandé
  explicitement ("en plus", pas "à la place").
- `/tickets/parallel?user_id=` : nouveau filtre pour le Gantt "mes
  tickets" — inclut les fermés (historique complet), exclut les
  archivés ; différent du comportement par défaut sans filtre
  (pensé pour direction/technicien, qui n'affiche que les ouverts).
- `/stats/reopenings` : nouvel endpoint, agrège `ticket_status_log`
  déjà alimenté par `update_ticket()` — rien de nouveau à
  journaliser, juste une vue différente de données déjà là.

**Frontend** :
- `lib.js` : `sortTickets`/`nextSortState` (tri par colonne, état
  "ouvert d'abord" comme colonne synthétique et tri par défaut),
  `sortByKeywordScore`.
- **Demandeur** : liste passée de cartes à un tableau triable par
  colonne (état/sujet/statut/créée/dernière activité), bascule vers
  un Gantt scopé à ses propres tickets (`/tickets/parallel?user_id=`).
- **Technicien** : sélecteur de tri "urgence puis attente" (défaut,
  inchangé) vs "mots-clés en tête" (re-tri côté client de la liste
  déjà chargée, jamais un second appel réseau) ; badge 🔑 sur les
  tickets qui matchent, avec le détail des mots-clés en info-bulle.
- **Politique** : nouvelle section "🔁 Réouvertures" (table détaillée,
  liée à la carte de synthèse existante), reste de la vue inchangée.
- **Admin** : nouvel onglet "🔁 Réouvertures & archivage" à trois
  sous-vues (réouvertures en lecture, gestion suppression/archivage
  des tickets actifs, liste des archivés avec désarchivage) —
  "Supprimer" reste le mot utilisé par le bouton (celui de l'équipe),
  le mécanisme réel est l'archivage réversible.

**Bug réel rencontré et corrigé pendant cette session** : un
`str_replace` sur `PolitiqueView.jsx` a laissé un bloc dupliqué (fin de
l'ancien Gantt + panneau priorités non retirés, en plus de la nouvelle
version) — détecté immédiatement par le compilateur TypeScript
(`Declaration or statement expected`), confirmé par un script de
comptage de profondeur des balises `<div>`/`</div>` avant correction,
recompilation propre vérifiée ensuite. Rappel pour la suite : après
tout `str_replace` sur un bloc JSX qui touche une frontière de
fonction ou un `return`, revérifier que l'`old_str` couvrait bien
*toute* la portion remplacée, pas seulement son début.

**Keycloak — fait.** Le portail utilise désormais `react-oidc-context`
(Authorization Code + PKCE, exactement la même bibliothèque et le même
schéma que `hub/` — voir `hub/README.md` pour les deux vrais accrocs
rencontrés en le mettant en place la première fois, réutilisables ici
tels quels : dossier d'import Keycloak vide au premier démarrage,
`crypto.subtle` qui exige HTTPS ou `localhost`). `LoginGate` (saisie de
login sans mot de passe) a été retirée — l'identité vient maintenant de
Keycloak/LDAP (`preferred_username`), résolue vers `users.login` via
`/portal/profile` (déjà existant, inchangé). Un login LDAP authentifié
mais absent de la base tickets se voit proposer la création d'un
compte demandeur, comme avant — sauf que cette identité est désormais
**vérifiée par LDAP**, pas simplement tapée librement par n'importe
qui. Déconnexion = vraie déconnexion Keycloak (`signoutRedirect`), plus
de session locale `localStorage` à revalider manuellement au chargement
(oidc-client-ts gère sa propre persistance).

**4 groupes Keycloak créés** (`keycloak/realm-template.json`), un par
rôle existant, chacun avec le rôle realm correspondant déjà attaché
(`administrateurs`→`admin`, `demandeurs`→`demandeur`,
`techniciens`→`technicien`, `direction`→`politique`) — assigner
quelqu'un à un rôle devient "le mettre dans le groupe" depuis la
console Keycloak (Users → onglet Groups), plutôt que d'attribuer un
rôle réalm individuellement à chaque utilisateur. Distinct de la
fédération LDAP→rôles (`LDAP_ROLES_ENABLED`, toujours désactivée par
défaut) : ces groupes sont natifs à Keycloak, ne dépendent d'aucune
structure de groupes déjà existante côté annuaire LDAP.

**Ce qui reste, volontairement pas fait ici** : `tickets-api` ne
vérifie toujours aucun jeton (aucune API du projet ne le fait à ce
stade) — l'identification est garantie côté frontend uniquement, pas
encore de bout en bout au niveau de l'API elle-même.

**Vérifié depuis cet environnement** : 32 tests backend — **contre une
vraie base SQLite réelle, pas de bouchon** (`sqlite3` est un module
standard Python, disponible ici, contrairement à MySQL/PostgreSQL/
Elasticsearch) : migration `archived_at`, transitions archivé/
désarchivé journalisées, exclusion des archivés sur chaque état de
`/queue`, `state=archived` et `include_archived`, score mots-clés
(correspondances multiples, insensible à la casse, pattern invalide
ignoré sans bloquer les autres, texte vide), tri SQL non perturbé par
le score, filtre `user_id` sur `/tickets/parallel` (inclut fermés,
exclut archivés), `/stats/reopenings` (vide, un ticket, plusieurs
cycles de réouverture, tri par nombre décroissant), et 5 tests de
non-régression explicites sur le comportement pré-existant des routes
touchées. Côté front : 14 tests Node sur `sortTickets`/
`nextSortState`/`sortByKeywordScore`. Syntaxe de toutes les vues
modifiées validée par le compilateur TypeScript (qui a d'ailleurs
attrapé le bug de duplication ci-dessus).

**Non vérifié** : rendu navigateur réel (comme pour tout ce projet,
pas de `npm install` possible ici) ; l'intégration Keycloak elle-même,
puisqu'elle n'est pas encore écrite.

## Limites connues

- **Génération automatique de ticket depuis un incident supervision**
  pas encore construite — les colonnes `source_type`/`source_nom`
  existent en prévision, mais rien ne les alimente encore
  automatiquement.
- **Pas d'authentification** — comme le reste du projet à ce stade.
- **Récurrence ICS (RRULE) non expansée.**
- **Suggestion floue volontairement simple** (recouvrement lexical,
  pas de NLP) — fonctionne bien sur du vocabulaire technique répété,
  moins bien sur des reformulations complètement différentes.

## Bug réel — base tickets perdue entre deux livraisons

Rencontré en conditions réelles : un compte demandeur créé avec
succès (self-service, LDAP), puis disparu à la livraison suivante —
retour à l'écran "aucun compte tickets ne lui correspond encore".
Diagnostiqué en éliminant méthodiquement chaque fausse piste plutôt
qu'en devinant : montage éphémère du conteneur ? Non, bind mount
persistant (`./tickets/data-generator:/data`). Schéma SQLite détruit à
chaque démarrage ? Non, idempotent (`CREATE TABLE IF NOT EXISTS`)
depuis un moment. Permissions root bloquant l'écriture ? Non, le
conteneur tourne lui-même en root, cohérent avec le fichier. La cause
réelle : `tickets.db` vit dans l'arborescence du projet — un
déploiement qui supprime puis réextrait le dossier entier à chaque
nouvelle livraison (plutôt que d'extraire par-dessus l'existant) le
perd à chaque fois, puisqu'il n'est jamais versionné/livré (généré à
l'exécution). Corrigé : `TICKETS_DATA_DIR` (`.env`), même mécanisme
que `KEYCLOAK_IMPORT_DIR`/`KEYCLOAK_BACKUP_DIR` — sortir ce dossier de
l'arborescence du projet le met à l'abri d'un futur redéploiement
complet.

## Accès multi-rôles (sélecteur, si plusieurs groupes Keycloak)

Le rôle local (`users.role`, celui qui détermine "de qui" sont les
tickets affichés dans la vue demandeur) reste l'identité de référence
— mais une personne membre de **plusieurs groupes Keycloak à la fois**
(cas d'un compte de test/administration, rencontré en conditions
réelles) voit désormais un sélecteur de rôle dans l'en-tête, pour
prévisualiser les autres vues sans changer d'identité.

**Basé sur les GROUPES Keycloak, pas sur `realm_access.roles`** — bug
Keycloak documenté de longue date (KEYCLOAK-3469), rencontré en
conditions réelles : les rôles hérités via l'appartenance à un groupe
ne remontent pas toujours de façon fiable dans le jeton, contrairement
à l'appartenance aux groupes elle-même (claim `groups`, mapper
dédié), qui s'est révélée fiable. `computeAccessibleRoles()`
(`src/lib.js`) calcule donc l'union du rôle local et des rôles dérivés
des groupes (`GROUP_TO_ROLE`), filtrée sur les 4 rôles connus, ordre
stable. **Invisible pour l'immense majorité des comptes** (un seul
groupe pertinent) — le sélecteur n'apparaît que si
`accessibleRoles.length > 1`.

Lien "🏠 retour au hub" ajouté dans l'en-tête (`portal-hub-link`) — le
hub vit à la racine (`/`) de la même origine (entrée unique par
chemin), un simple lien relatif suffit, aucune configuration
supplémentaire nécessaire. **Bug de découvrabilité rencontré en
conditions réelles** : d'abord une icône seule (🏠) sans texte, jamais
repérée par la personne, qui pensait n'avoir que "Se déconnecter"
comme option pour quitter. Corrigé : libellé texte ajouté ("🏠 Hub"),
bouton avec bordure/fond visibles en permanence plutôt qu'au survol
seul.

**Vérifié** : `computeAccessibleRoles`/`groupsToPortalRoles`
— 10 tests Node, dont le scénario exact rencontré (compte local
"demandeur", membre des 5 groupes Keycloak → les 4 rôles du portail
accessibles, "supervision" ignoré car pas une vue du portail, ordre
stable, pas de doublon).

## Interface types/niveaux + import Keycloak (onglet Admin)

**Types & niveaux** — le backend avait déjà tout le CRUD
(`REFERENCE_TABLES` dans `app.py`, présent depuis un moment) mais
aucune interface ne l'exposait — la personne devait passer par
l'onglet "Gestion base" du module Supervision SI principal. Ajouté
directement dans le portail (onglet 🏷️ Types & niveaux), composant
générique `ReferenceTableEditor` réutilisé pour les deux tables plutôt
que dupliqué. **Testé réellement** (pas supposé) : cycle complet
create/update/delete pour les deux tables, y compris la protection
d'intégrité référentielle existante (suppression d'un type encore
référencé par un ticket → 409, jamais une suppression silencieuse qui
casserait des tickets existants) — 11 tests Python via le client de
test Flask réel.

**Import direct du groupe Keycloak "demandeurs"** — nouvelle route
`/users/import-keycloak-group`, authentifie contre Keycloak (mêmes
identifiants admin que `keycloak-backup`, réutilisés plutôt que
dupliqués), joint le service Docker interne `keycloak:8080` (jamais
via `tls-proxy` : trafic conteneur-à-conteneur, pas navigateur).
**Propriété de sécurité testée explicitement** : un compte déjà
présent localement n'est **jamais écrasé** par un réimport, même si
son rôle a été changé à la main entre-temps (ex. promu technicien) —
17 tests Python, Keycloak simulé (mock) pour rester testable sans
instance réelle.

## "Pour le compte de" (personnel qui saisit à la place d'un demandeur)

**Reconsidéré en cours de discussion** : la demande initiale parlait
d'"usurpation" façon vraie impersonation Keycloak — après avoir
creusé le cas d'usage réel (technicien au téléphone qui saisit pour un
demandeur), la personne a confirmé qu'un mécanisme plus simple, local
au portail, suffit largement — jamais de Token Exchange, jamais de
client confidentiel Keycloak. Pour un vrai changement d'identité (ex.
tester une appli comme un autre utilisateur), la fonction
"Impersonate" native de la console Keycloak, utilisée directement,
reste le bon outil — indépendante de tout ce qui suit.

**Mécanisme** : `tickets.acted_by_user_id` et
`ticket_messages.acted_by_user_id` (migration douce, même pattern que
`archived_at`) — `user_id` reste le PROPRIÉTAIRE (apparaît chez le
demandeur, normalement), `acted_by_user_id`, quand renseigné, trace
qui l'a RÉELLEMENT saisi. Jamais un remplacement, toujours une trace
additionnelle — NULL dans l'immense majorité des lignes (saisie
normale par le propriétaire lui-même).

Côté portail : `ActingForDemandeurView` (nouveau, `App.jsx`) — le
personnel choisit un demandeur dans une liste déroulante, puis voit la
vue demandeur normale pour cette personne, avec un bandeau rappelant
qu'il saisit pour son compte. S'applique à **toutes** les actions
possibles depuis cette vue (création de demande, sous-demande,
messages du fil) — décidé avec la personne plutôt que limité à la
seule création de ticket.

**Bouton "Se déconnecter" retiré pour le personnel** — basé sur les
**groupes** Keycloak (`administrateurs`/`techniciens`/`direction`/`supervision`),
pas le rôle local du portail : quelqu'un peut être "demandeur"
localement tout en étant dans le groupe "supervision" (ex. un cadre
qui soumet parfois des demandes), la consigne portait sur les groupes.
Point soulevé une fois par la personne, tranché : garder le bouton
retiré malgré la disparition du lien direct avec l'usurpation
d'origine — un poste partagé entre plusieurs techniciens perdrait son
seul moyen de changer de session actuel ; à surveiller si ça devient
un vrai besoin plus tard.

**Vérifié réellement** : 14 tests Python (migration idempotente,
`user_id`/`acted_by_user_id` corrects après création avec et sans
"pour le compte de", validation d'un `acted_by_user_id` inexistant →
400, enrichissement de `GET /tickets/<id>/messages` par jointure).
**Bug de harnais de test trouvé et corrigé en même temps** : deux
fichiers de test existants (écrits avant cette migration) ne
l'appelaient pas — auraient fait planter tout nouveau test touchant
aux tickets sans lien avec cette fonctionnalité elle-même.

## Échéance de ticket + escalade automatique d'urgence

`tickets.deadline_ts` (migration douce, comme les précédentes) —
échéance optionnelle, **indépendante du niveau d'urgence initial**.
`deadline_escalation_rules` (table + CRUD complet, onglet "🏷️ Types &
niveaux" → section "⏰ Escalade automatique") : plusieurs seuils
possibles (ex. "48h avant → Urgent", "4h avant → Bloquant"), le seuil
franchi le plus urgent l'emporte à chaque évaluation.

**Ne redescend jamais** un niveau déjà supérieur (une urgence déjà
justifiée manuellement ou par mots-clés n'est jamais rabaissée par ce
mécanisme) — propriété testée explicitement. Évalué à chaque appel de
`/queue` (déjà interrogée en boucle par la vue technicien) plutôt
qu'une tâche de fond séparée — pas de scheduler à ajouter pour ce
volume de tickets. Champ échéance ajouté au formulaire de création
(vue demandeur), optionnel.

**Vérifié réellement** : 17 tests Python — les 5 scénarios croisés
(loin de l'échéance, un seuil franchi, deux seuils franchis, déjà à un
niveau supérieur, sans échéance du tout), l'idempotence d'une
réévaluation répétée, le branchement réel via `/queue` (pas juste la
fonction isolée), et la désactivation d'une règle.

## Vue calendrier livrée côté hub (livraison #272)

Chantier précédemment marqué "non livré" -- corrigé. Vérifié en
profondeur AVANT de construire quoi que ce soit : chaîne complète
testée de bout en bout (import ICS réel via `/calendar/import`,
dédoublonnage par UID confirmé sur un réimport identique, détection
par mot-clé, affectation événement→ticket via `/calendar/assign`) --
aucune régression trouvée, tout fonctionnait déjà correctement.

`CalendarView.jsx` (nouveau, côté hub) -- vue AGENDA (liste triée par
date), pas une grille semaine/jour -- choix délibéré dans un
environnement sans navigateur réel pour vérifier visuellement une
grille complexe ; import par adresse secrète iCal (`/calendar/
import_url`, déjà existant), filtre non affectés/affectés/tous,
sélection multiple + affectation à un ticket. Intégrée dans la
nouvelle tuile "ENT" du hub (voir `tasks/README.md`).

**Reste PAS FAIT** : une vraie grille semaine/jour visuelle (report
explicite, jamais tenté sans pouvoir la vérifier ici) ; "création de
ticket depuis un événement" en un clic (actuellement : affecter à un
ticket déjà existant, pas encore créer un nouveau ticket directement
depuis la vue calendrier).

## Débordement CSS du badge de groupes Keycloak

Retour réel, capture d'écran à l'appui : `.role-chip` (badge affichant
les groupes Keycloak, `🗂️ {groups.join(", ")}`) n'avait aucune limite
de largeur -- avec plusieurs groupes concaténés (un compte dans 7
groupes produit une chaîne d'environ 85 caractères), le header
débordait complètement.

Corrigé à deux niveaux : classe dédiée `.role-chip-groups` (largeur
plafonnée, troncature par points de suspension, liste complète
toujours disponible au survol via l'attribut `title`, mis à jour pour
la contenir en entier -- avant ce correctif il ne montrait qu'un
texte générique), et `flex-wrap: wrap` sur `.portal-header` en repli
de sécurité si un autre élément venait un jour causer le même
problème.

Point d'attention CSS retenu : `.role-chip` est en `inline-flex`
(nécessaire pour l'AUTRE usage de cette classe, le badge "👤 nom"),
incompatible avec `text-overflow: ellipsis` qui a besoin d'un contenu
texte simple en `inline-block`. Le sélecteur combiné
`.role-chip.role-chip-groups` force ce changement de mode d'affichage
UNIQUEMENT pour le badge des groupes, sans affecter l'autre usage.

## Vue demandeur redessinée — tableau au centre, ligne collante

Retour de design explicite, trois changements liés :

**Disposition inversée** -- `.demandeur-layout` remplace l'ancienne
`.columns` (toujours utilisée par `TechnicienView.jsx`, volontairement
non touchée) : le tableau des demandes devient la colonne LARGE/
centrale (`flex: 1`), le détail devient la colonne secondaire à
largeur fixe (420px) à droite -- l'inverse de la disposition
d'origine (formulaire+tableau à gauche en largeur fixe 400px, détail
flexible à droite).

**Ligne "nouvelle demande" collante** -- plus un panneau séparé
au-dessus du tableau, mais une SECONDE ligne dans le `<thead>` du
tableau lui-même, à côté de la ligne d'en-têtes triables. Objectif
explicite : rester visible en faisant défiler les anciennes demandes,
pour pouvoir s'en inspirer sans perdre le formulaire de vue. `position:
sticky` appliqué aux CELLULES (`.sticky-th`/`.sticky-td`), pas à
`<thead>`/`<tr>` directement -- le support navigateur de sticky sur
ces éléments de table est historiquement peu fiable, contrairement
aux cellules. Champs Sujet/Type/Envoyer toujours visibles (compact),
Échéance/Détails repliés par défaut derrière un bouton "▸ détails"
pour ne pas alourdir la ligne en permanence.

**Recopier un ticket existant** -- retour explicite : sélectionner un
ticket affiche un bouton "📋 Recopier vers une nouvelle demande" qui
préremplit la ligne collante (sujet, type, détails) avec le contenu
de ce ticket -- jamais un envoi automatique, juste une base à ajuster
avant validation. Rouvre automatiquement les champs étendus si le
ticket recopié avait des détails, pour ne jamais les recopier de
façon invisible. Logique d'extraction (`ticketToDraftFields`, dans
`lib.js`) volontairement PURE et séparée du rendu -- testable sans
React ni DOM, comme les autres fonctions de ce fichier.

Vérifié réellement : 8 tests sur `ticketToDraftFields` (extraction
correcte, repli sûr sur ticket incomplet/null/undefined, jamais l'id/
les dates/le statut dans le résultat). Reste vérifié par syntaxe
(tsc, sur tous les fichiers du module) et équilibre CSS -- **aucune
suite de tests de non-régression automatisée n'existe pour ce module
dans cet environnement** (contrairement au coffre-fort), à garder en
tête en testant ce changement en conditions réelles.

**Reste de cette série de retours** : la vue technicien (liste au
centre au démarrage, commandes à gauche avec liste des demandeurs et
bouton "usurpation" pour retranscrire des demandes orales, priorités/
élastiques de temps à droite, liste qui bascule à gauche à la
sélection d'un ticket) -- chantier à part entière, pas commencé.

## Vue technicien redessinée — commandes/liste/priorités

Suite directe du chantier précédent, dernier morceau de la série de
retours de design.

**Disposition en 3 colonnes**, changeant selon le contexte (demandé
explicitement) :
- **Sans sélection** : gauche = "👥 Demandeurs" (commandes), centre =
  file d'attente (large), droite = priorités/échéances.
- **Ticket sélectionné** : la file d'attente bascule à GAUCHE
  (compacte), le détail du ticket prend la place CENTRALE. La colonne
  droite (priorités/échéances) reste affichée dans les deux cas --
  contexte utile en permanence, qu'on travaille un ticket précis ou
  non.

**Usurpation** ("le technicien prend des demandes orales et les
retranscrit") -- réutilise le mécanisme `acted_by` DÉJÀ existant
(`ActingForDemandeurView` dans `App.jsx`, jusqu'ici accessible
uniquement comme cas de repli pour un rôle ne correspondant à rien
d'autre) : liste des demandeurs dans la colonne de gauche, bouton
"🎭 Usurper" par personne. Une fois activé, remplace ENTIÈREMENT la
vue technicien (jamais superposé) par la vue demandeur normale pour
cette personne, avec le technicien tracé comme auteur réel -- exactement
le même mécanisme que le formulaire de sous-demande, jamais un vrai
changement d'identité Keycloak.

**Panneau "priorités et élastiques de temps"** -- clarifié après coup
en trois perspectives à combiner (le premier essai était insuffisant) :

1. **Temps sans prise en charge** -- `wait_seconds`, déjà disponible.
   Nouvelle section "⏳ En attente" dans le panneau (les 5 tickets
   ouverts en attente depuis le plus longtemps).
2. **Temps depuis la prise en charge** -- **pas encore construit,
   nécessite une clarification** : aucun événement "pris en charge"
   n'est tracé aujourd'hui (`ticket_status_log` ne connaît que
   opened/closed/reopened). Avant d'ajouter un suivi backend, il faut
   trancher ce qui déclenche ce moment -- un bouton explicite
   "je prends en charge", le premier changement de statut, ou le
   premier message technicien dans le fil -- chacun a des
   implications différentes. En attente d'arbitrage.
3. **Temps restant avant l'échéance** -- corrigé après un vrai
   contresens dans la première version : le mécanisme d'escalade
   RÉEL (`apply_deadline_escalations`, backend) ne s'appuie QUE sur
   `deadline_ts` explicitement saisi, or ce champ est rarement
   renseigné en pratique. La perception réelle de l'urgence vient
   aujourd'hui du NIVEAU (priorité) seul : Forte = J+0, Moyenne = J+1,
   Faible = J+10, Notification = pas encore de délai défini. La barre
   affichée utilise désormais `deadline_ts` s'il est saisi (signal le
   plus fort), sinon retombe sur cette échéance IMPLICITE déduite du
   niveau -- marquée "≈" dans l'interface pour la distinguer d'une
   vraie échéance saisie. Basé sur la POSITION du rang parmi les
   niveaux connus, jamais sur le libellé exact ("Forte"/"Moyenne"...)
   -- reste correct même si les niveaux sont renommés. Amené à
   évoluer : version intermédiaire (délai modifiable + échéance
   calculée modifiable), version affinée (engagements paramétrés par
   type de tâche).

Logique pure et testée : `distinctRanksDesc`, `impliedDeadlineTs`,
`deadlineUrgency` (échéance explicite prioritaire sur l'implicite),
`ticketsByDeadlineUrgency`, `ticketsByLongestWait`, `groupByLevel`.

Ancien CSS `.columns`/`.col-list`/`.col-detail` retiré (plus aucun
usage après cette refonte, vérifié explicitement) -- jamais de code
mort laissé derrière, même principe déjà appliqué au coffre-fort.

Vérifié réellement : 22 tests (dont la vérification centrale :
échéance explicite qui l'emporte sur l'implicite, calcul par POSITION
de rang jamais par libellé, niveau "Notification" sans délai calculé
plutôt qu'un chiffre inventé). Syntaxe (tsc) sur l'ensemble du
module, équilibre CSS. Même réserve que pour la vue demandeur :
aucune suite de non-régression automatisée pour ce module dans cet
environnement.

**Reste ouvert** : le suivi de la "prise en charge" (perspective 2),
en attente d'arbitrage sur ce qui doit le déclencher.

## Statuts paramétrables avec type — "prise en charge" enfin résolue

Chantier long à converger (plusieurs allers-retours de clarification,
la personne changeant d'avis en cours de route -- normal pour une
vraie décision de conception, capturé ici pour la trace) :
- D'abord : type fixe (en_cours/en_pause/en_attente/**clos**).
- Puis : les deux ("clos" comme type, ou `ts_closed` existant)
  doivent fusionner, ou j'élimine le moins pratique.
- **Décision retenue** : élimination de "clos" comme type --
  `ts_closed` reste le SEUL mécanisme de fermeture/réouverture (déjà
  robuste, avec historique testé). Le type ne catégorise plus QUE le
  travail actif.
- Confirmation finale : les statuts de clôture réels (résolu, livré,
  abandonné...) **n'ont délibérément pas de type** -- ils
  accompagnent la fermeture manuelle, jamais un remplacement de
  `ts_closed`. Une demande peut être close sans être traitée
  (abandonné, par exemple), et un ticket clos peut toujours être
  rouvert -- exactement l'exigence de départ.

**Schéma** : `statuts.type` (TEXT nullable, contraint à `en_cours`/
`en_pause`/`en_attente` -- validé aussi bien à la création qu'à la
modification, `VALID_STATUT_TYPES`). `tickets.first_in_progress_ts`
(INTEGER nullable) -- posé UNE SEULE FOIS, jamais réécrit même si le
statut change à nouveau plus tard.

**Prise en charge, enfin définie précisément** : premier passage
d'un ticket à un statut de type `en_cours`. `PUT /tickets/<id>`
restructuré (le calcul se fait désormais AVANT la construction de la
requête UPDATE, pour pouvoir y ajouter `first_in_progress_ts` dans la
même écriture atomique) -- risque réel pris au sérieux : 18 tests
couvrant à la fois le nouveau comportement ET la non-régression
complète de l'existant (fermeture/réouverture/archivage, tous
toujours journalisés exactement comme avant).

**Interface** : nouveau `StatutsEditor` (`AdminView.jsx`) -- aucune
gestion des statuts n'existait côté portail jusqu'ici (contrairement
à types/niveaux), alors que le backend avait déjà tout le CRUD
générique. Menu déroulant contraint pour le type (pas un champ libre
comme le motif générique `ReferenceTableEditor`).

**Panneau "élastiques de temps"** (vue Technicien) : nouvelle section
"🔧 En cours depuis" (perspective 2, enfin disponible) --
`ticketsByLongestInProgress`, triée du plus longtemps pris en charge
au moins longtemps, exclut les tickets fermés et ceux jamais pris en
charge (couverts par "⏳ En attente" déjà existante).

Vérifié réellement : 26 tests au total sur cette tranche (18 sur la
migration/validation/prise en charge côté backend, 8 sur la nouvelle
fonction de tri). Non-régression complète, y compris le test Keycloak
existant.

## Sauvegardes versionnées — fondation avant l'éditeur générique et la console SQL

Chantier #3 de la file (gestionnaire de base de données généralisé),
commencé par la fondation de sécurité plutôt que par les
fonctionnalités les plus visibles -- demandé explicitement en
prévention : "d'où l'organisation de backup versionnés systématique
et d'options de restore", avant d'exposer un éditeur générique de
lignes ou une console SQL directe (les deux prochaines étapes de ce
chantier, pas encore construites).

**Deux déclencheurs**, demandés explicitement : périodique (toutes
les `TICKETS_BACKUP_PERIODIC_INTERVAL_HOURS` heures, 24h par défaut)
et avant chaque action risquée (appel direct de `run_backup()`,
prévu pour les futures routes d'édition générique/SQL non-SELECT --
pas encore câblé, ces routes n'existent pas encore).

**Format** : dump SQL natif, demandé explicitement (pas le format
JSON déjà utilisé par `/export`) -- `conn.iterdump()` (bibliothèque
standard) en SQLite, `pg_dump`/`psql` en PostgreSQL (binaires ajoutés
au Dockerfile, `postgresql-client`). Nouveau module dédié
`backup_manager.py` -- toutes les fonctions acceptent leurs
dépendances en paramètre (connecteur SQLite, exécuteur de
sous-processus), jamais un appel direct en dur, pour rester
testables sans vrai serveur PostgreSQL.

**Sécurité prise au sérieux** :
- Restauration DESTRUCTIVE par nature (SQLite : `iterdump()` produit
  des `CREATE TABLE` qui échoueraient sur une base déjà peuplée --
  le fichier est donc supprimé puis reconstruit). Copie de sécurité
  de l'état ACTUEL (`.before-restore`) conservée et restaurée
  automatiquement si la restauration échoue en cours de route --
  **jamais un échec partiel qui laisserait la base dans un état pire
  qu'avant**, vérifié réellement avec un dump volontairement corrompu.
- Nom de fichier de sauvegarde vérifié AVANT tout accès disque
  (`is_safe_backup_filename`) -- traversée de chemin (`../`) refusée
  aussi bien dans la logique interne que via la route HTTP elle-même.
- Mot de passe PostgreSQL jamais en argument de ligne de commande
  (visible dans `ps`) -- toujours via la variable d'environnement
  `PGPASSWORD`, même précaution qu'ailleurs dans ce projet.
- **Bug réel trouvé et corrigé avant tout déploiement** : gunicorn
  tourne avec plusieurs workers (`--workers 2`) -- chaque worker est
  un PROCESSUS SÉPARÉ qui importe `app.py` indépendamment, donc
  démarrerait sa PROPRE boucle périodique sans garde-fou, créant des
  sauvegardes en double à chaque intervalle. `_should_run_periodic_backup()`
  vérifie l'âge de la dernière sauvegarde périodique (fichier) avant
  d'en créer une nouvelle -- fenêtre de course résiduelle acceptée
  (au pire une sauvegarde en trop, jamais une perte de données), un
  vrai verrou distribué étant hors de proportion ici.

**Nouvelles routes** : `GET /backups` (liste), `POST /backups`
(déclenchement manuel), `POST /backups/<fichier>/restore`.

Vérifié réellement, avec du VRAI SQLite (pas une simulation) : dump
puis modification de la base puis restauration -- l'état exact de la
sauvegarde est retrouvé, les changements post-sauvegarde disparaissent
bel et bien. Scénario le plus critique testé explicitement : dump
corrompu en restauration → exception levée → **l'état d'avant est
intégralement préservé**, jamais de perte de données. Rétention
réelle vérifiée (purge automatique au-delà du nombre configuré).
Garde-fou anti-doublon multi-workers testé avec plusieurs workers
simulés. PostgreSQL : construction de commandes et gestion d'erreur
testées avec un faux sous-processus injecté (aucun serveur
PostgreSQL disponible dans cet environnement pour un test réel
bout en bout côté PostgreSQL -- seule réserve sur cette tranche).

52 tests réels au total sur cette fondation. Non-régression complète
sur le reste du backend tickets.

**Suite de ce chantier** (pas encore commencée) : éditeur générique
de lignes par table (avec appel à `run_backup("avant-edition")`),
console SQL directe avec test de syntaxe (`EXPLAIN` avant exécution
réelle, avec `run_backup("avant-sql")` pour tout ce qui n'est pas un
SELECT), et l'arborescence des relations (contraintes ou non).

## Barre "nouvelle demande" sortie du tableau — désalignement corrigé

Retour de test réel : la ligne "nouvelle demande" (une pseudo-ligne
de tableau, `colSpan` sur toute la largeur) essayait de coller sur la
grille de colonnes du tableau, mais son contenu interne (champ, menu
déroulant, bouton) ne correspondait jamais aux largeurs réelles des
colonnes "état/sujet/statut/..." en dessous -- décalage visuel
gênant.

**Corrigé** : sortie du `<table>` entièrement, devient sa propre
barre collante (`.new-request-bar`), juste au-dessus de l'en-tête des
colonnes -- l'en-tête touche désormais directement les données, plus
rien de mal aligné entre les deux. `position:sticky` toujours
appliqué à la cellule d'en-tête elle-même (`.sticky-th`), pas au
`<thead>`.

**Imperfection mineure assumée** : le décalage vertical entre la
barre et l'en-tête (`top: 52px` sur `.sticky-th`) est calé sur la
hauteur de la barre en état COMPACT (repliée) -- en état déplié
(champs échéance/détails visibles), la barre grandit et peut
légèrement chevaucher l'en-tête une fois les deux "collés" en haut du
défilement. La vraie plainte corrigée ici (désalignement des
colonnes) est traitée ; cet empilement pixel-parfait resterait à
vérifier dans un vrai navigateur, aucun disponible dans cet
environnement.

## Champ "site" sur le ticket, avec import en masse

Demandé en cours de test, en marge du chantier gestionnaire de base
de données : un champ "site" sur chaque ticket, alimenté depuis une
liste importée en masse (fichier texte, un site par ligne).

**Nouvelle table `sites`** (même famille que `types`/`levels`/
`statuts`) -- schéma SQLite et PostgreSQL synchronisés manuellement
(aucun outillage de migration partagé entre les deux dans ce projet).
`tickets.site_id`, migration douce comme les autres colonnes
ajoutées après coup. Réutilise le mécanisme CRUD générique déjà en
place (`REFERENCE_TABLES`) -- aucune route dupliquée pour l'édition/
suppression.

**Import en masse** (`POST /sites/import-text`) -- point le plus
délicat, signalé explicitement par la personne (fichier "Non-ISO
extended-ASCII text", donc PAS de l'UTF-8) : `decode_uploaded_text()`
essaie UTF-8, puis CP1252 (encodage Windows français le plus
répandu), puis Latin-1 en dernier recours (n'échoue jamais, accepte
n'importe quel octet). Le fichier est envoyé BRUT côté interface
(`FormData` avec le `File` directement, jamais `file.text()` qui
forcerait un décodage UTF-8 prématuré côté navigateur, perdant
irrémédiablement la possibilité d'essayer un autre encodage côté
serveur). Déduplique via la contrainte `UNIQUE` sur `sites.label` --
une ligne déjà présente est simplement ignorée (`skipped`), jamais
une erreur qui interromprait tout l'import pour un seul doublon.

**Interface** : nouvelle section "Sites" dans Admin → Référentiel
(édition manuelle comme les autres tables de référence, plus un
bouton d'import de fichier dédié). Menu déroulant "Site" ajouté à la
ligne collante de création (vue Demandeur, à côté de "Type") et au
formulaire éditable du détail (vue Technicien). Repris par "Recopier
vers une nouvelle demande" (`ticketToDraftFields`) -- un ticket
similaire concerne souvent le même site, jamais imposé, juste une
base à ajuster comme les autres champs de ce brouillon.

Vérifié réellement, avec du VRAI texte encodé en CP1252 (pas une
simulation) : les accents français ("Bibliothèque", "Batiment")
correctement retrouvés depuis les octets bruts. Réimport testé --
aucun doublon créé. Ticket avec et sans site testés (champ
optionnel). 32 tests réels sur cette tranche. Non-régression
complète sur tout le backend tickets.

## Éditeur générique de lignes + arborescence des relations

Suite du chantier gestionnaire de base de données, après la fondation
de sauvegarde. Nouveau module `db_explorer.py` -- introspection pure,
testable avec un curseur injecté (jamais une connexion créée en
interne), séparée de la logique des routes.

**Sécurité prise au sérieux** : tout nom de table venant d'une
requête HTTP est validé contre la liste RÉELLEMENT introspectée
(`is_known_table`) AVANT tout usage dans une chaîne SQL interpolée
(`PRAGMA table_info(<table>)` ne supporte pas les paramètres liés
côté SQLite -- l'interpolation est nécessaire, la validation en
amont est donc la seule protection). La clé primaire d'une table
n'est **jamais** éditable via ce mécanisme, quelle que soit la table
-- glissée dans le corps d'une requête, elle est simplement ignorée
(seuls les autres champs, fournis, sont appliqués).

**"Contraintes ou non"**, demandé explicitement : relations DÉCLARÉES
(vraies `REFERENCES` du schéma) ET PROBABLES (déduites du nom de
colonne -- `xxx_id` dont le préfixe pluralisé correspond à une table
connue), marquées "≈" dans l'interface. Vérifié sur le VRAI schéma
de la base tickets (pas une simulation) : 15 relations détectées,
dont une intéressante trouvée en le testant --
`tickets.site_id → sites.id` ressort comme **non déclarée** (ajoutée
via `ALTER TABLE` sans jamais poser de vraie contrainte FK) --
exactement le genre de cas que cette fonctionnalité doit repérer.

**Sauvegarde avant édition** -- chaque modification via l'éditeur
générique déclenche `run_backup("avant-edition")` AVANT l'écriture
(voir le chantier sauvegardes précédent) ; si la sauvegarde échoue,
l'édition est annulée par prudence plutôt que risquée sans filet.
Vérifié réellement : une sauvegarde apparaît bien AVANT chaque
modification, avec le bon fichier tracé.

**Interface** : l'onglet "🗄️ Base" (Admin) gagne deux sous-onglets --
"📋 Parcourir/éditer" (choix de table, pagination, édition cellule par
cellule au blur) et "🌳 Relations" (liste groupée par table
d'origine). Limite connue, assumée : un champ vidé s'enregistre
comme une chaîne vide, pas comme `NULL` -- pas de bascule explicite
pour "remettre à vide" pour l'instant.

Vérifié réellement : 60 tests sur cette tranche (introspection pure
avec un vrai SQLite en mémoire, contre le vrai schéma complet de la
base tickets, et les routes elles-mêmes -- y compris la vérification
explicite qu'une tentative de modifier une clé primaire est bien
ignorée). Non-régression complète sur tout le backend tickets.

**Reste de ce chantier** : la console SQL directe avec test de
syntaxe (`EXPLAIN` avant exécution réelle, `run_backup("avant-sql")`
pour tout ce qui n'est pas un `SELECT`) -- dernier morceau, pas
encore commencé.

## Console SQL directe — dernier morceau du gestionnaire de BDD

Clôt le chantier #3 (gestionnaire de base de données généralisé) --
console SQL directe avec test de syntaxe, demandée dès le départ.

**Vérifié EMPIRIQUEMENT avant d'écrire une ligne de code** (pas
supposé) -- deux points de sécurité fondamentaux pour ce mécanisme :
- `EXPLAIN <sql>` ne modifie JAMAIS réellement les données, même sur
  `DELETE`/`DROP TABLE` -- testé avec du vrai SQLite (crée une ligne,
  `EXPLAIN DELETE FROM t`, vérifie que la ligne existe toujours ;
  `EXPLAIN DROP TABLE t`, vérifie que la table existe toujours).
  C'est le mécanisme même du "test de syntaxe" demandé.
- `cur.execute()` (SQLite) refuse nativement les instructions
  empilées (`"SELECT 1; DROP TABLE x;"`) -- protection native contre
  ce type d'injection, jamais besoin de la redévelopper. Non
  re-vérifié pour PostgreSQL dans cet environnement (aucun serveur
  disponible) -- même réserve que pour `backup_manager.py`.

**Nouveau module `sql_console.py`** -- `is_select_statement` (premier
mot de la requête, détermine si une sauvegarde/confirmation est
nécessaire), `check_syntax` (le test, absorbe toute erreur
proprement), `execute_sql` (l'exécution réelle, jamais de commit
elle-même -- responsabilité de la route appelante).

**Sauvegarde avant exécution** -- `run_backup("avant-sql")`
déclenché pour tout ce qui N'EST PAS un `SELECT`, jamais pour un
`SELECT` (lecture seule, aucun risque). Vérifié réellement : un
`SELECT` n'entraîne aucune sauvegarde, un `UPDATE` en entraîne
exactement une, avec le fichier tracé sous le bon nom.

**Interface** : nouveau sous-onglet "💻 SQL" (Admin → 🗄️ Base) --
zone de texte, deux boutons distincts ("🔍 Vérifier la syntaxe",
jamais de confirmation nécessaire ; "▶️ Exécuter", confirmation
explicite exigée pour tout ce qui n'est pas un `SELECT`, avec rappel
qu'une sauvegarde sera prise). Résultats affichés en tableau pour un
`SELECT`, en nombre de lignes affectées sinon.

Vérifié réellement : 45 tests sur cette tranche (27 sur le module
pur avec du vrai SQLite -- y compris la vérification explicite que
`EXPLAIN` sur un `DELETE`/`DROP TABLE` ne touche jamais aux vraies
données --, 18 sur les routes, dont le déclenchement effectif de la
sauvegarde avant écriture). Non-régression complète sur tout le
backend tickets.

**Chantier #3 complet** : sauvegardes versionnées, éditeur générique
de lignes, arborescence des relations, console SQL -- les quatre
volets demandés sont livrés.

## Mise en page adaptative — colonne centrale pleine largeur quand rien n'est sélectionné

Dernière des 4 demandes groupées avec le mini-tableau d'observations
du coffre-fort. Demandé explicitement : "quand l'écran est vide, la
colonne centrale devrait prendre la largeur et la disposition se
transformer de fiche à ligne dans une table".

**Vue Technicien** : nouveau `QueueTable` -- vrai `<table>` (colonnes
#, Sujet, Demandeur, Site, Type, Niveau, Statut, Attente) remplaçant
les cartes compactes `QueueItem` quand aucun ticket n'est sélectionné.
`QueueItem` reste utilisé tel quel dans la file étroite de la colonne
latérale (une fois un ticket sélectionné, pour basculer rapidement
entre tickets).

**Colonne priorités masquée quand rien n'est sélectionné** -- choix
assumé : ses panneaux ("🎯 Priorités", "⏳ En attente", "🔧 En cours
depuis", "⏰ Échéances proches") deviennent largement redondants une
fois que le tableau plein largeur affiche déjà toute la file triée
avec sa colonne "Attente" -- l'espace libéré revient à la colonne
centrale. Redevient visible dès qu'un ticket est sélectionné, disposition
à 3 colonnes inchangée dans ce cas. **Point à confirmer avec la
personne** : si ces panneaux (tri par plus longue attente/prise en
charge/échéance) manquent en pratique une fois testés, un retour en
arrière partiel (les garder mais plus étroits) reste facile.

**Vue Demandeur** : `demandeur-detail-col` (déjà une fiche à droite
d'un tableau déjà présent, `demandeur-table-col`) était TOUJOURS
rendue, y compris vide (juste un message de substitution) --
empêchait le tableau de prendre toute la largeur même sans sélection.
Désormais rendue uniquement quand `detail` existe -- `flex: 1` sur
`demandeur-table-col` fait le reste automatiquement (flexbox), aucun
CSS supplémentaire nécessaire.

Media query responsive existante (< 900px, colonnes empilées)
vérifiée compatible sans modification -- s'applique uniquement aux
colonnes réellement présentes.

Vérifié : syntaxe (tsc) sur les deux vues, cohérence des setters
React. **Non vérifié dans cet environnement** : rendu visuel réel,
aucun navigateur disponible ici -- particulièrement important à
confirmer pour ce chantier vu qu'il s'agit uniquement de mise en
page.

### Complément — la colonne "👥 Demandeurs" avait été oubliée

Repris dans le backlog (l'item restait marqué non traité malgré ce
qui précède) : la colonne LATÉRALE de la vue Technicien affichait
encore "👥 Demandeurs" en PERMANENCE (300px fixes) quand rien n'est
sélectionné -- oubliée lors du premier passage ci-dessus, qui n'avait
traité que la colonne centrale (`QueueTable`) et la colonne priorités.
`QueueTable` ne prenait donc jamais VRAIMENT toute la largeur, juste
`100% - 300px - gap`.

**Corrigé** : quand rien n'est sélectionné, une seule colonne pleine
largeur (`technicien-full-col`) regroupe désormais file d'attente
(`QueueTable`, inchangé) ET l'accès aux Demandeurs -- replié par
défaut dans un panneau "+" (`showDemandeurs`, même motif que partout
ailleurs dans le projet) plutôt qu'une colonne dédiée à 300px qui
mangeait de la place même sans jamais s'en servir. Disposition à 3
colonnes (side/center/priority) inchangée dès qu'un ticket est
sélectionné.

Vérifié : syntaxe (tsc), classes CSS toutes présentes, setters
`useState` déclarés/utilisés cohérents, accolades JSX équilibrées.
Media query responsive existante (< 900px) compatible sans
modification (`technicien-full-col` a déjà `width: 100%` par défaut).
**Non vérifié dans cet environnement** : rendu visuel réel.

## Attribution par technicien, Gantt et timeline pour le technicien

Suite du bug tickets/rappels (livraison #114, voir hub/README.md).
Backlog : Gantt pour le technicien (jusqu'ici réservé à l'écran
politique) + timeline pour le technicien. En creusant la timeline,
découverte réelle : `ticket_time_entries` n'était JAMAIS rattaché à
un technicien précis (aucune colonne d'attribution, ni dans la table
ni dans aucun des points de saisie). Question ciblée posée avant de
construire (timeline de toute la file, sans rien toucher au schéma,
OU ajouter l'attribution d'abord) -- réponse : ajouter l'attribution,
même si "plus gros".

**Backend** : `ticket_time_entries.technician_login` (TEXT, nullable)
ajouté aux TROIS endroits qui définissent ce schéma (SQLITE_SCHEMA
embarqué dans `app.py`, `data-generator/schema.sql`,
`data-generator/schema.postgres.sql` -- gardés synchronisés,
convention déjà en place pour `weight`) + migration douce
(`ensure_technician_login_column`, même patron que
`ensure_weight_column`, fonctionne identiquement sur SQLite et
Postgres via `get_connection()`). `POST /tickets/<id>/time_entries`
accepte désormais `technician_login` (optionnel, rétrocompatible --
jamais validé contre `users`, même raisonnement que
`collections.created_by` côté coffre-fort). Nouvelle route
`GET /time_entries?technician_login=...` (jointure légère avec le
sujet du ticket, tri chronologique) pour la timeline personnelle.

**Trois points de création de segment identifiés** :
1. Rappel d'activité (`hub/src/settingsClient.js`,
   `submitTimeSegment`) -- attribue désormais au `login` du
   technicien connecté.
2. Saisie manuelle (`TechnicienView.jsx`, `addTimeEntry`) -- attribue
   à `me.login`.
3. Affectation calendrier en masse (`/calendar/assign`) -- **jamais
   touchée**, reste `technician_login: NULL`. Le connecteur OAuth/ICS
   est actuellement conçu "mono-opérateur" (voir commentaire existant
   sur `_pending_oauth_state`, jamais de session multi-utilisateur) --
   l'attribuer proprement demanderait de revoir ce connecteur en
   profondeur, hors de la portée de ce chantier. Dit explicitement
   plutôt que de laisser croire à une couverture complète.

**Gantt technicien** : réutilise TEL QUEL `/tickets/parallel` (même
route, mêmes fonctions pures `ganttBounds`/`segmentGeometry`/
`filterGanttRows` que l'écran politique) -- scopé aux tickets
ACTUELLEMENT affichés dans la file du technicien (`ticket_ids=...`,
mêmes filtres état/type/statut/demandeur déjà appliqués), pas la
liste globale de l'écran politique. Rechargé sur `tickets` (référence
stable) plutôt que `displayedTickets` (nouveau tableau à chaque
rendu, aurait fait requêter à chaque interaction sans rapport).

**Timeline technicien** : nouveau panneau, liste chronologique plate
(volontairement PAS un Gantt par ticket) des propres segments du
technicien connecté, via `GET /time_entries?technician_login=...`.

Les deux nouveaux panneaux repliés par défaut (même motif "+" que
"👥 Demandeurs"), chargés seulement à l'ouverture.

Vérifié réellement : `app.test_client()` (base isolée) -- création de
segment avec/sans attribution, jointure avec le sujet du ticket,
filtrage par technicien (y compris technicien sans aucun segment --
liste vide, jamais une erreur), **non-régression explicite sur
`/calendar/assign`** (jamais touché, toujours fonctionnel, ses
segments restent bien non attribués). Scénario de migration dédié sur
une base simulant l'ancien schéma (colonne retirée puis migration
rejouée) : segment pré-existant jamais perdu, nouveau segment attribué
créable ensuite. Syntaxe (`tsc --jsx` sur les 4 fichiers JS touchés,
`ast.parse` sur `app.py`), classes CSS toutes présentes, setters
`useState` cohérents, accolades JSX et CSS équilibrées.

**Non vérifié dans cet environnement** : rendu visuel réel, aucun
navigateur disponible ici -- particulièrement le Gantt technicien
(réutilisation de composants visuels déjà éprouvés côté politique,
mais jamais testés dans ce nouveau contexte) et la timeline (nouveau
panneau, jamais vérifié en conditions réelles). **Non fait,
assumé** : les segments importés du calendrier restent invisibles
dans "Ma timeline" (jamais attribués, voir ci-dessus) -- à rouvrir
plus tard si l'attribution du connecteur calendrier devient un besoin
réel.

## Documents joints (livraison #160)

`TicketDocuments.jsx` (`components/`) -- section "📎 Documents
joints" affichée à côté du fil de discussion (`TicketThread.jsx`)
dans les 4 vues (Demandeur, Technicien, Politique, Admin ×2 --
réouvertures et archivage). S'appuie sur `ged-api` (nouveau module
`ged/`, `gedApi.js`) EN DIRECT, jamais via `tickets-api` -- même
raisonnement de couplage FAIBLE que le reste de ce projet (une
liaison `linked_type="ticket"`/`linked_id=<id>`, voir
`ged/README.md` pour la table polymorphe).

Fonctions couvertes : lister les documents déjà liés à un ticket,
envoyer un nouveau document (lié immédiatement, un seul appel),
ajouter une nouvelle version à un document existant, télécharger
(dernière version, lien direct), retirer un document du ticket
(supprime le document CÔTÉ MAYAN, pas seulement la liaison -- voir
`ged/README.md`, `DELETE /documents/<id>`).

**Vérifié réellement** : `gedApi.js` testé avec un `fetch` simulé en
Node (17 cas -- bonnes URLs/méthodes, construction correcte du
`FormData` pour les envois de fichiers, préservation du message
d'erreur réel). Structure JSX de `TicketDocuments.jsx` et des 4 vues
modifiées vérifiée par un contrôle d'équilibre accolades/parenthèses/
balises.

**Non vérifié dans cet environnement** : compilation Vite réelle
(`npm install` bloqué ici, réseau restreint) ni rendu visuel dans un
vrai navigateur -- et, en amont, `ged-api`/Mayan EDMS eux-mêmes
restent non vérifiés contre une vraie instance (voir
`ged/README.md`) : ce sera donc aussi le premier test de bout en
bout de toute la chaîne, pas seulement de cette intégration.

## Lien direct vers un ticket depuis un document (livraison #170)

Demandé explicitement : depuis les "Liaisons" d'un document dans
`GedView.jsx` (hub), un lien `ticket#N` ouvre désormais la fiche
technicien de ce ticket directement (`?ticket=<id>` dans l'URL du
portail, lu UNE SEULE FOIS au montage de `App.jsx`).

**"En rôle technicien si possible, sinon lecture seule"** -- si la
personne qui clique n'a PAS accès technicien, repli sur sa PROPRE
vue (demandeur -- montre alors sa PROPRE liste de tickets, jamais
une fiche à laquelle elle n'a pas droit) accompagné d'un bandeau
explicite ("le lien pointait vers le ticket #N, mais vous n'avez
pas accès..."). Répond directement à la remarque complémentaire de
la personne ("un demandeur doit voir sa liste de tickets") : c'est
exactement le comportement de repli, pas une lecture seule séparée
à construire -- la vue demandeur existante EST déjà ce mode "sans
droits techniciens".

Le lien FORCE le rôle technicien (prioritaire sur un choix manuel de
rôle éventuel) quand accessible -- `TechnicienView.jsx` accepte un
nouveau prop `initialTicketId`, utilisé pour initialiser `selectedId`
: son `loadDetail` fait un fetch DIRECT par id (jamais filtré par la
file affichée), le ticket s'ouvre donc même s'il n'apparaît pas dans
les filtres par défaut (fermé, assigné à un autre technicien...).

**Vérifié réellement** : logique d'extraction du paramètre d'URL et
de calcul du rôle actif extraite et testée en isolation via Node (10
cas) -- y compris la protection basique contre une valeur non
numérique, et la confirmation que le comportement SANS lien reste
totalement inchangé. Structure JSX de `App.jsx` (portail),
`TechnicienView.jsx` et `GedView.jsx` (hub) vérifiée par un contrôle
d'équilibre accolades/parenthèses/balises.

**Non vérifié dans cet environnement** : compilation Vite réelle ni
rendu visuel dans un vrai navigateur (mêmes limites que le reste de
ce projet).

## Trois enrichissements du calendrier (livraison #282)

Trois demandes explicites, en plein test réel de déploiement ("note
backlog" puis "lance-toi") :

**Retour visuel sur "Importer"** -- le bouton avait déjà un état de
chargement (texte "Import…", désactivé), mais visiblement trop
discret pour être remarqué. Renforcé : encart de résultat nettement
plus visible (fond coloré vert/rouge selon succès/erreur, au lieu
d'un simple texte discret sous le bouton), champ désactivé pendant
l'import, curseur "wait".

**Filtre par motif à joker** (`*SAV*DEV*`, interrupteur sensibilité
à la casse) -- appliqué CÔTÉ HUB sur les événements déjà chargés,
jamais un nouveau paramètre d'API : le volume typique d'un agenda
reste largement en dessous de ce qui justifierait un filtrage
serveur, et un filtrage local donne un retour instantané pendant la
frappe. Conversion motif→regex testée en isolation (échappement de
tous les caractères spéciaux SAUF `*`, ancrage sur la chaîne entière,
sensibilité à la casse correcte dans les deux sens).

**Vue "Tickets par échéance"** à droite de la liste d'événements --
choix par défaut faits SANS cadrage complet préalable (la personne a
dit "lance-toi"), à ajuster après relecture :
- champ de date : `deadline_ts` -- seul champ "échéance" déjà présent
  sur `tickets`, même notion que l'escalade d'urgence déjà existante
  (`apply_deadline_escalations`, `WHERE deadline_ts IS NOT NULL AND
  ts_closed IS NULL`) -- jamais inventé, réutilise une convention
  déjà établie ailleurs dans `tickets/api/app.py`.
- périmètre : tickets ouverts (déjà le cas de la liste chargée via
  `/queue`) AVEC échéance définie -- ceux sans échéance sont exclus
  silencieusement de CETTE vue seulement, jamais de la file de
  tickets elle-même.
- vue LISTE triée par échéance croissante, pas une grille -- même
  raisonnement de vérifiabilité que la liste d'événements à gauche
  (aucun navigateur disponible pour vérifier visuellement une grille
  complexe dans cet environnement).
- **Aucune donnée supplémentaire chargée** -- `/queue` renvoyait déjà
  `deadline_ts` (`SELECT t.*`, toutes les colonnes), et cette liste
  était déjà chargée par ailleurs (menu d'affectation) -- simple
  filtrage/tri côté hub des tickets déjà en mémoire.

**Explicitement PAS fait** : aucun lien visuel vers l'événement
calendrier qui a potentiellement créé un ticket affiché ici (la
traçabilité existe déjà côté backend via `ticket_time_entries`,
jamais exposée comme telle dans cette vue) -- hors périmètre de
cette première version.

**Vérifié réellement** : logique de filtrage par motif et de
tri/filtrage des tickets par échéance testées en isolation (motif
avec caractères spéciaux, sensibilité à la casse dans les deux sens,
tickets sans échéance correctement exclus, tri croissant confirmé).
Structure JSX revérifiée après la disposition à deux colonnes.

## Cinq points d'ergonomie ENT/Calendrier (livraison #284)

Demandé explicitement, en plein test réel de déploiement : badge
mot-clé au survol, retour en arrière sur création de ticket, File
d'attente fidèle à la vraie tuile Tickets, statut automatique selon
le moment de l'événement source, changements de statut journalisés
avec validation groupée.

**Nouvelle table permanente `ticket_status_changes`** -- DISTINCTE de
`ticket_status_log` déjà existante (portée différente : 3
`event_type` fixes pour des métriques précises, jamais détournée ici
pour un usage différent). Trace CHAQUE changement (ancien statut →
nouveau, motif, qui/quand), `validated_at` NULL tant qu'il n'est pas
passé par la validation groupée -- jamais supprimée après validation,
seulement marquée comme validée (permanent, demandé explicitement).

**Statuts "Clos"/"En cours"/"Planifié"** créés automatiquement au
démarrage s'ils n'existent pas déjà (vérifié par libellé exact,
jamais de doublon). `determine_calendar_statut_label()` -- fonction
PURE (jamais consciente de QUAND elle est appelée), compare un
instant de référence à la fenêtre [début, fin] de l'événement
source : passé → Clos, dans la fenêtre → En cours, futur → Planifié.
Repli sur `start_ts` si `end_ts` absent, même motif déjà établi
ailleurs (`/calendar/assign`, `/calendar/create_ticket`).

**Deux moments d'application** :
- À la CRÉATION (`/calendar/create_ticket`) -- statut initial posé
  directement, journalisé mais déjà marqué validé (couvert par la
  validation de la création du ticket elle-même, #273 -- jamais une
  double validation pour le même geste).
- À la CONSULTATION (`POST /tickets/<id>/recalculate_status`,
  nouvelle route) -- appelée EXPLICITEMENT par l'appelant (jamais un
  déclenchement magique en arrière-plan), un changement RÉEL entre
  dans la file d'attente de validation groupée, jamais appliqué
  directement.

**Suppression réelle** (`DELETE /tickets/<id>`) pour le "retour en
arrière" sur une création -- STRICTEMENT limitée aux tickets encore
`pending_validation=1`, refusée sur un ticket déjà validé (même
prudence que partout ailleurs dans ce projet contre les vrais DELETE
-- l'exception ici est délibérée et étroite : annuler un geste
jamais confirmé n'est pas supprimer une donnée réelle).

**Validation groupée** (`GET /status-changes/pending`,
`POST /status-changes/validate_all`) -- applique TOUS les
changements en attente à la fois, jamais un écran par changement
(demandé explicitement). Interface : nouvelle section en tête de
l'écran Validation, avec lien vers la tuile Tickets (portail, vue
technicien) -- réutilise le contrôle d'accès PAR RÔLE déjà existant
côté portail (`TechnicienView.jsx`), rien de nouveau à coder pour
ça : le portail affiche déjà la bonne vue selon le rôle Keycloak de
la personne connectée.

**File d'attente** -- remplace "Tickets par échéance" (#282), reprend
fidèlement les colonnes de `tickets/portal/src/views/TechnicienView.jsx`
(`#`, Sujet, Demandeur, Type, Niveau, Statut, Attente) en réutilisant
les données déjà chargées via `/queue` (déjà toutes les colonnes
nécessaires jointes côté serveur, aucun nouvel appel réseau).
`formatWaitDuration` dupliqué depuis `tickets/portal/src/lib.js:fmtDuration`
-- deux frontends séparés, même motif d'autonomie déjà établi côté
backend.

**Mot-clé au survol** -- `matched_keywords` exposé côté API
(`/calendar/events`). ⚠️ Un SEUL mot-clé déclencheur configuré
aujourd'hui (`trigger_keyword`) -- jamais plusieurs mots distincts
en pratique tant que ce mécanisme reste mono-mot-clé.

**Vrai bug trouvé et corrigé en cours de route** : `setError` utilisé
dans `CalendarView.jsx` sans jamais avoir été déclaré -- aurait
provoqué une erreur d'exécution au premier clic sur "Annuler" pour
un ticket déjà validé ailleurs. Trouvé en relisant le code avant de
tester, jamais supposé correct sans vérifier.

**Vérifié réellement** : 36 assertions sur la chaîne statuts/
suppression/recalcul/validation groupée (dont un scénario simulant
le temps qui passe en modifiant directement l'événement source, pour
confirmer que le ticket reste inchangé tant que la validation
groupée n'a pas eu lieu, puis que l'historique complet -- création
ET recalcul -- reste intact après validation). Non-régression
complète de `tickets-api` reconfirmée. Structure JSX des trois vues
modifiées revérifiée.

## Branchement rights-api -- GROS CHANTIER en plusieurs passes (item 38 du backlog)

Ce module compte 85 routes -- très au-dessus de tout autre service
du projet (10 pour imap-client, le suivant plus large). Traité en
PLUSIEURS PASSES distinctes, jamais d'un coup, chaque passe testée
et documentée séparément dans ce README, jamais un branchement en
bloc sans examen route par route.

### Passe 1 (livraison #324) -- cluster console DB/SQL

De loin le cluster le plus dangereux du module, comparable ou
supérieur à `dba-api /sql` (déjà signalé "particulièrement sensible"
dans ce projet) :

- **`POST /db/sql/execute`** -- exécution SQL arbitraire, y compris
  DROP/DELETE/UPDATE. Sauvegarde automatique avant toute requête
  non-SELECT (protection déjà en place), mais reste une porte
  ouverte totale sur la base sans garde supplémentaire.
- **`PUT /db/tables/<table>/rows/<row_id>`** -- édition générique de
  n'importe quelle ligne éditable de n'importe quelle table,
  contourne TOUTE validation métier des routes typées normales
  (`/tickets`, `/users`...).
- **`POST /backups/<filename>/restore`** -- DESTRUCTIF, vide la base
  actuelle puis rejoue le dump choisi.
- **`POST /backups`** -- moins critique (crée juste une sauvegarde),
  gardé par cohérence pour éviter un abus/spam de déclenchements
  manuels.

JAMAIS gardé : `POST /db/sql/check` -- confirmé PUREMENT lecture
dans son propre commentaire (`EXPLAIN`, rollback systématique,
"vérifié empiriquement"), ni aucune route GET du cluster (`/db/tables`,
`/db/tables/<t>/columns`, `/db/relationships`, `/db/tables/<t>/rows`).

OPT-IN via `TICKETS_RIGHTS_API_URL`, vide par défaut, comportement
inchangé tant qu'elle n'est pas configurée.

**Vérifié réellement** : comportement opt-in par défaut confirmé,
FAIL CLOSED si `rights-api` injoignable, 403 confirmé sur les 4
routes gardées avec un groupe non autorisé, `/db/sql/check` et les
routes GET du cluster confirmées TOUJOURS libres. Non-régression
complète reconfirmée. Un premier jeu de tests contenait une erreur
d'URL (`/db/tables/tickets/1` au lieu de
`/db/tables/tickets/rows/1`) -- repérée par l'échec, corrigée avant
de conclure quoi que ce soit.

### Passe 2 (livraison #325) -- CRUD des données de référence

Gestion des 6 tables de référence de l'application : `users`,
`types`, `sites`, `levels`, `statuts`, `deadline_escalation_rules`.

**Trouvaille utile** : les routes PUT et DELETE de ces 6 tables
passent TOUTES par deux fonctions génériques partagées
(`update_reference_row`/`delete_reference_row`, section "Édition/
suppression génériques des tables de référence") -- une seule garde
posée dans chacune couvre les 12 routes PUT/DELETE d'un coup,
vérifiée explicitement contre PLUSIEURS tables différentes (`types`,
`sites`, `statuts` -- y compris la variante spéciale `update_statut`
qui pré-valide son corps avant de le transmettre) pour confirmer que
le motif fonctionne bien pour tous les appelants, pas seulement le
premier testé.

Gardé : `POST /users`, `POST /users/import-keycloak-group`,
`POST /types`, `POST /sites`, `POST /sites/import-text` (multipart),
`POST /levels`, `POST /deadline-escalation-rules`, `POST /statuts`,
plus les 12 routes PUT/DELETE via les deux fonctions communes
ci-dessus -- 20 routes au total pour cette passe.

**Vérifié réellement** : comportement opt-in par défaut confirmé,
FAIL CLOSED si `rights-api` injoignable, 403 confirmé sur les 8
routes POST individuelles ET sur les deux fonctions communes testées
contre 3 tables différentes chacune, lecture confirmée non affectée.
Non-régression complète reconfirmée (création/modification/
suppression d'un type, création/modification d'un statut avec la
variante spéciale).

### Passe 3 (livraison #326) -- tickets eux-mêmes (conclusion : rien à garder) + règles de filtrage/exclusion/mots-clés

**Conclusion importante sur le cœur ticket** : après examen complet
(création, édition, suppression, validation, ajout de temps, messages),
**rien n'a été gardé** dans ce sous-groupe -- décision délibérée,
pas un oubli :

- `POST /tickets` (création), `PUT /tickets/<id>` (décrite dans son
  propre commentaire comme "édition libre"), `POST /tickets/<id>/
  messages`, `POST /tickets/<id>/time_entries` -- toutes des actions
  de travail NORMALES, ouvertes à tous les rôles (`demandeur`,
  `technicien`...) par conception. Gater ces routes avec le droit
  `manage` (réservé à `admin_hub`) aurait cassé le fonctionnement
  normal du système de tickets pour tout le personnel non-admin.
- `DELETE /tickets/<id>` (`delete_pending_ticket`) -- SCOPÉE
  explicitement aux seuls tickets encore `pending_validation=1`
  (jamais un ticket confirmé/réel, l'appel est explicitement rejeté
  sinon) -- risque déjà borné par le code lui-même.
- Cluster de validation calendrier (`/tickets/<id>/validate`,
  `/tickets/<id>/recalculate_status`, `/status-changes/validate_all`)
  -- vérifié qu'AUCUNE restriction de rôle n'existe côté frontend
  (`hub/src/ValidationView.jsx`/`EntView.jsx`, accessible sans garde
  particulière) -- cohérent avec un usage NORMAL par le personnel
  faisant le tri des tickets auto-créés depuis le calendrier, pas
  une fonction réservée aux admins. Laissé délibérément ouvert par
  cohérence avec le reste du cluster de révision, plutôt que de
  gater arbitrairement une seule des quatre actions étroitement
  liées.

**En revanche**, les 3 clusters de RÈGLES DE CONFIGURATION affectant
le traitement AUTOMATIQUE pour tout le monde ont été gardés :

- `POST/DELETE /filter_rules` -- règles de filtrage calendrier
  (déclenchement automatique de création de ticket)
- `POST/DELETE /exclusion_rules` -- véto sur ce déclenchement
- `POST/DELETE /priority_keywords` -- signal de tri urgence partagé

Une règle trafiquée pourrait silencieusement supprimer/créer des
tickets à tort pour tout le monde, ou fausser le tri urgence de la
file d'attente -- même raisonnement que `classifier-api` (#315) et
`nebula-api`/`geo-import-api` (#314/#318) pour de la configuration
partagée affectant un traitement automatisé.

**Vérifié réellement** : comportement opt-in par défaut confirmé,
FAIL CLOSED si `rights-api` injoignable, 403 confirmé sur les 6
routes gardées avec un groupe non autorisé, ET confirmation EXPLICITE
que `create_ticket`/`update_ticket`/messages/temps restent TOUJOURS
libres même avec `rights-api` actif et refusant (pas juste "non
testé", vérifié positivement). Non-régression complète reconfirmée
-- une première erreur de test (payload incomplet sur
`create_filter_rule`, `pattern` manquant) repérée et corrigée avant
de conclure.

### Passe 4 (livraison #327) -- import calendrier, OAuth Google

Gardé les 3 routes qui font ENTRER de nouvelles données dans le
pipeline calendrier partagé : `POST /calendar/import` (upload .ics),
`POST /calendar/import_google_api` (depuis le compte Google déjà
connecté), `POST /calendar/import_url` (depuis une URL secrète iCal).
Même raisonnement que pour les règles de filtrage/exclusion (passe
3) : même si CES règles sont déjà gardées en aval, un import massif
de faux événements pourrait quand même exploiter des règles
légitimes pour générer des tickets parasites -- l'entrée du pipeline
mérite sa propre protection, pas seulement sa sortie.

**Particularité technique** : `POST /calendar/import` accepte SOIT
un fichier multipart, SOIT le contenu ICS BRUT directement en corps
de requête (`request.get_data(as_text=True)`) -- ni l'un ni l'autre
ne garantit un canal standard (JSON ou formulaire) pour transmettre
`groups`. Résolu en lisant `groups` depuis les PARAMÈTRES DE
REQUÊTE (`?groups=...`) pour cette route spécifique -- seule
exception à la convention JSON/multipart établie jusqu'ici.

**Délibérément PAS gardé** dans ce même cluster : `POST
/calendar/assign` (affectation événement<->ticket, même famille que
`/tickets/<id>/time_entries` déjà laissée libre en passe 3 -- action
de travail normale, pas admin) ; `POST /calendar/suggest_name`
(confirmé lecture pure -- une simple heuristique de suggestion,
aucune écriture) ; `POST /calendar/create_ticket` (déjà dans la
famille du cœur ticket, self-service).

**Limite CONNUE et assumée, à reprendre séparément** : les routes de
connexion OAuth elles-mêmes (`GET /oauth/google/start`, `GET
/oauth/google/callback`) sont des REDIRECTIONS navigateur, jamais un
appel API avec un corps -- le motif de garde établi (JSON/formulaire/
query params) ne s'applique pas proprement à un flux de redirection.
Or CONNECTER un compte Google différent est arguablement PLUS
consequential que déclencher un import depuis un compte déjà
connecté (ça détermine la SOURCE pour tout le monde, pas juste un
import ponctuel) -- pas construit ici faute d'une approche fiable
pour transmettre `groups` dans un flux de redirection, à reprendre
séparément plutôt que bâclé.

OPT-IN via `TICKETS_RIGHTS_API_URL` (réutilisée, pas de nouvelle
clé), comportement inchangé tant qu'elle n'est pas configurée.

**Vérifié réellement** : comportement opt-in par défaut confirmé,
FAIL CLOSED si `rights-api` injoignable, 403 confirmé sur les 3
routes gardées (y compris le cas particulier du corps brut ICS avec
`groups` en paramètres de requête), `/calendar/assign`/
`/calendar/suggest_name`/OAuth status confirmés TOUJOURS libres.
Non-régression complète reconfirmée.

### Passe 5 (livraison #328) -- import global de base + réglages

Gardé deux routes de sévérité élevée :

- **`POST /import`** -- même sévérité que le cluster console DB/SQL
  de la passe 1. `mode=replace` VIDE ENTIÈREMENT les tables
  concernées avant réinsertion (destructeur). Même `mode=merge`
  (défaut) permet d'injecter/écraser des lignes arbitraires dans
  N'IMPORTE QUELLE table via JSON brut, contournant toute validation
  métier des routes typées normales -- trouvé en examinant cette
  route en profondeur, pas juste par son verbe HTTP.
- **`POST /settings`** -- alimente `matching_config` (dont
  `trigger_keyword`), qui pilote le moteur de détection automatique
  calendrier->ticket -- même famille que filter_rules/exclusion_rules/
  priority_keywords déjà gardées en passe 3.

**Deux vrais bugs trouvés et corrigés EN COURS DE ROUTE, avant de
tester quoi que ce soit** (pas après un échec de test -- repérés à
la relecture du code existant) : les deux routes traitent TOUT le
corps JSON reçu comme des données métier SANS FILTRE -- `groups`
(ajouté pour la vérification des droits) aurait été soit inséré
comme une clé de configuration bidon dans `matching_config`
(`update_settings`, itère sur `body.items()` sans filtre), soit
confondu avec un nom de table inconnu (`import_database`, calcule
`unknown_tables = set(body.keys()) - set(TABLE_ORDER)`). Corrigé en
excluant explicitement `"groups"` du corps AVANT qu'il touche la
logique métier dans les deux cas -- vérifié positivement par test
que `groups` n'apparaît JAMAIS dans `matching_config` après un appel
autorisé, et qu'un import avec `groups` dans le corps n'est jamais
rejeté comme "table inconnue".

JAMAIS gardé : `GET /export` -- lecture pure, cohérent avec la
convention établie dans tout ce chantier (aucune route GET gardée
nulle part, y compris `/db/tables/<t>/rows` en passe 1 qui lit
pourtant tout aussi largement).

OPT-IN via `TICKETS_RIGHTS_API_URL` (réutilisée), comportement
inchangé tant qu'elle n'est pas configurée.

**Vérifié réellement** : comportement opt-in par défaut confirmé,
FAIL CLOSED si `rights-api` injoignable, 403 confirmé sur les 2
routes gardées, `GET /export` confirmée toujours libre, ET
confirmation POSITIVE (appel réellement autorisé, pas juste refusé)
que `groups` n'apparaît jamais dans les données réelles après un
import/réglage accepté. Non-régression complète reconfirmée.

### Passe 6 (livraison #329) -- `/raw_tables`, un contournement possible évité

**DÉCOUVERTE CRITIQUE** en examinant la dernière route d'écriture
non encore vue : `PUT /raw_tables/<table_name>/<row_id>` est une
route générique par LISTE BLANCHE (`RAW_EDITABLE_TABLES`) qui
recouvre à la fois :
- des tables déjà protégées PAR LEUR PROPRE ROUTE dans des passes
  précédentes -- `users`/`types`/`levels`/`statuts` (passe 2, via
  `update_reference_row`), `calendar_filter_rules`/`exclusion_rules`/
  `priority_keywords` (passe 3), `matching_config` (passe 5, via
  `/settings`) ;
- des tables délibérément laissées ouvertes -- `tickets`/
  `calendar_events`/`ticket_time_entries` (cœur ticket self-service,
  passe 3).

Sans garde adaptée, cette route AURAIT CONTOURNÉ silencieusement
toute la protection déjà posée : `PUT /raw_tables/users/5` aurait pu
modifier un utilisateur SANS passer par la garde de `PUT /users/5`,
rendant tout le travail des passes 2/3/5 inutile pour quiconque
découvre cette route alternative.

**Corrigé avec une garde CONDITIONNELLE**, jamais en bloc : un
ensemble `PROTECTED_RAW_TABLES` recense les tables déjà gardées
ailleurs -- la garde `rights-api` ne s'applique QUE si `table_name`
y figure. Reste cohérente avec CHAQUE décision déjà prise séparément
plutôt que de re-décider indépendamment ici.

OPT-IN via `TICKETS_RIGHTS_API_URL` (réutilisée), comportement
inchangé tant qu'elle n'est pas configurée.

**Vérifié réellement** : comportement opt-in par défaut confirmé,
FAIL CLOSED si `rights-api` injoignable -- MAIS uniquement pour les
tables protégées (vérifié explicitement dans les deux sens : une
table protégée refuse même pour `admin_hub` si `rights-api` est
injoignable, ET une table NON protégée reste TOUJOURS accessible
même dans ce même cas). Non-régression complète reconfirmée (table
inconnue toujours 400, édition d'une table non protégée toujours
fonctionnelle sans configuration).

### Passe 7 (livraison #330) -- OAuth Google résolue + balayage systématique des routes GET

**Limite de la passe 4 (#327) enfin résolue** : `GET
/oauth/google/start` est une redirection navigateur (aucun corps de
requête possible), mais accepte des paramètres de requête -- même
motif que `/calendar/import` en passe 4. Gardée avec `groups` lu
depuis `?groups=...`. Connecter un compte Google différent redéfinit
la SOURCE calendrier pour tout le monde -- arguablement plus
consequential que les imports déjà gardés.

Protéger `/start` protège INDIRECTEMENT `/oauth/google/callback`
aussi, sans avoir besoin de le garder directement : son contrôle
CSRF (`state`) exige qu'un `/start` AUTORISÉ ait déjà généré ce
`state` -- un appel direct au callback échoue de toute façon sans
`state` valide, avec ou sans `rights-api`. Vérifié explicitement par
test : un callback avec un `state` invalide échoue (400) même sans
jamais toucher à la garde `rights-api`.

**Balayage systématique des 37 routes GET restantes** -- recherche
automatisée de mots-clés d'écriture SQL (`INSERT`/`UPDATE`/`DELETE`)
dans le corps de CHAQUE fonction, pas une relecture au jugé. Deux
résultats :
- `/oauth/google/callback` -- effet de bord RÉEL confirmé (stocke un
  jeton), déjà traité ci-dessus via `/start`.
- `/stats/reopenings` -- FAUX POSITIF, le mot "UPDATE" provenait
  d'une mention de `update_ticket()` dans le commentaire de la
  fonction, pas d'une vraie requête SQL -- vérifié que la requête
  réelle est un `SELECT` pur avant de conclure.

**Aucune autre route GET du module n'a d'effet de bord caché** --
confirmé par ce balayage, pas juste supposé par convention.

OPT-IN via `TICKETS_RIGHTS_API_URL` (réutilisée), comportement
inchangé tant qu'elle n'est pas configurée.

**Vérifié réellement** : comportement opt-in par défaut confirmé
(redirection normale sans configuration), FAIL CLOSED si
`rights-api` injoignable, 403 confirmé sur `/oauth/google/start`
avec un groupe non autorisé, `/oauth/google/status` confirmée
toujours libre, dépendance du callback vis-à-vis d'un `start`
autorisé confirmée par test. Non-régression complète reconfirmée.

### Passe 8 (livraison #331) -- vérification finale et clôture du chantier

Passage final sur les 34 routes GET restantes (hors `/health`/`/logs`,
triviales). Échantillonnage ciblé sur les routes au nom le moins
explicite (`/terms/synthesis`, `/portal/profile`) pour confirmer
leur nature réelle avant de conclure -- toutes deux confirmées comme
des vues d'agrégation/consultation simples, sans surprise. Combiné
au balayage systématique déjà fait en passe 7 (recherche automatisée
de mots-clés SQL d'écriture sur les 37 routes GET, aucun résultat en
dehors du callback OAuth déjà traité), et à la structure homogène du
reste (listes simples via `simple_list_endpoint`, lectures uniques
par id, vues de statistiques/agrégation) -- **aucune route GET du
module ne justifie une garde `rights-api`**, cohérent avec la
convention appliquée sans exception dans tout ce chantier (aucune
lecture gardée nulle part, dans aucun des 20 services traités).

**Bilan complet du chantier `tickets-api`** (8 passes, #324-331) :

- **Cluster console DB/SQL** (passe 1) -- le plus dangereux du
  module, exécution SQL arbitraire, restauration destructive,
  édition brute de table.
- **CRUD des 6 tables de référence** (passe 2) -- 20 routes dont 12
  via deux fonctions génériques partagées.
- **Cœur ticket** (passe 3) -- conclusion délibérée de NE RIEN
  garder (self-service par conception, vérifié plutôt que supposé) ;
  gardé en échange les 3 clusters de règles de configuration
  partagée.
- **Import calendrier** (passe 4) -- 3 routes, dont un cas
  particulier de corps brut sans JSON/formulaire.
- **Import global de base + réglages** (passe 5) -- même sévérité
  que le cluster DB/SQL, DEUX vrais bugs de fuite de `groups` dans
  les données trouvés et corrigés avant tout test.
- **`/raw_tables`** (passe 6) -- DÉCOUVERTE CRITIQUE d'un
  contournement possible de toute la protection posée dans les
  passes précédentes, corrigé avec une garde conditionnelle par
  table.
- **OAuth Google + balayage systématique** (passe 7) -- dernière
  limite connue résolue, confirmation qu'aucune autre route GET n'a
  d'effet de bord caché.
- **Vérification finale** (passe 8, cette section) -- clôture.

**19 routes gardées au total** sur les 85 du module -- jamais un
branchement en bloc, chaque décision (garder ou laisser ouvert)
appuyée sur un examen réel du code et, quand nécessaire, du
frontend. `tickets-api` complète le chantier plus large de l'item 38
du backlog : **tous les ~32 services du projet sont désormais soit
branchés sur `rights-api`, soit confirmés sans rien à y brancher.**

## Ergonomie ENT/Calendrier -- vérification et complément (livraison #333)

Item 39 du backlog (cinq points explicites) -- relecture systématique
contre le code existant avant de coder quoi que ce soit de nouveau.
Résultat : quatre des cinq points étaient déjà entièrement livrés en
#284, jamais explicitement rapprochés de leur point précis du
backlog jusqu'à cette relecture.

**Points 1, 2, 3, 5 -- déjà livrés, confirmés par relecture directe**
(badge mots-clés, liste de retour en arrière, file d'attente
répliquant la tuile Tickets, validation groupée des changements de
statut). Aucun code modifié pour ces quatre points.

**Point 4 -- backend déjà livré, déclenchement frontend manquant,
complété ici.** `determine_calendar_statut_label`/
`ensure_calendar_statuts` existaient depuis #284 et fonctionnaient
correctement (3 statuts "Clos"/"En cours"/"Planifié" créés
automatiquement au démarrage, jamais de doublon) -- mais
`recalculateTicketStatus` (déjà exportée côté client,
`hub/src/calendarClient.js`) n'était jamais APPELÉE nulle part côté
interface. "Consultation" (le moment déclenchant un recalcul)
n'avait donc jamais de sens en pratique.

Câblé dans `hub/src/CalendarView.jsx:load()` -- retenu comme moment
de "consultation" : chaque ouverture/rafraîchissement de la vue
Calendrier (le point de contact le plus naturel avec les événements
calendrier eux-mêmes, entre les deux options évoquées avec la
personne). Recalcule UNIQUEMENT les tickets déjà liés à un événement
(`assigned_ticket_ids`, déjà chargé avec les événements) -- jamais
un appel au hasard sur tout ticket ouvert. Best-effort : une erreur
individuelle de recalcul n'empêche jamais l'affichage du reste
(`.catch(() => null)` par ticket).

**Vérifié réellement** : chaîne complète testée de bout en bout côté
backend -- un ticket lié (via `/calendar/assign`) à un événement
FUTUR passe en file d'attente de validation avec le statut
"Planifié" proposé (`changed: true`), visible dans
`/status-changes/pending`, puis RÉELLEMENT appliqué à
`tickets.statut_id` après `/status-changes/validate_all` -- jamais
appliqué directement au recalcul lui-même, confirmé par test (4
assertions). Un même ticket dont l'événement devient PASSÉ recalcule
bien vers "Clos". Structure JSX de `CalendarView.jsx` revérifiée
(accolades/parenthèses équilibrées, aucune balise non refermée)
après l'ajout.

## Reste à faire

- Backup/purge des logs et historiques avec lien vers un "SGBD de
  backup" (BLOB chiffré) -- noté par la personne mais PAS COMMENCÉ,
  questions de conception réelles non tranchées (quel moteur, quel
  mécanisme de lien exact) -- voir BACKLOG.md.
- Automates IMAP/ENT (traitement de messages, shell Python, accès
  fichiers/calendrier/SQL) -- PAS COMMENCÉ, chantier sensible en
  sécurité à cadrer sérieusement avant tout code -- voir BACKLOG.md
  item 40.
