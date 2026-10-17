// Tuile « Latence des IP publiques » (livraison #775) -- logique PURE, testée sous Node (hub/tests/latencyLib.test.mjs).
// Données : si-agent-api GET /latency (cibles, points de mesure, cellules cible × point, états des points).

export const MODES = [["agent", "agent en place (mesure lui-même)"], ["direct", "connexion directe (compte + sudo)"], ["indirect", "connexion par rebond"]];
export const LEVEL_TONE = { ok: "ok", warning: "warning", critical: "critical" };

export const fmtMs = (v) => (v == null ? "—" : v >= 1000 ? `${(v / 1000).toFixed(1)} s` : `${Math.round(v)} ms`);

export function cell(view, tid, pid) {
  return view?.cells?.[`${tid}|${pid}`] || null;
}

/** Cibles groupées (groupe, puis libellé) -> [{grp, targets}]. */
export function groups(targets) {
  const m = new Map();
  [...(targets || [])].sort((a, b) => (a.grp || "").localeCompare(b.grp || "") || (a.label || "").localeCompare(b.label || ""))
    .forEach((t) => { const g = t.grp || "sans groupe"; if (!m.has(g)) m.set(g, []); m.get(g).push(t); });
  return [...m].map(([grp, ts]) => ({ grp, targets: ts }));
}

/** Points visibles pour une cible (un point limité à certaines cibles ne s'affiche que pour elles). */
export const pointsFor = (points, tid) => (points || []).filter((p) => !p.targets?.length || p.targets.includes(tid));

export function pointLabel(p) {
  if (!p) return "";
  if (p.mode === "agent") return `${p.label} (agent ${p.agent})`;
  return `${p.label} (${p.login}@${p.host}${p.port && p.port !== 22 ? `:${p.port}` : ""}${p.jump ? ` par ${p.jump}` : ""}${p.sudo ? ", sudo" : ""} depuis ${p.agent})`;
}

/** Pire niveau des cellules d'une cible. */
export function worst(view, tid) {
  const order = { critical: 3, warning: 2, ok: 1 };
  let w = null;
  (view?.points || []).forEach((p) => { const c = cell(view, tid, p.id); if (c && (!w || order[c.level] > order[w])) w = c.level; });
  return w;
}

export function counts(view) {
  const c = { ok: 0, warning: 0, critical: 0, none: 0 };
  (view?.targets || []).forEach((t) => { const w = worst(view, t.id); c[w || "none"] += 1; });
  return c;
}

/** Commande pour préparer un accès direct / indirect : poser la clé de l'agent exécutant dans le compte de connexion. */
export function accessCommand(p) {
  if (!p || p.mode === "agent") return "";
  const k = `K=$(ssh root@${p.agent} 'cat /root/.ssh/id_ed25519.pub 2>/dev/null || cat /root/.ssh/id_rsa.pub')`;
  const j = p.jump ? `-J ${p.jump} ` : "";
  const port = p.port && p.port !== 22 ? `-p ${p.port} ` : "";
  return `${k} && ssh -t ${port}${j}${p.login}@${p.host} "mkdir -p ~/.ssh && chmod 700 ~/.ssh && touch ~/.ssh/authorized_keys && (grep -qxF \\"$K\\" ~/.ssh/authorized_keys || echo \\"$K\\" >> ~/.ssh/authorized_keys) && chmod 600 ~/.ssh/authorized_keys && echo cle posee"`;
}

export const emptyTarget = () => ({ id: "", label: "", ip: "", ports: "443", names: "", grp: "", enabled: true, notes: "" });
export const emptyPoint = (login = "francois") => ({ id: "", label: "", mode: "direct", agent: "", login, host: "", port: 22, jump: "", sudo: true, key: "", targets: [], enabled: true, notes: "" });

export const targetToForm = (t) => ({ ...t, ports: (t.ports || []).join(", "), names: (t.names || []).join(", ") });
export const formToTarget = (f) => ({ ...f, ports: String(f.ports || "").split(/[\s,;]+/).filter(Boolean).map(Number), names: String(f.names || "").split(/[\s,;]+/).filter(Boolean) });
export const formToPoint = (f) => ({ ...f, port: Number(f.port) || 22, targets: Array.isArray(f.targets) ? f.targets : String(f.targets || "").split(/[\s,;]+/).filter(Boolean) });

export function parseConfig(text) {
  let c;
  try { c = JSON.parse(text); } catch (e) { return { config: null, error: `JSON invalide : ${e.message}` }; }
  if (!c || typeof c !== "object" || (!Array.isArray(c.targets) && !Array.isArray(c.points))) return { config: null, error: "attendu : {targets: [...], points: [...], settings: {...}}" };
  return { config: c, error: null };
}

/** Série de la sparkline (24 h) -> points SVG normalisés. */
export function sparkPoints(series, key, w = 120, h = 24) {
  const vals = (series || []).map((s) => s[key]).filter((v) => v != null);
  if (vals.length < 2) return "";
  const max = Math.max(...vals), min = Math.min(...vals), span = max - min || 1;
  const pts = (series || []).filter((s) => s[key] != null);
  return pts.map((s, i) => `${Math.round((i * w) / (pts.length - 1))},${Math.round(h - ((s[key] - min) * h) / span)}`).join(" ");
}
