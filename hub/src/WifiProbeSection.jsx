// Section « Wi-Fi vu du poste » de la fiche agent (#525) : dernière mesure de
// la sonde wifi-probe (lien, canal, chemin, voisinage, constats) et
// historique des derniers passages pour repérer les créneaux dégradés.
import { useEffect, useState } from "react";
import { fetchAgentMeasurements } from "./siAgentClient.js";
import { wifiRows, wifiWorst, wifiTone, rssiTone, pctTone, fmt } from "./wifiLib.js";

function T({ tone, children, title }) {
  return <span className={`np-tone ${tone || "neutral"}`} title={title}>{children}</span>;
}

export default function WifiProbeSection({ apiBase, agentId, latest, when }) {
  const [hist, setHist] = useState([]);
  const [limit, setLimit] = useState(60);
  useEffect(() => {
    let alive = true;
    fetchAgentMeasurements(apiBase, agentId, { task: "plugin:wifi-probe", limit }).then((m) => { if (alive) setHist(m); }).catch(() => {});
    return () => { alive = false; };
  }, [apiBase, agentId, limit, latest?.at]);
  const d = latest?.data;
  if (!d) return null;
  const l = d.link || {};
  const rows = wifiRows(hist);
  const worst = wifiWorst(rows);
  const alerts = d.alerts || [];
  const kv = (label, body) => <div className="sa-wide"><span className="muted">{label}</span><span>{body}</span></div>;
  return (
    <>
      <h3>Wi-Fi vu du poste <span className="muted" style={{ textTransform: "none", letterSpacing: 0 }}>· sonde wifi-probe du {when(latest.at)} · <T tone={wifiTone(d.summary?.state)}>{d.summary?.state || "ok"}</T></span></h3>
      {d.error ? <p className="muted">⚠️ {d.error}</p> : (
        <>
          {!l.connected ? <p><T tone="bad">non associé</T> <span className="muted">— l'interface {d.iface || "Wi-Fi"} n'est rattachée à aucune borne : aucune mesure d'expérience possible.</span></p> : (
            <div className="sa-kv">
              {kv("Borne", <><code>{l.bssid}</code> · {l.ssid} · canal {l.channel} ({l.band}, {l.freq} MHz)</>)}
              {kv("Signal", <><T tone={rssiTone(l.signal_dbm)}>{fmt(l.signal_dbm, " dBm")}</T>{d.station?.signal_avg_dbm != null && <span className="muted"> · moyenne {fmt(d.station.signal_avg_dbm, " dBm")}</span>}{d.channel?.noise_dbm != null && <span className="muted"> · bruit {d.channel.noise_dbm} dBm</span>}</>)}
              {kv("Débit négocié", <>↑ {fmt(l.tx_mbit, " Mbit/s")} · ↓ {fmt(l.rx_mbit, " Mbit/s")}{l.tx_mcs && <span className="muted"> · {l.tx_mcs}</span>}</>)}
              {kv("Retransmissions", <><T tone={pctTone(d.rates?.retry_pct, 15, 30)}>{fmt(d.rates?.retry_pct, " %", 1)}</T>{d.rates?.failed_pct != null && <span className="muted"> · échecs {fmt(d.rates.failed_pct, " %", 2)}</span>}{d.rates?.window_packets != null && <span className="muted"> · sur {d.rates.window_packets} trames{d.rates.delta ? " depuis le passage précédent" : " (cumul)"}</span>}</>)}
              {kv("Occupation canal", d.channel ? <><T tone={pctTone(d.channel.busy_pct, 60, 80)}>{fmt(d.channel.busy_pct, " %", 1)}</T><span className="muted"> · par d'autres {fmt(d.channel.other_pct, " %", 1)} · nous ↑{fmt(d.channel.tx_pct, " %", 0)} ↓{fmt(d.channel.rx_pct, " %", 0)}{d.channel.delta ? "" : " (cumul)"}</span></> : <span className="muted">non fourni par le pilote Wi-Fi (survey vide){d.station?.tx_duration_us != null ? ` · temps d'antenne du poste : ↑${Math.round(d.station.tx_duration_us / 1000)} ms ↓${Math.round((d.station.rx_duration_us || 0) / 1000)} ms cumulés` : ""}</span>)}
              {kv(`Chemin (${d.ping?.target || "passerelle"})`, d.ping && d.ping.sent ? <>latence {fmt(d.ping.avg_ms, " ms", 1)} · gigue <T tone={pctTone(d.ping.jitter_ms, 30, 60)}>{fmt(d.ping.jitter_ms, " ms", 1)}</T> · pertes <T tone={pctTone(d.ping.loss_pct, 1, 5)}>{fmt(d.ping.loss_pct, " %", 1)}</T></> : <span className="muted">— (pas de passerelle Wi-Fi connue)</span>)}
              {kv("Flux UDP type cast", d.iperf ? (d.iperf.error ? <span className="muted">{d.iperf.error}</span> : <>{fmt(d.iperf.mbit, " Mbit/s", 1)} · gigue {fmt(d.iperf.jitter_ms, " ms", 1)} · pertes {fmt(d.iperf.loss_pct, " %", 2)} <span className="muted">(vers {d.iperf.server})</span></>) : <span className="muted">non configuré (argument <code>--iperf HOTE</code> de la sonde)</span>)}
              {d.neighbourhood?.our_bss && kv("Notre borne (balises)", <>{d.neighbourhood.our_bss.stations ?? "?"} stations · utilisation annoncée <T tone={pctTone(d.neighbourhood.our_bss.utilisation_pct, 60, 80)}>{fmt(d.neighbourhood.our_bss.utilisation_pct, " %", 0)}</T></>)}
              {kv("Voisinage", d.neighbourhood && !d.neighbourhood.error ? <>{d.neighbourhood.bss_count} BSS (SSID × bornes) · canaux {Object.entries(d.neighbourhood.channels || {}).map(([c, n]) => `${c}×${n}`).join(", ")}{d.neighbourhood.co_channel_radios != null && <> · <T tone={d.neighbourhood.co_channel_radios >= 3 ? "warn" : "neutral"}>{d.neighbourhood.co_channel_radios} autres bornes co-canal</T> <span className="muted">({d.neighbourhood.co_channel_bss} BSS)</span></>}{d.neighbourhood.co_channel?.length > 0 && <span className="muted"> · {d.neighbourhood.co_channel.map((b) => `${b.ssid || "?"} ${fmt(b.signal_dbm, " dBm")}`).join(", ")}</span>}{d.neighbourhood.same_ssid?.length > 0 && <span className="muted"> · même SSID : {d.neighbourhood.same_ssid.map((b) => `canal ${b.channel} ${fmt(b.signal_dbm, " dBm")}${b.stations != null ? ` (${b.stations} st.)` : ""}`).join(", ")}</span>}</> : <span className="muted">—</span>)}
            </div>
          )}
          {alerts.length > 0 && (
            <ul style={{ margin: "6px 0" }}>
              {alerts.map((a, i) => <li key={i}><T tone={wifiTone(a.severity)}>{a.severity}</T> {a.message}</li>)}
            </ul>
          )}
          {rows.length > 1 && (
            <details style={{ marginTop: 6 }}>
              <summary className="muted">Historique ({rows.length} passages{worst.disconnected ? `, ${worst.disconnected} non associé(s)` : ""}) — pires : signal {fmt(worst.rssi?.rssi, " dBm")}, retrans. {fmt(worst.retry?.retry, " %", 1)}, occupation {fmt(worst.busy?.busy, " %", 0)}, gigue {fmt(worst.jitter?.jitter, " ms", 1)}, pertes {fmt(worst.loss?.loss, " %", 1)}{worst.bssids.length > 1 ? ` · ${worst.bssids.length} bornes utilisées` : ""}</summary>
              <div className="hub-table-scroll">
                <table>
                  <thead><tr><th>Heure</th><th>Borne</th><th>Canal</th><th>Signal</th><th>↑ Mbit/s</th><th>Retrans. %</th><th>Occup. %</th><th>Latence ms</th><th>Gigue ms</th><th>Pertes %</th><th>Stations</th><th>État</th></tr></thead>
                  <tbody>{rows.map((r) => (
                    <tr key={r.at}>
                      <td className="muted">{when(r.at)}</td>
                      <td>{r.connected ? <code style={{ fontSize: 11 }}>{r.bssid}</code> : <T tone="bad">non associé</T>}</td>
                      <td>{r.channel ?? "—"}</td>
                      <td><T tone={rssiTone(r.rssi)}>{fmt(r.rssi)}</T></td>
                      <td>{fmt(r.tx)}</td>
                      <td><T tone={pctTone(r.retry, 15, 30)}>{fmt(r.retry, "", 1)}</T></td>
                      <td><T tone={pctTone(r.busy, 60, 80)}>{fmt(r.busy, "", 0)}</T></td>
                      <td>{fmt(r.latency, "", 1)}</td>
                      <td><T tone={pctTone(r.jitter, 30, 60)}>{fmt(r.jitter, "", 1)}</T></td>
                      <td><T tone={pctTone(r.loss, 1, 5)}>{fmt(r.loss, "", 1)}</T></td>
                      <td>{fmt(r.stations)}</td>
                      <td><T tone={wifiTone(r.state)}>{r.state}{r.alerts ? ` (${r.alerts})` : ""}</T></td>
                    </tr>
                  ))}</tbody>
                </table>
              </div>
              {rows.length >= limit && <button type="button" className="secondary" onClick={() => setLimit(limit + 120)}>Plus d'historique</button>}
            </details>
          )}
        </>
      )}
    </>
  );
}
