import { useEffect, useRef, useState } from "react";
import { fetchGeoHealth, fetchGeoLayers, importShapefile, fuseLayers, fetchLayerColumns, runCorrelation, syncGeolocationsConnector } from "./geoImportApi.js";
import {
  geometryTypeLabel, isValidFusionSelection, suggestFusionLayerName, looksLikeZipFile,
  CORRELATION_STRATEGIES, strategyNeedsColumns, formatCorrelationScore, validateCorrelationOptions,
} from "./geoImportLib.js";

export default function GeoImportApp() {
  const [health, setHealth] = useState(null);
  const [layers, setLayers] = useState([]);
  const [layersError, setLayersError] = useState(null);

  const [selectedFile, setSelectedFile] = useState(null);
  const [layerNameInput, setLayerNameInput] = useState("");
  const [importMode, setImportMode] = useState("overwrite");
  const [importing, setImporting] = useState(false);
  const [importResult, setImportResult] = useState(null); // {ok, layer, warnings, error, details}
  const fileInputRef = useRef(null);

  const [selectedForFusion, setSelectedForFusion] = useState(new Set());
  const [fusionTargetName, setFusionTargetName] = useState("");
  const [fusing, setFusing] = useState(false);
  const [fusionResult, setFusionResult] = useState(null);

  const [corrLayerA, setCorrLayerA] = useState("");
  const [corrLayerB, setCorrLayerB] = useState("");
  const [corrStrategy, setCorrStrategy] = useState("semantic");
  const [corrColumnsA, setCorrColumnsA] = useState([]);
  const [corrColumnsB, setCorrColumnsB] = useState([]);
  const [corrColumnA, setCorrColumnA] = useState("");
  const [corrColumnB, setCorrColumnB] = useState("");
  const [corrThreshold, setCorrThreshold] = useState(0.3);
  const [corrMaxDistance, setCorrMaxDistance] = useState(50);
  const [corrWindowDays, setCorrWindowDays] = useState(30);
  const [correlating, setCorrelating] = useState(false);
  const [corrResult, setCorrResult] = useState(null);

  const [syncingConnector, setSyncingConnector] = useState(false);
  const [connectorStatus, setConnectorStatus] = useState(null);

  function reload() {
    fetchGeoHealth().then(setHealth);
    fetchGeoLayers().then(({ layers, error }) => {
      setLayers(layers);
      setLayersError(error);
    });
  }

  useEffect(() => {
    reload();
  }, []);

  function handleFileChange(e) {
    const file = e.target.files?.[0] || null;
    setSelectedFile(file);
    setImportResult(null);
    if (file && !layerNameInput) {
      // suggestion de depart a partir du nom de fichier -- toujours
      // editable avant import, jamais impose.
      setLayerNameInput(file.name.replace(/\.zip$/i, ""));
    }
  }

  async function handleImport() {
    if (!selectedFile) return;
    setImporting(true);
    setImportResult(null);
    const { imported, skipped, error } = await importShapefile(selectedFile, layerNameInput, importMode);
    setImporting(false);
    setImportResult({ imported, skipped, error });
    if (!error) {
      setSelectedFile(null);
      setLayerNameInput("");
      if (fileInputRef.current) fileInputRef.current.value = "";
      reload();
    }
  }

  function toggleFusionSelection(name) {
    setSelectedForFusion((prev) => {
      const next = new Set(prev);
      if (next.has(name)) next.delete(name);
      else next.add(name);
      return next;
    });
  }

  async function handleFusion() {
    const sources = [...selectedForFusion];
    const target = fusionTargetName || suggestFusionLayerName(sources);
    setFusing(true);
    setFusionResult(null);
    const { layer, commonColumns, error } = await fuseLayers(sources, target);
    setFusing(false);
    setFusionResult({ ok: !error, layer, commonColumns, error });
    if (!error) {
      setSelectedForFusion(new Set());
      setFusionTargetName("");
      reload();
    }
  }

  const fusionSelectionList = [...selectedForFusion];
  const canFuse = isValidFusionSelection(fusionSelectionList);

  // Charge les colonnes dès qu'une couche est choisie pour la
  // corrélation -- les colonnes d'un shapefile sont arbitraires,
  // jamais supposées à l'avance côté frontend.
  useEffect(() => {
    if (corrLayerA) fetchLayerColumns(corrLayerA).then(({ columns }) => setCorrColumnsA(columns));
    else setCorrColumnsA([]);
    setCorrColumnA("");
  }, [corrLayerA]);

  useEffect(() => {
    if (corrLayerB) fetchLayerColumns(corrLayerB).then(({ columns }) => setCorrColumnsB(columns));
    else setCorrColumnsB([]);
    setCorrColumnB("");
  }, [corrLayerB]);

  function buildCorrelationOptions() {
    if (corrStrategy === "semantic") return { column_a: corrColumnA, column_b: corrColumnB, threshold: corrThreshold };
    if (corrStrategy === "temporal") return { column_a: corrColumnA, column_b: corrColumnB, window_days: corrWindowDays };
    return { max_distance_m: corrMaxDistance };
  }

  async function handleCorrelate() {
    const options = buildCorrelationOptions();
    const validationError = validateCorrelationOptions(corrStrategy, corrLayerA, corrLayerB, options);
    if (validationError) {
      setCorrResult({ ok: false, error: validationError, candidates: [] });
      return;
    }
    setCorrelating(true);
    setCorrResult(null);
    const { candidates, count, truncated, scoreDirection, error } = await runCorrelation(corrLayerA, corrLayerB, corrStrategy, options);
    setCorrelating(false);
    setCorrResult({ ok: !error, error, candidates, count, truncated, scoreDirection });
  }

  async function handleSyncConnector() {
    setSyncingConnector(true);
    setConnectorStatus(null);
    const { layer, synced, error } = await syncGeolocationsConnector();
    setSyncingConnector(false);
    setConnectorStatus({ ok: !error, layer, synced, error });
    if (!error) reload();
  }

  const distanceUnit = corrStrategy === "geographic" ? "m" : corrStrategy === "temporal" ? "j" : undefined;

  return (
    <div className="geo-import-app">
      <header className="geo-import-header">
        <strong>Dépôt shapefiles</strong>
        <span className="geo-import-subtitle">— import vers la base PostGIS de staging, puis fusion</span>
      </header>

      {health && health.status !== "ok" && (
        <div className="geo-import-health-banner">
          ⚠️ Base de staging injoignable{health.error ? ` — ${health.error}` : ""}.
          Vérifiez que <code>geo-postgres</code> est démarré.
        </div>
      )}

      <div className="geo-import-columns">
        <section className="geo-import-panel">
          <h3>Déposer un shapefile</h3>
          <p className="geo-import-hint">
            Archive .zip contenant .shp/.shx/.dbf (+ .prj recommandé pour le système de coordonnées).
            Reprojection automatique en WGS84 à l'import.
          </p>
          <input
            ref={fileInputRef}
            type="file"
            accept=".zip"
            onChange={handleFileChange}
            className="geo-import-file-input"
          />
          {selectedFile && !looksLikeZipFile(selectedFile.name) && (
            <p className="geo-import-error">⚠️ Ce fichier ne ressemble pas à une archive .zip.</p>
          )}
          {selectedFile && (
            <>
              <input
                className="geo-import-text-input"
                value={layerNameInput}
                onChange={(e) => setLayerNameInput(e.target.value)}
                placeholder="Nom de la couche (ignoré si l'archive en contient plusieurs)…"
              />
              <div className="geo-import-mode-choice">
                <label>
                  <input type="radio" checked={importMode === "overwrite"} onChange={() => setImportMode("overwrite")} />
                  Remplacer si la couche existe déjà
                </label>
                <label>
                  <input type="radio" checked={importMode === "append"} onChange={() => setImportMode("append")} />
                  Ajouter à une couche existante (même structure attendue)
                </label>
              </div>
              <button className="geo-import-btn" onClick={handleImport} disabled={importing}>
                {importing ? "Import en cours…" : "📥 Importer"}
              </button>
            </>
          )}
          {importResult && (
            <div className={`geo-import-result ${importResult.error ? "error" : "ok"}`}>
              {importResult.error && <>⚠️ {importResult.error}</>}
              {importResult.imported?.length > 0 && (
                <ul className="geo-import-batch-list">
                  {importResult.imported.map((r, i) => (
                    <li key={i} className={r.ok ? "ok" : "error"}>
                      {r.ok ? "✓" : "⚠️"} « {r.layer} »{!r.ok && ` — ${r.error}`}
                      {r.warnings?.length > 0 && (
                        <ul className="geo-import-warnings">
                          {r.warnings.map((w, j) => <li key={j}>{w}</li>)}
                        </ul>
                      )}
                    </li>
                  ))}
                </ul>
              )}
              {importResult.skipped?.length > 0 && (
                <>
                  <p className="geo-import-hint">Ignorés (jeu incomplet) :</p>
                  <ul className="geo-import-warnings">
                    {importResult.skipped.map((s, i) => <li key={i}>{s}</li>)}
                  </ul>
                </>
              )}
            </div>
          )}
        </section>

        <section className="geo-import-panel">
          <h3>Couches importées {layers.length > 0 && `(${layers.length})`}</h3>
          {layersError && <p className="geo-import-error">⚠️ {layersError}</p>}
          {layers.length === 0 && !layersError && (
            <p className="geo-import-hint">Aucune couche importée pour l'instant.</p>
          )}
          <ul className="geo-import-layer-list">
            {layers.map((l) => (
              <li key={l.name} className="geo-import-layer-item">
                <label>
                  <input
                    type="checkbox"
                    checked={selectedForFusion.has(l.name)}
                    onChange={() => toggleFusionSelection(l.name)}
                  />
                  <span className="geo-import-layer-name">{l.name}</span>
                  <span className="geo-import-layer-type">{geometryTypeLabel(l.geometry_type)}</span>
                  <span className="geo-import-layer-srid">SRID {l.srid}</span>
                </label>
              </li>
            ))}
          </ul>

          <div className="geo-import-fusion-tool">
            <h4>Outil de fusion</h4>
            <p className="geo-import-hint">
              Combine les couches cochées ci-dessus en une seule (colonnes communes uniquement,
              provenance tracée par couche d'origine).
            </p>
            <input
              className="geo-import-text-input"
              value={fusionTargetName}
              onChange={(e) => setFusionTargetName(e.target.value)}
              placeholder={canFuse ? suggestFusionLayerName(fusionSelectionList) : "Nom de la couche fusionnée…"}
              disabled={!canFuse}
            />
            <button className="geo-import-btn" onClick={handleFusion} disabled={!canFuse || fusing}>
              {fusing ? "Fusion en cours…" : `🔗 Fusionner (${fusionSelectionList.length} sélectionnée${fusionSelectionList.length > 1 ? "s" : ""})`}
            </button>
            {fusionResult && (
              <div className={`geo-import-result ${fusionResult.ok ? "ok" : "error"}`}>
                {fusionResult.ok ? (
                  <>✓ Couche fusionnée « {fusionResult.layer} » créée ({fusionResult.commonColumns.length} colonne{fusionResult.commonColumns.length > 1 ? "s" : ""} commune{fusionResult.commonColumns.length > 1 ? "s" : ""}).</>
                ) : (
                  <>⚠️ {fusionResult.error}</>
                )}
              </div>
            )}
          </div>
        </section>
      </div>

      <section className="geo-import-panel geo-import-connectors">
        <h3>Connecteurs vers les autres métiers</h3>
        <p className="geo-import-hint">
          Ponts progressifs vers les modules déjà existants, jamais un accès direct à leur base —
          toujours via leur API. Une fois synchronisée, une table de connecteur devient une couche
          normale, corrélable comme n'importe quelle couche importée.
        </p>
        <div className="geo-import-connector-row">
          <div>
            <strong>geolocations</strong> — positions déjà transversales (Fusion IP/MAC + OwnCloud)
          </div>
          <button className="geo-import-btn" onClick={handleSyncConnector} disabled={syncingConnector}>
            {syncingConnector ? "Synchronisation…" : "🔄 Synchroniser"}
          </button>
        </div>
        {connectorStatus && (
          <div className={`geo-import-result ${connectorStatus.ok ? "ok" : "error"}`}>
            {connectorStatus.ok
              ? `✓ ${connectorStatus.synced} position${connectorStatus.synced > 1 ? "s" : ""} synchronisée${connectorStatus.synced > 1 ? "s" : ""} vers « ${connectorStatus.layer} ».`
              : `⚠️ ${connectorStatus.error}`}
          </div>
        )}
      </section>

      <section className="geo-import-panel geo-import-correlation">
        <h3>Outil de corrélation</h3>
        <p className="geo-import-hint">
          Propose des liens candidats entre deux couches — sémantiques, géographiques ou
          temporels — classés par score. Jamais un merge automatique : c'est à vous de juger.
        </p>
        <div className="geo-import-corr-controls">
          <select className="geo-import-select" value={corrLayerA} onChange={(e) => setCorrLayerA(e.target.value)}>
            <option value="">— couche A —</option>
            {layers.map((l) => <option key={l.name} value={l.name}>{l.name}</option>)}
          </select>
          <select className="geo-import-select" value={corrLayerB} onChange={(e) => setCorrLayerB(e.target.value)}>
            <option value="">— couche B —</option>
            {layers.map((l) => <option key={l.name} value={l.name}>{l.name}</option>)}
          </select>
          <select className="geo-import-select" value={corrStrategy} onChange={(e) => setCorrStrategy(e.target.value)}>
            {CORRELATION_STRATEGIES.map((s) => <option key={s.key} value={s.key}>{s.label}</option>)}
          </select>
        </div>

        {strategyNeedsColumns(corrStrategy) && (
          <div className="geo-import-corr-controls">
            <select className="geo-import-select" value={corrColumnA} onChange={(e) => setCorrColumnA(e.target.value)} disabled={!corrLayerA}>
              <option value="">— colonne de A —</option>
              {corrColumnsA.map((c) => <option key={c.column_name} value={c.column_name}>{c.column_name}</option>)}
            </select>
            <select className="geo-import-select" value={corrColumnB} onChange={(e) => setCorrColumnB(e.target.value)} disabled={!corrLayerB}>
              <option value="">— colonne de B —</option>
              {corrColumnsB.map((c) => <option key={c.column_name} value={c.column_name}>{c.column_name}</option>)}
            </select>
            {corrStrategy === "semantic" && (
              <label className="geo-import-inline-number">
                seuil de similarité
                <input type="number" min="0" max="1" step="0.05" value={corrThreshold}
                  onChange={(e) => setCorrThreshold(Number(e.target.value))} />
              </label>
            )}
            {corrStrategy === "temporal" && (
              <label className="geo-import-inline-number">
                fenêtre (jours)
                <input type="number" min="0" step="1" value={corrWindowDays}
                  onChange={(e) => setCorrWindowDays(Number(e.target.value))} />
              </label>
            )}
          </div>
        )}
        {corrStrategy === "geographic" && (
          <div className="geo-import-corr-controls">
            <label className="geo-import-inline-number">
              distance max (mètres)
              <input type="number" min="0" step="10" value={corrMaxDistance}
                onChange={(e) => setCorrMaxDistance(Number(e.target.value))} />
            </label>
          </div>
        )}

        <button className="geo-import-btn" onClick={handleCorrelate} disabled={correlating}>
          {correlating ? "Corrélation en cours…" : "🔍 Corréler"}
        </button>

        {corrResult && !corrResult.ok && <p className="geo-import-error">⚠️ {corrResult.error}</p>}
        {corrResult?.ok && (
          <div className="geo-import-corr-results">
            <p className="geo-import-hint">
              {corrResult.count} candidat{corrResult.count > 1 ? "s" : ""}
              {corrResult.truncated && " (limité — affinez les critères pour voir plus finement)"}
            </p>
            {corrResult.candidates.length > 0 && (
              <table className="geo-import-corr-table">
                <thead>
                  <tr>
                    <th>A</th>
                    <th>B</th>
                    <th>Score</th>
                  </tr>
                </thead>
                <tbody>
                  {corrResult.candidates.map((c, i) => (
                    <tr key={i}>
                      <td>{c.a_label ?? `#${c.a_id}`}</td>
                      <td>{c.b_label ?? `#${c.b_id}`}</td>
                      <td>{formatCorrelationScore(c.score, corrResult.scoreDirection, distanceUnit)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        )}
      </section>
    </div>
  );
}
