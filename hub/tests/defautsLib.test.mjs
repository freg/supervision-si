// Tests #975 : bandeau des défauts majeurs.
import { test } from "node:test";
import assert from "node:assert/strict";
import { visibles, ignores, resume, nomFichier, defautsAffiches } from "../src/defautsLib.js";

const DS = [
  { id: 1, code: "historique-clients.enregistrement", statut: "ouvert", ignore: false, occurrences: 16, premiere: 1793900000, derniere: 1793950000 },
  { id: 2, code: "x", statut: "ouvert", ignore: true, occurrences: 1, premiere: 1793900000 },
  { id: 3, code: "y", statut: "resolu", ignore: false },
];

test("visibles / ignorés : seuls les défauts ouverts comptent", () => {
  assert.deepEqual(visibles(DS).map((d) => d.id), [1]);
  assert.deepEqual(ignores(DS).map((d) => d.id), [2]);
  assert.deepEqual(visibles(null), []);
});

test("résumé, nom de fichier, jeton interne absent", () => {
  assert.match(resume(DS[0]), /^16 fois depuis le .+, dernière .+/);
  assert.match(resume(DS[1]), /^le /);
  assert.equal(nomFichier(DS[0], new Date(2026, 10, 6, 9, 5).getTime()), "defaut-historique-clients.enregistrement-20261106-0905.txt");
  assert.deepEqual(defautsAffiches({ defauts: DS, jeton_interne: true }).map((d) => d.id), [1]);
  assert.equal(defautsAffiches({ defauts: DS, jeton_interne: false })[0].code, "notify.jeton-interne");
});

test("étiquette courte", async () => {
  const { etiquette } = await import("../src/defautsLib.js");
  assert.equal(etiquette({ titre: "Historique des clients Nebula : les relèves ne sont pas enregistrées" }), "Historique des clients Nebula");
  assert.equal(etiquette({ titre: "x".repeat(60) }).length, 40);
  assert.equal(etiquette({ code: "a.b" }), "a.b");
});
