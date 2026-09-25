// Audit d'application web (livraison #617) : (1) section de la fiche agent --
// détail par URL, décomposition DNS / TCP / TLS / premier octet / total,
// sous-ressources en échec ; (2) onglet « Audit web » de la tuile -- matrice
// URL × poste pour voir d'un coup d'œil si le défaut est sur un poste, sur
// un segment, ou sur l'application elle-même. Filtre début de mot.
import { useCallback, useEffect, useState } from "react";
import { fetchWebAudit } from "./siAgentClient.js";

function Tone({ tone, children, title }) { return <span className={`np-tone ${tone || "neutral"}`} title={title}>{children}</span>; }
const toneOf = (state) => (state === "critical" ? "bad" : state === "warning" ? "warn" : state === "ok" ? "good" : "neutral");
const ms = (v) => (v == null ? "—" : v >= 1000 ? `${(v / 1000).toFixed(1)} s` : `${Math.round(v)} ms`);
const FINDING_LABELS = {
  "dns-failed": "DNS en échec", "connect-failed": "connexion impossible", "tls-failed": "TLS en échec", "http-failed": "HTTP en échec",
  "http-error": "erreur serveur", "http-client-error": "erreur client (4xx)", "slow-ttfb": "premier octet lent", "slow-total": "page lente",
  "sub-errors": "sous-ressources en échec", "sub-slow": "sous-ressources lentes", "cert-expiring": "certificat bientôt expiré",
  "redirect-chain": "chaîne de redirections", "empty-body": "réponse vide", "mixed-content": "contenu mixte",
};
export const findingLabel = (c) => FINDING_LABELS[c] || c;

export function WebAuditSection({ latest, when }) {
  const data = latest?.data || {};
  const [open, setOpen] = useState(null);
  if (!latest) return null;
  return (
    <>
      <h3>Audit d'application web <span className="muted" style={{ textTransform: "none", letterSpacing: 0 }}>· sonde web-audit du {when(latest.at)}{data.summary && <> · {data.summary.ok} ok, {data.summary.warning} à surveiller, {data.summary.critical} en défaut</>}</span></h3>
      {data.error && <p style={{ color: "var(--danger)" }}>{data.error}</p>}
      {(data.urls || []).length === 0 && !data.error && <p className="muted">Aucune URL configurée : renseigner <code>--urls</code> dans le catalogue (sonde web-audit) ou <code>web-audit.txt</code> dans le dossier de l'agent.</p>}
      <div className="hub-table-scroll">
        <table>
          <thead><tr><th>URL</th><th>État</th><th>Code</th><th>DNS</th><th>TCP</th><th>TLS</th><th>1er octet</th><th>Total</th><th>Sous-ressources</th><th>Constats</th></tr></thead>
          <tbody>
            {(data.urls || []).map((u) => {
              const m = u.main || {};
              const bad = (u.subresources || []).filter((s) => s.error || (s.status || 0) >= 400);
              return (
                <>
                  <tr key={u.url} style={{ cursor: "pointer" }} onClick={() => setOpen(open === u.url ? null : u.url)}>
                    <td><b>{u.url}</b>{u.title && <span className="muted"> · {u.title}</span>}{u.final_url && u.final_url !== u.url && <div className="muted" style={{ fontSize: 12 }}>→ {u.final_url}</div>}</td>
                    <td><Tone tone={toneOf(u.state)}>{u.state}</Tone></td>
                    <td>{m.status ?? <span className="muted">—</span>}</td>
                    <td>{ms(m.dns_ms)}</td><td>{ms(m.connect_ms)}</td><td>{m.tls ? <span title={`${m.tls.version} · certificat ${m.tls.cert_days_left} j · ${m.tls.issuer || ""}`}>{ms(m.tls_ms)}</span> : <span className="muted">—</span>}</td>
                    <td>{ms(m.ttfb_ms)}</td><td>{ms(m.total_ms)}{m.bytes ? <span className="muted"> · {Math.round(m.bytes / 1024)} Ko</span> : null}</td>
                    <td>{(u.subresources || []).length === 0 ? <span className="muted">—</span> : <>{(u.subresources || []).length}{bad.length > 0 && <> · <Tone tone="bad">{bad.length} en échec</Tone></>}</>}</td>
                    <td>{(u.findings || []).length === 0 ? <span className="muted">aucun</span> : u.findings.map((f, i) => <Tone key={i} tone={f.severity === "critical" ? "bad" : f.severity === "warning" ? "warn" : "neutral"} title={f.detail}>{findingLabel(f.code)}</Tone>)}</td>
                  </tr>
                  {open === u.url && (
                    <tr key={`${u.url}-d`}><td colSpan={10} style={{ background: "var(--panel-2, transparent)" }}>
                      {m.error && <div style={{ color: "var(--danger)" }}>{m.error}</div>}
                      {m.addresses?.length > 0 && <div className="muted" style={{ fontSize: 12 }}>adresses : {m.addresses.join(", ")} · serveur : {m.server || "?"} · type : {m.content_type || "?"}</div>}
                      {(u.chain || []).length > 1 && <div className="muted" style={{ fontSize: 12 }}>redirections : {u.chain.map((c) => `${c.status ?? "?"} ${c.url}`).join(" → ")}</div>}
                      {(u.subresources || []).length > 0 && (
                        <table style={{ marginTop: 6 }}><thead><tr><th>Type</th><th>Ressource</th><th>Code</th><th>Durée</th><th>Erreur</th></tr></thead>
                          <tbody>{u.subresources.map((s, i) => <tr key={i} style={s.error || (s.status || 0) >= 400 ? { color: "var(--danger)" } : undefined}><td>{s.tag}</td><td><code style={{ fontSize: 12, wordBreak: "break-all" }}>{s.url}</code></td><td>{s.status ?? "—"}</td><td>{ms(s.ms)}</td><td>{s.error || ""}</td></tr>)}</tbody></table>
                      )}
                      {(u.findings || []).map((f, i) => <div key={i} style={{ fontSize: 12 }}><b>{findingLabel(f.code)}</b> — {f.detail}</div>)}
                    </td></tr>
                  )}
                </>
              );
            })}
          </tbody>
        </table>
      </div>
    </>
  );
}

export default function WebAuditTab({ base, fleet, when }) {
  const [data, setData] = useState(null);
  const [site, setSite] = useState("");
  const [q, setQ] = useState("");
  const [err, setErr] = useState(null);
  const load = useCallback(() => fetchWebAudit(base, site).then((d) => { setData(d); setErr(null); }).catch((e) => setErr(e.message)), [base, site]);
  useEffect(() => { load(); const t = setInterval(load, 60000); return () => clearInterval(t); }, [load]);
  const sites = [...new Set((fleet || []).map((a) => a.site).filter(Boolean))].sort();
  if (err) return <p style={{ color: "var(--danger)" }}>{err}</p>;
  if (!data) return <p className="muted">chargement…</p>;
  const qq = q.trim().toLowerCase();
  const urls = (data.urls || []).filter((u) => !qq || u.toLowerCase().split(/[\s./:-]+/).some((w) => w.startsWith(qq)));
  const audits = (data.audits || []).filter((a) => !qq || [a.agent_id, a.hostname].some((v) => String(v || "").toLowerCase().startsWith(qq)) || urls.length);
  const cell = (a, url) => {
    const u = (a.urls || []).find((x) => x.url === url);
    if (!u) return <td key={url} className="muted">—</td>;
    return (
      <td key={url} title={[u.error, ...(u.findings || []).map((f) => `${findingLabel(f.code)} : ${f.detail}`)].filter(Boolean).join("\n")}>
        <Tone tone={toneOf(u.state)}>{u.status ?? "✗"}</Tone> <span className="muted">{ms(u.ttfb_ms)}</span>{u.sub_failed > 0 && <span style={{ color: "var(--danger)" }}> · {u.sub_failed}/{u.sub_total}</span>}
      </td>
    );
  };
  return (
    <div className="hub-card lic-card">
      <p className="muted" style={{ marginTop: 0 }}>Chaque cellule : code HTTP, délai du premier octet, sous-ressources en échec / total, vus <b>depuis le poste</b>. Une colonne rouge = l'application ; une ligne rouge = le poste ou son segment. Les URL se règlent dans le catalogue (sonde <code>web-audit</code>, argument <code>--urls</code>) ou par poste dans <code>web-audit.txt</code>.</p>
      <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 8, flexWrap: "wrap" }}>
        <select value={site} onChange={(e) => setSite(e.target.value)}><option value="">— tous les sites —</option>{sites.map((s) => <option key={s} value={s}>{s}</option>)}</select>
        <input placeholder="Filtrer (poste, URL)" value={q} onChange={(e) => setQ(e.target.value)} style={{ minWidth: 220 }} />
        <span className="muted">{audits.length} poste(s) · {urls.length} URL</span>
        <button type="button" className="secondary" onClick={load}>Actualiser</button>
      </div>
      {audits.length === 0 ? <p className="muted">Aucun audit reçu : affecter la sonde <code>web-audit</code> aux postes (onglet Catalogue de sondes → affecter) avec ses URL.</p> : (
        <div className="hub-table-scroll">
          <table>
            <thead><tr><th>Poste</th><th>Site</th><th>Relevé</th>{urls.map((u) => <th key={u} title={u}>{u.replace(/^https?:\/\//, "").slice(0, 40)}</th>)}</tr></thead>
            <tbody>
              {audits.map((a) => (
                <tr key={a.agent_id}>
                  <td><b>{a.hostname || a.agent_id}</b>{a.error && <div style={{ color: "var(--danger)", fontSize: 12 }}>{a.error}</div>}</td>
                  <td>{a.site}</td><td className="muted">{when(a.at)}</td>
                  {urls.map((u) => cell(a, u))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
