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

// #443 : arbre des parcours (parents puis enfants, indentés) ; les enfants sans parent visible restent à plat.
export function journeyTree(journeys) {
  const byParent = new Map();
  const ids = new Set((journeys || []).map((j) => j.id));
  for (const j of journeys || []) {
    const p = j.parent_id && ids.has(j.parent_id) ? j.parent_id : null;
    if (!byParent.has(p)) byParent.set(p, []);
    byParent.get(p).push(j);
  }
  const out = [];
  const walk = (parent, depth) => {
    for (const j of byParent.get(parent) || []) { out.push({ ...j, depth }); walk(j.id, depth + 1); }
  };
  walk(null, 0);
  return out;
}

// Fil d'Ariane textuel d'une étape pour le mode « rejouer pas à pas » (storyboard).
export function storyboardFrame(step) {
  if (!step) return null;
  const dom = step.dom || {};
  return {
    title: stepTitle(step),
    headings: dom.headings || [],
    forms: (dom.forms || []).map((f) => ({ action: f.action, method: (f.method || "get").toUpperCase(), fields: (f.fields || []).map((x) => ({ name: x.name, type: x.type, label: x.label })) })),
    tables: (dom.tables || []).map((t) => ({ headers: t.headers || [], rows: t.rows })),
    links: dom.links_count,
    actions: (step.actions || []).map((a) => `${a.kind}${a.text ? ` « ${a.text} »` : a.field ? ` ${a.field}` : ""}`),
    replay: step.replay || [],
    queries: (step.queries || []).map((q) => `${q.kind} ${q.tables.join(", ")}`),
  };
}
