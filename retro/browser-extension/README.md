# Extension Firefox « parcours applicatif » (livraison #441)

Enregistre ce que la personne fait dans l'application web à rétro-ingénier
et l'envoie à l'**agent relais** local (`retro/relay/relay.py`), qui le
transmet à retro-api. Rien n'est envoyé ailleurs, rien n'est enregistré hors
du périmètre (URL de base de l'application, Options).

## Ce qui est capté

- `navigation` : chaque écran affiché (URL, titre, référent), y compris les
  changements d'URL sans rechargement ;
- `dom` : ce que l'écran montre — titre, en-têtes h1-h3, formulaires (action,
  méthode, **noms** des champs, type, libellé), colonnes des tableaux, nombre
  de liens ;
- `click` : élément cliqué (sélecteur court, texte, lien) ;
- `input` : champ saisi — **nom, type et longueur** ; la valeur seulement si
  l'option est cochée, et **jamais pour un mot de passe** ;
- `submit` : formulaire envoyé (action, méthode, noms des champs) ;
- `request` : requêtes HTTP du navigateur vers l'application (méthode, URL,
  type page/XHR, statut, redirection, durée, **clés** d'un corps de
  formulaire ; jamais les en-têtes, cookies ni valeurs) ; images, CSS et
  scripts sont ignorés ;
- `mark` : repère posé depuis le popup (« après validation du devis »).

## Installation (Firefox)

Extension **non signée** : `about:debugging` → « Ce Firefox » → « Charger un
module complémentaire temporaire » → `manifest.json` de ce dossier (à
refaire à chaque redémarrage de Firefox), ou, avec Firefox Developer
Edition / ESR, `xpinstall.signatures.required = false` dans `about:config`
puis `web-ext build` et installation du `.zip`. Ensuite, Options : URL du
relais (`http://127.0.0.1:6320` par défaut) et **URL de base de
l'application** (une par ligne).

Le relais sur le même poste : `python3 relay.py --central
https://VM:6443/api/retro --token <RETRO_RELAY_TOKEN> --ca ca.crt`
(la commande est affichée dans la tuile Rétro-ingénierie). Puis, dans le
popup : application, nom du parcours, testeur → *Démarrer* ; parcourir ;
*Poser un repère* quand utile ; *Terminer*. Un parcours démarré ailleurs
(relais) est adopté automatiquement par l'extension.

## Chromium / Chrome / Edge

`manifest.chromium.json` (Manifest V3, mêmes sources) : copier le dossier,
renommer ce fichier en `manifest.json`, `chrome://extensions` → mode
développeur → « Charger l'extension non empaquetée ». C'est cette variante
qu'utilise le harnais de vérification (Playwright + Chromium).

## Vérification

`node --test retro/browser-extension/test_lib.mjs` (fonctions pures :
périmètre, sélecteurs, valeurs masquées, description des formulaires) ;
chaîne réelle extension (Chromium MV3) → relais → retro-api sur une
application factice : navigation, clic, saisies (mot de passe masqué),
envoi de formulaire, redirection 302, XHR, repère — voir retro/README.md.
**Non vérifié dans Firefox réel** (pas de Firefox dans l'environnement de
développement) : le manifeste V2 et les API `browser.*` utilisées sont
celles documentées ; à confirmer au premier chargement.
