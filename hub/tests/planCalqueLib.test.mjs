// Tests #973 : calque du plan (espaces délimités, étiquettes typées).
import { test } from "node:test";
import assert from "node:assert/strict";
import { cliquerTrace, ajouterForme, ajouterEtiquette, retirer, renommer, espaceDe, centroide, dansPolygone, normaliserCalque, CALQUE_VIDE } from "../src/planCalqueLib.js";

const CARRE = [[0, 0], [0.5, 0], [0.5, 0.5], [0, 0.5]];

test("tracé : points ajoutés, fermeture en recliquant le premier point (3 points au moins)", () => {
  let r = cliquerTrace([], [0, 0]);
  assert.deepEqual(r, { points: [[0, 0]], ferme: false });
  r = cliquerTrace([[0, 0], [0.5, 0]], [0.001, 0.001]);
  assert.equal(r.ferme, false);                              // 2 points : pas encore un polygone
  r = cliquerTrace([[0, 0], [0.5, 0], [0.5, 0.5]], [0.005, 0.004]);
  assert.equal(r.ferme, true);
  assert.equal(r.points.length, 3);
});

test("formes et étiquettes : ajout, identifiants uniques, renommage, effacement", () => {
  let c = ajouterForme(CALQUE_VIDE, { nom: " Studio ", points: CARRE });
  c = ajouterForme(c, { type: "zone", nom: "Aile nord", points: [[0, 0], [1, 0], [1, 1], [0, 1]] });
  assert.deepEqual(c.formes.map((f) => [f.id, f.nom, f.type]), [["f1", "Studio", "espace"], ["f2", "Aile nord", "zone"]]);
  assert.equal(ajouterForme(c, { nom: "x", points: [[0, 0], [1, 1]] }).formes.length, 2);   // moins de 3 points : refusé
  c = ajouterEtiquette(c, { type: "spot", texte: "WBE660S-1", x: 0.1, y: 0.1 });
  assert.equal(ajouterEtiquette(c, { texte: "  ", x: 0.1, y: 0.1 }).etiquettes.length, 1);  // texte vide : refusé
  assert.equal(c.etiquettes[0].id, "e1");
  c = renommer(c, "f1", "Studio TV");
  assert.equal(c.formes[0].nom, "Studio TV");
  c = retirer(c, "e1");
  assert.equal(c.etiquettes.length, 0);
  assert.deepEqual(normaliserCalque(null), { formes: [], etiquettes: [] });
});

test("espace d'un point : l'espace prime sur la zone, le plus petit sur l'englobant", () => {
  let c = ajouterForme(CALQUE_VIDE, { type: "zone", nom: "Aile", points: [[0, 0], [1, 0], [1, 1], [0, 1]] });
  c = ajouterForme(c, { nom: "Studio", points: CARRE });
  c = ajouterForme(c, { nom: "Régie", points: [[0.1, 0.1], [0.2, 0.1], [0.2, 0.2], [0.1, 0.2]] });
  assert.equal(espaceDe(c, 0.15, 0.15), "Régie");
  assert.equal(espaceDe(c, 0.4, 0.4), "Studio");
  assert.equal(espaceDe(c, 0.9, 0.9), "Aile");
  assert.equal(espaceDe(c, null, 0.2), null);
  assert.ok(dansPolygone(0.25, 0.25, CARRE) && !dansPolygone(0.75, 0.25, CARRE));
  assert.deepEqual(centroide(CARRE).map((v) => Math.round(v * 100) / 100), [0.25, 0.25]);
});
