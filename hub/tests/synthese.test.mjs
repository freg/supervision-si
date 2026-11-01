import test from "node:test";
import assert from "node:assert/strict";
import { fillLink, ipLinks, zoneLink, daysUntil, describeIp, filterDoc } from "../src/syntheseLib.js";

const LINKS = { ipam_url: "https://ipam.exemple.fr/", ipam_search: "{ipam_url}index.php?page=tools&section=search&ip={query}", ovh_ip: "https://ovh/ip?ip={ip}", ovh_zone: "https://ovh/zone/{zone}", online_zone: "https://online/{zone}/dns" };
const DOC = {
  index: { "203.0.113.10": { dns: ["exemple.fr", "hub.exemple.fr"], ovh: { type: "DEDICATED", service: "ns1" }, services: [{ type: "IP" }], ipam: [], devices: [] },
    "192.0.2.10": { dns: [], ovh: null, services: [], ipam: [{ hostname: "super", description: "hub supervision", subnet: "192.0.2.0/28" }], devices: [] } },
  ovh_ips: [{ ip: "203.0.113.10", block: "203.0.113.10/32", type: "DEDICATED", service: "ns1" }, { ip: "203.0.113.11", block: "203.0.113.11/32", type: "FAILOVER", service: "ns1" }],
  zones: [{ zone: "exemple.fr", provider: "ovh", records: [{ name: "hub", fqdn: "hub.exemple.fr", type: "A", value: "203.0.113.10" }, { name: "www", fqdn: "www.exemple.fr", type: "CNAME", value: "exemple.fr." }] },
    { zone: "alpha-conseil.fr", provider: "online", records: [{ name: "urvp", fqdn: "urvp.alpha-conseil.fr", type: "A", value: "198.51.100.20" }] }],
  ipam: { subnets: [{ title: "Alpha Servers", cidr: "192.0.2.0/28", hosts: [{ ip: "192.0.2.10", hostname: "super", description: "hub supervision" }, { ip: "192.0.2.1", hostname: "vpn2" }] }], devices: [{ name: "ALPHA-CORE-01", ip: "192.0.2.254", type: "Router" }] },
  ovh_services: [{ service: "ip-203.0.113.10", type: "IP", ip: "203.0.113.10", effective_iso: "2026-10-01" }, { service: "exemple.fr", type: "Domaine", effective_iso: "2027-09-13" }],
};

test("liens", () => {
  assert.equal(fillLink("https://x/{zone}/dns", { zone: "a.fr" }), "https://x/a.fr/dns");
  assert.equal(fillLink("https://x/{zone}", {}), null);
  const l = ipLinks("203.0.113.10", DOC.index["203.0.113.10"], LINKS);
  assert.deepEqual(l.map((x) => x.label), ["IPAM", "IP OVH"]);
  assert.equal(l[0].href, "https://ipam.exemple.fr/index.php?page=tools&section=search&ip=203.0.113.10");
  assert.deepEqual(ipLinks("192.0.2.10", DOC.index["192.0.2.10"], LINKS).map((x) => x.label), ["IPAM"]);
  assert.deepEqual(ipLinks("1.2.3.4", null, {}), []);
  assert.equal(zoneLink(DOC.zones[0], LINKS), "https://ovh/zone/exemple.fr");
  assert.equal(zoneLink(DOC.zones[1], LINKS), "https://online/alpha-conseil.fr/dns");
});

test("échéances et description", () => {
  const now = Date.parse("2026-09-16T00:00:00");
  assert.equal(daysUntil("2026-10-01", now), 15);
  assert.equal(daysUntil("2026-09-01", now), -15);
  assert.equal(daysUntil(null), null);
  assert.match(describeIp("203.0.113.10", DOC.index["203.0.113.10"]), /DNS : exemple.fr, hub.exemple.fr · OVH DEDICATED ns1 · services : IP/);
  assert.equal(describeIp("9.9.9.9", null), "aucune information recoupée");
});

test("filtre transversal", () => {
  assert.equal(filterDoc(DOC, "  "), DOC);
  const f = filterDoc(DOC, "super");
  assert.equal(f.ipam.subnets[0].hosts.length, 1);
  assert.equal(f.ovh_ips.length, 0);
  const g = filterDoc(DOC, "hub.exemple");
  assert.equal(g.ovh_ips.length, 1, "IP recoupée par son nom DNS");
  assert.equal(g.zones.length, 1);
  assert.equal(g.ovh_services.length, 1, "service recoupé par l'IP");
  const h = filterDoc(DOC, "failover");
  assert.deepEqual(h.ovh_ips.map((o) => o.ip), ["203.0.113.11"]);
  assert.equal(filterDoc(DOC, "router").ipam.devices.length, 1);
  assert.equal(filterDoc(DOC, "zzz").zones.length, 0);
});
