// Filtres d'alertes des agents (livraison #607) -- onglet « Filtres d'alertes »
// de la tuile Agents hôtes : groupes de règles (catégories d'événements, plage
// horaire ouvrée, jours), affectation par agent (case à cocher + groupe),
// test à blanc (« un hors-ligne à telle heure serait-il filtré ? »).
import { useCallback, useEffect, useState } from "react";
import { fetchAlertFilters, saveAlertFilters, testAlertFilter, updateAgent } from "./siAgentClient.js";

const WHEN = { always: "toujours", outside: "hors des heures ouvrées", inside: "pendant les heures ouvrées" };

export default function AlertFiltersTab({ base, fleet, onChanged, notice }) {
  const [data, setData] = useState(null);
  const [groups, setGroups] = useState([]);
  const [busy, setBusy] = useState("");
  const [test, setTest] = useState({ agent: "", kind: "agent-offline", at: "" , result: null });
  const load = useCallback(() => fetchAlertFilters(base).then((d) => { if (!d.error) { setData(d); setGroups(d.groups || []); } else notice(d.error, false); }), [base]);  // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { load(); }, [load]);
  const setGroup = (i, patch) => setGroups(groups.map((g, j) => (j === i ? { ...g, ...patch } : g)));
  const setRule = (i, k, patch) => setGroup(i, { rules: groups[i].rules.map((r, j) => (j === k ? { ...r, ...patch } : r)) });
  const save = async () => {
    setBusy("enregistrement…");
    const r = await saveAlertFilters(base, groups);
    setBusy("");
    notice(r.error || `${(r.groups || []).length} groupe(s) enregistré(s)`, !r.error);
    if (!r.error) { load(); onChanged && onChanged(); }
  };
  const runTest = async () => {
    const r = await testAlertFilter(base, { agent_id: test.agent || undefined, kind: test.kind, at: test.at ? new Date(test.at).toISOString() : undefined });
    setTest({ ...test, result: r });
  };
  const toggleAgent = async (a, patch) => {
    const r = await updateAgent(base, a.agent_id, patch);
    notice(r.error || `${a.agent_id} : filtrage ${r.filter_enabled ? "activé (" + (r.filter_group || "aucun groupe") + ")" : "désactivé"}`, !r.error);
    onChanged && onChanged(); load();
  };
  if (!data) return <p className="muted">chargement…</p>;
  const cats = Object.entries(data.categories || {});
  return (
    <div>
      <p className="muted" style={{ marginTop: 0 }}>
        Une alerte filtrée reste dans le journal (case « afficher les filtrées ») mais n'apparaît ni dans le bandeau, ni dans la synthèse, ni dans les notifications.
        Chaque agent a sa case « filtrer » et son groupe ; un groupe = des règles par <b>catégorie</b> d'événement, <b>toujours</b> ou selon les <b>heures ouvrées</b> ({data.tz}).
        Besoin immédiat : groupe « Postes de travail » — les hors-ligne en dehors de 8 h 30 – 18 h (lun.–ven.) ne sont pas des pannes.
      </p>

      <h3 style={{ margin: "10px 0 6px" }}>Par agent</h3>
      <div style={{ maxHeight: 260, overflow: "auto", border: "1px solid var(--border)", borderRadius: 8 }}>
        <table style={{ width: "100%", fontSize: 13 }}>
          <thead style={{ position: "sticky", top: 0, background: "var(--panel)" }}><tr><th>Agent</th><th>Site</th><th>Hôte</th><th>Filtrer</th><th>Groupe</th></tr></thead>
          <tbody>
            {fleet.map((a) => (
              <tr key={a.agent_id}>
                <td><b>{a.agent_id}</b></td><td className="muted">{a.site}</td><td className="muted">{a.hostname || ""}</td>
                <td><input type="checkbox" checked={!!a.filter_enabled} onChange={(e) => toggleAgent(a, { filter_enabled: e.target.checked, filter_group: a.filter_group || groups[0]?.id || "" })} /></td>
                <td><select value={a.filter_group || ""} onChange={(e) => toggleAgent(a, { filter_group: e.target.value })} disabled={!a.filter_enabled}>
                  <option value="">— groupe —</option>{groups.map((g) => <option key={g.id} value={g.id}>{g.label}</option>)}</select></td>
              </tr>
            ))}
            {!fleet.length && <tr><td colSpan={5} className="muted">aucun agent.</td></tr>}
          </tbody>
        </table>
      </div>

      <h3 style={{ margin: "14px 0 6px" }}>Groupes de filtres {data.default && <span className="muted" style={{ fontWeight: 400 }}>(paramétrage par défaut, non enregistré)</span>}</h3>
      {groups.map((g, i) => (
        <div key={i} className="hub-card lic-card" style={{ marginBottom: 8 }}>
          <div className="lic-form" style={{ gridTemplateColumns: "1fr 2fr 3fr auto" }}>
            <label>Identifiant <input value={g.id} onChange={(e) => setGroup(i, { id: e.target.value })} /></label>
            <label>Libellé <input value={g.label} onChange={(e) => setGroup(i, { label: e.target.value })} /></label>
            <label>Description <input value={g.description || ""} onChange={(e) => setGroup(i, { description: e.target.value })} /></label>
            <label>&nbsp;<button type="button" className="secondary" onClick={() => setGroups(groups.filter((_, j) => j !== i))} disabled={!!data.usage?.[g.id]} title={data.usage?.[g.id] ? `utilisé par ${data.usage[g.id]} agent(s)` : ""}>retirer</button></label>
          </div>
          {(g.rules || []).map((r, k) => (
            <div key={k} style={{ display: "flex", gap: 10, alignItems: "flex-start", flexWrap: "wrap", marginTop: 8, padding: 8, border: "1px dashed var(--border)", borderRadius: 6 }}>
              <div style={{ minWidth: 260 }}>
                <div className="muted" style={{ fontSize: 12 }}>Catégories filtrées</div>
                {cats.map(([id, label]) => <label key={id} style={{ display: "block", fontSize: 12 }}><input type="checkbox" checked={(r.categories || []).includes(id)} onChange={(e) => setRule(i, k, { categories: e.target.checked ? [...(r.categories || []), id] : (r.categories || []).filter((c) => c !== id) })} /> {label}</label>)}
              </div>
              <div>
                <label style={{ display: "block", fontSize: 12 }}>Genres précis (facultatif, virgules)<br /><input value={(r.kinds || []).join(", ")} onChange={(e) => setRule(i, k, { kinds: e.target.value.split(",").map((x) => x.trim()).filter(Boolean) })} placeholder="agent-offline, command-failed" style={{ width: 260 }} /></label>
                <label style={{ display: "block", fontSize: 12, marginTop: 6 }}>Quand<br /><select value={r.when || "always"} onChange={(e) => setRule(i, k, { when: e.target.value })}>{Object.entries(WHEN).map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></label>
                {r.when !== "always" && <>
                  <div style={{ fontSize: 12, marginTop: 6 }}>Jours ouvrés : {(data.weekdays || []).map((d, di) => <label key={di} style={{ marginRight: 6 }}><input type="checkbox" checked={(r.days || []).includes(di)} onChange={(e) => setRule(i, k, { days: e.target.checked ? [...(r.days || []), di].sort() : (r.days || []).filter((x) => x !== di) })} /> {d}</label>)}</div>
                  <div style={{ fontSize: 12, marginTop: 6 }}>Heures ouvrées de <input value={r.start || "08:30"} onChange={(e) => setRule(i, k, { start: e.target.value })} style={{ width: 60 }} /> à <input value={r.end || "18:00"} onChange={(e) => setRule(i, k, { end: e.target.value })} style={{ width: 60 }} /></div>
                </>}
                <label style={{ display: "block", fontSize: 12, marginTop: 6 }}>Action <select value={r.action || "mute"} onChange={(e) => setRule(i, k, { action: e.target.value })}><option value="mute">filtrer (journal seulement)</option><option value="keep">laisser passer (exception)</option></select></label>
              </div>
              <button type="button" className="secondary" onClick={() => setGroup(i, { rules: g.rules.filter((_, j) => j !== k) })}>retirer la règle</button>
            </div>
          ))}
          <button type="button" className="secondary" style={{ marginTop: 6 }} onClick={() => setGroup(i, { rules: [...(g.rules || []), { categories: ["availability"], kinds: [], when: "outside", days: [0, 1, 2, 3, 4], start: "08:30", end: "18:00", action: "mute" }] })}>+ règle</button>
        </div>
      ))}
      <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
        <button type="button" className="secondary" onClick={() => setGroups([...groups, { id: `groupe-${groups.length + 1}`, label: "Nouveau groupe", description: "", rules: [] }])}>+ groupe</button>
        <button type="button" onClick={save} disabled={!!busy}>{busy ? `⏳ ${busy}` : "Enregistrer les groupes"}</button>
      </div>

      <h3 style={{ margin: "14px 0 6px" }}>Test à blanc</h3>
      <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
        <select value={test.agent} onChange={(e) => setTest({ ...test, agent: e.target.value, result: null })}><option value="">agent…</option>{fleet.map((a) => <option key={a.agent_id} value={a.agent_id}>{a.agent_id}</option>)}</select>
        <select value={test.kind} onChange={(e) => setTest({ ...test, kind: e.target.value, result: null })}>{(data.kinds || []).map((k) => <option key={k} value={k}>{k}</option>)}</select>
        <input type="datetime-local" value={test.at} onChange={(e) => setTest({ ...test, at: e.target.value, result: null })} />
        <button type="button" className="secondary" onClick={runTest} disabled={!test.agent}>Tester</button>
        {test.result && <span style={{ color: test.result.muted ? "var(--warning)" : "var(--ok)" }}>{test.result.muted ? `filtré — ${test.result.reason}` : `laissé passer (catégorie ${test.result.category})`}</span>}
      </div>
    </div>
  );
}
