// Recherche sur tout le réseau du site (livraison #852) : appareils, clients (nom, IP, MAC avec ou sans séparateurs,
// fabricant, système, SSID, VLAN, signal, dates « jj/mm »), VLAN, anomalies, fiches du campus ; un clic ouvre
// l'onglet concerné et met l'élément au point dans le synoptique.
import { useEffect, useState } from "react";

const TYPE = { appareil: "Appareil", client: "Client", vlan: "VLAN", anomalie: "Anomalie", fiche: "Fiche du campus" };

export default function NebulaRecherche({ nebulaApiBase, siteId, onOuvrir }) {
  const [q, setQ] = useState("");
  const [d, setD] = useState(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    const s = q.trim();
    if (!siteId || s.length < 2) { setD(null); return undefined; }
    let fini = false;
    const t = setTimeout(async () => {
      setBusy(true);
      try {
        const r = await fetch(`${nebulaApiBase}/sites/${encodeURIComponent(siteId)}/recherche?q=${encodeURIComponent(s)}`, { credentials: "include" });
        const j = await r.json();
        if (!fini) setD(j);
      } catch (e) { if (!fini) setD({ resultats: [], erreurs: [e.message] }); }
      if (!fini) setBusy(false);
    }, 400);
    return () => { fini = true; clearTimeout(t); };
  }, [q, siteId, nebulaApiBase]);
  return (
    <div className="hub-card" style={{ padding: "8px 12px" }}>
      <input type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Rechercher partout : nom, IP, MAC, fabricant, SSID, VLAN, signal (-70 dBm), date (23/10)…" style={{ width: "100%" }} aria-label="Rechercher dans le réseau du site" />
      {busy && <p className="muted" style={{ margin: "6px 0 0" }}>Recherche…</p>}
      {d && !busy && (
        <div style={{ maxHeight: 320, overflow: "auto", marginTop: 6 }}>
          {(d.resultats || []).length === 0 ? <p className="muted" style={{ margin: 0 }}>Rien ne correspond{(d.erreurs || []).length ? ` (sources partielles : ${d.erreurs.join(" ; ")})` : ""}.</p> : (
            <table className="services infra-table" style={{ width: "100%" }}>
              <thead><tr><th>Type</th><th>Élément</th><th>Trouvé dans</th></tr></thead>
              <tbody>{d.resultats.map((r, i) => (
                <tr key={i} style={{ cursor: "pointer" }} onClick={() => { onOuvrir && onOuvrir(r.lien || {}); setQ(""); }}>
                  <td className="muted">{TYPE[r.type] || r.type}</td><td><b>{r.titre}</b></td>
                  <td>{(r.champs || []).map(([c, v], j) => <span key={j} style={{ marginRight: 10 }}><span className="muted">{c}</span> {String(v).slice(0, 80)}</span>)}</td>
                </tr>))}</tbody>
            </table>)}
        </div>)}
    </div>
  );
}
