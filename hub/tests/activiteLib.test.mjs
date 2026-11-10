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

import { resumeCategorie, texteCategorie } from "../src/activiteLib.js";

test("catégorie : résumé et détail", () => {
  const c = { categorie: "mobile Android", confiance: 72, incertain: false, population: 120,
    hypotheses: [{ categorie: "mobile Android", score: 80, preuves: [{ poids: 40, texte: "système annoncé « Android »" }, { poids: -15, texte: "x" }] }],
    singularites: [{ texte: "fabricant « Edimax » : seul client du site dans ce cas" }] };
  assert.equal(resumeCategorie(c), "Catégorie proposée : mobile Android — confiance 72 %");
  const t = texteCategorie(c);
  assert.match(t, /\+40 {2}système annoncé/);
  assert.match(t, /-15 {2}x/);
  assert.match(t, /aux 120 clients du site/);
  assert.match(resumeCategorie({ categorie: null }), /pas assez/);
});

import { celluleCategorie } from "../src/activiteLib.js";

test("#1004 : colonne catégorie, confirmation, pas de verdict de régularité sur une relève", () => {
  assert.deepEqual(celluleCategorie({ categorie: "machine Linux / sans écran", confiance: 44, niveau: "moyenne" }), { texte: "machine Linux / sans écran · 44 %", couleur: "var(--warning)" });
  assert.equal(celluleCategorie({ categorie: "imprimante", confiance: 100, niveau: "confirmée" }).texte, "✔ imprimante");
  assert.equal(celluleCategorie({ categorie: null, niveau: "aucune" }).texte, "aucune");
  assert.match(resumeCategorie({ categorie: "imprimante", decision: { par: "freg" }, proposee: "poste Windows" }), /confirmée : imprimante \(par freg\) — le hub proposait poste Windows/);
  const l = resumeActivite({ jours: 14, jours_vus: 1, heures_par_jour: 2, volumes: { mesures: 1, moyenne_heure: 1, pointe_heure: 1, regularite_cv: 0, part_descendant: 0.5 } });
  assert.doesNotMatch(l[3], /régulier/);
});
