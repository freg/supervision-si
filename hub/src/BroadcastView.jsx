// Onglet « Annonces réseau » du volet Campus (livraison #568) : ce que la
// sonde broadcast-probe de l'agent du site a entendu -- protocoles diffusés,
// annonceurs (qui, quoi, à quel rythme), constats (DHCP multiple, RA IPv6,
// conflit ARP, STP, rafales), rapprochés des fiches matériel.
import { useEffect, useMemo, useState } from "react";
import { matchWindowsHosts } from "./campusCards.js";
import { rankFilter } from "./textFilter.js";
import { hubLink } from "./hubLinks.js";

const SEV = { warning: "var(--warning)", critical: "var(--danger)", info: "var(--muted)" };
const PROTO_LABEL = { arp: "ARP", dhcp: "DHCP", "netbios-ns": "NetBIOS (noms)", "netbios-dgm": "NetBIOS (datagrammes)", mdns: "mDNS / Bonjour", ssdp: "SSDP / UPnP", llmnr: "LLMNR", "ws-discovery": "WS-Discovery", lldp: "LLDP", cdp: "CDP", stp: "STP", "icmpv6-ra": "IPv6 annonce routeur", "icmpv6-ns": "IPv6 sollicitation voisin", "icmpv6-na": "IPv6 annonce voisin", mld: "MLD", igmp: "IGMP", anydesk: "AnyDesk", "anydesk-discovery": "AnyDesk (découverte)", artnet: "Art-Net", dropbox: "Dropbox LAN", steam: "Steam", "mikrotik-ndp": "MikroTik NDP", vrrp: "VRRP", hsrp: "HSRP", "ubiquiti-discovery": "Ubiquiti", capwap: "CAPWAP", snmp: "SNMP", "snmp-trap": "SNMP trap", ntp: "NTP", plex: "Plex", "wake-on-lan": "Wake-on-LAN", sip: "SIP" };

export default function BroadcastView({ siAgentApiBase, assets = [], site = "", agents = [] }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [query, setQuery] = useState("");
  const [agent, setAgent] = useState("");

  const load = async () => {
    setError(null);
    try {
      const r = await fetch(`${siAgentApiBase}/broadcasts${site ? `?site=${encodeURIComponent(site)}` : ""}`, { credentials: "include" });
      const j = await r.json();
      if (!r.ok) throw new Error(j.error || `${r.status}`);
      setData(j); if (!agent && j.probes?.[0]) setAgent(j.probes[0].agent_id);
    } catch (e) { setError(e.message); }
  };
  useEffect(() => { if (siAgentApiBase) load(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, [siAgentApiBase, site]);

  const probe = useMemo(() => (data?.probes || []).find((p) => p.agent_id === agent) || data?.probes?.[0] || null, [data, agent]);
  const announcers = useMemo(() => {
    if (!probe) return [];
    const hosts = probe.announcers.map((a) => ({ ...a, ip: a.ips?.[0] || "", name: a.names?.[0] || "" }));
    return rankFilter(matchWindowsHosts(hosts, assets), query, (a) => [a.mac, ...(a.ips || []), ...(a.names || []), ...(a.services || []), ...Object.keys(a.protocols || {}), a.asset?.name].filter(Boolean).join(" "));
  }, [probe, assets, query]);
  const when = (s) => (s ? new Date(s).toLocaleString("fr-FR") : "—");

  if (!siAgentApiBase) return <p className="muted">si-agent-api non configurée.</p>;
  return (
    <div>
      <p className="muted" style={{ margin: "0 0 8px" }}>
        Sonde <code>broadcast-probe</code> de l'agent du site (Agents hôtes → l'agent → Sondes) : écoute passive d'une minute toutes les cinq — ARP, DHCP, NetBIOS, mDNS/Bonjour, SSDP/UPnP, LLMNR, WS-Discovery, LLDP/CDP, STP, IPv6, multicast applicatif. Rien n'est émis.
        Ne voit que le VLAN du poste de la sonde (une sonde par VLAN à écouter, ou le poste en trunk).
      </p>
      <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap", marginBottom: 8 }}>
        {data?.probes?.length > 1 && <select value={agent} onChange={(e) => setAgent(e.target.value)}>{data.probes.map((p) => <option key={p.agent_id} value={p.agent_id}>{p.agent_id}{p.site ? ` (${p.site})` : ""}</option>)}</select>}
        <input type="search" placeholder="filtrer (MAC, IP, nom, service, protocole, fiche)" value={query} onChange={(e) => setQuery(e.target.value)} style={{ minWidth: 260 }} />
        <span style={{ flex: 1 }} />
        {probe ? <span className="muted">{probe.agent_id} · {probe.frames} trames en {probe.seconds} s ({probe.mode === "raw" ? "capture brute" : "écoute UDP sans privilège"}) · {when(probe.at)}</span> : <span className="muted">aucune mesure : activer la sonde <code>broadcast-probe</code> sur {agents.length ? agents.map((a) => <a key={a.agent_id} href={hubLink("si-agent", { agent: a.agent_id, section: "plugins" })} style={{ marginRight: 6 }}>{a.label || a.agent_id}</a>) : <a href={hubLink("si-agent")}>l'agent du site</a>}</span>}
        <button type="button" className="secondary" onClick={load}>Actualiser</button>
      </div>
      {error && <p style={{ color: "var(--danger)" }}>{error}</p>}
      {probe && (
        <>
          {probe.findings.length > 0 && (
            <ul style={{ margin: "0 0 10px", paddingLeft: 18 }}>
              {probe.findings.map((f, i) => <li key={i} style={{ color: SEV[f.severity] || "inherit" }}>{f.text}</li>)}
            </ul>
          )}
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 10 }}>
            {probe.protocols.map((p) => <span key={p.proto} className="na-chip" title={`${p.sources} émetteur(s)`}>{PROTO_LABEL[p.proto] || p.proto} <strong>{p.frames}</strong></span>)}
          </div>
          {Object.keys(probe.lldp || {}).length > 0 && <p className="muted" style={{ fontSize: 12 }}>LLDP entendu : {Object.values(probe.lldp).map((l) => `${l.sysname || l.chassis} port ${l.port || "?"}`).join(" · ")}</p>}
          <table style={{ width: "100%", borderCollapse: "collapse", textAlign: "left" }}>
            <thead><tr><th>Annonceur</th><th>Adresses</th><th>Fiche</th><th>Protocoles</th><th>Services annoncés</th><th>Trames / min</th></tr></thead>
            <tbody>
              {announcers.map((a) => (
                <tr key={a.mac}>
                  <td><strong>{a.names?.[0] || <span className="muted">?</span>}</strong>{a.names?.length > 1 && <div className="muted" style={{ fontSize: 11 }}>{a.names.slice(1).join(" · ")}</div>}<div><code style={{ fontSize: 11 }}>{a.mac}</code></div></td>
                  <td>{(a.ips || []).map((ip) => <div key={ip}><code>{ip}</code></div>)}</td>
                  <td>{a.asset ? <span>{a.asset.name} <span className="muted">· {a.asset.lab || ""}</span></span> : <span className="muted">—</span>}</td>
                  <td style={{ fontSize: 12 }}>{Object.entries(a.protocols || {}).map(([p, n]) => `${PROTO_LABEL[p] || p} ${n}`).join(" · ")}</td>
                  <td style={{ fontSize: 12 }}>{(a.services || []).join(" · ") || <span className="muted">—</span>}</td>
                  <td style={{ color: a.per_minute > 600 ? "var(--danger)" : undefined }}>{a.per_minute}</td>
                </tr>
              ))}
              {!announcers.length && <tr><td colSpan={6} className="muted">Rien d'entendu sur la fenêtre.</td></tr>}
            </tbody>
          </table>
        </>
      )}
    </div>
  );
}
