import React, { useState, useEffect, useCallback } from "react";
import {
  fetchApps, upsertApp, fetchAppMap, fetchJourneys, fetchJourney, endJourney, deleteJourney, annotateStep, collectQueries, scanPhpArchiveForApp,
  createJourney, fetchCompare,
} from "./retroClient.js";
import { STATUS_LABELS, stepTitle, stepSummary, screensByTables, dbTablesLabel, relayCommand, journeyTree, storyboardFrame } from "./retroJourneys.js";
import GeneratedAppView from "./GeneratedAppView.jsx";
import UnifiedToolView from "./UnifiedToolView.jsx";

// Parcours applicatifs (livraison #441, backlog 30 volet 2 -- « schéma
// fonctionnel de l'interface ») : la personne parcourt l'application réelle
// avec l'extension Firefox + l'agent relais ; ici on voit les parcours, chaque
// étape (écran, actions, requêtes, tables), la carte fonctionnelle écrans ↔
// routes ↔ tables (code scanné + journal SQL réel via dba-api).
export default function RetroJourneysPanel({ retroApiBase, connections, dbaApiBase }) {
  const [apps, setApps] = useState([]);
  const [tokenConfigured, setTokenConfigured] = useState(true);
  const [app, setApp] = useState("");
  const [newApp, setNewApp] = useState({ label: "", base_url: "", dba_connection_id: "", dba_database: "" });
  const [journeys, setJourneys] = useState([]);
  const [journey, setJourney] = useState(null);
  const [appMap, setAppMap] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState(null);
  const [scanning, setScanning] = useState(false);
  // #443 : rejeu pas à pas (storyboard) et comparaison avec le parent (rejeu)
  const [frame, setFrame] = useState(0);
  const [compare, setCompare] = useState(null);
  // #444 : application générée (phase 2)
  const [showGenerated, setShowGenerated] = useState(false);
  // #445 : outil unique (phase 3)
  const [showUnified, setShowUnified] = useState(false);

  const loadApps = useCallback(async () => {
    const r = await fetchApps(retroApiBase);
    if (r.error) { setError(r.error); return; }
    setApps(r.apps || []); setTokenConfigured(!!r.relay_token_configured);
    if (!app && r.apps?.length) setApp(r.apps[0].label);
  }, [retroApiBase, app]);
  useEffect(() => { loadApps(); }, [loadApps]);

  const loadJourneys = useCallback(async () => {
    if (!app) { setJourneys([]); setAppMap(null); return; }
    const r = await fetchJourneys(retroApiBase, app);
    if (!r.error) setJourneys(r.journeys || []);
    const m = await fetchAppMap(retroApiBase, app);
    if (!m.error) setAppMap(m);
  }, [retroApiBase, app]);
  useEffect(() => { loadJourneys(); }, [loadJourneys]);

  async function openJourney(id) {
    const r = await fetchJourney(retroApiBase, id);
    if (r.error) { setError(r.error); return; }
    setJourney(r); setFrame(0); setCompare(null);
    if (r.parent_id && r.kind === "replay") {
      const c = await fetchCompare(retroApiBase, r.parent_id, r.id);
      if (!c.error) setCompare(c);
    }
  }
  async function handleSubJourney(step) {
    const name = window.prompt(`Nom du sous-parcours qui part de l'étape ${step.n} (${stepTitle(step)}) :`, "");
    if (name === null) return;
    const r = await createJourney(retroApiBase, { app: journey.app, name: name || `sous-parcours depuis l'étape ${step.n}`, parent_id: journey.id, branch_step: step.n, tester: journey.tester });
    if (r.error) { setError(r.error); return; }
    setNotice(`sous-parcours « ${r.name} » créé (en cours) : dans le navigateur, revenez à l'écran de l'étape ${step.n}, puis dans le popup de l'extension choisissez-le et « Reprendre » -- ce qui suit s'y enregistre.`);
    await loadJourneys();
  }
  async function handleSaveApp(e) {
    e.preventDefault();
    const body = { label: newApp.label.trim(), base_url: newApp.base_url.trim() || null,
      dba_connection_id: newApp.dba_connection_id ? Number(newApp.dba_connection_id) : null, dba_database: newApp.dba_database.trim() || null };
    if (!body.label) return;
    const r = await upsertApp(retroApiBase, body);
    if (r.error) setError(r.error); else { setNotice(`application « ${r.label} » enregistrée`); setNewApp({ label: "", base_url: "", dba_connection_id: "", dba_database: "" }); await loadApps(); setApp(r.label); }
  }
  async function handleScan(e) {
    const file = e.target.files[0];
    if (!file || !app) return;
    setScanning(true); setError(null);
    const r = await scanPhpArchiveForApp(retroApiBase, file, app);
    setScanning(false); e.target.value = "";
    if (r.error) setError(r.error);
    else { setNotice(`code de « ${app} » analysé : ${r.routes?.length || 0} route(s), ${Object.keys(r.classes || {}).length} classe(s), ${r.join_candidates?.length || 0} relation(s)`); await loadApps(); await loadJourneys(); if (journey) openJourney(journey.id); }
  }
  async function handleCollect(j) {
    setBusy(true); setError(null);
    const r = await collectQueries(retroApiBase, j.id, {});
    setBusy(false);
    if (r.error) setError(r.error);
    else { setNotice(`${r.collected} requête(s) SQL lue(s) dans le journal général, ${r.attributed} rattachée(s) à ${r.steps} étape(s), ${r.tables} table(s)`); await loadJourneys(); if (journey?.id === j.id) openJourney(j.id); }
  }
  async function handleEnd(j) {
    const r = await endJourney(retroApiBase, j.id, null);
    if (r.error) setError(r.error); else { await loadJourneys(); if (journey?.id === j.id) openJourney(j.id); }
  }
  async function handleDelete(j) {
    if (!window.confirm(`Supprimer le parcours « ${j.name || j.id} » et ses événements ?`)) return;
    const r = await deleteJourney(retroApiBase, j.id);
    if (r.error) setError(r.error); else { if (journey?.id === j.id) setJourney(null); await loadJourneys(); }
  }
  async function handleAnnotate(step, text) {
    const r = await annotateStep(retroApiBase, journey.id, step, text);
    if (r.error) setError(r.error);
  }

  const current = apps.find((a) => a.label === app);
  const matrix = screensByTables(appMap);

  return (
    <>
      <div className="hub-card hub-settings-section">
        <h2>Parcours applicatifs — rétro-ingénierie dynamique</h2>
        <p className="muted" style={{ marginTop: -4 }}>
          Parcourez l'application réelle avec l'<strong>extension Firefox</strong> (<code>retro/browser-extension</code>) et l'<strong>agent relais</strong> sur votre
          poste (<code>retro/relay/relay.py</code>) : chaque écran, action, formulaire et requête arrive ici, puis est rapproché des routes et tables
          trouvées dans le code (archive analysée ci-dessous) et des requêtes SQL réellement exécutées (journal général MySQL lu via la connexion DBA).
        </p>
        <pre className="np-secret" style={{ fontSize: 12 }}>{relayCommand(retroApiBase && retroApiBase.startsWith("http") ? retroApiBase : null, tokenConfigured)}</pre>
        {!tokenConfigured && <p style={{ color: "var(--warning, #b7791f)" }}>⚠️ <code>RETRO_RELAY_TOKEN</code> n'est pas défini dans <code>.env</code> : le central refuse les événements du relais.</p>}
        {error && <p style={{ color: "var(--danger)" }}>⚠️ {error}</p>}
        {notice && <p className="muted">{notice}</p>}

        <div style={{ display: "flex", gap: 8, alignItems: "flex-end", flexWrap: "wrap", marginBottom: 8 }}>
          <div className="hub-settings-row" style={{ margin: 0 }}>
            <label>Application</label>
            <select value={app} onChange={(e) => { setApp(e.target.value); setJourney(null); }}>
              <option value="">— choisir —</option>
              {apps.map((a) => <option key={a.label} value={a.label}>{a.label}{a.has_scan ? "" : " (code non analysé)"} · {a.journeys} parcours</option>)}
            </select>
          </div>
          {app && (
            <label className="secondary" style={{ cursor: "pointer", display: "inline-block" }}>
              {scanning ? "Analyse…" : "📤 Analyser le code (ZIP) pour cette application"}
              <input type="file" accept=".zip" onChange={handleScan} disabled={scanning} style={{ display: "none" }} />
            </label>
          )}
          {app && <button onClick={() => setShowGenerated((v) => !v)} title="écrans déduits des parcours, rendus avec la charte du hub sur les tables réelles">{showGenerated ? "Masquer l'application générée" : "⚙ Application générée"}</button>}
          {apps.length >= 2 && <button onClick={() => setShowUnified((v) => !v)} title="comparer les applications enregistrées et produire un outil de gestion unique">{showUnified ? "Masquer l'outil unique" : "🧩 Outil unique"}</button>}
          {current && <span className="muted">{current.base_url || "URL de base non renseignée"} · {current.has_scan ? `code analysé le ${current.scanned_at} (${current.scan_summary?.routes} routes)` : "code non analysé"} · {current.dba_connection_id ? `connexion DBA #${current.dba_connection_id}${current.dba_database ? ` / ${current.dba_database}` : ""}` : "sans connexion DBA (pas de journal SQL)"}</span>}
        </div>

        <form onSubmit={handleSaveApp} style={{ display: "flex", gap: 8, alignItems: "flex-end", flexWrap: "wrap" }}>
          <div className="hub-settings-row" style={{ margin: 0 }}><label>Nouvelle application / mise à jour</label><input value={newApp.label} onChange={(e) => setNewApp({ ...newApp, label: e.target.value })} placeholder="libellé (ex. gestion)" /></div>
          <div className="hub-settings-row" style={{ margin: 0 }}><label>URL de base</label><input value={newApp.base_url} onChange={(e) => setNewApp({ ...newApp, base_url: e.target.value })} placeholder="https://gestion.exemple.fr" /></div>
          <div className="hub-settings-row" style={{ margin: 0 }}><label>Connexion DBA</label>
            <select value={newApp.dba_connection_id} onChange={(e) => setNewApp({ ...newApp, dba_connection_id: e.target.value })}>
              <option value="">— aucune —</option>
              {(connections || []).map((c) => <option key={c.id} value={c.id}>{c.label || c.name || `#${c.id}`}</option>)}
            </select></div>
          <div className="hub-settings-row" style={{ margin: 0 }}><label>Base</label><input value={newApp.dba_database} onChange={(e) => setNewApp({ ...newApp, dba_database: e.target.value })} placeholder="gestion" /></div>
          <button type="submit" className="secondary">Enregistrer</button>
        </form>
      </div>

      {app && showGenerated && <GeneratedAppView retroApiBase={retroApiBase} dbaApiBase={dbaApiBase} app={app} onClose={() => setShowGenerated(false)} />}
      {showUnified && <UnifiedToolView retroApiBase={retroApiBase} dbaApiBase={dbaApiBase} apps={apps} onClose={() => setShowUnified(false)} />}

      {app && (
        <div className="hub-card hub-settings-section">
          <h2>Parcours de « {app} » ({journeys.length})</h2>
          {journeys.length === 0 ? <p className="muted">Aucun parcours : démarrez-en un depuis le popup de l'extension (le relais doit tourner).</p> : (
            <div className="hub-table-scroll">
              <table>
                <thead><tr><th>Parcours</th><th>Testeur</th><th>Début</th><th>État</th><th>Événements</th><th>Requêtes SQL</th><th></th></tr></thead>
                <tbody>{journeyTree(journeys).map((j) => (
                  <tr key={j.id} style={journey?.id === j.id ? { fontWeight: 600 } : undefined}>
                    <td style={{ paddingLeft: 8 + j.depth * 18 }}>{j.depth > 0 && <span className="muted">↳ </span>}<a href="#" onClick={(e) => { e.preventDefault(); openJourney(j.id); }}>{j.name || j.id}</a>
                      {j.kind === "replay" && <> <span className="na-chip" title="rejeu automatique du parcours parent">rejeu</span></>}
                      {j.branch_step && <> <span className="muted" style={{ fontSize: 12 }}>depuis l'étape {j.branch_step}</span></>}</td>
                    <td className="muted">{j.tester || "—"}</td><td className="muted">{j.started_at}</td>
                    <td>{STATUS_LABELS[j.status] || j.status}</td><td>{j.events_count}</td>
                    <td className="muted">{j.queries_count ? `${j.queries_count} (${j.queries_collected_at})` : "—"}</td>
                    <td style={{ whiteSpace: "nowrap" }}>
                      <button className="secondary" disabled={busy || !(current?.dba_connection_id)} title={current?.dba_connection_id ? "lire mysql.general_log entre le début et la fin du parcours" : "renseigner une connexion DBA sur l'application"} onClick={() => handleCollect(j)}>Collecter le SQL</button>{" "}
                      {j.status === "recording" && <button className="secondary" onClick={() => handleEnd(j)}>Terminer</button>}{" "}
                      <button className="secondary" onClick={() => handleDelete(j)}>🗑</button>
                    </td>
                  </tr>
                ))}</tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {journey && journey.steps.length > 0 && (
        <div className="hub-card hub-settings-section">
          <h2>Rejouer pas à pas — étape {Math.min(frame + 1, journey.steps.length)} / {journey.steps.length}</h2>
          <p className="muted" style={{ marginTop: -4 }}>Ce que l'écran montrait, ce qui a été fait, ce que la base a exécuté. Pour rejouer réellement dans le navigateur : popup de l'extension → choisir ce parcours → « Rejouer » (le rejeu est enregistré comme parcours enfant et comparé).</p>
          <div style={{ display: "flex", gap: 8, marginBottom: 8 }}>
            <button className="secondary" disabled={frame <= 0} onClick={() => setFrame(frame - 1)}>◀ Précédente</button>
            <button className="secondary" disabled={frame >= journey.steps.length - 1} onClick={() => setFrame(frame + 1)}>Suivante ▶</button>
            <button className="secondary" onClick={() => handleSubJourney(journey.steps[frame])} title="créer un parcours enfant qui part de cet écran">＋ Sous-parcours à partir d'ici</button>
          </div>
          {(() => {
            const f = storyboardFrame(journey.steps[frame]);
            const sc = journey.map.screens.find((x) => x.steps.includes(journey.steps[frame].n)) || {};
            return (
              <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: 12 }}>
                <div className="hub-card" style={{ margin: 0, border: "1px dashed var(--border, #ccc)" }}>
                  <div style={{ fontWeight: 600 }}><code>{f.title}</code>{sc.route && <span className="muted" style={{ fontSize: 12 }}> · {sc.route} → {sc.handler}</span>}</div>
                  {f.headings.map((h, i) => <div key={i} style={{ fontSize: i === 0 ? 18 : 14, fontWeight: 600, margin: "6px 0 2px" }}>{h}</div>)}
                  {f.forms.map((fm, i) => (
                    <fieldset key={i} style={{ margin: "8px 0", padding: 8 }}>
                      <legend className="muted" style={{ fontSize: 12 }}>{fm.method} {fm.action || "(même page)"}</legend>
                      {fm.fields.map((x) => <div key={x.name} style={{ display: "flex", gap: 8, alignItems: "center", margin: "3px 0" }}><span style={{ minWidth: 140 }}>{x.label || x.name}</span><span className="na-chip"><code>{x.name}</code> {x.type}</span></div>)}
                    </fieldset>
                  ))}
                  {f.tables.map((t, i) => (
                    <table key={i} style={{ margin: "8px 0" }}><thead><tr>{t.headers.map((h) => <th key={h}>{h}</th>)}</tr></thead><tbody><tr>{t.headers.map((h) => <td key={h} className="muted">…</td>)}</tr></tbody></table>
                  ))}
                  {f.links != null && <div className="muted" style={{ fontSize: 12 }}>{f.links} lien(s) sur l'écran</div>}
                </div>
                <div>
                  <div><span className="muted">Actions</span><br />{f.actions.length ? f.actions.map((a, i) => <div key={i}>{a}</div>) : "—"}</div>
                  <div style={{ marginTop: 8 }}><span className="muted">Requêtes SQL</span><br />{f.queries.length ? f.queries.map((q, i) => <div key={i}><code>{q}</code></div>) : "—"}</div>
                  {f.replay.length > 0 && <div style={{ marginTop: 8 }}><span className="muted">Rejeu</span><br />{f.replay.map((r, i) => <div key={i} style={{ color: r.ok ? "var(--success, #1a7f37)" : "var(--danger)" }}>{r.ok ? "✓" : "✗"} {r.action}{r.error ? ` — ${r.error}` : ""}</div>)}</div>}
                  {journey.steps[frame].annotation && <div style={{ marginTop: 8 }}><span className="muted">Annotation</span><br />{journey.steps[frame].annotation}</div>}
                </div>
              </div>
            );
          })()}
        </div>
      )}

      {compare && (
        <div className="hub-card hub-settings-section">
          <h2>Rejeu comparé au parcours d'origine — {compare.summary.same} étape(s) identique(s), {compare.summary.different} différente(s)</h2>
          <div className="hub-table-scroll">
            <table>
              <thead><tr><th>#</th><th>Origine</th><th>Rejeu</th><th>Différences</th></tr></thead>
              <tbody>{compare.pairs.map((p) => (
                <tr key={p.n} style={p.same ? undefined : { background: "var(--warning-bg, #fff7e6)" }}>
                  <td className="muted">{p.n}</td>
                  <td><code>{p.a ? `${p.a.method && p.a.method !== "GET" ? p.a.method + " " : ""}${p.a.path || p.a.label || "?"}` : "—"}</code>{p.a?.status != null && <span className="muted"> {p.a.status}</span>}</td>
                  <td><code>{p.b ? `${p.b.method && p.b.method !== "GET" ? p.b.method + " " : ""}${p.b.path || p.b.label || "?"}` : "—"}</code>{p.b?.status != null && <span className="muted"> {p.b.status}</span>}</td>
                  <td className="muted" style={{ fontSize: 12 }}>{p.same ? "identique" : p.diffs.join(" · ")}</td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        </div>
      )}

      {journey && (
        <div className="hub-card hub-settings-section">
          <h2>Étapes de « {journey.name || journey.id} » ({journey.steps.length})</h2>
          <p className="muted" style={{ marginTop: -4 }}>Une étape par écran demandé (requête de page) ou repère. Tables « code » : déduites de la route et du fichier PHP ; « base » : requêtes SQL réellement exécutées pendant l'étape.</p>
          <div className="hub-table-scroll">
            <table>
              <thead><tr><th>#</th><th>Écran / action</th><th>Route (code)</th><th>Résumé</th><th>Formulaires</th><th>Tables (code)</th><th>Tables (base)</th><th>Annotation</th></tr></thead>
              <tbody>{journey.steps.map((s) => {
                const sc = journey.map.screens.find((x) => x.steps.includes(s.n)) || {};
                return (
                  <tr key={s.n}>
                    <td className="muted">{s.n}</td>
                    <td><code>{stepTitle(s)}</code>{s.dom?.headings?.length ? <div className="muted" style={{ fontSize: 12 }}>{s.dom.headings.slice(0, 3).join(" · ")}</div> : null}</td>
                    <td className="muted">{sc.route ? <>{sc.route}<br /><span style={{ fontSize: 12 }}>{sc.handler}</span></> : "—"}</td>
                    <td className="muted">{stepSummary(s)}</td>
                    <td className="muted">{(s.forms || []).filter((f) => f.source === "submit").map((f, i) => <div key={i}>{f.method.toUpperCase()} {f.action} : {f.fields.join(", ")}</div>)}{s.inputs?.length ? <div style={{ fontSize: 12 }}>saisies : {s.inputs.map((i) => `${i.field}${i.value != null ? `=${i.value}` : i.length != null ? ` (${i.length} car.)` : ""}`).join(", ")}</div> : null}</td>
                    <td className="muted">{Object.keys(sc.code_tables || {}).join(", ") || "—"}</td>
                    <td className="muted">{dbTablesLabel(s.db_tables)}</td>
                    <td><input defaultValue={s.annotation || ""} placeholder="note…" onBlur={(e) => { if ((e.target.value || "") !== (s.annotation || "")) handleAnnotate(s.n, e.target.value); }} style={{ width: 140 }} /></td>
                  </tr>
                );
              })}</tbody>
            </table>
          </div>
        </div>
      )}

      {appMap && appMap.screens.length > 0 && (
        <div className="hub-card hub-settings-section">
          <h2>Schéma fonctionnel de « {app} » — {appMap.counts.screens} écran(s), {appMap.counts.with_route} avec route, {appMap.counts.tables} table(s), {appMap.journeys} parcours</h2>
          <div className="hub-table-scroll">
            <table>
              <thead><tr><th>Écran</th><th>Titres</th><th>Route → contrôleur</th><th>Fichiers</th><th>Formulaires (champs ↔ gabarit)</th><th>Tables</th></tr></thead>
              <tbody>{appMap.screens.map((s) => (
                <tr key={s.screen}>
                  <td><code>{s.screen}</code><div className="muted" style={{ fontSize: 12 }}>{s.visits} visite(s), {s.actions} action(s)</div></td>
                  <td className="muted">{s.titles.join(" / ") || "—"}</td>
                  <td className="muted">{s.route ? <>{s.route}<br /><span style={{ fontSize: 12 }}>{s.handler}</span></> : "aucune route trouvée"}</td>
                  <td className="muted" style={{ fontSize: 12 }}>{s.files.join(", ") || "—"}</td>
                  <td className="muted" style={{ fontSize: 12 }}>{s.forms.map((f, i) => <div key={i}>{f.method.toUpperCase()} {f.action} : {f.fields.join(", ")}</div>)}{s.template_fields.length ? <div>↔ {s.template_fields.map((t) => `${t.field} = ${t.template}`).join(", ")}</div> : null}</td>
                  <td className="muted">{s.tables.map((t) => <span key={t} className="na-chip" title={`${s.code_tables[t] ? "code : " + s.code_tables[t].join(", ") : ""}${s.db_tables[t] ? ` base : ${s.db_tables[t].reads}r/${s.db_tables[t].writes}w` : ""}`}>{t}{s.code_tables[t] && s.db_tables[t] ? " ✓✓" : s.db_tables[t] ? " (base)" : " (code)"}</span>)}</td>
                </tr>
              ))}</tbody>
            </table>
          </div>
          {matrix.tables.length > 0 && (
            <>
              <h3>Écrans × tables</h3>
              <div className="hub-table-scroll">
                <table>
                  <thead><tr><th>Écran</th>{matrix.tables.map((t) => <th key={t} style={{ writingMode: "vertical-rl", fontSize: 11 }}>{t}</th>)}</tr></thead>
                  <tbody>{matrix.rows.map((r) => (
                    <tr key={r.screen}><td><code>{r.screen}</code></td>{matrix.tables.map((t) => (
                      <td key={t} style={{ textAlign: "center" }} title={r.cells[t] === "both" ? "code et base" : r.cells[t] === "code" ? "déduit du code" : r.cells[t] === "db" ? "vu dans le journal SQL" : ""}>
                        {r.cells[t] === "both" ? "●" : r.cells[t] === "code" ? "◐" : r.cells[t] === "db" ? "◑" : ""}
                      </td>))}
                    </tr>
                  ))}</tbody>
                </table>
              </div>
              <p className="muted" style={{ fontSize: 12 }}>● code et journal SQL concordent · ◐ déduit du code seulement · ◑ vu dans le journal SQL seulement (à retrouver dans le code, ou table touchée indirectement)</p>
            </>
          )}
        </div>
      )}
    </>
  );
}
