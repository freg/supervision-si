import test from "node:test";
import assert from "node:assert/strict";
import { requete, fmtAgeH, fmtMin, fmtOctets, taux5xx, compte } from "../src/prepLib.js";

test("préparation : requête", () => {
  assert.equal(requete({ cible: "pve-3", accueil: "pve-2", params: { debit_lan: 50, ip_min: "" }, transferes: [119, 102] }),
    "cible=pve-3&accueil=pve-2&debit_lan=50&transferes=102%2C119");
  assert.equal(requete({}), "");
});

test("préparation : formats", () => {
  assert.equal(fmtAgeH(0.2), "12 min");
  assert.equal(fmtAgeH(30), "30 h");
  assert.equal(fmtAgeH(240), "10 j");
  assert.equal(fmtAgeH(null), "—");
  assert.equal(fmtMin(25), "25 min");
  assert.equal(fmtMin(100), "1 h 40");
  assert.equal(fmtMin(120), "2 h");
  assert.equal(fmtOctets(370e9), "370 Go");
  assert.equal(fmtOctets(1.24e12), "1,2 To");
  assert.equal(fmtOctets(0), "—");
  assert.equal(taux5xx({ http_total: 1000, http_5xx: 150 }), 15);
  assert.equal(taux5xx({}), null);
  assert.deepEqual(compte([{ pra: { verdict: "ok" } }, { pra: { verdict: "bloquant" } }, {}], "pra"), { ok: 1, attention: 0, bloquant: 1, inconnu: 1 });
});
