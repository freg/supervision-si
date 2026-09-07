import { test } from "node:test";
import assert from "node:assert/strict";
import {
  GATEWAY_ROLE_HINT, findSupervisionHost, findGateways, isHostRouterLink,
  computeShares, normalizeBand, applyFlowFilters, describeFlowFilterResult,
} from "../src/networkFlowFilters.js";

const devices = [
  { id: 1, mac_address: "aa:bb:cc:00:00:01", ip_address: "192.168.1.1", role_hint: GATEWAY_ROLE_HINT },
  { id: 2, mac_address: "AA:BB:CC:00:00:02", ip_address: "192.168.1.10", role_hint: null },
  { id: 3, mac_address: "aa:bb:cc:00:00:03", ip_address: "192.168.1.21", role_hint: null },
  { id: 4, mac_address: "aa:bb:cc:00:00:04", ip_address: "192.168.1.35", role_hint: null },
];
const links = [
  { id: 1, device_a_id: 2, device_b_id: 1, bytes_total: 700 },  // hôte → routeur
  { id: 2, device_a_id: 1, device_b_id: 3, bytes_total: 150 },
  { id: 3, device_a_id: 4, device_b_id: 1, bytes_total: 100 },
  { id: 4, device_a_id: 1, device_b_id: 2, bytes_total: 40 },   // routeur → hôte
  { id: 5, device_a_id: 3, device_b_id: 4, bytes_total: 10 },
  { id: 6, device_a_id: 3, device_b_id: 2, bytes_total: 0 },    // volume nul : ignoré partout
];

test("l'hôte de supervision est reconnu par la MAC, insensible à la casse, puis par l'IP", () => {
  assert.equal(findSupervisionHost(devices, { interface_mac: "aa:bb:cc:00:00:02" })?.id, 2);
  assert.equal(findSupervisionHost(devices, { interface_mac: "AA:BB:CC:00:00:02 " })?.id, 2);
  assert.equal(findSupervisionHost(devices, { interface_mac: "00:00:00:00:00:99", interface_ip: "192.168.1.21" })?.id, 3, "MAC inconnue → IP");
  assert.equal(findSupervisionHost(devices, { interface_mac: null, interface_ip: null }), null);
  assert.equal(findSupervisionHost(devices, undefined), null);
  assert.equal(findSupervisionHost(undefined, { interface_mac: "aa:bb:cc:00:00:02" }), null);
});

test("les passerelles sont les appareils au rôle deviné, et seulement eux", () => {
  assert.deepEqual(findGateways(devices).map((d) => d.id), [1]);
  assert.deepEqual(findGateways([]), []);
  assert.equal(isHostRouterLink(links[0], 2, [1]), true);
  assert.equal(isHostRouterLink(links[3], 2, [1]), true, "dans les deux sens");
  assert.equal(isHostRouterLink(links[1], 2, [1]), false);
  assert.equal(isHostRouterLink(links[0], null, [1]), false, "hôte inconnu : rien à masquer");
  assert.equal(isHostRouterLink(links[0], 2, []), false, "pas de passerelle : rien à masquer");
});

test("les parts sont calculées sur le volume total, les flux nuls écartés", () => {
  const { total, shares } = computeShares(links);
  assert.equal(total, 1000);
  assert.equal(shares.size, 5);
  assert.equal(shares.get(links[0]), 70);
  assert.equal(shares.get(links[4]), 1);
  assert.deepEqual(computeShares([]), { total: 0, shares: new Map() });
});

test("la tranche saisie est bornée, ordonnée et tolérante", () => {
  assert.deepEqual(normalizeBand(10, 50), { minPct: 10, maxPct: 50 });
  assert.deepEqual(normalizeBand("50", "10"), { minPct: 10, maxPct: 50 }, "permutés");
  assert.deepEqual(normalizeBand(-5, 250), { minPct: 0, maxPct: 100 });
  assert.deepEqual(normalizeBand("", "abc"), { minPct: 0, maxPct: 100 });
  assert.deepEqual(normalizeBand(undefined, undefined), { minPct: 0, maxPct: 100 });
});

test("sans filtre, tout passe (hors volume nul)", () => {
  const r = applyFlowFilters(links, {});
  assert.equal(r.links.length, 5);
  assert.equal(r.keptBytes, 1000);
  assert.deepEqual(r.hidden, { hostRouter: 0, band: 0, volume: 0, subnet: 0 });
  assert.equal(describeFlowFilterResult(r), "5 flux sur 5 · 100 % du volume");
});

test("masquer hôte ↔ routeur retire les deux sens, la part reste calculée sur le total", () => {
  const r = applyFlowFilters(links, { hideHostRouter: true, hostId: 2, gatewayIds: [1] });
  assert.deepEqual(r.links.map((l) => l.id), [2, 3, 5]);
  assert.equal(r.hidden.hostRouter, 2);
  assert.equal(r.total, 1000, "base stable");
  assert.equal(r.keptBytes, 260);
  assert.equal(describeFlowFilterResult(r), "3 flux sur 5 · 26 % du volume · 2 hôte ↔ routeur masqué(s)");
});

test("la tranche de pourcentage garde les flux dont la part est dans [min, max]", () => {
  const r = applyFlowFilters(links, { minPct: 5, maxPct: 20 });
  assert.deepEqual(r.links.map((l) => l.id), [2, 3], "15 % et 10 %");
  assert.equal(r.hidden.band, 3);
  const bruit = applyFlowFilters(links, { minPct: 0, maxPct: 2 });
  assert.deepEqual(bruit.links.map((l) => l.id), [5]);
  const gros = applyFlowFilters(links, { minPct: 50, maxPct: 100 });
  assert.deepEqual(gros.links.map((l) => l.id), [1]);
  assert.match(describeFlowFilterResult(r), /3 hors tranche/);
});

test("les deux filtres se cumulent, hôte ↔ routeur compté avant la tranche", () => {
  const r = applyFlowFilters(links, { hideHostRouter: true, hostId: 2, gatewayIds: [1], minPct: 0, maxPct: 12 });
  assert.deepEqual(r.links.map((l) => l.id), [3, 5]);
  assert.deepEqual(r.hidden, { hostRouter: 2, band: 1, volume: 0, subnet: 0 });
});

test("hôte inconnu : la case hôte ↔ routeur ne masque rien, sans erreur", () => {
  const r = applyFlowFilters(links, { hideHostRouter: true, hostId: null, gatewayIds: [1] });
  assert.equal(r.links.length, 5);
  assert.equal(r.hidden.hostRouter, 0);
});

// --- Livraison #414 : volume absolu et sous-réseau ---
import {
  ipv4ToInt, subnetOf, ipInSubnet, listDeviceSubnets, linkSubnetRelation, DEFAULT_FLOW_FILTERS,
} from "../src/networkFlowFilters.js";

test("IPv4 : conversion, sous-réseau, appartenance, entrées invalides", () => {
  assert.equal(ipv4ToInt("192.168.1.10"), 3232235786);
  assert.equal(ipv4ToInt("256.1.1.1"), null);
  assert.equal(ipv4ToInt("1.2.3"), null);
  assert.equal(ipv4ToInt(null), null);
  assert.equal(subnetOf("192.168.1.10", 24), "192.168.1.0/24");
  assert.equal(subnetOf("192.168.37.10", 16), "192.168.0.0/16");
  assert.equal(subnetOf("192.168.37.10", 20), "192.168.32.0/20");
  assert.equal(subnetOf("10.0.0.200", 28), "10.0.0.192/28");
  assert.equal(subnetOf("bidon", 24), null);
  assert.equal(subnetOf("10.0.0.1", 40), null);
  assert.equal(ipInSubnet("192.168.1.77", "192.168.1.0/24"), true);
  assert.equal(ipInSubnet("192.168.2.77", "192.168.1.0/24"), false);
  assert.equal(ipInSubnet("192.168.2.77", "192.168.0.0/16"), true);
  assert.equal(ipInSubnet("192.168.2.77", "pas-un-cidr"), false);
  assert.equal(ipInSubnet(undefined, "192.168.1.0/24"), false);
});

test("les sous-réseaux des appareils sont listés par préfixe, triés par effectif", () => {
  const devs = [
    { id: 1, ip_address: "192.168.1.1" }, { id: 2, ip_address: "192.168.1.10" },
    { id: 3, ip_address: "192.168.2.5" }, { id: 4, ip_address: null }, { id: 5, ip_address: "10.0.0.1" },
  ];
  assert.deepEqual(listDeviceSubnets(devs, 24), [
    { subnet: "192.168.1.0/24", count: 2 }, { subnet: "10.0.0.0/24", count: 1 }, { subnet: "192.168.2.0/24", count: 1 },
  ]);
  assert.deepEqual(listDeviceSubnets(devs, 16), [{ subnet: "192.168.0.0/16", count: 3 }, { subnet: "10.0.0.0/16", count: 1 }]);
  assert.deepEqual(listDeviceSubnets([], 24), []);
});

test("filtre de volume absolu en Ko, bornes permutées si besoin, vide = pas de borne", () => {
  const r = applyFlowFilters(links, { minKo: 0.05, maxKo: 0.2 });   // 51,2 o à 204,8 o
  assert.deepEqual(r.links.map((l) => l.id), [2, 3]);
  assert.equal(r.hidden.volume, 3);
  const swapped = applyFlowFilters(links, { minKo: "0.2", maxKo: "0.05" });
  assert.deepEqual(swapped.links.map((l) => l.id), [2, 3]);
  const openEnded = applyFlowFilters(links, { minKo: "0.5", maxKo: "" });
  assert.deepEqual(openEnded.links.map((l) => l.id), [1]);
  assert.match(describeFlowFilterResult(r), /3 hors volume/);
  assert.equal(applyFlowFilters(links, { minKo: "abc" }).links.length, 5, "saisie invalide : pas de borne");
});

test("filtre de sous-réseau : interne (les deux) ou touchant (au moins un)", () => {
  const devs = [
    { id: 1, ip_address: "192.168.1.1" }, { id: 2, ip_address: "192.168.1.10" },
    { id: 3, ip_address: "192.168.2.21" }, { id: 4, ip_address: "192.168.2.35" },
  ];
  const byId = Object.fromEntries(devs.map((d) => [d.id, d]));
  assert.equal(linkSubnetRelation(links[0], byId, "192.168.1.0/24"), "intra");   // 2 → 1
  assert.equal(linkSubnetRelation(links[1], byId, "192.168.1.0/24"), "touche");  // 1 → 3
  assert.equal(linkSubnetRelation(links[4], byId, "192.168.1.0/24"), "hors");    // 3 → 4
  const intra = applyFlowFilters(links, { subnet: "192.168.1.0/24", subnetMode: "intra", devicesById: byId });
  assert.deepEqual(intra.links.map((l) => l.id), [1, 4]);
  assert.equal(intra.hidden.subnet, 3);
  const touche = applyFlowFilters(links, { subnet: "192.168.1.0/24", subnetMode: "touche", devicesById: byId });
  assert.deepEqual(touche.links.map((l) => l.id), [1, 2, 3, 4]);
  const seize = applyFlowFilters(links, { subnet: "192.168.0.0/16", subnetMode: "intra", devicesById: byId });
  assert.equal(seize.links.length, 5);
  assert.match(describeFlowFilterResult(intra), /3 hors sous-réseau/);
  assert.equal(applyFlowFilters(links, { subnet: "bidon", devicesById: byId }).links.length, 5, "CIDR invalide : ignoré");
});

test("les valeurs par défaut ne filtrent rien", () => {
  const r = applyFlowFilters(links, { ...DEFAULT_FLOW_FILTERS, hostId: 2, gatewayIds: [1], devicesById: {} });
  assert.equal(r.links.length, 5);
  assert.deepEqual(r.hidden, { hostRouter: 0, band: 0, volume: 0, subnet: 0 });
});
