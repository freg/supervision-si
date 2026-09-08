import test from "node:test";
import assert from "node:assert/strict";
import { layout, describeNode, nodeActions, checkoutText, LANE_W, ROW_H, LEFT, TOP } from "../src/versionGraph.js";

const graph = {
  nodes: [{ version: 1, parent: null, branch: "principale", status: "draft" }, { version: 2, parent: 1, branch: "principale", status: "superseded" },
    { version: 3, parent: 1, branch: "variante", status: "official", author: "freg", archived: true }],
  edges: [{ from: 1, to: 2 }, { from: 1, to: 3 }], lanes: { 1: 0, 2: 0, 3: 1 }, checkout: null,
};

test("mise en page : voies en colonnes, versions en lignes, fourche courbée", () => {
  const l = layout(graph);
  assert.equal(l.nodes[0].x, LEFT); assert.equal(l.nodes[2].x, LEFT + LANE_W);
  assert.equal(l.nodes[1].y, TOP + ROW_H);
  assert.equal(l.edges[0].fork, false); assert.match(l.edges[0].d, /^M.* L/);
  assert.equal(l.edges[1].fork, true); assert.match(l.edges[1].d, /^M.* C/);
  assert.equal(l.width, LEFT + 2 * LANE_W + 12);
  assert.equal(layout(null).nodes.length, 0);
});

test("libellés et actions", () => {
  assert.equal(describeNode(graph.nodes[2]), "v3 · officielle · branche variante · dérivée de v1 · freg · archive immuable");
  assert.equal(describeNode(graph.nodes[1]), "v2 · remplacée");
  assert.deepEqual(nodeActions(graph.nodes[0], graph, "freg"), ["official", "archive", "checkout"]);
  assert.deepEqual(nodeActions({ status: "archived" }, { checkout: { user: "freg" } }, "freg"), ["checkin"]);
  assert.deepEqual(nodeActions({ status: "official" }, { checkout: { user: "eve" } }, "freg"), ["archive"]);
  assert.match(checkoutText({ user: "eve", version_number: 2, checked_out_at: "t" }, "freg"), /sorti par eve \(à partir de v2\).*lecture seule/);
  assert.equal(checkoutText(null, "freg"), "disponible (personne ne l'a sorti)");
});
