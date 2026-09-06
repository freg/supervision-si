# Classification sémantique des identités découvertes (livraison #260)

Backlog item 34, **signalé "à prioriser fort car central"** par la
personne. Observation concrète, sur de vraies données réseau
(Exploration réseau, résolution DNS #250) :

> les mots ci-dessous ont du sens : ups, alice, bob, nms,
> dhcp139 avec l'ip 139 -- tout ça a du sens des personnes/login des
> client ip dynamique (à priori wifi), des services névralgiques...
> une classification automatique serait utile et ensuite une mise en
> relation vers des automates d'analyse spécifique pour évaluer le
> risque, les usages, les ressources consommées

Puis, en cours de conception : "le premier automate peut être une
lib python nltk, un dictionnaire des prénoms, un dictionnaire de
vocabulaire informatique, réseau, télécom... plein de dictionnaires
métiers", "une interface d'import de dictionnaires ?", et "je veux
pouvoir accéder aux stats d'usage des mots, lexèmes et d'orienter".

## Décisions prises en cours de conception

**NLTK vérifié NON installable** dans cet environnement de
développement (`pip install nltk` échoue, aucun miroir accessible) --
et même installé, ses corpus linguistiques généralistes (mots
anglais, noms très majoritairement anglo-saxons) n'auraient de toute
façon PAS couvert le vocabulaire réseau/télécom/informatique demandé
("plein de dictionnaires métiers") -- rien de comparable n'existe en
bibliothèque standard. `gender_guesser`/`names_dataset`/`faker`
vérifiés également absents.

**Architecture retenue : dictionnaires IMPORTABLES**, jamais des
listes codées en dur -- décision prise suite à la question explicite
de la personne. Chaque terme est classé sous une CATÉGORIE (libre --
`identite_personnelle`, `equipement_infrastructure`, et toute autre
catégorie que la personne voudra créer via un nouvel import), avec sa
propre SOURCE (le nom du dictionnaire importé, pour pouvoir retirer
un import entier d'un coup en cas d'erreur).

## Comment ça classe

1. **Motif STRUCTUREL `dhcpNNN`** -- reconnu directement, jamais un
   dictionnaire (ce n'est un "mot" pour personne). Testé PAR TOKEN
   (après découpage sur `.`/`-`/`_`) -- un bug réel a été trouvé et
   corrigé en testant contre les vraies données de la personne :
   le motif était d'abord ancré sur la CHAÎNE ENTIÈRE
   (`^dhcp...$`), qui ne matchait donc jamais un vrai nom d'hôte avec
   son suffixe de domaine ("dhcp136.**intranet**"). Bonus de
   confiance si le numéro correspond à la fin de l'adresse IP fournie
   (comparaison NUMÉRIQUE, gère les zéros de tête).
2. **Recherche en dictionnaire, token par token** -- le nom d'hôte
   est découpé sur `.`/`-`/`_`, chaque token comparé EXACTEMENT
   contre les termes importés (jamais une recherche de sous-chaîne,
   qui créerait des faux-positifs -- ex. "ups" ne doit jamais matcher
   à l'intérieur d'un autre mot). Tokens les plus longs testés en
   premier -- une correspondance plus spécifique l'emporte.

## Import de dictionnaires

`POST /dictionaries/import` (multipart) -- un terme par ligne,
lignes vides et `#commentaires` ignorés, jamais une exception sur une
ligne mal formée. Peut être appelé PLUSIEURS FOIS pour enrichir
progressivement (les doublons dans une même catégorie sont ignorés
proprement, `match_count` existant JAMAIS réinitialisé).

## Stats d'usage ("quels mots/lexèmes servent vraiment")

`GET /stats` -- par catégorie : nombre de termes, total des
correspondances, nombre de termes JAMAIS utilisés (signal direct de
ce qui, dans un dictionnaire importé, ne sert à rien sur les données
réelles). Chaque classification réussie incrémente `match_count` sur
le terme utilisé.

## Orientation manuelle ("je veux... orienter")

`POST /classify/confirm` -- confirme ou corrige la classification
d'un texte précis, journalisé. Avec `add_to_dictionary: true`,
ajoute TOUS les tokens SIGNIFICATIFS du texte (hors suffixes
génériques comme "intranet"/"local", voir `_GENERIC_TOKENS`) au
dictionnaire -- un nom composé ("marc-dupont.intranet") enrichit
ainsi le dictionnaire avec CHAQUE partie utile ("marc" ET "dupont"),
pas seulement la première, pour que les prochaines classifications
reconnaissent l'une ou l'autre indépendamment.

## Vérifié réellement

Testé en profondeur avec le VRAI jeu de données partagé par la
personne (20 lignes de sa liste d'appareils découverts, copiées
directement) : alice/bob/carol/dave correctement
classés comme identités personnelles, dhcp136/dhcp139/dhcp144
correctement classés comme clients DHCP dynamiques (bug de motif
trouvé et corrigé au passage), nms/ups-groupe-x/nas-siege-1/serveur
correctement classés comme équipement d'infrastructure. Import testé
avec un vrai upload multipart. Dédoublonnage confirmé (import
répété, match_count jamais écrasé). Stats d'usage vérifiées exactes.
Orientation manuelle testée -- confirme qu'un nom composé enrichit le
dictionnaire avec CHAQUE partie, pas seulement la première (bug de
conception trouvé et corrigé en cours de test). Aperçu (`preview=true`)
confirmé ne JAMAIS modifier les statistiques. Suppression d'un
dictionnaire entier testée. Dockerfile vérifié avec le script de
contrôle systématique développé en #252 -- aucun fichier manquant.
Structure JSX complète revérifiée.

## Reste à faire

- **Aucun dictionnaire fourni par défaut** -- volontairement, la
  personne doit importer les siens (prénoms réels de son
  organisation, vocabulaire métier réel) plutôt qu'hériter d'une
  liste générique qui ne correspondrait pas à son contexte.
- ~~Intégration avec Exploration réseau~~ **LIVRÉE EN #261** -- badge
  de classification affiché à côté de chaque nom d'hôte découvert,
  intégration côté hub (pas de couplage backend-à-backend). Voir
  `network-agent/README.md`.
- **"Automates d'analyse spécifique" selon la classification**
  (risque/usage/ressources) -- volet PAS COMMENCÉ, nature exacte à
  cadrer avec la personne (voir item 34 du backlog).
- Item 33 (collecte transversale d'identités à travers plusieurs
  modules) reste également à cadrer -- la classification pourrait
  s'appliquer aux identités collectées par ce futur mécanisme, pas
  seulement aux noms d'hôte de network-agent.

## Branchement rights-api (livraison #315)

Suite de l'item 38 du backlog. Service CENTRAL ("à prioriser fort")
-- son dictionnaire est utilisé par d'autres modules (ex. Exploration
réseau). Tamponner/vider le dictionnaire partagé corromprait
silencieusement les classifications de TOUS les consommateurs, pas
seulement de celui qui a fait le changement.

Gardé sur `import_dictionary`/`delete_term`/`delete_source`
(mutation directe du dictionnaire) et `confirm` (peut AUSSI ajouter
au dictionnaire via `add_to_dictionary` -- gardé en BLOC plutôt que
construire une garde conditionnelle sur ce seul paramètre, même
prudence que pour snmp-api #313). Jamais sur `classify`/
`classify/batch` -- interrogation du dictionnaire, jamais une
mutation.

OPT-IN via `CLASSIFIER_RIGHTS_API_URL`, vide par défaut,
comportement inchangé tant qu'elle n'est pas configurée.

**Vérifié réellement** : comportement opt-in par défaut confirmé,
FAIL CLOSED si `rights-api` injoignable, 403 confirmé sur les 4
routes gardées (multipart et JSON) avec un groupe non autorisé,
`classify`/`classify/batch` confirmés TOUJOURS libres. Non-régression
complète reconfirmée.
