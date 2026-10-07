import test from "node:test";
import assert from "node:assert/strict";
import { detectorFields, paramsToText, textToParams, toLocalInput, fromLocalInput, plannedList, missingParams, move } from "../src/pveMaintLib.js";

test("champs des détecteurs", () => {
  const cat = { detectors: { backup_recent: { fields: ["vmid", "max_age_h", "storage?"] } } };
  assert.deepEqual(detectorFields(cat, "backup_recent").map((f) => [f.name, f.optional]), [["vmid", false], ["max_age_h", false], ["storage", true]]);
  assert.deepEqual(detectorFields(cat, "x"), []);
});

test("paramètres clé=valeur", () => {
  assert.deepEqual(textToParams("storage=local\nconfirm=101; mode = stop\n=x\nbad"), { storage: "local", confirm: 101, mode: "stop" });
  assert.equal(paramsToText({ a: 1, b: "x" }), "a=1\nb=x");
  assert.deepEqual(missingParams({ required: { destroy: ["confirm"] } }, { action: "destroy", params: {} }), ["confirm"]);
  assert.deepEqual(missingParams({ required: {} }, { action: "start" }), []);
});

test("dates et planning", () => {
  const e = fromLocalInput("2026-10-10T22:30");
  assert.equal(toLocalInput(e), "2026-10-10T22:30");
  assert.equal(fromLocalInput(""), null); assert.equal(toLocalInput(null), "");
  assert.deepEqual(plannedList([{ planned: [{ at: 3 }, { at: 1 }] }, { planned: [{ at: 2 }] }, {}]).map((p) => p.at), [1, 2, 3]);
  assert.deepEqual(move([1, 2, 3], 0, 1), [2, 1, 3]); assert.deepEqual(move([1, 2], 1, 1), [1, 2]);
});
