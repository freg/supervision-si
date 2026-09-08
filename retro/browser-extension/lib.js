// Fonctions PURES partagées par le script de contenu, l'arrière-plan et le
// popup (supervision-si, parcours applicatif #441). Testées avec Node
// (retro/browser-extension/test_lib.mjs) : aucune dépendance au navigateur.
(function (root) {
  "use strict";
  // L'URL est-elle dans le périmètre de l'application enregistrée ? `bases` :
  // liste d'URL de base ("https://gestion.exemple.fr", "http://10.0.0.5/appli").
  // Vide = tout est enregistré (à éviter : préciser la base dans les options).
  function inScope(url, bases) {
    if (!url || /^(about|moz-extension|chrome|file|data|blob):/.test(url)) return false;
    const list = (bases || []).map((b) => String(b || "").trim().replace(/\/+$/, "")).filter(Boolean);
    if (!list.length) return true;
    return list.some((b) => url === b || url.startsWith(b + "/") || url.startsWith(b + "?"));
  }
  // Sélecteur CSS court et stable pour un élément (id > name > chemin de balises avec nth-child).
  function selectorFor(el) {
    if (!el || !el.tagName) return null;
    if (el.id) return "#" + el.id;
    const name = el.getAttribute && el.getAttribute("name");
    if (name) return el.tagName.toLowerCase() + "[name=\"" + name + "\"]";
    const parts = [];
    let node = el;
    while (node && node.tagName && parts.length < 5 && node.tagName !== "BODY" && node.tagName !== "HTML") {
      let part = node.tagName.toLowerCase();
      if (node.id) { parts.unshift("#" + node.id); break; }
      const parent = node.parentElement;
      if (parent) {
        const same = Array.prototype.filter.call(parent.children, (c) => c.tagName === node.tagName);
        if (same.length > 1) part += ":nth-child(" + (Array.prototype.indexOf.call(parent.children, node) + 1) + ")";
      }
      parts.unshift(part);
      node = parent;
    }
    return parts.join(" > ");
  }
  // Un formulaire -> {action, method, id, fields: [{name, type, label, required}]} (jamais les valeurs).
  function describeForm(form) {
    const fields = [];
    const seen = new Set();
    Array.prototype.forEach.call(form.elements || [], (el) => {
      const name = el.name || null;
      const type = (el.type || el.tagName || "").toLowerCase();
      if (!name || seen.has(name) || type === "submit" || type === "button" || type === "fieldset") return;
      seen.add(name);
      let label = null;
      if (el.labels && el.labels.length) label = (el.labels[0].textContent || "").trim().slice(0, 60) || null;
      else if (el.placeholder) label = el.placeholder.slice(0, 60);
      fields.push({ name: name, type: type, label: label, required: !!el.required });
    });
    return { action: form.getAttribute("action") || null, method: (form.getAttribute("method") || "get").toLowerCase(), id: form.id || null, fields: fields };
  }
  // Ce qu'un écran montre : titre, en-têtes, formulaires, colonnes des tableaux, nombre de liens.
  function describeDocument(doc) {
    const headings = Array.prototype.slice.call(doc.querySelectorAll("h1, h2, h3"), 0, 12).map((h) => (h.textContent || "").trim().replace(/\s+/g, " ").slice(0, 80)).filter(Boolean);
    const forms = Array.prototype.slice.call(doc.querySelectorAll("form"), 0, 20).map(describeForm);
    const tables = Array.prototype.slice.call(doc.querySelectorAll("table"), 0, 10).map((t) => {
      const headers = Array.prototype.slice.call(t.querySelectorAll("thead th, tr:first-child th"), 0, 30).map((th) => (th.textContent || "").trim().replace(/\s+/g, " ").slice(0, 40)).filter(Boolean);
      return { headers: headers, rows: t.querySelectorAll("tbody tr, tr").length, id: t.id || null };
    }).filter((t) => t.headers.length);
    return { title: (doc.title || "").slice(0, 120), headings: headings, forms: forms, tables: tables, links_count: doc.querySelectorAll("a[href]").length };
  }
  // Valeur d'un champ à envoyer : jamais un mot de passe ; sinon seulement si l'option est activée.
  function fieldValue(el, recordValues) {
    const type = (el.type || "").toLowerCase();
    if (type === "password" || type === "hidden") return { length: (el.value || "").length, value: null };
    if (!recordValues) return { length: (el.value || "").length, value: null };
    if (type === "checkbox" || type === "radio") return { length: null, value: el.checked ? (el.value || "on") : "" };
    return { length: (el.value || "").length, value: String(el.value || "").slice(0, 200) };
  }
  // Clés d'un corps de formulaire vues par webRequest (jamais les valeurs).
  function formKeys(requestBody) {
    if (!requestBody) return [];
    if (requestBody.formData) return Object.keys(requestBody.formData);
    return [];
  }
  // Même normalisation que journeys.normalize_path côté API (rejeu : « suis-je sur l'écran attendu ? »).
  function normalizePath(url, base) {
    let path, query;
    try { const u = new URL(url, "http://x"); path = u.pathname || "/"; query = u.search.slice(1); } catch (e) { return "/"; }
    if (base) {
      let bp = "";
      try { bp = new URL(base, "http://x").pathname.replace(/\/+$/, ""); } catch (e) { bp = ""; }
      if (bp && path.startsWith(bp + "/")) path = path.slice(bp.length); else if (bp && path === bp) path = "/";
    }
    const segs = path.split("/").map((s) => (s && (/^\d+$/.test(s) || /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(s) || /^[0-9a-f]{16,}$/i.test(s))) ? "{n}" : s);
    let out = segs.join("/") || "/";
    const keys = Array.from(new Set(query.split("&").filter(Boolean).map((kv) => decodeURIComponent(kv.split("=")[0])))).sort();
    if (keys.length) out += "?" + keys.join("&");
    return out;
  }
  const api = { inScope: inScope, selectorFor: selectorFor, describeForm: describeForm, describeDocument: describeDocument, fieldValue: fieldValue, formKeys: formKeys, normalizePath: normalizePath };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.RetroLib = api;
})(typeof self !== "undefined" ? self : this);
