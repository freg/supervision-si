import React, { useEffect, useState } from "react";
import { getJson, putJson } from "../api.js";
import {
  fmtDuration, fmtTs, fmtTsShort,
  ganttBounds, segmentGeometry, filterGanttRows,
} from "../lib.js";
import TicketThread from "../components/TicketThread.jsx";
import TicketDocuments from "../components/TicketDocuments.jsx";

// Vue POLITIQUE : synthèse chiffrée, Gantt filtrable (par ticket /
// demandeur / type / niveau — réutilise /tickets/parallel), gestion
// des priorités (niveau), clôture/réouverture des demandes, et vue
// des réouvertures (quels tickets reviennent, combien de fois).
export default function PolitiqueView({ me }) {
  const [summary, setSummary] = useState(null);
  const [ganttRows, setGanttRows] = useState([]);
  const [groupBy, setGroupBy] = useState("ticket");
  const [ganttFilter, setGanttFilter] = useState("");
  const [tickets, setTickets] = useState([]);
  const [levels, setLevels] = useState([]);
  const [stateFilter, setStateFilter] = useState("open");
  const [selectedId, setSelectedId] = useState(null);
  const [hasLoadedOnce, setHasLoadedOnce] = useState(false);

  const [reopenings, setReopenings] = useState([]);
  const [reopeningsLoaded, setReopeningsLoaded] = useState(false);
  const [showReopenings, setShowReopenings] = useState(false);

  const loadSummary = async () => {
    const res = await getJson("/stats/summary");
    if (res.ok) setSummary(res.data);
  };

  const loadGantt = async () => {
    const res = await getJson(`/tickets/parallel?group_by=${groupBy}`);
    if (res.ok) setGanttRows(res.data.tickets);
  };

  const loadTickets = async () => {
    const res = await getJson(`/queue?state=${stateFilter}`);
    if (res.ok) setTickets(res.data.tickets);
    setHasLoadedOnce(true);
  };

  const loadReopenings = async () => {
    const res = await getJson("/stats/reopenings");
    if (res.ok) setReopenings(res.data.tickets);
    setReopeningsLoaded(true);
  };

  useEffect(() => {
    loadSummary();
    loadReopenings();
    getJson("/levels").then((r) => r.ok && setLevels(r.data));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  useEffect(() => { loadGantt(); /* eslint-disable-line react-hooks/exhaustive-deps */ }, [groupBy]);
  useEffect(() => { loadTickets(); /* eslint-disable-line react-hooks/exhaustive-deps */ }, [stateFilter]);

  const setPriority = async (ticketId, levelId) => {
    const res = await putJson(`/tickets/${ticketId}`, {
      level_id: levelId === "" ? null : Number(levelId),
    });
    if (res.ok) { await loadTickets(); await loadSummary(); }
  };

  const closeTicket = async (t) => {
    if (!window.confirm(`Clore la demande #${t.id} — « ${t.subject} » ?`)) return;
    const res = await putJson(`/tickets/${t.id}`, { ts_closed: Math.round(Date.now() / 1000) });
    if (res.ok) { await loadTickets(); await loadSummary(); await loadGantt(); }
  };

  const reopenTicket = async (t) => {
    if (!window.confirm(`Rouvrir la demande #${t.id} — « ${t.subject} » ?`)) return;
    const res = await putJson(`/tickets/${t.id}`, { ts_closed: null });
    if (res.ok) { await loadTickets(); await loadSummary(); await loadGantt(); await loadReopenings(); }
  };

  const filteredRows = filterGanttRows(ganttRows, ganttFilter);
  const bounds = ganttBounds(filteredRows);

  return (
    <div>
      <div className="panel">
        <h2>🧭 Synthèse</h2>
        {!summary && <p className="muted">Chargement…</p>}
        {summary && (
          <>
            <div className="stat-cards">
              <div className="stat-card">
                <div className="value">{summary.open}</div>
                <div className="label">demandes ouvertes</div>
              </div>
              <div className="stat-card">
                <div className="value">{summary.closed}</div>
                <div className="label">demandes closes</div>
              </div>
              <div className="stat-card">
                <div className="value">{fmtDuration(summary.total_seconds)}</div>
                <div className="label">temps total passé</div>
              </div>
              <div className="stat-card clickable" onClick={() => setShowReopenings(true)}>
                <div className="value">{reopeningsLoaded ? reopenings.length : "…"}</div>
                <div className="label">demandes déjà rouvertes</div>
              </div>
            </div>
            <div className="form-row">
              <label>Par statut :</label>
              {summary.by_statut.map((s) => (
                <span key={s.label} className="badge">{s.label} : {s.value}</span>
              ))}
            </div>
            <div className="form-row">
              <label>Ouvertes par niveau :</label>
              {summary.open_by_level.map((l) => (
                <span key={l.label} className="badge level">{l.label} : {l.value}</span>
              ))}
            </div>
          </>
        )}
      </div>

      <div className="panel">
        <div className="panel-header-row">
          <h2>🔁 Réouvertures</h2>
          <button onClick={() => setShowReopenings((v) => !v)}>
            {showReopenings ? "Masquer" : "Afficher"}
          </button>
        </div>
        {showReopenings && (
          <>
            <p className="hint">
              Demandes déjà rouvertes au moins une fois après clôture — signal qu'une
              résolution n'a pas tenu, à distinguer d'une récidive (nouveau ticket similaire).
            </p>
            {!reopeningsLoaded && <p className="muted">Chargement…</p>}
            {reopeningsLoaded && reopenings.length === 0 && (
              <p className="muted">Aucune demande rouverte pour l'instant.</p>
            )}
            {reopenings.length > 0 && (
              <table className="portal-table">
                <thead>
                  <tr>
                    <th>#</th><th>Sujet</th><th>Demandeur</th>
                    <th>Réouvertures</th><th>Dernière réouverture</th><th>État actuel</th>
                  </tr>
                </thead>
                <tbody>
                  {reopenings.map((t) => (
                    <tr key={t.id} onClick={() => setSelectedId(t.id)} style={{ cursor: "pointer" }}>
                      <td>{t.id}</td>
                      <td>{t.subject}</td>
                      <td>{t.user_login || "—"}</td>
                      <td><span className="badge">{t.reopen_count}×</span></td>
                      <td>{fmtTs(t.last_reopened_ts)}</td>
                      <td>
                        {t.archived_at ? (
                          <span className="badge">📦 archivée</span>
                        ) : t.ts_closed ? (
                          <span className="badge closed">Fermée</span>
                        ) : (
                          <span className="badge open">Ouverte</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </>
        )}
      </div>

      <div className="panel">
        <h2>📊 Gantt — tickets ouverts</h2>
        <div className="filters-bar">
          <select value={groupBy} onChange={(e) => setGroupBy(e.target.value)}>
            <option value="ticket">Par ticket</option>
            <option value="user">Par demandeur</option>
            <option value="type">Par type</option>
            <option value="level">Par niveau</option>
          </select>
          <input
            placeholder="Filtrer les lignes…"
            value={ganttFilter}
            onChange={(e) => setGanttFilter(e.target.value)}
          />
        </div>
        {bounds && (
          <div className="gantt-scale">
            <span>{fmtTs(bounds.min)}</span>
            <span>{fmtTs(bounds.max)}</span>
          </div>
        )}
        {filteredRows.length === 0 && <p className="muted">Aucune ligne à afficher.</p>}
        {filteredRows.map((row) => (
          <div key={row.id} className="gantt-row">
            <div className="gantt-label" title={row.subject}>
              {groupBy === "ticket" ? `#${row.id} — ${row.subject}` : row.subject}
              {row.ticket_ids && <span className="muted"> ({row.ticket_ids.length})</span>}
            </div>
            <div className="gantt-track">
              {bounds && row.time_entries.map((e, i) => {
                const g = segmentGeometry(e, bounds);
                return (
                  <div
                    key={i}
                    className="gantt-seg"
                    style={{ left: `${g.left}%`, width: `${g.width}%` }}
                    title={`${fmtTs(e.start_ts)} → ${fmtTs(e.end_ts)}`}
                  />
                );
              })}
              {row.time_entries.length === 0 && (
                <span className="gantt-empty" style={{ paddingLeft: 6 }}>aucun temps saisi</span>
              )}
            </div>
          </div>
        ))}
      </div>

      <div className="panel">
        <h2>🎚️ Demandes — priorités et clôture</h2>
        <div className="filters-bar">
          <select value={stateFilter} onChange={(e) => setStateFilter(e.target.value)}>
            <option value="open">Ouvertes</option>
            <option value="closed">Closes</option>
            <option value="all">Toutes</option>
          </select>
        </div>
        {!hasLoadedOnce && <p className="muted">Chargement…</p>}
        {hasLoadedOnce && tickets.length === 0 && <p className="muted">Rien dans cette vue.</p>}
        {tickets.length > 0 && (
          <table className="portal-table">
            <thead>
              <tr>
                <th>#</th><th>Sujet</th><th>Demandeur</th><th>Statut</th>
                <th>Priorité (niveau)</th><th>Créée</th><th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {tickets.map((t) => (
                <tr
                  key={t.id}
                  className={t.id === selectedId ? "selected" : ""}
                  onClick={() => setSelectedId(t.id === selectedId ? null : t.id)}
                >
                  <td>{t.id}</td>
                  <td>
                    {t.subject}{t.parent_ticket_id && <span className="muted"> ↳ #{t.parent_ticket_id}</span>}
                    {t.reopen_count > 0 && <span className="badge" title="réouvertures"> 🔁 {t.reopen_count}</span>}
                  </td>
                  <td>{t.user_login || "—"}</td>
                  <td>{t.statut_label || "—"}</td>
                  <td onClick={(e) => e.stopPropagation()}>
                    <select
                      value={t.level_id ?? ""}
                      onChange={(e) => setPriority(t.id, e.target.value)}
                    >
                      <option value="">(aucun)</option>
                      {levels.map((l) => <option key={l.id} value={l.id}>{l.label}</option>)}
                    </select>
                  </td>
                  <td>{fmtTsShort(t.ts_created)}</td>
                  <td onClick={(e) => e.stopPropagation()}>
                    {t.ts_closed ? (
                      <button onClick={() => reopenTicket(t)}>🔓 Rouvrir</button>
                    ) : (
                      <button className="danger" onClick={() => closeTicket(t)}>🔒 Clore</button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {selectedId && (
          <div style={{ marginTop: 12 }}>
            <TicketThread ticketId={selectedId} me={me} />
            <TicketDocuments ticketId={selectedId} me={me} />
          </div>
        )}
      </div>
    </div>
  );
}
