// Client API vers ssh-tunnels-api (livraison #159, onglet hub #175).
// Même motif que gedClient.js/schemaAnalyzerClient.js -- toutes les
// fonctions renvoient TOUJOURS le corps JSON de la réponse, même en
// cas d'erreur HTTP (cette API renvoie systématiquement
// {"error": "..."} dans ce cas, un message précis à afficher tel
// quel).

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
  } catch {
    return { error: "Service ssh-tunnels injoignable" };
  }
}

// --- Clés SSH ---
export async function fetchKeys(apiBase) {
  const data = await fetchJson(apiBase, "/keys");
  return Array.isArray(data) ? data : [];
}

export async function setKeyEnabled(apiBase, keyId, enabled) {
  return fetchJson(apiBase, `/keys/${keyId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ enabled }),
  });
}

export async function deleteKey(apiBase, keyId) {
  return fetchJson(apiBase, `/keys/${keyId}`, { method: "DELETE" });
}

export async function generateKey(apiBase, { filename, passphrase, keyType }) {
  return fetchJson(apiBase, "/keys/generate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ filename, passphrase: passphrase || "", key_type: keyType || "ed25519" }),
  });
}

// --- Connexions SSH ---
export async function fetchConnections(apiBase) {
  const data = await fetchJson(apiBase, "/connections");
  return Array.isArray(data) ? data : [];
}

export async function createConnection(apiBase, { label, sshHost, sshPort, sshUser, sshKeyId, actor, authMethod, passwordUsername, password }) {
  return fetchJson(apiBase, "/connections", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      label, ssh_host: sshHost, ssh_port: sshPort ? Number(sshPort) : undefined,
      ssh_user: sshUser, ssh_key_id: sshKeyId, actor,
      auth_method: authMethod, password_username: passwordUsername, password,
    }),
  });
}

export async function deleteConnection(apiBase, connectionId) {
  return fetchJson(apiBase, `/connections/${connectionId}`, { method: "DELETE" });
}

/** Historique d'usage des identifiants (livraison #210, backlog item
 * 12) -- une ligne par tentative (tunnel ou montage), succès ET
 * échecs. */
export async function fetchConnectionUsageHistory(apiBase, connectionId) {
  return fetchJson(apiBase, `/connections/${connectionId}/usage-history`);
}

// --- Tunnels ---
export async function fetchTunnels(apiBase) {
  const data = await fetchJson(apiBase, "/tunnels");
  return Array.isArray(data) ? data : [];
}

export async function createTunnel(apiBase, { connectionId, label, remoteHost, remotePort, localPort, actor }) {
  return fetchJson(apiBase, "/tunnels", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      connection_id: connectionId, label, remote_host: remoteHost,
      remote_port: Number(remotePort), local_port: Number(localPort), actor,
    }),
  });
}

export async function deleteTunnel(apiBase, tunnelId) {
  return fetchJson(apiBase, `/tunnels/${tunnelId}`, { method: "DELETE" });
}

export async function startTunnel(apiBase, tunnelId) {
  return fetchJson(apiBase, `/tunnels/${tunnelId}/start`, { method: "POST" });
}

export async function stopTunnel(apiBase, tunnelId) {
  return fetchJson(apiBase, `/tunnels/${tunnelId}/stop`, { method: "POST" });
}

// --- Montages SSHFS (interface préparée -- mount/unmount renvoient
// volontairement une erreur 501 côté API tant que l'action réelle
// n'est pas construite, voir ssh-tunnels/README.md) ---
export async function fetchMounts(apiBase) {
  const data = await fetchJson(apiBase, "/mounts");
  return Array.isArray(data) ? data : [];
}

export async function createMount(apiBase, { connectionId, label, remotePath, localMountPath, actor }) {
  return fetchJson(apiBase, "/mounts", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      connection_id: connectionId, label, remote_path: remotePath,
      local_mount_path: localMountPath, actor,
    }),
  });
}

export async function deleteMount(apiBase, mountId) {
  return fetchJson(apiBase, `/mounts/${mountId}`, { method: "DELETE" });
}

export async function mountAction(apiBase, mountId) {
  return fetchJson(apiBase, `/mounts/${mountId}/mount`, { method: "POST" });
}

export async function unmountAction(apiBase, mountId) {
  return fetchJson(apiBase, `/mounts/${mountId}/unmount`, { method: "POST" });
}

// Supervision (livraison #182) -- espace/inodes distants, confirmation
// de montage actif, latence. `?latency=false` -- omis ici, toujours
// demandée par défaut (le hub affiche une valeur "..." pendant le
// calcul plutôt que de complexifier l'appel pour ce cas).
export async function fetchMountStats(apiBase, mountId) {
  return fetchJson(apiBase, `/mounts/${mountId}/stats`);
}
