// Client API vers classifier-api (livraison #260, classification
// sémantique des identités découvertes -- dictionnaires importables).

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

export async function importDictionary(apiBase, file, category, source) {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("category", category);
  if (source) formData.append("source", source);
  return fetchJson(apiBase, "/dictionaries/import", { method: "POST", body: formData });
}
export async function fetchTerms(apiBase, category) {
  const query = category ? `?category=${encodeURIComponent(category)}` : "";
  const data = await fetchJson(apiBase, `/dictionaries/terms${query}`);
  return Array.isArray(data) ? data : [];
}
export async function deleteTerm(apiBase, termId) {
  return fetchJson(apiBase, `/dictionaries/terms/${termId}`, { method: "DELETE" });
}
export async function deleteSource(apiBase, source) {
  return fetchJson(apiBase, `/dictionaries/sources/${encodeURIComponent(source)}`, { method: "DELETE" });
}
export async function fetchCategories(apiBase) {
  const data = await fetchJson(apiBase, "/dictionaries/categories");
  return Array.isArray(data) ? data : [];
}
export async function classifyText(apiBase, text, ipAddress) {
  const params = new URLSearchParams({ text });
  if (ipAddress) params.set("ip_address", ipAddress);
  return fetchJson(apiBase, `/classify?${params.toString()}`);
}
export async function classifyBatch(apiBase, items) {
  // `items` -- [{text, ip_address}, ...]. Best-effort explicite --
  // classifier-api peut être indisponible sans casser la vue
  // appelante (voir NetworkAgentView.jsx, livraison #261) : renvoie
  // toujours un objet, jamais une exception propagée.
  const data = await fetchJson(apiBase, "/classify/batch", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(items),
  });
  return data && !data.error ? data : {};
}
export async function confirmClassification(apiBase, text, category, addToDictionary, source) {
  return fetchJson(apiBase, "/classify/confirm", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text, category, add_to_dictionary: addToDictionary, source }),
  });
}
export async function fetchStats(apiBase) {
  const data = await fetchJson(apiBase, "/stats");
  return data && !data.error ? data : { by_category: [], top_terms: [] };
}
