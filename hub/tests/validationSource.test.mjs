// Provenance des tickets à valider (livraison #497).
import { test } from "node:test";
import assert from "node:assert/strict";
import { sourceText } from "../src/validationSource.js";

test("sourceText : libellé lisible + nom de source, tolérant", () => {
  assert.equal(sourceText({ source_type: "tableau", source_nom: "SUIVI:11" }), "tableau importé — SUIVI:11");
  assert.equal(sourceText({ source_type: "projeqtor", source_nom: "ProjeQtOr #7" }), "ProjeQtOr — ProjeQtOr #7");
  assert.equal(sourceText({ source_type: "inconnu" }), "inconnu", "type non répertorié : affiché tel quel");
  assert.equal(sourceText({ source_type: null }), "");
  assert.equal(sourceText(null), "");
});
