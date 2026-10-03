// Tour de contrôle — onglet Réseau (#655) : agrégation en lecture seule DNS / routage / flux. Logique pure testée sous Node.

// DNS : entrées de services (service-watch) + divergences de résolution (sonde dns-observe) -> lignes homogènes.
export function dnsRows(entries, dnsObs) {
  const rows = (entries || []).map((e) => ({ kind: "entrée", name: e.name, detail: (e.last?.ips || []).join(", ") || "—", state: e.last?.state || "?", alerts: (e.last?.alerts || []).length, at: e.last?.at || "" }));
  for (const a of dnsObs || []) for (const al of a.alerts || []) rows.push({ kind: "divergence", name: al.name || al.target || a.hostname, detail: al.message || al.detail || JSON.stringify(al).slice(0, 80), state: "alerte", alerts: 1, at: a.at || "", agent: a.hostname });
  return rows;
}

export function dnsSummary(rows) {
  const ko = rows.filter((r) => r.state && !["ok", "up", "?"].includes(String(r.state).toLowerCase())).length;
  return { total: rows.length, ko, alerts: rows.reduce((s, r) => s + (r.alerts || 0), 0) };
}

// Routage : routes MikroTik par routeur (actives/inactives/désactivées), passerelles par défaut.
export function routingSummary(routers) {
  const out = [];
  for (const r of routers || []) {
    const routes = r.routes || [];
    out.push({ router: r.name, error: r.error || null, total: routes.length, active: routes.filter((x) => x.active && !x.disabled).length, disabled: routes.filter((x) => x.disabled).length,
      defaults: routes.filter((x) => x.dst === "0.0.0.0/0").map((x) => `${x.gateway}${x.active ? "" : " (inactive)"}`), nat: r.nat || 0 });
  }
  return out;
}

// Flux : échanges « d'où vers où, combien » (network-agent links) + accès aux ressources (sonde) -> top N par volume.
export function topFlows(links, n = 15) {
  return [...(links || [])].map((l) => ({ a: l.device_a_name || l.device_a_ip || l.a || l.device_a_id, b: l.device_b_name || l.device_b_ip || l.b || l.device_b_id, bytes: Number(l.bytes || l.total_bytes || 0), packets: Number(l.packets || 0) }))
    .sort((x, y) => y.bytes - x.bytes).slice(0, n);
}

export function fmtBytes(n) {
  n = Number(n || 0); if (n < 1024) return `${n} o`; if (n < 1048576) return `${(n / 1024).toFixed(1)} Ko`; if (n < 1073741824) return `${(n / 1048576).toFixed(1)} Mo`; return `${(n / 1073741824).toFixed(2)} Go`;
}

export function resourceRows(resObs, n = 20) {
  const rows = [];
  for (const a of resObs || []) for (const r of a.resources || []) rows.push({ agent: a.hostname, name: r.name || r.host || r.ip, clients: (r.clients || []).length || r.client_count || 0, hits: r.hits || r.count || 0, ok: r.ok !== false });
  return rows.sort((x, y) => (y.hits || 0) - (x.hits || 0)).slice(0, n);
}
