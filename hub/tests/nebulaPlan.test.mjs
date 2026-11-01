// Plan du site (livraison #555).
import test from "node:test";
import assert from "node:assert/strict";
import { clientSpot, planItems, toFraction, mergePlacements } from "../src/nebulaPlan.js";

const TREE = { nodes: [
  { id: "ap1", name: "Borne A", kind: "ap", clients: [{ mac: "c1", status: "online" }, { mac: "c2", status: "online" }] },
  { id: "sw", name: "Cœur", kind: "switch", clients: [{ mac: "p1" }] },
  { id: "ap2", name: "Borne B", kind: "ap", clients: [] },
] };

test("clientSpot : anneau autour du parent, second anneau au-delà de 12", () => {
  const s = clientSpot({ x: 0.5, y: 0.5 }, 0, 4, 0.02);
  assert.ok(Math.abs(s.x - 0.5) < 1e-9 && Math.abs(s.y - 0.48) < 1e-9);
  const far = clientSpot({ x: 0.5, y: 0.5 }, 13, 20, 0.02);
  assert.ok(Math.hypot(far.x - 0.5, far.y - 0.5) > 0.03);
  assert.equal(clientSpot(null, 0, 1), null);
});

test("planItems : placés, clients en anneau ou à leur place, non placés triés", () => {
  const it = planItems(TREE, { ap1: { x: 0.2, y: 0.3 }, "client:c2": { x: 0.9, y: 0.9 } });
  assert.deepEqual(it.devices.map((d) => d.key), ["ap1"]);
  assert.deepEqual(it.unplaced.map((n) => n.name), ["Borne B", "Cœur"]);
  const c1 = it.clients.find((c) => c.key === "client:c1"), c2 = it.clients.find((c) => c.key === "client:c2");
  assert.equal(c1.auto, true); assert.equal(c2.auto, false); assert.equal(c2.x, 0.9);
  assert.equal(it.clients.find((c) => c.key === "client:p1"), undefined);  // parent non placé : pas dessiné
});

test("toFraction borne à [0,1] ; mergePlacements retire sur null", () => {
  assert.deepEqual(toFraction(150, 25, { left: 100, top: 0, width: 100, height: 100 }), { x: 0.5, y: 0.25 });
  assert.deepEqual(toFraction(-50, 500, { left: 0, top: 0, width: 100, height: 100 }), { x: 0, y: 1 });
  assert.equal(toFraction(1, 1, null), null);
  assert.deepEqual(mergePlacements({ a: { x: 0.1, y: 0.1 }, b: { x: 0.2, y: 0.2 } }, { a: null, c: { x: 0.3, y: 0.3, extra: 1 } }), { b: { x: 0.2, y: 0.2 }, c: { x: 0.3, y: 0.3 } });
});
