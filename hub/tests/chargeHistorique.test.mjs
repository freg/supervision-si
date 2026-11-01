// #932 : historique des tests de charge -- résumé et comparaison.
import { test } from "node:test";
import assert from "node:assert/strict";
import { tonVerdict, resumeRun, comparer, METRIQUES } from "../src/chargeHistorique.js";

const RUN1 = { at: "2026-10-30T09:00:00Z", data: { verdict: "défaut reproduit", epreuves: ["cpu", "disque"],
  processeur: { coeurs: 20, coeurs_finis: 20, gel_max_s: 0, erreurs_calcul: 0 },
  disque: { ecriture_mo_s: 112, lecture_mo_s: 190, identique: false, statut: "ok" },
  temperatures_apres: [{ celsius: 71 }, { celsius: 68 }], alerts: [{ severity: "critical", message: "relecture différente" }] } };
const RUN2 = { at: "2026-10-30T11:00:00Z", data: { verdict: "aucun défaut reproduit", epreuves: ["cpu", "disque", "memoire"],
  processeur: { coeurs: 20, coeurs_finis: 20, gel_max_s: 2.8, erreurs_calcul: 0 },
  memoire: { mo: 8192, blocs_errones: 0 }, disque: { ecriture_mo_s: 185, lecture_mo_s: 316, identique: true, statut: "ok" },
  temperatures_apres: [{ celsius: 60 }], alerts: [] } };

test("ton du verdict", () => {
  assert.equal(tonVerdict("aucun défaut reproduit"), "good");
  assert.equal(tonVerdict("non concluant"), "warn");
  assert.equal(tonVerdict("défaut reproduit"), "bad");
  assert.equal(tonVerdict("interrompu"), "neutral");
});

test("résumé d'un run", () => {
  const r = resumeRun(RUN1);
  assert.equal(r.verdict, "défaut reproduit");
  assert.equal(r.ton, "bad");
  assert.equal(r.epreuves, "cpu, disque");
  assert.match(r.disque, /DIFFÉRENTE/);
  assert.equal(r.temp, 71);
  assert.equal(r.critiques, 1);
  const r2 = resumeRun(RUN2);
  assert.match(r2.cpu, /figé 2.8s/);
  assert.equal(r2.critiques, 0);
  assert.equal(resumeRun({}).verdict, "—");
});

test("comparaison côte à côte", () => {
  const c = comparer([RUN2, RUN1]);
  assert.equal(c.entetes.length, 2);
  assert.equal(c.entetes[0].verdict, "aucun défaut reproduit");
  assert.equal(c.lignes.length, METRIQUES.length);
  const relecture = c.lignes.find((l) => l[0] === "Disque — relecture");
  assert.deepEqual(relecture, ["Disque — relecture", "identique", "DIFFÉRENTE"]);
  const gel = c.lignes.find((l) => l[0] === "Processeur — gel max");
  assert.deepEqual(gel, ["Processeur — gel max", "2.8 s", "0 s"]);
});

test("export CSV", async () => {
  const { csvHistorique } = await import("../src/chargeHistorique.js");
  const csv = csvHistorique([RUN1, RUN2]);
  assert.ok(csv.startsWith("﻿"), "BOM UTF-8 pour Excel");
  const lignes = csv.trim().split("\r\n");
  assert.equal(lignes.length, 3, "en-tête + 2 runs");
  assert.match(lignes[0], /^﻿?Date;Verdict;Épreuves/);
  assert.match(lignes[1], /défaut reproduit;cpu disque/);
  assert.match(lignes[1], /DIFFÉRENTE/);
  assert.match(lignes[2], /2,8/, "virgule décimale (gel 2.8 -> 2,8)");
});
