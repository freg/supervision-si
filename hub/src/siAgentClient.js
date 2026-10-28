// Client API vers si-agent-api (livraison #421) -- tuile « Agents hôtes ».
// Même motif que upsClient.js : jamais d'exception vers le composant,
// toujours un objet (`{error}` en cas d'échec) ou une liste vide.

async function fetchJson(apiBase, path, options) {
  try {
    const res = await fetch(`${apiBase}${path}`, options);
    let data = null;
    try {
      data = await res.json();
    } catch {
      data = null;
    }
    if (data === null) {
      return { error: `Réponse invalide du serveur (HTTP ${res.status})` };
    }
    if (!res.ok && data && typeof data === "object" && !data.error) {
      return { ...data, error: `HTTP ${res.status}` };
    }
    return data;
  } catch (err) {
    return { error: `Requête échouée : ${err.message}` };
  }
}

const json = (method, body) => ({
  method,
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body || {}),
});

export const fetchSiAgentStatus = (apiBase) => fetchJson(apiBase, "/status");

/** #884 : VPN WireGuard (état courant + sessions reconstituées). */
export async function fetchVpn(apiBase, days = 30) {
  try {
    const r = await fetch(`${apiBase}/vpn?days=${days}`, { credentials: "include" });
    const d = await r.json();
    return { serveurs: d?.serveurs || [], sessions: d?.sessions || [] };
  } catch { return { serveurs: [], sessions: [] }; }
}

/** #894 : messages syslog conservés par rsyslog-listener (même origine que le hub, via tls-proxy). */
export async function fetchSyslog(params = {}) {
  const q = new URLSearchParams(Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== "")).toString();
  try {
    const [e, m] = await Promise.all([
      fetch("/api/rsyslog-listener/journaux/emetteurs", { credentials: "include" }).then((r) => r.json()),
      fetch(`/api/rsyslog-listener/journaux?${q}`, { credentials: "include" }).then((r) => r.json()),
    ]);
    return { info: e || {}, messages: m?.messages || [], error: m?.error || null };
  } catch (err) { return { info: {}, messages: [], error: String(err) }; }
}

/** #883 : NAS relevés par SNMP (sonde nas-snmp). */
export async function fetchNas(apiBase) {
  try {
    const r = await fetch(`${apiBase}/nas`, { credentials: "include" });
    const d = await r.json();
    return Array.isArray(d?.nas) ? d.nas : [];
  } catch { return []; }
}

/** #876 : hôtes relevés à distance par un agent relais (sonde systemes), affichés sous leur relais dans la Flotte. */
export async function fetchRelayedHosts(apiBase) {
  try {
    const r = await fetch(`${apiBase}/relayed-hosts`, { credentials: "include" });
    const d = await r.json();
    return Array.isArray(d?.hosts) ? d.hosts : [];
  } catch { return []; }
}

export async function fetchFleet(apiBase, site) {
  const data = await fetchJson(apiBase, `/fleet${site ? `?site=${encodeURIComponent(site)}` : ""}`);
  return Array.isArray(data?.agents) ? data.agents : [];
}

// #432 : vue réseau passive de chaque agent (voisins, pairs, sous-réseaux)
export async function fetchNetviews(apiBase, site) {
  const data = await fetchJson(apiBase, `/netview${site ? `?site=${encodeURIComponent(site)}` : ""}`);
  return Array.isArray(data?.netviews) ? data.netviews : [];
}

// #487 : hyperviseurs Proxmox (dernière mesure du plugin par agent)
export async function fetchProxmox(apiBase, site) {
  const data = await fetchJson(apiBase, `/proxmox${site ? `?site=${encodeURIComponent(site)}` : ""}`);
  return Array.isArray(data?.proxmox) ? data.proxmox : [];
}

// #643 : panneau Observabilité réseau -- dernière mesure dns-observe (105) et
// resource-access (106) par agent, en un seul appel.
export async function fetchNetworkObservability(apiBase, site) {
  const data = await fetchJson(apiBase, `/network-observability${site ? `?site=${encodeURIComponent(site)}` : ""}`);
  return { dns: Array.isArray(data?.dns) ? data.dns : [], resources: Array.isArray(data?.resources) ? data.resources : [] };
}

// #504 : disponibilité des VM d'un hyperviseur (échantillons du plugin)
export const fetchProxmoxHistory = (apiBase, agentId, hours = 168) =>
  fetchJson(apiBase, `/proxmox/history?agent_id=${encodeURIComponent(agentId)}&hours=${hours}`);

export async function fetchFleetRisks(apiBase) {
  const data = await fetchJson(apiBase, "/risks");
  return Array.isArray(data?.risks) ? data.risks : [];
}

export const fetchAgent = (apiBase, agentId) => fetchJson(apiBase, `/agents/${encodeURIComponent(agentId)}`);
export const createAgent = (apiBase, body) => fetchJson(apiBase, "/agents", json("POST", body));
export const updateAgent = (apiBase, agentId, body) => fetchJson(apiBase, `/agents/${encodeURIComponent(agentId)}`, json("PUT", body));
export const deleteAgent = (apiBase, agentId, purge) => fetchJson(apiBase, `/agents/${encodeURIComponent(agentId)}${purge ? "?purge=true" : ""}`, { method: "DELETE" });
export const rotateAgentSecret = (apiBase, agentId) => fetchJson(apiBase, `/agents/${encodeURIComponent(agentId)}/rotate-secret`, json("POST", {}));
export const fetchInstall = (apiBase, agentId) => fetchJson(apiBase, `/agents/${encodeURIComponent(agentId)}/install`);
// #446 : fichier .cmd silencieux (secret inclus) généré par le central
export const installCmdUrl = (apiBase, agentId) => `${apiBase}/agents/${encodeURIComponent(agentId)}/install.cmd`;

export async function fetchAgentMeasurements(apiBase, agentId, { task, limit = 200, since } = {}) {
  const q = new URLSearchParams();
  if (task) q.set("task", task);
  if (limit) q.set("limit", String(limit));
  if (since) q.set("since", since);
  const data = await fetchJson(apiBase, `/agents/${encodeURIComponent(agentId)}/measurements?${q.toString()}`);
  return Array.isArray(data?.measurements) ? data.measurements : [];
}

export async function fetchPlugins(apiBase) {
  const data = await fetchJson(apiBase, "/plugins");
  return Array.isArray(data?.plugins) ? data.plugins : [];
}
export const fetchPlugin = (apiBase, pluginId) => fetchJson(apiBase, `/plugins/${encodeURIComponent(pluginId)}?body=true`);
export const savePlugin = (apiBase, body) => fetchJson(apiBase, "/plugins", json("POST", body));
export const deletePlugin = (apiBase, pluginId) => fetchJson(apiBase, `/plugins/${encodeURIComponent(pluginId)}`, { method: "DELETE" });

export const assignPlugin = (apiBase, agentId, pluginId, enabled = true) =>
  fetchJson(apiBase, `/agents/${encodeURIComponent(agentId)}/plugins/${encodeURIComponent(pluginId)}`, json("PUT", { enabled }));
export const unassignPlugin = (apiBase, agentId, pluginId) =>
  fetchJson(apiBase, `/agents/${encodeURIComponent(agentId)}/plugins/${encodeURIComponent(pluginId)}`, { method: "DELETE" });

export const sendCommand = (apiBase, agentId, type, params) =>
  fetchJson(apiBase, `/agents/${encodeURIComponent(agentId)}/commands`, json("POST", { type, params: params || {} }));
export async function fetchCommands(apiBase, agentId) {
  const data = await fetchJson(apiBase, `/agents/${encodeURIComponent(agentId)}/commands?limit=30`);
  return Array.isArray(data?.commands) ? data.commands : [];
}

// #422 : blocage, journal d'événements, synthèse, notifications
export const blockFleet = (apiBase, reason) => fetchJson(apiBase, "/block", json("POST", { reason }));
export const unblockFleet = (apiBase) => fetchJson(apiBase, "/unblock", json("POST", {}));
export const blockAgent = (apiBase, agentId, reason) => fetchJson(apiBase, `/agents/${encodeURIComponent(agentId)}/block`, json("POST", { reason }));
export const unblockAgent = (apiBase, agentId) => fetchJson(apiBase, `/agents/${encodeURIComponent(agentId)}/unblock`, json("POST", {}));
export const setPluginBlocked = (apiBase, agentId, pluginId, blocked, reason) =>
  fetchJson(apiBase, `/agents/${encodeURIComponent(agentId)}/plugins/${encodeURIComponent(pluginId)}`, json("PUT", { blocked, reason }));

export async function fetchEvents(apiBase, { agent, severity, minSeverity, kind, since, limit = 200 } = {}) {
  const q = new URLSearchParams();
  if (agent) q.set("agent", agent);
  if (severity) q.set("severity", severity);
  if (minSeverity) q.set("min_severity", minSeverity);
  if (kind) q.set("kind", kind);
  if (since) q.set("since", since);
  if (limit) q.set("limit", String(limit));
  const data = await fetchJson(apiBase, `/events?${q.toString()}`);
  return Array.isArray(data?.events) ? data.events : [];
}
/** #522 : déploiement contrôlé des mises à jour d'agents. */
export const fetchUpdates = (apiBase) => fetchJson(apiBase, "/updates");
export const saveUpdates = (apiBase, settings, actor) => fetchJson(apiBase, "/updates", json("PUT", { ...settings, actor }));
export const applyUpdates = (apiBase, agentId, actor) => fetchJson(apiBase, "/updates/apply", json("POST", { agent_id: agentId || null, actor }));

export const fetchEventsSummary = (apiBase, hours = 24) => fetchJson(apiBase, `/events/summary?hours=${hours}`);
export const testNotifications = (apiBase) => fetchJson(apiBase, "/notifications/test", json("POST", {}));

// #572 : contrôle d'une VM Proxmox par l'agent (commande vm_action) et suivi du résultat
export const vmAction = (apiBase, agentId, params) => sendCommand(apiBase, agentId, "vm_action", params);
// #613 : poste -- alimentation (reboot/shutdown/cancel), réveil par un agent du même segment, lanceurs, chien de garde
export const powerAction = (apiBase, agentId, params) => sendCommand(apiBase, agentId, "power_action", params);
export const wakeOnLan = (apiBase, viaAgentId, params) => sendCommand(apiBase, viaAgentId, "wol", params);
export const startupAction = (apiBase, agentId, params) => sendCommand(apiBase, agentId, "startup_action", params);
export const watchdogConfig = (apiBase, agentId, params) => sendCommand(apiBase, agentId, "watchdog_config", params);
export const benchCommand = (apiBase, agentId, params) => sendCommand(apiBase, agentId, "bench", params);  // #616
export const imageHost = (apiBase, agentId, params) => sendCommand(apiBase, agentId, "image_host", params);  // #621
export const browsePath = (apiBase, agentId, path) => sendCommand(apiBase, agentId, "browse", path ? { path } : {});  // #627
export const imageTransfer = (apiBase, agentId, params) => sendCommand(apiBase, agentId, "image_transfer", params);  // #634
// #836 : VM à la demande (clones de modèles Proxmox, durée de vie)
export const fetchVmsDemande = (apiBase) => fetchJson(apiBase, "/orchestration/vms");
export const saveVmsConfig = (apiBase, cfg) => fetchJson(apiBase, "/orchestration/vms/config", json("PUT", cfg));
export const createVmDemande = (apiBase, body) => fetchJson(apiBase, "/orchestration/vms", json("POST", body));
export const vmDemandeGeste = (apiBase, vmid, geste) => fetchJson(apiBase, `/orchestration/vms/${vmid}/${geste}`, json("POST", {}));
export const fetchImages = (apiBase, site) => fetchJson(apiBase, `/images${site ? `?site=${encodeURIComponent(site)}` : ""}`);  // #634
export const fetchWebAudit = (apiBase, site) => fetchJson(apiBase, `/web-audit${site ? `?site=${encodeURIComponent(site)}` : ""}`);  // #617
export const fetchCommand = (apiBase, cid) => fetchJson(apiBase, `/commands/${encodeURIComponent(cid)}`);

/** #607 : filtres d'alertes (catégories, groupes de règles), test à blanc ; `include_muted` sur le journal. */
export const fetchAlertFilters = (apiBase) => fetchJson(apiBase, "/alert-filters");
export const saveAlertFilters = (apiBase, groups) => fetchJson(apiBase, "/alert-filters", json("PUT", { groups }));
export const testAlertFilter = (apiBase, body) => fetchJson(apiBase, "/alert-filters/test", json("POST", body));
export async function fetchEventsMuted(apiBase, limit = 300) {
  const data = await fetchJson(apiBase, `/events?include_muted=1&limit=${limit}`);
  return Array.isArray(data?.events) ? data.events : [];
}

// #709 : session interactive -- l'agent relève ses commandes toutes les ~3 s tant qu'elle vit (renouvelée par la vue)
export const openInteractive = (apiBase, agentId, seconds = 300) => fetchJson(apiBase, `/agents/${encodeURIComponent(agentId)}/interactive`, json("POST", { seconds }));
export const closeInteractive = (apiBase, agentId) => fetchJson(apiBase, `/agents/${encodeURIComponent(agentId)}/interactive`, json("POST", { close: true }));

// #705 : maintenance / réorganisation des Proxmox (campagnes, avancement constaté, planification, sauvegardes)
export const fetchMaintCatalog = (apiBase) => fetchJson(apiBase, "/maint/catalog");
export const fetchMaintCampaigns = (apiBase) => fetchJson(apiBase, "/maint/campaigns");
export const fetchMaintCampaign = (apiBase, id) => fetchJson(apiBase, `/maint/campaigns/${id}`);
export const createMaintCampaign = (apiBase, body) => fetchJson(apiBase, "/maint/campaigns", json("POST", body));
export const updateMaintCampaign = (apiBase, id, body) => fetchJson(apiBase, `/maint/campaigns/${id}`, json("PUT", body));
export const deleteMaintCampaign = (apiBase, id) => fetchJson(apiBase, `/maint/campaigns/${id}`, { method: "DELETE" });
export const maintAction = (apiBase, id, aid, body) => fetchJson(apiBase, `/maint/campaigns/${id}/actions/${aid}`, json("POST", body));
export const maintTemplate = (apiBase, kind, body) => fetchJson(apiBase, `/maint/templates/${kind}`, json("POST", body));
export const fetchMaintBackups = (apiBase) => fetchJson(apiBase, "/maint/backups");

// #653 : plans PRA / opérations PVE (séquences de vm_action exécutées par le central)
export const fetchPraPlans = (apiBase) => fetchJson(apiBase, "/pra/plans");
export const createPraPlan = (apiBase, body) => fetchJson(apiBase, "/pra/plans", json("POST", body));
export const updatePraPlan = (apiBase, id, body) => fetchJson(apiBase, `/pra/plans/${id}`, json("PUT", body));
export const deletePraPlan = (apiBase, id) => fetchJson(apiBase, `/pra/plans/${id}`, { method: "DELETE" });
export const runPraPlan = (apiBase, id, mode, actor) => fetchJson(apiBase, `/pra/plans/${id}/run`, json("POST", { mode, actor }));
export const fetchPraRun = (apiBase, rid) => fetchJson(apiBase, `/pra/runs/${rid}`);
export const fetchPraRuns = (apiBase, id) => fetchJson(apiBase, `/pra/plans/${id}/runs`);
// #654 : rôles (bascule « celui qui répond ») et vérification
export const fetchPraRoles = (apiBase) => fetchJson(apiBase, "/pra/roles");
export const createPraRole = (apiBase, body) => fetchJson(apiBase, "/pra/roles", json("POST", body));
export const updatePraRole = (apiBase, id, body) => fetchJson(apiBase, `/pra/roles/${id}`, json("PUT", body));
export const deletePraRole = (apiBase, id) => fetchJson(apiBase, `/pra/roles/${id}`, { method: "DELETE" });
export const switchPraRole = (apiBase, id, to, actor) => fetchJson(apiBase, `/pra/roles/${id}/switch`, json("POST", { to, actor }));
export const checkPraRole = (apiBase, id) => fetchJson(apiBase, `/pra/roles/${id}/check`, { method: "POST" });
// #658 : migration serveur -> virtualisation (plan généré), transitions (Reprendre / Abandonner), retour en arrière
export const previewMigration = (apiBase, body) => fetchJson(apiBase, "/pra/migrations/plan", json("POST", body));
export const resumePraRun = (apiBase, rid) => fetchJson(apiBase, `/pra/runs/${rid}/resume`, { method: "POST" });
export const abortPraRun = (apiBase, rid, rollback, actor) => fetchJson(apiBase, `/pra/runs/${rid}/abort`, json("POST", { rollback, actor }));
export const rollbackPraRun = (apiBase, rid, actor) => fetchJson(apiBase, `/pra/runs/${rid}/rollback`, json("POST", { actor }));

// #743 : tournées de mesures réparties (supervision distribuée)
export const fetchRotations = (apiBase) => fetchJson(apiBase, "/rotations");
export const saveRotation = (apiBase, body, id) => fetchJson(apiBase, id ? `/rotations/${id}` : "/rotations", json(id ? "PUT" : "POST", body));
export const deleteRotation = (apiBase, id) => fetchJson(apiBase, `/rotations/${id}`, { method: "DELETE" });
export const fetchRotationRuns = (apiBase, id) => fetchJson(apiBase, `/rotations/${id}/runs?limit=100`);
export const fetchInfraOverview = (apiBase) => fetchJson(apiBase, "/infra/overview");   // #749
export const fetchHtop = (apiBase) => fetchJson(apiBase, "/htop");   // #800 : relais si-htop
export const fetchDataRf = (apiBase) => fetchJson(apiBase, "/datarf");   // #806 : sondes radio des sites
export const fetchDataRfConfig = (apiBase, sonde) => fetchJson(apiBase, `/datarf/config?sonde=${encodeURIComponent(sonde)}`);   // #807
export const sendDataRfConfig = (apiBase, body) => fetchJson(apiBase, "/datarf/config", json("POST", body));
export const fetchHtopHote = (apiBase, nom) => fetchJson(apiBase, `/htop/hote/${encodeURIComponent(nom)}`);
export const fetchGuestUsage = (apiBase) => fetchJson(apiBase, "/infra/guests");   // #769 : activité des CT / VM
export const saveGuestProfile = (apiBase, node, vmid, profile, actor) => fetchJson(apiBase, "/infra/guests/profile", json("PUT", { node, vmid, profile, actor }));
export const fetchEdge = (apiBase) => fetchJson(apiBase, "/edge");   // #776 : proxys d'entrée
export const fetchEdgePreview = (apiBase) => fetchJson(apiBase, "/edge/preview");
export const saveEdgeProxy = (apiBase, proxy, actor) => fetchJson(apiBase, "/edge/proxies", json("PUT", { proxy, actor }));
export const saveEdgeRoute = (apiBase, route, actor) => fetchJson(apiBase, "/edge/routes", json("PUT", { route, actor }));
export const deleteEdge = (apiBase, what, id, actor) => fetchJson(apiBase, `/edge/${what}/${encodeURIComponent(id)}?actor=${encodeURIComponent(actor || "")}`, { method: "DELETE" });
export const switchEdge = (apiBase, route, backend, actor) => fetchJson(apiBase, "/edge/switch", json("POST", { route, backend, actor }));
export const saveEdgeSettings = (apiBase, settings, actor) => fetchJson(apiBase, "/edge/settings", json("PUT", { settings, actor }));
export const applyEdge = (apiBase, actor) => fetchJson(apiBase, "/edge/apply", json("POST", { actor }));
export const checkEdgeDns = (apiBase) => fetchJson(apiBase, "/edge/dns-check", json("POST", {}));
export const fetchLatency = (apiBase) => fetchJson(apiBase, "/latency");   // #775 : latence des IP publiques
export const fetchLatencyHistory = (apiBase, target, point, hours = 24) => fetchJson(apiBase, `/latency/history?target=${encodeURIComponent(target)}&point=${encodeURIComponent(point)}&hours=${hours}`);
export const saveLatencyTarget = (apiBase, target, actor) => fetchJson(apiBase, "/latency/targets", json("PUT", { target, actor }));
export const saveLatencyPoint = (apiBase, point, actor) => fetchJson(apiBase, "/latency/points", json("PUT", { point, actor }));
export const deleteLatency = (apiBase, what, id) => fetchJson(apiBase, `/latency/${what}/${encodeURIComponent(id)}`, { method: "DELETE" });
export const saveLatencySettings = (apiBase, settings) => fetchJson(apiBase, "/latency/settings", json("PUT", settings));
export const runLatency = (apiBase, point) => fetchJson(apiBase, "/latency/run", json("POST", { point }));
export const fetchLatencyConfig = (apiBase) => fetchJson(apiBase, "/latency/config");
export const importLatencyConfig = (apiBase, config, actor) => fetchJson(apiBase, "/latency/config", json("PUT", { ...config, actor }));
export const fetchMigration = (apiBase) => fetchJson(apiBase, "/migration");   // #774 : tuile « Migration 2026-2027 »
export const fetchMigrationPrep = (apiBase, qs) => fetchJson(apiBase, `/migration/preparation${qs ? `?${qs}` : ""}`);   // #815 : préparer la réinstallation d'un nœud
export const fetchCopies = (apiBase) => fetchJson(apiBase, "/copies/inventaire");   // #856 : toutes les copies et leur distance à la source
export const saveCopiesRegles = (apiBase, regles) => fetchJson(apiBase, "/copies/regles", json("PUT", { regles }));
export const fetchRisques = (apiBase) => fetchJson(apiBase, "/migration/risques");   // #856 : risque permanent par CT / VM
export const saveAccesCibles = (apiBase, key, cibles) => fetchJson(apiBase, "/migration/acces", json("PUT", { key, cibles }));
export const verifierAcces = (apiBase) => fetchJson(apiBase, "/migration/acces/verifier", json("POST", {}));
export const saveMigrationCible = (apiBase, cible) => fetchJson(apiBase, "/migration/cible", json("PUT", { cible }));
export const fetchEtat = (apiBase) => fetchJson(apiBase, "/etat-des-lieux");   // #857 : état des lieux des systèmes
export const saveEtatLibelles = (apiBase, libelles) => fetchJson(apiBase, "/etat-des-lieux/libelles", json("PUT", { libelles }));
export const saveEtatManuel = (apiBase, key, fiche) => fetchJson(apiBase, "/etat-des-lieux/manuel", json("PUT", { key, fiche }));   // #858
export const saveEtatDecisions = (apiBase, decisions) => fetchJson(apiBase, "/etat-des-lieux/decisions", json("PUT", { decisions }));   // #862
export const saveEtatPhases = (apiBase, phases) => fetchJson(apiBase, "/etat-des-lieux/phases", json("PUT", { phases }));   // #863
export const saveEtatEol = (apiBase, eol) => fetchJson(apiBase, "/etat-des-lieux/eol", json("PUT", { eol }));
export const etatExportUrl = (apiBase) => `${apiBase}/etat-des-lieux/export.xlsx`;
export const etatAuditUrl = (apiBase) => `${apiBase}/etat-des-lieux/audit.html`;   // #860
export const saveEtatRegroupement = (apiBase, r) => fetchJson(apiBase, "/etat-des-lieux/regroupements", json("PUT", r));   // #879
export const fetchEtatBareme = (apiBase) => fetchJson(apiBase, "/etat-des-lieux/bareme");   // #882 : pesage
export const saveEtatBareme = (apiBase, b) => fetchJson(apiBase, "/etat-des-lieux/bareme", json("PUT", b));
export const fetchEtatPlan = (apiBase) => fetchJson(apiBase, "/etat-des-lieux/plan");   // #878 : temps estimés, phases, Gantt
export const saveEtatPlan = (apiBase, r) => fetchJson(apiBase, "/etat-des-lieux/plan", json("PUT", r));
export const saveMigrationPlan = (apiBase, plan, actor) => fetchJson(apiBase, "/migration/plan", json("PUT", { plan, actor }));
export const saveMigrationVars = (apiBase, vars, actor) => fetchJson(apiBase, "/migration/vars", json("PUT", { vars, actor }));
export const migrationControl = (apiBase, action, step, actor, onglet = "") => fetchJson(apiBase, "/migration/control", json("POST", { action, step, actor, onglet }));
export const fetchViews = (apiBase) => fetchJson(apiBase, "/views");   // #753 : vues de parc
export const saveViews = (apiBase, views, actor) => fetchJson(apiBase, "/views", json("PUT", { views, actor }));
export const fetchViewOverview = (apiBase, id) => fetchJson(apiBase, `/views/${encodeURIComponent(id)}/overview`);
export const fetchIaOverview = (apiBase) => fetchJson(apiBase, "/ia/overview");   // #756 : Parc IA
export const saveIaHosts = (apiBase, agents) => fetchJson(apiBase, "/ia/hosts", json("PUT", { agents }));
export const fetchIaAssistant = (apiBase, sub) => fetchJson(apiBase, `/ia/assistant/${sub}`);
export const fetchDiagTasks = (apiBase, tasks) => fetchJson(apiBase, `/diag/tasks?tasks=${encodeURIComponent(tasks.join(","))}`);   // #763
export const fetchRepatriations = (apiBase) => fetchJson(apiBase, "/repatriation");   // #761 : assistant de rapatriement
export const createRepatriation = (apiBase, body) => fetchJson(apiBase, "/repatriation", json("POST", body));
export const fetchRepatriation = (apiBase, id) => fetchJson(apiBase, `/repatriation/${id}`);
export const saveRepatriation = (apiBase, id, body) => fetchJson(apiBase, `/repatriation/${id}`, json("PUT", body));
export const launchRepatriation = (apiBase, id, actor) => fetchJson(apiBase, `/repatriation/${id}/launch`, json("POST", { actor }));
export const evaluateLeftovers = (apiBase, body) => fetchJson(apiBase, "/repatriation/cleanup/evaluate", json("POST", body));   // #765
export const purgeLeftover = (apiBase, body) => fetchJson(apiBase, "/repatriation/cleanup/purge", json("POST", body));
export const repatriationGuest = (apiBase, id, vmid, action, actor) => fetchJson(apiBase, `/repatriation/${id}/guest/${vmid}/${action}`, json("POST", { actor }));
// #795 : journal des chantiers (actes, surveillances, relances, interventions)
export const fetchJournal = (apiBase, chantier) => fetchJson(apiBase, `/journal${chantier ? `?chantier=${encodeURIComponent(chantier)}` : ""}`);
export const saveJournalEntry = (apiBase, entry, actor) => fetchJson(apiBase, "/journal", json("PUT", { entry, actor }));
export const deleteJournalEntry = (apiBase, id) => fetchJson(apiBase, `/journal/${encodeURIComponent(id)}`, { method: "DELETE" });
export const importJournal = (apiBase, payload, actor) => fetchJson(apiBase, "/journal/import", json("POST", { ...payload, actor }));
export const journalExportUrl = (apiBase, chantier) => `${apiBase}/journal/export.csv${chantier ? `?chantier=${encodeURIComponent(chantier)}` : ""}`;
export const fetchJournalSuggestions = (apiBase, days = 30) => fetchJson(apiBase, `/journal/suggestions?days=${days}`);
export const acceptJournalSuggestion = (apiBase, eventId, chantier, actor) => fetchJson(apiBase, `/journal/suggestions/${encodeURIComponent(eventId)}`, json("POST", { chantier, actor }));
// #798 : navigateurs des hôtes (écran web + automate)
export const fetchNavigateurs = (apiBase) => fetchJson(apiBase, "/navigateurs");
export const saveNavigateurs = (apiBase, navigateurs, actor) => fetchJson(apiBase, "/navigateurs", json("PUT", { navigateurs, actor }));
export const navCommand = (apiBase, agentId, params) => sendCommand(apiBase, agentId, "navigateur", params);
// #799/#800 : parcours appris, jeu, demande en langage courant
export const fetchParcours = (apiBase) => fetchJson(apiBase, "/parcours");
export const createParcours = (apiBase, parcours, actor) => fetchJson(apiBase, "/parcours", json("POST", { parcours, actor }));
export const updateParcours = (apiBase, id, parcours, actor) => fetchJson(apiBase, `/parcours/${id}`, json("PUT", { parcours, actor }));
export const deleteParcours = (apiBase, id) => fetchJson(apiBase, `/parcours/${id}`, { method: "DELETE" });
export const jouerParcours = (apiBase, id, body) => fetchJson(apiBase, `/parcours/${id}/jouer`, json("POST", body));
export const interpreterDemande = (apiBase, texte) => fetchJson(apiBase, "/parcours/interpreter", json("POST", { texte }));

// #822 : diffusions en cascade (déploiement avec dépendances)
export const fetchDiffusions = (apiBase) => fetchJson(apiBase, "/diffusions");
export const saveDiffusion = (apiBase, regle) => fetchJson(apiBase, regle.id ? `/diffusions/${regle.id}` : "/diffusions", json(regle.id ? "PUT" : "POST", regle));
export const deleteDiffusion = (apiBase, id) => fetchJson(apiBase, `/diffusions/${id}`, { method: "DELETE" });
export const runDiffusion = (apiBase, id, simulation, actor) => fetchJson(apiBase, `/diffusions/${id}/executer`, json("POST", { simulation, actor }));

// #825 : banc d'installation des agents sur un pool de VM
export const fetchBanc = (apiBase) => fetchJson(apiBase, "/banc");
export const saveBancPool = (apiBase, pool) => fetchJson(apiBase, "/banc/pool", json("PUT", pool));
export const startBanc = (apiBase, modeles) => fetchJson(apiBase, "/banc/runs", json("POST", { modeles }));
export const stopBancRun = (apiBase, id) => fetchJson(apiBase, `/banc/runs/${id}/arreter`, json("POST", {}));
export const purgeBanc = (apiBase) => fetchJson(apiBase, "/banc/runs", { method: "DELETE" });
export const buildBancTemplate = (apiBase, body) => fetchJson(apiBase, "/banc/modeles", json("POST", body));   // #826
// #831 : tuile Émulation et déploiement supervisé
export const fetchEmulation = (apiBase) => fetchJson(apiBase, "/emulation");
export const sendEmulation = (apiBase, body) => fetchJson(apiBase, "/emulation/commande", json("POST", body));
// #840 : agents de messagerie si-mailbox (résumés des agents reliés)
export const fetchMailbox = (apiBase) => fetchJson(apiBase, "/mailbox");
// #832 : orchestration (VM Proxmox, k3s, Nomad)
export const fetchOrchestration = (apiBase) => fetchJson(apiBase, "/orchestration");
export const sendOrchestration = (apiBase, body) => fetchJson(apiBase, "/orchestration/commande", json("POST", body));
export const fetchOrchImages = (apiBase, q) => fetchJson(apiBase, `/orchestration/images${q ? `?q=${encodeURIComponent(q)}` : ""}`);   // #834
export const fetchImageTags = (apiBase, image) => fetchJson(apiBase, `/orchestration/images/tags?image=${encodeURIComponent(image)}`);
