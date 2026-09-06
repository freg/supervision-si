import { useEffect, useMemo, useState } from "react";
import { fetchAllLogs, KNOWN_SERVICE_NAMES } from "./logsApi.js";
import { mergeLogEntries, fmtLogTimestamp } from "./logsLib.js";

const POLL_INTERVAL_MS = 15000;
const LEVELS = ["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"];

export default function LogsApp() {
  const [rawResults, setRawResults] = useState([]);
  const [loading, setLoading] = useState(true);
  const [serviceFilter, setServiceFilter] = useState("all");
  const [levelFilter, setLevelFilter] = useState("all");
  const [paused, setPaused] = useState(false);
  const [lastFetch, setLastFetch] = useState(null);

  useEffect(() => {
    if (paused) return;
    let cancelled = false;

    async function poll() {
      const results = await fetchAllLogs(200);
      if (cancelled) return;
      setRawResults(results);
      setLoading(false);
      setLastFetch(new Date());
    }

    poll();
    const interval = setInterval(poll, POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [paused]);

  const entries = useMemo(() => mergeLogEntries(rawResults), [rawResults]);
  const filtered = useMemo(() => {
    return entries.filter((e) => {
      if (serviceFilter !== "all" && e.service !== serviceFilter) return false;
      if (levelFilter !== "all" && e.level !== levelFilter) return false;
      return true;
    });
  }, [entries, serviceFilter, levelFilter]);

  const unreachable = rawResults.filter((r) => r.error);

  return (
    <div className="logs-app">
      <header className="logs-header">
        <strong>Logs</strong>
        <span className="logs-subtitle">
          — {KNOWN_SERVICE_NAMES.length} services, tampon en mémoire par service (jamais persisté)
        </span>
      </header>

      <div className="logs-toolbar">
        <select className="logs-select" value={serviceFilter} onChange={(e) => setServiceFilter(e.target.value)}>
          <option value="all">Tous les services</option>
          {KNOWN_SERVICE_NAMES.map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
        <select className="logs-select" value={levelFilter} onChange={(e) => setLevelFilter(e.target.value)}>
          <option value="all">Tous les niveaux</option>
          {LEVELS.map((l) => (
            <option key={l} value={l}>{l}</option>
          ))}
        </select>
        <button className="calendar-nav-btn" onClick={() => setPaused((v) => !v)}>
          {paused ? "▶ Reprendre" : "⏸ Pause"}
        </button>
        <span className="logs-count">
          {filtered.length} / {entries.length} entrée{entries.length > 1 ? "s" : ""}
        </span>
        {lastFetch && !paused && (
          <span className="logs-last-fetch">
            actualisé à {lastFetch.toLocaleTimeString("fr-FR")}
          </span>
        )}
      </div>

      {unreachable.length > 0 && (
        <p className="logs-unreachable">
          ⚠️ Injoignable : {unreachable.map((r) => `${r.service} (${r.error})`).join(", ")}
        </p>
      )}

      {loading && <p className="logs-empty">Chargement…</p>}
      {!loading && filtered.length === 0 && <p className="logs-empty">Aucun log ne correspond aux filtres actifs.</p>}

      {!loading && filtered.length > 0 && (
        <table className="logs-table">
          <thead>
            <tr>
              <th>Heure</th>
              <th>Service</th>
              <th>Niveau</th>
              <th>Message</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((e, i) => (
              <tr key={i} className={`log-row log-level-${(e.level || "").toLowerCase()}`}>
                <td className="logs-time">{fmtLogTimestamp(e.timestamp)}</td>
                <td className="logs-service">{e.service}</td>
                <td className="logs-level">{e.level}</td>
                <td className="logs-message">{e.message}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
