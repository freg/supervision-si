// Carte des redirections NAT (livraison #606) -- demandé : « un outil de
// visualisation des redirections NAT ». Tous les routeurs MikroTik du
// registre : schéma entrée (Internet, port) → routeur → cible (hôte:port du
// LAN), cibles nommées par les agents hôtes quand l'adresse est connue,
// conflits de port (règle jamais atteinte), règles désactivées, sortants
// (masquerade / src-nat) à part, filtre début de mot, activer / désactiver
// une règle sur place, lien vers la tuile MikroTik pour le reste.
import { useCallback, useEffect, useMemo, useState } from "react";
import PageFrame from "./PageFrame.jsx";
import { fetchNatMap, setNatRule } from "./mikrotikClient.js";
import { fetchFleet } from "./siAgentClient.js";
import { rankFilter } from "./textFilter.js";

const C = { red: "#e53935", orange: "#fb8c00", green: "#43a047", grey: "#9e9e9e", accent: "#4a9eda" };
const flowText = (f) => [f.router, f.proto, f.dst_address, f.dst_ports.join(","), f.to_address, f.to_ports.join(","), f.comment, f.in_iface, f.action].join(" ");

export default function NatMapView({ apiBase, siAgentApiBase, mikrotikUrl, onBack }) {
  const [map, setMap] = useState(null);
  const [err, setErr] = useState("");
  const [names, setNames] = useState({});
  const [query, setQuery] = useState("");
  const [showDisabled, setShowDisabled] = useState(true);
  const [busy, setBusy] = useState("");
  const [notice, setNotice] = useState(null);
  const load = useCallback(async () => {
    setBusy("lecture des routeurs…");
    const r = await fetchNatMap(apiBase);
    setBusy("");
    if (r.error) { setErr(r.error); return; }
    setMap(r);
    if (siAgentApiBase) {
      const agents = await fetchFleet(siAgentApiBase);
      const n = {};
      for (const a of agents) for (const ip of [a.last_ip, ...(a.ips || [])]) if (ip) n[ip] = a.hostname || a.label || a.agent_id;
      setNames(n);
    }
  }, [apiBase, siAgentApiBase]);
  useEffect(() => { load(); }, [load]);
  const flows = useMemo(() => rankFilter((map?.flows || []).filter((f) => showDisabled || !f.disabled), query, flowText), [map, query, showDisabled]);
  const inbound = flows.filter((f) => f.kind === "inbound");
  const outbound = flows.filter((f) => f.kind !== "inbound");
  const conflictIds = useMemo(() => new Set((map?.conflicts || []).flatMap((c) => c.rules.map((id) => `${c.router}:${id}`))), [map]);
  const toggle = async (f) => {
    const r = await setNatRule(apiBase, f.router, f.id, { disabled: f.disabled ? "no" : "yes" });
    setNotice({ ok: !r.error, text: r.error || `${f.router} : règle ${f.disabled ? "activée" : "désactivée"} (${f.proto} ${f.dst_ports.join(",")} → ${f.to_address}:${f.to_ports.join(",")})` });
    load();
  };
  if (!apiBase) return <PageFrame title="Redirections NAT" onBack={onBack}><p className="muted">mikrotik-api non configurée (<code>VITE_MIKROTIK_URL</code>).</p></PageFrame>;

  // --- schéma : colonnes Internet | routeurs | cibles, une ligne par flux entrant
  const routers = map?.routers || [];
  const targets = useMemo(() => {
    const by = new Map();
    for (const f of inbound) { const k = f.to_address || "?"; if (!by.has(k)) by.set(k, []); by.get(k).push(f); }
    return [...by.entries()];
  }, [inbound]);
  const ROW = 26, W = 980, X0 = 20, X1 = 380, X2 = 700, TOP = 30;
  const rowsY = {}; let y = TOP;
  const routerY = {}; routers.forEach((r) => { routerY[r.name] = y; y += Math.max(ROW * 2, ROW * inbound.filter((f) => f.router === r.name).length); });
  const routerRows = y;
  y = TOP; const targetY = {}; targets.forEach(([addr, fl]) => { targetY[addr] = y; y += ROW * Math.max(1, fl.length) + 30; });
  const H = Math.max(routerRows, y, 120) + 20;
  // y de chaque flux : côté routeur (empilé sous le routeur) et côté cible (empilé sous la cible)
  const rIdx = {}, tIdx = {};
  inbound.forEach((f) => {
    rIdx[f.router] = (rIdx[f.router] || 0); tIdx[f.to_address] = (tIdx[f.to_address] || 0);
    rowsY[`${f.router}:${f.id}`] = { yr: routerY[f.router] + ROW * rIdx[f.router] + 14, yt: targetY[f.to_address] + 24 + ROW * tIdx[f.to_address] + 8 };
    rIdx[f.router] += 1; tIdx[f.to_address] += 1;
  });
  return (
    <PageFrame title="Redirections NAT" onBack={onBack}
      actions={<>
        <input type="search" placeholder="filtrer (port, adresse, routeur, commentaire)" value={query} onChange={(e) => setQuery(e.target.value)} style={{ minWidth: 280 }} />
        <label style={{ display: "flex", gap: 4, alignItems: "center" }}><input type="checkbox" checked={showDisabled} onChange={(e) => setShowDisabled(e.target.checked)} /> désactivées</label>
        <button type="button" className="secondary" onClick={load} disabled={!!busy}>{busy ? `⏳ ${busy}` : "↻ relire"}</button>
        {mikrotikUrl && <a href={mikrotikUrl} target="_blank" rel="noopener noreferrer">tuile MikroTik ↗</a>}
      </>}
      foot={<span>{map ? `${map.counts.inbound} redirection(s) entrante(s) · ${map.counts.outbound} sortante(s) · ${map.counts.disabled} désactivée(s) · ${map.counts.targets} cible(s)` : "…"}{map?.counts?.conflicts ? <> · <span style={{ color: C.red, fontWeight: 600 }}>{map.counts.conflicts} conflit(s) de port</span></> : null}{notice ? <> · <span style={{ color: notice.ok ? C.green : C.red }}>{notice.text}</span></> : null}</span>}>
      {err && <p style={{ color: C.red }}>{err}</p>}
      {map?.registry_error && <p style={{ color: C.orange }}>{map.registry_error}</p>}
      {routers.some((r) => !r.reachable) && <p className="muted">Injoignable : {routers.filter((r) => !r.reachable).map((r) => `${r.name} (${r.error || "?"})`).join(" · ")}</p>}
      {map?.conflicts?.length > 0 && (
        <div className="hub-card lic-card" style={{ marginBottom: 10, borderColor: C.red }}>
          <b style={{ color: C.red }}>Conflits</b> — deux règles actives sur le même port d'entrée : seule la première est atteinte.
          <ul style={{ margin: "4px 0 0", paddingLeft: 18 }}>{map.conflicts.map((c, i) => <li key={i}><b>{c.router}</b> {c.key} : règles {c.rules.join(", ")}</li>)}</ul>
        </div>
      )}
      <div style={{ overflow: "auto", border: "1px solid var(--border)", borderRadius: 8, marginBottom: 10 }}>
        <svg width={W} height={H} style={{ display: "block", fontFamily: "inherit", fontSize: 12 }}>
          <text x={X0} y={16} fill="currentColor" fontWeight="700">Internet / entrée</text>
          <text x={X1} y={16} fill="currentColor" fontWeight="700">Routeur</text>
          <text x={X2} y={16} fill="currentColor" fontWeight="700">Cible (LAN)</text>
          {routers.map((r) => (
            <g key={r.name}>
              <rect x={X1 - 10} y={routerY[r.name] - 4} width={230} height={Math.max(ROW * 2, ROW * inbound.filter((f) => f.router === r.name).length) - 4} rx={8} fill="none" stroke={r.reachable ? C.accent : C.red} strokeWidth={1.5} />
              <text x={X1} y={routerY[r.name] + 10} fill="currentColor" fontWeight="700">{r.name}</text>
              <text x={X1} y={routerY[r.name] + 24} fill={C.grey}>{r.host}{r.site ? ` · ${r.site}` : ""}{!r.reachable ? " · injoignable" : ""}</text>
            </g>
          ))}
          {targets.map(([addr, fl]) => (
            <g key={addr}>
              <rect x={X2 - 10} y={targetY[addr] - 4} width={270} height={ROW * Math.max(1, fl.length) + 26} rx={8} fill="none" stroke="var(--border)" />
              <text x={X2 + 265 - 5} y={targetY[addr] + 10} fill="currentColor" fontWeight="700" textAnchor="end">{names[addr] ? `${names[addr]} (${addr})` : addr}</text>
            </g>
          ))}
          {inbound.map((f) => {
            const p = rowsY[`${f.router}:${f.id}`];
            const bad = conflictIds.has(`${f.router}:${f.id}`);
            const col = f.disabled ? C.grey : bad ? C.red : f.invalid ? C.orange : C.green;
            return (
              <g key={`${f.router}:${f.id}`} opacity={f.disabled ? 0.5 : 1}>
                <text x={X0} y={p.yr + 4} fill="currentColor">{f.proto} {f.dst_address || "*"}:{f.dst_ports.join(",")}{f.in_iface ? ` (${f.in_iface})` : ""}</text>
                <line x1={X0 + 190} y1={p.yr} x2={X1 - 12} y2={p.yr} stroke={col} strokeWidth={2} strokeDasharray={f.disabled ? "4 4" : undefined} />
                <path d={`M ${X1 + 222} ${p.yr} C ${X1 + 280} ${p.yr}, ${X2 - 70} ${p.yt}, ${X2 - 12} ${p.yt}`} fill="none" stroke={col} strokeWidth={2} strokeDasharray={f.disabled ? "4 4" : undefined} />
                <text x={X2} y={p.yt + 4} fill="currentColor" fontSize={11}>:{f.to_ports.join(",")}{f.comment ? ` — ${f.comment}` : ""}</text>
              </g>
            );
          })}
          {!inbound.length && map && <text x={X0} y={60} fill={C.grey}>aucune redirection entrante{query ? ` pour « ${query} »` : ""}.</text>}
        </svg>
      </div>
      <div style={{ maxHeight: "calc(100vh - 520px)", overflow: "auto", border: "1px solid var(--border)", borderRadius: 8 }}>
        <table style={{ width: "100%", fontSize: 13 }}>
          <thead style={{ position: "sticky", top: 0, background: "var(--panel)", zIndex: 1 }}><tr><th> </th><th>Routeur</th><th>Chaîne / action</th><th>Entrée</th><th>Cible</th><th>Commentaire</th><th>Paquets</th><th> </th></tr></thead>
          <tbody>
            {[...inbound, ...outbound].map((f) => {
              const bad = conflictIds.has(`${f.router}:${f.id}`);
              return (
                <tr key={`${f.router}:${f.id}`} style={{ opacity: f.disabled ? 0.55 : 1 }}>
                  <td><span style={{ display: "inline-block", width: 10, height: 10, borderRadius: 5, background: f.disabled ? C.grey : bad ? C.red : f.kind === "inbound" ? C.green : C.accent }} title={bad ? "conflit de port" : f.disabled ? "désactivée" : f.kind} /></td>
                  <td>{f.router}</td><td className="muted">{f.chain} / {f.action}</td>
                  <td>{f.kind === "inbound" ? `${f.proto} ${f.dst_address || "*"}:${f.dst_ports.join(",")}${f.in_iface ? ` (${f.in_iface})` : ""}` : `${f.src_address || "*"}${f.out_iface ? ` → ${f.out_iface}` : ""}`}</td>
                  <td>{f.kind === "inbound" ? <>{names[f.to_address] ? <b>{names[f.to_address]}</b> : null} {f.to_address}:{f.to_ports.join(",")}</> : f.to_address || "masquerade"}</td>
                  <td className="muted">{f.comment}</td><td className="muted">{f.packets ?? ""}</td>
                  <td>{f.id && <button type="button" className="secondary" style={{ fontSize: 11 }} onClick={() => toggle(f)}>{f.disabled ? "activer" : "désactiver"}</button>}</td>
                </tr>
              );
            })}
            {map && !flows.length && <tr><td colSpan={8} className="muted">aucune règle.</td></tr>}
          </tbody>
        </table>
      </div>
    </PageFrame>
  );
}
