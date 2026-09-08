import test from "node:test";
import assert from "node:assert/strict";
import { stepTitle, stepSummary, screensByTables, dbTablesLabel, journeyTree, storyboardFrame } from "../src/retroJourneys.js";

test("titres et résumés d'étapes", () => {
  assert.equal(stepTitle({ kind: "navigation", method: "POST", path: "/client/{n}/save" }), "POST /client/{n}/save");
  assert.equal(stepTitle({ kind: "navigation", method: "GET", path: "/clients", title: "Clients" }), "/clients — Clients");
  assert.equal(stepTitle({ kind: "mark", label: "après" }), "⚑ après");
  assert.equal(stepSummary({ actions: [{ kind: "click" }, { kind: "submit" }], inputs: [{}, {}], requests: [{ page: true }, { page: false }], queries: [{}] }),
    "1 clic(s), 2 saisie(s), 1 envoi(s), 1 requête(s) secondaire(s), 1 requête(s) SQL");
  assert.equal(stepSummary({}), "—");
  assert.equal(dbTablesLabel({ clients: { reads: 2, writes: 1 } }), "clients (2r/1w)");
});

test("matrice écrans × tables", () => {
  const m = screensByTables({ tables: { clients: {}, journal: {} }, screens: [
    { screen: "/clients", code_tables: { clients: ["x"] }, db_tables: { clients: { reads: 1 } } },
    { screen: "/client/{n}/save", code_tables: {}, db_tables: { journal: { writes: 1 } } },
  ] });
  assert.deepEqual(m.tables, ["clients", "journal"]);
  assert.deepEqual(m.rows[0].cells, { clients: "both", journal: null });
  assert.deepEqual(m.rows[1].cells, { clients: null, journal: "db" });
  assert.deepEqual(screensByTables(null), { tables: [], rows: [] });
});

test("#443 : arbre des parcours et image d'une étape", () => {
  const t = journeyTree([{ id: "a", name: "A" }, { id: "b", parent_id: "a" }, { id: "c", parent_id: "zz" }, { id: "d", parent_id: "b" }]);
  assert.deepEqual(t.map((j) => [j.id, j.depth]), [["a", 0], ["b", 1], ["d", 2], ["c", 0]]);
  const f = storyboardFrame({ kind: "navigation", path: "/clients", dom: { headings: ["Clients"], forms: [{ action: "/clients", fields: [{ name: "q", type: "text" }] }], tables: [{ headers: ["Nom"], rows: 3 }], links_count: 4 },
    actions: [{ kind: "click", text: "Dupont" }], replay: [{ action: "click", ok: true }], queries: [{ kind: "SELECT", tables: ["clients"] }] });
  assert.equal(f.title, "/clients"); assert.deepEqual(f.actions, ["click « Dupont »"]); assert.deepEqual(f.queries, ["SELECT clients"]);
  assert.equal(f.forms[0].method, "GET"); assert.equal(storyboardFrame(null), null);
});
