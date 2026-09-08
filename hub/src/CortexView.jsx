// Tuile « Cortex » (livraison #462) -- décloisonne, corrèle, relie,
// consolide. Première étape : file d'incidents corrélés (fenêtre +
// relation, cause racine amont), chaque hypothèse avec sa confiance en
// mots, ses preuves et le principe (parti pris) appliqué ; retour humain
// (confirmer / rejeter) qui alimente l'évaluation mesurée des principes ;
// entités consolidées avec rôles pondérés ; événements normalisés ;
// journal de collecte ; statistiques. Rien n'est affirmé sans dire pourquoi.
import { useCallback, useEffect, useState } from "react";
import { MapContainer, TileLayer, CircleMarker, Polyline, Popup, useMap } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import { fetchCortexStatus, fetchIncidents, fetchIncident, ackIncident, closeIncident, feedbackIncident, fetchEntities, fetchEntity, fetchEvents, fetchPrinciples, fetchCortexStats, fetchRuns, runCollect, fetchGraph, fetchRoutes, fetchChanges, fetchPositions, fetchPositionsQueue, resolvePositions, fetchPlaces, savePlaceNote, fetchIntervention, fetchLayers, fetchRules, ruleAction, fetchPredictions, fetchDrifts, fetchSamples, runLearn } from "./cortexClient.js";
import { layoutGraph, EDGE_STYLE, KIND_ICON, CHANGE_LABEL, changeTone, routesByHost } from "./cortexGraph.js";
import { PROVENANCE, provenanceStyle, LAYERS, defaultLayers, SEV_COLOR, boundsOf, sortPositions, provenanceCounts, chainText, whereText, RULE_STATE, OUTCOME, ruleText, minutesLeft, predictionStats, sparkPath } from "./cortexPlaces.js";
import { SEV, STATE_LABEL, KIND_LABEL, confidenceWord, pct, incidentLine, splitHypotheses, collectHealth, principleText, eventsBySource } from "./cortex.js";

const REFRESH_MS = 30000;
const TABS = [["incidents", "Incidents"], ["anticipation", "Anticipation"], ["graph", "Architecture"], ["map", "Carte"], ["positions", "Positions"], ["changes", "Ce qui a changé"], ["routes", "Routes"], ["entities", "Entités"], ["events", "Événements"], ["principles", "Principes & évaluations"], ["stats", "Statistiques"], ["runs", "Collecte"]];

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

function FitBounds({ bounds }) {
  const map = useMap();
  useEffect(() => { if (bounds) map.fitBounds(bounds, { padding: [24, 24], maxZoom: 15 }); }, [map, bounds]);
  return null;
}

// Fiche « où aller » d'une entité (#464) : lieu, position et provenance,
// amont (passerelle, borne, onduleur) avec état, incidents ouverts, voisins
// du même lieu, accès bastion, contact et accès du site (saisie humaine).
function InterventionSheet({ sheet, apiBase, login, groups, onSaved }) {
  const [contact, setContact] = useState(sheet.contact || "");
  const [access, setAccess] = useState(sheet.access || "");
  const [busy, setBusy] = useState(false);
  const siteKey = sheet.where?.length ? sheet.where[0].key : null;
  const pos = sheet.position;
  const st = pos ? provenanceStyle(pos.provenance) : null;
  return (
    <div className="hub-card hub-settings-section" style={{ marginTop: 8, textAlign: "left", borderLeft: "4px solid var(--accent, #2f6fd6)" }}>
      <h3 style={{ margin: "0 0 4px" }}>🧭 Fiche d'intervention — {sheet.entity.name || sheet.entity.ip || sheet.entity.key}</h3>
      <p style={{ margin: "0 0 4px" }}><strong>Où aller :</strong> {whereText(sheet)}{pos ? <> · <Tone tone={st.tone} title={st.help}>{pos.provenance} ({pct(pos.confidence)})</Tone> <span className="muted">{pos.lat?.toFixed(5)}, {pos.lon?.toFixed(5)} — {chainText(pos)} · principe <code>{pos.principle}</code></span></> : <span className="muted"> · sans position (file de travail)</span>}</p>
      <p style={{ margin: "0 0 4px" }}><strong>En amont :</strong> {sheet.upstream?.length ? sheet.upstream.map((u) => <span key={u.key + u.kind}><Tone tone={u.state === "ok" ? "good" : SEV[u.state]?.tone}>{u.name}</Tone> <span className="muted">({u.kind === "gateway_of" ? "passerelle" : u.kind === "uplink" ? "borne / switch" : u.kind === "powers_site" ? "onduleur du site" : u.kind}{u.state !== "ok" ? `, ${SEV[u.state]?.label || u.state}` : ""})</span> </span>) : <span className="muted">rien de connu</span>}</p>
      <p style={{ margin: "0 0 4px" }}><strong>Incidents ouverts :</strong> {sheet.incidents?.length ? sheet.incidents.map((i) => <span key={i.key}><Tone tone={SEV[i.severity]?.tone}>{SEV[i.severity]?.label}</Tone> {i.title} </span>) : <span className="muted">aucun</span>} · <strong>supervision :</strong> {sheet.supervised ? <Tone tone="good">supervisée</Tone> : <Tone tone="warn">vue par la découverte seule</Tone>}</p>
      <p style={{ margin: "0 0 4px" }}><strong>Accès :</strong> {sheet.bastion ? (sheet.bastion.available ? <Tone tone="good">joignable par le bastion ({sheet.bastion.via})</Tone> : <span className="muted">pas de cible bastion connue pour cette IP</span>) : <span className="muted">bastion non interrogé</span>}{sheet.ticket_url && <> · <a href={sheet.ticket_url} target="_blank" rel="noreferrer">ouvrir un ticket</a></>}</p>
      {sheet.same_place?.length > 0 && <p className="muted" style={{ margin: "0 0 4px" }}><strong>Au même lieu :</strong> {sheet.same_place.slice(0, 12).map((s) => `${s.name}${s.role ? ` (${s.role})` : ""}`).join(", ")}{sheet.same_place.length > 12 ? ` … (+${sheet.same_place.length - 12})` : ""}</p>}
      {siteKey && (
        <p style={{ margin: "4px 0 0" }}>
          <strong>Contact du site :</strong> <input className="ss-search" style={{ width: 220 }} value={contact} placeholder="nom, téléphone" onChange={(e) => setContact(e.target.value)} />
          {" "}<strong>Accès :</strong> <input className="ss-search" style={{ width: 260 }} value={access} placeholder="badge, clé, horaires" onChange={(e) => setAccess(e.target.value)} />
          {" "}<button className="secondary ss-origin" disabled={busy} onClick={async () => { setBusy(true); await savePlaceNote(apiBase, siteKey, { contact, access, by: login, groups }); setBusy(false); onSaved?.(); }}>enregistrer</button>
          <span className="muted"> (lieu {siteKey} — saisie humaine, jamais écrasée par la collecte)</span>
        </p>
      )}
      {sheet.principles?.length > 0 && <p className="muted" style={{ margin: "4px 0 0" }}>Principes appliqués : {sheet.principles.map((p) => `${p.id} (${pct(p.effective)})`).join(" · ")}</p>}
    </div>
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
  const [graph, setGraph] = useState(null);
  const [routes, setRoutes] = useState([]);
  const [changes, setChanges] = useState([]);
  const [graphNode, setGraphNode] = useState(null);
  const [positions, setPositions] = useState(null);
  const [queue, setQueue] = useState(null);
  const [provFilter, setProvFilter] = useState(null);
  const [layers, setLayers] = useState(null);
  const [activeLayers, setActiveLayers] = useState(defaultLayers);
  const [sheet, setSheet] = useState(null);
  const [rules, setRules] = useState(null);
  const [predictions, setPredictions] = useState([]);
  const [drifts, setDrifts] = useState(null);
  const [spark, setSpark] = useState({});
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
    if (tab === "graph") { const r = await fetchGraph(cortexApiBase); if (!r.error) setGraph(r); }
    if (tab === "routes") { const r = await fetchRoutes(cortexApiBase); if (!r.error) setRoutes(r.routes); }
    if (tab === "changes") { const r = await fetchChanges(cortexApiBase); if (!r.error) setChanges(r.changes); }
    if (tab === "positions") { const [r, qq] = await Promise.all([fetchPositions(cortexApiBase), fetchPositionsQueue(cortexApiBase)]); if (!r.error) setPositions(r.positions); if (!qq.error) setQueue(qq); }
    if (tab === "map") { const r = await fetchLayers(cortexApiBase); if (!r.error) setLayers(r); }
    if (tab === "anticipation") {
      const [r, p, d] = await Promise.all([fetchRules(cortexApiBase), fetchPredictions(cortexApiBase), fetchDrifts(cortexApiBase)]);
      if (!r.error) setRules(r); if (!p.error) setPredictions(p.predictions); if (!d.error) setDrifts(d);
    }
  }, [cortexApiBase, tab, incState, q]);
  const openSheet = async (key) => { const d = await fetchIntervention(cortexApiBase, key); if (!d.error) setSheet(d); else setNotice(`fiche : ${d.error}`); };
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
              {(detail.predictions || []).length > 0 && <p style={{ margin: "4px 0" }}><strong>🔮 Annoncé :</strong> {detail.predictions.map((p) => <span key={p.id}><Tone tone={confidenceWord(p.confidence).tone}>{p.message}</Tone> <span className="muted">(échéance {p.expected_at}{minutesLeft(p) != null ? `, dans ${minutesLeft(p)} min` : ""})</span> </span>)}</p>}
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

      {tab === "graph" && (() => {
        const l = layoutGraph(graph);
        const sel = graphNode ? l.nodes.find((n) => n.key === graphNode) : null;
        return (
          <div className="hub-card hub-settings-section">
            <p className="muted" style={{ margin: "0 0 6px" }}>Graphe d'architecture persistant : une colonne par site ; en haut ce qui est en amont (passerelles, routeurs, bornes, switches, onduleurs), au milieu les hôtes supervisés, en bas le reste. Arêtes : orange = dépendance (passerelle, borne), violet = alimentation, bleu = flux, gris = voisinage, vert = sonde. {l.truncated && "Affichage limité aux 300 premières entités."}</p>
            {l.nodes.length === 0 ? <p className="muted">Aucune entité encore (lancer une collecte).</p> : (
              <div className="hub-table-scroll" style={{ maxHeight: 620 }}>
                <svg width={l.width} height={l.height} role="img" aria-label="graphe d'architecture">
                  {l.sites.map((s, i) => <g key={s}><rect x={16 + i * l.colW} y={4} width={l.colW - 10} height={l.height - 8} fill="none" stroke="var(--border, #ddd)" rx={8} /><text x={16 + i * l.colW + 8} y={l.height - 4} fontSize={11} fill="currentColor" opacity={0.6}>{s}</text></g>)}
                  {l.edges.map((e, k) => { const st = EDGE_STYLE[e.kind] || { color: "#999", width: 1 }; return <line key={k} x1={e.x1} y1={e.y1} x2={e.x2} y2={e.y2} stroke={st.color} strokeWidth={st.width} opacity={0.75} />; })}
                  {l.nodes.map((n) => (
                    <g key={n.key} transform={`translate(${n.x},${n.y})`} style={{ cursor: "pointer" }} onClick={() => setGraphNode(n.key === graphNode ? null : n.key)}>
                      <circle r={n.key === graphNode ? 8 : 6} fill={n.layer === 0 ? "#c2410c" : n.layer === 1 ? "#2f9e5b" : "#8a8f98"} stroke="#fff" strokeWidth={1.5} />
                      <text x={11} y={4} fontSize={11} fill="currentColor">{KIND_ICON[n.kind] || ""} {String(n.name).slice(0, 22)}{n.role ? ` · ${n.role}` : ""}</text>
                      <title>{n.name} · {n.kind}{n.role ? ` · rôle ${n.role} (${pct(n.role_confidence)})` : ""}{n.vendor ? ` · ${n.vendor}` : ""} · sources : {(n.sources || []).join(", ")}</title>
                    </g>
                  ))}
                </svg>
              </div>
            )}
            {sel && <p style={{ margin: "6px 0 0" }}><strong>{sel.name}</strong> <span className="muted">{sel.key} · {KIND_LABEL[sel.kind] || sel.kind}{sel.site ? ` · ${sel.site}` : ""}{sel.vendor ? ` · ${sel.vendor}` : ""}{sel.role ? ` · rôle ${sel.role} (${pct(sel.role_confidence)})` : " · aucun rôle déduit"} · sources : {(sel.sources || []).join(", ")}</span> <button className="secondary ss-origin" onClick={async () => { const d = await fetchEntity(cortexApiBase, sel.key); if (!d.error) { setEntity(d); setTab("entities"); } }}>détail</button></p>}
          </div>
        );
      })()}

      {tab === "changes" && (
        <div className="hub-card hub-settings-section">
          <p className="muted" style={{ margin: "0 0 6px" }}>Ce qui a changé entre deux collectes (principe <code>change-since</code>) : entités apparues ou plus vues, relations nouvelles ou disparues, rôle dominant ou passerelle qui change. Les disparitions dues à une source en échec ne sont pas comptées.</p>
          {changes.length === 0 ? <p className="muted">Aucun changement enregistré (il faut au moins deux collectes).</p> : (
            <div className="hub-table-scroll"><table><thead><tr><th>Quand</th><th>Type</th><th>Changement</th></tr></thead>
              <tbody>{changes.map((c) => <tr key={c.id}><td className="muted">{c.at}</td><td><Tone tone={changeTone(c.kind)}>{CHANGE_LABEL[c.kind] || c.kind}</Tone></td><td>{c.message}</td></tr>)}</tbody></table></div>
          )}
        </div>
      )}

      {tab === "routes" && (
        <div className="hub-card hub-settings-section">
          <p className="muted" style={{ margin: "0 0 6px" }}>Table de routes consolidée (principe <code>route-known</code>) : pour chaque hôte équipé d'un agent, sa passerelle par défaut, ses sous-réseaux attachés et ceux qu'il sait joindre par une autre passerelle.</p>
          {routes.length === 0 ? <p className="muted">Aucune route (aucun agent n'a remonté sa vue réseau).</p> : (
            <div className="hub-table-scroll"><table><thead><tr><th>Hôte</th><th>Passerelle par défaut</th><th>État</th><th>Sous-réseaux attachés</th><th>Joignables via</th></tr></thead>
              <tbody>{routesByHost(routes).map((h) => <tr key={h.host}><td><strong>{h.name}</strong> <span className="muted">{h.host}</span></td><td>{h.default?.via || "—"}</td><td>{h.default?.state ? <Tone tone={h.default.state === "reachable" ? "good" : "warn"}>{h.default.state}</Tone> : "—"}</td><td className="muted">{h.attached.join(", ") || "—"}</td><td className="muted">{h.reachable.map((r) => `${r.destination}${r.via ? ` via ${r.via}` : ""}`).join(", ") || "—"}</td></tr>)}</tbody></table></div>
          )}
        </div>
      )}

      {tab === "entities" && (
        <div className="hub-card hub-settings-section">
          <p style={{ margin: "0 0 6px" }}><input className="ss-search" placeholder="filtrer : nom, IP, site, clé" value={q} onChange={(e) => setQ(e.target.value)} /> <span className="muted">{entities.length} entité(s) — fusionnées par MAC, IP puis nom ; les rôles sont des hypothèses pondérées.</span></p>
          <div className="hub-table-scroll"><table><thead><tr><th>Entité</th><th>Type</th><th>Site</th><th>Rôles (confiance)</th><th>Origines</th></tr></thead>
            <tbody>{entities.map((e) => (
              <tr key={e.key} style={{ cursor: "pointer" }} onClick={async () => { const d = await fetchEntity(cortexApiBase, e.key); if (!d.error) setEntity(d); }}>
                <td><strong>{e.name || e.ip || e.key}</strong> <span className="muted">{e.ip && e.name ? e.ip : ""} {e.mac || ""}{e.vendor ? ` · ${e.vendor}` : ""}{e.description ? ` · ${e.description}` : ""}</span></td><td>{KIND_LABEL[e.kind] || e.kind}</td><td>{e.site || "—"}</td>
                <td>{(e.roles || []).length ? e.roles.map((r) => <span key={r.role} title={`${r.evidence.join(" ; ")} — principes ${r.principles.join(", ")}`}><Tone tone={confidenceWord(r.confidence).tone}>{r.role} {pct(r.confidence)}</Tone> </span>) : <span className="muted">aucun indice</span>}</td>
                <td className="muted">{(e.origins || []).map((o) => o.source).filter((v, i, a) => a.indexOf(v) === i).join(", ")}</td>
              </tr>
            ))}</tbody></table></div>
          {entity && (
            <div className="hub-card hub-settings-section" style={{ marginTop: 10, textAlign: "left" }}>
              <h2 style={{ margin: "0 0 4px" }}>{entity.name || entity.ip || entity.key} <span className="muted">{entity.key}</span> <button className="secondary ss-origin" onClick={() => openSheet(entity.key)}>🧭 fiche d'intervention</button> <button className="secondary ss-origin" onClick={() => { setEntity(null); setSheet(null); }}>✕</button></h2>
              <p className="muted" style={{ margin: 0 }}>vu de {entity.first_seen} à {entity.last_seen}</p>
              {sheet && sheet.entity.key === entity.key && <InterventionSheet sheet={sheet} apiBase={cortexApiBase} login={login} groups={groups} onSaved={() => openSheet(entity.key)} />}
              <ul className="sa-risks">{(entity.roles || []).map((r) => <li key={r.role}><Conf c={r.confidence} /> {r.role} — {r.evidence.join(" ; ")} <span className="muted">(principes {r.principles.join(", ")})</span></li>)}</ul>
              <ul className="sa-risks">{(entity.relations || []).slice(0, 30).map((r, k) => <li key={k}><code>{r.a === entity.key ? "cette entité" : r.a}</code> —{r.kind}→ <code>{r.b === entity.key ? "cette entité" : r.b}</code> <span className="muted">{r.evidence} ({r.source})</span></li>)}</ul>
              {(entity.events || []).length > 0 && <p className="muted">{entity.events.length} événement(s) : {entity.events.slice(0, 5).map((e) => `${e.kind} (${STATE_LABEL[e.state]})`).join(" · ")}</p>}
            </div>
          )}
        </div>
      )}

      {tab === "anticipation" && (
        <div className="hub-card hub-settings-section">
          <p className="muted" style={{ margin: "0 0 6px" }}>Causalité apprise : les séquences « A précède B » plus fréquentes que le hasard deviennent des règles <em>proposées</em> (à confirmer ou rejeter) ; quand A survient, Cortex annonce B et juge ensuite son annonce (juste / fausse). Signaux faibles : écarts, tendances vers un seuil et habitudes horaires sur les mesures relevées. <button className="secondary ss-origin" disabled={busy} onClick={() => act("apprentissage", () => runLearn(cortexApiBase, groups))}>↻ réapprendre maintenant</button></p>
          {(() => { const st = predictionStats(predictions); return (
            <div className="hub-card hub-settings-section" style={{ marginBottom: 8, textAlign: "left" }}>
              <h3 style={{ margin: "0 0 4px" }}>🔮 Annonces <span className="muted">— {st.pending} en attente, {st.hits} juste(s), {st.misses} fausse(s){st.accuracy != null ? `, exactitude ${pct(st.accuracy)}` : ""}</span></h3>
              {predictions.length === 0 ? <p className="muted" style={{ margin: 0 }}>Aucune annonce : il faut des règles et un événement déclencheur ouvert.</p> : (
                <div className="hub-table-scroll"><table><thead><tr><th>Annonce</th><th>Confiance</th><th>Échéance</th><th>Issue</th><th>Règle</th></tr></thead>
                  <tbody>{predictions.slice(0, 40).map((p) => { const ml = minutesLeft(p); return (
                    <tr key={p.id}><td>{p.message}</td><td><Conf c={p.confidence} /></td><td className="muted">{p.expected_at}{!p.outcome && ml != null ? (ml >= 0 ? ` (dans ${ml} min)` : ` (dépassée de ${-ml} min)`) : ""}</td>
                      <td>{p.outcome ? <Tone tone={OUTCOME[p.outcome]?.tone}>{OUTCOME[p.outcome]?.label}</Tone> : <Tone tone="neutral">en attente</Tone>}</td><td className="muted"><code>{p.rule_id}</code></td></tr>); })}</tbody></table></div>
              )}
            </div>); })()}
          {rules && (
            <div className="hub-card hub-settings-section" style={{ marginBottom: 8, textAlign: "left" }}>
              <h3 style={{ margin: "0 0 4px" }}>📐 Règles apprises <span className="muted">— {rules.counts.proposed} proposée(s), {rules.counts.confirmed} confirmée(s), {rules.counts.rejected} rejetée(s) ; principes <code>sequence-learned</code> / <code>sequence-confirmed</code></span></h3>
              {rules.rules.length === 0 ? <p className="muted" style={{ margin: 0 }}>Aucune séquence assez fréquente (support ≥ 3, confiance ≥ 50 %, ≥ 2 × l'attendu) dans l'historique des occurrences.</p> : (
                <div className="hub-table-scroll"><table><thead><tr><th>Règle</th><th>Portée</th><th>Confiance</th><th>Attendu / observé</th><th>Jugée</th><th>État</th><th></th></tr></thead>
                  <tbody>{rules.rules.map((r) => (
                    <tr key={r.id}><td>{ruleText(r)}</td><td className="muted">{r.scope === "role" ? "par rôle" : "entités"}</td><td><Conf c={r.effective} /></td>
                      <td className="muted">{r.expected} / {r.count} (×{r.lift})</td><td className="muted">{r.hits} juste(s), {r.misses} fausse(s)</td>
                      <td><Tone tone={RULE_STATE[r.state]?.tone}>{RULE_STATE[r.state]?.label}</Tone>{r.decided_by ? <span className="muted"> par {r.decided_by}</span> : null}</td>
                      <td>{r.state !== "confirmed" && <button className="secondary ss-origin" disabled={busy} onClick={() => act("règle confirmée", () => ruleAction(cortexApiBase, r.id, "confirm", { by: login, groups }))}>✓ confirmer</button>}{" "}
                        {r.state !== "rejected" && <button className="secondary ss-origin" disabled={busy} onClick={() => act("règle rejetée", () => ruleAction(cortexApiBase, r.id, "reject", { by: login, groups }))}>✗ rejeter</button>}{" "}
                        {r.state !== "proposed" && <button className="secondary ss-origin" disabled={busy} onClick={() => act("règle remise en proposition", () => ruleAction(cortexApiBase, r.id, "reset", { by: login, groups }))}>↺</button>}</td></tr>
                  ))}</tbody></table></div>
              )}
            </div>
          )}
          {drifts && (
            <div className="hub-card hub-settings-section" style={{ textAlign: "left" }}>
              <h3 style={{ margin: "0 0 4px" }}>📈 Signaux faibles <span className="muted">— {drifts.drifts.length} dérive(s) en cours (événements de source <code>cortex</code>, regroupables en incidents), {drifts.tracked.length} série(s) suivie(s) ; principes <code>drift-zscore</code>, <code>drift-trend</code>, <code>seasonality</code></span></h3>
              {drifts.drifts.length > 0 && <ul className="sa-risks">{drifts.drifts.map((d) => <li key={d.fingerprint}><Tone tone={SEV[d.severity]?.tone}>{SEV[d.severity]?.label}</Tone> {d.message} <span className="muted">({STATE_LABEL[d.state]}, depuis {d.first_at})</span></li>)}</ul>}
              <div className="hub-table-scroll"><table><thead><tr><th>Entité</th><th>Mesure</th><th>Relevés</th><th>Dernier</th><th>Min – max</th><th>Courbe</th></tr></thead>
                <tbody>{drifts.tracked.map((t) => { const k = `${t.entity}|${t.metric}`; return (
                  <tr key={k} style={{ cursor: "pointer" }} onClick={async () => { if (spark[k]) return; const r = await fetchSamples(cortexApiBase, t.entity, t.metric); if (!r.error) setSpark((s) => ({ ...s, [k]: r.points })); }}>
                    <td>{t.entity}</td><td>{t.label}</td><td className="muted">{t.points}</td><td>{t.last}{t.unit} <span className="muted">{t.last_at}</span></td><td className="muted">{t.min} – {t.max}{t.unit}</td>
                    <td>{spark[k] ? <svg width={120} height={28}><path d={sparkPath(spark[k])} fill="none" stroke="var(--accent, #2f6fd6)" strokeWidth={1.5} /></svg> : <span className="muted">cliquer</span>}</td></tr>); })}</tbody></table></div>
            </div>
          )}
        </div>
      )}

      {tab === "positions" && (
        <div className="hub-card hub-settings-section">
          <p className="muted" style={{ margin: "0 0 6px" }}>Position mémorisée par entité avec sa provenance, résolue à chaque collecte par une échelle explicite (déclarée › validée › lieu déclaré › géolocalisation › résolue par le nom › propagée › voisinage › repli) — chaque barreau est un principe évalué. <button className="secondary ss-origin" disabled={busy} onClick={() => act("résolution", () => resolvePositions(cortexApiBase, groups))}>↻ résoudre maintenant</button></p>
          <p style={{ margin: "0 0 6px" }}>
            <button className={`secondary ss-origin${provFilter ? "" : " active"}`} onClick={() => setProvFilter(null)}>toutes ({(positions || []).length})</button>
            {provenanceCounts(positions).map(([p, n]) => <span key={p}> <button className={`secondary ss-origin${provFilter === p ? " active" : ""}`} title={provenanceStyle(p).help} style={{ borderLeft: `4px solid ${provenanceStyle(p).color}` }} onClick={() => setProvFilter(provFilter === p ? null : p)}>{p} ({n})</button></span>)}
          </p>
          {queue && queue.queue.length > 0 && (
            <div className="hub-card hub-settings-section" style={{ marginBottom: 8, textAlign: "left" }}>
              <strong>File de travail</strong> <span className="muted">— {queue.entities - queue.positioned + queue.queue.reduce((n, g) => n + g.entities.filter((e) => e.status === "repli").length, 0)} entité(s) sans position ou en repli : à déclarer (géolocalisations, lieu sur l'appareil) ou à valider (correspondances).</span>
              <ul className="sa-risks">{queue.queue.map((g) => <li key={g.site}><strong>{g.site}</strong> ({g.count}) : {g.entities.slice(0, 15).map((e) => `${e.name || e.ip || e.key} [${e.status}]`).join(", ")}{g.entities.length > 15 ? " …" : ""}</li>)}</ul>
            </div>
          )}
          <div className="hub-table-scroll"><table><thead><tr><th>Entité</th><th>Site</th><th>Provenance</th><th>Confiance</th><th>Lieu</th><th>Coordonnées</th><th>Comment</th><th>Depuis</th></tr></thead>
            <tbody>{sortPositions(positions, provFilter).map((p) => { const st = provenanceStyle(p.provenance); return (
              <tr key={p.entity} style={{ cursor: "pointer" }} onClick={async () => { const d = await fetchEntity(cortexApiBase, p.entity); if (!d.error) { setEntity(d); setTab("entities"); openSheet(p.entity); } }}>
                <td><strong>{p.name || p.ip || p.entity}</strong> <span className="muted">{p.kind ? KIND_LABEL[p.kind] || p.kind : ""}</span></td><td>{p.site || "—"}</td>
                <td><Tone tone={st.tone} title={st.help}>{p.provenance}</Tone></td><td>{pct(p.confidence)}</td><td className="muted">{p.place || "—"}</td>
                <td className="muted">{p.lat?.toFixed(5)}, {p.lon?.toFixed(5)}</td><td className="muted">{chainText(p)} <code>{p.principle}</code></td><td className="muted">{p.changed_at || p.first_at}</td>
              </tr>); })}</tbody></table></div>
        </div>
      )}

      {tab === "map" && (
        <div className="hub-card hub-settings-section">
          <p className="muted" style={{ margin: "0 0 6px" }}>Éclairage carto : couches activables sur les positions mémorisées. {layers?.summary && <>{layers.summary.positioned} positionnée(s), {layers.summary.unpositioned} sans position, {layers.summary.incidents} halo(s) d'incident, {layers.summary.unsupervised} sans supervision, {layers.summary.places} lieu(x), {layers.summary.dependencies} chemin(s).</>}</p>
          <p style={{ margin: "0 0 6px" }}>{LAYERS.map((l) => <label key={l.id} title={l.help} style={{ marginRight: 12 }}><input type="checkbox" checked={activeLayers.has(l.id)} onChange={() => setActiveLayers((s) => { const n = new Set(s); if (n.has(l.id)) n.delete(l.id); else n.add(l.id); return n; })} /> {l.label}</label>)}
            <span className="muted"> · légende : {PROVENANCE.map(([p, v]) => <span key={p} style={{ marginRight: 6 }}><span style={{ display: "inline-block", width: 10, height: 10, borderRadius: 5, background: v.color, verticalAlign: "middle" }} /> {p}</span>)}</span></p>
          <div style={{ height: 520, borderRadius: 8, overflow: "hidden", border: "1px solid var(--border, #ddd)" }}>
            <MapContainer center={[46.6, 2.4]} zoom={6} style={{ height: "100%", width: "100%" }} scrollWheelZoom>
              <TileLayer attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>' url="https://tile.openstreetmap.org/{z}/{x}/{y}.png" />
              <FitBounds bounds={boundsOf(layers?.positions?.features)} />
              {activeLayers.has("density") && (layers?.density?.features || []).map((f) => <CircleMarker key={`d-${f.properties.place}`} center={[f.geometry.coordinates[1], f.geometry.coordinates[0]]} radius={f.properties.radius} pathOptions={{ color: "#2f6fd6", weight: 1, fillColor: "#2f6fd6", fillOpacity: 0.12 }}><Popup><strong>{f.properties.name}</strong> ({f.properties.kind || "lieu"})<br />{f.properties.count} entité(s), {f.properties.supervised} supervisée(s), {f.properties.unsupervised} sans supervision, {f.properties.incidents} incident(s)</Popup></CircleMarker>)}
              {activeLayers.has("incidents") && (layers?.incidents?.features || []).map((f) => <CircleMarker key={`i-${f.properties.key}`} center={[f.geometry.coordinates[1], f.geometry.coordinates[0]]} radius={f.properties.radius} pathOptions={{ color: SEV_COLOR[f.properties.severity] || "#999", weight: 2, fillColor: SEV_COLOR[f.properties.severity] || "#999", fillOpacity: 0.25 }}><Popup><strong>{f.properties.title}</strong><br />{SEV[f.properties.severity]?.label} · {f.properties.entities} entité(s) · confiance {pct(f.properties.confidence)}<br /><button className="secondary ss-origin" onClick={() => { setTab("incidents"); openDetail(f.properties.key); }}>ouvrir l'incident</button></Popup></CircleMarker>)}
              {activeLayers.has("dependencies") && (layers?.dependencies?.features || []).map((f, k) => <Polyline key={`l-${k}`} positions={f.geometry.coordinates.map(([lon, lat]) => [lat, lon])} pathOptions={{ color: EDGE_STYLE[f.properties.kind]?.color || "#999", weight: 2, opacity: 0.8, dashArray: f.properties.kind === "powers_site" ? "4 4" : null }}><Popup>{f.properties.a_name} —{f.properties.kind}→ {f.properties.b_name}</Popup></Polyline>)}
              {activeLayers.has("positions") && (layers?.positions?.features || []).map((f) => { const st = provenanceStyle(f.properties.provenance); return <CircleMarker key={`p-${f.properties.key}`} center={[f.geometry.coordinates[1], f.geometry.coordinates[0]]} radius={5} pathOptions={{ color: st.color, weight: 1.5, fillColor: st.color, fillOpacity: 0.85 }}><Popup><strong>{f.properties.name}</strong> <span className="muted">{f.properties.key}</span><br />{f.properties.provenance} ({pct(f.properties.confidence)}) · {f.properties.place || f.properties.site || "sans lieu"}<br /><button className="secondary ss-origin" onClick={async () => { const d = await fetchEntity(cortexApiBase, f.properties.key); if (!d.error) { setEntity(d); setTab("entities"); openSheet(f.properties.key); } }}>fiche d'intervention</button></Popup></CircleMarker>; })}
              {activeLayers.has("unsupervised") && (layers?.unsupervised?.features || []).map((f) => <CircleMarker key={`u-${f.properties.key}`} center={[f.geometry.coordinates[1], f.geometry.coordinates[0]]} radius={11} pathOptions={{ color: "#c58a00", weight: 2, dashArray: "3 3", fill: false }}><Popup><strong>{f.properties.name}</strong><br />{f.properties.reason}</Popup></CircleMarker>)}
            </MapContainer>
          </div>
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
