// Tuile « Accès d'équipements » (livraison #498) : réservée aux
// administrateurs et techniciens, absente sans URL, rattachée à la
// thématique Sécurité & accès.
import test from "node:test";
import assert from "node:assert/strict";
import { buildFrontsList } from "../src/lib.js";
import { THEMES } from "../src/hubThemes.js";

const ids = (groups, credentialsUrl = "https://hub/credentials/") =>
  buildFrontsList({ groups, credentialsUrl }).map((f) => f.id);

test("tuile credentials : admin et technicien la voient, un demandeur non, absente sans URL", () => {
  assert.ok(ids(["administrateurs"]).includes("credentials"));
  assert.ok(ids(["techniciens"]).includes("credentials"));
  assert.ok(!ids(["demandeurs"]).includes("credentials"));
  assert.ok(!ids(["administrateurs"], "").includes("credentials"));
});

test("thématique Sécurité & accès : entrée front:credentials", () => {
  const sec = THEMES.find((t) => t.id === "securite");
  assert.ok(sec.entries.some((e) => e.front === "credentials"));
});
