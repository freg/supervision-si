import { normalizeBase, caFingerprintOf, installLines, oldHostLines, pushHistory, loadHistory, saveHistory } from "./agentInstallLib.js";
import IpPing from "./IpPing.jsx";
import React, { Fragment, useCallback, useEffect, useMemo, useState } from "react";
import { viewParams, clearViewParams, hubLink } from "./hubLinks.js";
import {
  fetchSiAgentStatus, fetchFleet, fetchRelayedHosts, fetchFleetRisks, fetchAgent, createAgent, updateAgent, deleteAgent,
  rotateAgentSecret, fetchInstall, installCmdUrl, agentAccueil, fetchPlugins, fetchPlugin, savePlugin, deletePlugin, assignPlugin,
  unassignPlugin, sendCommand, fetchCommands, blockFleet, unblockFleet, blockAgent, unblockAgent, setPluginBlocked,
  fetchEvents, fetchEventsSummary, testNotifications, fetchUpdates, saveUpdates, applyUpdates, fetchEventsMuted,
} from "./siAgentClient.js";
import {
  COMMAND_TYPES, CONTACT_LABELS, riskLabel, severityTone, stateTone, contactTone, gauge, formatBytes,
  formatUptime, formatAge, ageSeconds, sortFleet, riskSummaryText, diskRows, portRows, mergePlugins, storageSummary,
  validatePluginForm, defaultEntry, eventKindLabel, filterEvents, summarizeEvents, isSecurityEvent, EVENT_SEVERITIES, publishedPageUrl,
  groupFleet, agentSeverity, proxmoxRole } from "./siAgent.js";
import { orderItems } from "./listOrder.js";  // #742
import { useListOrder, OrderSwitch } from "./ListOrder.jsx";  // #742
import RotationsTab from "./RotationsTab.jsx";  // #743
import DiffusionsSection from "./DiffusionsSection.jsx";  // #822
import BancSection from "./BancSection.jsx";  // #825
// #525 : section « Wi-Fi vu du poste » (sonde wifi-probe, famille explorer).
import WifiProbeSection from "./WifiProbeSection.jsx";
import AlertFiltersTab from "./AlertFiltersTab.jsx";  // #607
import PathProbeSection from "./PathProbeSection.jsx";
import { etatMemorise, memoriserEtat } from "./navContext.js";   // #874
import HostControlSection from "./HostControlSection.jsx";  // #613
import DeployTab from "./DeployTab.jsx";  // #616
import WebAuditTab, { WebAuditSection } from "./WebAuditSection.jsx";  // #617
import NetworkObservabilityTab from "./NetworkObservabilityTab.jsx";  // #643
import WebTraceSection from "./WebTraceSection.jsx";  // #618
import FrontAccessSection from "./FrontAccessSection.jsx";  // #622
import MailServerSection from "./MailServerSection.jsx";  // #692
import OllamaSection from "./OllamaSection.jsx";  // #746
import { useTableColumns, TableColumnsHead, ColumnsMenu, AutoColumns } from "./TableColumns.jsx";  // #698
import { ONGLETS, SANS_MESURE, ongletDe, sectionsDe, collecte, versionEtat } from "./agentFiche.js";   // #922
import BoutonDetail from "./FenetreTexte.jsx";   // #923 : info-bulle importante -> mini bouton + fenêtre copiable
import OsActions from "./OsActions.jsx";   // #880
import AnalyseDistance from "./AnalyseDistance.jsx";   // #929 : exécution des commandes à distance dans la fiche agent
import Sauvegarde from "./Sauvegarde.jsx";   // #936 : section Sauvegardes dans la fiche agent

// Tuile « Agents hôtes » (livraison #421, backlog 63) -- flotte des agents
// si-agent (surveillance de l'hôte : CPU, mémoire, disques, services,
// ports, journal, comptes), risques internes, catalogue de sondes
// (plugins shell/python) affectées et poussées signées, commandes
// acquittées. #422 : blocage général / individuel, journal d'événements
// (agents + central), état de sécurité (CA, TLS, notifications). Toute la
// logique non-React est dans siAgent.js (testée à part) ; le central est
// si-agent-api (si-agent/README.md).

const REFRESH_MS = 30000;

const EMPTY_AGENT_FORM = { agent_id: "", site: "", label: "", host_interval_seconds: "", notes: "" };
const EMPTY_PLUGIN_FORM = { id: "", version: "1", runner: "shell", entry: "", interval_seconds: "3600", timeout_seconds: "60", args: "", description: "", body: "", privileged: false, max_memory_mb: "" };

function Tone({ tone, children, title }) {
  return <span className={`np-tone ${tone || "neutral"}`} title={title}>{children}</span>;
}

function when(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString("fr-FR");
}

function Gauge({ percent, label }) {
  const g = gauge(percent);
  return (
    <div className="sa-gauge" title={label}>
      <div className="sa-gauge-bar"><div className={`sa-gauge-fill ${g.tone}`} style={{ width: `${g.width}%` }} /></div>
      <span className={`sa-gauge-text np-tone ${g.tone}`}>{g.percent == null ? "—" : `${g.percent} %`}</span>
    </div>
  );
}

// #698 : colonnes du tableau des agents -- largeur à la souris, masquables, mémorisées par compte
// #868 : last_ip = X-Forwarded-For complet (« agent, relais, frontal ») -> la première adresse est celle de l'agent
const contactIp = (v) => (v || "").split(",")[0].trim() || null;

const AGENT_COLUMNS = [
  { id: "agent", label: "Agent", fixed: true }, { id: "site", label: "Site" }, { id: "host", label: "Hôte" }, { id: "version", label: "Version", title: "version de l'agent (orange : le central sert une version plus récente)" }, { id: "ip", label: "IP", title: "Adresse par laquelle l'agent contacte le hub (peut être celle d'un routeur / NAT) -- « ping » teste depuis le hub (#868)" }, { id: "contact", label: "Collecte", title: "vert : relevés à jour · jaune : pas de relevé récent · orange : collecte partielle ou sondes bloquées · rouge : hors ligne, jamais vu ou désactivé (détail au survol)" },
  { id: "cpu", label: "CPU" }, { id: "mem", label: "Mémoire" }, { id: "disk", label: "Disque (max)" },
  { id: "footprint", label: "Impact agent", title: "Empreinte de l'agent lui-même : % d'un cœur (moyenne de la fenêtre) · mémoire résidente" },
  { id: "risks", label: "Risques" }, { id: "plugins", label: "Sondes" },
  { id: "actions", label: "", fixed: true, className: "ups-actions-head", noResize: true },
];

// #899 : installation depuis l'accueil du hub, sans connexion -- ouverte pour CET agent, durée bornée, refermée au premier contact
function AccueilOuverture({ base, agentId }) {
  const [e, setE] = useState(null);
  useEffect(() => { agentAccueil(base, agentId).then(setE); }, [base, agentId]);
  const regler = async (h) => setE(await agentAccueil(base, agentId, h));
  if (!e || e.error) return null;
  return (
    <div className="hub-settings-row" style={{ margin: "8px 0 0", alignItems: "center" }}>
      <label>Installation depuis l'accueil (sans connexion)</label>
      {e.ouvert ? <Tone tone="warn">ouverte jusqu'au {new Date(e.jusqua).toLocaleString("fr-FR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" })}</Tone>
        : <span className="muted" style={{ fontSize: 12 }}>fermée{e.motif && e.motif !== "inconnu ou non ouvert" ? ` (${e.motif})` : ""}</span>}
      {e.ouvert ? <button className="secondary" onClick={() => regler(0)}>Fermer</button>
        : <><button className="secondary" onClick={() => regler(2)}>Ouvrir 2 h</button><button className="secondary" onClick={() => regler(24)}>Ouvrir 24 h</button></>}
      <span className="muted" style={{ fontSize: 12 }}>sur le poste : page d'accueil du hub › « Nouvel agent » › nom <code>{agentId}</code> ; se referme dès que l'agent contacte le hub</span>
    </div>
  );
}

const WINDOWS_DIAG = [
  "Get-ScheduledTask si-agent | Get-ScheduledTaskInfo | Format-List TaskName,LastRunTime,LastTaskResult,NextRunTime",
  "Get-Process python* -ErrorAction SilentlyContinue | Format-Table Id,StartTime",
  "if (Test-Path C:\\ProgramData\\si-agent\\agent.json) { (Get-Content C:\\ProgramData\\si-agent\\agent.json | ConvertFrom-Json).agent_id } else { 'agent.json ABSENT : enrolement non fait' }",
  "Get-Content C:\\ProgramData\\si-agent\\agent.log -Tail 30 -ErrorAction SilentlyContinue",
].join("\n");

export default function SiAgentView({ onBack, siAgentApiBase, actor }) {
  const agentCols = useTableColumns("si-agent.agents", AGENT_COLUMNS);
  const [status, setStatus] = useState(null);
  const [fleet, setFleet] = useState([]);
  const [relayed, setRelayed] = useState([]);   // #876 : hôtes relevés par un agent relais
  const [risks, setRisks] = useState([]);
  const [catalogue, setCatalogue] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState(null);
  const [now, setNow] = useState(Date.now());
  const [tab, setTab] = useState(() => { const t = viewParams().tab || etatMemorise("SiAgentView", "tab"); return ["events", "risks", "catalogue", "updates", "banc", "deploy", "webaudit", "netobs", "rotations", "filters"].includes(t) ? t : "fleet"; });   // #768 ; #874
  useEffect(() => { memoriserEtat("SiAgentView", "tab", tab); }, [tab]);   // #874
  const [busy, setBusy] = useState(false);

  const [showEnroll, setShowEnroll] = useState(false);
  const [agentForm, setAgentForm] = useState(EMPTY_AGENT_FORM);
  const [enrolled, setEnrolled] = useState(null);

  // #570 : lien profond ?view=si-agent&agent=<id>&section=plugins (depuis « activer la sonde… » ailleurs dans le hub)
  const initialParams = viewParams();
  const [selectedId, setSelectedId] = useState(initialParams.agent || null);
  const [detail, setDetail] = useState(null);
  const [install, setInstall] = useState(null);
  const [hubHistory, setHubHistory] = useState(() => loadHistory());   // #680 : adresses du hub déjà choisies (ce navigateur)
  const [hubAddr, setHubAddr] = useState(() => loadHistory()[0] || "");
  const [cmdType, setCmdType] = useState("collect_now");
  const [cmdPlugin, setCmdPlugin] = useState("");
  const [assignId, setAssignId] = useState("");
  const [settings, setSettings] = useState(null);
  const [sauvegardeMode, setSauvegardeMode] = useState("donnees");   // #936 : données | image | usb (boutons de l'en-tête)
  const [onglet, setOnglet] = useState(() => {   // #922 : fiche en onglets -- une section à l'écran, toutes à un clic
    const o = ongletDe(initialParams.section) || "resume";
    clearViewParams();
    return o;
  });
  const section = useMemo(() => sectionsDe(onglet), [onglet]);

  const [pluginForm, setPluginForm] = useState(EMPTY_PLUGIN_FORM);
  const [showPluginForm, setShowPluginForm] = useState(false);

  // #422 : journal d'événements
  const [events, setEvents] = useState([]);
  const [summary, setSummary] = useState(null);
  const [evFilter, setEvFilter] = useState(() => ({ minSeverity: "info", agent: initialParams.tab === "events" ? initialParams.agent || "" : "", securityOnly: false, text: initialParams.q || "" }));   // #768

  const load = useCallback(async () => {
    const [st, fl, rk, cat, ev, sm] = await Promise.all([
      fetchSiAgentStatus(siAgentApiBase), fetchFleet(siAgentApiBase), fetchFleetRisks(siAgentApiBase), fetchPlugins(siAgentApiBase),
      fetchEvents(siAgentApiBase, { limit: 300 }), fetchEventsSummary(siAgentApiBase, 24),
    ]);
    fetchRelayedHosts(siAgentApiBase).then(setRelayed);   // #876 : sans retarder la Flotte
    setStatus(st);
    setFleet(fl);
    setRisks(rk);
    setCatalogue(cat);
    setEvents(ev);
    setSummary(sm?.error ? null : sm);
    setError(st?.error || null);
    setLoading(false);
    setNow(Date.now());
  }, [siAgentApiBase]);

  const loadDetail = useCallback(async (agentId) => {
    if (!agentId) return;
    const d = await fetchAgent(siAgentApiBase, agentId);
    if (d?.error) { setError(d.error); return; }
    setDetail(d);
    const pub = d.publish || {};
    setSettings({ host_interval_seconds: d.host_interval_seconds, label: d.label || "", site: d.site || "", notes: d.notes || "",
      thresholds: JSON.stringify(d.risk_thresholds || {}, null, 0),
      // #563 : publication d'une page d'état sur le LAN du site (#547), réglable ici et plus seulement par l'API
      pub_enabled: !!pub.enabled, pub_port: pub.port || 8081, pub_title: pub.title || "État du réseau", pub_site_id: pub.site_id || "", pub_hours: pub.hours || 24, pub_hub_url: pub.hub_url || "",
      filter_enabled: !!d.filter_enabled, filter_group: d.filter_group || "",  // #607
      remote_shell: d.remote_shell || "off" });  // #919
  }, [siAgentApiBase]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    const id = setInterval(() => { load(); if (selectedId) loadDetail(selectedId); }, REFRESH_MS);
    return () => clearInterval(id);
  }, [load, loadDetail, selectedId]);
  useEffect(() => { setDetail(null); setInstall(null); if (selectedId) loadDetail(selectedId); }, [selectedId, loadDetail]);

  // --- Flotte ---
  async function handleEnroll(e) {
    e.preventDefault();
    setBusy(true);
    const body = { agent_id: agentForm.agent_id.trim(), site: agentForm.site.trim(), label: agentForm.label || null, notes: agentForm.notes || null };
    if (agentForm.host_interval_seconds) body.host_interval_seconds = Number(agentForm.host_interval_seconds);
    const r = await createAgent(siAgentApiBase, body);
    setBusy(false);
    if (r?.error) { setError(r.error); return; }
    setEnrolled(r);
    setAgentForm(EMPTY_AGENT_FORM);
    setShowEnroll(false);
    await load();
  }

  async function handleToggleActive(a) {
    const r = await updateAgent(siAgentApiBase, a.agent_id, { active: !a.active });
    if (r?.error) { setError(r.error); return; }
    await load();
    if (selectedId === a.agent_id) loadDetail(a.agent_id);
  }

  async function handleDelete(a) {
    if (!window.confirm(`Supprimer l'agent « ${a.agent_id} » et tout son historique ?`)) return;
    const r = await deleteAgent(siAgentApiBase, a.agent_id, true);
    if (r?.error) { setError(r.error); return; }
    if (selectedId === a.agent_id) setSelectedId(null);
    await load();
  }

  // --- Blocage (#422) ---
  async function handleBlockFleet() {
    const reason = window.prompt("BLOCAGE GÉNÉRAL : plus aucune sonde ne s'exécute ni ne s'installe sur AUCUN agent (la surveillance de l'hôte continue). Motif :", "incident de sécurité");
    if (reason === null) return;
    const r = await blockFleet(siAgentApiBase, reason);
    if (r?.error) { setError(r.error); return; }
    setNotice("Blocage général demandé : configuration et commande immédiate envoyées à tous les agents.");
    await load();
  }

  async function handleUnblockFleet() {
    if (!window.confirm("Lever le blocage général ? Les agents bloqués individuellement le restent.")) return;
    const r = await unblockFleet(siAgentApiBase);
    if (r?.error) { setError(r.error); return; }
    await load();
  }

  async function handleBlockAgent(a) {
    if (a.blocked) {
      const r = await unblockAgent(siAgentApiBase, a.agent_id);
      if (r?.error) { setError(r.error); return; }
    } else {
      const reason = window.prompt(`Bloquer toutes les sondes de « ${a.agent_id} » ? Motif :`, "analyse en cours");
      if (reason === null) return;
      const r = await blockAgent(siAgentApiBase, a.agent_id, reason);
      if (r?.error) { setError(r.error); return; }
    }
    await load();
    if (selectedId === a.agent_id) loadDetail(a.agent_id);
  }

  async function handlePluginBlock(p) {
    let reason = null;
    if (!p.blocked_central) {
      reason = window.prompt(`Bloquer la sonde « ${p.id} » sur cet agent ? Motif :`, "sortie suspecte");
      if (reason === null) return;
    }
    const r = await setPluginBlocked(siAgentApiBase, selectedId, p.id, !p.blocked_central, reason);
    if (r?.error) { setError(r.error); return; }
    await load();
    loadDetail(selectedId);
  }

  async function handleTestNotifications() {
    const r = await testNotifications(siAgentApiBase);
    if (r?.error) { setError(r.error); return; }
    const ok = Object.entries(r).filter(([k]) => k !== "at").map(([k, v]) => `${k} : ${v ? "envoyé" : "échec"}`).join(", ");
    setNotice(`Test de notification : ${ok || "aucun canal configuré"}.`);
    await load();
  }

  async function handleInstall(agentId) {
    const r = await fetchInstall(siAgentApiBase, agentId);
    if (r?.error) { setError(r.error); return; }
    setInstall(r);
  }

  async function handleRotate(agentId) {
    if (!window.confirm("Générer un nouveau secret ? L'agent installé cessera d'être accepté tant qu'il n'est pas réinstallé avec le nouveau.")) return;
    const r = await rotateAgentSecret(siAgentApiBase, agentId);
    if (r?.error) { setError(r.error); return; }
    setInstall({ agent_id: r.agent_id, secret: r.secret, install_command: r.install_command, site: r.site, package: r.package, download_command: r.download_command });
    setNotice("Nouveau secret généré -- à reporter sur l'hôte.");
  }

  async function handleSaveSettings(e) {
    e.preventDefault();
    let thresholds = {};
    try { thresholds = settings.thresholds ? JSON.parse(settings.thresholds) : {}; } catch { setError("Seuils : JSON invalide"); return; }
    const r = await updateAgent(siAgentApiBase, selectedId, {
      host_interval_seconds: Number(settings.host_interval_seconds) || 60, label: settings.label, site: settings.site, notes: settings.notes, risk_thresholds: thresholds,
      publish: { enabled: !!settings.pub_enabled, port: Number(settings.pub_port) || 8081, title: settings.pub_title || "État du réseau", site_id: settings.pub_site_id || "", hours: Number(settings.pub_hours) || 24, interval_seconds: 60, hub_url: settings.pub_hub_url || "" },
      filter_enabled: !!settings.filter_enabled, filter_group: settings.filter_group || "",  // #607
      remote_shell: settings.remote_shell || "off", actor,  // #919 : changement de mode journalisé avec son auteur
    });
    if (r?.error) { setError(r.error); return; }
    setNotice("Réglages enregistrés -- appliqués par l'agent à sa prochaine lecture de configuration (5 min au plus).");
    await load();
    loadDetail(selectedId);
  }

  // #929 : autorisation des commandes à distance, réglée directement dans l'onglet « Commandes à distance »
  // (désactivées / lecture seule / intervention), et plus noyée dans « Réglages ».
  async function handleRemoteShell(v) {
    if (v === "intervention" && !window.confirm("Autoriser les commandes d'INTERVENTION (modification du poste) depuis le hub ? Chaque commande est confirmée et journalisée.")) return;
    const r = await updateAgent(siAgentApiBase, selectedId, { remote_shell: v, actor });
    if (r?.error) { setError(r.error); return; }
    setNotice(`Commandes à distance : ${{ off: "désactivées", lecture: "lecture seule", intervention: "intervention autorisée" }[v]} — appliqué par l'agent à sa prochaine lecture de configuration (5 min au plus).`);
    await loadDetail(selectedId);
  }

  async function handleAssign() {
    if (!assignId) return;
    const r = await assignPlugin(siAgentApiBase, selectedId, assignId, true);
    if (r?.error) { setError(r.error); return; }
    setAssignId("");
    await load();
    loadDetail(selectedId);
  }

  async function handleAssignedToggle(p) {
    const r = await assignPlugin(siAgentApiBase, selectedId, p.id, !p.enabled_central);
    if (r?.error) { setError(r.error); return; }
    loadDetail(selectedId);
  }

  async function handleUnassign(p) {
    const r = await unassignPlugin(siAgentApiBase, selectedId, p.id);
    if (r?.error) { setError(r.error); return; }
    await load();
    loadDetail(selectedId);
  }

  async function handleCommand() {
    const def = COMMAND_TYPES.find((c) => c.type === cmdType);
    if (def?.needsPlugin && !cmdPlugin) { setError("Choisir une sonde pour cette commande."); return; }
    const r = await sendCommand(siAgentApiBase, selectedId, cmdType, def?.needsPlugin ? { id: cmdPlugin } : {});
    if (r?.error) { setError(r.error); return; }
    setNotice(`Commande ${r.id} en attente -- l'agent la relève à sa prochaine interrogation (1 min au plus).`);
    loadDetail(selectedId);
  }

  async function refreshCommands() {
    const cmds = await fetchCommands(siAgentApiBase, selectedId);
    setDetail((d) => (d ? { ...d, commands: cmds } : d));
  }

  // --- Catalogue ---
  function openPluginCreate() {
    setPluginForm(EMPTY_PLUGIN_FORM);
    setShowPluginForm(true);
  }

  async function openPluginEdit(p) {
    const full = await fetchPlugin(siAgentApiBase, p.id);
    if (full?.error) { setError(full.error); return; }
    setPluginForm({ id: full.id, version: String(full.version || "1"), runner: full.runner, entry: full.entry, interval_seconds: String(full.interval_seconds || 3600),
      timeout_seconds: String(full.timeout_seconds || 60), args: (full.args || []).join(" "), description: full.description || "", body: full.body || "",
      privileged: !!full.privileged, max_memory_mb: full.max_memory_mb ? String(full.max_memory_mb) : "" });
    setShowPluginForm(true);
    setTab("catalogue");
  }

  async function handleSavePlugin(e) {
    e.preventDefault();
    const why = validatePluginForm(pluginForm);
    if (why) { setError(why); return; }
    setBusy(true);
    const r = await savePlugin(siAgentApiBase, {
      manifest: { id: pluginForm.id.trim(), version: pluginForm.version.trim() || "1", runner: pluginForm.runner, entry: pluginForm.entry.trim(),
        interval_seconds: Number(pluginForm.interval_seconds) || 3600, timeout_seconds: Number(pluginForm.timeout_seconds) || 60,
        args: pluginForm.args.trim() ? pluginForm.args.trim().split(/\s+/) : [], description: pluginForm.description,
        privileged: !!pluginForm.privileged, max_memory_mb: pluginForm.max_memory_mb ? Number(pluginForm.max_memory_mb) : null },
      body: pluginForm.body,
    });
    setBusy(false);
    if (r?.error) { setError(r.error); return; }
    setShowPluginForm(false);
    setNotice(`Sonde « ${r.id} » v${r.version} enregistrée -- les agents affectés la reçoivent signée à leur prochaine configuration.`);
    await load();
  }

  async function handleDeletePlugin(p) {
    if (!window.confirm(`Retirer « ${p.id} » du catalogue ? Les ${p.assigned_agents} agent(s) affecté(s) la désinstalleront.`)) return;
    const r = await deletePlugin(siAgentApiBase, p.id);
    if (r?.error) { setError(r.error); return; }
    await load();
    if (selectedId) loadDetail(selectedId);
  }

  // --- Dérivés ---
  // #742 : ordre choisi (A → Z par défaut, récent, gravité) et regroupement par catégorie (rôle / OS)
  const [fleetOrder, setFleetOrder] = useListOrder("si-agent.fleet", "alpha");
  const [eventsOrder, setEventsOrder] = useListOrder("si-agent.events", "recent");
  const [byCategory, setByCategory] = useState(() => { try { return localStorage.getItem("hub.si-agent.byCategory") !== "0"; } catch (e) { return true; } });
  const [foldedCats, setFoldedCats] = useState({});
  const orderFleet = useCallback((xs) => orderItems(xs, fleetOrder, { name: (a) => a.agent_id, tie: (a) => a.hostname, date: (a) => a.last_seen_at, severity: agentSeverity }), [fleetOrder]);
  const sorted = useMemo(() => orderFleet(fleet), [fleet, orderFleet]);
  const fleetGroups = useMemo(() => groupFleet(fleet, orderFleet), [fleet, orderFleet]);
  const fleetRows = byCategory ? fleetGroups.flatMap((g) => [{ __group: g }, ...(foldedCats[g.id] ? [] : g.agents)]) : sorted;
  const host = detail?.latest?.host?.data || null;
  const hostRisks = detail?.latest?.risks?.data || null;
  const inventory = detail?.latest?.inventory?.data || null;
  // #428 : découverte passive et revue de l'hôte
  const netview = detail?.latest?.netview?.data || null;
  const hardware = inventory?.hardware || null;
  const activity = host?.activity || null;
  const plugins = useMemo(() => mergePlugins(detail?.plugins, inventory?.plugins), [detail, inventory]);
  const assignable = catalogue.filter((p) => !(detail?.plugins || []).some((ap) => ap.id === p.id));
  const disks = useMemo(() => diskRows(host), [host]);
  const storage = useMemo(() => storageSummary(host), [host]);
  const ports = useMemo(() => portRows(host), [host]);

  return (
    <div className="hub-settings hub-settings-wide">
      <div className="hub-settings-topbar">
        <button className="secondary" onClick={onBack}>◀ Retour</button>
        <h1>🖥 Agents hôtes</h1>
      </div>

      {error && <p className="hub-error ups-notice">{error} <button className="secondary" onClick={() => setError(null)}>✕</button></p>}
      {notice && <p className="muted ups-notice">{notice} <button className="secondary" onClick={() => setNotice(null)}>✕</button></p>}

      <div className="hub-card hub-settings-section ups-status-card">
        {status && !status.error ? (
          <p style={{ margin: 0 }}>
            {status.agents} agent(s) : <Tone tone="good">{status.contact.online} en ligne</Tone>
            {status.contact.offline > 0 && <> · <Tone tone="bad">{status.contact.offline} hors ligne</Tone></>}
            {status.contact.never > 0 && <> · <Tone tone="neutral">{status.contact.never} jamais vu(s)</Tone></>}
            {" · "}risques : <Tone tone={status.risks.critical ? "bad" : "neutral"}>{status.risks.critical} critique(s)</Tone>, <Tone tone={status.risks.warning ? "warn" : "neutral"}>{status.risks.warning} avertissement(s)</Tone>
            {" · "}{status.plugins} sonde(s) au catalogue · hors ligne après {formatAge(status.offline_after_seconds)} sans contact · {status.retention_days ? `${status.retention_days} jours d'archive` : "archive illimitée"}
            {!status.public_url && <><br /><Tone tone="warn">⚠ SI_AGENT_PUBLIC_URL non défini : la commande d'installation affiche « https://&lt;VM&gt;:6443/api/si-agent » à remplacer.</Tone></>}
            <br />
            <span className="muted">Sécurité :</span>{" "}
            {status.ca?.available ? <Tone tone="good" title={status.ca.sha256}>CA interne servie (empreinte {status.ca.sha256.slice(0, 12)}…)</Tone> : <Tone tone="warn">CA interne non montée (SI_AGENT_CA_FILE) : amorçage TLS par empreinte indisponible</Tone>}
            {" · "}réponses signées aux agents · sondes confinées (utilisateur non privilégié, limites, délai)
            {status.insecure_agents?.length > 0 && <> · <Tone tone="bad">⚠ TLS non vérifié sur : {status.insecure_agents.join(", ")}</Tone></>}
            {status.agents_blocked > 0 && <> · <Tone tone="warn">{status.agents_blocked} agent(s) bloqué(s)</Tone></>}
            {" · "}notifications : {status.notifications?.any
              ? <Tone tone="good">{Object.entries(status.notifications.channels).filter(([, v]) => v).map(([k]) => k).join(", ")} (≥ {status.notifications.min_severity})</Tone>
              : <Tone tone="warn">aucun canal (SECRETS_ALERT_* / SI_AGENT_NOTIFY_WEBHOOK_URL)</Tone>}
            {" "}<button className="secondary" style={{ padding: "0 6px", fontSize: 11 }} onClick={handleTestNotifications}>tester</button>
            {" · "}traces {status.log_level}
          </p>
        ) : (
          <p className="muted" style={{ margin: 0 }}>{loading ? "Chargement…" : "si-agent-api injoignable."}</p>
        )}
      </div>

      {status?.fleet_blocked && (
        <div className="sa-fleet-blocked">
          <strong>⛔ BLOCAGE GÉNÉRAL EN COURS</strong> — {status.fleet_block_reason || "sans motif"} (depuis {when(status.fleet_blocked_at)}). Aucune sonde ne s'exécute ni ne s'installe sur aucun agent ; la surveillance des hôtes continue.
          <button className="secondary" onClick={handleUnblockFleet}>Lever le blocage général</button>
        </div>
      )}

      <div className="ups-toolbar">
        <button className={`secondary na-section-toggle${tab === "fleet" ? " active" : ""}`} onClick={() => setTab("fleet")}>Flotte ({fleet.length})</button>
        <button className={`secondary na-section-toggle${tab === "risks" ? " active" : ""}`} onClick={() => setTab("risks")}>Risques ({risks.length})</button>
        <button className={`secondary na-section-toggle${tab === "catalogue" ? " active" : ""}`} onClick={() => setTab("catalogue")}>Catalogue de sondes ({catalogue.length})</button>
        <button className={`secondary na-section-toggle${tab === "updates" ? " active" : ""}`} onClick={() => setTab("updates")}>Mises à jour</button>
        <button className={`secondary na-section-toggle${tab === "deploy" ? " active" : ""}`} onClick={() => setTab("deploy")}>Déploiement</button>
        <button className={`secondary na-section-toggle${tab === "banc" ? " active" : ""}`} onClick={() => setTab("banc")}>Banc d'installation</button>
        <button className={`secondary na-section-toggle${tab === "webaudit" ? " active" : ""}`} onClick={() => setTab("webaudit")}>Audit web</button>
        <button className={`secondary na-section-toggle${tab === "netobs" ? " active" : ""}`} onClick={() => setTab("netobs")}>Observabilité réseau</button>
        <button className={`secondary na-section-toggle${tab === "rotations" ? " active" : ""}`} onClick={() => setTab("rotations")} title="Mesures lourdes réparties entre agents, à tour de rôle avec suppléance (#743)">Tournées</button>
        <button className={`secondary na-section-toggle${tab === "filters" ? " active" : ""}`} onClick={() => setTab("filters")}>Filtres d'alertes{fleet.some((a) => a.filter_enabled) ? ` (${fleet.filter((a) => a.filter_enabled).length})` : ""}</button>
        <button className={`secondary na-section-toggle${tab === "events" ? " active" : ""}`} onClick={() => setTab("events")}>
          Événements {summary ? <>({summary.counts.critical + summary.counts.warning} sur 24 h)</> : ""}
        </button>
        <span style={{ flex: 1 }} />
        {!status?.fleet_blocked && <button className="sa-danger" onClick={handleBlockFleet} title="Arrêt d'urgence de toutes les sondes, sur tous les agents">⛔ Blocage général</button>}
        <button className="secondary" onClick={load} disabled={busy}>⟳ Rafraîchir</button>
      </div>

      {tab === "fleet" && (
        <>
          <div className="ups-toolbar" style={{ marginTop: 0 }}>
            <h2 style={{ margin: 0 }}>Agents</h2>
            <button className="secondary" onClick={() => setShowEnroll((v) => !v)}>{showEnroll ? "✕ Fermer" : "+ Enrôler un agent"}</button>
          </div>

          {showEnroll && (
            <form className="hub-card hub-settings-section ups-form" onSubmit={handleEnroll}>
              <h3 style={{ marginTop: 0 }}>Nouvel agent</h3>
              <div className="ups-form-grid">
                <label>Identifiant <input value={agentForm.agent_id} onChange={(e) => setAgentForm({ ...agentForm, agent_id: e.target.value })} required placeholder="srv-fichiers-01" pattern="[A-Za-z0-9][A-Za-z0-9._\-]*" /></label>
                <label>Site <input value={agentForm.site} onChange={(e) => setAgentForm({ ...agentForm, site: e.target.value })} required placeholder="siege" /></label>
                <label>Libellé <input value={agentForm.label} onChange={(e) => setAgentForm({ ...agentForm, label: e.target.value })} placeholder="Serveur de fichiers" /></label>
                <label>Intervalle hôte (s) <input type="number" min="10" value={agentForm.host_interval_seconds} onChange={(e) => setAgentForm({ ...agentForm, host_interval_seconds: e.target.value })} placeholder="60 (défaut)" /></label>
                <label className="ups-form-wide">Notes <input value={agentForm.notes} onChange={(e) => setAgentForm({ ...agentForm, notes: e.target.value })} /></label>
              </div>
              <p className="muted" style={{ margin: "8px 0" }}>Le secret est généré ici et affiché UNE fois avec la commande d'installation à lancer sur l'hôte (<code>si-agent/agent/install.sh</code>).</p>
              <button type="submit" className="primary" disabled={busy}>Enrôler</button>
            </form>
          )}

          {enrolled && (
            <div className="hub-card hub-settings-section np-secret-box">
              <h3 style={{ marginTop: 0 }}>Agent « {enrolled.agent_id} » enrôlé -- commande d'installation (affichée une seule fois)</h3>
              <pre className="np-secret">{enrolled.install_command}</pre>
              <p className="muted" style={{ margin: "6px 0 0" }}>À lancer dans <code>si-agent/agent/</code> sur l'hôte (Python 3, systemd). Retrouvable plus tard par « Installation » sur la ligne de l'agent. <button className="secondary" onClick={() => setEnrolled(null)}>Masquer</button></p>
            </div>
          )}

          {!selectedId && !loading && sorted.length > 0 && (   /* #922 : fiche ouverte = elle remplace le tableau */
            <div className="ups-toolbar" style={{ margin: "4px 0" }}>
              <OrderSwitch value={fleetOrder} onChange={setFleetOrder} />
              <label title="Proxmox (PVE / PBS), sondes, VM, Windows, Linux -- étiquette #pve #pbs #sonde #vm #windows #linux dans le libellé pour forcer">
                <input type="checkbox" checked={byCategory} onChange={(e) => { setByCategory(e.target.checked); try { localStorage.setItem("hub.si-agent.byCategory", e.target.checked ? "1" : "0"); } catch (err) { /* non mémorisé */ } }} /> par catégorie
              </label>
              {byCategory && <span className="muted">{fleetGroups.map((g) => `${g.label} ${g.counts.total}`).join(" · ")}</span>}
            </div>
          )}
          {selectedId ? null : loading ? (
            <p className="muted">Chargement…</p>
          ) : sorted.length === 0 ? (
            <p className="muted">Aucun agent -- « + Enrôler un agent », puis lancer la commande d'installation sur l'hôte Linux.</p>
          ) : (
            <div className="hub-table-scroll">
              <table className="sa-fleet" style={agentCols.tableStyle}>
                <TableColumnsHead t={agentCols} render={(c) => (c.id === "actions" ? <ColumnsMenu t={agentCols} /> : undefined)} />
                <tbody>
                  {fleetRows.map((a) => {
                    if (a.__group) {
                      const g = a.__group, c = g.counts;
                      return (
                        <tr key={`cat-${g.id}`} className="sa-cat-row" onClick={() => setFoldedCats({ ...foldedCats, [g.id]: !foldedCats[g.id] })} style={{ cursor: "pointer" }}>
                          <td colSpan={agentCols.visible.length} style={{ fontWeight: 600, background: "var(--hub-surface-2, rgba(127,127,127,.12))" }}>
                            {foldedCats[g.id] ? "▸" : "▾"} {g.label} <span className="muted">({c.total})</span>
                            {c.critical > 0 && <> <Tone tone="bad">{c.critical} critique{c.critical > 1 ? "s" : ""}</Tone></>}
                            {c.offline > 0 && <> <Tone tone="warn">{c.offline} hors ligne</Tone></>}
                            {c.warning > 0 && <> <Tone tone="warn">{c.warning} avertissement{c.warning > 1 ? "s" : ""}</Tone></>}
                          </td>
                        </tr>
                      );
                    }
                    const age = ageSeconds(a.last_seen_at, now);
                    const fils = relayed.filter((h) => h.relay === a.agent_id);   // #876
                    return (
                      <Fragment key={a.agent_id}>
                      <tr className={`ups-row${selectedId === a.agent_id ? " active" : ""}${a.active ? "" : " inactive"}`} onClick={() => setSelectedId(selectedId === a.agent_id ? null : a.agent_id)}>
                        {agentCols.show("agent") && (
                        <td><strong>{a.agent_id}</strong>{byCategory && fleetGroups.some((g) => g.id === "proxmox" && g.agents.includes(a)) && <> <Tone tone="neutral">{proxmoxRole(a)}</Tone></>}{a.label && <div className="muted" style={{ fontSize: 11 }}>{a.label}</div>}
                          {publishedPageUrl(a) && <div style={{ fontSize: 11 }}><a href={publishedPageUrl(a)} target="_blank" rel="noopener noreferrer" onClick={(e) => e.stopPropagation()} title="Page publiée par l'agent sur le réseau de son site (#552)">page publiée ↗</a></div>}</td>
                        )}
                        {agentCols.show("site") && <td title={a.site}><span className="sa-site">{a.site}</span></td>}
                        {agentCols.show("host") && <td>{a.hostname ? <><code>{a.hostname}</code>{a.os && <div className="muted" style={{ fontSize: 11 }}>{a.os}</div>}</> : <span className="muted">—</span>}</td>}
                        {agentCols.show("version") && (() => { const v = versionEtat(a.agent_version, status?.package?.version); return <td><Tone tone={v.ton} title={v.titre}>{v.texte}</Tone></td>; })()}
                        {agentCols.show("ip") && <td onClick={(e) => e.stopPropagation()}><IpPing os={false} ip={contactIp(a.last_ip)} /><OsActions label={a.agent_id} ip={contactIp(a.last_ip)} agent={a.agent_id} /></td>}
                        {agentCols.show("contact") && (() => {   /* #922 : collecte = une pastille, le détail au survol */
                          const c = collecte({ ...a, blocked: a.blocked || status?.fleet_blocked }, age);
                          return <td title={c.lignes.join("\n")}><span className={`sa-pastille ${c.couleur}`} role="img" aria-label={c.lignes[0]} />
                            <BoutonDetail titre={`Collecte : ${a.agent_id}`} urgence={{ rouge: "critique", orange: "alerte", jaune: "alerte" }[c.couleur] || "info"} texte={c.lignes.join("\n")} /></td>;
                        })()}
                        {agentCols.show("cpu") && <td><Gauge percent={a.summary?.cpu_percent} label={`charge 5 min ${a.summary?.load5 ?? "—"}`} /></td>}
                        {agentCols.show("mem") && <td><Gauge percent={a.summary?.memory_percent} /></td>}
                        {agentCols.show("disk") && <td><Gauge percent={a.summary?.disk_max_percent} /></td>}
                        {agentCols.show("footprint") && <td style={{ whiteSpace: "nowrap" }}>{a.footprint ? <span title={`dernier point ${a.footprint.cpu_core_percent} % d'un cœur (${a.footprint.cpu_machine_percent} % machine) · max ${a.footprint.cpu_core_max} % · file ${a.footprint.queue_size ?? "?"}`}><Tone tone={a.footprint.cpu_core_avg > 25 ? "bad" : a.footprint.cpu_core_avg > 8 ? "warn" : "good"}>{a.footprint.cpu_core_avg} % cœur</Tone> · {formatBytes(a.footprint.rss_bytes)}{a.footprint.bench && <> · <Tone tone="warn">banc</Tone></>}</span> : <span className="muted">—</span>}</td>}
                        {agentCols.show("risks") && <td><Tone tone={stateTone(a.risks?.state)}>{riskSummaryText(a.risks)}</Tone>{a.summary?.partial?.length > 0 && <div className="muted" style={{ fontSize: 11 }} title={a.summary.partial.join(", ")}>collecte partielle</div>}</td>}
                        {agentCols.show("plugins") && <td className="muted">{a.plugins_assigned > 0 ? `${a.plugins_assigned} affectée${a.plugins_assigned > 1 ? "s" : ""}` : "—"}{a.pending_commands > 0 && <div style={{ fontSize: 11 }}>{a.pending_commands} cmd en attente</div>}</td>}
                        {agentCols.show("actions") && (
                        <td className="ups-actions" onClick={(e) => e.stopPropagation()}>
                          <button className="sa-micro" title="Installation : archive et commandes" onClick={() => { setSelectedId(a.agent_id); handleInstall(a.agent_id); }}>⤓</button>
                          <button className={`sa-micro${a.blocked ? "" : " danger"}`} title={a.blocked ? "Débloquer les sondes" : "Bloquer les sondes"} onClick={() => handleBlockAgent(a)}>{a.blocked ? "🔓" : "⛔"}</button>
                          <button className="sa-micro" title={a.active ? "Désactiver l'agent (requêtes refusées)" : "Réactiver l'agent"} onClick={() => handleToggleActive(a)}>{a.active ? "⏸" : "▶"}</button>
                          <button className="sa-micro danger" title="Supprimer l'agent" onClick={() => handleDelete(a)}>🗑</button>
                        </td>
                        )}
                      </tr>
                      {fils.map((h) => {
                        const hAge = h.at ? Math.max(0, Math.round((now - Date.parse(h.at)) / 1000)) : null;
                        return (
                          <tr key={`${a.agent_id}>${h.name}`} className="sa-relayed-row" title={h.error || ""}>
                            <td colSpan={agentCols.visible.length} style={{ paddingLeft: 28 }}>
                              <span className="muted">↳ relevé par {a.agent_id} :</span> <strong>{h.name}</strong>{" "}
                              <Tone tone={h.ok ? "good" : "bad"}>{h.ok ? "relevé" : "injoignable"}</Tone>{" "}
                              {h.os || "système inconnu"}{h.noyau ? ` · noyau ${h.noyau}` : ""}
                              {(h.ips || []).length > 0 && <> · <IpPing os={false} ip={h.ips[0]} /><OsActions label={h.name} ip={h.ips[0]} prefer={h.relay} />{h.ips.length > 1 ? <span className="muted"> +{h.ips.length - 1}</span> : null}</>}
                              {h.ports?.length > 0 && <span className="muted"> · ports {h.ports.slice(0, 12).join(", ")}{h.ports.length > 12 ? "…" : ""}</span>}
                              {hAge != null && <span className="muted"> · il y a {hAge < 3600 ? `${Math.round(hAge / 60)} min` : `${Math.round(hAge / 3600)} h`}</span>}
                              {h.error && <span style={{ color: "var(--danger)" }}> · {h.error}</span>}{h.error && <BoutonDetail titre={`Relevé de ${h.name}`} urgence="critique" texte={h.error} />}
                              {" "}<a href={hubLink("migration", { page: "etat" })} onClick={(e) => e.stopPropagation()}>état des lieux</a>
                            </td>
                          </tr>);
                      })}
                      </Fragment>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}

          {selectedId && (
            <div className="hub-card hub-settings-section ups-detail sa-detail">
              <div className="ups-toolbar" style={{ marginTop: 0 }}>
                <button className="secondary" onClick={() => setSelectedId(null)} title="revenir au tableau des agents">◀ Agents</button>
                <select value={selectedId} onChange={(e) => setSelectedId(e.target.value)} title="passer directement à un autre agent">
                  {[...fleet].sort((x, y) => x.agent_id.localeCompare(y.agent_id)).map((x) => <option key={x.agent_id} value={x.agent_id}>{x.agent_id}</option>)}
                </select>
                <h2 style={{ margin: 0 }}>{detail?.hostname || selectedId}</h2>
                {detail && (() => { const v = versionEtat(detail.agent_version, status?.package?.version); return <Tone tone={v.ton} title={v.titre}>v{v.texte}</Tone>; })()}
                {/windows/i.test(detail?.os || "") && (   /* #923/#936 : un agent Windows mène directement à son poste -- boutons rouges lisibles */
                  <span className="sa-liens-poste">Poste Windows :
                    <a href={hubLink("postes-windows", { agent: selectedId, onglet: "diagnostic" })}>Diagnostic</a>
                    <a href={hubLink("postes-windows", { agent: selectedId, onglet: "distance" })}>Analyse à distance</a>
                    <a href={hubLink("postes-windows", { agent: selectedId, onglet: "charge" })}>Tests de charge</a>
                    <button type="button" className="sa-btn-poste" title="sauvegarde des données (confs + montages) -- onglet Sauvegardes" onClick={() => { setSauvegardeMode("donnees"); setOnglet("sauvegardes"); }}>Sauvegarde · données</button>
                    <button type="button" className="sa-btn-poste" title="sauvegarde image du disque système -- onglet Sauvegardes" onClick={() => { setSauvegardeMode("image"); setOnglet("sauvegardes"); }}>Sauvegarde · image</button>
                    <button type="button" className="sa-btn-poste sa-btn-croix" title="préparer une clé USB de démarrage de secours -- onglet Sauvegardes" onClick={() => { setSauvegardeMode("usb"); setOnglet("sauvegardes"); }}>Boot USB urgence</button>
                  </span>)}
                {detail && (
                  <Tone tone={detail.config_applied ? "good" : "warn"} title={`version ${detail.config_version}`}>{detail.config_applied ? "configuration appliquée" : "configuration en attente"}</Tone>
                )}
                <span style={{ flex: 1 }} />
                <button className="secondary" onClick={() => loadDetail(selectedId)}>⟳</button>
                <button className="secondary" onClick={() => setSelectedId(null)}>✕</button>
              </div>

              {install && install.agent_id === selectedId && (
                <div className="np-secret-box hub-card" style={{ margin: "8px 0" }}>
                  {/* #680 : adresse du hub choisie (historique mémorisé), lignes régénérées : -k + empreinte de CA pour une
                      adresse interne, certificat public sinon ; le secret sur sa propre ligne (TOKEN=…), réutilisé ensuite. */}
                  {(() => {
                    const lanCentral = ((String(install.install_command || "").match(/--central\s+'?([^'\s]+)/) || [])[1]) || "";
                    const suggestions = [...new Set([...hubHistory, lanCentral, `${window.location.origin}/api/si-agent`].map(normalizeBase).filter(Boolean))];
                    const base = normalizeBase(hubAddr) || suggestions[0] || "";
                    const L = installLines({ base, agentId: install.agent_id, site: install.site, pkg: install.package, caFp: caFingerprintOf(install.install_command) });
                    const choose = (v) => { setHubAddr(v); const n = normalizeBase(v); if (n) { const h = pushHistory(hubHistory, n); setHubHistory(h); saveHistory(h); } };
                    return (
                      <>
                        <div className="hub-settings-row" style={{ margin: "0 0 6px" }}>
                          <label>Adresse du hub vue de l'hôte</label>
                          <input type="text" list="si-agent-hub-addresses" value={hubAddr || base} onChange={(e) => setHubAddr(e.target.value)} onBlur={(e) => choose(e.target.value)} placeholder="https://hub.exemple.fr/api/si-agent" />
                          <datalist id="si-agent-hub-addresses">{suggestions.map((u) => <option key={u} value={u} />)}</datalist>
                          <span className="muted" style={{ fontSize: 12 }}>{L.internal ? "adresse interne (LAN du hub) : CA du projet épinglée" : "adresse publique (campus, Internet, OVH) : certificat public, ni -k ni empreinte"}</span>
                          <div className="ds-inline" style={{ marginTop: 2 }}>{suggestions.map((u) => <button key={u} type="button" className={u === base ? "primary pv-mini" : "secondary pv-mini"} onClick={() => choose(u)}>{u.replace(/^https?:\/\//, "").replace(/\/api\/si-agent$/, "")}</button>)}</div>
                        </div>
                        <p style={{ margin: "0 0 4px" }}>0. Secret de l'agent, à coller d'abord dans le shell de l'hôte (ne pas diffuser) :</p>
                        <pre className="np-secret">{`TOKEN='${install.secret}'`}</pre>
                        {install.package ? (
                          <p className="muted" style={{ margin: "6px 0 4px", fontSize: 12 }}>
                            1. Archive de l'agent : <a href={`${siAgentApiBase}/package`} download={install.package.name}>télécharger <code>{install.package.name}</code></a> ({formatBytes(install.package.size)}, SHA-256 <code>{install.package.sha256.slice(0, 16)}…</code>) -- ou directement sur l'hôte :
                          </p>
                        ) : (
                          <p className="muted" style={{ margin: "6px 0 4px", fontSize: 12 }}>1. Archive de l'agent : absente de cette image (<code>si-agent/make-archive.sh</code> sur le poste, puis copie sur l'hôte).</p>
                        )}
                        {L.download && <pre className="np-secret">{L.download}</pre>}
                        <p style={{ margin: "6px 0 4px" }}>2. Installation, dans le dossier de l'archive (root ; <code>sudo</code> devant sinon) :</p>
                        <pre className="np-secret">{L.install}</pre>
                        <details style={{ marginTop: 6 }}>
                          <summary>2 bis. Hôte ancien : « si-agent requiert Python &gt;= 3.7 » (Debian 9 / Proxmox VE 5 = Python 3.5)</summary>
                          <p className="muted" style={{ margin: "4px 0", fontSize: 12 }}>Un Python 3.11 <b>autonome</b> est installé dans <code>/opt/pyagent</code>, sans toucher au Python du système, puis la même installation est relancée avec <code>--python</code> et <b>toutes</b> ses options. Une commande à la fois, dans le dossier de l'archive :</p>
                          {oldHostLines(L.install).map((c, i) => <pre key={i} className="np-secret">{c}</pre>)}
                          <p className="muted" style={{ margin: "2px 0 0", fontSize: 12 }}>
                            Hôte 32 bits (<code>uname -m</code> = <code>i686</code>) et <code>uv</code> refusé : archive <code>cpython-3.11.*-i686-unknown-linux-gnu-install_only.tar.gz</code> de python-build-standalone décompressée dans <code>/opt/pyagent</code>, puis <code>PYAGENT=/opt/pyagent/python/bin/python3</code> (<code>docs/agent-python-autonome.md</code>, option B).
                            {L.internal ? "" : " Adresse publique : si « CERTIFICATE_VERIFY_FAILED », l'installeur propose le magasin système ou certifi (même document)."}
                            {" "}Solution de passage : l'hôte reste à mettre à niveau (état des lieux).</p>
                        </details>
                      </>
                    );
                  })()}
                  {install.install_command_docker && (
                    <>
                      <p className="muted" style={{ margin: "6px 0 2px", fontSize: 12 }}>Variante conteneur (l'hôte a Docker, archive <code>si-agent-agent-&lt;version&gt;.tar.gz</code>, voir <code>si-agent/agent/README-DEPLOIEMENT.md</code>) :</p>
                      <pre className="np-secret">{install.install_command_docker}</pre>
                    </>
                  )}
                  {install.install_command_macos && (
                    <>
                      <p className="muted" style={{ margin: "6px 0 2px", fontSize: 12 }}>macOS (Terminal, <code>sudo</code> ; LaunchDaemon au démarrage, archive <code>si-agent-agent-&lt;version&gt;.tar.gz</code> décompressée) :</p>
                      <pre className="np-secret">{install.install_command_macos}</pre>
                    </>
                  )}
                  {install.install_command_windows && (
                    <>
                      <details style={{ margin: "8px 0" }}>
                        <summary style={{ cursor: "pointer" }}>Windows — l'agent est installé mais rien ne remonte : diagnostic sur le poste</summary>
                        <p className="muted" style={{ margin: "4px 0", fontSize: 12 }}>Sur le poste, Terminal <b>administrateur</b> (PowerShell), copier ce bloc : tâche planifiée, processus, journal, enrôlement.</p>
                        <pre className="np-secret">{WINDOWS_DIAG}</pre>
                        <p className="muted" style={{ margin: "4px 0 0", fontSize: 12 }}>
                          <b>LastTaskResult 0</b> + un processus <code>python</code> = l'agent tourne. Journal « central » / « flush » = il joint le hub.
                          Si <code>agent.json</code> manque : l'installation a échoué (relancer le .cmd, il montre son journal).
                          S'il tourne mais rien ici : activer la sonde <b>poste-windows</b> (Commandes ci-dessous) — sans sonde, seul l'inventaire de base remonte.</p>
                      </details>
                      {(() => {
                        const lan = ((String(install.install_command || "").match(/--central\s+'?([^'\s]+)/) || [])[1]) || "";
                        const b = normalizeBase(hubAddr) || [...hubHistory, lan, `${window.location.origin}/api/si-agent`].map(normalizeBase).filter(Boolean)[0] || "";
                        const W = installLines({ base: b, agentId: install.agent_id, site: install.site, pkg: install.package, caFp: caFingerprintOf(install.install_command) });
                        return W.downloadWindows ? (<>
                          <p className="muted" style={{ margin: "8px 0 2px", fontSize: 12 }}>Windows 10 / 11 — 1. téléchargement, vérification et décompression de l'archive (Terminal <b>administrateur</b>, PowerShell, dans un dossier de travail, ex. <code>cd $env:TEMP</code>) :</p>
                          <pre className="np-secret">{W.downloadWindows}</pre>
                        </>) : null;
                      })()}
                      <p className="muted" style={{ margin: "6px 0 2px", fontSize: 12 }}>Windows 10 / 11 — 2. installation : Terminal (administrateur), depuis l'archive décompressée (ne pas double-cliquer le .ps1 : le Bloc-notes s'ouvre ; <code>windows\install.cmd</code> fait l'élévation et accepte les mêmes arguments, ou pose les questions en double-clic) :</p>
                      <pre className="np-secret">{install.install_command_windows}</pre>
                      {install.install_cmd_available ? (
                        <p className="muted" style={{ margin: "4px 0 2px", fontSize: 12 }}>
                          Sans intervention : <a href={installCmdUrl(siAgentApiBase, selectedId)} download={`si-agent-install-${selectedId}.cmd`}>télécharger <code>si-agent-install-{selectedId}.cmd</code></a> (secret et empreinte inclus) et double-cliquer, où qu'il soit : « Éditeur inconnu » › Exécuter, UAC une fois ; il télécharge l'agent s'il n'est pas décompressé à côté, l'installe, affiche « OK » et s'efface.
                        </p>
                      ) : (
                        <p className="muted" style={{ margin: "4px 0 2px", fontSize: 12 }}>Fichier .cmd silencieux indisponible : CA interne absente sur le central (empreinte requise) ou caractère interdit dans l'identifiant / le site.</p>
                      )}
                    </>
                  )}
                  <AccueilOuverture base={siAgentApiBase} agentId={selectedId} />
                  <div style={{ display: "flex", gap: 8, marginTop: 6 }}>
                    <button className="secondary" onClick={() => handleRotate(selectedId)}>Nouveau secret</button>
                    <button className="secondary" onClick={() => setInstall(null)}>Masquer</button>
                  </div>
                </div>
              )}

              {!detail ? <p className="muted">Chargement…</p> : (
                <>
                  <div className="sa-onglets">   {/* #922 : onglets -- une section à la fois, toutes visibles d'un coup d'œil */}
                    {ONGLETS.map(([k, l]) => (
                      <button key={k} className={`secondary na-section-toggle${onglet === k ? " active" : ""}`} disabled={!host && !SANS_MESURE.has(k)} onClick={() => setOnglet(k)}>{l}</button>
                    ))}
                    {host && <span className="muted" style={{ fontSize: 12, marginLeft: "auto" }}>mesure du {when(detail.latest.host.at)}{host.partial?.length > 0 && <> · <Tone tone="warn">partielle : {host.partial.join(", ")}</Tone></>}</span>}
                  </div>
                  {!host && !SANS_MESURE.has(onglet) && (
                    <p className="muted">Aucune mesure reçue de cet agent pour l'instant{detail.last_seen_at ? "" : " -- il n'a jamais contacté le central : vérifier l'installation, l'URL du central et le secret"}. Onglets disponibles : Sondes, Commandes, Réglages.</p>
                  )}
                  {host && (<>

                  {section.risks && (
                    <>
                      <h3>Risques internes ({hostRisks?.risks?.length || 0})</h3>
                      {!hostRisks?.risks?.length ? <p className="muted">Aucun constat.</p> : (
                        <ul className="sa-risks">
                          {hostRisks.risks.map((r, i) => (
                            <li key={i}><Tone tone={severityTone(r.severity)}>{r.severity === "critical" ? "⛔" : r.severity === "warning" ? "⚠" : "ℹ"} {riskLabel(r.id)}</Tone> — {r.message}</li>
                          ))}
                        </ul>
                      )}
                    </>
                  )}

                  {section.system && (
                    <>
                      <h3>Système</h3>
                      <div className="sa-kv">
                        <div><span className="muted">OS</span>{host.system?.os || "—"}</div>
                        <div><span className="muted">Noyau</span>{host.system?.kernel || "—"}</div>
                        <div><span className="muted">Machine</span>{host.system?.model || host.system?.cpu_model || "—"}{host.system?.cpus ? ` · ${host.system.cpus} CPU` : ""}</div>
                        <div><span className="muted">Démarré depuis</span>{formatUptime(host.system?.uptime_seconds)}{host.system?.reboot_required && <> · <Tone tone="warn">redémarrage requis</Tone></>}</div>
                        <div><span className="muted">CPU</span>{host.cpu?.percent != null ? `${host.cpu.percent} %` : "—"} · charges {host.cpu?.load1 ?? "—"} / {host.cpu?.load5 ?? "—"} / {host.cpu?.load15 ?? "—"}</div>
                        {/* #520 : antivirus, même forme Windows / macOS (Centre de sécurité, produits + XProtect / Gatekeeper / SIP) */}
                        {host.antivirus && (
                          <div className="sa-wide"><span className="muted">Antivirus</span>
                            {(host.antivirus.products || []).length === 0 ? <Tone tone="bad">aucun antivirus détecté</Tone> : (host.antivirus.products || []).map((p, i) => (
                              <Fragment key={p.name}>{i ? " · " : ""}<Tone tone={p.enabled ? (p.up_to_date === false ? "warn" : "good") : p.enabled === false ? "bad" : "neutral"}>{p.name} {p.enabled ? "actif" : p.enabled === false ? "inactif" : "état inconnu"}{p.up_to_date === false ? ", définitions périmées" : ""}{p.definitions_age_days != null ? ` · signatures ${p.definitions_age_days} j` : ""}</Tone></Fragment>
                            ))}
                            {host.antivirus.platform && <> · Gatekeeper <Tone tone={host.antivirus.platform.gatekeeper === false ? "bad" : host.antivirus.platform.gatekeeper ? "good" : "neutral"}>{host.antivirus.platform.gatekeeper === false ? "off" : host.antivirus.platform.gatekeeper ? "on" : "?"}</Tone> · SIP <Tone tone={host.antivirus.platform.sip === false ? "bad" : host.antivirus.platform.sip ? "good" : "neutral"}>{host.antivirus.platform.sip === false ? "off" : host.antivirus.platform.sip ? "on" : "?"}</Tone>{host.antivirus.platform.xprotect_version && <> · XProtect {host.antivirus.platform.xprotect_version}{host.antivirus.platform.xprotect_age_days != null ? ` (${host.antivirus.platform.xprotect_age_days} j)` : ""}</>}</>}
                          </div>
                        )}
                        {host.windows && (host.windows.defender || host.windows.firewall?.length > 0) && (
                          <div className="sa-wide"><span className="muted">Windows</span>
                            {host.windows.defender ? <Tone tone={host.windows.defender.enabled && host.windows.defender.realtime ? "good" : "bad"}>Defender {host.windows.defender.enabled ? "actif" : "inactif"}{host.windows.defender.realtime === false ? ", temps réel désactivé" : ""}{host.windows.defender.signatures_age_days != null ? ` · signatures ${host.windows.defender.signatures_age_days} j` : ""}</Tone> : "Defender : —"}
                            {" · "}pare-feu : {(host.windows.firewall || []).map((p) => <Tone key={p.profile} tone={p.enabled ? "good" : "bad"}>{p.profile} {p.enabled ? "on" : "off"}</Tone>).reduce((acc, x, i) => (i ? [...acc, " / ", x] : [x]), [])}
                            {host.windows.updates?.last_hotfix && <> · dernier correctif {host.windows.updates.last_hotfix}</>}
                            {host.windows.bitlocker_c && <> · BitLocker C: {host.windows.bitlocker_c}</>}
                            {host.system?.display_version && <> · {host.system.display_version}</>}
                          </div>
                        )}
                        <div><span className="muted">Mémoire</span>{formatBytes(host.memory?.total_bytes != null && host.memory?.available_bytes != null ? host.memory.total_bytes - host.memory.available_bytes : null)} / {formatBytes(host.memory?.total_bytes)} ({host.memory?.used_percent ?? "—"} %){host.memory?.swap_total_bytes > 0 && <> · swap {host.memory.swap_used_percent} %</>}</div>
                        <div><span className="muted">Comptes</span>{host.system?.os_id === "windows" ? "administrateurs" : "sudo"} : {(host.accounts?.sudoers || []).join(", ") || "—"} · {host.system?.os_id === "windows" ? "locaux actifs" : "interactifs"} : {(host.accounts?.interactive || []).join(", ") || "—"}{host.accounts?.uid0_not_root?.length > 0 && <> · <Tone tone="bad">UID 0 : {host.accounts.uid0_not_root.join(", ")}</Tone></>}</div>
                        <div><span className="muted">Agent</span>v{detail.agent_version || "?"} · dernière IP <IpPing os={false} ip={contactIp(detail.last_ip)} /><OsActions label={detail.agent_id} ip={contactIp(detail.last_ip)} agent={detail.agent_id} />{inventory?.tools?.available && <> · outils : {inventory.tools.available.join(", ")}</>}</div>
                        {/* #549 : la page que l'agent publie sur son LAN, vue d'ici (même gabarit, même contenu) */}
                        {detail.publish?.enabled && (
                          <div><span className="muted">Publication</span>page « {detail.publish.title} » sur le port {detail.publish.port} du poste · {publishedPageUrl(detail) && <><a href={publishedPageUrl(detail)} target="_blank" rel="noopener noreferrer">ouvrir sur le site ↗</a> (depuis le réseau du site) · </>}<a href={`${siAgentApiBase}/agents/${encodeURIComponent(selectedId)}/publish/preview`} target="_blank" rel="noopener noreferrer">aperçu depuis le hub ↗</a></div>
                        )}
                      </div>
                    </>
                  )}

                  {/* #525 : sonde Wi-Fi « expérience client » -- affichée dès qu'une mesure existe */}
                  {section.network && detail.latest?.["plugin:wifi-probe"] && (
                    <WifiProbeSection apiBase={siAgentApiBase} agentId={selectedId} latest={detail.latest["plugin:wifi-probe"]} when={when} />
                  )}
                  {section.network && detail.latest?.["plugin:web-audit"] && (
                    <WebAuditSection latest={detail.latest["plugin:web-audit"]} when={when} />
                  )}
                  {section.network && detail.latest?.["plugin:front-access"] && (
                    <FrontAccessSection latest={detail.latest["plugin:front-access"]} when={when} />
                  )}
                  {detail.latest?.["plugin:mail-server"] && (
                    <MailServerSection latest={detail.latest["plugin:mail-server"]} when={when} />
                  )}
                  {(detail.latest?.["plugin:ollama"] || (inventory?.tools?.available || []).includes("ollama")) && (
                    <OllamaSection apiBase={siAgentApiBase} agentId={selectedId} latest={detail.latest?.["plugin:ollama"]} present when={when} onRefresh={() => loadDetail && loadDetail(selectedId)} />
                  )}
                  {section.network && detail.latest?.["plugin:web-trace"] && (
                    <WebTraceSection latest={detail.latest["plugin:web-trace"]} when={when} />
                  )}
                  {section.network && detail.latest?.["plugin:path-probe"] && (
                    <PathProbeSection apiBase={siAgentApiBase} agentId={selectedId} latest={detail.latest["plugin:path-probe"]} when={when} />
                  )}
                  {section.network && (
                    <>
                      <h3>Réseau vu de l'hôte {netview ? <span className="muted" style={{ textTransform: "none", letterSpacing: 0 }}>· découverte passive du {when(detail.latest.netview.at)}{netview.partial?.length > 0 && <> · <Tone tone="warn">partielle : {netview.partial.join(", ")}</Tone></>}</span> : null}</h3>
                      {!netview ? <p className="muted">Pas encore de mesure « netview » (agent ≥ 0.3.0, toutes les 5 min).</p> : (
                        <>
                          <div className="sa-kv">
                            <div><span className="muted">Sous-réseaux attachés</span>{netview.summary?.attached_subnets?.length ? netview.summary.attached_subnets.map((n) => <code key={n} style={{ marginRight: 6 }}>{n}</code>) : "—"}</div>
                            <div><span className="muted">Passerelle par défaut</span>{netview.summary?.default_gateway ? <><code>{netview.summary.default_gateway}</code> · ARP {netview.summary.default_gateway_state || "inconnu"}</> : <Tone tone="warn">aucune (sous-réseau isolé)</Tone>}</div>
                            <div className="sa-wide"><span className="muted">Routes directes</span>{netview.summary?.reachable_subnets?.length ? netview.summary.reachable_subnets.map((r) => <span key={r.subnet} className="na-chip"><code>{r.subnet}</code> via {r.gateway} ({r.gateway_state || "?"})</span>) : <span className="muted">aucune route statique vers un autre sous-réseau</span>}</div>
                            <div><span className="muted">DNS</span>{(netview.dns?.servers || []).join(", ") || "—"}{netview.dns?.search?.length ? ` · recherche ${netview.dns.search.join(", ")}` : ""}</div>
                            <div className="sa-wide"><span className="muted">Interfaces</span>{(netview.interfaces || []).map((i) => <span key={i.name} className="na-chip">{i.name} {i.state} {i.mac ? `· ${i.mac}` : ""} {i.addresses.filter((a) => a.family === "inet").map((a) => `${a.ip}/${a.prefix}`).join(" ")}</span>)}</div>
                          </div>
                          <div className="sa-two-cols">
                            <div>
                              <h4>Pairs des connexions établies ({netview.summary?.peers?.length || 0})</h4>
                              {netview.summary?.peers?.length ? (
                                <div className="hub-table-scroll" style={{ maxHeight: 220 }}>
                                  <AutoColumns id="SiAgentView.1"><table>
                                    <thead><tr><th>IP</th><th>Conn.</th><th>Ports</th><th>Processus</th><th>Portée</th></tr></thead>
                                    <tbody>{netview.summary.peers.slice(0, 40).map((p) => (
                                      <tr key={p.ip}><td><code>{p.ip}</code></td><td>{p.connections}</td><td className="muted">{p.ports.join(", ")}</td><td>{p.processes.join(", ") || "—"}</td><td>{p.local === true ? "sous-réseau local" : p.local === false ? <Tone tone="neutral">distant / routé</Tone> : "—"}</td></tr>
                                    ))}</tbody>
                                  </table></AutoColumns>
                                </div>
                              ) : <p className="muted">Aucune connexion établie au moment de la mesure.</p>}
                            </div>
                            <div>
                              <h4>Voisins ARP / NDP ({netview.neighbors?.length || 0}){netview.summary?.neighbors_outside_attached?.length > 0 && <> · <Tone tone="warn">{netview.summary.neighbors_outside_attached.length} hors sous-réseau attaché</Tone></>}</h4>
                              {netview.neighbors?.length ? (
                                <div className="hub-table-scroll" style={{ maxHeight: 220 }}>
                                  <AutoColumns id="SiAgentView.2"><table>
                                    <thead><tr><th>IP</th><th>MAC</th><th>Interface</th><th>État</th></tr></thead>
                                    <tbody>{netview.neighbors.slice(0, 60).map((n, i) => (
                                      <tr key={i}><td><code>{n.ip}</code></td><td className="muted">{n.mac || "—"}</td><td>{n.dev}</td><td>{n.state}</td></tr>
                                    ))}</tbody>
                                  </table></AutoColumns>
                                </div>
                              ) : <p className="muted">Aucun voisin résolu (l'hôte n'a parlé à personne sur le L2, ou table vidée).</p>}
                            </div>
                          </div>
                        </>
                      )}
                    </>
                  )}

                  {section.hardware && (
                    <>
                      <h3>Matériel {hardware ? <span className="muted" style={{ textTransform: "none", letterSpacing: 0 }}>· inventaire du {when(detail.latest.inventory.at)}</span> : null}</h3>
                      {!hardware ? <p className="muted">Pas encore d'inventaire matériel (agent ≥ 0.3.0, toutes les heures).</p> : (
                        <div className="sa-kv">
                          <div><span className="muted">Machine</span>{[hardware.vendor, hardware.product, hardware.product_version].filter(Boolean).join(" ") || "—"}{hardware.serial ? ` · n° ${hardware.serial}` : ""}{hardware.virtualization && hardware.virtualization !== "none" ? <> · <Tone tone="neutral">virtualisé ({hardware.virtualization})</Tone></> : ""}</div>
                          <div><span className="muted">Carte / BIOS</span>{hardware.board || "—"}{hardware.bios ? ` · BIOS ${hardware.bios}` : ""}</div>
                          <div><span className="muted">CPU</span>{hardware.cpu?.model || "—"}{hardware.cpu?.cpus ? ` · ${hardware.cpu.cpus} CPU` : ""}{hardware.cpu?.sockets ? ` (${hardware.cpu.sockets} socket, ${hardware.cpu.cores_per_socket} cœurs${hardware.cpu.threads_per_core ? `, ${hardware.cpu.threads_per_core} fils` : ""})` : ""}{hardware.cpu?.arch ? ` · ${hardware.cpu.arch}` : ""}</div>
                          <div><span className="muted">Mémoire installée</span>{formatBytes(hardware.memory_total_bytes)}</div>
                          <div className="sa-wide"><span className="muted">Disques physiques</span>{hardware.disks?.length ? hardware.disks.map((d) => <span key={d.name} className="na-chip"><code>{d.name}</code> {d.size} {d.model || d.vendor || ""} {d.transport || ""} {d.rotational == null ? "" : d.rotational ? "HDD" : "SSD"}{d.health && d.health !== "Healthy" ? ` ⚠ ${d.health}` : ""}</span>) : "—"}</div>
                          {hardware.software_count != null && (
                            <div className="sa-wide"><span className="muted">Logiciels installés ({hardware.software_count})</span>
                              {(hardware.software || []).slice(0, 40).map((s) => <span key={s.name} className="na-chip" title={`${s.publisher || ""} ${s.installed || ""}`.trim()}>{s.name}{s.version ? ` ${s.version}` : ""}</span>)}
                              {hardware.software_count > 40 && <span className="muted"> … et {hardware.software_count - 40} autres (inventaire complet dans la mesure)</span>}
                            </div>
                          )}
                          <div className="sa-wide"><span className="muted">Cartes réseau</span>{hardware.nics?.length ? hardware.nics.map((n) => <span key={n.name} className="na-chip">{n.name} {n.state} · {n.mac}{n.speed_mbps ? ` · ${n.speed_mbps} Mb/s` : ""}</span>) : "—"}</div>
                          {hardware.partial?.length > 0 && <div><span className="muted">Sources absentes</span><Tone tone="warn">{hardware.partial.join(", ")}</Tone></div>}
                        </div>
                      )}
                    </>
                  )}

                  {section.activity && (
                    <>
                      <h3>Activité {activity ? <span className="muted" style={{ textTransform: "none", letterSpacing: 0 }}>· {activity.process_count ?? "?"} processus · {activity.running_services_count ?? "?"} services actifs{activity.updates_available != null ? ` · ${activity.updates_available} mise(s) à jour en attente` : ""}</span> : null}</h3>
                      {!activity ? <p className="muted">Pas encore de mesure d'activité (agent ≥ 0.3.0).</p> : (
                        <div className="sa-two-cols">
                          <div>
                            <h4>Processus (CPU)</h4>
                            <div className="hub-table-scroll" style={{ maxHeight: 200 }}>
                              <AutoColumns id="SiAgentView.3"><table>
                                <thead><tr><th>PID</th><th>Utilisateur</th><th>CPU</th><th>Mém.</th><th>Commande</th></tr></thead>
                                <tbody>{(activity.top_cpu || []).map((p) => <tr key={p.pid}><td>{p.pid}</td><td>{p.user}</td><td>{p.cpu_percent} %</td><td>{formatBytes(p.rss_bytes)}</td><td><code>{p.command}</code></td></tr>)}</tbody>
                              </table></AutoColumns>
                            </div>
                            <h4>Processus (mémoire)</h4>
                            <div className="hub-table-scroll" style={{ maxHeight: 200 }}>
                              <AutoColumns id="SiAgentView.4"><table>
                                <thead><tr><th>PID</th><th>Utilisateur</th><th>Mém.</th><th>CPU</th><th>Commande</th></tr></thead>
                                <tbody>{(activity.top_memory || []).map((p) => <tr key={p.pid}><td>{p.pid}</td><td>{p.user}</td><td>{formatBytes(p.rss_bytes)}</td><td>{p.cpu_percent} %</td><td><code>{p.command}</code></td></tr>)}</tbody>
                              </table></AutoColumns>
                            </div>
                          </div>
                          <div>
                            <h4>Sessions ouvertes ({activity.sessions?.length || 0})</h4>
                            {activity.sessions?.length ? <ul>{activity.sessions.map((sn, i) => <li key={i}><strong>{sn.user}</strong> sur {sn.tty}{sn.from ? ` depuis ${sn.from}` : ""}{sn.since ? ` (${sn.since})` : ""}</li>)}</ul> : <p className="muted">Aucune.</p>}
                            <h4>Dernières connexions</h4>
                            {activity.last_logins?.length ? <pre className="sa-log">{activity.last_logins.map((l) => l.line).join("\n")}</pre> : <p className="muted">—{activity.partial?.includes("last") ? " (commande last absente)" : ""}</p>}
                            <h4>Services actifs ({activity.running_services_count ?? "?"})</h4>
                            <p className="muted" style={{ fontSize: 12 }}>{(activity.running_services || []).slice(0, 40).join(", ")}{(activity.running_services || []).length > 40 ? "…" : ""}</p>
                          </div>
                        </div>
                      )}
                    </>
                  )}

                  {section.disks && (
                    <>
                      <h3>Disques ({disks.length})</h3>
                      <div className="hub-table-scroll">
                        <AutoColumns id="SiAgentView.5"><table>
                          <thead><tr><th>Montage</th><th>Périphérique</th><th>Type</th><th>Utilisé</th><th>Total</th><th>Remplissage</th></tr></thead>
                          <tbody>{disks.map((d) => (
                            <tr key={d.mountpoint}><td><code>{d.mountpoint}</code>{d.remote && <> <span className="na-chip">distant</span></>}{d.readonly && <> <span className="na-chip" title="lecture seule : ne peut pas se remplir, jamais un risque">lecture seule</span></>}{d.removable && <> <span className="na-chip" title="support amovible ou image montée : information seulement">amovible</span></>}</td><td className="muted">{d.device}</td><td className="muted">{d.fstype}{d.measuredAs && <> <span title={`montage FUSE réservé à son utilisateur : mesuré en se présentant comme ${d.measuredAs}`}>({d.measuredAs})</span></>}</td><td>{d.used}</td><td>{d.total}</td><td>{d.gauge ? <Gauge percent={d.gauge.percent} /> : <Tone tone="warn" title={d.error || ""}>{d.invisible ? "invisible du conteneur" : "illisible"}{d.error ? ` — ${d.error}` : ""}</Tone>}</td></tr>
                          ))}</tbody>
                        </table></AutoColumns>
                      </div>
                    </>
                  )}

                  {section.storage && (
                    <>
                      <h3>Stockage {storage ? <span className="muted" style={{ fontWeight: "normal", fontSize: 12 }}>· {storage.available.join(", ")}</span> : null}</h3>
                      {!storage ? <p className="muted">Pas de couche de stockage remontée (agent antérieur à #503, ou lsblk / LVM / ZFS absents de l'hôte).</p> : (
                        <>
                          {storage.pools.length > 0 && (
                            <>
                              <h4>Pools ZFS ({storage.pools.length}) · {storage.snapshotTotal} snapshot{storage.snapshotTotal > 1 ? "s" : ""}</h4>
                              <div className="hub-table-scroll"><AutoColumns id="SiAgentView.6"><table>
                                <thead><tr><th>Pool</th><th>État</th><th>Alloué</th><th>Libre</th><th>Taille</th><th>Remplissage</th><th>Fragm.</th><th>Dernier scrub</th><th>Erreurs</th></tr></thead>
                                <tbody>{storage.pools.map((p) => (
                                  <tr key={p.pool}><td><code>{p.pool}</code></td><td><Tone tone={p.tone}>{p.state}</Tone></td><td>{p.alloc}</td><td>{p.free}</td><td>{p.size}</td><td>{p.gauge ? <Gauge percent={p.gauge.percent} /> : "—"}</td><td>{p.fragmentation}</td><td>{p.scrub}</td><td>{p.errors.length ? <Tone tone="warn">{p.errors.join(", ")}</Tone> : <span className="muted">aucune</span>}</td></tr>
                                ))}</tbody>
                              </table></AutoColumns></div>
                              <h4>Datasets et zvols ({storage.datasets.length})</h4>
                              <div className="hub-table-scroll"><AutoColumns id="SiAgentView.7"><table>
                                <thead><tr><th>Nom</th><th>Type</th><th>Montage</th><th>Utilisé</th><th>Disponible</th><th>Quota / taille</th><th>Remplissage</th><th>Compr.</th><th>Snapshots</th><th>Plus ancien</th><th>Plus récent</th></tr></thead>
                                <tbody>{storage.datasets.map((d) => (
                                  <tr key={d.name}><td><code>{d.name}</code></td><td className="muted">{d.type}</td><td className="muted">{d.mountpoint}</td><td>{d.used}</td><td>{d.avail}</td><td>{d.quota}</td><td>{d.gauge ? <Gauge percent={d.gauge.percent} /> : "—"}</td><td className="muted">{d.ratio}</td><td>{d.snapshots}{d.snapUsed ? <span className="muted"> ({d.snapUsed})</span> : null}</td><td className="muted">{d.snapOldest}</td><td className="muted">{d.snapNewest}</td></tr>
                                ))}</tbody>
                              </table></AutoColumns></div>
                            </>
                          )}
                          {storage.lvm && (
                            <>
                              <h4>LVM · {storage.lvm.groups.length} groupe{storage.lvm.groups.length > 1 ? "s" : ""}</h4>
                              <div className="hub-table-scroll"><AutoColumns id="SiAgentView.8"><table>
                                <thead><tr><th>Volume</th><th>Groupe</th><th>Genre</th><th>Taille</th><th>Pool / origine</th><th>Données</th><th>Métadonnées</th></tr></thead>
                                <tbody>{storage.lvm.volumes.map((v) => (
                                  <tr key={`${v.vg}/${v.lv}`}><td><code>{v.lv}</code>{v.active === false && <> <span className="na-chip">inactif</span></>}</td><td className="muted">{v.vg}</td><td className="muted">{v.kind}</td><td>{v.size}</td><td className="muted">{v.pool || v.origin}</td><td>{v.data ? <Gauge percent={v.data.percent} /> : "—"}</td><td>{v.meta ? <Gauge percent={v.meta.percent} /> : "—"}</td></tr>
                                ))}</tbody>
                              </table></AutoColumns></div>
                              <p className="muted" style={{ fontSize: 12 }}>{storage.lvm.groups.map((g) => `${g.vg} : ${g.size}, libre ${g.free}, ${g.pv} PV, ${g.lv} LV`).join(" · ")}</p>
                            </>
                          )}
                          {storage.md.length > 0 && (
                            <>
                              <h4>RAID logiciel ({storage.md.length})</h4>
                              <div className="hub-table-scroll"><AutoColumns id="SiAgentView.9"><table>
                                <thead><tr><th>Grappe</th><th>Niveau</th><th>État</th><th>Disques actifs</th><th>Membres</th></tr></thead>
                                <tbody>{storage.md.map((a) => (
                                  <tr key={a.array}><td><code>{a.array}</code></td><td>{a.level}</td><td><Tone tone={a.tone}>{a.state}</Tone></td><td>{a.active == null ? "—" : `${a.active} / ${a.total}`}</td><td className="muted">{a.devices}</td></tr>
                                ))}</tbody>
                              </table></AutoColumns></div>
                            </>
                          )}
                          {storage.blocks.length > 0 && (
                            <>
                              <h4>Périphériques bloc ({storage.blocks.length})</h4>
                              <div className="hub-table-scroll"><AutoColumns id="SiAgentView.10"><table>
                                <thead><tr><th>Nom</th><th>Type</th><th>Taille</th><th>FS</th><th>Montage</th><th>Modèle</th></tr></thead>
                                <tbody>{storage.blocks.map((b) => (
                                  <tr key={b.name}><td style={{ paddingLeft: 8 + b.depth * 16 }}><code>{b.name}</code>{b.removable && <> <span className="na-chip">amovible</span></>}</td><td className="muted">{b.type}{b.media ? ` · ${b.media}` : ""}</td><td>{b.size}</td><td className="muted">{b.fstype}</td><td><code>{b.mountpoint}</code></td><td className="muted">{b.model}</td></tr>
                                ))}</tbody>
                              </table></AutoColumns></div>
                            </>
                          )}
                        </>
                      )}
                    </>
                  )}

                  {section.ports && (
                    <>
                      <h3>Ports en écoute ({ports.length}){host.ports?.available === false && <> · <Tone tone="warn">ss indisponible</Tone></>}</h3>
                      <div className="hub-table-scroll">
                        <AutoColumns id="SiAgentView.11"><table>
                          <thead><tr><th>Proto</th><th>Port</th><th>Adresse</th><th>Processus</th><th>Exposition</th></tr></thead>
                          <tbody>{ports.map((p, i) => (
                            <tr key={i}><td>{p.proto}</td><td><strong>{p.port}</strong></td><td><code>{p.address}</code></td><td>{p.process || <span className="muted">—</span>}</td><td>{p.exposed ? <Tone tone="warn">toutes interfaces</Tone> : <span className="muted">local</span>}</td></tr>
                          ))}</tbody>
                        </table></AutoColumns>
                      </div>
                    </>
                  )}

                  {section.services && (
                    <>
                      <h3>Services systemd en échec ({host.services?.failed?.length || 0}){host.services?.available === false && <> · <Tone tone="warn">systemctl indisponible</Tone></>}</h3>
                      {host.services?.failed?.length ? <ul>{host.services.failed.map((u) => <li key={u}><code>{u}</code></li>)}</ul> : <p className="muted">Aucune.</p>}
                    </>
                  )}

                  {section.logs && (
                    <>
                      <h3>Erreurs du journal 24 h ({host.logs?.lines?.length || 0}) <span className="muted" style={{ textTransform: "none", letterSpacing: 0 }}>· source {host.logs?.source || "—"}</span></h3>
                      {host.logs?.lines?.length ? <pre className="sa-log">{host.logs.lines.slice(0, 50).join("\n")}</pre> : <p className="muted">Aucune.</p>}
                      {/* #929 : vue d'ensemble « ce qui s'est passé sur ce poste » -- les dernières commandes aussi, le détail est dans l'onglet Historique. */}
                      <h3 style={{ marginTop: 12 }}>Dernières commandes <button type="button" className="secondary" style={{ marginLeft: 6 }} onClick={() => setOnglet("historique")}>tout l'historique ↗</button></h3>
                      {!detail.commands?.length ? <p className="muted">Aucune commande envoyée à cet agent.</p> : (
                        <div className="hub-table-scroll">
                          <table><thead><tr><th>Quand</th><th>Commande</th><th>État</th></tr></thead>
                            <tbody>{detail.commands.slice(0, 10).map((c) => (
                              <tr key={c.id}>
                                <td className="muted">{when(c.created_at)}</td>
                                <td>{COMMAND_TYPES.find((t) => t.type === c.type)?.label || c.type}{c.params?.id && <> <code>{c.params.id}</code></>}</td>
                                <td><Tone tone={c.status === "done" ? "good" : c.status === "failed" ? "bad" : "warn"}>{c.status === "done" ? "acquittée" : c.status === "failed" ? "échec" : "en attente"}</Tone>
                                  {c.status === "failed" && c.result?.error && <> <BoutonDetail titre={`Échec : ${COMMAND_TYPES.find((t) => t.type === c.type)?.label || c.type}`} urgence="critique" texte={c.result.error} /></>}</td>
                              </tr>))}</tbody>
                          </table>
                        </div>
                      )}
                    </>
                  )}

                  {section.control && (
                    <HostControlSection apiBase={siAgentApiBase} agentId={selectedId} detail={detail} fleet={fleet} host={host} when={when} onRefresh={() => loadDetail && loadDetail(selectedId)} />
                  )}

                  </>)}

                  {section.plugins && (
                    <>
                      <h3>Sondes (plugins) sur cet hôte</h3>
                      <div className="ups-toolbar" style={{ margin: "0 0 6px" }}>
                        <select value={assignId} onChange={(e) => setAssignId(e.target.value)}>
                          <option value="">— affecter une sonde du catalogue —</option>
                          {assignable.map((p) => <option key={p.id} value={p.id}>{p.id} v{p.version} ({p.runner})</option>)}
                        </select>
                        <button className="secondary" onClick={handleAssign} disabled={!assignId}>Affecter</button>
                        {catalogue.length === 0 && <span className="muted">catalogue vide -- onglet « Catalogue de sondes »</span>}
                      </div>
                      {plugins.length === 0 ? <p className="muted">Aucune sonde affectée ni présente.</p> : (
                        <div className="hub-table-scroll">
                          <AutoColumns id="SiAgentView.12"><table>
                            <thead><tr><th>Sonde</th><th>Version</th><th>Origine</th><th>Central</th><th>Sur l'hôte</th><th>Blocage</th><th>Dernier résultat</th><th className="ups-actions-head"></th></tr></thead>
                            <tbody>{plugins.map((p) => {
                              const last = detail.latest?.[`plugin:${p.id}`];
                              return (
                                <tr key={p.id}>
                                  <td><strong>{p.id}</strong>{p.description && <div className="muted" style={{ fontSize: 11 }}>{p.description}</div>}</td>
                                  <td>{p.version || "—"}</td>
                                  <td className="muted">{p.assigned ? "catalogue" : p.source === "bundled" ? "livrée avec l'agent" : p.source || "—"}</td>
                                  <td>{p.assigned ? <label className="ups-form-check" style={{ fontSize: 12 }}><input type="checkbox" checked={!!p.enabled_central} onChange={() => handleAssignedToggle(p)} /> activée</label> : <span className="muted">non affectée</span>}</td>
                                  <td>{p.present ? <Tone tone={p.enabled_host ? "good" : "neutral"}>{p.enabled_host ? "active" : "présente, inactive"}</Tone> : <span className="muted">pas encore reçue</span>}{p.privileged && <div><Tone tone="warn" title="tourne en root sur l'hôte (drapeau signé par le central)">privilégiée</Tone></div>}</td>
                                  <td>
                                    {p.assigned ? (
                                      <label className="ups-form-check" style={{ fontSize: 12 }}><input type="checkbox" checked={!!p.blocked_central} onChange={() => handlePluginBlock(p)} /> bloquée</label>
                                    ) : <span className="muted">—</span>}
                                    {p.blocked_host && <div><Tone tone="bad">bloquée sur l'hôte</Tone></div>}
                                  </td>
                                  <td className="muted" title={last?.error || ""}>{last?.error && <BoutonDetail titre={`Dernier résultat : ${p.id}`} urgence={last.ok ? "info" : "critique"} texte={last.error} />}{last ? <><Tone tone={last.ok ? "good" : "bad"}>{last.ok ? "✔" : "✖"}</Tone> {when(last.at)}</> : "—"}</td>
                                  <td className="ups-actions">
                                    {p.assigned && <button className="secondary" onClick={() => handleUnassign(p)}>Retirer</button>}
                                    <button className="secondary" title="lancer cette sonde maintenant sur l'hôte" onClick={async () => { const r = await sendCommand(siAgentApiBase, selectedId, "run_plugin", { id: p.id }); if (r?.error) { setError(r.error); return; } setNotice(`Sonde ${p.id} lancée — résultat d'ici 1 min (voir Historique).`); loadDetail(selectedId); }}>Exécuter…</button>
                                  </td>
                                </tr>
                              );
                            })}</tbody>
                          </table></AutoColumns>
                        </div>
                      )}
                    </>
                  )}

                  {/* #929 : onglet « Commandes à distance » -- autorisation (désactivées / lecture seule / intervention)
                      ET exécution (analyses + commande libre) au même endroit. Le seul endroit où l'on agit en direct. */}
                  {section.distance && (
                    <>
                      <h3>Commandes à distance</h3>
                      <p className="muted" style={{ margin: "0 0 6px", textTransform: "none", letterSpacing: 0 }}>
                        Depuis le hub, on peut faire exécuter des commandes d'analyse sur ce poste. Choisis d'abord ce qui est autorisé,
                        puis lance une analyse en un clic ou une commande libre. En <b>lecture seule</b>, le poste refuse de lui-même toute
                        commande qui modifierait quelque chose.
                      </p>
                      <fieldset className="sa-autorisation" style={{ border: "1px solid var(--border)", borderRadius: 6, padding: "8px 10px", margin: "0 0 10px" }}>
                        <legend style={{ padding: "0 6px", fontSize: 12 }}>Autorisation des commandes à distance sur ce poste</legend>
                        {[["off", "Désactivées", "aucune commande à distance n'est acceptée"],
                          ["lecture", "Lecture seule", "seules les commandes qui ne modifient rien (analyses, relevés)"],
                          ["intervention", "Intervention", "autorise aussi les commandes qui modifient le poste — confirmé et journalisé"]].map(([v, lab, aide]) => (
                          <label key={v} className="ups-form-check" style={{ display: "block", margin: "2px 0" }} title={aide}>
                            <input type="radio" name="remote-shell" checked={(detail.remote_shell || "off") === v} onChange={() => handleRemoteShell(v)} />
                            {" "}<b>{lab}</b> <span className="muted" style={{ textTransform: "none", letterSpacing: 0 }}>— {aide}</span>
                          </label>))}
                      </fieldset>
                      {(detail.remote_shell || "off") === "off"
                        ? <p className="muted">Commandes à distance désactivées : choisis « Lecture seule » ci-dessus pour lancer des analyses.</p>
                        : <AnalyseDistance key={detail.remote_shell} agent={selectedId} base={siAgentApiBase} actor={actor} masquerModeLigne />}
                    </>
                  )}

                  {/* #936 : section Sauvegardes dans la fiche agent -- gestion de sauvegarde par poste (Windows) :
                      confs + montages -> clé USB / partage / PBS, et restauration (intervention). */}
                  {section.sauvegardes && (
                    <>
                      <h3>Sauvegardes</h3>
                      {/windows/i.test(detail?.os || "") || detail?.poste ? (
                        <Sauvegarde agent={selectedId} base={siAgentApiBase} actor={actor} mode={sauvegardeMode} />
                      ) : (
                        <p className="muted" style={{ textTransform: "none", letterSpacing: 0 }}>
                          La sauvegarde par agent (configurations logicielles + montages) concerne les postes Windows (sonde poste-windows).
                          Pour les serveurs et VM, voir la tuile <b>Sauvegardes</b> (récapitulatif PBS / copies / BackupPC / NAS) et <b>Migration › Copies et sauvegardes</b>.
                        </p>
                      )}
                    </>
                  )}

                  {/* #929 : ancien onglet « Commandes » -> « Historique » (lecture). La console générique passe en
                      « Actions avancées » repliée, pour ne pas la perdre, mais elle n'est plus la porte d'entrée. */}
                  {section.commands && (
                    <>
                      <h3>Historique des commandes</h3>
                      <p className="muted" style={{ margin: "0 0 6px", textTransform: "none", letterSpacing: 0 }}>
                        Ce qui a été envoyé à cet agent et le résultat. Pour agir en direct : onglet <b>Commandes à distance</b> ;
                        pour lancer/activer une sonde : onglet <b>Sondes</b>.
                        <button type="button" className="secondary" style={{ marginLeft: 8 }} onClick={refreshCommands}>⟳ Rafraîchir</button>
                      </p>
                      {!detail.commands?.length ? <p className="muted">Aucune commande envoyée à cet agent.</p> : (
                        <div className="hub-table-scroll">
                          <AutoColumns id="SiAgentView.13"><table>
                            <thead><tr><th>Quand</th><th>Commande</th><th>État</th><th>Résultat</th></tr></thead>
                            <tbody>{detail.commands.map((c) => (
                              <tr key={c.id}>
                                <td className="muted">{when(c.created_at)}</td>
                                <td>{COMMAND_TYPES.find((t) => t.type === c.type)?.label || c.type}{c.params?.id && <> <code>{c.params.id}</code></>}</td>
                                <td><Tone tone={c.status === "done" ? "good" : c.status === "failed" ? "bad" : "warn"}>{c.status === "done" ? "acquittée" : c.status === "failed" ? "échec" : "en attente"}</Tone></td>
                                <td className="muted" title={c.result ? JSON.stringify(c.result) : ""}>
                                  <div className="sa-cel-flex">
                                    <BoutonDetail titre={`Résultat : ${COMMAND_TYPES.find((t) => t.type === c.type)?.label || c.type}${c.params?.id ? " " + c.params.id : ""} (${when(c.created_at)})`}
                                      urgence={c.status === "failed" ? "critique" : "info"} texte={c.result ? (c.result.error || JSON.stringify(c.result.result ?? c.result, null, 2)) : ""} />
                                    <span className="sa-resultat-txt">{c.result?.error || (c.result?.result ? JSON.stringify(c.result.result) : "")}</span>
                                  </div>
                                </td>
                              </tr>
                            ))}</tbody>
                          </table></AutoColumns>
                        </div>
                      )}
                      <details style={{ marginTop: 10 }}>
                        <summary className="muted" style={{ cursor: "pointer" }}>Actions avancées (envoyer une commande de maintenance)</summary>
                        <p className="muted" style={{ margin: "6px 0", textTransform: "none", letterSpacing: 0 }}>
                          Rarement utile directement : la plupart de ces actions se font depuis leur onglet (Sondes, Poste, et « Mises à jour » en tête de la Flotte).
                        </p>
                        <div className="ups-toolbar" style={{ margin: "0 0 6px" }}>
                          <select value={cmdType} onChange={(e) => setCmdType(e.target.value)}>
                            {COMMAND_TYPES.map((c) => <option key={c.type} value={c.type}>{c.label}</option>)}
                          </select>
                          {COMMAND_TYPES.find((c) => c.type === cmdType)?.needsPlugin && (
                            <select value={cmdPlugin} onChange={(e) => setCmdPlugin(e.target.value)}>
                              <option value="">— sonde —</option>
                              {plugins.map((p) => <option key={p.id} value={p.id}>{p.id}</option>)}
                            </select>
                          )}
                          <button className="primary" onClick={handleCommand}>▶ Envoyer</button>
                        </div>
                      </details>
                    </>
                  )}

                  {section.settings && settings && (
                    <form onSubmit={handleSaveSettings}>
                      <h3>Réglages poussés à l'agent</h3>
                      <div className="ups-form-grid">
                        <label>Libellé <input value={settings.label} onChange={(e) => setSettings({ ...settings, label: e.target.value })} /></label>
                        <label>Site <input value={settings.site} onChange={(e) => setSettings({ ...settings, site: e.target.value })} required /></label>
                        <label>Intervalle hôte (s) <input type="number" min="10" value={settings.host_interval_seconds} onChange={(e) => setSettings({ ...settings, host_interval_seconds: e.target.value })} /></label>
                        <label>Seuils de risques (JSON) <input value={settings.thresholds} onChange={(e) => setSettings({ ...settings, thresholds: e.target.value })} placeholder='{"disk_warning_percent": 80}' /></label>
                        <label className="ups-form-wide">Notes <input value={settings.notes} onChange={(e) => setSettings({ ...settings, notes: e.target.value })} /></label>
                        <label><input type="checkbox" checked={!!settings.filter_enabled} onChange={(e) => setSettings({ ...settings, filter_enabled: e.target.checked })} /> Filtrer les alertes (#607)</label>
                        <label>Groupe de filtres <input value={settings.filter_group} onChange={(e) => setSettings({ ...settings, filter_group: e.target.value })} placeholder="postes-travail" list="sa-filter-groups" /><datalist id="sa-filter-groups"><option value="postes-travail" /><option value="silencieux" /></datalist></label>
                      </div>
                      {/* #929 : l'autorisation des commandes à distance a quitté Réglages pour son propre onglet. */}
                      <p className="muted" style={{ margin: "6px 0", textTransform: "none", letterSpacing: 0 }}>Autorisation des commandes à distance (désactivées / lecture seule / intervention) : onglet <button type="button" className="secondary" onClick={() => setOnglet("distance")}>Commandes à distance</button>.</p>
                      <h3 style={{ marginTop: 10 }}>Page d'état publiée sur le réseau du site</h3>
                      <p className="muted" style={{ margin: "0 0 6px" }}>L'agent sert sur son LAN une page « santé du réseau » (tableau Nebula du site), sans connexion ; le hub l'affiche en aperçu et en réel (Pages ouvertes → voir).</p>
                      <div className="ups-form-grid">
                        <label><input type="checkbox" checked={!!settings.pub_enabled} onChange={(e) => setSettings({ ...settings, pub_enabled: e.target.checked })} /> Publier</label>
                        <label>Port <input type="number" min="1024" max="65535" value={settings.pub_port} onChange={(e) => setSettings({ ...settings, pub_port: e.target.value })} /></label>
                        <label>Titre <input value={settings.pub_title} onChange={(e) => setSettings({ ...settings, pub_title: e.target.value })} /></label>
                        <label>Site Nebula (id, vide = tous) <input value={settings.pub_site_id} onChange={(e) => setSettings({ ...settings, pub_site_id: e.target.value })} /></label>
                        <label>Fenêtre (h) <input type="number" min="1" max="744" value={settings.pub_hours} onChange={(e) => setSettings({ ...settings, pub_hours: e.target.value })} /></label>
                        <label className="ups-form-wide">Lien « tableau de bord complet » (hub) <input value={settings.pub_hub_url} onChange={(e) => setSettings({ ...settings, pub_hub_url: e.target.value })} placeholder="https://<hub>:6443/?view=nebula" /></label>
                      </div>
                      <p className="muted" style={{ margin: "6px 0" }}>Clés de seuils : disk_warning_percent, disk_critical_percent, memory_warning_percent, swap_warning_percent, load_per_cpu_warning, recent_boot_seconds, log_errors_warning.</p>
                      <button type="submit" className="primary">Enregistrer</button>
                    </form>
                  )}
                </>
              )}
            </div>
          )}
        </>
      )}

      {tab === "risks" && (
        <>
          <h2 style={{ margin: "0 0 8px" }}>Risques internes de la flotte ({risks.length})</h2>
          {risks.length === 0 ? <p className="muted">Aucun constat sur les agents ayant remonté des mesures.</p> : (
            <div className="hub-table-scroll">
              <AutoColumns id="SiAgentView.14"><table>
                <thead><tr><th>Sévérité</th><th>Agent</th><th>Site</th><th>Constat</th><th>Détail</th><th>Relevé</th></tr></thead>
                <tbody>{risks.map((r, i) => (
                  <tr key={i} className="ups-row" onClick={() => { setTab("fleet"); setSelectedId(r.agent_id); }}>
                    <td><Tone tone={severityTone(r.severity)}>{r.severity}</Tone></td>
                    <td><strong>{r.agent_id}</strong>{r.hostname && <div className="muted" style={{ fontSize: 11 }}>{r.hostname}</div>}</td>
                    <td>{r.site}</td>
                    <td>{riskLabel(r.id)}{r.subject && <> <code>{r.subject}</code></>}</td>
                    <td>{r.message}</td>
                    <td className="muted">{when(r.at)}</td>
                  </tr>
                ))}</tbody>
              </table></AutoColumns>
            </div>
          )}
        </>
      )}

      {tab === "events" && (
        <>
          <div className="ups-toolbar" style={{ marginTop: 0 }}>
            <h2 style={{ margin: 0 }}>Journal des événements</h2>
            {summary && (
              <span className="muted" style={{ fontSize: 13 }}>
                24 h : <Tone tone={summary.counts.critical ? "bad" : "neutral"}>{summary.counts.critical} critique(s)</Tone>, <Tone tone={summary.counts.warning ? "warn" : "neutral"}>{summary.counts.warning} avertissement(s)</Tone>, {summary.counts.info} info
                {summary.agents_offline?.length > 0 && <> · <Tone tone="bad">hors ligne : {summary.agents_offline.join(", ")}</Tone></>}
                {summary.agents_blocked?.length > 0 && <> · <Tone tone="warn">bloqués : {summary.agents_blocked.join(", ")}</Tone></>}
              </span>
            )}
          </div>
          <div className="ups-timeline-controls">
            <label>Sévérité min.
              <select value={evFilter.minSeverity} onChange={(e) => setEvFilter({ ...evFilter, minSeverity: e.target.value })}>
                {EVENT_SEVERITIES.map((sv) => <option key={sv} value={sv}>{sv}</option>)}
              </select>
            </label>
            <label>Agent
              <select value={evFilter.agent} onChange={(e) => setEvFilter({ ...evFilter, agent: e.target.value })}>
                <option value="">tous</option>
                {fleet.map((a) => <option key={a.agent_id} value={a.agent_id}>{a.agent_id}</option>)}
              </select>
            </label>
            <label><input type="checkbox" checked={evFilter.securityOnly} onChange={(e) => setEvFilter({ ...evFilter, securityOnly: e.target.checked })} /> sécurité seulement</label>
            <label title="#607 : événements filtrés par le groupe de leur agent (journal seulement)"><input type="checkbox" checked={!!evFilter.showMuted} onChange={async (e) => { setEvFilter({ ...evFilter, showMuted: e.target.checked }); setEvents(e.target.checked ? await fetchEventsMuted(siAgentApiBase, 300) : await fetchEvents(siAgentApiBase, { limit: 300 })); }} /> afficher les filtrées{summary?.muted ? ` (${summary.muted} sur 24 h)` : ""}</label>
            <label>Recherche <input value={evFilter.text} onChange={(e) => setEvFilter({ ...evFilter, text: e.target.value })} placeholder="genre, message, agent" /></label>
            <OrderSwitch value={eventsOrder} onChange={setEventsOrder} />
          </div>
          {(() => {
            const shown = orderItems(filterEvents(events, evFilter), eventsOrder, { name: (e) => e.agent_id || e.kind, date: (e) => e.at, severity: (e) => e.severity, tie: (e) => e.message });
            const sm = summarizeEvents(shown);
            return shown.length === 0 ? <p className="muted">Aucun événement pour ces critères.</p> : (
              <>
                <p className="muted" style={{ margin: "4px 0" }}>{sm.total} événement(s) affiché(s) : {sm.agent} remonté(s) par les agents, {sm.central} du central, {sm.security} liés à la sécurité.</p>
                <div className="hub-table-scroll sa-events">
                  <AutoColumns id="SiAgentView.15"><table>
                    <thead><tr><th>Quand</th><th>Sévérité</th><th>Agent</th><th>Événement</th><th>Message</th><th>Source</th><th>Notifié</th></tr></thead>
                    <tbody>{shown.map((e) => (
                      <tr key={e.id} className={`ups-row${isSecurityEvent(e) ? " sa-event-security" : ""}`} style={{ opacity: e.muted ? 0.55 : 1 }} onClick={() => { if (e.agent_id) { setTab("fleet"); setSelectedId(e.agent_id); } }} title={e.muted ? `filtré : ${e.muted_by}` : e.details && Object.keys(e.details).length ? JSON.stringify(e.details) : ""}>
                        <td className="muted" style={{ whiteSpace: "nowrap" }}>{when(e.at)}</td>
                        <td><Tone tone={severityTone(e.severity)}>{e.severity === "critical" ? "⛔" : e.severity === "warning" ? "⚠" : "ℹ"} {e.severity}</Tone></td>
                        <td>{e.agent_id ? <strong>{e.agent_id}</strong> : <span className="muted">central</span>}</td>
                        <td>{isSecurityEvent(e) && <span title="sécurité">🔒 </span>}{eventKindLabel(e.kind)}</td>
                        <td>{e.muted ? <span className="muted">[filtré] </span> : null}{e.message}</td>
                        <td className="muted">{e.source}</td>
                        <td className="muted" style={{ fontSize: 11 }}>{e.notified ? Object.entries(e.notified).filter(([k]) => k !== "at").map(([k, v]) => `${k}${v ? "✔" : "✖"}`).join(" ") : ""}</td>
                      </tr>
                    ))}</tbody>
                  </table></AutoColumns>
                </div>
              </>
            );
          })()}
        </>
      )}

      {tab === "banc" && <BancSection base={siAgentApiBase} />}
      {tab === "updates" && <><UpdatesTab base={siAgentApiBase} /><DiffusionsSection base={siAgentApiBase} /></>}
      {tab === "webaudit" && <WebAuditTab base={siAgentApiBase} fleet={fleet} when={when} />}
      {tab === "netobs" && <NetworkObservabilityTab base={siAgentApiBase} fleet={fleet} when={when} />}
      {tab === "deploy" && <DeployTab base={siAgentApiBase} fleet={fleet} catalogue={catalogue} login="" notice={(t) => { setError(null); setNotice(t); }} error={(t) => { setNotice(null); setError(t); }} />}
      {tab === "rotations" && <RotationsTab base={siAgentApiBase} fleet={fleet} catalogue={catalogue} notice={(t, ok = true) => (ok ? setNotice(t) : setError(t))} />}
      {tab === "filters" && <AlertFiltersTab base={siAgentApiBase} fleet={fleet} onChanged={load} notice={(t, ok = true) => (ok ? setNotice(t) : setError(t))} />}

      {tab === "catalogue" && (
        <>
          <div className="ups-toolbar" style={{ marginTop: 0 }}>
            <h2 style={{ margin: 0 }}>Catalogue de sondes</h2>
            <button className="secondary" onClick={() => (showPluginForm ? setShowPluginForm(false) : openPluginCreate())}>{showPluginForm ? "✕ Fermer" : "+ Nouvelle sonde"}</button>
          </div>
          <p className="muted" style={{ margin: "0 0 8px" }}>Une sonde = un script shell ou Python qui écrit un JSON sur sa sortie standard. Affectée à un agent, elle lui est poussée signée (HMAC avec le secret de l'agent) et exécutée à son intervalle ; son résultat remonte comme mesure <code>plugin:&lt;id&gt;</code>.</p>

          {showPluginForm && (
            <form className="hub-card hub-settings-section ups-form" onSubmit={handleSavePlugin}>
              <h3 style={{ marginTop: 0 }}>{catalogue.some((p) => p.id === pluginForm.id) ? `Modifier « ${pluginForm.id} »` : "Nouvelle sonde"}</h3>
              <div className="ups-form-grid">
                <label>Identifiant <input value={pluginForm.id} onChange={(e) => setPluginForm({ ...pluginForm, id: e.target.value, entry: pluginForm.entry || defaultEntry(pluginForm.runner, e.target.value) })} required placeholder="disk-smart" /></label>
                <label>Version <input value={pluginForm.version} onChange={(e) => setPluginForm({ ...pluginForm, version: e.target.value })} placeholder="1" /></label>
                <label>Runner
                  <select value={pluginForm.runner} onChange={(e) => setPluginForm({ ...pluginForm, runner: e.target.value, entry: defaultEntry(e.target.value, pluginForm.id) })}>
                    <option value="shell">shell (bash)</option><option value="python">python (python3)</option>
                  </select>
                </label>
                <label>Fichier d'entrée <input value={pluginForm.entry} onChange={(e) => setPluginForm({ ...pluginForm, entry: e.target.value })} required /></label>
                <label>Intervalle (s) <input type="number" min="30" value={pluginForm.interval_seconds} onChange={(e) => setPluginForm({ ...pluginForm, interval_seconds: e.target.value })} /></label>
                <label>Délai max (s) <input type="number" min="1" value={pluginForm.timeout_seconds} onChange={(e) => setPluginForm({ ...pluginForm, timeout_seconds: e.target.value })} /></label>
                <label>Arguments <input value={pluginForm.args} onChange={(e) => setPluginForm({ ...pluginForm, args: e.target.value })} placeholder="séparés par des espaces" /></label>
                <label>Mémoire max (Mo) <input type="number" min="16" value={pluginForm.max_memory_mb} onChange={(e) => setPluginForm({ ...pluginForm, max_memory_mb: e.target.value })} placeholder="512 (défaut)" /></label>
                <label className="ups-form-check"><input type="checkbox" checked={!!pluginForm.privileged} onChange={(e) => setPluginForm({ ...pluginForm, privileged: e.target.checked })} /> privilégiée (root sur l'hôte)</label>
                <label className="ups-form-wide">Description <input value={pluginForm.description} onChange={(e) => setPluginForm({ ...pluginForm, description: e.target.value })} /></label>
                <label className="ups-form-wide">Script
                  <textarea className="sa-script" value={pluginForm.body} onChange={(e) => setPluginForm({ ...pluginForm, body: e.target.value })} rows={12} spellCheck={false}
                    placeholder={pluginForm.runner === "python" ? "import json\nprint(json.dumps({\"ok\": True}))" : "#!/bin/bash\necho '{\"ok\": true}'"} />
                </label>
              </div>
              <p className="muted" style={{ margin: "8px 0" }}>Changer le script ou la version fait re-signer et re-pousser la sonde à tous les agents affectés. Par défaut la sonde tourne <strong>sans privilège</strong> (utilisateur `nobody`, environnement minimal, mémoire et délai bornés) ; « privilégiée » = root sur l'hôte, drapeau couvert par la signature du central et journalisé.</p>
              <button type="submit" className="primary" disabled={busy}>Enregistrer au catalogue</button>
            </form>
          )}

          {catalogue.length === 0 ? <p className="muted">Catalogue vide -- « + Nouvelle sonde ». Les sondes livrées avec l'agent (network-neighbors, docker-containers) sont sur chaque hôte, désactivées, indépendamment du catalogue.</p> : (
            <div className="hub-table-scroll">
              <AutoColumns id="SiAgentView.16"><table>
                <thead><tr><th>Sonde</th><th>Version</th><th>Runner</th><th>Intervalle</th><th>Agents affectés</th><th>Mise à jour</th><th className="ups-actions-head"></th></tr></thead>
                <tbody>{orderItems(catalogue, "alpha", { name: (p) => p.id }).map((p) => (
                  <tr key={p.id}>
                    <td><strong>{p.id}</strong>{p.description && <div className="muted" style={{ fontSize: 11 }}>{p.description}</div>}</td>
                    <td>{p.version}</td>
                    <td>{p.runner} · <code>{p.entry}</code>{p.privileged && <> · <Tone tone="warn">privilégiée</Tone></>}</td>
                    <td>{formatAge(p.interval_seconds)}</td>
                    <td>{p.assigned_agents}</td>
                    <td className="muted">{when(p.updated_at)}</td>
                    <td className="ups-actions">
                      <button className="secondary" onClick={() => openPluginEdit(p)}>Modifier</button>
                      <button className="secondary" onClick={() => handleDeletePlugin(p)}>Retirer</button>
                    </td>
                  </tr>
                ))}</tbody>
              </table></AutoColumns>
            </div>
          )}
        </>
      )}
    </div>
  );
}


// #522 : déploiement contrôlé des mises à jour d'agents -- version servie
// par le central (archive construite dans l'image), état de chaque agent,
// canal bêta (cases), activation générale, planification auto ou bouton.
function UpdatesTab({ base }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const take = (r) => { if (r && r.error) setError(r.error); else { setData(r); setError(null); } };
  const load = useCallback(async () => { take(await fetchUpdates(base)); }, [base]);
  useEffect(() => { load(); const t = setInterval(load, 30000); return () => clearInterval(t); }, [load]);
  if (!data) return <p className="muted">{error || "Chargement…"}</p>;
  const s = data.settings || {};
  const pkg = data.package;
  const setSettings = async (patch) => {
    setBusy(true);
    take(await saveUpdates(base, { ...s, ...patch }, "hub")); setBusy(false);
  };
  const apply = async (agentId) => {
    setBusy(true);
    take(await applyUpdates(base, agentId, "hub")); setBusy(false);
  };
  // #891 : « Tout mettre à jour » -- même geste que le bouton de chaque ligne, enchaîné sur tous les agents en retard
  // (éligibles, non éligibles, en échec), sans dépendre du canal bêta ni de l'activation générale.
  const enRetard = (data?.agents || []).filter((a) => ["eligible", "not-eligible", "failed"].includes(a.status));
  const applyAll = async () => {
    if (!enRetard.length || !window.confirm(`Mettre à jour ${enRetard.length} agent(s) vers ${pkg.version} maintenant ?\n${enRetard.map((a) => a.agent_id).join(", ")}`)) return;
    setBusy(true);
    let ok = 0, ko = [];
    for (const a of enRetard) {
      const r = await applyUpdates(base, a.agent_id, "hub");
      if (r && r.error) ko.push(`${a.agent_id} : ${r.error}`); else ok += 1;
    }
    setError(ko.length ? `${ok} commande(s) envoyée(s), ${ko.length} échec(s) — ${ko.join(" ; ")}` : null);
    take(await fetchUpdates(base)); setBusy(false);
  };
  const toggleBeta = (id) => {
    const beta = new Set(s.beta_agents || []);
    if (beta.has(id)) beta.delete(id); else beta.add(id);
    setSettings({ beta_agents: [...beta] });
  };
  const STATUS = { "up-to-date": ["à jour", "good"], newer: ["plus récent que le central", "neutral"], unknown: ["version inconnue", "neutral"], pending: ["commande envoyée", "warn"],
    started: ["installation lancée", "warn"], stalled: ["installeur lancé, sans effet — voir Événements (agent-update-failed) et le journal update-*.log de l'agent", "bad"], failed: ["échec (réessai plus tard)", "bad"], eligible: ["à planifier", "warn"], "not-eligible": ["en attente d'activation", "neutral"], "no-package": ["archive absente", "bad"] };
  const agents = data.agents || [];
  const counts = data.counts || {};
  return (
    <>
      <div className="ups-toolbar" style={{ marginTop: 0 }}>
        <h2 style={{ margin: 0 }}>Mises à jour des agents</h2>
        <button className="secondary" onClick={load} disabled={busy}>⟳</button>
        {pkg && <button onClick={applyAll} disabled={busy || !enRetard.length} title="envoie la mise à jour à chaque agent en retard, comme le bouton de sa ligne">
          {busy ? "envoi…" : enRetard.length ? `Tout mettre à jour (${enRetard.length})` : "Tous à jour"}</button>}
        {error && <Tone tone="bad">{error}</Tone>}
      </div>
      <p className="muted" style={{ fontSize: 13 }}>
        {pkg ? <>Version servie par le central : <strong>{pkg.version}</strong> ({formatBytes(pkg.size)}, SHA-256 <code>{pkg.sha256.slice(0, 16)}…</code>)</> : <Tone tone="bad">aucune archive dans l'image du central</Tone>}
        {" · "}{agents.length} agent(s) : {Object.entries(counts).map(([k, v]) => `${v} ${(STATUS[k] || [k])[0]}`).join(", ") || "—"}
      </p>
      <div className="hub-card" style={{ padding: 10, marginBottom: 10 }}>
        <p style={{ margin: "0 0 6px" }}><strong>Déploiement contrôlé</strong> — 1. cochez un ou deux agents « bêta » ci-dessous ; 2. quand ils sont passés à jour sans incident, activez pour tous.</p>
        <label style={{ display: "inline-flex", gap: 6, alignItems: "center", marginRight: 16 }}>
          <input type="checkbox" checked={!!s.general_enabled} disabled={busy} onChange={(e) => { if (!e.target.checked || window.confirm("Activer la mise à jour pour TOUS les agents (hors bêta) ?")) setSettings({ general_enabled: e.target.checked }); }} />
          Activation générale (tous les agents)
        </label>
        <label style={{ display: "inline-flex", gap: 6, alignItems: "center", marginRight: 16 }}>
          <input type="checkbox" checked={!!s.auto} disabled={busy} onChange={(e) => setSettings({ auto: e.target.checked })} />
          Planification automatique (dès qu'un agent éligible dépose son inventaire)
        </label>
        <button onClick={() => apply(null)} disabled={busy || !pkg}>Appliquer maintenant aux agents éligibles</button>
        {s.updated_at && <span className="muted" style={{ fontSize: 12 }}> · réglages modifiés {formatAge(ageSeconds(s.updated_at))} par {s.updated_by || "?"}</span>}
      </div>
      <AutoColumns id="SiAgentView.17"><table className="sa-table">
        <thead><tr><th title="canal bêta : ces agents reçoivent une nouvelle version en premier, lors de la planification automatique ; sans effet sur les boutons « Mettre à jour »">Bêta ⓘ</th><th>Agent</th><th>Hôte</th><th>Site</th><th>Version</th><th>État</th><th>Dernière commande</th><th></th></tr></thead>
        <tbody>
          {orderItems(agents, "alpha", { name: (a) => a.agent_id }).map((a) => {
            const [label, tone] = STATUS[a.status] || [a.status, "neutral"];
            return (
              <tr key={a.agent_id} className="ups-row">
                <td><input type="checkbox" checked={(s.beta_agents || []).includes(a.agent_id)} disabled={busy} onChange={() => toggleBeta(a.agent_id)} title="canal bêta : reçoit la nouvelle version en premier" /></td>
                <td><code>{a.agent_id}</code></td>
                <td>{a.hostname || "—"}</td>
                <td className="muted" title={a.site || ""}><span className="sa-site">{a.site || "—"}</span></td>
                <td>{a.version || "?"}</td>
                <td><Tone tone={tone}>{label}</Tone>{a.channel === "beta" && <span className="muted" style={{ fontSize: 11 }}> · bêta</span>}</td>
                <td className="muted" style={{ fontSize: 12 }}>{a.last ? <>{a.last.to} · {a.last.status}{a.last.acked_at ? ` · acquittée ${formatAge(ageSeconds(a.last.acked_at))}` : a.last.created_at ? ` · envoyée ${formatAge(ageSeconds(a.last.created_at))}` : ""}{a.last.result && a.last.result.error ? ` · ${a.last.result.error}` : ""}</> : "—"}</td>
                <td>{(a.status === "eligible" || a.status === "not-eligible" || a.status === "failed") && pkg && <button className="secondary" disabled={busy} onClick={() => { if (window.confirm(`Mettre à jour ${a.agent_id} vers ${pkg.version} maintenant ?`)) apply(a.agent_id); }}>Mettre à jour</button>}</td>
              </tr>
            );
          })}
        </tbody>
      </table></AutoColumns>
      <p className="muted" style={{ fontSize: 12 }}>L'agent télécharge l'archive par sa liaison TLS habituelle, vérifie le SHA-256, lance son installeur en mode <code>--upgrade</code> (configuration, secret, CA et sondes conservés) détaché de son processus, acquitte « installation lancée », redémarre puis signale <code>agent-updated</code> (ou <code>agent-update-failed</code>) dans les événements ; sa nouvelle version apparaît à l'inventaire suivant.</p>
    </>
  );
}
