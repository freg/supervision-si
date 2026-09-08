// Script de contenu (supervision-si, parcours applicatif #441) : observe la
// page et envoie à l'arrière-plan des événements bruts -- navigation, DOM
// de l'écran, clics, saisies (nom du champ, longueur ; valeur seulement si
// l'option est activée, jamais un mot de passe), envois de formulaire.
// L'arrière-plan décide si la page est dans le périmètre et si un parcours
// est en cours : ici on n'émet que si l'enregistrement est actif.
(function () {
  "use strict";
  const L = window.RetroLib;
  const B = typeof browser !== "undefined" ? browser : chrome;
  let active = false, recordValues = false;

  function send(kind, data) {
    if (!active) return;
    try { B.runtime.sendMessage({ type: "event", kind: kind, at: new Date().toISOString(), url: location.href, data: data }); } catch (e) { /* page en cours de déchargement */ }
  }
  function refreshState() {
    try {
      B.runtime.sendMessage({ type: "state?", url: location.href }).then((s) => {
        const was = active;
        active = !!(s && s.active); recordValues = !!(s && s.recordValues);
        if (active && !was) { send("navigation", { url: location.href, title: document.title, referrer: document.referrer || null }); setTimeout(() => send("dom", L.describeDocument(document)), 300); }
      }).catch(() => { active = false; });
    } catch (e) { active = false; }
  }
  refreshState();
  B.runtime.onMessage.addListener((m) => { if (m && m.type === "state") { active = !!m.active; recordValues = !!m.recordValues; } });

  document.addEventListener("click", (e) => {
    const el = e.target && e.target.closest ? (e.target.closest("a, button, input, select, [role=button], [onclick]") || e.target) : e.target;
    if (!el || !el.tagName) return;
    send("click", { selector: L.selectorFor(el), tag: el.tagName, text: (el.innerText || el.value || el.getAttribute("aria-label") || "").trim().slice(0, 80),
      href: el.getAttribute ? el.getAttribute("href") : null, form: el.form && el.form.getAttribute ? (el.form.getAttribute("action") || el.form.id || "form") : null });
  }, true);
  document.addEventListener("change", (e) => {
    const el = e.target;
    if (!el || !el.name) return;
    const v = L.fieldValue(el, recordValues);
    send("input", { field: el.name, type: (el.type || el.tagName || "").toLowerCase(), length: v.length, value: v.value, selector: L.selectorFor(el),
      form: el.form ? (el.form.getAttribute("action") || el.form.id || "form") : null });
  }, true);
  // frappe dans un champ : un événement par pause de saisie (800 ms), même sans quitter le champ
  const typing = new Map();
  document.addEventListener("input", (e) => {
    const el = e.target;
    if (!el || !el.name) return;
    clearTimeout(typing.get(el.name));
    typing.set(el.name, setTimeout(() => {
      typing.delete(el.name);
      const v = L.fieldValue(el, recordValues);
      send("input", { field: el.name, type: (el.type || el.tagName || "").toLowerCase(), length: v.length, value: v.value, selector: L.selectorFor(el),
        form: el.form ? (el.form.getAttribute("action") || el.form.id || "form") : null, typed: true });
    }, 800));
  }, true);
  document.addEventListener("submit", (e) => {
    const f = e.target;
    if (!f || f.tagName !== "FORM") return;
    const d = L.describeForm(f);
    send("submit", { action: d.action, method: d.method, id: d.id, fields: d.fields.map((x) => x.name), selector: L.selectorFor(f) });
  }, true);
  // navigations sans rechargement (history.pushState) : nouvel écran
  let lastUrl = location.href;
  setInterval(() => {
    if (location.href !== lastUrl) { lastUrl = location.href; send("navigation", { url: location.href, title: document.title, spa: true }); setTimeout(() => send("dom", L.describeDocument(document)), 300); }
  }, 500);
})();
