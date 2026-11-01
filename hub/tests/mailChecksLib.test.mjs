import test from "node:test";
import assert from "node:assert/strict";
import { slug, newTest, newIndicator, validate, toPayload, testState, summary, TEMPLATES } from "../src/mailChecksLib.js";

test("#770 : nouveaux tests et indicateurs, identifiants", () => {
  assert.equal(slug("Lien piégé (colis)"), "lien-piege-colis");
  const t = newTest("eicar");
  assert.deepEqual([t.id, t.template, t.expect], ["virus-de-test-eicar", "eicar", ["Blocked INFECTED"]]);
  assert.equal(newTest("custom", "Hameçonnage").subject, "");
  assert.equal(newIndicator("Rejets TLS", "TLS library problem").window_minutes, 60);
  assert.ok(TEMPLATES.gtube.expect.includes("Blocked SPAM"));
});

test("#770 : validation (mêmes règles que l'agent)", () => {
  const ok = { canary: { to: "test@exemple.org" }, tests: [newTest("clean", "Ordinaire")], indicators: [newIndicator("Auth", "authentication failed")] };
  assert.deepEqual(validate(ok), []);
  assert.ok(validate({ canary: { to: "pas une adresse" } }).length);
  assert.ok(validate({ tests: [{ ...newTest("clean"), expect: ["bloqué"] }] })[0].includes("verdict attendu"));
  assert.ok(validate({ indicators: [{ ...newIndicator("x x", "("), id: "xx" }] })[0].includes("expression invalide"));
  assert.ok(validate({ tests: [newTest("clean", "A1"), newTest("clean", "A1")] }).some((e) => e.includes("double")));
});

test("#770 : contenu écrit sur l'agent -- éléments par défaut retirés listés", () => {
  const cat = { canary: { to: " test@exemple.org ", every_hours: "2" },
    tests: [{ id: "clean", label: "x", template: "clean", expect: ["Passed CLEAN"], enabled: true }],
    indicators: [{ id: "auth-failed", label: "a", regex: "x", window_minutes: "30", warn_above: "", crit_above: "100", enabled: true }] };
  const p = toPayload(cat);
  assert.equal(p.canary.to, "test@exemple.org"); assert.equal(p.canary.every_hours, 2);
  assert.deepEqual(p.remove, ["spam-gtube", "virus-eicar", "banned-exe", "bad-header", "dnsbl-rejects"]);
  assert.deepEqual([p.indicators[0].window_minutes, p.indicators[0].warn_above, p.indicators[0].crit_above], [30, null, 100]);
});

test("#770 : états des tests et synthèse", () => {
  const block = { canary: { to: "t@x.fr" }, tests: [
    { id: "a", enabled: true, last: { ok: true } }, { id: "b", enabled: true, last: { ok: false } },
    { id: "c", enabled: true, pending: true }, { id: "d", enabled: true }, { id: "e", enabled: false }],
    indicators: [{ state: "ok" }, { state: "warning" }] };
  assert.deepEqual(block.tests.map(testState), ["ok", "echec", "attente", "jamais", "inactif"]);
  assert.deepEqual(summary(block), { tests: 4, ok: 1, failed: 1, pending: 1, indicatorsAlert: 1, configured: true });
  assert.equal(summary({}).configured, false);
});
