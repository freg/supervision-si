// Client file-manager (livraison #396, backlog item 26) -- consomme
// file-manager-api pour agréger les sources (GED, SSHFS, espace protégé).

const DEFAULT_BASE = import.meta.env.VITE_FILE_MANAGER_API_BASE_URL || "";

async function _request(url, options = {}) {
  const resp = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const data = await resp.json().catch(() => ({}));
  return { status: resp.status, data };
}

export function fetchSources(apiBase = DEFAULT_BASE, groups = []) {
  return _request(`${apiBase}/sources`, {
    method: "POST",
    body: JSON.stringify({ groups }),
  });
}

export function browseSource(apiBase, sourceId, path = "", groups = [], depth = 1) {
  const params = new URLSearchParams({ path, depth: String(depth) });
  return _request(`${apiBase}/browse/${sourceId}?${params}`, {
    method: "POST",
    body: JSON.stringify({ groups }),
  });
}

export function browseItem(apiBase, sourceId, itemId, path = "", groups = []) {
  const params = new URLSearchParams({ path });
  return _request(`${apiBase}/browse/${sourceId}/${itemId}?${params}`, {
    method: "POST",
    body: JSON.stringify({ groups }),
  });
}

export function fetchStats(apiBase, sourceId, groups = []) {
  return _request(`${apiBase}/stats/${sourceId}`, {
    method: "POST",
    body: JSON.stringify({ groups }),
  });
}
