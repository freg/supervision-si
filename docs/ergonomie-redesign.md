# Redesign des écrans pour les non-initiés — brief d'ergonomie (livraison #540)

Demandé (22 sept. 2026) : « un redesign de l'interface avec pour objectifs
1. lisibilité, 2. simplicité, 3. logique métier / dépendances ; un redesign
des écrans à présenter aux non-initiés dans la prolongation de l'écran
externe de gestion de tickets ; se cultiver sur les notions d'ergonomie et
penser client dans le besoin ou dans la confusion ».

## 1. Ce que dit l'ergonomie (repères retenus)

Les critères de **Bastien & Scapin** (INRIA, 1993), toujours la grille de
référence francophone pour évaluer une interface :

| Critère | Ce qu'il impose ici |
|---|---|
| Guidage (incitation, groupement, feedback, lisibilité) | dire à chaque instant où l'on est, ce qu'on attend de la personne, ce qui s'est passé après son geste |
| Charge de travail (brièveté, densité) | le moins de champs, de choix et de mots possible par écran |
| Contrôle explicite | rien ne part sans un geste explicite ; la personne peut revenir en arrière |
| Adaptabilité | un chemin court pour qui sait, un chemin guidé pour qui ne sait pas |
| Gestion des erreurs | empêcher plutôt que signaler ; un message d'erreur dit quoi faire |
| Homogénéité | mêmes mots, mêmes places, mêmes gestes d'un écran à l'autre |
| Signifiance des codes | pas de couleur seule, pas de sigle, pas d'icône sans mot |
| Compatibilité | le vocabulaire de la personne, pas celui du système |

Les **dix heuristiques de Nielsen** (1994, nngroup.com) recoupent cette
grille ; deux comptent double pour un public en difficulté : *visibilité de
l'état du système* (« que se passe-t-il ? ») et *correspondance avec le
monde réel* (« l'imprimante du 2e » plutôt que « périphérique PRN-02 »).
Steve Krug (*Don't make me think*) résume la simplicité : une page se
comprend sans réfléchir, chaque écran a une action évidente, on supprime
la moitié des mots puis encore la moitié. Don Norman (*The Design of
Everyday Things*) donne la logique des dépendances : rendre visible le
**modèle conceptuel** — ce qui dépend de quoi — pour que la personne
comprenne pourquoi « le courriel ne marche plus » quand « le réseau du
bâtiment est coupé ». La charge cognitive (Sweller) et la loi de Hick
(le temps de décision croît avec le nombre de choix) fixent la règle :
**au plus quatre choix par écran, une seule action principale**.

## 2. La personne dans le besoin ou dans la confusion

Trois situations, et ce qu'elles exigent de l'écran :

- **Quelque chose ne marche plus** (stress, urgence, souvent pas de
  vocabulaire) : commencer par la question de la personne (« qu'est-ce qui
  ne marche pas ? »), pas par un formulaire ; lui dire tout de suite si le
  problème est déjà connu (« l'imprimante du 2e est en panne, on s'en
  occupe ») avant de lui demander quoi que ce soit ; une seule action
  principale, visible sans défiler ; après l'envoi, une preuve (numéro de
  suivi) et la suite (« quelqu'un vous rappelle sous 2 h »).
- **J'ai déposé une demande et je n'ai pas de nouvelles** : un numéro,
  un écran, un état en français (« reçue », « en cours », « résolue »), la
  date du dernier mouvement, et quoi faire si ça n'avance pas.
- **Je ne sais pas si c'est moi ou le système** : une page d'état des
  services en langage courant, avec la chaîne des dépendances (« Wi-Fi du
  bâtiment B en panne → messagerie et ENT inaccessibles depuis ce
  bâtiment »), datée, sans jargon, la même pour tout le monde.

Règles d'écriture qui en découlent : phrases courtes, verbes d'action,
tutoiement banni, vouvoiement neutre ; jamais un sigle sans son
explication ; les états en trois mots maximum ; l'heure toujours
affichée (une page d'état non datée n'est pas crédible) ; les erreurs
disent la cause ET le geste à faire (« le sujet est obligatoire : décrivez
le problème en une phrase »).

## 3. Le parti pris visuel : prolonger l'écran « tabloïd »

L'écran de saisie rapide (#500) a fixé un style dépouillé qui a plu :
papier blanc, encre noire, titres serif (Georgia), étiquettes en
capitales grises, filets noirs, aucune icône, aucune couleur décorative.
Le redesign le prolonge en **charte des écrans simples** (`simple.css`,
mêmes jetons `--ink`, `--paper`, `--rule`, `--grey`, `--soft`, `--link`)
avec trois ajouts : une largeur de lecture de 720 px maximum (60 à 75
caractères par ligne, l'optimum de lisibilité), une hiérarchie en trois
niveaux seulement (kicker, titre, corps) et trois états sémantiques
portés par un MOT et un filet, jamais par la couleur seule (« en panne »,
« dégradé », « ça marche »).

## 4. Les écrans (espace « Simple », servi par le pont sous `/demande/`)

| Écran | Question de la personne | Contenu | Action principale |
|---|---|---|---|
| `accueil` | « Que voulez-vous faire ? » | quatre portes, en phrases : signaler un problème, suivre ma demande, est-ce que ça marche ?, déposer plusieurs demandes | ouvrir une porte |
| `rapide` (existant) | « Qu'est-ce qui ne marche pas ? » | l'existant + affichage du **numéro de suivi** après l'envoi | Envoyer |
| `suivi` | « Où en est ma demande ? » | un champ numéro ; état en français, date du dernier mouvement, quoi faire si rien ne bouge | Voir |
| `etat` | « Est-ce que ça marche ? » | services en langage courant, état daté, et pour chaque panne ce qui en dépend (« donc … ne marche pas ») | (lecture) |

Logique métier et dépendances : la page d'état lit un **référentiel de
services** (`ETAT_SERVICES_FILE`, JSON tenu par l'administration :
`id`, `nom` en français, `sert_a`, `depend_de`), calcule l'impact d'une
panne par propagation dans les dépendances et l'écrit en une phrase. Le
même référentiel servira au hub (Cortex, service-watch) : une seule
description des dépendances, lisible par un non-initié et exploitable
par la supervision. Les états eux-mêmes viennent d'un fichier posé par
l'exploitation ou, plus tard, de service-watch / Cortex.

## 5. Ce que le redesign NE fait pas (volontairement)

Pas de refonte des tuiles du hub pour les techniciens : elles gardent
leur densité, c'est leur outil. Pas de couleurs de marque ni de logo :
la charte cliente se pose par-dessus, pas dedans. Pas d'authentification
sur ces écrans (même posture LAN que `/demande/`) : le numéro de suivi ne
donne que l'état, jamais le contenu de la demande ni le nom d'un autre
demandeur.

## 6. Mesurer

Cinq personnes non initiées, trois tâches (signaler l'imprimante du 2e en
panne ; retrouver l'état de sa demande ; dire si la messagerie marche
depuis le bâtiment B), chronomètre et « pensée à voix haute ». Critères :
tâche réussie sans aide, moins d'une minute, aucun mot demandé (« ça veut
dire quoi ? »). Un écran échoue dès qu'une personne sur cinq bloque.

## Références

- Bastien, J.M.C. & Scapin, D.L. (1993). *Critères ergonomiques pour
  l'évaluation d'interfaces utilisateurs*, rapport INRIA n° 156.
- Nielsen, J. (1994, mis à jour). *10 Usability Heuristics for User
  Interface Design*, nngroup.com.
- Krug, S. *Don't Make Me Think, Revisited* (2014).
- Norman, D. *The Design of Everyday Things* (éd. 2013).
- Sweller, J. (1988), charge cognitive ; Hick, W.E. (1952), loi de Hick.
- WCAG 2.2 (W3C) : contraste ≥ 4,5:1, cibles ≥ 24 px, texte redimensionnable.

## Note design permanente (22 sept. 2026, « à appliquer partout ») — livraison #562

1. L'en-tête d'un tableau reste fixé à l'écran, seul le `tbody` défile
   (règle globale `thead th { position: sticky }`, valable dans tout cadre
   qui défile).
2. Caractères fortement contrastés sur la couleur de fond (liens en couleur
   d'accent dans les deux thèmes, jamais le bleu marine du navigateur ;
   texte atténué lisible sur fond accent).
3. La page ne défile jamais : en-tête et pied du hub fixes (`.hub-shell`
   en `100vh`, `.hub-main` seule zone qui défile) ; ce sont les cadres et
   les `tbody` qui bougent.
4. Gabarit généralisé `PageFrame.jsx` (`.hub-page*`) : barre de titre,
   cadres latéraux à division **verticale** (colonnes) ou **horizontale**
   (bandes) dont le titre est fixe et les options défilent, zone centrale
   déroulante, pied de vue fixe. Nouvelles vues : partir de ce gabarit ;
   vues existantes : migrer à l'occasion (elles héritent déjà de 1 à 3).
5. Filtre texte priorisant le début de mot (`textFilter.js`,
   `rankFilter`) : « n » présente Nebula avant Onduleurs. Appliqué à
   l'Univers du hub ; à utiliser pour tout nouveau filtre.
6. Le hub présente le site publié par un agent en **aperçu** (page calculée
   par le central) et en **réel** (page servie sur le LAN du site), en
   cadre : menu Pages ouvertes → « voir » (`AgentPageView.jsx`).
7. (#570) Quand le hub dit « activer X », « déposer Y », « régler Z », il
   donne le **lien vers l'endroit du hub où on le fait** — jamais une
   consigne en texte seul. Mécanisme : `hubLinks.js` (`hubLink(view,
   params)` → `?view=…&agent=…&section=…`, `viewParams()` côté vue cible
   pour se placer). Exemples : « activer la sonde windows-probe sur
   <agent> » → tuile Agents hôtes, agent sélectionné, section Sondes ;
   Proxmox sans hyperviseur → Installation / Sondes de l'agent.
8. (#596) Tout bouton qui déclenche un traitement montre sa **prise en
   compte** et son **déroulement** : libellé qui change (« ⏳ analyse… »),
   bouton inactif pendant l'appel, résultat affiché à côté (✓ / erreur en
   couleur) et pas seulement dans le pied de page. Un enchaînement
   obligatoire (analyser puis importer) tient en **un seul bouton** dont le
   libellé avance (« 1. Analyser » → « Importer N éléments ») ; jamais deux
   boutons dont l'un est silencieusement inactif.
9. (#604) Partout où le hub importe un fichier : **zone de glisser-déposer**
   (`DropZone.jsx`, cliquable aussi, nom et taille du fichier retenu,
   formats acceptés affichés). Les cartes de formulaire s'étendent sur
   toute la largeur disponible (jamais un cadre plus étroit que ses
   champs) : `.lic-card` / `.lic-form`, champs à 100 % de leur cellule.
10. (#607) Les liens ont leur propre couleur `--link` (hub : `#8fc6f7` en
    sombre, `#1b5e93` en clair ; pages statiques sombres : `#7ab8f5`),
    jamais l'accent ni le bleu du navigateur : sur fond sombre l'accent
    (#2980b9 / #4a9eda) reste trop foncé pour un lien.
