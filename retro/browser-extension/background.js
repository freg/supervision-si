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
  const recentRequests = [];    // #443 : dernières requêtes de page vues (méthode, chemin normalisé) pour vérifier un `expect` POST
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
    if (d.type === "main_frame") { recentRequests.push({ method: r.method, path: L.normalizePath(r.url, replay.baseUrl) }); if (recentRequests.length > 50) recentRequests.shift(); }
    push("request", r.at, { method: r.method, url: r.url, type: d.type, status: d.statusCode, redirect_to: d.redirectUrl || null,
      duration_ms: Math.max(0, Date.now() - Date.parse(r.at)), form_keys: r.form_keys });
  }, { urls: ["<all_urls>"] });
  B.webRequest.onCompleted.addListener((d) => {
    const r = inflight.get(d.requestId);
    if (!r) return;
    inflight.delete(d.requestId);
    if (d.type === "main_frame") { recentRequests.push({ method: r.method, path: L.normalizePath(r.url, replay.baseUrl) }); if (recentRequests.length > 50) recentRequests.shift(); }
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
    if (m.type === "replay-start") return startReplay(m.payload);
    if (m.type === "replay-continue") { if (replay.status === "paused" || replay.status === "error") { replay.status = "running"; setTimeout(replayStep, 100); } return Promise.resolve({ ok: true, status: replay.status }); }
    if (m.type === "replay-stop") { replay.status = "stopped"; return Promise.resolve({ ok: true }); }
    if (m.type === "replay-status") return Promise.resolve({ status: replay.status, index: replay.index, total: replay.script.length, log: replay.log.slice(-8), current: replay.script[replay.index] || null });
    return null;
  }
  B.runtime.onMessage.addListener((m, sender, sendResponse) => {
    const p = handle(m, sender);
    if (!p) return false;
    p.then(sendResponse, (e) => sendResponse({ error: String(e) }));
    return true;
  });
  // -- rejeu (#443) : le script du central, action par action, dans un onglet -------------------
  const replay = { status: "idle", script: [], index: 0, tabId: null, baseUrl: null, log: [], journey: null };
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  function waitForLoad(tabId, timeoutMs) {
    return new Promise((resolve) => {
      let done = false;
      const t = setTimeout(() => { if (!done) { done = true; B.webNavigation.onCompleted.removeListener(on); resolve(false); } }, timeoutMs);
      function on(d) { if (d.tabId === tabId && d.frameId === 0 && !done) { done = true; clearTimeout(t); B.webNavigation.onCompleted.removeListener(on); resolve(true); } }
      B.webNavigation.onCompleted.addListener(on);
    });
  }
  async function replayStep() {
    const a = replay.script[replay.index];
    if (!a) { replay.status = "done"; push("replay-end", null, { steps: replay.index, log_tail: replay.log.slice(-5) }); await flush(); return; }
    let res = { ok: true };
    try {
      if (a.action === "navigate") {
        const loaded = waitForLoad(replay.tabId, 20000);
        await B.tabs.update(replay.tabId, { url: a.url });
        res.ok = await loaded; if (!res.ok) res.error = "page non chargée en 20 s : " + a.url;
        await sleep(600);
      } else if (a.action === "mark") {
        push("mark", null, { label: a.label || "repère", replay: true });
      } else if (a.action === "expect" && a.method && a.method !== "GET") {
        // écran transitoire (POST puis redirection) : vérifié par la requête vue, pas par l'URL affichée
        const seen = recentRequests.some((r) => r.method === a.method && r.path === (a.expect_path || "").split("?")[0]);
        res = seen ? { ok: true, what: a.method + " " + a.expect_path } : { ok: false, error: "requête attendue non vue : " + a.method + " " + a.expect_path };
      } else if (a.action === "expect") {
        res = await B.tabs.sendMessage(replay.tabId, { type: "do", action: Object.assign({}, a, { base_url: replay.baseUrl }) });
      } else {
        const navWait = (a.action === "click" || a.action === "submit") ? waitForLoad(replay.tabId, 6000) : null;
        res = await B.tabs.sendMessage(replay.tabId, { type: "do", action: a });
        if (res && res.ok && navWait) { await navWait; await sleep(500); }
      }
    } catch (e) { res = { ok: false, error: String(e.message || e) }; }
    replay.log.push({ index: replay.index, action: a.action, ok: !!(res && res.ok), error: res && res.error, needs_input: !!(res && res.needs_input) });
    push("replay-action", null, { index: replay.index, step: a.step, action: a.action, ok: !!(res && res.ok), error: (res && res.error) || null, what: res && res.what });
    if (res && res.needs_input) { replay.status = "paused"; replay.index += 1; return; }   // valeur non enregistrée : la personne saisit puis « Continuer »
    if (!res || !res.ok) { replay.status = "error"; replay.index += 1; return; }
    replay.index += 1;
    if (replay.status === "running") setTimeout(replayStep, 250);
  }
  async function startReplay(payload) {
    if (!payload || !payload.script) return { error: "script absent" };
    // l'onglet de rejeu : l'onglet actif s'il n'est pas une page de l'extension (popup ouvert dans un onglet), sinon le dernier onglet ordinaire, sinon un nouvel onglet
    const all = await B.tabs.query({ currentWindow: true });
    const ordinary = all.filter((t) => t.url && !/^(moz|chrome)-extension:/.test(t.url));
    const tab = ordinary.find((t) => t.active) || ordinary[ordinary.length - 1] || (await B.tabs.create({ url: "about:blank" }));
    Object.assign(replay, { status: "running", script: payload.script, index: 0, tabId: tab.id, baseUrl: payload.base_url || null, log: [], journey: payload.journey || null });
    setTimeout(replayStep, 100);
    return { ok: true, tabId: tab.id, actions: payload.script.length };
  }
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
