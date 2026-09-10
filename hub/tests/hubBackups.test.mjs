import test from "node:test";
import assert from "node:assert/strict";
import { fmtSize, restorePoint, chainSummary, scheduleText, lastRunText } from "../src/hubBackups.js";

test("formats", () => {
  assert.equal(fmtSize(2970704), "2.8 Mo");
  assert.equal(fmtSize(512), "512 o");
  assert.equal(scheduleText({ incremental_every_hours: 6, full_weekday: 6, full_hour: 2 }), "incrémentale toutes les 6 h, totale le dimanche à 2h");
  assert.equal(scheduleText({ incremental_every_hours: 0, full_weekday: null }), "manuelle");
  assert.equal(lastRunText(null), "aucune exécution depuis le démarrage du service");
  assert.match(lastRunText({ kind: "full", rc: 1, ended_at: "t" }), /totale ÉCHOUÉE/);
});

test("point de restauration = totale + incrémentales jusqu'à la session", () => {
  const chain = { full: { name: "f1", size: 10 }, increments: [{ name: "i1", size: 1 }, { name: "i2", size: 1 }, { name: "i3", size: 1 }], size: 13 };
  assert.deepEqual(restorePoint(chain, "i2").map((m) => m.name), ["f1", "i1", "i2"]);
  assert.deepEqual(restorePoint(chain, "f1").map((m) => m.name), ["f1"]);
  assert.deepEqual(restorePoint(chain, "zz"), []);
  assert.equal(chainSummary(chain), "totale + 3 incrémentales · 13 o");
  assert.equal(chainSummary({ full: null, increments: [{}], size: 0 }), "sans totale (orphelines) + 1 incrémentale · 0 o");
});
