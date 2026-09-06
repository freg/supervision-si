// Client API vers les routes /cyber-risks de prefs-api (livraison
// #187, écran hub "Cyber"). Même motif que fetchExternalLinks/
// createExternalLink déjà en place pour ce même service -- toutes
// les fonctions renvoient le corps JSON tel quel, y compris en cas
// d'erreur ({"error": "..."}).

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
    return { error: "Service préférences injoignable" };
  }
}

export async function fetchCyberRisks(apiBase) {
  const data = await fetchJson(apiBase, "/cyber-risks");
  return Array.isArray(data) ? data : [];
}

export async function createCyberRisk(apiBase, { label, description, category, modules, probability, impact, scope }) {
  return fetchJson(apiBase, "/cyber-risks", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ label, description, category, modules, probability, impact, scope }),
  });
}

/** Mise à jour PARTIELLE -- seuls les champs fournis dans `patch`
 * sont transmis (l'usage principal est {status} et/ou
 * {progress_notes} seuls, voir CyberView.jsx). */
export async function updateCyberRisk(apiBase, riskId, patch) {
  return fetchJson(apiBase, `/cyber-risks/${riskId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(patch),
  });
}

export async function deleteCyberRisk(apiBase, riskId) {
  return fetchJson(apiBase, `/cyber-risks/${riskId}`, { method: "DELETE" });
}

/** Historique VERSIONNÉ (livraison #199, demandé explicitement --
 * "un historique des matrices / versionné"). Sans `riskId` : tout
 * l'historique, toutes matrices confondues. Avec `riskId` : la
 * timeline d'UN risque précis (y compris s'il a depuis été
 * supprimé -- l'historique lui survit). */
export async function fetchCyberRisksHistory(apiBase, riskId) {
  const query = riskId ? `?risk_id=${riskId}` : "";
  return fetchJson(apiBase, `/cyber-risks/history${query}`);
}
