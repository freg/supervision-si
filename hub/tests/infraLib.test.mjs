import { test } from "node:test";
import assert from "node:assert/strict";
import { fmtBytes, fmtBps, fmtUptime, fillLevel, donutArcs, htopRows, sortRows, groupByHost, fills, pct } from "../src/infraLib.js";

const DATA = { nodes: [
  { name: "pve10", zone: "local", role: "pve", ok: true, cpu_pct: 12.5, cores_pct: [10, 15], ncpu: 2, mem_used: 8e9, mem_total: 32e9, swap_used: 0, swap_total: 8e9,
    tasks: { running: 2, total: 300 }, load: [0.5, 0.4, 0.3], uptime_s: 90061, disks: [{ mount: "/", device: "/dev/sda1", size: 100, used: 96, pct: 96 }],
    zpools: [{ name: "rpool", size: 1000, alloc: 300, pct: 30 }], storages: [] },
  { name: "pve-2", zone: "distant", role: "pve", ok: true, storages: [{ storage: "local", total: 2000, used: 1600, avail: 400 }, { storage: "backup", total: 2000, used: 1600, avail: 400 }] }],
  vms: [{ node: "pve10", vmid: 100, name: "partages", type: "qemu", status: "running", cpu_pct: 40, ncpu: 4, mem: 2e9, maxmem: 4e9, uptime_s: 60, zone: "local" }] };

test("formats", () => {
  assert.equal(fmtBytes(1.5e12), "1.50 To"); assert.equal(fmtBps(8e8), "800.0 Mbit/s"); assert.equal(fmtUptime(90061), "1 j 01:01");
  assert.equal(pct(1, 4), 25); assert.equal(pct(1, 0), null);
  assert.deepEqual(fillLevel(96), { tone: "critical", label: "critique" }); assert.equal(fillLevel(86).tone, "warning"); assert.equal(fillLevel(10).label, "");
});
test("anneau : segments proportionnels, segments nuls ignorés, cercle plein", () => {
  const a = donutArcs([{ value: 3 }, { value: 1 }, { value: 0 }]);
  assert.equal(a.length, 2); assert.equal(a[0].share, 0.75); assert.match(a[0].d, /^M /);
  assert.equal(donutArcs([{ value: 0 }]).length, 0);
  assert.equal(donutArcs([{ value: 5 }]).length, 1);
});
test("htop : hôtes puis VM, tri avec absents en bas", () => {
  const rows = htopRows(DATA);
  assert.deepEqual(rows.map((r) => r.kind), ["PVE", "PVE", "VM"]);
  const s = sortRows(rows, "cpu");
  assert.deepEqual(s.map((r) => r.name), ["100 partages", "pve10", "pve-2"]);
  assert.equal(sortRows(rows, "name", 1)[0].name, "100 partages");
});
test("remplissages : zfs + partitions hors pool, stockages dédoublonnés, plus plein d'abord", () => {
  const f = fills(DATA);
  assert.deepEqual(f.map((x) => `${x.node} ${x.what}`), ["pve10 /", "pve-2 local", "pve10 zfs rpool"]);
});
test("htop regroupé : VM sous leur hôte", () => {
  const g = groupByHost(htopRows(DATA), "cpu");
  assert.deepEqual(g.map((r) => r.name), ["pve10", "100 partages", "pve-2"]);
});
