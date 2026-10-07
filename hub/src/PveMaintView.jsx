// Tuile « Maintenance / réorganisation des Proxmox » (livraison #705). Données : si-agent-api /maint/* (maint.py).
//   - Campagnes : étapes et actions (manuelles ou opérations PVE exécutées par l'agent du nœud), avancement CONSTATÉ
//     par des détecteurs sur les mesures des agents (CT absent, sauvegarde récente, espace libre, stockage PBS, tâche…),
//     modèles (libérer un nœud, mettre en service un PBS, déplacer un CT en deux passes), édition, coches, simulation /
//     exécution ; une étape « après la précédente » reste bloquée tant que celle-ci n'est pas finie ;
//   - Planning : actions datées de toutes les campagnes (les opérations « auto » partent seules à l'heure si la campagne
//     est active) ;
//   - Sauvegardes : stockages (PBS compris), tâches planifiées, dernière sauvegarde de chaque CT/VM et anomalies.
import { useEffect, useState } from "react";
import HubIcon from "./HubIcon.jsx";
import { fetchMaintCatalog, fetchMaintCampaigns, fetchMaintCampaign, createMaintCampaign, updateMaintCampaign, deleteMaintCampaign,
  maintAction, maintTemplate, fetchMaintBackups } from "./siAgentClient.js";
import { STATE_LABEL, STATE_TONE, HOW_LABEL, STATUS_LABEL, detectorFields, paramsToText, textToParams, toLocalInput, fromLocalInput,
  emptyAction, plannedList, missingParams, move, gb } from "./pveMaintLib.js";

import { AutoColumns } from "./TableColumns.jsx";   // #707 : colonnes réglables
const when = (t) => (t ? new Date(t * 1000).toLocaleString("fr-FR", { dateStyle: "short", timeStyle: "short" }) : "—");
function Tone({ tone, children, title }) { return <span className={`np-tone ${tone || "neutral"}`} title={title}>{children}</span>; }
function Bar({ pct }) {
  return <span style={{ display: "inline-block", width: 120, height: 8, background: "var(--border)", borderRadius: 4, verticalAlign: "middle" }}>
    <span style={{ display: "block", width: `${pct}%`, height: 8, background: "var(--ok, #2e7d32)", borderRadius: 4 }} /></span>;
}
const box = { border: "1px solid var(--border)", borderRadius: 8, padding: 10, marginBottom: 10 };

export default function PveMaintView({ onBack, siAgentApiBase, login }) {
  const base = siAgentApiBase;
  const [tab, setTab] = useState("campagnes");
  const [catalog, setCatalog] = useState(null);
  const [list, setList] = useState(null);
  const [current, setCurrent] = useState(null);       // campagne ouverte (évaluée)
  const [draft, setDraft] = useState(null);           // campagne en édition (nouvelle ou existante)
  const [msg, setMsg] = useState(null);

  const loadList = async () => { const r = await fetchMaintCampaigns(base); if (r.error) setMsg({ error: r.error }); else setList(r.campaigns); };
  const open = async (id) => { const r = await fetchMaintCampaign(base, id); if (r.error) setMsg({ error: r.error }); else { setCurrent(r.campaign); setDraft(null); } };
  useEffect(() => {
    (async () => { const c = await fetchMaintCatalog(base); if (c.error) setMsg({ error: c.error }); else setCatalog(c); await loadList(); })();
    /* eslint-disable-next-line react-hooks/exhaustive-deps */
  }, [base]);
  useEffect(() => {                                   // constats rafraîchis chaque minute (hors édition)
    if (!current || draft) return undefined;
    const t = setInterval(() => open(current.id), 60000);
    return () => clearInterval(t);
    /* eslint-disable-next-line react-hooks/exhaustive-deps */
  }, [current?.id, draft]);

  const act = async (aid, op) => {
    if (op === "execute" && !window.confirm("Exécuter maintenant cette opération sur le Proxmox ?")) return;
    const r = await maintAction(base, current.id, aid, { op, actor: login });
    if (r.error) { setMsg({ error: r.error }); return; }
    setCurrent(r.campaign); setMsg(r.run_id ? { ok: `${op === "simulate" ? "Simulation" : "Exécution"} n°${r.run_id} lancée (suivi : tuile Contrôle PVE).` } : null);
    loadList();
  };
  const save = async () => {
    const body = { ...draft, actor: login };
    const r = draft.id ? await updateMaintCampaign(base, draft.id, body) : await createMaintCampaign(base, body);
    if (r.error) { setMsg({ error: r.error }); return; }
    setCurrent(r.campaign); setDraft(null); setMsg({ ok: "Campagne enregistrée." }); loadList();
  };
  const remove = async () => {
    if (!window.confirm(`Supprimer la campagne « ${current.name} » ? (les opérations déjà faites ne sont pas annulées)`)) return;
    const r = await deleteMaintCampaign(base, current.id);
    if (r.error) { setMsg({ error: r.error }); return; }
    setCurrent(null); loadList();
  };

  return (
    <div className="hub-settings">
      <div className="hub-settings-topbar"><button className="secondary" onClick={onBack}>◀ Retour</button>
        <h1><HubIcon icon="server" size={22} /> Maintenance des Proxmox</h1></div>
      <div className="na-section-tabs" style={{ display: "flex", gap: 6, marginBottom: 10 }}>
        {[["campagnes", "Campagnes"], ["planning", "Planning"], ["sauvegardes", "Sauvegardes (PBS)"]].map(([k, l]) =>
          <button key={k} className={`secondary na-section-toggle${tab === k ? " active" : ""}`} onClick={() => setTab(k)}>{l}</button>)}
      </div>
      {msg?.error && <p style={{ color: "var(--danger)" }}>{msg.error}</p>}
      {msg?.ok && <p style={{ color: "var(--ok, green)" }}>{msg.ok}</p>}
      {!catalog ? <p className="muted">⏳ lecture des Proxmox…</p> : (
        <>
          {catalog.nodes.length === 0 && <p className="hub-warning">Aucun nœud Proxmox ne remonte de mesure : activer le plugin <code>proxmox</code> sur l'agent de chaque PVE.</p>}
          {tab === "campagnes" && (
            <div style={{ display: "flex", gap: 12, alignItems: "flex-start", flexWrap: "wrap" }}>
              <div style={{ flex: "0 1 300px" }}>
                <button onClick={() => { setCurrent(null); setDraft({ name: "", status: "draft", notes: "", stages: [] }); }}>+ Nouvelle campagne</button>
                <TemplatePicker catalog={catalog} base={base} onReady={(c) => { setCurrent(null); setDraft(c); setMsg(null); }} onError={(e) => setMsg({ error: e })} />
                {(list || []).map((c) => (
                  <div key={c.id} style={{ ...box, cursor: "pointer", outline: current?.id === c.id ? "2px solid var(--accent, #1565c0)" : "none" }} onClick={() => open(c.id)}>
                    <strong>{c.name}</strong> <Tone tone={c.status === "active" ? "info" : c.status === "done" ? "good" : "neutral"}>{STATUS_LABEL[c.status]}</Tone>
                    <div style={{ marginTop: 4 }}><Bar pct={c.progress.pct} /> {c.progress.done}/{c.progress.total}</div>
                    {c.next_at && <div className="muted" style={{ fontSize: 12 }}>prochaine action prévue : {when(c.next_at)}</div>}
                  </div>))}
                {list && !list.length && <p className="muted">Aucune campagne.</p>}
              </div>
              <div style={{ flex: "1 1 560px", minWidth: 0 }}>
                {draft ? <Editor draft={draft} setDraft={setDraft} catalog={catalog} onSave={save} onCancel={() => setDraft(null)} />
                  : current ? <Campaign c={current} onAct={act} onEdit={() => setDraft(JSON.parse(JSON.stringify(current)))} onRemove={remove}
                    onStatus={async (status) => { const r = await updateMaintCampaign(base, current.id, { status, actor: login }); if (r.error) setMsg({ error: r.error }); else { setCurrent(r.campaign); loadList(); } }} />
                  : <p className="muted">Choisir une campagne, en créer une, ou partir d'un modèle.</p>}
              </div>
            </div>)}
          {tab === "planning" && <Planning list={list} onOpen={(id) => { setTab("campagnes"); open(id); }} />}
          {tab === "sauvegardes" && <Backups base={base} />}
        </>)}
    </div>
  );
}

// ------------------------------------------------------------------ campagne (lecture, actions)

function Campaign({ c, onAct, onEdit, onRemove, onStatus }) {
  return (
    <div>
      <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
        <h2 style={{ margin: 0 }}>{c.name}</h2>
        <select value={c.status} onChange={(e) => onStatus(e.target.value)}>{Object.entries(STATUS_LABEL).map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select>
        <Bar pct={c.progress.pct} /> <span>{c.progress.pct} % ({c.progress.done}/{c.progress.total})</span>
        <button className="secondary" onClick={onEdit}>Modifier</button>
        <button className="secondary" onClick={onRemove}>Supprimer</button>
      </div>
      {c.notes && <p className="muted">{c.notes}</p>}
      {c.status !== "active" && c.stages.some((s) => s.actions.some((a) => a.auto)) &&
        <p className="hub-warning">Des opérations sont planifiées en automatique : elles ne partiront qu'une fois la campagne passée en « active ».</p>}
      {c.stages.map((s, i) => (
        <div key={s.id} style={box}>
          <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
            <strong>{i + 1}. {s.title}</strong> <Tone tone={STATE_TONE[s.state]}>{STATE_LABEL[s.state]}</Tone>
            <span className="muted">{s.progress.done}/{s.progress.total}</span>
            {s.require_previous && <span className="muted" style={{ fontSize: 12 }}>après l'étape précédente</span>}
          </div>
          {s.notes && <p className="muted" style={{ margin: "4px 0" }}>{s.notes}</p>}
          <table style={{ marginTop: 6 }}><tbody>{s.actions.map((a) => (
            <tr key={a.id}>
              <td style={{ width: 110 }}><Tone tone={STATE_TONE[a.state]} title={a.done_how ? HOW_LABEL[a.done_how] : ""}>{STATE_LABEL[a.state]}{a.done_how ? ` (${HOW_LABEL[a.done_how]})` : ""}</Tone></td>
              <td>{a.title}{a.kind === "pra" && <span className="muted"> · {a.step.action} {a.step.vmid || ""} sur {a.step.agent_id}</span>}
                {a.detail && <div className="muted" style={{ fontSize: 12 }}>{a.detail}</div>}
                {a.notes && <div style={{ fontSize: 12 }}>{a.notes}</div>}</td>
              <td style={{ whiteSpace: "nowrap", fontSize: 12 }}>{a.at ? <>{when(a.at)}{a.auto ? " · auto" : ""}</> : ""}</td>
              <td style={{ whiteSpace: "nowrap" }}>
                {a.state !== "done" && <button className="secondary" onClick={() => onAct(a.id, "mark")} title="Marquer comme fait à la main">✓</button>}
                {a.manual_done && <button className="secondary" onClick={() => onAct(a.id, "unmark")} title="Retirer la coche">↺</button>}
                {a.kind === "pra" && a.state !== "done" && <> <button className="secondary" onClick={() => onAct(a.id, "simulate")}>Simuler</button>{" "}
                  <button disabled={a.state === "running" || s.state === "blocked"} onClick={() => onAct(a.id, "execute")}>Exécuter</button></>}
              </td>
            </tr>))}</tbody></table>
        </div>))}
      {!!c.history?.length && <details style={box}><summary>Historique ({c.history.length})</summary>
        <ul style={{ fontSize: 13 }}>{[...c.history].reverse().slice(0, 50).map((h, i) => <li key={i}>{when(h.at)} · {h.event}{h.action ? ` · ${h.action}` : ""}{h.by ? ` · ${h.by}` : ""}{h.run_id ? ` · exécution n°${h.run_id}` : ""}</li>)}</ul></details>}
    </div>
  );
}

// ------------------------------------------------------------------ édition

function Editor({ draft, setDraft, catalog, onSave, onCancel }) {
  const setStage = (i, patch) => setDraft({ ...draft, stages: draft.stages.map((s, j) => (j === i ? { ...s, ...patch } : s)) });
  return (
    <div>
      <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap", marginBottom: 8 }}>
        <input style={{ flex: "1 1 260px", fontSize: 16 }} value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })} placeholder="Nom de la campagne" />
        <select value={draft.status} onChange={(e) => setDraft({ ...draft, status: e.target.value })}>{Object.entries(STATUS_LABEL).map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select>
        <button onClick={onSave}>Enregistrer</button><button className="secondary" onClick={onCancel}>Annuler</button>
      </div>
      <textarea rows={2} style={{ width: "100%" }} value={draft.notes || ""} onChange={(e) => setDraft({ ...draft, notes: e.target.value })} placeholder="Objectif, contexte, fenêtre de maintenance…" />
      {draft.stages.map((s, i) => (
        <div key={s.id || i} style={box}>
          <div style={{ display: "flex", gap: 6, alignItems: "center", flexWrap: "wrap" }}>
            <strong>{i + 1}.</strong><input style={{ flex: "1 1 240px" }} value={s.title} onChange={(e) => setStage(i, { title: e.target.value })} placeholder="Titre de l'étape" />
            <label><input type="checkbox" checked={!!s.require_previous} onChange={(e) => setStage(i, { require_previous: e.target.checked })} /> après l'étape précédente</label>
            <button className="secondary" onClick={() => setDraft({ ...draft, stages: move(draft.stages, i, -1) })}>↑</button>
            <button className="secondary" onClick={() => setDraft({ ...draft, stages: move(draft.stages, i, 1) })}>↓</button>
            <button className="secondary" onClick={() => setDraft({ ...draft, stages: draft.stages.filter((_, j) => j !== i) })}>✕</button>
          </div>
          {s.actions.map((a, k) => (
            <ActionEditor key={a.id || k} a={a} catalog={catalog}
              onChange={(na) => setStage(i, { actions: s.actions.map((x, j) => (j === k ? na : x)) })}
              onMove={(d) => setStage(i, { actions: move(s.actions, k, d) })}
              onRemove={() => setStage(i, { actions: s.actions.filter((_, j) => j !== k) })} />))}
          <button className="secondary" onClick={() => setStage(i, { actions: [...s.actions, emptyAction()] })}>+ action</button>
        </div>))}
      <button className="secondary" onClick={() => setDraft({ ...draft, stages: [...draft.stages, { title: "", require_previous: false, actions: [emptyAction()] }] })}>+ étape</button>
    </div>
  );
}

function ActionEditor({ a, catalog, onChange, onMove, onRemove }) {
  const [ptext, setPtext] = useState(paramsToText(a.step?.params));
  const nodes = catalog.nodes;
  const set = (patch) => onChange({ ...a, ...patch });
  const step = a.step || { agent_id: nodes[0]?.agent_id || "", vmid: "", kind: "lxc", action: "backup", params: {} };
  const setStep = (patch) => set({ step: { ...step, ...patch } });
  const node = nodes.find((n) => n.agent_id === step.agent_id);
  const det = a.detector || null;
  const setDet = (patch) => set({ detector: det ? { ...det, ...patch } : null });
  const miss = a.kind === "pra" ? missingParams(catalog, step) : [];
  return (
    <div style={{ borderTop: "1px dashed var(--border)", padding: "6px 0", display: "grid", gap: 4 }}>
      <div style={{ display: "flex", gap: 6, flexWrap: "wrap", alignItems: "center" }}>
        <input style={{ flex: "1 1 260px" }} value={a.title} onChange={(e) => set({ title: e.target.value })} placeholder="Intitulé de l'action" />
        <select value={a.kind} onChange={(e) => set({ kind: e.target.value, step: e.target.value === "pra" ? step : null, auto: e.target.value === "pra" ? a.auto : false })}>
          <option value="manual">manuelle</option><option value="pra">opération PVE</option></select>
        <button className="secondary" onClick={() => onMove(-1)}>↑</button><button className="secondary" onClick={() => onMove(1)}>↓</button>
        <button className="secondary" onClick={onRemove}>✕</button>
      </div>
      {a.kind === "pra" && (
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap", alignItems: "center" }}>
          <select value={step.agent_id} onChange={(e) => setStep({ agent_id: e.target.value })}>{nodes.map((n) => <option key={n.agent_id} value={n.agent_id}>{n.node}</option>)}</select>
          <select value={step.vmid} onChange={(e) => { const vm = node?.vms.find((v) => String(v.vmid) === e.target.value); setStep({ vmid: Number(e.target.value), kind: vm?.type || step.kind }); }}>
            <option value="">— CT/VM —</option>{(node?.vms || []).map((v) => <option key={v.vmid} value={v.vmid}>{v.vmid} {v.name} ({v.status})</option>)}</select>
          <select value={step.action} onChange={(e) => setStep({ action: e.target.value })}>{catalog.actions.filter((x) => !["role_switch", "checkpoint", "image_host", "host_shutdown"].includes(x)).map((x) => <option key={x}>{x}</option>)}</select>
          <textarea rows={1} style={{ flex: "1 1 200px" }} value={ptext} onChange={(e) => { setPtext(e.target.value); setStep({ params: textToParams(e.target.value) }); }}
            placeholder={(catalog.required[step.action] || []).map((k) => `${k}=…`).join("  ") || "paramètres clé=valeur"} />
          {miss.length > 0 && <span style={{ color: "var(--danger)", fontSize: 12 }}>requis : {miss.join(", ")}</span>}
          {step.action === "destroy" && <span className="muted" style={{ fontSize: 12 }}>confirm = le vmid</span>}
        </div>)}
      <div style={{ display: "flex", gap: 6, flexWrap: "wrap", alignItems: "center" }}>
        <span className="muted">Constat :</span>
        <select value={det?.type || ""} onChange={(e) => set({ detector: e.target.value ? { type: e.target.value, params: det?.params || {} } : null })}>
          <option value="">aucun (coche ou exécution)</option>
          {Object.entries(catalog.detectors).map(([k, d]) => <option key={k} value={k}>{d.label}</option>)}</select>
        {det && detectorFields(catalog, det.type).map((f) => (
          f.name === "node" ? <select key={f.name} value={det.params?.node || ""} onChange={(e) => setDet({ params: { ...det.params, node: e.target.value } })}>
            <option value="">{f.optional ? "tout nœud" : "— nœud —"}</option>{nodes.map((n) => <option key={n.node} value={n.node}>{n.node}</option>)}</select>
            : <input key={f.name} style={{ width: f.name === "vmid" || f.name.endsWith("_h") || f.name.endsWith("_gb") ? 80 : 130 }} value={det.params?.[f.name] ?? ""} placeholder={f.name + (f.optional ? " (option)" : "")}
                onChange={(e) => setDet({ params: { ...det.params, [f.name]: /^\d+(\.\d+)?$/.test(e.target.value) ? Number(e.target.value) : e.target.value } })} />))}
      </div>
      <div style={{ display: "flex", gap: 6, flexWrap: "wrap", alignItems: "center" }}>
        <span className="muted">Prévu le</span>
        <input type="datetime-local" value={toLocalInput(a.at)} onChange={(e) => set({ at: fromLocalInput(e.target.value) })} />
        {a.kind === "pra" && <label><input type="checkbox" checked={!!a.auto} onChange={(e) => set({ auto: e.target.checked })} /> lancer automatiquement</label>}
        <input style={{ flex: "1 1 200px" }} value={a.notes || ""} onChange={(e) => set({ notes: e.target.value })} placeholder="consigne, commande, remarque" />
      </div>
    </div>
  );
}

// ------------------------------------------------------------------ modèles

function TemplatePicker({ catalog, base, onReady, onError }) {
  const [kind, setKind] = useState("");
  const [p, setP] = useState({});
  const nodes = catalog.nodes;
  const node = nodes.find((n) => n.node === p.node);
  const allVms = nodes.flatMap((n) => n.vms.map((v) => ({ ...v, node: n.node, agent_id: n.agent_id })));
  const toggle = (v) => setP({ ...p, vmids: (p.vmids || []).includes(v) ? p.vmids.filter((x) => x !== v) : [...(p.vmids || []), v] });
  const go = async () => {
    const r = await maintTemplate(base, kind, p);
    if (r.error) onError(r.error); else { onReady(r.campaign); setKind(""); setP({}); }
  };
  return (
    <div style={{ ...box, marginTop: 8 }}>
      <select value={kind} onChange={(e) => { setKind(e.target.value); setP({}); }}><option value="">Partir d'un modèle…</option>
        {Object.entries(catalog.templates).map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select>
      {kind === "free_node" && (
        <div style={{ display: "grid", gap: 4, marginTop: 6 }}>
          <select value={p.node || ""} onChange={(e) => { const n = nodes.find((x) => x.node === e.target.value); setP({ node: e.target.value, agent_id: n?.agent_id, vmids: [] }); }}>
            <option value="">— nœud —</option>{nodes.map((n) => <option key={n.node}>{n.node}</option>)}</select>
          {node && <>
            <div style={{ maxHeight: 160, overflow: "auto", fontSize: 13 }}>{node.vms.map((v) => <label key={v.vmid} style={{ display: "block" }}>
              <input type="checkbox" checked={(p.vmids || []).includes(v.vmid)} onChange={() => toggle(v.vmid)} /> {v.vmid} {v.name} <span className="muted">({v.status}, {gb(v.maxdisk)})</span></label>)}</div>
            <label>Sauvegarder vers <select value={p.backup_storage || ""} onChange={(e) => setP({ ...p, backup_storage: e.target.value })}><option value="">—</option>
              {node.storages.map((s) => <option key={s.storage} value={s.storage}>{s.storage} ({s.type}, {gb(s.avail)} libres)</option>)}</select></label>
            <label>Espace à constater sur <select value={p.free_storage || ""} onChange={(e) => setP({ ...p, free_storage: e.target.value })}><option value="">(aucun)</option>
              {node.storages.map((s) => <option key={s.storage} value={s.storage}>{s.storage}</option>)}</select>
              {p.free_storage && <> ≥ <input type="number" style={{ width: 70 }} value={p.min_free_gb || ""} onChange={(e) => setP({ ...p, min_free_gb: +e.target.value })} /> Go</>}</label>
          </>}
        </div>)}
      {kind === "pbs_setup" && (
        <div style={{ display: "grid", gap: 4, marginTop: 6 }}>
          <label>Nom du stockage PBS sur les nœuds <input value={p.pbs_storage || ""} onChange={(e) => setP({ ...p, pbs_storage: e.target.value })} placeholder="pbs-lan" /></label>
          <div style={{ fontSize: 13 }}>{nodes.map((n) => <label key={n.node} style={{ marginRight: 8 }}><input type="checkbox" checked={(p.nodes || []).includes(n.node)}
            onChange={() => setP({ ...p, nodes: (p.nodes || []).includes(n.node) ? p.nodes.filter((x) => x !== n.node) : [...(p.nodes || []), n.node] })} /> {n.node}</label>)}</div>
          <label>CT/VM à suivre (vmid séparés par des virgules) <input value={(p.vmids || []).join(",")} onChange={(e) => setP({ ...p, vmids: e.target.value.split(/[ ,;]+/).filter(Boolean).map(Number) })} /></label>
        </div>)}
      {kind === "move_guest" && (
        <div style={{ display: "grid", gap: 4, marginTop: 6 }}>
          <select value={p.vmids?.[0] ? `${p.source_node}|${p.vmids[0]}` : ""} onChange={(e) => { const [n, v] = e.target.value.split("|"); const src = nodes.find((x) => x.node === n);
            setP({ ...p, vmids: [Number(v)], source_node: n, source_agent: src?.agent_id }); }}>
            <option value="">— CT/VM à déplacer —</option>{allVms.map((v) => <option key={`${v.node}|${v.vmid}`} value={`${v.node}|${v.vmid}`}>{v.vmid} {v.name} sur {v.node}</option>)}</select>
          <select value={p.target_node || ""} onChange={(e) => setP({ ...p, target_node: e.target.value })}><option value="">— nœud cible —</option>
            {nodes.filter((n) => n.node !== p.source_node).map((n) => <option key={n.node}>{n.node}</option>)}</select>
        </div>)}
      {kind && <button style={{ marginTop: 6 }} onClick={go}>Préparer la campagne</button>}
    </div>
  );
}

// ------------------------------------------------------------------ planning et sauvegardes

function Planning({ list, onOpen }) {
  const rows = plannedList(list);
  if (!rows.length) return <p className="muted">Aucune action datée. Une date se pose dans l'édition d'une action (« Prévu le »).</p>;
  const now = Date.now() / 1000;
  return (
    <AutoColumns id="PveMaintView.1"><table><thead><tr><th>Date</th><th>Campagne</th><th>Étape</th><th>Action</th><th>Mode</th><th>État</th></tr></thead>
      <tbody>{rows.map((r) => (
        <tr key={`${r.campaign_id}|${r.action_id}`} style={{ cursor: "pointer" }} onClick={() => onOpen(r.campaign_id)}>
          <td style={{ whiteSpace: "nowrap", color: r.at < now && r.state !== "done" ? "var(--danger)" : undefined }}>{when(r.at)}</td>
          <td>{r.campaign}</td><td>{r.stage}</td><td>{r.title}</td><td>{r.auto ? "automatique" : "à la main"}</td>
          <td><Tone tone={STATE_TONE[r.state]}>{STATE_LABEL[r.state]}</Tone></td></tr>))}</tbody></table></AutoColumns>
  );
}

function Backups({ base }) {
  const [d, setD] = useState(null);
  const [onlyIssues, setOnlyIssues] = useState(true);
  useEffect(() => { (async () => setD(await fetchMaintBackups(base)))(); }, [base]);
  if (!d) return <p className="muted">⏳ lecture…</p>;
  if (d.error) return <p style={{ color: "var(--danger)" }}>{d.error}</p>;
  const s = d.summary;
  const guests = onlyIssues ? d.guests.filter((g) => g.flags.length) : d.guests;
  return (
    <div>
      <p>{s.guests} CT/VM · <Tone tone={s.never ? "bad" : "good"}>{s.never} jamais sauvegardé(s)</Tone> · <Tone tone={s.old ? "warn" : "good"}>{s.old} sauvegarde(s) ancienne(s)</Tone> ·
        {" "}<Tone tone={s.failed ? "bad" : "good"}>{s.failed} en échec</Tone> · <Tone tone={s.uncovered ? "warn" : "good"}>{s.uncovered} hors tâche planifiée</Tone> · {s.on_pbs} sur un PBS</p>
      {!d.has_pbs && <p className="hub-warning">Aucun stockage PBS déclaré sur les nœuds : modèle « Mettre en service un PBS » dans l'onglet Campagnes.</p>}
      <div style={box}><strong>Stockages de sauvegarde</strong>
        <AutoColumns id="PveMaintView.2"><table><thead><tr><th>Nœud</th><th>Stockage</th><th>Type</th><th>Occupation</th></tr></thead>
          <tbody>{d.stores.map((x) => <tr key={`${x.node}|${x.storage}`}><td>{x.node}</td><td>{x.storage}</td><td>{x.type}</td>
            <td>{x.total ? <><Bar pct={Math.round(100 * (x.used || 0) / x.total)} /> {gb(x.used)} / {gb(x.total)} ({gb(x.avail)} libres)</> : "—"}</td></tr>)}</tbody></table></AutoColumns></div>
      <div style={box}><strong>Tâches planifiées</strong>
        {d.jobs.length ? <AutoColumns id="PveMaintView.3"><table><thead><tr><th>Tâche</th><th>Active</th><th>Planification</th><th>Stockage</th><th>CT/VM</th><th>Mode</th><th>Rétention</th></tr></thead>
          <tbody>{d.jobs.map((j) => <tr key={`${j.node}|${j.id}`}><td>{j.id}</td><td>{j.enabled ? "oui" : "non"}</td><td>{j.schedule}</td><td>{j.storage}</td>
            <td>{j.all ? "tous" : (j.vmids || []).join(", ")}</td><td>{j.mode}</td><td>{typeof j.prune === "object" ? JSON.stringify(j.prune) : j.prune}</td></tr>)}</tbody></table></AutoColumns>
          : <p className="muted">Aucune tâche de sauvegarde planifiée.</p>}</div>
      <div style={box}><strong>Par CT/VM</strong> <label style={{ marginLeft: 8 }}><input type="checkbox" checked={onlyIssues} onChange={(e) => setOnlyIssues(e.target.checked)} /> seulement ceux à traiter</label>
        <AutoColumns id="PveMaintView.4"><table><thead><tr><th>Nœud</th><th>CT/VM</th><th>État</th><th>Dernière sauvegarde</th><th>Stockage</th><th>Tâches</th><th>À traiter</th></tr></thead>
          <tbody>{guests.map((g) => <tr key={`${g.node}|${g.vmid}`}><td>{g.node}{g.stale ? " ⚠" : ""}</td><td>{g.vmid} {g.name}</td><td>{g.status}</td>
            <td>{g.last_backup_at ? `${when(g.last_backup_at)} (${g.age_h} h)` : "—"}</td><td>{g.storage || "—"}</td><td>{g.jobs.join(", ") || "—"}</td>
            <td>{g.flags.map((f) => <Tone key={f} tone={/jamais|échec/.test(f) ? "bad" : "warn"}>{f}</Tone>)}</td></tr>)}</tbody></table></AutoColumns></div>
    </div>
  );
}
