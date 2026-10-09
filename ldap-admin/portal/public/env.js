// #737 : configuration d'exécution du front. Remplacé au démarrage du conteneur (front-write-env.mjs) quand le front
// est pré-compilé dans l'image ; vide en développement (les VITE_* sont alors lus par Vite).
window.__HUB_ENV__ = window.__HUB_ENV__ || {};
