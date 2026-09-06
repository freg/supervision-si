// Client d'agrégation des logs — interroge GET /logs sur chacun des 9
// services Flask du projet (chacun avec son propre tampon en mémoire,
// voir SERVICE_NAME dans leurs app.py respectifs) et renvoie les
// résultats bruts par service ; la fusion/tri se fait dans logsLib.js.
//
// Duplique volontairement les URLs de base déjà définies dans chaque
// *Api.js dédié plutôt que de les importer — même convention
// d'autonomie que le reste du projet (chaque module reste
// indépendant), et celui-ci a justement besoin de TOUS les services à
// la fois, contrairement aux autres clients qui n'en visent qu'un.
//
// pixel-grid-bridge et pipeline sont volontairement HORS PÉRIMÈTRE :
// ce sont des scripts de fond sans serveur HTTP, pas des services
// Flask — leurs logs restent visibles seulement via
// `docker compose logs pixel-grid-bridge` / `docker compose logs pipeline`.
const SERVICES = [
  { name: "api", envVar: "VITE_API_BASE_URL", defaultUrl: "http://localhost:6103" },
  { name: "pixel-grid-api", envVar: "VITE_PIXEL_GRID_API_BASE_URL", defaultUrl: "http://localhost:6104" },
  { name: "tickets-api", envVar: "VITE_TICKETS_API_BASE_URL", defaultUrl: "http://localhost:6105" },
  { name: "ipam-api", envVar: "VITE_IPAM_API_BASE_URL", defaultUrl: "http://localhost:6106" },
  { name: "optick-api", envVar: "VITE_OPTICK_API_BASE_URL", defaultUrl: "http://localhost:6107" },
  { name: "zenoss-api", envVar: "VITE_ZENOSS_API_BASE_URL", defaultUrl: "http://localhost:6108" },
  { name: "tts-gu-api", envVar: "VITE_TTSGU_API_BASE_URL", defaultUrl: "http://localhost:6109" },
  { name: "owncloud-api", envVar: "VITE_OWNCLOUD_API_BASE_URL", defaultUrl: "http://localhost:6110" },
  { name: "cacti-api", envVar: "VITE_CACTI_API_BASE_URL", defaultUrl: "http://localhost:6111" },
  { name: "owncloud-search-api", envVar: "VITE_OWNCLOUD_SEARCH_API_BASE_URL", defaultUrl: "http://localhost:6112" },
  { name: "geo-import-api", envVar: "VITE_GEO_IMPORT_API_BASE_URL", defaultUrl: "http://localhost:6113" },
];

export const KNOWN_SERVICE_NAMES = SERVICES.map((s) => s.name);

function baseUrlFor(service) {
  return import.meta.env[service.envVar] || service.defaultUrl;
}

/** Interroge les 9 services en parallèle. Ne lève jamais : un service
 * injoignable renvoie {service, entries: [], error} plutôt que de
 * faire échouer l'agrégation entière — les 8 autres restent lisibles. */
export async function fetchAllLogs(limit = 50) {
  return Promise.all(
    SERVICES.map(async (service) => {
      try {
        const response = await fetch(`${baseUrlFor(service)}/logs?limit=${limit}`);
        if (!response.ok) {
          return { service: service.name, entries: [], error: `HTTP ${response.status}` };
        }
        const body = await response.json();
        return { service: service.name, entries: body.entries || [], error: null };
      } catch (err) {
        return { service: service.name, entries: [], error: String(err) };
      }
    })
  );
}
