// Client API du portail coffre-fort -- ne transporte JAMAIS de secret
// en clair (voir shared/vaultCrypto.js pour le chiffrement de bout en
// bout) : ce module reste un simple client HTTP, comme les autres
// fronts, aucune logique cryptographique ici.
//
// Lecture défensive de import.meta.env : n'existe QUE sous Vite --
// vaultOps.js (qui importe ce module) doit rester testable en Node
// nu, où import.meta.env est simplement absent plutôt qu'un objet
// vide, ce qui ferait planter un accès direct à sa propriété.
const env = (typeof import.meta !== "undefined" && import.meta.env) || {};
export const API_BASE_URL = env.VITE_VAULT_API_BASE_URL || "http://localhost:6117";

async function request(path, options = {}) {
  try {
    const response = await fetch(`${API_BASE_URL}${path}`, options);
    const data = await response.json().catch(() => ({}));
    return { ok: response.ok, status: response.status, data };
  } catch (err) {
    return { ok: false, status: 0, data: { error: String(err) } };
  }
}

export const getJson = (path) => request(path);
export const postJson = (path, body) =>
  request(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
export const putJson = (path, body) =>
  request(path, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
// deleteJson(path, body) -- body OPTIONNEL (undefined = DELETE sans
// corps, comportement historique préservé pour tout appelant
// existant). Ajouté : DELETE /secrets/<id> (devenu un archivage,
// voir vault-api) exige désormais `archived_by` dans le corps -- bug
// réel trouvé en testant : cette fonction l'ignorait silencieusement
// jusqu'ici, aucun appelant n'en avait eu besoin avant.
export const deleteJson = (path, body) =>
  request(path, {
    method: "DELETE",
    ...(body !== undefined
      ? { headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }
      : {}),
  });
