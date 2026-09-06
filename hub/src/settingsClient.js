// Client pour /app-settings (prefs-api) -- paramétrage GLOBAL par
// application (pas personnel, voir preferences.js pour ça). Fonctions
// séparées du rendu pour rester testables (fetch injecté implicitement
// via globalThis.fetch, remplaçable en test comme le reste du projet).

/** Valeurs par défaut de app_settings pour l'application "tickets" --
 * TOUS les réglages globaux de cette application, pas seulement le
 * rappel d'activité (renommé après relecture : nommé à tort
 * "TECH_REMINDER" alors que ce même blob va accueillir d'autres
 * réglages au fil du temps, ex. local_requester_group ci-dessous --
 * jamais un nom qui devienne trompeur à mesure que la liste grandit).
 * Fusionnées avec ce qui est réellement enregistré (jamais de champ
 * manquant silencieusement si l'admin n'a encore rien configuré). */
export const DEFAULT_TICKETS_APP_SETTINGS = {
  // Rappel d'activité (technicien)
  message_state: "Vous travaillez actuellement sur le ticket {ticket}.",
  message_ask: "Quelle est votre activité en cours ?",
  frequency_minutes: 30,
  popup_duration_seconds: 120,
  // Import des demandeurs -- groupe Keycloak LOCAL complémentaire à
  // "demandeurs" (LDAP), demandé explicitement. Chaîne vide = aucun
  // second groupe configuré, l'import ne touche alors que
  // "demandeurs" comme avant.
  local_requester_group: "",
};

export async function fetchAppSettings(apiBase, appName) {
  try {
    const res = await fetch(`${apiBase}/app-settings?app=${encodeURIComponent(appName)}`);
    if (!res.ok) return {};
    return await res.json();
  } catch {
    return {}; // jamais bloquant -- l'appelant retombe sur ses propres défauts
  }
}

export async function saveAppSettings(apiBase, appName, data, actor) {
  try {
    const res = await fetch(
      `${apiBase}/app-settings?app=${encodeURIComponent(appName)}&actor=${encodeURIComponent(actor || "")}`,
      { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(data) }
    );
    if (!res.ok) return { ok: false, error: "échec de l'enregistrement" };
    return { ok: true, data: await res.json() };
  } catch {
    return { ok: false, error: "réseau indisponible" };
  }
}

/** Fusionne les valeurs par défaut (app_settings, application
 * "tickets") avec ce qui est réellement enregistré -- jamais un champ
 * `undefined` si l'admin n'a encore rien configuré (état normal, pas
 * une erreur). */
export function mergeTicketsAppSettings(stored) {
  return { ...DEFAULT_TICKETS_APP_SETTINGS, ...(stored || {}) };
}

// --- Préférences PERSONNELLES du rappel (namespace "tech_reminder"
// dans preferences.js, jamais confondu avec les défauts globaux
// ci-dessus) -----------------------------------------------------

export const DEFAULT_TECH_REMINDER_PREFS = {
  enabled: true,
  // null = utiliser la valeur par défaut de l'application (voir
  // mergeTicketsAppSettings) -- jamais une valeur inventée ici.
  frequency_minutes_override: null,
  popup_duration_seconds_override: null,
  snooze_until_ts: null, // epoch secondes -- "ne plus demander pour 60 min"
  snooze_until_reconnect: false, // "ne plus demander jusqu'à reconnexion au hub"
};

/** Fusionne les préférences personnelles enregistrées (namespace
 * "tech_reminder" du blob preferences.js) avec leurs défauts, PUIS
 * calcule les valeurs EFFECTIVES à utiliser (override personnel s'il
 * existe, sinon défaut de l'application). Jamais deux fonctions
 * séparées qui pourraient diverger sur cette règle de priorité. */
export function effectiveTechReminderConfig(personalPrefsStored, appSettingsStored) {
  const personal = { ...DEFAULT_TECH_REMINDER_PREFS, ...(personalPrefsStored || {}) };
  const appDefaults = mergeTicketsAppSettings(appSettingsStored);
  return {
    enabled: personal.enabled,
    frequencyMinutes: personal.frequency_minutes_override ?? appDefaults.frequency_minutes,
    popupDurationSeconds: personal.popup_duration_seconds_override ?? appDefaults.popup_duration_seconds,
    messageState: appDefaults.message_state,
    messageAsk: appDefaults.message_ask,
    snoozeUntilTs: personal.snooze_until_ts,
    snoozeUntilReconnect: personal.snooze_until_reconnect,
  };
}

/** La personne doit-elle voir le rappel MAINTENANT ? Centralise toute
 * la logique de "snooze" -- jamais recalculée différemment à deux
 * endroits. `nowTs` injecté (jamais Date.now() en dur) pour rester
 * testable. Suppose que l'appelant a DÉJÀ remis `snoozeUntilReconnect`
 * à false au moment de la reconnexion au hub (voir App.jsx) -- cette
 * fonction reste volontairement simple, elle ne fait que LIRE l'état
 * courant, jamais le modifier ni deviner un événement de connexion. */
export function shouldShowReminder(effectiveConfig, nowTs) {
  if (!effectiveConfig.enabled) return false;
  if (effectiveConfig.snoozeUntilReconnect) return false;
  if (effectiveConfig.snoozeUntilTs && nowTs < effectiveConfig.snoozeUntilTs) return false;
  return true;
}

// --- Historique des évolutions / backlog -- demandé explicitement,
// sert le contenu RÉEL de CHANGELOG.md/BACKLOG.md (monté en lecture
// seule côté prefs-api, jamais une copie figée) -------------------

export async function fetchChangelog(apiBase) {
  try {
    const res = await fetch(`${apiBase}/changelog`);
    const data = await res.json().catch(() => ({}));
    if (!res.ok) return { ok: false, error: data.error || "chargement impossible" };
    return { ok: true, content: data.content };
  } catch {
    return { ok: false, error: "réseau indisponible" };
  }
}

export async function fetchBacklog(apiBase) {
  try {
    const res = await fetch(`${apiBase}/backlog`);
    const data = await res.json().catch(() => ({}));
    if (!res.ok) return { ok: false, error: data.error || "chargement impossible" };
    return { ok: true, content: data.content };
  } catch {
    return { ok: false, error: "réseau indisponible" };
  }
}

/** Lit UNIQUEMENT le namespace "tech_reminder" du blob de préférences
 * personnelles -- jamais confondu avec le thème ou une future autre
 * préférence qui vivrait dans le même blob (voir prefs-api,
 * PUT /preferences fait déjà une fusion superficielle sûre). */
export async function fetchTechReminderPrefs(apiBase, login) {
  try {
    const res = await fetch(`${apiBase}/preferences?user=${encodeURIComponent(login)}`);
    if (!res.ok) return {};
    const data = await res.json();
    return data.tech_reminder || {};
  } catch {
    return {};
  }
}

/** Écrit UNIQUEMENT le namespace "tech_reminder" -- le PUT sous-jacent
 * fusionne superficiellement avec le reste du blob (thème compris),
 * jamais d'écrasement d'une préférence sans rapport. */
export async function saveTechReminderPrefs(apiBase, login, prefs) {
  try {
    const res = await fetch(`${apiBase}/preferences?user=${encodeURIComponent(login)}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ tech_reminder: prefs }),
    });
    if (!res.ok) return { ok: false, error: "échec de l'enregistrement" };
    return { ok: true };
  } catch {
    return { ok: false, error: "réseau indisponible" };
  }
}

// --- Session de suivi de temps "en direct" (rappel d'activité) ---------
//
// tickets-api n'a pas de notion de segment OUVERT (POST /time_entries
// exige start_ts ET end_ts dès la création, voir tickets/api/app.py) --
// le suivi "en direct" fonctionne donc par CLÔTURE DIFFÉRÉE : à chaque
// confirmation d'activité, on clôt la période depuis la DERNIÈRE
// confirmation (quel que soit le ticket qui était suivi pendant ce
// temps) et on démarre le suivi du nouveau choix. La session
// elle-même (quel ticket, depuis quand) est persistée dans les
// préférences personnelles -- survit à un rechargement de page.

/** Calcule le segment à soumettre à tickets-api lors d'une nouvelle
 * confirmation d'activité -- clôt la période depuis la DERNIÈRE
 * confirmation. `null` si c'est la toute première confirmation (rien
 * à clôturer) ou si la durée serait nulle/négative (horloge remise à
 * l'heure, session corrompue...) -- jamais un segment absurde envoyé
 * à l'API. */
export function computeSegmentToSubmit(previousSession, nowTs) {
  if (!previousSession || !previousSession.currentTicketId || !previousSession.sinceTs) return null;
  if (nowTs <= previousSession.sinceTs) return null;
  return { ticketId: previousSession.currentTicketId, startTs: previousSession.sinceTs, endTs: nowTs };
}

/** Nouvel état de session à mémoriser après une confirmation --
 * jamais recalculé différemment à deux endroits. `newTicketId` peut
 * être le MÊME ticket qu'avant (confirmation simple) ou un autre
 * (changement d'activité) -- traité identiquement ici, c'est
 * computeSegmentToSubmit qui aura déjà clos la période précédente. */
export function nextSession(newTicketId, nowTs) {
  return { currentTicketId: newTicketId, sinceTs: nowTs };
}

/** Session persistée dans un namespace SÉPARÉ de "tech_reminder"
 * (préférences déclaratives) -- l'état de suivi en cours change à
 * chaque confirmation, jamais mélangé avec les réglages that changent
 * rarement. Même garantie de fusion superficielle que le reste
 * (PUT /preferences ne touche jamais aux autres namespaces). */
export async function fetchReminderSession(apiBase, login) {
  try {
    const res = await fetch(`${apiBase}/preferences?user=${encodeURIComponent(login)}`);
    if (!res.ok) return null;
    const data = await res.json();
    return data.tech_reminder_session || null;
  } catch {
    return null;
  }
}

export async function saveReminderSession(apiBase, login, session) {
  try {
    await fetch(`${apiBase}/preferences?user=${encodeURIComponent(login)}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ tech_reminder_session: session }),
    });
  } catch {
    // Jamais bloquant -- la prochaine confirmation retentera simplement
  }
}

/** Soumet le segment calculé à tickets-api (voir computeSegmentToSubmit)
 * -- pas de nouvelle route nécessaire, réutilise POST /tickets/<id>/
 * time_entries tel quel. `technicianLogin` optionnel -- attribue le
 * segment (backlog, timeline personnelle du technicien, livraison
 * #115) ; absent, comportement historique inchangé (segment non
 * attribué). */
export async function submitTimeSegment(ticketsApiBase, segment, technicianLogin) {
  try {
    const body = { start_ts: segment.startTs, end_ts: segment.endTs };
    if (technicianLogin) body.technician_login = technicianLogin;
    const res = await fetch(`${ticketsApiBase}/tickets/${segment.ticketId}/time_entries`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    return { ok: res.ok };
  } catch {
    return { ok: false };
  }
}

/** Liste des tickets ouverts pour la popup du rappel -- même route
 * que la file d'attente technicien (tickets/api/app.py, /queue), pas
 * de duplication de logique de tri côté serveur. */
export async function fetchOpenTicketsForReminder(ticketsApiBase) {
  try {
    const res = await fetch(`${ticketsApiBase}/queue?state=open`);
    if (!res.ok) return [];
    const data = await res.json();
    return data.tickets || [];
  } catch {
    return [];
  }
}

// --- Bascule automatique vers un statut "en_cours" à la confirmation ---
// Bug remonté (constaté sur la version #105, backlog) : confirmer un
// ticket depuis le rappel soumettait bien un segment de temps (voir
// submitTimeSegment ci-dessus) mais ne touchait JAMAIS statut_id --
// or "en cours" (tickets/api/app.py, first_in_progress_ts, panneau
// "🔧 En cours depuis" de l'écran technicien) ne se déclenche QUE sur
// un changement de statut vers un type "en_cours", jamais sur la
// seule présence d'un segment de temps. Confirmé avec la personne :
// bascule automatique voulue.

/** Choisit le statut vers lequel BASCULER un ticket confirmé depuis le
 * rappel -- pure logique, testable sans réseau. Ne bascule JAMAIS si
 * le statut ACTUEL est déjà de type "en_cours" (plusieurs peuvent être
 * configurés -- ne jamais écraser un choix déjà actif ni spammer
 * l'historique d'un changement inutile) : renvoie `null` dans ce cas,
 * comme lorsqu'AUCUN statut de type "en_cours" n'est configuré du
 * tout (le schéma ne définit aucune priorité entre statuts -- le
 * PREMIER par `id`, ordre de création, sert de choix déterministe
 * s'il faut basculer). `null` = ne rien faire, jamais une exception :
 * le rappel continue de fonctionner normalement, juste sans cette
 * bascule tant qu'un statut de ce type n'existe pas. */
export function pickAutoInProgressStatutId(statuts, currentStatutId) {
  const current = (statuts || []).find((s) => String(s.id) === String(currentStatutId));
  if (current?.type === "en_cours") return null; // déjà bon, rien à faire
  const firstEnCours = (statuts || []).find((s) => s.type === "en_cours");
  return firstEnCours ? firstEnCours.id : null;
}

/** Liste des statuts configurés (avec leur `type`, voir
 * ensure_statut_type_column dans tickets/api/app.py) -- même route
 * que l'écran technicien pour le sélecteur de statut, réutilisée telle
 * quelle. */
export async function fetchStatuts(ticketsApiBase) {
  try {
    const res = await fetch(`${ticketsApiBase}/statuts`);
    if (!res.ok) return [];
    return await res.json();
  } catch {
    return [];
  }
}

/** Bascule le statut d'un ticket -- réutilise PUT /tickets/<id> tel
 * quel (même route que l'écran technicien, voir tickets/portal/src/
 * views/TechnicienView.jsx, updateField) : first_in_progress_ts et
 * ticket_status_log déjà gérés correctement là-bas, AUCUNE logique
 * dupliquée ici. */
export async function updateTicketStatus(ticketsApiBase, ticketId, statutId) {
  try {
    const res = await fetch(`${ticketsApiBase}/tickets/${ticketId}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ statut_id: statutId }),
    });
    return { ok: res.ok };
  } catch {
    return { ok: false };
  }
}

/** Liste TOUS les liens externes -- pas de filtre par rôle ici (fait
 * côté hub, voir lib.js buildFrontsList), cette fonction sert aussi
 * bien l'affichage du hub que l'écran d'administration. Échec réseau
 * -- liste vide, jamais une exception qui viderait le hub de ses
 * fronts internes (buildFrontsList reste utilisable avec
 * externalLinks: []). */
export async function fetchExternalLinks(prefsApiBase) {
  try {
    const res = await fetch(`${prefsApiBase}/external-links`);
    if (!res.ok) return [];
    return await res.json();
  } catch {
    return [];
  }
}

export async function createExternalLink(prefsApiBase, payload) {
  try {
    const res = await fetch(`${prefsApiBase}/external-links`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json().catch(() => ({}));
    return res.ok ? { ok: true, id: data.id } : { ok: false, error: data.error || "création impossible" };
  } catch {
    return { ok: false, error: "réseau indisponible" };
  }
}

export async function updateExternalLink(prefsApiBase, id, payload) {
  try {
    const res = await fetch(`${prefsApiBase}/external-links/${id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json().catch(() => ({}));
    return res.ok ? { ok: true } : { ok: false, error: data.error || "mise à jour impossible" };
  } catch {
    return { ok: false, error: "réseau indisponible" };
  }
}

export async function deleteExternalLink(prefsApiBase, id) {
  try {
    const res = await fetch(`${prefsApiBase}/external-links/${id}`, { method: "DELETE" });
    return { ok: res.ok };
  } catch {
    return { ok: false };
  }
}

/** Provisionne EN DIRECT un client OIDC Keycloak pour ce lien externe
 * -- backlog "interface d'intégration Keycloak", livraison #124.
 * Action ADMIN explicite : contrairement à postHubEvent
 * (shared/hubEvents.js), un échec ici DOIT remonter clairement --
 * jamais avalé silencieusement. `clientId` optionnel (dérivé du nom
 * du lien côté serveur si absent). */
/** Provisionne EN DIRECT un client OIDC Keycloak pour ce lien externe
 * -- backlog "interface d'intégration Keycloak", livraison #124.
 * Action ADMIN explicite : contrairement à postHubEvent
 * (shared/hubEvents.js), un échec ici DOIT remonter clairement --
 * jamais avalé silencieusement. `clientId` optionnel (dérivé du nom
 * du lien côté serveur si absent).
 *
 * `adopt` (livraison #125) -- cas réel : l'identifiant du client est
 * parfois déjà FIXÉ côté application externe (ex. trb140-sms-relay,
 * provisionné à la main en #123) -- changer l'identifiant casserait
 * cette application. `adopt: true` rattache ce lien à un client
 * Keycloak déjà existant plutôt que d'en créer un nouveau. Sur un
 * conflit (409, `existing_client: true`), remonte `existingClient`/
 * `existingRedirectUris` pour que l'écran propose l'adoption plutôt
 * que de simplement afficher une erreur bloquante. */
export async function provisionKeycloakClient(prefsApiBase, linkId, redirectUri, clientId, adopt) {
  try {
    const res = await fetch(`${prefsApiBase}/external-links/${linkId}/keycloak`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ redirect_uri: redirectUri, client_id: clientId || undefined, adopt: adopt || undefined }),
    });
    const data = await res.json().catch(() => ({}));
    if (res.ok) return { ok: true, ...data };
    return {
      ok: false,
      error: data.error || "provisionnement impossible",
      existingClient: !!data.existing_client,
      existingRedirectUris: data.existing_redirect_uris || [],
    };
  } catch {
    return { ok: false, error: "réseau indisponible" };
  }
}

/** Retire l'intégration Keycloak d'un lien -- le lien lui-même reste
 * (redevient un simple lien externe classique, voir prefs-api/app.py). */
export async function deprovisionKeycloakClient(prefsApiBase, linkId) {
  try {
    const res = await fetch(`${prefsApiBase}/external-links/${linkId}/keycloak`, { method: "DELETE" });
    const data = await res.json().catch(() => ({}));
    return res.ok ? { ok: true } : { ok: false, error: data.error || "retrait impossible" };
  } catch {
    return { ok: false, error: "réseau indisponible" };
  }
}

/** Charge la fenêtre glissante d'événements pour la timeline du hub
 * (voir hubTimelineLib.js pour le regroupement) -- lecture SEULE,
 * jamais partagée avec tickets/portal contrairement à postHubEvent
 * (shared/hubEvents.js) : seule la timeline elle-même (hub) affiche
 * ces événements pour l'instant. `sinceTs` en timestamp Unix
 * (secondes). Échec réseau -- liste vide, jamais une exception qui
 * casserait tout l'affichage. */
export async function fetchHubEvents(prefsApiBase, login, sinceTs) {
  try {
    const res = await fetch(`${prefsApiBase}/events?login=${encodeURIComponent(login)}&since=${sinceTs}`);
    if (!res.ok) return [];
    const data = await res.json();
    return data.events || [];
  } catch {
    return [];
  }
}

/** Charge le hubLayout personnel de l'utilisateur (personnalisation
 * de l'accueil, étape 2, livraison #133) -- lit le blob /preferences
 * déjà existant (même mécanisme que le thème), clé "hubLayout".
 * Absent (jamais personnalisé) -- undefined, laissé tel quel :
 * applyHubLayout (hubLayoutLib.js) gère déjà ce cas par défaut
 * (comportement identique à avant ce chantier). Échec réseau --
 * undefined aussi, jamais une exception qui viderait la grille. */
export async function fetchHubLayout(prefsApiBase, login) {
  try {
    const res = await fetch(`${prefsApiBase}/preferences?user=${encodeURIComponent(login)}`);
    if (!res.ok) return undefined;
    const data = await res.json();
    return data.hubLayout;
  } catch {
    return undefined;
  }
}

/** Sauvegarde le hubLayout personnel -- fusion superficielle déjà
 * gérée côté serveur (voir prefs-api/app.py, put_preferences), jamais
 * besoin de relire/renvoyer les autres préférences (theme, etc.) au
 * passage : un PUT ne portant QUE hubLayout ne les touche pas. */
export async function saveHubLayout(prefsApiBase, login, hubLayout) {
  try {
    const res = await fetch(`${prefsApiBase}/preferences?user=${encodeURIComponent(login)}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ hubLayout }),
    });
    return { ok: res.ok };
  } catch {
    return { ok: false };
  }
}

/** Indicateurs de présence Keycloak/gateway/vault-standalone (hub,
 * pied de page) -- livraison #138. Vérification faite CÔTÉ SERVEUR
 * (prefs-api, /status) plutôt que depuis le navigateur -- évite
 * entièrement les soucis CORS et de certificat auto-signé non
 * approuvé par CE navigateur pour vault-standalone (stack isolé, son
 * propre certificat). Échec réseau -- undefined, jamais une exception
 * qui casserait l'affichage pour un simple indicateur. */
export async function fetchInfraStatus(prefsApiBase) {
  try {
    const res = await fetch(`${prefsApiBase}/status`);
    if (!res.ok) return undefined;
    return await res.json();
  } catch {
    return undefined;
  }
}

/** Aide du hub (livraison #143) -- liste des README découverts par
 * prefs-api (voir prefs-api/app.py, _discover_readmes -- liste
 * blanche stricte côté serveur, cette fonction se contente d'appeler
 * l'API, aucune logique de sécurité à dupliquer ici). Échec réseau --
 * tableau vide, jamais une exception qui viderait l'écran d'aide. */
export async function fetchDocsList(apiBase) {
  try {
    const res = await fetch(`${apiBase}/docs`);
    if (!res.ok) return [];
    const data = await res.json();
    return Array.isArray(data.docs) ? data.docs : [];
  } catch {
    return [];
  }
}

/** Contenu d'UN document découvert -- `path` doit être l'un de ceux
 * renvoyés par fetchDocsList (prefs-api revalide de toute façon
 * contre une redécouverte en direct, jamais une confiance aveugle
 * même côté serveur -- voir le commentaire de sécurité complet
 * là-bas). Même forme de retour que fetchChangelog/fetchBacklog
 * ci-dessus, pour réutiliser exactement le même rendu markdown. */
export async function fetchDoc(apiBase, path) {
  try {
    const res = await fetch(`${apiBase}/docs/${path}`);
    const data = await res.json().catch(() => ({}));
    if (!res.ok) return { ok: false, error: data.error || "chargement impossible" };
    return { ok: true, content: data.content };
  } catch {
    return { ok: false, error: "réseau indisponible" };
  }
}

/** Documents de gouvernance VERSIONNÉS (livraison #195, demandé
 * explicitement -- "présenter versionnés dans l'aide et dans
 * iso27000") -- distinct de fetchDocsList/fetchDoc ci-dessus : ce
 * sont des fichiers BINAIRES (.docx) à TÉLÉCHARGER, jamais du
 * markdown à afficher en ligne. Échec réseau -- tableau vide, même
 * philosophie que fetchDocsList (jamais une exception qui viderait
 * l'écran). */
export async function fetchGovernanceDocuments(apiBase) {
  try {
    const res = await fetch(`${apiBase}/governance-documents`);
    if (!res.ok) return [];
    const data = await res.json();
    return Array.isArray(data) ? data : [];
  } catch {
    return [];
  }
}

/** URL directe de téléchargement -- pas d'appel fetch ici, juste
 * l'URL à mettre dans un lien `<a href>` (le navigateur gère le
 * téléchargement lui-même, inutile de faire transiter le contenu
 * binaire par le code JS). */
export function governanceDocumentDownloadUrl(apiBase, docId) {
  return `${apiBase}/governance-documents/${docId}/download`;
}
