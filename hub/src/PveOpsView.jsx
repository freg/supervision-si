import React, { useState, useEffect, useCallback } from "react";
import { fetchProxmox, vmAction, fetchCommand, fetchPraPlans, createPraPlan, updatePraPlan, deletePraPlan, runPraPlan, fetchPraRun, fetchPraRuns, fetchPraRoles, createPraRole, updatePraRole, deletePraRole, switchPraRole, checkPraRole } from "./siAgentClient.js";
import { OPS, FIELD_LABELS, flattenProxmox, otherNodes, makeStep, runSummary, stepText, replSummary } from "./pveOpsLib.js";
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
  const [roles, setRoles] = useState([]);          // #654 : rôles « celui qui répond »
  const [roleForm, setRoleForm] = useState(null);
  const [mikrotik, setMikrotik] = useState(false);
  const [sel, setSel] = useState(null);          // {host, vm, action}
  const [cmd, setCmd] = useState(null);          // dernière commande immédiate suivie
  const [plan, setPlan] = useState(null);        // plan en édition {id?, name, kind, notes, steps, continue_on_error}
  const [run, setRun] = useState(null);
  const [runs, setRuns] = useState([]);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState(null);

  const load = useCallback(async () => {
    const [p, pl, rl] = await Promise.all([fetchProxmox(siAgentApiBase), fetchPraPlans(siAgentApiBase), fetchPraRoles(siAgentApiBase)]);
    setHosts(flattenProxmox(p)); if (!pl.error) setPlans(pl.plans || []); if (!rl.error) { setRoles(rl.roles || []); setMikrotik(!!rl.mikrotik); }
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
  async function saveRole() {
    setBusy("role"); setError(null); const r = roleForm.id ? await updatePraRole(siAgentApiBase, roleForm.id, roleForm) : await createPraRole(siAgentApiBase, roleForm); setBusy("");
    if (r.error) { setError(r.error); return; } setRoleForm(null); load(); setNotice("Rôle enregistré");
  }
  async function doSwitch(role, to) {
    const c = role.candidates[to]; if (!window.confirm(`Basculer le rôle « ${role.name} » vers ${c.label} (${c.address}) ?${role.mechanism.kind === "mikrotik_nat" ? " La règle NAT du routeur sera modifiée." : " Mécanisme manuel : la redirection reste à faire."}`)) return;
    setBusy("switch"); setError(null); const r = await switchPraRole(siAgentApiBase, role.id, to, login); setBusy("");
    if (r.error && !r.role) { setError(r.error); return; }
    setNotice(r.ok ? `Rôle « ${r.role} » basculé vers ${r.to.label}${r.check?.checked ? ` — service vérifié (HTTP ${r.check.status}, ${r.check.ms} ms)` : ""}` : `Bascule appliquée mais ${r.error}`); load();
  }
  async function doCheck(role) { const r = await checkPraRole(siAgentApiBase, role.id); if (r.error) setError(r.error); else { setNotice(r.check.checked ? (r.check.ok ? `« ${role.name} » répond (HTTP ${r.check.status}, ${r.check.ms} ms)` : `« ${role.name} » ne répond pas : ${r.check.error || "HTTP " + r.check.status}`) : "Pas d'URL de service à vérifier"); load(); } }
  function addRoleStep(role, to) { addStep({ agent_id: "central", vmid: 0, kind: "qemu", action: "role_switch", role_id: role.id, to, params: { role_id: role.id, to }, label: `bascule ${role.name} → ${role.candidates[to].label}` }); }
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
                <table className="pv-table"><thead><tr><th>ID</th><th>Nom</th><th>Type</th><th>État</th><th>Réplication</th><th>Dernière sauvegarde</th><th>Opération</th></tr></thead>
                  <tbody>{h.vms.map((vm) => (
                    <React.Fragment key={vm.vmid}>
                      <tr className={sel && sel.vm.vmid === vm.vmid && sel.host.agent_id === h.agent_id ? "pv-selected" : ""}><td>{vm.vmid}</td><td>{vm.name}</td><td>{vm.type}</td><td>{vm.status}</td>
                        <td className={vm.replication.some((r) => !r.ok) ? "pv-ko" : ""}>{replSummary(vm.replication) || <span className="muted">—</span>}</td>
                        <td className={vm.last_backup && vm.last_backup.ok === false ? "pv-ko" : "muted"}>{vm.last_backup ? `${vm.last_backup.ok === false ? "✘" : "✔"} ${vm.last_backup.age_s !== undefined && vm.last_backup.age_s !== null ? "il y a " + Math.round(vm.last_backup.age_s / 3600) + " h" : ""}` : "—"}</td>
                        <td><select value={sel && sel.vm.vmid === vm.vmid && sel.host.agent_id === h.agent_id ? sel.action : ""} onChange={(e) => setSel(e.target.value ? { host: h, vm, action: e.target.value } : null)}>
                          <option value="">—</option>{Object.entries(OPS).map(([k, o]) => <option key={k} value={k}>{o.label}</option>)}</select></td></tr>
                      {sel && sel.vm.vmid === vm.vmid && sel.host.agent_id === h.agent_id && <tr><td colSpan={7}><OpForm key={sel.action} host={h} hosts={hosts} vm={vm} action={sel.action} onSubmit={execNow} onAddStep={addStep} busy={busy === "now"} /></td></tr>}
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
          <div className="hub-card hub-settings-section">
            <div className="pv-row-between"><h2 style={{ margin: 0 }}>Rôles — « celui qui répond » ({roles.length})</h2><button className="primary" onClick={() => setRoleForm({ name: "", service_url: "", notes: "", candidates: [{ label: "", address: "" }, { label: "", address: "" }], mechanism: { kind: mikrotik ? "mikrotik_nat" : "manual", router: "", rule_id: "" } })}>+ Rôle</button></div>
            <p className="muted">Un rôle = un service et ses candidats ordonnés ; la bascule change qui répond (règle NAT MikroTik modifiée, ou enregistrement manuel), puis vérifie l'URL du service. Une bascule peut être une étape de plan.</p>
            {roleForm && (
              <div className="pv-grid pv-form">
                <div className="hub-settings-row"><label>Nom</label><input type="text" value={roleForm.name} onChange={(e) => setRoleForm({ ...roleForm, name: e.target.value })} /></div>
                <div className="hub-settings-row"><label>URL du service (vérification)</label><input type="text" value={roleForm.service_url} onChange={(e) => setRoleForm({ ...roleForm, service_url: e.target.value })} placeholder="https://…" /></div>
                <div className="hub-settings-row"><label>Mécanisme</label><select value={roleForm.mechanism.kind} onChange={(e) => setRoleForm({ ...roleForm, mechanism: { ...roleForm.mechanism, kind: e.target.value } })}><option value="manual">manuel (enregistrement seul)</option><option value="mikrotik_nat" disabled={!mikrotik}>règle NAT MikroTik{mikrotik ? "" : " (MIKROTIK_API_URL absente)"}</option><option value="dns">enregistrement DNS (dns-api, intranet en fallback)</option><option value="keepalived">keepalived / VRRP (priorité sur les candidats)</option></select></div>
                {roleForm.mechanism.kind === "dns" && <><div className="hub-settings-row"><label>Zone</label><input type="text" value={roleForm.mechanism.zone || ""} onChange={(e) => setRoleForm({ ...roleForm, mechanism: { ...roleForm.mechanism, zone: e.target.value } })} placeholder="exemple.fr" /></div>
                  <div className="hub-settings-row"><label>Enregistrement (nom relatif) / TTL</label><div className="pv-inline"><input type="text" value={roleForm.mechanism.record || ""} onChange={(e) => setRoleForm({ ...roleForm, mechanism: { ...roleForm.mechanism, record: e.target.value } })} placeholder="www" /><input type="number" value={roleForm.mechanism.ttl || 60} onChange={(e) => setRoleForm({ ...roleForm, mechanism: { ...roleForm.mechanism, ttl: Number(e.target.value) } })} style={{ width: 80 }} /></div></div></>}
                {roleForm.mechanism.kind === "keepalived" && <div className="hub-settings-row"><label>Instance VRRP (chaque candidat doit porter l'agent_id de son hôte)</label><input type="text" value={roleForm.mechanism.instance || ""} onChange={(e) => setRoleForm({ ...roleForm, mechanism: { ...roleForm.mechanism, instance: e.target.value } })} placeholder="VI_WEB" /></div>}
                {roleForm.mechanism.kind === "mikrotik_nat" && <><div className="hub-settings-row"><label>Routeur (nom du registre)</label><input type="text" value={roleForm.mechanism.router} onChange={(e) => setRoleForm({ ...roleForm, mechanism: { ...roleForm.mechanism, router: e.target.value } })} /></div>
                  <div className="hub-settings-row"><label>Règle NAT (identifiant, ex. *1A)</label><input type="text" value={roleForm.mechanism.rule_id} onChange={(e) => setRoleForm({ ...roleForm, mechanism: { ...roleForm.mechanism, rule_id: e.target.value } })} /></div></>}
                <div className="pv-candidates">{roleForm.candidates.map((c, i) => <div key={i} className="pv-inline"><span className="muted">{i + 1}.</span><input type="text" placeholder="libellé" value={c.label} onChange={(e) => setRoleForm({ ...roleForm, candidates: roleForm.candidates.map((x, j) => (j === i ? { ...x, label: e.target.value } : x)) })} />
                  <input type="text" placeholder="adresse (IP[:port])" value={c.address} onChange={(e) => setRoleForm({ ...roleForm, candidates: roleForm.candidates.map((x, j) => (j === i ? { ...x, address: e.target.value } : x)) })} />
                  {roleForm.mechanism.kind === "keepalived" && <select value={c.agent_id || ""} onChange={(e) => setRoleForm({ ...roleForm, candidates: roleForm.candidates.map((x, j) => (j === i ? { ...x, agent_id: e.target.value } : x)) })}><option value="">agent de l'hôte…</option>{hosts.map((h) => <option key={h.agent_id} value={h.agent_id}>{h.agent_id}</option>)}</select>}
                  <button className="secondary pv-mini" onClick={() => setRoleForm({ ...roleForm, candidates: roleForm.candidates.filter((_, j) => j !== i) })}>✕</button></div>)}
                  <button className="secondary pv-mini" onClick={() => setRoleForm({ ...roleForm, candidates: [...roleForm.candidates, { label: "", address: "" }] })}>+ candidat</button></div>
                <div className="pv-inline"><button className="primary" onClick={saveRole} disabled={busy === "role"}>Enregistrer</button><button className="secondary" onClick={() => setRoleForm(null)}>Annuler</button></div>
              </div>
            )}
            <table className="pv-table"><thead><tr><th>Rôle</th><th>Répond actuellement</th><th>Mécanisme</th><th>Dernière vérification</th><th>Basculer vers</th><th></th></tr></thead>
              <tbody>{roles.map((r) => (
                <tr key={r.id}><td><b>{r.name}</b>{r.service_url && <div className="muted">{r.service_url}</div>}</td><td>{r.candidates[r.active] ? `${r.candidates[r.active].label} (${r.candidates[r.active].address})` : "—"}{r.last_switch_at && <div className="muted">{r.last_switch_at.replace("T", " ").slice(0, 16)}</div>}</td>
                  <td>{r.mechanism.kind === "mikrotik_nat" ? `NAT ${r.mechanism.router} ${r.mechanism.rule_id}` : r.mechanism.kind === "dns" ? `DNS ${r.mechanism.record}.${r.mechanism.zone}` : r.mechanism.kind === "keepalived" ? `VRRP ${r.mechanism.instance}` : "manuel"}</td>
                  <td className={r.last_check?.checked ? (r.last_check.ok ? "pv-ok" : "pv-ko") : "muted"}>{r.last_check?.checked ? (r.last_check.ok ? `✔ HTTP ${r.last_check.status}` : `✘ ${r.last_check.error || "HTTP " + r.last_check.status}`) : "—"}</td>
                  <td>{r.candidates.map((c, i) => i !== r.active && <button key={i} className="secondary pv-mini" disabled={busy === "switch"} onClick={() => doSwitch(r, i)} title={c.address}>{c.label}</button>)}</td>
                  <td className="pv-actions"><button className="secondary pv-mini" onClick={() => doCheck(r)}>vérifier</button>{r.candidates.map((c, i) => i !== r.active && <button key={i} className="secondary pv-mini" onClick={() => addRoleStep(r, i)} title="ajouter la bascule au plan en cours">+ plan → {c.label}</button>)}
                    <button className="secondary pv-mini" onClick={() => setRoleForm({ id: r.id, name: r.name, service_url: r.service_url, notes: r.notes, candidates: r.candidates, mechanism: { router: "", rule_id: "", ...r.mechanism } })}>éditer</button>
                    <button className="secondary pv-mini pv-danger" onClick={async () => { if (window.confirm(`Supprimer le rôle « ${r.name} » ?`)) { const x = await deletePraRole(siAgentApiBase, r.id); if (x.error) setError(x.error); else load(); } }}>✕</button></td></tr>))}
                {roles.length === 0 && <tr><td colSpan={6} className="muted">Aucun rôle déclaré.</td></tr>}</tbody></table>
          </div>
          {plan && (
            <div className="hub-card hub-settings-section">
              <h2>{plan.id ? `Plan n°${plan.id}` : "Nouveau plan"}</h2>
              <div className="pv-grid">
                <div className="hub-settings-row"><label>Nom</label><input type="text" value={plan.name} onChange={(e) => setPlan({ ...plan, name: e.target.value })} /></div>
                <div className="hub-settings-row"><label>Nature</label><select value={plan.kind} onChange={(e) => setPlan({ ...plan, kind: e.target.value })}><option value="pra">PRA (reprise d'activité)</option><option value="maintenance">maintenance</option><option value="bascule">bascule de rôle</option><option value="migration">migration</option></select></div>
                <div className="hub-settings-row"><label>Notes</label><input type="text" value={plan.notes} onChange={(e) => setPlan({ ...plan, notes: e.target.value })} /></div>
                <label className="pv-check"><input type="checkbox" checked={!!plan.continue_on_error} onChange={(e) => setPlan({ ...plan, continue_on_error: e.target.checked })} /> continuer malgré une étape en échec</label>
                <div className="hub-settings-row"><label>Déclencheur : perte de l'agent</label><select value={plan.trigger_agent_id || ""} onChange={(e) => setPlan({ ...plan, trigger_agent_id: e.target.value })}><option value="">aucun</option>{hosts.map((h) => <option key={h.agent_id} value={h.agent_id}>{h.node} ({h.agent_id})</option>)}</select></div>
                {plan.trigger_agent_id && <div className="hub-settings-row"><label>À la perte</label><select value={plan.trigger_mode || "notify"} onChange={(e) => setPlan({ ...plan, trigger_mode: e.target.value })}><option value="notify">proposer le plan (événement notifié)</option><option value="auto">LANCER automatiquement (délai de garde ci-dessous)</option></select></div>}
                {plan.trigger_agent_id && plan.trigger_mode === "auto" && <div className="hub-settings-row"><label>Délai de garde (s) entre deux lancements</label><input type="number" value={plan.trigger_cooldown_s || 3600} onChange={(e) => setPlan({ ...plan, trigger_cooldown_s: Number(e.target.value) })} /></div>}
              </div>
              <table className="pv-table"><thead><tr><th>#</th><th>Étape</th><th>Libellé</th><th></th></tr></thead>
                <tbody>{plan.steps.map((s, i) => <tr key={i}><td>{i + 1}</td><td>{stepText(s, roles)}</td><td><input type="text" value={s.label || ""} onChange={(e) => setPlan((p) => ({ ...p, steps: p.steps.map((x, j) => (j === i ? { ...x, label: e.target.value } : x)) }))} /></td>
                  <td className="pv-actions"><button className="secondary pv-mini" onClick={() => moveStep(i, -1)}>↑</button><button className="secondary pv-mini" onClick={() => moveStep(i, 1)}>↓</button><button className="secondary pv-mini" onClick={() => setPlan((p) => ({ ...p, steps: p.steps.filter((_, j) => j !== i) }))}>✕</button></td></tr>)}
                  {plan.steps.length === 0 && <tr><td colSpan={4} className="muted">Aucune étape : choisissez une opération sur une VM à gauche puis « Ajouter au plan en cours ».</td></tr>}</tbody></table>
              <div className="pv-inline">
                <button className="primary" onClick={savePlan} disabled={busy === "plan" || plan.steps.length === 0}>Enregistrer</button>
                {plan.id && <button className="secondary" onClick={() => launch("simulate")} disabled={!!busy}>Simuler</button>}
                {plan.id && <button className="secondary pv-danger" onClick={() => launch("execute")} disabled={!!busy || (run && run.status === "running")}>▶ Exécuter</button>}
              </div>
              {run && (<div className="pv-run"><h3>Exécution n°{run.id} ({run.mode}) — <span className={run.status === "done" ? "pv-ok" : run.status === "failed" ? "pv-ko" : ""}>{run.status}</span> <span className="muted">{runSummary(run)}</span></h3>
                <table className="pv-table"><thead><tr><th>#</th><th>Étape</th><th>État</th><th>Détail</th></tr></thead>
                  <tbody>{run.steps.map((s, i) => <tr key={i} className={["failed", "timeout"].includes(s.status) || s.ok === false ? "pv-row-ko" : ""}><td>{s.index}</td><td>{stepText(s, roles)}</td>
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
