// Logique pure de la section « Parcours applicatifs » (#441) : résumé d'une
// étape, matrice écrans × tables, libellés. Testée par tests/retroJourneys.test.mjs.
export const STATUS_LABELS = { recording: "en cours", done: "terminé" };

export function stepTitle(step) {
  if (!step) return "";
  if (step.kind === "mark") return `⚑ ${step.label || "repère"}`;
  const method = step.method && step.method !== "GET" ? `${step.method} ` : "";
  return `${method}${step.path || step.url || "?"}${step.title ? ` — ${step.title}` : ""}`;
}

export function stepSummary(step) {
  const actions = step?.actions || [];
  const count = (k) => actions.filter((a) => a.kind === k).length;
  const requests = step?.requests || [];
  const parts = [];
  if (count("click")) parts.push(`${count("click")} clic(s)`);
  const inputs = (step?.inputs || []).length;
  if (inputs) parts.push(`${inputs} saisie(s)`);
  if (count("submit")) parts.push(`${count("submit")} envoi(s)`);
  const xhr = requests.filter((r) => !r.page).length;
  if (xhr) parts.push(`${xhr} requête(s) secondaire(s)`);
  const q = (step?.queries || []).length;
  if (q) parts.push(`${q} requête(s) SQL`);
  return parts.join(", ") || "—";
}

// Matrice écrans × tables : { tables: [...], rows: [{screen, cells: {table: "code"|"db"|"both"|null}}] }
export function screensByTables(map) {
  const screens = map?.screens || [];
  const tables = Object.keys(map?.tables || {}).sort();
  const rows = screens.map((s) => {
    const cells = {};
    for (const t of tables) {
      const code = !!(s.code_tables && s.code_tables[t]);
      const db = !!(s.db_tables && s.db_tables[t]);
      cells[t] = code && db ? "both" : code ? "code" : db ? "db" : null;
    }
    return { screen: s.screen, route: s.route, cells };
  });
  return { tables, rows };
}

export function dbTablesLabel(dbTables) {
  return Object.entries(dbTables || {}).map(([t, e]) => `${t} (${e.reads || 0}r/${e.writes || 0}w)`).join(", ") || "—";
}

export function relayCommand(centralBase, tokenConfigured) {
  const central = centralBase || "https://<VM>:6443/api/retro";
  return `python3 relay.py --central ${central} --token <RETRO_RELAY_TOKEN${tokenConfigured ? "" : " — à définir dans .env"}> --ca ca.crt`;
}
