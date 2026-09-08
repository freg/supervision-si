// Tuile « Bastion » (livraison #454) -- console du bastion si-proxy :
// état du relais et du shim host, sessions en cours (kill), pause /
// reprise, IP bannies (déban), journal d'audit, cibles jointes. Réservée
// aux personnes de SI_PROXY_ADMIN_USERS : chaque appel porte le jeton
// Keycloak, vérifié par le pont si-proxy-admin-api. Le bastion ne
// journalise que des métadonnées -- rien ici n'affiche un jeton ni le
// contenu d'une session.
import { useCallback, useEffect, useMemo, useState } from "react";
import { fetchProxyStatus, fetchProxyAudit, fetchProxySummary, killProxySession, disableProxy, enableProxy, unbanProxyIp } from "./siProxyClient.js";
import { KIND_LABELS, EVENT_LABELS, fmtDuration, fmtBytes, clientLabel, describeEvent, sortAudit, refusalsByPeer, headline } from "./siProxy.js";

const REFRESH_MS = 5000;

function Tone({ tone, children, title }) {
  return <span className={`np-tone ${tone || "neutral"}`} title={title}>{children}</span>;
}
const TONE = { ok: "good", warning: "warn", critical: "bad" };

function when(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString("fr-FR");
}

export default function SiProxyView({ onBack, siProxyApiBase, accessToken, username }) {
  const [status, setStatus] = useState(null);
  const [summary, setSummary] = useState(null);
  const [audit, setAudit] = useState([]);
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState(null);
  const [busy, setBusy] = useState(false);
  const [filter, setFilter] = useState("all");
  const [hours, setHours] = useState(24);

  const load = useCallback(async () => {
    if (!siProxyApiBase || !accessToken) return;
    const [st, au, su] = await Promise.all([
      fetchProxyStatus(siProxyApiBase, accessToken),
      fetchProxyAudit(siProxyApiBase, accessToken, 300),
      fetchProxySummary(siProxyApiBase, accessToken, hours),
    ]);
    if (st?.status === 401 || st?.status === 403) { setError(st.error); setStatus(null); return; }
    setError(null);
    setStatus(st);
    if (!au?.error) setAudit(au.audit);
    if (!su?.error) setSummary(su);
  }, [siProxyApiBase, accessToken, hours]);

  useEffect(() => { load(); const id = setInterval(load, REFRESH_MS); return () => clearInterval(id); }, [load]);

  const act = async (label, fn) => {
    setBusy(true);
    const r = await fn();
    setBusy(false);
    setNotice(r?.error ? `${label} : ${r.error}` : `${label} : fait`);
    load();
  };

  const head = headline(status);
  const sessions = status?.sessions || [];
  const banned = status?.banned || [];
  const rows = useMemo(() => sortAudit(audit, { only: filter, limit: 200 }), [audit, filter]);
  const refusals = useMemo(() => refusalsByPeer(audit), [audit]);

  return (
    <div className="hub-settings hub-settings-wide">
      <div className="hub-settings-topbar">
        <button className="secondary" onClick={onBack}>◀ Retour</button>
        <h1>🛡 Bastion si-proxy</h1>
        <span className="muted">réservé — connecté en tant que {username || "?"}</span>
      </div>

      {error && <p className="hub-error">{error} — cette tuile est réservée aux personnes de SI_PROXY_ADMIN_USERS ; le pont a refusé le jeton.</p>}
      {notice && <p className="muted ups-notice">{notice} <button className="secondary" onClick={() => setNotice(null)}>✕</button></p>}

      <div className="hub-card hub-settings-section">
        <p style={{ margin: 0 }}>
          <Tone tone={TONE[head.state] || "neutral"}>{head.text}</Tone>
          {status && !status.error && (
            <>
              {" · "}relais : <Tone tone="good">joignable</Tone>
              {" · "}shim host : {status.host_connected ? <Tone tone="good">connecté</Tone> : <Tone tone="bad">absent</Tone>}
              {" · "}TLS mutuel : {status.mtls ? <Tone tone="good">oui (CN {status.allow_cn?.join(", ")})</Tone> : <Tone tone="warn">non (jeton seul)</Tone>}
              {" · "}compteurs : {status.counters?.opened ?? 0} ouvertes, {status.counters?.closed ?? 0} fermées, {status.counters?.refused ?? 0} refus
            </>
          )}
        </p>
        {status && !status.error && (
          <p style={{ margin: "8px 0 0" }}>
            {status.enabled
              ? <button className="secondary" disabled={busy} onClick={() => act("Mise en pause", () => disableProxy(siProxyApiBase, accessToken))}>⏸ Mettre le bastion en pause (refuser les nouvelles sessions)</button>
              : <button className="primary" disabled={busy} onClick={() => act("Reprise", () => enableProxy(siProxyApiBase, accessToken))}>▶ Réactiver le bastion</button>}
            {" "}<button className="secondary" disabled={busy} onClick={load}>↻ Rafraîchir</button>
          </p>
        )}
      </div>

      <div className="hub-card hub-settings-section">
        <h2 style={{ margin: "0 0 6px" }}>Sessions en cours ({sessions.length})</h2>
        {sessions.length === 0 ? <p className="muted" style={{ margin: 0 }}>Aucune session ouverte.</p> : (
          <div className="hub-table-scroll">
            <table>
              <thead><tr><th>#</th><th>Type</th><th>Cible</th><th>Client</th><th>Depuis</th><th>Ouverte</th><th>Durée</th><th></th></tr></thead>
              <tbody>
                {sessions.map((s) => (
                  <tr key={s.session}>
                    <td>{s.session}</td><td>{KIND_LABELS[s.kind] || s.kind}</td><td>{s.target || <span className="muted">host</span>}</td>
                    <td>{clientLabel(s.client)}</td><td>{s.peer || "—"}</td><td>{when(s.started)}</td><td>{fmtDuration(s.duration_s)}</td>
                    <td><button className="secondary" disabled={busy} onClick={() => act(`Session ${s.session} fermée`, () => killProxySession(siProxyApiBase, accessToken, s.session))}>✕ fermer</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="hub-card hub-settings-section">
        <h2 style={{ margin: "0 0 6px" }}>Fail2ban maison — IP bannies ({banned.length})</h2>
        {banned.length === 0 ? <p className="muted" style={{ margin: 0 }}>Aucune IP bannie.</p> : (
          <ul className="sa-risks">
            {banned.map((b) => (
              <li key={b.ip}><Tone tone="bad">⛔ {b.ip}</Tone> encore {fmtDuration(b.seconds_left)}{" "}
                <button className="secondary" disabled={busy} onClick={() => act(`Déban ${b.ip}`, () => unbanProxyIp(siProxyApiBase, accessToken, b.ip))}>lever</button></li>
            ))}
          </ul>
        )}
        {refusals.length > 0 && (
          <p className="muted" style={{ margin: "6px 0 0" }}>
            Refus par IP (journal) : {refusals.slice(0, 8).map((r) => `${r.peer} ×${r.count} (${r.reasons.join(", ")})`).join(" · ")}
          </p>
        )}
      </div>

      <div className="hub-card hub-settings-section">
        <h2 style={{ margin: "0 0 6px" }}>Cibles jointes par le bastion
          {" "}<select value={hours} onChange={(e) => setHours(Number(e.target.value))}>
            <option value={24}>24 h</option><option value={168}>7 jours</option><option value={720}>30 jours</option>
          </select>
        </h2>
        {summary && (
          <p className="muted" style={{ margin: "0 0 6px" }}>
            Sur {summary.window_h} h : {summary.sessions_window} session(s), {summary.refused_window} refus
            {summary.last_session ? ` · dernière session ${when(summary.last_session.at)} (${KIND_LABELS[summary.last_session.kind] || summary.last_session.kind}${summary.last_session.target ? ` → ${summary.last_session.target}` : ""})` : ""}
            {summary.last_refused ? ` · dernier refus ${when(summary.last_refused.at)} de ${summary.last_refused.peer || "?"} (${summary.last_refused.reason})` : ""}
          </p>
        )}
        {!summary?.targets?.length ? <p className="muted" style={{ margin: 0 }}>Aucune cible jointe dans le journal.</p> : (
          <div className="hub-table-scroll">
            <table>
              <thead><tr><th>Cible</th><th>Sessions</th><th>Types</th><th>Volume</th><th>Dernière</th></tr></thead>
              <tbody>{summary.targets.map((t) => <tr key={t.target}><td>{t.target}</td><td>{t.count}</td><td>{(t.kinds || []).map((k) => KIND_LABELS[k] || k).join(", ")}</td><td>{fmtBytes(t.bytes)}</td><td>{when(t.last)}</td></tr>)}</tbody>
            </table>
          </div>
        )}
        <p className="muted" style={{ margin: "6px 0 0" }}>Ces cibles apparaissent aussi comme liens « bastion » dans la tuile Supervision SI (onglet Liens) — catégorie Bastion.</p>
      </div>

      <div className="hub-card hub-settings-section">
        <h2 style={{ margin: "0 0 6px" }}>Journal d'audit
          {" "}<select value={filter} onChange={(e) => setFilter(e.target.value)}>
            <option value="all">tout</option>
            {Object.entries(EVENT_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
          <span className="muted"> ({rows.length} / {audit.length} événements, métadonnées seulement)</span>
        </h2>
        {rows.length === 0 ? <p className="muted" style={{ margin: 0 }}>Journal vide.</p> : (
          <div className="hub-table-scroll" style={{ maxHeight: 360 }}>
            <table>
              <thead><tr><th>Quand</th><th>Événement</th><th>Détail</th></tr></thead>
              <tbody>
                {rows.map((ev, i) => (
                  <tr key={`${ev.at}-${i}`}>
                    <td className="muted">{when(ev.at)}</td>
                    <td><Tone tone={ev.event === "refused" ? "bad" : ev.event === "session-start" ? "good" : "neutral"}>{EVENT_LABELS[ev.event] || ev.event}</Tone></td>
                    <td>{describeEvent(ev)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
