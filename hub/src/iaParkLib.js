// Logique pure de la tuile « Parc IA » (#756) : synthèse des évaluations par modèle, activité, gestes encadrés.

export const scoreTone = (s) => (s == null ? "neutral" : s >= 0.8 ? "good" : s >= 0.5 ? "warning" : "critical");

/** Meilleur passage et dernier passage par modèle (rapports du plus récent au plus ancien). */
export function byModel(reports) {
  const out = {};
  for (const r of reports || []) {
    const k = `${r.model || "?"} @ ${r.base_url || "?"}`;
    const m = out[k] || (out[k] = { key: k, model: r.model, base_url: r.base_url, runs: 0, last: r, best: r });
    m.runs += 1;
    if ((r.score ?? -1) > (m.best.score ?? -1)) m.best = r;
  }
  return Object.values(out).sort((a, b) => (b.last.at || "").localeCompare(a.last.at || ""));
}

/** Totaux d'activité sur la période : appels, erreurs, temps moyen pondéré, jetons/s moyen. */
export function activityTotals(days) {
  const n = (days || []).reduce((s, d) => s + d.n, 0);
  const errors = (days || []).reduce((s, d) => s + d.errors, 0);
  const w = (days || []).filter((d) => d.ms_avg != null);
  const ms = w.length ? Math.round(w.reduce((s, d) => s + d.ms_avg * d.n, 0) / w.reduce((s, d) => s + d.n, 0)) : null;
  const t = (days || []).filter((d) => d.tok_s_avg != null);
  return { n, errors, ms_avg: ms, tok_s_avg: t.length ? Math.round((10 * t.reduce((s, d) => s + d.tok_s_avg, 0)) / t.length) / 10 : null, max: Math.max(1, ...(days || []).map((d) => d.n)) };
}

const glob = (p) => new RegExp("^" + p.replace(/[.+^${}()|[\]\\]/g, "\\$&").replace(/\*/g, ".*").replace(/\?/g, ".") + "$");
/** Conteneurs que les listes blanches de l'agent autorisent pour les gestes. */
export const allowedContainers = (containers, patterns) => (containers || []).filter((c) => (patterns || []).some((p) => glob(p).test(c.name || "")));

export const ACTION_TARGET = { service_status: "unit", journal: "unit", service_restart: "unit", docker_logs: "container", docker_restart: "container", compose_update: "dir" };
/** Paramètres d'un geste prêts à envoyer, ou une erreur à afficher. */
export function gestureParams(g, catalogue) {
  if (!g?.action) return { error: "choisir un geste" };
  const target = ACTION_TARGET[g.action];
  if (target && !g[target]) return { error: { unit: "choisir le service", container: "choisir le conteneur", dir: "choisir le dossier compose" }[target] };
  const write = (catalogue?.write || []).includes(g.action);
  if (write && (g.reason || "").trim().length < 4) return { error: "motif obligatoire (journalisé sur l'hôte)" };
  const p = { action: g.action };
  if (target) p[target] = g[target];
  if (["journal", "docker_logs"].includes(g.action)) p.lines = Number(g.lines || 200);
  if (write) p.reason = g.reason.trim();
  return { params: p, write };
}
