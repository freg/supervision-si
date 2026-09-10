// Logique pure de l'application générée (#444) : écrans de navigation,
// colonnes affichables d'une liste, valeurs d'un formulaire, filtrage.
// Testée par tests/generatedApp.test.mjs.
export function navScreens(spec) {
  return (spec?.screens || []).filter((s) => s.nav && !s.hidden);
}

// Colonnes à afficher pour une liste : celles rattachées à une colonne réelle, sinon les colonnes de la table.
export function listColumns(screen, tableColumns) {
  const mapped = (screen?.columns || []).filter((c) => c.column);
  if (mapped.length) return mapped.map((c) => ({ label: c.label, column: c.column }));
  return (tableColumns || []).slice(0, 8).map((c) => ({ label: c, column: c }));
}

// Écran de fiche/formulaire associé à une liste : même table, genre form ou detail.
export function formScreenFor(spec, listScreen) {
  if (!listScreen?.table) return null;
  return (spec?.screens || []).find((s) => s.id !== listScreen.id && s.table === listScreen.table && (s.kind === "form" || s.kind === "detail")) || null;
}

// Champs éditables d'un formulaire : rattachés à une colonne, jamais la clé primaire.
export function editableFields(screen) {
  return (screen?.fields || []).filter((f) => f.column && f.column !== screen.pk);
}

// Champs d'un formulaire sans colonne dans cette application (#445 : outil unique projeté).
export function missingFields(screen) {
  return (screen?.fields || []).filter((f) => !f.column);
}

export function rowToValues(columns, row) {
  const out = {};
  (columns || []).forEach((c, i) => { out[c] = row?.[i]; });
  return out;
}

export function filterRows(rows, columns, needle) {
  const n = (needle || "").trim().toLowerCase();
  if (!n) return rows;
  return (rows || []).filter((r) => r.some((v) => v != null && String(v).toLowerCase().includes(n)));
}

export function specSummary(spec) {
  if (!spec) return "";
  const c = spec.counts || {};
  return `${c.screens || 0} écran(s), ${c.nav || 0} dans la navigation, ${c.with_table || 0} rattaché(s) à une table, ${c.todo || 0} point(s) à compléter`;
}
