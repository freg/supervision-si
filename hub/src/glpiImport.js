// Logique pure de la tuile GLPI Inventory (#437) : lignes d'un aperçu
// d'import (créations + mises à jour d'hôtes déjà présents) et libellés
// de la comparaison agents GLPI ↔ agents hôtes. Testée par
// tests/glpiImport.test.mjs.
export const COMPARISON_LABELS = { both: "vu des deux côtés", only_si: "seulement si-agent", only_glpi: "seulement GLPI Agent" };

// Candidats d'un aperçu (dry-run) : `created` toujours, `updated` quand
// l'API a été appelée avec update_existing (objets ; en import réel ce
// sont des chaînes de compte rendu, ignorées ici).
export function previewRows(preview) {
  const created = (preview?.created || []).filter((c) => c && typeof c === "object").map((c) => ({ ...c, action: "créer" }));
  const updated = (preview?.updated || []).filter((u) => u && typeof u === "object")
    .map((u) => ({ ...u, action: `mettre à jour (id ${u.glpi_id}, trouvé par ${u.matched_by})` }));
  return [...created, ...updated];
}

export function dropdownsLabel(row) {
  const d = row?.dropdowns || {};
  return [d.manufacturers_id, d.computermodels_id, d.locations_id].filter(Boolean).join(" / ") || "—";
}

export function describeSiAgent(si) {
  if (!si) return "—";
  return [si.agent_id, si.site, si.online].filter(Boolean).join(" · ");
}

export function describeGlpiAgent(g) {
  if (!g) return "—";
  const parts = [g.version ? `v${g.version}` : "?"];
  if (g.last_contact) parts.push(`contact ${g.last_contact}`);
  if (g.itemtype) parts.push(`${g.itemtype} #${g.items_id}`);
  return parts.join(" · ");
}

export function importResultLine(r) {
  if (!r) return "";
  const bits = [`${r.created?.length || 0} créé(s)`];
  if (r.updated?.length) bits.push(`${r.updated.length} mis à jour`);
  bits.push(`${r.skipped_existing?.length || 0} déjà présent(s)`, `${r.skipped_unselected?.length || 0} non sélectionné(s)`, `${r.errors?.length || 0} erreur(s)`);
  let line = bits.join(", ") + ".";
  if (r.warnings?.length) line += ` ${r.warnings.join(" ; ")}`;
  return line;
}
