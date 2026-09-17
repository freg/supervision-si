// Section « Chemin de service vu du poste » de la fiche agent (#527) :
// dernière mesure de la sonde path-probe (par interface : bail, passerelle,
// DNS distribués, DNS publics, HTTP, HTTPS, constats) et historique.
import { useEffect, useState } from "react";
import { fetchAgentMeasurements } from "./siAgentClient.js";
import { pathRows, pathWorst, pathLabel, dnsSummary, pathTone, pctTone, fmt } from "./pathLib.js";

function T({ tone, children, title }) {
  return <span className={`np-tone ${tone || "neutral"}`} title={title}>{children}</span>;
}

function Dns({ list }) {
  if (!list || !list.length) return <span className="muted">aucun</span>;
  return <>{list.map((d, i) => <span key={d.server + i} style={{ marginRight: 6 }}><code>{d.server}</code> <T tone={d.ok ? pctTone(d.ms, 500, 2000) : "bad"} title={d.error || (d.answers || []).join(", ")}>{d.ok ? fmt(d.ms, " ms") : d.error || "✗"}</T></span>)}</>;
}

function Web({ h }) {
  if (!h) return <span className="muted">non configuré</span>;
  if (h.portal) return <T tone="bad" title={h.detail}>intercepté</T>;
  if (!h.ok) return <T tone="bad" title={h.error || ""}>échec{h.status ? ` (${h.status})` : ""}</T>;
  return <><T tone={pctTone(h.ms, 3000, 8000)}>{fmt(h.ms, " ms")}</T> <span className="muted">{h.status}{h.ip ? ` · ${h.ip}` : ""}</span></>;
}

function age(s) {
  if (s == null) return "";
  if (s < 3600) return `${Math.round(s / 60)} min`;
  if (s < 86400) return `${(s / 3600).toFixed(1)} h`;
  return `${(s / 86400).toFixed(1)} j`;
}

export default function PathProbeSection({ apiBase, agentId, latest, when }) {
  const [hist, setHist] = useState([]);
  const [limit, setLimit] = useState(60);
  useEffect(() => {
    let alive = true;
    fetchAgentMeasurements(apiBase, agentId, { task: "plugin:path-probe", limit }).then((m) => { if (alive) setHist(m); }).catch(() => {});
    return () => { alive = false; };
  }, [apiBase, agentId, limit, latest?.at]);
  const d = latest?.data;
  if (!d) return null;
  const rows = pathRows(hist);
  const worst = pathWorst(rows);
  return (
    <>
      <h3>Chemin de service vu du poste <span className="muted" style={{ textTransform: "none", letterSpacing: 0 }}>· sonde path-probe du {when(latest.at)} · <T tone={pathTone(d.summary?.state)}>{d.summary?.state || "ok"}</T>{d.rotated_to ? ` · connexion activée : ${d.rotated_to}` : ""}</span></h3>
      {d.error ? <p className="muted">⚠️ {d.error}</p> : (
        <div className="hub-table-scroll">
          <table>
            <thead><tr><th>Chemin</th><th>Adresse / bail</th><th>Passerelle</th><th>DNS distribués</th><th>DNS publics</th><th>HTTP</th><th>HTTPS</th><th>État</th></tr></thead>
            <tbody>{(d.paths || []).map((p, i) => (
              <tr key={(p.iface || "") + i}>
                <td><strong>{pathLabel(p)}</strong>{p.iface && <span className="muted"> · {p.iface}</span>}{p.ssid && p.connection && <span className="muted"> · {p.connection}</span>}</td>
                <td>{p.up_error ? <T tone="bad" title={p.up_error}>activation échouée</T> : p.ip ? <><code>{p.ip}/{p.prefix}</code> {p.static ? <span className="muted">statique</span> : p.dhcp ? <span className="muted" title={`serveur DHCP ${p.dhcp.server || "?"}`}>bail {age(p.dhcp.age_s)}{p.dhcp.lease_s ? ` / ${age(p.dhcp.lease_s)}` : ""}</span> : null}</> : <T tone="bad">aucune adresse</T>}</td>
                <td>{p.gw_ping && p.gw_ping.sent ? <><code>{p.gateway}</code> <T tone={p.gw_ping.received ? pctTone(p.gw_ping.avg_ms, 50, 200) : "bad"}>{p.gw_ping.received ? fmt(p.gw_ping.avg_ms, " ms", 1) : "injoignable"}</T>{p.gw_ping.loss_pct > 0 && <T tone={pctTone(p.gw_ping.loss_pct, 5, 50)}> {fmt(p.gw_ping.loss_pct, " % pertes")}</T>}</> : <span className="muted">{p.gateway || "—"}</span>}</td>
                <td><Dns list={p.dns} /></td>
                <td><Dns list={p.dns_public} /></td>
                <td><Web h={p.http} /></td>
                <td><Web h={p.https} /></td>
                <td><T tone={pathTone(p.summary?.state)}>{p.summary?.state || "ok"}</T></td>
              </tr>
            ))}</tbody>
          </table>
        </div>
      )}
      {(d.alerts || []).length > 0 && (
        <ul style={{ margin: "6px 0" }}>
          {d.alerts.map((a, i) => <li key={i}><T tone={pathTone(a.severity)}>{a.severity}</T> {a.message}</li>)}
        </ul>
      )}
      {rows.length > 1 && (
        <details style={{ marginTop: 6 }}>
          <summary className="muted">Historique ({rows.length} lignes) — {worst.map((w) => `${w.label} : ${w.samples} passages, ${w.critical} critique(s), ${w.noIp} sans adresse, ${w.dnsFail} avec un DNS muet, ${w.httpFail} HTTP en échec, pire HTTP ${fmt(w.httpMs, " ms")}`).join(" · ")}</summary>
          <div className="hub-table-scroll">
            <table>
              <thead><tr><th>Heure</th><th>Chemin</th><th>Adresse</th><th>Passerelle ms</th><th>Pertes %</th><th>DNS ok</th><th>DNS ms</th><th>Publics ok</th><th>HTTP ms</th><th>HTTPS ms</th><th>État</th></tr></thead>
              <tbody>{rows.map((r, i) => (
                <tr key={r.at + r.label + i}>
                  <td className="muted">{when(r.at)}</td>
                  <td>{r.label}</td>
                  <td>{r.ip ? <code style={{ fontSize: 11 }}>{r.ip}</code> : <T tone="bad">aucune</T>}</td>
                  <td><T tone={pctTone(r.gwMs, 50, 200)}>{fmt(r.gwMs, "", 1)}</T></td>
                  <td><T tone={pctTone(r.gwLoss, 5, 50)}>{fmt(r.gwLoss, "", 0)}</T></td>
                  <td><T tone={r.dnsTotal ? (r.dnsOk === r.dnsTotal ? "good" : r.dnsOk ? "warn" : "bad") : "neutral"}>{r.dnsTotal ? `${r.dnsOk}/${r.dnsTotal}` : "—"}</T></td>
                  <td><T tone={pctTone(r.dnsMs, 500, 2000)}>{fmt(r.dnsMs, "", 0)}</T></td>
                  <td>{r.pubTotal ? `${r.pubOk}/${r.pubTotal}` : "—"}</td>
                  <td>{r.portal ? <T tone="bad">intercepté</T> : r.httpOk === false ? <T tone="bad">échec</T> : <T tone={pctTone(r.httpMs, 3000, 8000)}>{fmt(r.httpMs, "", 0)}</T>}</td>
                  <td>{r.httpsOk === false ? <T tone="bad">échec</T> : <T tone={pctTone(r.httpsMs, 3000, 8000)}>{fmt(r.httpsMs, "", 0)}</T>}</td>
                  <td><T tone={pathTone(r.state)}>{r.state}{r.alerts ? ` (${r.alerts})` : ""}</T></td>
                </tr>
              ))}</tbody>
            </table>
          </div>
          {rows.length >= limit && <button type="button" className="secondary" onClick={() => setLimit(limit + 120)}>Plus d'historique</button>}
        </details>
      )}
    </>
  );
}
