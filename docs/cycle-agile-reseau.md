# Cycle agile réseau

## Vue d'ensemble

Le cycle agile réseau est une tuile hub qui regroupe les outils de supervision réseau du projet en un parcours en 5 étapes : **Décider → Explorer → Déployer → Mesurer → Apprendre**.

Chaque étape donne accès aux outils existants du projet ou résume leur état, permettant une navigation fluide entre les différentes phases du cycle.

## Architecture

### Fichiers

| Fichier | Rôle |
|---------|------|
| `hub/src/NetworkCycleView.jsx` | Composant principal — panneau central avec navigation entre les étapes |
| `hub/src/networkCycleClient.js` | Client API — agrège les appels vers les services réseau |
| `hub/src/hub.css` | Styles CSS pour la navigation du cycle et les KPI |
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

## Flux de données

```
┌─────────────────────────────────────────────────────────────┐
│                    NetworkCycleView                         │
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
- **Performance** : Chargement à la demande — chaque étape ne charge ses données qu'à la sélection

## Évolutions possibles

- Ajout d'indicateurs de tendance (comparaison avec la période précédente)
- Notifications en cas de dépassement de seuils
- Export des données du cycle (PDF, CSV)
- Personnalisation de l'ordre des étapes par l'utilisateur
