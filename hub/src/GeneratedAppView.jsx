import React, { useState, useEffect, useCallback } from "react";
import { fetchUiSpec, saveUiSpec } from "./retroClient.js";
import { fetchTableColumnsForEdit, fetchTableRows, updateTableRow, insertTableRow } from "./schemaAnalyzerClient.js";
import { navScreens, listColumns, formScreenFor, editableFields, rowToValues, filterRows, specSummary } from "./generatedApp.js";

// Application générée (livraison #444, phase 2) : rend, avec la charte du
// hub (cartes, tableaux, formulaires), les écrans déduits des parcours --
// listes branchées sur les tables réelles via dba-api, fiches/formulaires
// qui écrivent dans ces tables (PUT/POST rows, mêmes garde-fous que
// l'Analyse de schémas : clé primaire jamais modifiée, colonnes validées
// contre le schéma). Ce que les parcours n'ont pas montré est marqué « à
// compléter » et modifiable dans l'onglet Spécification.
export default function GeneratedAppView({ retroApiBase, dbaApiBase, app, onClose }) {
  const [spec, setSpec] = useState(null);
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState(null);
  const [screenId, setScreenId] = useState(null);
  const [mode, setMode] = useState("app"); // app | spec
  const [tableCols, setTableCols] = useState({}); // table -> [{name, primary_key}]
  const [rows, setRows] = useState(null);       // {columns, rows, total_count}
  const [offset, setOffset] = useState(0);
  const [needle, setNeedle] = useState("");
  const [record, setRecord] = useState(null);   // {screen, values, pk} en édition ; pk null = création
  const [busy, setBusy] = useState(false);

  const load = useCallback(async (regenerate) => {
    setBusy(true); setError(null);
    const r = await fetchUiSpec(retroApiBase, app, regenerate);
    setBusy(false);
    if (r.error) { setError(r.error); return; }
    setSpec(r);
    const nav = navScreens(r);
    setScreenId((cur) => (cur && r.screens.some((s) => s.id === cur) ? cur : nav[0]?.id || r.screens[0]?.id || null));
    if (regenerate) setNotice(`spécification régénérée : ${specSummary(r)}`);
  }, [retroApiBase, app]);
  useEffect(() => { load(false); }, [load]);

  const screen = spec?.screens.find((s) => s.id === screenId) || null;
  const connId = spec?.dba_connection_id;
  const db = spec?.dba_database || null;

  const loadColumns = useCallback(async (table) => {
    if (!table || tableCols[table] || !connId) return;
    const cols = await fetchTableColumnsForEdit(dbaApiBase, connId, table, db);
    setTableCols((prev) => ({ ...prev, [table]: cols }));
  }, [dbaApiBase, connId, db, tableCols]);

  useEffect(() => {
    setRows(null); setRecord(null); setOffset(0); setNeedle("");
    if (!screen?.table || !connId) return;
    loadColumns(screen.table);
    if (screen.kind === "list" || screen.kind === "other") {
      fetchTableRows(dbaApiBase, connId, screen.table, db, 50, 0).then((r) => { if (r.error) setError(r.error); else setRows(r); });
    }
  }, [screenId, connId]); // eslint-disable-line react-hooks/exhaustive-deps

  async function page(newOffset) {
    const r = await fetchTableRows(dbaApiBase, connId, screen.table, db, 50, newOffset);
    if (r.error) setError(r.error); else { setRows(r); setOffset(newOffset); }
  }
  function openRecord(listScreen, row) {
    const form = formScreenFor(spec, listScreen) || listScreen;
    const values = rowToValues(rows.columns, row);
    const pkCol = form.pk || (tableCols[listScreen.table] || []).find((c) => c.primary_key)?.name;
    setRecord({ screen: form, values, pk: pkCol ? values[pkCol] : null, pkCol });
  }
  function newRecord(listScreen) {
    const form = formScreenFor(spec, listScreen) || listScreen;
    setRecord({ screen: form, values: {}, pk: null, pkCol: form.pk });
  }
  async function saveRecord(e) {
    e.preventDefault();
    const form = record.screen;
    const fields = editableFields(form);
    const payload = {};
    for (const f of fields) if (record.values[f.column] !== undefined) payload[f.column] = record.values[f.column];
    if (!Object.keys(payload).length) { setError("aucun champ rattaché à une colonne : compléter la spécification"); return; }
    setBusy(true);
    const r = record.pk != null ? await updateTableRow(dbaApiBase, connId, form.table, db, record.pk, payload) : await insertTableRow(dbaApiBase, connId, form.table, db, payload);
    setBusy(false);
    if (r.error) { setError(r.error); return; }
    setNotice(record.pk != null ? `ligne ${record.pk} de ${form.table} mise à jour` : `ligne créée dans ${form.table} (clé ${r.pk_value})`);
    setRecord(null);
    if (screen?.table) page(offset);
  }
  async function persistSpec(next) {
    setSpec(next);
    const r = await saveUiSpec(retroApiBase, app, next);
    if (r.error) setError(r.error); else setNotice("spécification enregistrée");
  }
  function updateScreen(id, patch) {
    persistSpec({ ...spec, screens: spec.screens.map((s) => (s.id === id ? { ...s, ...patch } : s)) });
  }

  if (!spec) return <div className="hub-card hub-settings-section"><p className="muted">{error ? `⚠️ ${error}` : "Chargement de la spécification…"}</p></div>;
  const nav = navScreens(spec);
  const cols = screen?.table ? (tableCols[screen.table] || []).map((c) => c.name) : [];

  return (
    <div className="hub-card hub-settings-section" style={{ borderColor: "var(--accent, #2b5797)" }}>
      <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
        <h2 style={{ margin: 0 }}>Application générée — « {app} »</h2>
        <span className="muted">{specSummary(spec)}{spec.generated_at ? ` · générée le ${spec.generated_at}` : ""}</span>
        <span style={{ flex: 1 }} />
        <button className={mode === "app" ? "" : "secondary"} onClick={() => setMode("app")}>Application</button>
        <button className={mode === "spec" ? "" : "secondary"} onClick={() => setMode("spec")}>Spécification</button>
        <button className="secondary" disabled={busy} onClick={() => load(true)} title="recalculer depuis les parcours, la carte et les colonnes réelles (choix manuels conservés)">↻ Régénérer</button>
        <button className="secondary" onClick={onClose}>Fermer</button>
      </div>
      {error && <p style={{ color: "var(--danger)" }}>⚠️ {error}</p>}
      {notice && <p className="muted">{notice}</p>}
      {!connId && <p style={{ color: "var(--warning, #b7791f)" }}>⚠️ Aucune connexion DBA sur l'application : les écrans s'affichent sans données (renseigner la connexion, puis Régénérer).</p>}

      {mode === "app" && (
        <div style={{ display: "grid", gridTemplateColumns: "200px 1fr", gap: 16, marginTop: 8 }}>
          <nav>
            {nav.length === 0 && <p className="muted">Aucun écran de navigation : voir Spécification.</p>}
            {nav.map((s) => (
              <button key={s.id} className={s.id === screenId ? "" : "secondary"} style={{ display: "block", width: "100%", textAlign: "left", marginBottom: 4 }} onClick={() => setScreenId(s.id)}>
                {s.kind === "list" ? "☰ " : s.kind === "form" ? "✎ " : "▸ "}{s.title}
              </button>
            ))}
          </nav>
          <div>
            {screen && (
              <>
                <h3 style={{ marginTop: 0 }}>{screen.title} <span className="muted" style={{ fontWeight: 400, fontSize: 12 }}>{screen.kind} · <code>{screen.screen}</code>{screen.table ? ` · table ${screen.table}` : " · sans table"}</span></h3>
                {screen.todo?.length > 0 && <p style={{ color: "var(--warning, #b7791f)", fontSize: 12 }}>À compléter : {screen.todo.join(" ; ")}</p>}
                {!record && (screen.kind === "list" || screen.kind === "other") && screen.table && (
                  <>
                    <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 8 }}>
                      <input placeholder="filtrer…" value={needle} onChange={(e) => setNeedle(e.target.value)} style={{ maxWidth: 240 }} />
                      <span className="muted">{rows ? `${rows.total_count ?? rows.rows.length} ligne(s)` : "…"}</span>
                      <span style={{ flex: 1 }} />
                      <button className="secondary" disabled={!rows || offset === 0} onClick={() => page(Math.max(0, offset - 50))}>◀</button>
                      <button className="secondary" disabled={!rows || rows.rows.length < 50} onClick={() => page(offset + 50)}>▶</button>
                      <button onClick={() => newRecord(screen)}>＋ Nouveau</button>
                    </div>
                    {rows && (
                      <div className="hub-table-scroll">
                        <table>
                          <thead><tr>{listColumns(screen, cols).map((c) => <th key={c.column}>{c.label}</th>)}<th /></tr></thead>
                          <tbody>{filterRows(rows.rows, rows.columns, needle).map((r, i) => (
                            <tr key={i}>
                              {listColumns(screen, cols).map((c) => <td key={c.column}>{String(r[rows.columns.indexOf(c.column)] ?? "")}</td>)}
                              <td><button className="secondary" onClick={() => openRecord(screen, r)}>Ouvrir</button></td>
                            </tr>
                          ))}</tbody>
                        </table>
                      </div>
                    )}
                  </>
                )}
                {!record && (screen.kind === "form" || screen.kind === "detail") && screen.table && (
                  <p className="muted">Fiche « {screen.title} » : ouvrez une ligne depuis une liste de la table <code>{screen.table}</code>, ou <button className="secondary" onClick={() => newRecord(screen)}>créer une nouvelle ligne</button>.</p>
                )}
                {!screen.table && <p className="muted">Cet écran n'est rattaché à aucune table : choisissez-en une dans l'onglet Spécification.</p>}
                {record && (
                  <form onSubmit={saveRecord} className="hub-card" style={{ margin: 0 }}>
                    <h4 style={{ marginTop: 0 }}>{record.pk != null ? `${record.screen.title} — ${record.pkCol} ${record.pk}` : `${record.screen.title} — nouvelle ligne`}</h4>
                    {editableFields(record.screen).length === 0 && <p style={{ color: "var(--warning, #b7791f)" }}>Aucun champ rattaché à une colonne : compléter la spécification.</p>}
                    {editableFields(record.screen).map((f) => (
                      <div className="hub-settings-row" key={f.name}>
                        <label title={`champ ${f.name} → colonne ${f.column} (${f.source}, ${Math.round((f.confidence || 0) * 100)} %)`}>{f.label || f.name}{f.required ? " *" : ""}</label>
                        {f.type === "textarea" ? (
                          <textarea value={record.values[f.column] ?? ""} onChange={(e) => setRecord({ ...record, values: { ...record.values, [f.column]: e.target.value } })} />
                        ) : f.type === "checkbox" ? (
                          <input type="checkbox" checked={!!record.values[f.column] && record.values[f.column] !== "0"} onChange={(e) => setRecord({ ...record, values: { ...record.values, [f.column]: e.target.checked ? 1 : 0 } })} />
                        ) : (
                          <input type={f.type === "date" ? "date" : "text"} name={f.column} inputMode={f.type === "number" ? "numeric" : f.type === "email" ? "email" : undefined} value={record.values[f.column] ?? ""} onChange={(e) => setRecord({ ...record, values: { ...record.values, [f.column]: e.target.value } })} />
                        )}
                      </div>
                    ))}
                    <div style={{ display: "flex", gap: 8 }}>
                      <button type="submit" disabled={busy}>{record.pk != null ? "Enregistrer" : "Créer"}</button>
                      <button type="button" className="secondary" onClick={() => setRecord(null)}>Annuler</button>
                    </div>
                  </form>
                )}
              </>
            )}
          </div>
        </div>
      )}

      {mode === "spec" && (
        <div className="hub-table-scroll" style={{ marginTop: 8 }}>
          <table>
            <thead><tr><th>Écran</th><th>Titre</th><th>Genre</th><th>Table</th><th>Colonnes / champs</th><th>Liens · actions</th><th>Nav.</th></tr></thead>
            <tbody>{spec.screens.map((s) => (
              <tr key={s.id} style={s.hidden ? { opacity: 0.5 } : undefined}>
                <td><code>{s.screen}</code><div className="muted" style={{ fontSize: 12 }}>{s.route ? `${s.route} → ${s.handler}` : "route non trouvée"} · {s.visits} visite(s)</div></td>
                <td><input value={s.title || ""} onChange={(e) => updateScreen(s.id, { title: e.target.value, title_manual: true })} style={{ width: 150 }} /></td>
                <td><select value={s.kind} onChange={(e) => updateScreen(s.id, { kind: e.target.value, nav: ["list", "form", "detail"].includes(e.target.value) && !s.hidden })}>
                  {["list", "form", "detail", "action", "other"].map((k) => <option key={k} value={k}>{k}</option>)}</select></td>
                <td>
                  <select value={s.table || ""} onChange={(e) => updateScreen(s.id, { table: e.target.value || null, table_manual: true, table_source: "choisi à la main", table_confidence: 1 })}>
                    <option value="">— aucune —</option>
                    {Object.keys(spec.tables || {}).map((t) => <option key={t} value={t}>{t}</option>)}
                  </select>
                  <div className="muted" style={{ fontSize: 12 }}>{s.table_source || ""}{s.table_confidence ? ` (${Math.round(s.table_confidence * 100)} %)` : ""}</div>
                </td>
                <td className="muted" style={{ fontSize: 12 }}>
                  {s.columns?.length > 0 && <div>colonnes : {s.columns.map((c) => `${c.label}${c.column ? ` → ${c.column}` : " (?)"}`).join(", ")}</div>}
                  {s.fields?.length > 0 && <div>champs : {s.fields.map((f) => `${f.name}${f.column ? ` → ${f.column}` : " (?)"}`).join(", ")}</div>}
                  {s.todo?.length > 0 && <div style={{ color: "var(--warning, #b7791f)" }}>{s.todo.join(" ; ")}</div>}
                </td>
                <td className="muted" style={{ fontSize: 12 }}>{(s.links || []).map((l) => `→ ${l.screen}`).join(", ")}{s.actions?.length ? ` · ${s.actions.map((a) => `${a.method} ${a.path}${a.writes?.length ? ` (écrit ${a.writes.join(", ")})` : ""}`).join(", ")}` : ""}</td>
                <td><input type="checkbox" checked={!s.hidden} onChange={(e) => updateScreen(s.id, { hidden: !e.target.checked, nav: e.target.checked && ["list", "form", "detail"].includes(s.kind) })} /></td>
              </tr>
            ))}</tbody>
          </table>
        </div>
      )}
    </div>
  );
}
