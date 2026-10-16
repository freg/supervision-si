// Tuile « Infra PVE / PBS » (livraison #749) : vue d'ensemble des Proxmox VE et PBS locaux et distants (OVH) --
// stockages, VM, CPU / mémoire, débits, connexions, transferts en cours, constats ; onglet « htop » (en-tête de htop
// pour chaque hôte et chaque VM, en tableau trié). Pleine largeur ; rafraîchie toutes les 30 s.
// Données : si-agent-api /infra/overview (sondes node-activity, proxmox, pve-remote, pbs).
import DataStatus from "./DataStatus.jsx";   // #763 : état des données
import { useEffect, useMemo, useState } from "react";
import { fetchInfraOverview } from "./siAgentClient.js";
import { fmtBytes, fmtBps, fmtUptime, fillLevel, donutArcs, htopRows, sortRows, groupByHost, fills, pct } from "./infraLib.js";

const ZONE = { local: "local", distant: "distant (OVH)" };
const TABS = [["synthese", "Synthèse"], ["htop", "htop"], ["transferts", "Transferts"], ["constats", "Constats"]];

function Status({ tone, label }) {
  if (!label) return null;
  return <span className={`infra-status ${tone}`}>{tone === "critical" ? "⛔" : "⚠"} {label}</span>;
}

function Donut({ title, segments, center, sub }) {
  const arcs = donutArcs(segments);
  return (
    <figure className="infra-card infra-donut">
      <figcaption>{title}</figcaption>
      <div className="infra-donut-body">
        <svg viewBox="0 0 120 120" width="140" height="140" role="img" aria-label={title}>
          {arcs.length === 0 && <circle cx="60" cy="60" r="43" fill="none" stroke="var(--viz-grid)" strokeWidth="18" />}
          {arcs.map((a) => <path key={a.label} d={a.d} fill={a.color}><title>{`${a.label} : ${a.text} (${Math.round(a.share * 100)} %)`}</title></path>)}
          <text x="60" y="58" textAnchor="middle" className="infra-donut-center">{center}</text>
          {sub && <text x="60" y="74" textAnchor="middle" className="infra-donut-sub">{sub}</text>}
        </svg>
        <ul className="infra-legend">{segments.map((s) => <li key={s.label}><i style={{ background: s.color }} />{s.label}<b>{s.text}</b></li>)}</ul>
      </div>
    </figure>
  );
}

// Barres horizontales groupées : rows [{label, values: [nombre], note?}], series [{name, color}] ; échelle commune 0..max
function Bars({ title, rows, series, max, fmt, note, empty }) {
  const m = max || Math.max(1, ...rows.flatMap((r) => r.values.map((v) => v || 0)));
  const h = series.length > 1 ? 9 : 12;
  return (
    <figure className="infra-card infra-bars">
      <figcaption>{title}{note && <span className="infra-note"> · {note}</span>}</figcaption>
      {series.length > 1 && <ul className="infra-legend inline">{series.map((s) => <li key={s.name}><i style={{ background: s.color }} />{s.name}</li>)}</ul>}
      {rows.length === 0 ? <p className="infra-muted">{empty || "Aucune donnée."}</p> : (
        <div className="infra-bars-list infra-scroll">
          {rows.map((r) => (
            <div key={r.label} className="infra-bar-row">
              <span className="infra-bar-label" title={r.label}>{r.label}</span>
              <svg className="infra-bar-svg" viewBox={`0 0 100 ${series.length * (h + 2)}`} preserveAspectRatio="none" height={series.length * (h + 2)}>
                {r.values.map((v, i) => (
                  <rect key={i} x="0" y={i * (h + 2)} width={Math.max(v ? 0.6 : 0, (100 * (v || 0)) / m)} height={h} rx="2" fill={series[i].color}>
                    <title>{`${r.label} — ${series[i].name} : ${fmt(v)}`}</title>
                  </rect>
                ))}
              </svg>
              <span className="infra-bar-value">{r.values.map((v) => fmt(v)).join(" / ")} <Status {...(r.status || {})} /></span>
            </div>
          ))}
        </div>
      )}
    </figure>
  );
}

function Kpi({ label, value, sub, tone }) {
  return <div className={`infra-kpi ${tone || ""}`}><span>{label}</span><b>{value}</b>{sub && <small>{sub}</small>}</div>;
}

function Meter({ value, max, label }) {
  const p = max ? Math.min(100, (100 * (value || 0)) / max) : value;
  if (p == null) return <span className="infra-muted">—</span>;
  const lv = fillLevel(p);
  return <span className="infra-meter-wrap" title={label}><span className="infra-meter"><span className={`fill ${lv.tone}`} style={{ width: `${p}%` }} /></span><em>{label}</em></span>;
}

function Cores({ cores }) {
  if (!cores?.length) return <span className="infra-muted">—</span>;
  return <span className="infra-cores" title={cores.map((c, i) => `${i + 1}: ${c ?? "?"} %`).join("  ")}>{cores.map((c, i) => <i key={i} style={{ height: `${Math.max(6, c || 0)}%` }} className={fillLevel(c).tone} />)}</span>;
}

export default function InfraView({ onBack, siAgentApiBase }) {
  const [data, setData] = useState(null);
  const [err, setErr] = useState(null);
  const [tab, setTab] = useState(() => { try { return localStorage.getItem("infra.tab") || "synthese"; } catch { return "synthese"; } });
  const [zone, setZone] = useState("all");
  const [sort, setSort] = useState({ col: "cpu", dir: -1 });
  const [grouped, setGrouped] = useState(true);
  const [at, setAt] = useState(null);

  useEffect(() => {
    let stop = false;
    const load = () => fetchInfraOverview(siAgentApiBase).then((d) => { if (!stop) { setData(d); setErr(d?.error || null); setAt(new Date()); } }).catch((e) => !stop && setErr(e.message));
    load();
    const id = setInterval(load, 30000);
    return () => { stop = true; clearInterval(id); };
  }, [siAgentApiBase]);
  useEffect(() => { try { localStorage.setItem("infra.tab", tab); } catch { /* stockage indisponible */ } }, [tab]);

  const view = useMemo(() => {
    if (!data) return null;
    const keep = (z) => zone === "all" || z === zone;
    return { ...data, nodes: (data.nodes || []).filter((n) => keep(n.zone)), vms: (data.vms || []).filter((v) => keep(v.zone)), transfers: (data.transfers || []).filter((t) => keep(t.zone)) };
  }, [data, zone]);
  const rows = useMemo(() => (grouped ? groupByHost : sortRows)(htopRows(view), sort.col, sort.dir), [view, sort, grouped]);

  const C = { s1: "var(--viz-1)", s2: "var(--viz-2)", s3: "var(--viz-3)", free: "var(--viz-free)" };
  const T = data?.totals || {};
  const th = (col, label) => <th onClick={() => setSort({ col, dir: sort.col === col ? -sort.dir : -1 })} className={sort.col === col ? "sorted" : ""}>{label}{sort.col === col ? (sort.dir < 0 ? " ▼" : " ▲") : ""}</th>;

  return (
    <div className="infra-root">
      <div className="infra-top">
        <button className="secondary" onClick={onBack}>◀ Retour</button>
        <h2>Infra PVE / PBS</h2>
        <div className="infra-tabs">{TABS.map(([k, l]) => <button key={k} className={tab === k ? "active" : ""} onClick={() => setTab(k)}>{l}{k === "constats" && data?.alerts?.length ? ` (${data.alerts.length})` : ""}</button>)}</div>
        <select value={zone} onChange={(e) => setZone(e.target.value)} aria-label="zone"><option value="all">local + distant</option><option value="local">local</option><option value="distant">distant (OVH)</option></select>
        {tab === "htop" && <label className="infra-muted"><input type="checkbox" checked={grouped} onChange={(e) => setGrouped(e.target.checked)} /> VM sous leur hôte</label>}
        <span className="infra-muted">{at ? `mis à jour ${at.toLocaleTimeString("fr-FR")}` : "lecture…"}</span>
      </div>
      {err && <p className="infra-error">{err}</p>}
      <DataStatus base={siAgentApiBase} tasks={["plugin:node-activity", "plugin:proxmox", "plugin:pve-remote", "plugin:pbs"]} error={err} refreshKey={at ? at.getTime() : 0} />
      {view && !view.nodes.length && <p className="infra-muted">Aucun nœud : activer les sondes <code>node-activity</code> (hôte local + nœuds distants de pve-remote.json), <code>proxmox</code>, <code>pve-remote</code> et <code>pbs</code> sur les agents des Proxmox (Agents hôtes › fiche › Sondes).</p>}

      {view && tab === "synthese" && (
        <div className="infra-scroll infra-page">
          <div className="infra-kpis">
            {["local", "distant"].filter((z) => zone === "all" || z === zone).map((z) => T[z] && (
              <div key={z} className="infra-kpi-group">
                <h3>{ZONE[z]}</h3>
                <Kpi label="nœuds joignables" value={`${T[z].reachable} / ${T[z].nodes}`} tone={T[z].reachable < T[z].nodes ? "warning" : ""} />
                <Kpi label="VM en marche" value={T[z].vms_running} sub={`${T[z].vms_stopped} arrêtée(s)`} />
                <Kpi label="stockages" value={`${pct(T[z].storage_used, T[z].storage_total) ?? "—"} %`} sub={`${fmtBytes(T[z].storage_used)} / ${fmtBytes(T[z].storage_total)}`} tone={fillLevel(pct(T[z].storage_used, T[z].storage_total)).tone} />
                <Kpi label="débit" value={fmtBps(T[z].rx_bps + T[z].tx_bps)} sub={`↓ ${fmtBps(T[z].rx_bps)} · ↑ ${fmtBps(T[z].tx_bps)}`} />
                <Kpi label="connexions établies" value={T[z].estab} />
              </div>
            ))}
            <div className="infra-kpi-group"><h3>activité</h3>
              <Kpi label="transferts en cours" value={view.transfers.filter((t) => t.what === "processus" || (t.what === "fichier" && t.active)).length} />
              <Kpi label="constats" value={(data.alerts || []).length} tone={(data.alerts || []).some((a) => a.severity === "critical") ? "critical" : (data.alerts || []).length ? "warning" : ""} />
            </div>
          </div>
          <div className="infra-grid">
            {["local", "distant"].filter((z) => (zone === "all" || z === zone) && T[z]?.storage_total).map((z) => (
              <Donut key={`st${z}`} title={`Stockages ${ZONE[z]}`} center={`${pct(T[z].storage_used, T[z].storage_total)} %`} sub="occupé"
                segments={[{ label: "occupé", value: T[z].storage_used, color: C.s1, text: fmtBytes(T[z].storage_used) }, { label: "libre", value: T[z].storage_total - T[z].storage_used, color: C.free, text: fmtBytes(T[z].storage_total - T[z].storage_used) }]} />
            ))}
            {["local", "distant"].filter((z) => (zone === "all" || z === zone) && T[z]?.vms_running + T[z]?.vms_stopped).map((z) => (
              <Donut key={`vm${z}`} title={`VM / CT ${ZONE[z]}`} center={T[z].vms_running + T[z].vms_stopped} sub="invités"
                segments={[{ label: "en marche", value: T[z].vms_running, color: C.s1, text: String(T[z].vms_running) }, { label: "arrêtés", value: T[z].vms_stopped, color: C.s2, text: String(T[z].vms_stopped) }]} />
            ))}
            <Bars title="Remplissage des disques, pools et stockages (%)" note="seuils 85 / 95 %" series={[{ name: "occupé", color: C.s1 }]} max={100} fmt={(v) => (v == null ? "—" : `${v} %`)}
              rows={fills(view).slice(0, 40).map((f) => ({ label: `${f.node} · ${f.what}`, values: [f.pct], status: fillLevel(f.pct) }))} />
            <Bars title="CPU et mémoire par nœud (%)" series={[{ name: "CPU", color: C.s1 }, { name: "mémoire", color: C.s2 }]} max={100} fmt={(v) => (v == null ? "—" : `${Math.round(v)} %`)}
              rows={view.nodes.filter((n) => n.cpu_pct != null || n.mem_total).map((n) => ({ label: n.name, values: [n.cpu_pct, pct(n.mem_used, n.mem_total)] }))} empty="sonde node-activity inactive" />
            <Bars title="Débit réseau par nœud" series={[{ name: "reçu", color: C.s1 }, { name: "émis", color: C.s2 }]} fmt={fmtBps}
              rows={view.nodes.filter((n) => (n.net || []).length).map((n) => ({ label: n.name, values: [(n.net || []).reduce((a, i) => a + (i.rx_bps || 0), 0), (n.net || []).reduce((a, i) => a + (i.tx_bps || 0), 0)] }))} empty="sonde node-activity inactive" />
            <Bars title="Connexions TCP établies par nœud" series={[{ name: "établies", color: C.s3 }]} fmt={(v) => (v == null ? "—" : String(v))}
              rows={view.nodes.filter((n) => n.conn?.estab != null).map((n) => ({ label: n.name, values: [n.conn.estab] }))} empty="sonde node-activity inactive" />
            <Bars title="Invités par nœud" series={[{ name: "en marche", color: C.s1 }, { name: "arrêtés", color: C.s2 }]} fmt={(v) => String(v ?? 0)}
              rows={view.nodes.filter((n) => n.guests?.total).map((n) => ({ label: n.name, values: [n.guests.running, n.guests.stopped] }))} />
            <Bars title="Transferts : débit des fichiers en cours" series={[{ name: "débit", color: C.s1 }]} fmt={fmtBps}
              rows={view.transfers.filter((t) => t.what === "fichier" && t.active).map((t) => ({ label: `${t.node} · ${(t.path || "").split("/").pop()} (${fmtBytes(t.size)})`, values: [(t.rate_bps || 0) * 8] }))} empty="aucun fichier en cours d'écriture dans les dossiers surveillés" />
          </div>
        </div>
      )}

      {view && tab === "htop" && (
        <div className="infra-table-wrap infra-scroll">
          <table className="infra-table">
            <thead><tr>{th("kind", "Type")}{th("name", "Nom")}{th("host", "Hôte")}{th("zone", "Zone")}{th("cpu", "CPU")}<th>Cœurs</th>{th("mem", "Mémoire")}<th>Swap</th><th>Tâches</th>{th("load", "Charge 1 / 5 / 15")}{th("uptime", "Uptime")}{th("status", "État")}</tr></thead>
            <tbody>{rows.map((r) => (
              <tr key={r.key} className={r.kind === "PVE" || r.kind === "PBS" ? "infra-host" : ""}>
                <td>{r.kind}</td><td>{grouped && (r.kind === "VM" || r.kind === "CT") ? <span className="infra-muted">└ </span> : null}{r.name}{r.error && <span className="infra-muted" title={r.error}> ⚠</span>}</td><td>{r.host}</td><td>{ZONE[r.zone] || r.zone}</td>
                <td><Meter value={r.cpu} label={r.cpu == null ? "—" : `${r.cpu} %${r.ncpu ? ` · ${r.ncpu} vCPU` : ""}`} /></td>
                <td><Cores cores={r.cores} /></td>
                <td><Meter value={r.mem} max={r.maxmem} label={r.maxmem ? `${fmtBytes(r.mem)} / ${fmtBytes(r.maxmem)}` : "—"} /></td>
                <td>{r.maxswap ? <Meter value={r.swap} max={r.maxswap} label={`${fmtBytes(r.swap)} / ${fmtBytes(r.maxswap)}`} /> : <span className="infra-muted">—</span>}</td>
                <td>{r.tasks ? `${r.tasks.total} (${r.tasks.running} en cours)` : "—"}</td>
                <td>{r.load ? r.load.map((x) => x.toFixed(2)).join("  ") : "—"}</td>
                <td>{fmtUptime(r.uptime)}</td><td>{r.status}</td>
              </tr>
            ))}</tbody>
          </table>
        </div>
      )}

      {view && tab === "transferts" && <PveTasks tasks={(data.pve_tasks || []).filter((t) => view.nodes.some((n) => n.name === t.node))} />}
      {view && tab === "transferts" && <XferDestinations rows={view.transfers.filter((t) => t.what === "destination")} />}
      {view && tab === "transferts" && (
        <div className="infra-table-wrap infra-scroll">
          <table className="infra-table">
            <thead><tr><th>Nœud</th><th>Zone</th><th>Nature</th><th>Objet</th><th>Taille</th><th>Débit</th><th>Depuis</th><th>Actif</th></tr></thead>
            <tbody>{view.transfers.length === 0 ? <tr><td colSpan={8} className="infra-muted">Aucun transfert en cours (processus vzdump, restauration, importdisk, zfs send/recv, rsync, scp ; fichiers récents des dossiers surveillés).</td></tr>
              : view.transfers.filter((t) => t.what !== "destination").map((t, i) => (
                <tr key={i}><td>{t.node}</td><td>{ZONE[t.zone] || t.zone}</td><td>{t.what === "processus" ? t.kind : "fichier"}</td>
                  <td className="infra-mono">{t.what === "processus" ? t.cmd : t.path}</td><td>{fmtBytes(t.size)}</td><td>{t.rate_bps != null ? fmtBps(t.rate_bps * 8) : "—"}</td>
                  <td>{t.elapsed_s != null ? fmtUptime(t.elapsed_s) : "—"}</td><td>{t.what === "processus" || t.active ? "oui" : "non"}</td></tr>))}</tbody>
          </table>
        </div>
      )}

      {view && tab === "constats" && (
        <div className="infra-table-wrap infra-scroll">
          <table className="infra-table">
            <thead><tr><th>Gravité</th><th>Constat</th><th>Agent</th></tr></thead>
            <tbody>{(data.alerts || []).length === 0 ? <tr><td colSpan={3} className="infra-muted">Aucun constat.</td></tr>
              : data.alerts.map((a) => <tr key={a.code}><td><Status tone={a.severity === "critical" ? "critical" : "warning"} label={a.severity === "critical" ? "critique" : "attention"} /></td><td>{a.message}</td><td>{a.agent_id}</td></tr>)}</tbody>
          </table>
        </div>
      )}
    </div>
  );
}


// #773 : destinations des transferts en cours (zfs send vers un fichier, zfs recv, rsync / scp vers un volume ou un disque) --
// copié, débit, fin estimée quand la taille totale est connue (snapshot envoyé), blocage après 6 min sans croissance.
function XferDestinations({ rows }) {
  if (!rows.length) return null;
  const eta = (s) => (s == null ? "—" : s < 3600 ? `${Math.max(1, Math.round(s / 60))} min` : s < 172800 ? `${(s / 3600).toFixed(1)} h` : `${Math.round(s / 86400)} j`);
  return (
    <div className="infra-card" style={{ marginBottom: 10 }}>
      <figcaption>Destinations des transferts <span className="infra-note">mesurées toutes les 2 min sur le nœud qui reçoit</span></figcaption>
      <table className="infra-table">
        <thead><tr><th>Nœud</th><th>Transfert</th><th>Destination</th><th>Copié</th><th>Avancement</th><th>Débit</th><th>Fin estimée</th></tr></thead>
        <tbody>{rows.map((t) => (
          <tr key={`${t.node}${t.key}`} title={t.cmd}>
            <td>{t.node}</td><td>{t.label}</td>
            <td className="infra-mono">{t.dest}<div className="infra-muted" style={{ fontSize: 11 }}>{t.measure}{t.measure !== "fichier" ? " (taille occupée du volume)" : ""}</div></td>
            <td>{fmtBytes(t.size)}{t.total ? ` / ${fmtBytes(t.total)}` : ""}</td>
            <td style={{ minWidth: 120 }}>{t.pct != null ? (<><div style={{ height: 8, background: "var(--border)", borderRadius: 4, overflow: "hidden" }}><div style={{ width: `${t.pct}%`, height: "100%", background: "var(--viz-1)" }} /></div><small>{t.pct} %</small></>) : <span className="infra-muted">total inconnu</span>}</td>
            <td>{t.stalled_runs >= 3 ? <Status tone="warning" label="ne progresse plus" /> : t.rate_bps != null ? fmtBps(t.rate_bps * 8) : "mesure au prochain passage"}</td>
            <td>{eta(t.eta_s)}</td>
          </tr>))}</tbody>
      </table>
    </div>
  );
}


// #766 : tâches Proxmox en cours (sauvegardes vzdump : CT / VM en cours, terminés, avancement ; autres tâches : dernière ligne)
const PBAR = (pct, est) => <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
  <span style={{ display: "inline-block", width: 160, height: 10, borderRadius: 5, background: "var(--border, #ccc)", overflow: "hidden" }}>
    <span style={{ display: "block", height: "100%", width: `${Math.max(0, Math.min(100, pct || 0))}%`, background: "var(--accent, #2a78d6)", transition: "width .5s" }} /></span>
  <b>{pct != null ? `${pct} %` : "—"}</b>{est && <span className="infra-muted" title="estimé : octets lus par proxmox-backup-client / espace utilisé du CT">≈</span>}</span>;

function PveTasks({ tasks }) {
  if (!tasks.length) return <p className="infra-muted">Aucune tâche Proxmox en cours sur les nœuds affichés.</p>;
  return <div className="infra-card" style={{ marginBottom: 8 }}><h4 style={{ marginTop: 0 }}>Tâches Proxmox en cours</h4>
    {tasks.map((t) => <div key={t.upid} style={{ marginBottom: 8 }}>
      <div><b>{t.node}</b> · {t.type}{t.id ? ` ${t.id}` : ""} · {t.user} · depuis {fmtUptime(t.elapsed_s)}</div>
      {t.progress ? <>
        <div>Ensemble : {PBAR(t.progress.overall_pct)} <span className="infra-muted">{t.progress.n_done} / {t.progress.n_total} terminé(s){t.done.length ? ` (${t.done.map((d) => `${d.vmid} en ${d.duration}`).join(", ")})` : ""}</span></div>
        {t.current != null && <div>En cours : <b>{t.current}</b> {PBAR(t.progress.current_pct, t.progress.current_estimated)}{t.detail && <span className="infra-muted"> {t.detail}</span>}{t.read_bytes != null && <span className="infra-muted"> · {fmtBytes(t.read_bytes)} lus</span>}</div>}
        {t.failed.map((f) => <div key={f.vmid} className="infra-status critical">{f.vmid} : {f.error}</div>)}
        {t.summary && <div className="infra-muted" style={{ fontSize: 12 }}>Dernier bilan : {t.summary}</div>}
      </> : <div className="infra-muted" style={{ fontSize: 12 }}>{t.percent != null ? PBAR(t.percent) : null} {t.last}</div>}
    </div>)}</div>;
}
