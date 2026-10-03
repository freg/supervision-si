import React, { useState, useEffect, useCallback } from "react";
import { fetchProxmox, vmAction, fetchCommand, fetchPraPlans, createPraPlan, updatePraPlan, deletePraPlan, runPraPlan, fetchPraRun, fetchPraRuns } from "./siAgentClient.js";
import { OPS, FIELD_LABELS, flattenProxmox, otherNodes, makeStep, runSummary, stepText } from "./pveOpsLib.js";
import HubIcon from "./HubIcon.jsx";

// Tuile « Contrôle PVE » (hub), livraison #653 -- supervision/contrôle de
// tous les Proxmox via l'agent de chaque hyperviseur : opérations
// immédiates (migration d'une VM vers un nœud, sauvegarde vzdump,
// déplacement de disque entre stockages, clonage, réplication pvesr) et
// PLANS (PRA, maintenance, bascule) = suites ordonnées d'opérations,
// simulées puis exécutées pas à pas par le central avec acquittement.
// Complète la tuile Proxmox (#488, lecture et actions unitaires).
// Non vérifié en navigateur ; logique pure testée sous Node.

function OpForm({ host, hosts, vm, action, onSubmit, onAddStep, busy }) {
  const [p, setP] = useState({ online: true, mode: "snapshot", schedule: "*/15" });
  const fields = OPS[action]?.fields || [];
  const set = (k, v) => setP((x) => ({ ...x, [k]: v }));
  return (
    <div className="pv-op">
      <div className="pv-grid">
        {fields.map((f) => (
          <div key={f} className="hub-settings-row"><label>{FIELD_LABELS[f] || f}</label>
            {f === "target" ? <select value={p.target || ""} onChange={(e) => set("target", e.target.value)}><option value="">—</option>{otherNodes(hosts, host.agent_id).map((n) => <option key={n} value={n}>{n}</option>)}</select>
              : f === "storage" ? <input type="text" list={`st-${host.agent_id}`} value={p.storage || ""} onChange={(e) => set("storage", e.target.value)} />
              : f === "mode" ? <select value={p.mode} onChange={(e) => set("mode", e.target.value)}><option value="snapshot">snapshot</option><option value="suspend">suspend</option><option value="stop">stop</option></select>
              : ["online", "with_local_disks"].includes(f) ? <label className="pv-check"><input type="checkbox" checked={!!p[f]} onChange={(e) => set(f, e.target.checked)} /> oui</label>
              : <input type="text" value={p[f] || ""} onChange={(e) => set(f, e.target.value)} />}
          </div>))}
        <datalist id={`st-${host.agent_id}`}>{host.storages.map((s) => <option key={s} value={s} />)}</datalist>
      </div>
      <div className="pv-inline">
        <button className="primary" disabled={busy} onClick={() => onSubmit(makeStep(host, vm, action, p))}>Exécuter maintenant</button>
        <button className="secondary" onClick={() => onAddStep(makeStep(host, vm, action, p))}>+ Ajouter au plan en cours</button>
      </div>
    </div>
  );
}

export default function PveOpsView({ onBack, siAgentApiBase, login }) {
  const [hosts, setHosts] = useState([]);
  const [plans, setPlans] = useState([]);
  const [sel, setSel] = useState(null);          // {host, vm, action}
  const [cmd, setCmd] = useState(null);          // dernière commande immédiate suivie
  const [plan, setPlan] = useState(null);        // plan en édition {id?, name, kind, notes, steps, continue_on_error}
  const [run, setRun] = useState(null);
  const [runs, setRuns] = useState([]);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState(null);

  const load = useCallback(async () => {
    const [p, pl] = await Promise.all([fetchProxmox(siAgentApiBase), fetchPraPlans(siAgentApiBase)]);
    setHosts(flattenProxmox(p)); if (!pl.error) setPlans(pl.plans || []);
  }, [siAgentApiBase]);
  useEffect(() => { load(); }, [load]);

  // suivi d'une commande immédiate puis d'une exécution de plan
  useEffect(() => {
    if (!cmd || !["pending"].includes(cmd.status)) return undefined;
    const id = setInterval(async () => { const c = await fetchCommand(siAgentApiBase, cmd.id); if (c && c.status !== "pending") { setCmd(c); load(); } }, 3000);
    return () => clearInterval(id);
  }, [cmd, siAgentApiBase, load]);
  useEffect(() => {
    if (!run || run.status !== "running") return undefined;
    const id = setInterval(async () => { const r = await fetchPraRun(siAgentApiBase, run.id); if (!r.error) { setRun(r.run); if (r.run.status !== "running") { load(); if (plan?.id) fetchPraRuns(siAgentApiBase, plan.id).then((x) => !x.error && setRuns(x.runs)); } } }, 3000);
    return () => clearInterval(id);
  }, [run, siAgentApiBase, load, plan]);

  async function execNow(step) {
    if (!window.confirm(`${stepText(step)} — exécuter maintenant sur ${step.agent_id} ?`)) return;
    setBusy("now"); setError(null); const r = await vmAction(siAgentApiBase, step.agent_id, { ...step.params, vmid: step.vmid, action: step.action, kind: step.kind }); setBusy("");
    if (r?.error) { setError(r.error); return; }
    setCmd(r?.command || r); setNotice(`Commande envoyée à ${step.agent_id} : ${stepText(step)}`);
  }
  function addStep(step) { setPlan((p) => ({ ...(p || { name: "Nouveau plan", kind: "pra", notes: "", steps: [], continue_on_error: false }), steps: [...(p?.steps || []), step] })); setNotice("Étape ajoutée au plan en cours (à enregistrer)"); }
  async function savePlan() {
    setBusy("plan"); setError(null);
    const r = plan.id ? await updatePraPlan(siAgentApiBase, plan.id, plan) : await createPraPlan(siAgentApiBase, plan); setBusy("");
    if (r.error) { setError(r.error); return; }
    setPlan(r.plan); setNotice("Plan enregistré"); load();
  }
  async function openPlan(p) { setPlan(p); setRun(null); const x = await fetchPraRuns(siAgentApiBase, p.id); if (!x.error) { setRuns(x.runs); if (x.runs[0]) setRun(x.runs[0]); } }
  async function removePlan(p) { if (!window.confirm(`Supprimer le plan « ${p.name} » et son historique ?`)) return; const r = await deletePraPlan(siAgentApiBase, p.id); if (r.error) setError(r.error); else { setPlan(null); setRun(null); load(); } }
  async function launch(mode) {
    if (mode === "execute" && !window.confirm(`Exécuter réellement le plan « ${plan.name} » (${plan.steps.length} étape(s)) ? Les opérations seront envoyées une à une aux hyperviseurs.`)) return;
    setBusy(mode); setError(null); const r = await runPraPlan(siAgentApiBase, plan.id, mode, login); setBusy("");
    if (r.error) { setError(r.error); return; }
    const x = await fetchPraRun(siAgentApiBase, r.run_id); if (!x.error) setRun(x.run);
  }
  const moveStep = (i, d) => setPlan((p) => { const st = [...p.steps]; const j = i + d; if (j < 0 || j >= st.length) return p; [st[i], st[j]] = [st[j], st[i]]; return { ...p, steps: st }; });

  return (
    <div className="hub-settings hub-settings-wide pv-view">
      <div className="hub-settings-topbar"><button className="secondary" onClick={onBack}>◀ Retour</button><h1><HubIcon icon="server" size={22} /> Contrôle PVE — opérations et plans de reprise</h1></div>
      {error && <div className="hub-card pv-error">⚠️ {error}</div>}
      {notice && <div className="hub-card pv-notice">{notice}</div>}
      <div className="pv-columns">
        <div className="pv-col">
          <div className="hub-card hub-settings-section">
            <h2>Hyperviseurs et VM <span className="muted">({hosts.length} nœud(s) remonté(s) par leur agent)</span></h2>
            {hosts.length === 0 && <p className="muted">Aucun hyperviseur : installez l'agent avec le plugin proxmox sur chaque nœud (tuile Agents hôtes).</p>}
            {hosts.map((h) => (
              <details key={h.agent_id} className="pv-details" open>
                <summary><b>{h.node}</b> <span className="muted">{h.agent_id} · {h.vms.length} VM/CT · stockages : {h.storages.join(", ") || "—"}</span></summary>
                <table className="pv-table"><thead><tr><th>ID</th><th>Nom</th><th>Type</th><th>État</th><th>Opération</th></tr></thead>
                  <tbody>{h.vms.map((vm) => (
                    <React.Fragment key={vm.vmid}>
                      <tr className={sel && sel.vm.vmid === vm.vmid && sel.host.agent_id === h.agent_id ? "pv-selected" : ""}><td>{vm.vmid}</td><td>{vm.name}</td><td>{vm.type}</td><td>{vm.status}</td>
                        <td><select value={sel && sel.vm.vmid === vm.vmid && sel.host.agent_id === h.agent_id ? sel.action : ""} onChange={(e) => setSel(e.target.value ? { host: h, vm, action: e.target.value } : null)}>
                          <option value="">—</option>{Object.entries(OPS).map(([k, o]) => <option key={k} value={k}>{o.label}</option>)}</select></td></tr>
                      {sel && sel.vm.vmid === vm.vmid && sel.host.agent_id === h.agent_id && <tr><td colSpan={5}><OpForm key={sel.action} host={h} hosts={hosts} vm={vm} action={sel.action} onSubmit={execNow} onAddStep={addStep} busy={busy === "now"} /></td></tr>}
                    </React.Fragment>))}</tbody></table>
              </details>))}
            {cmd && <div className={`pv-cmd ${cmd.status === "done" ? "pv-ok" : cmd.status === "failed" ? "pv-ko" : ""}`}>Commande {cmd.id} : {cmd.status === "pending" ? "en attente d'acquittement de l'agent…" : cmd.status === "done" ? "terminée" : `échec — ${cmd.result?.error || ""}`}{cmd.result?.result?.stdout ? <pre className="pv-log">{cmd.result.result.stdout}</pre> : null}</div>}
          </div>
        </div>
        <div className="pv-col">
          <div className="hub-card hub-settings-section">
            <div className="pv-row-between"><h2 style={{ margin: 0 }}>Plans ({plans.length})</h2><button className="primary" onClick={() => { setPlan({ name: "Nouveau plan", kind: "pra", notes: "", steps: [], continue_on_error: false }); setRun(null); setRuns([]); }}>+ Plan</button></div>
            <table className="pv-table"><thead><tr><th>Plan</th><th>Nature</th><th>Étapes</th><th>Dernière exécution</th><th></th></tr></thead>
              <tbody>{plans.map((p) => <tr key={p.id} className={plan && plan.id === p.id ? "pv-selected" : ""}><td><a href="#" onClick={(e) => { e.preventDefault(); openPlan(p); }}><b>{p.name}</b></a></td><td>{p.kind}</td><td>{p.steps.length}</td>
                <td className="muted">{p.last_run ? `${p.last_run.mode} · ${p.last_run.status} · ${(p.last_run.started_at || "").replace("T", " ").slice(0, 16)}` : "—"}</td><td><button className="secondary pv-mini pv-danger" onClick={() => removePlan(p)}>✕</button></td></tr>)}
                {plans.length === 0 && <tr><td colSpan={5} className="muted">Aucun plan : choisissez une opération sur une VM puis « Ajouter au plan en cours », ou « + Plan ».</td></tr>}</tbody></table>
          </div>
          {plan && (
            <div className="hub-card hub-settings-section">
              <h2>{plan.id ? `Plan n°${plan.id}` : "Nouveau plan"}</h2>
              <div className="pv-grid">
                <div className="hub-settings-row"><label>Nom</label><input type="text" value={plan.name} onChange={(e) => setPlan({ ...plan, name: e.target.value })} /></div>
                <div className="hub-settings-row"><label>Nature</label><select value={plan.kind} onChange={(e) => setPlan({ ...plan, kind: e.target.value })}><option value="pra">PRA (reprise d'activité)</option><option value="maintenance">maintenance</option><option value="bascule">bascule de rôle</option><option value="migration">migration</option></select></div>
                <div className="hub-settings-row"><label>Notes</label><input type="text" value={plan.notes} onChange={(e) => setPlan({ ...plan, notes: e.target.value })} /></div>
                <label className="pv-check"><input type="checkbox" checked={!!plan.continue_on_error} onChange={(e) => setPlan({ ...plan, continue_on_error: e.target.checked })} /> continuer malgré une étape en échec</label>
              </div>
              <table className="pv-table"><thead><tr><th>#</th><th>Étape</th><th>Libellé</th><th></th></tr></thead>
                <tbody>{plan.steps.map((s, i) => <tr key={i}><td>{i + 1}</td><td>{stepText(s)}</td><td><input type="text" value={s.label || ""} onChange={(e) => setPlan((p) => ({ ...p, steps: p.steps.map((x, j) => (j === i ? { ...x, label: e.target.value } : x)) }))} /></td>
                  <td className="pv-actions"><button className="secondary pv-mini" onClick={() => moveStep(i, -1)}>↑</button><button className="secondary pv-mini" onClick={() => moveStep(i, 1)}>↓</button><button className="secondary pv-mini" onClick={() => setPlan((p) => ({ ...p, steps: p.steps.filter((_, j) => j !== i) }))}>✕</button></td></tr>)}
                  {plan.steps.length === 0 && <tr><td colSpan={4} className="muted">Aucune étape : choisissez une opération sur une VM à gauche puis « Ajouter au plan en cours ».</td></tr>}</tbody></table>
              <div className="pv-inline">
                <button className="primary" onClick={savePlan} disabled={busy === "plan" || plan.steps.length === 0}>Enregistrer</button>
                {plan.id && <button className="secondary" onClick={() => launch("simulate")} disabled={!!busy}>Simuler</button>}
                {plan.id && <button className="secondary pv-danger" onClick={() => launch("execute")} disabled={!!busy || (run && run.status === "running")}>▶ Exécuter</button>}
              </div>
              {run && (<div className="pv-run"><h3>Exécution n°{run.id} ({run.mode}) — <span className={run.status === "done" ? "pv-ok" : run.status === "failed" ? "pv-ko" : ""}>{run.status}</span> <span className="muted">{runSummary(run)}</span></h3>
                <table className="pv-table"><thead><tr><th>#</th><th>Étape</th><th>État</th><th>Détail</th></tr></thead>
                  <tbody>{run.steps.map((s, i) => <tr key={i} className={["failed", "timeout"].includes(s.status) || s.ok === false ? "pv-row-ko" : ""}><td>{s.index}</td><td>{stepText(s)}</td>
                    <td>{run.mode === "simulate" ? (s.ok ? "✔ prêt" : "✘") : s.status}</td><td className="muted">{s.error || s.result?.error || (s.hostname ? `${s.hostname}, vu ${(s.last_seen || "").replace("T", " ").slice(0, 16)}` : "") || s.result?.result?.stdout?.slice(0, 200) || ""}</td></tr>)}</tbody></table>
                {runs.length > 1 && <p className="muted">Historique : {runs.map((r) => <button key={r.id} className={`pv-mini ${run.id === r.id ? "pv-selected" : "secondary"}`} onClick={() => setRun(r)}>{r.mode === "simulate" ? "sim" : "exéc"} {r.status} {(r.started_at || "").slice(5, 16).replace("T", " ")}</button>)}</p>}
              </div>)}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
