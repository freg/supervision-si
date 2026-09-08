// Tuile « Cortex » (livraison #462) -- décloisonne, corrèle, relie,
// consolide. Première étape : file d'incidents corrélés (fenêtre +
// relation, cause racine amont), chaque hypothèse avec sa confiance en
// mots, ses preuves et le principe (parti pris) appliqué ; retour humain
// (confirmer / rejeter) qui alimente l'évaluation mesurée des principes ;
// entités consolidées avec rôles pondérés ; événements normalisés ;
// journal de collecte ; statistiques. Rien n'est affirmé sans dire pourquoi.
import { useCallback, useEffect, useState } from "react";
import { fetchCortexStatus, fetchIncidents, fetchIncident, ackIncident, closeIncident, feedbackIncident, fetchEntities, fetchEntity, fetchEvents, fetchPrinciples, fetchCortexStats, fetchRuns, runCollect } from "./cortexClient.js";
import { SEV, STATE_LABEL, KIND_LABEL, confidenceWord, pct, incidentLine, splitHypotheses, collectHealth, principleText, eventsBySource } from "./cortex.js";

const REFRESH_MS = 30000;
const TABS = [["incidents", "Incidents"], ["entities", "Entités"], ["events", "Événements"], ["principles", "Principes & évaluations"], ["stats", "Statistiques"], ["runs", "Collecte"]];

function Tone({ tone, children, title }) {
  return <span className={`np-tone ${tone || "neutral"}`} title={title}>{children}</span>;
}
function Conf({ c }) {
  const w = confidenceWord(c);
  return <Tone tone={w.tone} title={`confiance ${pct(c)}`}>{w.word} ({pct(c)})</Tone>;
}

function Hypothesis({ h, incidentKey, apiBase, login, onDone }) {
  const [busy, setBusy] = useState(false);
  const vote = async (verdict) => {
    setBusy(true);
    await feedbackIncident(apiBase, incidentKey, { principle: h.principle, verdict, claim: h.claim, by: login });
    setBusy(false); onDone?.();
  };
  return (
    <li style={{ marginBottom: 4 }}>
      <Conf c={h.confidence} /> {h.claim}
      <span className="muted"> — principe <code>{h.principle}</code>{h.evidence?.length ? ` · preuves : ${h.evidence.join(" ; ")}` : ""}</span>
      {" "}<button className="secondary ss-origin" disabled={busy} title="cette hypothèse est juste" onClick={() => vote("confirmed")}>✓ juste</button>
      {" "}<button className="secondary ss-origin" disabled={busy} title="cette hypothèse est fausse" onClick={() => vote("rejected")}>✗ fausse</button>
    </li>
  );
}

export default function CortexView({ onBack, cortexApiBase, login, groups = [], onNavigate }) {
  const [tab, setTab] = useState("incidents");
  const [status, setStatus] = useState(null);
  const [incidents, setIncidents] = useState([]);
  const [incState, setIncState] = useState("open");
  const [detail, setDetail] = useState(null);
  const [entities, setEntities] = useState([]);
  const [q, setQ] = useState("");
  const [entity, setEntity] = useState(null);
  const [events, setEvents] = useState([]);
  const [principles, setPrinciples] = useState(null);
  const [stats, setStats] = useState(null);
  const [runs, setRuns] = useState([]);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState(null);

  const load = useCallback(async () => {
    const st = await fetchCortexStatus(cortexApiBase);
    if (st.error) { setError(st.error); return; }
    setError(null); setStatus(st);
    if (tab === "incidents") { const r = await fetchIncidents(cortexApiBase, incState); if (!r.error) setIncidents(r.incidents); }
    if (tab === "entities") { const r = await fetchEntities(cortexApiBase, q); if (!r.error) setEntities(r.entities); }
    if (tab === "events") { const r = await fetchEvents(cortexApiBase, "open"); if (!r.error) setEvents(r.events); }
    if (tab === "principles") { const r = await fetchPrinciples(cortexApiBase); if (!r.error) setPrinciples(r); }
    if (tab === "stats") { const r = await fetchCortexStats(cortexApiBase, 7); if (!r.error) setStats(r); }
    if (tab === "runs") { const r = await fetchRuns(cortexApiBase); if (!r.error) setRuns(r.runs); }
  }, [cortexApiBase, tab, incState, q]);
  useEffect(() => { load(); const id = setInterval(load, REFRESH_MS); return () => clearInterval(id); }, [load]);

  const openDetail = async (key) => { const d = await fetchIncident(cortexApiBase, key); if (!d.error) setDetail(d); };
  const act = async (label, fn) => { setBusy(true); const r = await fn(); setBusy(false); setNotice(r?.error ? `${label} : ${r.error}` : `${label} : fait`); load(); if (detail) openDetail(detail.key); };
  const health = collectHealth(status?.last_run);

  return (
    <div className="hub-settings hub-settings-wide">
      <div className="hub-settings-topbar">
        <button className="secondary" onClick={onBack}>◀ Retour</button>
        <h1>🧠 Cortex</h1>
        <span className="muted">décloisonne · corrèle · relie · consolide — chaque hypothèse est évaluée</span>
      </div>
      {error && <p className="hub-error">{error}</p>}
      {status && (
        <div className="hub-card hub-settings-section">
          <p style={{ margin: 0 }}>
            <Tone tone={status.incidents_critical ? "bad" : status.incidents_open ? "warn" : "good"}>{status.incidents_open} incident(s) ouvert(s){status.incidents_critical ? `, ${status.incidents_critical} critique(s)` : ""}</Tone>
            {" · "}{status.entities} entité(s) consolidée(s) · {status.events_open} événement(s) ouvert(s)
            {" · "}collecte : <Tone tone={health.tone}>{health.text}</Tone>{health.failed.length > 0 && <span className="muted"> — en échec : {health.failed.join(", ")}</span>}
            {" · "}fenêtre {status.window_seconds} s, toutes les {status.interval_seconds} s
            {" "}<button className="secondary ss-origin" disabled={busy || status.running} onClick={() => act("Collecte", () => runCollect(cortexApiBase, groups))}>↻ collecter maintenant</button>
          </p>
        </div>
      )}
      {notice && <p className="muted ups-notice">{notice} <button className="secondary" onClick={() => setNotice(null)}>✕</button></p>}
      <div style={{ display: "flex", gap: 6, flexWrap: "wrap", margin: "0 0 10px" }}>
        {TABS.map(([id, label]) => <button key={id} type="button" className={`secondary na-section-toggle${tab === id ? " active" : ""}`} onClick={() => setTab(id)}>{label}</button>)}
      </div>

      {tab === "incidents" && (
        <div className="hub-card hub-settings-section">
          <p style={{ margin: "0 0 6px" }}>
            <select value={incState} onChange={(e) => setIncState(e.target.value)}><option value="open">ouverts et acquittés</option><option value="acked">acquittés</option><option value="closed">clos</option><option value="all">tous</option></select>
            <span className="muted"> — un incident = des événements proches et reliés ; la cause proposée est l'entité la plus en amont (passerelle, onduleur…).</span>
          </p>
          {incidents.length === 0 ? <p className="muted">Aucun incident{incState === "open" ? " ouvert" : ""}.</p> : (
            <div className="hub-table-scroll"><table>
              <thead><tr><th>Sévérité</th><th>État</th><th>Incident</th><th>Cause proposée</th><th>Confiance</th><th>Depuis</th><th>Contenu</th><th></th></tr></thead>
              <tbody>{incidents.map((i) => (
                <tr key={i.key} className={detail?.key === i.key ? "active" : ""} style={{ cursor: "pointer" }} onClick={() => openDetail(i.key)}>
                  <td><Tone tone={SEV[i.severity]?.tone}>{SEV[i.severity]?.label || i.severity}</Tone></td>
                  <td>{STATE_LABEL[i.state] || i.state}{i.acked_by ? <span className="muted"> ({i.acked_by})</span> : ""}</td>
                  <td>{i.title}</td><td className="muted">{splitHypotheses(i.hypotheses).cause?.claim || "—"}</td>
                  <td><Conf c={i.confidence} /></td><td className="muted">{i.opened_at}</td><td className="muted">{incidentLine(i)}</td>
                  <td>{i.state === "open" && <button className="secondary ss-origin" disabled={busy} onClick={(e) => { e.stopPropagation(); act("Acquittement", () => ackIncident(cortexApiBase, i.key, login)); }}>acquitter</button>}
                    {" "}{i.state !== "closed" && <button className="secondary ss-origin" disabled={busy} onClick={(e) => { e.stopPropagation(); act("Clôture", () => closeIncident(cortexApiBase, i.key, login)); }}>clore</button>}</td>
                </tr>
              ))}</tbody>
            </table></div>
          )}
          {detail && (
            <div className="hub-card hub-settings-section" style={{ marginTop: 10, textAlign: "left" }}>
              <h2 style={{ margin: "0 0 4px" }}><Tone tone={SEV[detail.severity]?.tone}>{SEV[detail.severity]?.label}</Tone> {detail.title} <button className="secondary ss-origin" onClick={() => setDetail(null)}>✕</button></h2>
              <p className="muted" style={{ margin: "0 0 6px" }}>{incidentLine(detail)} · ouvert {detail.opened_at} · dernier événement {detail.last_at} · {STATE_LABEL[detail.state]}</p>
              <h3 style={{ margin: "6px 0 2px" }}>Hypothèses (chacune avec sa confiance, ses preuves, son principe — dites-nous si c'est juste)</h3>
              <ul className="sa-risks">{(detail.hypotheses || []).map((h, k) => <Hypothesis key={k} h={h} incidentKey={detail.key} apiBase={cortexApiBase} login={login} onDone={() => { load(); openDetail(detail.key); }} />)}</ul>
              <h3 style={{ margin: "6px 0 2px" }}>Entités concernées</h3>
              <ul className="sa-risks">{(detail.entity_details || []).filter(Boolean).map((e) => <li key={e.key}><strong>{e.name || e.ip || e.key}</strong> <span className="muted">{KIND_LABEL[e.kind] || e.kind}{e.site ? ` · ${e.site}` : ""} · {e.key}{e.key === detail.root ? " · cause proposée" : ""}</span></li>)}</ul>
              {(detail.relations || []).length > 0 && <><h3 style={{ margin: "6px 0 2px" }}>Relations utilisées</h3>
                <ul className="sa-risks">{detail.relations.slice(0, 20).map((r, k) => <li key={k}><code>{r.a}</code> —{r.kind}→ <code>{r.b}</code> <span className="muted">(principe {r.principle}, {r.evidence}, source {r.source})</span></li>)}</ul></>}
              <h3 style={{ margin: "6px 0 2px" }}>Événements</h3>
              <div className="hub-table-scroll"><table><thead><tr><th>Quand</th><th>Source</th><th>Type</th><th>Sévérité</th><th>Entité</th><th>Message</th><th>×</th></tr></thead>
                <tbody>{(detail.event_details || []).map((e) => <tr key={e.fingerprint}><td className="muted">{e.last_at}</td><td>{e.source}</td><td>{e.kind}</td><td><Tone tone={SEV[e.severity]?.tone}>{SEV[e.severity]?.label}</Tone></td><td className="muted">{e.entity}</td><td>{e.message}</td><td>{e.count}</td></tr>)}</tbody></table></div>
            </div>
          )}
        </div>
      )}

      {tab === "entities" && (
        <div className="hub-card hub-settings-section">
          <p style={{ margin: "0 0 6px" }}><input className="ss-search" placeholder="filtrer : nom, IP, site, clé" value={q} onChange={(e) => setQ(e.target.value)} /> <span className="muted">{entities.length} entité(s) — fusionnées par MAC, IP puis nom ; les rôles sont des hypothèses pondérées.</span></p>
          <div className="hub-table-scroll"><table><thead><tr><th>Entité</th><th>Type</th><th>Site</th><th>Rôles (confiance)</th><th>Origines</th></tr></thead>
            <tbody>{entities.map((e) => (
              <tr key={e.key} style={{ cursor: "pointer" }} onClick={async () => { const d = await fetchEntity(cortexApiBase, e.key); if (!d.error) setEntity(d); }}>
                <td><strong>{e.name || e.ip || e.key}</strong> <span className="muted">{e.ip && e.name ? e.ip : ""} {e.mac || ""}</span></td><td>{KIND_LABEL[e.kind] || e.kind}</td><td>{e.site || "—"}</td>
                <td>{(e.roles || []).length ? e.roles.map((r) => <span key={r.role} title={`${r.evidence.join(" ; ")} — principes ${r.principles.join(", ")}`}><Tone tone={confidenceWord(r.confidence).tone}>{r.role} {pct(r.confidence)}</Tone> </span>) : <span className="muted">aucun indice</span>}</td>
                <td className="muted">{(e.origins || []).map((o) => o.source).filter((v, i, a) => a.indexOf(v) === i).join(", ")}</td>
              </tr>
            ))}</tbody></table></div>
          {entity && (
            <div className="hub-card hub-settings-section" style={{ marginTop: 10, textAlign: "left" }}>
              <h2 style={{ margin: "0 0 4px" }}>{entity.name || entity.ip || entity.key} <span className="muted">{entity.key}</span> <button className="secondary ss-origin" onClick={() => setEntity(null)}>✕</button></h2>
              <p className="muted" style={{ margin: 0 }}>vu de {entity.first_seen} à {entity.last_seen}</p>
              <ul className="sa-risks">{(entity.roles || []).map((r) => <li key={r.role}><Conf c={r.confidence} /> {r.role} — {r.evidence.join(" ; ")} <span className="muted">(principes {r.principles.join(", ")})</span></li>)}</ul>
              <ul className="sa-risks">{(entity.relations || []).slice(0, 30).map((r, k) => <li key={k}><code>{r.a === entity.key ? "cette entité" : r.a}</code> —{r.kind}→ <code>{r.b === entity.key ? "cette entité" : r.b}</code> <span className="muted">{r.evidence} ({r.source})</span></li>)}</ul>
              {(entity.events || []).length > 0 && <p className="muted">{entity.events.length} événement(s) : {entity.events.slice(0, 5).map((e) => `${e.kind} (${STATE_LABEL[e.state]})`).join(" · ")}</p>}
            </div>
          )}
        </div>
      )}

      {tab === "events" && (
        <div className="hub-card hub-settings-section">
          <p className="muted" style={{ margin: "0 0 6px" }}>{events.length} événement(s) ouvert(s) — {eventsBySource(events).map(([s, n]) => `${s} ${n}`).join(" · ")}. Une empreinte par (source, type, entité) : un événement répété est rafraîchi (×), jamais dupliqué ; une source qui ne le remonte plus le ferme.</p>
          <div className="hub-table-scroll"><table><thead><tr><th>Dernier</th><th>Source</th><th>Type</th><th>Sévérité</th><th>Entité</th><th>Site</th><th>Message</th><th>×</th></tr></thead>
            <tbody>{events.map((e) => <tr key={e.fingerprint}><td className="muted">{e.last_at}</td><td>{e.source}</td><td>{e.kind}</td><td><Tone tone={SEV[e.severity]?.tone}>{SEV[e.severity]?.label}</Tone></td><td className="muted">{e.entity}</td><td>{e.site || "—"}</td><td>{e.message}</td><td>{e.count}</td></tr>)}</tbody></table></div>
        </div>
      )}

      {tab === "principles" && principles && (
        <div className="hub-card hub-settings-section">
          <p className="muted" style={{ margin: "0 0 6px" }}>Les partis pris de Cortex, tels qu'ils sont appliqués. La confiance de base est celle du concepteur ; la confiance mesurée intègre vos retours (« juste » / « fausse ») sur les hypothèses qui s'en réclament.</p>
          <ul className="sa-risks">{principles.principles.map((p) => (
            <li key={p.id} style={{ marginBottom: 8 }}>
              <Conf c={p.effective} /> <strong>{p.title}</strong> <code>{p.id}</code> <span className="muted">· {p.scope}</span><br />
              {p.statement}<br />
              <span className="muted">Limite connue : {p.limit} — {principleText(p)}</span>
            </li>
          ))}</ul>
          {principles.feedback?.length > 0 && <p className="muted" style={{ margin: "6px 0 0" }}>Derniers retours : {principles.feedback.slice(0, 8).map((f) => `${f.at} ${f.by_user || "?"} ${f.verdict === "confirmed" ? "✓" : "✗"} ${f.principle}`).join(" · ")}</p>}
        </div>
      )}

      {tab === "stats" && stats && (
        <div className="hub-card hub-settings-section">
          <p style={{ margin: "0 0 6px" }}>Sur {stats.days} jours : événements par source {Object.entries(stats.events_by_source).map(([k, v]) => `${k} ${v}`).join(", ") || "—"} · par sévérité {Object.entries(stats.events_by_severity).map(([k, v]) => `${SEV[k]?.label || k} ${v}`).join(", ") || "—"} · incidents ouverts {stats.incidents_open} ({stats.incidents_weak} regroupement(s) faible(s)).</p>
          <p className="muted" style={{ margin: "0 0 6px" }}>Par jour : {Object.entries(stats.events_by_day).map(([d, n]) => `${d} : ${n}`).join(" · ") || "—"}</p>
          <h3 style={{ margin: "6px 0 2px" }}>Entités les plus bruyantes</h3>
          <ul className="sa-risks">{stats.noisy_entities.map((n) => <li key={n.entity}><strong>{n.name}</strong> <span className="muted">{n.count} occurrence(s) · {n.entity}</span></li>)}</ul>
          <h3 style={{ margin: "6px 0 2px" }}>Principes : confiance effective et volume d'application</h3>
          <ul className="sa-risks">{stats.principles.filter((p) => p.applied).map((p) => <li key={p.id}><Conf c={p.effective} /> {p.title} <span className="muted">— appliqué {p.applied} fois, {p.confirmed} ✓ / {p.rejected} ✗</span></li>)}</ul>
        </div>
      )}

      {tab === "runs" && (
        <div className="hub-card hub-settings-section">
          <p className="muted" style={{ margin: "0 0 6px" }}>Journal des collectes : quelle source a répondu, en combien de temps, ce qui en est sorti. Une source en échec n'empêche pas les autres.</p>
          <div className="hub-table-scroll"><table><thead><tr><th>Quand</th><th>Durée</th><th>Sources</th><th>Résultat</th></tr></thead>
            <tbody>{runs.map((r) => <tr key={r.id}><td className="muted">{r.at}</td><td>{r.duration_ms} ms</td>
              <td>{Object.entries(r.sources || {}).map(([k, v]) => <span key={k}><Tone tone={v.ok ? "good" : "bad"} title={v.error || `${v.entities} ent., ${v.relations} rel., ${v.events} év. en ${v.ms} ms`}>{k}</Tone> </span>)}</td>
              <td className="muted">{r.counts ? `${r.counts.entities} entités, ${r.counts.relations} relations, ${r.counts.events_new} nouveaux / ${r.counts.events_refreshed} rafraîchis / ${r.counts.events_closed} fermés, ${r.counts.incidents} incidents` : ""}</td></tr>)}</tbody></table></div>
        </div>
      )}
    </div>
  );
}
