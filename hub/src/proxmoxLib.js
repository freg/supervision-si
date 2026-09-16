// Aides pures de la tuile Proxmox (livraison #504) : suivi des sauvegardes,
// accès et disponibilité -- testées par node --test, consommées par
// ProxmoxView.jsx.

/** Ton d'une exécution de sauvegarde : null (en cours) → neutral. */
export function backupRunTone(run) {
  if (!run) return "warning";
  if (run.ok === true) return "ok";
  if (run.ok === false) return "critical";
  return "neutral";
}

/** Résumé d'un suivi de sauvegarde par VM : dernier résultat, série d'échecs. */
export function backupSummary(vm) {
  const runs = vm?.backup_runs || [];
  const last = vm?.last_backup_run || runs[0] || null;
  let failStreak = 0;
  for (const r of runs) { if (r.ok === false) failStreak += 1; else if (r.ok === true) break; }
  return { last, runs, failStreak, jobs: vm?.backup_jobs || [], neverRun: runs.length === 0,
    tone: failStreak >= 2 ? "critical" : failStreak === 1 ? "warning" : last ? backupRunTone(last) : (vm?.last_backup ? "neutral" : "warning") };
}

/** Accès d'une VM sur la fenêtre : phrase courte + ton. */
export function accessSummary(vm) {
  const a = vm?.access;
  if (!a) return { text: "aucun accès", tone: "neutral", console: 0, changes: 0, views: 0, users: [], ips: [] };
  const parts = [];
  if (a.console_sessions) parts.push(`${a.console_sessions} console${a.console_sessions > 1 ? "s" : ""}`);
  if (a.changes) parts.push(`${a.changes} modif.`);
  if (a.views) parts.push(`${a.views} consult.`);
  return { text: parts.join(" · ") || "aucun accès", tone: a.console_sessions ? "warning" : a.changes ? "neutral" : "neutral",
    console: a.console_sessions || 0, changes: a.changes || 0, views: a.views || 0,
    users: (a.users || []).map((u) => `${u.key} (${u.count})`), ips: (a.ips || []).map((u) => `${u.key} (${u.count})`),
    lastAt: a.last_at || null, lastConsoleAt: a.last_console_at || null };
}

/** Journaux internes : synthèse lisible (SSH accepté/refusé, web par classe). */
export function guestLogsSummary(vm) {
  const g = vm?.guest_logs;
  if (!g) return null;
  const ssh = g.ssh ? { accepted: g.ssh.accepted || 0, failed: g.ssh.failed || 0, invalid: g.ssh.invalid_users || 0,
    lastAccepted: g.ssh.last_accepted ? `${g.ssh.last_accepted.user} depuis ${g.ssh.last_accepted.ip}` : null,
    byUser: (g.ssh.accepted_by_user || []).map((u) => `${u.key} ×${u.count}`), failedByIp: (g.ssh.failed_by_ip || []).map((u) => `${u.key} ×${u.count}`),
    tone: (g.ssh.failed || 0) >= 20 ? "critical" : (g.ssh.failed || 0) > 0 ? "warning" : "ok" } : null;
  const web = g.web ? { hits: g.web.hits || 0, status: g.web.status || {}, topIps: (g.web.top_ips || []).map((u) => `${u.key} ×${u.count}`),
    topPaths: (g.web.top_paths || []).map((u) => `${u.key} ×${u.count}`), tone: (g.web.status?.["5xx"] || 0) > 0 ? "warning" : "ok" } : null;
  return { collectedAt: g.collected_at || null, ssh, web, raw: g.raw || {}, errors: g.errors || [] };
}

/** Disponibilité d'une VM (réponse /proxmox/history) : libellé + ton. */
export function availabilityOf(history, vmid) {
  const v = history?.vms?.[String(vmid)];
  if (!v || v.availability_percent == null) return { text: "—", tone: "neutral", transitions: [], samples: 0 };
  const p = v.availability_percent;
  return { text: `${p} %`, percent: p, tone: p >= 99.5 ? "ok" : p >= 95 ? "warning" : "critical",
    transitions: v.transitions || [], samples: v.samples || 0 };
}

/** Sauvegardes de l'hyperviseur : compteurs 24 h et jobs actifs. */
export function nodeBackupSummary(node) {
  const b = node?.backups;
  if (!b) return null;
  const jobs = b.jobs || [];
  return { ok24: b.ok_24h || 0, failed24: b.failed_24h || 0, jobs, enabledJobs: jobs.filter((j) => j.enabled).length,
    tone: (b.failed_24h || 0) > 0 ? "critical" : (b.ok_24h || 0) > 0 ? "ok" : "neutral", runs: b.runs || [] };
}

/** #519 : santé de l'hyperviseur (IO, mémoire, ARC, pools, VM les plus
 *  écrivantes, options des VM) -- ton global, alertes et recommandations. */
export function hostHealthSummary(node) {
  const h = node?.host_health;
  if (!h) return null;
  const alerts = h.alerts || [];
  const tone = alerts.some((a) => a.severity === "critical") ? "critical" : alerts.some((a) => a.severity === "warning") ? "warning" : "ok";
  const mem = h.memory || null;
  const arc = h.arc || null;
  return {
    tone, alerts, recommendations: h.recommendations || [],
    memory: mem ? { total: mem.total, available: mem.available, swapUsed: mem.swap_used || 0, swapTotal: mem.swap_total || 0,
      tone: (mem.swap_used || 0) > 0 ? "warning" : "ok" } : null,
    arc: arc ? { size: arc.size, max: arc.c_max, hitPct: arc.hit_pct, ratio: arc.c_max ? arc.size / arc.c_max : null } : null,
    pools: (h.pools || []).map((p) => ({ pool: p.pool, capPct: p.cap_pct, state: p.state || p.health, io: p.io || null,
      tone: (p.state || p.health) && (p.state || p.health) !== "ONLINE" ? "critical" : p.cap_pct >= 90 ? "critical" : p.cap_pct >= 80 ? "warning" : "ok" })),
    disks: (h.disks || []).map((d) => ({ ...d, tone: d.util_pct >= 85 || d.await_ms >= 50 ? "warning" : d.util_pct >= 50 ? "neutral" : "ok" })),
    topVms: h.vm_io_top || [], intervalS: h.interval_s || null,
  };
}

/** Accès à l'hyperviseur : requêtes, échecs d'authentification, SSH. */
export function nodeAccessSummary(node) {
  const a = node?.access;
  if (!a) return null;
  const host = a.host || null;
  const ssh = a.ssh || null;
  const authFail = (host?.auth_failures || 0) + (a.auth_failures_24h || 0);
  return { requests: host?.requests || 0, users: (host?.users || []).map((u) => `${u.key} (${u.count})`), ips: (host?.ips || []).map((u) => `${u.key} (${u.count})`),
    authFailures: authFail, sshAccepted: ssh?.accepted || 0, sshFailed: ssh?.failed || 0,
    sshLast: ssh?.last_accepted ? `${ssh.last_accepted.user} depuis ${ssh.last_accepted.ip}` : null,
    tone: authFail >= 10 || (ssh?.failed || 0) >= 20 ? "critical" : authFail > 0 || (ssh?.failed || 0) > 0 ? "warning" : "ok" };
}
