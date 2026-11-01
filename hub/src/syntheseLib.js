// Infos synthèse SI (livraison #523) -- logique pure de la vue : filtre
// transversal, liens vers IPAM / OVH / Online, échéances, description d'une IP.
// Testée par node --test (hub/tests/synthese.test.mjs).

export function fillLink(template, vars) {
  if (!template) return null;
  let out = template;
  for (const [k, v] of Object.entries(vars || {})) out = out.split(`{${k}}`).join(encodeURIComponent(v ?? ""));
  return out.includes("{") ? null : out;
}

/** Liens pour une adresse : IPAM (si URL connue), gestion de l'IP chez OVH (si l'IP y est). */
export function ipLinks(ip, info, links) {
  const out = [];
  if (links?.ipam_url && links?.ipam_search) {
    const href = links.ipam_search.replace("{ipam_url}", links.ipam_url).replace("{query}", encodeURIComponent(ip));
    out.push({ label: "IPAM", href });
  }
  if (info?.ovh && links?.ovh_ip) out.push({ label: "IP OVH", href: fillLink(links.ovh_ip, { ip }) });
  return out.filter((l) => l.href);
}

export function zoneLink(zone, links) {
  if (!zone?.zone) return null;
  if (zone.provider === "online") return fillLink(links?.online_zone, { zone: zone.zone });
  return fillLink(links?.ovh_zone, { zone: zone.zone });
}

/** Jours avant une échéance ISO (négatif si dépassée) ; null si absente. */
export function daysUntil(iso, now = Date.now()) {
  if (!iso) return null;
  const t = Date.parse(iso + "T00:00:00");
  if (Number.isNaN(t)) return null;
  return Math.round((t - now) / 86400000);
}

export function describeIp(ip, info) {
  const parts = [];
  if (info?.dns?.length) parts.push(`DNS : ${info.dns.join(", ")}`);
  if (info?.ovh) parts.push(`OVH ${info.ovh.type || ""} ${info.ovh.service || ""}`.trim());
  if (info?.services?.length) parts.push(`services : ${info.services.map((s) => s.type).join(", ")}`);
  if (info?.ipam?.length) parts.push(`IPAM : ${info.ipam.map((h) => `${h.hostname || "?"} ${h.description ? `(${h.description})` : ""}`.trim()).join(", ")}`);
  if (info?.devices?.length) parts.push(`équipement : ${info.devices.join(", ")}`);
  return parts.join(" · ") || "aucune information recoupée";
}

const hit = (q, ...values) => values.some((v) => v != null && String(v).toLowerCase().includes(q));

/** Filtre transversal : une requête vide rend le document tel quel ; sinon chaque
 *  section ne garde que ce qui contient la requête (IP recoupées comprises). */
export function filterDoc(doc, query) {
  const q = (query || "").trim().toLowerCase();
  if (!q) return doc;
  const idx = doc.index || {};
  const ipMatches = (ip) => ip && (hit(q, ip) || (idx[ip] && hit(q, ...(idx[ip].dns || []), ...(idx[ip].ipam || []).map((h) => `${h.hostname} ${h.description}`), ...(idx[ip].devices || []))));
  return {
    ...doc,
    ovh_ips: (doc.ovh_ips || []).filter((o) => ipMatches(o.ip) || hit(q, o.block, o.type, o.service, o.description)),
    zones: (doc.zones || []).map((z) => ({ ...z, records: z.records.filter((r) => hit(q, z.zone, r.name, r.fqdn, r.type, r.value, r.comment) || ((r.type === "A" || r.type === "AAAA") && ipMatches(r.value))) })).filter((z) => z.records.length),
    ipam: {
      subnets: (doc.ipam?.subnets || []).map((s) => ({ ...s, hosts: s.hosts.filter((h) => hit(q, s.title, s.cidr, s.vlan, h.ip, h.hostname, h.description, h.mac, h.device, h.location, h.reverse, h.note)) })).filter((s) => s.hosts.length),
      devices: (doc.ipam?.devices || []).filter((d) => hit(q, d.name, d.ip, d.type, d.vendor, d.model)),
    },
    ovh_services: (doc.ovh_services || []).filter((s) => hit(q, s.service, s.type, s.status, s.ip) || ipMatches(s.ip)),
  };
}
