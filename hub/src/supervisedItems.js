// Logique PURE de la nouvelle tuile « Supervision SI » (livraison #423,
// backlog 64) -- aucun React, testée sous Node (hub/tests/supervisedItems.test.mjs).
//
// Trois responsabilités :
//   1. AGRÉGATION « supervisés » : tout ce que les tuiles supervisent,
//      ramené à une liste homogène {type, nom, site, état, dernier relevé,
//      tuile d'origine} et FUSIONNÉ par identité (même IP / même MAC = un
//      seul équipement, plusieurs origines).
//   2. PROPOSITIONS : suggestions de l'orchestrateur + signaux de vigilance
//      + appareils découverts (network-agent) non supervisés -- à cocher /
//      décocher par la personne (état persisté).
//   3. LIENS : liens construits automatiquement (flux network-agent, sites,
//      tunnels) et POSITION DÉDUITE d'un équipement sans coordonnées par ses
//      liens (« en période d'exploration, seule l'analyse des liens offre
//      une position ») -- la chaîne de déduction est conservée et affichée.

export const ITEM_TYPES = {
  probe: { label: "Sonde réseau", origin: "netprobe", icon: "📡" },
  ups: { label: "Onduleur", origin: "ups", icon: "🔋" },
  agent: { label: "Agent hôte", origin: "si-agent", icon: "🖥" },
  snmp: { label: "Cible SNMP", origin: "snmp", icon: "🧭" },
  tunnel: { label: "Tunnel SSH", origin: "ssh-tunnels", icon: "🔐" },
  wifi: { label: "Sonde WiFi", origin: "netprobe", icon: "📶" },
};

// Tri d'affichage : ce qui demande attention d'abord (l'inconnu avant l'ok).
export const STATE_ORDER = { critical: 0, warning: 1, unknown: 2, ok: 3 };
// Fusion : l'état CONNU le pire l'emporte ; « inconnu » (cible déclarée,
// jamais interrogée) ne dégrade jamais un état mesuré.
const MERGE_ORDER = { critical: 0, warning: 1, ok: 2, unknown: 3 };

const norm = (s) => (s == null ? "" : String(s)).trim().toLowerCase();

function identity(ip, mac, name) {
  if (ip) return `ip:${norm(ip)}`;
  if (mac) return `mac:${norm(mac)}`;
  return `name:${norm(name)}`;
}

// ---- 1. Normalisation par source ---------------------------------------

export function fromNetprobe(targets, latest, nowMs = Date.now()) {
  const byTarget = new Map((latest || []).map((s) => [s.target_id, s]));
  return (targets || []).map((t) => {
    const s = byTarget.get(t.id);
    let state = "unknown", stateText = "jamais sondée";
    if (!t.active) { state = "unknown"; stateText = "désactivée"; }
    else if (s) {
      if (!s.success) { state = "critical"; stateText = s.error || "injoignable"; }
      else if ((s.packet_loss_percent || 0) > 0) { state = "warning"; stateText = `perte ${s.packet_loss_percent} %`; }
      else { state = "ok"; stateText = s.latency_ms != null ? `${Math.round(s.latency_ms)} ms` : "répond"; }
    }
    return { key: `probe:${t.id}`, type: "probe", name: t.label || t.ip_address, ip: t.ip_address || null, mac: null, site: null,
      state, stateText, lastSeen: s?.sampled_at || null, origin: "netprobe", originId: t.id, identity: identity(t.ip_address, null, t.label) };
  });
}

export function fromUps(devices, nowMs = Date.now()) {
  return (devices || []).map((d) => {
    let state = "unknown", stateText = d.last_state || "inconnu";
    if (!d.enabled) { stateText = "désactivé"; }
    else if (d.last_ok === false) { state = "critical"; stateText = d.last_error || "échec du relevé"; }
    else if (d.last_state === "alarm") { state = "critical"; stateText = "alarme"; }
    else if (d.last_state === "ok") { state = "ok"; stateText = "normal"; }
    if (state === "ok" && d.last_polled_at) {
      const age = (nowMs - Date.parse(d.last_polled_at)) / 1000;
      if (Number.isFinite(age) && age > (d.poll_interval_seconds || 3600) * 2.5) { state = "warning"; stateText = "relevé ancien"; }
    }
    return { key: `ups:${d.id}`, type: "ups", name: d.name, ip: d.host || null, mac: null, site: d.site || null,
      state, stateText, lastSeen: d.last_polled_at || null, origin: "ups", originId: d.id, identity: identity(d.host, null, d.name) };
  });
}

export function fromSiAgent(fleet) {
  return (fleet || []).map((a) => {
    let state = "unknown", stateText = "jamais vu";
    if (a.online === "offline") { state = "critical"; stateText = "hors ligne"; }
    else if (a.online === "online") {
      const rs = a.risks?.state;
      state = rs === "critical" ? "critical" : rs === "warning" ? "warning" : "ok";
      stateText = rs === "critical" ? "risque critique" : rs === "warning" ? "avertissement" : "en ligne";
      if (a.blocked || a.host_blocked) stateText += " · sondes bloquées";
    }
    return { key: `agent:${a.agent_id}`, type: "agent", name: a.hostname || a.label || a.agent_id, ip: a.last_ip && !a.last_ip.startsWith("127.") ? a.last_ip : null, mac: null,
      site: a.site || null, state, stateText, lastSeen: a.last_seen_at || null, origin: "si-agent", originId: a.agent_id,
      identity: identity(a.last_ip && !a.last_ip.startsWith("127.") ? a.last_ip : null, null, a.hostname || a.agent_id) };
  });
}

export function fromSnmp(targets) {
  return (targets || []).map((t) => ({
    key: `snmp:${t.id}`, type: "snmp", name: t.label || t.host, ip: t.host || null, mac: null, site: null,
    state: "unknown", stateText: "déclarée (interrogation à la demande)", lastSeen: t.updated_at || null, origin: "snmp", originId: t.id,
    identity: identity(t.host, null, t.label),
  }));
}

export function fromSshTunnels(tunnels, connections) {
  const conn = new Map((connections || []).map((c) => [c.id, c]));
  return (tunnels || []).map((t) => {
    const c = conn.get(t.connection_id);
    const state = t.status === "running" ? "ok" : t.status === "error" ? "critical" : "unknown";
    return { key: `tunnel:${t.id}`, type: "tunnel", name: t.label, ip: c?.ssh_host || null, mac: null, site: null,
      state, stateText: t.status === "running" ? "actif" : t.status === "error" ? (t.last_error || "erreur") : "arrêté",
      lastSeen: t.updated_at || null, origin: "ssh-tunnels", originId: t.id, identity: identity(c?.ssh_host, null, t.label),
      remote: t.remote_host ? `${t.remote_host}:${t.remote_port}` : null };
  });
}

export function fromWifiAgents(agents, nowMs = Date.now(), staleAfter = 600) {
  return (agents || []).map((a) => {
    let state = "unknown", stateText = "jamais vue";
    if (a.last_seen_at) {
      const age = (nowMs - Date.parse(a.last_seen_at)) / 1000;
      state = age > staleAfter ? "warning" : "ok";
      stateText = age > staleAfter ? "silencieuse" : "en ligne";
    }
    if (a.active === false) { state = "unknown"; stateText = "désactivée"; }
    return { key: `wifi:${a.agent_id}`, type: "wifi", name: a.label || a.agent_id, ip: a.last_ip || null, mac: null, site: a.site || null,
      state, stateText, lastSeen: a.last_seen_at || null, origin: "netprobe", originId: a.agent_id, identity: identity(a.last_ip, null, a.agent_id) };
  });
}

// ---- Fusion par identité ------------------------------------------------

export function mergeItems(lists) {
  const out = new Map();
  for (const item of lists.flat()) {
    const cur = out.get(item.identity);
    if (!cur) {
      out.set(item.identity, { ...item, origins: [{ origin: item.origin, type: item.type, originId: item.originId, key: item.key, state: item.state, stateText: item.stateText }] });
      continue;
    }
    cur.origins.push({ origin: item.origin, type: item.type, originId: item.originId, key: item.key, state: item.state, stateText: item.stateText });
    if (MERGE_ORDER[item.state] < MERGE_ORDER[cur.state]) { cur.state = item.state; cur.stateText = item.stateText; }
    cur.site = cur.site || item.site;
    cur.ip = cur.ip || item.ip;
    cur.mac = cur.mac || item.mac;
    if (!cur.lastSeen || (item.lastSeen && item.lastSeen > cur.lastSeen)) cur.lastSeen = item.lastSeen;
  }
  return [...out.values()];
}

export function aggregateSupervised(sources, nowMs = Date.now()) {
  return mergeItems([
    fromNetprobe(sources.netprobeTargets, sources.netprobeLatest, nowMs),
    fromUps(sources.upsDevices, nowMs),
    fromSiAgent(sources.siAgentFleet),
    fromSnmp(sources.snmpTargets),
    fromSshTunnels(sources.sshTunnels, sources.sshConnections),
    fromWifiAgents(sources.wifiAgents, nowMs),
  ]);
}

// ---- 2. Propositions ------------------------------------------------------

export function buildProposals({ suggestions, signals, devices, supervised }) {
  const known = new Set();
  for (const it of supervised || []) { if (it.ip) known.add(`ip:${norm(it.ip)}`); if (it.mac) known.add(`mac:${norm(it.mac)}`); }
  const out = [];
  for (const s of suggestions || []) {
    if (s.status && s.status !== "open") continue;
    out.push({ key: `orch:${s.id}`, kind: "orchestrateur", severity: s.severity || "info", label: s.message, detail: s.suggested_action || s.rule_name,
      subject: s.subject_key, ip: s.subject_type === "ip" ? s.subject_key : null, mac: s.subject_type === "mac" ? s.subject_key : null, at: s.last_detected_at, raw: s });
  }
  for (const v of signals || []) {
    out.push({ key: `vig:${v.id}`, kind: "vigilance", severity: v.severity || "info", label: `${v.device_label || v.device_mac} : ${v.signal_type}`, detail: v.detail,
      subject: v.device_mac, ip: null, mac: v.device_mac, at: v.detected_at, raw: v });
  }
  for (const d of devices || []) {
    const ipk = d.ip_address ? `ip:${norm(d.ip_address)}` : null;
    const mack = d.mac_address ? `mac:${norm(d.mac_address)}` : null;
    if ((ipk && known.has(ipk)) || (mack && known.has(mack))) continue;
    out.push({ key: `dev:${d.id}`, kind: "decouvert", severity: "info", label: d.hostname || d.ip_address || d.mac_address,
      detail: [d.role_hint, d.ip_address, d.mac_address].filter(Boolean).join(" · "), subject: d.ip_address || d.mac_address, ip: d.ip_address || null, mac: d.mac_address || null, at: d.last_seen, raw: d });
  }
  const sev = { critical: 0, high: 0, warning: 1, medium: 1, info: 2, low: 2 };
  return out.sort((a, b) => (sev[a.severity] ?? 2) - (sev[b.severity] ?? 2) || String(b.at || "").localeCompare(String(a.at || "")));
}

// ---- Filtre et priorisation -------------------------------------------------

export function filterSupervised(items, { text = "", types = null, states = null, site = "" } = {}) {
  const t = norm(text);
  return (items || []).filter((it) => {
    if (types && types.length && !types.includes(it.type) && !it.origins.some((o) => types.includes(o.type))) return false;
    if (states && states.length && !states.includes(it.state)) return false;
    if (site && norm(it.site) !== norm(site)) return false;
    if (t && !`${it.name} ${it.ip || ""} ${it.mac || ""} ${it.site || ""} ${it.stateText}`.toLowerCase().includes(t)) return false;
    return true;
  });
}

// `priorities` : {identity: rang} (1 = premier). Priorisés d'abord (par
// rang), puis état (critique en tête), puis nom.
export function prioritizeSupervised(items, priorities = {}) {
  return [...(items || [])].sort((a, b) => {
    const pa = priorities[a.identity], pb = priorities[b.identity];
    if (pa != null || pb != null) {
      if (pa == null) return 1;
      if (pb == null) return -1;
      if (pa !== pb) return pa - pb;
    }
    return (STATE_ORDER[a.state] ?? 2) - (STATE_ORDER[b.state] ?? 2) || String(a.name).localeCompare(String(b.name));
  });
}

export function setPriority(priorities, identity, rank) {
  const p = { ...(priorities || {}) };
  if (rank == null) delete p[identity]; else p[identity] = rank;
  return p;
}

export function movePriority(priorities, orderedIdentities, identity, delta) {
  const ranked = orderedIdentities.filter((id) => priorities[id] != null).sort((a, b) => priorities[a] - priorities[b]);
  const idx = ranked.indexOf(identity);
  if (idx < 0) return setPriority(priorities, identity, ranked.length + 1);
  const to = Math.max(0, Math.min(ranked.length - 1, idx + delta));
  ranked.splice(idx, 1); ranked.splice(to, 0, identity);
  const out = {};
  ranked.forEach((id, i) => { out[id] = i + 1; });
  return out;
}

// ---- 3. Liens et positions déduites -------------------------------------------

// Liens homogènes : {a, b (identités), kind: "flux"|"tunnel"|"site", weight, label, via}
export function buildLinks({ naLinks = [], naDevices = [], tunnels = [], connections = [], supervised = [] }) {
  const devById = new Map((naDevices || []).map((d) => [d.id, d]));
  const out = [];
  for (const l of naLinks || []) {
    const a = devById.get(l.device_a_id), b = devById.get(l.device_b_id);
    if (!a || !b) continue;
    out.push({ a: identity(a.ip_address, a.mac_address, null), b: identity(b.ip_address, b.mac_address, null), kind: "flux", weight: l.bytes_total || 0,
      label: `${a.ip_address || a.mac_address} ↔ ${b.ip_address || b.mac_address}`, via: "network-agent" });
  }
  const conn = new Map((connections || []).map((c) => [c.id, c]));
  for (const t of tunnels || []) {
    const c = conn.get(t.connection_id);
    if (!c) continue;
    out.push({ a: identity(c.ssh_host, null, null), b: identity(t.remote_host, null, t.remote_host), kind: "tunnel", weight: 1, label: `${t.label} (${c.ssh_host} → ${t.remote_host}:${t.remote_port})`, via: "ssh-tunnels" });
  }
  // appartenance à un site : tous les supervisés d'un même site sont liés à son « nœud site »
  for (const it of supervised || []) {
    if (it.site) out.push({ a: it.identity, b: `site:${norm(it.site)}`, kind: "site", weight: 0, label: `${it.name} ∈ site ${it.site}`, via: "déclaration" });
  }
  return out;
}

// Positions connues : {identity -> {lat, lon, source, label}} depuis les
// coordonnées déclarées (network-agent), la table geolocations (pixel-grid,
// par nom / IP / site) et les sites.
// #426 : `matches` = {identity -> correspondance nom/site -> localisation
// calculée par pixel-grid (/geolocations/resolve), statut auto | suggested |
// validated | rejected | manual}. Une correspondance appliquée (auto,
// validated, manual) AVEC coordonnées vaut position « nom » -- plus jamais
// la position de repli pour « UPS-Arobase-5 » quand « Arobase 5 » est connue.
export const MATCH_STATUS = {
  auto: { label: "auto", applied: true },
  validated: { label: "validée", applied: true },
  manual: { label: "manuelle", applied: true },
  suggested: { label: "à confirmer", applied: false },
  rejected: { label: "rejetée", applied: false },
};

export function appliedMatch(matches, identity) {
  const m = matches && (matches instanceof Map ? matches.get(identity) : matches[identity]);
  return m && m.status && MATCH_STATUS[m.status]?.applied && m.localisation ? m : null;
}

// Site affiché : déclaré sur l'équipement, sinon la localisation résolue.
export function displaySite(item, matches) {
  if (item.site) return { site: item.site, resolved: false };
  const m = appliedMatch(matches, item.identity);
  return m ? { site: m.localisation, resolved: true, status: m.status } : { site: null, resolved: false };
}

export function knownPositions({ naDevices = [], geolocations = [], sites = [], supervised = [], matches = null }) {
  const pos = new Map();
  const geo = new Map((geolocations || []).filter((g) => g.latitude != null && g.longitude != null).map((g) => [norm(g.localisation), g]));
  for (const d of naDevices || []) {
    if (d.latitude != null && d.longitude != null) pos.set(identity(d.ip_address, d.mac_address, null), { lat: d.latitude, lon: d.longitude, source: "déclarée", label: "coordonnées de l'appareil (network-agent)" });
  }
  // nœud « site » : nom exact dans la table, sinon correspondance résolue
  // (« Annexe-Nord » -> « Agence Annexe Nord »)
  const siteNode = (name) => {
    const key = `site:${norm(name)}`;
    if (pos.has(key)) return;
    const g = geo.get(norm(name));
    if (g) { pos.set(key, { lat: g.latitude, lon: g.longitude, source: "site", label: `site ${name} (géolocalisations)` }); return; }
    const m = appliedMatch(matches, key);
    if (m && m.latitude != null && m.longitude != null) pos.set(key, { lat: m.latitude, lon: m.longitude, source: "site", label: `site ${name} ≈ ${m.localisation} (${MATCH_STATUS[m.status].label})`, match: m });
  };
  for (const s of sites || []) siteNode(s.name);
  for (const it of supervised || []) {
    if (it.site) siteNode(it.site);
    if (pos.has(it.identity)) continue;
    const g = geo.get(norm(it.ip)) || geo.get(norm(it.name));
    if (g) { pos.set(it.identity, { lat: g.latitude, lon: g.longitude, source: "géolocalisation", label: `table des géolocalisations (${g.localisation})` }); continue; }
    const m = appliedMatch(matches, it.identity);
    if (m && m.latitude != null && m.longitude != null) {
      const how = m.status === "auto" ? `automatique, ${m.method || "proche"}, score ${m.score}` : MATCH_STATUS[m.status].label;
      pos.set(it.identity, { lat: m.latitude, lon: m.longitude, source: "nom", label: `${m.localisation} d'après ${(m.method || "").endsWith("/site") ? "le site déclaré" : "le nom"} (${how})`, match: m });
    }
  }
  const dflt = geo.get("__default__");
  if (dflt) pos.set("__default__", { lat: dflt.latitude, lon: dflt.longitude, source: "repli", label: "position de repli (__default__)" });
  return pos;
}

// Déduction : un nœud sans position prend la moyenne pondérée des voisins
// positionnés (flux : poids = volume ; site : poids fort) ; itéré en
// largeur, profondeur bornée ; la chaîne {via, from} est conservée.
export function deducePositions(identities, links, known, { maxDepth = 3, useDefault = true } = {}) {
  const result = new Map();
  for (const [k, v] of known) result.set(k, { ...v, depth: 0, chain: [] });
  const neighbors = new Map();
  for (const l of links || []) {
    if (!neighbors.has(l.a)) neighbors.set(l.a, []);
    if (!neighbors.has(l.b)) neighbors.set(l.b, []);
    neighbors.get(l.a).push({ other: l.b, link: l });
    neighbors.get(l.b).push({ other: l.a, link: l });
  }
  for (let depth = 1; depth <= maxDepth; depth += 1) {
    const added = [];
    for (const id of identities) {
      if (result.has(id)) continue;
      const ns = (neighbors.get(id) || []).filter((n) => result.has(n.other));
      if (!ns.length) continue;
      let sw = 0, lat = 0, lon = 0;
      const chain = [];
      for (const n of ns) {
        const p = result.get(n.other);
        const w = n.link.kind === "site" ? 1000 : Math.max(1, Math.log10(1 + (n.link.weight || 0)));
        sw += w; lat += p.lat * w; lon += p.lon * w;
        chain.push({ via: n.link.kind, from: n.other, label: n.link.label, fromSource: p.source, fromDepth: p.depth });
      }
      added.push([id, { lat: lat / sw, lon: lon / sw, source: "déduite", depth, chain, label: `déduite de ${ns.length} lien(s)` }]);
    }
    if (!added.length) break;
    for (const [id, p] of added) result.set(id, p);
  }
  if (useDefault && result.has("__default__")) {
    const d = result.get("__default__");
    for (const id of identities) if (!result.has(id)) result.set(id, { lat: d.lat, lon: d.lon, source: "repli", depth: 99, chain: [], label: "position de repli" });
  }
  return result;
}

export function describeChain(p) {
  if (!p) return "sans position";
  if (p.source === "déduite") return `déduite (profondeur ${p.depth}) via ${p.chain.map((c) => `${c.via} → ${c.from} [${c.fromSource}]`).join(", ")}`;
  return p.label || p.source;
}

// ---- Cadres de la page centrale -------------------------------------------------

export const FRAME_KINDS = {
  map: "Carte",
  table: "Table des supervisés",
  links: "Liens et positions",
  proposals: "Propositions",
  summary: "Synthèse par état",
  // #424 : outils de l'ancienne maquette, nourris par les tuiles
  timeline: "Timeline des états",
  grid: "Mosaïque (pixel-grid)",
  calendar: "Calendrier de densité",
  radial: "Arbre radial",
  // #426 : correspondances nom -> localisation à valider, alias, lieux sans coordonnées
  geo: "Localisations",
};

export const DEFAULT_FRAMES = [{ kind: "map" }, { kind: "table" }];

// Disposition : 1 = plein ; 2 = côte à côte ; 3 = deux en haut + le
// troisième pleine largeur en bas ; 4 = 2 x 2.
export function frameLayout(n) {
  if (n <= 1) return { columns: "1fr", rows: "1fr", areas: ['"f0"'] };
  if (n === 2) return { columns: "1fr 1fr", rows: "1fr", areas: ['"f0 f1"'] };
  if (n === 3) return { columns: "1fr 1fr", rows: "1fr 1fr", areas: ['"f0 f1"', '"f2 f2"'] };
  return { columns: "1fr 1fr", rows: "1fr 1fr", areas: ['"f0 f1"', '"f2 f3"'] };
}

export function normalizeFrames(frames) {
  const list = Array.isArray(frames) ? frames.filter((f) => f && FRAME_KINDS[f.kind]) : [];
  if (!list.length) return DEFAULT_FRAMES.map((f) => ({ ...f }));
  return list.slice(0, 4).map((f) => ({ kind: f.kind }));
}

export function summarizeByState(items) {
  const out = { critical: 0, warning: 0, unknown: 0, ok: 0, total: 0, byType: {} };
  for (const it of items || []) {
    out[it.state] = (out[it.state] || 0) + 1; out.total += 1;
    const t = out.byType[it.type] || { critical: 0, warning: 0, unknown: 0, ok: 0, total: 0 };
    t[it.state] += 1; t.total += 1; out.byType[it.type] = t;
  }
  return out;
}

// ---- Préférences (localStorage, même motif que cycleActions.js) -----------------

export const PREF_KEYS = { frames: "hub.supervision.frames", priorities: "hub.supervision.priorities", proposals: "hub.supervision.proposals", tab: "hub.supervision.tab",
  selection: "hub.supervision.selection", window: "hub.supervision.window" };

export function loadPref(storage, key, fallback) {
  try {
    const raw = storage?.getItem(key);
    return raw ? JSON.parse(raw) : fallback;
  } catch { return fallback; }
}

export function savePref(storage, key, value) {
  try { storage?.setItem(key, JSON.stringify(value)); } catch { /* stockage indisponible : préférence non persistée */ }
}

// Points superposés (même site, même position de repli) : écartés en
// spirale de quelques mètres pour rester tous cliquables sur la carte.
export function spreadCoincident(points, step = 0.0006) {
  const groups = new Map();
  for (const p of points) {
    const k = `${p.lat.toFixed(5)},${p.lon.toFixed(5)}`;
    if (!groups.has(k)) groups.set(k, []);
    groups.get(k).push(p);
  }
  const out = [];
  for (const g of groups.values()) {
    g.forEach((p, i) => {
      if (i === 0) { out.push({ ...p, dlat: p.lat, dlon: p.lon }); return; }
      const r = step * Math.ceil(i / 6), a = (i % 6) * (Math.PI / 3) + Math.floor(i / 6) * 0.5;
      out.push({ ...p, dlat: p.lat + r * Math.cos(a), dlon: p.lon + r * Math.sin(a) * 1.5 });
    });
  }
  return out;
}

// ---- #426 : sujets envoyés à /geolocations/resolve et synthèse du cadre -----

// Un sujet par supervisé : identité stable, nom et site déclaré. Les
// sujets « IP nue » ou « MAC nue » sans nom lisible sont quand même envoyés
// (le site déclaré peut suffire).
export function resolveSubjects(supervised, sites = []) {
  const out = (supervised || []).map((it) => ({ subject: it.identity, name: it.name || null, site: it.site || null }));
  // nœuds « site » (sites d'exploration réseau et sites déclarés) : le nom
  // du site seul, pour placer le nœud auquel les liens rattachent les autres
  const names = new Set([...(sites || []).map((s) => s.name), ...(supervised || []).map((it) => it.site)].filter(Boolean).map((n) => String(n)));
  for (const n of names) out.push({ subject: `site:${norm(n)}`, name: null, site: n });
  return out;
}

export function resolveKey(supervised, sites = []) {
  return resolveSubjects(supervised, sites).map((s) => `${s.subject}|${s.name || ""}|${s.site || ""}`).sort().join("\n");
}

// Lignes du cadre « Localisations » : une par supervisé, avec la
// correspondance (ou son absence), triées : à confirmer, puis sans
// correspondance, puis automatiques, validées/manuelles, rejetées.
export function geoRows(supervised, matches) {
  const order = { suggested: 0, none: 1, auto: 2, validated: 3, manual: 3, rejected: 4 };
  return (supervised || []).map((it) => {
    const m = matches && (matches instanceof Map ? matches.get(it.identity) : matches[it.identity]);
    const status = m?.status || "none";
    return { item: it, match: m || null, status, applied: !!appliedMatch(matches, it.identity), mapped: !!m?.mapped };
  }).sort((a, b) => (order[a.status] ?? 1) - (order[b.status] ?? 1) || String(a.item.name).localeCompare(String(b.item.name)));
}

export function geoSummary(rows, geolocations = []) {
  const out = { total: rows.length, applied: 0, suggested: 0, none: 0, rejected: 0, unmapped: 0, pendingPlaces: 0 };
  for (const r of rows) {
    if (r.applied) out.applied += 1;
    if (r.status === "suggested") out.suggested += 1;
    if (r.status === "none") out.none += 1;
    if (r.status === "rejected") out.rejected += 1;
    if (r.applied && !r.mapped) out.unmapped += 1;
  }
  out.pendingPlaces = (geolocations || []).filter((g) => g.latitude == null || g.longitude == null).filter((g) => g.localisation !== "__default__").length;
  return out;
}
