import test from "node:test";
import assert from "node:assert/strict";
import { BASTION_TABS, classifyDirectPort, summarizeExposure, summarizeInbound, summarizeOutbound, connectorState, summarizeAuthorizations, summarizeShares, attentionCounts } from "../src/bastionInventory.js";

test("onglets de la console", () => {
  assert.deepEqual(BASTION_TABS.map((t) => t.id), ["proxy", "entries", "exits", "auth", "shares"]);
});

test("entrées : classement des ports publiés hors passerelle", () => {
  assert.equal(classifyDirectPort({ service: "tickets-postgres", loopback_only: false, proto: "tcp" }).severity, "critical");
  assert.equal(classifyDirectPort({ service: "elasticsearch", loopback_only: false, proto: "tcp" }).severity, "critical");
  assert.equal(classifyDirectPort({ service: "rsyslog-listener", loopback_only: false, proto: "udp" }).severity, "warning");
  assert.equal(classifyDirectPort({ service: "si-agent-api", loopback_only: false, proto: "tcp" }).severity, "warning");
  assert.equal(classifyDirectPort({ service: "si-proxy", loopback_only: true, proto: "tcp" }).severity, "info");
  const s = summarizeExposure({ gateway_port: "6443", gateway: [{ path: "/api/x/" }],
    direct_ports: [{ service: "si-proxy", host_port: "6452", loopback_only: true, proto: "tcp" }, { service: "geo-postgres", host_port: "6546", loopback_only: false, proto: "tcp" },
      { service: "ups-monitor-api", host_port: "6128", loopback_only: false, proto: "tcp" }], host_network: [{ service: "network-agent-api" }] });
  assert.deepEqual(s.direct.map((d) => d.service), ["geo-postgres", "ups-monitor-api", "si-proxy"]);
  assert.deepEqual(s.counts, { critical: 1, warning: 1, info: 1, gateway: 1 });
  assert.equal(summarizeExposure(null).counts.gateway, 0);
});

test("entrées : agents et sondes entrants", () => {
  const r = summarizeInbound({ siAgentStatus: { fleet_blocked: true, fleet_block_reason: "incident", insecure_agents: ["a1"] },
    siAgentFleet: [{ agent_id: "a1", online: "online", blocked: true }, { agent_id: "a2", online: "offline" }],
    netprobeAgents: [{ agent_id: "p1", role: "probe", last_seen_at: new Date().toISOString() }, { agent_id: "p2", role: "collector", last_seen_at: "2020-01-01T00:00:00Z" }] });
  assert.deepEqual([r.siAgent.total, r.siAgent.online, r.siAgent.blocked, r.siAgent.fleetBlocked, r.siAgent.insecure], [2, 1, 1, true, ["a1"]]);
  assert.deepEqual([r.netprobe.total, r.netprobe.online, r.netprobe.roles], [2, 1, { probe: 1, collector: 1 }]);
  assert.equal(summarizeInbound({ siAgentStatus: { error: "x" } }).siAgent, null);
});

test("sorties : tunnels, montages, connecteurs", () => {
  const conns = [{ id: 1, ssh_host: "gw.example", ssh_user: "ops", ssh_port: 2222 }];
  const o = summarizeOutbound({ tunnels: [{ id: 5, label: "GLPI distant", connection_id: 1, remote_host: "10.0.0.5", remote_port: 443, local_port: 18443, status: "running" },
    { id: 6, label: "vieux", connection_id: 9, remote_host: "10.0.0.6", remote_port: 22, local_port: 2202, status: "stopped", last_error: "timeout" }],
    connections: conns, mounts: [{ id: 2, label: "docs", connection_id: 1, remote_path: "/srv/docs", local_mount_path: "/mnt/docs", status: "mounted" }],
    connectors: [{ id: "glpi", error: "HTTP 500" }, { id: "nebula" }] });
  assert.equal(o.tunnels[0].via, "ops@gw.example:2222");
  assert.equal(o.tunnels[1].via, "connexion #9");
  assert.deepEqual(o.counts, { tunnelsRunning: 1, tunnels: 2, mounted: 1, mounts: 1, hosts: 1 });
  assert.equal(o.connectors[0].state, "critical");
  assert.equal(connectorState("imap", null).state, "unknown");
  assert.equal(connectorState("imap", { configured: false }).state, "warning");
  assert.equal(connectorState("imap", { text: "2 boîtes" }).text, "2 boîtes");
});

test("autorisations : permissions par type, liens externes ouverts à tous", () => {
  const a = summarizeAuthorizations({
    permissions: [{ id: 1, resource_type: "file-manager-protected", group_name: "admin_hub", action: "read" }, { id: 2, resource_type: "file-manager-protected", group_name: "technicien", action: "read" },
      { id: 3, resource_type: "ged", group_name: "admin_hub", action: "write" }],
    resourceTypes: ["file-manager-protected", "ged", "tickets"],
    externalLinks: [{ id: 1, name: "GLPI", url: "https://glpi", allowed_roles: ["admin"] }, { id: 2, name: "Wiki", url: "https://wiki", allowed_roles: [], keycloak_client_id: "wiki" }],
    groups: ["admin_hub"] });
  assert.equal(a.totalPermissions, 3);
  assert.deepEqual(a.permissions[0].groups, ["admin_hub", "technicien"]);
  assert.equal(a.linksForEveryone, 1);
  assert.equal(a.links[1].keycloak, true);
  assert.deepEqual(a.openTypes, ["tickets"]);
});

test("partages et compteurs d'attention", () => {
  const s = summarizeShares({ fileSources: [{ id: "protected-space", label: "Espace protégé", type: "protected-space" }, { id: "ged", label: "GED", type: "ged" }],
    mounts: [{ id: 1, label: "docs", status: "mounted", remote_path: "/a", local_mount_path: "/b" }], gedCount: 12 });
  assert.equal(s.sources[0].protectedSpace, true);
  assert.deepEqual(s.counts, { sources: 2, mounted: 1, mounts: 1 });
  const att = attentionCounts({ exposure: { counts: { critical: 4, warning: 2 } }, inbound: { siAgent: { insecure: ["x"] } },
    outbound: { tunnels: [{ lastError: "t" }], connectors: [{ state: "critical" }, { state: "ok" }] }, auth: { linksForEveryone: 3 } });
  assert.deepEqual(att, { entries: 7, exits: 2, auth: 3, shares: 0 });
});
