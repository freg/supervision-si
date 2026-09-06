import { useEffect, useRef, useState } from "react";
import {
  fetchUsers, fetchTypes, fetchLevels, fetchStatuts, fetchQueue,
  createUser, updateUser, deleteUserRow,
  createType, updateType, deleteTypeRow,
  createLevel, updateLevel, deleteLevelRow,
  createStatut, updateStatut, deleteStatutRow,
  updateTicket, exportDatabase, importDatabase, fetchTicket,
  updateRawTableRow,
} from "./ticketsApi.js";

// Miroir de la liste blanche côté serveur — table -> {pk, columns
// éditables}. ticket_status_log (journal) et oauth_credentials (jetons
// techniques) volontairement absents : pas de correction manuelle
// pertinente, restent en lecture seule dans cette vue.
const RAW_EDITABLE_CONFIG = {
  users: { pk: "id", columns: ["login", "name", "email", "group_name"] },
  types: { pk: "id", columns: ["label"] },
  levels: { pk: "id", columns: ["label", "rank"] },
  statuts: { pk: "id", columns: ["label", "description"] },
  tickets: { pk: "id", columns: ["subject", "description", "user_id", "type_id", "level_id", "statut_id", "ts_closed"] },
  calendar_events: { pk: "id", columns: ["summary", "description", "start_ts", "end_ts"] },
  calendar_filter_rules: { pk: "id", columns: ["label", "pattern", "target_field", "action", "priority"] },
  exclusion_rules: { pk: "id", columns: ["label", "pattern"] },
  priority_keywords: { pk: "id", columns: ["label", "pattern"] },
  ticket_time_entries: { pk: "id", columns: ["start_ts", "end_ts", "weight"] },
  matching_config: { pk: "key", columns: ["value"] },
};

function downloadJson(filename, data) {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

function JsonBlock({ data }) {
  if (data === null || data === undefined) {
    return <p className="pixel-grid-empty-hint">Clique un champ à gauche pour voir son contexte ici.</p>;
  }
  return (
    <pre style={{
      fontSize: "0.68rem", fontFamily: "var(--font-mono)", whiteSpace: "pre-wrap",
      wordBreak: "break-word", margin: 0, color: "var(--color-text)",
    }}>
      {JSON.stringify(data, null, 2)}
    </pre>
  );
}

/**
 * Construit une hiérarchie imbriquée {dim1: {dim2: [tickets...]}} à
 * partir de la liste des tickets déjà chargée — purement côté client,
 * pas de nouvel appel API nécessaire.
 */
function buildHierarchy(tickets, dims) {
  const root = {};
  for (const t of tickets) {
    let node = root;
    for (let i = 0; i < dims.length; i++) {
      const key = t[dims[i]] || "(non défini)";
      if (i === dims.length - 1) {
        if (!node[key]) node[key] = [];
        node[key].push(`#${t.id} ${t.subject}`);
      } else {
        if (!node[key]) node[key] = {};
        node = node[key];
      }
    }
  }
  return root;
}

const HIERARCHY_OPTIONS = [
  { key: "user", label: "Demandeur → Tickets", dims: ["user_login"] },
  { key: "level_user", label: "Niveau → Demandeur → Tickets", dims: ["level_label", "user_login"] },
  { key: "type_user", label: "Type → Demandeur → Tickets", dims: ["type_label", "user_login"] },
  { key: "statut_user", label: "Statut → Demandeur → Tickets", dims: ["statut_label", "user_login"] },
];

function formatCell(value) {
  if (value === null || value === undefined) return "—";
  if (typeof value === "boolean") return value ? "true" : "false";
  const text = String(value);
  return text.length > 80 ? text.slice(0, 80) + "…" : text;
}

/** Une table brute repliable — colonnes déduites de la première ligne.
 * Cellules éditables (liste blanche RAW_EDITABLE_CONFIG) modifiables
 * directement, sauvegarde automatique en quittant le champ (blur) ou
 * sur Entrée — pas de bouton "enregistrer" séparé, pensé pour de
 * petites corrections ponctuelles rapides. */
function RawTableSection({ name, rows, onRowSaved }) {
  const [expanded, setExpanded] = useState(false);
  const [localEdits, setLocalEdits] = useState({}); // { pkValue: { col: value } }
  const columns = rows.length > 0 ? Object.keys(rows[0]) : [];
  const editConfig = RAW_EDITABLE_CONFIG[name];

  function cellValue(row, col) {
    const key = editConfig ? row[editConfig.pk] : row.id;
    const edited = localEdits[key]?.[col];
    return edited !== undefined ? edited : row[col] ?? "";
  }

  function setCellValue(row, col, value) {
    const key = editConfig ? row[editConfig.pk] : row.id;
    setLocalEdits((prev) => ({ ...prev, [key]: { ...prev[key], [col]: value } }));
  }

  async function handleCellCommit(row, col) {
    if (!editConfig) return;
    const key = row[editConfig.pk];
    const newValue = localEdits[key]?.[col];
    const originalValue = row[col] ?? "";
    if (newValue === undefined || String(newValue) === String(originalValue)) return; // rien de changé
    await updateRawTableRow(name, key, { [col]: newValue });
    onRowSaved?.();
  }

  return (
    <div className="pixel-grid-main">
      <div
        className="timeline-title"
        style={{ fontSize: "0.8rem", cursor: "pointer", display: "flex", alignItems: "center", gap: "0.4rem" }}
        onClick={() => setExpanded((v) => !v)}
      >
        {expanded ? "▾" : "▸"} {name}
        <span className="pixel-grid-empty-hint">
          ({rows.length} ligne{rows.length > 1 ? "s" : ""}{editConfig ? " · éditable" : " · lecture seule"})
        </span>
      </div>
      {expanded && rows.length > 0 && (
        <div style={{ overflowX: "auto", maxHeight: 380, overflowY: "auto", marginTop: "0.3rem" }}>
          <table className="geo-table">
            <thead>
              <tr>{columns.map((c) => <th key={c}>{c}</th>)}</tr>
            </thead>
            <tbody>
              {rows.map((row, i) => (
                <tr key={i}>
                  {columns.map((c) => {
                    const editable = editConfig?.columns.includes(c);
                    return (
                      <td key={c} style={{ fontSize: "0.66rem", fontFamily: "var(--font-mono)" }}>
                        {editable ? (
                          <input
                            className="geo-input"
                            style={{ fontSize: "0.66rem", width: "100%", minWidth: 70 }}
                            value={cellValue(row, c)}
                            onChange={(e) => setCellValue(row, c, e.target.value)}
                            onBlur={() => handleCellCommit(row, c)}
                            onKeyDown={(e) => { if (e.key === "Enter") e.target.blur(); }}
                          />
                        ) : (
                          <span style={{ whiteSpace: "nowrap" }}>{formatCell(row[c])}</span>
                        )}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

/** Table générique éditable en ligne — mêmes colonnes pour users/types/levels/statuts. */
function EditableTable({ title, columns, rows, onUpdateRaw, onSaved, onDelete, onCreate, onRowClick }) {
  const [edits, setEdits] = useState({});
  const [newRow, setNewRow] = useState({});
  const [saving, setSaving] = useState(null);

  function fieldValue(row, col) {
    return edits[row.id]?.[col] !== undefined ? edits[row.id][col] : row[col] ?? "";
  }

  function setField(rowId, col, value) {
    setEdits((prev) => ({ ...prev, [rowId]: { ...prev[rowId], [col]: value } }));
  }

  async function handleSave(row) {
    const changes = edits[row.id];
    if (!changes) return;
    setSaving(row.id);
    await onUpdateRaw(row.id, changes);
    setSaving(null);
    setEdits((prev) => {
      const next = { ...prev };
      delete next[row.id];
      return next;
    });
    onSaved();
  }

  async function handleSaveAll() {
    const pendingIds = Object.keys(edits);
    if (pendingIds.length === 0) return;
    const ok = window.confirm(`Enregistrer les ${pendingIds.length} ligne(s) modifiée(s) de "${title}" ?`);
    if (!ok) return;
    setSaving("__all__");
    // Séquentiel plutôt qu'en parallèle — évite tout risque de collision
    // si plusieurs lignes touchent la même ressource sous-jacente.
    // Un seul rafraîchissement à la fin (onSaved), pas un par ligne —
    // sinon la page saute à chaque ligne enregistrée.
    for (const id of pendingIds) {
      await onUpdateRaw(Number(id) || id, edits[id]);
    }
    setSaving(null);
    setEdits({});
    onSaved();
  }

  async function handleCreate() {
    if (Object.keys(newRow).length === 0) return;
    await onCreate(newRow);
    setNewRow({});
  }

  function handleNewRowKeyDown(e) {
    if (e.key === "Enter") {
      e.preventDefault();
      handleCreate();
      // Garde le focus sur le même champ après création — pratique
      // pour enchaîner la saisie de plusieurs libellés à la suite.
      requestAnimationFrame(() => e.target.focus());
    }
  }

  function handleEditKeyDown(e, row) {
    if (e.key === "Enter") {
      e.preventDefault();
      handleSave(row);
    }
  }

  const pendingCount = Object.keys(edits).length;

  return (
    <div className="pixel-grid-main">
      <div className="timeline-title" style={{ fontSize: "0.85rem", display: "flex", alignItems: "center", gap: "0.5rem" }}>
        {title}
        {pendingCount > 0 && (
          <button className="pixel-grid-level-btn" style={{ fontSize: "0.65rem" }} onClick={handleSaveAll} disabled={saving === "__all__"}>
            {saving === "__all__" ? "…" : `💾 Tout enregistrer (${pendingCount})`}
          </button>
        )}
      </div>
      <table className="geo-table">
        <thead>
          <tr>
            <th>id</th>
            {columns.map((c) => <th key={c.key}>{c.label}</th>)}
            <th></th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.id} onClick={() => onRowClick(title, row)} style={{ cursor: "pointer" }}>
              <td>{row.id}</td>
              {columns.map((c) => (
                <td key={c.key}>
                  <input
                    className="geo-input"
                    style={{ width: c.width || 120 }}
                    value={fieldValue(row, c.key)}
                    onChange={(e) => setField(row.id, c.key, e.target.value)}
                    onClick={(e) => e.stopPropagation()}
                    onKeyDown={(e) => handleEditKeyDown(e, row)}
                  />
                </td>
              ))}
              <td className="geo-cell-actions">
                <button className="calendar-nav-btn" onClick={(e) => { e.stopPropagation(); handleSave(row); }} disabled={saving === row.id || !edits[row.id]}>
                  {saving === row.id ? "…" : "💾"}
                </button>
                <button className="basket-remove-btn" onClick={(e) => { e.stopPropagation(); onDelete(row.id); }} title="Supprimer">✕</button>
              </td>
            </tr>
          ))}
          <tr>
            <td className="pixel-grid-empty-hint">nouveau</td>
            {columns.map((c) => (
              <td key={c.key}>
                <input
                  className="geo-input"
                  style={{ width: c.width || 120 }}
                  placeholder={c.label}
                  value={newRow[c.key] || ""}
                  onChange={(e) => setNewRow((prev) => ({ ...prev, [c.key]: e.target.value }))}
                  onKeyDown={handleNewRowKeyDown}
                />
              </td>
            ))}
            <td>
              <button className="pixel-grid-reset-btn" onClick={handleCreate}>➕</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  );
}

function TicketsEditTable({ tickets, users, types, levels, statuts, onUpdated, onRowClick }) {
  const [edits, setEdits] = useState({});
  const [saving, setSaving] = useState(null);

  function fieldValue(t, col) {
    return edits[t.id]?.[col] !== undefined ? edits[t.id][col] : t[col] ?? "";
  }
  function setField(id, col, value) {
    setEdits((prev) => ({ ...prev, [id]: { ...prev[id], [col]: value } }));
  }
  async function handleSave(t) {
    const changes = edits[t.id];
    if (!changes) return;
    setSaving(t.id);
    await updateTicket(t.id, changes);
    setSaving(null);
    setEdits((prev) => { const n = { ...prev }; delete n[t.id]; return n; });
    onUpdated();
  }

  async function handleSaveAll() {
    const pendingIds = Object.keys(edits);
    if (pendingIds.length === 0) return;
    const ok = window.confirm(`Enregistrer les ${pendingIds.length} ticket(s) modifié(s) ?`);
    if (!ok) return;
    setSaving("__all__");
    for (const id of pendingIds) {
      await updateTicket(Number(id) || id, edits[id]);
    }
    setSaving(null);
    setEdits({});
    onUpdated();
  }

  const pendingCount = Object.keys(edits).length;

  return (
    <div className="pixel-grid-main">
      <div className="timeline-title" style={{ fontSize: "0.85rem", display: "flex", alignItems: "center", gap: "0.5rem" }}>
        Tickets
        {pendingCount > 0 && (
          <button className="pixel-grid-level-btn" style={{ fontSize: "0.65rem" }} onClick={handleSaveAll} disabled={saving === "__all__"}>
            {saving === "__all__" ? "…" : `💾 Tout enregistrer (${pendingCount})`}
          </button>
        )}
      </div>
      <table className="geo-table">
        <thead>
          <tr>
            <th>id</th><th>sujet</th><th>demandeur</th><th>type</th><th>niveau</th><th>statut</th><th>fermé</th><th></th>
          </tr>
        </thead>
        <tbody>
          {tickets.map((t) => (
            <tr key={t.id} onClick={() => onRowClick(t)} style={{ cursor: "pointer" }}>
              <td>{t.id}</td>
              <td>
                <input className="geo-input" style={{ width: 200 }} value={fieldValue(t, "subject")}
                  onChange={(e) => setField(t.id, "subject", e.target.value)} onClick={(e) => e.stopPropagation()}
                  onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); handleSave(t); } }} />
              </td>
              <td>
                <select className="geo-input" value={fieldValue(t, "user_id")} onChange={(e) => setField(t.id, "user_id", e.target.value)} onClick={(e) => e.stopPropagation()}>
                  <option value="">—</option>
                  {users.map((u) => <option key={u.id} value={u.id}>{u.login}</option>)}
                </select>
              </td>
              <td>
                <select className="geo-input" value={fieldValue(t, "type_id")} onChange={(e) => setField(t.id, "type_id", e.target.value)} onClick={(e) => e.stopPropagation()}>
                  <option value="">—</option>
                  {types.map((x) => <option key={x.id} value={x.id}>{x.label}</option>)}
                </select>
              </td>
              <td>
                <select className="geo-input" value={fieldValue(t, "level_id")} onChange={(e) => setField(t.id, "level_id", e.target.value)} onClick={(e) => e.stopPropagation()}>
                  <option value="">—</option>
                  {levels.map((l) => <option key={l.id} value={l.id}>{l.label}</option>)}
                </select>
              </td>
              <td>
                <select className="geo-input" value={fieldValue(t, "statut_id")} onChange={(e) => setField(t.id, "statut_id", e.target.value)} onClick={(e) => e.stopPropagation()}>
                  <option value="">—</option>
                  {statuts.map((s) => <option key={s.id} value={s.id}>{s.label}</option>)}
                </select>
              </td>
              <td>
                <input type="checkbox" checked={Boolean(fieldValue(t, "ts_closed"))}
                  onChange={(e) => setField(t.id, "ts_closed", e.target.checked ? Math.floor(Date.now() / 1000) : null)}
                  onClick={(e) => e.stopPropagation()} />
              </td>
              <td>
                <button className="calendar-nav-btn" onClick={(e) => { e.stopPropagation(); handleSave(t); }} disabled={saving === t.id || !edits[t.id]}>
                  {saving === t.id ? "…" : "💾"}
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ExportImportPanel({ onImported }) {
  const [mode, setMode] = useState("merge");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);

  async function handleExport() {
    setBusy(true);
    const dump = await exportDatabase();
    setBusy(false);
    if (dump) downloadJson(`tickets-export-${Date.now()}.json`, dump);
  }

  async function handleImport(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    setBusy(true);
    try {
      const text = await file.text();
      const data = JSON.parse(text);
      const res = await importDatabase(data, mode);
      setResult(res.ok ? res.data : { error: res.data.error });
      if (res.ok) onImported();
    } catch (err) {
      setResult({ error: "Fichier JSON invalide." });
    }
    setBusy(false);
    e.target.value = "";
  }

  return (
    <div className="pixel-grid-toolbar">
      <div className="pixel-grid-controls">
        <span className="pixel-grid-controls-label">Base complète :</span>
        <button className="sources-header-btn" onClick={handleExport} disabled={busy}>⬇️ Exporter (JSON)</button>
        <select className="geo-input" value={mode} onChange={(e) => setMode(e.target.value)}>
          <option value="merge">import : fusion (ajoute/met à jour)</option>
          <option value="replace">import : remplace tout (destructeur)</option>
        </select>
        <label className="inject-file-label" style={{ marginBottom: 0 }}>
          ⬆️ Importer un fichier
          <input type="file" accept=".json" onChange={handleImport} hidden disabled={busy} />
        </label>
      </div>
      {result && !result.error && (
        <p className="pixel-grid-hover-detail">
          Import {result.mode} réussi — {JSON.stringify(result.rows_imported)}
        </p>
      )}
      {result?.error && <p className="pixel-grid-error">{result.error}</p>}
      {mode === "replace" && (
        <p className="pixel-grid-error">
          ⚠️ Le mode "remplace" vide TOUTE la base avant de réimporter — y compris les tables absentes du fichier importé.
        </p>
      )}
    </div>
  );
}

export default function DatabaseAdminView({ onClose }) {
  const [users, setUsers] = useState([]);
  const [types, setTypes] = useState([]);
  const [levels, setLevels] = useState([]);
  const [statuts, setStatuts] = useState([]);
  const [tickets, setTickets] = useState([]);
  const [loading, setLoading] = useState(true);
  const [hasLoadedOnce, setHasLoadedOnce] = useState(false);
  const leftColumnRef = useRef(null);

  const [hierarchyKey, setHierarchyKey] = useState("user");
  const [inspected, setInspected] = useState(null); // { label, data }
  const [inspectLoading, setInspectLoading] = useState(false);

  const [showAllTables, setShowAllTables] = useState(false);
  const [allTablesData, setAllTablesData] = useState(null);
  const [allTablesLoading, setAllTablesLoading] = useState(false);

  async function handleToggleAllTables() {
    setShowAllTables((v) => !v);
    if (!allTablesData) {
      setAllTablesLoading(true);
      const dump = await exportDatabase();
      setAllTablesData(dump);
      setAllTablesLoading(false);
    }
  }

  async function reload() {
    // Ne montre le "Chargement…" plein écran qu'au tout premier
    // chargement — sinon la div défilante de gauche est démontée puis
    // recréée à chaque sauvegarde, ce qui remonte la page en haut.
    // Préserve aussi explicitement le défilement en filet de sécurité.
    const scrollTop = leftColumnRef.current?.scrollTop ?? 0;
    if (!hasLoadedOnce) setLoading(true);
    const [u, ty, l, s, t] = await Promise.all([
      fetchUsers(), fetchTypes(), fetchLevels(), fetchStatuts(), fetchQueue({ all: true }),
    ]);
    setUsers(u);
    setTypes(ty);
    setLevels(l);
    setStatuts(s);
    setTickets(t);
    setLoading(false);
    setHasLoadedOnce(true);
    requestAnimationFrame(() => {
      if (leftColumnRef.current) leftColumnRef.current.scrollTop = scrollTop;
    });
  }

  useEffect(() => {
    reload();
  }, []);

  function handleReferenceRowClick(tableTitle, row) {
    const dimByTitle = {
      "Utilisateurs": { field: "user_id", label: "login" },
      "Types": { field: "type_id", label: "label" },
      "Niveaux": { field: "level_id", label: "label" },
      "Statuts": { field: "statut_id", label: "label" },
    };
    const dim = dimByTitle[tableTitle];
    if (!dim) return;
    const relatedTickets = tickets.filter((t) => String(t[dim.field]) === String(row.id));
    setInspected({
      label: `${tableTitle} — ${row[dim.label] ?? row.id}`,
      data: { record: row, tickets_associes: relatedTickets.map((t) => ({ id: t.id, subject: t.subject, statut: t.statut_label })) },
    });
  }

  async function handleTicketRowClick(t) {
    setInspected({ label: `Ticket #${t.id}`, data: null });
    setInspectLoading(true);
    const full = await fetchTicket(t.id);
    setInspectLoading(false);
    setInspected({ label: `Ticket #${t.id} — ${t.subject}`, data: full });
  }

  const hierarchyOption = HIERARCHY_OPTIONS.find((h) => h.key === hierarchyKey);
  const hierarchyJson = buildHierarchy(tickets, hierarchyOption.dims);

  return (
    <div className="pixel-grid-app">
      <div className="pixel-grid-toolbar">
        <div className="timeline-header">
          <div className="timeline-title">🗄️ Gestion de la base</div>
          <button className="calendar-nav-btn" onClick={onClose}>← Retour</button>
        </div>
      </div>

      <ExportImportPanel onImported={reload} />

      <div className="pixel-grid-toolbar">
        <button className="sources-header-btn" onClick={handleToggleAllTables}>
          📚 Toutes les tables {showAllTables ? "▾" : "▸"}
        </button>
        {showAllTables && (
          <div style={{ marginTop: "0.5rem" }}>
            {allTablesLoading && <p className="synthesis-empty">Chargement…</p>}
            {!allTablesLoading && allTablesData && (
              <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
                {Object.entries(allTablesData).map(([tableName, rows]) => (
                  <RawTableSection key={tableName} name={tableName} rows={rows} onRowSaved={reload} />
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {loading && !hasLoadedOnce && <p className="synthesis-empty">Chargement…</p>}

      {hasLoadedOnce && (
        <div className="pixel-grid-body" style={{ gap: "1rem" }}>
          <div ref={leftColumnRef} className="pixel-grid-main" style={{ flex: 2, minWidth: 0, display: "flex", flexDirection: "column", gap: "1.5rem", maxHeight: "78vh", overflowY: "auto" }}>
            <EditableTable
              title="Utilisateurs"
              columns={[
                { key: "login", label: "login" }, { key: "name", label: "nom" },
                { key: "email", label: "email", width: 180 }, { key: "group_name", label: "groupe" },
              ]}
              rows={users}
              onUpdateRaw={updateUser}
              onSaved={reload}
              onDelete={async (id) => { await deleteUserRow(id); reload(); }}
              onCreate={async (f) => { await createUser(f); reload(); }}
              onRowClick={handleReferenceRowClick}
            />

            <EditableTable
              title="Types"
              columns={[{ key: "label", label: "libellé" }]}
              rows={types}
              onUpdateRaw={updateType}
              onSaved={reload}
              onDelete={async (id) => { await deleteTypeRow(id); reload(); }}
              onCreate={async (f) => { await createType(f); reload(); }}
              onRowClick={handleReferenceRowClick}
            />

            <EditableTable
              title="Niveaux"
              columns={[{ key: "label", label: "libellé" }, { key: "rank", label: "rang (tri)", width: 80 }]}
              rows={levels}
              onUpdateRaw={updateLevel}
              onSaved={reload}
              onDelete={async (id) => { await deleteLevelRow(id); reload(); }}
              onCreate={async (f) => { await createLevel(f); reload(); }}
              onRowClick={handleReferenceRowClick}
            />

            <EditableTable
              title="Statuts"
              columns={[{ key: "label", label: "libellé" }, { key: "description", label: "description", width: 200 }]}
              rows={statuts}
              onUpdateRaw={updateStatut}
              onSaved={reload}
              onDelete={async (id) => { await deleteStatutRow(id); reload(); }}
              onCreate={async (f) => { await createStatut(f); reload(); }}
              onRowClick={handleReferenceRowClick}
            />

            <TicketsEditTable tickets={tickets} users={users} types={types} levels={levels} statuts={statuts} onUpdated={reload} onRowClick={handleTicketRowClick} />
          </div>

          <div style={{ flex: 1, minWidth: 280, display: "flex", flexDirection: "column", gap: "0.75rem" }}>
            <div style={{ flex: 1, display: "flex", flexDirection: "column", minHeight: 0 }}>
              <div className="timeline-title" style={{ fontSize: "0.8rem", marginBottom: "0.3rem" }}>Vue générale</div>
              <div className="pixel-grid-controls" style={{ marginBottom: "0.4rem", flexWrap: "wrap" }}>
                {HIERARCHY_OPTIONS.map((h) => (
                  <button key={h.key} className={`pixel-grid-level-btn ${hierarchyKey === h.key ? "active" : ""}`} style={{ fontSize: "0.65rem" }} onClick={() => setHierarchyKey(h.key)}>
                    {h.label}
                  </button>
                ))}
              </div>
              <div className="pixel-grid-mosaic-wrapper" style={{ flex: 1, overflowY: "auto", padding: "0.5rem" }}>
                <JsonBlock data={hierarchyJson} />
              </div>
            </div>

            <div style={{ flex: 1, display: "flex", flexDirection: "column", minHeight: 0 }}>
              <div className="timeline-title" style={{ fontSize: "0.8rem", marginBottom: "0.3rem" }}>
                Contexte {inspected && <span className="pixel-grid-empty-hint">— {inspected.label}</span>}
              </div>
              <div className="pixel-grid-mosaic-wrapper" style={{ flex: 1, overflowY: "auto", padding: "0.5rem" }}>
                {inspectLoading ? <p className="synthesis-empty">Chargement…</p> : <JsonBlock data={inspected?.data ?? null} />}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
