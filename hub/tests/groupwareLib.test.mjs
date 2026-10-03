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
