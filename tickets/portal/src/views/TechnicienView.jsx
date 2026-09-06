import React, { useEffect, useState } from "react";
import { getJson, postJson, putJson } from "../api.js";
import {
  fmtTs, fmtDuration, datetimeLocalToTs, statusLogSteps, sortByKeywordScore,
  groupByLevel, ticketsByDeadlineUrgency, ticketsByLongestWait, ticketsByLongestInProgress, distinctRanksDesc,
  ganttBounds, segmentGeometry, filterGanttRows,
} from "../lib.js";
import TicketThread from "../components/TicketThread.jsx";
import TicketDocuments from "../components/TicketDocuments.jsx";
import DemandeurView from "./DemandeurView.jsx";

// Vue TECHNICIEN : complète les tickets, fait évoluer leur statut,
// dialogue avec les demandeurs. Réutilise /queue (mêmes tris/filtres
// que la file interne) et PUT /tickets/<id> (fermeture/réouverture
// EXPLICITE uniquement — philosophie du module).
//
// Mise en page revue après retour de design explicite : par défaut
// (aucun ticket sélectionné), colonne GAUCHE = commandes (liste des
// demandeurs + usurpation, voir plus bas), colonne CENTRALE = la
// file d'attente, colonne DROITE = priorités et échéances proches
// ("élastiques de temps"). Dès qu'un ticket est sélectionné, la
// liste bascule à GAUCHE (compacte) et le détail du ticket prend la
// place centrale -- la colonne droite (priorités/échéances) reste
// affichée dans les deux cas, contexte utile qu'on travaille un
// ticket précis ou non.

/** Élément de la file, réutilisé identique en colonne centrale (liste
 * large, par défaut) et en colonne gauche (liste compacte, une fois
 * un ticket sélectionné) -- jamais deux copies du même rendu. */
function QueueItem({ t, selected, onClick }) {
  return (
    <div
      className={`ticket-item${selected ? " selected" : ""}`}
      onClick={onClick}
    >
      <div className="subject">#{t.id} — {t.subject}</div>
      <div className="meta">
        {t.user_login && <span>👤 {t.user_login}</span>}
        {t.level_label && <span className="badge level">{t.level_label}</span>}
        {t.statut_label && <span className="badge">{t.statut_label}</span>}
        {t.ts_closed ? (
          <span className="badge closed">🔒 fermé</span>
        ) : (
          <span>⏳ {fmtDuration(t.wait_seconds)}</span>
        )}
        {t.segment_count > 0 && <span>⏱️ {t.segment_count}</span>}
        {t.reopen_count > 0 && <span>🔁 {t.reopen_count}</span>}
        {t.keyword_score > 0 && (
          <span className="badge keyword" title={t.keyword_matches.join(", ")}>
            🔑 {t.keyword_matches.join(", ")}
          </span>
        )}
      </div>
    </div>
  );
}

// Tableau plein largeur pour la file d'attente -- demandé
// explicitement : quand rien n'est sélectionné (aucune fiche à
// afficher), la colonne centrale doit prendre toute la largeur
// disponible et passer d'un style "carte" compact (QueueItem
// ci-dessus, toujours utilisé pour la file étroite une fois un
// ticket sélectionné) à un vrai tableau avec plus de colonnes
// visibles -- l'espace horizontal le permet.
function QueueTable({ tickets, onSelect }) {
  return (
    <table className="portal-table queue-table">
      <thead>
        <tr>
          <th>#</th>
          <th>Sujet</th>
          <th>Demandeur</th>
          <th>Site</th>
          <th>Type</th>
          <th>Niveau</th>
          <th>Statut</th>
          <th>Attente</th>
        </tr>
      </thead>
      <tbody>
        {tickets.map((t) => (
          <tr key={t.id} className="queue-table-row" onClick={() => onSelect(t.id)}>
            <td>{t.id}</td>
            <td>{t.subject}</td>
            <td>{t.user_login || "—"}</td>
            <td>{t.site_label || "—"}</td>
            <td>{t.type_label || "—"}</td>
            <td>{t.level_label && <span className="badge level">{t.level_label}</span>}</td>
            <td>{t.statut_label && <span className="badge">{t.statut_label}</span>}</td>
            <td>
              {t.ts_closed ? (
                <span className="badge closed">🔒 fermé</span>
              ) : (
                <span>⏳ {fmtDuration(t.wait_seconds)}</span>
              )}
              {t.segment_count > 0 && <span title="segments de temps"> ⏱️{t.segment_count}</span>}
              {t.reopen_count > 0 && <span title="réouvertures"> 🔁{t.reopen_count}</span>}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export default function TechnicienView({ me, initialTicketId }) {
  const [tickets, setTickets] = useState([]);
  const [hasLoadedOnce, setHasLoadedOnce] = useState(false);
  const [refs, setRefs] = useState({ users: [], types: [], levels: [], statuts: [], sites: [] });
  const [filters, setFilters] = useState({ state: "open", type_id: "", statut_id: "", user_id: "" });
  // "server" = tri déjà fait côté API (urgence puis ancienneté) ;
  // "keywords" = EN PLUS de ce tri, reclassé par score de mots-clés —
  // un choix explicite de la personne, jamais le comportement par défaut.
  const [sortMode, setSortMode] = useState("server");
  // initialTicketId (livraison #170) -- lien direct depuis un autre
  // écran (GedView.jsx, "Liaisons" d'un document) : `loadDetail`
  // ci-dessous fait un fetch DIRECT par id (jamais filtré par la
  // file affichée), donc l'initialiser ici suffit -- le ticket
  // s'ouvre même s'il n'apparaît pas dans les filtres par défaut
  // (fermé, autre technicien, etc.).
  const [selectedId, setSelectedId] = useState(initialTicketId || null);
  const [detail, setDetail] = useState(null);
  // Panneau "👥 Demandeurs" replié par défaut -- mise en page
  // adaptative (backlog), même motif "+" que partout ailleurs dans le
  // projet plutôt qu'une colonne fixe qui mangeait 300px en permanence.
  const [showDemandeurs, setShowDemandeurs] = useState(false);
  const [error, setError] = useState(null);
  const [entryStart, setEntryStart] = useState("");
  const [entryEnd, setEntryEnd] = useState("");

  // Gantt et timeline personnelle -- backlog, livraison #115. Repliés
  // par défaut (même motif "+" que Demandeurs ci-dessus), chargés
  // seulement à l'ouverture -- jamais de requête inutile tant que la
  // personne ne les a pas demandés.
  const [showGantt, setShowGantt] = useState(false);
  const [ganttRows, setGanttRows] = useState([]);
  const [ganttFilter, setGanttFilter] = useState("");
  const [showTimeline, setShowTimeline] = useState(false);
  const [myTimeline, setMyTimeline] = useState([]);
  const [myTimelineLoaded, setMyTimelineLoaded] = useState(false);

  // Usurpation -- "le technicien prend des demandes orales et les
  // retranscrit" (demandé explicitement). Réutilise le mécanisme
  // acted_by DÉJÀ existant (voir App.jsx, ActingForDemandeurView et
  // DemandeurView.jsx) -- jamais un vrai changement d'identité
  // Keycloak, juste la vue demandeur normale pour la personne
  // choisie, avec le technicien tracé comme auteur réel.
  const [actingAsId, setActingAsId] = useState(null);

  const loadRefs = async () => {
    const [u, t, l, s, si] = await Promise.all([
      getJson("/users"), getJson("/types"), getJson("/levels"), getJson("/statuts"), getJson("/sites"),
    ]);
    setRefs({
      users: u.ok ? u.data : [],
      types: t.ok ? t.data : [],
      levels: l.ok ? l.data : [],
      statuts: s.ok ? s.data : [],
      sites: si.ok ? si.data : [],
    });
  };

  const loadQueue = async () => {
    const params = new URLSearchParams();
    params.set("state", filters.state);
    if (filters.type_id) params.set("type_id", filters.type_id);
    if (filters.statut_id) params.set("statut_id", filters.statut_id);
    if (filters.user_id) params.set("user_id", filters.user_id);
    const res = await getJson(`/queue?${params.toString()}`);
    if (res.ok) setTickets(res.data.tickets);
    setHasLoadedOnce(true);
  };

  const loadDetail = async (id) => {
    const res = await getJson(`/tickets/${id}`);
    if (res.ok) setDetail(res.data);
  };

  // Gantt -- réutilise TEL QUEL /tickets/parallel (même route que
  // l'écran politique, voir lib.js pour ganttBounds/segmentGeometry),
  // scopé aux tickets ACTUELLEMENT affichés dans la file (mêmes
  // filtres état/type/statut/demandeur déjà appliqués) plutôt qu'à
  // toute la file globale -- backlog, livraison #115.
  const loadGantt = async (ticketIds) => {
    if (!ticketIds || ticketIds.length === 0) {
      setGanttRows([]);
      return;
    }
    const res = await getJson(`/tickets/parallel?ticket_ids=${ticketIds.join(",")}`);
    if (res.ok) setGanttRows(res.data.tickets);
  };

  // Timeline personnelle -- chronologique, mes propres segments à
  // travers TOUS mes tickets (distinct du Gantt, ticket-centrique) --
  // nécessite l'attribution par technicien (technician_login), voir
  // tickets/api/app.py et hub/src/settingsClient.js.
  const loadMyTimeline = async () => {
    if (!me?.login) return;
    const res = await getJson(`/time_entries?technician_login=${encodeURIComponent(me.login)}`);
    if (res.ok) setMyTimeline(res.data.entries);
    setMyTimelineLoaded(true);
  };

  useEffect(() => { loadRefs(); }, []);
  useEffect(() => { loadQueue(); /* eslint-disable-line react-hooks/exhaustive-deps */ }, [filters]);
  useEffect(() => {
    if (selectedId) loadDetail(selectedId);
    else setDetail(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedId]);

  // Rafraîchissement périodique léger -- pour que le panneau
  // "échéances proches" reste à jour même sans action de la
  // personne (le temps continue de s'écouler pendant qu'elle
  // travaille un ticket).
  const [now, setNow] = useState(() => Math.floor(Date.now() / 1000));
  useEffect(() => {
    const id = setInterval(() => setNow(Math.floor(Date.now() / 1000)), 60000);
    return () => clearInterval(id);
  }, []);

  const displayedTickets = sortMode === "keywords" ? sortByKeywordScore(tickets) : tickets;

  // Rechargé sur `tickets` (référence stable, ne change QUE quand
  // loadQueue reçoit vraiment de nouvelles données) plutôt que
  // `displayedTickets` (nouveau tableau à CHAQUE rendu, provoquerait
  // une requête à chaque frappe/interaction sans rapport) -- l'ordre
  // de tri n'affecte de toute façon pas le JEU d'ids demandé ici.
  useEffect(() => {
    if (!showGantt) return;
    loadGantt(tickets.map((t) => t.id));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [showGantt, tickets]);

  useEffect(() => {
    if (!showTimeline) return;
    loadMyTimeline();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [showTimeline]);

  const priorityGroups = groupByLevel(tickets.filter((t) => !t.ts_closed));
  const filteredGanttRows = filterGanttRows(ganttRows, ganttFilter);
  const technicienGanttBounds = ganttBounds(filteredGanttRows);
  // Rangs distincts depuis la liste COMPLÈTE des niveaux connus
  // (refs.levels), jamais seulement ceux présents dans les tickets
  // filtrés/affichés -- pour que la correspondance J+N par position
  // (voir lib.js) reste stable quel que soit le filtre actif.
  const levelRanksDesc = distinctRanksDesc(refs.levels);
  const urgentDeadlines = ticketsByDeadlineUrgency(tickets, now, { sortedDistinctRanksDesc: levelRanksDesc });
  const longestWaiting = ticketsByLongestWait(tickets, 5);
  const longestInProgress = ticketsByLongestInProgress(tickets, 5);

  const demandeurs = refs.users.filter((u) => u.role === "demandeur");
  const actingUser = demandeurs.find((d) => String(d.id) === String(actingAsId));

  const startActing = (userId) => {
    setSelectedId(null); // jamais les deux modes en même temps
    setActingAsId(userId);
  };
  const stopActing = () => setActingAsId(null);

  const selectTicket = (id) => {
    setActingAsId(null); // jamais les deux modes en même temps
    setSelectedId(id);
  };

  const updateField = async (field, value) => {
    if (!detail) return;
    const res = await putJson(`/tickets/${detail.id}`, { [field]: value === "" ? null : Number(value) });
    if (res.ok) {
      await loadDetail(detail.id);
      await loadQueue();
    } else {
      setError(res.data.error || "mise à jour impossible");
    }
  };

  const closeTicket = async () => {
    if (!detail) return;
    if (!window.confirm(`Fermer le ticket #${detail.id} ?`)) return;
    const res = await putJson(`/tickets/${detail.id}`, { ts_closed: Math.round(Date.now() / 1000) });
    if (res.ok) { await loadDetail(detail.id); await loadQueue(); }
  };

  const reopenTicket = async () => {
    if (!detail) return;
    if (!window.confirm(`Rouvrir le ticket #${detail.id} ?`)) return;
    const res = await putJson(`/tickets/${detail.id}`, { ts_closed: null });
    if (res.ok) { await loadDetail(detail.id); await loadQueue(); }
  };

  const addTimeEntry = async () => {
    const start = datetimeLocalToTs(entryStart);
    const end = datetimeLocalToTs(entryEnd);
    if (!detail || start === null || end === null) return;
    if (end <= start) {
      setError("la fin doit être après le début");
      return;
    }
    const res = await postJson(`/tickets/${detail.id}/time_entries`, {
      start_ts: start, end_ts: end, technician_login: me?.login,
    });
    if (res.ok) {
      setEntryStart("");
      setEntryEnd("");
      setError(null);
      await loadDetail(detail.id);
    } else {
      setError(res.data.error || "saisie impossible");
    }
  };

  // Mode usurpation -- remplace ENTIÈREMENT la vue technicien tant
  // qu'actif, jamais superposé (la personne saisit VRAIMENT pour le
  // compte d'un demandeur, pas de confusion possible avec le reste
  // de l'écran technicien).
  if (actingUser) {
    return (
      <div>
        <div className="acted-by-banner">
          ✍️ Vous saisissez pour le compte de <strong>{actingUser.name || actingUser.login}</strong> —
          tout ce que vous créez ici apparaît chez cette personne, avec votre nom tracé comme auteur réel.{" "}
          <button className="secondary" onClick={stopActing}>◀ Revenir à la vue technicien</button>
        </div>
        <DemandeurView me={actingUser} actedBy={me} />
      </div>
    );
  }

  return (
    <div>
      <div className="filters-bar">
        <select value={filters.state} onChange={(e) => setFilters({ ...filters, state: e.target.value })}>
          <option value="open">Ouverts</option>
          <option value="closed">Fermés</option>
          <option value="all">Tous</option>
        </select>
        <select value={filters.type_id} onChange={(e) => setFilters({ ...filters, type_id: e.target.value })}>
          <option value="">Type : tous</option>
          {refs.types.map((t) => <option key={t.id} value={t.id}>{t.label}</option>)}
        </select>
        <select value={filters.statut_id} onChange={(e) => setFilters({ ...filters, statut_id: e.target.value })}>
          <option value="">Statut : tous</option>
          {refs.statuts.map((s) => <option key={s.id} value={s.id}>{s.label}</option>)}
        </select>
        <select value={filters.user_id} onChange={(e) => setFilters({ ...filters, user_id: e.target.value })}>
          <option value="">Demandeur : tous</option>
          {refs.users.map((u) => <option key={u.id} value={u.id}>{u.login}</option>)}
        </select>
        <select value={sortMode} onChange={(e) => setSortMode(e.target.value)} title="En plus du tri urgence/attente déjà appliqué">
          <option value="server">Tri : urgence puis attente</option>
          <option value="keywords">Tri : mots-clés en tête</option>
        </select>
      </div>

      <div className="technicien-layout">
        {!selectedId ? (
          // Mise en page adaptative -- demandé explicitement : quand
          // le panneau détail est vide (rien de sélectionné), la
          // file d'attente prend TOUTE la largeur (une seule colonne
          // ici, plus le partage fixe side-col/center-col/priority-col
          // ci-dessous) et reste en style TABLE (QueueTable, déjà
          // construit) plutôt que cartes compactes -- plus de
          // colonnes visibles d'un coup d'œil, la place le permet.
          // "👥 Demandeurs" (utile pour retranscrire un appel
          // téléphonique) repliait auparavant 300px en PERMANENCE
          // dans une colonne dédiée, même sans jamais s'en servir --
          // replié par défaut ici, même motif "+" que partout
          // ailleurs dans le projet (voir vault, DBA...), pour ne
          // plus jamais rogner sur la largeur de la file par défaut.
          <div className="technicien-full-col">
            <div className="panel">
              <div className="panel-header-row">
                <h2>🧰 File d'attente</h2>
                <button
                  className="secondary"
                  onClick={() => setShowDemandeurs((v) => !v)}
                  title={showDemandeurs ? "Masquer" : "Retranscrire une demande reçue par téléphone"}
                >
                  {showDemandeurs ? "✕ Fermer" : "👥 Demandeurs"}
                </button>
              </div>
              {showDemandeurs && (
                <div className="technicien-demandeurs-panel">
                  <p className="muted">
                    Pour retranscrire une demande reçue par téléphone : choisissez la
                    personne, vous basculerez sur sa vue demandeur habituelle.
                  </p>
                  {demandeurs.length === 0 && <p className="muted">Aucun demandeur.</p>}
                  {demandeurs.map((u) => (
                    <div key={u.id} className="ticket-item technicien-demandeur-row">
                      <span>👤 {u.name || u.login}</span>
                      <button className="secondary" onClick={() => startActing(u.id)}>🎭 Usurper</button>
                    </div>
                  ))}
                </div>
              )}
              {!hasLoadedOnce && <p className="muted">Chargement…</p>}
              {hasLoadedOnce && displayedTickets.length === 0 && <p className="muted">Rien dans cette vue.</p>}
              {hasLoadedOnce && displayedTickets.length > 0 && (
                <QueueTable tickets={displayedTickets} onSelect={selectTicket} />
              )}
            </div>
          </div>
        ) : (
        <>
        <div className="technicien-side-col">
          <div className="panel">
            <h2>🧰 File d'attente</h2>
            {!hasLoadedOnce && <p className="muted">Chargement…</p>}
            {hasLoadedOnce && displayedTickets.length === 0 && <p className="muted">Rien dans cette vue.</p>}
            {displayedTickets.map((t) => (
              <QueueItem key={t.id} t={t} selected={t.id === selectedId} onClick={() => selectTicket(t.id)} />
            ))}
          </div>
        </div>

        <div className="technicien-center-col">
          {!detail && (
            <div className="panel">
              <p className="muted">Chargement du ticket…</p>
            </div>
          )}
          {detail && (
            <div className="panel">
              <h2>#{detail.id} — {detail.subject}</h2>
              {detail.description && <p>{detail.description}</p>}

              <div className="form-row">
                <label>Statut</label>
                <select
                  value={detail.statut_id ?? ""}
                  onChange={(e) => updateField("statut_id", e.target.value)}
                >
                  <option value="">(aucun)</option>
                  {refs.statuts.map((s) => <option key={s.id} value={s.id}>{s.label}</option>)}
                </select>
                <label>Niveau</label>
                <select
                  value={detail.level_id ?? ""}
                  onChange={(e) => updateField("level_id", e.target.value)}
                >
                  <option value="">(aucun)</option>
                  {refs.levels.map((l) => <option key={l.id} value={l.id}>{l.label}</option>)}
                </select>
                <label>Type</label>
                <select
                  value={detail.type_id ?? ""}
                  onChange={(e) => updateField("type_id", e.target.value)}
                >
                  <option value="">(aucun)</option>
                  {refs.types.map((t) => <option key={t.id} value={t.id}>{t.label}</option>)}
                </select>
                <label>Site</label>
                <select
                  value={detail.site_id ?? ""}
                  onChange={(e) => updateField("site_id", e.target.value)}
                >
                  <option value="">(aucun)</option>
                  {refs.sites.map((s) => <option key={s.id} value={s.id}>{s.label}</option>)}
                </select>
              </div>

              <div className="form-actions" style={{ marginTop: 10 }}>
                {detail.ts_closed ? (
                  <button onClick={reopenTicket}>🔓 Rouvrir</button>
                ) : (
                  <button className="danger" onClick={closeTicket}>🔒 Fermer le ticket</button>
                )}
                <button className="secondary" onClick={() => setSelectedId(null)}>◀ Retour à la file</button>
              </div>

              <h3>📈 Évolution</h3>
              <div className="status-steps">
                {statusLogSteps(detail.status_log).map((s, i) => (
                  <React.Fragment key={i}>
                    {i > 0 && <span className="status-arrow">→</span>}
                    <span className={`status-step ${s.kind}`}>
                      {s.label}<span className="ts">{fmtTs(s.ts)}</span>
                    </span>
                  </React.Fragment>
                ))}
              </div>

              <h3>⏱️ Temps passé — {fmtDuration(detail.total_seconds)}</h3>
              {detail.time_entries.length === 0 && <p className="muted">Aucun segment.</p>}
              {detail.time_entries.map((e) => (
                <div key={e.id} className="hint">
                  {fmtTs(e.start_ts)} → {fmtTs(e.end_ts)}
                  {e.weight !== 1 && ` (pondération ${e.weight})`}
                </div>
              ))}
              <div className="form-row" style={{ marginTop: 6 }}>
                <input type="datetime-local" value={entryStart} onChange={(e) => setEntryStart(e.target.value)} />
                <span className="muted">→</span>
                <input type="datetime-local" value={entryEnd} onChange={(e) => setEntryEnd(e.target.value)} />
                <button onClick={addTimeEntry} disabled={!entryStart || !entryEnd}>
                  ➕ Ajouter ce segment
                </button>
              </div>
              <p className="hint">
                Le rattachement automatique depuis l'agenda reste dans l'écran
                de revue du module interne — ici, saisie manuelle uniquement.
              </p>

              {detail.children.length > 0 && (
                <>
                  <h3>🧩 Sous-demandes</h3>
                  {detail.children.map((c) => (
                    <div key={c.id} className="ticket-item" onClick={() => selectTicket(c.id)}>
                      <div className="subject">#{c.id} — {c.subject}</div>
                      <div className="meta">
                        <span className={`badge ${c.ts_closed ? "closed" : "open"}`}>
                          {c.ts_closed ? "Fermée" : "Ouverte"}
                        </span>
                      </div>
                    </div>
                  ))}
                </>
              )}

              {error && <p className="error-text">{error}</p>}

              <TicketThread ticketId={detail.id} me={me} />
              <TicketDocuments ticketId={detail.id} me={me} />
            </div>
          )}
        </div>

        <div className="technicien-priority-col">
          <div className="panel">
            <h3>🎯 Priorités</h3>
            {priorityGroups.length === 0 && <p className="muted">Aucun ticket ouvert.</p>}
            {priorityGroups.map((g) => (
              <div key={g.label} className="priority-row">
                <span>{g.label}</span>
                <span className="badge">{g.count}</span>
              </div>
            ))}
          </div>
          <div className="panel">
            <h3>⏳ En attente (sans prise en charge)</h3>
            {longestWaiting.length === 0 && <p className="muted">Aucun ticket ouvert.</p>}
            {longestWaiting.map((t) => (
              <div key={t.id} className="ticket-item" onClick={() => selectTicket(t.id)}>
                <div className="subject">#{t.id} — {t.subject}</div>
                <div className="meta"><span>⏳ {fmtDuration(t.wait_seconds)}</span></div>
              </div>
            ))}
          </div>
          <div className="panel">
            <h3>🔧 En cours depuis</h3>
            <p className="muted hint">
              "Prise en charge" = premier passage à un statut de type "en cours" (voir Admin →
              Statuts). Un ticket jamais passé par un tel statut n'apparaît pas ici -- voir
              "⏳ En attente" ci-dessus.
            </p>
            {longestInProgress.length === 0 && <p className="muted">Aucun ticket pris en charge pour l'instant.</p>}
            {longestInProgress.map((t) => (
              <div key={t.id} className="ticket-item" onClick={() => selectTicket(t.id)}>
                <div className="subject">#{t.id} — {t.subject}</div>
                <div className="meta"><span>🔧 {fmtDuration(now - t.first_in_progress_ts)}</span></div>
              </div>
            ))}
          </div>
          <div className="panel">
            <h3>⏰ Échéances proches</h3>
            <p className="muted hint">
              Fenêtre : 48h avant échéance. "≈" = échéance non saisie, déduite du
              niveau (bêta) — voir tickets/README.md.
            </p>
            {urgentDeadlines.length === 0 && <p className="muted">Rien d'imminent.</p>}
            {urgentDeadlines.map(({ ticket: t, urgency: u }) => (
              <div key={t.id} className="deadline-elastic-row" onClick={() => selectTicket(t.id)}>
                <div className="deadline-elastic-label">
                  {u.implied ? "≈ " : ""}#{t.id} — {t.subject}
                </div>
                <div className="deadline-elastic-track">
                  <div
                    className={`deadline-elastic-fill${u.overdue ? " overdue" : ""}`}
                    style={{ width: `${Math.round(u.ratio * 100)}%` }}
                  />
                </div>
                <div className="deadline-elastic-time">
                  {u.overdue
                    ? `dépassée depuis ${fmtDuration(-u.hoursRemaining * 3600)}`
                    : `${fmtDuration(u.hoursRemaining * 3600)} restant`}
                </div>
              </div>
            ))}
          </div>
        </div>
        </>
        )}
      </div>

      <div className="panel">
        <div className="panel-header-row">
          <h2>📊 Gantt — ma file</h2>
          <button className="secondary" onClick={() => setShowGantt((v) => !v)}>
            {showGantt ? "✕ Fermer" : "Afficher"}
          </button>
        </div>
        {showGantt && (
          <>
            <div className="filters-bar">
              <input
                placeholder="Filtrer les lignes…"
                value={ganttFilter}
                onChange={(e) => setGanttFilter(e.target.value)}
              />
            </div>
            {technicienGanttBounds && (
              <div className="gantt-scale">
                <span>{fmtTs(technicienGanttBounds.min)}</span>
                <span>{fmtTs(technicienGanttBounds.max)}</span>
              </div>
            )}
            {filteredGanttRows.length === 0 && <p className="muted">Aucune ligne à afficher.</p>}
            {filteredGanttRows.map((row) => (
              <div key={row.id} className="gantt-row">
                <div className="gantt-label" title={row.subject}>
                  #{row.id} — {row.subject}
                </div>
                <div className="gantt-track">
                  {technicienGanttBounds && row.time_entries.map((e, i) => {
                    const g = segmentGeometry(e, technicienGanttBounds);
                    return (
                      <div
                        key={i}
                        className="gantt-seg"
                        style={{ left: `${g.left}%`, width: `${g.width}%` }}
                        title={`${fmtTs(e.start_ts)} → ${fmtTs(e.end_ts)}`}
                      />
                    );
                  })}
                  {row.time_entries.length === 0 && (
                    <span className="gantt-empty" style={{ paddingLeft: 6 }}>aucun temps saisi</span>
                  )}
                </div>
              </div>
            ))}
          </>
        )}
      </div>

      <div className="panel">
        <div className="panel-header-row">
          <h2>📅 Ma timeline</h2>
          <button className="secondary" onClick={() => setShowTimeline((v) => !v)}>
            {showTimeline ? "✕ Fermer" : "Afficher"}
          </button>
        </div>
        {showTimeline && (
          <>
            {!myTimelineLoaded && <p className="muted">Chargement…</p>}
            {myTimelineLoaded && myTimeline.length === 0 && (
              <p className="muted">Aucun temps saisi pour l'instant.</p>
            )}
            {myTimeline.length > 0 && (
              <ul className="technicien-timeline-list">
                {myTimeline.map((e) => (
                  <li key={e.id} className="technicien-timeline-item">
                    <span className="technicien-timeline-time">
                      {fmtTs(e.start_ts)} → {fmtTs(e.end_ts)}
                    </span>
                    <span className="technicien-timeline-subject">#{e.ticket_id} — {e.ticket_subject}</span>
                    <span className="muted">{fmtDuration(e.end_ts - e.start_ts)}</span>
                  </li>
                ))}
              </ul>
            )}
          </>
        )}
      </div>
    </div>
  );
}
