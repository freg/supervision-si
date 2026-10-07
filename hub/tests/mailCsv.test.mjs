import test from "node:test";
import assert from "node:assert/strict";
import { toCsv, MAIL_EXPORTS } from "../src/mailCsv.js";

test("#713 : CSV Excel (BOM, « ; », guillemets)", () => {
  const c = toCsv(["a", "b"], [["x;y", 'dit "oui"'], [["l1", "l2"], null]]);
  assert.equal(c, '﻿a;b\r\n"x;y";"dit ""oui"""\r\nl1, l2;');
  const r = MAIL_EXPORTS.log.row({ first: 0, last: 0, key: "4A1B", from: "a@x", to: ["b@y", "c@y"], states: ["sent"], amavis: { verdict: "Passed CLEAN", hits: -1, mail_id: "AbC" } });
  assert.deepEqual(r.slice(2, 9), ["4A1B", "a@x", ["b@y", "c@y"], ["sent"], "Passed CLEAN", -1, "AbC"]);
  assert.equal(MAIL_EXPORTS.quarantine.header.length, MAIL_EXPORTS.quarantine.row({ to: [] }).length);
});
