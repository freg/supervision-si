// Logique PURE de la tuile Cortex (livraison #462) -- testée sous Node
// (hub/tests/cortex.test.mjs). Présentation des incidents, des hypothèses
// (confiance en mots et en couleur), de la santé de la collecte, des
// principes (partis pris) et de leur évaluation mesurée.

export const SEV = { critical: { label: "critique", tone: "bad" }, warning: { label: "avertissement", tone: "warn" }, info: { label: "info", tone: "neutral" } };
export const STATE_LABEL = { open: "ouvert", acked: "acquitté", closed: "clos" };
export const KIND_LABEL = { hote: "hôte", passerelle: "passerelle", onduleur: "onduleur", cible: "cible sondée", equipement: "équipement", pair: "pair réseau" };

// Confiance 0-1 -> mot + ton, pour ne jamais afficher un nombre nu.
export function confidenceWord(c) {
  const n = Number(c) || 0;
  if (n >= 0.85) return { word: "forte", tone: "good" };
  if (n >= 0.6) return { word: "probable", tone: "neutral" };
  if (n >= 0.4) return { word: "faible", tone: "warn" };
  return { word: "très faible", tone: "bad" };
}
export const pct = (c) => `${Math.round((Number(c) || 0) * 100)} %`;

// Résumé d'un incident pour la liste.
export function incidentLine(i) {
  const n = (i.entities || []).length, m = (i.events || []).length;
  return `${n} entité${n > 1 ? "s" : ""}, ${m} événement${m > 1 ? "s" : ""}${i.weak ? " · regroupement faible" : ""}${i.sources?.length ? ` · ${i.sources.join(", ")}` : ""}`;
}

// La cause proposée (première hypothèse causale) et les autres.
export function splitHypotheses(hyps) {
  const causal = new Set(["upstream-first", "single-event", "window-cluster", "site-cluster"]);
  const list = hyps || [];
  const cause = list.find((h) => causal.has(h.principle)) || null;
  return { cause, others: list.filter((h) => h !== cause) };
}

// Santé de la dernière collecte : sources ok / en échec.
export function collectHealth(lastRun) {
  if (!lastRun) return { text: "aucune collecte depuis le démarrage", tone: "warn", ok: [], failed: [] };
  if (lastRun.error) return { text: `collecte en échec : ${lastRun.error}`, tone: "bad", ok: [], failed: [] };
  const rep = lastRun.report || {};
  const ok = Object.entries(rep).filter(([, v]) => v.ok).map(([k]) => k);
  const failed = Object.entries(rep).filter(([, v]) => !v.ok).map(([k, v]) => `${k} (${v.error || "?"})`);
  return { text: `${ok.length} source${ok.length > 1 ? "s" : ""} lue${ok.length > 1 ? "s" : ""}${failed.length ? `, ${failed.length} en échec` : ""} à ${lastRun.at}`, tone: failed.length ? "warn" : "good", ok, failed };
}

// Évaluation d'un principe en une phrase.
export function principleText(p) {
  const base = pct(p.base);
  if (p.measured == null) return `confiance de base ${base} — ${p.applied || 0} application(s), aucun retour humain encore`;
  return `mesurée ${pct(p.measured)} (base ${base}) — ${p.confirmed} confirmée(s), ${p.rejected} rejetée(s) sur ${p.applied || 0} application(s)`;
}

// Regroupe les événements ouverts par source pour un aperçu.
export function eventsBySource(events) {
  const m = new Map();
  for (const e of events || []) m.set(e.source, (m.get(e.source) || 0) + 1);
  return [...m.entries()].sort((a, b) => b[1] - a[1]);
}
