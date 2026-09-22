// Matrice des droits (livraison #559).
import test from "node:test";
import assert from "node:assert/strict";
import { buildCatalog, grantIndex, cellState, grantFor, columnSubjects, applyVisibility, subjectKey, subjectFromKey, RESOURCE_TYPE } from "../src/rightsCatalog.js";

test("buildCatalog : toutes les tuiles des thématiques, actions selon l'API", () => {
  const cat = buildCatalog();
  const ids = cat.map((c) => c.identifier);
  assert.ok(ids.includes("nebula") && ids.includes("tickets") && ids.includes("accounts") && ids.includes("rights"));
  assert.equal(new Set(ids).size, ids.length);
  const neb = cat.find((c) => c.identifier === "nebula");
  assert.deepEqual(neb.actions, ["view", "manage"]); assert.equal(neb.manageType, "nebula-api"); assert.equal(neb.theme, "Réseau");
  assert.deepEqual(cat.find((c) => c.identifier === "logs").actions, ["view"]);
});

test("cellState / grantFor : vue précise ou large, gestion par API", () => {
  const cat = buildCatalog();
  const neb = cat.find((c) => c.identifier === "nebula"), logs = cat.find((c) => c.identifier === "logs");
  const idx = grantIndex([{ resource_type: RESOURCE_TYPE, resource_id: "nebula", group_name: "site-alpha", action: "view" },
                          { resource_type: RESOURCE_TYPE, resource_id: null, group_name: "techniciens", action: "view" },
                          { resource_type: "nebula-api", resource_id: null, group_name: "user:bob", action: "manage" }]);
  assert.deepEqual(cellState(idx, neb, "site-alpha", "view"), { allowed: true, wide: false, na: false });
  assert.deepEqual(cellState(idx, logs, "techniciens", "view"), { allowed: true, wide: true, na: false });
  assert.equal(cellState(idx, neb, "user:bob", "manage").allowed, true);
  assert.equal(cellState(idx, logs, "user:bob", "manage").na, true);
  assert.deepEqual(grantFor(neb, "site-alpha", "view", false), { resource_type: RESOURCE_TYPE, resource_id: "nebula", subject: "site-alpha", action: "view", allowed: false });
  assert.deepEqual(grantFor(neb, "site-alpha", "manage", true), { resource_type: "nebula-api", resource_id: null, subject: "site-alpha", action: "manage", allowed: true });
});

test("columnSubjects, clés de sujet, applyVisibility", () => {
  const cols = columnSubjects({ groups: ["techniciens", "admin_hub", "site-alpha"], users: ["bob"], known: ["user:carol", "group:direction"] });
  assert.deepEqual(cols.map(subjectKey), ["admin_hub", "direction", "site-alpha", "techniciens", "user:bob", "user:carol"]);
  assert.deepEqual(subjectFromKey("user:x"), { kind: "user", name: "x" });
  assert.deepEqual(subjectFromKey("group:y"), { kind: "group", name: "y" });
  const r = applyVisibility(new Set(["nebula", "cortex"]), [{ id: "tickets" }, { id: "vault" }], ["nebula", "vault"]);
  assert.deepEqual([...r.views], ["nebula"]); assert.deepEqual(r.fronts.map((f) => f.id), ["vault"]);
  const open = applyVisibility(new Set(["nebula"]), [{ id: "tickets" }], null);
  assert.equal(open.views.size, 1); assert.equal(open.fronts.length, 1);
});
