import React, { useState, useEffect } from "react";
import { looksLikeHtml, sanitizeHtml } from "./htmlContentUtils.js";
import { fetchTunnels, fetchConnections as fetchSshConnections, startTunnel, stopTunnel, fetchConnectionUsageHistory } from "./sshTunnelsClient.js";
import {
  fetchDbaConnections,
  analyzeConnection,
  importProposals,
  fetchRelations,
  createRelation,
  updateRelation,
  deleteRelation,
  validateRelation,
  graphExportUrl,
  fetchTableColumnsForEdit,
  fetchTableRows,
  updateTableRow,
  insertTableRow,
  deleteTableRows,
  executeSql,
  sqlLiteral,
} from "./schemaAnalyzerClient.js";

// Analyse de schémas (hub), livraison #156 -- interface pour
// schema-analyzer-api (#151-#154, jusqu'ici accessible seulement via
// curl). S'appuie sur dba-api en LECTURE SEULE pour lister les
// connexions existantes -- créer/modifier une connexion reste le
// rôle de l'onglet DBA, jamais dupliqué ici.
//
// Quatre sous-onglets une fois une analyse lancée (même motif que
// LogsManagerView -- sous-onglets d'un même écran, pas des écrans
// séparés) : Schéma (tables/colonnes + colonnes-listes détectées),
// Relations (l'éditeur -- importer/valider/rejeter/ajouter/
// supprimer), Export (JSON/XML des relations CONFIRMÉES uniquement),
// Données (livraison #178, APPROXIMATION -- voir hub/README.md :
// navigateur/éditeur de LIGNES appuyé DIRECTEMENT sur le CRUD déjà
// existant de dba-api, enrichi par les relations CONFIRMÉES pour un
// "aller à la ligne liée").

const STATUS_LABELS = { proposed: "Proposée", confirmed: "Confirmée", rejected: "Rejetée" };
const EMPTY_MANUAL_FORM = { from_table: "", from_column: "", to_table: "", to_column: "" };

export default function SchemaAnalyzerView({ onBack, dbaApiBase, schemaApiBase, sshTunnelsApiBase, login }) {
  const [connections, setConnections] = useState([]);
  // Catalogue SGBD (livraison #221, backlog item 11) -- référence
  // croisée SANS FUSION avec les connexions dba-api existantes
  // (jamais touché leur schéma) : un tunnel SSH est considéré
  // "utilisé" par une connexion DBA si celle-ci pointe sur
  // 127.0.0.1/localhost avec le PORT LOCAL du tunnel -- la seule
  // information disponible pour faire ce lien, aucune référence
  // explicite stockée nulle part entre les deux systèmes.
  const [catalogTunnels, setCatalogTunnels] = useState([]);
  const [catalogSshConnections, setCatalogSshConnections] = useState([]);
  const [catalogLoaded, setCatalogLoaded] = useState(false);
  const [catalogBusy, setCatalogBusy] = useState(false);
  const [catalogHistoryFor, setCatalogHistoryFor] = useState(null);
  const [catalogHistory, setCatalogHistory] = useState({});
  const [showCatalog, setShowCatalog] = useState(false);
  const [connectionId, setConnectionId] = useState("");
  const [database, setDatabase] = useState("");
  const [analysis, setAnalysis] = useState(null);
  const [relations, setRelations] = useState([]);
  const [expandedTables, setExpandedTables] = useState(() => new Set());
  const [analyzing, setAnalyzing] = useState(false);
  const [busy, setBusy] = useState(false);
  // Diode "en cours" (livraison #209, extension item 18) -- dédiée à
  // l'import des propositions, distincte de `busy` (global).
  const [importingProposals, setImportingProposals] = useState(false);
  const [error, setError] = useState(null);
  const [importSummary, setImportSummary] = useState(null);
  const [subTab, setSubTab] = useState("schema");
  const [manualForm, setManualForm] = useState(EMPTY_MANUAL_FORM);
  // Validation contre les vraies données (livraison #241) --
  // {[relationId]: résultat ou "loading" ou {error}}.
  const [validationResults, setValidationResults] = useState({});

  // --- Onglet Données (livraison #178) ---
  const [dataTable, setDataTable] = useState("");
  const [dataColumns, setDataColumns] = useState([]);
  const [dataRows, setDataRows] = useState(null); // {columns, rows, total_count}
  const [dataOffset, setDataOffset] = useState(0);
  const [dataError, setDataError] = useState(null);
  const [dataBusy, setDataBusy] = useState(false);
  const [editingCell, setEditingCell] = useState(null); // {rowIndex, colName}
  // Fiche HTML (livraison #214, backlog item 7) -- {colName, value}
  // du contenu en cours d'aperçu, ou null. Une seule fiche à la fois
  // (jamais plusieurs ouvertes en parallèle -- inutile pour ce cas
  // d'usage, complexifierait l'affichage sans bénéfice).
  const [htmlPreview, setHtmlPreview] = useState(null);
  const [editingValue, setEditingValue] = useState("");
  const [selectedForDelete, setSelectedForDelete] = useState(() => new Set());
  const [showInsertForm, setShowInsertForm] = useState(false);
  const [insertValues, setInsertValues] = useState({});
  const [jumpNotice, setJumpNotice] = useState(null);
  const DATA_PAGE_SIZE = 25;

  useEffect(() => {
    let cancelled = false;
    fetchDbaConnections(dbaApiBase).then((list) => {
      if (!cancelled) setConnections(list);
    });
    return () => {
      cancelled = true;
    };
  }, [dbaApiBase]);

  async function loadRelations(connId, db) {
    const list = await fetchRelations(schemaApiBase, connId, db);
    setRelations(list);
  }

  async function handleAnalyze() {
    if (!connectionId) return;
    setAnalyzing(true);
    setError(null);
    setImportSummary(null);
    const result = await analyzeConnection(schemaApiBase, connectionId, database);
    setAnalyzing(false);
    if (result.error) {
      setError(result.error);
      setAnalysis(null);
      return;
    }
    setAnalysis(result);
    setSubTab("schema");
    loadRelations(connectionId, database);
  }

  async function loadCatalog() {
    setCatalogBusy(true);
    const [tunnels, sshConns] = await Promise.all([
      fetchTunnels(sshTunnelsApiBase),
      fetchSshConnections(sshTunnelsApiBase),
    ]);
    setCatalogTunnels(Array.isArray(tunnels) ? tunnels : []);
    setCatalogSshConnections(Array.isArray(sshConns) ? sshConns : []);
    setCatalogLoaded(true);
    setCatalogBusy(false);
  }

  function matchingDbaConnections(localPort) {
    // Correspondance par host+port UNIQUEMENT -- jamais une
    // référence stockée explicitement (voir commentaire d'état plus
    // haut). `password` (en clair côté dba-api, caractéristique
    // EXISTANTE de ce module, jamais introduite ici) n'est JAMAIS
    // affiché -- seul `label` est utilisé.
    return connections.filter((c) => ["127.0.0.1", "localhost"].includes(c.host) && Number(c.port) === Number(localPort));
  }

  async function handleCatalogToggleTunnel(tunnel) {
    setCatalogBusy(true);
    if (tunnel.status === "running") {
      await stopTunnel(sshTunnelsApiBase, tunnel.id);
    } else {
      await startTunnel(sshTunnelsApiBase, tunnel.id);
    }
    await loadCatalog();
  }

  async function handleCatalogToggleHistory(connectionId) {
    if (catalogHistoryFor === connectionId) {
      setCatalogHistoryFor(null);
      return;
    }
    setCatalogHistoryFor(connectionId);
    if (!catalogHistory[connectionId]) {
      const result = await fetchConnectionUsageHistory(sshTunnelsApiBase, connectionId);
      setCatalogHistory((prev) => ({ ...prev, [connectionId]: Array.isArray(result) ? result : [] }));
    }
  }

  async function handleImportProposals() {
    setImportingProposals(true);
    setBusy(true);
    setError(null);
    const result = await importProposals(schemaApiBase, connectionId, database, login);
    setImportingProposals(false);
    setBusy(false);
    if (result.error) {
      setError(result.error);
      return;
    }
    setImportSummary({ imported: result.imported.length, skipped: result.skipped.length });
    loadRelations(connectionId, database);
  }

  async function handleStatusChange(relationId, status) {
    setBusy(true);
    const result = await updateRelation(schemaApiBase, relationId, { status });
    setBusy(false);
    if (result.error) {
      setError(result.error);
      return;
    }
    loadRelations(connectionId, database);
  }

  async function handleDelete(relationId) {
    setBusy(true);
    await deleteRelation(schemaApiBase, relationId);
    setBusy(false);
    loadRelations(connectionId, database);
  }

  async function handleValidateRelation(r) {
    setValidationResults((prev) => ({ ...prev, [r.id]: "loading" }));
    const result = await validateRelation(schemaApiBase, {
      connection_id: connectionId,
      database,
      from_table: r.from_table,
      from_column: r.from_column,
      to_table: r.to_table,
      to_column: r.to_column,
      relation_type: r.relation_type,
    });
    setValidationResults((prev) => ({ ...prev, [r.id]: result }));
  }

  async function handleManualSubmit(e) {
    e.preventDefault();
    const { from_table, from_column, to_table, to_column } = manualForm;
    if (!from_table.trim() || !from_column.trim() || !to_table.trim() || !to_column.trim()) return;
    setBusy(true);
    setError(null);
    const result = await createRelation(schemaApiBase, {
      connection_id: Number(connectionId),
      database: database || undefined,
      from_table: from_table.trim(),
      from_column: from_column.trim(),
      to_table: to_table.trim(),
      to_column: to_column.trim(),
      actor: login,
    });
    setBusy(false);
    if (result.error) {
      setError(result.error);
      return;
    }
    setManualForm(EMPTY_MANUAL_FORM);
    loadRelations(connectionId, database);
  }

  function toggleTable(tableName) {
    setExpandedTables((prev) => {
      const next = new Set(prev);
      if (next.has(tableName)) next.delete(tableName);
      else next.add(tableName);
      return next;
    });
  }

  // --- Onglet Données (livraison #178) ---
  async function loadDataRows(table, offset) {
    setDataBusy(true);
    setDataError(null);
    const [cols, rowsResult] = await Promise.all([
      fetchTableColumnsForEdit(dbaApiBase, connectionId, table, database),
      fetchTableRows(dbaApiBase, connectionId, table, database, DATA_PAGE_SIZE, offset),
    ]);
    setDataBusy(false);
    setDataColumns(cols);
    if (rowsResult.error) {
      setDataError(rowsResult.error);
      setDataRows(null);
      return;
    }
    setDataRows(rowsResult);
  }

  function handleSelectDataTable(table) {
    setDataTable(table);
    setDataOffset(0);
    setSelectedForDelete(new Set());
    setJumpNotice(null);
    setShowInsertForm(false);
    if (table) loadDataRows(table, 0);
    else {
      setDataRows(null);
      setDataColumns([]);
    }
  }

  function pkColumnName() {
    const pk = dataColumns.find((c) => c.primary_key);
    return pk ? pk.name : null;
  }

  function startEditCell(rowIndex, colName, currentValue) {
    const col = dataColumns.find((c) => c.name === colName);
    if (col && col.primary_key) return; // clé primaire jamais éditable, même règle que dba-api
    setEditingCell({ rowIndex, colName });
    setEditingValue(currentValue === null || currentValue === undefined ? "" : String(currentValue));
  }

  async function commitEditCell() {
    if (!editingCell || !dataRows) return;
    const pkCol = pkColumnName();
    if (!pkCol) {
      setDataError("cette table n'a pas de clé primaire identifiable, édition impossible");
      setEditingCell(null);
      return;
    }
    const pkIndex = dataRows.columns.indexOf(pkCol);
    const row = dataRows.rows[editingCell.rowIndex];
    const pkValue = row[pkIndex];
    setDataBusy(true);
    const result = await updateTableRow(dbaApiBase, connectionId, dataTable, database, pkValue, { [editingCell.colName]: editingValue });
    setDataBusy(false);
    setEditingCell(null);
    if (result.error) {
      setDataError(result.error);
      return;
    }
    loadDataRows(dataTable, dataOffset);
  }

  function toggleSelectForDelete(pkValue) {
    setSelectedForDelete((prev) => {
      const next = new Set(prev);
      if (next.has(pkValue)) next.delete(pkValue);
      else next.add(pkValue);
      return next;
    });
  }

  async function handleDeleteSelectedRows() {
    if (selectedForDelete.size === 0) return;
    setDataBusy(true);
    const result = await deleteTableRows(dbaApiBase, connectionId, dataTable, database, Array.from(selectedForDelete));
    setDataBusy(false);
    if (result.error) {
      setDataError(result.error);
      return;
    }
    setSelectedForDelete(new Set());
    loadDataRows(dataTable, dataOffset);
  }

  async function handleInsertRow(e) {
    e.preventDefault();
    setDataBusy(true);
    const result = await insertTableRow(dbaApiBase, connectionId, dataTable, database, insertValues);
    setDataBusy(false);
    if (result.error) {
      setDataError(result.error);
      return;
    }
    setInsertValues({});
    setShowInsertForm(false);
    loadDataRows(dataTable, dataOffset);
  }

  /** "Aller à la ligne liée" -- APPROXIMATION (voir hub/README.md) :
   * pour la colonne cliquée, cherche une relation CONFIRMÉE dont
   * from_table/from_column correspondent, bascule sur to_table
   * FILTRÉE via un SELECT direct (executeSql, valeur échappée par
   * sqlLiteral) sur to_column = valeur. Résultat affiché comme la
   * page de données de la table cible (une seule ligne si trouvée).*/
  async function handleJumpToRelated(colName, value) {
    const rel = relations.find(
      (r) => r.status === "confirmed" && r.from_table === dataTable && r.from_column === colName,
    );
    if (!rel) return;
    setDataBusy(true);
    setDataError(null);
    const [cols, sqlResult] = await Promise.all([
      fetchTableColumnsForEdit(dbaApiBase, connectionId, rel.to_table, database),
      executeSql(dbaApiBase, connectionId, database, `SELECT * FROM ${rel.to_table} WHERE ${rel.to_column} = ${sqlLiteral(value)}`),
    ]);
    setDataBusy(false);
    if (sqlResult.error) {
      setDataError(sqlResult.error);
      return;
    }
    setDataTable(rel.to_table);
    setDataColumns(cols);
    setDataOffset(0);
    setSelectedForDelete(new Set());
    setDataRows({
      columns: sqlResult.columns || [],
      rows: sqlResult.rows || [],
      total_count: (sqlResult.rows || []).length,
    });
    setJumpNotice(`Filtré via la relation ${dataTable}.${colName} -> ${rel.to_table}.${rel.to_column} = ${value}`);
  }

  const selectedConnection = connections.find((c) => String(c.id) === String(connectionId));
  const tableNames = analysis ? Object.keys(analysis.tables).sort() : [];

  return (
    <div className="hub-settings hub-settings-wide">
      <div className="hub-settings-topbar">
        <button className="secondary" onClick={onBack}>◀ Retour</button>
        <h1>🧬 Analyse de schémas</h1>
      </div>

      <div className="hub-card hub-settings-section">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <h2>🗂️ Catalogue SGBD (tunnels SSH ↔ connexions DBA)</h2>
          <button
            className="secondary"
            onClick={() => {
              setShowCatalog(!showCatalog);
              if (!showCatalog && !catalogLoaded) loadCatalog();
            }}
          >
            {showCatalog ? "Masquer" : "Afficher"}
          </button>
        </div>
        {showCatalog && (
          <>
            <p className="muted">
              Correspondance faite par hôte+port (127.0.0.1/localhost + port local du tunnel) --
              aucune référence stockée explicitement entre `ssh-tunnels` et les connexions DBA.
            </p>
            {catalogBusy && !catalogLoaded ? (
              <p className="muted">Chargement…</p>
            ) : catalogTunnels.length === 0 ? (
              <p className="muted">Aucun tunnel SSH configuré (voir l'onglet Tunnels SSH pour en créer un).</p>
            ) : (
              <table>
                <thead>
                  <tr><th>Tunnel</th><th>Port local</th><th>Statut</th><th>Connexion(s) DBA utilisant ce port</th><th></th></tr>
                </thead>
                <tbody>
                  {catalogTunnels.map((t) => {
                    const sshConn = catalogSshConnections.find((c) => c.id === t.connection_id);
                    const matches = matchingDbaConnections(t.local_port);
                    return (
                      <React.Fragment key={t.id}>
                        <tr>
                          <td>{t.label} {sshConn ? `(${sshConn.label})` : ""}</td>
                          <td>{t.local_port}</td>
                          <td>{t.status === "running" ? "🟢 actif" : "⚪ arrêté"}</td>
                          <td>
                            {matches.length === 0
                              ? <span className="muted">aucune -- port non repris dans DBA</span>
                              : matches.map((m) => m.label).join(", ")}
                          </td>
                          <td>
                            <button className="secondary" disabled={catalogBusy} onClick={() => handleCatalogToggleTunnel(t)}>
                              {t.status === "running" ? "Arrêter" : "Démarrer"}
                            </button>{" "}
                            <button className="secondary" onClick={() => handleCatalogToggleHistory(t.connection_id)}>
                              Historique
                            </button>
                          </td>
                        </tr>
                        {catalogHistoryFor === t.connection_id && (
                          <tr>
                            <td colSpan={5} style={{ paddingLeft: 24 }}>
                              {!catalogHistory[t.connection_id] ? (
                                <span className="muted">Chargement…</span>
                              ) : catalogHistory[t.connection_id].length === 0 ? (
                                <span className="muted">Aucun usage enregistré pour cette connexion SSH.</span>
                              ) : (
                                <table style={{ fontSize: 13 }}>
                                  <thead><tr><th>Date</th><th>Action</th><th>Résultat</th></tr></thead>
                                  <tbody>
                                    {catalogHistory[t.connection_id].map((h) => (
                                      <tr key={h.id}>
                                        <td className="muted">{new Date(h.started_at).toLocaleString("fr-FR")}</td>
                                        <td>{h.action_type === "mount" ? "Montage" : "Tunnel"}</td>
                                        <td>{h.success ? "✅ succès" : `❌ échec`}</td>
                                      </tr>
                                    ))}
                                  </tbody>
                                </table>
                              )}
                            </td>
                          </tr>
                        )}
                      </React.Fragment>
                    );
                  })}
                </tbody>
              </table>
            )}
          </>
        )}
      </div>

      <div className="hub-card hub-settings-section">
        <h2>Connexion à analyser</h2>
        <p className="muted">
          Choisissez une connexion déjà configurée dans l'onglet DBA (MySQL directe ou dump
          importé) -- créer une nouvelle connexion se fait toujours là-bas.
        </p>
        <div className="hub-settings-row">
          <label>Connexion DBA</label>
          <select
            value={connectionId}
            onChange={(e) => {
              setConnectionId(e.target.value);
              setAnalysis(null);
              setRelations([]);
              setImportSummary(null);
              setError(null);
            }}
          >
            <option value="">— choisir une connexion —</option>
            {connections.map((c) => (
              <option key={c.id} value={c.id}>
                {c.label} ({c.engine})
              </option>
            ))}
          </select>
        </div>
        {connections.length === 0 && (
          <p className="muted">Aucune connexion DBA disponible -- créez-en une dans l'onglet DBA d'abord.</p>
        )}
        {selectedConnection && selectedConnection.engine !== "sqlite" && (
          <div className="hub-settings-row">
            <label>Base (optionnel)</label>
            <input
              type="text"
              value={database}
              onChange={(e) => setDatabase(e.target.value)}
              placeholder={selectedConnection.database_name || "laisser vide = base par défaut de la connexion"}
            />
          </div>
        )}
        <button onClick={handleAnalyze} disabled={!connectionId || analyzing}>
          {analyzing ? "🟠 Analyse en cours…" : "Analyser"}
        </button>
        {error && <p className="hub-error">{error}</p>}
      </div>

      {analysis && (
        <>
          <div className="tabs" style={{ marginBottom: 16, marginTop: 16 }}>
            <button className={subTab === "schema" ? "active" : ""} onClick={() => setSubTab("schema")}>
              Schéma ({tableNames.length} tables)
            </button>
            <button className={subTab === "relations" ? "active" : ""} onClick={() => setSubTab("relations")}>
              Relations ({relations.length})
            </button>
            <button className={subTab === "export" ? "active" : ""} onClick={() => setSubTab("export")}>
              Export
            </button>
            <button className={subTab === "data" ? "active" : ""} onClick={() => setSubTab("data")}>
              Données
            </button>
          </div>

          {subTab === "schema" && (
            <div className="hub-card hub-settings-section">
              <h2>Tables</h2>
              {tableNames.map((tname) => {
                const tinfo = analysis.tables[tname];
                const expanded = expandedTables.has(tname);
                return (
                  <div key={tname} style={{ marginBottom: 8 }}>
                    <button className="secondary" onClick={() => toggleTable(tname)}>
                      {expanded ? "▾" : "▸"} {tname} ({tinfo.columns.length} colonnes)
                    </button>
                    {expanded && (
                      <ul>
                        {tinfo.columns.map((c) => (
                          <li key={c.name}>
                            {c.name} — {c.type || "?"}
                            {c.primary_key ? " (clé primaire)" : ""}
                            {c.nullable === false ? " (obligatoire)" : ""}
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                );
              })}

              {analysis.list_like_columns.length > 0 && (
                <>
                  <h3>Colonnes-listes détectées</h3>
                  <p className="muted">
                    Colonnes texte dont le contenu ressemble à une liste d'identifiants (ex.
                    "1,2,5") -- à confirmer manuellement dans l'onglet Relations, jamais une
                    relation classique déclarée dans le schéma.
                  </p>
                  <ul>
                    {analysis.list_like_columns.map((c, i) => (
                      <li key={`${c.table}.${c.column}-${i}`}>
                        {c.table}.{c.column} ({Math.round(c.ratio * 100)}% de l'échantillon)
                        {c.guessed_referenced_table ? ` — cible devinée : ${c.guessed_referenced_table}` : " — aucune table cible devinée"}
                      </li>
                    ))}
                  </ul>
                </>
              )}
            </div>
          )}

          {subTab === "relations" && (
            <div className="hub-card hub-settings-section">
              <h2>Éditeur de relations</h2>
              <p className="muted">
                Les relations proposées automatiquement ne sont JAMAIS appliquées sans validation
                -- confirmez ou rejetez chacune ci-dessous.
              </p>
              <button onClick={handleImportProposals} disabled={busy}>
                {importingProposals ? "🟠 Import en cours…" : "Importer les propositions détectées"}
              </button>
              {importSummary && (
                <p className="muted">
                  {importSummary.imported} nouvelle(s) relation(s) importée(s)
                  {importSummary.skipped > 0 ? `, ${importSummary.skipped} déjà connue(s) (jamais écrasée(s))` : ""}.
                </p>
              )}

              <h3>Ajouter une relation manuellement</h3>
              {/* Sélection GRAPHIQUE dans les tables/colonnes déjà
                  analysées (livraison #267, demandé explicitement --
                  "je n'ai pas trouvé l'interface me permettant
                  graphiquement d'attribuer à un champ d'une table un
                  lien relationnel vers l'index d'une autre table") --
                  AVANT ce correctif, ce formulaire existait déjà mais
                  n'utilisait que des champs texte libres (table/colonne
                  à taper exactement, source du vrai problème signalé
                  -- rien de "graphique" à proprement parler). `analysis.tables`
                  est DÉJÀ chargé côté état dès qu'une analyse a tourné
                  (voir handleAnalyze) -- aucun nouvel appel réseau
                  nécessaire ici. Repli sur les champs texte SEULEMENT
                  si aucune analyse n'est encore disponible (jamais un
                  formulaire bloqué en attendant). */}
              {analysis?.tables ? (
                <form onSubmit={handleManualSubmit} style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "flex-end", marginBottom: 16 }}>
                  <div className="hub-settings-row">
                    <label>Table source</label>
                    <select
                      value={manualForm.from_table}
                      onChange={(e) => setManualForm({ ...manualForm, from_table: e.target.value, from_column: "" })}
                    >
                      <option value="">— choisir —</option>
                      {Object.keys(analysis.tables).sort().map((t) => <option key={t} value={t}>{t}</option>)}
                    </select>
                  </div>
                  <div className="hub-settings-row">
                    <label>Colonne source</label>
                    <select
                      value={manualForm.from_column}
                      onChange={(e) => setManualForm({ ...manualForm, from_column: e.target.value })}
                      disabled={!manualForm.from_table}
                    >
                      <option value="">— choisir —</option>
                      {(analysis.tables[manualForm.from_table]?.columns || []).map((c) => (
                        <option key={c.name} value={c.name}>{c.name}{c.primary_key ? " (clé primaire)" : ""}</option>
                      ))}
                    </select>
                  </div>
                  <div className="hub-settings-row">
                    <label>Table cible</label>
                    <select
                      value={manualForm.to_table}
                      onChange={(e) => setManualForm({ ...manualForm, to_table: e.target.value, to_column: "" })}
                    >
                      <option value="">— choisir —</option>
                      {Object.keys(analysis.tables).sort().map((t) => <option key={t} value={t}>{t}</option>)}
                    </select>
                  </div>
                  <div className="hub-settings-row">
                    <label>Colonne cible (l'index visé)</label>
                    <select
                      value={manualForm.to_column}
                      onChange={(e) => setManualForm({ ...manualForm, to_column: e.target.value })}
                      disabled={!manualForm.to_table}
                    >
                      <option value="">— choisir —</option>
                      {(analysis.tables[manualForm.to_table]?.columns || []).map((c) => (
                        <option key={c.name} value={c.name}>{c.name}{c.primary_key ? " (clé primaire)" : ""}</option>
                      ))}
                    </select>
                  </div>
                  <button type="submit" disabled={busy}>Ajouter</button>
                </form>
              ) : (
                <>
                  <p className="muted" style={{ marginTop: -4 }}>
                    Lancez d'abord une analyse (onglet "Schéma") pour choisir les tables/colonnes dans des
                    menus déroulants -- en attendant, saisie libre ci-dessous.
                  </p>
                  <form onSubmit={handleManualSubmit} style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "flex-end", marginBottom: 16 }}>
                    <div className="hub-settings-row">
                      <label>Table source</label>
                      <input value={manualForm.from_table} onChange={(e) => setManualForm({ ...manualForm, from_table: e.target.value })} />
                    </div>
                    <div className="hub-settings-row">
                      <label>Colonne source</label>
                      <input value={manualForm.from_column} onChange={(e) => setManualForm({ ...manualForm, from_column: e.target.value })} />
                    </div>
                    <div className="hub-settings-row">
                      <label>Table cible</label>
                      <input value={manualForm.to_table} onChange={(e) => setManualForm({ ...manualForm, to_table: e.target.value })} />
                    </div>
                    <div className="hub-settings-row">
                      <label>Colonne cible</label>
                      <input value={manualForm.to_column} onChange={(e) => setManualForm({ ...manualForm, to_column: e.target.value })} />
                    </div>
                    <button type="submit" disabled={busy}>Ajouter</button>
                  </form>
                </>
              )}

              {relations.length === 0 ? (
                <p className="muted">Aucune relation pour l'instant -- importez les propositions ou ajoutez-en une manuellement.</p>
              ) : (
                <table className="logs-dashboard-table">
                  <thead>
                    <tr>
                      <th>De</th>
                      <th>Vers</th>
                      <th>Type</th>
                      <th>Statut</th>
                      <th>Origine</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {relations.map((r) => {
                      const vResult = validationResults[r.id];
                      return (
                      <React.Fragment key={r.id}>
                      <tr>
                        <td>{r.from_table}.{r.from_column}</td>
                        <td>{r.to_table}.{r.to_column}</td>
                        <td>{r.relation_type === "list" ? "liste" : "clé étrangère"}</td>
                        <td>
                          {STATUS_LABELS[r.status] || r.status}
                          {r.confidence ? ` (confiance ${r.confidence})` : ""}
                        </td>
                        <td>{r.source === "manual" ? "manuelle" : "automatique"}</td>
                        <td>
                          {r.status !== "confirmed" && (
                            <button className="secondary" disabled={busy} onClick={() => handleStatusChange(r.id, "confirmed")} title="Confirmer">
                              ✔
                            </button>
                          )}
                          {r.status !== "rejected" && (
                            <button className="secondary" disabled={busy} onClick={() => handleStatusChange(r.id, "rejected")} title="Rejeter">
                              ✘
                            </button>
                          )}
                          <button className="secondary" disabled={busy} onClick={() => handleDelete(r.id)} title="Supprimer définitivement">
                            🗑
                          </button>
                          <button
                            className="secondary"
                            disabled={vResult === "loading"}
                            onClick={() => handleValidateRelation(r)}
                            title="Vérifier contre les vraies données"
                          >
                            🔍 Valider les données
                          </button>
                        </td>
                      </tr>
                      {vResult && (
                        <tr>
                          <td colSpan={6}>
                            {vResult === "loading" ? (
                              <span className="muted">Vérification en cours…</span>
                            ) : vResult.error ? (
                              <span style={{ color: "var(--hub-danger, #c0392b)" }}>⚠️ {vResult.error}</span>
                            ) : vResult.coverage_ratio === null ? (
                              <span className="muted">Aucune valeur non vide à vérifier dans l'échantillon.</span>
                            ) : (
                              <span>
                                <strong>{Math.round(vResult.coverage_ratio * 100)}%</strong> des {vResult.checked_count} valeur(s)
                                distincte(s) échantillonnée(s) correspondent à une ligne existante de{" "}
                                {r.to_table}.{r.to_column} ({vResult.matched_count}/{vResult.checked_count}).
                                {vResult.target_capped && " (table cible volumineuse -- vérifiée sur un sous-ensemble)"}
                                {vResult.sample_mismatches.length > 0 && (
                                  <> — valeurs sans correspondance : {vResult.sample_mismatches.join(", ")}</>
                                )}
                              </span>
                            )}
                          </td>
                        </tr>
                      )}
                      </React.Fragment>
                      );
                    })}
                  </tbody>
                </table>
              )}
            </div>
          )}

          {subTab === "export" && (
            <div className="hub-card hub-settings-section">
              <h2>Export du graphe relationnel</h2>
              <p className="muted">
                Exporte les tables et UNIQUEMENT les relations confirmées ci-dessus -- jamais les
                propositions en attente ni les rejetées.
              </p>
              <div style={{ display: "flex", gap: 8 }}>
                <a href={graphExportUrl(schemaApiBase, connectionId, database, "json")} target="_blank" rel="noreferrer">
                  <button>Télécharger en JSON</button>
                </a>
                <a href={graphExportUrl(schemaApiBase, connectionId, database, "xml")} target="_blank" rel="noreferrer">
                  <button>Télécharger en XML</button>
                </a>
              </div>
            </div>
          )}

          {subTab === "data" && (
            <div className="hub-card hub-settings-section">
              <h2>Données</h2>
              <p className="muted">
                ⚠️ Approximation (voir hub/README.md) : navigateur/éditeur de lignes appuyé
                directement sur dba-api, enrichi par les relations CONFIRMÉES pour un "aller à la
                ligne liée" (clic sur une valeur de colonne liée).
              </p>
              <div className="hub-settings-row">
                <label>Table</label>
                <select value={dataTable} onChange={(e) => handleSelectDataTable(e.target.value)}>
                  <option value="">— choisir —</option>
                  {tableNames.map((t) => (
                    <option key={t} value={t}>{t}</option>
                  ))}
                </select>
              </div>
              {dataError && <p className="hub-error">{dataError}</p>}
              {jumpNotice && <p className="muted">ℹ️ {jumpNotice}</p>}
              {dataBusy && <p className="muted">Chargement…</p>}

              {dataRows && (
                <>
                  <p className="muted">
                    {dataRows.total_count} ligne{dataRows.total_count > 1 ? "s" : ""} au total —
                    affichage {dataOffset + 1}-{dataOffset + dataRows.rows.length}
                  </p>
                  <div style={{ overflowX: "auto" }}>
                    <table className="hub-table">
                      <thead>
                        <tr>
                          <th></th>
                          {dataRows.columns.map((c) => (
                            <th key={c}>
                              {c}
                              {dataColumns.find((dc) => dc.name === c)?.primary_key ? " 🔑" : ""}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {dataRows.rows.map((row, rowIndex) => {
                          const pkCol = pkColumnName();
                          const pkIndex = pkCol ? dataRows.columns.indexOf(pkCol) : -1;
                          const pkValue = pkIndex >= 0 ? row[pkIndex] : null;
                          const hasRelation = (colName) =>
                            relations.some((r) => r.status === "confirmed" && r.from_table === dataTable && r.from_column === colName);
                          return (
                            <tr key={pkValue ?? rowIndex}>
                              <td>
                                {pkCol && (
                                  <input
                                    type="checkbox"
                                    checked={selectedForDelete.has(pkValue)}
                                    onChange={() => toggleSelectForDelete(pkValue)}
                                  />
                                )}
                              </td>
                              {row.map((cellValue, colIndex) => {
                                const colName = dataRows.columns[colIndex];
                                const isEditing = editingCell && editingCell.rowIndex === rowIndex && editingCell.colName === colName;
                                if (isEditing) {
                                  return (
                                    <td key={colName}>
                                      <input
                                        autoFocus
                                        value={editingValue}
                                        onChange={(e) => setEditingValue(e.target.value)}
                                        onBlur={commitEditCell}
                                        onKeyDown={(e) => {
                                          if (e.key === "Enter") commitEditCell();
                                          if (e.key === "Escape") setEditingCell(null);
                                        }}
                                      />
                                    </td>
                                  );
                                }
                                return (
                                  <td key={colName} onClick={() => startEditCell(rowIndex, colName, cellValue)} style={{ cursor: "pointer" }}>
                                    {hasRelation(colName) ? (
                                      <button
                                        className="secondary"
                                        onClick={(e) => {
                                          e.stopPropagation();
                                          handleJumpToRelated(colName, cellValue);
                                        }}
                                        title="Aller à la ligne liée"
                                      >
                                        {String(cellValue)} ↗
                                      </button>
                                    ) : looksLikeHtml(cellValue) ? (
                                      <span>
                                        <button
                                          className="secondary"
                                          onClick={(e) => {
                                            e.stopPropagation();
                                            setHtmlPreview({ colName, value: cellValue });
                                          }}
                                          title="Ce champ contient du HTML -- aperçu rendu"
                                        >
                                          📄 Aperçu
                                        </button>
                                        <span className="muted" style={{ marginLeft: 6, fontSize: 12 }}>
                                          {String(cellValue).replace(/<[^>]*>/g, " ").trim().slice(0, 40)}…
                                        </span>
                                      </span>
                                    ) : (
                                      String(cellValue ?? "")
                                    )}
                                  </td>
                                );
                              })}
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>

                  <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
                    <button
                      className="secondary"
                      disabled={dataOffset === 0}
                      onClick={() => { setDataOffset(Math.max(0, dataOffset - DATA_PAGE_SIZE)); loadDataRows(dataTable, Math.max(0, dataOffset - DATA_PAGE_SIZE)); }}
                    >
                      ◀ Précédent
                    </button>
                    <button
                      className="secondary"
                      disabled={dataOffset + DATA_PAGE_SIZE >= dataRows.total_count}
                      onClick={() => { const next = dataOffset + DATA_PAGE_SIZE; setDataOffset(next); loadDataRows(dataTable, next); }}
                    >
                      Suivant ▶
                    </button>
                    <button
                      className="secondary"
                      disabled={selectedForDelete.size === 0}
                      onClick={handleDeleteSelectedRows}
                    >
                      🗑 Supprimer la sélection ({selectedForDelete.size})
                    </button>
                    <button onClick={() => setShowInsertForm((v) => !v)}>
                      + Nouvelle ligne
                    </button>
                  </div>

                  {showInsertForm && (
                    <form onSubmit={handleInsertRow} style={{ marginTop: 12, display: "flex", gap: 8, flexWrap: "wrap", alignItems: "flex-end" }}>
                      {dataColumns.filter((c) => !c.primary_key).map((c) => (
                        <div className="hub-settings-row" key={c.name}>
                          <label>{c.name}</label>
                          <input
                            value={insertValues[c.name] || ""}
                            onChange={(e) => setInsertValues({ ...insertValues, [c.name]: e.target.value })}
                          />
                        </div>
                      ))}
                      <button type="submit" disabled={dataBusy}>Ajouter</button>
                    </form>
                  )}
                </>
              )}
            </div>
          )}
        </>
      )}

      {htmlPreview && (
        <div
          style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.45)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1000 }}
          onClick={() => setHtmlPreview(null)}
        >
          <div
            className="hub-card"
            style={{ maxWidth: 700, maxHeight: "80vh", overflow: "auto", padding: 20, background: "var(--hub-bg, #fff)" }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
              <h3 style={{ margin: 0 }}>Aperçu — {htmlPreview.colName}</h3>
              <button className="secondary" onClick={() => setHtmlPreview(null)}>Fermer ✕</button>
            </div>
            <p className="muted" style={{ fontSize: 12 }}>
              Rendu HTML assaini (livraison #214) -- balises actives (scripts, gestionnaires d'évènements) retirées.
            </p>
            <div dangerouslySetInnerHTML={{ __html: sanitizeHtml(htmlPreview.value) }} />
          </div>
        </div>
      )}
    </div>
  );
}
