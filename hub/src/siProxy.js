// Logique PURE de la tuile « Bastion » (livraison #454) -- aucun React,
// testée sous Node (hub/tests/siProxy.test.mjs) : accès à la tuile,
// formats (durées, volumes), lecture du journal d'audit, regroupements.

// Qui voit la tuile : les preferred_username de VITE_SI_PROXY_ADMIN_USERS
// (confort d'affichage -- le contrôle RÉEL est fait par le pont, qui
// vérifie le jeton Keycloak). Liste vide = personne.
export function parseAdminUsers(raw) {
  return String(raw || "").split(",").map((s) => s.trim().toLowerCase()).filter(Boolean);
}
export function canSeeBastion(username, raw) {
  const u = String(username || "").trim().toLowerCase();
  return !!u && parseAdminUsers(raw).includes(u);
}

export const KIND_LABELS = { shell: "shell host", connect: "https (CONNECT)", http: "http", "?": "inconnu" };
export const EVENT_LABELS = { "session-start": "ouverture", "session-end": "fermeture", refused: "refus" };

export function fmtDuration(s) {
  if (s == null || !Number.isFinite(Number(s))) return "—";
  const n = Math.max(0, Math.round(Number(s)));
  if (n < 60) return `${n} s`;
  if (n < 3600) return `${Math.floor(n / 60)} min ${n % 60 ? `${n % 60} s` : ""}`.trim();
  const h = Math.floor(n / 3600), m = Math.floor((n % 3600) / 60);
  return `${h} h${m ? ` ${m} min` : ""}`;
}

export function fmtBytes(b) {
  const n = Number(b) || 0;
  if (n < 1024) return `${n} o`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(n < 10240 ? 1 : 0)} Ko`;
  if (n < 1024 * 1024 * 1024) return `${(n / 1024 / 1024).toFixed(1)} Mo`;
  return `${(n / 1024 / 1024 / 1024).toFixed(2)} Go`;
}

// Un client `cn:freg` / `token:client` -> libellé lisible.
export function clientLabel(c) {
  if (!c) return "—";
  if (c.startsWith("cn:")) return `${c.slice(3)} (certificat)`;
  if (c.startsWith("token:")) return `jeton ${c.slice(6)}`;
  return c;
}

// Description d'une ligne du journal (jamais de secret : le journal n'en
// contient pas, on ne fait que reformuler).
export function describeEvent(ev) {
  const kind = KIND_LABELS[ev.kind] || ev.kind || "";
  const tgt = ev.target ? ` → ${ev.target}` : "";
  if (ev.event === "session-start") return `#${ev.session} ${kind}${tgt} par ${clientLabel(ev.client)}${ev.peer ? ` depuis ${ev.peer}` : ""}`;
  if (ev.event === "session-end") {
    const vol = `${fmtBytes(ev.bytes_up)} ↑ / ${fmtBytes(ev.bytes_down)} ↓`;
    return `#${ev.session} ${kind}${tgt} — ${fmtDuration(ev.duration_s)}, ${vol}${ev.outcome === "error" ? ` (erreur${ev.error ? ` : ${ev.error}` : ""})` : ""}`;
  }
  if (ev.event === "refused") return `refus${ev.peer ? ` de ${ev.peer}` : ""} : ${ev.reason || "?"}${ev.kind ? ` (${kind}${tgt})` : ""}`;
  return JSON.stringify(ev);
}

// Journal en ordre inverse (le plus récent d'abord), filtré par type.
export function sortAudit(events, { only = null, limit = 200 } = {}) {
  const xs = (events || []).filter((e) => !only || only === "all" || e.event === only);
  return xs.slice().sort((a, b) => (b.at || "").localeCompare(a.at || "")).slice(0, limit);
}

// Refus par IP (candidats au ban / à surveiller), les plus fréquents d'abord.
export function refusalsByPeer(events) {
  const m = new Map();
  for (const e of events || []) {
    if (e.event !== "refused" || !e.peer) continue;
    const cur = m.get(e.peer) || { peer: e.peer, count: 0, last: null, reasons: new Set() };
    cur.count += 1;
    if (!cur.last || (e.at || "") > cur.last) cur.last = e.at;
    if (e.reason) cur.reasons.add(e.reason);
    m.set(e.peer, cur);
  }
  return [...m.values()].map((r) => ({ ...r, reasons: [...r.reasons] })).sort((a, b) => b.count - a.count || a.peer.localeCompare(b.peer));
}

// Bandeau d'état de la tuile : couleur + texte à partir de /status.
export function headline(status) {
  if (!status || status.error) return { state: "critical", text: status?.error || "relais injoignable" };
  if (!status.host_connected) return { state: "warning", text: "shim host non connecté — aucune session possible" };
  if (!status.enabled) return { state: "warning", text: "bastion EN PAUSE — nouvelles sessions refusées" };
  const n = (status.sessions || []).length;
  return { state: "ok", text: n ? `${n} session(s) en cours` : "prêt — aucune session en cours" };
}
