// Ordre des listes du hub (#742) -- trois ordres pour toutes les listes, choisis par l'utilisateur et
// mémorisés par liste (ce navigateur) :
//   « alpha »    : alphabétique (défaut des inventaires : agents, sondes, équipements…) ;
//   « recent »   : antéchronologique (défaut des journaux : événements, constats, alertes) ;
//   « severity » : gravité d'abord (critique, avertissement, info / ok, inconnu), puis alphabétique.
// Pur et testé (tests/listOrder.test.mjs) ; le sélecteur est dans ListOrder.jsx.

export const ORDER_MODES = [
  { id: "alpha", label: "A → Z", title: "Ordre alphabétique" },
  { id: "recent", label: "Récent", title: "Du plus récent au plus ancien" },
  { id: "severity", label: "Gravité", title: "Le plus grave d'abord" },
];

// Vocabulaires de gravité rencontrés dans le hub, ramenés à un rang (0 = le plus grave).
const SEVERITY_RANK = {
  critical: 0, crit: 0, critique: 0, fatal: 0, emergency: 0, alert: 0, down: 0, bad: 0, error: 1, err: 1, erreur: 1, high: 1,
  warning: 2, warn: 2, avertissement: 2, medium: 2, degraded: 2,
  notice: 3, info: 3, low: 3, unknown: 4, inconnu: 4, ok: 5, good: 5, up: 5, none: 5,
};

export function severityRank(value) {
  if (value == null || value === "") return 4;
  if (typeof value === "number") return value;
  const r = SEVERITY_RANK[String(value).trim().toLowerCase()];
  return r == null ? 4 : r;
}

export function timeValue(value) {
  if (value == null || value === "") return null;
  if (typeof value === "number") return value > 1e12 ? value : value * 1000;   // epoch s ou ms
  const t = Date.parse(value);
  return Number.isNaN(t) ? null : t;
}

const collator = typeof Intl !== "undefined" ? new Intl.Collator("fr", { sensitivity: "base", numeric: true }) : null;
export function compareText(a, b) {
  const x = a == null ? "" : String(a), y = b == null ? "" : String(b);
  if (!x && y) return 1;            // les vides à la fin
  if (x && !y) return -1;
  return collator ? collator.compare(x, y) : x.localeCompare(y);
}

/**
 * Trie `items` (copie) selon `mode`.
 * acc = { name: item => texte, date: item => date ISO / epoch, severity: item => gravité ou rang, tie: item => texte }
 */
export function orderItems(items, mode = "alpha", acc = {}) {
  const name = acc.name || ((i) => i?.name ?? i?.label ?? i?.id);
  const date = acc.date || ((i) => i?.at ?? i?.updated_at ?? i?.created_at);
  const sev = acc.severity || ((i) => i?.severity ?? i?.state);
  const byName = (x, y) => compareText(name(x), name(y)) || compareText(acc.tie?.(x), acc.tie?.(y));
  const byDate = (x, y) => {
    const tx = timeValue(date(x)), ty = timeValue(date(y));
    if (tx == null && ty == null) return 0;
    if (tx == null) return 1;
    if (ty == null) return -1;
    return ty - tx;
  };
  const cmp = mode === "recent" ? (x, y) => byDate(x, y) || byName(x, y)
    : mode === "severity" ? (x, y) => severityRank(sev(x)) - severityRank(sev(y)) || byDate(x, y) || byName(x, y)
      : byName;
  return [...(items || [])].sort(cmp);
}

export function validMode(mode, fallback = "alpha") {
  return ORDER_MODES.some((m) => m.id === mode) ? mode : fallback;
}

const KEY = "hub.listOrder.";
export function loadOrder(listId, fallback = "alpha") {
  try {
    return validMode(window.localStorage.getItem(KEY + listId), fallback);
  } catch (e) {
    return fallback;
  }
}
export function saveOrder(listId, mode) {
  try { window.localStorage.setItem(KEY + listId, mode); } catch (e) { /* stockage indisponible : ordre non mémorisé */ }
}
