import React, { useState, useEffect } from "react";
import {
  fetchImportedSites, fetchImportedDevices, fetchImportedClients,
  importSitesCsv, importDevicesCsv, importClientsCsv, deleteImportedBatch,
  fetchImportBatches, deleteImportBatches,
  importNebulaDevicesToGlpi,
} from "./nebulaClient.js";

// Onglet Nebula (hub), livraison #228 -- interface pour nebula-api
// (#196-200) et le pont vers GLPI (#208), jusqu'ici accessibles
// seulement via curl.
//
// ⚠️ Vue INTÉRIMAIRE -- le backlog (item 16) note explicitement que
// la présentation "définitive" sera LA tuile unifiée de l'item 20
// (agent réseau fusionné), pas une tuile Nebula séparée -- mais cet
// agent n'existe pas encore. Cette vue rend utilisables dès
// maintenant les imports déjà construits, pour une démonstration,
// sans présumer de la forme finale de la tuile unifiée à venir.
//
// Voie CSV uniquement (import/imported/*) -- la voie API directe
// (test-connection) nécessite le Pro Pack Nebula + une clé support
// Zyxel, deux prérequis bloquants trouvés en #196, jamais réunis
// dans cet environnement -- non câblée ici pour ne pas présenter un
// bouton qui échouerait systématiquement sans ces prérequis.

const TABS = [
  { key: "sites", label: "Sites", columns: ["name", "status", "devices_count", "clients_count", "usage", "offline_devices", "percent_offline"] },
  { key: "devices", label: "Appareils", columns: ["name", "device_type", "model", "site", "mac_address", "status", "clients_count"] },
  { key: "clients", label: "Clients", columns: ["name", "mac_address", "ipv4_address", "connected_to", "manufacturer", "signal_strength", "last_seen"] },
];

const IMPORT_FN = { sites: importSitesCsv, devices: importDevicesCsv, clients: importClientsCsv };
const FETCH_FN = { sites: fetchImportedSites, devices: fetchImportedDevices, clients: fetchImportedClients };

export default function NebulaView({ onBack, nebulaApiBase, glpiApiBase }) {
  const [tab, setTab] = useState("sites");
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [importSummary, setImportSummary] = useState(null);
  const [glpiPreview, setGlpiPreview] = useState(null);
  const [showHistory, setShowHistory] = useState(false);
  const [batches, setBatches] = useState([]);
  const [selectedBatchIds, setSelectedBatchIds] = useState([]);

  useEffect(() => {
    load(tab);
    setSelectedBatchIds([]);
    if (showHistory) loadBatches();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab, nebulaApiBase]);

  async function load(which) {
    setLoading(true);
    setRows(await FETCH_FN[which](nebulaApiBase, false));
    setLoading(false);
  }

  async function loadBatches() {
    setBatches(await fetchImportBatches(nebulaApiBase, tab));
  }

  function toggleShowHistory() {
    setShowHistory((v) => {
      const next = !v;
      if (next) { loadBatches(); setSelectedBatchIds([]); }
      return next;
    });
  }

  function toggleBatchSelection(id) {
    setSelectedBatchIds((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));
  }

  async function handleDeleteSelectedBatches() {
    if (selectedBatchIds.length === 0) return;
    setBusy(true);
    setError(null);
    const result = await deleteImportBatches(nebulaApiBase, selectedBatchIds);
    if (result.error) setError(result.error);
    else {
      setSelectedBatchIds([]);
      loadBatches();
      load(tab);
    }
    setBusy(false);
  }

  async function handleFileUpload(e) {
    const file = e.target.files[0];
    if (!file) return;
    setBusy(true);
    setError(null);
    setImportSummary(null);
    const result = await IMPORT_FN[tab](nebulaApiBase, file);
    if (result.error) {
      setError(result.error);
    } else {
      setImportSummary(result);
      load(tab);
      if (showHistory) loadBatches();
    }
    setBusy(false);
    e.target.value = "";
  }

  async function handleCancelImport() {
    if (!importSummary || !importSummary.imported_at) return;
    setBusy(true);
    const result = await deleteImportedBatch(nebulaApiBase, tab, importSummary.imported_at);
    if (result.error) setError(result.error);
    else {
      setImportSummary(null);
      load(tab);
    }
    setBusy(false);
  }

  async function handleGlpiPreview() {
    setBusy(true);
    setError(null);
    const result = await importNebulaDevicesToGlpi(glpiApiBase, true);
    if (result.error) setError(result.error);
    else setGlpiPreview(result);
    setBusy(false);
  }

  async function handleGlpiConfirm() {
    setBusy(true);
    setError(null);
    const result = await importNebulaDevicesToGlpi(glpiApiBase, false);
    if (result.error) setError(result.error);
    else {
      setGlpiPreview(result);
      setImportSummary({ message: "Import vers GLPI confirmé." });
    }
    setBusy(false);
  }

  const activeTab = TABS.find((t) => t.key === tab);

  return (
    <div className="hub-settings hub-settings-wide">
      <div className="hub-settings-topbar">
        <button className="secondary" onClick={onBack}>◀ Retour</button>
        <h1>🌐 Nebula</h1>
      </div>

      <div className="hub-card">
        <p className="muted" style={{ margin: 0 }}>
          Voie CSV (export direct depuis le portail Nebula) -- la voie API directe nécessite le
          Pro Pack Nebula et une clé support Zyxel, non disponibles dans cet environnement.
        </p>
      </div>

      {error && (
        <div className="hub-card" style={{ borderColor: "var(--hub-danger, #c0392b)" }}>
          <p style={{ margin: 0 }}>⚠️ {error}</p>
        </div>
      )}

      <div className="hub-card hub-settings-section">
        <div className="tabs" style={{ marginBottom: 16 }}>
          {TABS.map((t) => (
            <button key={t.key} className={tab === t.key ? "active" : ""} onClick={() => { setTab(t.key); setImportSummary(null); }}>
              {t.label}
            </button>
          ))}
        </div>

        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
          <h2 style={{ margin: 0 }}>{activeTab.label} ({rows.length})</h2>
          <label className="secondary" style={{ cursor: "pointer" }}>
            📤 Importer un CSV des {activeTab.label}
            <input type="file" accept=".csv" onChange={handleFileUpload} disabled={busy} style={{ display: "none" }} />
          </label>
        </div>
        <p className="muted" style={{ marginTop: -8 }}>
          Le fichier est vérifié avant import -- un export d'un autre type (ex. Appareils déposé
          ici) est refusé avec un message indiquant le bon onglet à utiliser, jamais importé
          silencieusement au mauvais endroit.
        </p>

        {importSummary && (
          <p className="muted">
            {importSummary.imported != null ? `${importSummary.imported} ligne(s) importée(s).` : importSummary.message}
            {importSummary.ged_document_id != null && " Fichier archivé dans la GED."}
            {importSummary.ged_archive_error && ` Archivage GED échoué (données importées quand même) : ${importSummary.ged_archive_error}`}
            {importSummary.imported_at && (
              <>
                {" "}
                <button className="secondary" disabled={busy} onClick={handleCancelImport}>Annuler cet import</button>
              </>
            )}
          </p>
        )}

        <button className="secondary" onClick={toggleShowHistory} style={{ marginBottom: 12 }}>
          {showHistory ? "▾" : "▸"} Historique des imports {activeTab.label}
        </button>

        {showHistory && (
          <div style={{ marginBottom: 16, borderBottom: "1px solid var(--hub-border, #ddd)", paddingBottom: 12 }}>
            {batches.length === 0 ? (
              <p className="muted">Aucun import enregistré pour ce type.</p>
            ) : (
              <>
                <table>
                  <thead>
                    <tr><th></th><th>Fichier</th><th>Date</th><th>Lignes</th><th>Archive GED</th></tr>
                  </thead>
                  <tbody>
                    {batches.map((b) => (
                      <tr key={b.id}>
                        <td>
                          <input
                            type="checkbox"
                            checked={selectedBatchIds.includes(b.id)}
                            onChange={() => toggleBatchSelection(b.id)}
                          />
                        </td>
                        <td>{b.source_filename}</td>
                        <td className="muted">{new Date(b.imported_at).toLocaleString("fr-FR")}</td>
                        <td>{b.row_count}</td>
                        <td>{b.ged_document_id != null ? "✅" : b.ged_archive_error ? `⚠️ ${b.ged_archive_error}` : "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                <button
                  disabled={busy || selectedBatchIds.length === 0}
                  onClick={handleDeleteSelectedBatches}
                  style={{ marginTop: 8 }}
                >
                  Supprimer la sélection ({selectedBatchIds.length})
                </button>
                <p className="muted" style={{ marginTop: 4 }}>
                  Supprime les lignes importées par ces lots -- le fichier archivé dans la GED (✅)
                  reste disponible même après suppression des données.
                </p>
              </>
            )}
          </div>
        )}

        {loading ? (
          <p className="muted">Chargement…</p>
        ) : rows.length === 0 ? (
          <p className="muted">Aucune donnée importée pour l'instant -- utilisez "Importer un CSV des {activeTab.label}" ci-dessus.</p>
        ) : (
          <table>
            <thead>
              <tr>{activeTab.columns.map((c) => <th key={c}>{c}</th>)}</tr>
            </thead>
            <tbody>
              {rows.map((row, idx) => (
                <tr key={idx}>
                  {activeTab.columns.map((c) => <td key={c}>{row[c] ?? <span className="muted">—</span>}</td>)}
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="hub-card hub-settings-section">
        <h2>Import vers GLPI (livraison #208)</h2>
        <p className="muted">
          Importe les appareils Nebula déjà importés (onglet "Appareils" ci-dessus) vers GLPI, en
          NetworkEquipment. Toujours commencer par un aperçu avant de confirmer.
        </p>
        <div style={{ display: "flex", gap: 8 }}>
          <button disabled={busy} onClick={handleGlpiPreview}>Aperçu (dry-run)</button>
          {glpiPreview && (
            <button disabled={busy} onClick={handleGlpiConfirm}>Confirmer l'import</button>
          )}
        </div>
        {glpiPreview && (
          <div style={{ marginTop: 12 }}>
            <p className="muted">
              {glpiPreview.source_device_count} appareil(s) Nebula analysé(s) --{" "}
              {(glpiPreview.created || []).length} à créer,{" "}
              {(glpiPreview.skipped_existing || []).length} déjà présent(s),{" "}
              {(glpiPreview.errors || []).length} erreur(s).
            </p>
            {(glpiPreview.created || []).length > 0 && (
              <ul>
                {glpiPreview.created.map((line, idx) => (
                  <li key={idx}>
                    {typeof line === "string" ? line : `${line.itemtype} '${line.name}'${line.detail ? ` -- ${line.detail}` : ""}`}
                  </li>
                ))}
              </ul>
            )}
            {(glpiPreview.errors || []).length > 0 && (
              <ul>
                {glpiPreview.errors.map((line, idx) => <li key={idx} style={{ color: "var(--hub-danger, #c0392b)" }}>{line}</li>)}
              </ul>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
