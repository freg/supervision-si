// Synoptique en arbre (livraison #555).
import test from "node:test";
import assert from "node:assert/strict";
import { childrenMap, treeLayout, treeEdges, treeSummary } from "../src/nebulaTree.js";

const TREE = { nodes: [
  { id: "gw", name: "USG", kind: "gateway", parent: null, depth: 0, status: "online", clients: [] },
  { id: "core", name: "XS3800", kind: "switch", parent: "gw", depth: 1, status: "online", parent_port: 3, uplink_port: 1, link: { missing_on_a: [], missing_on_b: [], bare: false }, clients: [{ mac: "m1", name: "imprimante", status: "online" }] },
  { id: "ap1", name: "Borne A", kind: "ap", parent: "core", depth: 2, status: "online", parent_port: 5, uplink_port: 1, link: { missing_on_a: [], missing_on_b: [] }, clients: [{ mac: "c1", status: "online" }, { mac: "c2", status: "offline" }, { mac: "c3", status: "online" }] },
  { id: "edge", name: "GS2220", kind: "switch", parent: "core", depth: 2, status: "offline", parent_port: 25, uplink_port: 49, link: { missing_on_a: [], missing_on_b: [30] }, clients: [] },
  { id: "ap2", name: "Borne B", kind: "ap", parent: "edge", depth: 3, status: "online", link: { bare: true, missing_on_a: [], missing_on_b: [] }, clients: [] },
  { id: "ap9", name: "Orpheline", kind: "ap", parent: "gw", depth: 1, status: "inconnu", unlinked: true, clients: [] },
], loose_clients: [{ mac: "zz" }] };

test("childrenMap : racine, commutateurs avant bornes, plus de clients d'abord", () => {
  const k = childrenMap(TREE.nodes);
  assert.deepEqual(k.get("").map((n) => n.id), ["gw"]);
  assert.deepEqual(k.get("gw").map((n) => n.id), ["core", "ap9"]);
  assert.deepEqual(k.get("core").map((n) => n.id), ["edge", "ap1"]);
});

test("treeLayout : parent centré au-dessus de ses enfants, clients regroupés puis dépliés", () => {
  const l = treeLayout(TREE, { nodeWidth: 100, gap: 10, rowHeight: 100, clientWidth: 50 });
  const p = (id) => l.positions.get(id);
  assert.equal(p("gw").y, 50); assert.equal(p("core").y, 150); assert.equal(p("ap2").y, 350);
  // le cœur est centré sur son sous-arbre (edge + ap1 + son groupe de clients)
  const kidsMin = Math.min(p("edge").x, p("ap1").x, l.groups.get("core").x), kidsMax = Math.max(p("edge").x, p("ap1").x, l.groups.get("core").x);
  assert.ok(p("core").x >= kidsMin && p("core").x <= kidsMax);
  assert.equal(l.groups.get("ap1").count, 3); assert.equal(l.groups.get("ap1").online, 2);
  assert.equal(l.groups.get("ap1").y, p("ap1").y + 100);
  assert.equal(l.clientPositions.size, 0);
  // dépliage : 3 feuilles clients sous la borne A, plus de groupe
  const e = treeLayout(TREE, { nodeWidth: 100, gap: 10, rowHeight: 100, clientWidth: 50, expanded: new Set(["ap1"]) });
  assert.equal(e.groups.has("ap1"), false);
  assert.equal([...e.clientPositions.keys()].filter((k) => k.startsWith("ap1|")).length, 3);
  assert.ok(e.width > l.width);
  assert.equal(e.height, 50 + 4 * 100);
});

test("treeEdges : ton par liaison ; treeSummary : comptes", () => {
  const ed = treeEdges(TREE);
  const tone = (id) => ed.find((e) => e.b === id).tone;
  assert.equal(tone("core"), "ok"); assert.equal(tone("edge"), "bad"); assert.equal(tone("ap2"), "muted"); assert.equal(tone("ap9"), "unlinked");
  assert.equal(ed.find((e) => e.b === "edge").a_port, 25);
  assert.deepEqual(treeSummary(TREE), { gateways: 1, switches: 2, aps: 3, clients: 4, clientsOnline: 3, loose: 1, offline: 1, unlinked: 1 });
});
