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
  async function loadJourneys() {
    const app = ($("app").value || (cfg.journey && cfg.journey.app) || "").trim();
    $("existingApp").textContent = app ? `(${app})` : "";
    if (!app) { $("journeys").innerHTML = ""; return; }
    try {
      const d = await relay(`/journeys?app=${encodeURIComponent(app)}`);
      $("journeys").innerHTML = (d.journeys || []).map((x) => `<option value="${x.id}" data-status="${x.status}">${x.name || x.id} · ${x.status === "recording" ? "en cours" : "terminé"} · ${x.events_count} év.${x.parent_id ? " (sous-parcours)" : ""}</option>`).join("");
    } catch (e) { $("journeys").innerHTML = ""; }
  }
  async function refreshReplay() {
    const r = await B.runtime.sendMessage({ type: "replay-status" });
    const box = $("replayBox");
    if (!r || r.status === "idle") { box.hidden = true; return; }
    box.hidden = false;
    const cur = r.current ? `${r.current.action}${r.current.field ? " " + r.current.field : ""}${r.current.expect_path ? " " + r.current.expect_path : ""}` : "—";
    const last = r.log[r.log.length - 1];
    $("replayStatus").innerHTML = `Rejeu : <b>${r.status}</b> ${r.index}/${r.total} · prochaine : ${cur}` + (last && !last.ok ? `<br><span class="err">${last.needs_input ? "valeur non enregistrée pour « " + (r.log[r.log.length - 1].field || "") + "» : saisissez-la dans la page puis Continuer" : last.error}</span>` : "");
    $("btnContinue").hidden = !(r.status === "paused" || r.status === "error");
  }
  async function refresh() {
    const s = await B.runtime.sendMessage({ type: "status" });
    cfg = s.cfg;
    const j = cfg.journey;
    $("start").hidden = !!j; $("running").hidden = !j;
    if (j && j.app) $("app").value = j.app;
    await loadJourneys(); await refreshReplay();
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
  $("app").onchange = loadJourneys;
  $("btnAdopt").onclick = async () => {
    const id = $("journeys").value; if (!id) return;
    try {
      const j = await relay(`/journeys/${id}/adopt`, {});
      await B.storage.local.set({ journey: { id: j.id, app: j.app, name: j.name, started_at: j.started_at, parent_id: j.parent_id, branch_step: j.branch_step } });
      await B.runtime.sendMessage({ type: "reload" }); await refresh();
    } catch (e) { alert("reprise impossible : " + e.message); }
  };
  $("btnReplay").onclick = async () => {
    const id = $("journeys").value; if (!id) return;
    try {
      const r = await relay("/replay", { journey_id: id, tester: $("tester").value.trim() || null });
      await B.storage.local.set({ journey: { id: r.journey.id, app: r.journey.app, name: r.journey.name, started_at: r.journey.started_at, parent_id: id, kind: "replay" } });
      await B.runtime.sendMessage({ type: "reload" });
      await B.runtime.sendMessage({ type: "replay-start", payload: { script: r.script, base_url: r.base_url, journey: r.journey } });
      await refresh();
    } catch (e) { alert("rejeu impossible : " + e.message); }
  };
  $("btnContinue").onclick = async () => { await B.runtime.sendMessage({ type: "replay-continue" }); await refreshReplay(); };
  $("btnAbort").onclick = async () => { await B.runtime.sendMessage({ type: "replay-stop" }); await refreshReplay(); };
  setInterval(refreshReplay, 1500);
  refresh();
})();
