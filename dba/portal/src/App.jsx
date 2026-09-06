import React, { useEffect, useState } from "react";
import { getJson, postJson, putJson, deleteJson, deleteJsonWithBody, API_BASE_URL } from "./api.js";
import { fetchSshTunnels, fetchSshConnections, fetchSshConnectionUsageHistory, startSshTunnel, stopSshTunnel } from "./sshTunnelsApi.js";
import { createLocalThemeStore } from "./preferences.js";
import { useUnsavedChangesWarning } from "./useUnsavedChangesWarning.js";
import versionInfo from "./VERSION.json";

// Une seule instance pour toute la durée de vie de l'appli -- mode
// LOCAL (pas de compte connu ici, décidé avec la personne), voir
// shared/preferences.js.
const themeStore = createLocalThemeStore();

const ENGINES = [
  { id: "sqlite", label: "SQLite" },
  { id: "postgres", label: "PostgreSQL" },
  { id: "mysql", label: "MySQL" },
];

// Mots-clés dont la présence dans une requête SQL libre déclenche une
// confirmation avant exécution — jamais un blocage, juste un filet de
// sécurité pour une frappe malheureuse (ex. DELETE sans WHERE). Simple
// recherche de sous-chaîne insensible à la casse, pas un vrai parseur
// SQL -- ne prétend pas détecter tous les cas, juste les plus courants.
const DESTRUCTIVE_KEYWORDS = ["drop ", "delete ", "truncate ", "alter table"];

function looksDestructive(sql) {
  const lower = sql.toLowerCase();
  return DESTRUCTIVE_KEYWORDS.some((kw) => lower.includes(kw));
}

// --- Onglet Connexions ---
function ConnectionsTab({ connections, onChanged, selectedId, onSelect }) {
  const [label, setLabel] = useState("");
  const [engine, setEngine] = useState("postgres");
  const [host, setHost] = useState("");
  const [port, setPort] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [databaseName, setDatabaseName] = useState("");
  const [filePath, setFilePath] = useState("");
  const [error, setError] = useState(null);
  const [testResults, setTestResults] = useState({}); // { [id]: {ok, message} }

  // Édition d'une connexion existante -- demandé explicitement, le
  // backend (PUT /connections/<id>, générique) le permettait déjà,
  // seule l'interface manquait. Formulaire séparé de celui de
  // création (mêmes champs, mais jamais mélangés) -- ouvert/fermé
  // par connexion, jamais plus d'une à la fois.
  const [editingId, setEditingId] = useState(null);
  const [editFields, setEditFields] = useState({});
  const [editError, setEditError] = useState(null);
  const [editBusy, setEditBusy] = useState(false);

  const reset = () => {
    setLabel(""); setHost(""); setPort(""); setUsername("");
    setPassword(""); setDatabaseName(""); setFilePath("");
  };

  const create = async () => {
    const body = { label: label.trim(), engine };
    if (engine === "sqlite") {
      body.file_path = filePath.trim();
    } else {
      body.host = host.trim();
      body.port = port ? Number(port) : null;
      body.username = username.trim();
      body.password = password;
      body.database_name = databaseName.trim() || null;
    }
    const res = await postJson("/connections", body);
    if (res.ok) {
      setError(null);
      reset();
      onChanged();
    } else {
      setError(res.data.error || "création impossible");
    }
  };

  const test = async (id) => {
    const res = await postJson(`/connections/${id}/test`);
    setTestResults((prev) => ({ ...prev, [id]: res.ok ? res.data : { ok: false, message: "requête impossible" } }));
  };

  const remove = async (id) => {
    if (!window.confirm("Supprimer cette connexion ? (les identifiants stockés seront perdus)")) return;
    const res = await deleteJson(`/connections/${id}`);
    if (res.ok) onChanged();
  };

  const startEdit = (c) => {
    setEditingId(c.id);
    setEditFields({
      label: c.label,
      engine: c.engine,
      host: c.host || "",
      port: c.port != null ? String(c.port) : "",
      username: c.username || "",
      password: "", // jamais préremplie (jamais renvoyée par l'API) -- vide = conserver l'actuel
      database_name: c.database_name || "",
      file_path: c.file_path || "",
    });
    setEditError(null);
  };

  const cancelEdit = () => {
    setEditingId(null);
    setEditFields({});
    setEditError(null);
  };

  const saveEdit = async () => {
    if (!editFields.label?.trim()) return;
    const body = { label: editFields.label.trim(), engine: editFields.engine };
    if (editFields.engine === "sqlite") {
      body.file_path = editFields.file_path.trim();
    } else {
      body.host = editFields.host.trim();
      body.port = editFields.port ? Number(editFields.port) : null;
      body.username = editFields.username.trim();
      body.database_name = editFields.database_name.trim() || null;
      // Le mot de passe n'est envoyé QUE s'il a été saisi -- un champ
      // vide signifie "conserver le mot de passe actuel", jamais un
      // écrasement accidentel par une chaîne vide.
      if (editFields.password) body.password = editFields.password;
    }
    setEditBusy(true);
    const res = await putJson(`/connections/${editingId}`, body);
    setEditBusy(false);
    if (res.ok) {
      cancelEdit();
      onChanged();
    } else {
      setEditError(res.data.error || "modification impossible");
    }
  };

  // Import d'une sauvegarde mysqldump --all-databases (ou tout dump
  // mysqldump classique) -- multipart, jamais du JSON (fetch brut
  // plutôt que postJson qui force Content-Type: application/json).
  // Envoi synchrone : pour une TRÈS grosse sauvegarde, la requête peut
  // prendre longtemps (jusqu'à 30 min côté serveur avant abandon) --
  // pas de barre de progression fine possible sans un vrai système de
  // tâches asynchrones, pas construit pour cette première version.
  const [importStatus, setImportStatus] = useState({}); // { [connId]: "uploading" | {ok, message} }

  async function handleImportDump(connId, file) {
    setImportStatus((prev) => ({ ...prev, [connId]: "uploading" }));
    const formData = new FormData();
    formData.append("file", file);
    try {
      const response = await fetch(`${API_BASE_URL}/connections/${connId}/import-mysql-dump`, {
        method: "POST",
        body: formData,
      });
      const data = await response.json().catch(() => ({}));
      if (response.ok) {
        setImportStatus((prev) => ({ ...prev, [connId]: { ok: true, message: "Import réussi" } }));
      } else {
        setImportStatus((prev) => ({ ...prev, [connId]: { ok: false, message: data.error || `Erreur ${response.status}` } }));
      }
    } catch (err) {
      setImportStatus((prev) => ({ ...prev, [connId]: { ok: false, message: "Impossible de joindre l'API" } }));
    }
  }

  return (
    <div>
      <div className="dba-panel">
        <h2>➕ Nouvelle connexion</h2>
        <div className="dba-form-row">
          <input placeholder="libellé (ex. Prod MySQL clients)" value={label} onChange={(e) => setLabel(e.target.value)} />
          <select value={engine} onChange={(e) => setEngine(e.target.value)}>
            {ENGINES.map((e) => <option key={e.id} value={e.id}>{e.label}</option>)}
          </select>
        </div>
        {engine === "sqlite" ? (
          <div className="dba-form-row">
            <input
              placeholder="chemin du fichier (ex. /data/quelquechose.db)"
              value={filePath}
              onChange={(e) => setFilePath(e.target.value)}
              style={{ minWidth: "320px" }}
            />
          </div>
        ) : (
          <div className="dba-form-row">
            <input placeholder="hôte" value={host} onChange={(e) => setHost(e.target.value)} />
            <input placeholder={engine === "mysql" ? "port (3306)" : "port (5432)"} value={port} onChange={(e) => setPort(e.target.value)} style={{ width: "90px" }} />
            <input placeholder="utilisateur" value={username} onChange={(e) => setUsername(e.target.value)} />
            <input type="password" placeholder="mot de passe" value={password} onChange={(e) => setPassword(e.target.value)} />
            <input placeholder="base par défaut (optionnel)" value={databaseName} onChange={(e) => setDatabaseName(e.target.value)} />
          </div>
        )}
        <button className="primary" onClick={create} disabled={!label.trim()}>Créer la connexion</button>
        {error && <p className="dba-error">{error}</p>}
      </div>

      <div className="dba-panel">
        <h2>Connexions configurées ({connections.length})</h2>
        {connections.length === 0 && <p className="dba-muted">Aucune connexion pour l'instant.</p>}
        <div className="dba-conn-list">
          {connections.map((c) => (
            <div
              key={c.id}
              className={`dba-conn-item ${selectedId === c.id ? "selected" : ""}`}
              onClick={() => onSelect(c.id)}
            >
              <span>
                {c.label}
                <span className="dba-engine-badge">{c.engine}</span>
                {" — "}
                <span className="dba-muted">
                  {c.engine === "sqlite" ? c.file_path : `${c.username}@${c.host}${c.port ? ":" + c.port : ""}`}
                </span>
              </span>
              <span onClick={(e) => e.stopPropagation()}>
                <button className="secondary" onClick={() => test(c.id)}>🔌 Tester</button>
                {" "}
                <button className="secondary" onClick={() => (editingId === c.id ? cancelEdit() : startEdit(c))}>
                  {editingId === c.id ? "✕ Annuler" : "✏️ Modifier"}
                </button>
                {" "}
                <button className="danger" onClick={() => remove(c.id)}>🗑️</button>
                {testResults[c.id] && (
                  <span style={{ marginLeft: "8px", fontSize: "12px", color: testResults[c.id].ok ? "var(--ok)" : "var(--danger)" }}>
                    {testResults[c.id].ok ? "✓" : "✗"} {testResults[c.id].message}
                  </span>
                )}
              </span>

              {editingId === c.id && (
                <div onClick={(e) => e.stopPropagation()} style={{ marginTop: "10px", paddingTop: "10px", borderTop: "1px solid var(--border)" }}>
                  <div className="dba-form-row">
                    <input placeholder="libellé" value={editFields.label} onChange={(e) => setEditFields({ ...editFields, label: e.target.value })} />
                    <select value={editFields.engine} onChange={(e) => setEditFields({ ...editFields, engine: e.target.value })}>
                      {ENGINES.map((e) => <option key={e.id} value={e.id}>{e.label}</option>)}
                    </select>
                  </div>
                  {editFields.engine === "sqlite" ? (
                    <div className="dba-form-row">
                      <input
                        placeholder="chemin du fichier"
                        value={editFields.file_path}
                        onChange={(e) => setEditFields({ ...editFields, file_path: e.target.value })}
                        style={{ minWidth: "320px" }}
                      />
                    </div>
                  ) : (
                    <div className="dba-form-row">
                      <input placeholder="hôte" value={editFields.host} onChange={(e) => setEditFields({ ...editFields, host: e.target.value })} />
                      <input placeholder="port" value={editFields.port} onChange={(e) => setEditFields({ ...editFields, port: e.target.value })} style={{ width: "90px" }} />
                      <input placeholder="utilisateur" value={editFields.username} onChange={(e) => setEditFields({ ...editFields, username: e.target.value })} />
                      <input
                        type="password"
                        placeholder="mot de passe (vide = inchangé)"
                        value={editFields.password}
                        onChange={(e) => setEditFields({ ...editFields, password: e.target.value })}
                      />
                      <input placeholder="base par défaut" value={editFields.database_name} onChange={(e) => setEditFields({ ...editFields, database_name: e.target.value })} />
                    </div>
                  )}
                  <button className="primary" onClick={saveEdit} disabled={editBusy || !editFields.label?.trim()}>
                    {editBusy ? "…" : "💾 Enregistrer"}
                  </button>
                  {editError && <p className="dba-error">{editError}</p>}
                </div>
              )}
              {c.engine === "mysql" && (
                <div onClick={(e) => e.stopPropagation()} style={{ marginTop: "6px", display: "flex", alignItems: "center", gap: "8px" }}>
                  <label className="secondary" style={{ cursor: "pointer", display: "inline-block" }}>
                    📥 Importer un dump (mysqldump)
                    <input
                      type="file"
                      accept=".sql,.sql.gz,text/plain"
                      style={{ display: "none" }}
                      disabled={importStatus[c.id] === "uploading"}
                      onChange={(e) => {
                        const file = e.target.files?.[0];
                        if (file) handleImportDump(c.id, file);
                        e.target.value = ""; // permet de réimporter le même fichier une seconde fois si besoin
                      }}
                    />
                  </label>
                  {importStatus[c.id] === "uploading" && <span className="dba-muted">Import en cours… (peut prendre du temps sur une grosse sauvegarde)</span>}
                  {importStatus[c.id]?.ok === true && <span style={{ color: "var(--ok)", fontSize: "12px" }}>✓ {importStatus[c.id].message}</span>}
                  {importStatus[c.id]?.ok === false && <span style={{ color: "var(--danger)", fontSize: "12px" }}>✗ {importStatus[c.id].message}</span>}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// --- Sélecteur commun connexion + base (réutilisé par Browse et SQL) ---
function ConnectionDatabasePicker({ connections, connId, onConnChange, database, onDatabaseChange, disabled }) {
  const [databases, setDatabases] = useState([]);

  useEffect(() => {
    if (!connId) { setDatabases([]); return; }
    getJson(`/connections/${connId}/databases`).then((r) => {
      if (r.ok) {
        setDatabases(r.data);
        if (r.data.length > 0 && !r.data.includes(database)) onDatabaseChange(r.data[0]);
      }
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [connId]);

  return (
    <div className="dba-form-row">
      <select value={connId || ""} onChange={(e) => onConnChange(Number(e.target.value) || null)} disabled={disabled}>
        <option value="">— Choisir une connexion —</option>
        {connections.map((c) => <option key={c.id} value={c.id}>{c.label} ({c.engine})</option>)}
      </select>
      {connId && databases.length > 0 && (
        <select value={database || ""} onChange={(e) => onDatabaseChange(e.target.value)} disabled={disabled}>
          {databases.map((d) => <option key={d} value={d}>{d}</option>)}
        </select>
      )}
    </div>
  );
}

// --- Onglet Parcourir ---
function BrowseTab({ connections }) {
  const [connId, setConnId] = useState(null);
  const [database, setDatabase] = useState(null);
  const [tables, setTables] = useState([]);
  const [table, setTable] = useState(null);
  const [columns, setColumns] = useState([]);
  const [rows, setRows] = useState([]);
  const [totalCount, setTotalCount] = useState(0);
  const [offset, setOffset] = useState(0);
  const [error, setError] = useState(null);
  const limit = 50;

  // Édition de cellule avec validation par ligne -- demandé
  // explicitement : le bouton valider/annuler apparaît et BLOQUE la
  // navigation (changement de page, de table, de connexion) tant que
  // l'action n'est pas choisie. Une seule ligne éditable à la fois --
  // jamais deux éditions concurrentes qui se marcheraient dessus.
  const [editingRowIndex, setEditingRowIndex] = useState(null);
  const [editedValues, setEditedValues] = useState({}); // {indexColonne: nouvelle valeur (texte)}
  const [saveBusy, setSaveBusy] = useState(false);
  const [saveError, setSaveError] = useState(null);
  const isEditing = editingRowIndex !== null;

  // Sélection multiple + opérations en lot -- demandé explicitement.
  // Identifiants de clé primaire plutôt que des index de ligne --
  // reste valide même après un tri/rechargement, jamais désynchronisé
  // d'une position dans le tableau.
  const [selectedPks, setSelectedPks] = useState(new Set());
  const [bulkBusy, setBulkBusy] = useState(false);
  const [bulkError, setBulkError] = useState(null);

  // Ajout d'une ligne -- demandé explicitement, même esprit que
  // l'édition (formulaire inline, jamais une nouvelle page).
  const [addingRow, setAddingRow] = useState(false);
  const [newRowValues, setNewRowValues] = useState({});
  const [addBusy, setAddBusy] = useState(false);
  const [addError, setAddError] = useState(null);

  const pkColIndex = columns.findIndex((c) => c.primary_key);
  const isBusy = isEditing || addingRow; // pour bloquer la navigation ET les operations en lot pendant l'une ou l'autre

  // Modification de schéma (ajout/renommage/modification/suppression
  // de colonne) -- demandé explicitement, traité séparément des
  // lignes vu son ampleur propre.
  const [showAddColumnForm, setShowAddColumnForm] = useState(false);
  const [newColName, setNewColName] = useState("");
  const [newColType, setNewColType] = useState("");
  const [newColNullable, setNewColNullable] = useState(true);
  const [editingColumn, setEditingColumn] = useState(null); // nom de la colonne en cours d'edition, ou null
  const [editColNewName, setEditColNewName] = useState("");
  const [editColNewType, setEditColNewType] = useState("");
  const [editColNullable, setEditColNullable] = useState(true);
  const [schemaBusy, setSchemaBusy] = useState(false);
  const [schemaError, setSchemaError] = useState(null);

  // Avertissement natif du navigateur si la personne ferme l'onglet
  // ou navigue ailleurs pendant une édition en cours -- demandé
  // explicitement (premier morceau, isolé, d'une proposition plus
  // large concernant une coquille à onglets pour le hub).
  useUnsavedChangesWarning(isBusy);

  useEffect(() => {
    if (!connId) { setTables([]); setTable(null); return; }
    getJson(`/connections/${connId}/tables${database ? `?database=${encodeURIComponent(database)}` : ""}`).then((r) => {
      if (r.ok) { setTables(r.data); setTable(null); }
    });
  }, [connId, database]);

  useEffect(() => {
    if (!connId || !table) { setColumns([]); setRows([]); return; }
    setOffset(0);
    setSelectedPks(new Set()); // jamais une sélection périmée d'une autre table
    load(0);
    getJson(`/connections/${connId}/tables/${encodeURIComponent(table)}/columns${database ? `?database=${encodeURIComponent(database)}` : ""}`)
      .then((r) => r.ok && setColumns(r.data));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [connId, database, table]);

  const load = async (newOffset) => {
    const params = new URLSearchParams({ limit, offset: newOffset });
    if (database) params.set("database", database);
    const res = await getJson(`/connections/${connId}/tables/${encodeURIComponent(table)}/rows?${params}`);
    if (res.ok) {
      setRows(res.data.rows);
      setTotalCount(res.data.total_count);
      setError(null);
    } else {
      setError(res.data.error || "lecture impossible");
    }
  };

  const changePage = (delta) => {
    if (isBusy) return; // navigation bloquée pendant une édition ou un ajout en cours
    const next = Math.max(0, offset + delta * limit);
    setOffset(next);
    setSelectedPks(new Set()); // jamais une sélection périmée d'une autre page
    load(next);
  };

  const startEditRow = (rowIndex) => {
    if (isBusy) return; // une seule opération à la fois -- jamais une édition pendant un ajout, ou l'inverse
    setEditingRowIndex(rowIndex);
    setEditedValues({});
    setSaveError(null);
  };

  const cancelEdit = () => {
    setEditingRowIndex(null);
    setEditedValues({});
    setSaveError(null);
  };

  const confirmEdit = async () => {
    if (Object.keys(editedValues).length === 0) {
      cancelEdit(); // rien de réellement modifié -- annulation silencieuse
      return;
    }
    const pkColIndex = columns.findIndex((c) => c.primary_key);
    if (pkColIndex === -1) return; // ne devrait jamais arriver (cellule non cliquable sans clé primaire identifiée)
    const pkValue = rows[editingRowIndex][pkColIndex];
    const updates = {};
    for (const [colIndexStr, value] of Object.entries(editedValues)) {
      updates[columns[Number(colIndexStr)].name] = value;
    }

    setSaveBusy(true);
    setSaveError(null);
    const params = new URLSearchParams();
    if (database) params.set("database", database);
    const res = await putJson(
      `/connections/${connId}/tables/${encodeURIComponent(table)}/rows${params.toString() ? `?${params}` : ""}`,
      { pk_value: pkValue, updates }
    );
    setSaveBusy(false);
    if (res.ok) {
      // Mise à jour locale immédiate -- jamais un rechargement complet
      // de la page pour une seule ligne modifiée.
      setRows((prev) => {
        const next = [...prev];
        const updatedRow = [...next[editingRowIndex]];
        for (const [colIndexStr, value] of Object.entries(editedValues)) {
          updatedRow[Number(colIndexStr)] = value;
        }
        next[editingRowIndex] = updatedRow;
        return next;
      });
      cancelEdit();
    } else {
      setSaveError(res.data.error || "modification impossible");
    }
  };

  const toggleRowSelection = (pkValue) => {
    setSelectedPks((prev) => {
      const next = new Set(prev);
      if (next.has(pkValue)) next.delete(pkValue);
      else next.add(pkValue);
      return next;
    });
  };

  const toggleSelectAll = () => {
    if (pkColIndex === -1) return;
    if (selectedPks.size === rows.length && rows.length > 0) {
      setSelectedPks(new Set());
    } else {
      setSelectedPks(new Set(rows.map((r) => r[pkColIndex])));
    }
  };

  const deleteSelected = async () => {
    if (selectedPks.size === 0) return;
    if (!window.confirm(`Supprimer ${selectedPks.size} ligne(s) ? Cette action est irréversible.`)) return;
    setBulkBusy(true);
    setBulkError(null);
    const params = new URLSearchParams();
    if (database) params.set("database", database);
    const res = await deleteJsonWithBody(
      `/connections/${connId}/tables/${encodeURIComponent(table)}/rows${params.toString() ? `?${params}` : ""}`,
      { pk_values: [...selectedPks] }
    );
    setBulkBusy(false);
    if (res.ok) {
      setSelectedPks(new Set());
      load(offset); // rechargement complet ici -- contrairement à une édition simple, le nombre de lignes/la pagination changent
    } else {
      setBulkError(res.data.error || "suppression impossible");
    }
  };

  const duplicateSelected = async () => {
    if (selectedPks.size === 0 || pkColIndex === -1) return;
    if (!window.confirm(`Dupliquer ${selectedPks.size} ligne(s) ? Une nouvelle clé sera générée pour chaque copie.`)) return;
    setBulkBusy(true);
    setBulkError(null);
    const editableCols = columns.filter((c) => !c.primary_key);
    const params = new URLSearchParams();
    if (database) params.set("database", database);
    const query = params.toString() ? `?${params}` : "";
    let failed = 0;
    for (const row of rows) {
      if (!selectedPks.has(row[pkColIndex])) continue;
      const values = {};
      for (const col of editableCols) {
        const idx = columns.findIndex((c) => c.name === col.name);
        values[col.name] = row[idx];
      }
      // Séquentiel plutôt qu'en parallèle -- une duplication en lot
      // reste rare et de faible volume ici (sélection manuelle),
      // jamais besoin de paralléliser au risque de saturer la
      // connexion cible.
      const res = await postJson(`/connections/${connId}/tables/${encodeURIComponent(table)}/rows${query}`, { values });
      if (!res.ok) failed += 1;
    }
    setBulkBusy(false);
    setSelectedPks(new Set());
    if (failed > 0) {
      setBulkError(`${failed} duplication(s) sur ${selectedPks.size} ont échoué.`);
    }
    load(offset);
  };

  const startAddRow = () => {
    if (isBusy) return;
    setAddingRow(true);
    setNewRowValues({});
    setAddError(null);
  };

  const cancelAddRow = () => {
    setAddingRow(false);
    setNewRowValues({});
    setAddError(null);
  };

  const confirmAddRow = async () => {
    setAddBusy(true);
    setAddError(null);
    const params = new URLSearchParams();
    if (database) params.set("database", database);
    const res = await postJson(
      `/connections/${connId}/tables/${encodeURIComponent(table)}/rows${params.toString() ? `?${params}` : ""}`,
      { values: newRowValues }
    );
    setAddBusy(false);
    if (res.ok) {
      cancelAddRow();
      load(offset); // rechargement complet -- le total et la pagination changent
    } else {
      setAddError(res.data.error || "ajout impossible");
    }
  };

  // Recharge colonnes ET données -- toute modification de schéma
  // change potentiellement les deux (une colonne en moins/en plus
  // apparaît aussi dans chaque ligne déjà chargée).
  const reloadSchema = async () => {
    const colParams = database ? `?database=${encodeURIComponent(database)}` : "";
    const res = await getJson(`/connections/${connId}/tables/${encodeURIComponent(table)}/columns${colParams}`);
    if (res.ok) setColumns(res.data);
    load(offset);
  };

  const confirmAddColumn = async () => {
    if (!newColName.trim() || !newColType.trim()) return;
    setSchemaBusy(true);
    setSchemaError(null);
    const params = new URLSearchParams();
    if (database) params.set("database", database);
    const res = await postJson(
      `/connections/${connId}/tables/${encodeURIComponent(table)}/columns${params.toString() ? `?${params}` : ""}`,
      { name: newColName.trim(), type: newColType.trim(), nullable: newColNullable }
    );
    setSchemaBusy(false);
    if (res.ok) {
      setShowAddColumnForm(false);
      setNewColName(""); setNewColType(""); setNewColNullable(true);
      reloadSchema();
    } else {
      setSchemaError(res.data.error || "ajout de colonne impossible");
    }
  };

  const startEditColumn = (col) => {
    setEditingColumn(col.name);
    setEditColNewName(col.name);
    setEditColNewType(col.type);
    setEditColNullable(col.nullable);
    setSchemaError(null);
  };

  const cancelEditColumn = () => {
    setEditingColumn(null);
    setSchemaError(null);
  };

  const confirmEditColumn = async () => {
    setSchemaBusy(true);
    setSchemaError(null);
    const params = new URLSearchParams();
    if (database) params.set("database", database);
    const body = {};
    if (editColNewName.trim() && editColNewName.trim() !== editingColumn) body.new_name = editColNewName.trim();
    if (editColNewType.trim()) body.new_type = editColNewType.trim();
    body.nullable = editColNullable;
    const res = await putJson(
      `/connections/${connId}/tables/${encodeURIComponent(table)}/columns/${encodeURIComponent(editingColumn)}${params.toString() ? `?${params}` : ""}`,
      body
    );
    setSchemaBusy(false);
    if (res.ok) {
      setEditingColumn(null);
      reloadSchema();
    } else {
      setSchemaError(res.data.error || "modification de colonne impossible");
    }
  };

  const deleteColumn = async (colName) => {
    if (!window.confirm(`Supprimer la colonne "${colName}" ? Toutes les données qu'elle contient seront perdues, action irréversible.`)) return;
    setSchemaBusy(true);
    setSchemaError(null);
    const params = new URLSearchParams();
    if (database) params.set("database", database);
    const res = await deleteJson(
      `/connections/${connId}/tables/${encodeURIComponent(table)}/columns/${encodeURIComponent(colName)}${params.toString() ? `?${params}` : ""}`
    );
    setSchemaBusy(false);
    if (res.ok) {
      reloadSchema();
    } else {
      setSchemaError(res.data.error || "suppression de colonne impossible");
    }
  };

  return (
    <div>
      <div className="dba-panel">
        <ConnectionDatabasePicker
          connections={connections} connId={connId} onConnChange={setConnId}
          database={database} onDatabaseChange={setDatabase}
          disabled={isBusy}
        />
        {connId && tables.length > 0 && (
          <div className="dba-form-row">
            <select value={table || ""} onChange={(e) => setTable(e.target.value || null)} disabled={isBusy}>
              <option value="">— Choisir une table —</option>
              {tables.map((t) => <option key={t} value={t}>{t}</option>)}
            </select>
          </div>
        )}
      </div>

      {error && <p className="dba-error">{error}</p>}

      {table && columns.length > 0 && (
        <div className="dba-panel">
          <div className="dba-panel-header-row">
            <h2>{table} — colonnes</h2>
            <button className="secondary" onClick={() => setShowAddColumnForm((v) => !v)} disabled={schemaBusy}>
              {showAddColumnForm ? "✕ Annuler" : "+ Ajouter une colonne"}
            </button>
          </div>
          {schemaError && <p className="dba-error">{schemaError}</p>}

          {showAddColumnForm && (
            <div className="dba-form-row dba-add-column-form">
              <input placeholder="nom" value={newColName} onChange={(e) => setNewColName(e.target.value)} disabled={schemaBusy} autoFocus />
              <input placeholder="type SQL (ex. VARCHAR(200), INTEGER)" value={newColType} onChange={(e) => setNewColType(e.target.value)} disabled={schemaBusy} />
              <label className="dba-inline-checkbox">
                <input type="checkbox" checked={newColNullable} onChange={(e) => setNewColNullable(e.target.checked)} disabled={schemaBusy} />
                Nullable
              </label>
              <button className="primary" onClick={confirmAddColumn} disabled={schemaBusy || !newColName.trim() || !newColType.trim()}>
                {schemaBusy ? "…" : "✓ Ajouter"}
              </button>
            </div>
          )}

          <table className="dba-table">
            <thead><tr><th>Nom</th><th>Type</th><th>Nullable</th><th>Clé primaire</th><th className="dba-row-actions-col"></th></tr></thead>
            <tbody>
              {columns.map((c) => (
                editingColumn === c.name ? (
                  <tr key={c.name} className="dba-row-editing">
                    <td><input value={editColNewName} onChange={(e) => setEditColNewName(e.target.value)} disabled={schemaBusy} /></td>
                    <td><input value={editColNewType} onChange={(e) => setEditColNewType(e.target.value)} disabled={schemaBusy} /></td>
                    <td>
                      <input type="checkbox" checked={editColNullable} onChange={(e) => setEditColNullable(e.target.checked)} disabled={schemaBusy} />
                    </td>
                    <td>{c.primary_key ? "🔑" : ""}</td>
                    <td className="dba-row-actions">
                      <button className="primary" onClick={confirmEditColumn} disabled={schemaBusy}>{schemaBusy ? "…" : "✓"}</button>
                      <button onClick={cancelEditColumn} disabled={schemaBusy}>✕</button>
                    </td>
                  </tr>
                ) : (
                  <tr key={c.name}>
                    <td>{c.name}</td><td>{c.type}</td>
                    <td>{c.nullable ? "oui" : "non"}</td>
                    <td>{c.primary_key ? "🔑" : ""}</td>
                    <td className="dba-row-actions">
                      {!c.primary_key && (
                        <>
                          <button className="secondary" onClick={() => startEditColumn(c)} disabled={schemaBusy || editingColumn !== null}>✏️</button>
                          <button className="danger" onClick={() => deleteColumn(c.name)} disabled={schemaBusy || editingColumn !== null}>🗑️</button>
                        </>
                      )}
                    </td>
                  </tr>
                )
              ))}
            </tbody>
          </table>
        </div>
      )}

      {table && (columns.length > 0) && (
        <div className="dba-panel">
          <div className="dba-panel-header-row">
            <h2>Données ({totalCount} ligne{totalCount > 1 ? "s" : ""} au total)</h2>
            <button className="secondary" onClick={startAddRow} disabled={isBusy}>+ Ajouter une ligne</button>
          </div>
          {columns.every((c) => !c.primary_key) && (
            <p className="dba-muted">Aucune clé primaire identifiée sur cette table -- édition/sélection indisponibles.</p>
          )}
          {saveError && <p className="dba-error">{saveError}</p>}
          {addError && <p className="dba-error">{addError}</p>}
          {bulkError && <p className="dba-error">{bulkError}</p>}

          {selectedPks.size > 0 && (
            <div className="dba-bulk-toolbar">
              <span>{selectedPks.size} ligne{selectedPks.size > 1 ? "s" : ""} sélectionnée{selectedPks.size > 1 ? "s" : ""}</span>
              <button className="secondary" onClick={duplicateSelected} disabled={bulkBusy}>
                {bulkBusy ? "…" : "📋 Dupliquer"}
              </button>
              <button className="danger" onClick={deleteSelected} disabled={bulkBusy}>
                {bulkBusy ? "…" : "🗑️ Supprimer"}
              </button>
            </div>
          )}

          {rows.length === 0 && !addingRow && <p className="dba-muted">Aucune ligne.</p>}

          {(rows.length > 0 || addingRow) && (
          <div style={{ overflowX: "auto" }}>
            <table className="dba-table">
              <thead>
                <tr>
                  {columns.some((c) => c.primary_key) && (
                    <th>
                      <input
                        type="checkbox"
                        checked={rows.length > 0 && selectedPks.size === rows.length}
                        onChange={toggleSelectAll}
                        disabled={isBusy}
                      />
                    </th>
                  )}
                  {columns.map((c) => <th key={c.name}>{c.name}</th>)}
                  {columns.some((c) => c.primary_key) && <th className="dba-row-actions-col"></th>}
                </tr>
              </thead>
              <tbody>
                {addingRow && (
                  <tr className="dba-row-editing">
                    {columns.some((c) => c.primary_key) && <td></td>}
                    {columns.map((col) => (
                      <td key={col.name}>
                        {col.primary_key ? (
                          <span className="dba-muted">(auto)</span>
                        ) : (
                          <input
                            value={newRowValues[col.name] ?? ""}
                            onChange={(e) => setNewRowValues((prev) => ({ ...prev, [col.name]: e.target.value }))}
                            disabled={addBusy}
                            placeholder={col.nullable ? "" : "requis"}
                          />
                        )}
                      </td>
                    ))}
                    <td className="dba-row-actions">
                      <button className="primary" onClick={confirmAddRow} disabled={addBusy}>
                        {addBusy ? "…" : "✓ Ajouter"}
                      </button>
                      <button onClick={cancelAddRow} disabled={addBusy}>✕ Annuler</button>
                    </td>
                  </tr>
                )}
                {rows.map((r, i) => {
                  const rowIsEditing = editingRowIndex === i;
                  const rowPk = pkColIndex !== -1 ? r[pkColIndex] : undefined;
                  const isSelected = pkColIndex !== -1 && selectedPks.has(rowPk);
                  return (
                    <tr key={i} className={rowIsEditing ? "dba-row-editing" : isSelected ? "dba-row-selected" : ""}>
                      {columns.some((c) => c.primary_key) && (
                        <td>
                          {pkColIndex !== -1 && (
                            <input
                              type="checkbox"
                              checked={isSelected}
                              onChange={() => toggleRowSelection(rowPk)}
                              disabled={isBusy}
                            />
                          )}
                        </td>
                      )}
                      {r.map((v, j) => {
                        const col = columns[j];
                        if (rowIsEditing && !col.primary_key) {
                          const currentValue = editedValues[j] !== undefined ? editedValues[j] : (v === null ? "" : String(v));
                          return (
                            <td key={j}>
                              <input
                                value={currentValue}
                                onChange={(e) => setEditedValues((prev) => ({ ...prev, [j]: e.target.value }))}
                                disabled={saveBusy}
                                autoFocus={j === r.findIndex((_, k) => !columns[k].primary_key)}
                              />
                            </td>
                          );
                        }
                        const editable = !col.primary_key && !isBusy && columns.some((c) => c.primary_key);
                        return (
                          <td
                            key={j}
                            title={String(v)}
                            className={editable ? "dba-editable-cell" : ""}
                            onClick={editable ? () => startEditRow(i) : undefined}
                          >
                            {v === null ? <em className="dba-muted">NULL</em> : String(v)}
                          </td>
                        );
                      })}
                      {columns.some((c) => c.primary_key) && (
                        <td className="dba-row-actions">
                          {rowIsEditing && (
                            <>
                              <button className="primary" onClick={confirmEdit} disabled={saveBusy}>
                                {saveBusy ? "…" : "✓ Valider"}
                              </button>
                              <button onClick={cancelEdit} disabled={saveBusy}>✕ Annuler</button>
                            </>
                          )}
                        </td>
                      )}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          )}
          <div className="dba-pagination">
            <button className="secondary" onClick={() => changePage(-1)} disabled={offset === 0 || isBusy}>← Précédent</button>
            <span>{offset + 1}–{Math.min(offset + limit, totalCount)} sur {totalCount}</span>
            <button className="secondary" onClick={() => changePage(1)} disabled={offset + limit >= totalCount || isBusy}>Suivant →</button>
          </div>
        </div>
      )}
    </div>
  );
}

// --- Onglet SQL libre (couvre aussi la gestion de schéma -- DDL =
// juste du SQL, pas de formulaire séparé pour CREATE/ALTER/DROP). ---
function SqlTab({ connections }) {
  const [connId, setConnId] = useState(null);
  const [database, setDatabase] = useState(null);
  const [sql, setSql] = useState("");
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [running, setRunning] = useState(false);

  const run = async () => {
    const trimmed = sql.trim();
    if (!trimmed || !connId) return;
    if (looksDestructive(trimmed) && !window.confirm(
      "Cette requête ressemble à une opération destructrice ou de modification de schéma " +
      "(DROP/DELETE/TRUNCATE/ALTER). Continuer ?"
    )) {
      return;
    }
    setRunning(true);
    setError(null);
    setResult(null);
    const res = await postJson(`/connections/${connId}/sql`, { sql: trimmed, database });
    setRunning(false);
    if (res.ok) setResult(res.data);
    else setError(res.data.error || "exécution impossible");
  };

  return (
    <div>
      <div className="dba-panel">
        <ConnectionDatabasePicker
          connections={connections} connId={connId} onConnChange={setConnId}
          database={database} onDatabaseChange={setDatabase}
        />
        <textarea
          className="dba-sql-editor"
          placeholder="SELECT * FROM ma_table LIMIT 10;&#10;-- ou CREATE TABLE / ALTER TABLE / DELETE...&#10;-- Ctrl+Entrée pour exécuter"
          value={sql}
          onChange={(e) => setSql(e.target.value)}
          onKeyDown={(e) => { if ((e.ctrlKey || e.metaKey) && e.key === "Enter") run(); }}
        />
        <div className="dba-form-row" style={{ marginTop: "8px" }}>
          <button className="primary" onClick={run} disabled={!connId || !sql.trim() || running}>
            {running ? "Exécution…" : "▶ Exécuter (Ctrl+Entrée)"}
          </button>
        </div>
      </div>

      {error && <p className="dba-error">{error}</p>}

      {result && result.affected_rows !== undefined && (
        <p className="dba-success">✓ {result.affected_rows} ligne(s) affectée(s).</p>
      )}

      {result && result.columns && (
        <div className="dba-panel">
          <h2>Résultat ({result.row_count} ligne{result.row_count > 1 ? "s" : ""})</h2>
          <div style={{ overflowX: "auto" }}>
            <table className="dba-table">
              <thead><tr>{result.columns.map((c) => <th key={c}>{c}</th>)}</tr></thead>
              <tbody>
                {result.rows.map((r, i) => (
                  <tr key={i}>{r.map((v, j) => <td key={j} title={String(v)}>{v === null ? <em className="dba-muted">NULL</em> : String(v)}</td>)}</tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

// --- Onglet Catalogue SGBD (livraison #229, backlog item 11) ---
// Extension au portail DBA lui-même de la référence croisée déjà
// livrée côté hub (#221, SchemaAnalyzerView.jsx) -- MÊME logique de
// correspondance (hôte+port, jamais une fusion avec le schéma
// `connections` de ce portail), volontairement dupliquée plutôt que
// partagée entre deux codebases FRONTEND séparées (ce portail et le
// hub sont deux applis Vite distinctes, sans module commun entre
// elles à ce jour -- introduire un partage aurait été un chantier à
// part, jamais fait ici).
function CatalogTab({ connections }) {
  const [tunnels, setTunnels] = useState([]);
  const [sshConnections, setSshConnections] = useState([]);
  const [loaded, setLoaded] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [historyFor, setHistoryFor] = useState(null);
  const [history, setHistory] = useState({});

  const load = async () => {
    setBusy(true);
    setError(null);
    const [tRes, cRes] = await Promise.all([fetchSshTunnels(), fetchSshConnections()]);
    if (!tRes.ok) setError(tRes.data?.error || "chargement des tunnels échoué");
    else if (!cRes.ok) setError(cRes.data?.error || "chargement des connexions SSH échoué");
    else {
      setTunnels(tRes.data);
      setSshConnections(cRes.data);
    }
    setLoaded(true);
    setBusy(false);
  };

  useEffect(() => { load(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const matchingDbaConnections = (localPort) =>
    connections.filter((c) => ["127.0.0.1", "localhost"].includes(c.host) && Number(c.port) === Number(localPort));

  const toggleTunnel = async (tunnel) => {
    setBusy(true);
    if (tunnel.status === "running") await stopSshTunnel(tunnel.id);
    else await startSshTunnel(tunnel.id);
    await load();
  };

  const toggleHistory = async (connectionId) => {
    if (historyFor === connectionId) { setHistoryFor(null); return; }
    setHistoryFor(connectionId);
    if (!history[connectionId]) {
      const res = await fetchSshConnectionUsageHistory(connectionId);
      setHistory((prev) => ({ ...prev, [connectionId]: res.ok ? res.data : [] }));
    }
  };

  return (
    <div>
      <p className="dba-muted">
        Correspondance faite par hôte+port (127.0.0.1/localhost + port local du tunnel) -- aucune
        référence stockée explicitement entre `ssh-tunnels` et les connexions de ce portail.
      </p>
      {error && <p style={{ color: "var(--dba-danger, #c0392b)" }}>⚠️ {error}</p>}
      {!loaded ? (
        <p className="dba-muted">Chargement…</p>
      ) : tunnels.length === 0 ? (
        <p className="dba-muted">Aucun tunnel SSH configuré (onglet Tunnels SSH du hub).</p>
      ) : (
        <table className="dba-table">
          <thead>
            <tr><th>Tunnel</th><th>Port local</th><th>Statut</th><th>Connexion(s) utilisant ce port</th><th></th></tr>
          </thead>
          <tbody>
            {tunnels.map((t) => {
              const sshConn = sshConnections.find((c) => c.id === t.connection_id);
              const matches = matchingDbaConnections(t.local_port);
              return (
                <React.Fragment key={t.id}>
                  <tr>
                    <td>{t.label} {sshConn ? `(${sshConn.label})` : ""}</td>
                    <td>{t.local_port}</td>
                    <td>{t.status === "running" ? "🟢 actif" : "⚪ arrêté"}</td>
                    <td>{matches.length === 0 ? <span className="dba-muted">aucune -- port non repris ici</span> : matches.map((m) => m.label).join(", ")}</td>
                    <td>
                      <button className="secondary" disabled={busy} onClick={() => toggleTunnel(t)}>
                        {t.status === "running" ? "Arrêter" : "Démarrer"}
                      </button>{" "}
                      <button className="secondary" onClick={() => toggleHistory(t.connection_id)}>Historique</button>
                    </td>
                  </tr>
                  {historyFor === t.connection_id && (
                    <tr>
                      <td colSpan={5}>
                        {!history[t.connection_id] ? (
                          <span className="dba-muted">Chargement…</span>
                        ) : history[t.connection_id].length === 0 ? (
                          <span className="dba-muted">Aucun usage enregistré.</span>
                        ) : (
                          <table className="dba-table">
                            <thead><tr><th>Date</th><th>Action</th><th>Résultat</th></tr></thead>
                            <tbody>
                              {history[t.connection_id].map((h) => (
                                <tr key={h.id}>
                                  <td className="dba-muted">{new Date(h.started_at).toLocaleString("fr-FR")}</td>
                                  <td>{h.action_type === "mount" ? "Montage" : "Tunnel"}</td>
                                  <td>{h.success ? "✅ succès" : "❌ échec"}</td>
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
    </div>
  );
}

const TABS = [
  { id: "connections", label: "🔌 Connexions" },
  { id: "browse", label: "📋 Parcourir" },
  { id: "sql", label: "⌨️ SQL" },
  { id: "catalog", label: "🗂️ Catalogue SGBD" },
];

export default function App() {
  const [tab, setTab] = useState("connections");
  const [connections, setConnections] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [theme, setThemeState] = useState(themeStore.get() || "light");
  useEffect(() => themeStore.onChange(setThemeState), []);
  const toggleTheme = () => themeStore.set(theme === "dark" ? "light" : "dark");

  const loadConnections = () => getJson("/connections").then((r) => r.ok && setConnections(r.data));
  useEffect(() => { loadConnections(); }, []);

  return (
    <div>
      <header className="dba-header">
        <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
          <a href="/" className="dba-hub-link" title="Retour au hub">🏠 Hub</a>
          <a href="/?view=settings" className="dba-hub-link" title="Paramètres (page dédiée dans le hub)">⚙️ Paramètres</a>
          <button
            className="dba-hub-link"
            onClick={toggleTheme}
            title={theme === "dark" ? "Passer au thème clair" : "Passer au thème sombre"}
          >
            {theme === "dark" ? "☀️" : "🌙"}
          </button>
          <h1>🗄️ DBA — Administration multi-SGBD</h1>
        </div>
      </header>
      <div className="dba-tabs">
        {TABS.map((t) => (
          <button key={t.id} className={tab === t.id ? "active" : ""} onClick={() => setTab(t.id)}>
            {t.label}
          </button>
        ))}
      </div>
      <main className="dba-main">
        {tab === "connections" && (
          <ConnectionsTab
            connections={connections}
            onChanged={loadConnections}
            selectedId={selectedId}
            onSelect={setSelectedId}
          />
        )}
        {tab === "browse" && <BrowseTab connections={connections} />}
        {tab === "sql" && <SqlTab connections={connections} />}
        {tab === "catalog" && <CatalogTab connections={connections} />}
      </main>
      <div className="version-badge" title={`hash contenu : ${versionInfo.content_hash} · hash git : ${versionInfo.git_hash} · dernière vérification : ${versionInfo.last_checked_at}`}>
        #{versionInfo.delivery_number || "?"}
      </div>
    </div>
  );
}
