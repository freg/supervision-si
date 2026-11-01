// Logique pure de l'écran « Urgence » (livraison #796) : état résumé des alertes, contacts, abonnement aux alertes poussées.
export const SEV_RANK = { critical: 0, warning: 1, info: 2 };
export const SEV_LABEL = { critical: "critique", warning: "alerte", info: "info" };
export const SNAPSHOT_KEY = "hub.urgence.snapshot";
export const CONTACTS_KEY = "hub.urgence.contacts";

/** Accès rapides en déplacement : vue du hub (+ paramètres). */
export const QUICK_LINKS = [
  { view: "aujourdhui", label: "Aujourd'hui", icon: "⏰" },
  { view: "si-agent", params: { tab: "events" }, label: "Événements des agents", icon: "📋" },
  { view: "notifications", params: { tab: "sms" }, label: "SMS (envoi, journal, relance)", icon: "📡" },
  { view: "control", label: "Tour de contrôle (services)", icon: "🚦" },
  { view: "migration", label: "Migration (pilotage)", icon: "🔀" },
  { view: "journal", label: "Journal des chantiers", icon: "📚" },
  { view: "pve-ops", label: "Contrôle PVE (PRA)", icon: "🖥" },
];

/** Instant ISO (UTC, format des événements de si-agent) il y a `hours` heures. */
export function sinceIso(hours, now = Date.now()) {
  return new Date(now - hours * 3600e3).toISOString().replace(/\.\d{3}Z$/, "Z");
}

/** Tri : plus grave d'abord, puis plus récent. */
export function sortEvents(events) {
  return [...(events || [])].sort((a, b) =>
    (SEV_RANK[a.severity] ?? 9) - (SEV_RANK[b.severity] ?? 9) || String(b.at || "").localeCompare(String(a.at || "")) || (b.id || 0) - (a.id || 0));
}

/** Résumé : compteurs, niveau global (critique | alerte | ok), hôtes touchés. */
export function summarize(events) {
  const list = events || [];
  const critical = list.filter((e) => e.severity === "critical").length;
  const warning = list.filter((e) => e.severity === "warning").length;
  const hosts = [...new Set(list.filter((e) => e.severity !== "info").map((e) => e.agent_id || e.source).filter(Boolean))].sort();
  return { critical, warning, hosts, level: critical ? "critique" : warning ? "alerte" : "ok" };
}

/** Regroupe les répétitions (même hôte, même type, même message) : une ligne avec le nombre et la dernière date. */
export function groupEvents(events) {
  const m = new Map();
  for (const e of sortEvents(events)) {
    const k = [e.agent_id || e.source || "", e.kind || "", e.message || ""].join("\u0001");
    const g = m.get(k);
    if (g) { g.count += 1; if (String(e.at) > String(g.last)) g.last = e.at; if (String(e.at) < String(g.first)) g.first = e.at; }
    else m.set(k, { ...e, count: 1, first: e.at, last: e.at });
  }
  return [...m.values()];
}

/** Clé VAPID publique (base64url) -> Uint8Array pour pushManager.subscribe. */
export function urlBase64ToUint8Array(b64) {
  const s = String(b64 || "").replace(/-/g, "+").replace(/_/g, "/");
  const pad = s + "=".repeat((4 - (s.length % 4)) % 4);
  const raw = typeof atob === "function" ? atob(pad) : Buffer.from(pad, "base64").toString("binary");
  const out = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; i++) out[i] = raw.charCodeAt(i);
  return out;
}

/** L'appareil peut-il recevoir des alertes poussées ? -> {ok, reason} (raison lisible sinon). */
export function pushSupport(env) {
  const w = env || {};
  if (!w.isSecureContext) return { ok: false, reason: "il faut ouvrir le hub par son adresse https publique (pas http://192.168…)" };
  if (!w.serviceWorker) return { ok: false, reason: "navigateur sans service worker" };
  if (!w.PushManager || !w.Notification) {
    return { ok: false, reason: w.ios ? "sur iPhone : d'abord Partager › « Sur l'écran d'accueil », puis ouvrir le hub depuis l'icône" : "ce navigateur ne gère pas les alertes poussées" };
  }
  if (w.permission === "denied") return { ok: false, reason: "notifications refusées pour ce site : les réautoriser dans les réglages du navigateur" };
  return { ok: true, reason: "" };
}

/** Nom d'appareil proposé pour l'abonnement (modifiable). */
export function deviceLabel(ua = "") {
  const s = String(ua);
  const os = /Android/i.test(s) ? "Android" : /iPhone|iPad/i.test(s) ? "iOS" : /Mac OS X/i.test(s) ? "Mac" : /Windows/i.test(s) ? "Windows" : /Linux/i.test(s) ? "Linux" : "appareil";
  const nav = /Edg\//.test(s) ? "Edge" : /OPR\/|Opera/.test(s) ? "Opera" : /Firefox\//.test(s) ? "Firefox" : /Chrome\//.test(s) ? "Chrome" : /Safari\//.test(s) ? "Safari" : "";
  return nav ? `${os} · ${nav}` : os;
}

/** Contacts : nettoyage (nom requis), lien tel: (chiffres et + seulement). */
export function normContacts(list) {
  return (Array.isArray(list) ? list : [])
    .map((c) => ({ name: String(c?.name || "").trim().slice(0, 80), role: String(c?.role || "").trim().slice(0, 80), phone: String(c?.phone || "").trim().slice(0, 40) }))
    .filter((c) => c.name);
}
export function telHref(phone) {
  const t = String(phone || "").replace(/[^0-9+]/g, "");
  return t.length >= 3 ? `tel:${t}` : "";
}

/** Instantané gardé sur l'appareil pour la page hors ligne (alertes allégées, 50 au plus). */
export function makeSnapshot(events, now = Date.now()) {
  return {
    at: new Date(now).toISOString(),
    events: sortEvents(events).slice(0, 50).map((e) => ({ id: e.id, at: e.at, severity: e.severity, kind: e.kind, agent_id: e.agent_id, source: e.source, message: String(e.message || "").slice(0, 300) })),
  };
}

/** Âge lisible d'un horodatage ISO. */
export function ago(iso, now = Date.now()) {
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return "";
  const s = Math.max(0, Math.round((now - t) / 1000));
  if (s < 60) return "à l'instant";
  if (s < 3600) return `il y a ${Math.round(s / 60)} min`;
  if (s < 86400) return `il y a ${Math.floor(s / 3600)} h ${String(Math.round((s % 3600) / 60)).padStart(2, "0")}`;
  return `il y a ${Math.floor(s / 86400)} j`;
}
