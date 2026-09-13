// Tests des helpers purs de la cloche SMS (livraison #490).
import { test } from "node:test";
import assert from "node:assert/strict";
import { relativeTime, notifTitle, notifExcerpt, bellTone } from "../src/smsBell.js";

const NOW = new Date("2026-09-13T12:00:00Z");

test("relativeTime : échelles et garde-fous", () => {
  assert.equal(relativeTime("2026-09-13T11:59:40Z", NOW), "à l'instant");
  assert.equal(relativeTime("2026-09-13T11:57:00Z", NOW), "il y a 3 min");
  assert.equal(relativeTime("2026-09-13T10:00:00Z", NOW), "il y a 2 h");
  assert.equal(relativeTime("2026-09-08T12:00:00Z", NOW), "il y a 5 j");
  assert.equal(relativeTime("2026-09-13T13:00:00Z", NOW), "à l'instant", "futur = navigateur en avance");
  assert.equal(relativeTime("pas une date", NOW), "", "illisible : jamais de NaN");
  assert.equal(relativeTime(null, NOW), "");
});

test("notifTitle : expéditeur interprété, sinon sujet, sinon enveloppe", () => {
  assert.equal(notifTitle({ fields: { sender: "+33612345678" }, subject: "SMS de +33612345678" }), "+33612345678");
  assert.equal(notifTitle({ subject: "Alerte" }), "Alerte");
  assert.equal(notifTitle({ from_addr: "gw@sms.lan" }), "gw@sms.lan");
  assert.equal(notifTitle({}), "?");
});

test("notifExcerpt : texte interprété, troncature propre", () => {
  assert.equal(notifExcerpt({ fields: { text: "reunion avancee" } }), "reunion avancee");
  assert.equal(notifExcerpt({ summary: "SMS de x : coucou" }), "SMS de x : coucou");
  const long = { fields: { text: "mot ".repeat(40).trim() } };
  const out = notifExcerpt(long, 90);
  assert.ok(out.length <= 91 && out.endsWith("…"), "tronqué avec ellipse");
  assert.equal(notifExcerpt({}), "");
});

test("bellTone : ambre si non lu, jamais rouge, neutre sinon", () => {
  assert.equal(bellTone(0), "neutral");
  assert.equal(bellTone(3), "warn");
  assert.equal(bellTone(3, true), "neutral", "API injoignable : neutre, signalé par le title");
});
