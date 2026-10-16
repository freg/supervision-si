import test from "node:test";
import assert from "node:assert/strict";
import {
  ago, ipIgnored, webLast, loginLast, mysqlLast, lastActivity, idleClass, daySeries, sortGuests, filterGuests, counts,
  profileToForm, formToProfile, fmtPct, fmtCount,
} from "../src/guestUsageLib.js";

const NOW = Date.parse("2026-10-15T12:00:00Z");
const row = (o = {}) => ({ key: `${o.node || "pve-3"}/${o.vmid || 106}`, node: "pve-3", vmid: 106, name: "ob1", status: "running", collected: true, profile: {}, ...o });
const OB1 = row({
  web: { last: { at: "2026-10-15T11:59:00Z", ip: "10.0.0.5" }, hits24: 40, hits7d: 300, per_day: [{ day: "2026-10-14", hits: 10 }, { day: "2026-10-15", hits: 30 }],
         ips: [{ ip: "10.0.0.5", hits: 200, last_at: "2026-10-15T11:59:00Z" }, { ip: "198.51.100.7", hits: 5, last_at: "2026-10-13T08:00:00Z" }],
         owncloud: { last_at: "2026-10-12T08:00:00Z", last_user: "alice", hits7d: 3 } },
  login: { last: { user: "root", from: "203.0.113.9", at: "2026-10-14T10:00:00" }, count7d: 3,
           users: [{ user: "root", from: "203.0.113.9", last_at: "2026-10-14T10:00:00" }, { user: "deploy", from: null, last_at: "2026-10-01T09:00:00" }] },
  mysql: { ok: true, last_activity_at: "2026-10-15T11:30:00Z", conn7d: 70, users_seen: [{ user: "modoboa", last_seen: "2026-10-15T11:30:00Z" }],
           sessions: [{ user: "modoboa" }, { user: "modoboa" }, { user: "roundcube" }] },
  cpu: { avg24: 3.2 },
});

test("#769 : durées lisibles et IP ignorées (exactes ou réseau IPv4)", () => {
  assert.equal(ago("2026-10-15T11:59:30Z", NOW), "à l'instant");
  assert.equal(ago("2026-10-15T09:00:00Z", NOW), "il y a 3 h");
  assert.equal(ago("2026-10-05T12:00:00Z", NOW), "il y a 10 j");
  assert.equal(ago(null, NOW), "—");
  assert.ok(ipIgnored("10.0.0.5", ["10.0.0.0/24"]));
  assert.ok(!ipIgnored("10.0.1.5", ["10.0.0.0/24"]));
  assert.ok(ipIgnored("192.0.2.10", ["192.0.2.10"]));
  assert.ok(!ipIgnored("2001:db8::1", ["10.0.0.0/8"]));
});

test("#769 : dernier accès par source, fiche appliquée (IP ignorées, comptes suivis)", () => {
  assert.deepEqual(webLast(OB1), { at: "2026-10-15T11:59:00Z", who: "10.0.0.5" });
  const ign = { ...OB1, profile: { ignore_ips: ["10.0.0.0/24"] } };
  assert.deepEqual(webLast(ign), { at: "2026-10-13T08:00:00Z", who: "198.51.100.7" });   // la supervision ne compte plus
  assert.equal(loginLast(OB1).who, "root@203.0.113.9");
  assert.deepEqual(loginLast({ ...OB1, profile: { unix_accounts: ["deploy"] } }), { at: "2026-10-01T09:00:00", who: "deploy" });
  assert.equal(loginLast({ ...OB1, profile: { unix_accounts: ["absent"] } }), null);
  assert.equal(mysqlLast(OB1).who, "modoboa, roundcube");
  assert.equal(mysqlLast({ ...OB1, profile: { mysql_user: "roundcube" } }), null);       // jamais vu en session
  assert.equal(mysqlLast({ ...OB1, mysql: { ok: false } }), null);
  assert.equal(lastActivity(OB1).kind, "http");
  assert.equal(lastActivity({ ...ign, profile: { ignore_ips: ["10.0.0.0/24"] } }).kind, "mysql");
});

test("#769 : classes d'inactivité, séries, tri, filtres, comptes", () => {
  assert.equal(idleClass(OB1, NOW), "actif");
  const vieux = row({ vmid: 110, name: "vieux", web: { last: { at: "2026-08-01T00:00:00Z", ip: "x" }, ips: [] } });
  assert.equal(idleClass(vieux, NOW), "dormant");
  assert.equal(idleClass(row({ vmid: 111, collected: false, status: "stopped" }), NOW), "inconnu");
  assert.equal(idleClass(row({ vmid: 112 }), NOW), "dormant");                           // relevé, aucune trace
  const s = daySeries(OB1.web.per_day, "hits", 3, NOW);
  assert.deepEqual(s, [{ day: "2026-10-13", v: 0 }, { day: "2026-10-14", v: 10 }, { day: "2026-10-15", v: 30 }]);
  const rows = [vieux, OB1, row({ vmid: 111, collected: false, status: "stopped", node: "pve-1" })];
  assert.deepEqual(sortGuests(rows, "activity", -1).map((r) => r.vmid), [106, 110, 111]);
  assert.deepEqual(sortGuests(rows, "node", 1).map((r) => r.vmid), [111, 106, 110]);
  assert.deepEqual(filterGuests(rows, { idle: "dormant" }, NOW).map((r) => r.vmid), [110]);
  assert.deepEqual(filterGuests(rows, { running: true, q: "OB" }, NOW).map((r) => r.vmid), [106]);
  assert.deepEqual(filterGuests(rows, { node: "pve-1" }, NOW).map((r) => r.vmid), [111]);
  assert.deepEqual(counts(rows, NOW), { total: 3, collected: 2, web: 2, mysql: 1, dormant: 1, unknown: 1 });
});

test("#769 : fiche -- listes, aucun mot de passe recopié", () => {
  const f = profileToForm({ unix_accounts: ["www-data", "deploy"], mysql_user: "modoboa" });
  assert.equal(f.unix_accounts, "www-data, deploy");
  assert.equal(f.notes, "");
  const ok = formToProfile({ ...f, ignore_ips: "10.0.0.0/24; 192.0.2.10", vault_ref: "OB1 / mysql modoboa" });
  assert.deepEqual(ok, { profile: { unix_accounts: ["www-data", "deploy"], mysql_user: "modoboa", vault_ref: "OB1 / mysql modoboa", ignore_ips: ["10.0.0.0/24", "192.0.2.10"] }, error: null });
  assert.match(formToProfile({ notes: "root mot de passe : Xy12" }).error, /coffre-fort/);
  assert.match(formToProfile({ vault_ref: "password=abc" }).error, /coffre-fort/);
  assert.equal(fmtPct(3.25), "3.3 %");
  assert.equal(fmtPct(null), "—");
  assert.equal(fmtCount(25300), "25 k");
});

// ---------------------------------------------------------------- #771 : activité réelle dans le temps
import { actClass, idleSince, monthSeries, totals12, decisionOrder, decisionsCsv, formToProfile as f2p, PROFILE_FIELDS as PF } from "../src/guestUsageLib.js";

const NOW771 = Date.parse("2026-10-16T12:00:00Z");
const ROWA = { key: "pve-a/101", node: "pve-a", vmid: 101, name: "site; ancien", type: "lxc", status: "running",
  activity: { class: "inactif", idle_days: 229, last_any: "2026-03-01", first_day: "2025-11-03", last_active: { web: "2025-11-03", login: "2026-03-01", mysql: null },
    months: [{ month: "2025-10", active_days: 9, req: 999 }, { month: "2025-11", active_days: 1, req: 40, bytes: 2e6, logins: 0, mysql_q: 0 },
      { month: "2026-03", active_days: 1, req: 0, logins: 2, mysql_q: 5 }] },
  profile: { decision: "archiver", decision_reason: "plus consulté \"du tout\"", planned_for: "2026-11-15", migration_status: "planifiee" } };
const ROWB = { key: "pve-a/102", node: "pve-a", vmid: 102, name: "mail", type: "qemu", status: "running", activity: { class: "actif", idle_days: 0, last_any: "2026-10-16", months: [] } };
const ROWC = { key: "pve-b/103", node: "pve-b", vmid: 103, name: "neuf", type: "lxc", status: "stopped" };

test("#771 : classe, inactif depuis", () => {
  assert.equal(actClass(ROWA), "inactif");
  assert.equal(actClass(ROWC), "inconnu");
  assert.equal(idleSince(ROWA), "depuis le 01/03/2026");
  assert.equal(idleSince({ activity: { first_day: "2025-11-03" } }), "aucune depuis le 03/11/2025");
  assert.equal(idleSince(ROWC), "");
});

test("#771 : séries mensuelles et totaux 12 mois", () => {
  const s = monthSeries(ROWA, "active_days", 13, NOW771);
  assert.equal(s.length, 13);
  assert.equal(s[0].month, "2025-10");
  assert.equal(s[12].month, "2026-10");
  assert.equal(s[0].v, 9);
  const t = totals12(ROWA, NOW771);                         // 2025-10 hors des 12 derniers mois
  assert.deepEqual([t.req, t.active_days, t.logins, t.mysql_q], [40, 2, 2, 5]);
});

test("#771 : liste pour les décideurs (moins actifs d'abord, CSV Excel)", () => {
  assert.deepEqual(decisionOrder([ROWB, ROWC, ROWA]).map((r) => r.vmid), [101, 102, 103]);
  const csv = decisionsCsv([ROWB, ROWA]);
  assert.ok(csv.startsWith("﻿Nœud;VMID;Nom;"));
  const lines = csv.trim().split("\r\n");
  assert.equal(lines.length, 3);
  assert.ok(lines[1].includes('"site; ancien"'));
  assert.ok(lines[1].includes('"plus consulté ""du tout"""'));
  assert.ok(lines[1].includes("archiver puis arrêter"));
  assert.ok(lines[1].includes("15/11/2026"));
  assert.ok(lines[1].includes(";229;"));
});

test("#771 : fiche -- décision et suivi de migration", () => {
  assert.ok(PF.some(([k]) => k === "decision") && PF.some(([k]) => k === "migration_status"));
  const { profile, error } = f2p({ decision: "migrer", target: "pve10", planned_for: "2026-11-15", migration_status: "a_planifier" });
  assert.equal(error, null);
  assert.deepEqual(profile, { decision: "migrer", target: "pve10", planned_for: "2026-11-15", migration_status: "a_planifier" });
});
