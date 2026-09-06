# Cycle agile réseau

## Vue d'ensemble

Le cycle agile réseau est une tuile hub qui regroupe les outils de supervision réseau du projet en un parcours en 5 étapes : **Décider → Explorer → Déployer → Mesurer → Apprendre**.

Chaque étape donne accès aux outils existants du projet ou résume leur état, permettant une navigation fluide entre les différentes phases du cycle.

La tuile propose **deux modes de vue** :
- **Classique** : navigation par onglets horizontaux avec KPI et tableaux détaillés
- **Graphique** : diagramme SVG interactif avec nœuds, flèches animées et indicateurs de statut temps réel

## Architecture

### Fichiers

| Fichier | Rôle |
|---------|------|
| `hub/src/NetworkCycleView.jsx` | Composant principal — panneau central avec navigation entre les étapes + onglet graphique SVG |
| `hub/src/networkCycleClient.js` | Client API — agrège les appels vers les services réseau |
| `hub/src/hub.css` | Styles CSS pour la navigation du cycle, les KPI et le diagramme SVG |
| `docs/cycle-agile-reseau.md` | Cette documentation |

### Intégration

- **Menu** : Ajout de l'entrée "Cycle agile réseau" dans le menu déroulant "Réseau" de la barre de navigation
- **Vue** : Ajout du rendu conditionnel dans `App.jsx` pour `viewMode === "network-cycle"`
- **API** : Le client `networkCycleClient.js` délègue aux API existantes (netmap-orchestrator, network-agent, netprobe, snmp, ssh-tunnels, vigilance, backup-restore)

## Les 5 étapes

### 1. Décider (netmap-orchestrator)

**Objectif** : Analyser les besoins et les suggestions d'action réseau.

**Outil** : `netmap-orchestrator` — génère des suggestions d'analyse/supervision à partir des données collectées par network-agent.

**Indicateurs affichés** :
- Nombre de suggestions ouvertes
- Nombre de suggestions traitées
- Nombre de suggestions rejetées

**Actions** : Navigation vers l'orchestrateur réseau détaillé.

### 2. Explorer (network-agent)

**Objectif** : Découvrir et cartographier le réseau existant.

**Outil** : `network-agent` — capture passive du trafic pour découvrir les appareils, services et échanges.

**Indicateurs affichés** :
- État de la capture (active/arrêtée)
- Nombre de sites découverts
- Nombre total d'appareils

**Actions** : Navigation vers l'exploration réseau détaillée.

### 3. Déployer (ssh-tunnels + snmp)

**Objectif** : Déployer les accès et les équipements nécessaires.

**Outils** :
- `ssh-tunnels` — gestion des connexions SSH, tunnels et montages SSHFS
- `snmp` — gestion des cibles SNMP et interrogation des équipements

**Indicateurs affichés** :
- Nombre de connexions SSH configurées
- Nombre de tunnels actifs
- Nombre de cibles SNMP enregistrées

**Actions** : Navigation vers les vues détaillées ssh-tunnels et snmp.

### 4. Mesurer (netprobe)

**Objectif** : Établir les lignes de base et surveiller les KPIs réseau.

**Outil** : `netprobe` — sondes smokeping, scans nmap, captures tcpdump.

**Indicateurs affichés** :
- Nombre de cibles surveillées
- Nombre de cibles en ligne
- Nombre de sondes actives

**Données** : Latence, perte de paquets, dernier échantillon par cible.

**Actions** : Navigation vers les sondes réseau détaillées.

### 5. Apprendre (vigilance + backup-restore)

**Objectif** : Analyser les retours, détecter les anomalies et corriger.

**Outils** :
- `vigilance` — automates d'analyse cyber-vigilance/santé du parc
- `backup-restore` — suivi de la couverture des sauvegardes

**Indicateurs affichés** :
- Nombre de signaux critiques
- Nombre d'avertissements
- Nombre d'appareils sans sauvegarde

**Actions** : Navigation vers les vues détaillées vigilance et backup-restore.

## Mode graphique (diagramme SVG interactif)

### Concept

Le mode graphique offre une **interface de commande visuelle** du cycle agile. Les 5 étapes sont disposées en pentagone avec :
- **Nœuds** : icône + label + indicateur de statut temps réel (point coloré)
- **Flèches animées** : flux continu Décider → Explorer → Déployer → Mesurer → Apprendre → (retour)
- **Interactivité** : clic sur un nœud = navigation vers la vue détaillée de l'étape (bascule en mode classique)

### Fonctionnement

```
┌──────────────────────────────────────────────────────────┐
│  [📋 Classique]  [🔄 Graphique]  ← onglets de bascule   │
├──────────────────────────────────────────────────────────┤
│                                                          │
│         🧭 Décider                                       │
│            ╲                                             │
│             ╲  ← flèche animée                            │
│              ╲                                           │
│            🕸️ Explorer ──── 🚀 Déployer                  │
│                                ╱                         │
│                               ╱                          │
│              🧠 Apprendre ←── 📊 Mesurer                 │
│                                                          │
│  ● OK  ● Attention  ● Critique  ● Inconnu  ← légende    │
└──────────────────────────────────────────────────────────┘
```

### Indicateurs de statut temps réel

Chaque nœud affiche un **point de statut** calculé à partir des données `networkCycleClient.js` :

| Couleur | Signification | Logique |
|---------|---------------|---------|
| 🟢 Vert | OK | Service opérationnel, pas d'anomalie |
| 🟡 Jaune | Attention | Présence d'avertissements ou dégradation partielle |
| 🔴 Rouge | Critique | Service en erreur ou signaux critiques détectés |
| ⚪ Gris | Inconnu | Service non configuré ou pas de données |

**Logique par étape** :
- **Décider** : OK si l'orchestrateur répond
- **Explorer** : OK si capture active, rouge si arrêtée
- **Déployer** : OK si tunnels/cibles opérationnels, warn si erreur sur un tunnel
- **Mesurer** : OK si toutes les cibles en ligne, warn si partielles, rouge si toutes hors ligne
- **Apprendre** : OK si aucun signal critique, warn si warnings, rouge si critiques

### Données temps réel

Le graphique charge **toutes les étapes en parallèle** lors de l'activation du mode graphique (pas de chargement à la demande comme en mode classique). Cela permet d'afficher une vue d'ensemble immédiate de l'état du réseau.

```javascript
// Chargement parallèle de toutes les étapes
useEffect(() => {
  if (viewMode !== "graphique") return;
  const promises = [];
  if (netmapOrchestratorApiBase) {
    promises.push(fetchOrchestratorSummary(...), fetchOrchestratorSuggestions(...));
  }
  // ... etc pour chaque service
  await Promise.all(promises);
}, [viewMode, ...apiBases]);
```

### Navigation depuis le graphique

Clic sur un nœud → `handleNodeClick(stepId)` :
1. Met à jour `step` pour sélectionner l'étape
2. Bascule `viewMode` vers `"classique"` pour afficher le détail

```javascript
function handleNodeClick(stepId) {
  setStep(stepId);
  setViewMode("classique");
}
```

### Position des nœuds (viewBox 800×400)

| Étape | X | Y |
|-------|---|---|
| Décider | 130 | 200 |
| Explorer | 280 | 90 |
| Déployer | 520 | 90 |
| Mesurer | 670 | 200 |
| Apprendre | 400 | 320 |

Les flèches utilisent des courbes de Bézier quadratiques avec un point de contrôle décalé perpendiculairement pour éviter le chevauchement.

### Animation CSS

Les flux sont animés via `stroke-dasharray` + `@keyframes nc-flow` pour un effet de déplacement continu le long des flèches :

```css
.nc-graph-arrow-flow {
  stroke-dasharray: 8 12;
  animation: nc-flow 1.5s linear infinite;
}
@keyframes nc-flow {
  to { stroke-dashoffset: -40; }
}
```

## Flux de données

```
┌─────────────────────────────────────────────────────────────┐
│                    NetworkCycleView                          │
│  ┌──────────────────────┐  ┌──────────────────────────────┐ │
│  │ Mode classique       │  │ Mode graphique               │ │
│  │ (chargement à la     │  │ (chargement parallèle de     │ │
│  │  demande par étape)  │  │  toutes les étapes)          │ │
│  └──────────────────────┘  └──────────────────────────────┘ │
├─────────────────────────────────────────────────────────────┤
│  networkCycleClient.js                                      │
│  ┌─────────────┬─────────────┬─────────────┬──────────────┐ │
│  │ Décider     │ Explorer    │ Déployer    │ Mesurer      │ │
│  │             │             │             │              │ │
│  │ netmap-     │ network-    │ ssh-tunnels │ netprobe     │ │
│  │ orchestr.   │ agent       │ snmp        │              │ │
│  └─────────────┴─────────────┴─────────────┴──────────────┘ │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │ Apprendre                                               │ │
│  │ vigilance   backup-restore                              │ │
│  └─────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

## Configuration

Aucune variable d'environnement supplémentaire requise. La tuile utilise les variables existantes :

- `VITE_NETMAP_ORCHESTRATOR_API_BASE_URL`
- `VITE_NETWORK_AGENT_API_BASE_URL`
- `VITE_NETPROBE_API_BASE_URL`
- `VITE_SNMP_API_BASE_URL`
- `VITE_SSH_TUNNELS_API_BASE_URL`
- `VITE_VIGILANCE_API_BASE_URL`
- `VITE_BACKUP_RESTORE_API_BASE_URL`

Si une variable n'est pas définie, l'étape correspondante affiche un message indiquant que le service n'est pas configuré.

## Conventions respectées

- **TabShell** : La tuile s'intègre dans le système de navigation existant (menu déroulant, viewMode)
- **hub-settings** : Utilise les classes CSS existantes (`hub-settings`, `hub-card`, `hub-settings-section`, etc.)
- **Responsive** : La navigation du cycle est scrollable horizontalement sur les petits écrans
- **Accessibilité** : Boutons avec libellés clairs, indicateurs visuels de couleur accompagnés de texte
- **Performance** : Chargement à la demande en mode classique ; chargement parallèle uniquement à l'activation du graphique
- **Dark theme** : Utilise les variables CSS du thème (`--bg`, `--panel`, `--border`, `--text`, `--muted`, `--accent`)

## Interactions du graphique (livraison #399)

### Zoom et déplacement

Le dessin (flèches + nœuds) vit dans un `<g>` portant
`translate(x y) scale(zoom)`. Le **viewBox ne change jamais** : les marqueurs
de flèche déclarés dans `<defs>` restent donc valables et l'épaisseur du trait
suit naturellement le zoom.

| Geste | Effet |
|---|---|
| Molette | Zoom **ancré sous le curseur** (le point survolé ne bouge pas) |
| Glisser (bouton gauche) | Déplacement |
| `+` / `−` | Zoom centré sur le milieu du viewBox |
| `⟲` | Retour à la vue initiale |

Bornes : `GRAPH_ZOOM_MIN = 0.6`, `GRAPH_ZOOM_MAX = 4`, pas `1.25`.

Trois points de mise en œuvre qui ne sont pas évidents :

1. **Le facteur de zoom est recalculé APRÈS bornage** (`zoomAtPoint`).
   Appliquer le facteur demandé une fois la butée atteinte ferait glisser le
   dessin sous le curseur à chaque cran de molette supplémentaire.
2. **Le déplacement utilise UNE échelle commune aux deux axes**
   (`clientDeltaToViewBox`). `preserveAspectRatio="xMidYMid meet"` n'applique
   qu'une seule échelle, celle du côté le plus contraint : diviser par
   `rect.width` en x et `rect.height` en y ferait dériver le dessin en
   diagonale pendant un glisser horizontal.
3. **Le glisser n'utilise PAS `setPointerCapture`.** La capture redirige aussi
   l'événement `click` vers l'élément capturant, ce qui casserait le clic sur
   un nœud. Les gestionnaires vivent sur `window` le temps du geste, et un
   déplacement de plus de 4 px marque `draggedRef` pour que la fin du glisser
   ne soit pas interprétée comme un clic.

La molette est écoutée en **non passif** (`addEventListener` avec
`{ passive: false }` dans un effet, pas `onWheel`) : React attache ses
gestionnaires au conteneur racine, où `wheel` est passif par défaut, et un
`preventDefault()` y serait ignoré avec un avertissement console.

### Infobulles

Au survol d'un nœud, une infobulle HTML donne le détail de l'étape
(`getStepTooltipLines`) — elle **complète** le texte compact déjà affiché sous
le nœud, elle ne le répète pas. Le contenu n'utilise que des champs déjà
consommés ailleurs dans la vue, jamais un champ d'API supposé.

`.nc-graph-container` étant en `overflow: hidden`, la position est **bornée
côté JS** (`clampTooltipPosition`) et l'infobulle bascule à gauche du curseur
plutôt que de déborder — un débordement serait simplement coupé. Piège déjà
rencontré ailleurs dans le projet (barre d'onglets du hub).

### Rafraîchissement

- `⟳` : rechargement manuel immédiat.
- Case « auto 30s » : rechargement périodique (`GRAPH_REFRESH_MS`).
- Horodatage de la dernière mise à jour à droite de la barre d'outils.

La minuterie n'est armée **que** si l'onglet graphique est affiché ET la
bascule enclenchée ; elle est nettoyée au retour de l'effet, donc jamais de
battement résiduel en mode classique ni après démontage. Le chargement des
données est un `useCallback` unique (`loadGraphData`) partagé par l'activation
de l'onglet et le rafraîchissement — jamais deux copies divergentes de la même
liste d'appels.

## Logique pure et tests

`hub/src/networkCycleGraph.js` — aucun import React, donc testable directement
sous Node. Même motif que `ldapTree.js` (`buildColumns`/`buildTree`).

```bash
node --test hub/tests/networkCycleGraph.test.mjs   # 12 tests
```

Couvre : bornage du zoom (dont `NaN`/`undefined`), immobilité du point
d'ancrage, absence de dérive à la butée, aller-retour zoom avant/arrière,
échelle commune du déplacement, conteneur non mesuré, letterboxing du
`meet`, bornage de l'infobulle sur les quatre bords, et contenu des
infobulles sur données absentes puis réelles.

**Non couvert** (pas de navigateur ici) : rendu visuel, gestes souris et
molette réels.

### Tendances entre deux rafraîchissements (livraison #404)

Rendu possible par le rafraîchissement automatique : les métriques de chaque
étape (`extractStepMetrics` -- mêmes champs que le texte de statut) sont
gardées en mémoire du composant d'un rafraîchissement à l'autre, et comparées
au suivant (`compareMetrics`). Aucun stockage, aucune API : la « période
précédente » est simplement le rafraîchissement précédent (30 s en auto).

- Un marqueur apparaît en haut à droite du nœud quand quelque chose a
  changé : `▼` (au moins une dégradation), `▲` (amélioration seulement),
  `±` (variation neutre, ex. nombre de cibles SNMP).
- L'infobulle détaille chaque variation : `cibles en ligne : 5 → 4 ▼`.
- La polarité de chaque métrique est explicite (`METRIC_POLARITY`) : plus
  de suggestions ouvertes ou de signaux critiques est une dégradation, plus
  de sites découverts ou de tunnels actifs une amélioration.
- Une métrique apparue ou disparue (service qui répond puis ne répond plus)
  n'est pas une variation : ignorée plutôt qu'affichée comme `0 → N`.

Point de mise en œuvre : `graphData` change à chaque réponse d'API
individuelle ; l'effet de comparaison ne dépend donc que de l'horodatage de
fin de rafraîchissement et lit les données via une ref, sinon la
« référence précédente » glisserait à chaque réponse.

## Évolutions possibles

- Notifications en cas de dépassement de seuils
- Export des données du cycle (PDF, CSV)
- Personnalisation de l'ordre des étapes par l'utilisateur
