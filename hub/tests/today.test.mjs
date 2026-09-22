// Tests de la vue « Aujourd'hui » (livraison #544).
import test from "node:test";
import assert from "node:assert/strict";
import { servicesSummary, ticketsSummary, incidentsSummary, overall } from "../src/today.js";

test("services : tout va bien / pannes et dégradés en phrases", () => {
  assert.equal(servicesSummary(null).tone, "unknown");
  assert.deepEqual(servicesSummary({ services: [{ etat: "ok" }] }), { tone: "ok", headline: "Tout fonctionne.", lines: [] });
  const s = servicesSummary({ services: [{ etat: "panne" }, { etat: "panne" }, { etat: "degrade" }, { etat: "ok" }], phrases: ["Wi-Fi : en panne, donc Imprimante ne marche pas."] });
  assert.equal(s.tone, "panne");
  assert.equal(s.headline, "2 services en panne, 1 dégradé.");
  assert.equal(s.lines.length, 1);
  assert.equal(servicesSummary({ services: [{ etat: "degrade" }] }).headline, "1 service dégradé.");
});

test("demandes : en cours, en attente, en retard, reçues/résolues sur 24 h", () => {
  const now = 1_000_000;
  const rows = [
    { ts_created: now - 3600 },                                   // nouvelle, en attente
    { ts_created: now - 3 * 86400, user_login: "bob" },           // prise, mais vieille (retard = sans réponse > 2 j)
    { ts_created: now - 5 * 86400, ts_closed: now - 100 },        // résolue aujourd'hui
    { ts_created: now - 10, archived_at: 1 },                     // archivée : ignorée du « en cours »
  ];
  const t = ticketsSummary(rows, now);
  assert.equal(t.headline, "2 demandes en cours.");
  assert.deepEqual(t.lines, ["1 en attente de prise en charge", "1 sans réponse depuis plus de deux jours", "2 reçues et 1 résolue depuis 24 h"]);
  assert.equal(t.tone, "panne");
  assert.equal(ticketsSummary([], now).headline, "Aucune demande en cours.");
  assert.equal(ticketsSummary([], now).tone, "ok");
  assert.equal(ticketsSummary(undefined).tone, "unknown");
});

test("incidents : titres, critiques, pris en charge, troncature", () => {
  assert.equal(incidentsSummary([]).headline, "Aucun incident en cours.");
  const inc = incidentsSummary([{ title: "Cœur de réseau injoignable", severity: "critical" }, { title: "Onduleur sur batterie", severity: "warning", state: "acked" }]);
  assert.equal(inc.headline, "2 incidents en cours, dont 1 critique.");
  assert.deepEqual(inc.lines, ["Cœur de réseau injoignable", "Onduleur sur batterie (pris en charge)"]);
  assert.equal(inc.tone, "panne");
  const many = incidentsSummary(Array.from({ length: 7 }, (_, i) => ({ title: "i" + i, severity: "warning" })));
  assert.equal(many.lines.length, 6);
  assert.equal(many.lines[5], "… et 2 autres");
  assert.equal(many.tone, "degrade");
});

test("mot du jour : la pire des trois", () => {
  assert.equal(overall([{ tone: "ok" }, { tone: "ok" }]), "Journée calme : tout fonctionne.");
  assert.equal(overall([{ tone: "ok" }, { tone: "unknown" }]), "Certaines informations manquent.");
  assert.equal(overall([{ tone: "degrade" }, { tone: "unknown" }]), "Quelques points à surveiller.");
  assert.equal(overall([{ tone: "panne" }, { tone: "ok" }]), "Des problèmes en cours demandent une action.");
});
