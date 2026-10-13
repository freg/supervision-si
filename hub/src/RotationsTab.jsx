// Tournées de mesures réparties (#743, item 120 volet 1) : une sonde lourde ou intrusive confiée à un groupe d'agents ;
// le central choisit qui la lance et quand -- à tour de rôle avec suppléance (rotate) ou chacun décalé dans la période
// (spread) -- pour une mesure globalement régulière, sans rafale. Heures calmes, plafond par site, couverture sur 24 h.
import React, { useEffect, useState } from "react";
import { fetchRotations, saveRotation, deleteRotation, fetchRotationRuns } from "./siAgentClient.js";
import { orderItems } from "./listOrder.js";
import { useListOrder, OrderSwitch } from "./ListOrder.jsx";

const EMPTY = { name: "", plugin_id: "", mode: "rotate", period_seconds: 3600, agents: [], quiet: "", max_concurrent_per_site: 1, enabled: true, notes: "" };
const hhmm = (t) => new Date(t * 1000).toLocaleString("fr-FR", { weekday: "short", hour: "2-digit", minute: "2-digit" });
const period = (s) => (s % 86400 === 0 ? `${s / 86400} j` : s % 3600 === 0 ? `${s / 3600} h` : `${Math.round(s / 60)} min`);
export const parseQuiet = (txt) => String(txt || "").split(/[,;]/).map((x) => x.trim()).filter(Boolean)
  .map((x) => x.split("-").map((h) => parseInt(h, 10))).filter((p) => p.length === 2 && p.every((h) => Number.isInteger(h)));
const quietText = (q) => (q || []).map(([a, b]) => `${a}-${b}`).join(", ");
const STATUS = { done: "fait", failed: "échec", skipped: "sauté", queued: "envoyé", waiting: "en attente de place" };

export default function RotationsTab({ base, fleet, catalogue, notice }) {
  const [rows, setRows] = useState([]);
  const [form, setForm] = useState(null);
  const [runs, setRuns] = useState({ id: null, list: [] });
  const [order, setOrder] = useListOrder("si-agent.rotations", "alpha");
  const load = async () => { const r = await fetchRotations(base); if (r?.error) notice(r.error, false); else setRows(r?.rotations || []); };
  useEffect(() => { load(); const t = setInterval(load, 30000); return () => clearInterval(t); /* eslint-disable-next-line */ }, [base]);

  const edit = (p) => setForm(p ? { ...p, quiet: quietText(p.quiet_hours) } : { ...EMPTY });
  const submit = async (e) => {
    e.preventDefault();
    const body = { ...form, period_seconds: Number(form.period_seconds), max_concurrent_per_site: Number(form.max_concurrent_per_site), quiet_hours: parseQuiet(form.quiet) };
    const r = await saveRotation(base, body, form.id);
    if (r?.error) { notice(r.error, false); return; }
    notice(`tournée « ${r.name} » enregistrée`); setForm(null); load();
  };
  const remove = async (p) => { if (!window.confirm(`Supprimer la tournée « ${p.name} » et son historique ?`)) return; await deleteRotation(base, p.id); load(); };
  const showRuns = async (p) => { if (runs.id === p.id) { setRuns({ id: null, list: [] }); return; } const r = await fetchRotationRuns(base, p.id); setRuns({ id: p.id, list: r?.runs || [] }); };
  const sorted = orderItems(rows, order, { name: (p) => p.name, date: (p) => p.updated_at, severity: (p) => (p.coverage_24h?.rate == null ? "unknown" : p.coverage_24h.rate < 0.5 ? "critical" : p.coverage_24h.rate < 0.9 ? "warning" : "ok") });

  return (
    <div className="hub-card hub-settings-section">
      <p className="muted" style={{ marginTop: 0 }}>Une <strong>tournée</strong> confie une sonde lourde ou intrusive (balayage, capture, débit…) à plusieurs agents. Le central choisit qui la lance et quand : <em>à tour de rôle</em> (un agent par créneau ; s'il est hors ligne, le suivant le supplée) ou <em>réparti</em> (chaque agent une fois par période, décalés). Heures calmes et plafond de lancements simultanés par site.</p>
      <div className="ups-toolbar">
        <button onClick={() => edit(null)}>+ Nouvelle tournée</button>
        <OrderSwitch value={order} onChange={setOrder} />
      </div>
      {form && (
        <form onSubmit={submit} className="hub-card" style={{ margin: "8px 0" }}>
          <div className="ups-toolbar" style={{ flexWrap: "wrap", gap: 8 }}>
            <label>Nom <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required /></label>
            <label>Sonde <select value={form.plugin_id} onChange={(e) => setForm({ ...form, plugin_id: e.target.value })} required>
              <option value="">—</option>{orderItems(catalogue, "alpha", { name: (p) => p.id }).map((p) => <option key={p.id} value={p.id}>{p.id}</option>)}</select></label>
            <label>Mode <select value={form.mode} onChange={(e) => setForm({ ...form, mode: e.target.value })}>
              <option value="rotate">à tour de rôle (suppléance)</option><option value="spread">réparti (chaque agent)</option></select></label>
            <label>Période <select value={form.period_seconds} onChange={(e) => setForm({ ...form, period_seconds: e.target.value })}>
              {[900, 1800, 3600, 7200, 14400, 21600, 43200, 86400].map((s) => <option key={s} value={s}>{period(s)}</option>)}</select></label>
            <label title="ex. 22-6, 12-14">Heures calmes <input value={form.quiet} onChange={(e) => setForm({ ...form, quiet: e.target.value })} placeholder="22-6" size={10} /></label>
            <label title="0 = sans plafond">Max simultanés par site <input type="number" min="0" value={form.max_concurrent_per_site} onChange={(e) => setForm({ ...form, max_concurrent_per_site: e.target.value })} style={{ width: 50 }} /></label>
            <label><input type="checkbox" checked={form.enabled} onChange={(e) => setForm({ ...form, enabled: e.target.checked })} /> active</label>
          </div>
          <div style={{ margin: "6px 0" }}><span className="muted">Agents :</span>{" "}
            {orderItems(fleet, "alpha", { name: (a) => a.agent_id }).map((a) => (
              <label key={a.agent_id} style={{ marginRight: 10, whiteSpace: "nowrap" }}>
                <input type="checkbox" checked={form.agents.includes(a.agent_id)} onChange={(e) => setForm({ ...form, agents: e.target.checked ? [...form.agents, a.agent_id] : form.agents.filter((x) => x !== a.agent_id) })} /> {a.agent_id}
                {a.site ? <span className="muted"> ({a.site})</span> : null}
              </label>))}
          </div>
          <button type="submit">Enregistrer</button> <button type="button" className="secondary" onClick={() => setForm(null)}>Annuler</button>
        </form>
      )}
      {sorted.length === 0 ? <p className="muted">Aucune tournée.</p> : (
        <div className="hub-table-scroll"><table>
          <thead><tr><th>Tournée</th><th>Sonde</th><th>Mode · période</th><th>Agents</th><th>Prochains créneaux</th><th>24 h</th><th /></tr></thead>
          <tbody>{sorted.map((p) => {
            const c = p.coverage_24h || {};
            return (
              <React.Fragment key={p.id}>
                <tr className={`ups-row${p.enabled ? "" : " inactive"}`}>
                  <td><strong>{p.name}</strong>{!p.enabled && <div className="muted">inactive</div>}</td>
                  <td><code>{p.plugin_id}</code></td>
                  <td>{p.mode === "spread" ? "réparti" : "à tour de rôle"} · {period(p.period_seconds)}{p.quiet_hours?.length ? <div className="muted">calme {quietText(p.quiet_hours)}</div> : null}</td>
                  <td className="muted">{p.agents.join(", ")}</td>
                  <td className="muted" style={{ fontSize: 12 }}>{(p.next || []).slice(0, 3).map((n) => <div key={`${n.at}-${n.agent}`}>{hhmm(n.at)} · {n.agent || "?"}</div>)}</td>
                  <td title={`prévus ${c.expected ?? "?"} · faits ${c.done ?? 0} · suppléés ${c.substituted ?? 0} · sautés ${c.skipped ?? 0} · échecs ${c.failed ?? 0}`}>
                    {c.rate == null ? "—" : `${Math.round(c.rate * 100)} %`}{c.substituted ? <div className="muted">{c.substituted} suppléance(s)</div> : null}</td>
                  <td className="ups-actions"><button className="secondary" onClick={() => showRuns(p)}>Historique</button> <button className="secondary" onClick={() => edit(p)}>Modifier</button> <button className="secondary" onClick={() => remove(p)}>Supprimer</button></td>
                </tr>
                {runs.id === p.id && (
                  <tr><td colSpan={7}>{runs.list.length === 0 ? <span className="muted">Aucun créneau encore.</span> : (
                    <table><thead><tr><th>Créneau</th><th>Agent</th><th>État</th><th>Détail</th></tr></thead>
                      <tbody>{runs.list.map((r) => (
                        <tr key={r.id}><td>{hhmm(r.slot_start)}</td><td>{r.agent_id || "—"}{r.substitute_for ? <span className="muted"> (supplée {r.substitute_for})</span> : null}</td>
                          <td>{STATUS[r.status] || r.status}</td><td className="muted">{r.detail || ""}</td></tr>))}</tbody></table>)}</td></tr>
                )}
              </React.Fragment>
            );
          })}</tbody>
        </table></div>
      )}
    </div>
  );
}
