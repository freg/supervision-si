# Mini charte d'icônes du hub

Livraison #410. Origine : retour de tests sur le cycle agile réseau —
« le cerveau est un peu saignant et la fusée trop Tintin ; propose des jeux
d'icônes et de symboles, qu'on construise une mini charte pour le hub ».

Ce document décrit ce qui est **choisi**, ce qui est **proposé** pour
comparaison, et les **règles** qui permettent d'étendre la charte aux
autres tuiles sans y revenir à chaque fois. Le code correspondant est
`hub/src/icons.js` (données et règles, pur, testé) et `hub/src/StepIcon.jsx`
(rendu HTML et SVG).

## 1. Ce qui change tout de suite

| Étape | Avant | Après (jeu « Emoji sobres ») | Pourquoi |
|---|---|---|---|
| Décider | 🧭 | 🧭 | inchangé : un instrument, pas un personnage |
| Explorer | 🕸️ | 🕸️ | inchangé, cohérent avec la tuile « Exploration réseau » |
| Déployer | 🚀 | 📦 | on *met en place* quelque chose (tunnels, cibles SNMP) ; la fusée raconte un lancement, pas une mise en service |
| Mesurer | 📊 | 📊 | inchangé |
| Apprendre | 🧠 | 📚 | on capitalise (signaux, sauvegardes) ; le cerveau est un organe, pas un objet |

Appliqué **partout où une étape est nommée** : menu classique, nœuds du
graphique, titre du panneau de détail, infobulle. Une seule source
(`ICON_SETS`), jamais une icône recopiée à la main dans une vue.

## 2. Trois jeux à comparer à l'écran

Dans la tuile Cycle agile, le sélecteur « Icônes » (à droite des onglets
Classique / Graphique) bascule le jeu en direct. La préférence est locale
au navigateur (`localStorage`, clé `hub.cycle.iconSet`) : le temps de
trancher, elle n'a pas à traverser les comptes.

| Jeu | Décider | Explorer | Déployer | Mesurer | Apprendre | Caractère |
|---|---|---|---|---|---|---|
| **Emoji sobres** (défaut) | 🧭 | 🕸️ | 📦 | 📊 | 📚 | le langage déjà utilisé par toutes les tuiles du hub ; dessin qui dépend du système de la personne (Apple, Windows, Noto) |
| **Symboles monochromes** | ⎈ | ⌕ | ⇪ | ∿ | ✎ | Unicode, prennent la couleur de l'étape et suivent le thème clair/sombre ; police-dépendants mais sobres |
| **Pictogrammes au trait** | boussole | loupe + nœuds | cube | barres | livre ouvert | SVG 24×24, trait 2 px, bouts ronds, dessinés pour le projet : rendu identique sur toutes les machines ; la voie d'une vraie charte si le hub entier quitte l'emoji |

Alternatives emoji étudiées, disponibles d'un mot dans `icons.js`
(`EMOJI_ALTERNATIVES`) : Décider 🎯 ⚖️ 🗺️ · Explorer 🔍 📡 · Déployer 🛠️
🧩 ⚙️ · Mesurer 📈 📏 ⏱️ · Apprendre 💡 🎓 📝.

Écartés, avec la raison, pour ne pas y revenir (`REJECTED_ICONS`) :
🚀 (véhicule, clin d'œil) et 🧠 (organe).

## 3. Règles de la charte

1. **Une idée = une icône**, réutilisée à l'identique partout où l'idée
   apparaît (tuile, menu, titre, bouton d'ouverture). Si « Exploration
   réseau » est 🕸️ dans le menu Réseau, c'est 🕸️ dans le cycle.
2. **La couleur porte l'identité, jamais l'état.** Chaque étape a sa
   couleur (`CYCLE_STEPS[].color`), utilisée pour le cercle du nœud, la
   bordure du bouton actif, le titre. L'état (ok / attention / critique /
   inconnu) passe **toujours** par la pastille de statut et les variables
   de thème `--ok`, `--warning`, `--danger`, `--muted` — jamais par
   l'icône elle-même, jamais par une couleur en dur (piège déjà corrigé
   plusieurs fois : un vert fixe ressort faux en thème sombre).
3. **Objets et symboles, pas d'anthropomorphisme ni de clin d'œil.** Un
   instrument (boussole, loupe, règle), un objet (paquet, livre), un
   symbole (barres, onde). Pas de visages, d'organes, de véhicules, de
   gestes.
4. **Lisible sur les deux thèmes.** Les emoji sont fournis en texte ; les
   symboles et les tracés en `currentColor` ; aucune icône n'a de fond
   propre.
5. **Tailles** : 16 px dans un bouton de menu, 20 px dans un titre de
   panneau, 22 px dans un nœud de graphique, 14–15 px dans une infobulle.
   Toujours par la prop `size` de `StepIcon` / `SvgStepIcon`.
6. **États du hub** (à respecter dans toute nouvelle vue) : 🟢 / `--ok`
   en ligne, ⚪ ou `--muted` arrêté ou inconnu, ⚠️ / `--warning`
   attention, 🔴 / `--danger` erreur ou critique. Ce sont les seuls
   symboles d'état ; on ne « colore » pas une icône d'identité pour dire
   qu'elle va mal.

## 4. Étendre la charte aux autres tuiles

`icons.js` ne connaît aujourd'hui que les cinq étapes du cycle. Pour
étendre : ajouter une clé par tuile dans chaque jeu (`ICON_SETS.*.icons`),
avec le même identifiant que celui du menu (`network-agent`, `netprobe`,
`ssh-tunnels`…), puis remplacer les emoji en dur de `App.jsx` par
`<StepIcon set={…} step="network-agent" />`. Le test
`hub/tests/icons.test.mjs` impose déjà que **chaque jeu définisse chaque
clé** : impossible d'ajouter une tuile à un jeu et de l'oublier dans les
autres.

Décision attendue de la personne : quel jeu devient le défaut, et si la
préférence doit devenir un réglage de compte (comme le thème) plutôt qu'un
réglage de navigateur.

## Vérifié / non vérifié

Vérifié : 6 tests Node sur `icons.js` ; build Vite réel du hub ; rendu
réel des trois jeux dans Chromium (Playwright) en thème clair et sombre,
menu classique et graphique, sans erreur console. Non vérifié : le rendu
des emoji sur le poste de la personne (dépend de sa police système), le
rendu des symboles Unicode sur Windows (police Segoe UI Symbol).
