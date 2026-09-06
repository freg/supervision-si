// Classification IPv4 privée/publique — générique, aucune connaissance
// métier. Usage INFORMATIF uniquement (étiqueter une IP dans une liste
// avant de lancer une géolocalisation) : la décision qui compte
// vraiment (appeler ou non le service GeoIP externe) est reprise et
// revérifiée côté serveur (pixel-grid/api/app.py::classify_ip, basée
// sur le module standard Python `ipaddress`, IPv4 ET IPv6) — jamais une
// confiance aveugle dans ce doublon JS plus simple.
//
// IPv4 uniquement (toutes les IP réellement rencontrées dans ce
// projet jusqu'ici) — une IPv6 renvoie "unknown" plutôt qu'un verdict
// potentiellement faux.

function parseIpv4(ip) {
  const m = String(ip || "").trim().match(/^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$/);
  if (!m) return null;
  const octets = m.slice(1, 5).map(Number);
  if (octets.some((o) => o < 0 || o > 255)) return null;
  return octets;
}

/** "private" | "public" | "invalid" | "unknown" (non-IPv4, ex. IPv6 —
 * le backend reste seul juge dans ce cas, jamais un verdict local). */
export function classifyIp(ip) {
  const octets = parseIpv4(ip);
  if (!octets) {
    return /:/.test(String(ip || "")) ? "unknown" : "invalid";
  }
  const [a, b] = octets;

  if (a === 10) return "private"; // 10.0.0.0/8
  if (a === 172 && b >= 16 && b <= 31) return "private"; // 172.16.0.0/12
  if (a === 192 && b === 168) return "private"; // 192.168.0.0/16
  if (a === 127) return "private"; // loopback
  if (a === 169 && b === 254) return "private"; // link-local
  if (a === 0) return "private"; // non spécifiée
  if (a >= 224 && a <= 239) return "private"; // multicast
  if (a >= 240) return "private"; // réservée (classe E)

  return "public";
}

export function isGeolocatable(ip) {
  return classifyIp(ip) === "public";
}
