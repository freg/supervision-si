import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { updatesWithLinks, entryLabel, shortDate } from "../src/hubUpdatesLib.js";

test("#762 : la dernière livraison figure dans hubUpdates.json (python3 scripts/gen-hub-updates.py à chaque livraison)", () => {
  const items = JSON.parse(readFileSync(new URL("../src/hubUpdates.json", import.meta.url), "utf-8"));
  const last = Number(readFileSync(new URL("../../shared/DELIVERY_NUMBER", import.meta.url), "utf-8").trim());
  assert.ok(items.length > 0); assert.ok(items[0].n >= last, `hubUpdates.json s'arrête à #${items[0].n}, livraison courante #${last}`);
});

test("#762 : liens des mises à jour (nouvelles tuiles, écrans modifiés, plages de livraisons)", () => {
  const themes = [{ entries: [{ view: "infra", label: "Infra PVE / PBS" }, { view: "nebula", label: "Nebula" }, { front: "assistant", label: "Assistant IA" }] }];
  const r = updatesWithLinks([{ n: 750, from: 749, date: "2026-10-14", title: "x" }, { n: 751, date: "2026-10-14", title: "y" }],
    { since: { infra: 749, "action:aide": 750 }, links: { 750: [{ view: "nebula", hint: "h" }, { view: "infra" }], 751: [{ front: "assistant" }] }, themes });
  assert.deepEqual(r[0].links.map((l) => [l.view, l.label, !!l.isNew]), [["infra", "Infra PVE / PBS", true], ["nebula", "Nebula", false]]);
  assert.equal(r[1].links[0].label, "Assistant IA");
  assert.equal(entryLabel({ view: "inconnue" }, themes), "inconnue");
  assert.equal(shortDate("2026-10-14"), "14/10");
});

test("#790 : les liens de mise à jour gardent leurs paramètres d'écran (onglet précis)", async () => {
  const { updatesWithLinks } = await import("../src/hubUpdatesLib.js");
  const [u] = updatesWithLinks([{ n: 9001, date: "2026-10-19", title: "x" }], {
    since: {}, themes: [], links: { 9001: [{ view: "notifications", params: { tab: "sms" } }, { view: "notifications" }] } });
  assert.equal(u.links.length, 2);
  assert.deepEqual(u.links[0].params, { tab: "sms" });
});
