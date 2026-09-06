import { useEffect, useState } from "react";
import {
  fetchFilterRules, createFilterRule, deleteFilterRule,
  fetchExclusionRules, createExclusionRule, deleteExclusionRule,
  fetchPriorityKeywords, createPriorityKeyword, deletePriorityKeyword,
  fetchTypes, fetchLevels, fetchUsers,
} from "./ticketsApi.js";

const ACTION_LABELS = {
  attach_existing: "Rattache à un ticket existant",
  create_ticket: "Crée un nouveau ticket",
  both: "Rattache si possible, sinon crée",
};

export default function TicketRulesView({ onClose }) {
  const [rules, setRules] = useState([]);
  const [types, setTypes] = useState([]);
  const [levels, setLevels] = useState([]);
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);

  const [form, setForm] = useState({
    label: "", pattern: "", target_field: "summary", action: "both",
    ticket_ref_group: "ticket_id", default_type_id: "", default_level_id: "",
    default_user_id: "", priority: 0,
  });
  const [error, setError] = useState(null);

  const [exclusions, setExclusions] = useState([]);
  const [exclusionForm, setExclusionForm] = useState({ label: "", pattern: "" });
  const [exclusionError, setExclusionError] = useState(null);

  const [priorities, setPriorities] = useState([]);
  const [priorityForm, setPriorityForm] = useState({ label: "", pattern: "" });
  const [priorityError, setPriorityError] = useState(null);

  async function reload() {
    setLoading(true);
    const [r, t, l, u, ex, pr] = await Promise.all([
      fetchFilterRules(), fetchTypes(), fetchLevels(), fetchUsers(), fetchExclusionRules(), fetchPriorityKeywords(),
    ]);
    setRules(r);
    setTypes(t);
    setLevels(l);
    setUsers(u);
    setExclusions(ex);
    setPriorities(pr);
    setLoading(false);
  }

  useEffect(() => {
    reload();
  }, []);

  async function handleCreate() {
    if (!form.label.trim() || !form.pattern.trim()) {
      setError("Le libellé et le motif sont requis.");
      return;
    }
    try {
      new RegExp(form.pattern);
    } catch (err) {
      setError(`Expression régulière invalide : ${err.message}`);
      return;
    }
    setError(null);
    const result = await createFilterRule({
      ...form,
      default_type_id: form.default_type_id || null,
      default_level_id: form.default_level_id || null,
      default_user_id: form.default_user_id || null,
      priority: Number(form.priority) || 0,
    });
    if (!result.ok) {
      setError(result.data.error || "Échec de la création.");
      return;
    }
    setForm({ ...form, label: "", pattern: "" });
    reload();
  }

  async function handleDelete(id) {
    const ok = await deleteFilterRule(id);
    if (ok) reload();
  }

  async function handleCreateExclusion() {
    if (!exclusionForm.label.trim() || !exclusionForm.pattern.trim()) {
      setExclusionError("Le libellé et le motif sont requis.");
      return;
    }
    try {
      new RegExp(exclusionForm.pattern);
    } catch (err) {
      setExclusionError(`Expression régulière invalide : ${err.message}`);
      return;
    }
    setExclusionError(null);
    const result = await createExclusionRule(exclusionForm);
    if (!result.ok) {
      setExclusionError(result.data.error || "Échec de la création.");
      return;
    }
    setExclusionForm({ label: "", pattern: "" });
    reload();
  }

  async function handleDeleteExclusion(id) {
    const ok = await deleteExclusionRule(id);
    if (ok) reload();
  }

  async function handleCreatePriority() {
    if (!priorityForm.label.trim() || !priorityForm.pattern.trim()) {
      setPriorityError("Le libellé et le motif sont requis.");
      return;
    }
    try {
      new RegExp(priorityForm.pattern);
    } catch (err) {
      setPriorityError(`Expression régulière invalide : ${err.message}`);
      return;
    }
    setPriorityError(null);
    const result = await createPriorityKeyword(priorityForm);
    if (!result.ok) {
      setPriorityError(result.data.error || "Échec de la création.");
      return;
    }
    setPriorityForm({ label: "", pattern: "" });
    reload();
  }

  async function handleDeletePriority(id) {
    const ok = await deletePriorityKeyword(id);
    if (ok) reload();
  }

  return (
    <div className="pixel-grid-app">
      <div className="pixel-grid-toolbar">
        <div className="timeline-header">
          <div className="timeline-title">⚙️ Règles de filtrage calendrier</div>
          <button className="calendar-nav-btn" onClick={onClose}>← Retour</button>
        </div>
      </div>

      <p className="synthesis-empty">
        Appliquées par ordre de priorité croissante (la première règle qui
        matche s'applique) à chaque nouvel événement calendrier importé.
        Le groupe nommé (ex: <code>(?P&lt;ticket_id&gt;\d+)</code>) porte
        l'identifiant de ticket pour le mode "rattache".
      </p>

      {loading && <p className="synthesis-empty">Chargement…</p>}

      {!loading && (
        <div className="pixel-grid-body">
          <div className="pixel-grid-main">
            <table className="geo-table">
              <thead>
                <tr>
                  <th>Priorité</th><th>Libellé</th><th>Motif</th><th>Action</th><th></th>
                </tr>
              </thead>
              <tbody>
                {rules.map((r) => (
                  <tr key={r.id}>
                    <td>{r.priority}</td>
                    <td>{r.label}</td>
                    <td><code>{r.pattern}</code></td>
                    <td>{ACTION_LABELS[r.action] || r.action}</td>
                    <td>
                      <button className="basket-remove-btn" onClick={() => handleDelete(r.id)} title="Supprimer">✕</button>
                    </td>
                  </tr>
                ))}
                {rules.length === 0 && (
                  <tr><td colSpan={5} className="synthesis-empty">Aucune règle configurée pour l'instant.</td></tr>
                )}
              </tbody>
            </table>

            <div className="pixel-grid-toolbar" style={{ marginTop: "1rem" }}>
              <div className="timeline-title" style={{ fontSize: "0.85rem" }}>Nouvelle règle</div>
              <div className="pixel-grid-controls">
                <input className="geo-input" placeholder="Libellé" value={form.label}
                  onChange={(e) => setForm({ ...form, label: e.target.value })} />
                <input className="geo-input" style={{ width: 220 }} placeholder="Motif (regex)" value={form.pattern}
                  onChange={(e) => setForm({ ...form, pattern: e.target.value })} />
                <select className="geo-input" value={form.target_field}
                  onChange={(e) => setForm({ ...form, target_field: e.target.value })}>
                  <option value="summary">titre</option>
                  <option value="description">description</option>
                  <option value="both">titre + description</option>
                </select>
                <select className="geo-input" value={form.action}
                  onChange={(e) => setForm({ ...form, action: e.target.value })}>
                  <option value="attach_existing">rattache existant</option>
                  <option value="create_ticket">crée un ticket</option>
                  <option value="both">rattache, sinon crée</option>
                </select>
              </div>
              <div className="pixel-grid-controls">
                <input className="geo-input" placeholder="Nom du groupe regex (id ticket)" value={form.ticket_ref_group}
                  onChange={(e) => setForm({ ...form, ticket_ref_group: e.target.value })} />
                <select className="geo-input" value={form.default_type_id}
                  onChange={(e) => setForm({ ...form, default_type_id: e.target.value })}>
                  <option value="">type par défaut</option>
                  {types.map((t) => <option key={t.id} value={t.id}>{t.label}</option>)}
                </select>
                <select className="geo-input" value={form.default_level_id}
                  onChange={(e) => setForm({ ...form, default_level_id: e.target.value })}>
                  <option value="">niveau par défaut</option>
                  {levels.map((l) => <option key={l.id} value={l.id}>{l.label}</option>)}
                </select>
                <select className="geo-input" value={form.default_user_id}
                  onChange={(e) => setForm({ ...form, default_user_id: e.target.value })}>
                  <option value="">demandeur par défaut</option>
                  {users.map((u) => <option key={u.id} value={u.id}>{u.login}</option>)}
                </select>
                <input className="geo-input" style={{ width: 80 }} type="number" placeholder="priorité" value={form.priority}
                  onChange={(e) => setForm({ ...form, priority: e.target.value })} />
                <button className="pixel-grid-reset-btn" onClick={handleCreate}>➕ Créer</button>
              </div>
              {error && <p className="pixel-grid-error">{error}</p>}
            </div>

            <div style={{ marginTop: "2rem", borderTop: "1px solid var(--color-border)", paddingTop: "1rem" }}>
              <div className="timeline-title" style={{ fontSize: "0.85rem" }}>🚫 Liste d'exclusion</div>
              <p className="synthesis-empty">
                Un événement qui matche l'un de ces motifs n'est <strong>jamais</strong>
                {" "}considéré comme un ticket potentiel — même s'il matche par ailleurs
                le mot-clé déclencheur (ex: une réunion récurrente qui mentionne "SAV"
                dans son titre sans être elle-même un ticket).
              </p>

              <table className="geo-table">
                <thead>
                  <tr><th>Libellé</th><th>Motif</th><th></th></tr>
                </thead>
                <tbody>
                  {exclusions.map((ex) => (
                    <tr key={ex.id}>
                      <td>{ex.label}</td>
                      <td><code>{ex.pattern}</code></td>
                      <td>
                        <button className="basket-remove-btn" onClick={() => handleDeleteExclusion(ex.id)} title="Supprimer">✕</button>
                      </td>
                    </tr>
                  ))}
                  {exclusions.length === 0 && (
                    <tr><td colSpan={3} className="synthesis-empty">Aucune exclusion configurée.</td></tr>
                  )}
                </tbody>
              </table>

              <div className="pixel-grid-controls" style={{ marginTop: "0.5rem" }}>
                <input className="geo-input" placeholder="Libellé" value={exclusionForm.label}
                  onChange={(e) => setExclusionForm({ ...exclusionForm, label: e.target.value })} />
                <input className="geo-input" style={{ width: 260 }} placeholder="Motif (regex)" value={exclusionForm.pattern}
                  onChange={(e) => setExclusionForm({ ...exclusionForm, pattern: e.target.value })} />
                <button className="pixel-grid-reset-btn" onClick={handleCreateExclusion}>➕ Exclure</button>
              </div>
              {exclusionError && <p className="pixel-grid-error">{exclusionError}</p>}
            </div>

            <div style={{ marginTop: "2rem", borderTop: "1px solid var(--color-border)", paddingTop: "1rem" }}>
              <div className="timeline-title" style={{ fontSize: "0.85rem" }}>🔥 Mots-clés d'urgence</div>
              <p className="synthesis-empty">
                Ne décident ni n'excluent rien — servent uniquement au tri
                "Urgence" de l'écran de revue (les événements matchant
                remontent en tête).
              </p>

              <table className="geo-table">
                <thead>
                  <tr><th>Libellé</th><th>Motif</th><th></th></tr>
                </thead>
                <tbody>
                  {priorities.map((p) => (
                    <tr key={p.id}>
                      <td>{p.label}</td>
                      <td><code>{p.pattern}</code></td>
                      <td>
                        <button className="basket-remove-btn" onClick={() => handleDeletePriority(p.id)} title="Supprimer">✕</button>
                      </td>
                    </tr>
                  ))}
                  {priorities.length === 0 && (
                    <tr><td colSpan={3} className="synthesis-empty">Aucun mot-clé configuré.</td></tr>
                  )}
                </tbody>
              </table>

              <div className="pixel-grid-controls" style={{ marginTop: "0.5rem" }}>
                <input className="geo-input" placeholder="Libellé" value={priorityForm.label}
                  onChange={(e) => setPriorityForm({ ...priorityForm, label: e.target.value })} />
                <input className="geo-input" style={{ width: 260 }} placeholder="Motif (regex)" value={priorityForm.pattern}
                  onChange={(e) => setPriorityForm({ ...priorityForm, pattern: e.target.value })} />
                <button className="pixel-grid-reset-btn" onClick={handleCreatePriority}>➕ Ajouter</button>
              </div>
              {priorityError && <p className="pixel-grid-error">{priorityError}</p>}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
