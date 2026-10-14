// Anticipation Wi-Fi (livraison #758, BACKLOG 122 tranche 1) : pic habituel attendu par borne dans les prochaines
// heures, affluence inhabituelle, bornes instables (battements d'état 24 h), disponibilité 7 / 30 jours, étendues
// DHCP par SSID. Réglages enregistrés avec ceux de l'occupation (cfg.occupancy.anticipation).
// Données : nebula-api /report/anticipation (calcul à la demande sur les relevés #747 et les transitions Nebula).
import { useEffect, useState } from "react";
import { AutoColumns } from "./TableColumns.jsx";

const tone = (n, t) => (n == null ? "neutral" : n >= t.ap_crit ? "bad" : n >= t.ap_warn ? "warn" : "good");
const avTone = (p) => (p == null ? "neutral" : p >= 99.5 ? "good" : p >= 97 ? "warn" : "bad");

export default function NebulaAnticipation({ base, cfg, setCfg, call }) {
  const [data, setData] = useState(null), [err, setErr] = useState(null), [pool, setPool] = useState({ ssid: "", size: "" });
  const a = cfg.occupancy.anticipation || {};
  const setA = (k, v) => setCfg({ ...cfg, occupancy: { ...cfg.occupancy, anticipation: { ...a, [k]: v } } });
  const load = async () => { try { setData(await call(`${base}/anticipation`)); setErr(null); } catch (e) { setErr(e.message); } };
  useEffect(() => { load(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, [base]);
  const num = (k, min, max, w = 56) => <input type="number" min={min} max={max} value={a[k] ?? ""} onChange={(e) => setA(k, +e.target.value)} style={{ width: w }} />;
  const t = data?.thresholds || { ap_warn: cfg.occupancy.ap_warn, ap_crit: cfg.occupancy.ap_crit };
  const sites = Object.entries(data?.sites || {});
  const flaps = sites.flatMap(([, s]) => s.flapping || []);
  const unusual = sites.flatMap(([, s]) => s.unusual || []);
  const av = sites.flatMap(([, s]) => Object.entries(s.availability_30 || {}).map(([dev, p30]) => ({ dev, p30, p7: (s.availability_7 || {})[dev] })))
    .filter((r) => r.p30 != null).sort((x, y) => x.p30 - y.p30);
  const pools = a.dhcp_pools || {};
  return (
    <div>
      <label><input type="checkbox" checked={a.enabled !== false} onChange={(e) => setA("enabled", e.target.checked)} /> <strong>Anticipation</strong> <span className="muted">(alertes <code>nebula.anticipation</code>)</span></label>
      <div style={{ display: "grid", gap: 6, marginTop: 6 }}>
        <label>Prévenir {num("horizon_hours", 1, 12)} h avant un pic habituel (au moins {num("min_weeks", 1, 5)} semaine(s) observée(s) au même créneau) — seuils de borne {t.ap_warn} / {t.ap_crit} clients</label>
        <label>Affluence inhabituelle : au-delà de l'habituel + {num("unusual_margin_pct", 10, 500)} % et d'au moins {num("unusual_min", 1, 500)} clients</label>
        <label>Borne instable : {num("flap_count", 2, 50)} passages hors ligne / en alerte en 24 h</label>
        <div>Étendues DHCP par SSID (alerte à {num("dhcp_warn_pct", 10, 100)} %, critique à {num("dhcp_crit_pct", 10, 100)} %) :{" "}
          {Object.entries(pools).map(([s, n]) => <span key={s} className="np-tone neutral" style={{ marginRight: 4 }}>{s} : {n} <button type="button" className="secondary" onClick={() => { const p = { ...pools }; delete p[s]; setA("dhcp_pools", p); }}>✕</button></span>)}
          <input value={pool.ssid} onChange={(e) => setPool({ ...pool, ssid: e.target.value })} placeholder="SSID" style={{ width: 120 }} />
          <input type="number" min={1} value={pool.size} onChange={(e) => setPool({ ...pool, size: e.target.value })} placeholder="adresses" style={{ width: 90 }} />
          <button type="button" className="secondary" disabled={!pool.ssid || !(+pool.size > 0)} onClick={() => { setA("dhcp_pools", { ...pools, [pool.ssid.trim()]: +pool.size }); setPool({ ssid: "", size: "" }); }}>Ajouter</button></div>
        <span className="muted" style={{ fontSize: 12 }}>Les réglages s'appliquent après « Enregistrer » (en bas de la page). Le profil habituel se construit avec les relevés d'occupation (35 jours conservés) : il faut quelques semaines de relevés pour les premières prévisions.</span>
      </div>
      <div style={{ margin: "8px 0" }}><button type="button" className="secondary" onClick={load}>Actualiser</button>{err && <span style={{ color: "var(--danger)" }}> {err}</span>}</div>
      {data && <>
        {(data.forecast.length > 0 || unusual.length > 0 || flaps.length > 0) && (
          <ul style={{ fontSize: 13 }}>
            {data.forecast.map((r) => <li key={r.id}><span className={`np-tone ${r.severity === "haute" ? "bad" : "warn"}`}>pic attendu</span> {r.message}</li>)}
            {unusual.map((r) => <li key={r.id}><span className="np-tone warn">inhabituel</span> {r.message}</li>)}
            {flaps.map((r) => <li key={r.id}><span className={`np-tone ${r.severity === "haute" ? "bad" : "warn"}`}>instable</span> {r.message} — {r.action}</li>)}
          </ul>)}
        {data.next_hours.length > 0 ? (
          <details open><summary>Prochaines heures : clients habituels par borne (p90 des semaines observées)</summary>
            <div className="hub-table-scroll"><AutoColumns id="NebulaAnticipation.1"><table>
              <thead><tr><th>Borne</th>{data.next_hours[0].hours.map((h) => <th key={h.at}>{h.at}</th>)}</tr></thead>
              <tbody>{data.next_hours.map((r) => <tr key={r.dev_id}><td>{r.name}</td>{r.hours.map((h) => <td key={h.at} title={h.p50 != null ? `médiane ${h.p50} · ${h.weeks} semaine(s)` : "pas assez de semaines"}>{h.p90 != null ? <span className={`np-tone ${tone(h.p90, t)}`}>{h.p90}</span> : <span className="muted">—</span>}</td>)}</tr>)}</tbody>
            </table></AutoColumns></div></details>
        ) : <p className="muted" style={{ fontSize: 13 }}>Pas encore de profil habituel (il faut des relevés d'occupation sur {a.min_weeks || 2} semaine(s) au moins).</p>}
        {av.length > 0 && (
          <details><summary>Disponibilité des appareils Nebula (7 / 30 jours, des moins disponibles aux plus disponibles)</summary>
            <div className="hub-table-scroll"><AutoColumns id="NebulaAnticipation.2"><table><thead><tr><th>Appareil</th><th>7 jours</th><th>30 jours</th></tr></thead>
              <tbody>{av.map((r) => <tr key={r.dev}><td>{data.names?.[r.dev] || r.dev}</td><td><span className={`np-tone ${avTone(r.p7)}`}>{r.p7 ?? "—"} %</span></td><td><span className={`np-tone ${avTone(r.p30)}`}>{r.p30} %</span></td></tr>)}</tbody>
            </table></AutoColumns></div></details>)}
        {data.dhcp.length > 0 && (
          <table style={{ fontSize: 13, marginTop: 6 }}><thead><tr><th>SSID</th><th>Clients connectés</th><th>Étendue</th><th>Occupation</th></tr></thead>
            <tbody>{data.dhcp.map((d) => <tr key={d.ssid}><td>{d.ssid}</td><td>{d.clients}</td><td>{d.pool}</td>
              <td><span className={`np-tone ${d.pct >= (a.dhcp_crit_pct || 95) ? "bad" : d.pct >= (a.dhcp_warn_pct || 80) ? "warn" : "good"}`}>{d.pct} %</span></td></tr>)}</tbody></table>)}
      </>}
    </div>
  );
}
