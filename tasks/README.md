# Tâches (Kanban) + tuile ENT (livraisons #271-272)

Demandé explicitement, en revenant sur un sujet abordé puis écarté
(la connexion à un agenda Google) : "une fois validée intègre un
calendrier/agenda interne au hub et branche le sur la gestion de
tickets et sur une gestion de tâche indépendante des tickets avec
une vue kanban. la tuile ENT environnement numérique de travail".

## Chemin parcouru avant de coder

1. **Question sur l'accès aux sources Thunderbird** -- clarifié
   honnêtement : pas d'accès permanent au dépôt, recherche web
   utilisée pour confirmer que Thunderbird embarque bien des
   identifiants OAuth propres à SON identité (correctif Mozilla
   officiel trouvé, "Use Thunderbird OAuth credentials for new
   Google calendars"). Réutiliser ces identifiants pour le hub aurait
   violé les conditions d'utilisation de l'API Google (l'écran de
   consentement afficherait "Thunderbird" pour un usage réel
   différent) -- écarté pour cette raison, jamais une question de
   faisabilité technique.
2. **Deux pistes légitimes présentées** -- URL secrète iCal (lecture
   seule, aucune clé API) vs vraie appli OAuth du hub (lecture/
   écriture, configuration Google Cloud). **La personne a choisi
   l'URL secrète iCal.**
3. **Vérification de `icalendar` (bibliothèque Python)** -- non
   installable dans cet environnement (réseau restreint, même
   contrainte que partout ailleurs dans ce projet).
4. **Découverte en cours de route** : `tickets/api/` contenait DÉJÀ
   un parseur ICS maison (`ics_parser.py`), les routes
   `/calendar/import_url` (l'approche URL secrète, déjà là),
   `/calendar/import` (upload direct, y compris depuis un export
   Thunderbird), un moteur de suggestion événement→ticket, et
   l'affectation elle-même (`/calendar/assign`) -- travail antérieur
   non couvert par le résumé de compaction reçu en début de session.
   Vérifié AVEC PRUDENCE que ce n'était pas du contenu injecté
   (inspection du style/des conventions, confirmation que ces
   modules sont réellement importés par `app.py`) avant de s'y fier.
   Chaîne complète testée de bout en bout AVANT de construire quoi
   que ce soit par-dessus -- voir `tickets/README.md`, section "Vue
   calendrier livrée côté hub".

## Ce qui a été construit

### `tasks/` -- gestion de tâches INDÉPENDANTE des tickets (#271)

Nouveau module, aucune table partagée avec `tickets` -- une tâche
n'est pas un ticket de support. Trois colonnes fixes pour cette
première tranche (`todo`/`doing`/`done`), `position` gérant l'ordre
au sein d'une colonne (dense, jamais de trou).

`move_task` (le cœur du Kanban) gère le déplacement au sein d'une
même colonne ET entre colonnes différentes, en renumérotant
proprement les deux colonnes concernées -- testé en profondeur
(déplacement intra-colonne, inter-colonnes, position hors limites
bornée automatiquement, suppression qui comble le trou laissé).

`KanbanView.jsx` (hub) -- déplacement par BOUTONS (← / →) plutôt que
glisser-déposer -- choix délibéré : un glisser-déposer HTML5 fiable
est plus complexe à construire et à vérifier sans navigateur réel
disponible dans cet environnement de développement ; les boutons
donnent le même résultat fonctionnel, de façon prévisible et
testable.

### `CalendarView.jsx` (hub, dans `tickets/README.md`) -- vue agenda (#272)

Réutilise entièrement le backend déjà existant côté `tickets-api`
(voir ci-dessus) -- import par URL secrète, filtre non affectés/
affectés/tous, sélection multiple + affectation à un ticket ouvert.

### `EntView.jsx` -- la tuile "ENT" (#272)

Conteneur à onglets réunissant Calendrier et Tâches -- même motif
d'onglets que le reste du hub. Promue en TUILE D'ACCUEIL (même
mécanisme que GED/#172 et Exploration réseau/#265 -- `onClick`
interne, jamais une URL externe), affichée si `tickets-api` OU
`tasks-api` est configuré.

**Vérifié réellement** : socle `tasks/store.py` testé en profondeur
(13 scénarios, y compris les cas limites du repositionnement
Kanban) -- tout confirmé au premier passage. Routes `tasks-api`
testées de bout en bout (validation, 404 propres, jamais un crash).
Dockerfile vérifié avec le script de contrôle systématique développé
en #252 -- aucun fichier manquant dès la première livraison.
Structure JSX des trois nouvelles vues (`CalendarView`, `KanbanView`,
`EntView`) revérifiée, y compris après correction du doublonnage de
barre de titre (résolu avec une prop `embedded`).

## Reste à faire

- **Vraie grille semaine/jour** pour le calendrier -- reportée
  explicitement, une vue agenda (liste) livrée à la place (voir
  raisonnement dans `tickets/README.md`).
- **"Création de ticket depuis un événement"** en un clic -- pas
  encore fait, seule l'affectation à un ticket EXISTANT est câblée.
- **Colonnes Kanban personnalisables** -- trois colonnes fixes pour
  l'instant (todo/doing/done), jamais présumé qu'un jeu configurable
  était demandé.
- **Glisser-déposer** -- reporté au profit de boutons, pour les
  raisons de vérifiabilité expliquées plus haut ; pourrait être
  ajouté plus tard si souhaité, une fois un retour d'usage réel.
- **Connecteur OAuth2 Google** (alternative à l'URL secrète,
  `google_oauth.py`) -- déjà présent côté backend (travail
  antérieur), mais NON TESTÉ contre un vrai compte Google, et
  volontairement pas la piste choisie pour cette livraison.

## Création automatique de ticket + écran de validation (livraison #273)

Demandé explicitement en réponse au point noté "reste à faire" de la
livraison précédente : "Oui branche la création auto. Ajouté un
écran de validation des tickets automatique".

**Nouvelle colonne `tickets.pending_validation`** (migration douce,
même motif que `ensure_statut_type_column`/`ensure_first_in_progress_column`
déjà existants) -- 0 par défaut (tout ticket créé normalement),
1 UNIQUEMENT pour un ticket créé automatiquement, en attente de
confirmation humaine. Même esprit que `suggestion_engine.py` déjà en
place : "jamais d'exécution automatique silencieuse, la décision
finale reste humaine".

**`POST /calendar/create_ticket`** -- sujet = résumé de l'événement,
description = description de l'événement, demandeur DEVINÉ via
`best_candidate_name` (mécanisme heuristique déjà existant) --
appliqué SEULEMENT sur correspondance EXACTE avec un utilisateur
connu, sinon laissé vide (jamais une correspondance approximative
imposée silencieusement).

**`GET /tickets/pending_validation`** + **`POST /tickets/<id>/validate`**
(avec correction optionnelle du demandeur/type/niveau/statut au
passage) -- l'écran de validation demandé explicitement. Le rejet
réutilise le mécanisme d'archivage DÉJÀ EXISTANT
(`PUT /tickets/<id> {"archived_at": ...}`) -- jamais un vrai DELETE,
même convention que le reste de ce module.

`ValidationView.jsx` (hub) -- troisième onglet de la tuile ENT.
Bouton "+ Créer un ticket" ajouté dans `CalendarView.jsx` pour chaque
événement non affecté.

**Un vrai bug trouvé et corrigé en testant** : la première version
de `/calendar/create_ticket` omettait deux colonnes obligatoires de
`ticket_time_entries` (`created_at`, et le repli `end_ts → start_ts`
pour un événement sans heure de fin) -- repéré immédiatement par le
test, corrigé en reprenant exactement le motif déjà établi côté
`/calendar/assign`.

**Un cas révélateur confirmé par le test** : sur un événement où le
détecteur heuristique a deviné à tort le mot "inconnu" comme nom de
demandeur, AUCUNE fausse affectation n'a eu lieu -- "inconnu" ne
correspondant à aucun login réel, le champ est resté vide,
correctement laissé à un humain de trancher via l'écran de
validation.

**Vérifié réellement** : chaîne complète testée de bout en bout
(création avec demandeur deviné correctement, création sans
demandeur devinable, écran de validation listant exactement les
tickets en attente, validation simple, validation avec correction,
rejet via archivage, tous les cas d'erreur -- événement introuvable,
event_id manquant, validation d'un ticket normal jamais en attente,
validation d'un ticket introuvable). Non-régression complète de
`tickets-api` reconfirmée après les modifications. Structure JSX des
nouvelles vues revérifiée.

## Reste à faire

- ~~Correction du type/niveau/statut à la validation~~ **LIVRÉE EN
  #274** -- les quatre champs (demandeur/type/niveau/statut) sont
  désormais éditables côté écran de validation, un seul objet
  d'état par ticket plutôt que quatre séparés.
- **Notification** quand un nouveau ticket arrive en attente de
  validation -- aucune pour l'instant, consultation manuelle de
  l'onglet Validation.

## Écran de validation : correction complète (livraison #274)

`POST /tickets/<id>/validate` acceptait déjà les quatre champs
(`user_id`/`type_id`/`level_id`/`statut_id`) depuis #273 -- seule
l'interface n'exposait que la correction du demandeur. Corrigé :
`ValidationView.jsx` affiche désormais quatre menus déroulants par
ticket en attente (demandeur, type, niveau, statut), avec un
**objet d'état unique par ticket** (`{user_id, type_id, level_id,
statut_id}`) plutôt que quatre `useState` séparés -- plus simple à
faire évoluer si un futur champ s'ajoute.

**Vérifié réellement** : logique de construction du payload testée
en isolation -- un champ non renseigné n'est JAMAIS transmis
(évite d'écraser une valeur avec `0`/`null` par erreur), le
demandeur deviné automatiquement ET une correction manuelle
d'un autre champ se combinent correctement dans le même envoi, et
choisir explicitement "— aucun —" efface bien un champ deviné
plutôt que de le laisser tel quel silencieusement. Structure JSX
revérifiée.

## Branchement rights-api (livraison #312)

Suite de l'item 38 du backlog. SCOPE VOLONTAIREMENT ÉTROIT : ce
kanban est délibérément COLLABORATIF (aucune notion de propriétaire
dans le schéma -- créer/déplacer/modifier une carte est l'usage
NORMAL de l'outil, pas une élévation de privilège). Gardé
UNIQUEMENT sur `DELETE /tasks/<id>` -- suppression définitive, sans
mécanisme d'archive, la seule action qualitativement différente du
fonctionnement collaboratif attendu. Jamais sur create/update/move,
qui resteraient bloqués pour un usage normal sans fermer aucune
brèche réelle.

OPT-IN via `TASKS_RIGHTS_API_URL`, vide par défaut, comportement
inchangé tant qu'elle n'est pas configurée.

**Vérifié réellement** : comportement opt-in par défaut confirmé,
create/update/move confirmés TOUJOURS libres même avec `rights-api`
actif et refusant, FAIL CLOSED sur `delete_task` si `rights-api`
injoignable, 403 confirmé pour un groupe non autorisé. Non-régression
complète reconfirmée.
