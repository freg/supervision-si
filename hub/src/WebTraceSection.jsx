// Trace réseau du poste (livraison #618) -- section de la fiche agent : ce que
// le poste a fait sur le réseau pendant la capture (sonde web-trace) : hôtes
// (nom par SNI / Host / DNS), protocole, connexions sans réponse, RST,
// retransmissions, RTT ; DNS ; requêtes HTTP en clair ; poignées TLS ; constats.
import { useState } from "react";

function Tone({ tone, children, title }) { return <span className={`np-tone ${tone || "neutral"}`} title={title}>{children}</span>; }
const ms = (v) => (v == null ? "—" : v >= 1000 ? `${(v / 1000).toFixed(1)} s` : `${Math.round(v)} ms`);
const kb = (b) => (b == null ? "—" : b >= 1048576 ? `${(b / 1048576).toFixed(1)} Mo` : `${Math.round(b / 1024)} Ko`);
const LABELS = { "connect-failed": "connexions sans réponse", "connect-partial": "connexions partiellement sans réponse", "slow-rtt": "RTT élevé", "retransmissions": "retransmissions",
  resets: "RST", "dns-failures": "DNS en échec", "dns-unanswered": "DNS sans réponse", "slow-dns": "DNS lent", "http-error": "erreur serveur HTTP", "http-client-error": "erreur client HTTP", "slow-tls": "TLS lent" };

export default function WebTraceSection({ latest, when }) {
  const d = latest?.data || {};
  const [q, setQ] = useState("");
  if (!latest) return null;
  const qq = q.trim().toLowerCase();
  const hosts = (d.hosts || []).filter((h) => !qq || [h.name, h.ip, h.proto, ...(h.names || [])].some((v) => String(v || "").toLowerCase().split(/[\s.:-]+/).some((w) => w.startsWith(qq))));
  return (
    <>
      <h3>Trace réseau du poste <span className="muted" style={{ textTransform: "none", letterSpacing: 0 }}>· sonde web-trace du {when(latest.at)}{d.tool && <> · {d.tool}, {d.seconds} s, {d.packets} paquets{d.ipv6_packets > 0 && <>, {d.ipv6_packets} IPv6 non décodés</>}</>}{d.summary?.state && <> · <Tone tone={d.summary.state === "critical" ? "bad" : d.summary.state === "warning" ? "warn" : "good"}>{d.summary.state}</Tone></>}</span></h3>
      {d.error && <p style={{ color: "var(--danger)" }}>{d.error}</p>}
      {!d.error && (
        <>
          <div className="sa-kv">
            <div className="sa-wide"><span className="muted">Constats</span>{(d.findings || []).length === 0 ? <span className="muted">aucun</span> : d.findings.map((f, i) => <Tone key={i} tone={f.severity === "critical" ? "bad" : f.severity === "warning" ? "warn" : "neutral"} title={f.detail}>{LABELS[f.code] || f.code} — {f.detail}</Tone>)}</div>
            <div><span className="muted">Protocoles</span>{Object.entries(d.protocols || {}).map(([k, v]) => <span key={k} className="na-chip">{k} {v}</span>)}</div>
            <div><span className="muted">DNS</span>{d.dns ? <>{d.dns.queries} requête(s), {d.dns.responses} réponse(s){d.dns.failures > 0 && <> · <Tone tone="warn">{d.dns.failures} en échec</Tone></>}{d.dns.unanswered > 0 && <> · <Tone tone="warn">{d.dns.unanswered} sans réponse</Tone></>} · moyenne {ms(d.dns.avg_ms)}, max {ms(d.dns.max_ms)}</> : "—"}</div>
            <div><span className="muted">Poste</span>{(d.local_ips || []).join(", ") || "—"} · {d.summary?.hosts} serveur(s) · {d.summary?.http_requests} requête(s) HTTP en clair · {d.summary?.tls_handshakes} poignée(s) TLS</div>
          </div>
          <div style={{ display: "flex", gap: 8, alignItems: "center", margin: "6px 0" }}><input placeholder="Filtrer (hôte, IP, protocole)" value={q} onChange={(e) => setQ(e.target.value)} style={{ minWidth: 240 }} /><span className="muted">{hosts.length} serveur(s)</span></div>
          <div className="hub-table-scroll" style={{ maxHeight: 360, overflow: "auto" }}>
            <table>
              <thead><tr><th>Serveur</th><th>Adresse:port</th><th>Protocole</th><th>Connexions</th><th>Sans réponse</th><th>RST</th><th>Retrans.</th><th>RTT moy. / max</th><th>Volume</th></tr></thead>
              <tbody>
                {hosts.length === 0 && <tr><td colSpan={9} className="muted">aucun serveur joint pendant la capture</td></tr>}
                {hosts.map((h) => (
                  <tr key={`${h.ip}:${h.port}`} style={h.syn_failed ? { color: "var(--danger)" } : undefined}>
                    <td><b>{h.name || <span className="muted">?</span>}</b>{h.names?.length > 1 && <span className="muted"> +{h.names.length - 1}</span>}</td>
                    <td><code>{h.ip}:{h.port}</code></td><td>{h.proto}</td><td>{h.flows}</td>
                    <td>{h.syn_failed ? <Tone tone="bad">{h.syn_failed}</Tone> : 0}</td><td>{h.rst}</td><td>{h.retrans ? <Tone tone="warn">{h.retrans}</Tone> : 0}</td>
                    <td>{ms(h.rtt_ms)}{h.rtt_max_ms != null && <span className="muted"> / {ms(h.rtt_max_ms)}</span>}</td><td>{kb(h.bytes)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {(d.http || []).length > 0 && (
            <>
              <h4 style={{ margin: "10px 0 4px" }}>Requêtes HTTP en clair</h4>
              <div className="hub-table-scroll" style={{ maxHeight: 240, overflow: "auto" }}>
                <table><thead><tr><th>Hôte</th><th>Méthode</th><th>Chemin</th><th>Code</th><th>1er octet</th></tr></thead>
                  <tbody>{d.http.map((r, i) => <tr key={i} style={r.status >= 400 ? { color: "var(--danger)" } : undefined}><td>{r.host}</td><td>{r.method}</td><td><code style={{ fontSize: 12, wordBreak: "break-all" }}>{r.path}</code></td><td>{r.status}</td><td>{ms(r.ttfb_ms)}</td></tr>)}</tbody></table>
              </div>
            </>
          )}
          {(d.tls || []).length > 0 && (
            <div className="muted" style={{ fontSize: 12, marginTop: 6 }}>Poignées TLS : {d.tls.slice(0, 20).map((t, i) => <span key={i} className="na-chip">{t.sni} {ms(t.hello_ms)}</span>)}{d.tls.length > 20 && <> … ({d.tls.length})</>}</div>
          )}
        </>
      )}
    </>
  );
}
