# network-explorer — frontend autonome, sans Keycloak ni passerelle

Livraison #393. Demandé explicitement, après une première tentative
mal comprise (page HTML statique avec données figées) puis corrigée
par la personne : "un docker front qui se branche sur le/les dockers
api" -- PAS des données statiques, un VRAI frontend qui interroge les
VRAIES API en direct.

## Ce que c'est

Un frontend React/Vite MINIMAL, sans authentification (aucun
`<AuthProvider>`, contrairement à `vault-admin-portal`) et sans
passage par `tls-proxy` -- juste deux tuiles réseau, pour tester
isolément :

- **Agent réseau** (`NetworkAgentView.jsx`) -- appareils, services,
  échanges, filtres profondeur/géographie/volume (#392), et les deux
  visualisations de flux (graphe alluvial, radial tree pondéré, #389).
- **Orchestrateur réseau** (`NetmapOrchestratorView.jsx`) -- suggestions
  d'analyse/supervision (#388-391).

## Réutilisation, jamais un fork

Ces deux vues (+ leurs clients API, leurs sous-composants de
visualisation, leur CSS) sont copiées TELLES QUELLES depuis `hub/src/`
au moment du build (voir `Dockerfile`) -- source CANONIQUE unique,
même motif déjà établi dans ce projet pour `vault-admin-portal`
(`vaultOps.js`/`api.js` copiés depuis `vault/portal`). Toute
correction faite sur l'original du hub se répercute ici
automatiquement au prochain build, jamais une divergence silencieuse
entre deux copies.

Le bouton "◀ Retour" de chaque vue reste visible mais devient un
NO-OP ici (`onBack={() => {}}`) -- ces vues n'ont nulle part où
"retourner" dans ce contexte autonome, jamais modifié dans les
fichiers originaux pour ce cas d'usage secondaire.

## ⚠️ Sécurité -- AUCUNE protection d'accès ici

Contrairement au hub principal (Keycloak) : ce portail n'authentifie
PERSONNE. Il se contente d'appeler les API déjà exposées directement
sur l'hôte (`network-agent-api`, `netmap-orchestrator-api`) -- la
SEULE barrière réelle reste l'accès réseau (LAN) à ces API elles-mêmes.
Même précaution que `vault-admin-portal`/`launcher` -- **jamais routé
par `tls-proxy`** (vérifié absent de
`tls-proxy/render_nginx_conf.py`), jamais exposé au-delà du réseau
local de confiance.

## Configuration

`VITE_NETWORK_AGENT_API_BASE_URL` et
`VITE_NETMAP_ORCHESTRATOR_API_BASE_URL` pointent directement vers les
ports déjà exposés de ces deux API (`NETWORK_AGENT_HOST_PORT`,
`NETMAP_ORCHESTRATOR_API_PORT`) -- jamais via la passerelle.
`NETWORK_EXPLORER_LAN_PORT` (défaut 6126).

## Démarrer

```bash
./scripts/run-all.sh main up -d --build network-explorer
```

(`network-agent-api` et `netmap-orchestrator-api` doivent déjà tourner
-- voir leurs README respectifs.)

## Vérifié / non vérifié

**Vérifié réellement** : syntaxe JSX (`App.jsx`, `main.jsx`), validité
YAML du câblage `docker-compose.yml`. Les vues réutilisées
(`NetworkAgentView.jsx`, `NetmapOrchestratorView.jsx`) sont
elles-mêmes déjà testées séparément (voir `network-agent/README.md`,
`netmap-orchestrator/README.md`) -- rien de nouveau à re-tester côté
logique, seul l'assemblage (imports, câblage des props, absence
d'authentification) est propre à cette livraison.

**Non vérifié dans cet environnement** : `npm install` réel (aucun
`node_modules` construit ici), rendu visuel réel, connexion réelle
aux deux API depuis ce nouveau conteneur.
