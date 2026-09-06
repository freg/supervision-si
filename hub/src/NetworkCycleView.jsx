import React, { useState, useEffect, useCallback, useMemo } from "react";
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

// Position des nœuds sur le SVG (disposés en cercle/flow)
// viewBox 0 0 800 400 — centres calculés pour un pentagone fluide
const NODE_POSITIONS = {
  decider:    { x: 130, y: 200 },
  explorer:   { x: 280, y: 90 },
  deployer:   { x: 520, y: 90 },
  mesurer:    { x: 670, y: 200 },
  apprendre:  { x: 400, y: 320 },
};

// Flux ordonnés pour les flèches
const FLOW_EDGES = [
  { from: "decider", to: "explorer" },
  { from: "explorer", to: "deployer" },
  { from: "deployer", to: "mesurer" },
  { from: "mesurer", to: "apprendre" },
  { from: "apprendre", to: "decider" },
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

// Détermine le statut global d'une étape pour l'indicateur visuel
function getStepStatus(stepId, data) {
  switch (stepId) {
    case "decider": {
      if (!data.netmapOrchestratorApiBase) return "unknown";
      const s = data.orchestratorSummary;
      if (!s) return "unknown";
      return "ok";
    }
    case "explorer": {
      if (!data.networkAgentApiBase) return "unknown";
      const status = data.captureStatus;
      if (!status) return "unknown";
      return status.running ? "ok" : "down";
    }
    case "deployer": {
      if (!data.sshTunnelsApiBase && !data.snmpApiBase) return "unknown";
      const tunnels = data.tunnels || [];
      const snmp = data.snmpTargets || [];
      if (tunnels.length === 0 && snmp.length === 0) return "unknown";
      const hasDown = tunnels.some((t) => t.status === "error");
      return hasDown ? "warn" : "ok";
    }
    case "mesurer": {
      if (!data.netprobeApiBase) return "unknown";
      const samples = data.latestSamples || [];
      if (samples.length === 0) return "unknown";
      const downCount = samples.filter((s) => !s.success).length;
      if (downCount === samples.length) return "down";
      if (downCount > 0) return "warn";
      return "ok";
    }
    case "apprendre": {
      if (!data.vigilanceApiBase && !data.backupRestoreApiBase) return "unknown";
      const sum = data.vigilanceSummary || [];
      const critical = sum.filter((s) => s.severity === "critical").reduce((a, s) => a + (s.n || 0), 0);
      if (critical > 0) return "down";
      const warning = sum.filter((s) => s.severity === "warning").reduce((a, s) => a + (s.n || 0), 0);
      if (warning > 0) return "warn";
      return "ok";
    }
    default:
      return "unknown";
  }
}

// Texte de statut affiché sous chaque nœud
function getStepStatusText(stepId, data) {
  switch (stepId) {
    case "decider": {
      if (!data.netmapOrchestratorApiBase) return "Non configuré";
      const s = data.orchestratorSummary;
      if (!s) return "Pas de données";
      return `${s.open ?? 0} suggestions ouvertes`;
    }
    case "explorer": {
      if (!data.networkAgentApiBase) return "Non configuré";
      const status = data.captureStatus;
      if (!status) return "Pas de données";
      const sites = data.sites?.length ?? 0;
      return status.running ? `Active — ${sites} sites` : "Capture arrêtée";
    }
    case "deployer": {
      const tunnelCount = data.tunnels?.length ?? 0;
      const snmpCount = data.snmpTargets?.length ?? 0;
      const running = data.tunnels?.filter((t) => t.status === "running").length ?? 0;
      if (tunnelCount === 0 && snmpCount === 0) return "Non configuré";
      return `${running}/${tunnelCount} tunnels · ${snmpCount} cibles`;
    }
    case "mesurer": {
      if (!data.netprobeApiBase) return "Non configuré";
      const samples = data.latestSamples || [];
      if (samples.length === 0) return "Pas de données";
      const up = samples.filter((s) => s.success).length;
      return `${up}/${samples.length} en ligne`;
    }
    case "apprendre": {
      if (!data.vigilanceApiBase && !data.backupRestoreApiBase) return "Non configuré";
      const sum = data.vigilanceSummary || [];
      const critical = sum.filter((s) => s.severity === "critical").reduce((a, s) => a + (s.n || 0), 0);
      const warning = sum.filter((s) => s.severity === "warning").reduce((a, s) => a + (s.n || 0), 0);
      if (critical === 0 && warning === 0) return "Rien de critique";
      return `⚠ ${critical} crit. · ${warning} warn.`;
    }
    default:
      return "";
  }
}

// Calcule les points de contrôle pour une courbe de Bézier entre deux nœuds
function computeEdgePath(fromId, toId) {
  const from = NODE_POSITIONS[fromId];
  const to = NODE_POSITIONS[toId];
  if (!from || !to) return "";

  const dx = to.x - from.x;
  const dy = to.y - from.y;
  const dist = Math.sqrt(dx * dx + dy * dy);

  // Courbure légère pour éviter le chevauchement des flèches
  const curveFactor = dist * 0.2;
  const midX = (from.x + to.x) / 2;
  const midY = (from.y + to.y) / 2;

  // Perpendiculaire pour la courbure
  const nx = -dy / dist;
  const ny = dx / dist;
  const cx = midX + nx * curveFactor;
  const cy = midY + ny * curveFactor;

  return `M ${from.x} ${from.y} Q ${cx} ${cy} ${to.x} ${to.y}`;
}

// Point de départ de la flèche (sur le bord du nœud, pas le centre)
function getArrowStartEnd(fromId, toId, nodeRadius = 38) {
  const from = NODE_POSITIONS[fromId];
  const to = NODE_POSITIONS[toId];
  if (!from || !to) return { path: "", start: from, end: to };

  const dx = to.x - from.x;
  const dy = to.y - from.y;
  const dist = Math.sqrt(dx * dx + dy * dy);
  if (dist === 0) return { path: "", start: from, end: to };

  const ux = dx / dist;
  const uy = dy / dist;

  const startX = from.x + ux * nodeRadius;
  const startY = from.y + uy * nodeRadius;
  const endX = to.x - ux * (nodeRadius + 14);
  const endY = to.y - uy * (nodeRadius + 14);

  const curveFactor = dist * 0.2;
  const midX = (startX + endX) / 2;
  const midY = (startY + endY) / 2;
  const nx = -dy / dist;
  const ny = dx / dist;
  const cx = midX + nx * curveFactor;
  const cy = midY + ny * curveFactor;

  const path = `M ${startX} ${startY} Q ${cx} ${cy} ${endX} ${endY}`;
  return { path, start: { x: startX, y: startY }, end: { x: endX, y: endY } };
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
  const [viewMode, setViewMode] = useState("classique");
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

  // Données temps réel pour le graphique (chargées en arrière-plan)
  const graphData = useMemo(() => ({
    netmapOrchestratorApiBase,
    networkAgentApiBase,
    netprobeApiBase,
    snmpApiBase,
    sshTunnelsApiBase,
    vigilanceApiBase,
    backupRestoreApiBase,
    orchestratorSummary,
    suggestions,
    captureStatus,
    sites,
    tunnels,
    connections,
    snmpTargets,
    latestSamples,
    probeConfigs,
    vigilanceSummary,
    signals,
    coverage,
  }), [
    netmapOrchestratorApiBase, networkAgentApiBase, netprobeApiBase,
    snmpApiBase, sshTunnelsApiBase, vigilanceApiBase, backupRestoreApiBase,
    orchestratorSummary, suggestions, captureStatus, sites, tunnels,
    connections, snmpTargets, latestSamples, probeConfigs,
    vigilanceSummary, signals, coverage,
  ]);

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

  // Chargement initial des données pour le graphique (toutes les étapes)
  useEffect(() => {
    if (viewMode !== "graphique") return;
    // Charge les données de toutes les étapes non encore chargées
    const loadAll = async () => {
      const promises = [];
      if (netmapOrchestratorApiBase) {
        promises.push(
          fetchOrchestratorSummary(netmapOrchestratorApiBase).then((d) => {
            if (!d?.error) setOrchestratorSummary(d);
          }),
          fetchOrchestratorSuggestions(netmapOrchestratorApiBase, "open").then((d) => {
            setSuggestions(Array.isArray(d) ? d : []);
          })
        );
      }
      if (networkAgentApiBase) {
        promises.push(
          fetchCaptureStatus(networkAgentApiBase).then((d) => {
            if (!d?.error) setCaptureStatus(d);
          }),
          fetchSites(networkAgentApiBase).then((d) => {
            setSites(Array.isArray(d) ? d : []);
          })
        );
      }
      if (sshTunnelsApiBase) {
        promises.push(
          fetchTunnels(sshTunnelsApiBase).then((d) => setTunnels(Array.isArray(d) ? d : [])),
          fetchConnections(sshTunnelsApiBase).then((d) => setConnections(Array.isArray(d) ? d : []))
        );
      }
      if (snmpApiBase) {
        promises.push(
          fetchSnmpTargets(snmpApiBase).then((d) => setSnmpTargets(Array.isArray(d) ? d : []))
        );
      }
      if (netprobeApiBase) {
        promises.push(
          fetchLatestSamples(netprobeApiBase).then((d) => setLatestSamples(Array.isArray(d?.latest) ? d.latest : [])),
          fetchProbeConfigs(netprobeApiBase).then((d) => setProbeConfigs(Array.isArray(d?.configs) ? d.configs : []))
        );
      }
      if (vigilanceApiBase) {
        promises.push(
          fetchSignals(vigilanceApiBase).then((d) => setSignals(Array.isArray(d) ? d : [])),
          fetchVigilanceSummary(vigilanceApiBase).then((d) => setVigilanceSummary(Array.isArray(d) ? d : []))
        );
      }
      if (backupRestoreApiBase) {
        promises.push(
          fetchCoverage(backupRestoreApiBase).then((d) => {
            if (!d?.error) setCoverage(d);
          })
        );
      }
      await Promise.all(promises);
    };
    loadAll();
  }, [viewMode, netmapOrchestratorApiBase, networkAgentApiBase, netprobeApiBase, snmpApiBase, sshTunnelsApiBase, vigilanceApiBase, backupRestoreApiBase]);

  const currentStep = CYCLE_STEPS.find((s) => s.id === step);
  const stepIndex = CYCLE_STEPS.findIndex((s) => s.id === step);

  // Navigation depuis le graphique : on sélectionne l'étape ET on bascule en mode classique
  function handleNodeClick(stepId) {
    setStep(stepId);
    setViewMode("classique");
  }

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

  // --- Rendu du graphique SVG interactif ---
  function renderGraphique() {
    const nodeRadius = 38;
    const svgWidth = 800;
    const svgHeight = 400;

    return (
      <div className="nc-graph-container">
        <svg
          className="nc-graph-svg"
          viewBox={`0 0 ${svgWidth} ${svgHeight}`}
          preserveAspectRatio="xMidYMid meet"
        >
          <defs>
            {/* Marqueur de flèche statique */}
            <marker
              id="nc-arrowhead"
              viewBox="0 0 10 10"
              refX="9"
              refY="5"
              markerWidth="6"
              markerHeight="6"
              orient="auto-start-reverse"
            >
              <path d="M 0 0 L 10 5 L 0 10 z" fill="var(--border)" />
            </marker>
            {/* Marqueur de flèche animé (accent) */}
            <marker
              id="nc-arrowhead-flow"
              viewBox="0 0 10 10"
              refX="9"
              refY="5"
              markerWidth="7"
              markerHeight="7"
              orient="auto-start-reverse"
            >
              <path d="M 0 0 L 10 5 L 0 10 z" fill="var(--accent)" />
            </marker>
          </defs>

          {/* Flèches du flux (animées) */}
          {FLOW_EDGES.map((edge) => {
            const { path } = getArrowStartEnd(edge.from, edge.to, nodeRadius);
            const fromStep = CYCLE_STEPS.find((s) => s.id === edge.from);
            return (
              <path
                key={`${edge.from}-${edge.to}`}
                d={path}
                className="nc-graph-arrow-flow"
                style={{ stroke: fromStep?.color ?? "var(--accent)" }}
              />
            );
          })}

          {/* Nœuds */}
          {CYCLE_STEPS.map((s) => {
            const pos = NODE_POSITIONS[s.id];
            const status = getStepStatus(s.id, graphData);
            const statusText = getStepStatusText(s.id, graphData);
            return (
              <g
                key={s.id}
                className="nc-graph-node"
                onClick={() => handleNodeClick(s.id)}
              >
                {/* Cercle principal du nœud */}
                <circle
                  cx={pos.x}
                  cy={pos.y}
                  r={nodeRadius}
                  className="nc-graph-node-circle"
                  style={{ stroke: s.color }}
                />
                {/* Icône */}
                <text
                  x={pos.x}
                  y={pos.y - 6}
                  className="nc-graph-node-icon"
                >
                  {s.icon}
                </text>
                {/* Label */}
                <text
                  x={pos.x}
                  y={pos.y + 16}
                  className="nc-graph-node-label"
                >
                  {s.label}
                </text>
                {/* Indicateur de statut (coin inférieur droit) */}
                <circle
                  cx={pos.x + nodeRadius - 8}
                  cy={pos.y + nodeRadius - 8}
                  r={6}
                  className={`nc-status-dot ${status}`}
                />
                {/* Texte de statut */}
                <text
                  x={pos.x}
                  y={pos.y + nodeRadius + 16}
                  className="nc-graph-node-status-text"
                >
                  {statusText}
                </text>
              </g>
            );
          })}
        </svg>

        {/* Légende */}
        <div className="nc-graph-legend">
          <span><span className="nc-graph-legend-dot" style={{ background: "#00b894" }}></span> OK</span>
          <span><span className="nc-graph-legend-dot" style={{ background: "#fdcb6e" }}></span> Attention</span>
          <span><span className="nc-graph-legend-dot" style={{ background: "#c0392b" }}></span> Critique</span>
          <span><span className="nc-graph-legend-dot" style={{ background: "var(--muted)" }}></span> Inconnu</span>
        </div>
      </div>
    );
  }

  return (
    <div className="hub-settings hub-settings-wide">
      <div className="hub-settings-topbar">
        <button className="secondary" onClick={onBack}>◀ Retour</button>
        <h1>🔄 Cycle agile réseau</h1>
      </div>

      {error && <p className="hub-error">{error}</p>}

      {/* Onglets de vue : classique / graphique */}
      <div className="nc-view-tabs">
        <button
          className={`nc-view-tab ${viewMode === "classique" ? "active" : ""}`}
          onClick={() => setViewMode("classique")}
        >
          📋 Classique
        </button>
        <button
          className={`nc-view-tab ${viewMode === "graphique" ? "active" : ""}`}
          onClick={() => setViewMode("graphique")}
        >
          🔄 Graphique
        </button>
      </div>

      {viewMode === "graphique" ? (
        renderGraphique()
      ) : (
        <>
          {/* Navigation du cycle (mode classique) */}
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
        </>
      )}
    </div>
  );
}
