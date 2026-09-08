(function () {
  "use strict";
  const B = typeof browser !== "undefined" ? browser : chrome;
  const $ = (id) => document.getElementById(id);
  let cfg = null;
  async function relay(path, body) {
    const base = (cfg && cfg.relayUrl || "http://127.0.0.1:6320").replace(/\/+$/, "");
    const res = await fetch(base + path, body ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) } : {});
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.error || ("relais HTTP " + res.status));
    return data;
  }
  async function refresh() {
    const s = await B.runtime.sendMessage({ type: "status" });
    cfg = s.cfg;
    const j = cfg.journey;
    $("start").hidden = !!j; $("running").hidden = !j;
    $("stats").textContent = `${s.stats.sent} envoyé(s), ${s.stats.queued} en attente` + (s.stats.lastError ? ` — ${s.stats.lastError}` : "");
    try {
      const st = await relay("/status");
      $("status").innerHTML = (j ? `<span class="on">Enregistrement : ${j.name || j.id}</span> (${j.app})<br>` : "Aucun parcours en cours.<br>") +
        `Relais : ${st.pending} en file, ${st.sent} transmis, central ${st.central_url}` + (st.last_error ? `<br><span class="err">${st.last_error}</span>` : "") +
        (cfg.bases && cfg.bases.length ? `<br>Périmètre : ${cfg.bases.join(", ")}` : `<br><span class="err">Périmètre non défini : toutes les pages seraient enregistrées — voir Options.</span>`);
    } catch (e) {
      $("status").innerHTML = `<span class="err">Relais injoignable (${cfg.relayUrl}) : ${e.message}</span><br>Lancer : python3 relay.py --config relay.json`;
    }
  }
  $("btnStart").onclick = async () => {
    try {
      const app = $("app").value.trim(); if (!app) return alert("libellé d'application requis");
      const bases = cfg.bases || [];
      const j = await relay("/journeys", { app: app, name: $("name").value.trim(), tester: $("tester").value.trim(), base_url: bases[0] || null });
      await B.storage.local.set({ journey: { id: j.id, app: j.app, name: j.name, started_at: j.started_at } });
      await B.runtime.sendMessage({ type: "reload" });
      await refresh();
    } catch (e) { alert("démarrage impossible : " + e.message); }
  };
  $("btnMark").onclick = async () => { await B.runtime.sendMessage({ type: "mark", label: $("label").value.trim() || "repère" }); $("label").value = ""; await refresh(); };
  $("btnStop").onclick = async () => {
    try {
      const j = cfg.journey;
      await B.runtime.sendMessage({ type: "flush" });
      await relay(`/journeys/${j.id}/end`, { notes: null });
      await B.storage.local.set({ journey: null });
      await B.runtime.sendMessage({ type: "reload" });
      await refresh();
    } catch (e) { alert("fin impossible : " + e.message); }
  };
  $("opts").onclick = (e) => { e.preventDefault(); B.runtime.openOptionsPage(); };
  refresh();
})();
