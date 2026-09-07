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

export const DEFAULT_FLOW_FILTERS = { hideHostRouter: false, minPct: 0, maxPct: 100 };

/**
 * Applique les filtres.
 * @param {Array} links
 * @param {Object} opts - { hideHostRouter, hostId, gatewayIds, minPct, maxPct }
 * @returns {{ links: Array, total: number, keptBytes: number,
 *            hidden: { hostRouter: number, band: number }, shares: Map }}
 */
export function applyFlowFilters(links, opts = {}) {
  const { total, shares } = computeShares(links);
  const { minPct, maxPct } = normalizeBand(opts.minPct, opts.maxPct);
  const hidden = { hostRouter: 0, band: 0 };
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
  return parts.join(" · ");
}
