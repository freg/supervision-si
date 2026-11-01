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
import { paramsVisibles, valeursInitiales, brouillonDepuis, resumeParcours } from "../src/navigateurLib.js";
test("#799 : paramètres visibles, valeurs, brouillon, résumé", () => {
  const p = { acces: "gmao", etapes: [{ action: "goto" }, { action: "click", ecrit: true }],
    parametres: [{ nom: "identifiant", defaut: "alice" }, { nom: "mot_de_passe", secret: true }, { nom: "objet", defaut: "x" }, { nom: "site", defaut: "" }] };
  assert.deepEqual(paramsVisibles(p).map((x) => x.nom), ["objet", "site"]);
  assert.deepEqual(paramsVisibles({ ...p, acces: "" }).map((x) => x.nom), ["identifiant", "objet", "site"]);
  assert.deepEqual(valeursInitiales(p, { valeurs: { site: "beta" } }), { objet: "x", site: "beta" });
  assert.equal(brouillonDepuis({ base_url: "https://a", etapes: [1] }, "ovh1").navigateur, "ovh1");
  assert.equal(resumeParcours(p), "2 étapes · écrit (confirmation) · accès « gmao »");
});
