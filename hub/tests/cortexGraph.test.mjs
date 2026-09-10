import test from "node:test";
import assert from "node:assert/strict";
import { layerOf, layoutGraph, routesByHost, changeTone, columnWidth, COL_W, PAD } from "../src/cortexGraph.js";

test("couches et colonnes par site", () => {
  assert.equal(layerOf({ kind: "passerelle" }), 0);
  assert.equal(layerOf({ kind: "equipement", role: "switch" }), 0);
  assert.equal(layerOf({ kind: "hote" }), 1);
  assert.equal(layerOf({ kind: "pair" }), 2);
  const g = { nodes: [{ key: "gw", name: "routeur", kind: "passerelle", site: "bureau" }, { key: "h1", name: "srv1", kind: "hote", site: "bureau" }, { key: "h2", name: "srv2", kind: "hote", site: "agence" }, { key: "p", name: "pair", kind: "pair" }],
    edges: [{ a: "gw", b: "h1", kind: "gateway_of" }, { a: "h1", b: "zz", kind: "flow" }] };
  const l = layoutGraph(g);
  assert.deepEqual(l.sites, ["agence", "bureau", "(sans site)"]);
  const gw = l.nodes.find((n) => n.key === "gw"), h1 = l.nodes.find((n) => n.key === "h1");
  assert.equal(gw.col, 1); assert.equal(gw.layer, 0); assert.equal(h1.col, 1); assert.equal(h1.layer, 1);
  assert.ok(h1.y > gw.y);
  assert.equal(l.edges.length, 1);   // l'arête vers un nœud inconnu est ignorée
  assert.equal(l.colW, COL_W); assert.equal(l.width, PAD * 2 + 3 * COL_W);
  assert.equal(layoutGraph(null).nodes.length, 0);
  // une étiquette longue élargit toutes les colonnes : rien ne déborde sur le site voisin
  const wide = layoutGraph({ nodes: [{ key: "x", name: "MacBook-Air-de-Alice-tres-long", kind: "hote", role: "hote-supervise", site: "bureau" }], edges: [] });
  assert.ok(wide.colW > COL_W); assert.equal(wide.colW, columnWidth(wide.nodes)); assert.equal(wide.width, PAD * 2 + wide.colW);
});

test("routes par hôte et ton des changements", () => {
  const r = routesByHost([{ host: "a", host_name: "srv1", kind: "default", destination: "default", via: "10.0.0.1" }, { host: "a", kind: "attached", destination: "10.0.0.0/24" }, { host: "a", kind: "reachable", destination: "10.1.0.0/16", via: "10.0.0.254" }]);
  assert.equal(r[0].default.via, "10.0.0.1"); assert.deepEqual(r[0].attached, ["10.0.0.0/24"]); assert.equal(r[0].reachable.length, 1);
  assert.equal(changeTone("entity-gone"), "warn"); assert.equal(changeTone("entity-new"), "good"); assert.equal(changeTone("role-changed"), "neutral");
});
