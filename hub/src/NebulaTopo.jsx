// Synoptique du réseau Nebula (livraison #553) : carte SVG, nœuds et
// liaisons cliquables, filtre par VLAN. Données : /vlan-map (#548) et les
// états de /health-board (#546). La logique (graphe, niveaux, positions)
// est dans nebulaTopo.js.
import { useEffect, useMemo, useState } from "react";
import { buildGraph, layout, edgeCarries, nodeSummary, KIND_LABEL } from "./nebulaTopo.js";

async function getJson(url) {
  const r = await fetch(url, { credentials: "include" });
  const j = await r.json();
  if (!r.ok) throw new Error(j.error || `${r.status}`);
  return j;
}

const NODE_W = 150, NODE_H = 46;
const STATUS_COLOR = { online: "#2e7d32", offline: "#c62828", alerting: "#ef6c00", inconnu: "#9e9e9e" };
const KIND_GLYPH = { gateway: "⛨", switch: "▤", ap: "((•))", other: "▣", unknown: "?" };

export default function NebulaTopo({ nebulaApiBase, siteId, vmap: given }) {
  const [vmap, setVmap] = useState(given || null);
  const [statuses, setStatuses] = useState({});
  const [error, setError] = useState(null);
  const [selected, setSelected] = useState(null); // {type: "node"|"edge", id}
  const [vlanFilter, setVlanFilter] = useState("");

  useEffect(() => {
    if (!siteId) return;
    let alive = true;
    (async () => {
      try {
        const [m, h] = await Promise.all([given ? Promise.resolve(given) : getJson(`${nebulaApiBase}/sites/${encodeURIComponent(siteId)}/vlan-map`), getJson(`${nebulaApiBase}/sites/${encodeURIComponent(siteId)}/health-board?hours=1`).catch(() => null)]);
        if (!alive) return;
        setVmap(m);
        if (h) setStatuses(Object.fromEntries((h.devices || []).map((d) => [d.name, d.status])));
      } catch (e) { if (alive) setError(e.message); }
    })();
    return () => { alive = false; };
  }, [nebulaApiBase, siteId, given]);

  const graph = useMemo(() => (vmap ? buildGraph(vmap, statuses) : null), [vmap, statuses]);
  const lay = useMemo(() => (graph ? layout(graph, 1000, 130, NODE_W) : null), [graph]);
  if (error) return <p style={{ color: "var(--danger)" }}>{error}</p>;
  if (!graph || !lay) return <p className="muted">Chargement du synoptique…</p>;

  const vid = vlanFilter ? Number(vlanFilter) : null;
  const pos = (id) => lay.positions.get(id);
  const nodeOn = (n) => !vid || nodeSummary(n, vmap).vlans.some((v) => v.vid === vid) || nodeSummary(n, vmap).ssids.some((s) => s.vid === vid) || graph.edges.some((e) => (e.a === n.id || e.b === n.id) && edgeCarries(e, vid));
  const sel = selected ? (selected.type === "node" ? graph.nodes.find((n) => n.id === selected.id) : graph.edges.find((e) => e.id === selected.id)) : null;

  return (
    <div>
      <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap", marginBottom: 8 }}>
        <span className="muted">Mettre en évidence un VLAN :</span>
        <select value={vlanFilter} onChange={(e) => setVlanFilter(e.target.value)}>
          <option value="">— tous —</option>
          {(vmap.vlans || []).map((v) => <option key={v.vid} value={v.vid}>{v.vid}{v.ssids?.length ? ` · ${v.ssids.map((s) => s.name).join(", ")}` : ""}{v.subnet ? ` · ${v.subnet}` : ""}</option>)}
        </select>
        <span className="muted">Liaison rouge = VLAN manquant d'un côté · pointillé = sans VLAN (agrégat ou inutilisée) · cliquer un nœud ou une liaison.</span>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: sel ? "1fr 340px" : "1fr", gap: 12 }}>
        <div style={{ overflow: "auto", border: "1px solid var(--border)", borderRadius: 8, background: "var(--panel)" }}>
          <svg viewBox={`0 0 ${lay.width} ${lay.height}`} width={lay.width} height={lay.height} style={{ display: "block" }} fontFamily="system-ui, sans-serif">
            {graph.edges.map((e) => {
              const a = pos(e.a), b = pos(e.b); if (!a || !b) return null;
              const on = !vid || edgeCarries(e, vid);
              const color = e.tone === "bad" ? "#c62828" : e.tone === "muted" ? "#9e9e9e" : vid && on ? "#1565c0" : "#607d8b";
              const active = selected?.type === "edge" && selected.id === e.id;
              const mx = (a.x + b.x) / 2, my = (a.y + b.y) / 2;
              return (
                <g key={e.id} style={{ cursor: "pointer" }} onClick={() => setSelected({ type: "edge", id: e.id })} opacity={on ? 1 : 0.15}>
                  <line x1={a.x} y1={a.y} x2={b.x} y2={b.y} stroke={color} strokeWidth={active ? 5 : e.tone === "bad" ? 3 : 2} strokeDasharray={e.tone === "muted" ? "6 5" : undefined} />
                  <line x1={a.x} y1={a.y} x2={b.x} y2={b.y} stroke="transparent" strokeWidth={14} />
                  <text x={mx} y={my - 4} fontSize="10" fill={color} textAnchor="middle">{e.a_port != null ? `${e.a_port} ↔ ${e.b_port ?? "?"}` : ""}</text>
                </g>
              );
            })}
            {graph.nodes.map((n) => {
              const p = pos(n.id); if (!p) return null;
              const on = nodeOn(n);
              const active = selected?.type === "node" && selected.id === n.id;
              return (
                <g key={n.id} transform={`translate(${p.x - NODE_W / 2},${p.y - NODE_H / 2})`} style={{ cursor: "pointer" }} onClick={() => setSelected({ type: "node", id: n.id })} opacity={on ? 1 : 0.25}>
                  <rect width={NODE_W} height={NODE_H} rx={8} fill="var(--bg)" stroke={active ? "#1565c0" : STATUS_COLOR[n.status] || "#9e9e9e"} strokeWidth={active ? 3 : 2} />
                  <circle cx={14} cy={14} r={5} fill={STATUS_COLOR[n.status] || "#9e9e9e"} />
                  <text x={24} y={18} fontSize="11" fill="var(--text)" fontWeight="600">{n.name.length > 20 ? n.name.slice(0, 19) + "…" : n.name}</text>
                  <text x={24} y={34} fontSize="10" fill="var(--muted)">{KIND_GLYPH[n.kind]} {n.model || KIND_LABEL[n.kind]}</text>
                </g>
              );
            })}
          </svg>
        </div>
        {sel && (
          <div className="hub-card" style={{ margin: 0 }}>
            <div style={{ display: "flex", justifyContent: "space-between" }}><strong>{selected.type === "node" ? sel.name : "Liaison"}</strong><button type="button" className="secondary" onClick={() => setSelected(null)}>✕</button></div>
            {selected.type === "node" ? (() => {
              const s = nodeSummary(sel, vmap);
              return (
                <div>
                  <p className="muted" style={{ margin: "4px 0" }}>{KIND_LABEL[sel.kind]} · {sel.model || "—"} · état : {sel.status}</p>
                  {s.vlans.length > 0 && sel.kind === "switch" && (
                    <table><thead><tr><th>VLAN</th><th>Non étiqueté</th><th>Étiqueté</th><th>SSID</th></tr></thead>
                      <tbody>{s.vlans.map((v) => <tr key={v.vid}><td><strong>{v.vid}</strong>{v.subnet && <div className="muted" style={{ fontSize: 11 }}>{v.subnet}</div>}</td><td>{v.untagged.join(" ") || "—"}</td><td>{v.tagged.join(" ") || "—"}</td><td>{v.ssids.join(", ")}</td></tr>)}</tbody></table>
                  )}
                  {sel.kind === "gateway" && s.vlans.length > 0 && <ul>{s.vlans.map((v) => <li key={v.vid}>VLAN {v.vid} · {v.iface} · {v.subnet || "adresse non publiée"}{v.guest ? " · invités" : ""}</li>)}</ul>}
                  {sel.kind === "ap" && <ul>{s.ssids.map((x) => <li key={x.name} style={{ opacity: x.enabled ? 1 : 0.5 }}>{x.name} → VLAN {x.vid}{x.enabled ? "" : " (désactivé)"}</li>)}</ul>}
                  <p className="muted" style={{ fontSize: 12 }}>Liaisons : {graph.edges.filter((e) => e.a === sel.id || e.b === sel.id).map((e) => { const o = e.a === sel.id ? e.b : e.a; const on = graph.nodes.find((n) => n.id === o); return `${on?.name || o} (port ${e.a === sel.id ? e.a_port : e.b_port})`; }).join(" · ") || "aucune"}</p>
                </div>
              );
            })() : (() => {
              const na = graph.nodes.find((n) => n.id === sel.a), nb = graph.nodes.find((n) => n.id === sel.b);
              return (
                <div>
                  <p style={{ margin: "4px 0" }}>{na?.name} port {sel.a_port} ↔ {nb?.name} port {sel.b_port ?? "?"}</p>
                  {sel.bare ? <p className="muted">Aucun VLAN déclaré des deux côtés : membre d'un agrégat LACP, ou lien inutilisé.</p> : sel.external ? <p className="muted">Voisin LLDP (borne, passerelle ou équipement hors commutateurs) : VLAN lus sur le port du commutateur seulement.</p> : (
                    <div>
                      <div>Côté {na?.name} : {Array.isArray(sel.a_vlans) ? sel.a_vlans.join(" ") : sel.a_vlans}</div>
                      <div>Côté {nb?.name} : {Array.isArray(sel.b_vlans) ? sel.b_vlans.join(" ") : sel.b_vlans}</div>
                      {sel.missing_on_a.length > 0 && <div style={{ color: "var(--danger)" }}>Manquants côté {na?.name} : {sel.missing_on_a.join(" ")}</div>}
                      {sel.missing_on_b.length > 0 && <div style={{ color: "var(--danger)" }}>Manquants côté {nb?.name} : {sel.missing_on_b.join(" ")}</div>}
                    </div>
                  )}
                </div>
              );
            })()}
          </div>
        )}
      </div>
    </div>
  );
}
