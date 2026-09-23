import test from "node:test";
import assert from "node:assert/strict";
import { recordsToCsv } from "../src/campusCards.js";

test("recordsToCsv : BOM, point-virgule, guillemets", () => {
  const csv = recordsToCsv([{ Nom: "LED-01", "Adresse IP": "192.0.2.10", Commentaire: 'a;b "c"' }, { Nom: "LED-02" }], ["Nom", "Adresse IP", "Commentaire"]);
  assert.ok(csv.startsWith("﻿Nom;Adresse IP;Commentaire\r\n"));
  assert.ok(csv.includes('LED-01;192.0.2.10;"a;b ""c"""'));
  assert.ok(csv.endsWith("LED-02;;"));
});
