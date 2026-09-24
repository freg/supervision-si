import test from "node:test";
import assert from "node:assert/strict";
import { byModule, filterActions, effectiveGroups, parseEmails, queueSummary, groupLabel } from "../src/notifyLib.js";

const actions = [
  { id: "mikrotik.nat.add", module: "mikrotik", label: "Règle NAT ajoutée", groups: [], default_group: "auto:mikrotik" },
  { id: "mikrotik.*", module: "mikrotik", label: "", groups: ["m:infra"], default_group: "auto:mikrotik" },
  { id: "cisco.restore", module: "cisco", label: "Restauration", groups: ["g:astreinte"], default_group: "auto:cisco" },
  { id: "cisco.backup", module: "cisco", label: "Sauvegarde", groups: [], default_group: "auto:cisco" },
];

test("groupement par module et filtre", () => {
  assert.deepEqual(byModule(actions).map(([m, xs]) => [m, xs.length]), [["cisco", 2], ["mikrotik", 2]]);
  assert.deepEqual(filterActions(actions, "rest").map((a) => a.id), ["cisco.restore"]);
});

test("groupes effectifs : action > module.* > défaut", () => {
  assert.deepEqual(effectiveGroups(actions[0], actions), { groups: ["m:infra"], source: "module" });
  assert.deepEqual(effectiveGroups(actions[2], actions), { groups: ["g:astreinte"], source: "action" });
  assert.deepEqual(effectiveGroups(actions[3], actions), { groups: ["auto:cisco"], source: "défaut" });
});

test("emails et résumés", () => {
  assert.deepEqual(parseEmails("A@x.test, b@x.test;  a@x.test\nc@x.test"), ["a@x.test", "b@x.test", "c@x.test"]);
  assert.equal(queueSummary({ queued: 2, sent: 10, held: 1 }), "2 en file, 1 retenu, 10 envoyé");
  assert.equal(queueSummary({}), "file vide");
  assert.equal(groupLabel({ name: "Infra", kind: "meta", resolved: ["a", "b"] }), "Infra (méta) — 2 adresses");
});
