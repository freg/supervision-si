import { useEffect, useRef, useState } from "react";
import {
  fetchCalendarEvents, assignEvents, fetchQueue, fetchSettings, updateSettings,
  fetchUsers, fetchTypes, fetchLevels, fetchStatuts,
  createTicket, createUser, createType, createLevel, createStatut,
  suggestNameForEvents, mineCandidates, fetchTitleMatches, fetchTermSynthesis,
} from "./ticketsApi.js";
import CreatableSelect from "./CreatableSelect.jsx";

function formatDuration(startTs, endTs) {
  const seconds = endTs - startTs;
  if (seconds < 3600) return `${Math.round(seconds / 60)}min`;
  return `${(seconds / 3600).toFixed(1)}h`;
}

/**
 * Regroupe les événements au titre strictement identique — cas
 * typique : le même ticket traité sur plusieurs plages horaires
 * distinctes (ex: "SAV Didier/SMS" répété à chaque reprise). Préserve
 * l'ordre de tri déjà appliqué côté serveur (position du premier
 * exemplaire rencontré = position du groupe).
 */
function groupDuplicateEvents(events) {
  const groups = [];
  const indexByKey = new Map();
  for (const e of events) {
    const key = (e.summary || "").trim().toLowerCase();
    if (key && indexByKey.has(key)) {
      groups[indexByKey.get(key)].events.push(e);
    } else {
      if (key) indexByKey.set(key, groups.length);
      groups.push({ key: key || `__unique_${e.id}`, events: [e] });
    }
  }
  return groups;
}

/**
 * Division verticale redimensionnable — pour équilibrer l'espace entre
 * "créer un ticket" (plus d'espace par défaut) et "tickets reconnus"
 * (liste existante), avec une limite qu'on peut faire glisser.
 */
function ResizableSplit({ top, bottom, defaultTopPercent = 62, height = 480 }) {
  const [topPercent, setTopPercent] = useState(defaultTopPercent);
  const containerRef = useRef(null);
  const draggingRef = useRef(false);

  function startDrag(e) {
    draggingRef.current = true;
    e.preventDefault();
  }

  useEffect(() => {
    function onMove(e) {
      if (!draggingRef.current || !containerRef.current) return;
      const rect = containerRef.current.getBoundingClientRect();
      const pct = ((e.clientY - rect.top) / rect.height) * 100;
      setTopPercent(Math.min(85, Math.max(15, pct)));
    }
    function onUp() {
      draggingRef.current = false;
    }
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    return () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
  }, []);

  return (
    <div ref={containerRef} style={{ display: "flex", flexDirection: "column", height }}>
      <div style={{ height: `${topPercent}%`, overflowY: "auto", minHeight: 0 }}>{top}</div>
      <div
        onMouseDown={startDrag}
        title="Glisser pour redimensionner"
        style={{
          height: 7, cursor: "row-resize", background: "var(--color-border)",
          flexShrink: 0, borderRadius: 3, margin: "3px 0",
        }}
      />
      <div style={{ height: `${100 - topPercent}%`, overflowY: "auto", minHeight: 0 }}>{bottom}</div>
    </div>
  );
}

export default function CalendarReviewView({ onClose, onAssigned }) {
  const [events, setEvents] = useState([]);
  const [tickets, setTickets] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedEventIds, setSelectedEventIds] = useState(new Set());
  const [selectedTicketIds, setSelectedTicketIds] = useState(new Set());
  const [mode, setMode] = useState("full");
  const [triggerKeyword, setTriggerKeyword] = useState("SAV");
  const [savingKeyword, setSavingKeyword] = useState(false);
  const [assigning, setAssigning] = useState(false);
  const [ticketFilter, setTicketFilter] = useState("");

  const [users, setUsers] = useState([]);
  const [types, setTypes] = useState([]);
  const [levels, setLevels] = useState([]);
  const [statuts, setStatuts] = useState([]);
  const [newTicket, setNewTicket] = useState({ subject: "", user_id: "", type_id: "", level_id: "", statut_id: "" });
  const [creatingTicketSaving, setCreatingTicketSaving] = useState(false);
  const [sortMode, setSortMode] = useState("relevance");
  const [suggestedName, setSuggestedName] = useState("");
  const [showMining, setShowMining] = useState(false);
  const [miningResult, setMiningResult] = useState(null);
  const [miningLoading, setMiningLoading] = useState(false);
  const [autoSweepNotice, setAutoSweepNotice] = useState(null);
  const [showTitleMatches, setShowTitleMatches] = useState(false);
  const [titleMatches, setTitleMatches] = useState(null);
  const [titleMatchesLoading, setTitleMatchesLoading] = useState(false);
  const [applyingMatch, setApplyingMatch] = useState(null);
  const [synthesisTerm, setSynthesisTerm] = useState(null);
  const [synthesisData, setSynthesisData] = useState(null);
  const [synthesisLoading, setSynthesisLoading] = useState(false);
  const [includeClosedTickets, setIncludeClosedTickets] = useState(false);
  const [reopenOnAssign, setReopenOnAssign] = useState(false);

  async function reload() {
    setLoading(true);
    const [evts, settings, allOpenTickets, u, ty, l, s] = await Promise.all([
      fetchCalendarEvents("unassigned", sortMode), fetchSettings(), fetchQueue({ state: includeClosedTickets ? "all" : "open" }),
      fetchUsers(), fetchTypes(), fetchLevels(), fetchStatuts(),
    ]);
    setEvents(evts);
    setTickets(allOpenTickets);
    setUsers(u);
    setTypes(ty);
    setLevels(l);
    setStatuts(s);
    if (settings.trigger_keyword) setTriggerKeyword(settings.trigger_keyword);
    setLoading(false);
  }

  useEffect(() => {
    reload();
  }, [sortMode, includeClosedTickets]);

  useEffect(() => {
    if (selectedEventIds.size === 0) {
      setSuggestedName("");
      return;
    }
    let cancelled = false;
    suggestNameForEvents([...selectedEventIds]).then((result) => {
      if (!cancelled && result.ok) setSuggestedName(result.data.candidate || "");
    });
    return () => {
      cancelled = true;
    };
  }, [selectedEventIds]);

  async function handleOpenMining() {
    setShowMining((v) => !v);
    if (!miningResult) {
      setMiningLoading(true);
      const result = await mineCandidates(15);
      setMiningResult(result);
      setMiningLoading(false);
    }
  }

  async function handleQuickCreateUser(token) {
    await createUser({ login: token, name: token });
    await reload();
    setMiningResult(null); // force un nouveau calcul (le candidat créé doit disparaître ou se marquer "connu")
    const result = await mineCandidates(15);
    setMiningResult(result);
  }

  async function handleOpenTitleMatches() {
    setShowTitleMatches((v) => !v);
    if (!titleMatches) {
      setTitleMatchesLoading(true);
      const result = await fetchTitleMatches(1);
      setTitleMatches(result);
      setTitleMatchesLoading(false);
    }
  }

  async function handleViewSynthesis(term) {
    setSynthesisTerm(term);
    setSynthesisLoading(true);
    const result = await fetchTermSynthesis(term);
    setSynthesisData(result);
    setSynthesisLoading(false);
  }

  async function handleApplyTitleMatch(match) {
    setApplyingMatch(match.event_id);
    const result = await assignEvents([match.event_id], [match.ticket_id], "full");
    setApplyingMatch(null);
    if (result.ok) {
      setTitleMatches((prev) => ({
        ...prev,
        matches: prev.matches.filter((m) => m.event_id !== match.event_id),
      }));
      reload();
      onAssigned();
    }
  }

  function selectGroup(eventIds, additive) {
    setSelectedEventIds((prev) => {
      if (!additive) {
        // Clic simple = mono-tâche : remplace la sélection, ne l'ajoute pas.
        const allAlreadySelected = eventIds.every((id) => prev.has(id)) && prev.size === eventIds.length;
        return allAlreadySelected ? new Set() : new Set(eventIds); // reclique pour désélectionner
      }
      // Ctrl/Cmd+clic = ajoute ou retire ce groupe de la sélection existante (mode lot).
      const next = new Set(prev);
      const allSelected = eventIds.every((id) => next.has(id));
      for (const id of eventIds) {
        allSelected ? next.delete(id) : next.add(id);
      }
      return next;
    });
  }

  function toggleTicket(id) {
    setSelectedTicketIds((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  }

  function pickSuggestion(eventIds, ticketId) {
    setSelectedEventIds(new Set(eventIds));
    setSelectedTicketIds(new Set([ticketId]));
  }

  async function handleAssign() {
    if (selectedEventIds.size === 0 || selectedTicketIds.size === 0) return;
    setAssigning(true);
    const result = await assignEvents([...selectedEventIds], [...selectedTicketIds], mode, reopenOnAssign);
    setAssigning(false);
    if (result.ok) {
      const notices = [];
      if (result.data.auto_added_duplicates > 0) {
        notices.push(`+ ${result.data.auto_added_duplicates} événement(s) au même titre affecté(s) automatiquement (${result.data.events_assigned} au total).`);
      }
      if (result.data.reopened_ticket_ids?.length > 0) {
        notices.push(`🔓 ${result.data.reopened_ticket_ids.length} ticket(s) rouvert(s) : #${result.data.reopened_ticket_ids.join(", #")}.`);
      }
      setAutoSweepNotice(notices.length > 0 ? notices.join(" ") : null);
      setSelectedEventIds(new Set());
      setSelectedTicketIds(new Set());
      setReopenOnAssign(false);
      reload();
      onAssigned();
    }
  }

  async function handleSaveKeyword() {
    setSavingKeyword(true);
    await updateSettings({ trigger_keyword: triggerKeyword });
    setSavingKeyword(false);
    reload();
  }

  async function handleCreateUser(payload) {
    const result = await createUser({ login: payload.label, name: payload.label });
    if (result.ok) {
      // Mise à jour locale immédiate — évite une fenêtre où le <select>
      // reçoit la nouvelle valeur (via onChange) AVANT que la nouvelle
      // option n'existe dans sa propre liste (options périmées le temps
      // que reload() aboutisse) : le <select> ignorait alors la
      // sélection, obligeant à rouvrir la liste déroulante à la main.
      // Vrai bug trouvé et corrigé.
      setUsers((prev) => [...prev, { id: result.data.id, login: payload.label, name: payload.label }]);
    }
    reload(); // resynchronise le reste en arrière-plan, sans bloquer
    return result.ok ? result.data.id : null;
  }
  async function handleCreateType(payload) {
    const result = await createType({ label: payload.label });
    if (result.ok) {
      setTypes((prev) => [...prev, { id: result.data.id, label: payload.label }]);
    }
    reload();
    return result.ok ? result.data.id : null;
  }
  async function handleCreateLevel(payload) {
    const result = await createLevel({ label: payload.label, rank: Number(payload.rank) || 0 });
    if (result.ok) {
      setLevels((prev) => [...prev, { id: result.data.id, label: payload.label, rank: Number(payload.rank) || 0 }]);
    }
    reload();
    return result.ok ? result.data.id : null;
  }
  async function handleCreateStatut(payload) {
    const result = await createStatut({ label: payload.label });
    if (result.ok) {
      setStatuts((prev) => [...prev, { id: result.data.id, label: payload.label }]);
    }
    reload();
    return result.ok ? result.data.id : null;
  }

  async function handleCreateTicket() {
    if (!newTicket.subject.trim()) return;
    setCreatingTicketSaving(true);
    const result = await createTicket({
      user_id: newTicket.user_id || null, subject: newTicket.subject,
      type_id: newTicket.type_id || null, level_id: newTicket.level_id || null,
      statut_id: newTicket.statut_id || null,
    });
    setCreatingTicketSaving(false);
    if (result.ok) {
      const newTicketId = result.data.id;
      setNewTicket({ subject: "", user_id: "", type_id: "", level_id: "", statut_id: "" });
      await reload();
      // Sélectionne directement le ticket fraîchement créé — reste à
      // choisir les événements et le mode, puis "Affecter" comme
      // d'habitude (pas de court-circuit du flux normal).
      setSelectedTicketIds((prev) => new Set([...prev, newTicketId]));
    }
  }

  const filteredTickets = tickets.filter((t) =>
    !ticketFilter.trim() || t.subject.toLowerCase().includes(ticketFilter.toLowerCase()) || String(t.id) === ticketFilter.trim()
  );

  // Deux sources possibles pour un ticket sélectionné : la liste
  // manuelle "Tickets reconnus" (ts_closed), ou une puce de suggestion
  // (is_closed) — un ticket fermé suggéré n'apparaît pas forcément
  // dans la liste manuelle si "inclure les fermés" est décoché.
  const closedTicketIdsFromSuggestions = new Set(
    events.flatMap((e) => (e.suggestions || []).filter((s) => s.is_closed).map((s) => s.ticket_id))
  );
  const selectionHasClosedTicket = [...selectedTicketIds].some(
    (id) => tickets.find((t) => t.id === id)?.ts_closed || closedTicketIdsFromSuggestions.has(id)
  );

  return (
    <div className="pixel-grid-app">
      <div className="pixel-grid-toolbar">
        <div className="timeline-header">
          <div className="timeline-title">📋 Revue des imports calendrier</div>
          <button className="calendar-nav-btn" onClick={onClose}>← Retour</button>
        </div>
        <div className="pixel-grid-controls">
          <span className="pixel-grid-controls-label">Mot-clé/regex déclencheur :</span>
          <input className="geo-input" style={{ width: 100 }} value={triggerKeyword}
            onChange={(e) => setTriggerKeyword(e.target.value)} title="Expression régulière, insensible à la casse — ex: SAV, SAV.*, SAV-\d+" />
          <button className="pixel-grid-reset-btn" onClick={handleSaveKeyword} disabled={savingKeyword}>
            {savingKeyword ? "…" : "💾"}
          </button>
          <button className="sources-header-btn" onClick={handleOpenMining}>
            🔍 Analyser les imports {showMining ? "▾" : "▸"}
          </button>
          <button className="sources-header-btn" onClick={handleOpenTitleMatches}>
            🔗 Correspondances de titres {showTitleMatches ? "▾" : "▸"}
          </button>
          <input
            className="geo-input"
            style={{ width: 140 }}
            placeholder="🔎 chercher un terme…"
            onKeyDown={(e) => { if (e.key === "Enter" && e.target.value.trim()) handleViewSynthesis(e.target.value.trim()); }}
            title="Entrée pour voir la synthèse des tickets mentionnant ce terme"
          />
        </div>

        {showMining && (
          <div className="pixel-grid-hover-detail" style={{ marginTop: "0.5rem" }}>
            <p style={{ margin: "0 0 0.4rem 0" }}>
              ⚠️ Heuristique (fréquence + position), pas un vrai NER — des
              candidats non pertinents sont possibles (termes techniques
              récurrents, fragments de sujet). À valider avant création.
            </p>
            {miningLoading && <p className="synthesis-empty">Analyse…</p>}
            {!miningLoading && miningResult && (
              <div style={{ display: "flex", gap: "0.4rem", flexWrap: "wrap" }}>
                {miningResult.candidates.map((c) => (
                  <span key={c.token} className="pixel-grid-level-btn" style={{ display: "inline-flex", gap: "0.3rem", alignItems: "center" }}>
                    <button
                      className="calendar-nav-btn"
                      style={{ padding: "0 0.2rem", fontWeight: "inherit" }}
                      onClick={() => handleViewSynthesis(c.token)}
                      title={`Voir la synthèse des tickets mentionnant "${c.token}"`}
                    >
                      {c.token}
                    </button>
                    ({c.frequency})
                    {c.matches_existing_user ? (
                      <span title="Correspond déjà à un utilisateur connu">✓</span>
                    ) : (
                      <button className="calendar-nav-btn" style={{ padding: "0 0.3rem" }} onClick={() => handleQuickCreateUser(c.token)} title="Créer cet utilisateur">
                        +
                      </button>
                    )}
                  </span>
                ))}
                {miningResult.candidates.length === 0 && (
                  <span className="pixel-grid-empty-hint">Aucun candidat trouvé sur {miningResult.total_events_analyzed} événement(s) analysé(s).</span>
                )}
              </div>
            )}
          </div>
        )}

        {showTitleMatches && (
          <div className="pixel-grid-hover-detail" style={{ marginTop: "0.5rem" }}>
            <p style={{ margin: "0 0 0.4rem 0" }}>
              🔗 Indépendant du mot-clé déclencheur — cherche un mot ou
              groupe de mots partagé (≥ 3 caractères, mot-clé exclu)
              entre le titre d'un événement non affecté et le sujet
              d'un ticket ouvert. Rattrape les titres qu'un
              déclenchement classique ne capte pas (ex: "SMS" seul,
              alors qu'un ticket "SAV Didier/SMS" existe déjà).
            </p>
            {titleMatchesLoading && <p className="synthesis-empty">Analyse…</p>}
            {!titleMatchesLoading && titleMatches && (
              <div style={{ display: "flex", flexDirection: "column", gap: "0.3rem" }}>
                {titleMatches.matches.map((m) => (
                  <div key={m.event_id} className="timeline-incident-card" style={{ display: "flex", alignItems: "center", gap: "0.5rem", justifyContent: "space-between" }}>
                    <span style={{ fontSize: "0.75rem" }}>
                      <strong>"{m.event_summary}"</strong> → #{m.ticket_id} "{m.ticket_subject}"{m.is_closed ? " 🔒" : ""}
                      {" "}<span className="pixel-grid-empty-hint">(mots partagés : {m.shared_words.join(", ")})</span>
                    </span>
                    <button
                      className="pixel-grid-reset-btn"
                      style={{ fontSize: "0.68rem", flexShrink: 0 }}
                      onClick={() => handleApplyTitleMatch(m)}
                      disabled={applyingMatch === m.event_id}
                    >
                      {applyingMatch === m.event_id ? "…" : "➕ Ajouter ce segment"}
                    </button>
                  </div>
                ))}
                {titleMatches.matches.length === 0 && (
                  <span className="pixel-grid-empty-hint">Aucune correspondance trouvée sur {titleMatches.total_events_analyzed} événement(s) non affecté(s).</span>
                )}
              </div>
            )}
          </div>
        )}
      </div>

      {synthesisTerm && (
        <div className="pixel-grid-toolbar" style={{ border: "1px solid var(--color-select)", marginBottom: "0.75rem" }}>
          <div className="timeline-header">
            <div className="timeline-title">🔎 Synthèse — "{synthesisTerm}"</div>
            <button className="calendar-nav-btn" onClick={() => { setSynthesisTerm(null); setSynthesisData(null); }}>✕ Fermer</button>
          </div>

          {synthesisLoading && <p className="synthesis-empty">Analyse…</p>}

          {!synthesisLoading && synthesisData && (
            <>
              <div className="pixel-grid-controls" style={{ flexWrap: "wrap" }}>
                <span className="pixel-grid-level-btn">{synthesisData.synthesis.total_tickets} ticket(s)</span>
                <span className="pixel-grid-level-btn">{synthesisData.synthesis.open_count} ouvert(s) · {synthesisData.synthesis.closed_count} fermé(s)</span>
                <span className="pixel-grid-level-btn">{(synthesisData.synthesis.total_seconds / 3600).toFixed(1)}h au total</span>
                {synthesisData.synthesis.distinct_users.length > 0 && (
                  <span className="pixel-grid-level-btn">👤 {synthesisData.synthesis.distinct_users.join(", ")}</span>
                )}
              </div>

              <div className="timeline-incident-list" style={{ maxHeight: 220, overflowY: "auto", marginTop: "0.4rem" }}>
                {synthesisData.tickets.map((t) => (
                  <div key={t.id} className="timeline-incident-card">
                    <span style={{ fontSize: "0.75rem" }}>
                      #{t.id} — {t.subject} · <span className="pixel-grid-empty-hint">
                        {t.statut_label || (t.ts_closed ? "fermé" : "ouvert")} · {t.user_login || "sans demandeur"} · {(t.total_seconds / 3600).toFixed(1)}h
                      </span>
                    </span>
                  </div>
                ))}
                {synthesisData.tickets.length === 0 && <p className="synthesis-empty">Aucun ticket ne mentionne ce terme.</p>}
              </div>

              {synthesisData.unassigned_events.length > 0 && (
                <>
                  <p className="pixel-grid-empty-hint" style={{ marginTop: "0.4rem" }}>
                    ⚡ {synthesisData.unassigned_events.length} événement(s) calendrier non affecté(s) mentionnent aussi ce terme :
                  </p>
                  <div className="timeline-incident-list" style={{ maxHeight: 140, overflowY: "auto" }}>
                    {synthesisData.unassigned_events.map((e) => (
                      <div key={e.id} className="timeline-incident-card">
                        <span style={{ fontSize: "0.72rem" }}>{new Date(e.start_ts * 1000).toLocaleDateString()} — {e.summary}</span>
                      </div>
                    ))}
                  </div>
                </>
              )}
            </>
          )}
        </div>
      )}

      {loading && <p className="synthesis-empty">Chargement…</p>}

      {!loading && (
        <div className="pixel-grid-body">
          <div className="pixel-grid-main">
            <p className="synthesis-empty">
              {events.length} événement(s) non affecté(s). Coche un ou plusieurs
              événements à gauche, un ou plusieurs tickets à droite, choisis le
              mode, puis Affecter — ou clique directement une suggestion pour
              une affectation rapide 1-vers-1.
            </p>

            <div className="pixel-grid-body" style={{ gap: "1rem" }}>
              <div className="pixel-grid-main">
                <div className="pixel-grid-controls" style={{ marginBottom: "0.4rem" }}>
                  <span className="pixel-grid-controls-label">Trier :</span>
                  <button className={`pixel-grid-level-btn ${sortMode === "relevance" ? "active" : ""}`} onClick={() => setSortMode("relevance")} title="Suggestions en tête, plus récent d'abord">
                    Pertinence
                  </button>
                  <button className={`pixel-grid-level-btn ${sortMode === "oldest" ? "active" : ""}`} onClick={() => setSortMode("oldest")} title="Le plus ancien en premier">
                    Oubliés
                  </button>
                  <button className={`pixel-grid-level-btn ${sortMode === "requester" ? "active" : ""}`} onClick={() => setSortMode("requester")} title="Groupé par demandeur détecté">
                    Demandeur
                  </button>
                  <button className={`pixel-grid-level-btn ${sortMode === "urgency" ? "active" : ""}`} onClick={() => setSortMode("urgency")} title="Mots-clés d'urgence en tête (voir ⚙️ Règles calendrier)">
                    Urgence
                  </button>
                </div>
                <div className="timeline-title" style={{ fontSize: "0.8rem" }}>Événements</div>
                <div className="timeline-incident-list" style={{ maxHeight: 460, overflowY: "auto" }}>
                  {groupDuplicateEvents(events).map((group) => {
                    const e = group.events[0]; // représentant — mêmes suggestions pour tout le groupe (titre identique)
                    const groupIds = group.events.map((ev) => ev.id);
                    const allSelected = groupIds.every((id) => selectedEventIds.has(id));
                    const someSelected = !allSelected && groupIds.some((id) => selectedEventIds.has(id));
                    const totalSeconds = group.events.reduce((sum, ev) => sum + (ev.end_ts - ev.start_ts), 0);
                    const isGroup = group.events.length > 1;

                    return (
                      <div
                        key={group.key}
                        className={`timeline-incident-card ${allSelected ? "selected" : ""}`}
                        onClick={(ev) => selectGroup(groupIds, ev.ctrlKey || ev.metaKey || ev.shiftKey)}
                        style={{
                          cursor: "pointer",
                          borderLeft: allSelected ? "3px solid var(--color-select)" : "3px solid transparent",
                          background: allSelected ? "var(--color-select-bg, rgba(90,160,255,0.12))" : someSelected ? "rgba(255,255,255,0.04)" : undefined,
                        }}
                        title={allSelected ? "Sélectionné — clique pour désélectionner (Ctrl+clic pour ajouter/retirer sans remplacer)" : "Clique pour sélectionner (remplace la sélection actuelle)"}
                      >
                        <div style={{ display: "flex", gap: "0.5rem", alignItems: "flex-start" }}>
                          {allSelected && <span style={{ flexShrink: 0 }}>✅</span>}
                          <div style={{ flex: 1 }}>
                            <div className="timeline-incident-times">
                              {isGroup ? (
                                <>
                                  <strong>×{group.events.length}</strong> reprises · {new Date(group.events.reduce((m, ev) => Math.min(m, ev.start_ts), Infinity) * 1000).toLocaleDateString()}
                                  {" → "}{new Date(group.events.reduce((m, ev) => Math.max(m, ev.start_ts), -Infinity) * 1000).toLocaleDateString()}
                                  {" · "}{(totalSeconds / 3600).toFixed(1)}h au total
                                </>
                              ) : (
                                <>{new Date(e.start_ts * 1000).toLocaleString()} · {formatDuration(e.start_ts, e.end_ts)}</>
                              )}
                              {e.priority_match && <span title="Mot-clé d'urgence détecté" style={{ marginLeft: "0.4rem" }}>🔥</span>}
                              {e.requester_hint && <span className="pixel-grid-empty-hint" style={{ marginLeft: "0.4rem" }}>👤 {e.requester_hint}</span>}
                            </div>
                            <div>{e.summary}</div>
                            {isGroup && (
                              <details style={{ marginTop: "0.2rem" }} onClick={(ev) => ev.stopPropagation()}>
                                <summary className="pixel-grid-empty-hint" style={{ cursor: "pointer" }}>voir les {group.events.length} occurrences</summary>
                                <ul style={{ margin: "0.3rem 0 0 1rem", padding: 0, fontSize: "0.7rem", color: "var(--color-text-muted)" }}>
                                  {group.events.map((ev) => (
                                    <li key={ev.id}>{new Date(ev.start_ts * 1000).toLocaleString()} · {formatDuration(ev.start_ts, ev.end_ts)}</li>
                                  ))}
                                </ul>
                              </details>
                            )}
                            {e.suggestions?.length > 0 && (
                              <div style={{ marginTop: "0.3rem", display: "flex", gap: "0.3rem", flexWrap: "wrap" }}>
                                {e.suggestions.map((s) => (
                                  <button
                                    key={s.ticket_id}
                                    className="pixel-grid-level-btn"
                                    style={{ fontSize: "0.68rem" }}
                                    onClick={(ev) => { ev.preventDefault(); ev.stopPropagation(); pickSuggestion(groupIds, s.ticket_id); }}
                                    title={isGroup ? `${s.reason} — affecte les ${group.events.length} occurrences` : s.reason}
                                  >
                                    {s.confidence === "haute" ? "🎯" : "💡"} #{s.ticket_id}{s.is_closed ? " 🔒" : ""}{isGroup ? ` (×${group.events.length})` : ""}
                                  </button>
                                ))}
                              </div>
                            )}
                            {e.excluded && (
                              <div className="pixel-grid-empty-hint" style={{ marginTop: "0.3rem" }}>
                                🚫 exclu (règle : <code>{e.excluded_reason}</code>)
                              </div>
                            )}
                            {!e.excluded && e.triggered && e.suggestions?.length === 0 && (
                              <div className="pixel-grid-empty-hint" style={{ marginTop: "0.3rem" }}>
                                ⚡ mot-clé détecté, mais aucun ticket ouvert à proposer — coche cet
                                événement et utilise "Nouveau ticket" à droite
                              </div>
                            )}
                          </div>
                        </div>
                      </div>
                    );
                  })}
                  {events.length === 0 && <p className="synthesis-empty">Rien à affecter.</p>}
                </div>
              </div>

              <div className="pixel-grid-main">
                <div className="timeline-title" style={{ fontSize: "0.8rem" }}>Tickets</div>
                <ResizableSplit
                  defaultTopPercent={62}
                  height={460}
                  top={
                    <div className="inject-form" style={{ marginTop: 0 }}>
                      <div className="inject-form-title">Nouveau ticket</div>
                      <input className="calendar-keywords-input" placeholder="Sujet"
                        value={newTicket.subject} onChange={(e) => setNewTicket({ ...newTicket, subject: e.target.value })} />
                      {(() => {
                        const firstSelected = events.find((e) => selectedEventIds.has(e.id));
                        if (!firstSelected || newTicket.subject) return null;
                        return (
                          <button
                            className="pixel-grid-level-btn"
                            style={{ fontSize: "0.68rem", marginTop: "0.3rem" }}
                            onClick={() => setNewTicket({ ...newTicket, subject: firstSelected.summary })}
                            title="Reprendre le titre de l'événement sélectionné comme sujet"
                          >
                            💡 utiliser : "{firstSelected.summary}"
                          </button>
                        );
                      })()}
                      <div className="pixel-grid-controls" style={{ flexWrap: "wrap" }}>
                        <CreatableSelect
                          value={newTicket.user_id} onChange={(v) => setNewTicket({ ...newTicket, user_id: v })}
                          options={users.map((u) => ({ id: u.id, label: u.login }))}
                          placeholder="demandeur" onCreate={handleCreateUser}
                          defaultLabel={suggestedName}
                          suggestion={suggestedName}
                        />
                        <CreatableSelect
                          value={newTicket.type_id} onChange={(v) => setNewTicket({ ...newTicket, type_id: v })}
                          options={types.map((t) => ({ id: t.id, label: t.label }))}
                          placeholder="type" onCreate={handleCreateType}
                        />
                        <CreatableSelect
                          value={newTicket.level_id} onChange={(v) => setNewTicket({ ...newTicket, level_id: v })}
                          options={levels.map((l) => ({ id: l.id, label: l.label }))}
                          placeholder="niveau" onCreate={handleCreateLevel}
                          extraFields={[{ key: "rank", placeholder: "rang" }]}
                        />
                        <CreatableSelect
                          value={newTicket.statut_id} onChange={(v) => setNewTicket({ ...newTicket, statut_id: v })}
                          options={statuts.map((s) => ({ id: s.id, label: s.label }))}
                          placeholder="statut" onCreate={handleCreateStatut}
                        />
                      </div>
                      <div className="inject-form-actions">
                        <button className="calendar-nav-btn inject-submit-btn" onClick={handleCreateTicket} disabled={creatingTicketSaving || !newTicket.subject.trim()}>
                          {creatingTicketSaving ? "…" : "➕ Créer et sélectionner"}
                        </button>
                      </div>
                      {newTicket.subject.trim() && !newTicket.user_id && (
                        <p className="pixel-grid-empty-hint" style={{ color: "var(--color-warning, #e0a94c)" }}>
                          ⚠️ Aucun demandeur sélectionné — le ticket sera créé sans.
                        </p>
                      )}
                    </div>
                  }
                  bottom={
                    <>
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.3rem" }}>
                        <span className="pixel-grid-empty-hint">Tickets reconnus</span>
                        <label style={{ display: "flex", gap: "0.3rem", alignItems: "center", cursor: "pointer", fontSize: "0.68rem" }}>
                          <input type="checkbox" checked={includeClosedTickets} onChange={(e) => setIncludeClosedTickets(e.target.checked)} />
                          inclure les fermés
                        </label>
                      </div>
                      <input className="calendar-keywords-input" placeholder="Filtrer par sujet ou #id"
                        value={ticketFilter} onChange={(e) => setTicketFilter(e.target.value)} />
                      <div style={{ marginTop: "0.4rem" }}>
                        {filteredTickets.map((t) => (
                          <label key={t.id} className="timeline-incident-card" style={{ display: "flex", gap: "0.5rem", cursor: "pointer" }}>
                            <input type="checkbox" checked={selectedTicketIds.has(t.id)} onChange={() => toggleTicket(t.id)} />
                            <span>#{t.id} — {t.subject}{t.ts_closed ? " 🔒" : ""}</span>
                          </label>
                        ))}
                        {filteredTickets.length === 0 && (
                          <p className="synthesis-empty">Aucun ticket pour l'instant.</p>
                        )}
                      </div>
                    </>
                  }
                />
              </div>
            </div>

            <div className="pixel-grid-toolbar" style={{ marginTop: "1rem" }}>
              <div className="pixel-grid-controls">
                <span className="pixel-grid-controls-label">
                  {selectedEventIds.size} événement(s) → {selectedTicketIds.size} ticket(s) — mode :
                </span>
                <button className={`pixel-grid-level-btn ${mode === "full" ? "active" : ""}`} onClick={() => setMode("full")}>
                  Durée entière chacun
                </button>
                <button className={`pixel-grid-level-btn ${mode === "split" ? "active" : ""}`} onClick={() => setMode("split")}>
                  Répartie également
                </button>
                {selectionHasClosedTicket && (
                  <label style={{ display: "flex", gap: "0.3rem", alignItems: "center", cursor: "pointer", fontSize: "0.72rem" }}>
                    <input type="checkbox" checked={reopenOnAssign} onChange={(e) => setReopenOnAssign(e.target.checked)} />
                    🔓 rouvrir aussi le(s) ticket(s) fermé(s) sélectionné(s)
                  </label>
                )}
                <button
                  className="pixel-grid-reset-btn"
                  onClick={handleAssign}
                  disabled={assigning || selectedEventIds.size === 0 || selectedTicketIds.size === 0}
                >
                  {assigning ? "…" : "✅ Affecter"}
                </button>
              </div>
              {autoSweepNotice && <p className="pixel-grid-hover-detail">🧹 {autoSweepNotice}</p>}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
