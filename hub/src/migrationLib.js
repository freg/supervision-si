// Tuile « Migration 2026-2027 » (livraison #774) -- logique PURE, testée sous Node (hub/tests/migrationLib.test.mjs).
// État fourni par si-agent-api GET /migration (plan, paramètres, marche, étapes avec mesure et erreur classée).

export const STATUS = {
  a_faire: ["à faire", ""], lance: ["envoyée à l'agent", "warning"], en_cours: ["en cours", "warning"], en_pause: ["en pause", "warning"],
  fait: ["réussie", "ok"], erreur: ["en erreur", "critical"], arrete: ["arrêtée", "critical"], saute: ["sautée", ""],
  manuel: ["à faire à la main", "warning"], manuel_fait: ["faite à la main", "ok"],
};
export const ACTIVE = ["lance", "en_cours", "en_pause"];
export const RUN_LABEL = { arrete: "arrêtée", en_cours: "en cours", en_pause: "en pause", termine: "terminée" };
export const KIND_LABEL = {
  check_ssh: "contrôle SSH", check_space: "contrôle de place", check_file: "contrôle de fichier", zfs_create: "création de volume",
  rsync_pull: "copie rsync", rsync_pull_all: "copie rsync (lot)", zfs_pull: "copie ZFS", zfs_send_file: "flux ZFS vers fichier",
  verify_rsync: "vérification rsync", verify_zfs: "vérification ZFS", manual: "à la main",
};

export const statusLabel = (s) => (STATUS[s] || [s || "?"])[0];
export const statusTone = (s) => (STATUS[s] || ["", ""])[1];

export function allSteps(view) {
  return (view?.plan?.phases || []).flatMap((ph) => ph.steps.map((s) => ({ ...s, phase: ph.id, phaseTitle: ph.title })));
}

/** Étape à montrer en grand : celle qui tourne, sinon la dernière en erreur, sinon la prochaine. */
export function focusStep(view) {
  const st = allSteps(view);
  return st.find((s) => ACTIVE.includes(s.status) || s.status === "manuel") || st.find((s) => s.status === "erreur" || s.status === "arrete")
    || st.find((s) => s.next) || null;
}

export function progress(view) {
  const total = view?.total || 0, done = view?.done || 0;
  return { total, done, pct: total ? Math.round((100 * done) / total) : 0 };
}

export function phaseProgress(ph) {
  const n = ph.steps.length, d = ph.steps.filter((s) => ["fait", "saute", "manuel_fait"].includes(s.status)).length;
  const bad = ph.steps.some((s) => s.status === "erreur" || s.status === "arrete"), act = ph.steps.some((s) => ACTIVE.includes(s.status) || s.status === "manuel");
  return { n, d, tone: bad ? "critical" : d === n ? "ok" : act ? "warning" : "" };
}

/** Boutons de la barre de pilotage -> {start, next, pause, resume, stop} (true = actif). */
export function controls(view) {
  const st = allSteps(view);
  const running = st.some((s) => s.status === "lance" || s.status === "en_cours");
  const paused = st.some((s) => s.status === "en_pause");
  const waitingHand = st.some((s) => s.status === "manuel");
  const hasNext = !!view?.next;
  const idle = !running && !paused;
  return {
    start: !!view?.plan && idle && hasNext && !waitingHand && (view?.run?.state || "arrete") === "arrete",
    next: !!view?.plan && idle && hasNext && !waitingHand,
    pause: running, resume: paused, stop: running || paused,
  };
}

/** Gestes possibles sur une étape. */
export function stepActions(s) {
  const a = [];
  if (["erreur", "arrete"].includes(s.status)) a.push("retry");
  if (s.status === "manuel" || (s.kind === "manual" && s.status === "a_faire") || s.status === "erreur") a.push("done");
  if (["a_faire", "erreur", "arrete", "manuel"].includes(s.status)) a.push("skip");
  if (["fait", "saute", "erreur", "arrete", "manuel_fait"].includes(s.status)) a.push("reset");
  return a;
}
export const ACTION_LABEL = { retry: "Relancer", done: "Fait", skip: "Sauter", reset: "Remettre à faire" };

export function parsePlan(text) {
  let p;
  try { p = JSON.parse(text); } catch (e) { return { plan: null, error: `JSON invalide : ${e.message}` }; }
  if (!p || typeof p !== "object" || !Array.isArray(p.phases)) return { plan: null, error: "plan attendu : {name, vars, phases: [...]}" };
  return { plan: p, error: null };
}

export function fmtBytes(n) {
  if (n == null) return "—";
  const u = ["o", "Ko", "Mo", "Go", "To"];
  let i = 0, v = n;
  while (v >= 1024 && i < u.length - 1) { v /= 1024; i += 1; }
  return `${v >= 100 || i === 0 ? Math.round(v) : v.toFixed(1)} ${u[i]}`;
}
/** Avancement « restant / transféré / total » (total connu), sinon le transféré seul ; « ≈ » : mesure sur le volume entier. */
export function fmtProgress(r) {
  if (!r || r.size == null) return "";
  const approx = r.scope === "volume" ? "≈ " : "";
  if (!r.total) return approx + fmtBytes(r.size);
  return `${approx}${fmtBytes(Math.max(0, r.total - r.size))} / ${fmtBytes(r.size)} / ${fmtBytes(r.total)}`;
}
export const fmtRate = (bps) => (bps == null ? "—" : `${fmtBytes(bps)}/s`);
export function fmtDuration(s) {
  if (s == null || !Number.isFinite(s)) return "—";
  s = Math.max(0, Math.round(s));
  const d = Math.floor(s / 86400), h = Math.floor((s % 86400) / 3600), m = Math.floor((s % 3600) / 60);
  return d ? `${d} j ${h} h` : h ? `${h} h ${String(m).padStart(2, "0")}` : m ? `${m} min` : `${s} s`;
}
/** Durée écoulée d'une étape (secondes epoch côté serveur). */
export function elapsed(s, nowMs) {
  if (!s?.launched_at) return null;
  return ((s.ended_at || nowMs / 1000) - s.launched_at);
}

/** Texte à copier pour une solution « commande ». */
export function solutionCommand(err) {
  const sol = err?.solution;
  if (!sol || sol.kind !== "command" || !sol.command) return "";
  return sol.command;
}

/** Variables du plan vides et utilisées par une étape pas encore faite. */
export function missingVars(view) {
  const need = new Set();
  allSteps(view).forEach((s) => { if (!["fait", "saute", "manuel_fait"].includes(s.status)) (s.missing_vars || []).forEach((v) => need.add(v)); });
  return [...need].sort();
}
