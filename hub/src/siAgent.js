// Logique PURE de la tuile « Agents hôtes » (livraison #421, backlog 63)
// -- aucun React, testée sous Node (hub/tests/siAgent.test.mjs). Le rendu
// vit dans SiAgentView.jsx.

export const RISK_LABELS_FR = {
  "disk-full": "Disque plein",
  "disk-high": "Disque presque plein",
  "memory-high": "Mémoire saturée",
  "swap-high": "Swap utilisé",
  "load-high": "Charge CPU élevée",
  "reboot-required": "Redémarrage requis",
  "recent-boot": "Démarrage récent",
  "service-failed": "Service en échec",
  "port-exposed": "Port sensible exposé",
  "uid0-account": "Compte UID 0 hors root",
  "log-errors": "Erreurs dans le journal",
};

export const COMMAND_TYPES = [
  { type: "collect_now", label: "Collecter maintenant", needsPlugin: false },
  { type: "flush", label: "Envoyer la file", needsPlugin: false },
  { type: "run_plugin", label: "Exécuter une sonde", needsPlugin: true },
  { type: "enable_plugin", label: "Activer une sonde (sur l'hôte)", needsPlugin: true },
  { type: "disable_plugin", label: "Désactiver une sonde (sur l'hôte)", needsPlugin: true },
  { type: "remove_plugin", label: "Retirer une sonde (sur l'hôte)", needsPlugin: true },
];

export const CONTACT_LABELS = { online: "en ligne", offline: "hors ligne", never: "jamais vu", unknown: "inconnu" };

export function riskLabel(id) {
  return RISK_LABELS_FR[id] || id || "—";
}

export function severityTone(severity) {
  if (severity === "critical") return "bad";
  if (severity === "warning") return "warn";
  if (severity === "info") return "neutral";
  return "neutral";
}

export function stateTone(state) {
  if (state === "critical") return "bad";
  if (state === "warning") return "warn";
  if (state === "ok") return "good";
  return "neutral";
}

export function contactTone(online) {
  if (online === "online") return "good";
  if (online === "offline") return "bad";
  return "neutral";
}

// Jauge : pourcentage borné [0, 100] + ton selon seuils (85 / 95 par
// défaut, comme les seuils disque de l'agent).
export function gauge(percent, warn = 85, critical = 95) {
  if (percent == null || Number.isNaN(Number(percent))) return { percent: null, tone: "neutral", width: 0 };
  const p = Math.max(0, Math.min(100, Number(percent)));
  const tone = p >= critical ? "bad" : p >= warn ? "warn" : "good";
  return { percent: Math.round(p * 10) / 10, tone, width: p };
}

export function formatBytes(bytes) {
  if (bytes == null || Number.isNaN(Number(bytes))) return "—";
  const units = ["o", "Ko", "Mo", "Go", "To"];
  let v = Number(bytes);
  let i = 0;
  while (v >= 1024 && i < units.length - 1) { v /= 1024; i += 1; }
  const txt = i === 0 ? String(v) : (Number.isInteger(v) || v >= 100 ? v.toFixed(0) : v.toFixed(1));
  return `${txt} ${units[i]}`;
}

export function formatUptime(seconds) {
  if (seconds == null || Number.isNaN(Number(seconds))) return "—";
  const s = Math.floor(Number(seconds));
  const d = Math.floor(s / 86400);
  const h = Math.floor((s % 86400) / 3600);
  const m = Math.floor((s % 3600) / 60);
  if (d > 0) return `${d} j ${h} h`;
  if (h > 0) return `${h} h ${m} min`;
  return `${m} min`;
}

export function formatAge(seconds) {
  if (seconds == null || Number.isNaN(Number(seconds))) return "—";
  const s = Math.max(0, Math.floor(Number(seconds)));
  if (s < 60) return `${s} s`;
  if (s < 3600) return `${Math.floor(s / 60)} min`;
  if (s < 86400) return `${Math.floor(s / 3600)} h`;
  return `${Math.floor(s / 86400)} j`;
}

export function ageSeconds(iso, nowMs = Date.now()) {
  if (!iso) return null;
  const t = Date.parse(iso);
  return Number.isNaN(t) ? null : (nowMs - t) / 1000;
}

// Ordre d'affichage de la flotte : d'abord ce qui demande attention
// (risques critiques, hors ligne), puis site / identifiant.
export function sortFleet(agents) {
  const rank = (a) => {
    const st = a.risks?.state;
    if (st === "critical") return 0;
    if (a.online === "offline") return 1;
    if (st === "warning") return 2;
    if (a.online === "never") return 4;
    return 3;
  };
  return [...(agents || [])].sort((x, y) => rank(x) - rank(y) || String(x.site || "").localeCompare(String(y.site || "")) || String(x.agent_id).localeCompare(String(y.agent_id)));
}

// Regroupe les constats par sévérité pour un résumé lisible ("2 critiques, 3 avertissements").
export function riskSummaryText(summary) {
  const c = summary?.counts || {};
  const parts = [];
  if (c.critical) parts.push(`${c.critical} critique${c.critical > 1 ? "s" : ""}`);
  if (c.warning) parts.push(`${c.warning} avertissement${c.warning > 1 ? "s" : ""}`);
  if (c.info) parts.push(`${c.info} info`);
  if (!parts.length) return summary?.state === "ok" ? "aucun" : "—";
  return parts.join(", ");
}

// Lignes du tableau des disques d'une mesure host.
// #438 : un montage illisible (FUSE/sshfs sans allow_other, NFS périmé) ou
// invisible depuis le conteneur est listé avec sa raison, tailles à « — ».
export function diskRows(host) {
  return (host?.disks || []).map((d) => ({
    mountpoint: d.mountpoint,
    device: d.device,
    fstype: d.fstype,
    remote: !!d.remote,
    used: d.total_bytes == null ? "—" : formatBytes(d.used_bytes),
    total: d.total_bytes == null ? "—" : formatBytes(d.total_bytes),
    gauge: d.used_percent == null ? null : gauge(d.used_percent),
    error: d.error || null,
    invisible: d.visible === false,
  }));
}

// Ports en écoute : exposés en premier, puis par numéro.
export function portRows(host) {
  return [...(host?.ports?.ports || [])].sort((a, b) => (Number(!!b.exposed) - Number(!!a.exposed)) || (a.port - b.port));
}

// Sondes : celles affectées par le central (catalogue) + celles présentes
// sur l'hôte d'après le dernier inventaire, fusionnées par identifiant.
export function mergePlugins(assigned, inventoryPlugins) {
  const out = new Map();
  for (const p of assigned || []) out.set(p.id, { id: p.id, version: p.version, runner: p.runner, description: p.description, assigned: true, enabled_central: !!p.enabled, blocked_central: !!p.blocked, privileged: !!p.privileged, present: false });
  for (const p of inventoryPlugins || []) {
    const cur = out.get(p.id) || { id: p.id, assigned: false };
    out.set(p.id, { ...cur, version: cur.version || p.version, present: true, enabled_host: !!(p.effective_enabled ?? p.enabled),
      blocked_host: !!(p.effective_blocked ?? p.blocked), privileged: cur.privileged || !!p.privileged, source: p.source || "bundled", runner: cur.runner || p.runner });
  }
  return [...out.values()].sort((a, b) => a.id.localeCompare(b.id));
}

// Validation du formulaire de plugin avant envoi (miroir des règles de
// validate_manifest côté agent -- refuser ici évite un aller-retour).
export function validatePluginForm(form) {
  const id = (form.id || "").trim();
  if (!/^[a-z0-9][a-z0-9_-]*$/.test(id)) return "identifiant : minuscules, chiffres, - et _";
  if (!["shell", "python"].includes(form.runner)) return "runner : shell ou python";
  const entry = (form.entry || "").trim();
  if (!entry || entry.includes("/") || entry.includes("\\") || entry.startsWith(".")) return "entrée : nom de fichier simple";
  const interval = Number(form.interval_seconds || 3600);
  if (!Number.isFinite(interval) || interval < 30) return "intervalle : 30 s minimum";
  if (!(form.body || "").trim()) return "script vide";
  return null;
}

export function defaultEntry(runner, id) {
  const base = (id || "plugin").replace(/-/g, "_");
  return runner === "python" ? `${base}.py` : `${base}.sh`;
}

// ---- #422 : événements, blocage ----------------------------------------

export const EVENT_KIND_LABELS_FR = {
  "agent-started": "Agent démarré",
  "config-applied": "Configuration appliquée",
  "config-replayed": "Configuration rejouée (refusée)",
  "central-response-rejected": "Réponse du central non signée / altérée",
  "central-auth-refused": "Authentification refusée par le central",
  "auth-refused": "Requête d'agent refusée",
  "plugin-installed": "Sonde installée",
  "plugin-refused": "Sonde refusée (signature)",
  "plugin-removed": "Sonde retirée",
  "plugin-failed": "Sonde en échec",
  "plugin-blocked": "Sonde bloquée",
  "plugin-unblocked": "Sonde débloquée",
  "plugin-catalogued": "Sonde au catalogue",
  "plugin-uncatalogued": "Sonde retirée du catalogue",
  "plugin-assigned": "Sonde affectée",
  "plugin-unassigned": "Sonde désaffectée",
  "blocked": "Blocage général (agent)",
  "unblocked": "Déblocage général (agent)",
  "fleet-blocked": "BLOCAGE GÉNÉRAL de la flotte",
  "fleet-unblocked": "Blocage général levé",
  "agent-blocked": "Agent bloqué",
  "agent-unblocked": "Agent débloqué",
  "agent-enrolled": "Agent enrôlé",
  "agent-deleted": "Agent supprimé",
  "agent-activated": "Agent réactivé",
  "agent-deactivated": "Agent désactivé",
  "agent-offline": "Agent hors ligne",
  "agent-online": "Agent de nouveau en ligne",
  "secret-rotated": "Secret renouvelé",
  "command-block": "Commande de blocage envoyée",
  "command-acked": "Commande appliquée",
  "command-failed": "Commande en échec",
  "command-replayed": "Commande rejouée (ignorée)",
  "command-unknown": "Commande inconnue",
  "tls-insecure": "TLS non vérifié",
  "notification-test": "Test de notification",
};

export const EVENT_SEVERITIES = ["critical", "warning", "info"];

export function eventKindLabel(kind) {
  return EVENT_KIND_LABELS_FR[kind] || kind || "—";
}

// Genres qui relèvent de la SÉCURITÉ (mis en avant dans la synthèse).
export const SECURITY_KINDS = new Set([
  "config-replayed", "central-response-rejected", "central-auth-refused", "auth-refused", "plugin-refused",
  "command-replayed", "tls-insecure", "fleet-blocked", "agent-blocked", "plugin-blocked", "secret-rotated", "plugin-catalogued",
]);

export function isSecurityEvent(e) {
  return SECURITY_KINDS.has(e?.kind) || e?.severity === "critical";
}

// Synthèse d'un lot d'événements : compteurs par sévérité / source, part sécurité.
export function summarizeEvents(events) {
  const out = { total: 0, critical: 0, warning: 0, info: 0, agent: 0, central: 0, security: 0, byKind: {} };
  for (const e of events || []) {
    out.total += 1;
    if (e.severity in out) out[e.severity] += 1;
    if (e.source === "agent") out.agent += 1; else out.central += 1;
    if (isSecurityEvent(e)) out.security += 1;
    out.byKind[e.kind] = (out.byKind[e.kind] || 0) + 1;
  }
  return out;
}

// Filtre côté client (onglet Événements) : sévérité minimale, agent, sécurité seulement, texte.
export function filterEvents(events, { minSeverity = "info", agent = "", securityOnly = false, text = "" } = {}) {
  const max = EVENT_SEVERITIES.indexOf(minSeverity);
  const t = (text || "").trim().toLowerCase();
  return (events || []).filter((e) => {
    if (EVENT_SEVERITIES.indexOf(e.severity) > max) return false;
    if (agent && e.agent_id !== agent) return false;
    if (securityOnly && !isSecurityEvent(e)) return false;
    if (t && !`${e.kind} ${e.message} ${e.agent_id || ""}`.toLowerCase().includes(t)) return false;
    return true;
  });
}

// Ton du bandeau de synthèse sur l'accueil du hub.
export function bannerTone(summary) {
  if (!summary) return "neutral";
  if (summary.fleet_blocked || summary.counts?.critical > 0) return "bad";
  if (summary.counts?.warning > 0 || summary.agents_offline?.length > 0 || summary.agents_blocked?.length > 0) return "warn";
  return "good";
}

export function bannerHeadline(summary) {
  if (!summary) return "Agents hôtes : synthèse indisponible";
  if (summary.fleet_blocked) return `BLOCAGE GÉNÉRAL des sondes en cours${summary.fleet_block_reason ? ` — ${summary.fleet_block_reason}` : ""}`;
  const parts = [];
  const c = summary.counts || {};
  if (c.critical) parts.push(`${c.critical} critique${c.critical > 1 ? "s" : ""}`);
  if (c.warning) parts.push(`${c.warning} avertissement${c.warning > 1 ? "s" : ""}`);
  if (summary.agents_offline?.length) parts.push(`${summary.agents_offline.length} agent${summary.agents_offline.length > 1 ? "s" : ""} hors ligne`);
  if (summary.agents_blocked?.length) parts.push(`${summary.agents_blocked.length} bloqué${summary.agents_blocked.length > 1 ? "s" : ""}`);
  if (!parts.length) return `Agents hôtes : rien à signaler sur ${summary.window_hours} h (${summary.agents} agent${summary.agents > 1 ? "s" : ""})`;
  return `Agents hôtes, ${summary.window_hours} h : ${parts.join(", ")}`;
}
