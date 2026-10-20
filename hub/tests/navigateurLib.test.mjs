import test from "node:test";
import assert from "node:assert/strict";
import { ecranUrl, lireEtapes, etatCommande, imageDe, trierNavigateurs } from "../src/navigateurLib.js";

test("#798 : écran, étapes, état des commandes", () => {
  const u = ecranUrl("ovh1");
  assert.ok(u.startsWith("/navigateur/ovh1/vnc.html?"));
  assert.ok(u.includes("path=navigateur%2Fovh1%2Fwebsockify"));
  assert.ok(ecranUrl("ovh1", { viewOnly: true }).includes("view_only=1"));
  assert.deepEqual(lireEtapes('[{"action":"goto","value":"/"}]').etapes, [{ action: "goto", value: "/" }]);
  assert.match(lireEtapes("[").erreur, /JSON/);
  assert.match(lireEtapes("[]").erreur, /non vide/);
  assert.match(lireEtapes('[{"value":1}]').erreur, /étape 1/);
  assert.equal(etatCommande({ status: "pending" }).etat, "attente");
  assert.equal(etatCommande({ status: "done", result: { ok: true, result: { titre: "Accueil" } } }).texte, "fait · Accueil");
  assert.equal(etatCommande({ status: "done", result: { ok: true, result: { statut: "confirmation" } } }).etat, "confirmation");
  assert.equal(etatCommande({ status: "failed", result: { ok: false, error: "parcours en échec" } }).texte, "parcours en échec");
  assert.equal(imageDe(""), "");
  assert.equal(imageDe("QUJD"), "data:image/jpeg;base64,QUJD");
  assert.deepEqual(trierNavigateurs([{ nom: "b" }, { nom: "a", libelle: "Zed" }]).map((n) => n.nom), ["b", "a"]);
});
