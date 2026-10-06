// Matrice SSID × VLAN (livraison #686) : pour chaque SSID, le VLAN et le
// sous-réseau PRÉVUS (carte des VLAN), ce qui est OBSERVÉ (clients sans fil et
// sous-réseau de leur adresse) et ce qui est PROUVÉ (dernier test actif
// ssid-vlan-check.sh importé), avec un verdict et les écarts en phrases.
import { useEffect, useState } from "react";

const TONE = { "prouvé": "good", "observé": "good", "à prouver": "warn", "désactivé": "neutral", "écart": "bad" };

export default function NebulaSsidMatrix({ nebulaApiBase, siteId, version }) {
  const [m, setM] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState(null);
  const base = `${nebulaApiBase}/sites/${encodeURIComponent(siteId)}`;

  const load = async () => {
    setBusy(true); setError(null);
    try {
      const r = await fetch(`${base}/ssid-matrix`, { credentials: "include" });
      const j = await r.json();
      if (!r.ok) throw new Error(j.error || `${r.status}`);
      setM(j);
    } catch (e) { setError(e.message); }
    finally { setBusy(false); }
  };
  useEffect(() => { if (siteId) load(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, [siteId, version]);

  const importProof = async (file) => {
    if (!file) return;
    setMsg(null);
    const fd = new FormData(); fd.append("file", file);
    try {
      const r = await fetch(`${base}/ssid-proof`, { method: "POST", body: fd, credentials: "include" });
      const j = await r.json();
      if (!r.ok) throw new Error(j.error || `${r.status}`);
      setMsg(`Test importé : ${j.ssids} SSID.`); load();
    } catch (e) { setMsg(`Import refusé : ${e.message}`); }
  };

  return (
    <div>
      <h3>Matrice SSID × VLAN <span className="muted" style={{ textTransform: "none", letterSpacing: 0 }}>· prévue / observée / prouvée</span></h3>
      <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap", marginBottom: 6 }}>
        <button type="button" className="secondary" disabled={busy} onClick={load}>{busy ? "Lecture…" : "Recalculer"}</button>
        <label className="secondary" style={{ cursor: "pointer" }}>Importer un test actif (CSV)
          <input type="file" accept=".csv,.txt,text/plain" style={{ display: "none" }} onChange={(e) => { importProof(e.target.files[0]); e.target.value = ""; }} />
        </label>
        {m && <span className="muted">{Object.entries(m.summary).map(([k, n]) => `${n} ${k}`).join(" · ")}{m.proof_imported_at ? ` · test actif du ${new Date(m.proof_imported_at * 1000).toLocaleString("fr-FR")}` : " · aucun test actif importé"}</span>}
      </div>
      {msg && <p className="muted">{msg}</p>}
      {error && <p style={{ color: "var(--danger)" }}>{error}</p>}
      {m && (
        <>
          <table>
            <thead><tr><th>SSID</th><th>Prévu</th><th>Observé</th><th>Prouvé</th><th>Verdict</th></tr></thead>
            <tbody>{m.ssids.map((r) => (
              <tr key={r.ssid} style={{ opacity: r.enabled ? 1 : 0.6 }}>
                <td><strong>{r.ssid}</strong>{r.guest && <span className="muted"> invités</span>}{!r.enabled && <span className="muted"> (désactivé)</span>}</td>
                <td>{r.planned.vlan != null ? <>VLAN {r.planned.vlan}{r.planned.subnet && <span className="muted"> · {r.planned.subnet}{r.planned.subnet_inferred ? " (déduit)" : ""}</span>}</> : <span className="muted">—</span>}</td>
                <td>{r.observed ? <>{r.observed.clients} client(s){r.observed.with_ip > 0 && <span className="muted"> · {r.observed.in_plan}/{r.observed.with_ip} dans le plan</span>}</> : <span className="muted">aucun client</span>}</td>
                <td>{r.proven ? (r.proven.association ? <>{r.proven.address || "pas de bail"}{Object.keys(r.proven.targets || {}).length > 0 && <span className="muted"> · {Object.values(r.proven.targets).filter(Boolean).length}/{Object.keys(r.proven.targets).length} cibles</span>}</> : <span style={{ color: "var(--danger)" }}>association KO</span>) : <span className="muted">—</span>}</td>
                <td><span className={`np-tone ${TONE[r.verdict] || "neutral"}`}>{r.verdict}</span></td>
              </tr>
            ))}</tbody>
          </table>
          {m.ssids.some((r) => r.gaps.length || r.notes.length) && (
            <ul>{m.ssids.flatMap((r) => [...r.gaps.map((g, i) => <li key={`${r.ssid}g${i}`}><strong>{r.ssid}</strong> : {g}</li>), ...r.notes.map((n, i) => <li key={`${r.ssid}n${i}`} className="muted"><strong>{r.ssid}</strong> : {n}</li>)])}</ul>
          )}
          {m.vlans_without_ssid.length > 0 && <p className="muted">VLAN sans SSID (filaire seulement) : {m.vlans_without_ssid.join(", ")}.</p>}
          <p className="muted" style={{ fontSize: 12 }}>
            Observé : {m.sources.with_ssid} client(s) rattaché(s) à un SSID ({m.sources.api_clients} par l'API, {m.sources.csv_clients} par le dernier export CSV).
            {m.sources.with_ssid === 0 && " L'API ne publie pas le SSID des clients sur ce site : importer l'export « Clients » du portail Nebula (onglet Imports)."}
            {" "}Prouvé : <code>sudo SSIDCHECK_CSV=/root/ssid-check.csv ./nebula/tools/ssid-vlan-check.sh &lt;wifi&gt; &lt;fichier-ssids&gt; [cibles]</code> puis importer le CSV ici.
          </p>
          {m.errors.length > 0 && <p className="muted">Appels en échec : {m.errors.join(" · ")}</p>}
        </>
      )}
    </div>
  );
}
