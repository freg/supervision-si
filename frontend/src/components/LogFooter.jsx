import { useEffect, useState } from "react";
import { fetchAllLogs } from "../apps/logsApi.js";
import { mergeLogEntries, pickPriorityEntries, countByLevel, fmtLogTimestamp } from "../apps/logsLib.js";

const POLL_INTERVAL_MS = 15000;
const COLLAPSED_LINE_COUNT = 2;
const EXPANDED_MAX_ROWS = 30;

export default function LogFooter({ onOpenLogs }) {
  const [entries, setEntries] = useState([]);
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    let cancelled = false;

    async function poll() {
      const results = await fetchAllLogs(50);
      if (cancelled) return;
      setEntries(mergeLogEntries(results));
    }

    poll();
    const interval = setInterval(poll, POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  const counts = countByLevel(entries);
  const errorCount = counts.CRITICAL + counts.ERROR;
  const collapsedEntries = pickPriorityEntries(entries, COLLAPSED_LINE_COUNT);
  const expandedEntries = entries.slice(0, EXPANDED_MAX_ROWS);

  return (
    <div className={`log-footer${expanded ? " expanded" : ""}${errorCount > 0 ? " has-errors" : ""}`}>
      <button className="log-footer-bar" onClick={() => setExpanded((v) => !v)}>
        <span className="log-footer-toggle">{expanded ? "▼" : "▲"}</span>
        <div className="log-footer-lines">
          {collapsedEntries.length === 0 && (
            <div className="log-footer-line log-footer-empty">Aucun log récent.</div>
          )}
          {collapsedEntries.map((e, i) => (
            <div key={i} className={`log-footer-line log-level-${(e.level || "").toLowerCase()}`}>
              <span className="log-footer-time">{fmtLogTimestamp(e.timestamp)}</span>
              <span className="log-footer-service">{e.service}</span>
              <span className="log-footer-message">{e.message}</span>
            </div>
          ))}
        </div>
        {errorCount > 0 && <span className="log-footer-badge">{errorCount}</span>}
      </button>

      {expanded && (
        <div className="log-footer-panel">
          <div className="log-footer-panel-header">
            <span>
              {entries.length} entrée{entries.length > 1 ? "s" : ""} récente{entries.length > 1 ? "s" : ""}
              {entries.length > EXPANDED_MAX_ROWS && ` (${EXPANDED_MAX_ROWS} affichées)`}
            </span>
            <button className="log-footer-viewall" onClick={onOpenLogs}>
              Voir tout dans l'onglet Logs →
            </button>
          </div>
          <div className="log-footer-panel-list">
            {expandedEntries.length === 0 && (
              <p className="log-footer-panel-empty">Aucun log récent sur les services joignables.</p>
            )}
            {expandedEntries.map((e, i) => (
              <div key={i} className={`log-footer-panel-row log-level-${(e.level || "").toLowerCase()}`}>
                <span className="log-footer-time">{fmtLogTimestamp(e.timestamp)}</span>
                <span className="log-footer-service">{e.service}</span>
                <span className="log-footer-level">{e.level}</span>
                <span className="log-footer-message">{e.message}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
