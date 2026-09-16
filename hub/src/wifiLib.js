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
