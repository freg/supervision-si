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
  B.runtime.onMessage.addListener((m, sender, sendResponse) => {
    if (m && m.type === "state") { active = !!m.active; recordValues = !!m.recordValues; return; }
    if (m && m.type === "do") { const r = perform(m.action); sendResponse(r); return true; }
  });
  // -- rejeu (#443) : une action du script exécutée sur la page courante ---------------------
  function findByText(tag, text, href) {
    const cands = Array.prototype.slice.call(document.querySelectorAll(href ? "a[href]" : (tag || "a, button, input, [role=button]")));
    if (href) { const h = cands.find((a) => a.getAttribute("href") === href); if (h) return h; }
    const t = (text || "").trim().toLowerCase();
    if (!t) return null;
    return cands.find((el) => ((el.innerText || el.value || el.getAttribute("aria-label") || "").trim().toLowerCase() === t)) || null;
  }
  function fieldEl(a) {
    let el = null;
    if (a.selector) { try { el = document.querySelector(a.selector); } catch (e) { el = null; } }
    if (!el && a.field) el = document.querySelector("[name=\"" + a.field + "\"]");
    return el;
  }
  function perform(a) {
    try {
      if (a.action === "click") {
        let el = null;
        if (a.selector) { try { el = document.querySelector(a.selector); } catch (e) { el = null; } }
        if (!el) el = findByText(a.tag ? a.tag.toLowerCase() : null, a.text, a.href);
        if (!el) return { ok: false, error: "élément introuvable : " + (a.selector || a.text || a.href) };
        el.scrollIntoView && el.scrollIntoView({ block: "center" });
        el.click();
        return { ok: true, what: L.selectorFor(el) };
      }
      if (a.action === "fill") {
        const el = fieldEl(a);
        if (!el) return { ok: false, error: "champ introuvable : " + (a.field || a.selector) };
        if (a.value == null) { el.focus(); el.scrollIntoView && el.scrollIntoView({ block: "center" }); return { ok: false, needs_input: true, field: a.field, length: a.length }; }
        const type = (el.type || "").toLowerCase();
        if (type === "checkbox" || type === "radio") el.checked = a.value !== "" && a.value !== "0" && a.value !== "false";
        else if (el.tagName === "SELECT") { el.value = a.value; if (el.value !== a.value) { const o = Array.prototype.find.call(el.options, (x) => x.text.trim() === a.value); if (o) el.value = o.value; } }
        else el.value = a.value;
        el.dispatchEvent(new Event("input", { bubbles: true })); el.dispatchEvent(new Event("change", { bubbles: true }));
        return { ok: true, what: a.field };
      }
      if (a.action === "submit") {
        let form = null;
        if (a.selector) { try { form = document.querySelector(a.selector); } catch (e) { form = null; } }
        if (!form && a.form) form = document.querySelector("form[action=\"" + a.form + "\"]") || document.getElementById(a.form);
        if (!form) form = document.querySelector("form");
        if (!form) return { ok: false, error: "formulaire introuvable" };
        const btn = form.querySelector("button[type=submit], input[type=submit], button:not([type])");
        if (btn) btn.click(); else if (form.requestSubmit) form.requestSubmit(); else form.submit();
        return { ok: true, what: form.getAttribute("action") || form.id || "form" };
      }
      if (a.action === "expect") {
        const here = L.normalizePath(location.href, a.base_url);
        return { ok: here === a.expect_path, here: here, expected: a.expect_path, error: here === a.expect_path ? null : "écran attendu " + a.expect_path + ", obtenu " + here };
      }
      return { ok: false, error: "action inconnue : " + a.action };
    } catch (e) { return { ok: false, error: String(e.message || e) }; }
  }

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
