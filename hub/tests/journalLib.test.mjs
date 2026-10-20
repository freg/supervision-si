import test from "node:test";
import assert from "node:assert/strict";
import { fmtDay, weekday, durationMin, fmtDuration, offHour, isWeekend, filterEntries, importPayload, totals, entryToForm } from "../src/journalLib.js";

test("#795 : dates, jours, durées, heures hors bureau", () => {
  assert.equal(fmtDay("2026-10-20"), "20/10/2026");
  assert.equal(weekday("2026-10-20"), "mardi");
  assert.equal(isWeekend("2026-10-18"), true);
  assert.equal(durationMin({ start: "17:50", end: "18:17" }), 27);
  assert.equal(durationMin({ start: "23:30", end: "00:10" }), 40);
  assert.equal(durationMin({ start: "10:00" }), null);
  assert.equal(fmtDuration(100), "1 h 40");
  assert.equal(offHour("2026-10-20", "12:15"), false);
  assert.equal(offHour("2026-10-20", "12:22"), true);
  assert.equal(offHour("2026-10-20", "18:17"), true);
  assert.equal(offHour("2026-10-18", "10:00"), true);
  assert.equal(offHour("", "23:00"), false);
});

test("#795 : filtre, import, totaux, formulaire", () => {
  const E = [{ acte: "Bascule du site A", nature: "Intervention", statut: "Fait" }, { acte: "Veille SMS", nature: "Surveillance", statut: "En cours" }];
  assert.equal(filterEntries(E, { q: "bascule" }).length, 1);
  assert.equal(filterEntries(E, { nature: "Surveillance" })[0].acte, "Veille SMS");
  assert.deepEqual(importPayload('[{"acte":"a"}]', "j.json", "SMS"), { rows: [{ acte: "a", chantier: "SMS" }] });
  assert.deepEqual(importPayload('{"entries":[{"acte":"a","chantier":"X"}]}'), { rows: [{ acte: "a", chantier: "X" }] });
  assert.ok(importPayload("{oups", "j.json").error);
  assert.deepEqual(importPayload("﻿Chantier;Date;Acte\nA;20/10/2026;x", "j.csv", "B"), { csv: "Chantier;Date;Acte\nA;20/10/2026;x", chantier: "B" });
  assert.equal(totals([{ lignes: 2, fait: 1, a_faire: 1, weekend: 1, hors_heures: 2, minutes: 30 }, { lignes: 1, fait: 1, a_faire: 0, weekend: 0, hors_heures: 0, minutes: 10 }]).minutes, 40);
  assert.equal(entryToForm({ acte: "x", end: null }).end, "");
});
