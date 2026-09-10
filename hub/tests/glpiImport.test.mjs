import test from "node:test";
import assert from "node:assert/strict";
import { previewRows, dropdownsLabel, describeSiAgent, describeGlpiAgent, importResultLine } from "../src/glpiImport.js";

test("previewRows : créations et mises à jour d'un aperçu, chaînes de compte rendu ignorées", () => {
  const rows = previewRows({
    created: [{ key: "srv-01", name: "srv-01", itemtype: "Computer", dropdowns: { manufacturers_id: "Dell Inc.", locations_id: "Arobase-5" } }],
    updated: [{ key: "pc-x", name: "pc-x", itemtype: "Computer", glpi_id: 7, matched_by: "name" }, "Computer 'z' -- id GLPI 3 mis à jour"],
  });
  assert.deepEqual(rows.map((r) => [r.key, r.action]), [["srv-01", "créer"], ["pc-x", "mettre à jour (id 7, trouvé par name)"]]);
  assert.equal(dropdownsLabel(rows[0]), "Dell Inc. / Arobase-5");
  assert.equal(dropdownsLabel(rows[1]), "—");
  assert.deepEqual(previewRows(null), []);
});

test("libellés de la comparaison et du compte rendu d'import", () => {
  assert.equal(describeSiAgent({ agent_id: "srv-01", site: "Arobase-5", online: "online" }), "srv-01 · Arobase-5 · online");
  assert.equal(describeSiAgent(null), "—");
  assert.equal(describeGlpiAgent({ version: "1.11", last_contact: "2026-09-08 08:00:00", itemtype: "Computer", items_id: 7 }), "v1.11 · contact 2026-09-08 08:00:00 · Computer #7");
  assert.equal(describeGlpiAgent({}), "?");
  assert.equal(importResultLine({ created: ["a"], updated: ["b"], skipped_existing: [], skipped_unselected: [], errors: [], warnings: ["x1 : sans inventaire"] }),
    "1 créé(s), 1 mis à jour, 0 déjà présent(s), 0 non sélectionné(s), 0 erreur(s). x1 : sans inventaire");
});
