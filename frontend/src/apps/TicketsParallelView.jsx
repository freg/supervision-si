import { useEffect, useState } from "react";
import { fetchParallelTickets } from "./ticketsApi.js";

const GROUP_LABELS = {
  ticket: "Par ticket",
  user: "Par demandeur",
  type: "Par type",
  level: "Par niveau",
};

export default function TicketsParallelView({ onClose }) {
  const [tickets, setTickets] = useState([]);
  const [loading, setLoading] = useState(true);
  const [groupBy, setGroupBy] = useState("ticket");

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    fetchParallelTickets(null, groupBy).then((t) => {
      if (!cancelled) {
        setTickets(t.filter((tk) => tk.time_entries.length > 0));
        setLoading(false);
      }
    });
    return () => {
      cancelled = true;
    };
  }, [groupBy]);

  const allEntries = tickets.flatMap((t) => t.time_entries);
  // Math.min(...tableau) / Math.max(...tableau) plantent silencieusement
  // ("Maximum call stack size exceeded") sur de grands tableaux — piège
  // JS connu, confirmé en test. reduce() n'a pas cette limite.
  const minTs = allEntries.length ? allEntries.reduce((min, e) => Math.min(min, e.start_ts), Infinity) : 0;
  const maxTs = allEntries.length ? allEntries.reduce((max, e) => Math.max(max, e.end_ts), -Infinity) : 1;
  const span = Math.max(maxTs - minTs, 1);
  const markerTimes = [...new Set(allEntries.map((e) => e.start_ts))].sort((a, b) => a - b);

  function pct(ts) {
    return ((ts - minTs) / span) * 100;
  }

  return (
    <div className="pixel-grid-app">
      <div className="pixel-grid-toolbar">
        <div className="timeline-header">
          <div className="timeline-title">📊 Tickets parallèles</div>
          <button className="calendar-nav-btn" onClick={onClose}>← Retour</button>
        </div>
        <div className="pixel-grid-controls">
          <span className="pixel-grid-controls-label">Vision :</span>
          {Object.entries(GROUP_LABELS).map(([key, label]) => (
            <button
              key={key}
              className={`pixel-grid-level-btn ${groupBy === key ? "active" : ""}`}
              onClick={() => setGroupBy(key)}
            >
              {label}
            </button>
          ))}
        </div>
        <p className="pixel-grid-empty-hint">
          Axe temporel partagé — {groupBy === "ticket"
            ? "une ligne par ticket ouvert"
            : `une ligne par ${GROUP_LABELS[groupBy].toLowerCase().replace("par ", "")}, tous ses tickets combinés`}
          , marqueurs verticaux sur chaque entrée calendrier distincte.
        </p>
      </div>

      {loading && <p className="synthesis-empty">Chargement…</p>}

      {!loading && allEntries.length === 0 && (
        <p className="synthesis-empty">Aucun segment de temps enregistré pour cette vision.</p>
      )}

      {!loading && allEntries.length > 0 && (
        <div className="parallel-gantt-wrapper">
          <div className="parallel-gantt-markers">
            {markerTimes.map((ts, i) => (
              <div key={i} className="parallel-gantt-marker" style={{ left: `${pct(ts)}%` }}>
                <span className="parallel-gantt-marker-label">
                  {new Date(ts * 1000).toLocaleString(undefined, { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" })}
                </span>
              </div>
            ))}
          </div>

          {tickets.map((t) => (
            <div key={t.id} className="parallel-gantt-row">
              <div className="parallel-gantt-row-label" title={t.ticket_ids ? `Tickets #${t.ticket_ids.join(", #")}` : t.subject}>
                {groupBy === "ticket" ? `#${t.id} ${t.subject}` : `${t.subject} (${t.ticket_ids.length} ticket${t.ticket_ids.length > 1 ? "s" : ""})`}
              </div>
              <div className="parallel-gantt-row-track">
                {markerTimes.map((ts, i) => (
                  <div key={i} className="parallel-gantt-gridline" style={{ left: `${pct(ts)}%` }} />
                ))}
                {t.time_entries.map((e, i) => (
                  <div
                    key={i}
                    className="timeline-bar-segment"
                    style={{
                      left: `${pct(e.start_ts)}%`,
                      width: `${Math.max(pct(e.end_ts) - pct(e.start_ts), 0.4)}%`,
                      opacity: e.weight < 1 ? 0.55 : 1,
                    }}
                    title={`${new Date(e.start_ts * 1000).toLocaleString()} → ${new Date(e.end_ts * 1000).toLocaleString()}${e.weight < 1 ? ` (poids ${e.weight})` : ""}`}
                  />
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
