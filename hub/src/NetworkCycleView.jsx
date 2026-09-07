import React, { useState, useEffect, useCallback, useMemo, useRef } from "react";
import {
  fetchOrchestratorSummary, fetchOrchestratorSuggestions,
  fetchCaptureStatus, fetchSites,
  fetchTunnels, fetchConnections,
  fetchSnmpTargets,
  fetchLatestSamples, fetchProbeConfigs,
  fetchVigilanceSummary, fetchSignals,
  fetchCoverage,
} from "./networkCycleClient.js";
import {
  GRAPH_ZOOM_STEP,
  GRAPH_VIEW_INITIAL,
  GRAPH_REFRESH_MS,
  GRAPH_VB_WIDTH,
  GRAPH_VB_HEIGHT,
  zoomAtPoint,
  clientDeltaToViewBox,
  clientPointToViewBox,
  clampTooltipPosition,
  getStepTooltipLines,
  extractStepMetrics,
  compareMetrics,
  summarizeTrend,
} from "./networkCycleGraph.js";
import { ICON_SETS, ICON_SET_IDS, loadIconSetPreference, saveIconSetPreference } from "./icons.js";
import { StepIcon, SvgStepIcon } from "./StepIcon.jsx";
import {
  nextMenuState, graphHeightPx, loadLayoutPreference, saveLayoutPreference, hiddenMenuLabel,
} from "./networkCycleLayout.js";

const browserStorage = () => (typeof localStorage !== "undefined" ? localStorage : undefined);

// Tuile hub "Réseau" -- cycle agile réseau en 5 étapes :
// Décider → Explorer → Déployer → Mesurer → Apprendre.
// Chaque étape donne accès aux outils existants du projet
// (netmap-orchestrator, network-agent, netprobe, snmp,
// ssh-tunnels, backup-restore, vigilance) ou résume leur état.

// Les icônes ne sont plus portées ici mais par la charte (icons.js,
// livraison #410) : un jeu d'icônes choisi par la personne, appliqué
// partout où une étape est nommée (menu classique, graphique, titres).
// La couleur reste l'identité de l'étape (règle 2 de la charte).
const CYCLE_STEPS = [
  { id: "decider", label: "Décider", color: "#6c5ce7" },
  { id: "explorer", label: "Explorer", color: "#0984e3" },
  { id: "deployer", label: "Déployer", color: "#00b894" },
  { id: "mesurer", label: "Mesurer", color: "#fdcb6e" },
  { id: "apprendre", label: "Apprendre", color: "#e17055" },
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
  // Disposition (#411) : deux zones, MENU en haut (barre classique OU
  // schéma graphique -- la seule chose que les onglets changent), DÉTAIL
  // de l'étape en bas, toujours présent. Le menu a trois états
  // (expanded / reduced / hidden, voir networkCycleLayout.js) ; l'état
  // d'avant un masquage est retenu pour que la languette le restaure.
  const [layout, setLayout] = useState(() => loadLayoutPreference(browserStorage()));
  const { viewMode, menuState } = layout;
  const menuBeforeHideRef = useRef(null);
  const detailRef = useRef(null);
  const [viewportH, setViewportH] = useState(() => (typeof window !== "undefined" ? window.innerHeight : 900));
  function setViewMode(mode) {
    setLayout((l) => ({ ...l, viewMode: mode }));
  }
  function applyMenuAction(action) {
    setLayout((l) => {
      if (action === "hide") menuBeforeHideRef.current = l.menuState;
      return { ...l, menuState: nextMenuState(l.menuState, action, menuBeforeHideRef.current) };
    });
  }
  useEffect(() => { saveLayoutPreference(browserStorage(), layout); }, [layout]);
  useEffect(() => {
    if (typeof window === "undefined") return undefined;
    const onResize = () => setViewportH(window.innerHeight);
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);
  const graphVisible = viewMode === "graphique" && menuState !== "hidden";

  // Jeu d'icônes de la charte (#410) -- préférence locale au navigateur.
  const [iconSet, setIconSet] = useState(() => loadIconSetPreference(browserStorage()));
  function chooseIconSet(id) {
    setIconSet(id);
    saveIconSetPreference(browserStorage(), id);
  }

  // Graphique : zoom/déplacement, infobulle, rafraîchissement automatique
  const [graphView, setGraphView] = useState(GRAPH_VIEW_INITIAL);
  const [hovered, setHovered] = useState(null);      // { id, x, y } -- x/y en px conteneur
  const [autoRefresh, setAutoRefresh] = useState(false);
  const [lastGraphRefresh, setLastGraphRefresh] = useState(null);
  const [panning, setPanning] = useState(false);
  const graphContainerRef = useRef(null);
  const svgRef = useRef(null);
  const panRef = useRef(null);                        // état du glisser en cours
  const draggedRef = useRef(false);                   // vrai si le dernier geste a déplacé
  // Tendances entre deux rafraîchissements (#404) : métriques du
  // rafraîchissement précédent (ref, jamais un état -- ne doit pas
  // déclencher de rendu) et variations calculées (état, affichées).
  const lastMetricsRef = useRef(null);
  const graphDataRef = useRef(null);
  const [trends, setTrends] = useState({});
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

  // Chargement des données du graphique (toutes les étapes, en parallèle).
  // Extrait en useCallback -- appelé À LA FOIS à l'activation de l'onglet
  // graphique ET par le rafraîchissement automatique, jamais deux copies
  // divergentes de la même liste d'appels.
  const loadGraphData = useCallback(async () => {
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
    setLastGraphRefresh(new Date());
  }, [netmapOrchestratorApiBase, networkAgentApiBase, netprobeApiBase, snmpApiBase, sshTunnelsApiBase, vigilanceApiBase, backupRestoreApiBase]);

  // Chargement à l'activation de l'onglet graphique (ou à sa réapparition
  // après un masquage -- les statuts affichés doivent être à jour).
  useEffect(() => {
    if (!graphVisible) return;
    loadGraphData();
  }, [graphVisible, loadGraphData]);

  // Rafraîchissement automatique -- actif UNIQUEMENT quand l'onglet graphique
  // est affiché ET la bascule enclenchée. La minuterie est nettoyée au retour
  // de l'effet, donc jamais de battement résiduel après un passage en mode
  // classique ni après démontage du composant.
  useEffect(() => {
    if (!graphVisible || !autoRefresh) return undefined;
    const id = setInterval(() => { loadGraphData(); }, GRAPH_REFRESH_MS);
    return () => clearInterval(id);
  }, [graphVisible, autoRefresh, loadGraphData]);

  // Tendances : comparaison des métriques entre deux rafraîchissements
  // COMPLETS. graphData change à chaque réponse d'API individuelle (une
  // dizaine par rafraîchissement) -- en dépendre ici ferait glisser la
  // "référence précédente" à chaque réponse et ne comparerait plus que la
  // dernière. D'où la lecture via une ref, et un déclenchement sur le seul
  // horodatage de fin de rafraîchissement (posé APRÈS Promise.all).
  graphDataRef.current = graphData;
  useEffect(() => {
    if (!lastGraphRefresh) return;
    const data = graphDataRef.current;
    const cur = {};
    for (const st of CYCLE_STEPS) cur[st.id] = extractStepMetrics(st.id, data);
    const prev = lastMetricsRef.current;
    if (prev) {
      const next = {};
      for (const st of CYCLE_STEPS) next[st.id] = compareMetrics(prev[st.id], cur[st.id]);
      setTrends(next);
    }
    lastMetricsRef.current = cur;
  }, [lastGraphRefresh]);

  const currentStep = CYCLE_STEPS.find((s) => s.id === step);
  const stepIndex = CYCLE_STEPS.findIndex((s) => s.id === step);

  // --- Interactions du graphique : molette, glisser, survol ---

  // La molette est écoutée en NON PASSIF, seule façon d'empêcher le
  // défilement de la page pendant le zoom : React attache ses gestionnaires
  // au conteneur racine, où `wheel` est passif par défaut -- un simple
  // onWheel + preventDefault serait ignoré avec un avertissement console.
  useEffect(() => {
    const el = svgRef.current;
    if (!el || !graphVisible) return undefined;
    const onWheel = (e) => {
      e.preventDefault();
      const rect = el.getBoundingClientRect();
      const anchor = clientPointToViewBox(
        e.clientX - rect.left, e.clientY - rect.top, rect,
        GRAPH_VB_WIDTH, GRAPH_VB_HEIGHT,
      );
      const factor = e.deltaY < 0 ? GRAPH_ZOOM_STEP : 1 / GRAPH_ZOOM_STEP;
      setGraphView((v) => zoomAtPoint(v, factor, anchor.x, anchor.y));
    };
    el.addEventListener("wheel", onWheel, { passive: false });
    return () => el.removeEventListener("wheel", onWheel);
  }, [graphVisible]);

  // Déplacement : les gestionnaires vivent sur `window` le temps du glisser,
  // JAMAIS via setPointerCapture sur le SVG -- la capture redirige aussi
  // l'événement `click` vers l'élément capturant, ce qui casserait le clic
  // sur un nœud (le geste principal de ce graphique).
  useEffect(() => {
    if (!panning) return undefined;
    const onMove = (e) => {
      const start = panRef.current;
      if (!start || !svgRef.current) return;
      const rect = svgRef.current.getBoundingClientRect();
      const { dx, dy } = clientDeltaToViewBox(
        e.clientX - start.x, e.clientY - start.y, rect,
        GRAPH_VB_WIDTH, GRAPH_VB_HEIGHT,
      );
      if (Math.abs(e.clientX - start.x) + Math.abs(e.clientY - start.y) > 4) {
        draggedRef.current = true;
      }
      setGraphView({ zoom: start.view.zoom, x: start.view.x + dx, y: start.view.y + dy });
    };
    const onUp = () => {
      panRef.current = null;
      setPanning(false);
    };
    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
    window.addEventListener("pointercancel", onUp);
    return () => {
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
      window.removeEventListener("pointercancel", onUp);
    };
  }, [panning]);

  function handlePanStart(e) {
    // Bouton principal uniquement -- le clic droit reste au menu contextuel.
    if (e.button !== 0) return;
    draggedRef.current = false;
    panRef.current = { x: e.clientX, y: e.clientY, view: graphView };
    setPanning(true);
  }

  function zoomBy(factor) {
    setGraphView((v) => zoomAtPoint(v, factor, GRAPH_VB_WIDTH / 2, GRAPH_VB_HEIGHT / 2));
  }

  function resetGraphView() {
    setGraphView(GRAPH_VIEW_INITIAL);
  }

  function pointInContainer(e) {
    const box = graphContainerRef.current?.getBoundingClientRect();
    if (!box) return null;
    return { x: e.clientX - box.left, y: e.clientY - box.top };
  }

  function handleNodeEnter(stepId, e) {
    const p = pointInContainer(e);
    if (p) setHovered({ id: stepId, x: p.x, y: p.y });
  }

  function handleNodeMove(e) {
    const p = pointInContainer(e);
    if (p) setHovered((h) => (h ? { ...h, x: p.x, y: p.y } : h));
  }

  // Navigation depuis le graphique (#411) : on sélectionne l'étape, dont
  // le détail se déplie DANS LA ZONE BASSE -- on ne quitte plus le
  // schéma. Retour de tests : « quand on clique sur l'une des icônes, les
  // fonctionnalités se déplient sur la seconde moitié basse de l'écran ».
  function handleNodeClick(stepId) {
    // Un glisser qui se termine sur un nœud n'est PAS un clic -- sans ce
    // garde-fou, tout déplacement du graphique se terminerait par un
    // changement d'étape inattendu.
    if (draggedRef.current) {
      draggedRef.current = false;
      return;
    }
    selectStep(stepId);
  }

  // Sélection d'une étape depuis n'importe quel menu. Si le détail commence
  // sous la moitié basse de la fenêtre (schéma en grand sur un petit écran),
  // la page défile juste assez pour l'y amener -- le schéma reste visible
  // dans la moitié haute. Pas de scrollIntoView : avec "nearest" il alignait
  // le BAS du détail et faisait sortir le menu de l'écran (constaté au
  // rendu réel) ; avec "start" il ferait sortir le schéma.
  function selectStep(stepId) {
    setStep(stepId);
    if (typeof requestAnimationFrame !== "function" || typeof window === "undefined") return;
    requestAnimationFrame(() => {
      const rect = detailRef.current?.getBoundingClientRect?.();
      if (!rect) return;
      const half = window.innerHeight / 2;
      if (rect.top > half + 40) {
        window.scrollBy({ top: rect.top - half, behavior: "smooth" });
      }
    });
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
            <span className="nc-kpi-value" style={{ color: "var(--danger)" }}>{criticalCount}</span>
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
                    <td style={{ color: s.severity === "critical" ? "var(--danger)" : "var(--warning, #b7791f)" }}>{s.severity}</td>
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

  // --- Barre d'outils du graphique (zoom, rafraîchissement) ---
  function renderGraphToolbar() {
    return (
      <div className="nc-graph-toolbar">
        <button type="button" className="nc-graph-btn" onClick={() => zoomBy(GRAPH_ZOOM_STEP)} title="Zoom avant">+</button>
        <button type="button" className="nc-graph-btn" onClick={() => zoomBy(1 / GRAPH_ZOOM_STEP)} title="Zoom arrière">−</button>
        <button type="button" className="nc-graph-btn" onClick={resetGraphView} title="Réinitialiser la vue">⟲</button>
        <span className="nc-graph-zoom-level">{Math.round(graphView.zoom * 100)} %</span>
        <span className="nc-graph-toolbar-sep" />
        <button type="button" className="nc-graph-btn" onClick={() => loadGraphData()} title="Rafraîchir maintenant">⟳</button>
        <label className="nc-graph-auto" title={`Rafraîchissement automatique toutes les ${GRAPH_REFRESH_MS / 1000} secondes`}>
          <input
            type="checkbox"
            checked={autoRefresh}
            onChange={(e) => setAutoRefresh(e.target.checked)}
          />
          auto {GRAPH_REFRESH_MS / 1000}s
        </label>
        {lastGraphRefresh && (
          <span className="nc-graph-refresh-time" title="Dernière mise à jour">
            {lastGraphRefresh.toLocaleTimeString("fr-FR")}
          </span>
        )}
      </div>
    );
  }

  // --- Infobulle de survol d'un nœud ---
  function renderGraphTooltip() {
    if (!hovered) return null;
    const s = CYCLE_STEPS.find((c) => c.id === hovered.id);
    const lines = getStepTooltipLines(hovered.id, graphData);
    const box = graphContainerRef.current?.getBoundingClientRect();
    // Dimensions estimées plutôt que mesurées : une mesure réelle imposerait
    // un rendu en deux passes (ref + effet de mise en page) pour un gain nul
    // ici, la largeur étant fixée et les lignes courtes.
    const trendCount = (trends[hovered.id] || []).length;
    const tipW = 250;
    const tipH = 40 + lines.length * 18 + (trendCount ? 22 + trendCount * 17 : 0);
    const { left, top } = clampTooltipPosition(
      hovered.x, hovered.y, tipW, tipH,
      box?.width ?? GRAPH_VB_WIDTH, box?.height ?? 420,
    );
    return (
      <div
        className="nc-graph-tooltip"
        style={{ left, top, width: tipW, borderTopColor: s?.color }}
      >
        <div className="nc-graph-tooltip-title">
          <StepIcon set={iconSet} step={hovered.id} size={15} color={s?.color} /> {s?.label}
        </div>
        {lines.map((line, i) => (
          <div key={i} className="nc-graph-tooltip-line">{line}</div>
        ))}
        {(trends[hovered.id] || []).length > 0 && (
          <div className="nc-graph-tooltip-trends">
            <div className="nc-graph-tooltip-trends-title">Depuis le rafraîchissement précédent</div>
            {trends[hovered.id].map((c) => (
              <div key={c.label} className={`nc-graph-tooltip-trend ${c.tone}`}>
                {c.label} : {c.before} → {c.after} {c.delta > 0 ? "▲" : "▼"}
              </div>
            ))}
          </div>
        )}
        <div className="nc-graph-tooltip-hint">Cliquer pour afficher cette étape ci-dessous</div>
      </div>
    );
  }

  // --- Rendu du graphique SVG interactif ---
  function renderGraphique() {
    const nodeRadius = 38;
    const svgWidth = GRAPH_VB_WIDTH;
    const svgHeight = GRAPH_VB_HEIGHT;

    return (
      <div
        className={`nc-graph-container ${menuState}`}
        ref={graphContainerRef}
        style={{ height: graphHeightPx(menuState, viewportH) }}
      >
        {renderGraphToolbar()}
        <svg
          ref={svgRef}
          className={`nc-graph-svg${panning ? " panning" : ""}`}
          viewBox={`0 0 ${svgWidth} ${svgHeight}`}
          preserveAspectRatio="xMidYMid meet"
          onPointerDown={handlePanStart}
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

          {/* Tout le dessin vit dans un groupe transformé : le zoom et le
              déplacement n'agissent QUE sur ce groupe, jamais sur le viewBox
              -- les marqueurs de flèche déclarés dans <defs> restent donc
              valables, et l'échelle du trait suit naturellement le zoom. */}
          <g transform={`translate(${graphView.x} ${graphView.y}) scale(${graphView.zoom})`}>

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
                  className={`nc-graph-node${s.id === step ? " selected" : ""}`}
                  onClick={() => handleNodeClick(s.id)}
                  onMouseEnter={(e) => handleNodeEnter(s.id, e)}
                  onMouseMove={handleNodeMove}
                  onMouseLeave={() => setHovered(null)}
                >
                  {/* Cercle principal du nœud */}
                  <circle
                    cx={pos.x}
                    cy={pos.y}
                    r={nodeRadius}
                    className="nc-graph-node-circle"
                    style={{ stroke: s.color }}
                  />
                  {/* Icône de la charte (#410) : emoji, symbole ou tracé */}
                  <SvgStepIcon set={iconSet} step={s.id} x={pos.x} y={pos.y - 6} size={22} color={s.color} />
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
                  {/* Marqueur de tendance (coin supérieur droit) -- présent
                      seulement si quelque chose a changé depuis le
                      rafraîchissement précédent ; le détail est dans
                      l'infobulle. */}
                  {summarizeTrend(trends[s.id]) && (
                    <text
                      x={pos.x + nodeRadius - 6}
                      y={pos.y - nodeRadius + 10}
                      className={`nc-trend-mark ${summarizeTrend(trends[s.id])}`}
                    >
                      {summarizeTrend(trends[s.id]) === "bad" ? "▼" : summarizeTrend(trends[s.id]) === "good" ? "▲" : "±"}
                    </text>
                  )}
                </g>
              );
            })}
          </g>
        </svg>

        {renderGraphTooltip()}

        {/* Légende */}
        <div className="nc-graph-legend">
          {/* Couleurs portées par le CSS (variables de thème), jamais en dur
              dans un style en ligne -- un #00b894 fixe ressort faux en thème
              sombre, piège déjà corrigé plusieurs fois dans ce projet. */}
          <span><span className="nc-graph-legend-dot ok"></span> OK</span>
          <span><span className="nc-graph-legend-dot warn"></span> Attention</span>
          <span><span className="nc-graph-legend-dot down"></span> Critique</span>
          <span><span className="nc-graph-legend-dot unknown"></span> Inconnu</span>
        </div>
      </div>
    );
  }

  // --- Menu classique : la barre d'étapes (#411 : un menu parmi deux) ---
  function renderClassicNav() {
    return (
      <div className="nc-cycle-nav">
        {CYCLE_STEPS.map((s, idx) => (
          <React.Fragment key={s.id}>
            <button
              className={`nc-cycle-step${step === s.id ? " active" : ""}`}
              onClick={() => selectStep(s.id)}
              style={{ borderColor: step === s.id ? s.color : undefined }}
            >
              <StepIcon set={iconSet} step={s.id} size={16} color={s.color} className="nc-cycle-icon" />
              <span className="nc-cycle-label">{s.label}</span>
            </button>
            {idx < CYCLE_STEPS.length - 1 && <span className="nc-cycle-arrow">→</span>}
          </React.Fragment>
        ))}
      </div>
    );
  }

  // --- Barre du menu : onglets + jeu d'icônes + réduction/masquage ---
  function renderMenuBar() {
    return (
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
        {/* Charte d'icônes (#410) : les jeux proposés se comparent en
            direct, dans le menu ET le graphique ; docs/charte-icones-hub.md */}
        <label className="nc-icon-set" title={ICON_SETS[iconSet]?.description}>
          Icônes
          <select value={iconSet} onChange={(e) => chooseIconSet(e.target.value)}>
            {ICON_SET_IDS.map((id) => (
              <option key={id} value={id}>{ICON_SETS[id].label}</option>
            ))}
          </select>
        </label>
        {/* Réduction / masquage du menu (#411). La barre classique est
            déjà compacte : le bouton de réduction n'a de sens que pour le
            schéma. Le masquage laisse une languette (renderHiddenTab). */}
        <span className="nc-menu-controls">
          {viewMode === "graphique" && (
            <button
              type="button"
              className="nc-graph-btn"
              onClick={() => applyMenuAction("toggle")}
              title={menuState === "expanded" ? "Réduire le schéma" : "Agrandir le schéma"}
            >
              {menuState === "expanded" ? "▾" : "▴"}
            </button>
          )}
          <button
            type="button"
            className="nc-graph-btn"
            onClick={() => applyMenuAction("hide")}
            title={viewMode === "graphique" ? "Masquer le schéma (une languette reste pour le rouvrir)" : "Masquer le menu (une languette reste pour le rouvrir)"}
          >
            ✕
          </button>
        </span>
      </div>
    );
  }

  // --- Languette : seule trace du menu quand il est masqué ---
  function renderHiddenTab() {
    return (
      <button type="button" className="nc-menu-tab" onClick={() => applyMenuAction("show")}>
        <span className="nc-menu-tab-arrow">▸</span>
        {hiddenMenuLabel(viewMode)}
        <span className="nc-menu-tab-step">
          · étape : <StepIcon set={iconSet} step={step} size={14} color={currentStep?.color} /> {currentStep?.label}
        </span>
      </button>
    );
  }

  return (
    <div className="hub-settings hub-settings-wide">
      <div className="hub-settings-topbar">
        <button className="secondary" onClick={onBack}>◀ Retour</button>
        <h1>🔄 Cycle agile réseau</h1>
      </div>

      {error && <p className="hub-error">{error}</p>}

      {/* Zone haute : le MENU -- barre classique ou schéma graphique,
          c'est la seule différence entre les deux onglets (#411). */}
      {menuState === "hidden" ? (
        renderHiddenTab()
      ) : (
        <div className={`nc-menu nc-menu-${viewMode} ${menuState}`}>
          {renderMenuBar()}
          {viewMode === "graphique" ? renderGraphique() : renderClassicNav()}
        </div>
      )}

      {/* Zone basse : le DÉTAIL de l'étape courante, toujours présent. */}
      <div className="nc-detail" ref={detailRef}>
        <div className="hub-card hub-settings-section nc-step-content">
          <h2 style={{ marginTop: 0, color: currentStep?.color }}>
            <StepIcon set={iconSet} step={step} size={20} color={currentStep?.color} /> {currentStep?.label}
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
            <button className="secondary" onClick={() => selectStep(CYCLE_STEPS[stepIndex - 1].id)}>
              ← {CYCLE_STEPS[stepIndex - 1].label}
            </button>
          )}
          {stepIndex < CYCLE_STEPS.length - 1 && (
            <button className="secondary" onClick={() => selectStep(CYCLE_STEPS[stepIndex + 1].id)} style={{ marginLeft: "auto" }}>
              {CYCLE_STEPS[stepIndex + 1].label} →
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
