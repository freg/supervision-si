// #995 : mesure des mises à jour de la tour.
import test from "node:test";
import assert from "node:assert/strict";
import { tonCharge, tonIo, duree, etapeLaPlusLongue, texteComparaison } from "../src/towerMesuresLib.js";

test("tons de charge et d'attente disque", () => {
  assert.equal(tonCharge(3, 4), "ok"); assert.equal(tonCharge(6, 4), "warn"); assert.equal(tonCharge(9, 4), "bad");
  assert.equal(tonCharge(null, 4), ""); assert.equal(tonCharge(0.5, 0), "ok");
  assert.equal(tonIo(5), "ok"); assert.equal(tonIo(15), "warn"); assert.equal(tonIo(45), "bad"); assert.equal(tonIo(null), "");
});

test("durées lisibles", () => {
  assert.equal(duree(42), "42 s"); assert.equal(duree(125), "2 min 05"); assert.equal(duree(3725), "1 h 02"); assert.equal(duree(null), "—");
});

test("étape la plus longue", () => {
  assert.equal(etapeLaPlusLongue({ etapes: [{ label: "a", duree_s: 3 }, { label: "b", duree_s: 90 }, { label: "c", duree_s: null }] }).label, "b");
  assert.equal(etapeLaPlusLongue({ etapes: [] }), null);
});

test("comparaison à la main / par la tour", () => {
  assert.equal(texteComparaison({}), "pas encore de construction mesurée");
  const t = texteComparaison({ main: { n: 3, secondes_par_service: 60, services_par_lancement: 2 }, tour: { n: 2, secondes_par_service: 150, services_par_lancement: 6 } });
  assert.match(t, /à la main : 1 min 00 par service/);
  assert.match(t, /par la tour : 2 min 30 par service \(6 service/);
  assert.match(t, /rapport 2,5×/);
});
