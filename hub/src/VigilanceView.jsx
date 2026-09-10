import React, { useState, useEffect } from "react";
import { fetchSignals, fetchSummary, triggerAnalysis } from "./vigilanceClient.js";

// Tuile "Vigilance" (hub), livraison #262 -- backlog item 34, suite
// du module Classification (#260). Demandé explicitement, en
// confirmant une proposition concrète ("pour la catégorie 'client
// DHCP dynamique'... croiser avec les niveaux d'usage") : "OUI
// j'aime c'est tout à fait le genre d'analyse que je veux, sois
// créatif et si possible cible les éléments de cyber vigilance et de
// santé du parc et du réseau".
//
// Trois signaux ciblés sur les clients DHCP dynamiques (voir
// vigilance/README.md pour le raisonnement complet de chacun) :
// contact avec de l'infrastructure (violation de segmentation
// potentielle), diversité de services élevée, croissance de volume
// anormale. Plus un quatrième (livraison #266), cette fois côté
// équipements d'infrastructure : silence prolongé (panne, coupure,
// ou signe de compromission).

const SEVERITY_COLORS = { critical: "var(--danger)", warning: "var(--warning, #b7791f)" };
const SIGNAL_LABELS = {
  contact_infrastructure: "Contact avec de l'infrastructure",
  diversite_services: "Diversité de services élevée",
  croissance_volume: "Croissance de volume anormale",
  infrastructure_silencieuse: "Infrastructure silencieuse",
};

export default function VigilanceView({ onBack, vigilanceApiBase }) {
  const [summary, setSummary] = useState(null);
  const [signals, setSignals] = useState(null);
  const [filterSeverity, setFilterSeverity] = useState("");
  const [loading, setLoading] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);
  const [analyzeResult, setAnalyzeResult] = useState(null);

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [vigilanceApiBase]);

  async function load() {
    setLoading(true);
    const [s, sig] = await Promise.all([fetchSummary(vigilanceApiBase), fetchSignals(vigilanceApiBase, { severity: filterSeverity || undefined })]);
    setSummary(s);
    setSignals(sig);
    setLoading(false);
  }

  async function handleFilterChange(severity) {
    setFilterSeverity(severity);
    setSignals(await fetchSignals(vigilanceApiBase, { severity: severity || undefined }));
  }

  async function handleAnalyzeNow() {
    setAnalyzing(true);
    setAnalyzeResult(null);
    const result = await triggerAnalysis(vigilanceApiBase);
    setAnalyzeResult(result);
    setAnalyzing(false);
    await load();
  }

  const criticalCount = summary ? summary.filter((s) => s.severity === "critical").reduce((a, s) => a + s.n, 0) : 0;
  const warningCount = summary ? summary.filter((s) => s.severity === "warning").reduce((a, s) => a + s.n, 0) : 0;

  return (
    <div className="hub-settings hub-settings-wide">
      <div className="hub-settings-topbar">
        <button className="secondary" onClick={onBack}>◀ Retour</button>
        <h1>🛡️ Vigilance</h1>
      </div>

      <div className="hub-card">
        <p className="muted" style={{ margin: 0 }}>
          Automates d'analyse croisant les appareils classés par <strong>Classification</strong> (surtout les
          clients DHCP dynamiques) avec les échanges, services et niveaux d'usage observés par
          <strong> Exploration réseau</strong> -- pour repérer des comportements qui s'écartent du profil
          attendu d'un client transitoire.
        </p>
      </div>

      {loading ? (
        <p className="muted">Chargement…</p>
      ) : (
        <>
          <div className="hub-card hub-settings-section">
            <h2>Santé du parc -- 7 derniers jours</h2>
            <div style={{ display: "flex", gap: 24, alignItems: "center", marginBottom: 12 }}>
              <span style={{ color: SEVERITY_COLORS.critical, fontWeight: "bold" }}>{criticalCount} critique(s)</span>
              <span style={{ color: SEVERITY_COLORS.warning, fontWeight: "bold" }}>{warningCount} avertissement(s)</span>
              <button onClick={handleAnalyzeNow} disabled={analyzing}>
                {analyzing ? "Analyse en cours…" : "Lancer une analyse maintenant"}
              </button>
            </div>
            {analyzeResult && (
              analyzeResult.error
                ? <p style={{ color: "var(--danger)" }}>⚠️ {analyzeResult.error}</p>
                : <p className="muted">{analyzeResult.signals_detected} signal(aux) détecté(s) à ce passage.</p>
            )}
            {!summary || summary.length === 0 ? (
              <p className="muted">Aucun signal sur les 7 derniers jours -- soit tout va bien, soit
                l'analyse n'a pas encore tourné (elle tourne périodiquement en arrière-plan).</p>
            ) : (
              <table>
                <thead><tr><th>Signal</th><th>Sévérité</th><th>Occurrences</th><th>Appareils distincts</th></tr></thead>
                <tbody>
                  {summary.map((s, idx) => (
                    <tr key={idx}>
                      <td>{SIGNAL_LABELS[s.signal_type] || s.signal_type}</td>
                      <td style={{ color: SEVERITY_COLORS[s.severity] || "inherit" }}>{s.severity}</td>
                      <td>{s.n}</td>
                      <td>{s.distinct_devices}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>

          <div className="hub-card hub-settings-section">
            <h2>Détail des signaux</h2>
            <div className="hub-settings-row">
              <label>Filtrer par sévérité</label>
              <select value={filterSeverity} onChange={(e) => handleFilterChange(e.target.value)}>
                <option value="">— toutes —</option>
                <option value="critical">Critique</option>
                <option value="warning">Avertissement</option>
              </select>
            </div>
            {!signals || signals.length === 0 ? (
              <p className="muted">Aucun signal pour ce filtre.</p>
            ) : (
              <div style={{ maxHeight: 400, overflowY: "auto" }}>
                <table>
                  <thead><tr><th>Appareil</th><th>Signal</th><th>Détail</th><th>Détecté</th></tr></thead>
                  <tbody>
                    {signals.map((s) => (
                      <tr key={s.id}>
                        <td>{s.device_label}</td>
                        <td style={{ color: SEVERITY_COLORS[s.severity] || "inherit" }}>{SIGNAL_LABELS[s.signal_type] || s.signal_type}</td>
                        <td className="muted">{s.detail}</td>
                        <td className="muted">{new Date(s.detected_at).toLocaleString("fr-FR")}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
