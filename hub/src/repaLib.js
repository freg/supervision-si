// Logique pure de l'assistant de rapatriement (#761) : navigation entre étapes, conditions pour « Suivant »,
// position du curseur sur le synoptique, résumé du bilan.

export const STEP_IDS = ["inventaire", "preparation", "rapatriement", "verification", "nettoyage", "bilan"];

/** Ce qui empêche de passer à l'étape suivante (message) ou null. */
export function blocker(c) {
  if (!c) return "campagne non chargée";
  const sel = (c.guests || []).filter((g) => g.decision === "rapatrier");
  switch (c.step) {
    case "inventaire": return (c.guests || []).some((g) => g.decision) ? null : "décider du sort d'au moins un CT / VM";
    case "preparation": {
      const ko = (c.checks || []).filter((k) => !k.ok);
      return ko.length ? `contrôle à régler : ${ko[0].label}` : null;
    }
    case "rapatriement": return sel.length && sel.every((g) => ["validate", "destroy", "done", "diff"].includes(g.phase)) ? null : "exports encore en cours";
    case "verification": return sel.every((g) => ["destroy", "done"].includes(g.phase) || g.phase === "aborted") ? null : "copies à valider (ou à abandonner)";
    case "nettoyage": return sel.every((g) => ["done", "aborted"].includes(g.phase)) ? null : "destructions encore en attente (plage horaire)";
    default: return "dernière étape";
  }
}

export const nextStep = (s) => STEP_IDS[Math.min(STEP_IDS.length - 1, STEP_IDS.indexOf(s) + 1)];
export const prevStep = (s) => STEP_IDS[Math.max(0, STEP_IDS.indexOf(s) - 1)];
/** Le passage Préparation -> Rapatriement lance les plans : seul retour possible ensuite, la consultation. */
export const launchesOnNext = (s) => s === "preparation";

/** Position (0..1) du curseur sur le bandeau : centre de l'étape courante ; et remplissage = avancement global. */
export function cursor(c) {
  const i = Math.max(0, STEP_IDS.indexOf(c?.step || "inventaire"));
  return { index: i, x: (i + 0.5) / STEP_IDS.length, fill: Math.min(1, Math.max(0, (c?.progress?.percent || 0) / 100)) };
}

export function summary(c) {
  const g = c?.guests || [];
  const by = (d) => g.filter((x) => x.decision === d);
  const done = by("rapatrier").filter((x) => x.phase === "done");
  return { rapatrier: by("rapatrier").length, garder: by("garder").length, supprimer: by("supprimer").length, done: done.length,
    freed: done.reduce((s, x) => s + (x.size || 0), 0), failed: by("rapatrier").filter((x) => ["failed", "diff", "aborted"].includes(x.phase)).length };
}
