import { useEffect, useState } from "react";
import { fetchQueue, fetchStatuts, updateTicket } from "./ticketsApi.js";

const UNASSIGNED_KEY = "unassigned";

function ReprisesBadges({ t }) {
  if (!t.segment_count && !t.reopen_count && !t.similar_tickets_count) return null;
  return (
    <div style={{ display: "flex", gap: "0.2rem", marginTop: "0.3rem", flexWrap: "wrap" }}>
      {t.segment_count > 1 && (
        <span className="pixel-grid-level-btn" style={{ fontSize: "0.6rem" }} title={`${t.segment_count} plages horaires`}>
          ⏱️ {t.segment_count}
        </span>
      )}
      {t.reopen_count > 0 && (
        <span className="pixel-grid-level-btn" style={{ fontSize: "0.6rem" }} title={`Rouvert ${t.reopen_count} fois`}>
          🔁 {t.reopen_count}
        </span>
      )}
      {t.similar_tickets_count > 0 && (
        <span className="pixel-grid-level-btn" style={{ fontSize: "0.6rem" }} title={`${t.similar_tickets_count} ticket(s) au sujet proche`}>
          ♻️ {t.similar_tickets_count}
        </span>
      )}
    </div>
  );
}

function KanbanCard({ t, statuts, onSelect, onMoved }) {
  async function handleMove(e) {
    e.stopPropagation();
    const newStatutId = e.target.value || null;
    await updateTicket(t.id, { statut_id: newStatutId });
    onMoved();
  }

  return (
    <div className="timeline-incident-card" style={{ cursor: "pointer" }} onClick={() => onSelect(t.id)}>
      <div className="timeline-incident-header">
        <span className={`status-dot ${t.level_rank >= 3 ? "unavailable" : t.level_rank >= 2 ? "" : "ok"}`} />
        <span style={{ fontSize: "0.72rem" }}>{t.level_label || "—"}</span>
      </div>
      <div style={{ fontSize: "0.8rem", marginBottom: "0.2rem" }}>#{t.id} — {t.subject}</div>
      <div className="pixel-grid-empty-hint">
        {t.type_label || "—"} · {t.user_login || "—"}
      </div>
      <ReprisesBadges t={t} />
      <select
        className="geo-input"
        style={{ marginTop: "0.4rem", width: "100%", fontSize: "0.68rem" }}
        value={t.statut_id || ""}
        onClick={(e) => e.stopPropagation()}
        onChange={handleMove}
      >
        <option value="">Non classé</option>
        {statuts.map((s) => <option key={s.id} value={s.id}>{s.label}</option>)}
      </select>
    </div>
  );
}

export default function KanbanBoardView({ onClose, onSelectTicket }) {
  const [tickets, setTickets] = useState([]);
  const [statuts, setStatuts] = useState([]);
  const [loading, setLoading] = useState(true);

  async function reload() {
    setLoading(true);
    const [t, s] = await Promise.all([fetchQueue({ all: true }), fetchStatuts()]);
    setTickets(t);
    setStatuts(s);
    setLoading(false);
  }

  useEffect(() => {
    reload();
  }, []);

  if (loading) return <p className="synthesis-empty">Chargement…</p>;

  const columns = [
    { key: UNASSIGNED_KEY, label: "Non classé", tickets: tickets.filter((t) => !t.statut_id) },
    ...statuts.map((s) => ({ key: s.id, label: s.label, tickets: tickets.filter((t) => t.statut_id === s.id) })),
  ];

  return (
    <div className="pixel-grid-app">
      <div className="pixel-grid-toolbar">
        <div className="timeline-header">
          <div className="timeline-title">🗂️ Tableau Kanban</div>
          <button className="calendar-nav-btn" onClick={onClose}>← Retour</button>
        </div>
        <p className="pixel-grid-empty-hint">
          Vision alternative à la liste triable — une colonne par statut,
          déplace un ticket via le sélecteur en bas de sa carte.
        </p>
      </div>

      <div style={{ display: "flex", gap: "0.75rem", overflowX: "auto", paddingBottom: "1rem" }}>
        {columns.map((col) => (
          <div key={col.key} style={{ minWidth: 260, flexShrink: 0 }}>
            <div className="timeline-title" style={{ fontSize: "0.8rem", marginBottom: "0.4rem" }}>
              {col.label} <span className="pixel-grid-empty-hint">({col.tickets.length})</span>
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: "0.4rem", maxHeight: "70vh", overflowY: "auto" }}>
              {col.tickets.map((t) => (
                <KanbanCard key={t.id} t={t} statuts={statuts} onSelect={onSelectTicket} onMoved={reload} />
              ))}
              {col.tickets.length === 0 && <p className="pixel-grid-empty-hint">—</p>}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
