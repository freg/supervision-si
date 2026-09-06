import React, { useEffect, useMemo, useState } from "react";
import { getJson, postJson } from "../api.js";
import {
  fmtTs, fmtTsShort, statusLogSteps,
  sortTickets, nextSortState, TICKET_SORT_COLUMNS,
  ganttBounds, segmentGeometry, ticketToDraftFields,
} from "../lib.js";
import TicketThread from "../components/TicketThread.jsx";
import TicketDocuments from "../components/TicketDocuments.jsx";
import { postHubEvent } from "../hubEvents.js";

const PREFS_API_BASE_URL = import.meta.env.VITE_PREFS_API_BASE_URL || "";

// Vue DEMANDEUR (client) : crée sa demande -> ticket, suit son
// évolution, ajoute des sous-demandes et dialogue façon forum/chat.
//
// Mise en page revue après retour explicite : le tableau des demandes
// occupe désormais le CENTRE (large, colonne principale), le détail
// devient la colonne secondaire à droite -- inverse de la disposition
// d'origine (formulaire+tableau à gauche en largeur fixe, détail à
// droite en largeur flexible). La ligne "nouvelle demande" est
// désormais COLLANTE en tête du tableau lui-même (jamais un panneau
// séparé) : reste visible pendant qu'on fait défiler les anciens
// tickets, pour pouvoir s'en inspirer sans perdre le formulaire de
// vue -- demandé explicitement.
export default function DemandeurView({ me, actedBy }) {
  const [tickets, setTickets] = useState([]);
  const [hasLoadedOnce, setHasLoadedOnce] = useState(false);
  const [types, setTypes] = useState([]);
  const [sites, setSites] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [detail, setDetail] = useState(null);
  const [error, setError] = useState(null);
  // Tri par défaut : état (ouverts en priorité, demandé explicitement).
  const [sort, setSort] = useState({ key: "state", dir: "asc" });

  const [ganttRows, setGanttRows] = useState([]);
  const [showGantt, setShowGantt] = useState(false);

  // formulaire nouvelle demande -- désormais intégré à la ligne
  // collante du tableau (voir rendu plus bas), jamais un panneau
  // séparé.
  const [subject, setSubject] = useState("");
  const [description, setDescription] = useState("");
  const [typeId, setTypeId] = useState("");
  const [siteId, setSiteId] = useState("");
  const [deadline, setDeadline] = useState(""); // <input type="datetime-local">, chaîne locale
  const [creating, setCreating] = useState(false);
  // Échéance/détails repliés par défaut (ligne collante compacte) --
  // rouvert automatiquement par handleRecopier si le ticket recopié
  // avait des détails, pour ne jamais les cacher silencieusement.
  const [showMoreFields, setShowMoreFields] = useState(false);

  // sous-demande inline
  const [subSubject, setSubSubject] = useState("");

  const loadTickets = async () => {
    const res = await getJson(`/queue?state=all&user_id=${me.id}`);
    if (res.ok) setTickets(res.data.tickets);
    setHasLoadedOnce(true);
  };

  const loadGantt = async () => {
    const res = await getJson(`/tickets/parallel?group_by=ticket&user_id=${me.id}`);
    if (res.ok) setGanttRows(res.data.tickets);
  };

  const loadDetail = async (id) => {
    const res = await getJson(`/tickets/${id}`);
    if (res.ok) setDetail(res.data);
  };

  useEffect(() => {
    loadTickets();
    loadGantt();
    getJson("/types").then((r) => r.ok && setTypes(r.data));
    getJson("/sites").then((r) => r.ok && setSites(r.data));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (selectedId) loadDetail(selectedId);
    else setDetail(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedId]);

  const createDemande = async () => {
    const s = subject.trim();
    if (!s || creating) return;
    setCreating(true);
    setError(null);
    const res = await postJson("/tickets", {
      user_id: me.id,
      subject: s,
      description: description.trim() || null,
      type_id: typeId ? Number(typeId) : null,
      site_id: siteId ? Number(siteId) : null,
      // datetime-local -> epoch secondes ; new Date("YYYY-MM-DDTHH:mm")
      // interprète la chaîne en heure LOCALE du navigateur, cohérent
      // avec ce que la personne a réellement saisi dans le champ.
      deadline_ts: deadline ? Math.floor(new Date(deadline).getTime() / 1000) : null,
      source_type: "portal",
      ...(actedBy ? { acted_by_user_id: actedBy.id } : {}),
    });
    setCreating(false);
    if (res.ok) {
      setSubject("");
      setDescription("");
      setTypeId("");
      setSiteId("");
      setDeadline("");
      setShowMoreFields(false);
      // Timeline hub (backlog, livraison #119) -- attribué au
      // véritable acteur (le technicien s'il usurpe la vue demandeur,
      // même raisonnement que acted_by_user_id ci-dessus), jamais
      // bloquant pour la création elle-même (déjà réussie ici).
      postHubEvent(PREFS_API_BASE_URL, {
        login: actedBy?.login || me.login, category: "ticket_cree", label: `#${res.data.id} — ${s}`,
      });
      await loadTickets();
      await loadGantt();
      setSelectedId(res.data.id);
    } else {
      setError(res.data.error || "création impossible");
    }
  };

  const createSousDemande = async () => {
    const s = subSubject.trim();
    if (!s || !detail) return;
    const res = await postJson("/tickets", {
      user_id: me.id,
      subject: s,
      parent_ticket_id: detail.id,
      source_type: "portal",
      ...(actedBy ? { acted_by_user_id: actedBy.id } : {}),
    });
    if (res.ok) {
      setSubSubject("");
      postHubEvent(PREFS_API_BASE_URL, {
        login: actedBy?.login || me.login, category: "ticket_cree", label: `#${res.data.id} — ${s}`,
        data: { parentTicketId: detail.id },
      });
      await loadDetail(detail.id);
      await loadTickets();
    } else {
      setError(res.data.error || "sous-demande impossible");
    }
  };

  // "Recopier" -- demandé explicitement : préremplit la ligne collante
  // de nouvelle demande avec le contenu du ticket actuellement
  // sélectionné, jamais un envoi automatique (la personne relit/
  // ajuste avant de valider elle-même). Rouvre les champs
  // étendus si le ticket recopié avait des détails, pour ne jamais
  // les laisser invisiblement recopiés.
  const handleRecopier = () => {
    if (!detail) return;
    const draft = ticketToDraftFields(detail);
    setSubject(draft.subject);
    setDescription(draft.description);
    setTypeId(draft.typeId);
    setSiteId(draft.siteId);
    if (draft.description) setShowMoreFields(true);
  };

  const roots = useMemo(() => tickets.filter((t) => !t.parent_ticket_id), [tickets]);
  const sortedRoots = useMemo(() => sortTickets(roots, sort.key, sort.dir), [roots, sort]);
  const ganttBoundsValue = useMemo(() => ganttBounds(ganttRows), [ganttRows]);
  const columnCount = Object.keys(TICKET_SORT_COLUMNS).length;

  const headerClick = (key) => setSort((prev) => nextSortState(prev, key));
  const sortIndicator = (key) => (sort.key === key ? (sort.dir === "asc" ? " ▲" : " ▼") : "");

  return (
    <>
      {actedBy && (
        <div className="acted-by-banner">
          ✍️ Vous saisissez pour le compte de <strong>{me.name || me.login}</strong> —
          tout ce que vous créez ici (demandes, messages) apparaît chez cette
          personne, avec votre nom tracé comme auteur réel.
        </div>
      )}
      <div className="demandeur-layout">
        <div className="demandeur-table-col">
          <div className="panel-header-row">
            <h2>📋 Mes demandes</h2>
            <div className="panel-header-actions">
              {detail && !showGantt && (
                <button
                  className="secondary"
                  onClick={handleRecopier}
                  title="Préremplir la ligne de nouvelle demande ci-dessus avec le contenu de ce ticket"
                >
                  📋 Recopier vers une nouvelle demande
                </button>
              )}
              <button onClick={() => setShowGantt((v) => !v)}>
                {showGantt ? "📋 Voir la liste" : "📊 Voir le Gantt"}
              </button>
            </div>
          </div>

          {error && <p className="error-text">{error}</p>}

          {!showGantt && (
            <div className="table-scroll">
              <div className="new-request-bar">
                <div className="new-request-compact">
                  <input
                    value={subject}
                    onChange={(e) => setSubject(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && createDemande()}
                    placeholder="➕ Nouvelle demande — résumé du besoin ou de l'incident"
                  />
                  <select value={typeId} onChange={(e) => setTypeId(e.target.value)}>
                    <option value="">(type non précisé)</option>
                    {types.map((t) => (
                      <option key={t.id} value={t.id}>{t.label}</option>
                    ))}
                  </select>
                  <select value={siteId} onChange={(e) => setSiteId(e.target.value)}>
                    <option value="">(site non précisé)</option>
                    {sites.map((s) => (
                      <option key={s.id} value={s.id}>{s.label}</option>
                    ))}
                  </select>
                  <button
                    type="button"
                    className="new-request-toggle"
                    onClick={() => setShowMoreFields((v) => !v)}
                    title="Échéance, détails"
                  >
                    {showMoreFields ? "▾" : "▸"} détails
                  </button>
                  <button className="primary" onClick={createDemande} disabled={creating || !subject.trim()}>
                    Envoyer
                  </button>
                </div>
                {showMoreFields && (
                  <div className="new-request-expanded">
                    <div className="form-row">
                      <label>Échéance</label>
                      <input
                        type="datetime-local"
                        value={deadline}
                        onChange={(e) => setDeadline(e.target.value)}
                        title="Optionnel — l'urgence du ticket montera automatiquement à l'approche de cette échéance, selon les règles configurées par l'administration"
                      />
                    </div>
                    <div className="form-row">
                      <label>Détails</label>
                      <textarea
                        rows={2}
                        value={description}
                        onChange={(e) => setDescription(e.target.value)}
                        placeholder="Contexte, depuis quand, ce qui a été tenté…"
                      />
                    </div>
                  </div>
                )}
              </div>
              <table className="portal-table">
                <thead>
                  <tr>
                    {Object.entries(TICKET_SORT_COLUMNS).map(([key, label]) => (
                      <th key={key} className="sortable sticky-th" onClick={() => headerClick(key)}>
                        {label}{sortIndicator(key)}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {!hasLoadedOnce && (
                    <tr><td colSpan={columnCount} className="muted">Chargement…</td></tr>
                  )}
                  {hasLoadedOnce && sortedRoots.length === 0 && (
                    <tr><td colSpan={columnCount} className="muted">Aucune demande pour l'instant.</td></tr>
                  )}
                  {sortedRoots.map((t) => (
                    <tr
                      key={t.id}
                      className={t.id === selectedId ? "selected" : ""}
                      onClick={() => setSelectedId(t.id)}
                    >
                      <td>
                        <span className={`badge ${t.ts_closed ? "closed" : "open"}`}>
                          {t.ts_closed ? "Fermée" : "Ouverte"}
                        </span>
                      </td>
                      <td>#{t.id} — {t.subject}</td>
                      <td>{t.statut_label || "—"}</td>
                      <td>{fmtTsShort(t.ts_created)}</td>
                      <td>{fmtTsShort(t.last_change)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {showGantt && (
            <div className="panel">
              {ganttBoundsValue && (
                <div className="gantt-scale">
                  <span>{fmtTs(ganttBoundsValue.min)}</span>
                  <span>{fmtTs(ganttBoundsValue.max)}</span>
                </div>
              )}
              {ganttRows.length === 0 && <p className="muted">Aucun temps encore saisi sur vos demandes.</p>}
              {ganttRows.map((row) => (
                <div key={row.id} className="gantt-row" onClick={() => setSelectedId(row.id)}>
                  <div className="gantt-label" title={row.subject}>#{row.id} — {row.subject}</div>
                  <div className="gantt-track">
                    {ganttBoundsValue && row.time_entries.map((e, i) => {
                      const g = segmentGeometry(e, ganttBoundsValue);
                      return (
                        <div key={i} className="gantt-seg" style={{ left: `${g.left}%`, width: `${g.width}%` }}
                             title={`${fmtTs(e.start_ts)} → ${fmtTs(e.end_ts)}`} />
                      );
                    })}
                    {row.time_entries.length === 0 && (
                      <span className="gantt-empty" style={{ paddingLeft: 6 }}>aucun temps saisi</span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {detail && (
        <div className="demandeur-detail-col">
          {detail && (
            <div className="panel">
              <h2>#{detail.id} — {detail.subject}</h2>
              {detail.site_label && <p className="hint">📍 {detail.site_label}</p>}
              {detail.description && <p>{detail.description}</p>}

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
                {detail.status_log.length === 0 && <span className="muted">—</span>}
              </div>

              <h3>🧩 Sous-demandes</h3>
              {detail.children.length === 0 && (
                <p className="muted">Aucune sous-demande.</p>
              )}
              {detail.children.map((c) => (
                <div key={c.id} className="ticket-item" onClick={() => setSelectedId(c.id)}>
                  <div className="subject">#{c.id} — {c.subject}</div>
                  <div className="meta">
                    <span className={`badge ${c.ts_closed ? "closed" : "open"}`}>
                      {c.ts_closed ? "Fermée" : "Ouverte"}
                    </span>
                    <span>créée {fmtTsShort(c.ts_created)}</span>
                  </div>
                </div>
              ))}
              <div className="form-row">
                <input
                  value={subSubject}
                  onChange={(e) => setSubSubject(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && createSousDemande()}
                  placeholder="Ajouter une sous-demande liée… (Entrée = créer)"
                />
                <button onClick={createSousDemande} disabled={!subSubject.trim()}>➕</button>
              </div>
              {detail.parent_ticket_id && (
                <p className="hint">
                  Cette demande est une sous-demande de{" "}
                  <a href="#" onClick={(e) => { e.preventDefault(); setSelectedId(detail.parent_ticket_id); }}>
                    #{detail.parent_ticket_id}
                  </a>.
                </p>
              )}

              <TicketThread ticketId={detail.id} me={me} actedBy={actedBy} />
              <TicketDocuments ticketId={detail.id} me={me} />
            </div>
          )}
        </div>
        )}
      </div>
    </>
  );
}
