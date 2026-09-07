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
export function diskRows(host) {
  return (host?.disks || []).map((d) => ({
    mountpoint: d.mountpoint,
    device: d.device,
    fstype: d.fstype,
    used: formatBytes(d.used_bytes),
    total: formatBytes(d.total_bytes),
    gauge: gauge(d.used_percent),
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
  for (const p of assigned || []) out.set(p.id, { id: p.id, version: p.version, runner: p.runner, description: p.description, assigned: true, enabled_central: !!p.enabled, present: false });
  for (const p of inventoryPlugins || []) {
    const cur = out.get(p.id) || { id: p.id, assigned: false };
    out.set(p.id, { ...cur, version: cur.version || p.version, present: true, enabled_host: !!(p.effective_enabled ?? p.enabled), source: p.source || "bundled", runner: cur.runner || p.runner });
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
