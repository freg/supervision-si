import test from "node:test";
import assert from "node:assert/strict";
import { roleInitials } from "../src/lib.js";

test("roleInitials (#554) : uniques, allongées si besoin", () => {
  assert.deepEqual(roleInitials(["Administrateur", "Demandeur", "Direction", "Maître des clés", "Service", "Supervision", "Technicien"]), ["A", "De", "Di", "M", "Se", "Su", "T"]);
  assert.deepEqual(roleInitials(["Technicien"]), ["T"]);
  assert.deepEqual(roleInitials([]), []);
});
