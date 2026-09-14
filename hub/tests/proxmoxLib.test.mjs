// Aides de la tuile Proxmox (livraison #504).
import test from "node:test";
import assert from "node:assert/strict";
import { backupSummary, accessSummary, guestLogsSummary, availabilityOf, nodeBackupSummary, nodeAccessSummary } from "../src/proxmoxLib.js";

test("backupSummary : série d'échecs, jamais lancée, dernier résultat", () => {
  assert.equal(backupSummary({ backup_runs: [] }).tone, "warning");
  assert.equal(backupSummary({ backup_runs: [], last_backup: { age_s: 100 } }).tone, "neutral");
  assert.equal(backupSummary({ backup_runs: [{ ok: true }] }).tone, "ok");
  const s = backupSummary({ backup_runs: [{ ok: false }, { ok: false }, { ok: true }], backup_jobs: ["nightly"] });
  assert.equal(s.failStreak, 2); assert.equal(s.tone, "critical"); assert.deepEqual(s.jobs, ["nightly"]);
  assert.equal(backupSummary({ backup_runs: [{ ok: null }, { ok: false }] }).tone, "warning");
});

test("accessSummary : phrase et ton, sans accès", () => {
  assert.equal(accessSummary({}).text, "aucun accès");
  const a = accessSummary({ access: { console_sessions: 2, changes: 1, views: 5, users: [{ key: "root@pam", count: 8 }], ips: [] } });
  assert.equal(a.text, "2 consoles · 1 modif. · 5 consult."); assert.equal(a.tone, "warning"); assert.deepEqual(a.users, ["root@pam (8)"]);
});

test("guestLogsSummary : SSH/web, tons, absence", () => {
  assert.equal(guestLogsSummary({}), null);
  const g = guestLogsSummary({ guest_logs: { collected_at: 1, ssh: { accepted: 2, failed: 25, invalid_users: 3, last_accepted: { user: "alice", ip: "192.0.2.20" }, accepted_by_user: [], failed_by_ip: [{ key: "198.51.100.7", count: 25 }] },
    web: { hits: 4, status: { "2xx": 3, "5xx": 1 }, top_ips: [], top_paths: [] }, raw: { ssh: "x" }, errors: [] } });
  assert.equal(g.ssh.tone, "critical"); assert.equal(g.ssh.lastAccepted, "alice depuis 192.0.2.20"); assert.equal(g.web.tone, "warning"); assert.equal(g.raw.ssh, "x");
});

test("availabilityOf / nodeBackupSummary / nodeAccessSummary", () => {
  const h = { vms: { "100": { availability_percent: 97.2, transitions: [{ at: "t", from: "running", to: "stopped" }], samples: 40 } } };
  assert.equal(availabilityOf(h, 100).tone, "warning"); assert.equal(availabilityOf(h, 101).text, "—");
  assert.equal(availabilityOf({ vms: { "1": { availability_percent: 100 } } }, 1).tone, "ok");
  const nb = nodeBackupSummary({ backups: { ok_24h: 3, failed_24h: 1, jobs: [{ enabled: true }, { enabled: false }] } });
  assert.equal(nb.tone, "critical"); assert.equal(nb.enabledJobs, 1);
  assert.equal(nodeBackupSummary({}), null);
  const na = nodeAccessSummary({ access: { host: { requests: 12, auth_failures: 2, users: [{ key: "root@pam", count: 12 }], ips: [] }, ssh: { accepted: 1, failed: 0, last_accepted: { user: "bob", ip: "192.0.2.21" } }, auth_failures_24h: 1 } });
  assert.equal(na.authFailures, 3); assert.equal(na.tone, "warning"); assert.equal(na.sshLast, "bob depuis 192.0.2.21");
});
