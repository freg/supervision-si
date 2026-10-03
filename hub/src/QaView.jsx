import React, { useState, useEffect, useCallback } from "react";
import { getCatalog, listSites, createSite, updateSite, deleteSite, probeSite, listScenarios, createScenario, updateScenario, deleteScenario, runScenario, listRuns, runCampaign, listCampaigns, createTicket, shotUrl } from "./qaClient.js";
import { emptyStep, fieldsFor, validateSteps, loginFromProbe, runBadge, campaignSummary } from "./qaLib.js";
import HubIcon from "./HubIcon.jsx";

// Tuile « Tests QA en ligne » (hub), livraison #651 -- teste un site DÉPLOYÉ,
// porté par l'IA de portage ou non : sites (URL + étapes de connexion),
// scénarios pas à pas joués dans Chromium (qa-api, captures par étape),
// mode QA : depuis une exécution, créer un ticket Incident ou Évolution
// (module Tickets) -- le scénario devient alors un test TRAVERSANT de
// non-régression, rejoué en campagne site par site.
// Non vérifié en navigateur (pas de `npm run build`) : syntaxe @babel/parser,
// logique pure testée sous Node.

// Hors du composant : un sous-composant défini DANS QaView serait recréé à chaque
// rendu et chaque frappe ferait perdre le focus aux champs (piège React classique).
function StepsEditor({ steps, catalog, onChange, onMove, onRemove, onAdd }) {
  return (
    <table className="qa-table qa-steps">
      <thead><tr><th>#</th><th>Action</th><th>Sélecteur (CSS)</th><th>Valeur / texte / URL</th><th>Note</th><th></th></tr></thead>
      <tbody>{steps.map((s, i) => { const f = fieldsFor(s.action, catalog); return (
        <tr key={i}><td>{i + 1}</td>
          <td><select value={s.action} onChange={(e) => onChange(i, "action", e.target.value)}>{catalog.map((a) => <option key={a.id} value={a.id}>{a.label}</option>)}</select></td>
          <td>{f.includes("selector") ? <input type="text" value={s.selector} onChange={(e) => onChange(i, "selector", e.target.value)} placeholder="#id, .classe, a[href='/x']" /> : <span className="muted">—</span>}</td>
          <td>{f.includes("value") || s.action === "expect_text" ? <input type={/mot de passe|password/i.test(s.note || s.selector) ? "password" : "text"} value={s.value} onChange={(e) => onChange(i, "value", e.target.value)} /> : <span className="muted">—</span>}</td>
          <td><input type="text" value={s.note || ""} onChange={(e) => onChange(i, "note", e.target.value)} /></td>
          <td className="qa-actions"><button className="secondary" onClick={() => onMove(i, -1)} title="monter">↑</button><button className="secondary" onClick={() => onMove(i, 1)} title="descendre">↓</button><button className="secondary" onClick={() => onRemove(i)} title="retirer">✕</button></td></tr>); })}
      </tbody>
      <tfoot><tr><td colSpan={6}><button className="secondary" onClick={onAdd}>+ Étape</button></td></tr></tfoot>
    </table>
  );
}

export default function QaView({ onBack, qaApiBase, login }) {
  const [catalog, setCatalog] = useState([]);
  const [sites, setSites] = useState([]);
  const [site, setSite] = useState(null);
  const [siteForm, setSiteForm] = useState(null);     // {name, base_url, notes, ported, login_steps}
  const [scenarios, setScenarios] = useState([]);
  const [editing, setEditing] = useState(null);      // {id?, name, kind, steps}
  const [run, setRun] = useState(null);              // dernière exécution affichée
  const [runs, setRuns] = useState([]);
  const [campaign, setCampaign] = useState(null);
  const [campaigns, setCampaigns] = useState([]);
  const [probe, setProbe] = useState(null);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState(null);
  const [ticketForm, setTicketForm] = useState(null);   // {runId, kind, comment}

  const refreshSites = useCallback(async () => { const r = await listSites(qaApiBase); if (r.error) setError(r.error); else setSites(r.sites || []); }, [qaApiBase]);
  useEffect(() => { getCatalog(qaApiBase).then((r) => !r.error && setCatalog(r.actions || [])); refreshSites(); }, [qaApiBase, refreshSites]);

  async function openSite(s) {
    setSite(s); setEditing(null); setRun(null); setRuns([]); setCampaign(null); setProbe(null); setError(null); setNotice(null); setTicketForm(null);
    setSiteForm({ name: s.name, base_url: s.base_url, notes: s.notes || "", ported: !!s.ported, login_steps: s.login_steps || [] });
    const [x, c] = await Promise.all([listScenarios(qaApiBase, s.id), listCampaigns(qaApiBase, s.id)]);
    if (!x.error) setScenarios(x.scenarios || []); if (!c.error) setCampaigns(c.campaigns || []);
  }
  async function saveSite() {
    setBusy("site"); setError(null);
    const r = site ? await updateSite(qaApiBase, site.id, siteForm) : await createSite(qaApiBase, siteForm); setBusy("");
    if (r.error) { setError(r.error); return; }
    await refreshSites(); openSite(r.site); setNotice("Site enregistré");
  }
  async function removeSite() {
    if (!window.confirm(`Supprimer le site « ${site.name} », ses scénarios et ses exécutions ?`)) return;
    const r = await deleteSite(qaApiBase, site.id); if (r.error) setError(r.error); else { setSite(null); setSiteForm(null); refreshSites(); }
  }
  async function doProbe() {
    setBusy("probe"); setError(null); const r = await probeSite(qaApiBase, site.id); setBusy("");
    if (r.error) setError(r.error); else { setProbe(r.probe); setNotice(`Reconnaissance : « ${r.probe.title || "sans titre"} », HTTP ${r.probe.status}, ${r.probe.forms.length} formulaire(s), ${r.probe.links.length} lien(s)`); }
  }
  function adoptLogin() {
    const s = loginFromProbe(probe, "/"); if (!s) { setError("Aucun formulaire avec mot de passe trouvé sur cette page"); return; }
    setSiteForm((f) => ({ ...f, login_steps: s })); setNotice("Étapes de connexion proposées : complétez identifiant et mot de passe, puis enregistrez le site");
  }
  async function saveScenario() {
    const msg = validateSteps(editing.steps, catalog); if (msg) { setError(msg); return; }
    if (!editing.name.trim()) { setError("Nom du scénario obligatoire"); return; }
    setBusy("scenario"); setError(null);
    const r = editing.id ? await updateScenario(qaApiBase, editing.id, editing) : await createScenario(qaApiBase, site.id, editing); setBusy("");
    if (r.error) { setError(r.error); return; }
    const x = await listScenarios(qaApiBase, site.id); if (!x.error) setScenarios(x.scenarios); setEditing(r.scenario); setNotice("Scénario enregistré");
  }
  async function removeScenario(x) {
    if (!window.confirm(`Supprimer le scénario « ${x.name} » et ses exécutions ?`)) return;
    const r = await deleteScenario(qaApiBase, x.id); if (r.error) setError(r.error); else { setEditing(null); setRun(null); const l = await listScenarios(qaApiBase, site.id); if (!l.error) setScenarios(l.scenarios); }
  }
  async function play(x) {
    setBusy("run" + x.id); setError(null); setNotice(null); setTicketForm(null);
    const r = await runScenario(qaApiBase, x.id, login); setBusy("");
    if (r.error) { setError(r.error); return; }
    setRun({ ...r.run, scenario: x }); const l = await listScenarios(qaApiBase, site.id); if (!l.error) setScenarios(l.scenarios);
    const h = await listRuns(qaApiBase, x.id); if (!h.error) setRuns(h.runs);
  }
  async function showHistory(x) { const h = await listRuns(qaApiBase, x.id); if (!h.error) { setRuns(h.runs); setRun(h.runs[0] ? { ...h.runs[0], scenario: x } : null); } }
  async function playCampaign(kind) {
    setBusy("campaign"); setError(null); const r = await runCampaign(qaApiBase, site.id, kind, login); setBusy("");
    if (r.error) { setError(r.error); return; }
    setCampaign(r); const c = await listCampaigns(qaApiBase, site.id); if (!c.error) setCampaigns(c.campaigns); const l = await listScenarios(qaApiBase, site.id); if (!l.error) setScenarios(l.scenarios);
  }
  async function submitTicket() {
    setBusy("ticket"); setError(null); const r = await createTicket(qaApiBase, ticketForm.runId, { kind: ticketForm.kind, comment: ticketForm.comment }); setBusy("");
    if (r.error) { setError(r.error); return; }
    setTicketForm(null); setNotice(`Ticket n°${r.ticket_id} créé (${r.kind === "incident" ? "incident" : "évolution"}) : le scénario est désormais un test de non-régression`);
    if (run && run.id === r.run.id) setRun({ ...r.run, scenario: r.scenario }); const l = await listScenarios(qaApiBase, site.id); if (!l.error) setScenarios(l.scenarios);
  }

  const setStep = (i, k, v) => setEditing((e) => ({ ...e, steps: e.steps.map((s, j) => (j === i ? { ...s, [k]: v } : s)) }));
  const moveStep = (i, dir) => setEditing((e) => { const st = [...e.steps]; const j = i + dir; if (j < 0 || j >= st.length) return e; [st[i], st[j]] = [st[j], st[i]]; return { ...e, steps: st }; });
  const setLoginStep = (i, k, v) => setSiteForm((f) => ({ ...f, login_steps: f.login_steps.map((s, j) => (j === i ? { ...s, [k]: v } : s)) }));


  return (
    <div className="hub-settings hub-settings-wide qa-view">
      <div className="hub-settings-topbar">
        <button className="secondary" onClick={site ? () => { setSite(null); setSiteForm(null); refreshSites(); } : onBack}>◀ {site ? "Sites" : "Retour"}</button>
        <h1><HubIcon icon="shield-check" size={22} /> Tests QA en ligne{site ? ` — ${site.name}` : ""}</h1>
      </div>
      {error && <div className="hub-card qa-error">⚠️ {error}</div>}
      {notice && <div className="hub-card qa-notice">{notice}</div>}

      {!site && !siteForm && (
        <>
          <div className="hub-card"><p className="muted" style={{ margin: 0 }}>
            Un site déployé (porté par l'IA de portage ou non), des scénarios joués pas à pas dans un vrai navigateur avec capture à chaque étape.
            Mode QA : une exécution en échec ou un manque constaté crée un ticket <b>incident</b> ou <b>évolution</b> ; le scénario devient alors un test
            traversant de <b>non-régression</b>, rejoué en campagne.</p></div>
          <div className="hub-card hub-settings-section">
            <div className="qa-row-between"><h2 style={{ margin: 0 }}>Sites ({sites.length})</h2>
              <button className="primary" onClick={() => setSiteForm({ name: "", base_url: "https://", notes: "", ported: false, login_steps: [] })}>+ Nouveau site</button></div>
            <table className="qa-table"><thead><tr><th>Site</th><th>URL</th><th>Porté</th><th>Scénarios</th><th>Non-régression</th><th>Dernière exécution</th></tr></thead>
              <tbody>{sites.map((s) => <tr key={s.id} className="qa-clickable" onClick={() => openSite(s)}><td><b>{s.name}</b></td><td className="muted">{s.base_url}</td><td>{s.ported ? "✔" : "—"}</td><td>{s.scenarios}</td><td>{s.nr}</td><td>{runBadge(s.last_status)}</td></tr>)}
                {sites.length === 0 && <tr><td colSpan={6} className="muted">Aucun site : ajoutez-en un (URL de base, étapes de connexion).</td></tr>}</tbody></table>
          </div>
        </>
      )}

      {siteForm && (
        <div className="qa-columns">
          <div className="qa-col">
            <div className="hub-card hub-settings-section">
              <h2>Site</h2>
              <div className="qa-grid">
                <div className="hub-settings-row"><label>Nom</label><input type="text" value={siteForm.name} onChange={(e) => setSiteForm({ ...siteForm, name: e.target.value })} /></div>
                <div className="hub-settings-row"><label>URL de base</label><input type="text" value={siteForm.base_url} onChange={(e) => setSiteForm({ ...siteForm, base_url: e.target.value })} /></div>
                <div className="hub-settings-row"><label>Notes</label><input type="text" value={siteForm.notes} onChange={(e) => setSiteForm({ ...siteForm, notes: e.target.value })} /></div>
                <label className="qa-check"><input type="checkbox" checked={siteForm.ported} onChange={(e) => setSiteForm({ ...siteForm, ported: e.target.checked })} /> application portée (Python)</label>
              </div>
              <h3>Étapes de connexion <span className="muted">(jouées avant chaque scénario ; vide = site sans authentification)</span></h3>
              <StepsEditor steps={siteForm.login_steps} catalog={catalog} onChange={setLoginStep} onMove={(i, d) => setSiteForm((f) => { const st = [...f.login_steps]; const j = i + d; if (j < 0 || j >= st.length) return f; [st[i], st[j]] = [st[j], st[i]]; return { ...f, login_steps: st }; })}
                onRemove={(i) => setSiteForm((f) => ({ ...f, login_steps: f.login_steps.filter((_, j) => j !== i) }))} onAdd={() => setSiteForm((f) => ({ ...f, login_steps: [...f.login_steps, emptyStep(f.login_steps.length ? "fill" : "goto")] }))} />
              <div className="qa-inline">
                <button className="primary" onClick={saveSite} disabled={busy === "site"}>Enregistrer le site</button>
                {site && <button className="secondary" onClick={doProbe} disabled={busy === "probe"}>{busy === "probe" ? "Reconnaissance…" : "Reconnaître la page d'accueil"}</button>}
                {probe && <button className="secondary" onClick={adoptLogin}>Proposer les étapes de connexion</button>}
                {site && <button className="secondary qa-danger" onClick={removeSite}>Supprimer</button>}
              </div>
              {probe && (
                <details className="qa-details" open><summary>Reconnaissance : {probe.title} (HTTP {probe.status})</summary>
                  {probe.headings.length > 0 && <p className="muted">Titres : {probe.headings.join(" · ")}</p>}
                  {probe.forms.map((f, i) => <p key={i} className="muted">Formulaire {i + 1} ({f.method} {f.action || "—"}) : {f.fields.map((x) => `${x.tag}${x.type ? `[${x.type}]` : ""} ${x.id ? "#" + x.id : x.name ? `[name=${x.name}]` : ""}`).join(", ")}</p>)}
                  {probe.links.length > 0 && <p className="muted">Liens : {probe.links.slice(0, 25).map((l) => `${l.text || "(sans texte)"} → ${l.href}`).join(" · ")}</p>}
                </details>
              )}
            </div>

            {site && (
              <div className="hub-card hub-settings-section">
                <div className="qa-row-between"><h2 style={{ margin: 0 }}>Scénarios ({scenarios.length})</h2>
                  <div className="qa-inline">
                    <button className="secondary" onClick={() => playCampaign("non-regression")} disabled={busy === "campaign"}>{busy === "campaign" ? "Campagne…" : "▶ Campagne de non-régression"}</button>
                    <button className="secondary" onClick={() => playCampaign("all")} disabled={busy === "campaign"}>▶ Tout rejouer</button>
                    <button className="primary" onClick={() => { setEditing({ name: "", kind: "qa", steps: [emptyStep("goto")] }); setRun(null); }}>+ Scénario</button>
                  </div></div>
                <table className="qa-table"><thead><tr><th>Scénario</th><th>Nature</th><th>Étapes</th><th>Ticket</th><th>Dernier résultat</th><th></th></tr></thead>
                  <tbody>{scenarios.map((x) => <tr key={x.id} className={editing && editing.id === x.id ? "qa-selected" : ""}>
                    <td><a href="#" onClick={(e) => { e.preventDefault(); setEditing(x); showHistory(x); }}><b>{x.name}</b></a></td>
                    <td>{x.kind === "non-regression" ? "non-régression" : "QA"}</td><td>{x.steps.length}</td><td>{x.ticket_id ? `n°${x.ticket_id}` : "—"}</td>
                    <td>{runBadge(x.last_status)}{x.last_run_at ? <span className="muted"> {x.last_run_at.replace("T", " ")}</span> : null}</td>
                    <td className="qa-actions"><button className="primary" onClick={() => play(x)} disabled={busy === "run" + x.id}>{busy === "run" + x.id ? "…" : "▶"}</button></td></tr>)}
                    {scenarios.length === 0 && <tr><td colSpan={6} className="muted">Aucun scénario.</td></tr>}</tbody></table>
                {campaign && (
                  <div className="qa-campaign"><h3>Campagne n°{campaign.campaign.id} : {campaignSummary(campaign.runs).passed}/{campaignSummary(campaign.runs).total} réussis ({campaignSummary(campaign.runs).ratio} %)</h3>
                    <table className="qa-table"><tbody>{campaign.runs.map((r) => <tr key={r.id}><td>{r.scenario_name}</td><td className={r.status === "ok" ? "qa-ok" : "qa-ko"}>{runBadge(r.status)}</td><td className="muted">{r.summary.first_failure}</td>
                      <td><button className="secondary" onClick={() => { setRun({ ...r, scenario: scenarios.find((x) => x.id === r.scenario_id) }); }}>détail</button></td></tr>)}</tbody></table></div>
                )}
                {campaigns.length > 0 && <p className="muted">Campagnes précédentes : {campaigns.slice(0, 8).map((c) => `${c.started_at.replace("T", " ")} ${c.passed}/${c.total}`).join(" · ")}</p>}
              </div>
            )}
          </div>

          <div className="qa-col">
            {editing && (
              <div className="hub-card hub-settings-section">
                <h2>{editing.id ? `Scénario n°${editing.id}` : "Nouveau scénario"}</h2>
                <div className="qa-grid">
                  <div className="hub-settings-row"><label>Nom</label><input type="text" value={editing.name} onChange={(e) => setEditing({ ...editing, name: e.target.value })} /></div>
                  <div className="hub-settings-row"><label>Nature</label><select value={editing.kind} onChange={(e) => setEditing({ ...editing, kind: e.target.value })}><option value="qa">QA (exploration)</option><option value="non-regression">non-régression (test traversant)</option></select></div>
                </div>
                <StepsEditor steps={editing.steps} catalog={catalog} onChange={setStep} onMove={moveStep} onRemove={(i) => setEditing((e) => ({ ...e, steps: e.steps.filter((_, j) => j !== i) }))} onAdd={() => setEditing((e) => ({ ...e, steps: [...e.steps, emptyStep("click")] }))} />
                <div className="qa-inline">
                  <button className="primary" onClick={saveScenario} disabled={busy === "scenario"}>Enregistrer</button>
                  {editing.id && <button className="secondary" onClick={() => play(editing)} disabled={busy === "run" + editing.id}>▶ Jouer</button>}
                  {editing.id && <button className="secondary qa-danger" onClick={() => removeScenario(editing)}>Supprimer</button>}
                </div>
              </div>
            )}

            {run && (
              <div className="hub-card hub-settings-section">
                <h2>Exécution n°{run.id} — {run.scenario ? run.scenario.name : ""} <span className={run.status === "ok" ? "qa-ok" : "qa-ko"}>{runBadge(run.status)}</span></h2>
                <p className="muted">{run.started_at.replace("T", " ")} · {run.summary.passed}/{run.summary.total} étapes · {run.final_url}{run.error ? ` · ${run.error}` : ""}{run.ticket_id ? ` · ticket n°${run.ticket_id} (${run.ticket_kind})` : ""}</p>
                <table className="qa-table"><thead><tr><th>#</th><th>Action</th><th>Résultat</th><th>ms</th><th>Capture</th></tr></thead>
                  <tbody>{run.results.map((r, i) => <tr key={i} className={r.ok ? "" : "qa-row-ko"}><td>{r.login ? `connexion ${-r.index}` : r.index}</td><td>{r.action}</td><td className={r.ok ? "qa-ok" : "qa-ko"}>{r.ok ? "✔" : `✘ ${r.error}`}</td><td className="muted">{r.duration_ms}</td>
                    <td>{r.shot ? <a href={shotUrl(qaApiBase, run.id, r.shot)} target="_blank" rel="noreferrer"><img className="qa-thumb" src={shotUrl(qaApiBase, run.id, r.shot)} alt={`étape ${r.index}`} /></a> : ""}</td></tr>)}</tbody></table>
                {!run.ticket_id && !ticketForm && (
                  <div className="qa-inline"><button className="primary" onClick={() => setTicketForm({ runId: run.id, kind: "incident", comment: "" })}>Ticket incident</button>
                    <button className="secondary" onClick={() => setTicketForm({ runId: run.id, kind: "evolution", comment: "" })}>Ticket évolution</button>
                    <span className="muted">Le scénario devient un test traversant de non-régression.</span></div>
                )}
                {ticketForm && ticketForm.runId === run.id && (
                  <div className="qa-ticket"><div className="hub-settings-row"><label>Commentaire ({ticketForm.kind === "incident" ? "incident constaté" : "évolution souhaitée"}) — le déroulé pas à pas est ajouté automatiquement</label>
                    <textarea rows={3} value={ticketForm.comment} onChange={(e) => setTicketForm({ ...ticketForm, comment: e.target.value })} /></div>
                    <div className="qa-inline"><button className="primary" onClick={submitTicket} disabled={busy === "ticket"}>Créer le ticket</button><button className="secondary" onClick={() => setTicketForm(null)}>Annuler</button></div></div>
                )}
                {runs.length > 1 && <p className="muted">Historique : {runs.map((r) => <button key={r.id} className={`qa-mini ${r.id === run.id ? "qa-selected" : ""}`} onClick={() => setRun({ ...r, scenario: run.scenario })}>{runBadge(r.status).slice(0, 1)} {r.started_at.slice(5, 16).replace("T", " ")}</button>)}</p>}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
