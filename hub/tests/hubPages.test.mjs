import { test } from "node:test";
import assert from "node:assert/strict";
import { pagesCatalogue, catalogueRecherche } from "../src/hubPages.js";
import { universeEntries } from "../src/hubTree.js";

test("« historique » trouve l'historique des clients quand Nebula est disponible", () => {
  const cat = new Map([["view:retro", { id: "view:retro", kind: "view", view: "retro", label: "Historique des évolutions" }]]);
  const r = universeEntries(catalogueRecherche(cat, new Set(["retro", "nebula"])), { query: "historique" });
  assert.deepEqual(r.map((l) => l.id).sort(), ["page:nebula-historique", "view:retro"]);
  assert.equal(universeEntries(catalogueRecherche(cat, new Set(["nebula"])), { query: "tablettes" })[0].id, "page:nebula-surveillance");
  assert.equal(pagesCatalogue(new Set(["retro"])).length, 0);
});
