// Onglet « Accès Windows » du volet Campus (livraison #567) : hôtes vus par
// la sonde windows-probe des agents du site (NetBIOS, SMB, RDP, AnyDesk,
// VNC, WinRM, SSH), rapprochés des fiches matériel, avec les liens d'accès
// (fichier .rdp, anydesk:, smb://, vnc://) et les constats de sécurité.
import { useEffect, useMemo, useState } from "react";
import { matchWindowsHosts, accessLinks } from "./campusCards.js";
import { rankFilter } from "./textFilter.js";

const SEV = { warning: "var(--warning)", critical: "var(--danger)", info: "var(--muted)" };

function download(name, text) {
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([text], { type: "application/x-rdp" })); a.download = name; a.click();
}

export default function WindowsHostsView({ siAgentApiBase, assets = [], site = "" }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [query, setQuery] = useState("");
  const [onlyWindows, setOnlyWindows] = useState(true);

  const load = async () => {
    setError(null);
    try {
      const r = await fetch(`${siAgentApiBase}/windows-hosts${site ? `?site=${encodeURIComponent(site)}` : ""}`, { credentials: "include" });
      const j = await r.json();
      if (!r.ok) throw new Error(j.error || `${r.status}`);
      setData(j);
    } catch (e) { setError(e.message); }
  };
  useEffect(() => { if (siAgentApiBase) load(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, [siAgentApiBase, site]);

  const hosts = useMemo(() => {
    const all = matchWindowsHosts(data?.hosts || [], assets).filter((h) => !onlyWindows || h.windows_like);
    return rankFilter(all, query, (h) => [h.name, h.ip, h.mac, h.workgroup, h.asset?.name, h.asset?.lab, ...Object.keys(h.ports || {})].filter(Boolean).join(" "));
  }, [data, assets, query, onlyWindows]);
  const when = (s) => (s ? new Date(s).toLocaleString("fr-FR") : "—");

  if (!siAgentApiBase) return <p className="muted">si-agent-api non configurée.</p>;
  return (
    <div>
      <p className="muted" style={{ margin: "0 0 8px" }}>
        Sonde <code>windows-probe</code> de l'agent du site (Agents hôtes → l'agent → Sondes) : balaie le réseau, interroge NetBIOS, SMB, RDP, AnyDesk, VNC, WinRM, SSH — sans authentification ni action.
        Les liens ouvrent le client installé sur votre poste (fichier .rdp pour RDP, <code>anydesk:</code>, <code>smb://</code>) ; ils ne passent pas par le hub.
      </p>
      <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap", marginBottom: 8 }}>
        <input type="search" placeholder="filtrer (nom, IP, MAC, groupe, fiche, port)" value={query} onChange={(e) => setQuery(e.target.value)} style={{ minWidth: 260 }} />
        <label className="muted"><input type="checkbox" checked={onlyWindows} onChange={(e) => setOnlyWindows(e.target.checked)} /> postes Windows seulement</label>
        <span style={{ flex: 1 }} />
        {data?.probes?.length ? <span className="muted">{data.probes.map((p) => `${p.agent_id} : ${p.scanned ?? "?"} adresses, ${p.stats?.alive ?? "?"} hôtes, ${when(p.at)}`).join(" · ")}</span> : <span className="muted">aucune mesure : activer la sonde sur l'agent du site</span>}
        <button type="button" className="secondary" onClick={load}>Actualiser</button>
      </div>
      {error && <p style={{ color: "var(--danger)" }}>{error}</p>}
      <table style={{ width: "100%", borderCollapse: "collapse", textAlign: "left" }}>
        <thead><tr><th>Hôte</th><th>IP</th><th>Fiche</th><th>Groupe / domaine</th><th>MAC</th><th>Accès</th><th>SMB</th><th>RDP</th><th>Constats</th></tr></thead>
        <tbody>
          {hosts.map((h) => (
            <tr key={h.ip}>
              <td><strong>{h.name || <span className="muted">?</span>}</strong></td>
              <td><code>{h.ip}</code></td>
              <td>{h.asset ? <span title={h.asset.lab}>{h.asset.name} <span className="muted">· {h.asset.lab || ""}</span></span> : <span className="muted">—</span>}</td>
              <td>{h.workgroup || <span className="muted">—</span>}</td>
              <td><code style={{ fontSize: 11 }}>{h.mac || "—"}</code></td>
              <td style={{ whiteSpace: "nowrap" }}>
                {accessLinks(h).map((l) => (
                  <span key={l.kind} style={{ marginRight: 6 }}>
                    {l.download ? <button type="button" className="secondary" onClick={() => download(l.download.name, l.download.text)} title="télécharge un fichier .rdp à ouvrir avec le client Bureau à distance">{l.label}</button>
                      : l.href ? <a className="secondary" href={l.href} title={l.copy || l.href}>{l.label}</a>
                      : <button type="button" className="secondary" onClick={() => navigator.clipboard?.writeText(l.copy)} title={`copier : ${l.copy}`}>{l.label}</button>}
                    {l.copy && l.href && <button type="button" className="secondary" style={{ fontSize: 10, padding: "1px 4px", marginLeft: 2 }} onClick={() => navigator.clipboard?.writeText(l.copy)} title={`copier ${l.copy}`}>⧉</button>}
                  </span>
                ))}
                {!accessLinks(h).length && <span className="muted">aucun port d'accès</span>}
              </td>
              <td>{h.smb?.open ? `${h.smb.dialect || "?"}${h.smb.signing_required ? " · signé" : ""}${h.smb.smb1 ? " · SMB1 !" : ""}` : <span className="muted">—</span>}</td>
              <td>{h.rdp?.open ? (h.rdp.protocol || "ouvert") : <span className="muted">—</span>}</td>
              <td>{(h.findings || []).map((f) => <div key={f.code} style={{ color: SEV[f.severity] || "inherit", fontSize: 12 }}>{f.text}</div>)}</td>
            </tr>
          ))}
          {data && !hosts.length && <tr><td colSpan={9} className="muted">Aucun hôte{onlyWindows ? " Windows" : ""} vu par la sonde.</td></tr>}
        </tbody>
      </table>
    </div>
  );
}
