// Logique pure du module « Tests QA en ligne » (hub, #651) -- testée sous Node.

// Étape vide prête à l'édition.
export const emptyStep = (action = "goto") => ({ action, selector: "", value: "", note: "" });

// Quels champs montrer pour une action (miroir de qa_steps.ACTIONS côté API).
export function fieldsFor(action, catalog) {
  const a = (catalog || []).find((x) => x.id === action);
  return a ? a.fields : ["selector", "value"];
}

// Validation locale avant envoi (même règles que l'API, messages en français).
export function validateSteps(steps, catalog) {
  if (!steps || steps.length === 0) return "Ajoutez au moins une étape";
  for (let i = 0; i < steps.length; i += 1) {
    const s = steps[i]; const f = fieldsFor(s.action, catalog);
    if (!catalog.some((x) => x.id === s.action)) return `Étape ${i + 1} : action inconnue`;
    if (f.includes("selector") && !(s.selector || "").trim()) return `Étape ${i + 1} : sélecteur manquant`;
    if (f.includes("value") && !(s.value || "").trim() && s.action !== "expect_text") return `Étape ${i + 1} : valeur manquante`;
    if (s.action === "wait" && !/^\d+$/.test(s.value || "")) return `Étape ${i + 1} : durée en millisecondes`;
  }
  return "";
}

// Étapes de connexion devinées depuis une reconnaissance (probe) : premier formulaire avec un champ password.
export function loginFromProbe(probe, loginPath) {
  const form = (probe?.forms || []).find((f) => f.fields.some((x) => x.type === "password"));
  if (!form) return null;
  const sel = (x) => (x.id ? `#${x.id}` : x.name ? `[name="${x.name}"]` : x.tag);
  const user = form.fields.find((x) => x.tag === "input" && ["text", "email", ""].includes(x.type));
  const pass = form.fields.find((x) => x.type === "password");
  const submit = form.fields.find((x) => x.type === "submit" || x.type === "image" || x.tag === "button");
  const steps = [{ action: "goto", selector: "", value: loginPath || "/", note: "page de connexion" }];
  if (user) steps.push({ action: "fill", selector: sel(user), value: "", note: "identifiant" });
  if (pass) steps.push({ action: "fill", selector: sel(pass), value: "", note: "mot de passe" });
  steps.push(submit ? { action: "click", selector: sel(submit), value: "", note: "valider" } : { action: "press", selector: sel(pass), value: "Enter", note: "valider" });
  return steps;
}

export function runBadge(status) {
  return { ok: "✔ réussi", ko: "✘ échec", error: "⚠ erreur", running: "… en cours" }[status] || "—";
}

// Synthèse d'une campagne : {total, passed, failed, ratio}.
export function campaignSummary(runs) {
  const total = (runs || []).length; const passed = (runs || []).filter((r) => r.status === "ok").length;
  return { total, passed, failed: total - passed, ratio: total ? Math.round((100 * passed) / total) : 0 };
}

// #721 : vues internes du hub à visiter pour le « tour du hub » (une fois chacune, dans l'ordre des thématiques).
export function hubTourViews(themes) {
  const seen = new Set(); const out = [];
  for (const t of themes || []) for (const e of t.entries || []) {
    if (e.view && !seen.has(e.view)) { seen.add(e.view); out.push({ view: e.view, label: `${t.name} › ${e.label}` }); }
  }
  return out;
}

// #721 : synthèse des audits d'une exécution -- note moyenne et nombre de constats par gravité.
export function auditSummary(results) {
  const audits = (results || []).filter((r) => r.action === "audit" && Array.isArray(r.findings));
  const count = { erreur: 0, avertissement: 0, info: 0 };
  audits.forEach((r) => r.findings.forEach((f) => { count[f.severity] = (count[f.severity] || 0) + 1; }));
  const avg = audits.length ? Math.round(audits.reduce((a, r) => a + (r.score ?? 0), 0) / audits.length) : null;
  return { pages: audits.length, score: avg, ...count };
}

// #727 : synthèse d'une comparaison visuelle (GET /runs/<id>/diff) -- étapes comparées, écarts significatifs,
// plus grand écart en %, et libellé prêt à afficher.
export function diffSummary(diff) {
  const steps = (diff && diff.steps) || []; const compared = steps.filter((s) => !s.error);
  const significant = compared.filter((s) => s.significant).length;
  const max = compared.reduce((m, s) => Math.max(m, s.ratio || 0), 0);
  const maxPct = Math.round(max * 1000) / 10;
  const label = compared.length === 0 ? "aucune capture comparable"
    : significant === 0 ? `identique à la référence (${compared.length} capture(s), écart max ${maxPct} %)`
    : `${significant} capture(s) différente(s) sur ${compared.length} (écart max ${maxPct} %)`;
  return { compared: compared.length, missing: steps.length - compared.length, significant, maxPct, label };
}

// #727 : écart d'une étape en pourcentage lisible.
export const ratioPct = (r) => `${Math.round((r || 0) * 1000) / 10} %`;

// #727 : zones masquées -- texte saisi « .horloge, #compteur » → sélecteurs nettoyés (vides retirés).
export const parseMask = (text) => (text || "").split(",").map((x) => x.trim()).filter(Boolean);

// #728 : maquettes -- libellés d'état et d'étape, écart de note signé, étape suivante utile.
export const mockupStatus = (s) => ({ brouillon: "brouillon", presentee: "présentée", validee: "✔ validée", integree: "★ intégrée", rejetee: "✘ rejetée" }[s] || s || "—");
export const slideIcon = (k) => ({ avant: "①", proposition: "②", variante: "③", regles: "④", decision: "⑤" }[k] || "•");
export const scoreDelta = (d) => (d === null || d === undefined ? "" : d > 0 ? `+${d}` : `${d}`);
// Première étape à regarder : la première variante non rendue, sinon la situation actuelle.
export function firstSlide(slides) {
  const i = (slides || []).findIndex((s) => (s.kind === "proposition" || s.kind === "variante") && !s.rendered);
  return i >= 0 ? i : 0;
}
// Couples de vignettes d'une variante : capture de la situation actuelle / de la variante / différences.
export function shotTriples(slide) {
  return ((slide && slide.diff && slide.diff.steps) || []).filter((s) => !s.error)
    .map((s) => ({ index: s.index, refRun: s.ref_run, refShot: s.ref_shot, shot: s.shot, diff: s.diff, ratio: s.ratio, significant: !!s.significant }));
}

// #729 : conformité à la maquette validée (résultat de design_check) -> {cls, text} ; null si le scénario n'a pas de cible.
export function designBadge(d) {
  if (!d) return null;
  if (d.conforme) return { cls: "qa-ok", text: `✔ conforme à la maquette${d.score !== null && d.score !== undefined ? ` (${d.score}/100)` : ""}` };
  if (!d.compared) return { cls: "muted", text: "maquette : aucune capture comparable" };
  return { cls: "qa-ko", text: `✘ écart avec la maquette : ${d.significant}/${d.compared} capture(s)${d.score !== null && d.score !== undefined && d.target_score !== null && d.target_score !== undefined ? ` · note ${d.score}/100 pour ${d.target_score} visés` : ""}` };
}
