# Assistant de design et de parcours dans le module QA — cadrage (2026-10-09, item 116)

## Demande (mot pour mot)

« J'en voudrais aussi une [IA] qui soit capable de refondre un design visuel du hub avec des étapes de présentation de
maquette. Elle s'intégrerait dans le module de QA avec des outils d'automatisation de parcours dans le hub et dans les
applications comme celle des tickets… L'idée est d'assister le design en évolution et de rejouer un bug ou au
contraire une vérification de conformité visuelle et ergonomique. »

## Ce qui existe déjà (à réutiliser, pas à refaire)

- `qa/` (#651) : sites, scénarios pas à pas joués dans Chromium (Playwright), captures à chaque étape, échec → ticket
  incident/évolution, campagnes de non-régression, reconnaissance d'une page inconnue.
- Règles de design PERMANENTES (22 sept.) : en-têtes de tableau fixes, contraste fort, pied fixe, cadres qui défilent,
  filtres par début de mot, liens « là où on le fait » ; thème = variables de `shared/theme.css` uniquement.
- Brief d'ergonomie `docs/ergonomie-redesign.md` (#541) ; assistant-api (modèle local, extraction JSON) ; #715 (catalogue
  des vues du hub, `?view=` pour atteindre chaque écran).

## Proposition en 5 tranches (une livraison chacune)

1. **Parcours enregistrés** : enregistreur de gestes dans le hub et les fronts (clics, saisies, navigation → étapes QA),
   catalogue des vues du hub (#715) comme points d'entrée ; parcours « tour du hub » généré (une capture par vue).
2. **Conformité visuelle et ergonomique automatique** : à chaque capture, contrôles mesurés dans la page (contraste
   WCAG des textes, couleurs hors `theme.css`, en-tête de tableau qui défile, page qui défile au lieu des cadres,
   textes tronqués, cibles trop petites, débordements, thème sombre) → constats notés par règle, dans le rapport QA.
3. **Différences visuelles** : référence par écran et par thème, différence de pixels avec masque des zones vivantes,
   seuil ; « rejouer un bug » = rejouer le parcours du ticket et comparer à la capture d'origine.
4. **Maquettes et étapes de présentation** : à partir d'un écran capturé, l'assistant propose une refonte (CSS/variables,
   disposition) appliquée dans une copie isolée de la page (feuille injectée, jamais en production) ; présentation en
   étapes (avant / proposition / variantes / règles respectées), validation par la personne, puis ticket évolution
   avec le correctif CSS proposé.
5. **Boucle de conception** : la maquette validée devient une référence (tranche 3) ; la campagne vérifie ensuite que
   le développement la respecte.

## Décisions (9 oct. 2026)

- Vision : **locale sans modèle de vision** (DOM, styles calculés, règles) -- rien ne sort du SI.
- Périmètre : **hub seul** d'abord (tour par le catalogue des vues).
- Références de captures : volume `qa/data`, par exécution (défaut, à revoir à la tranche 3).
- Livré : tranches 1-2 (#721 : tour du hub + étape `audit`), 3 (#727 : référence, différences, zones masquées),
  4 (#728 : maquettes en étapes, variantes calculées depuis les constats, décision → ticket évolution),
  5 (#729 : la variante validée devient la cible du scénario ; campagnes « conforme à la maquette », maquette intégrée).

## Questions initiales

- Modèle de vision pour « refondre » (analyse de captures) : les modèles locaux actuels sont textuels ; tranche 4 en
  local = propositions à partir du DOM et des règles ; un modèle vision (local GPU ou externe) changerait la portée.
- Fronts visés en premier : hub seul, puis portail tickets ? (comptes de test du coffre pour la connexion)
- Où vivent les références (captures) : volume `qa/data`, versionnées par livraison (#N) ?
