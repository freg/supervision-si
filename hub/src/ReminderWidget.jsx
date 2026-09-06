import { useEffect, useState } from "react";
import { isTechnicien } from "./lib.js";
import {
  fetchAppSettings, fetchTechReminderPrefs, saveTechReminderPrefs, DEFAULT_TECH_REMINDER_PREFS,
  effectiveTechReminderConfig, shouldShowReminder,
  fetchReminderSession, saveReminderSession, computeSegmentToSubmit, nextSession, submitTimeSegment,
  fetchOpenTicketsForReminder, fetchStatuts, updateTicketStatus, pickAutoInProgressStatutId,
} from "./settingsClient.js";
import { postHubEvent } from "./hubEvents.js";

const nowTs = () => Math.floor(Date.now() / 1000);

// Widget de rappel d'activité -- demandé explicitement : intégré au
// hub lui-même (indépendant de l'onglet ouvert), deux minuteries
// SÉPARÉES (fréquence du rappel vs durée d'affichage avant fermeture
// auto -- jamais confondues), démarre/rattache un vrai suivi de temps
// sur le ticket choisi. Toute la logique métier (session, segments,
// snooze) vit dans settingsClient.js, testée séparément -- ce fichier
// ne fait que le rendu et l'orchestration des minuteries.
export default function ReminderWidget({ login, groups, prefsApiBase, ticketsApiBase, ticketsPortalUrl }) {
  const isTech = isTechnicien(groups);

  const [effectiveConfig, setEffectiveConfig] = useState(null); // null tant que pas chargé
  const [session, setSession] = useState(null);
  const [showPopup, setShowPopup] = useState(false);
  const [tickets, setTickets] = useState([]);
  const [ticketsLoading, setTicketsLoading] = useState(false);
  // Statuts configurés (avec leur `type`) -- pour la bascule
  // automatique vers "en_cours" à la confirmation, voir handleConfirm.
  // Chargés UNE FOIS au montage (config qui change rarement, jamais
  // reléchargés à chaque ouverture du popup contrairement aux
  // tickets) -- backlog, bug tickets/rappels.
  const [statuts, setStatuts] = useState([]);

  // Chargement initial -- config effective (défauts app + overrides
  // personnels) et session en cours. Remet à zéro "snooze jusqu'à
  // reconnexion" ICI (on vient justement de se reconnecter au hub,
  // montage de ce widget) -- shouldShowReminder reste volontairement
  // une fonction pure qui ne fait que LIRE cet état, jamais le
  // modifier elle-même.
  useEffect(() => {
    if (!isTech || !login) return;
    (async () => {
      const [appData, personalData, sessionData, statutsData] = await Promise.all([
        fetchAppSettings(prefsApiBase, "tickets"),
        fetchTechReminderPrefs(prefsApiBase, login),
        fetchReminderSession(prefsApiBase, login),
        fetchStatuts(ticketsApiBase),
      ]);
      let personal = { ...DEFAULT_TECH_REMINDER_PREFS, ...personalData };
      if (personal.snooze_until_reconnect) {
        personal = { ...personal, snooze_until_reconnect: false };
        saveTechReminderPrefs(prefsApiBase, login, personal);
      }
      setEffectiveConfig(effectiveTechReminderConfig(personal, appData));
      setSession(sessionData);
      setStatuts(statutsData);
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isTech, login]);

  const openPopup = () => {
    setShowPopup(true);
    setTicketsLoading(true);
    fetchOpenTicketsForReminder(ticketsApiBase).then((t) => {
      setTickets(t);
      setTicketsLoading(false);
    });
  };

  // Minuterie de FRÉQUENCE -- déclenche l'affichage périodiquement.
  // Recréée si la config change (ex. l'admin vient de modifier la
  // fréquence par défaut) -- jamais une ancienne fréquence qui
  // continuerait de tourner en arrière-plan.
  useEffect(() => {
    if (!isTech || !effectiveConfig) return;
    const intervalMs = Math.max(1, effectiveConfig.frequencyMinutes) * 60 * 1000;
    const id = setInterval(() => {
      if (shouldShowReminder(effectiveConfig, nowTs())) openPopup();
    }, intervalMs);
    return () => clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isTech, effectiveConfig]);

  // Minuterie d'AUTO-FERMETURE -- séparée de la fréquence ci-dessus,
  // demandé explicitement ("deux durées distinctes"). Se ferme toute
  // seule si aucune réaction, jamais de segment soumis dans ce cas --
  // la session en cours continue simplement d'être suivie, la
  // PROCHAINE confirmation réussie couvrira toute la période cumulée.
  //
  // Timeline hub (backlog, livraison #119) : émet "rappel_sans_reaction"
  // ICI SEULEMENT -- jamais sur "Fermer"/snooze (des actions
  // EXPLICITES, une forme de réaction même sans choisir de ticket) ;
  // "sans réaction/fermeture" (demandé tel quel) ne colle qu'au cas où
  // rien n'a été touché du tout. session/tickets lus depuis la
  // fermeture (closure) de cet effet -- stables pendant toute la durée
  // d'affichage du popup, aucun des deux ne change tant qu'il reste
  // ouvert (voir handleConfirm/openPopup).
  useEffect(() => {
    if (!showPopup || !effectiveConfig) return;
    const id = setTimeout(() => {
      const currentTicket = tickets.find((t) => t.id === session?.currentTicketId);
      postHubEvent(prefsApiBase, {
        login,
        category: "rappel_sans_reaction",
        label: currentTicket ? `#${currentTicket.id} — ${currentTicket.subject}` : null,
      });
      setShowPopup(false);
    }, Math.max(5, effectiveConfig.popupDurationSeconds) * 1000);
    return () => clearTimeout(id);
  }, [showPopup, effectiveConfig]);

  const handleConfirm = async (ticketId) => {
    const now = nowTs();
    const segment = computeSegmentToSubmit(session, now);
    if (segment) await submitTimeSegment(ticketsApiBase, segment, login);
    // Bug corrigé (backlog, constaté sur la version #105) : confirmer
    // un ticket ne touchait jusqu'ici JAMAIS son statut -- "en cours"
    // (tickets/api/app.py, first_in_progress_ts) ne se déclenche que
    // sur un changement de statut vers un type "en_cours", jamais sur
    // la seule présence d'un segment de temps. Bascule automatique
    // confirmée avec la personne -- jamais si déjà sur un statut de
    // ce type (voir pickAutoInProgressStatutId), jamais si aucun n'est
    // configuré (null -- dégrade proprement, aucune bascule tentée).
    const confirmedTicket = tickets.find((t) => t.id === ticketId);
    const autoStatutId = pickAutoInProgressStatutId(statuts, confirmedTicket?.statut_id);
    if (autoStatutId) await updateTicketStatus(ticketsApiBase, ticketId, autoStatutId);
    // Timeline hub (backlog, livraison #119) : "changement_activite"
    // -- seulement si la confirmation change RÉELLEMENT de ticket par
    // rapport à la session en cours (reconfirmer le MÊME ticket n'est
    // pas un changement d'activité, juste une confirmation de
    // présence -- jamais un événement dans ce cas). Pas de session
    // précédente (toute première confirmation) -- pas de changement
    // non plus, rien à comparer.
    if (session?.currentTicketId && session.currentTicketId !== ticketId) {
      postHubEvent(prefsApiBase, {
        login,
        category: "changement_activite",
        label: confirmedTicket ? `#${confirmedTicket.id} — ${confirmedTicket.subject}` : null,
        data: { fromTicketId: session.currentTicketId, toTicketId: ticketId },
      });
    }
    const newSession = nextSession(ticketId, now);
    setSession(newSession);
    saveReminderSession(prefsApiBase, login, newSession); // jamais bloquant pour la fermeture du popup
    setShowPopup(false);
  };

  const handleSnoozeMinutes = async (minutes) => {
    const until = nowTs() + minutes * 60;
    const updated = { ...DEFAULT_TECH_REMINDER_PREFS, snooze_until_ts: until };
    await saveTechReminderPrefs(prefsApiBase, login, updated);
    setEffectiveConfig((prev) => ({ ...prev, snoozeUntilTs: until }));
    setShowPopup(false);
  };

  const handleSnoozeUntilReconnect = async () => {
    const updated = { ...DEFAULT_TECH_REMINDER_PREFS, snooze_until_reconnect: true };
    await saveTechReminderPrefs(prefsApiBase, login, updated);
    setEffectiveConfig((prev) => ({ ...prev, snoozeUntilReconnect: true }));
    setShowPopup(false);
  };

  if (!isTech || !showPopup || !effectiveConfig) return null;

  const currentTicket = tickets.find((t) => t.id === session?.currentTicketId);
  const message = currentTicket
    ? effectiveConfig.messageState.replace("{ticket}", `#${currentTicket.id} — ${currentTicket.subject}`)
    : effectiveConfig.messageAsk;

  return (
    <div className="reminder-overlay" onClick={() => setShowPopup(false)}>
      <div className="reminder-popup" onClick={(e) => e.stopPropagation()}>
        <h3>⏰ Rappel d'activité</h3>
        <p>{message}</p>

        {ticketsLoading && <p className="muted">Chargement des tickets…</p>}
        {!ticketsLoading && tickets.length === 0 && <p className="muted">Aucun ticket ouvert.</p>}
        {!ticketsLoading && tickets.length > 0 && (
          <div className="reminder-ticket-list">
            {tickets.map((t) => (
              <div
                key={t.id}
                className={`reminder-ticket-item${t.id === session?.currentTicketId ? " selected" : ""}`}
              >
                <button className="reminder-ticket-select" onClick={() => handleConfirm(t.id)}>
                  {t.id === session?.currentTicketId ? "✓ " : ""}#{t.id} — {t.subject}
                </button>
                {ticketsPortalUrl && (
                  <a href={ticketsPortalUrl} target="_blank" rel="noreferrer" title="Ouvrir ce ticket">
                    ↗
                  </a>
                )}
              </div>
            ))}
          </div>
        )}

        {/* Clôture différée -- le temps du ticket qu'on vient de
            choisir n'est comptabilisé qu'au PROCHAIN rappel (voir
            settingsClient.js, computeSegmentToSubmit) : tickets-api
            n'a pas de notion de segment ouvert. Dit explicitement
            plutôt que de laisser croire qu'"acquitter" enregistre du
            temps immédiatement -- source de confusion réelle
            remontée (deux confirmations, aucun des deux tickets ne
            semblait "en cours"). */}
        {!ticketsLoading && tickets.length > 0 && (
          <p className="muted reminder-deferred-note">
            Le temps du ticket choisi sera comptabilisé au prochain rappel.
          </p>
        )}

        <div className="reminder-actions">
          <button className="secondary" onClick={() => handleSnoozeMinutes(60)}>
            Ne plus demander pendant 60 min
          </button>
          <button className="secondary" onClick={handleSnoozeUntilReconnect}>
            Ne plus demander jusqu'à reconnexion
          </button>
          <button onClick={() => setShowPopup(false)}>Fermer</button>
        </div>
      </div>
    </div>
  );
}
