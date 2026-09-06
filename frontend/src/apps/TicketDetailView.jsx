import { useEffect, useState } from "react";
import { fetchTicket, addTimeEntry } from "./ticketsApi.js";

function formatDuration(seconds) {
  if (seconds < 60) return `${seconds}s`;
  if (seconds < 3600) return `${Math.round(seconds / 60)}min`;
  return `${(seconds / 3600).toFixed(1)}h`;
}

function formatDateTimeLocal(ts) {
  const d = new Date(ts * 1000);
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

/**
 * Gantt "riche" : plusieurs segments par ticket (pas juste début/fin),
 * chacun positionné proportionnellement dans la plage totale d'activité
 * du ticket — même principe visuel que la timeline équipement du
 * module pixel-grid.
 */
function TicketGantt({ entries }) {
  if (entries.length === 0) {
    return <p className="synthesis-empty">Aucun segment de temps enregistré pour l'instant.</p>;
  }

  const minTs = entries.reduce((m, e) => Math.min(m, e.start_ts), Infinity);
  const maxTs = entries.reduce((m, e) => Math.max(m, e.end_ts), -Infinity);
  const span = Math.max(maxTs - minTs, 1);

  return (
    <div className="timeline-bar-track">
      {entries.map((e, i) => {
        const startPct = ((e.start_ts - minTs) / span) * 100;
        const widthPct = Math.max(((e.end_ts - e.start_ts) / span) * 100, 0.5);
        return (
          <div
            key={i}
            className="timeline-bar-segment"
            style={{ left: `${startPct}%`, width: `${widthPct}%` }}
            title={`${new Date(e.start_ts * 1000).toLocaleString()} → ${new Date(e.end_ts * 1000).toLocaleString()} (${formatDuration(e.end_ts - e.start_ts)})`}
          />
        );
      })}
    </div>
  );
}

export default function TicketDetailView({ ticketId, onClose }) {
  const [ticket, setTicket] = useState(null);
  const [loading, setLoading] = useState(true);
  const [newStart, setNewStart] = useState("");
  const [newEnd, setNewEnd] = useState("");
  const [saving, setSaving] = useState(false);

  async function reload() {
    setLoading(true);
    const data = await fetchTicket(ticketId);
    setTicket(data);
    setLoading(false);
  }

  useEffect(() => {
    reload();
  }, [ticketId]);

  async function handleAddEntry() {
    if (!newStart || !newEnd) return;
    setSaving(true);
    const startTs = Math.floor(new Date(newStart).getTime() / 1000);
    const endTs = Math.floor(new Date(newEnd).getTime() / 1000);
    const result = await addTimeEntry(ticketId, startTs, endTs);
    setSaving(false);
    if (result.ok) {
      setNewStart("");
      setNewEnd("");
      reload();
    }
  }

  if (loading) return <p className="synthesis-empty">Chargement…</p>;
  if (!ticket || ticket.error) return <p className="pixel-grid-error">Ticket introuvable.</p>;

  return (
    <div className="pixel-grid-app">
      <div className="pixel-grid-toolbar">
        <div className="timeline-header">
          <div>
            <div className="timeline-title">🎫 #{ticket.id} — {ticket.subject}</div>
            <div className="pixel-grid-empty-hint">
              créé le {new Date(ticket.ts_created * 1000).toLocaleString()}
              {ticket.ts_closed && ` · fermé le ${new Date(ticket.ts_closed * 1000).toLocaleString()}`}
            </div>
          </div>
          <button className="calendar-nav-btn" onClick={onClose}>← Retour à la file</button>
        </div>
      </div>

      <div className="pixel-grid-body">
        <div className="pixel-grid-main">
          <div className="timeline-summary">
            Temps total enregistré : <strong>{formatDuration(ticket.total_seconds)}</strong>
            {" · "}{ticket.time_entries.length} segment(s)
            {ticket.source_type && ` · généré depuis un incident (${ticket.source_type} / ${ticket.source_nom})`}
          </div>

          <TicketGantt entries={ticket.time_entries} />

          {ticket.description && (
            <div className="pixel-grid-detail-event-data" style={{ marginTop: "0.75rem" }}>
              <div className="synthesis-field-row">
                <span className="synthesis-field-label">description</span>
                <span>{ticket.description}</span>
              </div>
            </div>
          )}

          <div className="timeline-incident-list" style={{ marginTop: "1rem" }}>
            {[...ticket.time_entries].reverse().map((e) => (
              <div key={e.id} className="timeline-incident-card">
                <div className="timeline-incident-times">
                  {new Date(e.start_ts * 1000).toLocaleString()} → {new Date(e.end_ts * 1000).toLocaleString()}
                  {" — "}{formatDuration(e.end_ts - e.start_ts)}
                  {e.calendar_event_id ? " (depuis calendrier)" : " (saisie manuelle)"}
                </div>
              </div>
            ))}
          </div>

          <div className="pixel-grid-toolbar" style={{ marginTop: "1rem" }}>
            <div className="pixel-grid-controls">
              <span className="pixel-grid-controls-label">Ajouter un segment manuel :</span>
              <input type="datetime-local" className="geo-input" value={newStart} onChange={(e) => setNewStart(e.target.value)} />
              <span className="pixel-grid-controls-label">→</span>
              <input type="datetime-local" className="geo-input" value={newEnd} onChange={(e) => setNewEnd(e.target.value)} />
              <button className="pixel-grid-reset-btn" onClick={handleAddEntry} disabled={saving || !newStart || !newEnd}>
                {saving ? "…" : "➕ Ajouter"}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
