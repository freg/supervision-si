// Sonde Wi-Fi « expérience client » (#525) -- logique pure pour la section
// Wi-Fi de la fiche agent : lignes d'historique à partir des mesures
// plugin:wifi-probe, pires valeurs sur la fenêtre, et rendu des constats.

/** Une ligne compacte par mesure (les plus récentes d'abord). */
export function wifiRows(measurements) {
  return (measurements || []).filter((m) => m && m.data && !m.data.error).map((m) => {
    const d = m.data;
    const l = d.link || {};
    return {
      at: m.at,
      connected: !!l.connected,
      bssid: l.bssid || null,
      channel: l.channel ?? null,
      band: l.band || null,
      rssi: l.signal_dbm ?? null,
      tx: l.tx_mbit ?? null,
      rx: l.rx_mbit ?? null,
      retry: d.rates?.retry_pct ?? null,
      busy: d.channel?.busy_pct ?? null,
      other: d.channel?.other_pct ?? null,
      latency: d.ping?.avg_ms ?? null,
      jitter: d.ping?.jitter_ms ?? null,
      loss: d.ping?.loss_pct ?? null,
      stations: d.neighbourhood?.our_bss?.stations ?? null,
      bssUtil: d.neighbourhood?.our_bss?.utilisation_pct ?? null,
      state: d.summary?.state || "ok",
      alerts: (d.alerts || []).length,
    };
  });
}

/** Pire valeur de chaque indicateur sur la fenêtre (pour repérer les créneaux). */
export function wifiWorst(rows) {
  const r = (rows || []).filter((x) => x.connected);
  const pick = (key, cmp) => r.reduce((best, x) => (x[key] == null ? best : best == null || cmp(x[key], best[key]) ? x : best), null);
  return {
    samples: (rows || []).length,
    disconnected: (rows || []).filter((x) => !x.connected).length,
    rssi: pick("rssi", (a, b) => a < b),
    retry: pick("retry", (a, b) => a > b),
    busy: pick("busy", (a, b) => a > b),
    jitter: pick("jitter", (a, b) => a > b),
    loss: pick("loss", (a, b) => a > b),
    bssids: [...new Set(r.map((x) => x.bssid).filter(Boolean))],
  };
}

export function wifiTone(state) {
  return state === "critical" ? "bad" : state === "warning" ? "warn" : "good";
}

export function rssiTone(v) {
  if (v == null) return "neutral";
  return v <= -80 ? "bad" : v <= -70 ? "warn" : "good";
}

export function pctTone(v, warn, crit) {
  if (v == null) return "neutral";
  return v >= crit ? "bad" : v >= warn ? "warn" : "good";
}

export function fmt(v, unit = "", digits = 0) {
  if (v == null || Number.isNaN(v)) return "—";
  return `${Number(v).toFixed(digits)}${unit}`;
}

/** v3 (#529) : utilisation des canaux par borne (radio) dans le temps, à partir
 *  des listes `neighbourhood.radios` de chaque passage. Une entrée par radio :
 *  dernière valeur, max / moyenne d'utilisation, max de stations, nombre de
 *  passages « occupé sans client », canaux vus. Triée par pire utilisation. */
export function radioSeries(measurements, { idleBusyPct = 40, idleStations = 1 } = {}) {
  const by = {};
  const ms = (measurements || []).filter((m) => m && m.data && !m.data.error);
  for (let i = ms.length - 1; i >= 0; i--) { // du plus ancien au plus récent
    const m = ms[i];
    for (const r of m.data.neighbourhood?.radios || []) {
      const k = r.radio || (r.bssid || "").slice(0, 14);
      const e = by[k] || (by[k] = { radio: k, ssid: r.ssid, bssid: r.bssid, samples: 0, utilSum: 0, utilN: 0, utilMax: null, stationsMax: null, idleBusy: 0, channels: new Set(), last: null, ours: false });
      e.samples += 1;
      if (r.channel != null) e.channels.add(r.channel);
      if (r.utilisation_pct != null) {
        e.utilSum += r.utilisation_pct; e.utilN += 1;
        if (e.utilMax == null || r.utilisation_pct > e.utilMax) e.utilMax = r.utilisation_pct;
        if (r.utilisation_pct >= idleBusyPct && (r.stations || 0) <= idleStations) e.idleBusy += 1;
      }
      if (r.stations != null && (e.stationsMax == null || r.stations > e.stationsMax)) e.stationsMax = r.stations;
      e.last = { at: m.at, channel: r.channel, signal: r.signal_dbm, stations: r.stations, util: r.utilisation_pct, ssid: r.ssid };
      if (r.ssid) e.ssid = r.ssid;
      if (m.data.link?.bssid && m.data.link.bssid.slice(0, 14) === k) e.ours = true;
    }
  }
  return Object.values(by).map((e) => ({ ...e, channels: [...e.channels].sort((a, b) => a - b), utilAvg: e.utilN ? e.utilSum / e.utilN : null }))
    .sort((a, b) => (b.utilMax ?? -1) - (a.utilMax ?? -1) || (b.last?.signal ?? -100) - (a.last?.signal ?? -100));
}

/** Radios par canal (dernier passage) : combien de bornes se partagent chaque canal. */
export function channelCrowd(series) {
  const by = {};
  for (const e of series || []) {
    const c = e.last?.channel;
    if (c == null) continue;
    (by[c] = by[c] || []).push(e);
  }
  return Object.entries(by).map(([channel, radios]) => ({ channel: Number(channel), radios: radios.length, utilMax: radios.reduce((m, r) => (r.last?.util != null && (m == null || r.last.util > m) ? r.last.util : m), null) }))
    .sort((a, b) => b.radios - a.radios || a.channel - b.channel);
}
