// Tuile « Vues de parc » (livraison #753) : listes d'agents paramétrables, organisées en groupes -- Serveurs, Postes,
// Serveurs d'IA, Postes personnels, ou toute autre vue. Pour chaque agent : l'en-tête de htop (CPU et cœurs, charge,
// mémoire, swap, disques, débit, uptime), services en échec, constats, version de l'agent, modèles Ollama chargés.
// Pleine largeur, rafraîchie toutes les 30 s. Mode « Organiser » : vues, groupes, agents (rangement proposé à partir
// des catégories #742 ; l'étiquette #perso dans le libellé d'un agent le range dans les postes personnels).
// Données : si-agent-api /views (réglage partagé) et /views/<id>/overview.
import DataStatus from "./DataStatus.jsx";   // #763 : état des données
import { useEffect, useMemo, useState } from "react";
import { fetchFleet, fetchViews, saveViews, fetchViewOverview } from "./siAgentClient.js";
import { fmtBytes, fmtBps, fmtUptime, fillLevel } from "./infraLib.js";
import { suggestViews, sortHtop, rowTone, moveAgent, viewAgents, gpuCells } from "./fleetViewsLib.js";

function Meter({ p, label }) {
  if (p == null) return <span className="infra-muted">—</span>;
  return <span className="infra-meter-wrap" title={label}><span className="infra-meter"><span className={`fill ${fillLevel(p).tone}`} style={{ width: `${Math.min(100, p)}%` }} /></span><em>{label}</em></span>;
}
function Cores({ cores }) {
  if (!cores?.length) return null;
  return <span className="infra-cores" title={cores.map((c, i) => `${i + 1}: ${c} %`).join("  ")}>{cores.map((c, i) => <i key={i} style={{ height: `${Math.max(6, c)}%` }} className={fillLevel(c).tone} />)}</span>;
}
const DOT = { good: "●", warning: "▲", critical: "■" };

function GroupTable({ g, sort, setSort, compact }) {
  const rows = useMemo(() => sortHtop(g.rows, sort.col, sort.dir), [g.rows, sort]);
  const th = (col, label) => <th onClick={() => setSort({ col, dir: sort.col === col ? -sort.dir : -1 })} className={sort.col === col ? "sorted" : ""}>{label}{sort.col === col ? (sort.dir < 0 ? " ▼" : " ▲") : ""}</th>;
  const t = g.totals || {};
  return (
    <section className="infra-card" style={{ marginBottom: 12 }}>
      <div className="infra-top" style={{ margin: 0 }}>
        <h3 style={{ margin: 0 }}>{g.name}</h3>
        <span className="infra-muted">{t.online}/{t.agents} en ligne · CPU moy. {t.cpu_avg ?? "—"} % · mémoire moy. {t.mem_avg ?? "—"} % · disque max {t.disk_max ?? "—"} %{t.failed_services ? ` · ${t.failed_services} service(s) en échec` : ""}</span>
        {t.critical > 0 && <span className="infra-status critical">⛔ {t.critical} à traiter</span>}
        {g.note && <span className="infra-muted">— {g.note}</span>}
      </div>
      {g.missing?.length > 0 && <p className="infra-muted">Agents inconnus du central : {g.missing.join(", ")}</p>}
      <div className="infra-table-wrap infra-scroll">
        <table className="infra-table">
          <thead><tr><th />{th("name", "Hôte")}{!compact && <th>Système</th>}{th("cpu_pct", "CPU")}{th("load", "Charge 1 / 5 / 15")}{th("mem_pct", "Mémoire")}{th("swap_pct", "Swap")}{th("disk_max_pct", "Disques")}
            {th("net_rx_bps", "Débit ↓ / ↑")}{th("uptime_s", "Uptime")}{th("failed_services", "Services")}<th>Constats</th><th>IA</th><th>GPU</th>{!compact && <th>Agent</th>}</tr></thead>
          <tbody>{rows.length === 0 ? <tr><td colSpan={15} className="infra-muted">Aucun agent dans ce groupe (Organiser).</td></tr> : rows.map((r) => {
            const tone = rowTone(r);
            return (
              <tr key={r.agent_id}>
                <td className={`infra-dot ${tone}`} title={r.online === "online" ? "en ligne" : `hors ligne${r.last_seen ? " depuis " + new Date(r.last_seen).toLocaleString("fr-FR") : ""}`}>{DOT[tone]}</td>
                <td><b>{r.hostname || r.agent_id}</b>{r.hostname && r.hostname !== r.agent_id && <div className="infra-muted">{r.agent_id}</div>}</td>
                {!compact && <td className="infra-muted">{r.os || "—"}{r.cpus ? ` · ${r.cpus} cœurs` : ""}</td>}
                <td><Meter p={r.cpu_pct} label={r.cpu_pct == null ? "—" : `${r.cpu_pct} %`} /> <Cores cores={r.cores_pct} /></td>
                <td style={{ whiteSpace: "nowrap", fontFamily: "ui-monospace, Menlo, monospace", fontSize: 12 }}>{r.load1 == null ? "—" : [r.load1, r.load5, r.load15].map((x) => (x ?? 0).toFixed(2)).join("  ")}</td>
                <td><Meter p={r.mem_pct} label={r.mem_total ? `${r.mem_pct ?? "?"} % de ${fmtBytes(r.mem_total)}` : r.mem_pct != null ? `${r.mem_pct} %` : "—"} /></td>
                <td>{r.swap_total ? <Meter p={r.swap_pct} label={`${r.swap_pct ?? 0} % de ${fmtBytes(r.swap_total)}`} /> : <span className="infra-muted">—</span>}</td>
                <td title={(r.disks || []).map((d) => `${d.mount} ${d.pct} %${d.total ? " de " + fmtBytes(d.total) : ""}`).join("\n")}>
                  <Meter p={r.disk_max_pct} label={r.disks?.length ? `${r.disks[0].mount} ${r.disk_max_pct} %${r.disks.length > 1 ? ` (+${r.disks.length - 1})` : ""}` : "—"} /></td>
                <td style={{ whiteSpace: "nowrap", fontFamily: "ui-monospace, Menlo, monospace", fontSize: 12 }}>{r.net_rx_bps == null ? "—" : `${fmtBps(r.net_rx_bps)} / ${fmtBps(r.net_tx_bps)}`}</td>
                <td style={{ whiteSpace: "nowrap" }}>{fmtUptime(r.uptime_s)}</td>
                <td>{r.failed_services ? <span className="infra-status warning">⚠ {r.failed_services}</span> : r.failed_services === 0 ? "0" : "—"}</td>
                <td>{Object.entries(r.risks || {}).filter(([, n]) => n).map(([s, n]) => <span key={s} className={`infra-status ${s === "critical" ? "critical" : "warning"}`}>{n} {s}</span>)}</td>
                <td>{r.ollama ? <span title={r.ollama.loaded.map((m) => `${m.name} : ${m.gpu_pct ?? "?"} % GPU`).join("\n")}>{r.ollama.up ? `${r.ollama.loaded.length}/${r.ollama.models} chargé(s)` : <span className="infra-status critical">Ollama arrêté</span>}
                  {r.ollama.loaded.map((m) => <div key={m.name} className="infra-muted">{m.name}{m.gpu_pct != null ? ` · ${m.gpu_pct} % GPU` : ""}</div>)}</span> : <span className="infra-muted">—</span>}</td>
                <td>{r.gpus ? (r.gpus.length ? gpuCells(r).map((g, i) => <div key={i} title={g.title} style={{ whiteSpace: "nowrap" }}>
                  <span className={`infra-dot ${g.tone}`}>{DOT[g.tone]}</span> {g.name} {g.pct != null ? <Meter p={g.pct} label={g.label} /> : <span className="infra-muted">{g.label}</span>}</div>)
                  : <span className="infra-muted">aucune carte</span>) : <span className="infra-muted" title="sonde gpu inactive (fiche de l'agent › Sondes)">—</span>}</td>
                {!compact && <td className="infra-muted">{r.version || "—"}</td>}
              </tr>);
          })}</tbody>
        </table>
      </div>
    </section>
  );
}

function Organizer({ views, setViews, fleet, onSave, onCancel, busy }) {
  const [vi, setVi] = useState(0);
  const [filter, setFilter] = useState("");
  const v = views[vi] || views[0];
  const upd = (nv) => setViews(views.map((x, i) => (i === vi ? nv : x)));
  const inView = viewAgents(v);
  const where = (id) => v.groups.findIndex((g) => g.agents.includes(id));
  const shown = (fleet || []).filter((a) => !filter || `${a.agent_id} ${a.hostname || ""} ${a.label || ""} ${a.os || ""}`.toLowerCase().includes(filter.toLowerCase()));
  return (
    <div className="infra-card">
      <div className="infra-top" style={{ margin: 0 }}>
        <select value={vi} onChange={(e) => setVi(Number(e.target.value))}>{views.map((x, i) => <option key={x.id} value={i}>{x.label}</option>)}</select>
        <input value={v.label} onChange={(e) => upd({ ...v, label: e.target.value })} aria-label="libellé de la vue" />
        <button className="secondary" onClick={() => { const id = `vue-${Date.now() % 1000000}`; setViews([...views, { id, label: "Nouvelle vue", groups: [] }]); setVi(views.length); }}>+ Vue</button>
        {views.length > 1 && <button className="secondary" onClick={() => { if (window.confirm(`Supprimer la vue « ${v.label} » ?`)) { setViews(views.filter((_, i) => i !== vi)); setVi(0); } }}>Supprimer la vue</button>}
        <button className="secondary" onClick={() => upd({ ...v, groups: [...v.groups, { name: `Groupe ${v.groups.length + 1}`, agents: [], note: "" }] })}>+ Groupe</button>
        <button className="secondary" onClick={() => setViews(suggestViews(views, fleet))} title="range les agents dans les vues encore vides (catégories, OS, Ollama, étiquette #perso)">Proposer un rangement</button>
        <button className="primary" onClick={onSave} disabled={busy}>Enregistrer</button><button className="secondary" onClick={onCancel}>Fermer</button>
      </div>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", margin: "8px 0" }}>{v.groups.map((g, gi) => (
        <span key={gi} style={{ display: "inline-flex", gap: 6, alignItems: "center", border: "1px solid var(--viz-grid, #ccc)", borderRadius: 6, padding: "4px 6px" }}><input value={g.name} onChange={(e) => upd({ ...v, groups: v.groups.map((x, k) => (k === gi ? { ...x, name: e.target.value } : x)) })} style={{ width: 150 }} />
          <input value={g.note || ""} placeholder="note" onChange={(e) => upd({ ...v, groups: v.groups.map((x, k) => (k === gi ? { ...x, note: e.target.value } : x)) })} style={{ width: 120 }} />
          <small>{g.agents.length} agent(s)</small>
          <span>{gi > 0 && <button className="secondary" onClick={() => { const gs = [...v.groups]; [gs[gi - 1], gs[gi]] = [gs[gi], gs[gi - 1]]; upd({ ...v, groups: gs }); }}>◀</button>}
            <button className="secondary" onClick={() => upd({ ...v, groups: v.groups.filter((_, k) => k !== gi) })}>✕</button></span></span>))}</div>
      <input value={filter} onChange={(e) => setFilter(e.target.value)} placeholder="filtrer les agents" />
      <div className="infra-table-wrap infra-scroll" style={{ maxHeight: "50vh" }}>
        <table className="infra-table"><thead><tr><th>Agent</th><th>Système</th><th>Groupe dans « {v.label} »</th></tr></thead>
          <tbody>{shown.map((a) => (
            <tr key={a.agent_id} className={inView.has(a.agent_id) ? "infra-host" : ""}><td><b>{a.hostname || a.agent_id}</b> <span className="infra-muted">{a.agent_id}{a.label && a.label !== a.agent_id ? ` · ${a.label}` : ""}</span></td><td className="infra-muted">{a.os || "—"}</td>
              <td><select value={where(a.agent_id)} onChange={(e) => upd(moveAgent(v, a.agent_id, Number(e.target.value) < 0 ? null : Number(e.target.value)))}>
                <option value={-1}>— hors vue —</option>{v.groups.map((g, gi) => <option key={gi} value={gi}>{g.name}</option>)}</select></td></tr>))}</tbody></table>
      </div>
    </div>
  );
}

export default function FleetViewsView({ onBack, siAgentApiBase, username }) {
  const base = siAgentApiBase;
  const [views, setViews] = useState(null);
  const [vid, setVid] = useState(() => { try { return localStorage.getItem("fleetviews.vid") || "serveurs"; } catch { return "serveurs"; } });
  const [data, setData] = useState(null);
  const [err, setErr] = useState(null);
  const [at, setAt] = useState(null);
  const [sort, setSort] = useState({ col: "name", dir: -1 });
  const [compact, setCompact] = useState(false);
  const [edit, setEdit] = useState(null);
  const [fleet, setFleet] = useState([]);
  const [busy, setBusy] = useState(false);

  useEffect(() => { fetchViews(base).then((r) => setViews(r?.views || [])).catch((e) => setErr(e.message)); }, [base]);
  useEffect(() => {
    if (!views?.length) return undefined;
    const id = views.some((v) => v.id === vid) ? vid : views[0].id;
    if (id !== vid) setVid(id);
    try { localStorage.setItem("fleetviews.vid", id); } catch { /* stockage indisponible */ }
    let stop = false;
    const load = () => fetchViewOverview(base, id).then((d) => { if (!stop) { setData(d); setErr(d?.error || null); setAt(new Date()); } }).catch((e) => !stop && setErr(e.message));
    load(); const t = setInterval(load, 30000);
    return () => { stop = true; clearInterval(t); };
  }, [base, vid, views]);

  const organize = async () => { setFleet(await fetchFleet(base).catch(() => [])); setEdit(JSON.parse(JSON.stringify(views))); };
  const save = async () => {
    setBusy(true);
    try { const r = await saveViews(base, edit, username); if (r?.error) throw new Error(r.error); setViews(r.views); setEdit(null); } catch (e) { window.alert(e.message); } finally { setBusy(false); }
  };

  return (
    <div className="infra-root">
      <div className="infra-top">
        <button className="secondary" onClick={onBack}>◀ Retour</button>
        <h2>Vues de parc</h2>
        <div className="infra-tabs">{(views || []).map((v) => <button key={v.id} className={vid === v.id ? "active" : ""} onClick={() => setVid(v.id)}>{v.label}</button>)}</div>
        <label className="infra-muted"><input type="checkbox" checked={compact} onChange={(e) => setCompact(e.target.checked)} /> compact</label>
        <button className="secondary" onClick={organize}>Organiser</button>
        <span className="infra-muted">{at ? `mis à jour ${at.toLocaleTimeString("fr-FR")}` : "lecture…"}</span>
      </div>
      <DataStatus base={base} tasks={["host", "plugin:node-activity", "plugin:ollama"]} error={err} stale={900} refreshKey={at ? at.getTime() : 0}
        labels={{ host: "relevé des hôtes", "plugin:node-activity": "détail des nœuds", "plugin:ollama": "modèles IA" }} />
      {edit && <Organizer views={edit} setViews={setEdit} fleet={fleet} onSave={save} onCancel={() => setEdit(null)} busy={busy} />}
      {data && <>
        {data.groups.length === 0 && <p className="infra-muted">Cette vue n'a pas encore de groupe : « Organiser » puis « Proposer un rangement », ou créer les groupes à la main.</p>}
        {data.groups.map((g, i) => <GroupTable key={i} g={g} sort={sort} setSort={setSort} compact={compact} />)}
        {data.unassigned?.length > 0 && <p className="infra-muted">Hors de cette vue : {data.unassigned.length} agent(s) ({data.unassigned.slice(0, 12).join(", ")}{data.unassigned.length > 12 ? "…" : ""}).</p>}
      </>}
    </div>
  );
}
