// Serveur de messagerie (livraison #692) -- section de la fiche d'un agent
// qui porte la sonde mail-server : état, constats, verdicts Amavis, faux
// positifs probables (à libérer depuis la quarantaine), file, services ;
// #708 : politiques antispam (seuils par domaine), conservation (quarantaine,
// journal), authentification des expéditeurs fréquents (DKIM aligné, SPF).
import { AutoColumns } from "./TableColumns.jsx";   // #707 : colonnes réglables
function Tone({ tone, children }) { return <span className={`np-tone ${tone || "neutral"}`}>{children}</span>; }
const TONE = { critical: "bad", warning: "warn", ok: "good" };

export default function MailServerSection({ latest, when }) {
  if (!latest) return null;
  const d = latest.data || {};
  const log = d.log || {};
  const fps = log.false_positive_candidates || [];
  const am = d.amavis || {};
  const lim = d.limits || {};
  const auth = log.sender_auth || [];
  const weak = auth.filter((a) => a.blocked && !a.authenticated).length;
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
          <AutoColumns id="MailServerSection.1"><table>
            <thead><tr><th>Heure</th><th>Score</th><th>Expéditeur</th><th>Destinataire(s)</th><th>Quarantaine</th></tr></thead>
            <tbody>{fps.map((f, i) => (
              <tr key={i}><td>{new Date(f.at * 1000).toLocaleString("fr-FR")}</td><td>{f.hits}</td><td>{f.from || "<>"}</td><td>{(f.to || []).join(", ")}</td><td><code>{f.quarantine || "—"}</code></td></tr>
            ))}</tbody>
          </table></AutoColumns>
          <p className="muted" style={{ fontSize: 12 }}>À libérer depuis la quarantaine (Modoboa › Quarantaine, ou <code>amavisd-release &lt;id&gt; &lt;secret&gt;</code>) avant la purge automatique.</p>
        </details>
      )}
      {(am.policies || []).length > 0 && (
        <details>
          <summary>Politiques antispam ({am.policies.length}){am.config?.final_spam_destiny ? ` — spam : ${am.config.final_spam_destiny}` : ""}</summary>
          <AutoColumns id="MailServerSection.policies"><table>
            <thead><tr><th>Politique</th><th>Marquage (tag2)</th><th>Blocage (kill)</th><th>Quarantaine</th><th>Domaines</th><th>Boîtes</th></tr></thead>
            <tbody>{am.policies.map((g, i) => (
              <tr key={i}><td>{g.policy || "—"}{g.lover ? " (spam accepté)" : ""}{g.bypass ? " (sans analyse)" : ""}</td><td>{g.tag2 ?? "—"}</td>
                <td>{g.kill != null && g.kill < (lim.kill_min ?? 5) ? <Tone tone="bad">{g.kill}</Tone> : g.kill ?? "—"}</td><td>{g.quarantine_to || "—"}</td>
                <td>{g.domains.join(", ") || "—"}</td><td>{g.mailboxes || ""}</td></tr>))}</tbody>
          </table></AutoColumns>
          <p className="muted" style={{ fontSize: 12 }}>Blocage (kill) : au-dessus de ce score le message n'est pas remis (quarantaine ou suppression). Sous {lim.kill_min ?? 5}, du courrier légitime est bloqué.</p>
        </details>
      )}
      {(am.retention || d.log_retention_days != null) && (
        <p className="muted" style={{ fontSize: 13 }}>
          Conservation : quarantaine récupérable sur {am.retention?.quarantine_days ?? "?"} j · historique Amavis {am.retention?.history_days ?? "?"} j ·
          journal mail {d.log_retention_days ?? "?"} j (logrotate)</p>
      )}
      {auth.length > 0 && (
        <details>
          <summary>Authentification des expéditeurs ({auth.length} domaines, dernière heure){weak ? ` — ${weak} bloqué(s) sans authentification` : ""}</summary>
          <AutoColumns id="MailServerSection.auth"><table>
            <thead><tr><th>Domaine</th><th>Messages</th><th>Bloqués</th><th>DKIM aligné</th><th>SPF</th><th>État</th></tr></thead>
            <tbody>{auth.map((a) => (
              <tr key={a.domain}><td>{a.domain}</td><td>{a.messages}</td><td>{a.blocked || ""}</td><td>{a.dkim_aligned || ""}</td>
                <td>{Object.entries(a.spf || {}).map(([k, v]) => `${k} ×${v}`).join(", ") || "—"}</td>
                <td>{a.authenticated ? <Tone tone="good">authentifié</Tone> : <Tone tone={a.blocked ? "bad" : "warn"}>non authentifié</Tone>}</td></tr>))}</tbody>
          </table></AutoColumns>
          <p className="muted" style={{ fontSize: 12 }}>Non authentifié : ni signature DKIM du domaine, ni SPF « pass ». À signaler à l'expéditeur ; une règle « adoucir » (onglet Quarantaine) évite de le bloquer en attendant.</p>
        </details>
      )}
    </>
  );
}
