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

// #659 : mise à jour git -- phrase d'état et bloqueurs
import { gitText, gitBlocker } from "../src/towerLib.js";
test("git : texte et bloqueurs", () => {
  const g = { branch: "main", current: "657", remote_number: "659", behind: 2, ahead: 0, dirty: [], head: { hash: "dd4ce73", subject: "feat: x" } };
  assert.match(gitText(g), /#657 → #659 : 2 commit\(s\) en retard sur origin\/main/);
  assert.equal(gitBlocker(g), null);
  assert.match(gitText({ ...g, behind: 0 }), /à jour sur origin\/main/);
  assert.equal(gitText({ error: "pas un clone" }), "pas un clone");
  assert.match(gitBlocker({ ...g, dirty: ["a.py"] }), /a\.py/);
  assert.match(gitBlocker({ ...g, ahead: 1 }), /non poussés/);
  assert.match(gitBlocker({ ...g, hint: "SSH" }), /SSH/);
  assert.match(gitBlocker({ ...g, fetch_error: "timeout" }), /fetch/);
});

// #662 : répartition -- lignes cohortes, déplacement, texte d'état d'un nœud
import { cohortRows, moveCohort, nodeText } from "../src/towerLib.js";
test("répartition : cohortRows / moveCohort / nodeText", () => {
  const data = { nodes: [{ name: "super", cohorts: ["core", "tickets"] }, { name: "vm-reseau", cohorts: ["reseau"] }], cohorts: [{ name: "core", services: ["hub"], manager: true }, { name: "reseau", services: ["cisco-api", "snmp-api"] }, { name: "tickets", services: ["tickets-api"] }, { name: "geo", services: ["geo-api"] }] };
  const rows = cohortRows(data);
  assert.deepEqual(rows.map((r) => [r.name, r.node, r.count]), [["core", "super", 1], ["reseau", "vm-reseau", 2], ["tickets", "super", 1], ["geo", "", 1]]);
  const moved = moveCohort(data.nodes, "tickets", "vm-reseau");
  assert.deepEqual(moved.map((n) => n.cohorts), [["core"], ["reseau", "tickets"]]);
  assert.deepEqual(moveCohort(data.nodes, "tickets", "").map((n) => n.cohorts), [["core"], ["reseau"]]);
  assert.deepEqual(data.nodes[0].cohorts, ["core", "tickets"]);   // pur
  assert.equal(nodeText(null), "—"); assert.match(nodeText({ error: "timeout" }), /injoignable/);
  assert.match(nodeText({ version: "661", running: ["a", "b"], missing: ["c"] }), /v661 · 2 en marche · 1 arrêté\(s\) : c/);
});
