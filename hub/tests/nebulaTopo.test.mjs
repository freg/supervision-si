// Tests du synoptique Nebula (livraison #553).
import test from "node:test";
import assert from "node:assert/strict";
import { buildGraph, assignTiers, layout, edgeCarries, nodeSummary } from "../src/nebulaTopo.js";

const VMAP = {
  devices: [{ devId: "gw", name: "USG", model: "USG FLEX 700H", type: "GWH" }, { devId: "core", name: "XS3800-28", model: "XS3800-28", type: "SW" },
            { devId: "edge", name: "GS2220-50HP-1", model: "GS2220-50HP", type: "SW" }, { devId: "ap1", name: "Borne 1", model: "WBE660S", type: "AP" }, { devId: "ap9", name: "Borne isolée", model: "WBE660S", type: "AP" }],
  links: [
    { a: "core", a_port: 25, b: "edge", b_port: 49, external: false, a_vlans: [1, 30], b_vlans: [1], missing_on_a: [], missing_on_b: [30] },
    { a: "core", a_port: 26, b: "edge", b_port: 50, external: false, a_vlans: [], b_vlans: [], missing_on_a: [], missing_on_b: [], bare: true },
    { a: "core", a_port: 1, b: null, b_name: "USG", b_port: "ge3", external: true },
    { a: "edge", a_port: 5, b: null, b_name: "borne 1", b_port: "eth0", external: true },
    { a: "edge", a_port: 6, b: null, b_name: "pc-inconnu", b_port: null, external: true },
    { a: "edge", a_port: 5, b: null, b_name: "borne 1", b_port: "eth0", external: true },
  ],
  vlans: [{ vid: 1, switches: { "XS3800-28": { untagged: [25], tagged: [] } }, ssids: [{ name: "Campus", enabled: true }], subnet: null, gateway_interface: null },
          { vid: 30, switches: { "XS3800-28": { untagged: [], tagged: [25] } }, ssids: [{ name: "Numeria", enabled: true }], subnet: "192.0.2.0/23", gateway_interface: "VLAN30" }],
};

test("buildGraph : nœuds de l'inventaire, voisins externes rattachés ou créés, arêtes dédoublonnées avec ton", () => {
  const g = buildGraph(VMAP, { "Borne 1": "online", USG: "online" });
  assert.deepEqual(g.nodes.map((n) => n.id).sort(), ["ap1", "ap9", "core", "edge", "ext:pc-inconnu", "gw"]);
  assert.equal(g.nodes.find((n) => n.id === "ap1").status, "online");
  assert.equal(g.nodes.find((n) => n.id === "ap9").status, "inconnu");
  assert.equal(g.edges.length, 5);
  assert.equal(g.edges.find((e) => e.a_port === 25).tone, "bad");
  assert.equal(g.edges.find((e) => e.a_port === 26).tone, "muted");
  assert.equal(g.edges.find((e) => e.a_port === 1).b, "gw");
  assert.equal(g.edges.find((e) => e.a_port === 5).b, "ap1");
  assert.equal(g.edges.find((e) => e.a_port === 6).b, "ext:pc-inconnu");
});

test("assignTiers + layout : passerelle en haut, cœur, accès, bornes, isolés en bas", () => {
  const g = buildGraph(VMAP);
  const t = assignTiers(g);
  assert.equal(t.get("gw"), 0); assert.equal(t.get("core"), 1); assert.equal(t.get("edge"), 2); assert.equal(t.get("ap1"), 3);
  assert.equal(t.get("ap9"), 4);  // isolé : dernier niveau
  const l = layout(g, 800, 100, 150);
  assert.equal(l.positions.get("gw").y, 60); assert.equal(l.positions.get("ap9").y, 60 + 4 * 100);
  assert.equal(l.height, 60 + 5 * 100);
  assert.ok(l.positions.get("ap1").x !== l.positions.get("ext:pc-inconnu").x);
  // niveau large : repli en rangées de 8 au plus
  const many = { devices: [{ devId: "sw", name: "S", type: "SW" }, ...Array.from({ length: 20 }, (_, i) => ({ devId: "a" + i, name: "AP " + i, type: "AP" }))],
                 links: Array.from({ length: 20 }, (_, i) => ({ a: "sw", a_port: i, b: null, b_name: "AP " + i, external: true })), vlans: [] };
  const lm = layout(buildGraph(many), 1000, 100, 150, 8);
  const ys = new Set([...lm.positions.values()].filter((p) => p.tier === 1).map((p) => p.y));
  assert.equal(ys.size, 3);
  assert.ok(lm.width <= 8 * 170 + 40 + 1);
  // sans passerelle : le nœud le plus connecté fait racine
  const g2 = buildGraph({ ...VMAP, devices: VMAP.devices.filter((d) => d.type !== "GWH"), links: VMAP.links.filter((l) => l.b_name !== "USG") });
  assert.equal(assignTiers(g2).get("edge"), 0);
});

test("edgeCarries et nodeSummary", () => {
  const g = buildGraph(VMAP);
  const e = g.edges.find((x) => x.a_port === 25);
  assert.ok(edgeCarries(e, 30)); assert.ok(!edgeCarries(e, 99)); assert.ok(edgeCarries({ a_vlans: "all", b_vlans: [] }, 5));
  const sw = nodeSummary(g.nodes.find((n) => n.id === "core"), VMAP);
  assert.deepEqual(sw.vlans.map((v) => v.vid), [1, 30]);
  const ap = nodeSummary(g.nodes.find((n) => n.id === "ap1"), VMAP);
  assert.deepEqual(ap.ssids.map((s) => [s.name, s.vid]), [["Campus", 1], ["Numeria", 30]]);
  const gw = nodeSummary(g.nodes.find((n) => n.id === "gw"), VMAP);
  assert.deepEqual(gw.vlans, [{ vid: 30, subnet: "192.0.2.0/23", iface: "VLAN30", guest: undefined }]);
});
