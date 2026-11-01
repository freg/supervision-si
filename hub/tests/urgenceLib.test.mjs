import test from "node:test";
import assert from "node:assert/strict";
import { sinceIso, sortEvents, summarize, groupEvents, urlBase64ToUint8Array, pushSupport, deviceLabel, normContacts, telHref, makeSnapshot, ago, QUICK_LINKS } from "../src/urgenceLib.js";

const EV = [
  { id: 1, at: "2026-10-20T08:00:00Z", severity: "warning", kind: "probe-alert", agent_id: "super", message: "disque 85 %" },
  { id: 2, at: "2026-10-20T09:00:00Z", severity: "critical", kind: "probe-alert", agent_id: "preprodia", message: "hub injoignable" },
  { id: 3, at: "2026-10-20T09:30:00Z", severity: "warning", kind: "probe-alert", agent_id: "super", message: "disque 85 %" },
  { id: 4, at: "2026-10-20T07:00:00Z", severity: "info", kind: "agent-up", agent_id: "pve-a", message: "agent revenu" },
];

test("#796 : tri, résumé et regroupement des alertes", () => {
  assert.deepEqual(sortEvents(EV).map((e) => e.id), [2, 3, 1, 4]);
  assert.deepEqual(summarize(EV), { critical: 1, warning: 2, hosts: ["preprodia", "super"], level: "critique" });
  assert.equal(summarize([EV[0]]).level, "alerte");
  assert.equal(summarize([]).level, "ok");
  const g = groupEvents(EV);
  assert.equal(g.length, 3);
  const disque = g.find((x) => x.message === "disque 85 %");
  assert.equal(disque.count, 2);
  assert.equal(disque.first, "2026-10-20T08:00:00Z");
  assert.equal(disque.last, "2026-10-20T09:30:00Z");
  assert.equal(sinceIso(24, Date.parse("2026-10-20T12:00:00.123Z")), "2026-10-19T12:00:00Z");
});

test("#796 : clé VAPID base64url -> octets", () => {
  const b = urlBase64ToUint8Array("BAEC_-8");
  assert.deepEqual([...b], [4, 1, 2, 255, 239]);
  assert.equal(urlBase64ToUint8Array("").length, 0);
});

test("#796 : capacités de l'appareil pour les alertes poussées", () => {
  const ok = { isSecureContext: true, serviceWorker: true, PushManager: true, Notification: true, permission: "default" };
  assert.equal(pushSupport(ok).ok, true);
  assert.match(pushSupport({ ...ok, isSecureContext: false }).reason, /https/);
  assert.match(pushSupport({ ...ok, PushManager: false, ios: true }).reason, /écran d'accueil/);
  assert.match(pushSupport({ ...ok, permission: "denied" }).reason, /réautoriser/);
  assert.equal(pushSupport().ok, false);
  assert.equal(deviceLabel("Mozilla/5.0 (Linux; Android 14) AppleWebKit Chrome/129 Mobile Safari/537"), "Android · Chrome");
  assert.equal(deviceLabel("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) Version/17 Mobile Safari/604"), "iOS · Safari");
  assert.equal(deviceLabel(""), "appareil");
});

test("#796 : contacts, liens tel:, instantané hors ligne, âge", () => {
  assert.deepEqual(normContacts([{ name: " Astreinte ", phone: "+33 6 00 00 00 00", role: "réseau" }, { name: "" }, null]),
    [{ name: "Astreinte", phone: "+33 6 00 00 00 00", role: "réseau" }]);
  assert.deepEqual(normContacts("x"), []);
  assert.equal(telHref("+33 6 00-00.00 00"), "tel:+33600000000");
  assert.equal(telHref("ab"), "");
  const s = makeSnapshot(EV, Date.parse("2026-10-20T10:00:00Z"));
  assert.equal(s.at, "2026-10-20T10:00:00.000Z");
  assert.equal(s.events[0].id, 2);
  assert.ok(!("details" in s.events[0]));
  const now = Date.parse("2026-10-20T10:00:00Z");
  assert.equal(ago("2026-10-20T09:59:30Z", now), "à l'instant");
  assert.equal(ago("2026-10-20T09:15:00Z", now), "il y a 45 min");
  assert.equal(ago("2026-10-20T07:30:00Z", now), "il y a 2 h 30");
  assert.equal(ago("2026-10-18T10:00:00Z", now), "il y a 2 j");
  assert.equal(ago("n'importe quoi", now), "");
  assert.ok(QUICK_LINKS.every((l) => l.view && l.label));
});
