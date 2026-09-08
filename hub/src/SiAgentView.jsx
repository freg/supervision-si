import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
  fetchSiAgentStatus, fetchFleet, fetchFleetRisks, fetchAgent, createAgent, updateAgent, deleteAgent,
  rotateAgentSecret, fetchInstall, fetchPlugins, fetchPlugin, savePlugin, deletePlugin, assignPlugin,
  unassignPlugin, sendCommand, fetchCommands, blockFleet, unblockFleet, blockAgent, unblockAgent, setPluginBlocked,
  fetchEvents, fetchEventsSummary, testNotifications,
} from "./siAgentClient.js";
import {
  COMMAND_TYPES, CONTACT_LABELS, riskLabel, severityTone, stateTone, contactTone, gauge, formatBytes,
  formatUptime, formatAge, ageSeconds, sortFleet, riskSummaryText, diskRows, portRows, mergePlugins,
  validatePluginForm, defaultEntry, eventKindLabel, filterEvents, summarizeEvents, isSecurityEvent, EVENT_SEVERITIES,
} from "./siAgent.js";

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

export default function SiAgentView({ onBack, siAgentApiBase }) {
  const [status, setStatus] = useState(null);
  const [fleet, setFleet] = useState([]);
  const [risks, setRisks] = useState([]);
  const [catalogue, setCatalogue] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState(null);
  const [now, setNow] = useState(Date.now());
  const [tab, setTab] = useState("fleet");
  const [busy, setBusy] = useState(false);

  const [showEnroll, setShowEnroll] = useState(false);
  const [agentForm, setAgentForm] = useState(EMPTY_AGENT_FORM);
  const [enrolled, setEnrolled] = useState(null);

  const [selectedId, setSelectedId] = useState(null);
  const [detail, setDetail] = useState(null);
  const [install, setInstall] = useState(null);
  const [cmdType, setCmdType] = useState("collect_now");
  const [cmdPlugin, setCmdPlugin] = useState("");
  const [assignId, setAssignId] = useState("");
  const [settings, setSettings] = useState(null);
  const [section, setSection] = useState({ risks: true, system: true, network: true, hardware: false, activity: false, disks: true, ports: false, services: false, logs: false, plugins: true, commands: true, settings: false });

  const [pluginForm, setPluginForm] = useState(EMPTY_PLUGIN_FORM);
  const [showPluginForm, setShowPluginForm] = useState(false);

  // #422 : journal d'événements
  const [events, setEvents] = useState([]);
  const [summary, setSummary] = useState(null);
  const [evFilter, setEvFilter] = useState({ minSeverity: "info", agent: "", securityOnly: false, text: "" });

  const load = useCallback(async () => {
    const [st, fl, rk, cat, ev, sm] = await Promise.all([
      fetchSiAgentStatus(siAgentApiBase), fetchFleet(siAgentApiBase), fetchFleetRisks(siAgentApiBase), fetchPlugins(siAgentApiBase),
      fetchEvents(siAgentApiBase, { limit: 300 }), fetchEventsSummary(siAgentApiBase, 24),
    ]);
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
    setSettings({ host_interval_seconds: d.host_interval_seconds, label: d.label || "", site: d.site || "", notes: d.notes || "",
      thresholds: JSON.stringify(d.risk_thresholds || {}, null, 0) });
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
    setInstall({ agent_id: r.agent_id, secret: r.secret, install_command: r.install_command, site: r.site });
    setNotice("Nouveau secret généré -- à reporter sur l'hôte.");
  }

  async function handleSaveSettings(e) {
    e.preventDefault();
    let thresholds = {};
    try { thresholds = settings.thresholds ? JSON.parse(settings.thresholds) : {}; } catch { setError("Seuils : JSON invalide"); return; }
    const r = await updateAgent(siAgentApiBase, selectedId, {
      host_interval_seconds: Number(settings.host_interval_seconds) || 60, label: settings.label, site: settings.site, notes: settings.notes, risk_thresholds: thresholds,
    });
    if (r?.error) { setError(r.error); return; }
    setNotice("Réglages enregistrés -- appliqués par l'agent à sa prochaine lecture de configuration (5 min au plus).");
    await load();
    loadDetail(selectedId);
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
  const sorted = useMemo(() => sortFleet(fleet), [fleet]);
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
  const ports = useMemo(() => portRows(host), [host]);
  const toggle = (k) => setSection((s) => ({ ...s, [k]: !s[k] }));

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

          {loading ? (
            <p className="muted">Chargement…</p>
          ) : sorted.length === 0 ? (
            <p className="muted">Aucun agent -- « + Enrôler un agent », puis lancer la commande d'installation sur l'hôte Linux.</p>
          ) : (
            <div className="hub-table-scroll">
              <table className="sa-fleet">
                <thead>
                  <tr><th>Agent</th><th>Site</th><th>Hôte</th><th>Contact</th><th>CPU</th><th>Mémoire</th><th>Disque (max)</th><th>Risques</th><th>Sondes</th><th className="ups-actions-head"></th></tr>
                </thead>
                <tbody>
                  {sorted.map((a) => {
                    const age = ageSeconds(a.last_seen_at, now);
                    return (
                      <tr key={a.agent_id} className={`ups-row${selectedId === a.agent_id ? " active" : ""}${a.active ? "" : " inactive"}`} onClick={() => setSelectedId(selectedId === a.agent_id ? null : a.agent_id)}>
                        <td><strong>{a.agent_id}</strong>{a.label && <div className="muted" style={{ fontSize: 11 }}>{a.label}</div>}</td>
                        <td>{a.site}</td>
                        <td>{a.hostname ? <><code>{a.hostname}</code>{a.os && <div className="muted" style={{ fontSize: 11 }}>{a.os}</div>}</> : <span className="muted">—</span>}</td>
                        <td>
                          <Tone tone={contactTone(a.online)} title={when(a.last_seen_at)}>{CONTACT_LABELS[a.online] || a.online}</Tone>
                          {age != null && <div className="muted" style={{ fontSize: 11 }}>il y a {formatAge(age)}</div>}
                          {!a.active && <div className="muted" style={{ fontSize: 11 }}>désactivé</div>}
                          {(a.blocked || a.host_blocked || status?.fleet_blocked) && <div><Tone tone="bad" title={a.blocked_reason || a.host_blocked_reason || ""}>⛔ sondes bloquées{a.host_blocked ? " (confirmé)" : ""}</Tone></div>}
                          {a.insecure_tls && <div><Tone tone="warn">TLS non vérifié</Tone></div>}
                        </td>
                        <td><Gauge percent={a.summary?.cpu_percent} label={`charge 5 min ${a.summary?.load5 ?? "—"}`} /></td>
                        <td><Gauge percent={a.summary?.memory_percent} /></td>
                        <td><Gauge percent={a.summary?.disk_max_percent} /></td>
                        <td><Tone tone={stateTone(a.risks?.state)}>{riskSummaryText(a.risks)}</Tone>{a.summary?.partial?.length > 0 && <div className="muted" style={{ fontSize: 11 }} title={a.summary.partial.join(", ")}>collecte partielle</div>}</td>
                        <td className="muted">{a.plugins_assigned > 0 ? `${a.plugins_assigned} affectée${a.plugins_assigned > 1 ? "s" : ""}` : "—"}{a.pending_commands > 0 && <div style={{ fontSize: 11 }}>{a.pending_commands} cmd en attente</div>}</td>
                        <td className="ups-actions" onClick={(e) => e.stopPropagation()}>
                          <button className="secondary" onClick={() => { setSelectedId(a.agent_id); handleInstall(a.agent_id); }}>Installation</button>
                          <button className={a.blocked ? "secondary" : "sa-danger"} onClick={() => handleBlockAgent(a)}>{a.blocked ? "Débloquer" : "Bloquer"}</button>
                          <button className="secondary" onClick={() => handleToggleActive(a)}>{a.active ? "Désactiver" : "Activer"}</button>
                          <button className="secondary" onClick={() => handleDelete(a)}>Supprimer</button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}

          {selectedId && (
            <div className="hub-card hub-settings-section ups-detail sa-detail">
              <div className="ups-toolbar" style={{ marginTop: 0 }}>
                <h2 style={{ margin: 0 }}>{selectedId}{detail?.hostname ? ` — ${detail.hostname}` : ""}</h2>
                {detail && (
                  <Tone tone={detail.config_applied ? "good" : "warn"} title={`version ${detail.config_version}`}>{detail.config_applied ? "configuration appliquée" : "configuration en attente"}</Tone>
                )}
                <span style={{ flex: 1 }} />
                <button className="secondary" onClick={() => loadDetail(selectedId)}>⟳</button>
                <button className="secondary" onClick={() => setSelectedId(null)}>✕</button>
              </div>

              {install && install.agent_id === selectedId && (
                <div className="np-secret-box hub-card" style={{ margin: "8px 0" }}>
                  <p style={{ margin: "0 0 6px" }}>Commande d'installation (secret inclus -- ne pas diffuser) :</p>
                  <pre className="np-secret">{install.install_command}</pre>
                  {install.install_command_docker && (
                    <>
                      <p className="muted" style={{ margin: "6px 0 2px", fontSize: 12 }}>Variante conteneur (l'hôte a Docker, archive <code>si-agent-agent-&lt;version&gt;.tar.gz</code>, voir <code>si-agent/agent/README-DEPLOIEMENT.md</code>) :</p>
                      <pre className="np-secret">{install.install_command_docker}</pre>
                    </>
                  )}
                  {install.install_command_windows && (
                    <>
                      <p className="muted" style={{ margin: "6px 0 2px", fontSize: 12 }}>Windows 10 / 11 — Terminal (administrateur), depuis l'archive décompressée (ne pas double-cliquer le .ps1 : le Bloc-notes s'ouvre ; <code>windows\install.cmd</code> fait l'élévation et accepte les mêmes arguments, ou pose les questions en double-clic) :</p>
                      <pre className="np-secret">{install.install_command_windows}</pre>
                    </>
                  )}
                  <div style={{ display: "flex", gap: 8, marginTop: 6 }}>
                    <button className="secondary" onClick={() => handleRotate(selectedId)}>Nouveau secret</button>
                    <button className="secondary" onClick={() => setInstall(null)}>Masquer</button>
                  </div>
                </div>
              )}

              {!detail ? <p className="muted">Chargement…</p> : !host ? (
                <p className="muted">Aucune mesure reçue de cet agent pour l'instant{detail.last_seen_at ? "" : " -- il n'a jamais contacté le central : vérifier l'installation, l'URL du central et le secret"}.</p>
              ) : (
                <>
                  <div className="sa-sections">
                    {[["risks", "Risques"], ["system", "Système"], ["network", "Réseau vu de l'hôte"], ["hardware", "Matériel"], ["activity", "Activité"], ["disks", "Disques"], ["ports", "Ports"], ["services", "Services"], ["logs", "Journal"], ["plugins", "Sondes"], ["commands", "Commandes"], ["settings", "Réglages"]].map(([k, l]) => (
                      <button key={k} className={`secondary na-section-toggle${section[k] ? " active" : ""}`} onClick={() => toggle(k)}>{l}</button>
                    ))}
                    <span className="muted" style={{ fontSize: 12, marginLeft: "auto" }}>mesure du {when(detail.latest.host.at)}{host.partial?.length > 0 && <> · <Tone tone="warn">partielle : {host.partial.join(", ")}</Tone></>}</span>
                  </div>

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
                        <div><span className="muted">Agent</span>v{detail.agent_version || "?"} · dernière IP {detail.last_ip || "—"}{inventory?.tools?.available && <> · outils : {inventory.tools.available.join(", ")}</>}</div>
                      </div>
                    </>
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
                                  <table>
                                    <thead><tr><th>IP</th><th>Conn.</th><th>Ports</th><th>Processus</th><th>Portée</th></tr></thead>
                                    <tbody>{netview.summary.peers.slice(0, 40).map((p) => (
                                      <tr key={p.ip}><td><code>{p.ip}</code></td><td>{p.connections}</td><td className="muted">{p.ports.join(", ")}</td><td>{p.processes.join(", ") || "—"}</td><td>{p.local === true ? "sous-réseau local" : p.local === false ? <Tone tone="neutral">distant / routé</Tone> : "—"}</td></tr>
                                    ))}</tbody>
                                  </table>
                                </div>
                              ) : <p className="muted">Aucune connexion établie au moment de la mesure.</p>}
                            </div>
                            <div>
                              <h4>Voisins ARP / NDP ({netview.neighbors?.length || 0}){netview.summary?.neighbors_outside_attached?.length > 0 && <> · <Tone tone="warn">{netview.summary.neighbors_outside_attached.length} hors sous-réseau attaché</Tone></>}</h4>
                              {netview.neighbors?.length ? (
                                <div className="hub-table-scroll" style={{ maxHeight: 220 }}>
                                  <table>
                                    <thead><tr><th>IP</th><th>MAC</th><th>Interface</th><th>État</th></tr></thead>
                                    <tbody>{netview.neighbors.slice(0, 60).map((n, i) => (
                                      <tr key={i}><td><code>{n.ip}</code></td><td className="muted">{n.mac || "—"}</td><td>{n.dev}</td><td>{n.state}</td></tr>
                                    ))}</tbody>
                                  </table>
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
                          <div><span className="muted">CPU</span>{hardware.cpu?.model || "—"}{hardware.cpu?.cpus ? ` · ${hardware.cpu.cpus} CPU` : ""}{hardware.cpu?.sockets ? ` (${hardware.cpu.sockets} socket, ${hardware.cpu.cores_per_socket} cœurs, ${hardware.cpu.threads_per_core} fils)` : ""}{hardware.cpu?.arch ? ` · ${hardware.cpu.arch}` : ""}</div>
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
                              <table>
                                <thead><tr><th>PID</th><th>Utilisateur</th><th>CPU</th><th>Mém.</th><th>Commande</th></tr></thead>
                                <tbody>{(activity.top_cpu || []).map((p) => <tr key={p.pid}><td>{p.pid}</td><td>{p.user}</td><td>{p.cpu_percent} %</td><td>{formatBytes(p.rss_bytes)}</td><td><code>{p.command}</code></td></tr>)}</tbody>
                              </table>
                            </div>
                            <h4>Processus (mémoire)</h4>
                            <div className="hub-table-scroll" style={{ maxHeight: 200 }}>
                              <table>
                                <thead><tr><th>PID</th><th>Utilisateur</th><th>Mém.</th><th>CPU</th><th>Commande</th></tr></thead>
                                <tbody>{(activity.top_memory || []).map((p) => <tr key={p.pid}><td>{p.pid}</td><td>{p.user}</td><td>{formatBytes(p.rss_bytes)}</td><td>{p.cpu_percent} %</td><td><code>{p.command}</code></td></tr>)}</tbody>
                              </table>
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
                        <table>
                          <thead><tr><th>Montage</th><th>Périphérique</th><th>Type</th><th>Utilisé</th><th>Total</th><th>Remplissage</th></tr></thead>
                          <tbody>{disks.map((d) => (
                            <tr key={d.mountpoint}><td><code>{d.mountpoint}</code>{d.remote && <> <span className="na-chip">distant</span></>}{d.readonly && <> <span className="na-chip" title="lecture seule : ne peut pas se remplir, jamais un risque">lecture seule</span></>}{d.removable && <> <span className="na-chip" title="support amovible ou image montée : information seulement">amovible</span></>}</td><td className="muted">{d.device}</td><td className="muted">{d.fstype}{d.measuredAs && <> <span title={`montage FUSE réservé à son utilisateur : mesuré en se présentant comme ${d.measuredAs}`}>({d.measuredAs})</span></>}</td><td>{d.used}</td><td>{d.total}</td><td>{d.gauge ? <Gauge percent={d.gauge.percent} /> : <Tone tone="warn" title={d.error || ""}>{d.invisible ? "invisible du conteneur" : "illisible"}{d.error ? ` — ${d.error}` : ""}</Tone>}</td></tr>
                          ))}</tbody>
                        </table>
                      </div>
                    </>
                  )}

                  {section.ports && (
                    <>
                      <h3>Ports en écoute ({ports.length}){host.ports?.available === false && <> · <Tone tone="warn">ss indisponible</Tone></>}</h3>
                      <div className="hub-table-scroll">
                        <table>
                          <thead><tr><th>Proto</th><th>Port</th><th>Adresse</th><th>Processus</th><th>Exposition</th></tr></thead>
                          <tbody>{ports.map((p, i) => (
                            <tr key={i}><td>{p.proto}</td><td><strong>{p.port}</strong></td><td><code>{p.address}</code></td><td>{p.process || <span className="muted">—</span>}</td><td>{p.exposed ? <Tone tone="warn">toutes interfaces</Tone> : <span className="muted">local</span>}</td></tr>
                          ))}</tbody>
                        </table>
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
                    </>
                  )}

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
                          <table>
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
                                  <td className="muted" title={last?.error || ""}>{last ? <><Tone tone={last.ok ? "good" : "bad"}>{last.ok ? "✔" : "✖"}</Tone> {when(last.at)}</> : "—"}</td>
                                  <td className="ups-actions">
                                    {p.assigned && <button className="secondary" onClick={() => handleUnassign(p)}>Retirer</button>}
                                    <button className="secondary" onClick={() => { setCmdType("run_plugin"); setCmdPlugin(p.id); setSection((s) => ({ ...s, commands: true })); }}>Exécuter…</button>
                                  </td>
                                </tr>
                              );
                            })}</tbody>
                          </table>
                        </div>
                      )}
                    </>
                  )}

                  {section.commands && (
                    <>
                      <h3>Commandes</h3>
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
                        <button className="secondary" onClick={refreshCommands}>⟳ Résultats</button>
                      </div>
                      {!detail.commands?.length ? <p className="muted">Aucune commande.</p> : (
                        <div className="hub-table-scroll">
                          <table>
                            <thead><tr><th>Quand</th><th>Commande</th><th>État</th><th>Résultat</th></tr></thead>
                            <tbody>{detail.commands.map((c) => (
                              <tr key={c.id}>
                                <td className="muted">{when(c.created_at)}</td>
                                <td>{COMMAND_TYPES.find((t) => t.type === c.type)?.label || c.type}{c.params?.id && <> <code>{c.params.id}</code></>}</td>
                                <td><Tone tone={c.status === "done" ? "good" : c.status === "failed" ? "bad" : "warn"}>{c.status === "done" ? "acquittée" : c.status === "failed" ? "échec" : "en attente"}</Tone></td>
                                <td className="muted" style={{ fontSize: 11, maxWidth: 420, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }} title={c.result ? JSON.stringify(c.result) : ""}>
                                  {c.result?.error || (c.result?.result ? JSON.stringify(c.result.result) : "")}
                                </td>
                              </tr>
                            ))}</tbody>
                          </table>
                        </div>
                      )}
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
              <table>
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
              </table>
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
            <label>Recherche <input value={evFilter.text} onChange={(e) => setEvFilter({ ...evFilter, text: e.target.value })} placeholder="genre, message, agent" /></label>
          </div>
          {(() => {
            const shown = filterEvents(events, evFilter);
            const sm = summarizeEvents(shown);
            return shown.length === 0 ? <p className="muted">Aucun événement pour ces critères.</p> : (
              <>
                <p className="muted" style={{ margin: "4px 0" }}>{sm.total} événement(s) affiché(s) : {sm.agent} remonté(s) par les agents, {sm.central} du central, {sm.security} liés à la sécurité.</p>
                <div className="hub-table-scroll sa-events">
                  <table>
                    <thead><tr><th>Quand</th><th>Sévérité</th><th>Agent</th><th>Événement</th><th>Message</th><th>Source</th><th>Notifié</th></tr></thead>
                    <tbody>{shown.map((e) => (
                      <tr key={e.id} className={`ups-row${isSecurityEvent(e) ? " sa-event-security" : ""}`} onClick={() => { if (e.agent_id) { setTab("fleet"); setSelectedId(e.agent_id); } }} title={e.details && Object.keys(e.details).length ? JSON.stringify(e.details) : ""}>
                        <td className="muted" style={{ whiteSpace: "nowrap" }}>{when(e.at)}</td>
                        <td><Tone tone={severityTone(e.severity)}>{e.severity === "critical" ? "⛔" : e.severity === "warning" ? "⚠" : "ℹ"} {e.severity}</Tone></td>
                        <td>{e.agent_id ? <strong>{e.agent_id}</strong> : <span className="muted">central</span>}</td>
                        <td>{isSecurityEvent(e) && <span title="sécurité">🔒 </span>}{eventKindLabel(e.kind)}</td>
                        <td>{e.message}</td>
                        <td className="muted">{e.source}</td>
                        <td className="muted" style={{ fontSize: 11 }}>{e.notified ? Object.entries(e.notified).filter(([k]) => k !== "at").map(([k, v]) => `${k}${v ? "✔" : "✖"}`).join(" ") : ""}</td>
                      </tr>
                    ))}</tbody>
                  </table>
                </div>
              </>
            );
          })()}
        </>
      )}

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
              <table>
                <thead><tr><th>Sonde</th><th>Version</th><th>Runner</th><th>Intervalle</th><th>Agents affectés</th><th>Mise à jour</th><th className="ups-actions-head"></th></tr></thead>
                <tbody>{catalogue.map((p) => (
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
              </table>
            </div>
          )}
        </>
      )}
    </div>
  );
}
