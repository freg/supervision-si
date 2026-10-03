import test from "node:test";
import assert from "node:assert/strict";
import { flattenProxmox, otherNodes, makeStep, runSummary, stepText, OPS } from "../src/pveOpsLib.js";

const data = [{ agent_id: "pve10", hostname: "pve10", node: { name: "pve10" }, vms: [{ vmid: 101, name: "super", type: "qemu", status: "running" }, { vmid: 900, name: "tpl", template: 1 }], storages: [{ storage: "local-zfs" }, { name: "pbs" }] },
  { agent_id: "pve11", hostname: "pve11", node: {}, vms: [] }];

test("flattenProxmox et otherNodes", () => {
  const h = flattenProxmox(data);
  assert.deepEqual(h[0].vms, [{ vmid: 101, name: "super", type: "qemu", status: "running" }]);
  assert.deepEqual(h[0].storages, ["local-zfs", "pbs"]); assert.equal(h[1].node, "pve11");
  assert.deepEqual(otherNodes(h, "pve10"), ["pve11"]);
});

test("makeStep ne garde que les champs de l'opération et type les nombres", () => {
  const h = flattenProxmox(data)[0];
  const s = makeStep(h, h.vms[0], "clone", { newid: "9101", name: "super-pra", storage: "", foo: "x" });
  assert.deepEqual(s, { agent_id: "pve10", vmid: 101, kind: "qemu", action: "clone", params: { newid: 9101, name: "super-pra" }, label: "super : Cloner" });
  assert.equal(makeStep(h, { vmid: 203, type: "lxc" }, "migrate", { target: "pve11", online: true }).kind, "lxc");
  assert.ok(Object.keys(OPS).includes("replicate"));
});

test("runSummary et stepText", () => {
  assert.equal(runSummary({ steps: [{ index: 1, status: "done" }, { index: 2, status: "failed", result: { error: "refusé" } }, { index: 3, status: "pending" }] }), "1/3 étape(s) — échec à l'étape 2 : refusé");
  assert.equal(runSummary({ steps: [{ index: 1, ok: true }, { index: 2, ok: false, error: "agent inconnu" }] }), "1/2 étape(s) — échec à l'étape 2 : agent inconnu");
  assert.equal(stepText({ agent_id: "pve10", params: { vmid: 101, action: "migrate", kind: "qemu", target: "pve11" } }), "pve10 · VM 101 · Migrer vers un nœud (target=pve11)");
});
