import { test } from "node:test";
import assert from "node:assert/strict";
import { octetsFr, resumeActivite, barres } from "../src/activiteLib.js";

test("octets à la française", () => {
  assert.equal(octetsFr(950), "950 o");
  assert.equal(octetsFr(1_500_000).replace(/ | /g, " "), "1,5 Mo");
  assert.equal(octetsFr(null), "—");
});

test("résumé d'activité", () => {
  const l = resumeActivite({ jours: 14, jours_vus: 5, heures_par_jour: 5, continu: false, part_nuit: 0, part_weekend: 0, wifi: true, ssids: ["atelier"], bornes: ["a", "b"], vlans: ["22"],
    volumes: { mesures: 25, moyenne_heure: 12_000_000, pointe_heure: 40_000_000, regularite_cv: 1.4, part_descendant: 0.9 } });
  assert.match(l[0], /Présent 5 jour\(s\) sur 14/);
  assert.match(l[2], /Wi-Fi \(atelier\) — 2 équipements \(mobile\) — VLAN 22/);
  assert.match(l[3], /par rafales/);
  assert.deepEqual(resumeActivite({ jours: 14, jours_vus: 0 }), ["Aucune présence enregistrée sur 14 jours."]);
  assert.match(resumeActivite({ jours: 7, jours_vus: 7, heures_par_jour: 24, continu: true, filaire: true, volumes: {} })[3], /non publiés/);
});

test("barres", () => {
  assert.deepEqual(barres([0, 2, 4]), [0, 0.5, 1]);
  assert.deepEqual(barres([0, 0]), [0, 0]);
});
