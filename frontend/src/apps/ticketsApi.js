export const API_BASE_URL = import.meta.env.VITE_TICKETS_API_BASE_URL || "http://localhost:6105";

async function getJson(path) {
  try {
    const response = await fetch(`${API_BASE_URL}${path}`);
    if (!response.ok) return null;
    return await response.json();
  } catch (err) {
    return null;
  }
}

async function postJson(path, body) {
  try {
    const response = await fetch(`${API_BASE_URL}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await response.json().catch(() => ({}));
    return { ok: response.ok, data };
  } catch (err) {
    return { ok: false, data: { error: "Impossible de joindre l'API tickets" } };
  }
}

async function putJson(path, body) {
  try {
    const response = await fetch(`${API_BASE_URL}${path}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await response.json().catch(() => ({}));
    return { ok: response.ok, data };
  } catch (err) {
    return { ok: false, data: { error: "Impossible de joindre l'API tickets" } };
  }
}

async function deleteRow(path) {
  try {
    const response = await fetch(`${API_BASE_URL}${path}`, { method: "DELETE" });
    const data = await response.json().catch(() => ({}));
    return { ok: response.ok, data };
  } catch (err) {
    return { ok: false, data: { error: "Impossible de joindre l'API tickets" } };
  }
}

export async function updateUser(id, fields) {
  return putJson(`/users/${id}`, fields);
}
export async function deleteUserRow(id) {
  return deleteRow(`/users/${id}`);
}
export async function updateType(id, fields) {
  return putJson(`/types/${id}`, fields);
}
export async function deleteTypeRow(id) {
  return deleteRow(`/types/${id}`);
}
export async function updateLevel(id, fields) {
  return putJson(`/levels/${id}`, fields);
}
export async function deleteLevelRow(id) {
  return deleteRow(`/levels/${id}`);
}
export async function updateStatut(id, fields) {
  return putJson(`/statuts/${id}`, fields);
}
export async function deleteStatutRow(id) {
  return deleteRow(`/statuts/${id}`);
}
export async function updateTicket(id, fields) {
  return putJson(`/tickets/${id}`, fields);
}

export async function updateRawTableRow(table, id, fields) {
  return putJson(`/raw_tables/${table}/${id}`, fields);
}

export async function fetchTermSynthesis(term) {
  return getJson(`/terms/synthesis?term=${encodeURIComponent(term)}`);
}

export async function exportDatabase() {
  return getJson("/export");
}

export async function importDatabase(data, mode) {
  return postJson(`/import?mode=${mode}`, data);
}

export async function fetchUsers() {
  return (await getJson("/users")) || [];
}
export async function fetchTypes() {
  return (await getJson("/types")) || [];
}
export async function fetchLevels() {
  return (await getJson("/levels")) || [];
}
export async function fetchStatuts() {
  return (await getJson("/statuts")) || [];
}

export async function createUser(user) {
  return postJson("/users", user);
}
export async function createType(type) {
  return postJson("/types", type);
}
export async function createLevel(level) {
  return postJson("/levels", level);
}
export async function createStatut(statut) {
  return postJson("/statuts", statut);
}

export async function fetchQueue(filters = {}) {
  const params = new URLSearchParams();
  if (filters.typeId) params.set("type_id", filters.typeId);
  if (filters.userId) params.set("user_id", filters.userId);
  if (filters.statutId) params.set("statut_id", filters.statutId);
  if (filters.state) params.set("state", filters.state);
  if (filters.all) params.set("all", "true");
  const query = params.toString();
  const result = await getJson(`/queue${query ? `?${query}` : ""}`);
  return result?.tickets || [];
}

export async function fetchTicket(id) {
  return getJson(`/tickets/${id}`);
}

export async function createTicket(ticket) {
  return postJson("/tickets", ticket);
}

export async function addTimeEntry(ticketId, startTs, endTs) {
  return postJson(`/tickets/${ticketId}/time_entries`, { start_ts: startTs, end_ts: endTs });
}

export async function suggestNameForEvents(eventIds) {
  return postJson("/calendar/suggest_name", { event_ids: eventIds });
}

export async function fetchTitleMatches(minScore = 1) {
  return (await getJson(`/calendar/title_matches?min_score=${minScore}`)) || { matches: [], total_events_analyzed: 0 };
}

export async function mineCandidates(limit = 15) {
  return (await getJson(`/calendar/mine_candidates?limit=${limit}`)) || { candidates: [], total_events_analyzed: 0 };
}

export async function fetchCalendarEvents(only = "unassigned", sort = "relevance") {
  const result = await getJson(`/calendar/events?only=${only}&sort=${sort}`);
  return result?.events || [];
}

export async function fetchPriorityKeywords() {
  return (await getJson("/priority_keywords")) || [];
}

export async function createPriorityKeyword(rule) {
  return postJson("/priority_keywords", rule);
}

export async function deletePriorityKeyword(id) {
  try {
    const response = await fetch(`${API_BASE_URL}/priority_keywords/${id}`, { method: "DELETE" });
    return response.ok;
  } catch (err) {
    return false;
  }
}

export async function assignEvents(eventIds, ticketIds, mode, reopen = false) {
  return postJson("/calendar/assign", { event_ids: eventIds, ticket_ids: ticketIds, mode, reopen });
}

export async function fetchParallelTickets(ticketIds, groupBy = "ticket") {
  const params = new URLSearchParams({ group_by: groupBy });
  if (ticketIds && ticketIds.length) params.set("ticket_ids", ticketIds.join(","));
  const result = await getJson(`/tickets/parallel?${params.toString()}`);
  return result?.tickets || [];
}

export async function fetchSettings() {
  return (await getJson("/settings")) || {};
}

export async function updateSettings(settings) {
  return postJson("/settings", settings);
}

export async function fetchExclusionRules() {
  return (await getJson("/exclusion_rules")) || [];
}

export async function createExclusionRule(rule) {
  return postJson("/exclusion_rules", rule);
}

export async function deleteExclusionRule(id) {
  try {
    const response = await fetch(`${API_BASE_URL}/exclusion_rules/${id}`, { method: "DELETE" });
    return response.ok;
  } catch (err) {
    return false;
  }
}

export async function fetchFilterRules() {
  return (await getJson("/filter_rules")) || [];
}

export async function createFilterRule(rule) {
  return postJson("/filter_rules", rule);
}

export async function deleteFilterRule(id) {
  try {
    const response = await fetch(`${API_BASE_URL}/filter_rules/${id}`, { method: "DELETE" });
    return response.ok;
  } catch (err) {
    return false;
  }
}

export async function fetchGoogleOAuthStatus() {
  return (await getJson("/oauth/google/status")) || { configured: false, connected: false };
}

export async function importGoogleApi() {
  return postJson("/calendar/import_google_api", {});
}

export async function importCalendarFile(file) {
  const form = new FormData();
  form.append("file", file);
  try {
    const response = await fetch(`${API_BASE_URL}/calendar/import`, { method: "POST", body: form });
    const data = await response.json().catch(() => ({}));
    return { ok: response.ok, data };
  } catch (err) {
    return { ok: false, data: { error: "Impossible de joindre l'API tickets" } };
  }
}

export async function importCalendarUrl(url) {
  return postJson("/calendar/import_url", { url });
}
