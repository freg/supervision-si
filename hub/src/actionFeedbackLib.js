// Retour visuel des boutons du hub (livraison #778) -- logique PURE, testée sous Node (hub/tests/actionFeedbackLib.test.mjs).
// Constat : un clic qui envoie une modification (POST / PUT / PATCH / DELETE) ne montrait rien ; on recliquait, l'action
// partait plusieurs fois. actionFeedback.js (installé une fois dans main.jsx) relie chaque envoi au bouton cliqué juste
// avant : bouton occupé (pas de second clic) pendant l'envoi, puis bandeau « fait » ou « échec : raison ».

export const MUTATING = ["POST", "PUT", "PATCH", "DELETE"];
export const CLICK_WINDOW_MS = 1500;

export function isMutating(init, input) {
  const m = String((init && init.method) || (input && typeof input === "object" && input.method) || "GET").toUpperCase();
  return MUTATING.includes(m);
}

/** Libellé court d'un bouton : texte visible, sinon title / aria-label. */
export function buttonLabel(text, title) {
  const t = String(text || "").replace(/\s+/g, " ").trim() || String(title || "").trim() || "action";
  return t.length > 48 ? `${t.slice(0, 47)}…` : t;
}

/** Réponse d'un envoi -> {ok, text} pour le bandeau. data : JSON de la réponse (ou null). */
export function outcome(status, ok, data) {
  const d = data && typeof data === "object" ? data : {};
  if (ok && d.ok !== false && !d.error) return { ok: true, text: String(d.message || "fait").slice(0, 200) };
  const why = d.error || d.message || (Array.isArray(d.errors) && d.errors.join(" · ")) || (status ? `HTTP ${status}` : "pas de réponse du serveur");
  return { ok: false, text: `échec : ${String(why).slice(0, 240)}` };
}

/** Le clic est-il assez récent pour que l'envoi lui soit attribué ? */
export const fromClick = (clickAt, now) => clickAt != null && now - clickAt >= 0 && now - clickAt <= CLICK_WINDOW_MS;
