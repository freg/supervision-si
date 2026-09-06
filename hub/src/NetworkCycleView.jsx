import React, { useState, useEffect, useCallback } from "react";
import {
  fetchOrchestratorSummary, fetchOrchestratorSuggestions,
  fetchCaptureStatus, fetchSites,
  fetchTunnels, fetchConnections,
  fetchSnmpTargets,
  fetchLatestSamples, fetchProbeConfigs,
  fetchVigilanceSummary, fetchSignals,
  fetchCoverage,
} from "./networkCycleClient.js";

// Tuile hub "Réseau" -- cycle agile réseau en 5 étapes :
// Décider → Explorer → Déployer → Mesurer → Apprendre.
// Chaque étape donne accès aux outils existants du projet
// (netmap-orchestrator, network-agent, netprobe, snmp,
// ssh-tunnels, backup-restore, vigilance) ou résume leur état.

const CYCLE_STEPS = [
  { id: "decider", label: "Décider", icon: "🧭", color: "#6c5ce7" },
  { id: "explorer", label: "Explorer", icon: "🕸️", color: "#0984e3" },
  { id: "deployer", label: "Déployer", icon: "🚀", color: "#00b894" },
  { id: "mesurer", label: "Mesurer", icon: "📊", color: "#fdcb6e" },
  { id: "apprendre", label: "Apprendre", icon: "🧠", color: "#e17055" },
];

function formatDate(iso) {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString("fr-FR");
  } catch {
    return iso;
  }
}

function StatusPill({ ok, label }) {
  return (
    <span className={`nc-pill ${ok ? "ok" : "down"}`}>
      {ok ? "🟢" : "🔴"} {label}
    </span>
  );
}

export default function NetworkCycleView({
  onBack,
  netmapOrchestratorApiBase,
  networkAgentApiBase,
  netprobeApiBase,
  snmpApiBase,
  sshTunnelsApiBase,
  vigilanceApiBase,
  backupRestoreApiBase,
  onNavigate,
}) {
  const [step, setStep] = useState("decider");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // État consolidé de chaque étape
  const [orchestratorSummary, setOrchestratorSummary] = useState(null);
  const [suggestions, setSuggestions] = useState([]);
  const [captureStatus, setCaptureStatus] = useState(null);
  const [sites, setSites] = useState([]);
  const [tunnels, setTunnels] = useState([]);
  const [connections, setConnections] = useState([]);
  const [snmpTargets, setSnmpTargets] = useState([]);
  const [latestSamples, setLatestSamples] = useState([]);
  const [probeConfigs, setProbeConfigs] = useState([]);
  const [vigilanceSummary, setVigilanceSummary] = useState([]);
  const [signals, setSignals] = useState([]);
  const [coverage, setCoverage] = useState(null);

  const loadStep = useCallback(async (s) => {
    setLoading(true);
    setError(null);
    try {
      switch (s) {
        case "decider": {
          const [sum, sug] = await Promise.all([
            netmapOrchestratorApiBase ? fetchOrchestratorSummary(netmapOrchestratorApiBase) : Promise.resolve(null),
            netmapOrchestratorApiBase ? fetchOrchestratorSuggestions(netmapOrchestratorApiBase, "open") : Promise.resolve([]),
          ]);
          setOrchestratorSummary(sum && !sum.error ? sum : null);
          setSuggestions(Array.isArray(sug) ? sug : []);
          break;
        }
        case "explorer": {
          const [status, siteList] = await Promise.all([
            networkAgentApiBase ? fetchCaptureStatus(networkAgentApiBase) : Promise.resolve(null),
            networkAgentApiBase ? fetchSites(networkAgentApiBase) : Promise.resolve([]),
          ]);
          setCaptureStatus(status && !status.error ? status : null);
          setSites(Array.isArray(siteList) ? siteList : []);
          break;
        }
        case "deployer": {
          const [tun, conn, snmp] = await Promise.all([
            sshTunnelsApiBase ? fetchTunnels(sshTunnelsApiBase) : Promise.resolve([]),
            sshTunnelsApiBase ? fetchConnections(sshTunnelsApiBase) : Promise.resolve([]),
            snmpApiBase ? fetchSnmpTargets(snmpApiBase) : Promise.resolve([]),
          ]);
          setTunnels(Array.isArray(tun) ? tun : []);
          setConnections(Array.isArray(conn) ? conn : []);
          setSnmpTargets(Array.isArray(snmp) ? snmp : []);
          break;
        }
        case "mesurer": {
          const [samples, configs] = await Promise.all([
            netprobeApiBase ? fetchLatestSamples(netprobeApiBase) : Promise.resolve([]),
            netprobeApiBase ? fetchProbeConfigs(netprobeApiBase) : Promise.resolve([]),
          ]);
          setLatestSamples(Array.isArray(samples) ? samples : []);
          setProbeConfigs(Array.isArray(configs) ? configs : []);
          break;
        }
        case "apprendre": {
          const [vsig, vsum, cov] = await Promise.all([
            vigilanceApiBase ? fetchSignals(vigilanceApiBase) : Promise.resolve([]),
            vigilanceApiBase ? fetchVigilanceSummary(vigilanceApiBase) : Promise.resolve([]),
            backupRestoreApiBase ? fetchCoverage(backupRestoreApiBase) : Promise.resolve(null),
          ]);
          setSignals(Array.isArray(vsig) ? vsig : []);
          setVigilanceSummary(Array.isArray(vsum) ? vsum : []);
          setCoverage(cov && !cov.error ? cov : null);
          break;
        }
      }
    } catch (err) {
      setError(err.message);
    }
    setLoading(false);
  }, [netmapOrchestratorApiBase, networkAgentApiBase, netprobeApiBase, snmpApiBase, sshTunnelsApiBase, vigilanceApiBase, backupRestoreApiBase]);

  useEffect(() => {
    loadStep(step);
  }, [step, loadStep]);

  const currentStep = CYCLE_STEPS.find((s) => s.id === step);
  const stepIndex = CYCLE_STEPS.findIndex((s) => s.id === step);

  function renderDecider() {
    if (!netmapOrchestratorApiBase) {
      return <p className="muted">Orchestrateur réseau non configuré (VITE_NETMAP_ORCHESTRATOR_API_BASE_URL).</p>;
    }
    return (
      <>
        <div className="nc-kpi-row">
          <div className="nc-kpi">
            <span className="nc-kpi-value">{orchestratorSummary?.open ?? "—"}</span>
            <span className="nc-kpi-label">Suggestions ouvertes</span>
          </div>
          <div className="nc-kpi">
            <span className="nc-kpi-value">{orchestratorSummary?.done ?? "—"}</span>
            <span className="nc-kpi-label">Traitées</span>
          </div>
          <div className="nc-kpi">
            <span className="nc-kpi-value">{orchestratorSummary?.dismissed ?? "—"}</span>
            <span className="nc-kpi-label">Rejetées</span>
          </div>
        </div>
        {suggestions.length === 0 ? (
          <p className="muted">Aucune suggestion ouverte pour l'instant.</p>
        ) : (
          <div className="hub-table-scroll">
            <table>
              <thead><tr><th>Sév.</th><th>Message</th><th>Action suggérée</th><th>Détectée</th></tr></thead>
              <tbody>
                {suggestions.slice(0, 10).map((s) => (
                  <tr key={s.id}>
                    <td>{s.severity === "critical" ? "🔴" : s.severity === "warning" ? "⚠️" : "ℹ️"}</td>
                    <td>{s.message}</td>
                    <td className="muted">{s.suggested_action || "—"}</td>
                    <td className="muted">{formatDate(s.last_detected_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {onNavigate && netmapOrchestratorApiBase && (
          <button className="secondary" onClick={() => onNavigate("netmap-orchestrator")} style={{ marginTop: 12 }}>
            🧭 Ouvrir l'orchestrateur réseau
          </button>
        )}
      </>
    );
  }

  function renderExplorer() {
    if (!networkAgentApiBase) {
      return <p className="muted">Agent réseau non configuré (VITE_NETWORK_AGENT_API_BASE_URL).</p>;
    }
    const totalDevices = sites.reduce((acc, s) => acc + (s.segments?.reduce((a, seg) => a + (seg.device_count || 0), 0) || 0), 0);
    return (
      <>
        <div className="nc-kpi-row">
          <div className="nc-kpi">
            <span className="nc-kpi-value">{captureStatus?.running ? "🟢" : "⚪"}</span>
            <span className="nc-kpi-label">{captureStatus?.running ? "Capture active" : "Capture arrêtée"}</span>
          </div>
          <div className="nc-kpi">
            <span className="nc-kpi-value">{sites.length}</span>
            <span className="nc-kpi-label">Sites</span>
          </div>
          <div className="nc-kpi">
            <span className="nc-kpi-value">{totalDevices}</span>
            <span className="nc-kpi-label">Appareils découverts</span>
          </div>
        </div>
        {sites.length === 0 ? (
          <p className="muted">Aucun site découvert pour l'instant.</p>
        ) : (
          <div className="hub-table-scroll">
            <table>
              <thead><tr><th>Site</th><th>Segments</th><th>Appareils</th></tr></thead>
              <tbody>
                {sites.map((site) => (
                  <tr key={site.id}>
                    <td>{site.name}</td>
                    <td className="muted">{(site.segments || []).map((s) => s.label).join(", ")}</td>
                    <td>{(site.segments || []).reduce((a, s) => a + (s.device_count || 0), 0)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {onNavigate && networkAgentApiBase && (
          <button className="secondary" onClick={() => onNavigate("network-agent")} style={{ marginTop: 12 }}>
            🕸️ Ouvrir l'exploration réseau
          </button>
        )}
      </>
    );
  }

  function renderDeployer() {
    const runningTunnels = tunnels.filter((t) => t.status === "running").length;
    return (
      <>
        <div className="nc-kpi-row">
          <div className="nc-kpi">
            <span className="nc-kpi-value">{connections.length}</span>
            <span className="nc-kpi-label">Connexions SSH</span>
          </div>
          <div className="nc-kpi">
            <span className="nc-kpi-value">{runningTunnels}/{tunnels.length}</span>
            <span className="nc-kpi-label">Tunnels actifs</span>
          </div>
          <div className="nc-kpi">
            <span className="nc-kpi-value">{snmpTargets.length}</span>
            <span className="nc-kpi-label">Cibles SNMP</span>
          </div>
        </div>
        {tunnels.length > 0 && (
          <>
            <h3 style={{ marginBottom: 4 }}>Tunnels</h3>
            <div className="hub-table-scroll">
              <table>
                <thead><tr><th>Nom</th><th>Via</th><th>Local → Distant</th><th>Statut</th></tr></thead>
                <tbody>
                  {tunnels.map((t) => (
                    <tr key={t.id}>
                      <td>{t.label}</td>
                      <td className="muted">{t.connection_label || `#${t.connection_id}`}</td>
                      <td className="muted">:{t.local_port} → {t.remote_host}:{t.remote_port}</td>
                      <td>{statusLabel(t.status)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
        {snmpTargets.length > 0 && (
          <>
            <h3 style={{ marginBottom: 4, marginTop: 12 }}>Cibles SNMP</h3>
            <div className="hub-table-scroll">
              <table>
                <thead><tr><th>Nom</th><th>Hôte</th><th>Port</th></tr></thead>
                <tbody>
                  {snmpTargets.map((t) => (
                    <tr key={t.id}>
                      <td>{t.label}</td>
                      <td className="muted">{t.host}</td>
                      <td className="muted">{t.port}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
        <div style={{ display: "flex", gap: 8, marginTop: 12, flexWrap: "wrap" }}>
          {onNavigate && sshTunnelsApiBase && (
            <button className="secondary" onClick={() => onNavigate("ssh-tunnels")}>🔐 Tunnels SSH</button>
          )}
          {onNavigate && snmpApiBase && (
            <button className="secondary" onClick={() => onNavigate("snmp")}>📡 SNMP</button>
          )}
        </div>
      </>
    );
  }

  function renderMesurer() {
    if (!netprobeApiBase) {
      return <p className="muted">Sondes réseau non configurées (VITE_NETPROBE_API_BASE_URL).</p>;
    }
    const activeProbes = probeConfigs.filter((c) => c.enabled).length;
    const upSamples = latestSamples.filter((s) => s.success).length;
    return (
      <>
        <div className="nc-kpi-row">
          <div className="nc-kpi">
            <span className="nc-kpi-value">{latestSamples.length}</span>
            <span className="nc-kpi-label">Cibles surveillées</span>
          </div>
          <div className="nc-kpi">
            <span className="nc-kpi-value">{upSamples}</span>
            <span className="nc-kpi-label">En ligne</span>
          </div>
          <div className="nc-kpi">
            <span className="nc-kpi-value">{activeProbes}/{probeConfigs.length}</span>
            <span className="nc-kpi-label">Sondes actives</span>
          </div>
        </div>
        {latestSamples.length > 0 && (
          <div className="hub-table-scroll">
            <table>
              <thead><tr><th>Cible</th><th>État</th><th>Latence</th><th>Perte</th><th>Quand</th></tr></thead>
              <tbody>
                {latestSamples.map((s) => (
                  <tr key={s.target_id}>
                    <td>{s.ip_address || `#${s.target_id}`}</td>
                    <td>{s.success ? "🟢" : "🔴"}</td>
                    <td className="muted">{s.latency_ms != null ? `${s.latency_ms.toFixed(1)} ms` : "—"}</td>
                    <td className="muted">{s.packet_loss_percent != null ? `${s.packet_loss_percent}%` : "—"}</td>
                    <td className="muted">{formatDate(s.sampled_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {onNavigate && netprobeApiBase && (
          <button className="secondary" onClick={() => onNavigate("netprobe")} style={{ marginTop: 12 }}>
            📡 Ouvrir les sondes réseau
          </button>
        )}
      </>
    );
  }

  function renderApprendre() {
    const criticalCount = vigilanceSummary.filter((s) => s.severity === "critical").reduce((a, s) => a + (s.n || 0), 0);
    const warningCount = vigilanceSummary.filter((s) => s.severity === "warning").reduce((a, s) => a + (s.n || 0), 0);
    return (
      <>
        <div className="nc-kpi-row">
          <div className="nc-kpi">
            <span className="nc-kpi-value" style={{ color: "var(--hub-danger, #c0392b)" }}>{criticalCount}</span>
            <span className="nc-kpi-label">Critiques</span>
          </div>
          <div className="nc-kpi">
            <span className="nc-kpi-value" style={{ color: "var(--warning, #b7791f)" }}>{warningCount}</span>
            <span className="nc-kpi-label">Avertissements</span>
          </div>
          <div className="nc-kpi">
            <span className="nc-kpi-value">{coverage?.without_backup ?? "—"}</span>
            <span className="nc-kpi-label">Sans sauvegarde</span>
          </div>
        </div>
        {vigilanceSummary.length > 0 && (
          <div className="hub-table-scroll">
            <table>
              <thead><tr><th>Signal</th><th>Sévérité</th><th>Occurrences</th><th>Appareils</th></tr></thead>
              <tbody>
                {vigilanceSummary.map((s, idx) => (
                  <tr key={idx}>
                    <td>{signalLabel(s.signal_type)}</td>
                    <td style={{ color: s.severity === "critical" ? "var(--hub-danger, #c0392b)" : "var(--warning, #b7791f)" }}>{s.severity}</td>
                    <td>{s.n}</td>
                    <td>{s.distinct_devices}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <div style={{ display: "flex", gap: 8, marginTop: 12, flexWrap: "wrap" }}>
          {onNavigate && vigilanceApiBase && (
            <button className="secondary" onClick={() => onNavigate("vigilance")}>🛡️ Vigilance</button>
          )}
          {onNavigate && backupRestoreApiBase && (
            <button className="secondary" onClick={() => onNavigate("backup-restore")}>💾 Sauvegardes</button>
          )}
        </div>
      </>
    );
  }

  function statusLabel(status) {
    const labels = { running: "🟢 en cours", stopped: "⚪ arrêté", error: "🔴 erreur" };
    return labels[status] || status || "—";
  }

  function signalLabel(type) {
    const labels = {
      contact_infrastructure: "Contact infrastructure",
      diversite_services: "Diversité services",
      croissance_volume: "Croissance volume",
      infrastructure_silencieuse: "Infrastructure silencieuse",
    };
    return labels[type] || type;
  }

  return (
    <div className="hub-settings hub-settings-wide">
      <div className="hub-settings-topbar">
        <button className="secondary" onClick={onBack}>◀ Retour</button>
        <h1>🔄 Cycle agile réseau</h1>
      </div>

      {error && <p className="hub-error">{error}</p>}

      {/* Navigation du cycle */}
      <div className="nc-cycle-nav">
        {CYCLE_STEPS.map((s, idx) => (
          <React.Fragment key={s.id}>
            <button
              className={`nc-cycle-step${step === s.id ? " active" : ""}`}
              onClick={() => setStep(s.id)}
              style={{ borderColor: step === s.id ? s.color : undefined }}
            >
              <span className="nc-cycle-icon">{s.icon}</span>
              <span className="nc-cycle-label">{s.label}</span>
            </button>
            {idx < CYCLE_STEPS.length - 1 && <span className="nc-cycle-arrow">→</span>}
          </React.Fragment>
        ))}
      </div>

      {/* Contenu de l'étape */}
      <div className="hub-card hub-settings-section nc-step-content">
        <h2 style={{ marginTop: 0, color: currentStep?.color }}>
          {currentStep?.icon} {currentStep?.label}
        </h2>
        {loading ? (
          <p className="muted">Chargement…</p>
        ) : (
          <>
            {step === "decider" && renderDecider()}
            {step === "explorer" && renderExplorer()}
            {step === "deployer" && renderDeployer()}
            {step === "mesurer" && renderMesurer()}
            {step === "apprendre" && renderApprendre()}
          </>
        )}
      </div>

      {/* Navigation précédent/suivant */}
      <div className="nc-step-nav">
        {stepIndex > 0 && (
          <button className="secondary" onClick={() => setStep(CYCLE_STEPS[stepIndex - 1].id)}>
            ← {CYCLE_STEPS[stepIndex - 1].label}
          </button>
        )}
        {stepIndex < CYCLE_STEPS.length - 1 && (
          <button className="secondary" onClick={() => setStep(CYCLE_STEPS[stepIndex + 1].id)} style={{ marginLeft: "auto" }}>
            {CYCLE_STEPS[stepIndex + 1].label} →
          </button>
        )}
      </div>
    </div>
  );
}
