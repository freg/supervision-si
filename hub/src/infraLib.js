// Vue d'ensemble PVE / PBS (#749) -- calculs purs de la tuile (testés : tests/infraLib.test.mjs).
export const fmtBytes = (n) => (n == null ? "—" : n >= 1e12 ? (n / 1e12).toFixed(2) + " To" : n >= 1e9 ? (n / 1e9).toFixed(1) + " Go" : n >= 1e6 ? Math.round(n / 1e6) + " Mo" : Math.round(n / 1e3) + " Ko");
export const fmtBps = (n) => (n == null ? "—" : n >= 1e9 ? (n / 1e9).toFixed(2) + " Gbit/s" : n >= 1e6 ? (n / 1e6).toFixed(1) + " Mbit/s" : Math.round(n / 1e3) + " kbit/s");
export const pct = (used, total) => (total ? Math.round((1000 * used) / total) / 10 : null);
export function fmtUptime(s) {
  if (s == null) return "—";
  const d = Math.floor(s / 86400), h = Math.floor((s % 86400) / 3600), m = Math.floor((s % 3600) / 60);
  return d ? `${d} j ${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}` : `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}`;
}
// Gravité d'un remplissage : seuils 85 / 95 (les mêmes que l'agent) -> ton + libellé (jamais la couleur seule)
export function fillLevel(p) {
  if (p == null) return { tone: "neutral", label: "" };
  if (p >= 95) return { tone: "critical", label: "critique" };
  if (p >= 85) return { tone: "warning", label: "à surveiller" };
  return { tone: "ok", label: "" };
}
// Arcs d'un anneau : [{value, ...}] -> [{...seg, d}] (chemins SVG), écart de 2 px entre segments
export function donutArcs(segments, r = 52, inner = 34, cx = 60, cy = 60) {
  const total = segments.reduce((a, s) => a + (s.value || 0), 0);
  if (!total) return [];
  let a0 = -Math.PI / 2;
  const gap = segments.filter((s) => s.value > 0).length > 1 ? 2 / r : 0;
  return segments.filter((s) => s.value > 0).map((s) => {
    const span = (2 * Math.PI * s.value) / total;
    const a1 = a0 + span;
    const s0 = a0 + gap / 2, s1 = Math.max(s0 + 0.0001, a1 - gap / 2);
    const large = s1 - s0 > Math.PI ? 1 : 0;
    const p = (rad, ang) => [cx + rad * Math.cos(ang), cy + rad * Math.sin(ang)].map((v) => v.toFixed(2)).join(" ");
    const d = span >= 2 * Math.PI - 1e-6
      ? `M ${p(r, 0)} A ${r} ${r} 0 1 1 ${p(r, Math.PI)} A ${r} ${r} 0 1 1 ${p(r, 0)} M ${p(inner, 0)} A ${inner} ${inner} 0 1 0 ${p(inner, Math.PI)} A ${inner} ${inner} 0 1 0 ${p(inner, 0)} Z`
      : `M ${p(r, s0)} A ${r} ${r} 0 ${large} 1 ${p(r, s1)} L ${p(inner, s1)} A ${inner} ${inner} 0 ${large} 0 ${p(inner, s0)} Z`;
    a0 = a1;
    return { ...s, d, share: s.value / total };
  });
}
// Lignes « htop » : un hôte par nœud, puis ses VM
export function htopRows(data) {
  const rows = [];
  for (const n of data?.nodes || []) {
    rows.push({ key: `n:${n.name}`, kind: n.role === "pbs" ? "PBS" : "PVE", name: n.name, zone: n.zone, host: n.name, ok: n.ok !== false && n.cpu_pct !== undefined,
      cpu: n.cpu_pct, cores: n.cores_pct || [], ncpu: n.ncpu, mem: n.mem_used, maxmem: n.mem_total, swap: n.swap_used, maxswap: n.swap_total,
      tasks: n.tasks, load: n.load, uptime: n.uptime_s, status: n.ok === false ? "injoignable" : "en ligne", error: n.error || n.activity_error });
  }
  for (const v of data?.vms || []) {
    rows.push({ key: `v:${v.node}:${v.vmid}`, kind: v.type === "lxc" ? "CT" : "VM", name: `${v.vmid} ${v.name}`, zone: v.zone, host: v.node, ok: v.status === "running",
      cpu: v.cpu_pct, cores: [], ncpu: v.ncpu, mem: v.mem, maxmem: v.maxmem, swap: null, maxswap: null, tasks: null, load: null, uptime: v.uptime_s, status: v.status });
  }
  return rows;
}
// Tri des lignes htop : colonne + sens ; valeurs absentes toujours en bas
export function sortRows(rows, col, dir = -1) {
  const val = (r) => (col === "mem" ? (r.maxmem ? r.mem / r.maxmem : null) : col === "load" ? (r.load ? r.load[0] : null) : r[col]);
  return [...rows].sort((a, b) => {
    const x = val(a), y = val(b);
    if (x == null && y == null) return 0;
    if (x == null) return 1;
    if (y == null) return -1;
    return typeof x === "string" ? dir * x.localeCompare(y) : dir * (x - y);
  });
}
// Remplissages pour l'histogramme : partitions, pools ZFS, stockages, datastores PBS (un par système de fichiers)
export function fills(data) {
  const out = [];
  for (const n of data?.nodes || []) {
    for (const z of n.zpools || []) out.push({ node: n.name, zone: n.zone, what: `zfs ${z.name}`, used: z.alloc, total: z.size, pct: z.pct });
    for (const d of n.disks || []) if (!(n.zpools || []).length || !/^(rpool|tank|data|backup)\b/.test(d.device || "")) out.push({ node: n.name, zone: n.zone, what: d.mount, used: d.used, total: d.size, pct: d.pct });
    const seen = new Set();
    if (!(n.disks || []).length) for (const s of n.storages || []) {
      const k = `${s.total}|${s.avail}`;
      if (!s.total || seen.has(k)) continue;
      seen.add(k); out.push({ node: n.name, zone: n.zone, what: s.storage, used: s.used, total: s.total, pct: pct(s.used, s.total) });
    }
    for (const d of n.datastores || []) out.push({ node: n.name, zone: n.zone, what: `pbs ${d.name}`, used: d.used, total: d.total, pct: d.used_percent });
  }
  return out.sort((a, b) => (b.pct ?? -1) - (a.pct ?? -1));
}
// htop regroupé : chaque hôte (dans l'ordre du tri) suivi de ses VM (triées pareil) ; VM d'un hôte inconnu à la fin
export function groupByHost(rows, col, dir = -1) {
  const hosts = sortRows(rows.filter((r) => r.kind === "PVE" || r.kind === "PBS"), col, dir);
  const vms = sortRows(rows.filter((r) => r.kind === "VM" || r.kind === "CT"), col, dir);
  const out = [];
  for (const h of hosts) out.push(h, ...vms.filter((v) => v.host === h.host));
  const known = new Set(hosts.map((h) => h.host));
  return out.concat(vms.filter((v) => !known.has(v.host)));
}
