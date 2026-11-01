import test from "node:test";
import assert from "node:assert/strict";
import { presenceBadge, fmtAge, sourceStats, connectorConfig, groupLinks, rowSummary, groupNodes } from "../src/datasyncLib.js";

test("presence et âges", () => {
  assert.deepEqual(presenceBadge({ presence: "jamais" }), { label: "jamais vue", cls: "ds-muted" });
  assert.equal(presenceBadge({ presence: "present", ping_age_s: 30 }).cls, "ds-ok");
  assert.equal(presenceBadge({ presence: "absent", ping_age_s: 7200 }).label, "absente (dernier signe il y a 2 h)");
  assert.equal(fmtAge(90), "2 min"); assert.equal(fmtAge(172800), "2 j"); assert.equal(fmtAge(null), "—");
});

test("sourceStats agrège les tables", () => {
  assert.deepEqual(sourceStats({ tables: [{ rows: 3, batches: 2, errors: 0, last_batch_at: "2026-10-01T10:00:00" }, { rows: 2, batches: 1, errors: 1, last_batch_at: "2026-10-02T09:00:00" }] }),
    { rows: 5, batches: 3, errors: 1, last: "2026-10-02T09:00:00" });
  assert.deepEqual(sourceStats({}), { rows: 0, batches: 0, errors: 0, last: "" });
});

test("connectorConfig : json valide, port selon le pilote, jamais de mot de passe", () => {
  const c = JSON.parse(connectorConfig("https://hub/api/datasync", "tok", { kind: "postgres" }));
  assert.equal(c.db.port, 5432); assert.equal(c.db.password, ""); assert.equal(c.token, "tok"); assert.equal(c.tables.length, 2);
  assert.equal(JSON.parse(connectorConfig("x", "", null)).token, "<jeton>");
});

test("groupLinks, rowSummary, groupNodes", () => {
  const g = groupLinks([{ kind: "field", status: "proposed" }, { kind: "relation", status: "confirmed" }, { kind: "x", status: "proposed" }]);
  assert.equal(g.field.proposed.length, 1); assert.equal(g.relation.confirmed.length, 1);
  assert.equal(rowSummary({ id: 1, subject: "Panne", n: null, e: "" }), "id: 1 · subject: Panne");
  const gn = groupNodes([{ level: 1, source: "b", table: "t" }, { level: 0, source: "a", table: "tickets" }, { level: 1, source: "b", table: "t" }]);
  assert.deepEqual(gn.map((x) => [x.level, x.table, x.rows.length]), [[0, "tickets", 1], [1, "t", 2]]);
});
