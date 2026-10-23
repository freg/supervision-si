// Synoptique du réseau Nebula en ARBRE façon Nebula (livraison #555, remplace
// le graphe par niveaux de #553) : passerelle en haut, cœur, commutateurs
// d'accès et bornes, puis les clients sous chaque appareil (pastille
// « n clients » dépliable). Données : /sites/<id>/topology. Nœuds et liaisons
// cliquables ; la logique (arbre, positions) est dans nebulaTree.js.
import { useEffect, useMemo, useState } from "react";
import { treeLayout, treeEdges, treeSummary, KIND_LABEL, apPortAudit, TONS, tonAppareil, tonClient, comptesSousArbre, tonDominant, normMac } from "./nebulaTree.js";

import { AutoColumns } from "./TableColumns.jsx";   // #707 : colonnes réglables
async function getJson(url) {
  const r = await fetch(url, { credentials: "include" });
  const j = await r.json();
  if (!r.ok) throw new Error(j.error || `${r.status}`);
  return j;
}

const NODE_W = 150, NODE_H = 46, CLIENT_W = 74, CLIENT_H = 30;
export const STATUS_COLOR = { online: "#2e7d32", offline: "#c62828", alerting: "#ef6c00", inconnu: "#9e9e9e" };
const KIND_GLYPH = { gateway: "⛨", switch: "▤", ap: "((•))", other: "▣" };
const EDGE_COLOR = { ok: "#607d8b", bad: "#c62828", muted: "#9e9e9e", unlinked: "#bdbdbd" };

export default function NebulaTopo({ nebulaApiBase, siteId, focus = null, groups = [], login = "" }) {
  // #851 : appareils névralgiques (absents = rouge) ; les autres postes absents restent gris
  const [nev, setNev] = useState({});
  const [raison, setRaison] = useState("");
  const loadNev = () => { if (siteId) getJson(`${nebulaApiBase}/sites/${encodeURIComponent(siteId)}/nevralgiques`).then((d) => setNev(d.nevralgiques || {})).catch(() => {}); };
  useEffect(loadNev, [nebulaApiBase, siteId]);  // eslint-disable-line react-hooks/exhaustive-deps
  const nevSet = useMemo(() => new Set(Object.keys(nev)), [nev]);
  const marquer = async (c, on) => {
    const r = await fetch(`${nebulaApiBase}/sites/${encodeURIComponent(siteId)}/nevralgiques`, { method: "PUT", credentials: "include", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ mac: c.mac, nom: c.name || c.mac, raison, nevralgique: on, user: login, groups }) });
    const d = await r.json().catch(() => ({}));
    if (r.ok) { setNev(d.nevralgiques || {}); setRaison(""); } else alert(d.error || r.status);
  };
  const [tree, setTree] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const [period, setPeriod] = useState("1d");
  const [expanded, setExpanded] = useState(new Set());
  // #566 : mise au point depuis une fiche du campus ({mac} ou {name}) -- déplie
  // l'appareil qui sert le client et le sélectionne
  useEffect(() => {
    if (!tree || !focus) return;
    const macs = (focus.macs || (focus.mac ? [focus.mac] : [])).map((m) => String(m).toLowerCase().replace(/-/g, ":"));
    const nm = (focus.name || "").trim().toLowerCase();
    for (const n of tree.nodes) {
      if (nm && n.name.trim().toLowerCase() === nm) { setSelected({ type: "node", id: n.id }); return; }
      (n.clients || []).forEach((cl, i) => {
        const cm = String(cl.mac || "").toLowerCase().replace(/-/g, ":");
        if ((cm && macs.includes(cm)) || (nm && String(cl.name || "").trim().toLowerCase() === nm)) {
          setExpanded((e) => new Set([...e, n.id]));
          setSelected({ type: "client", id: `${n.id}|${cl.mac || i}`, client: cl, parent: n.id });
        }
      });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tree, focus]);
  const [selected, setSelected] = useState(null); // {type: "node"|"client", id}
  const [orientation, setOrientation] = useState(() => { try { return localStorage.getItem("hub.nebula.topo.orientation") || "horizontal"; } catch { return "horizontal"; } });
  const [stagger, setStagger] = useState(() => { try { return Number(localStorage.getItem("hub.nebula.topo.stagger") || 3); } catch { return 3; } });
  const setOrient = (v) => { setOrientation(v); try { localStorage.setItem("hub.nebula.topo.orientation", v); } catch { /* ignore */ } };
  const setStag = (v) => { setStagger(v); try { localStorage.setItem("hub.nebula.topo.stagger", String(v)); } catch { /* ignore */ } };

  const load = async (refresh) => {
    if (!siteId) return;
    setBusy(true); setError(null);
    try { setTree(await getJson(`${nebulaApiBase}/sites/${encodeURIComponent(siteId)}/topology?period=${period}${refresh ? "&refresh=1" : ""}`)); }
    catch (e) { setError(e.message); }
    finally { setBusy(false); }
  };
  useEffect(() => { load(false); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, [nebulaApiBase, siteId, period]);

  const comptes = useMemo(() => (tree ? comptesSousArbre(tree, nevSet) : new Map()), [tree, nevSet]);
  const lay = useMemo(() => (tree ? treeLayout(tree, { orientation, stagger, nodeHeight: NODE_H, rowHeight: 120, colWidth: 320, clientWidth: CLIENT_W, clientHeight: CLIENT_H, expanded }) : null), [tree, expanded, orientation, stagger]);
  const edges = useMemo(() => (tree ? treeEdges(tree) : []), [tree]);
  if (error) return <p style={{ color: "var(--danger)" }}>{error}</p>;
  if (!tree || !lay) return <p className="muted">Chargement du synoptique…</p>;

  const byId = new Map(tree.nodes.map((n) => [n.id, n]));
  const vertical = lay.orientation === "vertical";
  const anchor = (id, side) => { // point d'attache d'un nœud : bas/haut en vertical, droite/gauche en horizontal
    const p = pos(id); const w = lay.nodeWidth.get(id) || NODE_W;
    if (!p) return null;
    return vertical ? { x: p.x, y: p.y + (side === "out" ? NODE_H / 2 : -NODE_H / 2) } : { x: p.x + (side === "out" ? w / 2 : -w / 2), y: p.y };
  };
  const sum = treeSummary(tree);
  const pos = (id) => lay.positions.get(id);
  const toggle = (id) => setExpanded((s) => { const n = new Set(s); n.has(id) ? n.delete(id) : n.add(id); return n; });
  const selNode = selected?.type === "node" ? byId.get(selected.id) : null;
  const selClient = selected?.type === "client" ? selected.client : null;
  const showPanel = selNode || selClient;

  const clientBox = (key, x, y, c, parentId) => {
    const active = selected?.type === "client" && selected.id === key;
    return (
      <g key={key} transform={`translate(${x - CLIENT_W / 2},${y - CLIENT_H / 2})`} style={{ cursor: "pointer" }} onClick={() => setSelected({ type: "client", id: key, client: c, parent: parentId })}>
        <rect width={CLIENT_W} height={CLIENT_H} rx={6} fill="var(--bg)" stroke={active ? "#1565c0" : TONS[tonClient(c, nevSet)]} strokeWidth={active ? 2.5 : nevSet.has(normMac(c.mac)) ? 2 : 1.2} />
        <circle cx={9} cy={CLIENT_H / 2} r={3.5} fill={TONS[tonClient(c, nevSet)]} />
        <text x={16} y={CLIENT_H / 2 + 4} fontSize="9.5" fill="var(--text)">{nevSet.has(normMac(c.mac)) ? "★" : ""}{String(c.name || c.mac || "?").length > 11 ? String(c.name || c.mac).slice(0, 10) + "…" : (c.name || c.mac)}</text>
        <title>{`${c.name || c.mac} — ${c.status}${nevSet.has(normMac(c.mac)) ? " — névralgique : " + (nev[normMac(c.mac)]?.raison || "") : ""}`}</title>
      </g>
    );
  };

  return (
    <div>
      <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap", marginBottom: 8 }}>
        <span>{sum.gateways} passerelle · {sum.switches} commutateur{sum.switches > 1 ? "s" : ""} · {sum.aps} borne{sum.aps > 1 ? "s" : ""} · {sum.clients} client{sum.clients > 1 ? "s" : ""} ({sum.clientsOnline} en ligne)</span>
        {sum.offline > 0 && <span style={{ color: "var(--danger)" }}>{sum.offline} hors ligne</span>}
        {sum.unlinked > 0 && <span className="muted">{sum.unlinked} sans liaison connue (rattaché{sum.unlinked > 1 ? "s" : ""} à la racine)</span>}
        {sum.loose > 0 && <span className="muted">{sum.loose} client{sum.loose > 1 ? "s" : ""} sans appareil identifié</span>}
        <span className="muted" title="Rouge : appareil réseau hors ligne ou poste névralgique absent · orange : doute · vert : en ligne · gris : poste absent sans importance">
          <span style={{ color: TONS.rouge }}>●</span> panne <span style={{ color: TONS.orange }}>●</span> doute <span style={{ color: TONS.vert }}>●</span> en ligne <span style={{ color: TONS.gris }}>●</span> absent ; ★ névralgique</span>
        <span style={{ flex: 1 }} />
        <label className="muted">Clients vus depuis <select value={period} onChange={(e) => setPeriod(e.target.value)}><option value="2h">2 h</option><option value="1d">1 jour</option><option value="7d">7 jours</option></select></label>
        <button type="button" className="secondary" disabled={busy} onClick={() => load(true)}>{busy ? "Lecture…" : "Relire"}</button>
        <button type="button" className="secondary" onClick={() => setExpanded(expanded.size ? new Set() : new Set(tree.nodes.filter((n) => n.clients?.length).map((n) => n.id)))}>{expanded.size ? "Replier les clients" : "Déplier tous les clients"}</button>
        <label className="muted">Disposition <select value={orientation} onChange={(e) => setOrient(e.target.value)}><option value="vertical">arbre vertical étagé</option><option value="horizontal">arbre horizontal (une ligne par équipement)</option></select></label>
        {orientation === "vertical" && <label className="muted">Étages <select value={stagger} onChange={(e) => setStag(Number(e.target.value))}><option value={1}>1</option><option value={2}>2</option><option value={3}>3</option><option value={4}>4</option></select></label>}
      </div>
      <p className="muted" style={{ margin: "0 0 8px", fontSize: 12 }}>Chaque appareil est relié à celui qui le dessert (voisinage LLDP) : arbre horizontal façon d3 (une ligne par équipement, étiquettes entières) ou vertical étagé. Liaison rouge = VLAN manquant d'un côté · pointillé = agrégat ou lien nu · gris clair = liaison inconnue. Cliquer une pastille « n clients » pour la déplier, un nœud ou un client pour le détail.</p>
      <div style={{ display: "grid", gridTemplateColumns: showPanel ? "1fr 340px" : "1fr", gap: 12 }}>
        <div style={{ overflow: "auto", border: "1px solid var(--border)", borderRadius: 8, background: "var(--panel)", maxHeight: "70vh" }}>
          <svg viewBox={`0 0 ${lay.width} ${lay.height}`} width={lay.width} height={lay.height} style={{ display: "block" }} fontFamily="system-ui, sans-serif">
            {edges.map((e) => {
              const a = pos(e.a), b = pos(e.b); if (!a || !b) return null;
              const color = EDGE_COLOR[e.tone];
              const wa = lay.nodeWidth.get(e.a) || NODE_W, wb = lay.nodeWidth.get(e.b) || NODE_W;
              const d = vertical ? `M${a.x},${a.y + NODE_H / 2} C${a.x},${(a.y + b.y) / 2} ${b.x},${(a.y + b.y) / 2} ${b.x},${b.y - NODE_H / 2}`
                                 : `M${a.x + wa / 2},${a.y} C${(a.x + wa / 2 + b.x - wb / 2) / 2},${a.y} ${(a.x + wa / 2 + b.x - wb / 2) / 2},${b.y} ${b.x - wb / 2},${b.y}`;
              return (
                <g key={e.id}>
                  <path d={d} fill="none" stroke={color} strokeWidth={e.tone === "bad" ? 3 : 2} strokeDasharray={e.tone === "muted" ? "6 5" : e.tone === "unlinked" ? "2 4" : undefined} />
                  {e.a_port != null && (vertical ? <text x={b.x} y={b.y - NODE_H / 2 - 3} fontSize="9" fill={color} textAnchor="middle">{e.a_port} → {e.b_port ?? "?"}</text>
                                                 : <text x={b.x - wb / 2 - 4} y={b.y - 4} fontSize="9" fill={color} textAnchor="end">{e.a_port} → {e.b_port ?? "?"}</text>)}
                </g>
              );
            })}
            {[...lay.groups.entries()].map(([pid, g]) => { const o = anchor(pid, "out"); if (!o) return null; return (
              <g key={`g-${pid}`}>
                <line x1={o.x} y1={o.y} x2={vertical ? g.x : g.x - CLIENT_W / 2} y2={vertical ? g.y - CLIENT_H / 2 : g.y} stroke="#90a4ae" strokeWidth={1.5} strokeDasharray="3 3" />
                <g transform={`translate(${g.x - CLIENT_W / 2},${g.y - CLIENT_H / 2})`} style={{ cursor: "pointer" }} onClick={() => toggle(pid)}>
                  <rect width={CLIENT_W} height={CLIENT_H} rx={15} fill="var(--bg)" stroke="#90a4ae" strokeWidth={1.5} />
                  <text x={CLIENT_W / 2} y={CLIENT_H / 2 + 4} fontSize="10" fill="var(--text)" textAnchor="middle" fontWeight="600">{g.count} client{g.count > 1 ? "s" : ""}</text>
                  {(() => { const cl = byId.get(pid)?.clients || []; const t = { rouge: 0, orange: 0, vert: 0, gris: 0 }; for (const c of cl) t[tonClient(c, nevSet)] += 1; const d = tonDominant(t);
                    return <>{(d === "rouge" || d === "orange") && <circle cx={CLIENT_W - 8} cy={8} r={4} fill={TONS[d]} />}<title>{`${t.vert} en ligne · ${t.rouge} névralgique(s) absent(s) · ${t.orange} douteux · ${t.gris} absent(s) sans importance`}</title></>; })()}
                </g>
              </g>
            ); })}
            {[...lay.clientPositions.entries()].map(([key, cp]) => { const o = anchor(cp.parent, "out"); if (!o) return null; return (
              <g key={`c-${key}`}>
                <line x1={o.x} y1={o.y} x2={vertical ? cp.x : cp.x - CLIENT_W / 2} y2={vertical ? cp.y - CLIENT_H / 2 : cp.y} stroke="#b0bec5" strokeWidth={1} />
                {clientBox(key, cp.x, cp.y, cp.client, cp.parent)}
              </g>
            ); })}
            {tree.nodes.map((n) => {
              const p = pos(n.id); if (!p) return null;
              const w = lay.nodeWidth.get(n.id) || NODE_W;
              const active = selected?.type === "node" && selected.id === n.id;
              return (
                <g key={n.id} transform={`translate(${p.x - w / 2},${p.y - NODE_H / 2})`} style={{ cursor: "pointer" }} onClick={() => setSelected({ type: "node", id: n.id })} opacity={n.unlinked ? 0.7 : 1}>
                  <rect width={w} height={NODE_H} rx={8} fill="var(--bg)" stroke={active ? "#1565c0" : TONS[tonAppareil(n.status)]} strokeWidth={active ? 3 : 2} />
                  <circle cx={14} cy={14} r={5} fill={TONS[tonAppareil(n.status)]} />
                  {(() => { const c = comptes.get(n.id) || { rouge: 0, orange: 0, vert: 0, gris: 0 }; const tot = c.rouge + c.orange + c.vert + c.gris; let x = 3;
                    return <g>
                      {["rouge", "orange", "vert", "gris"].map((k) => { const ww = tot ? (w - 6) * c[k] / tot : 0; const el = ww > 0 ? <rect key={k} x={x} y={NODE_H - 6} width={ww} height={3} fill={TONS[k]} /> : null; x += ww; return el; })}
                      <text x={w - 4} y={-4} fontSize="10" textAnchor="end" fontWeight="700">{c.rouge > 0 && <tspan fill={TONS.rouge}>● {c.rouge}  </tspan>}{c.orange > 0 && <tspan fill={TONS.orange}>● {c.orange}  </tspan>}<tspan fill={TONS.vert}>● {c.vert}</tspan></text>
                      <title>{`${n.name} et en aval : ${c.rouge} en panne (rouge) · ${c.orange} douteux · ${c.vert} en ligne · ${c.gris} absents sans importance`}</title>
                    </g>; })()}
                  <text x={24} y={18} fontSize="11" fill="var(--text)" fontWeight="600">{n.name}</text>
                  <text x={24} y={34} fontSize="10" fill="var(--muted)">{KIND_GLYPH[n.kind]} {n.model || KIND_LABEL[n.kind]}{n.clients?.length ? ` · ${n.clients.length}` : ""}</text>
                </g>
              );
            })}
          </svg>
        </div>
        {showPanel && (
          <div className="hub-card" style={{ margin: 0 }}>
            <div style={{ display: "flex", justifyContent: "space-between" }}><strong>{selNode ? selNode.name : selClient.name || selClient.mac}</strong><button type="button" className="secondary" onClick={() => setSelected(null)}>✕</button></div>
            {selNode ? (
              <div>
                <p className="muted" style={{ margin: "4px 0" }}>{KIND_LABEL[selNode.kind]} · {selNode.model || "—"} · état : {selNode.status}</p>
                {selNode.parent && <p style={{ margin: "4px 0" }}>Relié à <strong>{byId.get(selNode.parent)?.name}</strong> (port {selNode.parent_port ?? "?"}) par son port {selNode.uplink_port ?? "?"}{selNode.unlinked ? " — liaison non observée, rattachement par défaut" : ""}</p>}
                {selNode.link && (selNode.link.missing_on_a?.length || selNode.link.missing_on_b?.length) ? <p style={{ color: "var(--danger)", margin: "4px 0" }}>VLAN manquants : {[...(selNode.link.missing_on_a || []), ...(selNode.link.missing_on_b || [])].join(" ")}</p> : null}
                {selNode.link && Array.isArray(selNode.link.a_vlans) && <p className="muted" style={{ margin: "4px 0", fontSize: 12 }}>VLAN sur le port amont : {selNode.link.a_vlans.join(" ") || "aucun"}</p>}
                <p style={{ margin: "4px 0" }}>Enfants : {tree.nodes.filter((n) => n.parent === selNode.id).map((n) => n.name).join(" · ") || "aucun"}</p>
                {selNode.clients?.length > 0 && (
                  <AutoColumns id="NebulaTopo.1"><table><thead><tr><th>Client</th><th>IP</th><th>VLAN</th><th>État</th></tr></thead>
                    <tbody>{selNode.clients.map((c) => <tr key={c.mac} style={{ cursor: "pointer" }} onClick={() => setSelected({ type: "client", id: `${selNode.id}|${c.mac}`, client: c, parent: selNode.id })}><td>{c.name}</td><td>{c.ip || "—"}</td><td>{c.vlan ?? "—"}</td><td style={{ color: TONS[tonClient(c, nevSet)] }}>{c.status}</td></tr>)}</tbody></table></AutoColumns>
                )}
              </div>
            ) : (
              <div>
                <p className="muted" style={{ margin: "4px 0" }}>{selClient.wired ? "Client filaire" : "Client Wi-Fi"} · état : {selClient.status}</p>
                {nevSet.has(normMac(selClient.mac))
                  ? <p style={{ margin: "4px 0" }}><b style={{ color: TONS.rouge }}>★ névralgique</b>{nev[normMac(selClient.mac)]?.raison ? ` — ${nev[normMac(selClient.mac)].raison}` : ""} <button type="button" className="secondary" onClick={() => marquer(selClient, false)}>retirer</button></p>
                  : selClient.mac && <p style={{ margin: "4px 0" }}><input value={raison} onChange={(e) => setRaison(e.target.value)} placeholder="rôle (ex. pilote 4 écrans interactifs)" size={30} /> <button type="button" className="secondary" onClick={() => marquer(selClient, true)}>Marquer névralgique</button></p>}
                <ul style={{ margin: "4px 0", paddingLeft: 18 }}>
                  <li>Servi par <strong>{byId.get(selected.parent)?.name}</strong>{selClient.port != null ? ` (port ${selClient.port})` : ""}</li>
                  <li>MAC {selClient.mac || "—"} · IP {selClient.ip || "—"} · VLAN {selClient.vlan ?? "—"}</li>
                  {selClient.manufacturer && <li>Fabricant : {selClient.manufacturer}</li>}
                  {selClient.os && <li>Système : {selClient.os}</li>}
                  {selClient.last_seen && <li>Vu : {new Date(Number(selClient.last_seen)).toLocaleString("fr-FR")}</li>}
                </ul>
              </div>
            )}
          </div>
        )}
      </div>
      {tree.loose_clients?.length > 0 && <details style={{ marginTop: 8 }}><summary className="muted">{tree.loose_clients.length} client{tree.loose_clients.length > 1 ? "s" : ""} sans appareil identifié</summary><ul>{tree.loose_clients.map((c) => <li key={c.mac}>{c.name} · {c.ip || "—"} · VLAN {c.vlan ?? "—"}</li>)}</ul></details>}
      {/* #565 : réglage des ports de commutateur qui desservent les bornes (PVID = VLAN de gestion non tagué, allowed = all) */}
      {(() => { const a = apPortAudit(tree); if (!a.rows.length) return null; return (
        <details style={{ marginTop: 4 }} open={a.differing + a.notAll > 0}>
          <summary className="muted">Ports des bornes : {a.rows.length} · PVID attendu {a.expectedPvid ?? "?"}{a.differing ? <span style={{ color: "var(--danger)" }}> · {a.differing} PVID différent{a.differing > 1 ? "s" : ""}</span> : ""}{a.notAll ? <span style={{ color: "var(--danger)" }}> · {a.notAll} sans « all »</span> : " · tous en « all »"}</summary>
          <AutoColumns id="NebulaTopo.2"><table style={{ borderCollapse: "collapse", marginTop: 4 }}>
            <thead><tr><th>Borne</th><th>Commutateur</th><th>Port</th><th>PVID</th><th>VLAN autorisés</th><th></th></tr></thead>
            <tbody>{a.rows.map((r) => <tr key={r.id} style={{ color: r.ok ? undefined : "var(--danger)" }}><td>{r.name}</td><td>{r.switch}</td><td>{r.port ?? "?"}</td><td>{r.pvid ?? "?"}</td><td>{r.all ? "all" : (r.allowed.join(", ") || "—")}</td><td>{r.ok ? "✓" : r.pvid !== a.expectedPvid ? `PVID ≠ ${a.expectedPvid}` : "pas « all »"}</td></tr>)}</tbody>
          </table></AutoColumns>
          <p className="muted" style={{ margin: "4px 0" }}>Lu sur le port du commutateur (Nebula). Le PVID doit être le VLAN de gestion des bornes (celui de leur adresse IP) et identique partout ; « all » laisse passer les VLAN de tous les SSID, présents et futurs.</p>
        </details>); })()}
      {tree.unmatched?.length > 0 && <details style={{ marginTop: 4 }}><summary className="muted">{tree.unmatched.length} voisin{tree.unmatched.length > 1 ? "s" : ""} LLDP hors inventaire Nebula (postes, téléphones, imprimantes… vus sur les ports des commutateurs)</summary><ul>{tree.unmatched.map((u, i) => <li key={i}>{u.switch} port {u.port} → {u.sysname || "?"} ({u.chassis || "?"})</li>)}</ul></details>}
      {tree.errors?.length > 0 && <p className="muted" style={{ fontSize: 12 }}>Appels en échec (arbre partiel) : {tree.errors.join(" · ")}</p>}
    </div>
  );
}
