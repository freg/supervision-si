import React, { useState } from "react";
import {
  createGroup, renameGroup, deleteGroup, setTileGroup, setTileHidden, moveTile, moveGroup,
} from "./hubLayoutLib.js";
import { saveHubLayout } from "./settingsClient.js";

// Personnalisation de l'accueil, étape 3 (livraison #140) -- écran
// accessible à TOUT utilisateur authentifié (pas réservé aux
// administrateurs, contrairement à "Liens externes"). Contrôles
// EXPLICITES (flèches, menu déroulant) restent la méthode fiable et
// testée pour TOUT réordonnancement -- le glisser-déposer n'est ici
// qu'une couche ADDITIONNELLE pour le cas le plus courant (assigner
// une tuile à un cadre), jamais un remplacement : voir le choix acté
// avec la personne (contrôles + glisser-déposer, "les 2").
//
// Chaque action ENREGISTRE IMMÉDIATEMENT (voir commit ci-dessous) --
// pas de bouton "Enregistrer" global à part, mise à jour optimiste
// du hubLayout affiché avant même la confirmation réseau (même
// principe que ObservationsScreen.jsx côté coffre-fort).
export default function PersonalizeHomeView({ fronts, hubLayout, onHubLayoutChanged, apiBase, login, onBack }) {
  const [newGroupTitle, setNewGroupTitle] = useState("");
  const [renamingGroupId, setRenamingGroupId] = useState(null);
  const [renameDraft, setRenameDraft] = useState("");
  const [saving, setSaving] = useState(false);
  const [dragOverTarget, setDragOverTarget] = useState(null); // id de cadre survolé, ou "__none__", ou null

  const groups = Array.isArray(hubLayout?.groups) ? hubLayout.groups : [];
  const sortedGroups = [...groups].sort((a, b) => (a.order ?? 0) - (b.order ?? 0));

  async function commit(newHubLayout) {
    setSaving(true);
    onHubLayoutChanged(newHubLayout);
    await saveHubLayout(apiBase, login, newHubLayout);
    setSaving(false);
  }

  function handleCreateGroup() {
    if (!newGroupTitle.trim()) return;
    commit(createGroup(hubLayout, newGroupTitle));
    setNewGroupTitle("");
  }

  function handleRenameGroup(groupId) {
    if (!renameDraft.trim()) { setRenamingGroupId(null); return; }
    commit(renameGroup(hubLayout, groupId, renameDraft));
    setRenamingGroupId(null);
  }

  function handleDeleteGroup(groupId, title) {
    if (!window.confirm(`Supprimer le cadre "${title}" ? Les tuiles qu'il contient repasseront sans cadre (jamais supprimées).`)) return;
    commit(deleteGroup(hubLayout, groupId, fronts));
  }

  // État affiché d'une tuile -- même repli que getEffectiveTileState
  // (interne à hubLayoutLib.js, jamais exporté -- usage réservé aux
  // mutations) -- refait ici en léger, purement pour l'AFFICHAGE
  // (case à cocher/menu déroulant), aucune décision de persistance
  // prise à partir de cette copie locale.
  function getTileDisplayState(frontId) {
    const existing = hubLayout?.tiles?.[frontId];
    return {
      groupId: existing && typeof existing.groupId === "string" ? existing.groupId : null,
      hidden: existing?.hidden === true,
    };
  }

  function handleDropOnGroup(e, groupId) {
    e.preventDefault();
    setDragOverTarget(null);
    const frontId = e.dataTransfer.getData("text/plain");
    if (frontId) commit(setTileGroup(hubLayout, frontId, groupId, fronts));
  }

  return (
    <div className="hub-settings">
      <div className="hub-settings-topbar">
        <button className="secondary" onClick={onBack}>◀ Retour</button>
        <h1>🎨 Personnaliser l'accueil</h1>
        {saving && <span className="muted personalize-saving">Enregistrement…</span>}
      </div>

      <div className="hub-card hub-settings-section">
        <h2 className="personalize-section-title">Cadres</h2>
        <p className="muted">
          Regroupez vos tuiles dans des cadres titrés. Glissez une tuile depuis la liste
          ci-dessous jusqu'à un cadre pour l'y assigner, ou utilisez le menu déroulant --
          les flèches restent la méthode la plus fiable pour réordonner.
        </p>

        {sortedGroups.length === 0 && <p className="muted">Aucun cadre pour l'instant.</p>}
        {sortedGroups.map((g, i) => (
          <div
            key={g.id}
            className={`personalize-group-row${dragOverTarget === g.id ? " personalize-drop-target" : ""}`}
            onDragOver={(e) => { e.preventDefault(); setDragOverTarget(g.id); }}
            onDragLeave={() => setDragOverTarget(null)}
            onDrop={(e) => handleDropOnGroup(e, g.id)}
          >
            {renamingGroupId === g.id ? (
              <input
                className="personalize-group-rename-input"
                value={renameDraft}
                onChange={(e) => setRenameDraft(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") handleRenameGroup(g.id);
                  if (e.key === "Escape") setRenamingGroupId(null);
                }}
                autoFocus
              />
            ) : (
              <span className="personalize-group-title">{g.title}</span>
            )}
            <div className="hub-external-links-actions">
              <button className="secondary" disabled={i === 0} onClick={() => commit(moveGroup(hubLayout, g.id, "up"))} title="Monter">▲</button>
              <button className="secondary" disabled={i === sortedGroups.length - 1} onClick={() => commit(moveGroup(hubLayout, g.id, "down"))} title="Descendre">▼</button>
              {renamingGroupId === g.id ? (
                <button className="secondary" onClick={() => handleRenameGroup(g.id)} title="Valider">✓</button>
              ) : (
                <button className="secondary" onClick={() => { setRenamingGroupId(g.id); setRenameDraft(g.title); }} title="Renommer">✏️</button>
              )}
              <button className="secondary" onClick={() => handleDeleteGroup(g.id, g.title)} title="Supprimer">🗑️</button>
            </div>
          </div>
        ))}

        {/* Cible de dépôt dédiée pour retirer une tuile de son cadre par
            glisser-déposer -- symétrique des cadres ci-dessus, jamais un
            simple oubli de cas. */}
        <div
          className={`personalize-group-row personalize-none-target${dragOverTarget === "__none__" ? " personalize-drop-target" : ""}`}
          onDragOver={(e) => { e.preventDefault(); setDragOverTarget("__none__"); }}
          onDragLeave={() => setDragOverTarget(null)}
          onDrop={(e) => handleDropOnGroup(e, null)}
        >
          <span className="muted">◻ Sans cadre (glisser une tuile ici pour l'en retirer)</span>
        </div>

        <div className="personalize-new-group">
          <input
            value={newGroupTitle}
            onChange={(e) => setNewGroupTitle(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") handleCreateGroup(); }}
            placeholder="Nom du nouveau cadre"
          />
          <button className="primary" onClick={handleCreateGroup} disabled={!newGroupTitle.trim()}>
            + Nouveau cadre
          </button>
        </div>
      </div>

      <div className="hub-card hub-settings-section">
        <h2 className="personalize-section-title">Tuiles</h2>
        <table className="personalize-tiles-table">
          <thead>
            <tr><th>Tuile</th><th>Visible</th><th>Cadre</th><th>Position</th></tr>
          </thead>
          <tbody>
            {fronts.map((f) => {
              const state = getTileDisplayState(f.id);
              return (
                <tr
                  key={f.id}
                  className={state.hidden ? "personalize-tile-hidden" : ""}
                  draggable
                  onDragStart={(e) => e.dataTransfer.setData("text/plain", f.id)}
                  title="Glisser vers un cadre ci-dessus pour l'y assigner"
                >
                  <td>{f.name}</td>
                  <td>
                    <input
                      type="checkbox"
                      checked={!state.hidden}
                      onChange={(e) => commit(setTileHidden(hubLayout, f.id, !e.target.checked, fronts))}
                      title={state.hidden ? "Masquée -- cocher pour afficher" : "Visible -- décocher pour masquer"}
                    />
                  </td>
                  <td>
                    <select
                      value={state.groupId || ""}
                      onChange={(e) => commit(setTileGroup(hubLayout, f.id, e.target.value || null, fronts))}
                    >
                      <option value="">(sans cadre)</option>
                      {sortedGroups.map((g) => (
                        <option key={g.id} value={g.id}>{g.title}</option>
                      ))}
                    </select>
                  </td>
                  <td className="hub-external-links-actions">
                    <button className="secondary" onClick={() => commit(moveTile(hubLayout, f.id, "up", fronts))} title="Monter">▲</button>
                    <button className="secondary" onClick={() => commit(moveTile(hubLayout, f.id, "down", fronts))} title="Descendre">▼</button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
