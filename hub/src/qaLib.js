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
