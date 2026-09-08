import test from "node:test";
import assert from "node:assert/strict";
import { layoutGraph, nodeHeight, edgePath, edgeMidpoint, edgeLabel, graphSummary, proposalSummary, fieldInventory, NODE_W, HEAD_H, ROW_H } from "../src/metaGraph.js";

const graph = {
  apps: ["crm", "gestion"],
  nodes: [
    { id: "crm:customers", app: "crm", table: "customers", columns: [{ name: "customer_id", pk: true, term: "client" }, { name: "name", term: "nom", screens: ["customers"] }] },
    { id: "gestion:clients", app: "gestion", table: "clients", columns: [{ name: "id", pk: true, term: "id" }, { name: "nom", term: "nom" }, { name: "ville_id", term: "ville" }] },
    { id: "gestion:villes", app: "gestion", table: "villes", columns: [{ name: "id", pk: true, term: "id" }] },
  ],
  edges: [
    { from: "gestion:clients", to: "gestion:villes", kind: "fk", columns: [["ville_id", "id"]], sources: ["code"] },
    { from: "crm:customers", to: "gestion:clients", kind: "equiv", columns: [["name", "nom"], ["customer_id", "id"], ["mail", "email"]], sources: ["même nom de table"] },
  ],
  counts: { nodes: 3, columns: 6, fk: 1, equiv: 1, xref: 0 },
};

test("layoutGraph : une colonne par application, nœuds empilés", () => {
  const l = layoutGraph(graph);
  assert.equal(l.columns.length, 2);
  assert.equal(l.columns[0].app, "crm");
  assert.ok(l.columns[1].x > l.columns[0].x + NODE_W);
  assert.equal(l.nodes["gestion:clients"].x, l.nodes["gestion:villes"].x);
  assert.ok(l.nodes["gestion:villes"].y > l.nodes["gestion:clients"].y + l.nodes["gestion:clients"].h);
  assert.equal(nodeHeight(graph.nodes[1]), HEAD_H + 3 * ROW_H + 6);
  assert.equal(nodeHeight({ columns: new Array(12).fill({ name: "c" }) }), HEAD_H + 9 * ROW_H + 6);
  assert.ok(l.width > 0 && l.height > 0);
  assert.deepEqual(layoutGraph(null).columns, []);
});

test("edgePath / edgeMidpoint / edgeLabel", () => {
  const l = layoutGraph(graph);
  assert.match(edgePath(l, graph.edges[0]), /^M .* C /);
  assert.match(edgePath(l, graph.edges[1]), /^M .* C /);
  assert.equal(edgePath(l, { from: "x", to: "y" }), null);
  const m = edgeMidpoint(l, graph.edges[1]);
  assert.ok(m.x > l.nodes["crm:customers"].x && m.x < l.nodes["gestion:clients"].x + NODE_W);
  assert.equal(edgeLabel(graph.edges[1]), "name ↔ nom (+2)");
  assert.equal(edgeLabel(graph.edges[0]), "ville_id ↔ id");
  assert.equal(edgeLabel({ columns: [] }), "");
});

test("résumés et relevé des champs", () => {
  assert.equal(graphSummary(graph), "3 entité(s), 6 attribut(s), 1 relation(s), 1 équivalence(s), 0 référence(s) inter-gestion");
  assert.equal(proposalSummary({ counts: { entities: 2, merged: 1, kept: 1, relations: 1, conflicts: 0, orphans: 2 } }), "2 entité(s) cible(s) : 1 fusionnée(s), 1 reprise(s) telle(s) quelle(s) ; 1 relation(s) ; 0 conflit(s) de type, 2 attribut(s) propre(s)");
  const inv = fieldInventory(graph);
  assert.equal(inv.length, 6);
  const name = inv.find((r) => r.app === "crm" && r.column === "name");
  assert.deepEqual(name.equivalents, ["gestion:clients.nom"]);
  assert.deepEqual(name.screens, ["customers"]);
  const nom = inv.find((r) => r.app === "gestion" && r.column === "nom");
  assert.deepEqual(nom.equivalents, ["crm:customers.name"]);
  assert.deepEqual(inv.find((r) => r.column === "ville_id").equivalents, []);
  assert.deepEqual(fieldInventory(null), []);
});
