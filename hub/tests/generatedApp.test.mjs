import test from "node:test";
import assert from "node:assert/strict";
import { navScreens, listColumns, formScreenFor, editableFields, rowToValues, filterRows, specSummary } from "../src/generatedApp.js";

const spec = { counts: { screens: 3, nav: 2, with_table: 3, todo: 1 }, screens: [
  { id: "clients", kind: "list", nav: true, table: "clients", columns: [{ label: "Nom", column: "nom" }, { label: "Ville", column: null }] },
  { id: "client-n", kind: "form", nav: true, table: "clients", pk: "id", fields: [{ name: "id", column: "id" }, { name: "nom", column: "nom" }, { name: "csrf", column: null }] },
  { id: "save", kind: "action", nav: false, table: "clients" },
] };

test("navigation, colonnes, formulaire lié, champs éditables", () => {
  assert.deepEqual(navScreens(spec).map((s) => s.id), ["clients", "client-n"]);
  assert.deepEqual(listColumns(spec.screens[0], ["id", "nom", "email"]), [{ label: "Nom", column: "nom" }]);
  assert.deepEqual(listColumns({ columns: [] }, ["id", "nom"]), [{ label: "id", column: "id" }, { label: "nom", column: "nom" }]);
  assert.equal(formScreenFor(spec, spec.screens[0]).id, "client-n");
  assert.equal(formScreenFor(spec, { id: "x", table: null }), null);
  assert.deepEqual(editableFields(spec.screens[1]).map((f) => f.name), ["nom"]);
  assert.deepEqual(rowToValues(["id", "nom"], [1, "Dupont"]), { id: 1, nom: "Dupont" });
  assert.equal(filterRows([[1, "Dupont"], [2, "Durand"]], ["id", "nom"], "dur").length, 1);
  assert.equal(specSummary(spec), "3 écran(s), 2 dans la navigation, 3 rattaché(s) à une table, 1 point(s) à compléter");
});

test("missingFields : champs sans colonne (outil unique projeté)", async () => {
  const { missingFields } = await import("../src/generatedApp.js");
  const screen = { pk: "id", fields: [{ name: "nom", column: "name" }, { name: "remise", column: null }, { name: "ville", column: undefined }] };
  assert.deepEqual(missingFields(screen).map((f) => f.name), ["remise", "ville"]);
  assert.deepEqual(missingFields(null), []);
});
