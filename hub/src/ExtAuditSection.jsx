// Audit extérieur (livraison #687) : sur un agent « point d'observation »
// (CT/VM chez l'hébergeur, audit_enabled), lance un contrôle NON INTRUSIF de nos
// applications en ligne -- ports exposés, TLS, en-têtes de sécurité, redirection
// https -- limité à la liste blanche du central (SI_AGENT_AUDIT_ALLOWED).
// Résultat : dernière mesure `ext-audit`, constats par gravité.
import { useState } from "react";
import { sendCommand } from "./siAgentClient.js";

const SEV = { critical: ["bad", "critique"], warning: ["warn", "avertissement"], info: ["neutral", "info"] };

export function parseTargets(text) {
  return String(text || "").split(/\r?\n/).map((l) => l.trim()).filter((l) => l && !l.startsWith("#")).map((l) => {
    const [host, ports] = l.split(/\s+/);
    const t = { host: host.toLowerCase() };
    if (ports) t.ports = ports.split(",").map((p) => parseInt(p, 10)).filter((p) => p > 0 && p < 65536);
    return t;
  });
}

export default function ExtAuditSection({ apiBase, agentId, detail }) {
  const enabled = detail?.latest?.inventory?.data?.audit_enabled;
  const last = detail?.latest?.["ext-audit"];
  const [text, setText] = useState("");
  const [msg, setMsg] = useState(null);
  const [busy, setBusy] = useState(false);
  if (!enabled && !last) return null;
  const launch = async () => {
    const targets = parseTargets(text);
    if (!targets.length) return;
    setBusy(true); setMsg(null);
    try { await sendCommand(apiBase, agentId, "ext_audit", { targets }); setMsg("Audit envoyé : résultat ici à la fin (quelques minutes)."); }
    catch (e) { setMsg(`Refusé : ${e.message}`); }
    setBusy(false);
  };
  return (
    <>
      <h3 style={{ marginTop: 12 }}>Audit extérieur {last ? <span className="muted" style={{ textTransform: "none", letterSpacing: 0 }}>· dernier du {new Date(last.at).toLocaleString("fr-FR")} · {last.data?.summary?.critical ?? 0} critique(s), {last.data?.summary?.warning ?? 0} avertissement(s)</span> : null}</h3>
      {enabled && (
        <div style={{ display: "flex", gap: 8, alignItems: "flex-start", flexWrap: "wrap" }}>
          <textarea rows={3} style={{ minWidth: 320 }} value={text} onChange={(e) => setText(e.target.value)} placeholder={"app.exemple.fr\nportail.exemple.fr 443,8443"} />
          <button type="button" className="secondary" disabled={busy || !text.trim()} onClick={launch}>{busy ? "⏳…" : "Lancer l'audit"}</button>
          <div className="muted" style={{ fontSize: 12, maxWidth: 520 }}>Une cible par ligne, ports facultatifs (sinon une courte liste usuelle). Contrôle non intrusif : connexions TCP, poignée de main TLS, requête HEAD. Le central refuse toute cible hors de sa liste blanche (<code>SI_AGENT_AUDIT_ALLOWED</code>).</div>
        </div>
      )}
      {msg && <p className="muted">{msg}</p>}
      {last && (last.data?.targets || []).map((t) => (
        <details key={t.host} open={(t.score?.critical || 0) + (t.score?.warning || 0) > 0}>
          <summary><strong>{t.host}</strong> <span className="muted">{(t.addresses || []).join(", ")} · ports ouverts : {Object.entries(t.ports || {}).filter(([, s]) => s === "open").map(([p]) => p).join(", ") || "aucun"}{t.tls?.not_after ? ` · certificat jusqu'au ${t.tls.not_after}` : ""}{t.tls?.version ? ` · ${t.tls.version}` : ""}</span></summary>
          {(t.findings || []).length === 0 ? <p className="muted">Aucun constat.</p> : (
            <ul>{t.findings.map((f, i) => <li key={i}><span className={`np-tone ${SEV[f.severity]?.[0] || "neutral"}`}>{SEV[f.severity]?.[1] || f.severity}</span> {f.message}</li>)}</ul>
          )}
        </details>
      ))}
    </>
  );
}
