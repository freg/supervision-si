// #519 : synthèse « santé de l'hyperviseur » côté tuile.
import test from "node:test";
import assert from "node:assert/strict";
import { hostHealthSummary } from "../src/proxmoxLib.js";

test("absent -> null ; tons et projection", () => {
  assert.equal(hostHealthSummary({}), null);
  const node = { host_health: {
    memory: { total: 32e9, available: 9e9, swap_total: 8e9, swap_used: 4e8 },
    arc: { size: 3.2e9, c_max: 3.3e9, hit_pct: 90 },
    pools: [{ pool: "rpool", cap_pct: 84, state: "ONLINE", io: { r_ops: 3, w_ops: 900, r_bps: 2e4, w_bps: 4.5e7 } }, { pool: "tank", cap_pct: 10, state: "DEGRADED" }],
    disks: [{ dev: "sda", util_pct: 95, await_ms: 9.3, rkb_s: 1, wkb_s: 12000 }, { dev: "zd0", util_pct: 5, await_ms: 1, rkb_s: 0, wkb_s: 1, vmid: 100, dataset: "rpool/data/vm-100-disk-0" }],
    vm_io_top: [{ vmid: 111, rkb_s: 0, wkb_s: 12000, util_pct: 90 }],
    alerts: [{ severity: "warning", message: "swap" }], recommendations: ["x"], interval_s: 2,
  } };
  const h = hostHealthSummary(node);
  assert.equal(h.tone, "warning");
  assert.equal(h.memory.tone, "warning");
  assert.equal(h.pools[0].tone, "warning");
  assert.equal(h.pools[1].tone, "critical");
  assert.equal(h.disks[0].tone, "warning");
  assert.equal(h.disks[1].tone, "ok");
  assert.equal(h.topVms[0].vmid, 111);
  assert.equal(h.intervalS, 2);
  assert.equal(hostHealthSummary({ host_health: { alerts: [{ severity: "critical", message: "pool" }] } }).tone, "critical");
  assert.equal(hostHealthSummary({ host_health: {} }).tone, "ok");
});
