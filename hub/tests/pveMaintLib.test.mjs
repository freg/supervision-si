import test from "node:test";
import assert from "node:assert/strict";
import { detectorFields, paramsToText, textToParams, toLocalInput, fromLocalInput, plannedList, missingParams, move } from "../src/pveMaintLib.js";

test("champs des détecteurs", () => {
  const cat = { detectors: { backup_recent: { fields: ["vmid", "max_age_h", "storage?"] } } };
  assert.deepEqual(detectorFields(cat, "backup_recent").map((f) => [f.name, f.optional]), [["vmid", false], ["max_age_h", false], ["storage", true]]);
  assert.deepEqual(detectorFields(cat, "x"), []);
});

test("paramètres clé=valeur", () => {
  assert.deepEqual(textToParams("storage=local\nconfirm=101; mode = stop\n=x\nbad"), { storage: "local", confirm: 101, mode: "stop" });
  assert.equal(paramsToText({ a: 1, b: "x" }), "a=1\nb=x");
  assert.deepEqual(missingParams({ required: { destroy: ["confirm"] } }, { action: "destroy", params: {} }), ["confirm"]);
  assert.deepEqual(missingParams({ required: {} }, { action: "start" }), []);
});

test("dates et planning", () => {
  const e = fromLocalInput("2026-10-10T22:30");
  assert.equal(toLocalInput(e), "2026-10-10T22:30");
  assert.equal(fromLocalInput(""), null); assert.equal(toLocalInput(null), "");
  assert.deepEqual(plannedList([{ planned: [{ at: 3 }, { at: 1 }] }, { planned: [{ at: 2 }] }, {}]).map((p) => p.at), [1, 2, 3]);
  assert.deepEqual(move([1, 2, 3], 0, 1), [2, 1, 3]); assert.deepEqual(move([1, 2], 1, 1), [1, 2]);
});

test("campaignLines (#723) : CT arrêtés d'abord, en marche seulement sur demande, exclusions, VM et nœuds injoignables écartés", async () => {
  const { campaignLines } = await import("../src/pveMaintLib.js");
  const nodes = [
    { name: "pve-2", host: "203.0.113.22", ok: true, guests: [{ vmid: 113, type: "lxc", status: "running", name: "web" }, { vmid: 110, type: "lxc", status: "stopped", name: "old" }] },
    { name: "pve-1", host: "203.0.113.21", ok: true, guests: [{ vmid: 108, type: "lxc", status: "stopped", name: "" }, { vmid: 200, type: "qemu", status: "stopped" }, { vmid: 101, type: "lxc", status: "stopped", name: "a" }] },
    { name: "pve-3", host: "203.0.113.23", ok: false, guests: [{ vmid: 1, type: "lxc", status: "stopped" }] },
  ];
  const body = (t) => t.split("\n").filter((l) => l && !l.startsWith("#"));
  assert.deepEqual(body(campaignLines(nodes)), ["203.0.113.21 101 stop 2 pve-1   # a", "203.0.113.21 108 stop 2 pve-1", "203.0.113.22 110 stop 2 pve-2   # old"]);
  const all = body(campaignLines(nodes, { includeRunning: true, exclude: ["pve-1/108"], keep: 1 }));
  assert.deepEqual(all, ["203.0.113.21 101 stop 1 pve-1   # a", "203.0.113.22 110 stop 1 pve-2   # old", "203.0.113.22 113 stop 1 pve-2   # running : web"]);
});

test("filterInventory / inventorySummary (#724)", async () => {
  const { filterInventory, inventorySummary } = await import("../src/pveMaintLib.js");
  const now = 1_800_000_000;
  const rows = [{ source: "ssh", node: "pve-1", vmid: 108, name: "Ancien", kind: "snapshot", at: now - 40 * 86400, where: "avant-maj" },
    { source: "pbs", node: "pbs10", vmid: 101, name: "101", kind: "sauvegarde", at: now - 3600, where: "backup:ct/101" }];
  assert.equal(filterInventory(rows, { kind: "snapshot", now }).length, 1);
  assert.equal(filterInventory(rows, { q: "ANCIEN", now }).length, 1);
  assert.equal(filterInventory(rows, { olderThanDays: 30, now })[0].vmid, 108);
  assert.deepEqual(inventorySummary(rows, now), { snapshot: 1, sauvegarde: 1, oldSnapshots: 1, bySource: { ssh: 1, pbs: 1 } });
});
