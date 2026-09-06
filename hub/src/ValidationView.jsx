import React, { useState, useEffect } from "react";
import {
  fetchPendingValidationTickets, validateTicket, rejectTicket,
  fetchUsers, fetchTypes, fetchLevels, fetchStatuts,
  fetchPendingStatusChanges, validateAllStatusChanges,
} from "./calendarClient.js";

// Onglet "Validation" de la tuile ENT (livraison #273, demandé
// explicitement : "ajoute un écran de validation des tickets
// automatique"). Liste les tickets créés automatiquement depuis un
// événement calendrier (pending_validation=1) -- jamais traités
// comme des tickets pleinement réels tant qu'un humain ne les a pas
// confirmés ici, même esprit que le moteur de suggestion déjà
// existant côté calendrier ("la décision finale reste humaine").
//
// Rejeter réutilise le mécanisme d'archivage DÉJÀ EXISTANT
// (PUT /tickets/<id> {"archived_at": ...}) -- jamais un vrai DELETE,
// même convention que le reste de ce module (voir tickets/README.md).
//
// Correction demandeur/type/niveau/statut À LA VALIDATION (livraison
// #274) -- POST /tickets/<id>/validate acceptait déjà ces quatre
// champs depuis #273, seule l'interface n'exposait que le demandeur.
// Un objet unique PAR TICKET (jamais quatre state séparés) --
// {user_id, type_id, level_id, statut_id}, initialisé depuis les
// valeurs déjà présentes sur le ticket (souvent NULL pour un ticket
// auto-créé, sauf le demandeur parfois deviné).

const FIELD_LABELS = { user_id: "Demandeur", type_id: "Type", level_id: "Niveau", statut_id: "Statut" };

export default function ValidationView({ embedded, onBack, ticketsApiBase, portalUrl }) {
  const [tickets, setTickets] = useState([]);
  const [users, setUsers] = useState([]);
  const [types, setTypes] = useState([]);
  const [levels, setLevels] = useState([]);
  const [statuts, setStatuts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [overridesByTicket, setOverridesByTicket] = useState({});
  const [statusChanges, setStatusChanges] = useState([]);
  const [loadingChanges, setLoadingChanges] = useState(true);

  useEffect(() => {
    load();
    loadStatusChanges();
    fetchUsers(ticketsApiBase).then(setUsers);
    fetchTypes(ticketsApiBase).then(setTypes);
    fetchLevels(ticketsApiBase).then(setLevels);
    fetchStatuts(ticketsApiBase).then(setStatuts);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ticketsApiBase]);

  async function loadStatusChanges() {
    setLoadingChanges(true);
    setStatusChanges(await fetchPendingStatusChanges(ticketsApiBase));
    setLoadingChanges(false);
  }

  async function handleValidateAllStatusChanges() {
    setBusy(true);
    await validateAllStatusChanges(ticketsApiBase);
    setBusy(false);
    await loadStatusChanges();
  }

  async function load() {
    setLoading(true);
    setTickets(await fetchPendingValidationTickets(ticketsApiBase));
    setLoading(false);
  }

  function fieldValue(ticket, field) {
    return overridesByTicket[ticket.id]?.[field] ?? (ticket[field] || "");
  }
  function setField(ticketId, field, value) {
    setOverridesByTicket({
      ...overridesByTicket,
      [ticketId]: { ...overridesByTicket[ticketId], [field]: value },
    });
  }

  async function handleValidate(ticket) {
    setBusy(true);
    const payload = {};
    for (const field of Object.keys(FIELD_LABELS)) {
      const value = fieldValue(ticket, field);
      if (value) payload[field] = Number(value);
    }
    await validateTicket(ticketsApiBase, ticket.id, payload);
    setBusy(false);
    await load();
  }

  async function handleReject(ticketId) {
    if (!window.confirm("Rejeter ce ticket créé automatiquement ? Il sera archivé (récupérable), jamais supprimé définitivement.")) return;
    setBusy(true);
    await rejectTicket(ticketsApiBase, ticketId);
    setBusy(false);
    await load();
  }

  return (
    <div className="hub-settings hub-settings-wide">
      {!embedded && (
        <div className="hub-settings-topbar">
          <button className="secondary" onClick={onBack}>◀ Retour</button>
          <h1>✅ Validation</h1>
        </div>
      )}

      <div className="hub-card">
        <h2 style={{ marginTop: 0 }}>Changements de statut en attente</h2>
        <p className="muted" style={{ marginTop: -4 }}>
          Chaque changement est journalisé de façon permanente. La validation ci-dessous s'applique à
          L'ENSEMBLE des changements en attente à la fois — pas un écran par changement.
          {portalUrl && (
            <> Pour les autres actions sur un ticket, voir la <a href={portalUrl} target="_blank" rel="noreferrer">tuile Tickets</a> (vue technicien selon vos droits).</>
          )}
        </p>
        {loadingChanges ? (
          <p className="muted">Chargement…</p>
        ) : statusChanges.length === 0 ? (
          <p className="muted">Aucun changement en attente.</p>
        ) : (
          <>
            <table>
              <thead><tr><th>Ticket</th><th>Ancien statut</th><th>Nouveau statut</th><th>Motif</th><th>Quand</th></tr></thead>
              <tbody>
                {statusChanges.map((c) => (
                  <tr key={c.id}>
                    <td>#{c.ticket_id} — {c.ticket_subject}</td>
                    <td className="muted">{c.old_label || "—"}</td>
                    <td>{c.new_label || "—"}</td>
                    <td className="muted">{c.reason}</td>
                    <td className="muted">{c.changed_at}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <button disabled={busy} onClick={handleValidateAllStatusChanges} style={{ marginTop: 8 }}>
              ✅ Valider tout ({statusChanges.length})
            </button>
          </>
        )}
      </div>

      <div className="hub-card">
        <p className="muted" style={{ margin: 0 }}>
          Tickets créés automatiquement depuis un événement calendrier -- vérifiez/complétez le
          demandeur, le type, le niveau et le statut (parfois devinés, parfois vides) avant de confirmer.
        </p>
      </div>

      {loading ? (
        <p className="muted">Chargement…</p>
      ) : tickets.length === 0 ? (
        <p className="muted">Aucun ticket en attente de validation.</p>
      ) : (
        tickets.map((t) => (
          <div key={t.id} className="hub-card" style={{ marginBottom: 12 }}>
            <p style={{ margin: 0, fontWeight: "bold" }}>{t.subject}</p>
            {t.description && <p className="muted" style={{ margin: "4px 0" }}>{t.description}</p>}
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 8, alignItems: "flex-end" }}>
              <div className="hub-settings-row" style={{ margin: 0 }}>
                <label>Demandeur</label>
                <select value={fieldValue(t, "user_id")} onChange={(e) => setField(t.id, "user_id", e.target.value)}>
                  <option value="">— aucun —</option>
                  {users.map((u) => <option key={u.id} value={u.id}>{u.login}</option>)}
                </select>
              </div>
              <div className="hub-settings-row" style={{ margin: 0 }}>
                <label>Type</label>
                <select value={fieldValue(t, "type_id")} onChange={(e) => setField(t.id, "type_id", e.target.value)}>
                  <option value="">— aucun —</option>
                  {types.map((ty) => <option key={ty.id} value={ty.id}>{ty.label}</option>)}
                </select>
              </div>
              <div className="hub-settings-row" style={{ margin: 0 }}>
                <label>Niveau</label>
                <select value={fieldValue(t, "level_id")} onChange={(e) => setField(t.id, "level_id", e.target.value)}>
                  <option value="">— aucun —</option>
                  {levels.map((l) => <option key={l.id} value={l.id}>{l.label}</option>)}
                </select>
              </div>
              <div className="hub-settings-row" style={{ margin: 0 }}>
                <label>Statut</label>
                <select value={fieldValue(t, "statut_id")} onChange={(e) => setField(t.id, "statut_id", e.target.value)}>
                  <option value="">— aucun —</option>
                  {statuts.map((s) => <option key={s.id} value={s.id}>{s.label}</option>)}
                </select>
              </div>
              <button disabled={busy} onClick={() => handleValidate(t)}>✅ Confirmer</button>
              <button className="secondary" disabled={busy} onClick={() => handleReject(t.id)}>🗑 Rejeter</button>
            </div>
          </div>
        ))
      )}
    </div>
  );
}
