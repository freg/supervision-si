// Logique pure du module Recherche — validation de clauses côté UI,
// parsing des fragments de highlight Elasticsearch. Testable via Node,
// aucune dépendance à import.meta.env.

export const OPERATOR_LABELS = {
  contains: "contient",
  phrase: "phrase exacte",
  equals: "égal à",
  exists: "existe",
  gte: "≥",
  lte: "≤",
};

export function isClauseComplete(clause) {
  if (!clause || !clause.field || !clause.operator) return false;
  if (clause.operator === "exists") return true;
  return clause.value !== undefined && clause.value !== null && clause.value !== "";
}

export function countCompleteClauses(clauses) {
  return (clauses || []).filter(isClauseComplete).length;
}

/** Découpe un fragment de highlight Elasticsearch (délimité par
 * <em>/</em>, les balises par défaut d'ES) en segments {text,
 * emphasized}. JAMAIS destiné à un rendu via dangerouslySetInnerHTML :
 * le contenu source d'un document indexé (PDF/Word arbitraires) n'est
 * pas fiable — seuls les délimiteurs <em>/</em> connus sont traités
 * spécialement ici, tout le reste doit rester du texte simple rendu
 * normalement par React (échappé automatiquement). */
export function parseHighlightFragment(fragment) {
  if (typeof fragment !== "string" || fragment === "") return [];
  const parts = fragment.split(/(<em>|<\/em>)/);
  const segments = [];
  let emphasized = false;
  for (const part of parts) {
    if (part === "<em>") {
      emphasized = true;
      continue;
    }
    if (part === "</em>") {
      emphasized = false;
      continue;
    }
    if (part === "") continue;
    segments.push({ text: part, emphasized });
  }
  return segments;
}

/** Premier fragment de highlight exploitable, tous champs confondus
 * (l'ordre des clés d'un objet JS suit l'ordre d'insertion — celui
 * renvoyé par le backend, lui-même celui d'Elasticsearch). null si
 * aucun highlight disponible pour ce résultat. */
export function firstHighlightFragment(highlight) {
  if (!highlight || typeof highlight !== "object") return null;
  for (const fragments of Object.values(highlight)) {
    if (Array.isArray(fragments) && fragments.length > 0) return fragments[0];
  }
  return null;
}
