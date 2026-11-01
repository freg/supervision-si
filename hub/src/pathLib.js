// Sonde « chemin de service » path-probe (#527) -- logique pure pour la
// section de la fiche agent : une ligne par chemin (interface) et par
// mesure, pires valeurs, rendu des états.
import { wifiTone, pctTone, fmt } from "./wifiLib.js";

export { wifiTone as pathTone, pctTone, fmt };

/** Libellé court d'un chemin : SSID, sinon connexion, sinon interface. */
export function pathLabel(p) {
  return p?.ssid || p?.connection || p?.iface || "?";
}

/** Résumé DNS d'un chemin : "2/3" serveurs répondants, pire latence. */
export function dnsSummary(list) {
  const l = list || [];
  const ok = l.filter((d) => d.ok);
  return { ok: ok.length, total: l.length, worstMs: ok.reduce((m, d) => (d.ms != null && (m == null || d.ms > m) ? d.ms : m), null), down: l.filter((d) => !d.ok).map((d) => d.server) };
}

/** Une ligne par (mesure, chemin), les plus récentes d'abord. */
export function pathRows(measurements) {
  const rows = [];
  for (const m of measurements || []) {
    if (!m || !m.data || m.data.error) continue;
    for (const p of m.data.paths || []) {
      const dns = dnsSummary(p.dns);
      const pub = dnsSummary(p.dns_public);
      rows.push({
        at: m.at,
        label: pathLabel(p),
        iface: p.iface,
        ip: p.ip || null,
        gwMs: p.gw_ping?.avg_ms ?? null,
        gwLoss: p.gw_ping?.loss_pct ?? null,
        dnsOk: dns.ok,
        dnsTotal: dns.total,
        dnsMs: dns.worstMs,
        pubOk: pub.ok,
        pubTotal: pub.total,
        httpMs: p.http?.ok ? p.http.ms : null,
        httpOk: p.http ? !!p.http.ok : null,
        httpsMs: p.https?.ok ? p.https.ms : null,
        httpsOk: p.https ? !!p.https.ok : null,
        portal: !!(p.http?.portal || p.https?.portal),
        state: p.summary?.state || "ok",
        alerts: (p.alerts || []).length,
      });
    }
  }
  return rows;
}

/** Par chemin : nombre de passages, passages en échec HTTP, pires valeurs. */
export function pathWorst(rows) {
  const by = {};
  for (const r of rows || []) {
    const w = by[r.label] || (by[r.label] = { label: r.label, samples: 0, noIp: 0, httpFail: 0, dnsFail: 0, gwMs: null, dnsMs: null, httpMs: null, critical: 0 });
    w.samples += 1;
    if (!r.ip) w.noIp += 1;
    if (r.httpOk === false) w.httpFail += 1;
    if (r.dnsTotal && r.dnsOk < r.dnsTotal) w.dnsFail += 1;
    if (r.state === "critical") w.critical += 1;
    for (const k of ["gwMs", "dnsMs", "httpMs"]) if (r[k] != null && (w[k] == null || r[k] > w[k])) w[k] = r[k];
  }
  return Object.values(by);
}
