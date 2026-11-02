import test from "node:test";
import assert from "node:assert/strict";
import { niveauCase, filtrer, grille, resume, commandesAide, texteConstat, ageCollecte } from "../src/auditSecuriteLib.js";

const CS = [
  { id: "a", domaine: "wifi", niveau: "critique", probabilite: 4, impact: 4, score: 16, titre: "SSID ouvert", preuve: "open", preconisation: "WPA3", effort: "faible", source: "nebula", etat: "a_traiter" },
  { id: "b", domaine: "acces", niveau: "eleve", probabilite: 3, impact: 3, score: 9, titre: "SSH root", preuve: "yes", preconisation: "clés", effort: "faible", source: "proxmox", etat: "traite", note: "fait" },
  { id: "c", domaine: "wifi", niveau: "faible", probabilite: 1, impact: 2, score: 2, titre: "clients éphémères", preuve: "", preconisation: "", effort: "moyen", source: "historique" },
];

test("niveauCase : mêmes seuils que le serveur", () => {
  assert.equal(niveauCase(4, 4), "critique"); assert.equal(niveauCase(3, 4), "critique"); assert.equal(niveauCase(2, 4), "eleve");
  assert.equal(niveauCase(2, 2), "modere"); assert.equal(niveauCase(1, 3), "faible");
});

test("filtrer : domaine, niveau, état, case, texte", () => {
  assert.deepEqual(filtrer(CS, { domaine: "wifi" }).map((c) => c.id), ["a", "c"]);
  assert.deepEqual(filtrer(CS, { niveau: "eleve" }).map((c) => c.id), ["b"]);
  assert.deepEqual(filtrer(CS, { etat: "a_traiter" }).map((c) => c.id), ["a", "c"]);   // état absent = à traiter
  assert.deepEqual(filtrer(CS, { cas: { p: 3, i: 3 } }).map((c) => c.id), ["b"]);
  assert.deepEqual(filtrer(CS, { q: "wpa" }).map((c) => c.id), ["a"]);
  assert.equal(filtrer(null).length, 0);
});

test("grille et résumé", () => {
  const m = { total: 3, par_niveau: { critique: 1, eleve: 1, faible: 1 }, cases: { 4: { 4: ["a"] }, 3: { 3: ["b"] }, 2: { 1: ["c"] } } };
  const g = grille(m);
  assert.equal(g.length, 4); assert.equal(g[0][3].n, 1); assert.equal(g[0][3].niveau, "critique"); assert.equal(g[1][2].n, 1); assert.equal(g[2][0].n, 1); assert.equal(g[3][0].n, 0);
  assert.equal(resume(m), "3 constat(s) — 1 critique(s), 1 élevé(s), 0 modéré(s), 1 faible(s)");
  assert.equal(resume(null), "0 constat(s) — 0 critique(s), 0 élevé(s), 0 modéré(s), 0 faible(s)");
});

test("aide, texte et âge", () => {
  const a = commandesAide("https://hub/api/nebula", "s1");
  assert.match(a.proxmox, /audit-proxmox\.sh/); assert.match(a.proxmox, /sites\/s1\/audit\/importer/); assert.match(a.hote, /<ip>/);
  const t = texteConstat(CS[1], { acces: "Accès" });
  assert.match(t, /Domaine : Accès/); assert.match(t, /3 × impact 3 = 9/); assert.match(t, /Note : fait/);
  assert.equal(ageCollecte(null), "jamais"); assert.equal(ageCollecte(1000 - 120, 1000), "il y a 2 min"); assert.equal(ageCollecte(10, 10 + 2 * 86400), "il y a 2 j");
});
