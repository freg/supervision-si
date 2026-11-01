// #928 : helpers de l'onglet « Accès services ».
import { test } from "node:test";
import assert from "node:assert/strict";
import { secondes, codeTon, resume } from "../src/accesServicesLib.js";

test("formats", () => {
  assert.equal(secondes(null), "—");
  assert.equal(secondes(1234), "1,23 s");
  assert.equal(secondes(80), "0,08 s");
  assert.equal(codeTon(200), "good");
  assert.equal(codeTon(302), "warn");
  assert.equal(codeTon(401), "bad");
  assert.equal(codeTon(503), "bad");
  assert.equal(codeTon(null), "");
});

test("synthèse d'un résultat", () => {
  const r = resume({ sites: [
    { brut: { total_ms: 120, status: 200 }, authentifie: { total_ms: 400, connecte: true } },
    { brut: { erreur: "connect-echec" }, authentifie: null },
    { brut: { total_ms: 2500, status: 200 }, authentifie: { total_ms: 6000, connecte: true } },
    { brut: { total_ms: 100, status: 200 }, authentifie: { total_ms: 300, connecte: false } },
  ] });
  assert.equal(r.sites, 4);
  assert.equal(r.injoignables, 1);
  assert.equal(r.refuses, 1);
  assert.equal(r.authentifies, 3);
  assert.equal(r.lents, 1, "un seul site lent (brut >2s et auth >5s sur le même) -- compté une fois");
  assert.deepEqual(resume(null), { sites: 0, injoignables: 0, refuses: 0, lents: 0, authentifies: 0 });
});
