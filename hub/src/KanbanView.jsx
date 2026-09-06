import React, { useState, useEffect } from "react";
import { fetchTasks, createTask, moveTask, deleteTask } from "./tasksClient.js";

// Tuile "Tâches" (hub), livraison #271 -- gestion de tâches
// INDÉPENDANTE des tickets, avec vue Kanban, demandée explicitement
// ("une gestion de tâche indépendante des tickets avec une vue
// kanban"). Trois colonnes fixes (todo/doing/done) pour cette
// première tranche.
//
// Déplacement par BOUTONS (← / →) plutôt que glisser-déposer --
// choix délibéré : un glisser-déposer HTML5 fiable est plus complexe
// à construire et à vérifier sans navigateur réel disponible dans
// cet environnement de développement ; les boutons donnent le même
// résultat fonctionnel (déplacer une tâche entre colonnes), de façon
// prévisible et testable.

const COLUMNS = [
  { status: "todo", label: "À faire" },
  { status: "doing", label: "En cours" },
  { status: "done", label: "Fait" },
];

export default function KanbanView({ onBack, tasksApiBase, embedded, onViewRelations }) {
  const [tasks, setTasks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [newTitle, setNewTitle] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tasksApiBase]);

  async function load() {
    setLoading(true);
    setTasks(await fetchTasks(tasksApiBase));
    setLoading(false);
  }

  async function handleCreate(e) {
    e.preventDefault();
    if (!newTitle.trim()) return;
    setBusy(true);
    await createTask(tasksApiBase, { title: newTitle.trim(), status: "todo" });
    setNewTitle("");
    await load();
    setBusy(false);
  }

  async function handleMove(taskId, targetStatus) {
    setBusy(true);
    await moveTask(tasksApiBase, taskId, targetStatus, 0);
    await load();
    setBusy(false);
  }

  async function handleDelete(taskId) {
    setBusy(true);
    await deleteTask(tasksApiBase, taskId);
    await load();
    setBusy(false);
  }

  function columnIndex(status) {
    return COLUMNS.findIndex((c) => c.status === status);
  }

  return (
    <div className="hub-settings hub-settings-wide">
      {!embedded && (
        <div className="hub-settings-topbar">
          <button className="secondary" onClick={onBack}>◀ Retour</button>
          <h1>🗂️ Tâches</h1>
        </div>
      )}

      <div className="hub-card">
        <form onSubmit={handleCreate} style={{ display: "flex", gap: 8 }}>
          <input value={newTitle} onChange={(e) => setNewTitle(e.target.value)} placeholder="Nouvelle tâche…" style={{ flex: 1 }} />
          <button type="submit" disabled={busy || !newTitle.trim()}>Ajouter</button>
        </form>
      </div>

      {loading ? (
        <p className="muted">Chargement…</p>
      ) : (
        <div style={{ display: "flex", gap: 16, alignItems: "flex-start" }}>
          {COLUMNS.map((col) => {
            const colTasks = tasks.filter((t) => t.status === col.status).sort((a, b) => a.position - b.position);
            const idx = columnIndex(col.status);
            return (
              <div key={col.status} className="hub-card" style={{ flex: "1 1 0", minWidth: 220 }}>
                <h2 style={{ marginTop: 0 }}>{col.label} ({colTasks.length})</h2>
                {colTasks.length === 0 ? (
                  <p className="muted">Aucune tâche.</p>
                ) : (
                  colTasks.map((t) => (
                    <div key={t.id} className="hub-card" style={{ marginBottom: 8, padding: 8 }}>
                      <p style={{ margin: 0, fontWeight: "bold" }}>{t.title}</p>
                      {t.description && <p className="muted" style={{ margin: "4px 0" }}>{t.description}</p>}
                      {t.due_date && <p className="muted" style={{ margin: "4px 0" }}>Échéance : {t.due_date}</p>}
                      <div style={{ display: "flex", gap: 4, marginTop: 6 }}>
                        {idx > 0 && (
                          <button className="secondary" disabled={busy} onClick={() => handleMove(t.id, COLUMNS[idx - 1].status)}>
                            ← {COLUMNS[idx - 1].label}
                          </button>
                        )}
                        {idx < COLUMNS.length - 1 && (
                          <button className="secondary" disabled={busy} onClick={() => handleMove(t.id, COLUMNS[idx + 1].status)}>
                            {COLUMNS[idx + 1].label} →
                          </button>
                        )}
                        <button className="secondary" disabled={busy} onClick={() => handleDelete(t.id)}>🗑</button>
                        {onViewRelations && (
                          <button className="secondary" title="Voir les relations" onClick={() => onViewRelations("task", t.id)}>🔗</button>
                        )}
                      </div>
                    </div>
                  ))
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
