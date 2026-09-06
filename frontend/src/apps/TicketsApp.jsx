import { useEffect, useState } from "react";
import {
  fetchQueue, fetchUsers, fetchTypes, fetchLevels, fetchStatuts,
  createTicket, createUser, createType, createLevel, createStatut,
  importCalendarFile, importCalendarUrl,
  fetchGoogleOAuthStatus, importGoogleApi, API_BASE_URL,
} from "./ticketsApi.js";
import CreatableSelect from "./CreatableSelect.jsx";
import TicketDetailView from "./TicketDetailView.jsx";
import TicketRulesView from "./TicketRulesView.jsx";
import CalendarReviewView from "./CalendarReviewView.jsx";
import TicketsParallelView from "./TicketsParallelView.jsx";
import DatabaseAdminView from "./DatabaseAdminView.jsx";
import KanbanBoardView from "./KanbanBoardView.jsx";

function formatWait(seconds) {
  if (seconds < 3600) return `${Math.round(seconds / 60)}min`;
  if (seconds < 86400) return `${(seconds / 3600).toFixed(1)}h`;
  return `${(seconds / 86400).toFixed(1)}j`;
}

function NewTicketForm({ users, types, levels, statuts, onCreated, onReferenceCreated }) {
  const [form, setForm] = useState({ user_id: "", subject: "", type_id: "", level_id: "", statut_id: "", description: "" });
  const [open, setOpen] = useState(false);

  async function handleSubmit() {
    if (!form.subject.trim()) return;
    const result = await createTicket({
      user_id: form.user_id || null, subject: form.subject,
      type_id: form.type_id || null, level_id: form.level_id || null,
      statut_id: form.statut_id || null, description: form.description,
    });
    if (result.ok) {
      setForm({ user_id: "", subject: "", type_id: "", level_id: "", statut_id: "", description: "" });
      setOpen(false);
      onCreated();
    }
  }

  async function handleCreateUser(payload) {
    const result = await createUser({ login: payload.label, name: payload.label });
    if (result.ok) onReferenceCreated("users", { id: result.data.id, login: payload.label, name: payload.label });
    return result.ok ? result.data.id : null;
  }
  async function handleCreateType(payload) {
    const result = await createType({ label: payload.label });
    if (result.ok) onReferenceCreated("types", { id: result.data.id, label: payload.label });
    return result.ok ? result.data.id : null;
  }
  async function handleCreateLevel(payload) {
    const result = await createLevel({ label: payload.label, rank: Number(payload.rank) || 0 });
    if (result.ok) onReferenceCreated("levels", { id: result.data.id, label: payload.label, rank: Number(payload.rank) || 0 });
    return result.ok ? result.data.id : null;
  }
  async function handleCreateStatut(payload) {
    const result = await createStatut({ label: payload.label });
    if (result.ok) onReferenceCreated("statuts", { id: result.data.id, label: payload.label });
    return result.ok ? result.data.id : null;
  }

  if (!open) {
    return (
      <button className="inject-toggle-btn" onClick={() => setOpen(true)}>➕ Nouveau ticket</button>
    );
  }

  return (
    <div className="inject-form">
      <div className="inject-form-title">Nouveau ticket</div>
      <input className="calendar-keywords-input" placeholder="Sujet" value={form.subject}
        onChange={(e) => setForm({ ...form, subject: e.target.value })} />
      <div className="pixel-grid-controls">
        <CreatableSelect
          value={form.user_id} onChange={(v) => setForm({ ...form, user_id: v })}
          options={users.map((u) => ({ id: u.id, label: u.login }))}
          placeholder="demandeur" onCreate={handleCreateUser}
        />
        <CreatableSelect
          value={form.type_id} onChange={(v) => setForm({ ...form, type_id: v })}
          options={types.map((t) => ({ id: t.id, label: t.label }))}
          placeholder="type" onCreate={handleCreateType}
        />
        <CreatableSelect
          value={form.level_id} onChange={(v) => setForm({ ...form, level_id: v })}
          options={levels.map((l) => ({ id: l.id, label: l.label }))}
          placeholder="niveau" onCreate={handleCreateLevel}
          extraFields={[{ key: "rank", placeholder: "rang" }]}
        />
        <CreatableSelect
          value={form.statut_id} onChange={(v) => setForm({ ...form, statut_id: v })}
          options={statuts.map((s) => ({ id: s.id, label: s.label }))}
          placeholder="statut" onCreate={handleCreateStatut}
        />
      </div>
      <input className="calendar-keywords-input" placeholder="Description" value={form.description}
        onChange={(e) => setForm({ ...form, description: e.target.value })} />
      {form.subject.trim() && !form.user_id && (
        <p className="pixel-grid-empty-hint" style={{ color: "var(--color-warning, #e0a94c)" }}>
          ⚠️ Aucun demandeur sélectionné — le ticket sera créé sans, tu pourras le renseigner plus tard.
        </p>
      )}
      <div className="inject-form-actions">
        <button className="calendar-nav-btn" onClick={() => setOpen(false)}>Annuler</button>
        <button className="calendar-nav-btn inject-submit-btn" onClick={handleSubmit}>Créer</button>
      </div>
    </div>
  );
}

function CalendarImportPanel({ onImported }) {
  const [url, setUrl] = useState("");
  const [importing, setImporting] = useState(false);
  const [result, setResult] = useState(null);
  const [oauthStatus, setOauthStatus] = useState({ configured: false, connected: false });

  useEffect(() => {
    fetchGoogleOAuthStatus().then(setOauthStatus);
  }, []);

  async function handleGoogleApiImport() {
    setImporting(true);
    const r = await importGoogleApi();
    setImporting(false);
    setResult(r.ok ? r.data : { error: r.data.error });
    if (r.ok) onImported();
  }

  async function handleUrlImport() {
    if (!url.trim()) return;
    setImporting(true);
    const r = await importCalendarUrl(url.trim());
    setImporting(false);
    setResult(r.ok ? r.data : { error: r.data.error });
    if (r.ok) onImported();
  }

  async function handleFileImport(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    setImporting(true);
    const r = await importCalendarFile(file);
    setImporting(false);
    setResult(r.ok ? r.data : { error: r.data.error });
    if (r.ok) onImported();
    e.target.value = "";
  }

  return (
    <div className="pixel-grid-toolbar">
      <div className="pixel-grid-controls">
        <span className="pixel-grid-controls-label">Import agenda :</span>
        <input className="geo-input" style={{ width: 280 }} placeholder="URL secrète iCal Google"
          value={url} onChange={(e) => setUrl(e.target.value)} />
        <button className="pixel-grid-reset-btn" onClick={handleUrlImport} disabled={importing}>
          {importing ? "…" : "Importer l'URL"}
        </button>
        <label className="inject-file-label" style={{ marginBottom: 0 }}>
          ou fichier .ics
          <input type="file" accept=".ics" onChange={handleFileImport} hidden />
        </label>
      </div>

      <div className="pixel-grid-controls">
        <span className="pixel-grid-controls-label">ou connecteur OAuth2 :</span>
        {!oauthStatus.configured && (
          <span className="pixel-grid-empty-hint">
            non configuré (GOOGLE_OAUTH_CLIENT_ID/SECRET dans .env) — voir tickets/README.md
          </span>
        )}
        {oauthStatus.configured && !oauthStatus.connected && (
          <a className="pixel-grid-reset-btn" href={`${API_BASE_URL}/oauth/google/start`} target="_blank" rel="noreferrer">
            🔗 Connecter mon agenda Google
          </a>
        )}
        {oauthStatus.configured && oauthStatus.connected && (
          <>
            <span className="pixel-grid-empty-hint">✅ agenda connecté</span>
            <button className="pixel-grid-reset-btn" onClick={handleGoogleApiImport} disabled={importing}>
              {importing ? "…" : "Importer via l'API"}
            </button>
          </>
        )}
      </div>

      {result && !result.error && (
        <p className="pixel-grid-hover-detail">
          {result.total_events} événement(s) trouvé(s) — {result.imported} nouveau(x),
          {" "}{result.already_known} déjà connu(s). Passe par "📋 Revue import"
          pour les affecter à des tickets.
        </p>
      )}
      {result?.diagnostic && (
        <div className="pixel-grid-error">
          <p style={{ margin: "0 0 0.3rem 0" }}>
            ⚠️ 0 événement trouvé — la requête a réussi (HTTP {result.diagnostic.http_status})
            mais le contenu ne ressemble {result.diagnostic.looks_like_ics ? "" : "PAS "}
            à du vrai ICS ({result.diagnostic.content_type}, {result.diagnostic.content_length} caractères).
            {!result.diagnostic.looks_like_ics && " Probablement une page de connexion/redirection plutôt que l'agenda lui-même — vérifie que l'URL est bien l'adresse secrète iCal (pas le lien de partage classique)."}
          </p>
          <details>
            <summary style={{ cursor: "pointer" }}>Aperçu du contenu reçu</summary>
            <pre style={{ whiteSpace: "pre-wrap", fontSize: "0.65rem" }}>{result.diagnostic.content_preview}</pre>
          </details>
        </div>
      )}
      {result?.error && <p className="pixel-grid-error">{result.error}</p>}
    </div>
  );
}

export default function TicketsApp() {
  const [tickets, setTickets] = useState([]);
  const [users, setUsers] = useState([]);
  const [types, setTypes] = useState([]);
  const [levels, setLevels] = useState([]);
  const [statuts, setStatuts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState({ typeId: "", userId: "", statutId: "", state: "open" });
  const [selectedTicketId, setSelectedTicketId] = useState(null);
  const [showRules, setShowRules] = useState(false);
  const [showReview, setShowReview] = useState(false);
  const [showParallel, setShowParallel] = useState(false);
  const [showAdmin, setShowAdmin] = useState(false);
  const [showKanban, setShowKanban] = useState(false);

  async function reload() {
    setLoading(true);
    const [t, u, ty, l, s] = await Promise.all([
      fetchQueue(filters), fetchUsers(), fetchTypes(), fetchLevels(), fetchStatuts(),
    ]);
    setTickets(t);
    setUsers(u);
    setTypes(ty);
    setLevels(l);
    setStatuts(s);
    setLoading(false);
  }

  function handleReferenceCreated(table, item) {
    // Mise à jour locale immédiate — le <select> voit la nouvelle option
    // dès ce rendu, sans attendre un rechargement complet (vrai bug
    // corrigé : sans ça, la valeur sélectionnée n'avait pas encore
    // d'option correspondante et retombait à vide côté interface).
    if (table === "users") setUsers((prev) => [...prev, item]);
    if (table === "types") setTypes((prev) => [...prev, item]);
    if (table === "levels") setLevels((prev) => [...prev, item]);
    if (table === "statuts") setStatuts((prev) => [...prev, item]);
    reload(); // resynchronise le reste en arrière-plan
  }

  useEffect(() => {
    reload();
  }, [filters]);

  if (selectedTicketId) {
    return <TicketDetailView ticketId={selectedTicketId} onClose={() => { setSelectedTicketId(null); reload(); }} />;
  }
  if (showRules) {
    return <TicketRulesView onClose={() => { setShowRules(false); reload(); }} />;
  }
  if (showReview) {
    return <CalendarReviewView onClose={() => { setShowReview(false); reload(); }} onAssigned={reload} />;
  }
  if (showParallel) {
    return <TicketsParallelView onClose={() => { setShowParallel(false); reload(); }} />;
  }
  if (showAdmin) {
    return <DatabaseAdminView onClose={() => { setShowAdmin(false); reload(); }} />;
  }
  if (showKanban) {
    return <KanbanBoardView onClose={() => { setShowKanban(false); reload(); }} onSelectTicket={setSelectedTicketId} />;
  }

  return (
    <div className="pixel-grid-app">
      <div className="pixel-grid-toolbar">
        <div className="sources-header-actions">
          <NewTicketForm users={users} types={types} levels={levels} statuts={statuts} onCreated={reload} onReferenceCreated={handleReferenceCreated} />
          <button className="sources-header-btn" onClick={() => setShowReview(true)}>📋 Revue import</button>
          <button className="sources-header-btn" onClick={() => setShowParallel(true)}>📊 Vue parallèle</button>
          <button className="sources-header-btn" onClick={() => setShowAdmin(true)}>🗄️ Gestion base</button>
          <button className="sources-header-btn" onClick={() => setShowKanban(true)}>🗂️ Kanban</button>
          <button className="sources-header-btn" onClick={() => setShowRules(true)}>⚙️ Règles calendrier</button>
        </div>

        <div className="pixel-grid-controls">
          <span className="pixel-grid-controls-label">Filtrer :</span>
          <select className="geo-input" value={filters.typeId} onChange={(e) => setFilters({ ...filters, typeId: e.target.value })}>
            <option value="">tous types</option>
            {types.map((t) => <option key={t.id} value={t.id}>{t.label}</option>)}
          </select>
          <select className="geo-input" value={filters.userId} onChange={(e) => setFilters({ ...filters, userId: e.target.value })}>
            <option value="">tous demandeurs</option>
            {users.map((u) => <option key={u.id} value={u.id}>{u.login}</option>)}
          </select>
          <select className="geo-input" value={filters.state} onChange={(e) => setFilters({ ...filters, state: e.target.value })}>
            <option value="open">ouverts seulement</option>
            <option value="closed">fermés seulement</option>
            <option value="all">tous (ouverts + fermés)</option>
          </select>
          <select className="geo-input" value={filters.statutId} onChange={(e) => setFilters({ ...filters, statutId: e.target.value })}>
            <option value="">tous statuts</option>
            {statuts.map((s) => <option key={s.id} value={s.id}>{s.label}</option>)}
          </select>
        </div>
      </div>

      <CalendarImportPanel onImported={reload} />

      {loading && <p className="synthesis-empty">Chargement…</p>}

      {!loading && (
        <table className="geo-table">
          <thead>
            <tr>
              <th>Niveau</th><th>Sujet</th><th>Type</th><th>Demandeur</th><th>Statut</th><th>Attente</th><th>Reprises</th>
            </tr>
          </thead>
          <tbody>
            {tickets.map((t) => (
              <tr key={t.id} onClick={() => setSelectedTicketId(t.id)} style={{ cursor: "pointer" }}>
                <td>
                  <span className={`status-dot ${t.level_rank >= 3 ? "unavailable" : t.level_rank >= 2 ? "" : "ok"}`} style={{ marginRight: "0.4rem" }} />
                  {t.level_label || "—"}
                </td>
                <td>#{t.id} — {t.subject}</td>
                <td>{t.type_label || "—"}</td>
                <td>
                  {t.user_login || <span title="Aucun demandeur renseigné" style={{ color: "var(--color-warning, #e0a94c)" }}>⚠️ non renseigné</span>}
                </td>
                <td>
                  {t.statut_label || (t.ts_closed ? "fermé" : "ouvert")}
                  {t.ts_closed && <span title="Ticket fermé" style={{ marginLeft: "0.3rem" }}>🔒</span>}
                </td>
                <td>{formatWait(t.wait_seconds)}</td>
                <td style={{ whiteSpace: "nowrap" }}>
                  {t.segment_count > 1 && (
                    <span className="pixel-grid-level-btn" style={{ fontSize: "0.65rem", marginRight: "0.2rem" }} title={`${t.segment_count} plages horaires distinctes`}>
                      ⏱️ {t.segment_count}
                    </span>
                  )}
                  {t.reopen_count > 0 && (
                    <span className="pixel-grid-level-btn" style={{ fontSize: "0.65rem", marginRight: "0.2rem" }} title={`Rouvert ${t.reopen_count} fois`}>
                      🔁 {t.reopen_count}
                    </span>
                  )}
                  {t.similar_tickets_count > 0 && (
                    <span className="pixel-grid-level-btn" style={{ fontSize: "0.65rem" }} title={`${t.similar_tickets_count} autre(s) ticket(s) au sujet proche, même demandeur — récidive possible`}>
                      ♻️ {t.similar_tickets_count}
                    </span>
                  )}
                  {!t.segment_count && !t.reopen_count && !t.similar_tickets_count && (
                    <span className="pixel-grid-empty-hint">—</span>
                  )}
                </td>
              </tr>
            ))}
            {tickets.length === 0 && (
              <tr><td colSpan={7} className="synthesis-empty">Aucun ticket ne correspond aux filtres.</td></tr>
            )}
          </tbody>
        </table>
      )}
    </div>
  );
}
