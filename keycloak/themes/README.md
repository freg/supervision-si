# Thèmes de connexion Keycloak (livraison #275)

Demandé explicitement : "peux tu proposer des skins pour la mire
keycloak ? et intégrer un skin par défaut qui soit cohérent avec le
hub".

## Skins proposés

- **`hub`** (clair) -- **skin PAR DÉFAUT, intégré** (`loginTheme`
  dans `keycloak/realm-template.json`). Reprend exactement la
  palette claire du hub (`shared/theme.css`,
  `:root[data-theme="light"]`) : fond `#f4f6f8`, carte `#ffffff`,
  accent `#2980b9`, police "Segoe UI".
- **`hub-dark`** (sombre) -- skin ALTERNATIF, PAS activé par défaut.
  Même structure, palette sombre du hub
  (`:root[data-theme="dark"]`) : fond `#1a1d23`, carte `#22262e`,
  accent `#4a9eda`. À sélectionner manuellement si préféré (Realm
  Settings → Themes → Login Theme → `hub-dark`, dans la console
  d'administration Keycloak).

D'autres variantes de couleur seraient triviales à ajouter sur ce
même squelette (copier un dossier, changer les valeurs hexadécimales
dans `login.css`) -- pas construites par défaut, la personne n'ayant
demandé qu'un skin cohérent + des propositions, jamais une liste
close.

## Comment ça marche (raisonnement, pas une supposition)

**`parent=keycloak`** dans chaque `theme.properties` -- hérite de
TOUS les gabarits FreeMarker et toute la logique du thème classique
Keycloak (formulaires, i18n, gestion des erreurs, accessibilité) ;
SEUL le CSS est remplacé (`styles=css/login.css`). Approche la plus
robuste : jamais de réimplémentation des templates HTML, donc jamais
cassée par une montée de version mineure de Keycloak -- confirmée
valable en Keycloak 26 (image utilisée par ce projet,
`quay.io/keycloak/keycloak:26.0`) par la documentation officielle
Red Hat.

Sélecteurs CSS ciblés (`.login-pf`, `.card-pf`/`#kc-login`,
`#kc-header-wrapper`, `.btn-primary`, `.pf-c-*`...) **vérifiés avant
d'écrire quoi que ce soit** contre plusieurs sources convergentes
(dépôt officiel `keycloak/keycloak` sur GitHub, documentation Red
Hat 26.0, plusieurs guides indépendants) -- le thème classique
mélange des classes Bootstrap-like ET PatternFly selon les éléments,
les deux jeux sont donc ciblés pour rester robuste aux variations
mineures de sous-version.

## ⚠️ Piège évité : montage Docker par sous-dossier, jamais le parent

Chaque thème est monté INDIVIDUELLEMENT sur son propre sous-chemin
(`./keycloak/themes/hub:/opt/keycloak/themes/hub:ro`), **jamais**
tout `/opt/keycloak/themes` d'un coup. Un montage sur le dossier
PARENT aurait REMPLACÉ entièrement son contenu côté conteneur,
effaçant les thèmes intégrés (`keycloak`, `base`, `keycloak.v2`)
dont `parent=keycloak` dépend -- aurait cassé la connexion, le
compte ET la console d'administration en même temps. Voir
`gateway/docker-compose.yml`.

## Non vérifié dans cet environnement

**Aucun rendu visuel possible ici** (pas de navigateur, pas
d'instance Keycloak réelle disponible) -- les couleurs/sélecteurs
sont corrects sur le papier (vérifiés contre la documentation et le
code source officiels), mais le premier déploiement réel reste le
seul vrai test. Points à vérifier en particulier au premier essai :
contraste texte/fond du skin sombre, alignement de la carte de
connexion sur mobile, apparence des boutons de connexion sociale
(SSO) si un jour activés (icônes définies dans le thème
`keycloak` parent, jamais retouchées ici).

## Comment appliquer

Le skin `hub` est déjà réglé comme défaut dans
`keycloak/realm-template.json` (`"loginTheme": "hub"`) -- s'applique
au prochain rendu (`python3 keycloak/render.py`) puis au prochain
import realm (`--import-realm`, au premier démarrage du volume
Keycloak, voir `keycloak/README.md` pour le comportement "une seule
fois" déjà documenté). Pour un realm DÉJÀ importé (volume Keycloak
existant), changer le thème via la console d'administration
(Realm Settings → Themes) reste nécessaire -- le fichier
realm-template.json n'est relu qu'au tout premier import.

## Quatre vrais bugs trouvés en déploiement réel (livraison #281)

Le skin "hub" avait été livré (#275) sans jamais avoir été vérifié
visuellement (aucun navigateur disponible en développement) --
quatre bugs réels sont apparus au premier vrai test, signalés par la
personne, corrigés une fois le VRAI code source HTML de la page de
connexion transmis (bien plus fiable que de re-deviner une troisième
fois) :

1. **Bouton "Connexion" illisible (texte blanc sur fond blanc)** --
   `#kc-login` avait été pris pour l'ID de la CARTE de connexion
   (d'après une documentation qui devait décrire une version
   différente de Keycloak) -- en réalité, dans cette version 26,
   `#kc-login` est l'ID du BOUTON lui-même
   (`<input type="submit" id="kc-login" class="pf-c-button
   pf-m-primary...">`). La règle de carte lui donnait donc un fond
   blanc qui l'emportait par SPÉCIFICITÉ CSS (`#id` bat toujours
   `.classe.classe`) sur le bleu voulu par la règle de bouton --
   texte blanc (de la règle bouton) sur fond blanc (de la règle
   carte, plus spécifique). Corrigé : `.card-pf` seule pour la
   carte, `#kc-login` dédié au bouton avec `background-color`
   (jamais le raccourci `background`) + `!important` pour battre le
   CSS PatternFly v4 fourni.
2. **Largeur non bornée** -- `.card-pf` n'avait jamais de
   `max-width`, prenant toute la largeur de l'écran ("inverse des
   interfaces data", selon la personne). Corrigé : `max-width: 480px`
   + centrage.
3. **Menu de langue resté ouvert en permanence** -- correctif
   DÉFENSIF ajouté (masquer `.pf-c-dropdown__menu` par défaut, ne le
   révéler que sur une classe d'état "ouvert") -- ⚠️ PAS confirmé que
   c'est la cause réelle (pourrait être `menu-button-links.js`,
   hérité du thème parent, jamais modifié ici) -- à revérifier après
   ce correctif.
4. Un quatrième point signalé ("l'autre texte de connexion") --
   PAS ENCORE ÉCLAIRCI, demande de précision en attente.

`hub-dark` corrigé PAR ANALOGIE directe (mêmes bugs structurels très
probables, jamais vérifié lui-même en conditions réelles -- seul
"hub" a été réellement testé).

**Leçon retenue** : la documentation externe sur les sélecteurs
Keycloak peut décrire une version différente de celle réellement
déployée -- le VRAI code source HTML de la page rendue est la seule
source fiable, à demander dès le premier signe d'écart plutôt que de
re-deviner.

## Correctifs réels et thème par défaut (livraison #296)

Reprise du 4ème point signalé en #281 (jamais éclairci à l'époque)
et du menu langue -- demandé explicitement "pour les démos internes".
Trois points :

1. **Menu de langue -- CORRIGÉ, cette fois avec le VRAI gabarit
   Keycloak en main** (dépôt officiel `keycloak/keycloak`,
   `base/login/template.ftl`), pas une supposition. Structure réelle :
   ```
   <div id="kc-locale-dropdown" class="menu-button-links ...">
     <button id="kc-current-locale-link" aria-expanded="false" ...>
     <ul id="language-switch1" class="pf-c-dropdown__menu ...">
   </div>
   ```
   AUCUNE classe `.pf-m-expanded` nulle part -- la supposition de
   #281 était fausse. L'état ouvert/fermé est porté par l'attribut
   ARIA standard `aria-expanded` sur le BOUTON (motif universel pour
   un menu accessible, confirmé par la documentation PatternFly et
   les pratiques ARIA usuelles) -- `menu-button-links.js` bascule cet
   attribut au clic. Corrigé avec un sélecteur de fratrie CSS
   (`#kc-current-locale-link[aria-expanded="true"] ~ #language-switch1`),
   ciblant directement cet état plutôt qu'une classe devinée.
   ⚠️ Toujours pas vérifié dans un vrai navigateur (aucun outil
   disponible ici) -- mais fondé sur le code source réel de Keycloak
   cette fois, pas une hypothèse.

2. **Champs et boutons centrés/réduits** -- `.pf-c-form-control` et
   `#kc-login` n'avaient aucune largeur propre (héritaient de 100%
   de la carte, 480px) -- réduits à `max-width: 320px`, centrés
   (`margin: auto`).

3. **Thème PAR DÉFAUT changé vers `hub-dark`** (demandé
   explicitement) -- `keycloak/realm-template.json`,
   `"loginTheme": "hub-dark"`. Vérifié : `vault-standalone` n'a pas
   de réglage équivalent (thème différent, rien à synchroniser).

Les trois correctifs appliqués IDENTIQUEMENT aux deux thèmes
(`hub` et `hub-dark`) -- cohérence entre les deux, pas seulement
celui devenu défaut.

## Badge de numéro de livraison (livraison #298)

Demandé explicitement. Affiché en CSS pur (`::after` sur `.card-pf`,
`content: "v298"`) -- jamais une réécriture de gabarit FreeMarker,
cohérent avec le principe déjà établi ("parent=keycloak... SEULEMENT
le CSS est remplacé"). Mis à jour MANUELLEMENT à chaque livraison qui
touche ce thème -- pas d'automatisation pour l'instant.

## ⚠️ Recréation MANUELLE requise après toute modification (livraison #300, cause racine réelle trouvée)

**Diagnostic complet mené en conditions réelles (#298-#300)**, chaque
fausse piste éliminée méthodiquement avant de trouver la vraie
cause :
- ❌ Cache serveur Keycloak -- `start-dev` le désactive DÉJÀ par
  défaut (confirmé par plusieurs sources officielles), jamais la
  cause ici.
- ❌ Cache navigateur -- éliminé avec une fenêtre de navigation
  privée neuve, aucun changement.
- ❌ Cache nginx (tls-proxy) -- aucune directive `proxy_cache` dans
  `tls-proxy/render_nginx_conf.py`, éliminé.
- ❌ Mauvais thème sélectionné -- confirmé "hub" actif dans la
  console d'administration (Realm Settings → Themes).
- ✅ **VRAIE CAUSE, confirmée par `docker exec ... cat login.css`
  montrant le contenu du TOUT PREMIER `login.css` (#275), jamais mis
  à jour depuis** : `restart` ne RECRÉE JAMAIS un conteneur -- il
  relance le MÊME conteneur, dont les montages restent figés à ce
  qu'ils étaient à sa création INITIALE. `keycloak` est défini dans
  `gateway/docker-compose.yml`, séparé du `docker-compose.yml`
  racine que `scripts/chantier.sh build` (l'alias `deploie` habituel)
  cible -- son conteneur n'a donc jamais été RECRÉÉ depuis sa toute
  première création, quel que soit le nombre de `restart` lancés
  depuis. Seul `up -d` relit la config actuelle et recrée le
  conteneur si nécessaire (montages compris).

**Décision confirmée avec la personne** : ne PAS automatiser cette
recréation dans le `build` normal de `chantier.sh` -- Keycloak sert
d'AUTRES consommateurs (ex. TRB140/SMS) qui ne doivent jamais subir
une coupure comme effet de bord d'un déploiement routinier sans
rapport avec Keycloak. Doit rester un geste DÉLIBÉRÉ, jamais
implicite -- voir l'option `--all` de `chantier.sh build` (#299),
qui utilise bien `up -d`, pas `restart`.

**Donc, à chaque livraison future qui touche `keycloak/themes/` ou
`keycloak/realm-template.json`** : signaler explicitement la
commande de recréation manuelle, ne jamais supposer que `deploie`
suffit :
```
docker compose -p supervision-si-gateway --env-file .env \
  --project-directory . -f gateway/docker-compose.yml up -d
```
(ou `./scripts/chantier.sh build --all`, qui fait la même chose).

## Correctif d'alignement étiquettes/champs (livraison #300)

Signalé par la personne après vérification visuelle réelle (premier
retour positif complet sur les correctifs #296/#298/#299, UN SEUL
point encore décalé) : les CHAMPS de saisie (`.pf-c-form-control`)
avaient été centrés/réduits en #296 (`max-width: 320px`, `margin:
auto`), mais les ÉTIQUETTES (`.pf-c-form__label`) étaient restées
alignées à gauche sur toute la largeur de la carte -- ne
correspondaient plus au bord gauche des champs recentrés. Corrigé en
appliquant le MÊME `max-width`/centrage aux étiquettes, sur les deux
thèmes.

## Reste à faire

- **"Si possible un choix de skins"** -- les deux thèmes existent
  déjà et restent sélectionnables depuis la console d'administration
  Keycloak (Realm Settings → Themes). Un bouton de bascule EN PAGE
  (jour/nuit sans passer par l'admin) demanderait du JavaScript
  nouveau, jamais testable dans un vrai navigateur ici -- pas
  construit pour l'instant plutôt que livré sans avoir pu le
  vérifier sur un écran de connexion (sensible par nature). Voir
  BACKLOG.md item 46.
- Toujours pas vérifié en conditions réelles depuis #281 -- premier
  vrai test à faire par la personne après ce correctif.
