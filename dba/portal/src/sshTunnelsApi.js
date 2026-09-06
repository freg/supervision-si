// Client API vers ssh-tunnels-api pour le catalogue SGBD (livraison
// #229, backlog item 11 -- extension au portail DBA lui-même, après
// la version déjà livrée côté hub en #221/SchemaAnalyzerView.jsx).
// Même convention de réponse que api.js de CE portail
// ({ok, status, data}) -- PAS le motif {error} du hub, pour rester
// cohérent avec le reste de ce codebase précis plutôt que copier
// mécaniquement une convention d'ailleurs.

export const SSH_TUNNELS_API_BASE_URL =
  import.meta.env.VITE_SSH_TUNNELS_API_BASE_URL || "http://localhost:6134";

async function sshRequest(path, options = {}) {
  try {
    const response = await fetch(`${SSH_TUNNELS_API_BASE_URL}${path}`, options);
    const data = await response.json().catch(() => ({}));
    return { ok: response.ok, status: response.status, data };
  } catch (err) {
    return { ok: false, status: 0, data: { error: String(err) } };
  }
}

export const fetchSshTunnels = () => sshRequest("/tunnels");
export const fetchSshConnections = () => sshRequest("/connections");
export const fetchSshConnectionUsageHistory = (connectionId) => sshRequest(`/connections/${connectionId}/usage-history`);
export const startSshTunnel = (tunnelId) => sshRequest(`/tunnels/${tunnelId}/start`, { method: "POST" });
export const stopSshTunnel = (tunnelId) => sshRequest(`/tunnels/${tunnelId}/stop`, { method: "POST" });
