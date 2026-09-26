// Accès publics du frontal (livraison #622, item 99) -- section de la fiche de
// l'agent installé sur la VM frontale (sonde front-access) : codes, clients
// par IP publique, chemins, lenteurs, erreurs 5xx, constats.
import { useState } from "react";

function Tone({ tone, children, title }) { return <span className={`np-tone ${tone || "neutral"}`} title={title}>{children}</span>; }
const ms = (v) => (v == null ? "—" : v >= 1000 ? `${(v / 1000).toFixed(1)} s` : `${Math.round(v)} ms`);
const LABELS = { "hub-unreachable": "hub injoignable (5xx)", "auth-refused-burst": "refus répétés (401/403)", "scan-404": "exploration automatique (404)", "slow-backend": "réponses lentes" };

export default function FrontAccessSection({ latest, when }) {
  const d = latest?.data || {};
  const [q, setQ] = useState("");
  if (!latest) return null;
  const st = d.status || {};
  const qq = q.trim().toLowerCase();
  const clients = (d.clients || []).filter((c) => !qq || [c.ip, c.ua, c.top_path].some((v) => String(v || "").toLowerCase().split(/[\s./:-]+/).some((w) => w.startsWith(qq))));
  return (
    <>
      <h3>Accès publics (frontal) <span className="muted" style={{ textTransform: "none", letterSpacing: 0 }}>· sonde front-access du {when(latest.at)} · fenêtre {d.window_minutes} min · {d.total} requête(s), {d.distinct_clients} client(s){d.summary?.state && <> · <Tone tone={d.summary.state === "critical" ? "bad" : d.summary.state === "warning" ? "warn" : "good"}>{d.summary.state}</Tone></>}</span></h3>
      {d.error && <p style={{ color: "var(--danger)" }}>{d.error}</p>}
      {!d.error && (
        <>
          <div className="sa-kv">
            <div className="sa-wide"><span className="muted">Constats</span>{(d.findings || []).length === 0 ? <span className="muted">aucun</span> : d.findings.map((f, i) => <Tone key={i} tone={f.severity === "critical" ? "bad" : f.severity === "warning" ? "warn" : "neutral"} title={f.detail}>{LABELS[f.code] || f.code} — {f.detail}</Tone>)}</div>
            <div><span className="muted">Codes</span>{["2xx", "3xx", "401", "403", "404", "4xx", "5xx"].filter((k) => st[k]).map((k) => <Tone key={k} tone={k === "5xx" ? "bad" : k === "401" || k === "403" ? "warn" : k === "2xx" ? "good" : "neutral"}>{k} {st[k]}</Tone>)}{d.api_auth_refused > 0 && <span className="muted"> · {d.api_auth_refused} refus sur /api/ (jeton exigé)</span>}</div>
            <div><span className="muted">Latence</span>{d.latency?.measured ? <>moyenne {ms(d.latency.avg_ms)} · max {ms(d.latency.max_ms)} · {d.latency.measured} mesurée(s)</> : <span className="muted">non journalisée (relancer front-reverse-proxy.sh #622 pour ajouter %D)</span>}</div>
            <div className="sa-wide"><span className="muted">Chemins</span>{(d.top_paths || []).slice(0, 10).map((p) => <span key={p.path} className="na-chip"><code>{p.path}</code> {p.count}</span>)}</div>
          </div>
          <div style={{ display: "flex", gap: 8, alignItems: "center", margin: "6px 0" }}><input placeholder="Filtrer (IP, navigateur, chemin)" value={q} onChange={(e) => setQ(e.target.value)} style={{ minWidth: 240 }} /><span className="muted">{clients.length} client(s)</span></div>
          <div className="hub-table-scroll" style={{ maxHeight: 320, overflow: "auto" }}>
            <table>
              <thead><tr><th>Client (IP publique)</th><th>Requêtes</th><th>Refus 401/403</th><th>Erreurs 5xx</th><th>Volume</th><th>Navigateur</th><th>Chemin le plus demandé</th><th>Dernier accès</th></tr></thead>
              <tbody>
                {clients.length === 0 && <tr><td colSpan={8} className="muted">aucun accès dans la fenêtre</td></tr>}
                {clients.map((c) => (
                  <tr key={c.ip} style={c.errors ? { color: "var(--danger)" } : undefined}>
                    <td><code>{c.ip}</code></td><td>{c.count}</td><td>{c.auth_refused ? <Tone tone="warn">{c.auth_refused}</Tone> : 0}</td><td>{c.errors ? <Tone tone="bad">{c.errors}</Tone> : 0}</td>
                    <td>{Math.round((c.bytes || 0) / 1024)} Ko</td><td>{c.ua}</td><td><code style={{ fontSize: 12 }}>{c.top_path}</code></td><td className="muted">{c.last ? c.last.replace("T", " ") : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {(d.slow || []).length > 0 && <div className="muted" style={{ fontSize: 12, marginTop: 6 }}>Lentes : {d.slow.slice(0, 8).map((s, i) => <span key={i} className="na-chip">{s.path} {ms(s.ms)} ({s.status})</span>)}</div>}
          {(d.errors_5xx || []).length > 0 && <div style={{ fontSize: 12, marginTop: 6, color: "var(--danger)" }}>5xx : {d.errors_5xx.slice(-8).map((e, i) => <span key={i} className="na-chip">{e.at?.slice(11, 19)} {e.ip} {e.path} → {e.status}</span>)}</div>}
        </>
      )}
    </>
  );
}
