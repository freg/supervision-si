import React, { useState, useEffect } from "react";
import { fetchCalendarEvents, importFromUrl, assignEventsToTickets, fetchOpenTickets, createTicketFromEvent, deleteTicket, recalculateTicketStatus } from "./calendarClient.js";

// Filtre par motif à joker (livraison #282, demandé explicitement --
// "un filtre du genre '*SAV*DEV*' avec un on/off sur la casse").
// Convertit un motif façon glob (jokers `*` = n'importe quoi) en
// expression régulière ancrée sur toute la chaîne -- échappe TOUS
// les caractères spéciaux regex SAUF `*`, jamais l'inverse (un motif
// contenant des parenthèses, points... ne doit jamais casser la
// construction de la regex). Testée en isolation avant intégration
// (motif vide -> ne matche que la chaîne vide, jamais tout par
// défaut -- géré côté appelant : un motif vide désactive le filtre
// plutôt que de l'appliquer littéralement).
function wildcardToRegex(pattern, caseSensitive) {
  const escaped = pattern.replace(/[.+?^${}()|[\]\\]/g, "\\$&").replace(/\*/g, ".*");
  return new RegExp("^" + escaped + "$", caseSensitive ? "" : "i");
}

// Tuile "Calendrier" (hub), livraison #272 -- reprend un chantier
// explicitement noté "en cours, non livré" côté tickets/README.md :
// le backend (parseur ICS, /calendar/import_url, moteur de
// suggestion, affectation aux tickets) existait déjà et a été
// vérifié réellement avant cette livraison -- SEULE la vue manquait
// côté interface.
//
// Vue AGENDA (liste triée par date), pas une grille semaine/jour --
// choix délibéré dans cet environnement sans navigateur réel pour
// tester visuellement une grille complexe ; une liste reste un
// agenda au sens plein du terme, fonctionnelle et entièrement
// vérifiable.

function formatDate(ts) {
  return new Date(ts * 1000).toLocaleString("fr-FR", { weekday: "short", day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });
}

// Même logique que tickets/portal/src/lib.js:fmtDuration -- dupliquée
// ici plutôt qu'importée (deux frontends SÉPARÉS, aucune dépendance
// croisée entre eux, même motif d'autonomie déjà établi ailleurs
// dans ce projet côté backend).
function formatWaitDuration(seconds) {
  const s = Math.round(seconds || 0);
  if (s < 60) return `${s} s`;
  const h = Math.floor(s / 3600);
  const m = Math.round((s % 3600) / 60);
  if (h === 0) return `${m} min`;
  return m === 0 ? `${h} h` : `${h} h ${String(m).padStart(2, "0")}`;
}

export default function CalendarView({ onBack, ticketsApiBase, onViewRelations, embedded }) {
  const [events, setEvents] = useState([]);
  const [filter, setFilter] = useState("unassigned");
  const [titlePattern, setTitlePattern] = useState("");
  const [caseSensitive, setCaseSensitive] = useState(false);
  const [loading, setLoading] = useState(true);
  const [importUrl, setImportUrl] = useState("");
  const [importing, setImporting] = useState(false);
  const [importResult, setImportResult] = useState(null);
  const [selectedEventIds, setSelectedEventIds] = useState(() => new Set());
  const [createdTickets, setCreatedTickets] = useState([]);
  const [error, setError] = useState(null);
  const [tickets, setTickets] = useState([]);
  const [selectedTicketId, setSelectedTicketId] = useState("");
  const [assigning, setAssigning] = useState(false);

  useEffect(() => {
    load();
    fetchOpenTickets(ticketsApiBase).then(setTickets);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ticketsApiBase, filter]);

  async function load() {
    setLoading(true);
    const fetchedEvents = await fetchCalendarEvents(ticketsApiBase, filter);
    setEvents(fetchedEvents);
    setLoading(false);

    // Statut automatique "à la consultation" (livraison #284, point 4
    // -- backend déjà prêt depuis #284 : determine_calendar_statut_label,
    // ensure_calendar_statuts, POST /tickets/<id>/recalculate_status,
    // jamais câblé côté interface jusqu'ici). "Consultation" retenue
    // ici = ouverture/rafraîchissement de CETTE vue -- choix parmi les
    // deux évoqués (vue Calendrier vs écran de Validation), le plus
    // naturel puisque c'est ici que les événements calendrier sont
    // effectivement regardés. Recalcule UNIQUEMENT les tickets déjà
    // liés à un événement (assigned_ticket_ids, déjà chargé avec les
    // événements -- jamais un appel par ticket ouvert au hasard).
    // Erreurs individuelles ignorées (best-effort, jamais bloquant --
    // un recalcul manqué n'empêche jamais d'afficher le reste).
    const linkedTicketIds = new Set();
    for (const e of fetchedEvents) {
      for (const tid of e.assigned_ticket_ids || []) linkedTicketIds.add(tid);
    }
    if (linkedTicketIds.size > 0) {
      await Promise.all(
        Array.from(linkedTicketIds).map((tid) => recalculateTicketStatus(ticketsApiBase, tid).catch(() => null))
      );
      fetchOpenTickets(ticketsApiBase).then(setTickets);
    }
  }

  async function handleImport(e) {
    e.preventDefault();
    if (!importUrl.trim()) return;
    setImporting(true);
    const result = await importFromUrl(ticketsApiBase, importUrl.trim());
    setImporting(false);
    setImportResult(result);
    if (!result.error) await load();
  }

  function toggleEvent(id) {
    setSelectedEventIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  async function handleAssign() {
    if (selectedEventIds.size === 0 || !selectedTicketId) return;
    setAssigning(true);
    await assignEventsToTickets(ticketsApiBase, Array.from(selectedEventIds), [Number(selectedTicketId)], "full");
    setAssigning(false);
    setSelectedEventIds(new Set());
    await load();
  }

  async function handleCreateTicket(eventId) {
    setAssigning(true);
    const result = await createTicketFromEvent(ticketsApiBase, eventId);
    setAssigning(false);
    if (!result.error) {
      // Liste de retour en arrière (livraison #284, demandé
      // explicitement) -- propre à cette session (perdue au
      // rechargement de la page, jamais persistée : un "undo"
      // n'a de sens que pendant la session où le geste a été fait).
      setCreatedTickets((prev) => [...prev, { ticketId: result.ticket_id, eventId, subject: events.find((e) => e.id === eventId)?.summary || `Ticket #${result.ticket_id}` }]);
    }
    await load();
  }

  async function handleUndoCreateTicket(ticketId) {
    setAssigning(true);
    const result = await deleteTicket(ticketsApiBase, ticketId);
    setAssigning(false);
    if (result.error) {
      setError(result.error);
      return;
    }
    setCreatedTickets((prev) => prev.filter((t) => t.ticketId !== ticketId));
    await load();
  }

  // Filtre par motif à joker -- appliqué CÔTÉ HUB sur les événements
  // déjà chargés (jamais un nouveau paramètre d'API) : volume typique
  // d'un agenda largement sous ce qui justifierait un filtrage côté
  // serveur, et un filtrage local donne un retour instantané pendant
  // la frappe, sans aller-retour réseau à chaque caractère.
  const filteredEvents = titlePattern.trim()
    ? events.filter((e) => wildcardToRegex(titlePattern.trim(), caseSensitive).test(e.summary || ""))
    : events;

  // "File d'attente" (livraison #284, renommée depuis "Tickets par
  // échéance" -- demandé explicitement : "fonctionne comme dans la
  // tuile tickets"). Réutilise directement `tickets` (déjà chargé
  // via /queue pour le sélecteur d'affectation) -- ce endpoint
  // renvoie déjà TOUTES les colonnes nécessaires (user_login,
  // type_label, level_label, statut_label, wait_seconds...) et un
  // tri déjà fait côté serveur (priorité puis temps d'attente,
  // voir tickets/api/app.py:technician_queue) -- jamais retrié ici.

  return (
    <div className="hub-settings hub-settings-wide">
      {!embedded && (
        <div className="hub-settings-topbar">
          <button className="secondary" onClick={onBack}>◀ Retour</button>
          <h1>📅 Calendrier</h1>
        </div>
      )}
      {error && <p className="hub-error">{error}</p>}

      <div className="hub-card hub-settings-section">
        <h2>Importer depuis une adresse secrète iCal</h2>
        <p className="muted" style={{ marginTop: -4 }}>
          Google Calendar → Paramètres de l'agenda → Adresse secrète au format iCal.
        </p>
        <form onSubmit={handleImport} style={{ display: "flex", gap: 8 }}>
          <input value={importUrl} onChange={(e) => setImportUrl(e.target.value)} placeholder="https://calendar.google.com/calendar/ical/…" style={{ flex: 1 }} disabled={importing} />
          <button type="submit" disabled={importing} style={importing ? { opacity: 0.6, cursor: "wait" } : undefined}>
            {importing ? "⏳ Import en cours…" : "Importer"}
          </button>
        </form>
        {importResult && (
          <div
            className="hub-card"
            style={{
              marginTop: 8,
              padding: "8px 12px",
              background: importResult.error ? "var(--danger-bg)" : "var(--hub-ok-bg, #eafaf1)",
              border: `1px solid ${importResult.error ? "var(--danger)" : "var(--hub-ok, #27ae60)"}`,
            }}
          >
            {importResult.error ? (
              <p style={{ margin: 0, color: "var(--danger)" }}>⚠️ {importResult.error}</p>
            ) : (
              <p style={{ margin: 0, color: "var(--hub-ok, #27ae60)", fontWeight: 500 }}>
                ✅ Import terminé — {importResult.imported} nouvel(le)(s) évènement(s), {importResult.already_known} déjà connu(s).
              </p>
            )}
          </div>
        )}
      </div>

      <div style={{ display: "flex", gap: 16, alignItems: "flex-start" }}>
      <div className="hub-card hub-settings-section" style={{ flex: "2 1 0", minWidth: 0 }}>
        <div style={{ display: "flex", gap: 8, alignItems: "flex-end", marginBottom: 12 }}>
          <div className="hub-settings-row" style={{ margin: 0 }}>
            <label>Filtre</label>
            <select value={filter} onChange={(e) => setFilter(e.target.value)}>
              <option value="unassigned">Non affectés</option>
              <option value="assigned">Affectés à un ticket</option>
              <option value="all">Tous</option>
            </select>
          </div>
          <div className="hub-settings-row" style={{ margin: 0 }}>
            <label>Motif sur le titre (ex. *SAV*DEV*)</label>
            <input value={titlePattern} onChange={(e) => setTitlePattern(e.target.value)} placeholder="*SAV*" style={{ width: 160 }} />
          </div>
          <label style={{ display: "flex", alignItems: "center", gap: 4, marginBottom: 4 }}>
            <input type="checkbox" checked={caseSensitive} onChange={(e) => setCaseSensitive(e.target.checked)} />
            Sensible à la casse
          </label>
        </div>

        {loading ? (
          <p className="muted">Chargement…</p>
        ) : filteredEvents.length === 0 ? (
          <p className="muted">{events.length === 0 ? "Aucun évènement pour ce filtre." : "Aucun évènement ne correspond au motif."}</p>
        ) : (
          <div style={{ maxHeight: 420, overflowY: "auto" }}>
            <table>
              <thead><tr><th></th><th>Date</th><th>Titre</th><th>Statut</th><th></th></tr></thead>
              <tbody>
                {filteredEvents.map((e) => (
                  <tr key={e.id}>
                    <td>
                      {filter === "unassigned" && (
                        <input type="checkbox" checked={selectedEventIds.has(e.id)} onChange={() => toggleEvent(e.id)} />
                      )}
                    </td>
                    <td className="muted">{formatDate(e.start_ts)}</td>
                    <td>{e.summary}</td>
                    <td className="muted">
                      {e.assigned_ticket_ids?.length > 0
                        ? `Ticket #${e.assigned_ticket_ids.join(", #")}`
                        : e.triggered ? (
                          <span title={(e.matched_keywords || []).join(", ")}>
                            🔶 {(() => {
                              const joined = (e.matched_keywords || []).join(", ");
                              return joined.length > 15 ? joined.slice(0, 15) + "…" : joined;
                            })()}
                          </span>
                        ) : "—"}
                    </td>
                    <td>
                      {filter === "unassigned" && (
                        <button className="secondary" disabled={assigning} onClick={() => handleCreateTicket(e.id)}>
                          + Créer un ticket
                        </button>
                      )}
                      {onViewRelations && (
                        <button className="secondary" title="Voir les relations" onClick={() => onViewRelations("calendar_event", e.id)}>🔗</button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {createdTickets.length > 0 && (
          <div className="hub-card" style={{ marginTop: 12, padding: "8px 12px" }}>
            <p className="muted" style={{ margin: "0 0 6px", fontSize: "0.9em" }}>
              Tickets créés durant cette session — retour en arrière possible tant qu'ils ne sont pas validés :
            </p>
            {createdTickets.map((t) => (
              <div key={t.ticketId} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "2px 0" }}>
                <span>#{t.ticketId} — {t.subject}</span>
                <button className="secondary" disabled={assigning} onClick={() => handleUndoCreateTicket(t.ticketId)}>↩ Annuler</button>
              </div>
            ))}
          </div>
        )}

        {filter === "unassigned" && (
          <div style={{ display: "flex", gap: 8, alignItems: "flex-end", marginTop: 12 }}>
            <div className="hub-settings-row" style={{ margin: 0 }}>
              <label>Affecter la sélection ({selectedEventIds.size}) au ticket</label>
              <select value={selectedTicketId} onChange={(e) => setSelectedTicketId(e.target.value)}>
                <option value="">— choisir —</option>
                {tickets.map((t) => <option key={t.id} value={t.id}>#{t.id} — {t.subject}</option>)}
              </select>
            </div>
            <button onClick={handleAssign} disabled={assigning || selectedEventIds.size === 0 || !selectedTicketId}>
              {assigning ? "Affectation…" : "Affecter"}
            </button>
          </div>
        )}
      </div>

      <div className="hub-card hub-settings-section" style={{ flex: "1 1 0", minWidth: 320 }}>
        <h2 style={{ marginTop: 0 }}>File d'attente</h2>
        <p className="muted" style={{ marginTop: -4, fontSize: "0.9em" }}>
          Mêmes colonnes que la tuile Tickets (ordre déjà trié côté serveur par priorité puis temps d'attente).
        </p>
        {tickets.length === 0 ? (
          <p className="muted">Aucun ticket ouvert.</p>
        ) : (
          <div style={{ maxHeight: 420, overflowY: "auto" }}>
            <table>
              <thead>
                <tr><th>#</th><th>Sujet</th><th>Demandeur</th><th>Type</th><th>Niveau</th><th>Statut</th><th>Attente</th>{onViewRelations && <th></th>}</tr>
              </thead>
              <tbody>
                {tickets.map((t) => (
                  <tr key={t.id}>
                    <td className="muted">{t.id}</td>
                    <td>{t.subject}</td>
                    <td className="muted">{t.user_login || "—"}</td>
                    <td className="muted">{t.type_label || "—"}</td>
                    <td className="muted">{t.level_label || "—"}</td>
                    <td className="muted">{t.statut_label || "—"}</td>
                    <td className="muted">
                      {t.ts_closed ? "🔒 fermé" : `⏳ ${formatWaitDuration(t.wait_seconds)}`}
                    </td>
                    {onViewRelations && (
                      <td>
                        <button className="secondary" title="Voir les relations" onClick={() => onViewRelations("ticket", t.id)}>🔗</button>
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
      </div>
    </div>
  );
}
