import test from "node:test";
import assert from "node:assert/strict";
import { functionMatrix, fieldOrigin, sourceLabel, unifiedSummary, canCompare, coverage } from "../src/unifiedTool.js";

const cmp = {
  apps: ["crm", "gestion"],
  groups: [{ function: "Fiche client", kind: "form", score: 0.7, why: ["champs communs : email, nom"], apps: ["gestion", "crm"],
    screens: [{ app: "gestion", id: "client-n", title: "Fiche client" }, { app: "crm", id: "customer-n", title: "Fiche client" }],
    common_fields: ["email", "nom"], specific_fields: { gestion: ["remise"], crm: ["tel"] } }],
  unique: [{ app: "gestion", id: "produits", title: "Produits", kind: "list" }],
  counts: { groups: 1, shared_by_all: 1, unique: 1, screens: { crm: 2, gestion: 3 } },
};

test("functionMatrix : une ligne par fonction puis par écran propre", () => {
  const rows = functionMatrix(cmp);
  assert.equal(rows.length, 2);
  assert.equal(rows[0].function, "Fiche client");
  assert.equal(rows[0].shared, true);
  assert.equal(rows[0].cells.crm.id, "customer-n");
  assert.equal(rows[1].function, "Produits");
  assert.equal(rows[1].cells.crm, null);
  assert.equal(rows[1].cells.gestion.id, "produits");
  assert.deepEqual(rows[1].why, ["propre à gestion"]);
  assert.deepEqual(functionMatrix(null), []);
});

test("fieldOrigin / sourceLabel", () => {
  const f = { name: "nom", apps: ["crm", "gestion"], sources: { crm: { table: "customers", column: "name" }, gestion: { table: "clients", column: null } } };
  assert.equal(fieldOrigin(f, ["crm", "gestion"]), "commun");
  assert.equal(fieldOrigin({ apps: ["crm"] }, ["crm", "gestion"]), "propre à crm");
  assert.equal(fieldOrigin({}, ["crm"]), "");
  assert.equal(sourceLabel(f, "crm"), "customers.name");
  assert.equal(sourceLabel(f, "gestion"), "clients (colonne inconnue)");
  assert.equal(sourceLabel(f, "compta"), null);
});

test("résumé, sélection, recouvrement", () => {
  assert.equal(unifiedSummary({ counts: { screens: 4, shared: 2, partial: 0, unique: 2 } }), "4 écran(s) : 2 commun(s) à toutes, 0 partagé(s) par certaines, 2 propre(s) à une application");
  assert.equal(unifiedSummary(null), "");
  assert.equal(canCompare(["a"]), false);
  assert.equal(canCompare(["a", "b"]), true);
  assert.equal(coverage(cmp, "crm", "gestion"), 50);
  assert.equal(coverage(cmp, "crm", "crm"), null);
});
