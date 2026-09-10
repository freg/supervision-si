// Logique PURE de l'onglet « Sondes WiFi » (netprobe, livraison #407) :
// regroupement des dernières mesures par sonde, détection des changements
// de borne (itinérance) dans un historique wifi_link, série de signal pour
// le graphique. Aucun import React -- testé sous Node
// (hub/tests/netprobeAgents.test.mjs), même motif que networkAgentHistory.js.

// Tâches "connues" dont l'onglet sait faire une lecture compacte ; toute
// autre tâche est affichée brute (ok/erreur + JSON), jamais cachée.
export const KNOWN_TASKS = ["wifi_link", "wifi_scan", "sys"];

export function ageSeconds(iso, nowMs = Date.now()) {
  if (!iso) return null;
  const t = Date.parse(iso);
  if (!Number.isFinite(t)) return null;
  return Math.max(0, Math.round((nowMs - t) / 1000));
}

export function formatAge(seconds) {
  if (seconds == null) return "jamais";
  if (seconds < 60) return `${seconds} s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)} min`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)} h ${Math.floor((seconds % 3600) / 60)} min`;
  return `${Math.floor(seconds / 86400)} j`;
}

// Une sonde "en vie" a donné signe de vie il y a moins de `staleAfter`
// secondes (défaut 10 min : 20 fois le rythme de wifi_link).
export function liveness(agent, nowMs = Date.now(), staleAfter = 600) {
  const age = ageSeconds(agent?.last_seen_at, nowMs);
  if (age == null) return "never";
  return age <= staleAfter ? "alive" : "stale";
}

// Regroupe la liste plate `latest` (une entrée par sonde x tâche) en
// {agent_id: {task: mesure}} -- l'API renvoie une liste triée, l'onglet
// veut une ligne par sonde.
export function groupLatestByAgent(latest) {
  const out = {};
  for (const m of latest || []) {
    if (!m || !m.agent_id || !m.task) continue;
    (out[m.agent_id] = out[m.agent_id] || {})[m.task] = m;
  }
  return out;
}

// Lecture compacte d'une mesure wifi_link.
export function describeWifiLink(m) {
  if (!m) return null;
  if (!m.ok) return { text: m.error || "erreur", tone: "bad" };
  const d = m.data || {};
  if (d.connected === false) return { text: "déconnectée", tone: "bad" };
  const parts = [];
  if (d.ssid) parts.push(d.ssid);
  if (d.band && d.channel != null) parts.push(`${d.band} GHz ch ${d.channel}`);
  if (d.signal_dbm != null) parts.push(`${d.signal_dbm} dBm`);
  if (d.tx_bitrate_mbps != null) parts.push(`${d.tx_bitrate_mbps} Mb/s`);
  return { text: parts.join(" · ") || "connectée", tone: signalTone(d.signal_dbm), bssid: d.bssid || null };
}

// Seuils usuels d'un client WiFi : > -67 dBm confortable, -67..-75 limite,
// en dessous dégradé. Indicatifs, jamais une vérité absolue.
export function signalTone(dbm) {
  if (dbm == null) return "neutral";
  if (dbm >= -67) return "good";
  if (dbm >= -75) return "warn";
  return "bad";
}

export function describePing(m) {
  if (!m) return null;
  const d = m.data || {};
  if (!m.ok || d.ok === false) return { text: `${d.host || ""} injoignable`.trim(), tone: "bad" };
  const loss = d.loss_pct != null ? `${d.loss_pct}% perte` : null;
  const rtt = d.rtt_avg_ms != null ? `${d.rtt_avg_ms} ms` : null;
  const tone = d.loss_pct > 0 ? "warn" : "good";
  return { text: [d.host, rtt, loss].filter(Boolean).join(" · "), tone };
}

export function describeScan(m) {
  if (!m) return null;
  if (!m.ok) return { text: m.error || "scan impossible", tone: "neutral" };
  const s = (m.data || {}).summary || {};
  const parts = [`${s.total ?? 0} bornes visibles`];
  if (s.our_channel) {
    parts.push(`${s.co_channel_count ?? 0} co-canal (${s.our_channel})`);
  }
  const tone = (s.co_channel_count ?? 0) >= 3 ? "warn" : "neutral";
  const strongest = s.strongest_co_channel;
  return { text: parts.join(" · "), tone, strongest: strongest || null };
}

export function describeSys(m) {
  if (!m) return null;
  const d = m.data || {};
  const parts = [];
  if (d.cpu_temp_c != null) parts.push(`${d.cpu_temp_c} °C`);
  if (d.load1 != null) parts.push(`charge ${d.load1}`);
  if (d.uptime_s != null) parts.push(`up ${formatAge(d.uptime_s)}`);
  let tone = "neutral";
  if (d.under_voltage_now) { parts.push("⚡ sous-tension"); tone = "bad"; }
  else if (d.under_voltage_occurred) { parts.push("⚡ sous-tension passée"); tone = "warn"; }
  else if (d.cpu_temp_c != null && d.cpu_temp_c >= 75) tone = "warn";
  return { text: parts.join(" · ") || "—", tone };
}

// Changements de borne dans un historique wifi_link (ordre quelconque en
// entrée, remis en ordre chronologique). C'est le "suivi de BSSID /
// itinérance" que #385 laissait hors de portée. Une déconnexion
// (connected=false) puis reconnexion sur la MÊME borne n'est pas une
// itinérance ; sur une autre borne, si. Les mesures en erreur sont
// ignorées (on ne sait pas où était le client).
export function detectBssidChanges(measurements) {
  const rows = (measurements || [])
    .filter((m) => m && m.ok && m.data && m.task === "wifi_link")
    .slice()
    .sort((a, b) => (a.at < b.at ? -1 : a.at > b.at ? 1 : 0));
  const events = [];
  let prev = null;
  let disconnectedSince = null;
  for (const m of rows) {
    const d = m.data;
    if (d.connected === false) {
      if (disconnectedSince == null) disconnectedSince = m.at;
      continue;
    }
    if (!d.bssid) continue;
    if (prev && prev.bssid !== d.bssid) {
      events.push({ at: m.at, from: prev.bssid, to: d.bssid, from_ssid: prev.ssid || null, to_ssid: d.ssid || null,
                    signal_before: prev.signal_dbm ?? null, signal_after: d.signal_dbm ?? null,
                    after_disconnect: disconnectedSince != null, disconnected_since: disconnectedSince });
    } else if (prev && disconnectedSince != null) {
      events.push({ at: m.at, from: prev.bssid, to: d.bssid, reconnect: true, disconnected_since: disconnectedSince });
    }
    prev = { bssid: d.bssid, ssid: d.ssid, signal_dbm: d.signal_dbm };
    disconnectedSince = null;
  }
  return events;
}

// Série (at, valeur) d'un champ numérique des mesures ok, ordre
// chronologique -- alimente la ligne de signal.
export function seriesOf(measurements, field) {
  return (measurements || [])
    .filter((m) => m && m.ok && m.data && typeof m.data[field] === "number")
    .map((m) => ({ at: m.at, value: m.data[field] }))
    .sort((a, b) => (a.at < b.at ? -1 : a.at > b.at ? 1 : 0));
}

// Chemin SVG d'une ligne pour une série, mise à l'échelle dans width x
// height (marges internes `pad`). Renvoie aussi min/max pour les
// libellés. Série vide ou d'un seul point : chemin vide, jamais NaN.
export function buildLinePath(series, width, height, pad = 4) {
  const n = series.length;
  if (n < 2 || width <= 0 || height <= 0) return { path: "", min: null, max: null, points: [] };
  let min = Infinity, max = -Infinity;
  for (const p of series) { if (p.value < min) min = p.value; if (p.value > max) max = p.value; }
  const span = max - min || 1;
  const points = series.map((p, i) => ({
    x: pad + (i / (n - 1)) * (width - 2 * pad),
    y: pad + (1 - (p.value - min) / span) * (height - 2 * pad),
    at: p.at, value: p.value,
  }));
  const path = points.map((p, i) => `${i === 0 ? "M" : "L"} ${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join(" ");
  return { path, min, max, points };
}

// Nom lisible d'une tâche : "ping:192.168.10.1" -> "ping 192.168.10.1".
export function taskLabel(task) {
  if (!task) return "";
  const i = task.indexOf(":");
  return i < 0 ? task : `${task.slice(0, i)} ${task.slice(i + 1)}`;
}
