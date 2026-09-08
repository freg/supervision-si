// Client de la console Bastion élargie (livraison #455) : sondes de santé
// des connecteurs SORTANTS (nebula, glpi, imap, sauvegardes, ownCloud) et
// inventaire d'exposition (si-proxy-admin-api /exposure, jeton Keycloak).
// Jamais d'exception vers le composant : {error} ou un objet.

async function getJson(url, options = {}) {
  try {
    const res = await fetch(url, options);
    let data = null;
    try { data = await res.json(); } catch { data = null; }
    if (!res.ok) return { error: (data && data.error) || `HTTP ${res.status}`, status: res.status };
    return data ?? {};
  } catch (err) {
    return { error: `injoignable : ${err.message}` };
  }
}

// /health générique -> {text, configured} ; "degraded" (ownCloud sans base) = non configuré.
export async function probeHealth(apiBase) {
  if (!apiBase) return null;
  const d = await getJson(`${apiBase}/health`);
  if (d.error) return d;
  if (d.status === "degraded") return { configured: false, text: Object.entries(d).filter(([k]) => k !== "status").map(([k, v]) => `${k} : ${v}`).join(", ") || "dégradé" };
  return { configured: true, text: "joignable" };
}

// Sauvegardes : /health + nombre de connecteurs déclarés.
export async function probeBackup(apiBase) {
  if (!apiBase) return null;
  const h = await probeHealth(apiBase);
  if (!h || h.error) return h;
  const c = await getJson(`${apiBase}/connectors`);
  const n = Array.isArray(c) ? c.length : Array.isArray(c?.connectors) ? c.connectors.length : null;
  return { configured: n == null ? true : n > 0, text: n == null ? "joignable" : `${n} connecteur(s) déclaré(s)` };
}

// IMAP : /health + nombre de boîtes configurées.
export async function probeImap(apiBase) {
  if (!apiBase) return null;
  const h = await probeHealth(apiBase);
  if (!h || h.error) return h;
  const f = await getJson(`${apiBase}/folders`);
  const n = Array.isArray(f) ? f.length : Array.isArray(f?.folders) ? f.folders.length : null;
  return { configured: n == null ? true : n > 0, text: n == null ? "joignable" : `${n} boîte(s) / dossier(s)` };
}

export async function fetchExposure(siProxyApiBase, token) {
  if (!siProxyApiBase || !token) return null;
  return getJson(`${siProxyApiBase}/exposure`, { headers: { Authorization: `Bearer ${token}` } });
}
