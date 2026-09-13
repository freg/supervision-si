// Client API vers imap-connectors (livraison #489). Même motif que
// snmpClient.js -- toutes les fonctions renvoient TOUJOURS le corps
// JSON de la réponse, même en cas d'erreur HTTP.

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

const json = (method, body) => ({ method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });

export const fetchConnectors = async (apiBase) => {
  const data = await fetchJson(apiBase, "/connectors");
  return Array.isArray(data?.connectors) ? data.connectors : [];
};
export const createConnector = (apiBase, body) => fetchJson(apiBase, "/connectors", json("POST", body));
export const updateConnector = (apiBase, id, body) => fetchJson(apiBase, `/connectors/${id}`, json("PUT", body));
export const deleteConnector = (apiBase, id) => fetchJson(apiBase, `/connectors/${id}`, { method: "DELETE" });
export const testConnector = (apiBase, id) => fetchJson(apiBase, `/connectors/${id}/test`, json("POST", {}));
export const runConnector = (apiBase, id) => fetchJson(apiBase, `/connectors/${id}/run`, json("POST", {}));
export const fetchConnectorStats = (apiBase, days = 30) => fetchJson(apiBase, `/stats?days=${days}`);
export const fetchConnectorMessages = async (apiBase, { connectorId, errors } = {}) => {
  const q = new URLSearchParams();
  if (connectorId) q.set("connector_id", String(connectorId));
  if (errors) q.set("errors", "1");
  const data = await fetchJson(apiBase, `/messages?${q.toString()}`);
  return Array.isArray(data?.messages) ? data.messages : [];
};

// Cloche SMS (livraison #490) : non lus + accusés de réception.
export const fetchNotifications = (apiBase, targets = ["sms"]) =>
  fetchJson(apiBase, `/notifications?targets=${encodeURIComponent(targets.join(","))}`);
export const ackNotifications = (apiBase, body) =>
  fetchJson(apiBase, "/notifications/ack", json("POST", body));
