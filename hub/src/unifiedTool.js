// Logique pure de l'outil unique (#445, phase 3) : matrice fonctions ×
// applications à partir de la comparaison, origine des champs, résumé.
// Testée par tests/unifiedTool.test.mjs.

// Lignes de la matrice : une par fonction (groupe), puis une par écran
// propre à une application ; une cellule par application.
export function functionMatrix(comparison) {
  if (!comparison) return [];
  const apps = comparison.apps || [];
  const rows = (comparison.groups || []).map((g) => ({
    function: g.function, kind: g.kind, score: g.score, why: g.why || [], shared: g.apps.length === apps.length,
    cells: Object.fromEntries(apps.map((a) => [a, g.screens.find((s) => s.app === a) || null])),
    common: g.common_fields || [], specific: g.specific_fields || {},
  }));
  for (const u of comparison.unique || []) {
    rows.push({ function: u.title || u.id, kind: u.kind, score: null, why: [`propre à ${u.app}`], shared: false,
      cells: Object.fromEntries(apps.map((a) => [a, a === u.app ? u : null])), common: [], specific: {} });
  }
  return rows;
}

// Libellé d'origine d'un champ ou d'une colonne unifiés.
export function fieldOrigin(field, apps) {
  const n = (field?.apps || []).length;
  if (!n) return "";
  if (apps && n === apps.length) return "commun";
  return `propre à ${field.apps.join(", ")}`;
}

// « table.colonne » d'un champ unifié pour une application, ou null.
export function sourceLabel(field, app) {
  const s = field?.sources?.[app];
  if (!s) return null;
  return s.column ? `${s.table || "?"}.${s.column}` : `${s.table || "?"} (colonne inconnue)`;
}

export function unifiedSummary(uni) {
  if (!uni) return "";
  const c = uni.counts || {};
  return `${c.screens || 0} écran(s) : ${c.shared || 0} commun(s) à toutes, ${c.partial || 0} partagé(s) par certaines, ${c.unique || 0} propre(s) à une application`;
}

// Applications cochables : au moins deux pour comparer.
export function canCompare(selected) {
  return (selected || []).length >= 2;
}

// Pourcentage de recouvrement fonctionnel entre deux applications de la comparaison.
export function coverage(comparison, a, b) {
  if (!comparison || a === b) return null;
  const shared = (comparison.groups || []).filter((g) => g.apps.includes(a) && g.apps.includes(b)).length;
  const total = Math.min(comparison.counts?.screens?.[a] || 0, comparison.counts?.screens?.[b] || 0);
  return total ? Math.round((100 * shared) / total) : 0;
}
