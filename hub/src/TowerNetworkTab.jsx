import React, { useState, useEffect } from "react";
import { fetchMikrotikRouters, fetchRoutes, fetchNatRules } from "./mikrotikClient.js";
import { fetchCiscoSwitches, fetchCiscoRoutes } from "./ciscoClient.js";
import { fetchSites, fetchLinks } from "./networkAgentClient.js";
import { fetchNetworkObservability } from "./siAgentClient.js";
import { dnsRows, dnsSummary, routingSummary, ciscoRouteRows, topFlows, fmtBytes, resourceRows } from "./towerNetworkLib.js";
import TowerDnsPanel from "./TowerDnsPanel.jsx";

import { AutoColumns } from "./TableColumns.jsx";   // #707 : colonnes réglables
// Tour de contrôle → onglet « Réseau » (#655) : DNS / routage / flux → trafic, en LECTURE SEULE, agrégés depuis les
// modules existants (service-watch, sonde dns-observe, MikroTik, network-agent, sonde resource-access). Chaque panneau
// charge seul et affiche son erreur sans bloquer les autres. Les actions restent dans leurs tuiles (NAT, Cisco…).

async function getJson(url) {
  try { const r = await fetch(url); const d = await r.json(); return d && d.error ? { error: d.error } : d; } catch (e) { return { error: e.message }; }
}

export default function TowerNetworkTab({ serviceWatchUrl, siAgentApiBase, mikrotikApiBase, networkAgentApiBase, dnsApiBase, ciscoApiBase, login }) {
  const [dns, setDns] = useState({ loading: true });
  const [routing, setRouting] = useState({ loading: true });
  const [flows, setFlows] = useState({ loading: true });
  const [segment, setSegment] = useState("");
  const [segments, setSegments] = useState([]);

  useEffect(() => {
    (async () => {
      const [entries, obs] = await Promise.all([serviceWatchUrl ? getJson(`${serviceWatchUrl.replace(/\/+$/, "")}/entries`) : { entries: [] }, siAgentApiBase ? fetchNetworkObservability(siAgentApiBase) : null]);
      const rows = dnsRows(entries?.entries || [], obs?.dns || []);
      setDns({ rows, summary: dnsSummary(rows), error: entries?.error || null, resources: obs?.resources || [] });
    })();
  }, [serviceWatchUrl, siAgentApiBase]);

  useEffect(() => {
    if (!mikrotikApiBase && !ciscoApiBase) { setRouting({ routers: [], error: "MikroTik et Cisco non configurés" }); return; }
    (async () => {
      const routers = mikrotikApiBase ? await fetchMikrotikRouters(mikrotikApiBase) : [];
      const detailed = await Promise.all(routers.map(async (r) => { const [rt, nat] = await Promise.all([fetchRoutes(mikrotikApiBase, r.name), fetchNatRules(mikrotikApiBase, r.name)]); return { name: r.name, kind: "mikrotik", host: r.host, routes: rt?.routes || [], error: rt?.error || null, nat: (nat?.rules || []).length, natRules: nat?.rules || [] }; }));
      // #660 : équipements Cisco (routes de niveau 3 : show ip route), lecture seule
      const switches = ciscoApiBase ? await fetchCiscoSwitches(ciscoApiBase) : [];
      const cisco = await Promise.all(switches.map(async (sw) => { const rt = await fetchCiscoRoutes(ciscoApiBase, sw.name); return { name: `${sw.name} (Cisco)`, kind: "cisco", host: sw.host, routes: ciscoRouteRows(rt?.routes), error: rt?.error || null, nat: 0, natRules: [] }; }));
      const all = [...detailed, ...cisco];
      setRouting({ routers: all, summary: routingSummary(all) });
    })();
  }, [mikrotikApiBase, ciscoApiBase]);

  useEffect(() => { if (networkAgentApiBase) fetchSites(networkAgentApiBase).then((s) => { setSegments(s); if (s[0] && !segment) setSegment(String(s[0].id || s[0].segment_id || "")); }); }, [networkAgentApiBase]);  // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (!networkAgentApiBase || !segment) { setFlows({ links: [], error: networkAgentApiBase ? null : "Exploration réseau non configurée" }); return; }
    (async () => { const l = await fetchLinks(networkAgentApiBase, Number(segment)); setFlows({ links: Array.isArray(l) ? l : l?.links || [], error: l?.error || null }); })();
  }, [networkAgentApiBase, segment]);

  return (
    <div className="tn-grid">
      <div className="hub-card tn-card">
        <h3>DNS {dns.summary && <span className="muted">— {dns.summary.total} entrée(s), {dns.summary.ko} en défaut, {dns.summary.alerts} alerte(s)</span>}</h3>
        {dns.error && <p className="tn-ko">{dns.error}</p>}
        {dns.loading ? <p className="muted">chargement…</p> : (
          <AutoColumns id="TowerNetworkTab.1"><table className="tn-table"><thead><tr><th>Nom</th><th>Nature</th><th>Détail</th><th>État</th><th>Vu</th></tr></thead>
            <tbody>{(dns.rows || []).slice(0, 60).map((r, i) => <tr key={i} className={r.state !== "ok" && r.state !== "?" ? "tn-row-ko" : ""}><td><b>{r.name}</b>{r.agent ? <span className="muted"> ({r.agent})</span> : null}</td><td>{r.kind}</td><td className="muted">{r.detail}</td><td>{r.state}</td><td className="muted">{(r.at || "").replace("T", " ").slice(0, 16)}</td></tr>)}
              {(dns.rows || []).length === 0 && <tr><td colSpan={5} className="muted">Aucune entrée : importez une zone dans « Entrées de services » ou activez la sonde dns-observe sur un agent.</td></tr>}</tbody></table></AutoColumns>
        )}
      </div>
      {dnsApiBase && <div className="hub-card tn-card tn-wide"><h3>DNS éditable <span className="muted">— Internet (OVH, Scaleway) avec cache, intranet en fallback</span></h3><TowerDnsPanel dnsApiBase={dnsApiBase} login={login} /></div>}
      <div className="hub-card tn-card">
        <h3>Routage {routing.summary && <span className="muted">— {routing.summary.length} routeur(s)</span>}</h3>
        {routing.error && <p className="tn-ko">{routing.error}</p>}
        {routing.loading ? <p className="muted">chargement…</p> : (routing.summary || []).map((s, i) => (
          <details key={s.router} className="tn-details" open={i === 0}>
            <summary><b>{s.router}</b> — {s.error ? <span className="tn-ko">{s.error}</span> : <>{s.active} route(s) active(s), {s.disabled} désactivée(s), {s.kind === "cisco" ? "" : `${s.nat} règle(s) NAT`} · défaut : {s.defaults.join(", ") || "—"}</>}</summary>
            {!s.error && <AutoColumns id="TowerNetworkTab.2"><table className="tn-table"><thead><tr><th>Destination</th><th>Passerelle</th><th>Dist.</th><th>État</th><th>Commentaire</th></tr></thead>
              <tbody>{routing.routers[i].routes.map((r) => <tr key={r.id} className={r.disabled ? "tn-muted" : !r.active ? "tn-row-ko" : ""}><td>{r.dst}</td><td>{r.gateway}</td><td>{r.distance}</td><td>{r.disabled ? "désactivée" : r.active ? "active" : "inactive"}{r.dynamic ? " (dyn.)" : ""}</td><td className="muted">{r.comment}</td></tr>)}</tbody></table></AutoColumns>}
            {!s.error && routing.routers[i].natRules.length > 0 && <p className="muted">NAT : {routing.routers[i].natRules.slice(0, 12).map((n) => `${n.chain || ""} ${n["dst-port"] || ""}→${n["to-addresses"] || ""}${n["to-ports"] ? ":" + n["to-ports"] : ""}`).join(" · ")}</p>}
          </details>
        ))}
      </div>
      <div className="hub-card tn-card">
        <h3>Flux → trafic</h3>
        {segments.length > 0 && <div className="tn-inline"><label className="muted">Segment</label><select value={segment} onChange={(e) => setSegment(e.target.value)}>{segments.map((s) => <option key={s.id || s.segment_id} value={s.id || s.segment_id}>{s.name || s.label || s.id}</option>)}</select></div>}
        {flows.error && <p className="tn-ko">{flows.error}</p>}
        {flows.loading ? <p className="muted">chargement…</p> : (
          <AutoColumns id="TowerNetworkTab.3"><table className="tn-table"><thead><tr><th>D'où</th><th>Vers où</th><th>Volume</th></tr></thead>
            <tbody>{topFlows(flows.links).map((f, i) => <tr key={i}><td>{f.a}</td><td>{f.b}</td><td>{fmtBytes(f.bytes)}</td></tr>)}
              {(flows.links || []).length === 0 && <tr><td colSpan={3} className="muted">Aucun échange relevé sur ce segment.</td></tr>}</tbody></table></AutoColumns>
        )}
        {dns.resources && dns.resources.length > 0 && (<><h4>Accès aux ressources (sondes)</h4>
          <AutoColumns id="TowerNetworkTab.4"><table className="tn-table"><thead><tr><th>Ressource</th><th>Poste</th><th>Clients</th><th>Accès</th></tr></thead>
            <tbody>{resourceRows(dns.resources).map((r, i) => <tr key={i} className={r.ok ? "" : "tn-row-ko"}><td>{r.name}</td><td className="muted">{r.agent}</td><td>{r.clients}</td><td>{r.hits}</td></tr>)}</tbody></table></AutoColumns></>)}
      </div>
    </div>
  );
}
