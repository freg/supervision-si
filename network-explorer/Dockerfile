FROM node:20-slim

WORKDIR /app

COPY network-explorer/package.json .
RUN npm install

COPY network-explorer/ .

# Réutilisation TELLE QUELLE des vues déjà construites pour le hub
# (livraison #393, demandé explicitement : "un docker front qui se
# branche sur le/les dockers api") -- JAMAIS forkées/dupliquées ici :
# source CANONIQUE = hub/src, même motif déjà établi dans ce projet
# pour vault-admin-portal (vaultOps.js/api.js copiés depuis
# vault/portal, voir son Dockerfile) -- toute correction faite sur
# l'original se répercute ici automatiquement au prochain build,
# jamais une divergence silencieuse entre deux copies.
COPY hub/src/NetworkAgentView.jsx src/NetworkAgentView.jsx
COPY hub/src/NetmapOrchestratorView.jsx src/NetmapOrchestratorView.jsx
COPY hub/src/networkAgentClient.js src/networkAgentClient.js
COPY hub/src/networkAgentHistory.js src/networkAgentHistory.js
COPY hub/src/netmapOrchestratorClient.js src/netmapOrchestratorClient.js
COPY hub/src/classifierClient.js src/classifierClient.js
COPY hub/src/alluvialLayout.js src/alluvialLayout.js
COPY hub/src/weightedRadialLayout.js src/weightedRadialLayout.js
COPY hub/src/components/AlluvialFlowChart.jsx src/components/AlluvialFlowChart.jsx
COPY hub/src/components/WeightedRadialTree.jsx src/components/WeightedRadialTree.jsx
# Livraisons #412/#413 -- filtres des flux, zoom et échelle des graphiques.
# Piège documenté (#402) : un nouvel import dans NetworkAgentView.jsx sans
# sa ligne COPY ici casse le build de CE conteneur, pas celui du hub.
COPY hub/src/networkFlowFilters.js src/networkFlowFilters.js
COPY hub/src/chartZoom.js src/chartZoom.js
COPY hub/src/chartScales.js src/chartScales.js
COPY hub/src/components/ZoomableChart.jsx src/components/ZoomableChart.jsx
COPY hub/src/hub.css src/hub.css
# #737 : colonnes réglables (#707) importées par NetmapOrchestratorView -- absentes depuis #707 (la vue cassait au chargement)
COPY hub/src/TableColumns.jsx src/TableColumns.jsx
COPY hub/src/tableLayout.js src/tableLayout.js
COPY shared/theme.css src/theme.css

# #737 : pré-compilé dans l'image (configuration lue à l'exécution dans env.js) et servi statiquement ;
# FRONT_MODE=dev pour l'ancien serveur de développement Vite. Échec de la compilation : repli sur ce serveur.
COPY shared/front/serve.mjs /app/front-serve.mjs
COPY shared/front/write-env.mjs /app/front-write-env.mjs
COPY shared/front/entrypoint.sh /app/front-entrypoint.sh
ENV FRONT_BASE=/
RUN FRONT_RUNTIME_ENV=1 NODE_OPTIONS=--max-old-space-size=1536 npx vite build --logLevel warn --outDir dist-prebuilt \
    || (echo "front : pré-compilation échouée, serveur de développement au démarrage" && rm -rf dist-prebuilt)
EXPOSE 5173
CMD ["sh", "/app/front-entrypoint.sh"]
