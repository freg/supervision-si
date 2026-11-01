// #868 : bouton « ping » à côté d'une IP du hub -- test de connectivité rapide DEPUIS LE HUB
// (API centrale si-agent-api : ICMP puis repli TCP sur 22/443/80/3389/8006/161).
// Usage : <IpPing ip="192.0.2.4" /> (affiche l'IP + le bouton) ou <IpPing ip={x} bare /> (bouton seul).
import { useState } from "react";
import OsActions from "./OsActions.jsx";   // #880 : « ⚙ OS » à côté de chaque IP (désactivable : os={false})

const API = import.meta.env.VITE_SI_AGENT_API_BASE_URL || "";

export async function pingHosts(hosts) {
  try {
    const r = await fetch(`${API}/ping`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ hosts }) });
    const d = await r.json();
    return Array.isArray(d?.results) ? d.results : [];
  } catch {
    return [];
  }
}

export function pingTitle(r) {
  if (!r) return "Tester la connectivité depuis le hub";
  if (r.error) return `${r.host} : ${r.error}`;
  const parts = [`${r.host}${r.ip && r.ip !== r.host ? ` (${r.ip})` : ""}`];
  if (r.icmp) parts.push(r.icmp.ok ? `ICMP ${r.icmp.rtt_ms} ms` : `ICMP ${r.icmp.ok === false ? `sans réponse (perte ${r.icmp.loss_pct ?? 100} %)` : r.icmp.error || "indisponible"}`);
  if (r.tcp) parts.push(r.tcp.ok ? (r.tcp.port ? `TCP ${r.tcp.port} ouvert ${r.tcp.rtt_ms} ms` : r.tcp.note) : `TCP ${r.tcp.ports.join("/")} sans réponse`);
  parts.push(`testé depuis le hub à ${(r.at || "").slice(11, 19)}`);
  return parts.join(" · ");
}

export function PingResult({ r }) {
  if (!r) return null;
  const ok = r.ok;
  const style = { fontSize: 11, padding: "0 5px", borderRadius: 3, marginLeft: 4, whiteSpace: "nowrap",
    color: ok ? "var(--ok)" : "var(--danger)", background: ok ? "var(--ok-bg)" : "var(--danger-bg)" };
  const txt = ok ? `✓ ${r.rtt_ms != null ? `${r.rtt_ms} ms` : "joignable"}${r.via && r.via !== "icmp" ? ` (${r.via})` : ""}` : `✗ ${r.state || "injoignable"}`;
  return <span style={style} title={pingTitle(r)}>{txt}</span>;
}

export default function IpPing({ ip, bare = false, children, os = true, label }) {
  const [busy, setBusy] = useState(false);
  const [res, setRes] = useState(null);
  if (!ip) return children ?? (bare ? null : <span className="muted">—</span>);
  const run = async (e) => {
    e.stopPropagation();
    e.preventDefault();
    setBusy(true);
    const [r] = await pingHosts([ip]);
    setRes(r || { host: ip, ok: false, state: "erreur", error: "API centrale injoignable" });
    setBusy(false);
  };
  return (
    <span style={{ whiteSpace: "nowrap" }}>
      {!bare && (children ?? <code>{ip}</code>)}
      <button type="button" className="secondary" onClick={run} disabled={busy} title={pingTitle(res)}
        style={{ fontSize: 10, padding: "0 5px", marginLeft: 4, lineHeight: "16px", minHeight: 0 }}>
        {busy ? "…" : "ping"}
      </button>
      <PingResult r={res} />
      {os && <OsActions label={label || ip} ip={ip} />}
    </span>
  );
}
