# relations-api

Livraison #335, backlog item 38 point 2 -- "la tuile ENT devient une
super tuile" avec une sous-tuile "relations" (liens événement-
utilisateur-document-message-ticket). Modèle clarifié par la personne
le 2026-09-04 :

- **Relation DIRECTE** = association d'un marqueur commun entre deux
  éléments : une référence identique (chaîne identique dans un champ
  nom, dans un label, adresse IP, proximité géographique, proximité
  sémantique).
- **Relation INDIRECTE** = un attribut associé à un élément direct ou
  à un ensemble ; deux éléments d'un même ensemble sont en relation
  indirecte l'un avec l'autre.

## SERVICE SANS ÉTAT PROPRE

Contrairement à la quasi-totalité des autres modules de ce projet,
`relations-api` ne possède AUCUNE base de données à lui : il
interroge les autres services (`tickets-api`, `ged-api`, `tasks-api`)
à la volée à chaque requête via leur API HTTP déjà publique -- jamais
un accès direct à leur base -- et calcule les relations en mémoire.
Aucun cache, aucune persistance dans cette première passe -- le
volume de données croisées reste modeste (tickets ouverts +
événements calendrier + documents connus + tâches), recalculer à
chaque appel est largement suffisant tant que ça ne devient pas un
problème réel de performance observé en usage.

## Portée cumulée (passes #335-338) -- les QUATRE formes construites

**Relations DIRECTES construites**, les QUATRE formes mentionnées par
la personne : correspondance EXACTE de texte (nom/label/sujet/titre,
normalisé -- minuscules, espaces superflus réduits, comparé pour une
égalité stricte ; seuil de longueur minimale `MIN_MARKER_LENGTH = 3`
pour éviter le bruit d'un libellé générique très court, #335) ;
correspondance par adresse IPv4 identique trouvée dans le texte
combiné libellé+description de deux entités (validation des octets
0-255, #336) ; proximité SÉMANTIQUE, au moins un mot significatif
commun entre les textes de deux entités (technique déjà établie dans
ce projet, jamais un modèle NLP réel, #337) ; proximité GÉOGRAPHIQUE,
distance sous un seuil (2 km) entre les coordonnées connues (via
`pixel-grid-api`) des sites associés à deux entités -- seule forme
qui n'exige pas une correspondance exacte, une vraie "proximité"
(#338).

## Entités couvertes

Quatre types pour cette première passe (voir `entity_fetchers.py`) :
- **ticket** -- tickets OUVERTS uniquement (`tickets-api:/queue`),
  jamais l'historique complet, périmètre volontairement restreint.
- **calendar_event** -- tous les événements connus
  (`tickets-api:/calendar/events`).
- **document** -- tous les documents connus de `ged-api`
  (`ged-api:/documents`, au moins une liaison enregistrée).
- **task** -- toutes les tâches (`tasks-api:/tasks`).

## Limite structurelle de la passe #335, levée en #336

Avec un SEUL critère de relation directe (nom identique) et UN SEUL
marqueur par entité, aucune relation indirecte ne pouvait jamais se
produire -- toutes les entités partageant un même marqueur formaient
une clique totalement connectée en DIRECT entre elles, jamais un
pont vers un cluster de marqueur différent. Vérifié explicitement
par test (`relation_engine.py`) plutôt que simplement affirmé.

**Levée depuis l'ajout de la correspondance par IP** (#336, voir
section suivante) : une entité porte désormais potentiellement DEUX
marqueurs distincts (son nom ET une IP mentionnée dans son texte).
Premier cas de relation INDIRECTE réellement observé, confirmé par
test dans les deux sens.

## Routes

- `GET /relations?entity_type=<type>&entity_id=<id>` -- relations
  directes (avec le marqueur qui les justifie) et indirectes d'UNE
  entité précise. `entity_type` parmi `ticket`/`calendar_event`/
  `document`/`task`.
- `GET /graph` -- vue d'ensemble, TOUTES les relations directes
  trouvées tous types confondus. Peut devenir coûteux si le volume
  grandit beaucoup -- accepté pour cette première passe, à surveiller.
- `GET /health`, `GET /version` -- standard.

## Interface hub

Cinquième onglet de la tuile ENT (`hub/src/EntView.jsx`), à côté de
Calendrier/Tâches/Validation/GED -- voir `hub/README.md` pour le
détail de l'intégration. Interface volontairement minimale pour cette
première passe (`hub/src/RelationsView.jsx`) : un formulaire
type+identifiant, affichage des relations directes/indirectes en
listes simples. Pas de graphe visuel, pas de navigation cliquable
d'une entité à l'autre -- à construire dans une passe ultérieure une
fois le modèle de correspondance plus riche (IP/géo/sémantique).

## Vérifié réellement

`relation_engine.py` (calcul pur, sans réseau) testé en isolation :
normalisation des libellés (casse, espaces), détection d'une
relation directe entre deux entités de TYPES DIFFÉRENTS partageant le
même libellé normalisé, seuil de longueur minimale respecté,
composantes connexes calculées correctement sur un cluster à 3
entités, confirmation explicite de la limite structurelle
(aucune indirecte possible avec un seul marqueur par entité).

`app.py` testé de bout en bout avec les trois services amont simulés
(`unittest.mock`) : `/graph` et `/relations` renvoient les bonnes
relations sur un scénario à 3 entités partageant un libellé
identique (clique complète), aucune relation pour une entité au
libellé différent, 404 sur une entité inconnue, 400 sur un
`entity_type` invalide, 502 si un service amont est injoignable
(`FetchError` propagée correctement). Un premier jeu de données de
test contenait une erreur (libellés pas réellement identiques entre
les trois entités) -- repérée par l'échec de l'assertion, corrigée
avant de conclure.

Structure JSX de `RelationsView.jsx` et `EntView.jsx` revérifiée
(accolades/parenthèses équilibrées, aucune balise non refermée) après
l'intégration.

## Deuxième forme de relation directe : IP (livraison #336)

Deuxième critère de relation DIRECTE construit : une adresse IPv4
IDENTIQUE trouvée dans le texte (libellé + description combinés,
voir `entity_fetchers.py`) de deux entités différentes. Validation
des octets (0-255) pour réduire le bruit d'un faux positif type
numéro de version ("2.5.13.4") -- jamais parfait (une vraie IP à
tous octets <256 ressemble aussi à une version), mais réduit le cas
le plus évident.

**La limite structurelle documentée en #335 est désormais LEVÉE** --
confirmé par test, pas simplement supposé : une entité porte
désormais potentiellement DEUX marqueurs (son nom ET une IP
mentionnée dans son texte). Si cette IP est partagée avec une
troisième entité qui n'a PAS le même nom, cette troisième entité
devient une relation INDIRECTE de la première, via la seconde comme
pont. Premier cas de relation indirecte RÉELLEMENT observé (pas
seulement théorique) -- voir `relation_engine.py`, section testée
explicitement dans les deux sens (A indirecte de C, ET C indirecte
de A).

`compute_direct_relations` combine désormais deux dictionnaires
intermédiaires (marqueurs de nom, marqueurs d'IP) via une fonction
factorisée (`_pairs_by_marker`) -- même logique de regroupement pour
les deux critères, jamais dupliquée.

**Vérifié réellement** : extraction d'IP en isolation (une IP simple,
aucune IP, IP répétée dans le même texte comptée une seule fois,
octet invalide >255 rejeté). Scénario à trois entités A-B-C testé de
bout en bout (A et B partagent un nom, B et C partagent une IP,
A et C n'ont directement RIEN en commun) -- confirmé que A et C
apparaissent bien l'un pour l'autre en INDIRECT, jamais en direct.
Non-régression complète reconfirmée sur les scénarios "nom seul" de
la passe #335, y compris `description: None` (pas seulement absent)
géré sans exception.

## Troisième forme de relation directe : proximité sémantique (livraison #337)

Troisième critère de relation DIRECTE construit : au moins
`MIN_SEMANTIC_SHARED_WORDS` (= 1) mots significatifs COMMUNS entre
les textes de deux entités -- même technique déjà établie dans ce
projet pour une tâche apparentée
(`tickets/api/suggestion_engine.py`, "score de similarité par mots
significatifs partagés"), jamais un vrai modèle NLP (aucun accès
réseau pour en télécharger un pendant le développement, même
contrainte documentée là-bas). `STOPWORDS` et la logique
d'extraction dupliquées À L'IDENTIQUE dans `relation_engine.py`
(service séparé, jamais un import inter-conteneurs pour une si
petite fonction pure) -- si la liste évolue côté `tickets-api`,
penser à répercuter ici. Seuil minimal (1 mot partagé) repris tel
quel de `suggestion_engine.py:analyze_title_matches`, jamais un
chiffre inventé sans précédent dans ce projet.

Contrairement au regroupement O(n) des critères nom/IP (un
dictionnaire intermédiaire `{marqueur: [entités]}`), la comparaison
sémantique nécessite une comparaison PAR PAIRES -- O(n²). Acceptable
tant que le volume reste modeste (voir portée du service en tête de
ce document) -- à surveiller si ça devient un problème réel de
performance en usage.

**Déduplication nom/sémantique** : un nom identique implique presque
toujours un recouvrement de mots significatifs (les mots du nom
lui-même comptent) -- ajouter AUSSI un marqueur sémantique pour la
même paire aurait été une redondance quasi systématique, jamais un
signal supplémentaire réel. Supprimée explicitement pour les paires
déjà justifiées par le nom. PAS la même suppression pour IP+
sémantique : partager une IP n'implique pas forcément un
recouvrement du reste du texte, la combinaison reste un signal
double genuinement informatif -- vérifié par test que les DEUX
marqueurs distincts sont bien conservés dans ce cas.

**Vérifié réellement** : extraction de mots significatifs en
isolation (mots vides exclus, normalisation des accents confirmée
avec des textes réellement équivalents -- un premier test contenait
une erreur, un mot supplémentaire non voulu dans l'un des deux
textes comparés, repérée par l'échec et corrigée avant de conclure).
Scénario purement sémantique (aucun nom ni IP en commun, seulement du
vocabulaire partagé) confirmé de bout en bout. Déduplication
nom/sémantique vérifiée (une seule relation renvoyée, pas de doublon)
ET conservation du double signal IP+sémantique vérifiée sur un cas
distinct (les deux marqueurs bien présents). Non-régression complète
reconfirmée sur tous les scénarios des passes #335-336 (nom seul, IP
seule, indirect via IP).

## Quatrième et dernière forme de relation directe : proximité géographique (livraison #338)

Quatrième critère de relation DIRECTE construit -- SEULE forme parmi
les quatre qui n'exige PAS une correspondance exacte, une vraie
"proximité" : deux entités dont le `site` (pour l'instant, seuls les
TICKETS en ont un via `site_label`, aucun des trois autres types
d'entités n'a de notion de lieu dans ce projet) résout, via une
nouvelle source (`pixel-grid-api:/geolocations`, déjà existant pour
un autre usage -- cartographie des géolocalisations connues par nom),
à des coordonnées distantes de moins de `GEO_PROXIMITY_KM` (= 2 km,
choix raisonnable pour un contexte "même campus/site professionnel
proche", jamais vérifié contre un vrai jeu de données ni discuté
avec la personne -- à ajuster une fois un usage réel observé).
Distance calculée par la formule de Haversine (distance à vol
d'oiseau, suffisante à cette échelle).

**pixel-grid-api est une source OPTIONNELLE**, contrairement aux
trois autres (tickets/ged/tasks-api, ESSENTIELLES -- sans elles rien
à mettre en relation) : injoignable ou sans aucune localisation
cartographiée, la proximité géographique est simplement absente des
résultats, jamais une erreur qui bloquerait les trois autres
critères de fonctionner. Vérifié explicitement par test.

**Les QUATRE formes de relation directe mentionnées par la personne
sont désormais toutes construites.**

**Vérifié réellement** : `haversine_km` en isolation (distance connue
Paris-Lyon plausible, distance d'un point à lui-même nulle, deux
points proches sous le seuil). Scénario à trois tickets testé de
bout en bout (deux sites proches géographiquement mais sans aucun
mot/nom en commun -- liés ; un troisième site distant -- jamais lié),
un premier test contenant un mot partagé accidentel entre les deux
textes de test (créant une relation sémantique EN PLUS de la
géographique, comportement correct mais fausse mon assertion) --
repéré et le texte de test corrigé pour isoler proprement la
vérification. Dégradation gracieuse confirmée par test explicite :
`pixel-grid-api` injoignable -> toujours 200 avec simplement aucune
relation géographique, jamais une 502 qui bloquerait le reste. Non-
régression complète reconfirmée sur tous les scénarios des passes
#335-337.

## Reste à faire

- Relations directes par IP -- limitée pour l'instant à
  `tickets`/`calendar_events`/`documents`/`tasks` (texte déjà
  récupéré). Étendre aux IP connues d'autres modules (`netprobe`/
  `network-agent`/`ipam`) nécessiterait de nouveaux fetchers dédiés,
  pas construit ici.
- Relations directes par proximité géographique -- limitée pour
  l'instant aux TICKETS uniquement (seul type d'entité avec un
  `site` dans ce projet) ; seuil `GEO_PROXIMITY_KM` (2 km) jamais
  vérifié contre un vrai jeu de données ni discuté avec la personne,
  à ajuster une fois un usage réel observé.
- Proximité sémantique -- réglages possibles à affiner une fois un
  vrai usage observé : seuil `MIN_SEMANTIC_SHARED_WORDS` peut-être
  trop permissif (1 seul mot partagé) sur un volume réel de données,
  jamais vérifié contre un vrai jeu de production. Comparaison O(n²)
  à surveiller si le volume d'entités grandit significativement.
- Interface : graphe visuel, navigation cliquable ENTRE deux entités
  déjà affichées comme liées (actuellement, il faut ressaisir
  manuellement le type+identifiant de l'entité liée pour voir SES
  propres relations). Intégration directe depuis les vues Calendrier
  (tickets + événements) ✅ FAITE (#339, `hub/README.md`), GED
  (documents) et Tâches ✅ FAITE (#356, même motif bouton "🔗" que
  Calendrier -- reste le graphe visuel/navigation entre deux entités
  déjà liées, jamais construit).
- Persistance/cache si le volume de données grandit au point de
  rendre le recalcul à la volée trop coûteux -- pas un problème
  observé pour l'instant, à surveiller.
