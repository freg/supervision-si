import test from "node:test";
import assert from "node:assert/strict";
import { matchRank, rankFilter } from "../src/textFilter.js";

test("début de mot avant contenu, accents et casse ignorés", () => {
  assert.equal(matchRank("Nebula", "n"), 0);
  assert.equal(matchRank("Onduleurs (UPS)", "n"), 1);
  assert.equal(matchRank("Cycle agile réseau", "res"), 0);
  assert.equal(matchRank("Comptes et groupes", "x"), -1);
  assert.equal(matchRank("Évènements", "eve"), 0);
  const items = ["Onduleurs", "Agents hôtes", "Nebula", "Sondes réseau", "Netmap"];
  assert.deepEqual(rankFilter(items, "n", (s) => s), ["Nebula", "Netmap", "Onduleurs", "Agents hôtes", "Sondes réseau"]);
  assert.deepEqual(rankFilter(items, "", (s) => s), items);
  assert.deepEqual(rankFilter(items, "N", (s) => s, (a, b) => a.localeCompare(b)), ["Nebula", "Netmap", "Agents hôtes", "Onduleurs", "Sondes réseau"]);
});
