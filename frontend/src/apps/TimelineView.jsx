import { useEffect, useState } from "react";
import { fetchTimeline } from "./pixelGridApi.js";

function formatDuration(seconds) {
  if (seconds === null || seconds === undefined) return "en cours";
  if (seconds < 60) return `${seconds}s`;
  if (seconds < 3600) return `${Math.round(seconds / 60)}min`;
  if (seconds < 86400) return `${(seconds / 3600).toFixed(1)}h`;
  return `${(seconds / 86400).toFixed(1)}j`;
}

/**
 * Barre horizontale proportionnelle — chaque incident occupe une
 * largeur proportionnelle à sa position/durée dans la plage totale.
 * Volontairement simple (divs positionnés en %), pas de librairie de
 * graphique supplémentaire.
 */
function IncidentBar({ incidents, minTs, maxTs }) {
  const span = Math.max(maxTs - minTs, 1);

  return (
    <div className="timeline-bar-track">
      {incidents.map((inc, i) => {
        const startPct = ((inc.start_ts - minTs) / span) * 100;
        const endTs = inc.ongoing ? maxTs : inc.end_ts;
        const widthPct = Math.max(((endTs - inc.start_ts) / span) * 100, 0.4);
        return (
          <div
            key={i}
            className={`timeline-bar-segment ${inc.ongoing ? "timeline-bar-ongoing" : ""}`}
            style={{ left: `${startPct}%`, width: `${widthPct}%` }}
            title={`${inc.start_iso} → ${inc.ongoing ? "en cours" : inc.end_iso} (${formatDuration(inc.duration_seconds)})`}
          />
        );
      })}
    </div>
  );
}

export default function TimelineView({ type, nom, onClose }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    fetchTimeline(type, nom).then((result) => {
      if (!cancelled) {
        setData(result);
        setLoading(false);
      }
    });
    return () => {
      cancelled = true;
    };
  }, [type, nom]);

  return (
    <div className="pixel-grid-app">
      <div className="pixel-grid-toolbar">
        <div className="timeline-header">
          <div>
            <div className="timeline-title">📈 Timeline — {nom}</div>
            <div className="pixel-grid-empty-hint">type : {type}</div>
          </div>
          <button className="calendar-nav-btn" onClick={onClose}>
            ← Retour à la mosaïque
          </button>
        </div>
      </div>

      {loading && <p className="synthesis-empty">Chargement…</p>}

      {!loading && !data && <p className="pixel-grid-error">Impossible de charger la timeline.</p>}

      {!loading && data && data.kind === "integer_enum" && (
        <TimelineIncidents events={data.events} incidents={data.incidents} />
      )}

      {!loading && data && data.kind === "continuous" && (
        <TimelineSeries events={data.events} />
      )}
    </div>
  );
}

function TimelineIncidents({ events, incidents }) {
  if (events.length === 0) {
    return <p className="synthesis-empty">Aucun événement pour cet équipement.</p>;
  }

  const minTs = events.reduce((m, e) => Math.min(m, e.ts), Infinity);
  const maxTs = events.reduce((m, e) => Math.max(m, e.ts), -Infinity);

  return (
    <div className="pixel-grid-body">
      <div className="pixel-grid-main">
        <div className="timeline-summary">
          {incidents.length} incident(s) appariés (début/fin) sur {events.length} événement(s) bruts —
          plage : {new Date(minTs * 1000).toISOString()} → {new Date(maxTs * 1000).toISOString()}
        </div>

        {incidents.length > 0 && <IncidentBar incidents={incidents} minTs={minTs} maxTs={maxTs} />}

        <div className="timeline-incident-list">
          {[...incidents].reverse().map((inc, i) => (
            <div key={i} className={`timeline-incident-card ${inc.ongoing ? "timeline-incident-ongoing" : ""}`}>
              <div className="timeline-incident-header">
                <span className={`status-dot ${inc.ongoing ? "unavailable" : "ok"}`} />
                <span className="timeline-incident-duration">{formatDuration(inc.duration_seconds)}</span>
                {inc.ongoing && <span className="timeline-ongoing-badge">EN COURS</span>}
              </div>
              <div className="timeline-incident-times">
                {inc.start_iso} → {inc.ongoing ? "…" : inc.end_iso}
              </div>
              {inc.data && (
                <div className="timeline-incident-data">
                  {Object.entries(inc.data).map(([k, v]) => (
                    <div key={k} className="synthesis-field-row">
                      <span className="synthesis-field-label">{k}</span>
                      <span>{String(v)}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}
          {incidents.length === 0 && (
            <p className="synthesis-empty">
              Aucun couple début/fin détecté (que des événements valeur=-1, ou aucune résolution trouvée).
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

function TimelineSeries({ events }) {
  if (events.length === 0) {
    return <p className="synthesis-empty">Aucun événement pour cet équipement.</p>;
  }

  const minVal = events.reduce((m, e) => Math.min(m, e.valeur), Infinity);
  const maxVal = events.reduce((m, e) => Math.max(m, e.valeur), -Infinity);
  const valSpan = Math.max(maxVal - minVal, 0.0001);
  const width = 100 / events.length;

  return (
    <div className="pixel-grid-body">
      <div className="pixel-grid-main">
        <div className="timeline-summary">
          {events.length} point(s) — min {minVal.toFixed(1)}, max {maxVal.toFixed(1)}
        </div>

        <div className="timeline-series-chart">
          {events.map((e, i) => {
            const heightPct = ((e.valeur - minVal) / valSpan) * 100;
            return (
              <div
                key={i}
                className="timeline-series-bar"
                style={{ left: `${i * width}%`, width: `${width}%`, height: `${heightPct}%` }}
                title={`${e.iso} : ${e.valeur}`}
              />
            );
          })}
        </div>
      </div>
    </div>
  );
}
