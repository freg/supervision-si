// Serveur de messagerie (livraison #692) -- section de la fiche d'un agent
// qui porte la sonde mail-server : état, constats, verdicts Amavis, faux
// positifs probables (à libérer depuis la quarantaine), file, services.
function Tone({ tone, children }) { return <span className={`np-tone ${tone || "neutral"}`}>{children}</span>; }
const TONE = { critical: "bad", warning: "warn", ok: "good" };

export default function MailServerSection({ latest, when }) {
  if (!latest) return null;
  const d = latest.data || {};
  const log = d.log || {};
  const fps = log.false_positive_candidates || [];
  return (
    <>
      <h3 style={{ marginTop: 12 }}>Serveur de messagerie <span className="muted" style={{ textTransform: "none", letterSpacing: 0 }}>· sonde mail-server du {when(latest.at)} · fenêtre {log.window_minutes ?? "?"} min{d.summary?.state && <> · <Tone tone={TONE[d.summary.state]}>{d.summary.state}</Tone></>}</span></h3>
      {(d.alerts || []).length > 0 && (
        <ul>{d.alerts.map((a) => <li key={a.code}><Tone tone={TONE[a.severity]}>{a.severity}</Tone> {a.message}</li>)}</ul>
      )}
      <p className="muted" style={{ fontSize: 13 }}>
        Services : {Object.entries(d.services || {}).map(([k, v]) => `${k} ${v}`).join(" · ") || "—"}
        {" "}· file Postfix : {d.queue?.count ?? "?"} message(s){d.queue?.oldest_seconds ? `, le plus ancien ${Math.round(d.queue.oldest_seconds / 60)} min` : ""}
        {" "}· Amavis : {Object.entries(log.amavis || {}).map(([k, v]) => `${v} ${k}`).join(", ") || "aucun verdict"}
        {d.os?.debian && <> · Debian {d.os.debian}{d.os.eol ? ` (hors support depuis ${d.os.eol})` : ""}</>}
      </p>
      {fps.length > 0 && (
        <details open>
          <summary>Faux positifs probables ({fps.length}) — bloqués avec un score &lt; {log.fp_below}</summary>
          <table>
            <thead><tr><th>Heure</th><th>Score</th><th>Expéditeur</th><th>Destinataire(s)</th><th>Quarantaine</th></tr></thead>
            <tbody>{fps.map((f, i) => (
              <tr key={i}><td>{new Date(f.at * 1000).toLocaleString("fr-FR")}</td><td>{f.hits}</td><td>{f.from || "<>"}</td><td>{(f.to || []).join(", ")}</td><td><code>{f.quarantine || "—"}</code></td></tr>
            ))}</tbody>
          </table>
          <p className="muted" style={{ fontSize: 12 }}>À libérer depuis la quarantaine (Modoboa › Quarantaine, ou <code>amavisd-release &lt;id&gt; &lt;secret&gt;</code>) avant la purge automatique.</p>
        </details>
      )}
    </>
  );
}
