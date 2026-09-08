// Logique PURE de l'onglet « Sauvegardes du hub » (livraison #459) --
// testée sous Node (hub/tests/hubBackups.test.mjs). Présentation du
// catalogue de sessions à la manière d'ARCserve : chaînes totale ->
// incrémentales, point de restauration choisi = la session et tout ce
// qui la précède dans sa chaîne.

export function fmtSize(b) {
  const n = Number(b) || 0;
  if (n < 1024) return `${n} o`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(0)} Ko`;
  if (n < 1024 * 1024 * 1024) return `${(n / 1024 / 1024).toFixed(1)} Mo`;
  return `${(n / 1024 / 1024 / 1024).toFixed(2)} Go`;
}

export const KIND_LABEL = { full: "totale", incremental: "incrémentale" };

// Point de restauration : pour une session, la liste ordonnée des archives
// à rejouer (totale puis incrémentales jusqu'à elle).
export function restorePoint(chain, sessionName) {
  if (!chain) return [];
  const members = (chain.full ? [chain.full] : []).concat(chain.increments || []);
  const idx = members.findIndex((m) => m.name === sessionName);
  return idx < 0 ? [] : members.slice(0, idx + 1);
}

// Résumé d'une chaîne pour l'en-tête d'un bloc.
export function chainSummary(chain) {
  const n = chain.increments?.length || 0;
  return `${chain.full ? "totale" : "sans totale (orphelines)"}${n ? ` + ${n} incrémentale${n > 1 ? "s" : ""}` : ""} · ${fmtSize(chain.size)}`;
}

// Prochaine échéance lisible d'après la planification.
export function scheduleText(schedule) {
  if (!schedule) return "manuelle";
  const parts = [];
  if (schedule.incremental_every_hours > 0) parts.push(`incrémentale toutes les ${schedule.incremental_every_hours} h`);
  if (schedule.full_weekday != null) parts.push(`totale le ${["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"][schedule.full_weekday] || "?"} à ${schedule.full_hour}h`);
  return parts.length ? parts.join(", ") : "manuelle";
}

// Dernier run lisible.
export function lastRunText(last) {
  if (!last) return "aucune exécution depuis le démarrage du service";
  return `${KIND_LABEL[last.kind] || last.kind} ${last.rc === 0 ? "réussie" : "ÉCHOUÉE"} (${last.ended_at || "?"})`;
}
