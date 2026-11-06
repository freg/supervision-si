# Démonstration automatisée du hub (livraison #982)

Visite thématique des écrans, enregistrée en captures, puis **diaporama HTML autonome** (images incluses : s'ouvre
dans n'importe quel navigateur, flèches, lecture automatique, plein écran, balayage au doigt) et **présentation
.pptx** (16:9, une capture par diapositive, légende, notes). À relancer à chaque grande évolution.

```
cd ~/SRC/data2/tickets/supervision-si && ./scripts/demo.sh
cd ~/SRC/data2/tickets/supervision-si && ./scripts/demo.sh idruide
```
Sortie : `demo/sorties/<parcours>-<AAAAMMJJ-HHMM>/` (diaporama.html, <parcours>.pptx, captures, manifeste.json,
journal.txt). `python3 demo/build.py <dossier>` refait diaporama et pptx après retouche des légendes du manifeste.

## Réglages (.env, jamais dans git)
- `DEMO_HUB_URL` : adresse du hub telle que le navigateur l'ouvre (ex. https://…/).
- `DEMO_USER`, `DEMO_PASSWORD` : compte Keycloak **dédié à la démonstration**, droits de lecture seulement.

## Parcours (`demo/parcours/<id>.json`)
`id`, `titre`, `sous_titre`, `public`, `variables` (valeurs par défaut de `{nom}`), `theme` (`dark` par défaut, `light` pour une impression — #991), `masquer` (sélecteurs CSS cachés
sur les captures, ex. le bandeau d'alertes), `largeur`/`hauteur` (1600×900), `etapes` : `titre`, `legende`, `vue`
(identifiant de vue du hub), `params` (paramètres d'URL, ex. `{"tab": "vlan"}`), `saisir` (`[{selecteur, texte}]`),
`cliquer` (sélecteurs Playwright, dans l'ordre : `button:has-text("Alertes")`, `tr:has-text("{terminal}")`…),
`attendre`, `defiler`, `zone` (capturer un seul élément), `pause_ms`. Un élément introuvable n'arrête pas la visite :
la capture est faite et le journal le signale.

Livrés : `idruide` (tout est ouvert, les flux passent), `maj-terminal` (suivre une tablette : fiche, activité,
chemin réseau, passages, flux), `vlan-ssid` (VLAN, SSID, bornes, lieux… et le site 51, alias le lab des métiers).
