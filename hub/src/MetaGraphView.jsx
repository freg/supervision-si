import React, { useState, useEffect, useMemo } from "react";
import { fetchMetagraph } from "./retroClient.js";
import { layoutGraph, edgePath, edgeMidpoint, edgeLabel, graphSummary, proposalSummary, fieldInventory, EDGE_STYLES, HEAD_H, ROW_H, MAX_ROWS } from "./metaGraph.js";

// Méta-relevé et proposition de fusion (livraison #448, phase 4) : le
// graphe des entités (tables) de chaque application, leurs attributs, les
// relations intra-application (code, journal SQL, noms), les équivalences
// entre applications (spec unique) et les références inter-gestions ;
// le relevé des champs ligne à ligne ; la proposition d'évolution
// (entités cibles fusionnées, correspondance des attributs, conflits de
// types, attributs propres, relations conservées).
export default function MetaGraphView({ retroApiBase, apps }) {
  const [graph, setGraph] = useState(null);
  const [error, setError] = useState(null);
  const [mode, setMode] = useState("graph"); // graph | fields | proposal
  const [selected, setSelected] = useState(null); // id du nœud
  const [filter, setFilter] = useState("");

  useEffect(() => {
    setGraph(null); setError(null);
    fetchMetagraph(retroApiBase, apps).then((r) => { if (r.error) setError(r.error); else setGraph(r); });
  }, [retroApiBase, (apps || []).join(",")]); // eslint-disable-line react-hooks/exhaustive-deps

  const layout = useMemo(() => layoutGraph(graph), [graph]);
  const inventory = useMemo(() => fieldInventory(graph), [graph]);
  const node = graph?.nodes.find((n) => n.id === selected) || null;
  const nodeEdges = graph ? graph.edges.filter((e) => e.from === selected || e.to === selected) : [];

  if (error) return <p style={{ color: "var(--danger)" }}>⚠️ {error}</p>;
  if (!graph) return <p className="muted">Méta-relevé…</p>;

  const rows = inventory.filter((r) => !filter || `${r.app} ${r.table} ${r.column} ${r.term} ${r.type || ""}`.toLowerCase().includes(filter.toLowerCase()));

  return (
    <div>
      <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap", marginBottom: 8 }}>
        <span className="muted">{graphSummary(graph)}</span>
        <span style={{ flex: 1 }} />
        <button className={mode === "graph" ? "" : "secondary"} onClick={() => setMode("graph")}>Graphe</button>
        <button className={mode === "fields" ? "" : "secondary"} onClick={() => setMode("fields")}>Relevé des champs</button>
        <button className={mode === "proposal" ? "" : "secondary"} onClick={() => setMode("proposal")}>Proposition de fusion</button>
      </div>
      <p className="muted" style={{ fontSize: 12, margin: "0 0 8px" }}>
        Sources : {Object.entries(graph.inputs || {}).map(([a, i]) => `${a} (${i.scan ? "code analysé" : "code non analysé"}, ${i.queries} requête(s) SQL, ${i.typed_columns} table(s) typée(s) via dba-api)`).join(" · ")}
      </p>

      {mode === "graph" && (
        <div style={{ display: "grid", gridTemplateColumns: node ? "1fr 300px" : "1fr", gap: 12 }}>
          <div className="hub-table-scroll" style={{ border: "1px solid var(--border)", borderRadius: 8, background: "var(--panel)" }}>
            <svg width={layout.width} height={layout.height} style={{ display: "block", fontFamily: "inherit" }}>
              {layout.columns.map((c) => <text key={c.app} x={c.x} y={22} fontSize={14} fontWeight={600} fill="currentColor">{c.app}</text>)}
              {graph.edges.map((e, i) => {
                const d = edgePath(layout, e);
                if (!d) return null;
                const st = EDGE_STYLES[e.kind] || EDGE_STYLES.fk;
                const m = edgeMidpoint(layout, e);
                const dim = selected && e.from !== selected && e.to !== selected;
                return (
                  <g key={i} opacity={dim ? 0.25 : 1}>
                    <path d={d} fill="none" stroke={st.stroke} strokeWidth={e.kind === "equiv" ? 2 : 1.5} strokeDasharray={st.dash || undefined}>
                      <title>{`${e.kind} · ${e.from} → ${e.to}\n${(e.sources || []).join(", ")}\n${(e.columns || []).map((p) => `${p[0]} ↔ ${p[1]}`).join("\n")}`}</title>
                    </path>
                    {m && edgeLabel(e) && <text x={m.x} y={m.y - 4} fontSize={10} textAnchor="middle" fill={st.stroke}>{edgeLabel(e)}</text>}
                  </g>
                );
              })}
              {graph.nodes.map((n) => {
                const p = layout.nodes[n.id];
                const cols = n.columns.slice(0, MAX_ROWS);
                const isSel = n.id === selected;
                return (
                  <g key={n.id} transform={`translate(${p.x},${p.y})`} style={{ cursor: "pointer" }} onClick={() => setSelected(isSel ? null : n.id)}>
                    <rect width={p.w} height={p.h} rx={6} fill="var(--panel)" stroke={isSel ? "var(--accent, #2b5797)" : "var(--border)"} strokeWidth={isSel ? 2 : 1} />
                    <rect width={p.w} height={HEAD_H} rx={6} fill={isSel ? "var(--accent, #2b5797)" : "var(--border)"} opacity={isSel ? 1 : 0.5} />
                    <text x={8} y={17} fontSize={12} fontWeight={600} fill="currentColor">{n.table}{n.in_code ? "" : " ·"}</text>
                    {cols.map((c, i) => (
                      <text key={c.name} x={10} y={HEAD_H + 12 + i * ROW_H} fontSize={11} fill="currentColor" opacity={c.pk ? 1 : 0.85}>
                        {c.pk ? "🔑 " : ""}{c.name}{c.type ? <tspan opacity={0.55}> {c.type}</tspan> : null}
                      </text>
                    ))}
                    {n.columns.length > MAX_ROWS && <text x={10} y={HEAD_H + 12 + MAX_ROWS * ROW_H} fontSize={11} fill="currentColor" opacity={0.6}>… {n.columns.length - MAX_ROWS} de plus</text>}
                  </g>
                );
              })}
            </svg>
            <div className="muted" style={{ fontSize: 12, padding: "4px 8px", display: "flex", gap: 16, flexWrap: "wrap" }}>
              {Object.entries(EDGE_STYLES).map(([k, st]) => <span key={k}><svg width={28} height={8}><line x1={0} y1={4} x2={28} y2={4} stroke={st.stroke} strokeWidth={2} strokeDasharray={st.dash || undefined} /></svg> {st.label}</span>)}
              <span>« · » après un nom : table absente du code analysé</span>
            </div>
          </div>
          {node && (
            <div className="hub-card hub-settings-section" style={{ padding: 12 }}>
              <h3 style={{ margin: "0 0 4px" }}>{node.app} · {node.table}</h3>
              <p className="muted" style={{ fontSize: 12, margin: "0 0 6px" }}>{node.columns.length} attribut(s) · écrans : {node.screens.length ? node.screens.map((s) => s.title || s.id).join(", ") : "aucun"}</p>
              <div className="hub-table-scroll">
                <table>
                  <thead><tr><th>Attribut</th><th>Type</th><th>Écrans</th></tr></thead>
                  <tbody>{node.columns.map((c) => <tr key={c.name}><td>{c.pk ? "🔑 " : ""}{c.name}<div className="muted" style={{ fontSize: 11 }}>{c.term !== c.name ? c.term : ""}</div></td><td className="muted">{c.type || "?"}</td><td className="muted" style={{ fontSize: 11 }}>{(c.screens || []).join(", ")}</td></tr>)}</tbody>
                </table>
              </div>
              {nodeEdges.length > 0 && (
                <>
                  <h4 style={{ margin: "8px 0 4px" }}>Relations</h4>
                  {nodeEdges.map((e, i) => (
                    <p key={i} style={{ fontSize: 12, margin: "0 0 4px" }}>
                      <span className="na-chip">{e.kind}</span> {e.from === node.id ? `→ ${e.to}` : `← ${e.from}`}<br />
                      <span className="muted">{(e.sources || []).join(", ")} · {(e.columns || []).map((p) => `${p[0]} ↔ ${p[1]}`).join(", ")}</span>
                    </p>
                  ))}
                </>
              )}
            </div>
          )}
        </div>
      )}

      {mode === "fields" && (
        <>
          <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 6 }}>
            <input placeholder="filtrer (application, table, colonne, terme, type)…" value={filter} onChange={(e) => setFilter(e.target.value)} style={{ maxWidth: 360 }} />
            <span className="muted">{rows.length} attribut(s)</span>
          </div>
          <div className="hub-table-scroll">
            <table>
              <thead><tr><th>Application</th><th>Table</th><th>Colonne</th><th>Type</th><th>Terme</th><th>Écrans</th><th>Équivalents</th></tr></thead>
              <tbody>{rows.map((r, i) => (
                <tr key={i}>
                  <td>{r.app}</td><td>{r.table}</td><td>{r.pk ? "🔑 " : ""}{r.column}</td><td className="muted">{r.type || "?"}</td>
                  <td className="muted">{r.term}</td><td className="muted" style={{ fontSize: 12 }}>{r.screens.join(", ")}</td>
                  <td style={{ fontSize: 12 }}>{r.equivalents.length ? r.equivalents.map((x) => <code key={x} style={{ marginRight: 6 }}>{x}</code>) : <span className="muted">—</span>}</td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        </>
      )}

      {mode === "proposal" && graph.proposal && (
        <div>
          <p className="muted" style={{ fontSize: 12 }}>{proposalSummary(graph.proposal)}. Une entité cible par groupe d'entités équivalentes ; attributs = union, avec la colonne de chaque application ; les entités propres à une application sont reprises telles quelles. C'est une proposition à arbitrer, chaque ligne dit d'où elle vient.</p>
          {graph.proposal.entities.map((e) => (
            <div key={e.name} className="hub-card hub-settings-section" style={{ margin: "0 0 8px", padding: 12 }}>
              <h3 style={{ margin: "0 0 4px" }}>{e.name} <span className="muted" style={{ fontWeight: 400, fontSize: 12 }}>← {e.members.map((m) => `${m.app}.${m.table}`).join(" + ")}</span>
                {e.apps.length > 1 ? <span className="na-chip" style={{ marginLeft: 6 }}>fusion</span> : <span className="na-chip" style={{ marginLeft: 6 }}>reprise</span>}</h3>
              {e.todo?.length > 0 && <p style={{ color: "var(--warning, #b7791f)", fontSize: 12, margin: "0 0 4px" }}>{e.todo.join(" ; ")}</p>}
              <div className="hub-table-scroll">
                <table>
                  <thead><tr><th>Attribut cible</th>{e.apps.map((a) => <th key={a}>{a}</th>)}<th>Remarque</th></tr></thead>
                  <tbody>{e.attributes.map((a) => (
                    <tr key={a.name} style={a.orphan ? { opacity: 0.8 } : undefined}>
                      <td>{a.pk ? "🔑 " : ""}{a.name}</td>
                      {e.apps.map((ap) => <td key={ap} style={{ fontSize: 12 }}>{a.columns[ap] ? <code>{a.columns[ap].column}{a.columns[ap].type ? ` ${a.columns[ap].type}` : ""}</code> : <span className="muted">—</span>}</td>)}
                      <td className="muted" style={{ fontSize: 12 }}>
                        {a.type_conflict ? <span style={{ color: "var(--warning, #b7791f)" }}>types différents : {a.type_conflict.join(" / ")}</span> : a.orphan ? `propre à ${Object.keys(a.columns).join(", ")}` : a.shared ? "commun" : ""}
                      </td>
                    </tr>
                  ))}</tbody>
                </table>
              </div>
            </div>
          ))}
          {graph.proposal.relations.length > 0 && (
            <div className="hub-card hub-settings-section" style={{ padding: 12 }}>
              <h3 style={{ margin: "0 0 4px" }}>Relations entre entités cibles</h3>
              <div className="hub-table-scroll">
                <table>
                  <thead><tr><th>De</th><th>Vers</th><th>Genre</th><th>Sources</th><th>Via</th></tr></thead>
                  <tbody>{graph.proposal.relations.map((r, i) => (
                    <tr key={i}><td>{r.from}</td><td>{r.to}</td><td><span className="na-chip">{r.kind}</span></td><td className="muted" style={{ fontSize: 12 }}>{r.sources.join(", ")}</td>
                      <td className="muted" style={{ fontSize: 12 }}>{r.via.map((v) => `${v.from} → ${v.to} (${(v.columns || []).map((p) => `${p[0]} ↔ ${p[1]}`).join(", ")})`).join(" ; ")}</td></tr>
                  ))}</tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
