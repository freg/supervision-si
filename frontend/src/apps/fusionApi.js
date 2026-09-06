// Fusion IP/MAC — appels DIRECTS aux services existants (mêmes URLs
// déjà utilisées par les onglets IPAM et Zenoss), corrélation faite
// entièrement côté navigateur. Aucun service intermédiaire, aucune
// copie de données quelque part.
const IPAM_API_BASE_URL = import.meta.env.VITE_IPAM_API_BASE_URL || "http://localhost:6106";
const ZENOSS_API_BASE_URL = import.meta.env.VITE_ZENOSS_API_BASE_URL || "http://localhost:6108";

async function fetchEntries(baseUrl, path) {
  try {
    const response = await fetch(`${baseUrl}${path}`);
    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      return { entries: [], error: body.error || `HTTP ${response.status}` };
    }
    const body = await response.json();
    return { entries: body.entries || [], error: null };
  } catch (err) {
    return { entries: [], error: String(err) };
  }
}

export const fetchIpamIpList = () => fetchEntries(IPAM_API_BASE_URL, "/ip_list");
export const fetchZenossIpList = () => fetchEntries(ZENOSS_API_BASE_URL, "/ip_list");
