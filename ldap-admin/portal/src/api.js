// Client API du portail LDAP -- même convention que dba/portal/src/api.js,
// étendue pour porter le mot de passe de liaison en en-tête
// (X-LDAP-Bind-Password) à chaque appel qui en a besoin. Ce mot de
// passe n'est JAMAIS stocké ici -- transmis en paramètre par
// l'appelant (App.jsx, état React en mémoire uniquement), jamais lu
// depuis un stockage persistant.
export const API_BASE_URL =
  import.meta.env.VITE_LDAP_ADMIN_API_BASE_URL || "http://localhost:6122";

async function request(path, options = {}, bindPassword) {
  try {
    const headers = { ...(options.headers || {}) };
    if (bindPassword) headers["X-LDAP-Bind-Password"] = bindPassword;
    const response = await fetch(`${API_BASE_URL}${path}`, { ...options, headers });
    const data = await response.json().catch(() => ({}));
    return { ok: response.ok, status: response.status, data };
  } catch (err) {
    return { ok: false, status: 0, data: { error: String(err) } };
  }
}

export const getJson = (path, bindPassword) => request(path, {}, bindPassword);
export const postJson = (path, body, bindPassword) =>
  request(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }, bindPassword);
export const putJson = (path, body, bindPassword) =>
  request(path, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }, bindPassword);

/** Contenu LDIF brut d'une sauvegarde -- réponse text/plain, pas
 * JSON, d'où une fonction séparée plutôt que de forcer getJson à
 * gérer les deux formats. */
export async function getText(path) {
  try {
    const response = await fetch(`${API_BASE_URL}${path}`);
    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      return { ok: false, status: response.status, data };
    }
    const text = await response.text();
    return { ok: true, status: response.status, text };
  } catch (err) {
    return { ok: false, status: 0, data: { error: String(err) } };
  }
}
