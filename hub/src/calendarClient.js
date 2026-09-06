// Client API vers tickets-api pour le calendrier (livraison #272 --
// vue hub manquante sur un backend déjà substantiel, voir
// tickets/README.md "Chantier en cours (calendrier ICS)").

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

export async function fetchCalendarEvents(ticketsApiBase, only) {
  const query = only ? `?only=${only}` : "";
  const data = await fetchJson(ticketsApiBase, `/calendar/events${query}`);
  return Array.isArray(data?.events) ? data.events : [];
}
export async function importFromUrl(ticketsApiBase, url) {
  return fetchJson(ticketsApiBase, "/calendar/import_url", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ url }),
  });
}
export async function assignEventsToTickets(ticketsApiBase, eventIds, ticketIds, mode) {
  return fetchJson(ticketsApiBase, "/calendar/assign", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ event_ids: eventIds, ticket_ids: ticketIds, mode: mode || "full" }),
  });
}
export async function fetchOpenTickets(ticketsApiBase) {
  const data = await fetchJson(ticketsApiBase, "/queue");
  return Array.isArray(data?.tickets) ? data.tickets : [];
}
export async function createTicketFromEvent(ticketsApiBase, eventId) {
  return fetchJson(ticketsApiBase, "/calendar/create_ticket", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ event_id: eventId }),
  });
}
export async function fetchPendingValidationTickets(ticketsApiBase) {
  const data = await fetchJson(ticketsApiBase, "/tickets/pending_validation");
  return Array.isArray(data?.tickets) ? data.tickets : [];
}
export async function validateTicket(ticketsApiBase, ticketId, fields) {
  return fetchJson(ticketsApiBase, `/tickets/${ticketId}/validate`, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(fields || {}),
  });
}
export async function rejectTicket(ticketsApiBase, ticketId) {
  return fetchJson(ticketsApiBase, `/tickets/${ticketId}`, {
    method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ archived_at: Math.floor(Date.now() / 1000) }),
  });
}
export async function fetchUsers(ticketsApiBase) {
  const data = await fetchJson(ticketsApiBase, "/users");
  return Array.isArray(data) ? data : Array.isArray(data?.users) ? data.users : [];
}
export async function fetchTypes(ticketsApiBase) {
  const data = await fetchJson(ticketsApiBase, "/types");
  return Array.isArray(data) ? data : [];
}
export async function fetchLevels(ticketsApiBase) {
  const data = await fetchJson(ticketsApiBase, "/levels");
  return Array.isArray(data) ? data : [];
}
export async function fetchStatuts(ticketsApiBase) {
  const data = await fetchJson(ticketsApiBase, "/statuts");
  return Array.isArray(data) ? data : [];
}
export async function deleteTicket(ticketsApiBase, ticketId) {
  return fetchJson(ticketsApiBase, `/tickets/${ticketId}`, { method: "DELETE" });
}
export async function recalculateTicketStatus(ticketsApiBase, ticketId) {
  return fetchJson(ticketsApiBase, `/tickets/${ticketId}/recalculate_status`, { method: "POST" });
}
export async function fetchPendingStatusChanges(ticketsApiBase) {
  const data = await fetchJson(ticketsApiBase, "/status-changes/pending");
  return Array.isArray(data?.changes) ? data.changes : [];
}
export async function validateAllStatusChanges(ticketsApiBase) {
  return fetchJson(ticketsApiBase, "/status-changes/validate_all", { method: "POST" });
}
