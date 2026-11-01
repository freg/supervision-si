// Logique pure du module « Portage PHP → Python » (hub, livraison #650) --
// testée sous Node (hub/tests/portageLib.test.mjs), jamais enfouie dans le .jsx.

export const STEP_LABELS = {
  inventory: "Inventorier (unités, PORT_SPEC)",
  schema: "Schéma mesuré (base)",
  scaffold: "Squelette Flask",
  routes: "Écrans métier",
  install: "Installer le port",
  migrate: "Migrations",
  smoke: "Tests de fumée",
};

// Étapes cochées par défaut selon ce qui est déjà importé : sans dump, pas
// de schéma ni de migrations ni de fumée (ils exigent la base).
export function defaultSteps(files) {
  const all = Object.keys(STEP_LABELS);
  if (!files) return all;
  return all.filter((s) => files.dump || !["schema", "migrate", "smoke"].includes(s));
}

// Résumé des décisions du PORT_SPEC : {total, porter, differe, mort, vide}.
export function summarizeDecisions(units) {
  const r = { total: 0, porter: 0, differe: 0, mort: 0, vide: 0 };
  for (const u of units || []) {
    r.total += 1;
    const d = (u.decision || "").toLowerCase();
    if (!d) r.vide += 1;
    else if (d.includes("pas porter") || d.includes("mort")) r.mort += 1;
    else if (d.includes("diff")) r.differe += 1;
    else r.porter += 1;
  }
  return r;
}

// Lecture du rapport de fumée (smoke.md) : ligne de synthèse + lignes de routes.
export function parseSmoke(text) {
  const routes = [];
  let summary = "";
  for (const line of (text || "").split("\n")) {
    const m = line.match(/^\|\s*`([^`]+)`\s*\|\s*([^|]+?)\s*\|/);
    if (m) routes.push({ route: m[1], status: m[2] });
    else if (line.startsWith("pytest")) summary = line.trim();
  }
  return { summary, routes };
}

export function statusLabel(project) {
  if (!project) return "";
  if (project.running || project.run_status === "running") return "en cours";
  if (project.run_status === "ok") return "terminé";
  if (project.run_status === "failed") return "en échec";
  return "jamais lancé";
}

export function slugify(name) {
  return (name || "").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "") || "projet";
}
