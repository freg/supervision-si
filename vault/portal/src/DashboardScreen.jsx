import { useEffect, useMemo, useState } from "react";
import { loadAllDecryptedSecretLabels, fetchGlobalHistory } from "./vaultOps.js";
import { computeVaultStats, computeMostActiveEditors, annotateHistoryWithLabels, usedSecretsByFrequency } from "./vaultSearchLib.js";

/**
 * Réservé aux comptes is_system_master (vérifié par l'appelant, voir
 * App.jsx -- cet écran ne vérifie rien lui-même, il suppose déjà
 * l'accès légitime). Les statistiques et libellés du journal sont
 * calculés CÔTÉ CLIENT à partir de secrets déjà déchiffrés -- jamais
 * une route serveur dédiée : le serveur ne peut techniquement pas
 * produire un "top 10" ou associer un libellé lisible au journal
 * (tout est chiffré de son point de vue).
 */
export default function DashboardScreen({ login, privateKey }) {
  const [loading, setLoading] = useState(true);
  const [secrets, setSecrets] = useState([]);
  const [history, setHistory] = useState([]);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    Promise.all([loadAllDecryptedSecretLabels(login, privateKey), fetchGlobalHistory()]).then(
      ([secretsRes, historyData]) => {
        if (cancelled) return;
        if (secretsRes.ok) {
          setSecrets(secretsRes.secrets);
        } else {
          setError(secretsRes.error);
        }
        setHistory(historyData);
        setLoading(false);
      }
    );
    return () => { cancelled = true; };
  }, [login, privateKey]);

  const stats = useMemo(() => computeVaultStats(secrets), [secrets]);
  const topUsed = useMemo(() => usedSecretsByFrequency(secrets, 10), [secrets]);
  const mostActive = useMemo(() => computeMostActiveEditors(history, 10), [history]);
  const annotatedHistory = useMemo(() => annotateHistoryWithLabels(history, secrets), [history, secrets]);

  if (loading) return <p className="vault-muted">Chargement du tableau de bord…</p>;

  return (
    <div className="vault-dashboard">
      <p className="vault-muted">
        Vue d'ensemble à travers TOUT le coffre — accessible uniquement grâce à l'accès
        permanent (maître_système). Les statistiques reflètent ce qui a pu être déchiffré ;
        les libellés du journal proviennent de la même liste.
      </p>
      {error && <p className="vault-error">{error}</p>}

      <div className="vault-dashboard-stats">
        <div className="vault-dashboard-stat-card">
          <span className="vault-dashboard-stat-value">{stats.totalSecrets}</span>
          <span className="vault-dashboard-stat-label">codes au total</span>
        </div>
        <div className="vault-dashboard-stat-card">
          <span className="vault-dashboard-stat-value">{stats.totalCollections}</span>
          <span className="vault-dashboard-stat-label">collections</span>
        </div>
        <div className="vault-dashboard-stat-card">
          <span className="vault-dashboard-stat-value">{stats.totalAccesses}</span>
          <span className="vault-dashboard-stat-label">révélations cumulées</span>
        </div>
      </div>

      <div className="vault-dashboard-columns">
        <div className="vault-panel">
          <h3>🔥 Les plus utilisés</h3>
          {topUsed.length === 0 && <p className="vault-muted">Aucun usage enregistré pour l'instant.</p>}
          <ol className="vault-search-top-list">
            {topUsed.map((s) => (
              <li key={s.id}>
                <span className="vault-search-secret-label">{s.label}</span>
                <span className="vault-search-top-count">{s.access_count}×</span>
              </li>
            ))}
          </ol>
        </div>

        <div className="vault-panel">
          <h3>👤 Les plus actifs</h3>
          {mostActive.length === 0 && <p className="vault-muted">Aucune activité enregistrée pour l'instant.</p>}
          <ol className="vault-search-top-list">
            {mostActive.map((e) => (
              <li key={e.login}>
                <span className="vault-search-secret-label">{e.login}</span>
                <span className="vault-search-top-count">{e.count}</span>
              </li>
            ))}
          </ol>
        </div>
      </div>

      <div className="vault-panel">
        <h3>📜 Journal (200 événements les plus récents)</h3>
        {annotatedHistory.length === 0 && <p className="vault-muted">Aucun événement pour l'instant.</p>}
        <ul className="vault-dashboard-journal">
          {annotatedHistory.map((h, i) => (
            <li key={i}>
              <strong>{h.action === "created" ? "Création" : h.action === "updated" ? "Modification" : h.action}</strong>
              {" — "}<em>{h.label}</em>{" "}
              par <strong>{h.changed_by}</strong> le {new Date(h.changed_at).toLocaleString("fr-FR")}
              {h.reason && <> — {h.reason}</>}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
