# Tests QA en ligne (module du hub, livraison #651)

Teste en ligne un **site déployé** — application portée par l'IA de portage ou n'importe quel site du parc, porté ou
non. Un site = une URL de base et des étapes de connexion (jouées avant chaque scénario). Un scénario = des étapes
pas à pas (aller à, saisir, cliquer, choisir, cocher, touche, attendre, vérifier : visible / texte / URL / valeur /
absent, capture), jouées dans un vrai Chromium (Playwright) avec capture à chaque navigation et à chaque échec.

**Boucle QA demandée** : mode QA (exploration) → depuis une exécution, ticket **incident** ou **évolution** créé dans
le module Tickets (déroulé pas à pas, étape en échec, URL, commentaire du testeur) → le scénario devient un **test
traversant de non-régression**, rejoué en **campagne** (tous les scénarios de non-régression du site, ou tous).

## Décisions

- Image Playwright officielle (`mcr.microsoft.com/playwright/python`) : navigateurs inclus, ~1,5 Go ; un worker
  gunicorn, exécutions synchrones bornées par étape (`QA_STEP_TIMEOUT_MS`, défaut 15 s), délai gunicorn 900 s.
- `runner.py` (Playwright) est injectable : les tests de l'API tournent sans navigateur (`FakeRunner`), le runner
  réel a été vérifié à part contre une application déployée (connexion, navigation, vérification en échec avec
  capture, reconnaissance d'une page).
- Tickets : `POST /tickets` de tickets-api (`TICKETS_API_INTERNAL_URL`), `type_id` résolu par libellé commençant
  par « Incident » / « Évolution » dans `/types` (sinon sans type), `source_type = qa`, `source_nom = <site>`. Une
  exécution crée au plus un ticket (409 ensuite).
- Secrets de connexion des sites en clair dans `qa.db` (même décision assumée que DBA), masqués en lecture
  (`••••`) et conservés si renvoyés masqués.
- Reconnaissance (`POST /sites/<id>/probe`) : titre, formulaires et champs, liens, titres — pour écrire les étapes
  d'un site inconnu ; le hub en déduit des étapes de connexion à compléter.
- Hors périmètre pour l'instant : enregistrement de parcours par capture des gestes (on écrit les étapes), planification
  des campagnes (bouton seulement), sites derrière un bastion.

## API (`/api/qa/`)

`GET /catalog` · `GET/POST /sites`, `PUT/DELETE /sites/<id>`, `POST /sites/<id>/probe` ·
`GET/POST /sites/<id>/scenarios`, `PUT/DELETE /scenarios/<id>` · `POST /scenarios/<id>/run`, `GET /scenarios/<id>/runs` ·
`POST /sites/<id>/campaign {kind: non-regression|all}`, `GET /sites/<id>/campaigns` · `GET /runs/<id>/shot/stepN.png` ·
`POST /runs/<id>/ticket {kind: incident|evolution, comment}`.

## Vérifié / non vérifié

- `qa/api/test_qa.py` (test_client, runner simulé, tickets-api simulé) : site et masquage du mot de passe,
  validation des étapes, exécution avec captures (et refus d'un chemin `../`), échec → ticket incident (type résolu,
  déroulé dans la description, scénario passé en non-régression, 409 au second), campagne, ticket évolution,
  suppression en cascade.
- `runner.py` réel : joué contre une application déployée (hors de ce dépôt).
- Front : `hub/tests/qaLib.test.mjs`, syntaxe `@babel/parser`, aucun setter sans `useState`, aucune couleur en dur.
- Non vérifié : build de l'image, rendu navigateur.

## Conformité visuelle et ergonomique, tour du hub (livraison #721, item 116 tranches 1-2)

- Étape **`audit`** (valeur vide ou `strict`) : relevé dans la page (`qa_design.AUDIT_JS` : couleurs calculées, tailles,
  défilements, en-têtes de tableau, styles en ligne, textes tronqués) puis règles **pures** (`qa_design.evaluate`, testées
  sans navigateur) : contraste WCAG (4,5:1, 3:1 grands textes), la page ne défile pas (seuls cadres et tbody), pas de
  défilement horizontal, en-tête fixe d'un tableau qui défile, cibles ≥ 24 px, couleur en dur hors `theme.css`, textes
  tronqués. Résultat : `findings` + `score` /100 dans le résultat de l'étape ; `strict` = une erreur fait échouer l'étape.
- **Tour du hub** : `POST /sites/<id>/hub-tour {views:[{view,label}], wait_ms?, strict?}` → scénario « Tour du hub —
  conformité visuelle » (aller à `?view=…`, attendre, auditer ; capture à chaque visite), régénéré sans doublon. Le hub
  envoie la liste de ses vues (thématiques) : bouton « 🧭 Tour du hub (conformité) » d'un site.
- Décisions (9 oct.) : analyse **locale sans modèle de vision** (DOM, styles, règles ; rien ne sort du SI), **hub seul**
  d'abord. Suite (item 116) : références et différences de captures (tranche 3), maquettes en étapes (tranche 4).
- `AUDIT_JS` vérifié dans un vrai Chromium (Playwright) sur une page de test : les 6 règles détectent leur cas.

## Référence visuelle et différences de captures (livraison #727, item 116 tranche 3)

- **Référence** : `PUT /scenarios/<id>/reference {run_id|null}` -- une exécution du scénario devient la référence
  (captures attendues). Hub : « ★ Définir comme référence » dans le détail d'une exécution.
- **Comparaison** : `GET /runs/<id>/diff[?against=<exécution>]` -- étape par étape (hors connexion), écart en % des
  pixels (seuil par canal 24, significatif au-delà de 0,5 %), zone touchée, taille changée, image de différence
  (capture assombrie, changements en rouge) mise en cache `diff-<against>-<capture>` dans le dossier de l'exécution.
  `against` sert à **rejouer un bug** : rejouer le scénario d'un ticket puis comparer à l'exécution jointe au ticket.
- **Zones masquées** : champ du scénario (sélecteurs CSS séparés par des virgules) passé à la capture Playwright
  (`mask`) pour neutraliser horloges, compteurs, dates.
- Calcul pur Pillow (`qa_visual.py`, testé sans navigateur) ; analyse locale, aucun modèle de vision.

## Maquettes en étapes (livraison #728, item 116 tranche 4)

- Une **maquette** part d'une exécution (situation actuelle) et porte des **variantes** = feuilles CSS injectées par
  Playwright (`add_init_script`, balise `style#qa-mockup`) dans le navigateur de test seulement : copie isolée, rien
  n'est modifié en production.
- **Variantes calculées** (`qa_mockup.py`, sans modèle de vision) depuis les constats `audit` : couleur de texte la plus
  proche atteignant le contraste (AA, puis variante AAA 7:1), en-tête de tableau fixe, cibles portées à 24 px ; les
  règles sans correctif sûr (page qui défile, couleur en dur, texte tronqué) deviennent des notes. Variantes manuelles
  libres (pas de balise, `@import` ni ressource externe ; 20 000 caractères au plus).
- **Présentation** : ① situation actuelle (note, captures) → ② proposition → ③ variantes (note et écart, vignettes
  avant / variante / différences) → ④ règles respectées (constats par règle avant / après) → ⑤ décision.
- **Décision** validée → ticket **évolution** (module Tickets) avec la variante, le gain de note et le correctif CSS à
  reporter dans `shared/theme.css` / le composant. Les exécutions de maquette restent hors de l'historique du scénario.
- API : `GET|POST /scenarios/<id>/mockups`, `GET|PUT|DELETE /mockups/<id>`, `POST /mockups/<id>/render[?variant=i]`,
  `POST /mockups/<id>/decision {status: validee|rejetee, variant, comment}`.
- Vérifié dans un vrai Chromium (Playwright) sur une page de test : note 70 → 95 avec la variante calculée
  (contraste, en-tête fixe, cible petite corrigés ; reste la couleur en dur, non corrigeable par CSS).

## Boucle de conception : maquette validée = cible (livraison #729, item 116 tranche 5)

- Valider une variante en fait la **cible** du scénario (`target_run_id`, `target_mockup_id`) et le passe en
  non-régression. Chaque exécution (unitaire ou en campagne) est comparée aux captures de la variante : `design`
  `{compared, significant, score, target_score, conforme}` ; conforme = parcours réussi et aucun écart significatif.
- La première exécution conforme marque la maquette **intégrée** (`integrated_run_id`, `integrated_at`).
- `GET /runs/<id>/design` (historique), `DELETE /scenarios/<id>/target` (le développement change de direction) ;
  supprimer la maquette retire aussi la cible. Hub : badge « conforme / écart avec la maquette » dans le détail et
  dans la campagne, « Voir les écarts avec la maquette ».
