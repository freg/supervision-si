// Tests des helpers purs de la cloche de notifications (livraison
// #490, généralisée #491 : SMS + alertes Zenoss, #493 : notifications diverses).
import { test } from "node:test";
import assert from "node:assert/strict";
import { relativeTime, smsTitle, notifExcerpt, zenossTitle, zenossExcerpt, zenossLineTone, notificationTitle, notificationExcerpt, bellTone } from "../src/notifBell.js";

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

test("smsTitle : expéditeur interprété, sinon sujet, sinon enveloppe", () => {
  assert.equal(smsTitle({ fields: { sender: "+33612345678" }, subject: "SMS de +33612345678" }), "+33612345678");
  assert.equal(smsTitle({ subject: "Alerte" }), "Alerte");
  assert.equal(smsTitle({ from_addr: "gw@sms.lan" }), "gw@sms.lan");
  assert.equal(smsTitle({}), "?");
});

test("notifExcerpt : texte interprété, troncature propre", () => {
  assert.equal(notifExcerpt({ fields: { text: "reunion avancee" } }), "reunion avancee");
  assert.equal(notifExcerpt({ summary: "SMS de x : coucou" }), "SMS de x : coucou");
  const long = { fields: { text: "mot ".repeat(40).trim() } };
  const out = notifExcerpt(long, 90);
  assert.ok(out.length <= 91 && out.endsWith("…"), "tronqué avec ellipse");
  assert.equal(notifExcerpt({}), "");
});

test("zenossTitle : équipement interprété, sinon sujet", () => {
  assert.equal(zenossTitle({ fields: { device: "sw-coeur" } }), "sw-coeur");
  assert.equal(zenossTitle({ subject: "[Site A] sw-coeur Ping degrade" }), "[Site A] sw-coeur Ping degrade");
  assert.equal(zenossTitle({}), "?");
});

test("zenossExcerpt : message + sévérité + localisation ; résolution préfixée", () => {
  const active = { fields: { device: "sw-coeur", message: "Ping degrade", severite: "Warning", localisation: "/Parc", clear: false } };
  assert.equal(zenossExcerpt(active), "Ping degrade (Warning) — /Parc");
  const clear = { fields: { device: "sw-coeur", clear_message: "Ping OK", clear: true } };
  assert.ok(zenossExcerpt(clear).startsWith("Résolution :"), "une résolution ne passe jamais pour une alerte");
  assert.equal(zenossExcerpt({ summary: "alerte x : y" }), "alerte x : y");
});

test("zenossLineTone : sévérité → ton, tolérant au texte libre", () => {
  assert.equal(zenossLineTone({ fields: { clear: true } }), "ok");
  assert.equal(zenossLineTone({ fields: { severite: "Critical" } }), "bad");
  assert.equal(zenossLineTone({ fields: { severite: "error" } }), "bad");
  assert.equal(zenossLineTone({ fields: { severite: "Warning" } }), "warn");
  assert.equal(zenossLineTone({ fields: { severite: "Info" } }), "neutral", "non reconnu : jamais rouge par défaut");
  assert.equal(zenossLineTone({ fields: {} }), "neutral");
});

test("notificationTitle/Excerpt : sujet en titre, expéditeur en extrait (#493)", () => {
  const n = { fields: { subject: "Sauvegarde terminee", from: "backup@lan" } };
  assert.equal(notificationTitle(n), "Sauvegarde terminee");
  assert.equal(notificationExcerpt(n), "de backup@lan");
  assert.equal(notificationTitle({ from_addr: "cron@lan" }), "cron@lan");
  assert.equal(notificationTitle({}), "?");
  assert.equal(notificationExcerpt({ summary: "notif" }), "notif");
  assert.equal(notificationExcerpt({}), "");
});

test("bellTone : rouge si alertes supervision, ambre si SMS ou notifications", () => {
  assert.equal(bellTone({}), "neutral");
  assert.equal(bellTone({ smsUnread: 3 }), "warn");
  assert.equal(bellTone({ notifUnread: 1 }), "warn", "notifications diverses : ambre aussi (#493)");
  assert.equal(bellTone({ zenossUnread: 1 }), "bad");
  assert.equal(bellTone({ smsUnread: 3, notifUnread: 2, zenossUnread: 1 }), "bad", "la supervision prime");
  assert.equal(bellTone({ zenossUnread: 2, failed: true }), "neutral", "API injoignable : neutre, signalé par le title");
});
