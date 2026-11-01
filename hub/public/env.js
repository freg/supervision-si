// #736 : configuration d'exécution du hub. Remplacé au démarrage du conteneur (write-env.mjs) quand le hub est
// pré-compilé dans l'image ; vide en développement ou en compilation au démarrage (les VITE_* sont alors figés).
window.__HUB_ENV__ = window.__HUB_ENV__ || {};
