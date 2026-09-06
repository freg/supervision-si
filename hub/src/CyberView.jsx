import React, { useState, useEffect } from "react";
import { fetchCyberRisks, createCyberRisk, updateCyberRisk, deleteCyberRisk, fetchCyberRisksHistory } from "./cyberRisksClient.js";
import { fetchGovernanceDocuments, governanceDocumentDownloadUrl } from "./settingsClient.js";

// Écran "Cyber" (livraison #187) -- demandé explicitement : "au même
// niveau que Logs" (menu horizontal texte, #173), "une matrice en
// premier", "à destination en premier lieu des politiques et des
// béotiens" -- DESIGN VOLONTAIREMENT SIMPLE, code couleur explicite,
// jamais de jargon technique dans la vue par défaut (la matrice) --
// le détail/jargon reste réservé à l'onglet "Suivi", pour qui doit
// réellement AGIR sur ces risques.
//
// Deux onglets : "Matrice" (par défaut, lecture seule -- probabilité
// × impact, code couleur, un coup d'œil suffit) et "Suivi" (liste
// complète, statut modifiable, notes d'avancement -- le "suivi des
// points cyber à traiter et avancement" demandé explicitement).

const PROBABILITY_LEVELS = ["élevée", "moyenne", "faible"]; // ordre d'affichage : le plus probable en haut
const IMPACT_LEVELS = ["faible", "moyen", "élevé"]; // gauche -> droite, impact croissant

const STATUS_LABELS = {
  a_traiter: "À traiter",
  en_cours: "En cours",
  traite: "Traité",
  accepte: "Accepté (risque assumé)",
};
const STATUS_ORDER = ["a_traiter", "en_cours", "traite", "accepte"];

function probabilityIndex(p) {
  const i = PROBABILITY_LEVELS.indexOf(p);
  return i === -1 ? null : PROBABILITY_LEVELS.length - i; // "élevée" -> 3, "faible" -> 1
}
function impactIndex(i) {
  const idx = IMPACT_LEVELS.indexOf(i);
  return idx === -1 ? null : idx + 1; // "faible" -> 1, "élevé" -> 3
}

/** Score = probabilité × impact (1 à 9) -- seuils choisis pour une
 * matrice 3×3 classique (diagonale verte -> orange -> rouge). */
function severityColor(probability, impact) {
  const p = probabilityIndex(probability);
  const im = impactIndex(impact);
  if (p === null || im === null) return { bg: "var(--panel)", fg: "var(--muted)", border: "var(--border)" };
  const score = p * im;
  if (score >= 6) return { bg: "var(--danger-bg)", fg: "var(--danger)", border: "var(--danger)" };
  if (score >= 3) return { bg: "var(--warning-bg)", fg: "var(--warning)", border: "var(--warning)" };
  return { bg: "var(--ok-bg)", fg: "var(--ok)", border: "var(--ok)" };
}

const STATUS_DOT = { a_traiter: "⚪", en_cours: "🔵", traite: "🟢", accepte: "⚫" };

// Évolution ISO/IEC 27001 (livraison #193, demandée explicitement) --
// ISO/IEC 27001 exige d'examiner les risques "en tenant compte des
// menaces, vulnérabilités ET IMPACTS" -- cette distinction HUB / SI
// supervisé EST cette dimension d'impact, rendue explicite. "HUB" =
// risque intrinsèque à supervision-si lui-même. "SI supervisé" =
// impact d'un risque du hub SUR les systèmes qu'il gère (bases de
// données, annuaire, équipements réseau...) -- le hub comme VECTEUR,
// pas comme cible.
const SCOPE_LABELS = { hub: "HUB", si_supervise: "SI supervisé" };
const SCOPE_ICON = { hub: "🏠", si_supervise: "🔗" };
const SCOPE_FILTERS = [
  { key: "mixte", label: "Vue mixte" },
  { key: "hub", label: `${SCOPE_ICON.hub} HUB seul` },
  { key: "si_supervise", label: `${SCOPE_ICON.si_supervise} SI supervisé seul` },
];

// Historique versionné (livraison #199, demandé explicitement --
// "un historique des matrices / versionné").
const HISTORY_CHANGE_LABELS = { created: "➕ Créé", updated: "✏️ Modifié", deleted: "🗑️ Supprimé" };

export default function CyberView({ onBack, prefsApiBase, login }) {
  const [risks, setRisks] = useState([]);
  const [hasLoadedOnce, setHasLoadedOnce] = useState(false);
  const [tab, setTab] = useState("matrix");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [expandedId, setExpandedId] = useState(null);
  const [newRiskForm, setNewRiskForm] = useState({ label: "", description: "", category: "", modules: "", probability: "moyenne", impact: "moyen", scope: "hub" });
  const [showNewForm, setShowNewForm] = useState(false);
  const [scopeFilter, setScopeFilter] = useState("mixte");
  const [governanceDocs, setGovernanceDocs] = useState([]);
  const [history, setHistory] = useState(null); // null = pas encore chargé (onglet Historique jamais ouvert)
  const [historyLoading, setHistoryLoading] = useState(false);

  async function load() {
    const data = await fetchCyberRisks(prefsApiBase);
    setRisks(data);
    setHasLoadedOnce(true);
  }

  useEffect(() => {
    load();
    // Documents de gouvernance ISO/IEC 27000 (livraison #195,
    // demandé explicitement -- "présenter versionnés... dans
    // iso27000") -- chargés une fois, indépendamment des risques.
    fetchGovernanceDocuments(prefsApiBase).then(setGovernanceDocs);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Historique (livraison #199) -- chargement PARESSEUX, seulement
  // au premier passage sur l'onglet "Historique" (potentiellement
  // volumineux à terme, jamais chargé si la personne ne le consulte
  // pas). `history === null` distingue "jamais chargé" de "chargé,
  // vide" (tableau).
  useEffect(() => {
    if (tab !== "history" || history !== null) return;
    setHistoryLoading(true);
    fetchCyberRisksHistory(prefsApiBase).then((result) => {
      setHistoryLoading(false);
      if (result && !result.error) setHistory(result);
      else setHistory([]);
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab]);

  async function handleStatusChange(riskId, status) {
    setBusy(true);
    setError(null);
    const result = await updateCyberRisk(prefsApiBase, riskId, { status });
    setBusy(false);
    if (result.error) {
      setError(result.error);
      return;
    }
    load();
  }

  async function handleScopeChange(riskId, scope) {
    setBusy(true);
    setError(null);
    const result = await updateCyberRisk(prefsApiBase, riskId, { scope });
    setBusy(false);
    if (result.error) {
      setError(result.error);
      return;
    }
    load();
  }

  async function handleNotesBlur(riskId, progress_notes) {
    setBusy(true);
    const result = await updateCyberRisk(prefsApiBase, riskId, { progress_notes });
    setBusy(false);
    if (result.error) setError(result.error);
  }

  async function handleCreate(e) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    const result = await createCyberRisk(prefsApiBase, { ...newRiskForm, modules: newRiskForm.modules || null });
    setBusy(false);
    if (result.error) {
      setError(result.error);
      return;
    }
    setNewRiskForm({ label: "", description: "", category: "", modules: "", probability: "moyenne", impact: "moyen", scope: "hub" });
    setShowNewForm(false);
    load();
  }

  async function handleDelete(riskId) {
    setBusy(true);
    setError(null);
    const result = await deleteCyberRisk(prefsApiBase, riskId);
    setBusy(false);
    if (result && result.error) {
      setError(result.error);
      return;
    }
    load();
  }

  const scopedRisks = scopeFilter === "mixte" ? risks : risks.filter((r) => r.scope === scopeFilter);
  const gridRisks = scopedRisks.filter((r) => probabilityIndex(r.probability) !== null && impactIndex(r.impact) !== null);
  const toEvaluateRisks = scopedRisks.filter((r) => probabilityIndex(r.probability) === null || impactIndex(r.impact) === null);

  const doneCount = scopedRisks.filter((r) => r.status === "traite" || r.status === "accepte").length;

  return (
    <div className="hub-settings hub-settings-wide">
      <div className="hub-settings-topbar">
        <button className="secondary" onClick={onBack}>◀ Retour</button>
        <h1>🛡️ Cyber</h1>
      </div>

      <div className="tabs">
        <button className={tab === "matrix" ? "active" : ""} onClick={() => setTab("matrix")}>Matrice</button>
        <button className={tab === "tracking" ? "active" : ""} onClick={() => setTab("tracking")}>Suivi</button>
        <button className={tab === "history" ? "active" : ""} onClick={() => setTab("history")}>Historique</button>
        <button className={tab === "architecture" ? "active" : ""} onClick={() => setTab("architecture")}>Architecture</button>
      </div>

      {governanceDocs.length > 0 && (
        <div className="hub-card" style={{ margin: "12px 0", padding: 12 }}>
          <h3 style={{ marginTop: 0 }}>📄 Documents ISO/IEC 27000</h3>
          <ul style={{ marginBottom: 0 }}>
            {governanceDocs.map((d) => (
              <li key={d.id} style={{ marginBottom: 4 }}>
                <a href={governanceDocumentDownloadUrl(prefsApiBase, d.id)} target="_blank" rel="noreferrer">{d.name}</a>
                <span className="muted"> — version {d.version} · mis à jour le {(d.updated_at || "").slice(0, 10)}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {error && <p className="hub-error">{error}</p>}
      {!hasLoadedOnce && <p className="muted">Chargement…</p>}

      {tab === "matrix" && hasLoadedOnce && (
        <div className="hub-card hub-settings-section">
          <p className="muted">
            Chaque point représente un sujet de sécurité identifié. La position dans le tableau indique
            à quel point il est probable (de haut en bas) et grave s'il se produit (de gauche à droite).
            <strong> Rouge = à regarder en priorité.</strong> {SCOPE_ICON.hub} = risque du HUB lui-même,{" "}
            {SCOPE_ICON.si_supervise} = impact possible sur le système d'information supervisé (bases de
            données, annuaire, équipements réseau...) si ce risque du HUB se concrétise.
          </p>
          <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
            {SCOPE_FILTERS.map((f) => (
              <button
                key={f.key}
                className={scopeFilter === f.key ? "" : "secondary"}
                onClick={() => setScopeFilter(f.key)}
              >
                {f.label}
              </button>
            ))}
          </div>
          <table style={{ width: "100%", borderCollapse: "collapse", tableLayout: "fixed" }}>
            <thead>
              <tr>
                <th style={{ width: "12%" }}></th>
                {IMPACT_LEVELS.map((im) => (
                  <th key={im} style={{ textAlign: "center", padding: 8, fontWeight: "normal", color: "var(--muted)" }}>
                    Gravité : {im}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {PROBABILITY_LEVELS.map((prob) => (
                <tr key={prob}>
                  <td style={{ color: "var(--muted)", fontSize: 13, verticalAlign: "top", padding: 8 }}>
                    Probabilité : {prob}
                  </td>
                  {IMPACT_LEVELS.map((im) => {
                    const cellRisks = gridRisks.filter((r) => r.probability === prob && r.impact === im);
                    const colors = severityColor(prob, im);
                    return (
                      <td
                        key={im}
                        style={{
                          background: colors.bg, border: `1px solid ${colors.border}`,
                          verticalAlign: "top", padding: 8, minHeight: 60,
                        }}
                      >
                        {cellRisks.map((r) => (
                          <div
                            key={r.id}
                            onClick={() => setExpandedId(expandedId === r.id ? null : r.id)}
                            title={SCOPE_LABELS[r.scope]}
                            style={{
                              cursor: "pointer", background: "var(--panel)", borderRadius: 6, padding: "4px 8px",
                              marginBottom: 4, fontSize: 13, color: colors.fg, fontWeight: 600,
                            }}
                          >
                            {SCOPE_ICON[r.scope]} {STATUS_DOT[r.status]} {r.label}
                            {expandedId === r.id && (
                              <p style={{ color: "var(--text)", fontWeight: "normal", marginTop: 6, fontSize: 13 }}>
                                <span className="muted">{SCOPE_LABELS[r.scope]} — </span>{r.description}
                              </p>
                            )}
                          </div>
                        ))}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>

          {toEvaluateRisks.length > 0 && (
            <div style={{ marginTop: 16 }}>
              <h4>À évaluer (évolutions prévues, pas encore construites)</h4>
              <ul>
                {toEvaluateRisks.map((r) => (
                  <li key={r.id}>
                    {SCOPE_ICON[r.scope]} {STATUS_DOT[r.status]} <strong>{r.label}</strong> — <span className="muted">{r.description}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          <p className="muted" style={{ marginTop: 16, fontSize: 13 }}>
            {doneCount} / {scopedRisks.length} points traités ou assumés — cliquez sur un point pour le détail,
            l'onglet "Suivi" permet de mettre à jour l'avancement.
          </p>
        </div>
      )}

      {tab === "tracking" && hasLoadedOnce && (
        <div className="hub-card hub-settings-section">
          <h2>Suivi des points cyber ({risks.length})</h2>
          {STATUS_ORDER.map((status) => {
            const group = risks.filter((r) => r.status === status);
            if (group.length === 0) return null;
            return (
              <div key={status} style={{ marginBottom: 16 }}>
                <h4>{STATUS_DOT[status]} {STATUS_LABELS[status]} ({group.length})</h4>
                {group.map((r) => (
                  <div key={r.id} className="hub-card" style={{ marginBottom: 8, padding: 12 }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 8 }}>
                      <div>
                        <strong>{SCOPE_ICON[r.scope]} {r.label}</strong>
                        <span className="muted"> — {SCOPE_LABELS[r.scope]}</span>
                        {r.category && <span className="muted"> — {r.category}</span>}
                        {r.modules && <span className="muted"> ({r.modules})</span>}
                        <p className="muted" style={{ margin: "4px 0" }}>{r.description}</p>
                        <span className="muted" style={{ fontSize: 12 }}>
                          Probabilité : {r.probability} · Gravité : {r.impact}
                        </span>
                      </div>
                      <button className="secondary" disabled={busy} onClick={() => handleDelete(r.id)}>Retirer</button>
                    </div>
                    <div style={{ display: "flex", gap: 8, marginTop: 8, alignItems: "center" }}>
                      <label>
                        Statut :{" "}
                        <select value={r.status} disabled={busy} onChange={(e) => handleStatusChange(r.id, e.target.value)}>
                          {STATUS_ORDER.map((s) => (
                            <option key={s} value={s}>{STATUS_LABELS[s]}</option>
                          ))}
                        </select>
                      </label>
                      <label>
                        Portée :{" "}
                        <select value={r.scope} disabled={busy} onChange={(e) => handleScopeChange(r.id, e.target.value)}>
                          {Object.keys(SCOPE_LABELS).map((s) => (
                            <option key={s} value={s}>{SCOPE_ICON[s]} {SCOPE_LABELS[s]}</option>
                          ))}
                        </select>
                      </label>
                    </div>
                    <textarea
                      defaultValue={r.progress_notes || ""}
                      placeholder="Notes d'avancement (où en est-on, prochaine étape...)"
                      style={{ width: "100%", marginTop: 8, minHeight: 50 }}
                      onBlur={(e) => handleNotesBlur(r.id, e.target.value)}
                    />
                  </div>
                ))}
              </div>
            );
          })}

          <button className="secondary" onClick={() => setShowNewForm((v) => !v)}>
            {showNewForm ? "Annuler" : "+ Ajouter un point"}
          </button>
          {showNewForm && (
            <form onSubmit={handleCreate} style={{ marginTop: 8, display: "flex", flexDirection: "column", gap: 8, maxWidth: 500 }}>
              <input
                placeholder="Intitulé"
                value={newRiskForm.label}
                onChange={(e) => setNewRiskForm({ ...newRiskForm, label: e.target.value })}
              />
              <textarea
                placeholder="Description en langage clair"
                value={newRiskForm.description}
                onChange={(e) => setNewRiskForm({ ...newRiskForm, description: e.target.value })}
              />
              <input
                placeholder="Catégorie (ex. Réseau, Secrets...)"
                value={newRiskForm.category}
                onChange={(e) => setNewRiskForm({ ...newRiskForm, category: e.target.value })}
              />
              <input
                placeholder="Modules concernés (ex. ssh-tunnels)"
                value={newRiskForm.modules}
                onChange={(e) => setNewRiskForm({ ...newRiskForm, modules: e.target.value })}
              />
              <div style={{ display: "flex", gap: 8 }}>
                <label>
                  Probabilité :{" "}
                  <select value={newRiskForm.probability} onChange={(e) => setNewRiskForm({ ...newRiskForm, probability: e.target.value })}>
                    {PROBABILITY_LEVELS.map((p) => <option key={p} value={p}>{p}</option>)}
                  </select>
                </label>
                <label>
                  Gravité :{" "}
                  <select value={newRiskForm.impact} onChange={(e) => setNewRiskForm({ ...newRiskForm, impact: e.target.value })}>
                    {IMPACT_LEVELS.map((im) => <option key={im} value={im}>{im}</option>)}
                  </select>
                </label>
                <label>
                  Portée :{" "}
                  <select value={newRiskForm.scope} onChange={(e) => setNewRiskForm({ ...newRiskForm, scope: e.target.value })}>
                    {Object.keys(SCOPE_LABELS).map((s) => (
                      <option key={s} value={s}>{SCOPE_ICON[s]} {SCOPE_LABELS[s]}</option>
                    ))}
                  </select>
                </label>
              </div>
              <button type="submit" disabled={busy || !newRiskForm.label}>Ajouter</button>
            </form>
          )}
        </div>
      )}

      {tab === "history" && (
        <div className="hub-card hub-settings-section">
          <p className="muted">
            Chaque création, modification ou suppression d'un point de la matrice est enregistrée ici --
            un instantané complet à cet instant précis, jamais écrasé par les changements suivants
            (même un point depuis supprimé reste visible ici).
          </p>
          {historyLoading && <p className="muted">Chargement…</p>}
          {!historyLoading && history && history.length === 0 && (
            <p className="muted">Aucun changement enregistré depuis la mise en place de l'historique.</p>
          )}
          {!historyLoading && history && history.length > 0 && (
            <table className="logs-entries-table">
              <thead>
                <tr><th>Date</th><th>Type</th><th>Point</th><th>Portée</th><th>Statut</th></tr>
              </thead>
              <tbody>
                {history.map((h) => (
                  <tr key={h.id}>
                    <td className="muted">{new Date(h.recorded_at).toLocaleString("fr-FR")}</td>
                    <td>{HISTORY_CHANGE_LABELS[h.change_type] || h.change_type}</td>
                    <td>{h.label}</td>
                    <td>{SCOPE_ICON[h.scope]} {SCOPE_LABELS[h.scope]}</td>
                    <td>{STATUS_DOT[h.status]} {STATUS_LABELS[h.status] || h.status}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {tab === "architecture" && (
        <div className="hub-card hub-settings-section">
          <p className="muted">
            Vue d'ensemble des ressources du projet, des grandes catégories de configuration et des
            systèmes externes liés -- générée à partir de l'état réel du projet (livraison #207).
          </p>
          <div style={{ overflowX: "auto" }}>
            <img
              src={`${prefsApiBase}/architecture-diagram`}
              alt="Architecture du projet supervision-si : ressources, configuration et systèmes externes liés"
              style={{ maxWidth: "100%", minWidth: 900 }}
            />
          </div>
        </div>
      )}
    </div>
  );
}
