// Synoptique en arbre (livraison #555).
import test from "node:test";
import assert from "node:assert/strict";
import { childrenMap, treeLayout, treeEdges, treeSummary, labelWidth } from "../src/nebulaTree.js";

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

test("treeLayout vertical étagé : parent centré, frères sur des sous-rangées, étiquettes entières", () => {
  const l = treeLayout(TREE, { stagger: 3, nodeHeight: 40, rowHeight: 100, clientWidth: 50 });
  const p = (id) => l.positions.get(id);
  assert.equal(l.orientation, "vertical");
  assert.equal(p("gw").depth, 0); assert.equal(p("core").depth, 1); assert.equal(p("ap2").depth, 3);
  assert.ok(p("core").y > p("gw").y && p("ap2").y > p("edge").y);
  // enfants de core : edge (index 0, sous-rangée 0), groupe de clients (1), ap1 (2) -> trois hauteurs différentes
  const ys = new Set([p("edge").y, l.groups.get("core").y, p("ap1").y]);
  assert.equal(ys.size, 3);
  assert.deepEqual([p("edge").tier, p("ap1").tier], [0, 2]);
  // le cœur est centré sur son sous-arbre
  const xs = [p("edge").x, p("ap1").x, l.groups.get("core").x];
  assert.ok(p("core").x >= Math.min(...xs) && p("core").x <= Math.max(...xs));
  assert.equal(l.groups.get("ap1").count, 3); assert.equal(l.groups.get("ap1").online, 2);
  assert.equal(l.clientPositions.size, 0);
  // largeur d'étiquette : jamais tronquée, bornée
  assert.ok(labelWidth({ name: "WBE660S-EU0101F-10", model: "WBE660S", kind: "ap" }) > 140);
  assert.equal(labelWidth({ name: "x".repeat(200), kind: "ap" }), 280);
  assert.ok(l.nodeWidth.get("gw") >= 120);
  // deux frères de même sous-rangée (index 0 et 3) ne se chevauchent pas
  const many = { nodes: [{ id: "r", name: "R", kind: "switch", parent: null, clients: [] }, ...Array.from({ length: 7 }, (_, i) => ({ id: "a" + i, name: "WBE660S-EU0101F-1" + i, kind: "ap", parent: "r", clients: [] }))] };
  const m = treeLayout(many, { stagger: 3 });
  const a0 = m.positions.get("a0"), a3 = m.positions.get("a3");
  assert.equal(a0.tier, a3.tier);
  assert.ok(Math.abs(a3.x - a0.x) >= m.nodeWidth.get("a0"));
  // dépliage : 3 feuilles clients sous la borne A, plus de groupe
  const e = treeLayout(TREE, { stagger: 3, clientWidth: 50, expanded: new Set(["ap1"]) });
  assert.equal(e.groups.has("ap1"), false);
  assert.equal([...e.clientPositions.keys()].filter((k) => k.startsWith("ap1|")).length, 3);
});

test("treeLayout horizontal : profondeur en colonnes, une ligne par feuille", () => {
  const l = treeLayout(TREE, { orientation: "horizontal", colWidth: 250, nodeHeight: 40 });
  const p = (id) => l.positions.get(id);
  assert.equal(l.orientation, "horizontal");
  assert.ok(p("core").x > p("gw").x && p("ap2").x > p("edge").x);
  // feuilles à des hauteurs distinctes, parent centré verticalement sur ses enfants
  const ys = [p("edge").y, p("ap1").y, l.groups.get("core").y];
  assert.equal(new Set(ys).size, 3);
  assert.ok(p("core").y >= Math.min(...ys) && p("core").y <= Math.max(...ys));
  assert.ok(l.height > l.width / 4);
});

test("treeEdges : ton par liaison ; treeSummary : comptes", () => {
  const ed = treeEdges(TREE);
  const tone = (id) => ed.find((e) => e.b === id).tone;
  assert.equal(tone("core"), "ok"); assert.equal(tone("edge"), "bad"); assert.equal(tone("ap2"), "muted"); assert.equal(tone("ap9"), "unlinked");
  assert.equal(ed.find((e) => e.b === "edge").a_port, 25);
  assert.deepEqual(treeSummary(TREE), { gateways: 1, switches: 2, aps: 3, clients: 4, clientsOnline: 3, loose: 1, offline: 1, unlinked: 1 });
});
