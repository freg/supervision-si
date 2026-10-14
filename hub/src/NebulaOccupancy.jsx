// Occupation des bornes Wi-Fi (livraison #747) : réglages (relevé, seuils par borne, signal faible, alertes
// Nebula hors ligne / en alerte, récapitulatif), dernier relevé par borne, statistiques de la période, constats
// en cours. Données : nebula-api /report/occupancy ; réglages enregistrés avec ceux du rapport (PUT /report/settings).
import { useEffect, useState } from "react";
import { AutoColumns } from "./TableColumns.jsx";

const DAYS = [[1, "lun"], [2, "mar"], [3, "mer"], [4, "jeu"], [5, "ven"], [6, "sam"], [7, "dim"]];
const when = (t) => (t ? new Date(t * 1000).toLocaleString("fr-FR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" }) : "—");

export default function NebulaOccupancy({ base, cfg, setCfg, call, groups, login, box }) {
  const [data, setData] = useState(null);
  const [hours, setHours] = useState(24);
  const [msg, setMsg] = useState(null);
  const [busy, setBusy] = useState(false);
  const o = cfg.occupancy;
  const setO = (k, v) => setCfg({ ...cfg, occupancy: { ...o, [k]: v } });
  const setR = (k, v) => setCfg({ ...cfg, occupancy: { ...o, recap: { ...o.recap, [k]: v } } });
  const load = async () => { try { setData(await call(`${base}/occupancy?hours=${hours}`)); } catch (e) { setMsg({ error: e.message }); } };
  useEffect(() => { load(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, [base, hours]);
  const num = (k, min, max, w = 60) => <input type="number" min={min} max={max} value={o[k]} onChange={(e) => setO(k, +e.target.value)} style={{ width: w }} />;
  const sendNow = async () => {
    setBusy(true); setMsg(null);
    try { const r = await call(`${base}/occupancy/send`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ groups, user: login, sample: true }) });
      setMsg({ ok: `Relevé fait, récapitulatif de test : ${r.status}, ${r.recipients ?? "?"} destinataire(s)` }); await load(); }
    catch (e) { setMsg({ error: e.message }); }
    setBusy(false);
  };
  const cur = Object.values(data?.current?.sites || {}).flatMap((s) => s.aps || []);
  const tone = (n) => (n >= o.ap_crit ? "bad" : n >= o.ap_warn ? "warn" : "good");
  return (
    <div style={box}>
      <label><input type="checkbox" checked={o.enabled} onChange={(e) => setO("enabled", e.target.checked)} /> <strong>Occupation des bornes Wi-Fi et alertes Nebula</strong></label>
      <div style={{ marginTop: 8, display: "grid", gap: 6 }}>
        <label>Relevé des clients toutes les {num("sample_minutes", 5, 120)} min</label>
        <label>Borne chargée à partir de {num("ap_warn", 1, 500)} clients, critique à {num("ap_crit", 1, 500)} · site chargé à {num("site_warn", 0, 100000, 80)} (0 = pas de seuil)</label>
        <label>Signal faible : sous {num("weak_dbm", -95, -40)} dBm, alerte si ≥ {num("weak_pct", 0, 100)} % des clients d'une borne (à partir de {num("weak_min_clients", 1, 500)} clients)</label>
        <label><input type="checkbox" checked={o.status_alerts} onChange={(e) => setO("status_alerts", e.target.checked)} /> alerte Nebula quand un appareil est hors ligne ou en alerte depuis {num("status_delay_minutes", 0, 1440)} min</label>
        <label><input type="checkbox" checked={o.recap.enabled} onChange={(e) => setR("enabled", e.target.checked)} /> récapitulatif à <input type="time" value={o.recap.time} onChange={(e) => setR("time", e.target.value)} /> sur les {""}
          <input type="number" min={1} max={168} value={o.recap.hours} onChange={(e) => setR("hours", +e.target.value)} style={{ width: 60 }} /> dernières heures, les{" "}
          {DAYS.map(([d, l]) => <label key={d} style={{ marginRight: 4 }}><input type="checkbox" checked={o.recap.weekdays.includes(d)} onChange={() => setR("weekdays", o.recap.weekdays.includes(d) ? o.recap.weekdays.filter((x) => x !== d) : [...o.recap.weekdays, d].sort())} />{l}</label>)}
        </label>
        <span className="muted" style={{ fontSize: 12 }}>Messages : actions <code>nebula.occupation-seuil</code>, <code>nebula.alerte-nebula</code>, <code>nebula.occupation-recap</code> (destinataires ci-dessus + groupes de la tuile Notifications). Prochain récapitulatif : {data?.next_recap ? new Date(data.next_recap).toLocaleString("fr-FR") : "—"}. Enregistrer avec le bouton général.</span>
      </div>
      <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap", margin: "8px 0" }}>
        <button type="button" className="secondary" disabled={busy} onClick={sendNow}>{busy ? "⏳" : "Relever maintenant et envoyer un récapitulatif de test"}</button>
        <label className="muted">Statistiques sur <select value={hours} onChange={(e) => setHours(+e.target.value)}>{[6, 24, 72, 168].map((h) => <option key={h} value={h}>{h} h</option>)}</select></label>
        {msg?.ok && <span style={{ color: "var(--ok, green)" }}>{msg.ok}</span>}
        {msg?.error && <span style={{ color: "var(--danger)" }}>{msg.error}</span>}
      </div>
      {cur.length > 0 && <p className="muted" style={{ fontSize: 13 }}>Dernier relevé {when(data.current.at)} : {cur.reduce((a, b) => a + b.clients, 0)} client(s) sur {cur.length} borne(s){data.recap?.site_peak && <> · pic de la période {data.recap.site_peak.clients} le {when(data.recap.site_peak.at)}</>}</p>}
      {(data?.recap?.aps || []).length > 0 && (
        <div className="hub-table-scroll"><AutoColumns id="NebulaOccupancy.1"><table>
          <thead><tr><th>Borne</th><th>Maintenant</th><th>Moyenne</th><th>p95</th><th>Max</th><th>Heure du max</th><th>Signal faible</th></tr></thead>
          <tbody>{data.recap.aps.map((r) => { const c = cur.find((x) => x.dev_id === r.dev_id); return (
            <tr key={r.dev_id}><td>{r.name}</td><td>{c ? <span className={`np-tone ${tone(c.clients)}`}>{c.clients}</span> : "—"}</td><td>{r.avg}</td><td>{r.p95}</td>
              <td><span className={`np-tone ${tone(r.max)}`}>{r.max}</span></td><td>{when(r.max_at)}</td><td>{c ? c.weak : "—"}</td></tr>); })}</tbody>
        </table></AutoColumns></div>
      )}
      {(data?.open || []).length > 0 && (
        <details open><summary>Constats en cours ({data.open.length})</summary>
          <ul style={{ fontSize: 13 }}>{data.open.map((e) => <li key={e.id}><span className={`np-tone ${e.severity === "haute" ? "bad" : "warn"}`}>{e.kind === "nebula" ? "Nebula" : "occupation"}</span> {e.message} · depuis {when(e.first_seen)}</li>)}</ul>
        </details>
      )}
    </div>
  );
}
