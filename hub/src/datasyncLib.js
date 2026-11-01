// Logique pure du module « Synchronisation centrale » (hub, #652) -- testée sous Node.

export function presenceBadge(s) {
  if (!s || s.presence === "jamais") return { label: "jamais vue", cls: "ds-muted" };
  if (s.presence === "present") return { label: `présente (il y a ${fmtAge(s.ping_age_s)})`, cls: "ds-ok" };
  return { label: `absente (dernier signe il y a ${fmtAge(s.ping_age_s)})`, cls: "ds-ko" };
}

export function fmtAge(sec) {
  if (sec === null || sec === undefined) return "—";
  if (sec < 60) return `${sec} s`;
  if (sec < 3600) return `${Math.round(sec / 60)} min`;
  if (sec < 86400) return `${Math.round(sec / 3600)} h`;
  return `${Math.round(sec / 86400)} j`;
}

// Statistiques agrégées d'une source : lignes, lots, erreurs, dernier lot.
export function sourceStats(s) {
  const t = s.tables || [];
  return { rows: t.reduce((a, x) => a + (x.rows || 0), 0), batches: t.reduce((a, x) => a + (x.batches || 0), 0),
    errors: t.reduce((a, x) => a + (x.errors || 0), 0), last: t.map((x) => x.last_batch_at || "").sort().reverse()[0] || "" };
}

// Configuration du connecteur à copier (sans mot de passe de base : la personne le renseigne).
export function connectorConfig(central, token, source) {
  return JSON.stringify({ central, token: token || "<jeton>", verify_tls: true,
    db: { driver: source?.kind || "mysql", host: "localhost", port: source?.kind === "postgres" ? 5432 : 3306, user: "lecture", password: "", name: "application" },
    tables: [{ name: "table1", pk: "id", watermark: "last_update" }, { name: "table2", pk: "id" }], interval_s: 300, ping_s: 60, batch: 500 }, null, 2);
}

// Liens groupés pour l'affichage : par kind puis statut.
export function groupLinks(links) {
  const g = { field: { proposed: [], confirmed: [], rejected: [] }, relation: { proposed: [], confirmed: [], rejected: [] } };
  for (const l of links || []) if (g[l.kind] && g[l.kind][l.status]) g[l.kind][l.status].push(l);
  return g;
}

// Valeurs d'une ligne pour un rendu compact : {k: v} -> "k: v · k2: v2" (texte tronqué).
export function rowSummary(row, max = 6) {
  return Object.entries(row || {}).filter(([, v]) => v !== null && v !== "").slice(0, max).map(([k, v]) => `${k}: ${String(v).slice(0, 40)}`).join(" · ");
}

// Nœuds d'une recherche relationnelle regroupés par niveau puis par source/table.
export function groupNodes(nodes) {
  const out = {};
  for (const n of nodes || []) { const k = `${n.level}|${n.source}|${n.table}`; (out[k] = out[k] || { level: n.level, source: n.source, table: n.table, rows: [] }).rows.push(n); }
  return Object.values(out).sort((a, b) => a.level - b.level || a.source.localeCompare(b.source) || a.table.localeCompare(b.table));
}
