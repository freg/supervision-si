// Colonnes des tableaux du hub : largeur à la souris, colonnes masquables,
// réglages mémorisés par utilisateur et par tableau (livraison #698).
//
// Mémorisation : prefs-api (`PUT /preferences?user=` fusionne les clés à plat,
// une clé `table.<id>` par tableau -> aucun tableau n'écrase un autre), plus une
// copie locale (localStorage) pour un affichage immédiat au chargement. Rien
// de bloquant : prefs-api injoignable = réglages gardés localement.
// Parties pures testées par tests/tableLayout.test.mjs.

export const MIN_WIDTH = 40;
export const MAX_WIDTH = 1200;

export const clampWidth = (w) => Math.round(Math.max(MIN_WIDTH, Math.min(MAX_WIDTH, Number(w) || MIN_WIDTH)));

/** Réglages bruts (prefs-api, localStorage, versions anciennes) -> {widths, hidden} ne citant que des colonnes connues. */
export function normalizeLayout(raw, columns) {
  const known = new Map(columns.map((c) => [c.id, c]));
  const widths = {};
  for (const [id, w] of Object.entries((raw && typeof raw === "object" && raw.widths) || {})) {
    if (known.has(id) && Number.isFinite(Number(w))) widths[id] = clampWidth(w);
  }
  const hidden = Array.isArray(raw?.hidden) ? [...new Set(raw.hidden.filter((id) => known.has(id) && !known.get(id).fixed))] : [];
  // jamais toutes les colonnes masquables masquées s'il n'y a pas de colonne fixe
  const visible = columns.filter((c) => !hidden.includes(c.id));
  return { widths, hidden: visible.length ? hidden : [] };
}

export const visibleColumns = (columns, layout) => columns.filter((c) => !layout.hidden.includes(c.id));

export function toggleHidden(layout, columns, id) {
  const col = columns.find((c) => c.id === id);
  if (!col || col.fixed) return layout;
  const hidden = layout.hidden.includes(id) ? layout.hidden.filter((x) => x !== id) : [...layout.hidden, id];
  return normalizeLayout({ ...layout, hidden }, columns);
}

export const setWidth = (layout, id, w) => ({ ...layout, widths: { ...layout.widths, [id]: clampWidth(w) } });

export function resetWidth(layout, id) {
  const widths = { ...layout.widths };
  delete widths[id];
  return { ...layout, widths };
}

export const isDefault = (layout) => !layout.hidden.length && !Object.keys(layout.widths).length;

// ------------------------------------------------------------------ mémorisation

const cfg = { apiBase: "", user: "" };
let accountPrefs = null;           // promesse des préférences du compte (un seul GET)
const timers = {};
const localKey = (id) => `hub.table.${id}`;

/** Appelé une fois par App quand l'utilisateur est connu. */
export function configureTablePrefs({ apiBase, user }) {
  if (cfg.apiBase === (apiBase || "") && cfg.user === (user || "")) return;
  cfg.apiBase = apiBase || ""; cfg.user = user || ""; accountPrefs = null;
}

export function readLocal(id) {
  try { return JSON.parse(localStorage.getItem(localKey(id)) || "null"); } catch { return null; }
}

function writeLocal(id, layout) {
  try { localStorage.setItem(localKey(id), JSON.stringify(layout)); } catch { /* stockage indisponible */ }
}

/** Réglages du compte pour ce tableau (null si inconnus). */
export async function loadAccount(id, fetchImpl = globalThis.fetch) {
  if (!cfg.apiBase || !cfg.user || !fetchImpl) return null;
  if (!accountPrefs) {
    accountPrefs = fetchImpl(`${cfg.apiBase}/preferences?user=${encodeURIComponent(cfg.user)}`)
      .then((r) => (r.ok ? r.json() : {})).catch(() => ({}));
  }
  const all = await accountPrefs;
  return all?.[`table.${id}`] || null;
}

/** Mémorise localement tout de suite, puis dans le compte (regroupé : une écriture par rafale de réglages). */
export function saveLayout(id, layout, fetchImpl = globalThis.fetch, delay = 600) {
  writeLocal(id, layout);
  if (!cfg.apiBase || !cfg.user || !fetchImpl) return;
  clearTimeout(timers[id]);
  timers[id] = setTimeout(() => {
    const body = { [`table.${id}`]: isDefault(layout) ? null : layout };
    fetchImpl(`${cfg.apiBase}/preferences?user=${encodeURIComponent(cfg.user)}`, {
      method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
    }).catch(() => { /* gardé localement */ });
    if (accountPrefs) accountPrefs = accountPrefs.then((all) => ({ ...all, ...body }));
  }, delay);
}
