import test from "node:test";
import assert from "node:assert/strict";
import { groupByLab, labs, assetSummary } from "../src/campusCards.js";

test("groupByLab / labs / assetSummary", () => {
  const items = [{ name: "PC01", kind: "PC", lab: "Lab B", nebula: { status: "online" } }, { name: "Tab", kind: "Tablette", lab: "Lab A" }, { name: "Casque", kind: "VR", lab: "", nebula: { status: "offline" } }, { name: "PC02 nano", kind: "PC", lab: "Lab A" }];
  const g = groupByLab(items, "");
  assert.deepEqual(g.map((x) => x.lab), ["Lab A", "Lab B", "(sans lab)"]);
  assert.deepEqual(groupByLab(items, "pc").flatMap((x) => x.items.map((i) => i.name)), ["PC02 nano", "PC01"]);
  assert.deepEqual(groupByLab(items, "", "Lab B").map((x) => x.items.length), [1]);
  assert.deepEqual(labs(items), ["Lab A", "Lab B"]);
  const s = assetSummary(items);
  assert.equal(s.total, 4); assert.equal(s.matched, 2); assert.equal(s.online, 1); assert.deepEqual(s.byKind[0], ["PC", 2]);
});
