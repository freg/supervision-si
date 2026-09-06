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

## Évolutions possibles

- Rafraîchissement automatique des données du graphique (polling)
- Zoom/pan sur le diagramme SVG
- Affichage de tooltips détaillés au survol des nœuds
- Ajout d'indicateurs de tendance (comparaison avec la période précédente)
- Notifications en cas de dépassement de seuils
- Export des données du cycle (PDF, CSV)
- Personnalisation de l'ordre des étapes par l'utilisateur
