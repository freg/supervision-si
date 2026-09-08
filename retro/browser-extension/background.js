// Arrière-plan (supervision-si, parcours applicatif #441) : état de
// l'enregistrement (parcours courant, périmètre), requêtes HTTP vues par le
// navigateur (webRequest : méthode, URL, type, statut, clés de formulaire --
// jamais les valeurs ni les en-têtes), file d'envoi vers l'agent relais local.
// Firefox (MV2, page d'arrière-plan persistante) ET Chromium (MV3, service
// worker : manifest.chromium.json) : mêmes sources.
if (typeof importScripts === "function" && typeof self.RetroLib === "undefined") importScripts("lib.js");
(function () {
  "use strict";
  const B = typeof browser !== "undefined" ? browser : chrome;
  const L = self.RetroLib;
  const DEFAULTS = { relayUrl: "http://127.0.0.1:6320", bases: [], recordValues: false, journey: null };
  let cfg = Object.assign({}, DEFAULTS);
  let queue = [];
  let timer = null;
  const inflight = new Map();   // requestId -> {at, method, url, type, form_keys}
  let stats = { sent: 0, queued: 0, errors: 0, lastError: null };

  async function load() {
    const s = await B.storage.local.get(["relayUrl", "bases", "recordValues", "journey"]);
    cfg = Object.assign({}, DEFAULTS, s);
  }
  function active() { return !!(cfg.journey && cfg.journey.id); }
  function scope(url) { return active() && L.inScope(url, cfg.bases); }

  function push(kind, at, data) {
    queue.push({ kind: kind, at: at || new Date().toISOString(), data: data });
    stats.queued = queue.length;
    if (!timer) timer = setTimeout(flush, 1500);
  }
  async function flush() {
    timer = null;
    if (!queue.length || !active()) return;
    const batch = queue.splice(0, 300);
    try {
      const res = await fetch(cfg.relayUrl.replace(/\/+$/, "") + "/events", { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ journey_id: cfg.journey.id, events: batch }) });
      if (!res.ok) throw new Error("relais HTTP " + res.status);
      stats.sent += batch.length; stats.lastError = null;
    } catch (e) {
      queue = batch.concat(queue); stats.errors += 1; stats.lastError = String(e.message || e);
      timer = setTimeout(flush, 5000);   // on réessaie : le relais garde l'ordre, rien n'est perdu tant que le navigateur est ouvert
    }
    stats.queued = queue.length;
  }

  // -- requêtes HTTP ------------------------------------------------------------------------
  B.webRequest.onBeforeRequest.addListener((d) => {
    if (d.tabId < 0 || !scope(d.url)) return;
    inflight.set(d.requestId, { at: new Date().toISOString(), method: d.method, url: d.url, type: d.type, form_keys: L.formKeys(d.requestBody) });
  }, { urls: ["<all_urls>"] }, ["requestBody"]);
  // redirection (302 après un POST) : la requête d'origine est émise ici, la
  // suivante (même requestId, nouvelle URL) repart par onBeforeRequest
  B.webRequest.onBeforeRedirect.addListener((d) => {
    const r = inflight.get(d.requestId);
    if (!r) return;
    inflight.delete(d.requestId);
    push("request", r.at, { method: r.method, url: r.url, type: d.type, status: d.statusCode, redirect_to: d.redirectUrl || null,
      duration_ms: Math.max(0, Date.now() - Date.parse(r.at)), form_keys: r.form_keys });
  }, { urls: ["<all_urls>"] });
  B.webRequest.onCompleted.addListener((d) => {
    const r = inflight.get(d.requestId);
    if (!r) return;
    inflight.delete(d.requestId);
    if (["main_frame", "sub_frame", "xmlhttprequest", "other", "beacon"].indexOf(d.type) < 0 && !/\.(php|json|xml|csv)(\?|$)/i.test(d.url)) return;  // pas les images/CSS/JS
    push("request", r.at, { method: r.method, url: r.url, type: d.type, status: d.statusCode, duration_ms: Math.max(0, Date.now() - Date.parse(r.at)), form_keys: r.form_keys,
      content_type: (d.responseHeaders || []).filter((h) => h.name.toLowerCase() === "content-type").map((h) => h.value)[0] || null, from_cache: !!d.fromCache });
  }, { urls: ["<all_urls>"] }, ["responseHeaders"]);
  B.webRequest.onErrorOccurred.addListener((d) => {
    const r = inflight.get(d.requestId);
    if (!r) return;
    inflight.delete(d.requestId);
    push("request", r.at, { method: r.method, url: r.url, type: d.type, status: null, error: d.error, form_keys: r.form_keys });
  }, { urls: ["<all_urls>"] });

  // -- messages du contenu et du popup (réponse par sendResponse : Firefox et Chromium) --------
  function handle(m, sender) {
    if (!m || !m.type) return null;
    if (m.type === "state?") return Promise.resolve({ active: scope(m.url), recordValues: cfg.recordValues, journey: cfg.journey });
    if (m.type === "event") {
      if (scope(m.url)) push(m.kind, m.at, Object.assign({ page_url: m.url, tab: sender && sender.tab ? sender.tab.id : null }, m.data || {}));
      return Promise.resolve({ ok: true });
    }
    if (m.type === "status") return Promise.resolve({ cfg: cfg, stats: stats, active: active() });
    if (m.type === "reload") return load().then(broadcast).then(() => ({ ok: true }));
    if (m.type === "mark") { push("mark", null, { label: m.label || "repère" }); return flush().then(() => ({ ok: true })); }
    if (m.type === "note") { push("note", null, { text: m.text || "" }); return Promise.resolve({ ok: true }); }
    if (m.type === "flush") return flush().then(() => stats);
    return null;
  }
  B.runtime.onMessage.addListener((m, sender, sendResponse) => {
    const p = handle(m, sender);
    if (!p) return false;
    p.then(sendResponse, (e) => sendResponse({ error: String(e) }));
    return true;
  });
  // -- suivre le parcours courant du relais ------------------------------------------------------
  // Un parcours peut être démarré depuis le relais (ou le hub) plutôt que
  // depuis le popup : toutes les 5 s, sans parcours local, on adopte celui du
  // relais (et son URL de base comme périmètre si aucun n'est configuré) ;
  // quand le relais n'en a plus, on s'arrête.
  async function followRelay() {
    try {
      const res = await fetch(cfg.relayUrl.replace(/\/+$/, "") + "/status");
      const st = await res.json();
      const cur = st && st.current;
      if (cur && !(cfg.journey && cfg.journey.id === cur.id)) {
        const upd = { journey: { id: cur.id, app: cur.app, name: cur.name, started_at: cur.started_at, from_relay: true } };
        if ((!cfg.bases || !cfg.bases.length) && cur.base_url) upd.bases = [cur.base_url];
        await B.storage.local.set(upd);
      } else if (!cur && cfg.journey && cfg.journey.from_relay) {
        await flush();
        await B.storage.local.set({ journey: null });
      }
    } catch (e) { /* relais absent : rien */ }
  }
  setInterval(followRelay, 5000);
  async function broadcast() {
    const tabs = await B.tabs.query({});
    for (const t of tabs) {
      try { await B.tabs.sendMessage(t.id, { type: "state", active: scope(t.url), recordValues: cfg.recordValues }); } catch (e) { /* onglet sans script */ }
    }
  }
  B.storage.onChanged.addListener(() => load().then(broadcast));
  load().then(followRelay);
})();
