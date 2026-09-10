// Filtres des visualisations de flux (Exploration réseau) -- livraison #412.
// Logique PURE (aucun React), testée sous Node (hub/tests/networkFlowFilters.test.mjs).
//
// Retour de tests : « ajouter des options de filtrage, notamment réduire la
// visu des flux entre l'hôte de la supervision et le routeur ; filtre sur
// une tranche du % des flux du graphique ». Deux filtres, appliqués AVANT
// les deux vues (alluvial, radial), jamais dans les composants de dessin :
//
//   1. hôte de supervision <-> routeur : ces échanges (hub, sondes,
//      tunnels, tout ce que la VM de supervision dit à la passerelle)
//      dominent le volume sans rien dire du site observé. L'hôte est
//      reconnu par la MAC (puis l'IP) de l'interface de capture, exposée
//      par `/capture/status` (#412) ; le routeur par le rôle deviné
//      « passerelle probable (NAT/routeur) ». La personne peut corriger
//      l'hôte à la main.
//   2. tranche de pourcentage : on garde les flux dont la PART DU VOLUME
//      TOTAL (tous flux du segment, avant tout filtre -- une base stable,
//      sinon la part de chaque flux changerait à chaque case cochée) est
//      comprise entre min % et max %. « Entre 0 et 2 % » isole le bruit de
//      fond, « entre 20 et 100 % » ne garde que les gros échanges.

export const GATEWAY_ROLE_HINT = "passerelle probable (NAT/routeur)";

function normMac(v) {
  return typeof v === "string" ? v.trim().toLowerCase() : "";
}

// Hôte de supervision parmi les appareils : MAC de l'interface de
// capture d'abord (identité forte), IP ensuite (peut être partagée après
// un changement de bail), sinon null -- jamais une devinette sur le nom.
export function findSupervisionHost(devices, captureStatus) {
  const list = Array.isArray(devices) ? devices : [];
  const mac = normMac(captureStatus?.interface_mac);
  if (mac) {
    const byMac = list.find((d) => normMac(d.mac_address) === mac);
    if (byMac) return byMac;
  }
  const ip = typeof captureStatus?.interface_ip === "string" ? captureStatus.interface_ip.trim() : "";
  if (ip) {
    const byIp = list.find((d) => d.ip_address === ip);
    if (byIp) return byIp;
  }
  return null;
}

export function findGateways(devices) {
  return (Array.isArray(devices) ? devices : []).filter((d) => d.role_hint === GATEWAY_ROLE_HINT);
}

export function isHostRouterLink(link, hostId, gatewayIds) {
  if (hostId == null || !gatewayIds || gatewayIds.length === 0) return false;
  const a = link.device_a_id;
  const b = link.device_b_id;
  const gw = new Set(gatewayIds);
  return (a === hostId && gw.has(b)) || (b === hostId && gw.has(a));
}

// Part de chaque flux dans le volume total, en pour cent (0 si total nul).
export function computeShares(links) {
  const list = (Array.isArray(links) ? links : []).filter((l) => (l?.bytes_total ?? 0) > 0);
  const total = list.reduce((s, l) => s + l.bytes_total, 0);
  const shares = new Map(list.map((l) => [l, total > 0 ? (l.bytes_total / total) * 100 : 0]));
  return { total, shares };
}

// Borne et ordonne une tranche saisie à la main : valeurs hors [0, 100]
// ramenées dans l'intervalle, min > max permutés, non-nombres → 0 / 100.
export function normalizeBand(minPct, maxPct) {
  const toNum = (v, dflt) => {
    const n = typeof v === "number" ? v : parseFloat(v);
    return Number.isFinite(n) ? Math.min(100, Math.max(0, n)) : dflt;
  };
  let lo = toNum(minPct, 0);
  let hi = toNum(maxPct, 100);
  if (lo > hi) [lo, hi] = [hi, lo];
  return { minPct: lo, maxPct: hi };
}

// --- Sous-réseaux (#414 : « réseau /24 /16 ») -- IPv4 seulement, pur ---

export const SUBNET_PREFIXES = [16, 20, 24, 28];

export function ipv4ToInt(ip) {
  if (typeof ip !== "string") return null;
  const parts = ip.trim().split(".");
  if (parts.length !== 4) return null;
  let n = 0;
  for (const p of parts) {
    if (!/^\d{1,3}$/.test(p)) return null;
    const v = Number(p);
    if (v > 255) return null;
    n = n * 256 + v;
  }
  return n;
}

function prefixMask(len) {
  if (len <= 0) return 0;
  if (len >= 32) return 0xffffffff;
  return (0xffffffff << (32 - len)) >>> 0;
}

// "192.168.1.0/24" pour une IP et une longueur de préfixe ; null si invalide.
export function subnetOf(ip, prefixLength) {
  const n = ipv4ToInt(ip);
  if (n === null || !Number.isInteger(prefixLength) || prefixLength < 0 || prefixLength > 32) return null;
  const base = (n & prefixMask(prefixLength)) >>> 0;
  const a = base >>> 24, b = (base >>> 16) & 255, c = (base >>> 8) & 255, d = base & 255;
  return `${a}.${b}.${c}.${d}/${prefixLength}`;
}

export function ipInSubnet(ip, cidr) {
  if (typeof cidr !== "string" || !cidr.includes("/")) return false;
  const [net, lenRaw] = cidr.split("/");
  const len = Number(lenRaw);
  const n = ipv4ToInt(ip);
  const b = ipv4ToInt(net);
  if (n === null || b === null || !Number.isInteger(len) || len < 0 || len > 32) return false;
  const m = prefixMask(len);
  return ((n & m) >>> 0) === ((b & m) >>> 0);
}

// Sous-réseaux présents parmi les appareils, à une longueur de préfixe
// donnée, avec le nombre d'appareils -- calculé côté client à partir des
// dernières IP connues (l'API a aussi /observed-subnets, mais on veut ici
// exactement les appareils affichés, filtres compris).
export function listDeviceSubnets(devices, prefixLength) {
  const counts = new Map();
  for (const d of Array.isArray(devices) ? devices : []) {
    const s = subnetOf(d.ip_address, prefixLength);
    if (!s) continue;
    counts.set(s, (counts.get(s) || 0) + 1);
  }
  return [...counts.entries()]
    .map(([subnet, count]) => ({ subnet, count }))
    .sort((x, y) => y.count - x.count || (x.subnet < y.subnet ? -1 : 1));
}

// Un flux « touche » le sous-réseau si l'un de ses deux appareils y est ;
// il est « interne » si les deux y sont.
export function linkSubnetRelation(link, devicesById, cidr) {
  const a = devicesById?.[link.device_a_id];
  const b = devicesById?.[link.device_b_id];
  const inA = ipInSubnet(a?.ip_address, cidr);
  const inB = ipInSubnet(b?.ip_address, cidr);
  if (inA && inB) return "intra";
  if (inA || inB) return "touche";
  return "hors";
}

export const DEFAULT_FLOW_FILTERS = {
  hideHostRouter: false,
  minPct: 0,
  maxPct: 100,
  minKo: "",          // volume minimal en Ko (vide = pas de borne)
  maxKo: "",          // volume maximal en Ko (vide = pas de borne)
  subnet: "",         // "192.168.1.0/24" ou vide
  subnetMode: "intra", // "intra" (les deux appareils dedans) ou "touche" (au moins un)
};

function koToBytes(v) {
  if (v === "" || v === null || v === undefined) return null;
  const n = typeof v === "number" ? v : parseFloat(v);
  return Number.isFinite(n) && n >= 0 ? n * 1024 : null;
}

/**
 * Applique les filtres.
 * @param {Array} links
 * @param {Object} opts - { hideHostRouter, hostId, gatewayIds, minPct, maxPct,
 *                          minKo, maxKo, subnet, subnetMode, devicesById }
 * @returns {{ links: Array, total: number, keptBytes: number,
 *            hidden: { hostRouter: number, band: number, volume: number, subnet: number }, shares: Map }}
 */
export function applyFlowFilters(links, opts = {}) {
  const { total, shares } = computeShares(links);
  const { minPct, maxPct } = normalizeBand(opts.minPct, opts.maxPct);
  let minBytes = koToBytes(opts.minKo);
  let maxBytes = koToBytes(opts.maxKo);
  if (minBytes !== null && maxBytes !== null && minBytes > maxBytes) [minBytes, maxBytes] = [maxBytes, minBytes];
  const subnet = typeof opts.subnet === "string" && opts.subnet.includes("/") ? opts.subnet : "";
  const subnetMode = opts.subnetMode === "touche" ? "touche" : "intra";
  const hidden = { hostRouter: 0, band: 0, volume: 0, subnet: 0 };
  const kept = [];
  for (const [l, share] of shares) {
    if (opts.hideHostRouter && isHostRouterLink(l, opts.hostId, opts.gatewayIds)) {
      hidden.hostRouter += 1;
      continue;
    }
    if (share < minPct || share > maxPct) {
      hidden.band += 1;
      continue;
    }
    if ((minBytes !== null && l.bytes_total < minBytes) || (maxBytes !== null && l.bytes_total > maxBytes)) {
      hidden.volume += 1;
      continue;
    }
    if (subnet) {
      const rel = linkSubnetRelation(l, opts.devicesById, subnet);
      if (rel === "hors" || (subnetMode === "intra" && rel !== "intra")) {
        hidden.subnet += 1;
        continue;
      }
    }
    kept.push(l);
  }
  const keptBytes = kept.reduce((s, l) => s + l.bytes_total, 0);
  return { links: kept, total, keptBytes, hidden, shares };
}

// Résumé lisible : « 5 flux sur 8 · 31 % du volume ».
export function describeFlowFilterResult(result) {
  const all = result.shares.size;
  const pct = result.total > 0 ? Math.round((result.keptBytes / result.total) * 100) : 0;
  const parts = [`${result.links.length} flux sur ${all}`, `${pct} % du volume`];
  if (result.hidden.hostRouter > 0) parts.push(`${result.hidden.hostRouter} hôte ↔ routeur masqué(s)`);
  if (result.hidden.band > 0) parts.push(`${result.hidden.band} hors tranche`);
  if (result.hidden.volume > 0) parts.push(`${result.hidden.volume} hors volume`);
  if (result.hidden.subnet > 0) parts.push(`${result.hidden.subnet} hors sous-réseau`);
  return parts.join(" · ");
}
