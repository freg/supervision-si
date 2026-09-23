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

test("matchWindowsHosts / accessLinks (#567)", async () => {
  const { matchWindowsHosts, accessLinks } = await import("../src/campusCards.js");
  const assets = [{ name: "PC01 Allee", macs: ["02:00:00:aa:bb:01"] }, { name: "PC-Med07", macs: [] }];
  const hosts = [{ ip: "192.0.2.10", mac: "02-00-00-AA-BB-01", name: "X", ports: { rdp: 3389, smb: 445 } }, { ip: "192.0.2.11", name: "PC-MED07", ports: { anydesk: 7070 } }, { ip: "192.0.2.12", name: "AUTRE", ports: {} }];
  const m = matchWindowsHosts(hosts, assets);
  assert.equal(m[0].asset.name, "PC01 Allee"); assert.equal(m[1].asset.name, "PC-Med07"); assert.equal(m[2].asset, null);
  const l = accessLinks(hosts[0]);
  assert.deepEqual(l.map((x) => x.kind), ["rdp", "smb"]);
  assert.match(l[0].download.text, /full address:s:192\.0\.2\.10/); assert.equal(l[1].copy, "\\\\192.0.2.10");
  assert.equal(accessLinks(hosts[1])[0].href, "anydesk:192.0.2.11");
});
