// Détection et assainissement HTML (livraison #214, backlog item 7).
// Contexte donné par la personne : tickets d'anciennes gestions
// (importés en dump MySQL dans DBA) rédigés en HTML, affichés tels
// quels aujourd'hui (balises brutes), illisibles en l'état.
//
// ⚠️ Assainissement VOLONTAIREMENT LÉGER, fait main -- npm est
// inaccessible dans cet environnement de développement (tenté
// `npm install dompurify`, 403 même en simple consultation via
// `npm view`), donc pas de bibliothèque de référence (DOMPurify)
// éprouvée disponible ici. Proportionné au contexte réel : données
// INTERNES déjà importées dans la propre base de la personne (pas du
// contenu externe non fiable soumis par des tiers), affichées
// uniquement à elle-même dans son propre outil d'administration --
// pas une défense contre un contenu réellement hostile. Si ce
// contenu pouvait un jour provenir d'une source moins fiable,
// remplacer par une vraie bibliothèque d'assainissement, jamais
// étendre cette fonction ad hoc pour ce cas-là.

const HTML_TAG_PATTERN = /<\/?[a-z][a-z0-9]*(\s[^<>]*)?\/?>/i;

export function looksLikeHtml(value) {
  if (typeof value !== "string" || !value) return false;
  return HTML_TAG_PATTERN.test(value);
}

export function sanitizeHtml(html) {
  if (typeof html !== "string") return "";
  let clean = html;
  // Balises <script>...</script> et <style>...</style> retirées ENTIÈREMENT
  // (contenu compris), jamais juste les balises ouvrantes/fermantes.
  clean = clean.replace(/<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi, "");
  clean = clean.replace(/<style\b[^<]*(?:(?!<\/style>)<[^<]*)*<\/style>/gi, "");
  // <iframe>, <object>, <embed> -- capacité d'exécution/intégration
  // externe, jamais utile pour du contenu de ticket.
  clean = clean.replace(/<iframe\b[^>]*>[\s\S]*?<\/iframe>/gi, "");
  clean = clean.replace(/<(object|embed)\b[^>]*>[\s\S]*?<\/\1>/gi, "");
  // Attributs on* (onclick, onerror, onload...) -- gestionnaires
  // d'évènements JS inline, quel que soit l'élément qui les porte.
  clean = clean.replace(/\s+on[a-z]+\s*=\s*(".*?"|'.*?'|[^\s>]+)/gi, "");
  // href/src pointant vers javascript: -- neutralisé plutôt que retiré
  // (garde la structure du lien visible, juste rendu inerte).
  clean = clean.replace(/(href|src)(\s*=\s*)(["'])\s*javascript:[^"']*\3/gi, '$1$2$3#$3');
  return clean;
}
