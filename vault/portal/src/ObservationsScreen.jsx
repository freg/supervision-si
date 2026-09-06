import { Fragment, useEffect, useMemo, useState } from "react";
import { loadAllDecryptedSecretLabels, fetchObservationsSummary, fetchSecretObservations, addSecretObservation } from "./vaultOps.js";
import {
  mergeSecretsWithObservationsSummary, filterSecretsByObservationPresence, sortSecretsByObservationCriteria,
} from "./vaultSearchLib.js";

/**
 * Écran "Observations" -- demandé explicitement (redesign convenu
 * avec la personne après une demande initiale à la mise en page
 * ambiguë) : un tableau UNIQUE de tous les secrets accessibles,
 * triable/filtrable sur la présence d'observations, avec un détail
 * dépliable par ligne (toutes les observations de ce secret,
 * la plus récente en premier). Même esprit "tableau défilable" que
 * "Utilisation des codes" (VaultSearchScreen.jsx) -- motif apprécié
 * explicitement par la personne pour sa simplicité.
 *
 * Le résumé (nombre + date la plus récente) vient d'une route
 * serveur dédiée, agrégée, JAMAIS déchiffrée (juste des métadonnées
 * en clair -- voir vault/api/app.py, POST /secrets/observations-summary).
 * Le déchiffrement du contenu réel des observations n'a lieu qu'au
 * dépli d'une ligne (fetchSecretObservations, déjà existant), jamais
 * pour tout le tableau d'un coup -- inutile tant que la ligne n'est
 * pas ouverte.
 *
 * Depuis backlog coffre-fort (livraison #117) : ajout d'une
 * observation directement depuis la ligne dépliée -- jusqu'ici
 * possible uniquement depuis un secret ouvert/révélé (écran
 * Collections ou popup de révélation en Recherche). Réutilise
 * addSecretObservation tel quel (vaultOps.js), aucune logique
 * parallèle.
 */
export default function ObservationsScreen({ login, privateKey, isReadOnly }) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [secrets, setSecrets] = useState([]);
  const [summary, setSummary] = useState({});
  const [filterMode, setFilterMode] = useState("all"); // "all" | "with" | "without"
  const [sortBy, setSortBy] = useState("recent"); // "recent" | "count" | "alpha"
  const [expandedId, setExpandedId] = useState(null);
  const [expandedObservations, setExpandedObservations] = useState([]);
  const [expandedLoading, setExpandedLoading] = useState(false);
  // Formulaire d'ajout -- propre à la ligne dépliée, jamais pré-rempli
  // d'une ligne à l'autre (voir toggleExpand, réinitialisé à chaque
  // dépli/repli).
  const [newObservationText, setNewObservationText] = useState("");
  const [addingObservation, setAddingObservation] = useState(false);
  const [addObservationError, setAddObservationError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    loadAllDecryptedSecretLabels(login, privateKey).then(async (res) => {
      if (cancelled) return;
      if (!res.ok) {
        setError(res.error);
        setLoading(false);
        return;
      }
      setSecrets(res.secrets);
      const ids = res.secrets.map((s) => s.id);
      const summaryData = await fetchObservationsSummary(ids);
      if (cancelled) return;
      setSummary(summaryData);
      setLoading(false);
    });
    return () => { cancelled = true; };
  }, [login, privateKey]);

  const merged = useMemo(() => mergeSecretsWithObservationsSummary(secrets, summary), [secrets, summary]);
  const filtered = useMemo(() => filterSecretsByObservationPresence(merged, filterMode), [merged, filterMode]);
  const sorted = useMemo(() => sortSecretsByObservationCriteria(filtered, sortBy), [filtered, sortBy]);

  const toggleExpand = async (secret) => {
    setAddObservationError(null);
    setNewObservationText("");
    if (expandedId === secret.id) {
      setExpandedId(null);
      return;
    }
    setExpandedId(secret.id);
    setExpandedObservations([]);
    if (secret.observationCount === 0) return; // rien à charger, la ligne dépliée montrera juste "aucune observation"
    setExpandedLoading(true);
    const observations = await fetchSecretObservations(secret.id, secret.collectionKey);
    // Plus récente en premier -- demandé explicitement, alors que
    // fetchSecretObservations renvoie chronologique CROISSANT (comme
    // le serveur, voir vault/api/app.py) -- inversion uniquement pour
    // CET affichage, jamais côté serveur ni pour les autres usages de
    // cette même fonction.
    observations.sort((a, b) => new Date(b.createdAt) - new Date(a.createdAt));
    setExpandedObservations(observations);
    setExpandedLoading(false);
  };

  /** Ajoute une observation depuis la ligne dépliée -- réutilise
   * addSecretObservation tel quel (même fonction que l'écran
   * Collections et le popup de révélation en Recherche), la clé de
   * collection est déjà disponible sur `secret` (voir
   * loadAllDecryptedSecretLabels, vaultOps.js). Après succès,
   * recharge les observations de CETTE ligne (pour l'afficher
   * immédiatement) et met à jour le résumé LOCALEMENT (jamais un
   * rechargement complet de tous les secrets pour une seule ligne
   * modifiée -- mise à jour optimiste, même esprit que FieldsEditor). */
  const handleAddObservation = async (secret) => {
    if (!newObservationText.trim()) return;
    setAddingObservation(true);
    setAddObservationError(null);
    const res = await addSecretObservation(secret.id, newObservationText.trim(), secret.collectionKey, login);
    if (res.ok) {
      setNewObservationText("");
      const observations = await fetchSecretObservations(secret.id, secret.collectionKey);
      observations.sort((a, b) => new Date(b.createdAt) - new Date(a.createdAt));
      setExpandedObservations(observations);
      setSummary((prev) => ({
        ...prev,
        [secret.id]: { count: observations.length, most_recent_at: observations[0]?.createdAt || null },
      }));
    } else {
      setAddObservationError(res.error);
    }
    setAddingObservation(false);
  };

  if (loading) return <p className="vault-muted">Chargement…</p>;
  if (error) return <p className="vault-error">{error}</p>;

  return (
    <div className="vault-panel">
      <div className="vault-panel-header-row">
        <h2>📝 Observations</h2>
      </div>

      <div className="vault-observations-page-toolbar">
        <div className="vault-form-row">
          <label className="vault-inline-label">Filtrer :</label>
          <select value={filterMode} onChange={(e) => setFilterMode(e.target.value)}>
            <option value="all">Tous les secrets</option>
            <option value="with">Avec observations</option>
            <option value="without">Sans observation</option>
          </select>
          <label className="vault-inline-label">Trier par :</label>
          <select value={sortBy} onChange={(e) => setSortBy(e.target.value)}>
            <option value="recent">Observation la plus récente</option>
            <option value="count">Nombre d'observations</option>
            <option value="alpha">Libellé (alphabétique)</option>
          </select>
        </div>
        <p className="vault-muted">{sorted.length} secret{sorted.length !== 1 ? "s" : ""}</p>
      </div>

      {sorted.length === 0 && <p className="vault-muted">Aucun secret ne correspond à ce filtre.</p>}

      {sorted.length > 0 && (
        <div className="vault-usage-table-scroll">
          <table className="vault-usage-table vault-observations-page-table">
            <thead>
              <tr>
                <th>Libellé</th>
                <th>Collection</th>
                <th>Localisation</th>
                <th>Observations</th>
                <th>Plus récente</th>
              </tr>
            </thead>
            <tbody>
              {sorted.map((s) => (
                <Fragment key={s.id}>
                  <tr onClick={() => toggleExpand(s)} className={expandedId === s.id ? "vault-observations-row-expanded" : ""}>
                    <td>{expandedId === s.id ? "▾ " : "▸ "}{s.label}</td>
                    <td>{s.collectionName}</td>
                    <td>{s.localisation || "—"}</td>
                    <td className={s.observationCount > 0 ? "vault-usage-count" : "vault-muted"}>{s.observationCount}</td>
                    <td className="vault-muted">
                      {s.mostRecentObservationAt ? new Date(s.mostRecentObservationAt).toLocaleString("fr-FR") : "—"}
                    </td>
                  </tr>
                  {expandedId === s.id && (
                    <tr className="vault-observations-detail-row">
                      <td colSpan={5}>
                        {expandedLoading && <p className="vault-muted">Déchiffrement…</p>}
                        {!expandedLoading && expandedObservations.length === 0 && (
                          <p className="vault-muted">Aucune observation.</p>
                        )}
                        {!expandedLoading && expandedObservations.length > 0 && (
                          <table className="vault-observations-table">
                            <tbody>
                              {expandedObservations.map((o) => (
                                <tr key={o.id}>
                                  <td>{o.text}</td>
                                  <td className="vault-muted">{o.author} — {new Date(o.createdAt).toLocaleString("fr-FR")}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        )}
                        {!isReadOnly && !expandedLoading && (
                          <div className="vault-form-row vault-observations-page-add-row">
                            <input
                              placeholder="nouvelle observation (ex. code changé le 12, porte grippée le matin…)"
                              value={newObservationText}
                              onChange={(e) => setNewObservationText(e.target.value)}
                              onKeyDown={(e) => e.key === "Enter" && handleAddObservation(s)}
                            />
                            <button
                              className="secondary"
                              onClick={() => handleAddObservation(s)}
                              disabled={addingObservation || !newObservationText.trim()}
                            >
                              {addingObservation ? "…" : "+ Ajouter"}
                            </button>
                          </div>
                        )}
                        {addObservationError && <p className="vault-error">{addObservationError}</p>}
                      </td>
                    </tr>
                  )}
                </Fragment>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
