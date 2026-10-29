// #919 : libellés, durées et motifs de refus de l'onglet « Analyse à distance ».
import { test } from "node:test";
import assert from "node:assert/strict";
import { STATUTS, MODES, actif, duree, refus, permis, libelle, date } from "../src/shellDistance.js";

test("statuts : actifs (relevé toutes les 3 s) et libellés connus ou repli", () => {
  assert.ok(actif("en_attente") && actif("lance") && actif("en_cours"));
  assert.ok(!actif("fini") && !actif("refuse") && !actif("delai"));
  assert.deepEqual(libelle(STATUTS, "refuse"), ["refusée par le poste", "bad"]);
  assert.deepEqual(libelle(STATUTS, "inconnu"), ["inconnu", "neutral"]);
  assert.equal(libelle(MODES, "intervention")[1], "warn");
});

test("durée : secondes, minutes, heures, en cours", () => {
  assert.equal(duree({ debut: 100, fin: 142 }), "42 s");
  assert.equal(duree({ debut: 100, fin: 100 + 185 }), "3 min 05");
  assert.equal(duree({ debut: 0, fin: 3 * 3600 + 7 * 60 }), "3 h 07");
  assert.equal(duree({ debut: 1000 }, 1010), "10 s");
  assert.equal(duree({}), "—");
});

test("refus de la garde et modes permis", () => {
  const s = "SI-SHELL-REFUS : ligne 1 : « Remove-Item » peut modifier le poste\nSI-SHELL-REFUS : ligne 2 : écriture dans un fichier\n";
  assert.deepEqual(refus(s), ["ligne 1 : « Remove-Item » peut modifier le poste", "ligne 2 : écriture dans un fichier"]);
  assert.deepEqual(refus("rien"), []);
  assert.ok(permis("lecture", "lecture") && !permis("lecture", "intervention") && permis("intervention", "intervention"));
  assert.ok(!permis("off", "lecture") && !permis(null, "lecture"));
});

test("date : ISO avec ou sans Z, valeur vide", () => {
  assert.match(date("2026-10-29T15:00:09Z"), /^\d\d\/\d\d \d\d:\d\d$/);
  assert.match(date("2026-10-29 15:00:09"), /^29\/10 /);
  assert.equal(date(null), "—");
});
