// Client API vers mikrotik-api (module livraison #485, intégration
// transversale hub #486). Même motif que snmpClient.js -- toutes les
// fonctions renvoient TOUJOURS le corps JSON de la réponse, même en
// cas d'erreur HTTP.

async function fetchJson(apiBase, path, options) {
  try {
    const res = await fetch(`${apiBase}${path}`, options);
    let data = null;
    try {
      data = await res.json();
    } catch {
      data = null;
    }
    if (data === null) {
      return { error: `Réponse invalide du serveur (HTTP ${res.status})` };
    }
    return data;
  } catch (err) {
    return { error: `Requête échouée : ${err.message}` };
  }
}

// Registre des routeurs + joignabilité mesurée par mikrotik-api
// (GET system/identity sur chaque routeur -- sonde légère).
// Renvoie toujours une LISTE (vide en cas d'erreur, le diagnostic
// reste affiché côté tuile MikroTik).
export async function fetchMikrotikRouters(apiBase) {
  const data = await fetchJson(apiBase, "/routers");
  return Array.isArray(data?.routers) ? data.routers : [];
}

// #606 : carte des redirections NAT de tous les routeurs (entrée → routeur → cible).
export const fetchNatMap = (apiBase, site = "") => fetchJson(apiBase, `/nat-map${site ? `?site=${encodeURIComponent(site)}` : ""}`);
export const setNatRule = (apiBase, router, id, patch) => fetchJson(apiBase, `/routers/${encodeURIComponent(router)}/nat/${encodeURIComponent(id)}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(patch) });
