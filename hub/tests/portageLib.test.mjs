import test from "node:test";
import assert from "node:assert/strict";
import { defaultSteps, summarizeDecisions, parseSmoke, statusLabel, slugify, STEP_LABELS } from "../src/portageLib.js";

test("defaultSteps : sans dump, pas d'étapes qui exigent la base", () => {
  assert.deepEqual(defaultSteps({ dump: false }), ["inventory", "scaffold", "routes", "install"]);
  assert.deepEqual(defaultSteps({ dump: true }), Object.keys(STEP_LABELS));
  assert.equal(defaultSteps(null).length, 7);
});

test("summarizeDecisions classe les décisions", () => {
  const r = summarizeDecisions([{ decision: "" }, { decision: "porter tel quel" }, { decision: "différer" }, { decision: "ne pas porter (mort)" }, { decision: "porter en simplifiant" }]);
  assert.deepEqual(r, { total: 5, porter: 2, differe: 1, mort: 1, vide: 1 });
  assert.deepEqual(summarizeDecisions(undefined), { total: 0, porter: 0, differe: 0, mort: 0, vide: 0 });
});

test("parseSmoke lit la synthèse et les routes", () => {
  const r = parseSmoke("# x\n\npytest : 2 passed · routes : 3×200\n\n| route | statut |\n|---|---|\n| `/` | 200 |\n| `/stats` | 500 |\n");
  assert.equal(r.summary, "pytest : 2 passed · routes : 3×200");
  assert.deepEqual(r.routes, [{ route: "/", status: "200" }, { route: "/stats", status: "500" }]);
  assert.deepEqual(parseSmoke(""), { summary: "", routes: [] });
});

test("statusLabel et slugify", () => {
  assert.equal(statusLabel({ running: true }), "en cours");
  assert.equal(statusLabel({ run_status: "failed" }), "en échec");
  assert.equal(statusLabel({ run_status: "" }), "jamais lancé");
  assert.equal(slugify("Gestion Clés 2"), "gestion-cl-s-2");
  assert.equal(slugify(""), "projet");
});
