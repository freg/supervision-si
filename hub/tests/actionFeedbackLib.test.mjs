import test from "node:test";
import assert from "node:assert/strict";
import { isMutating, buttonLabel, outcome, fromClick } from "../src/actionFeedbackLib.js";

test("envois concernés, libellés, issue", () => {
  assert.equal(isMutating({ method: "put" }), true); assert.equal(isMutating(undefined), false); assert.equal(isMutating({}, { method: "DELETE" }), true);
  assert.equal(buttonLabel("  ⏭  Étape\n suivante "), "⏭ Étape suivante"); assert.equal(buttonLabel("", "titre"), "titre"); assert.equal(buttonLabel("x".repeat(60)).length, 48);
  assert.deepEqual(outcome(200, true, { ok: true, message: "plan importé" }), { ok: true, text: "plan importé" });
  assert.deepEqual(outcome(200, true, null), { ok: true, text: "fait" });
  assert.deepEqual(outcome(409, false, { ok: false, message: "une étape tourne déjà" }), { ok: false, text: "échec : une étape tourne déjà" });
  assert.deepEqual(outcome(200, true, { ok: false, error: "refus" }), { ok: false, text: "échec : refus" });
  assert.deepEqual(outcome(0, false, null), { ok: false, text: "échec : pas de réponse du serveur" });
  assert.equal(fromClick(1000, 2000), true); assert.equal(fromClick(1000, 3000), false); assert.equal(fromClick(null, 5), false);
});
