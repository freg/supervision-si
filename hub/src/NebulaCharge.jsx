// Charge du réseau (livraison #851) -- onglet « Charge » de la tuile Nebula : par borne, SSID, VLAN et commutateur,
// clients (distincts sur la fenêtre ; simultanés moyens / max d'après les relevés d'occupation du hub) et débit
// moyen sur la fenêtre. Sources : OpenAPI Nebula (clients des bornes avec octets, clients du site / des commutateurs,
// usage de la liaison montante des commutateurs) ; la passerelle n'expose pas d'usage documenté.
import { useEffect, useState } from "react";

const PERIODES = [["2h", "2 h"], ["1d", "1 jour"], ["7d", "7 jours"], ["30d", "30 jours"]];
const vol = (o) => (o == null ? "—" : o >= 1e9 ? `${(o / 1e9).toFixed(2)} Go` : o >= 1e6 ? `${(o / 1e6).toFixed(1)} Mo` : `${Math.round(o / 1e3)} ko`);
const deb = (m) => (m == null ? "—" : m >= 1 ? `${m.toFixed(2)} Mbit/s` : `${Math.round(m * 1000)} kbit/s`);

function Barre({ v, max }) {
  const p = max ? Math.min(100, (100 * v) / max) : 0;
  return <span style={{ display: "inline-block", width: 80, height: 6, background: "var(--border, #263241)", borderRadius: 3, verticalAlign: "middle", marginRight: 6 }}>
    <span style={{ display: "block", width: `${p}%`, height: 6, background: "var(--accent, #4aa3ff)", borderRadius: 3 }} /></span>;
}

function Tableau({ titre, cols, lignes, cle, tri }) {
  const max = Math.max(0, ...lignes.map((l) => l[tri] || 0));
  return (
    <div className="hub-card">
      <h3 style={{ marginTop: 0 }}>{titre} ({lignes.length})</h3>
      <div style={{ maxHeight: 380, overflow: "auto" }}><table className="services infra-table" style={{ width: "100%" }}>
        <thead><tr>{cols.map(([k, l]) => <th key={k}>{l}</th>)}</tr></thead>
        <tbody>{[...lignes].sort((a, b) => (b[tri] || 0) - (a[tri] || 0)).map((l) => (
          <tr key={l[cle]}>{cols.map(([k, , f]) => <td key={k}>{k === tri ? <><Barre v={l[k] || 0} max={max} />{f ? f(l[k], l) : l[k]}</> : f ? f(l[k], l) : (l[k] ?? "—")}</td>)}</tr>))}</tbody>
      </table></div>
    </div>
  );
}

export default function NebulaCharge({ nebulaApiBase, siteId }) {
  const [periode, setPeriode] = useState("1d");
  const [d, setD] = useState(null);
  const [err, setErr] = useState(null);
  const [busy, setBusy] = useState(false);
  const load = async (refresh) => {
    if (!siteId) return;
    setBusy(true); setErr(null);
    try {
      const r = await fetch(`${nebulaApiBase}/sites/${encodeURIComponent(siteId)}/charge?period=${periode}${refresh ? "&refresh=1" : ""}`, { credentials: "include" });
      const j = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(j.error || r.status);
      setD(j);
    } catch (e) { setErr(e.message); }
    setBusy(false);
  };
  useEffect(() => { load(false); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, [nebulaApiBase, siteId, periode]);

  return (
    <div>
      <div className="hub-card" style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
        <label>Fenêtre <select value={periode} onChange={(e) => setPeriode(e.target.value)}>{PERIODES.map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select></label>
        <button type="button" onClick={() => load(true)} disabled={busy}>{busy ? "en cours…" : "Relire"}</button>
        {d && <span>{d.total.clients_wifi} client(s) Wi-Fi distinct(s) · {vol(d.total.wifi_octets)} · débit moyen Wi-Fi {deb(d.total.wifi_debit_mbps)}</span>}
        {d && <span className="muted">lu le {new Date(d.at * 1000).toLocaleString("fr-FR")}{d.periode_commutateurs !== d.periode ? ` · commutateurs sur ${d.periode_commutateurs}` : ""}</span>}
      </div>
      {err && <p style={{ color: "var(--danger)" }}>{err}</p>}
      {d && (d.erreurs || []).length > 0 && <p className="muted">Sources partielles : {d.erreurs.join(" ; ")}</p>}
      {d && <>
        <Tableau titre="Bornes Wi-Fi" cle="dev_id" tri="debit_mbps" lignes={d.bornes} cols={[["nom", "Borne"], ["clients", "Clients distincts"],
          ["simultanes_moy", "Simultanés moy. / max", (v, l) => (v == null ? "—" : `${v} / ${l.simultanes_max}`)], ["descendant_o", "Descendant", vol], ["montant_o", "Montant", vol], ["debit_mbps", "Débit moyen", deb]]} />
        <Tableau titre="SSID" cle="ssid" tri="debit_mbps" lignes={d.ssids} cols={[["ssid", "SSID"], ["vlan", "VLAN"], ["clients", "Clients distincts"], ["descendant_o", "Descendant", vol], ["montant_o", "Montant", vol], ["debit_mbps", "Débit moyen", deb]]} />
        <Tableau titre="VLAN" cle="vlan" tri="clients" lignes={d.vlans} cols={[["vlan", "VLAN"], ["clients", "Clients distincts"], ["filaires", "dont filaires"], ["ssids", "SSID", (v) => (v || []).join(", ") || "—"],
          ["wifi_descendant_o", "Wi-Fi descendant", vol], ["wifi_debit_mbps", "Débit Wi-Fi moyen", deb]]} />
        <Tableau titre="Commutateurs (liaison montante)" cle="dev_id" tri="debit_mbps" lignes={d.commutateurs} cols={[["nom", "Commutateur"], ["descendant_o", "Reçu", vol], ["montant_o", "Émis", vol], ["debit_mbps", "Débit moyen", deb], ["erreur", "Note", (v) => v || ""]]} />
        <div className="hub-card"><h3 style={{ marginTop: 0 }}>Passerelle / pare-feu</h3>
          {(d.passerelles || []).map((g) => <p key={g.dev_id} style={{ margin: "4px 0" }}><b>{g.nom}</b> : {g.erreur ? <span className="muted">{g.erreur}</span> : <code>{JSON.stringify(g.brut)}</code>}</p>)}
          <p className="muted" style={{ margin: 0 }}>L'OpenAPI Nebula documente l'usage des liaisons montantes des commutateurs et les octets par client des bornes, pas l'usage par interface du pare-feu ni le débit instantané. Clients « simultanés » : relevés d'occupation du hub (onglet Rapports &amp; alertes, occupation activée).</p></div>
      </>}
    </div>
  );
}
