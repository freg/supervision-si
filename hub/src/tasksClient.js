// Client API vers tasks-api (livraison #271, gestion de tâches
// indépendante des tickets, vue Kanban).

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

export async function fetchTasks(apiBase) {
  const data = await fetchJson(apiBase, "/tasks");
  return Array.isArray(data) ? data : [];
}
export async function createTask(apiBase, payload) {
  return fetchJson(apiBase, "/tasks", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload),
  });
}
export async function updateTask(apiBase, taskId, fields) {
  return fetchJson(apiBase, `/tasks/${taskId}`, {
    method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(fields),
  });
}
export async function moveTask(apiBase, taskId, status, position) {
  return fetchJson(apiBase, `/tasks/${taskId}/move`, {
    method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ status, position }),
  });
}
export async function deleteTask(apiBase, taskId) {
  return fetchJson(apiBase, `/tasks/${taskId}`, { method: "DELETE" });
}
