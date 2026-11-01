import test from "node:test";
import assert from "node:assert/strict";
import { contractTone, filterContracts, gapSummary, softwareTotals, pickContract, defaultManager, fmtDays, filterGaps } from "../src/licensesLib.js";

const contracts = [
  { id: 1, software_id: 1, software: "Office 365", vendor: "Microsoft", kind: "subscription", quantity: 10, assigned: 12, days_left: 200, cost: 1200 },
  { id: 2, software_id: 2, software: "DraftSight", vendor: "Dassault", kind: "per-device", quantity: 2, assigned: 1, days_left: 30 },
  { id: 3, software_id: 3, software: "eDraw", vendor: "Wondershare", kind: "perpetual", quantity: 1, assigned: 1, days_left: null },
  { id: 4, software_id: 3, software: "eDraw", vendor: "Wondershare", kind: "perpetual", quantity: 1, assigned: 0, days_left: -5 },
];

test("lampe par contrat", () => {
  assert.equal(contractTone(contracts[0]), "red");     // sur-attribué
  assert.equal(contractTone(contracts[1]), "orange");  // expire dans 30 j
  assert.equal(contractTone(contracts[2]), "green");
  assert.equal(contractTone(contracts[3]), "red");     // expiré
  assert.equal(contractTone(null), "grey");
});

test("filtre début de mot d'abord", () => {
  assert.deepEqual(filterContracts(contracts, "d").map((c) => c.id), [2, 3, 4]);  // DraftSight / Dassault (début de mot) avant « eDraw »
  assert.deepEqual(filterContracts(contracts, "abonn").map((c) => c.id), [1]);
  assert.deepEqual(filterGaps([{ kind: "expired", severity: "critical", software: "a", text: "" }, { kind: "spare", severity: "info", software: "b", text: "" }], "", "info").map((g) => g.kind), ["spare"]);
});

test("résumé des écarts et totaux par logiciel", () => {
  const s = gapSummary([{ severity: "critical" }, { severity: "info" }, { severity: "info" }]);
  assert.deepEqual(s, { critical: 1, warning: 0, info: 2, total: 3, tone: "red" });
  assert.equal(gapSummary([]).tone, "green");
  const totals = softwareTotals(contracts, { 3: [{ host: "PC-1" }, { host: "PC-1" }, { host: "PC-2" }] });
  assert.deepEqual(totals.map((t) => [t.software, t.quantity, t.assigned, t.installed, t.contracts, t.tone]),
    [["DraftSight", 2, 1, 0, 1, "orange"], ["eDraw", 2, 1, 2, 2, "red"], ["Office 365", 10, 12, 0, 1, "red"]]);
});

test("choix du contrat pour une case et gestionnaire par OS", () => {
  const col = { contracts: [{ id: 1, kind: "per-user", quantity: 1, assigned: 1 }, { id: 2, kind: "per-device", quantity: 5, assigned: 0 }] };
  assert.equal(pickContract(col, "host").id, 2);
  assert.equal(pickContract(col, "user").id, 1);  // seul contrat utilisateur, même plein
  assert.equal(pickContract({ contracts: [] }, "user"), null);
  assert.equal(defaultManager("Windows 11"), "winget");
  assert.equal(defaultManager("darwin"), "brew");
  assert.equal(defaultManager("linux (fedora)"), "dnf");
  assert.equal(defaultManager("linux"), "apt");
  assert.equal(fmtDays(-3), "expiré depuis 3 j");
  assert.equal(fmtDays(12), "12 j");
});
