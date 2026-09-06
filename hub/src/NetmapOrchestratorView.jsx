import { useState, useEffect, useCallback } from "react";
import {
  fetchSuggestions, fetchSummary, runAllRules, setSuggestionStatus,
} from "./netmapOrchestratorClient.js";

// Tuile hub pour netmap-orchestrator-api (livraison #388-391) --
// consultation des suggestions d'analyse/supervision réseau
// proposées à partir des données de network-agent-api. Ce module
// n'exécute AUCUNE action lui-même (voir netmap-orchestrator/README.md)
// -- cette vue affiche le CONTEXTE de chaque suggestion
// (`suggested_action`/`action_params`) pour qu'une action réelle soit
// menée manuellement via le module concerné (netprobe, snmp-api...).

const SEVERITY_ICONS = { info: "ℹ️", warning: "⚠️", critical: "🔴" };
const STATUS_LABELS = { open: "Ouvertes", dismissed: "Rejetées", done: "Traitées" };

function formatDate(iso) {
  if (!iso) return "?";
  try {
    return new Date(iso).toLocaleString("fr-FR");
  } catch {
    return iso;
  }
}

export default function NetmapOrchestratorView({ onBack, netmapOrchestratorApiBase }) {
  const [statusFilter, setStatusFilter] = useState("open");
  const [suggestions, setSuggestions] = useState([]);
  const [summary, setSummary] = useState({});
  const [loading, setLoading] = useState(false);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState(null);

  const reload = useCallback(async () => {
    setLoading(true);
    const [s, sum] = await Promise.all([
      fetchSuggestions(netmapOrchestratorApiBase, { status: statusFilter || undefined }),
      fetchSummary(netmapOrchestratorApiBase),
    ]);
    setSuggestions(s);
    setSummary(sum);
    setLoading(false);
  }, [netmapOrchestratorApiBase, statusFilter]);

  useEffect(() => {
    reload();
  }, [reload]);

  async function handleRunNow() {
    setRunning(true);
    setError(null);
    const result = await runAllRules(netmapOrchestratorApiBase);
    setRunning(false);
    if (result && result.error) {
      setError(result.error);
      return;
    }
    reload();
  }

  async function handleSetStatus(id, status) {
    const result = await setSuggestionStatus(netmapOrchestratorApiBase, id, status);
    if (result && result.error) {
      setError(result.error);
      return;
    }
    reload();
  }

  return (
    <div className="hub-settings hub-settings-wide">
      <div className="hub-settings-topbar">
        <button className="secondary" onClick={onBack}>◀ Retour</button>
        <h1>🧭 Orchestrateur réseau</h1>
      </div>

      {error && (
        <div className="hub-card" style={{ borderColor: "var(--hub-danger, #c0392b)" }}>
          <p style={{ margin: 0 }}>⚠️ {error}</p>
        </div>
      )}

      <div className="hub-card hub-settings-section">
        <p className="muted" style={{ marginTop: 0 }}>
          Suggestions d'analyse/supervision réseau à partir des données déjà collectées par
          network-agent (appareils, services, flux). Ce module ne lance rien lui-même -- chaque
          suggestion indique quoi faire et avec quel contexte, l'action reste manuelle.
        </p>
        <div className="hub-settings-row">
          {Object.entries(STATUS_LABELS).map(([key, label]) => (
            <button
              key={key}
              className={statusFilter === key ? "" : "secondary"}
              onClick={() => setStatusFilter(key)}
            >
              {label} ({summary[key] ?? 0})
            </button>
          ))}
          <button className="secondary" onClick={() => setStatusFilter("")}>
            Toutes
          </button>
          <button onClick={handleRunNow} disabled={running}>
            {running ? "Analyse en cours…" : "🔄 Lancer une analyse maintenant"}
          </button>
        </div>
      </div>

      <div className="hub-card hub-settings-section">
        {loading ? (
          <p className="muted">Chargement…</p>
        ) : suggestions.length === 0 ? (
          <p className="muted">Aucune suggestion {statusFilter ? STATUS_LABELS[statusFilter]?.toLowerCase() : ""} pour l'instant.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th></th>
                <th>Message</th>
                <th>Règle</th>
                <th>Action suggérée</th>
                <th>Détectée</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {suggestions.map((s) => (
                <tr key={s.id}>
                  <td>{SEVERITY_ICONS[s.severity] || "•"}</td>
                  <td>{s.message}</td>
                  <td className="muted">{s.rule_name}</td>
                  <td className="muted">
                    {s.suggested_action ? (
                      <>
                        <code>{s.suggested_action}</code>
                        {s.action_params && (
                          <div style={{ fontSize: "0.8em" }}>
                            {Object.entries(s.action_params).map(([k, v]) => `${k}=${v}`).join(", ")}
                          </div>
                        )}
                      </>
                    ) : (
                      "—"
                    )}
                  </td>
                  <td className="muted">{formatDate(s.last_detected_at)}</td>
                  <td>
                    {s.status === "open" && (
                      <>
                        <button className="secondary" onClick={() => handleSetStatus(s.id, "done")}>✅ Traité</button>{" "}
                        <button className="secondary" onClick={() => handleSetStatus(s.id, "dismissed")}>✕ Rejeter</button>
                      </>
                    )}
                    {s.status !== "open" && (
                      <button className="secondary" onClick={() => handleSetStatus(s.id, "open")}>↺ Rouvrir</button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
