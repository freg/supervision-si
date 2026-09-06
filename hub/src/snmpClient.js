// Client API vers snmp-api (livraison #212-213, interface hub #227).
// Même motif que sshTunnelsClient.js -- toutes les fonctions renvoient
// TOUJOURS le corps JSON de la réponse, même en cas d'erreur HTTP.

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

// --- Cibles enregistrées ---
export async function fetchSnmpTargets(apiBase) {
  const data = await fetchJson(apiBase, "/targets");
  return Array.isArray(data) ? data : [];
}

export async function createSnmpTarget(apiBase, { label, host, port, community, actor }) {
  return fetchJson(apiBase, "/targets", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ label, host, port: port ? Number(port) : undefined, community, actor }),
  });
}

export async function deleteSnmpTarget(apiBase, targetId) {
  return fetchJson(apiBase, `/targets/${targetId}`, { method: "DELETE" });
}

// --- Interrogation (cible enregistrée OU host+community en direct) ---
export async function querySnmpSystemInfo(apiBase, { targetId, host, community, port, timeout }) {
  const body = targetId
    ? { target_id: targetId, port: port ? Number(port) : undefined, timeout }
    : { host, community, port: port ? Number(port) : undefined, timeout };
  return fetchJson(apiBase, "/query", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export async function walkSnmpInterfaces(apiBase, { targetId, host, community, port, timeout }) {
  const body = targetId
    ? { target_id: targetId, port: port ? Number(port) : undefined, timeout }
    : { host, community, port: port ? Number(port) : undefined, timeout };
  return fetchJson(apiBase, "/walk-interfaces", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

// --- Pont vers GLPI (livraison #232) -- appelé côté glpi-api, pas snmp-api ---
export async function importSnmpTargetsToGlpi(glpiApiBase, dryRun) {
  return fetchJson(glpiApiBase, `/import/snmp-targets?dry_run=${dryRun ? "true" : "false"}`, { method: "POST" });
}
