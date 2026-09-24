import test from "node:test";
import assert from "node:assert/strict";
import { itemsOf, mergeItems, emptyRow, cleanRow, statsText, deliveryText, touchesHub } from "../src/towerLib.js";

test("itemsOf accepte l'objet du registre ou une liste", () => {
  assert.deepEqual(itemsOf({ switches: [{ name: "a" }] }, "switches"), [{ name: "a" }]);
  assert.deepEqual(itemsOf([{ name: "b" }], "switches"), [{ name: "b" }]);
  assert.throws(() => itemsOf({ autre: [] }, "switches"));
});

test("fusion par nom (même règle que tower.py)", () => {
  const cur = [{ name: "a", host: "1" }, { name: "b", host: "2" }];
  const r = mergeItems(cur, [{ name: "b", host: "3" }, { name: "c", host: "4" }, { name: "a", host: "1" }]);
  assert.deepEqual(r.items.map((x) => x.host), ["1", "3", "4"]);
  assert.deepEqual(r.stats, { added: 1, updated: 1, unchanged: 1, removed: 0 });
  assert.equal(statsText(r.stats), "1 ajoutée(s), 1 mise(s) à jour, 1 identique(s)");
  assert.equal(mergeItems(cur, [{ name: "z" }], "name", "replace").stats.removed, 2);
});

test("lignes : défauts et nettoyage", () => {
  const fields = [{ name: "name" }, { name: "port", type: "int" }, { name: "platform", default: "ios" }, { name: "site" }];
  assert.deepEqual(emptyRow(fields), { platform: "ios" });
  assert.deepEqual(cleanRow({ name: " r1 ", port: "23", site: "" }, fields), { name: "r1", port: 23 });
});

test("résumés", () => {
  assert.equal(deliveryText({ current: "585", number: "586", changed: ["a"], added: [], unchanged: 10, kept: ["d"] }),
    "585 → 586 : 1 modifié(s), 0 ajouté(s), 10 inchangé(s), 1 donnée(s) locale(s) conservée(s)");
  assert.equal(touchesHub({ steps: [{ cmd: "./scripts/run.sh up -d --build hub nebula-api" }] }), true);
  assert.equal(touchesHub({ steps: [{ cmd: "./scripts/run.sh up -d --build nebula-api" }] }), false);
});
