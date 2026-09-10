// Logique PURE de la console « Bastion » élargie (livraison #455) -- aucun
// React, testée sous Node (hub/tests/bastionInventory.test.mjs).
//
// Demandé : « une passe sur l'ensemble des outils et des tuiles pour mettre
// dans bastion tout ce qui concerne les entrées, sorties, autorisations,
// partages ». Rien n'est dupliqué : chaque onglet AGRÈGE ce que les tuiles
// d'origine exposent déjà (leurs API), avec les actions de coupure qui
// existent (bloquer une flotte d'agents, arrêter un tunnel, démonter un
// partage, lever une permission) et un renvoi vers la tuile d'origine
// pour le reste.

export const BASTION_TABS = [
  { id: "proxy", label: "Bastion si-proxy", icon: "🛡" },
  { id: "entries", label: "Entrées", icon: "⬇" },
  { id: "exits", label: "Sorties", icon: "⬆" },
  { id: "auth", label: "Autorisations", icon: "🔑" },
  { id: "shares", label: "Partages", icon: "🔗" },
];

// ---- Entrées -------------------------------------------------------------
// Ports publiés directement (contournent la passerelle) : lecture de
// EXPOSURE.json. Sévérité : base de données ou index exposés sur toutes les
// interfaces = critique ; API/portail hors passerelle = avertissement ;
// boucle locale seulement = info.
const DB_HINT = /postgres|mysql|maria|elasticsearch|redis|memcached|mongo/i;
export function classifyDirectPort(p) {
  if (p.loopback_only) return { severity: "info", why: "boucle locale de la VM seulement" };
  if (DB_HINT.test(p.service)) return { severity: "critical", why: "base ou index joignable directement, hors passerelle et hors Keycloak" };
  if (p.proto === "udp") return { severity: "warning", why: "flux UDP entrant (pas de TLS, pas d'authentification)" };
  return { severity: "warning", why: "API ou portail publié hors passerelle TLS" };
}

export function summarizeExposure(exposure) {
  const direct = (exposure?.direct_ports || []).map((p) => ({ ...p, ...classifyDirectPort(p) }));
  const order = { critical: 0, warning: 1, info: 2 };
  direct.sort((a, b) => order[a.severity] - order[b.severity] || Number(a.host_port) - Number(b.host_port));
  return {
    gatewayPort: exposure?.gateway_port || "6443",
    gateway: exposure?.gateway || [],
    direct,
    hostNetwork: exposure?.host_network || [],
    counts: { critical: direct.filter((d) => d.severity === "critical").length, warning: direct.filter((d) => d.severity === "warning").length,
      info: direct.filter((d) => d.severity === "info").length, gateway: (exposure?.gateway || []).length },
    error: exposure?.error || null,
  };
}

// Agents entrants (si-agent) + sondes (netprobe) : ce qui SE CONNECTE au hub.
export function summarizeInbound({ siAgentStatus, siAgentFleet, netprobeAgents }) {
  const fleet = siAgentFleet || [];
  const probes = netprobeAgents || [];
  const staleAfter = 600 * 1000;
  const now = Date.now();
  const probeOnline = probes.filter((a) => a.last_seen_at && now - new Date(a.last_seen_at).getTime() < staleAfter).length;
  return {
    siAgent: siAgentStatus && !siAgentStatus.error ? {
      total: fleet.length, online: fleet.filter((a) => a.online === "online").length,
      blocked: fleet.filter((a) => a.blocked || a.host_blocked).length,
      fleetBlocked: !!siAgentStatus.fleet_blocked, fleetBlockReason: siAgentStatus.fleet_block_reason || null,
      insecure: siAgentStatus.insecure_agents || [], publicUrl: siAgentStatus.public_url || null,
    } : null,
    netprobe: { total: probes.length, online: probeOnline, roles: probes.reduce((m, a) => { m[a.role || "?"] = (m[a.role || "?"] || 0) + 1; return m; }, {}) },
  };
}

// ---- Sorties -------------------------------------------------------------
export function summarizeOutbound({ tunnels, connections, mounts, connectors }) {
  const byConn = new Map((connections || []).map((c) => [c.id, c]));
  const t = (tunnels || []).map((x) => {
    const c = byConn.get(x.connection_id);
    return { id: x.id, label: x.label, status: x.status || "stopped", running: x.status === "running",
      via: c ? `${c.ssh_user ? `${c.ssh_user}@` : ""}${c.ssh_host}${c.ssh_port && c.ssh_port !== 22 ? `:${c.ssh_port}` : ""}` : `connexion #${x.connection_id}`,
      to: `${x.remote_host}:${x.remote_port}`, localPort: x.local_port, lastError: x.last_error || null };
  });
  const m = (mounts || []).map((x) => {
    const c = byConn.get(x.connection_id);
    return { id: x.id, label: x.label, status: x.status || "unmounted", mounted: x.status === "mounted",
      via: c ? c.ssh_host : `connexion #${x.connection_id}`, remotePath: x.remote_path, localPath: x.local_mount_path, lastError: x.last_error || null };
  });
  return {
    tunnels: t, mounts: m, connections: connections || [],
    connectors: (connectors || []).map((c) => ({ ...c, state: c.state || (c.error ? "critical" : c.configured === false ? "warning" : "ok") })),
    counts: { tunnelsRunning: t.filter((x) => x.running).length, tunnels: t.length, mounted: m.filter((x) => x.mounted).length, mounts: m.length,
      hosts: new Set((connections || []).map((c) => c.ssh_host)).size },
  };
}

// Connecteurs sortants : chaque tuile qui parle à un service EXTERNE, à partir
// de son /health (ou équivalent). `probe` = résultat brut du client ; on ne
// garde qu'un état + un libellé.
export const OUTBOUND_CONNECTORS = [
  { id: "nebula", label: "Zyxel Nebula (cloud)", tile: "nebula", what: "inventaire sites/appareils/clients, import GLPI" },
  { id: "glpi", label: "GLPI (API REST)", tile: "glpi-inventory", what: "lecture et ÉCRITURE d'items d'inventaire" },
  { id: "imap", label: "Messagerie IMAP", tile: "imap", what: "lecture de boîtes, règles, déplacement de messages" },
  { id: "owncloud", label: "ownCloud / Nextcloud (base externe)", tile: "external-bases", what: "lecture seule de l'arborescence" },
  { id: "backup", label: "Sauvegardes (BackupPC / Clonezilla / restic)", tile: "backup-restore", what: "cibles de sauvegarde et restauration" },
  { id: "geoip", label: "Géolocalisation IP (ip-api.com)", tile: "supervision-si", what: "IP publiques seulement ; IP privées : table locale" },
  { id: "notify", label: "Notifications (webhook / SMTP / SMS)", tile: "si-agent", what: "alertes sortantes des agents, UPS, secrets" },
];

export function connectorState(id, probe) {
  if (probe == null) return { id, state: "unknown", text: "non configuré dans le hub (URL absente)" };
  if (probe.error) return { id, state: "critical", text: probe.error };
  if (probe.configured === false) return { id, state: "warning", text: "service joignable mais connecteur non configuré" };
  return { id, state: "ok", text: probe.text || "joignable" };
}

// ---- Autorisations -------------------------------------------------------
export function summarizeAuthorizations({ permissions, resourceTypes, externalLinks, groups }) {
  const perms = permissions || [];
  const byType = new Map();
  for (const p of perms) {
    const cur = byType.get(p.resource_type) || { resourceType: p.resource_type, count: 0, groups: new Set(), actions: new Set(), items: [] };
    cur.count += 1; cur.groups.add(p.group_name); cur.actions.add(p.action); cur.items.push(p);
    byType.set(p.resource_type, cur);
  }
  const types = [...byType.values()].map((t) => ({ ...t, groups: [...t.groups].sort(), actions: [...t.actions].sort() })).sort((a, b) => b.count - a.count);
  const links = (externalLinks || []).map((l) => ({ id: l.id, name: l.name, url: l.url, roles: Array.isArray(l.allowed_roles) ? l.allowed_roles : [],
    everyone: !Array.isArray(l.allowed_roles) || l.allowed_roles.length === 0, keycloak: !!l.keycloak_client_id }));
  return {
    permissions: types, totalPermissions: perms.length,
    resourceTypes: resourceTypes || [],
    links, linksForEveryone: links.filter((l) => l.everyone).length,
    myGroups: groups || [],
    // sans permission déclarée, un type de ressource « ouvert » = visible de tous (opt-in rights-api)
    openTypes: (resourceTypes || []).filter((rt) => !byType.has(typeof rt === "string" ? rt : rt.id || rt.name)),
  };
}

// ---- Partages ------------------------------------------------------------
export function summarizeShares({ fileSources, mounts, gedCount }) {
  const src = (fileSources || []).map((s) => ({ id: s.id, label: s.label || s.id, type: s.type || s.id, description: s.description || "",
    protectedSpace: s.type === "protected-space" || s.id === "protected-space", available: s.available !== false }));
  const m = (mounts || []).map((x) => ({ id: x.id, label: x.label, mounted: x.status === "mounted", remotePath: x.remote_path, localPath: x.local_mount_path }));
  return { sources: src, mounts: m, gedCount: gedCount ?? null,
    counts: { sources: src.length, mounted: m.filter((x) => x.mounted).length, mounts: m.length } };
}

// Compteur d'attention pour l'en-tête de la tuile (ce qui mérite un regard).
export function attentionCounts({ exposure, inbound, outbound, auth }) {
  return {
    entries: (exposure?.counts?.critical || 0) + (exposure?.counts?.warning || 0) + (inbound?.siAgent?.insecure?.length || 0),
    exits: (outbound?.tunnels || []).filter((t) => t.lastError).length + (outbound?.connectors || []).filter((c) => c.state === "critical").length,
    auth: auth?.linksForEveryone || 0,
    shares: 0,
  };
}
