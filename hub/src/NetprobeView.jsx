import React, { useState, useEffect } from "react";
import {
  fetchTargets, addTarget, setTargetActive, deleteTarget, importFromNetworkAgent,
  fetchProbeConfigs, setProbeConfig, setProbeConfigEnabled, deleteProbeConfig,
  fetchLatestSamples, fetchSamples,
  scanTarget, fetchNmapScans,
  tcpdumpCapture,
  fetchAnalysisResults, runAnalysis,
} from "./netprobeClient.js";
import NetprobeAgentsTab from "./NetprobeAgentsTab.jsx";

// Tuile "Sondes réseau" (netprobe, livraisons #295/#297/#302/#305/
// #307) -- six onglets : Cibles (collecteur d'IP), Sondes (système
// de contrôle), Suivi (échantillons smokeping), Scans (nmap à la
// demande), Capture (tcpdump partagé, sans stockage), Analyse
// (analyseur multi-scripts, constats sur les données des volets
// précédents). Module DÉLIBÉRÉMENT séparé de network-agent (charge
// active vs capture passive continue, voir netprobe/README.md) --
// import depuis network-agent proposé comme RACCOURCI de saisie,
// jamais une fusion des deux modules.

const PROBE_TYPES = ["smokeping", "nmap", "tcpdump", "ip-collector", "analyzer"];

function formatLatency(ms) {
  return ms == null ? "—" : `${ms.toFixed(1)} ms`;
}

export default function NetprobeView({ onBack, netprobeApiBase }) {
  const [tab, setTab] = useState("cibles");
  const [targets, setTargets] = useState([]);
  const [loadingTargets, setLoadingTargets] = useState(true);
  const [newIp, setNewIp] = useState("");
  const [newLabel, setNewLabel] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  const [configs, setConfigs] = useState([]);
  const [configForm, setConfigForm] = useState({ probeType: "smokeping", enabled: true, frequencySeconds: "300", scheduleStartHour: "", scheduleEndHour: "", targetId: "" });

  const [latest, setLatest] = useState([]);
  const [loadingLatest, setLoadingLatest] = useState(true);
  const [selectedTargetId, setSelectedTargetId] = useState(null);
  const [history, setHistory] = useState([]);

  const [scanTargetId, setScanTargetId] = useState("");
  const [scanPorts, setScanPorts] = useState("");
  const [scanning, setScanning] = useState(false);
  const [scanResult, setScanResult] = useState(null);
  const [scanHistoryTargetId, setScanHistoryTargetId] = useState(null);
  const [scanHistory, setScanHistory] = useState([]);

  const [captureInterface, setCaptureInterface] = useState("");
  const [capturePacketCount, setCapturePacketCount] = useState("200");
  const [capturing, setCapturing] = useState(false);
  const [captureResult, setCaptureResult] = useState(null);

  const [analysisResults, setAnalysisResults] = useState([]);
  const [loadingAnalysis, setLoadingAnalysis] = useState(false);
  const [runningAnalysis, setRunningAnalysis] = useState(false);

  useEffect(() => {
    loadTargets();
    loadConfigs();
    loadLatest();
    loadAnalysisResults();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [netprobeApiBase]);

  async function loadTargets() {
    setLoadingTargets(true);
    setTargets(await fetchTargets(netprobeApiBase));
    setLoadingTargets(false);
  }
  async function loadConfigs() {
    setConfigs(await fetchProbeConfigs(netprobeApiBase));
  }
  async function loadLatest() {
    setLoadingLatest(true);
    setLatest(await fetchLatestSamples(netprobeApiBase));
    setLoadingLatest(false);
  }

  async function handleAddTarget(e) {
    e.preventDefault();
    if (!newIp.trim()) return;
    setBusy(true);
    setError(null);
    const result = await addTarget(netprobeApiBase, newIp.trim(), newLabel.trim());
    setBusy(false);
    if (result.error) {
      setError(result.error);
      return;
    }
    setNewIp("");
    setNewLabel("");
    await loadTargets();
  }

  async function handleToggleActive(target) {
    setBusy(true);
    await setTargetActive(netprobeApiBase, target.id, !target.active);
    setBusy(false);
    await loadTargets();
  }

  async function handleDeleteTarget(targetId) {
    setBusy(true);
    await deleteTarget(netprobeApiBase, targetId);
    setBusy(false);
    await loadTargets();
    await loadLatest();
  }

  async function handleImportFromNetworkAgent() {
    setBusy(true);
    setError(null);
    const result = await importFromNetworkAgent(netprobeApiBase);
    setBusy(false);
    if (result.error) {
      setError(result.error);
      return;
    }
    await loadTargets();
  }

  async function handleSetConfig(e) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    const result = await setProbeConfig(netprobeApiBase, {
      ...configForm,
      targetId: configForm.targetId ? Number(configForm.targetId) : null,
    });
    setBusy(false);
    if (result.error) {
      setError(result.error);
      return;
    }
    await loadConfigs();
  }

  async function handleToggleConfigEnabled(config) {
    setBusy(true);
    await setProbeConfigEnabled(netprobeApiBase, config.id, !config.enabled);
    setBusy(false);
    await loadConfigs();
  }

  async function handleDeleteConfig(configId) {
    setBusy(true);
    await deleteProbeConfig(netprobeApiBase, configId);
    setBusy(false);
    await loadConfigs();
  }

  async function handleSelectTarget(targetId) {
    setSelectedTargetId(targetId);
    setHistory(await fetchSamples(netprobeApiBase, targetId, 50));
  }

  async function handleScan(e) {
    e.preventDefault();
    if (!scanTargetId) return;
    setScanning(true);
    setError(null);
    setScanResult(null);
    const result = await scanTarget(netprobeApiBase, Number(scanTargetId), scanPorts.trim() || null);
    setScanning(false);
    if (result.error) {
      setError(result.error);
      return;
    }
    setScanResult(result);
    if (String(scanHistoryTargetId) === String(scanTargetId)) {
      setScanHistory(await fetchNmapScans(netprobeApiBase, Number(scanTargetId)));
    }
  }

  async function handleShowScanHistory(targetId) {
    setScanHistoryTargetId(targetId);
    setScanHistory(await fetchNmapScans(netprobeApiBase, targetId));
  }

  async function handleCapture(e) {
    e.preventDefault();
    setCapturing(true);
    setError(null);
    setCaptureResult(null);
    const count = capturePacketCount.trim() ? Number(capturePacketCount) : undefined;
    const result = await tcpdumpCapture(netprobeApiBase, captureInterface.trim() || null, count);
    setCapturing(false);
    if (result.error && !result.success) {
      setError(result.error);
      return;
    }
    setCaptureResult(result);
  }

  async function loadAnalysisResults() {
    setLoadingAnalysis(true);
    setAnalysisResults(await fetchAnalysisResults(netprobeApiBase));
    setLoadingAnalysis(false);
  }

  async function handleRunAnalysis() {
    setRunningAnalysis(true);
    setError(null);
    const result = await runAnalysis(netprobeApiBase);
    setRunningAnalysis(false);
    if (result.error) {
      setError(result.error);
      return;
    }
    await loadAnalysisResults();
  }

  const latestByTargetId = Object.fromEntries(latest.map((s) => [s.target_id, s]));

  return (
    <div className="hub-settings hub-settings-wide">
      <div className="hub-settings-topbar">
        <button className="secondary" onClick={onBack}>◀ Retour</button>
        <h1>📡 Sondes réseau</h1>
      </div>
      {error && <p className="hub-error">{error}</p>}

      <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
        <button className={tab === "cibles" ? "" : "secondary"} onClick={() => setTab("cibles")}>🎯 Cibles</button>
        <button className={tab === "sondes" ? "" : "secondary"} onClick={() => setTab("sondes")}>⚙️ Sondes</button>
        <button className={tab === "suivi" ? "" : "secondary"} onClick={() => setTab("suivi")}>📈 Suivi</button>
        <button className={tab === "scans" ? "" : "secondary"} onClick={() => setTab("scans")}>🔍 Scans</button>
        <button className={tab === "capture" ? "" : "secondary"} onClick={() => setTab("capture")}>📦 Capture</button>
        <button className={tab === "analyse" ? "" : "secondary"} onClick={() => setTab("analyse")}>🧠 Analyse</button>
        {/* Sondes distribuées (livraison #407, items 45/47/48) -- flotte de
            Raspberry Pi (sondes WiFi + collecteurs de site), mesures remontées,
            itinérance. Composant séparé : cette vue est déjà longue. */}
        <button className={tab === "wifi" ? "" : "secondary"} onClick={() => setTab("wifi")}>📶 Sondes WiFi</button>
      </div>

      {tab === "wifi" && <NetprobeAgentsTab netprobeApiBase={netprobeApiBase} />}

      {tab === "cibles" && (
        <div className="hub-card hub-settings-section">
          <h2 style={{ marginTop: 0 }}>Cibles surveillées</h2>
          <form onSubmit={handleAddTarget} style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "flex-end", marginBottom: 12 }}>
            <div className="hub-settings-row" style={{ margin: 0 }}>
              <label>Adresse IP</label>
              <input value={newIp} onChange={(e) => setNewIp(e.target.value)} placeholder="192.168.1.10" />
            </div>
            <div className="hub-settings-row" style={{ margin: 0 }}>
              <label>Libellé (optionnel)</label>
              <input value={newLabel} onChange={(e) => setNewLabel(e.target.value)} placeholder="serveur-x" />
            </div>
            <button type="submit" disabled={busy}>+ Ajouter</button>
            <button type="button" className="secondary" disabled={busy} onClick={handleImportFromNetworkAgent}>
              ⬇ Importer depuis network-agent
            </button>
          </form>

          {loadingTargets ? (
            <p className="muted">Chargement…</p>
          ) : targets.length === 0 ? (
            <p className="muted">Aucune cible enregistrée pour l'instant.</p>
          ) : (
            <div className="hub-table-scroll">
            <table>
              <thead><tr><th>IP</th><th>Libellé</th><th>Source</th><th>Actif</th><th></th></tr></thead>
              <tbody>
                {targets.map((t) => (
                  <tr key={t.id}>
                    <td>{t.ip_address}</td>
                    <td className="muted">{t.label || "—"}</td>
                    <td className="muted">{t.source}</td>
                    <td>
                      <input type="checkbox" checked={!!t.active} disabled={busy} onChange={() => handleToggleActive(t)} />
                    </td>
                    <td><button className="secondary" disabled={busy} onClick={() => handleDeleteTarget(t.id)}>🗑</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
            </div>
          )}
        </div>
      )}

      {tab === "sondes" && (
        <div className="hub-card hub-settings-section">
          <h2 style={{ marginTop: 0 }}>Système de contrôle</h2>
          <p className="muted" style={{ marginTop: -4 }}>
            Désactivé par défaut -- une sonde ne démarre jamais toute seule sans configuration explicite.
            Un octroi PRÉCIS (cible choisie) prime sur la configuration GLOBALE (aucune cible = s'applique à toutes).
          </p>
          <form onSubmit={handleSetConfig} style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "flex-end", marginBottom: 12 }}>
            <div className="hub-settings-row" style={{ margin: 0 }}>
              <label>Type de sonde</label>
              <select value={configForm.probeType} onChange={(e) => setConfigForm({ ...configForm, probeType: e.target.value })}>
                {PROBE_TYPES.map((pt) => <option key={pt} value={pt}>{pt}</option>)}
              </select>
            </div>
            <div className="hub-settings-row" style={{ margin: 0 }}>
              <label>Cible (vide = global)</label>
              <select value={configForm.targetId} onChange={(e) => setConfigForm({ ...configForm, targetId: e.target.value })}>
                <option value="">— toutes les cibles —</option>
                {targets.map((t) => <option key={t.id} value={t.id}>{t.ip_address}{t.label ? ` (${t.label})` : ""}</option>)}
              </select>
            </div>
            <div className="hub-settings-row" style={{ margin: 0 }}>
              <label>Activé</label>
              <select value={configForm.enabled ? "1" : "0"} onChange={(e) => setConfigForm({ ...configForm, enabled: e.target.value === "1" })}>
                <option value="1">Oui</option>
                <option value="0">Non</option>
              </select>
            </div>
            <div className="hub-settings-row" style={{ margin: 0 }}>
              <label>Fréquence (secondes)</label>
              <input value={configForm.frequencySeconds} onChange={(e) => setConfigForm({ ...configForm, frequencySeconds: e.target.value })} placeholder="300" style={{ width: 90 }} />
            </div>
            <div className="hub-settings-row" style={{ margin: 0 }}>
              <label>Fenêtre horaire (0-23, optionnel)</label>
              <div style={{ display: "flex", gap: 4, alignItems: "center" }}>
                <input value={configForm.scheduleStartHour} onChange={(e) => setConfigForm({ ...configForm, scheduleStartHour: e.target.value })} placeholder="8" style={{ width: 50 }} />
                <span>→</span>
                <input value={configForm.scheduleEndHour} onChange={(e) => setConfigForm({ ...configForm, scheduleEndHour: e.target.value })} placeholder="18" style={{ width: 50 }} />
              </div>
            </div>
            <button type="submit" disabled={busy}>Enregistrer</button>
          </form>

          {configs.length === 0 ? (
            <p className="muted">Aucune configuration enregistrée -- toutes les sondes sont désactivées par défaut.</p>
          ) : (
            <div className="hub-table-scroll">
            <table>
              <thead><tr><th>Type</th><th>Cible</th><th>Activé</th><th>Fréquence</th><th>Fenêtre</th><th></th></tr></thead>
              <tbody>
                {configs.map((c) => (
                  <tr key={c.id}>
                    <td>{c.probe_type}</td>
                    <td className="muted">{c.target_id == null ? "(toutes)" : (targets.find((t) => t.id === c.target_id)?.ip_address || `#${c.target_id}`)}</td>
                    <td>{c.enabled ? "✅" : "—"}</td>
                    <td className="muted">{c.frequency_seconds ? `${c.frequency_seconds} s` : "—"}</td>
                    <td className="muted">{c.schedule_start_hour != null ? `${c.schedule_start_hour}h → ${c.schedule_end_hour}h` : "—"}</td>
                    <td style={{ display: "flex", gap: 4 }}>
                      <button className="secondary" disabled={busy} onClick={() => handleToggleConfigEnabled(c)} title={c.enabled ? "Suspendre" : "Activer"}>
                        {c.enabled ? "⏸" : "▶"}
                      </button>
                      <button className="secondary" disabled={busy} onClick={() => handleDeleteConfig(c.id)} title="Supprimer">🗑</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            </div>
          )}
        </div>
      )}

      {tab === "suivi" && (
        <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
          <div className="hub-card hub-settings-section" style={{ flex: "1 1 0", minWidth: 320 }}>
            <h2 style={{ marginTop: 0 }}>Dernier échantillon par cible</h2>
            {loadingLatest ? (
              <p className="muted">Chargement…</p>
            ) : latest.length === 0 ? (
              <p className="muted">Aucun échantillon pour l'instant -- vérifiez que smokeping est activé dans l'onglet Sondes.</p>
            ) : (
              <div className="hub-table-scroll">
              <table>
                <thead><tr><th>IP</th><th>État</th><th>Latence</th><th>Perte</th><th>Quand</th></tr></thead>
                <tbody>
                  {latest.map((s) => {
                    const target = targets.find((t) => t.id === s.target_id);
                    return (
                      <tr key={s.target_id} style={{ cursor: "pointer" }} onClick={() => handleSelectTarget(s.target_id)}>
                        <td>{target?.ip_address || `#${s.target_id}`}</td>
                        <td>{s.success ? "🟢" : "🔴"}</td>
                        <td className="muted">{formatLatency(s.latency_ms)}</td>
                        <td className="muted">{s.packet_loss_percent != null ? `${s.packet_loss_percent}%` : "—"}</td>
                        <td className="muted">{s.sampled_at}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
              </div>
            )}
          </div>

          {selectedTargetId && (
            <div className="hub-card hub-settings-section" style={{ flex: "1 1 0", minWidth: 320 }}>
              <h2 style={{ marginTop: 0 }}>
                Historique -- {targets.find((t) => t.id === selectedTargetId)?.ip_address || `#${selectedTargetId}`}
              </h2>
              {history.length === 0 ? (
                <p className="muted">Aucun échantillon.</p>
              ) : (
                <div style={{ maxHeight: 420, overflowY: "auto", overflowX: "auto" }}>
                  <table>
                    <thead><tr><th>Quand</th><th>État</th><th>Latence</th><th>Perte</th></tr></thead>
                    <tbody>
                      {history.map((s) => (
                        <tr key={s.id}>
                          <td className="muted">{s.sampled_at}</td>
                          <td>{s.success ? "🟢" : "🔴"}</td>
                          <td className="muted">{formatLatency(s.latency_ms)}</td>
                          <td className="muted">{s.packet_loss_percent != null ? `${s.packet_loss_percent}%` : "—"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {tab === "scans" && (
        <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
          <div className="hub-card hub-settings-section" style={{ flex: "1 1 0", minWidth: 320 }}>
            <h2 style={{ marginTop: 0 }}>Scan à la demande</h2>
            <p className="muted" style={{ marginTop: -4 }}>
              Geste EXPLICITE -- jamais programmé automatiquement (contrairement à smokeping) : un scan de
              ports est plus intrusif qu'un ping, peut déclencher des alertes côté cible.
            </p>
            <form onSubmit={handleScan} style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "flex-end", marginBottom: 12 }}>
              <div className="hub-settings-row" style={{ margin: 0 }}>
                <label>Cible</label>
                <select value={scanTargetId} onChange={(e) => setScanTargetId(e.target.value)}>
                  <option value="">— choisir —</option>
                  {targets.map((t) => <option key={t.id} value={t.id}>{t.ip_address}{t.label ? ` (${t.label})` : ""}</option>)}
                </select>
              </div>
              <div className="hub-settings-row" style={{ margin: 0 }}>
                <label>Ports (optionnel, ex: 22,80,443)</label>
                <input value={scanPorts} onChange={(e) => setScanPorts(e.target.value)} placeholder="défaut : top 1000" style={{ width: 160 }} />
              </div>
              <button type="submit" disabled={scanning || !scanTargetId}>
                {scanning ? "Scan en cours…" : "🔍 Lancer le scan"}
              </button>
            </form>

            {scanResult && (
              <div>
                {scanResult.open_ports.length === 0 ? (
                  <p className="muted">Aucun port ouvert trouvé{scanResult.scan_duration_seconds != null ? ` (${scanResult.scan_duration_seconds.toFixed(1)}s)` : ""}.</p>
                ) : (
                  <div className="hub-table-scroll">
                  <table>
                    <thead><tr><th>Port</th><th>Protocole</th><th>Service</th></tr></thead>
                    <tbody>
                      {scanResult.open_ports.map((p) => (
                        <tr key={`${p.protocol}-${p.port}`}>
                          <td>{p.port}</td>
                          <td className="muted">{p.protocol}</td>
                          <td className="muted">{p.service || "—"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  </div>
                )}
              </div>
            )}
          </div>

          <div className="hub-card hub-settings-section" style={{ flex: "1 1 0", minWidth: 320 }}>
            <h2 style={{ marginTop: 0 }}>Historique des scans</h2>
            <div className="hub-settings-row" style={{ margin: "0 0 12px" }}>
              <label>Cible</label>
              <select value={scanHistoryTargetId || ""} onChange={(e) => handleShowScanHistory(Number(e.target.value))}>
                <option value="">— choisir —</option>
                {targets.map((t) => <option key={t.id} value={t.id}>{t.ip_address}{t.label ? ` (${t.label})` : ""}</option>)}
              </select>
            </div>
            {scanHistoryTargetId && (
              scanHistory.length === 0 ? (
                <p className="muted">Aucun scan pour cette cible.</p>
              ) : (
                <div style={{ maxHeight: 420, overflowY: "auto", overflowX: "auto" }}>
                  <table>
                    <thead><tr><th>Quand</th><th>État</th><th>Ports ouverts</th></tr></thead>
                    <tbody>
                      {scanHistory.map((s) => (
                        <tr key={s.id}>
                          <td className="muted">{s.scanned_at}</td>
                          <td>{s.success ? "🟢" : "🔴"}</td>
                          <td className="muted">{s.open_ports.length > 0 ? s.open_ports.map((p) => p.port).join(", ") : "—"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )
            )}
          </div>
        </div>
      )}

      {tab === "capture" && (
        <div className="hub-card hub-settings-section">
          <h2 style={{ marginTop: 0 }}>Capture partagée</h2>
          <p className="muted" style={{ marginTop: -4 }}>
            Sans stockage -- le résultat n'est jamais conservé, seulement affiché ici. Geste explicite,
            comme le scan nmap. Une interface calme peut prendre jusqu'à la fin du délai avant de rendre
            un résultat partiel.
          </p>
          <form onSubmit={handleCapture} style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "flex-end", marginBottom: 12 }}>
            <div className="hub-settings-row" style={{ margin: 0 }}>
              <label>Interface (optionnel)</label>
              <input value={captureInterface} onChange={(e) => setCaptureInterface(e.target.value)} placeholder="défaut du système" style={{ width: 140 }} />
            </div>
            <div className="hub-settings-row" style={{ margin: 0 }}>
              <label>Nombre de paquets</label>
              <input value={capturePacketCount} onChange={(e) => setCapturePacketCount(e.target.value)} placeholder="200" style={{ width: 90 }} />
            </div>
            <button type="submit" disabled={capturing}>
              {capturing ? "Capture en cours…" : "📦 Capturer"}
            </button>
          </form>

          {captureResult && (
            <div>
              <p className="muted">
                {captureResult.packet_count} paquet(s) capturé(s)
                {captureResult.error ? ` — ${captureResult.error}` : ""}
              </p>
              {Object.keys(captureResult.protocol_counts || {}).length > 0 && (
                <div style={{ display: "flex", gap: 16, flexWrap: "wrap", marginBottom: 12 }}>
                  {Object.entries(captureResult.protocol_counts).map(([proto, count]) => (
                    <span key={proto} className="muted">{proto} : <strong>{count}</strong></span>
                  ))}
                </div>
              )}
              {(captureResult.top_ips || []).length > 0 && (
                <div className="hub-table-scroll">
                <table>
                  <thead><tr><th>IP</th><th>Occurrences</th></tr></thead>
                  <tbody>
                    {captureResult.top_ips.map((t) => (
                      <tr key={t.ip}><td>{t.ip}</td><td className="muted">{t.count}</td></tr>
                    ))}
                  </tbody>
                </table>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {tab === "analyse" && (
        <div className="hub-card hub-settings-section">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 4 }}>
            <h2 style={{ margin: 0 }}>Constats des analyseurs</h2>
            <button disabled={runningAnalysis} onClick={handleRunAnalysis}>
              {runningAnalysis ? "Analyse en cours…" : "🧠 Lancer maintenant"}
            </button>
          </div>
          <p className="muted" style={{ marginTop: 4 }}>
            Compare les données déjà collectées par les volets précédents (smokeping, nmap) pour repérer une
            dégradation ou un changement -- jamais un nouveau sondage, seulement une relecture de l'historique.
          </p>

          {loadingAnalysis ? (
            <p className="muted">Chargement…</p>
          ) : analysisResults.length === 0 ? (
            <p className="muted">Aucun constat pour l'instant -- lancez une analyse, ou activez "analyzer" dans l'onglet Sondes pour un passage automatique périodique.</p>
          ) : (
            <div className="hub-table-scroll">
            <table>
              <thead><tr><th></th><th>Analyseur</th><th>Cible</th><th>Constat</th><th>Quand</th></tr></thead>
              <tbody>
                {analysisResults.map((r) => (
                  <tr key={r.id}>
                    <td>{r.severity === "critical" ? "🔴" : r.severity === "warning" ? "🟡" : "🔵"}</td>
                    <td className="muted">{r.analyzer_name}</td>
                    <td className="muted">{r.target_id == null ? "(global)" : (targets.find((t) => t.id === r.target_id)?.ip_address || `#${r.target_id}`)}</td>
                    <td>{r.message}</td>
                    <td className="muted">{r.detected_at}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
