// Carte des VLAN (livraison #548) : ce que l'OpenAPI Nebula permet de
// reconstituer -- par VLAN les SSID, le sous-réseau, les ports de chaque
// commutateur ; les liaisons LLDP entre commutateurs avec les VLAN manquants
// d'un côté ; les anomalies en phrases. Export CSV.
import { useEffect, useState } from "react";
import NebulaTopo from "./NebulaTopo.jsx";

async function getJson(url) {
  const r = await fetch(url, { credentials: "include" });
  const j = await r.json();
  if (!r.ok) throw new Error(j.error || `${r.status}`);
  return j;
}

export default function NebulaVlan({ nebulaApiBase }) {
  const [sites, setSites] = useState([]);
  const [siteId, setSiteId] = useState("");
  const [map, setMap] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    getJson(`${nebulaApiBase}/health-board?hours=1`).then((d) => { setSites(d.sites || []); if (d.sites && d.sites[0]) setSiteId(d.sites[0].site_id); }).catch((e) => setError(e.message));
  }, [nebulaApiBase]);

  const load = async (refresh) => {
    if (!siteId) return;
    setBusy(true); setError(null);
    try { setMap(await getJson(`${nebulaApiBase}/sites/${encodeURIComponent(siteId)}/vlan-map${refresh ? "?refresh=1" : ""}`)); }
    catch (e) { setError(e.message); }
    finally { setBusy(false); }
  };
  useEffect(() => { load(false); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, [siteId]);

  const switches = map ? map.switches.map((s) => s.name) : [];
  return (
    <div>
      <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap", marginBottom: 10 }}>
        <select value={siteId} onChange={(e) => setSiteId(e.target.value)}>{sites.map((s) => <option key={s.site_id} value={s.site_id}>{s.site_name}</option>)}</select>
        <button type="button" className="secondary" disabled={busy} onClick={() => load(true)}>{busy ? "Lecture…" : "Relire depuis Nebula"}</button>
        {siteId && <a className="secondary" href={`${nebulaApiBase}/sites/${encodeURIComponent(siteId)}/vlan-map?format=csv`}>Export CSV</a>}
        {map && <span className="muted">calculée {new Date(map.at * 1000).toLocaleString("fr-FR")} · cache 10 min</span>}
      </div>
      {error && <p style={{ color: "var(--danger)" }}>{error}</p>}
      {map && (
        <div>
          <h3>Synoptique</h3>
          <NebulaTopo nebulaApiBase={nebulaApiBase} siteId={siteId} vmap={map} />
          {map.anomalies.length > 0 ? (
            <div className="hub-card" style={{ borderColor: "var(--danger)" }}>
              <strong>{map.anomalies.length} anomalie{map.anomalies.length > 1 ? "s" : ""}</strong>
              <ul>{map.anomalies.map((a, i) => <li key={i}>{a}</li>)}</ul>
            </div>
          ) : <p className="muted">Aucune anomalie : chaque liaison porte les mêmes VLAN des deux côtés et chaque SSID a son VLAN sur les commutateurs.</p>}
          {map.errors.length > 0 && <p className="muted">Appels en échec (carte partielle) : {map.errors.join(" · ")}</p>}
          <h3>VLAN ({map.vlans.length})</h3>
          <table>
            <thead><tr><th>VLAN</th><th>Sous-réseau</th><th>SSID</th>{switches.map((n) => <th key={n}>{n}</th>)}<th>MAC</th><th>Clients</th></tr></thead>
            <tbody>
              {map.vlans.map((v) => (
                <tr key={v.vid}>
                  <td><strong>{v.vid}</strong>{v.management.length > 0 && <span className="muted"> (gestion)</span>}</td>
                  <td>{v.subnet ? <span title={v.subnet_inferred ? "déduit des adresses des clients (la passerelle ne publie pas ses adresses)" : v.gateway_interface || ""}>{v.subnet}{v.subnet_inferred && <span className="muted"> (déduit)</span>}</span> : v.gateway_interface ? <span className="muted">{v.gateway_interface}</span> : <span className="muted">—</span>}{v.guest && <span className="muted"> invités</span>}</td>
                  <td>{v.ssids.map((s) => <span key={s.name} style={{ opacity: s.enabled ? 1 : 0.5 }}>{s.name}{s.enabled ? "" : " (désactivé)"} </span>)}</td>
                  {switches.map((n) => { const p = v.switches[n]; return <td key={n}>{p ? <span>{p.untagged.length > 0 && <span>U: {p.untagged.join(" ")}</span>}{p.untagged.length > 0 && p.tagged.length > 0 && " · "}{p.tagged.length > 0 && <span className="muted">T: {p.tagged.join(" ")}</span>}</span> : <span className="muted">—</span>}</td>; })}
                  <td>{v.mac_count}</td><td>{v.clients}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="muted">U = ports non étiquetés (PVID), T = ports étiquetés (trunk).</p>
          <h3>Liaisons entre commutateurs (LLDP)</h3>
          {map.links.filter((l) => !l.external).length === 0 ? <p className="muted">Aucune liaison LLDP entre deux commutateurs du site.</p> : (
            <table>
              <thead><tr><th>Commutateur A</th><th>Port</th><th>Commutateur B</th><th>Port</th><th>VLAN côté A</th><th>VLAN côté B</th><th>Manquants</th></tr></thead>
              <tbody>{map.links.filter((l) => !l.external).map((l, i) => (
                <tr key={i} style={(l.missing_on_a.length || l.missing_on_b.length) ? { color: "var(--danger)" } : undefined}>
                  <td>{l.a_name}</td><td>{l.a_port}</td><td>{l.b_name}</td><td>{l.b_port}</td>
                  <td>{Array.isArray(l.a_vlans) ? l.a_vlans.join(" ") : l.a_vlans}</td><td>{Array.isArray(l.b_vlans) ? l.b_vlans.join(" ") : l.b_vlans}</td>
                  <td>{l.missing_on_a.length > 0 && `côté ${l.a_name} : ${l.missing_on_a.join(" ")}`}{l.missing_on_a.length > 0 && l.missing_on_b.length > 0 && " · "}{l.missing_on_b.length > 0 && `côté ${l.b_name} : ${l.missing_on_b.join(" ")}`}</td>
                </tr>
              ))}</tbody>
            </table>
          )}
          {map.links.filter((l) => l.external).length > 0 && (
            <details><summary>Autres voisins LLDP ({map.links.filter((l) => l.external).length})</summary>
              <ul>{map.links.filter((l) => l.external).map((l, i) => <li key={i}>{l.a_name} port {l.a_port} → {l.b_name}{l.b_port ? ` (port ${l.b_port})` : ""}</li>)}</ul>
            </details>
          )}
        </div>
      )}
    </div>
  );
}
