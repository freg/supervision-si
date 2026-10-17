// Retour visuel des boutons du hub (livraison #778), installé une fois au démarrage (main.jsx), sans toucher aux vues :
// le dernier bouton cliqué devient « occupé » (aria-busy : roue, second clic bloqué) tant que l'envoi qu'il a déclenché
// n'a pas répondu ; un bandeau dit ensuite « fait » (ou le message du serveur) ou « échec : raison ». Les lectures (GET)
// et les envois sans clic (rafraîchissements, sauvegardes automatiques) ne changent rien. Logique pure : actionFeedbackLib.js.
import { isMutating, buttonLabel, outcome, fromClick } from "./actionFeedbackLib.js";

let lastBtn = null, lastAt = null, box = null, hideTimer = null;

function toast(kind, text) {
  if (!box) {
    box = document.createElement("div");
    box.className = "hub-action-toast";
    box.setAttribute("role", "status");
    box.setAttribute("aria-live", "polite");
    document.body.appendChild(box);
  }
  clearTimeout(hideTimer);
  box.dataset.kind = kind;
  box.textContent = text;
  box.hidden = false;
  if (kind !== "busy") hideTimer = setTimeout(() => { box.hidden = true; }, kind === "error" ? 9000 : 3500);
}

export function installActionFeedback() {
  if (typeof window === "undefined" || window.__hubActionFeedback) return;
  window.__hubActionFeedback = true;
  document.addEventListener("click", (e) => {
    const b = e.target && e.target.closest ? e.target.closest("button, input[type=submit], input[type=button]") : null;
    if (!b) return;
    if (b.getAttribute("aria-busy") === "true") {   // déjà en cours : second clic ignoré
      e.preventDefault(); e.stopPropagation();
      toast("busy", `${buttonLabel(b.textContent || b.value, b.title)} : déjà en cours…`);
      return;
    }
    lastBtn = b; lastAt = performance.now();
  }, true);
  const orig = window.fetch.bind(window);
  window.fetch = (input, init) => {
    if (!isMutating(init, input) || !fromClick(lastAt, performance.now()) || !lastBtn) return orig(input, init);
    const b = lastBtn, label = buttonLabel(b.textContent || b.value, b.title || b.getAttribute("aria-label"));
    lastBtn = null;
    b.setAttribute("aria-busy", "true");
    toast("busy", `${label} : envoi en cours…`);
    const done = (res, data) => {
      b.removeAttribute("aria-busy");
      const o = outcome(res ? res.status : 0, res ? res.ok : false, data);
      toast(o.ok ? "ok" : "error", `${label} : ${o.text}`);
    };
    return orig(input, init).then((res) => {
      res.clone().json().then((d) => done(res, d), () => done(res, null));
      return res;
    }, (err) => { done(null, { error: err && err.message }); throw err; });
  };
}
