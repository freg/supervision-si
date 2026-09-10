import React, { useState, useEffect, useCallback } from "react";
import { fetchCompareApps, fetchUnified } from "./retroClient.js";
import { functionMatrix, fieldOrigin, sourceLabel, unifiedSummary, canCompare, coverage } from "./unifiedTool.js";
import GeneratedAppView from "./GeneratedAppView.jsx";
import MetaGraphView from "./MetaGraphView.jsx";

// Outil unique (livraison #445, phase 3) : compare les applications
// enregistrées (écrans remplissant la même fonction : mêmes champs /
// colonnes après normalisation, titres, tables) et présente UNE interface
// -- un écran par fonction, champs = union -- rendue application par
// application sur ses tables réelles (projection `view=`), avec les champs
// communs et ceux propres à chaque application.
export default function UnifiedToolView({ retroApiBase, dbaApiBase, apps, onClose }) {
  const [selected, setSelected] = useState(() => (apps || []).map((a) => a.label));
  const [comparison, setComparison] = useState(null);
  const [unified, setUnified] = useState(null);
  const [view, setView] = useState("");       // application rendue
  const [viewSpec, setViewSpec] = useState(null);
  const [mode, setMode] = useState("matrix"); // matrix | fields | app | meta (#448)
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    if (!canCompare(selected)) { setComparison(null); setUnified(null); return; }
    setBusy(true); setError(null);
    const [c, u] = await Promise.all([fetchCompareApps(retroApiBase, selected), fetchUnified(retroApiBase, selected)]);
    setBusy(false);
    if (c.error) { setError(c.error); return; }
    if (u.error) { setError(u.error); return; }
    setComparison(c); setUnified(u);
    setView((cur) => (cur && selected.includes(cur) ? cur : selected[0]));
  }, [retroApiBase, selected]);
  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    if (!view || !canCompare(selected)) { setViewSpec(null); return; }
    fetchUnified(retroApiBase, selected, view).then((r) => { if (r.error) setError(r.error); else setViewSpec(r); });
  }, [retroApiBase, selected, view]);

  function toggle(label) {
    setSelected((cur) => (cur.includes(label) ? cur.filter((x) => x !== label) : [...cur, label]));
  }

  const rows = functionMatrix(comparison);
  const appList = comparison?.apps || selected;

  return (
    <div className="hub-card hub-settings-section" style={{ borderColor: "var(--accent, #2b5797)" }}>
      <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
        <h2 style={{ margin: 0 }}>Outil unique</h2>
        <span className="muted">{unified ? unifiedSummary(unified) : "comparaison des applications enregistrées"}</span>
        <span style={{ flex: 1 }} />
        <button className={mode === "matrix" ? "" : "secondary"} onClick={() => setMode("matrix")}>Fonctions × applications</button>
        <button className={mode === "fields" ? "" : "secondary"} onClick={() => setMode("fields")}>Champs unifiés</button>
        <button className={mode === "app" ? "" : "secondary"} onClick={() => setMode("app")}>Interface unique</button>
        <button className={mode === "meta" ? "" : "secondary"} onClick={() => setMode("meta")} title="entités, attributs, relations intra et inter-applications, proposition de fusion">Méta-graphe &amp; fusion</button>
        <button className="secondary" disabled={busy} onClick={load}>↻</button>
        <button className="secondary" onClick={onClose}>Fermer</button>
      </div>
      <div style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap", margin: "8px 0" }}>
        <span className="muted">Applications comparées :</span>
        {(apps || []).map((a) => (
          <label key={a.label} style={{ cursor: "pointer" }}>
            <input type="checkbox" checked={selected.includes(a.label)} onChange={() => toggle(a.label)} /> {a.label}
          </label>
        ))}
        {!canCompare(selected) && <span style={{ color: "var(--warning, #b7791f)" }}>cochez au moins deux applications</span>}
      </div>
      {error && <p style={{ color: "var(--danger)" }}>⚠️ {error}</p>}
      {busy && !comparison && <p className="muted">Comparaison…</p>}

      {mode === "matrix" && comparison && (
        <>
          <p className="muted" style={{ fontSize: 12 }}>
            {comparison.counts.groups} fonction(s) commune(s) ({comparison.counts.shared_by_all} à toutes), {comparison.counts.unique} écran(s) sans équivalent.
            {appList.length === 2 && ` Recouvrement fonctionnel ${appList[0]} / ${appList[1]} : ${coverage(comparison, appList[0], appList[1])} %.`}
            {" "}Rapprochement par champs et colonnes de même nom (préfixes de formulaire, accents, pluriels et synonymes courants FR/EN ignorés), titres et tables ; un score sous {Math.round(0.4 * 100)} % ne rapproche pas.
          </p>
          <div className="hub-table-scroll">
            <table>
              <thead><tr><th>Fonction</th><th>Genre</th>{appList.map((a) => <th key={a}>{a}</th>)}<th>Score · raisons</th><th>Champs communs</th><th>Champs propres</th></tr></thead>
              <tbody>{rows.map((r, i) => (
                <tr key={i} style={r.shared ? undefined : { opacity: r.score == null ? 0.7 : 1 }}>
                  <td><strong>{r.function}</strong>{r.shared && <span className="na-chip" style={{ marginLeft: 6 }}>commun</span>}</td>
                  <td className="muted">{r.kind}</td>
                  {appList.map((a) => <td key={a}>{r.cells[a] ? <span title={r.cells[a].id}>{r.cells[a].title || r.cells[a].id}<div className="muted" style={{ fontSize: 11 }}><code>{r.cells[a].screen}</code>{r.cells[a].table ? ` · ${r.cells[a].table}` : ""}</div></span> : <span className="muted">—</span>}</td>)}
                  <td className="muted" style={{ fontSize: 12 }}>{r.score != null ? `${Math.round(r.score * 100)} % · ` : ""}{r.why.join(" ; ")}</td>
                  <td className="muted" style={{ fontSize: 12 }}>{r.common.join(", ")}</td>
                  <td className="muted" style={{ fontSize: 12 }}>{Object.entries(r.specific).filter(([, v]) => v.length).map(([a, v]) => `${a} : ${v.join(", ")}`).join(" · ")}</td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        </>
      )}

      {mode === "fields" && unified && (
        <div style={{ marginTop: 8 }}>
          {unified.screens.map((s) => (
            <div key={s.id} className="hub-card hub-settings-section" style={{ margin: "0 0 8px 0", padding: 12 }}>
              <h3 style={{ margin: "0 0 4px 0" }}>{s.title} <span className="muted" style={{ fontWeight: 400, fontSize: 12 }}>{s.kind} · {s.apps.join(", ")}{s.score != null ? ` · ${Math.round(s.score * 100)} %` : ""}</span>
                {s.shared ? <span className="na-chip" style={{ marginLeft: 6 }}>commun</span> : s.apps.length > 1 ? <span className="na-chip" style={{ marginLeft: 6 }}>partiel</span> : <span className="na-chip" style={{ marginLeft: 6 }}>propre</span>}</h3>
              {s.todo?.length > 0 && <p style={{ color: "var(--warning, #b7791f)", fontSize: 12, margin: "0 0 4px" }}>{s.todo.join(" ; ")}</p>}
              <div className="hub-table-scroll">
                <table>
                  <thead><tr><th>{s.kind === "list" ? "Colonne" : "Champ"}</th><th>Origine</th>{unified.apps.map((a) => <th key={a}>{a}</th>)}</tr></thead>
                  <tbody>
                    {(s.kind === "list" ? s.columns : s.fields).map((f) => (
                      <tr key={f.name || f.label}>
                        <td>{f.label || f.name}{f.required ? " *" : ""}{f.name && f.label !== f.name ? <span className="muted" style={{ fontSize: 11 }}> ({f.name})</span> : ""}</td>
                        <td className="muted" style={{ fontSize: 12 }}>{fieldOrigin(f, unified.apps)}</td>
                        {unified.apps.map((a) => <td key={a} style={{ fontSize: 12 }}>{sourceLabel(f, a) ? <code>{sourceLabel(f, a)}</code> : <span className="muted">—</span>}{f.names?.[a] && f.names[a] !== f.name ? <span className="muted"> · champ {f.names[a]}</span> : ""}</td>)}
                      </tr>
                    ))}
                    {(s.kind === "list" ? s.columns : s.fields).length === 0 && <tr><td colSpan={2 + unified.apps.length} className="muted">aucun champ vu dans les parcours</td></tr>}
                  </tbody>
                </table>
              </div>
            </div>
          ))}
        </div>
      )}

      {mode === "meta" && canCompare(selected) && <MetaGraphView retroApiBase={retroApiBase} apps={selected} />}

      {mode === "app" && unified && (
        <div style={{ marginTop: 8 }}>
          <div className="hub-settings-row" style={{ margin: "0 0 8px 0" }}>
            <label>Données de l'application</label>
            <select value={view} onChange={(e) => setView(e.target.value)}>
              {unified.apps.map((a) => <option key={a} value={a}>{a}</option>)}
            </select>
            <span className="muted" style={{ fontSize: 12 }}>mêmes écrans pour toutes les applications ; lecture / écriture dans les tables de celle choisie (les champs qu'elle n'a pas sont indiqués, non saisissables)</span>
          </div>
          {viewSpec && viewSpec.app === view && <GeneratedAppView key={view} retroApiBase={retroApiBase} dbaApiBase={dbaApiBase} app={view} externalSpec={viewSpec} heading={`Interface unique — données de « ${view} »`} />}
        </div>
      )}
    </div>
  );
}
