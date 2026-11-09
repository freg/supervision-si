// #999 : onglet ownCloud.
import test from "node:test";
import assert from "node:assert/strict";
import { depuis, filtrerComptes, trierComptes, repartition, barresActivite, avancement, go } from "../src/owncloudLib.js";

const NOW = 1_794_000_000, J = 86400;
const C = [
  { id: "u1", nom: "Alice ÉLAN", statut: "actif", origine: "ldap", go_fichiers: 10, go_corbeille: 1, derniere_connexion: NOW - 3600 },
  { id: "u2", nom: "Bob Bravo", statut: "inactif", origine: "ldap", go_fichiers: 80, go_corbeille: 40, derniere_connexion: NOW - 900 * J, doublon: true },
  { id: "dave", nom: "dave", statut: "jamais", origine: "locale", go_fichiers: 0, go_corbeille: 0, derniere_connexion: null },
];

test("ancienneté lisible", () => {
  assert.equal(depuis(NOW - 3600, NOW), "aujourd'hui"); assert.equal(depuis(NOW - 12 * J, NOW), "il y a 12 j");
  assert.equal(depuis(NOW - 200 * J, NOW), "il y a 7 mois"); assert.equal(depuis(NOW - 900 * J, NOW), "il y a 2 ans"); assert.equal(depuis(null, NOW), "jamais");
});

test("filtres et recherche au début d'un mot, sans accent", () => {
  assert.deepEqual(filtrerComptes(C, "inactif").map((c) => c.id), ["u2"]);
  assert.deepEqual(filtrerComptes(C, "doublon").map((c) => c.id), ["u2"]);
  assert.deepEqual(filtrerComptes(C, "locale").map((c) => c.id), ["dave"]);
  assert.deepEqual(filtrerComptes(C, "tous", "ela").map((c) => c.id), ["u1"]);
  assert.deepEqual(filtrerComptes(C, "tous", "ravo").map((c) => c.id), []);
});

test("tris", () => {
  assert.deepEqual(trierComptes(C).map((c) => c.id), ["u1", "u2", "dave"]);
  assert.deepEqual(trierComptes(C, "fichiers").map((c) => c.id), ["u2", "u1", "dave"]);
  assert.deepEqual(trierComptes(C, "nom").map((c) => c.id), ["u1", "u2", "dave"]);
});

test("répartition, activité, avancement, unités françaises", () => {
  const r = repartition({ fichiers: 871.8, corbeilles: 381.1, versions: 43.5 });
  assert.deepEqual(r.map((x) => x.pct), [67.2, 29.4, 3.4]);
  assert.deepEqual(repartition({}), []);
  const b = barresActivite([{ actions: 4 }, { actions: 400 }, { actions: 0 }]);
  assert.deepEqual(b.map((x) => x.h), [10, 100, 2]);
  assert.deepEqual(avancement([{ etat: "fait" }, { etat: "refuse" }, { etat: "a_decider", genre: "décision" }, { etat: "a_faire", genre: "étape" }]), { clos: 2, total: 4, decisions: 1 });
  assert.equal(go(381.1), "381,1 Go");
});
