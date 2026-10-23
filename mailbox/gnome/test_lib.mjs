// si-mailbox (#843) : mise en forme du widget GNOME (node --test mailbox/gnome/test_lib.mjs)
import { test } from "node:test";
import assert from "node:assert/strict";
import { resume } from "./si-mailbox@exemple.fr/lib.js";

test("texte, état et lignes du widget", () => {
  const d = { maj: 1000, dossier: "INBOX", total: 12, comptes: [{ nom: "pro", n: 12 }], filtres: [{ nom: "Banque", n: 3 }, { nom: "Facture", n: 0 }], erreurs: [] };
  const r = resume(d, 1030);
  assert.equal(r.texte, "12 · 3");
  assert.equal(r.etat, "filtre");
  assert.deepEqual(r.lignes, ["Non lus (INBOX) : 12", "Banque : 3", "Facture : 0", "Relevé à l'instant"]);
  assert.equal(resume({ ...d, filtres: [], total: 0 }, 1030).texte, "0");
  assert.equal(resume({ ...d, filtres: [], total: 0 }, 1030).etat, "calme");
  assert.equal(resume(d, 1000 + 1200).etat, "ancien");
  assert.equal(resume({ ...d, comptes: [], erreurs: ["pro : refusé"] }, 1030).texte, "!");
  assert.equal(resume(null, 0).etat, "absent");
});
