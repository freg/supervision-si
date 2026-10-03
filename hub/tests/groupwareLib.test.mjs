import test from "node:test";
import assert from "node:assert/strict";
import { rightsLabel, maskToText, myGrants, categoryTree, collectionNameOk, APPS } from "../src/groupwareLib.js";

test("droits : libellés et masque", () => {
  assert.equal(rightsLabel("r"), "lecture"); assert.equal(rightsLabel("raedp"), "tout"); assert.equal(rightsLabel("rp"), "lire, voir le privé"); assert.equal(rightsLabel(""), "aucun");
  assert.equal(maskToText(15), "raed"); assert.equal(maskToText(31), "raedp"); assert.equal(maskToText(0), "");
  assert.ok(APPS.calendar);
});
test("partages donnés / reçus", () => {
  const data = { grants: [{ owner: "bob", app: "calendar", grantee: "alice", rights: 1 }, { owner: "carol", app: "calendar", grantee: "bob", rights: 1 }], effective: { calendar: { bob: 31, carol: 1, alice: 15 }, infolog: { bob: 31 } } };
  const m = myGrants(data, "bob");
  assert.deepEqual(Object.keys(m.given), ["calendar"]); assert.deepEqual(m.received, [{ app: "calendar", owner: "alice", rights: "raed" }, { app: "calendar", owner: "carol", rights: "r" }]);
});
test("catégories en arbre, partagées d'abord ; convention de nom des collections", () => {
  const t = categoryTree([{ id: 1, name: "Perso", owner: "bob", parent_id: 0 }, { id: 2, name: "Bâtiment", owner: "", parent_id: 0 }, { id: 3, name: "Toiture", owner: "", parent_id: 2 }]);
  assert.deepEqual(t.map((r) => r.name), ["Bâtiment", "Perso"]); assert.equal(t[0].children[0].name, "Toiture");
  assert.ok(collectionNameOk("calendar", "agenda-equipe")); assert.ok(!collectionNameOk("calendar", "perso")); assert.ok(collectionNameOk("addressbook", "Contacts-clients")); assert.ok(collectionNameOk("infolog", "x"));
});

import { contactToForm, formToContact, contactRow, EMPTY_CONTACT } from "../src/groupwareLib.js";
test("carnet : formulaire <-> contact, ligne", () => {
  const c = { fn: "Alice Martin", first: "Alice", last: "Martin", org: "Alpha", tels: [{ type: "work", value: "01" }, { type: "cell", value: "06" }], emails: [{ value: "a@exemple.fr" }], adr: { street: "5 rue", zip: "86000", city: "Villexemple", country: "France" }, categories: ["client", "VIP"], rights: "rae" };
  const f = contactToForm(c); assert.equal(f.tel, "01"); assert.equal(f.cell, "06"); assert.equal(f.city, "Villexemple"); assert.equal(f.categories, "client, VIP");
  const back = formToContact(f); assert.deepEqual(back.tels, [{ type: "work", value: "01" }, { type: "cell", value: "06" }]); assert.deepEqual(back.categories, ["client", "VIP"]); assert.equal(back.adr.zip, "86000");
  assert.equal(formToContact({ ...EMPTY_CONTACT, first: "X" }).adr, null);
  const r = contactRow(c); assert.equal(r.name, "Alice Martin"); assert.equal(r.tel, "01 · 06"); assert.ok(r.writable); assert.equal(contactRow({ org: "Seule" }).name, "Seule");
});

import { weekOf, monthGrid, eventsOfDay, eventToForm, formToEvent, busyOfDay, freeSlots, dateKey, defaultSlot } from "../src/groupwareLib.js";
test("agenda : semaine, mois, événements du jour, chevauchements", () => {
  const w = weekOf(new Date(2026, 9, 7)); assert.equal(dateKey(w[0]), "2026-10-05"); assert.equal(dateKey(w[6]), "2026-10-11");
  const m = monthGrid(new Date(2026, 9, 1)); assert.equal(dateKey(m[0][0]), "2026-09-28"); assert.ok(m.length >= 5 && dateKey(m[m.length - 1][6]) >= "2026-10-31");
  const evs = [{ title: "A", start: "2026-10-07T09:00", end: "2026-10-07T10:00" }, { title: "B", start: "2026-10-07T09:30", end: "2026-10-07T11:00" }, { title: "C", start: "2026-10-07", end: "2026-10-08", all_day: true }, { title: "D", start: "2026-10-06T22:00", end: "2026-10-07T01:00" }, { title: "E", start: "2026-10-08T09:00", end: "2026-10-08T10:00" }];
  const d = eventsOfDay(evs, new Date(2026, 9, 7)); assert.deepEqual(d.allDay.map((e) => e.title), ["C"]); assert.deepEqual(d.timed.map((e) => e.title), ["D", "A", "B"]); assert.equal(d.timed[0].top, 0); assert.equal(d.timed[0].height, 60); assert.equal(d.timed[2].col, 1); assert.equal(d.cols, 2);
  assert.equal(eventsOfDay(evs, new Date(2026, 9, 8)).allDay.length, 0);
});
test("agenda : formulaire <-> événement, créneau par défaut, disponibilités", () => {
  const f = eventToForm({ title: "Point", start: "2026-10-05T09:00+02:00", end: "2026-10-05T09:30+02:00", rrule: { freq: "WEEKLY", byday: "MO", until: "2026-12-31T23:59+01:00" }, categories: ["interne"] });
  assert.equal(f.start, "2026-10-05T09:00"); assert.equal(f.freq, "weekly"); assert.equal(f.until, "2026-12-31");
  const e = formToEvent(f); assert.deepEqual(e.rrule, { freq: "weekly", byday: "MO", until: "2026-12-31T23:59" }); assert.deepEqual(e.categories, ["interne"]); assert.equal(formToEvent({ ...f, freq: "" }).rrule, null);
  assert.deepEqual(defaultSlot(new Date(2026, 9, 7), 14), { start: "2026-10-07T14:00", end: "2026-10-07T15:00" });
  const busy = { alice: [{ start: "2026-10-07T09:00", end: "2026-10-07T10:00" }], bob: [{ start: "2026-10-07T12:00", end: "2026-10-07T14:00" }] };
  assert.deepEqual(busyOfDay(busy.alice, new Date(2026, 9, 7)), [{ top: 540, bottom: 600 }]);
  assert.deepEqual(freeSlots(busy, new Date(2026, 9, 7)), ["08:00–09:00", "10:00–12:00", "14:00–19:00"]);
  assert.deepEqual(freeSlots({}, new Date(2026, 9, 7), 9, 12), ["09:00–12:00"]);
});

import { isLate, kanban, infologToForm, formToInfolog, linkLabel, INFOLOG_STATUS } from "../src/groupwareLib.js";
test("infolog : retard, kanban, formulaire, libellés de liens", () => {
  const today = new Date(2026, 9, 7);
  assert.ok(isLate({ due: "2026-10-06", status: "open" }, today)); assert.ok(!isLate({ due: "2026-10-06", status: "done" }, today)); assert.ok(!isLate({ due: "", status: "open" }, today)); assert.ok(!isLate({ due: "2026-10-07", status: "open" }, today));
  const k = kanban([{ id: 1, status: "open" }, { id: 2, status: "done" }, { id: 3, status: "open" }]); assert.deepEqual(Object.keys(k), Object.keys(INFOLOG_STATUS)); assert.equal(k.open.length, 2); assert.equal(k.ongoing.length, 0);
  const f = infologToForm({ id: 5, type: "call", title: "Rappeler", categories: ["client"], private: 1, links: [{ app: "ticket", id: "42", link_id: 9 }] }); assert.equal(f.categories, "client"); assert.equal(f.private, true); assert.deepEqual(f.links, [{ app: "ticket", id: "42" }]);
  const e = formToInfolog({ ...f, priority: "2", links: [{ app: "ticket", id: "42" }, { app: "", id: "" }] }); assert.equal(e.priority, 2); assert.deepEqual(e.categories, ["client"]); assert.equal(e.links.length, 1);
  assert.equal(linkLabel({ app: "contact", id: "alice/contacts-pro/u1" }), "contact u1 (alice)"); assert.equal(linkLabel({ app: "ticket", id: "42" }), "ticket n°42"); assert.equal(linkLabel({ app: "x", id: "y" }), "x y");
});
