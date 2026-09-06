// Gestionnaire de logs (hub), livraison #139 -- I/O réseau (voir
// logsLib.js pour la logique pure). Chemins RELATIFS (voir
// logsLib.js pour le raisonnement) -- jamais besoin de PREFS_API_BASE_URL
// ou d'une autre variable d'environnement ici, le navigateur résout
// déjà correctement contre l'origine courante. Exception :
// fetchPushedSources ci-dessous, qui a besoin de joindre PRÉCISÉMENT
// prefs-api (les sources externes n'y vivent que là), reçoit donc
// `prefsApiBase` en paramètre comme le reste du hub qui parle à
// prefs-api spécifiquement.

/** Charge les logs d'UN SEUL service. undefined en cas d'échec
 * (service en panne, réseau coupé, réponse non-OK) -- jamais une
 * exception qui interromprait Promise.all côté appelant. C'est
 * d'ailleurs TOUT L'INTÉRÊT de cet outil : rester utilisable même
 * quand certains services répondent mal. */
export async function fetchServiceLogs(path, limit) {
  try {
    const res = await fetch(`${path}?limit=${limit}`);
    if (!res.ok) return undefined;
    const data = await res.json();
    return Array.isArray(data.entries) ? data.entries : undefined;
  } catch {
    return undefined;
  }
}

/** Charge les logs de TOUS les services fournis (les 15 fixes, ou la
 * liste combinée avec les sources externes poussées -- livraison
 * #142) EN PARALLÈLE (jamais l'un après l'autre -- un service
 * injoignable ajouterait sinon bêtement son délai d'attente à celui
 * du suivant, comme pour /status côté prefs-api). Renvoie
 * { [serviceId]: entries[] | undefined } -- directement la forme
 * attendue par mergeLogEntries/summarizeLogEntries (logsLib.js). Un
 * service en échec vaut `undefined` dans le résultat, jamais une clé
 * absente (le tableau de bord doit voir explicitement QUELS services
 * sont en panne). `services` : paramètre OBLIGATOIRE (même
 * raisonnement que logsLib.js) -- jamais un repli implicite sur
 * LOG_SERVICES qui ferait disparaître les sources externes. */
export async function fetchAllServiceLogs(services, limit) {
  const list = Array.isArray(services) ? services : [];
  const results = await Promise.all(
    list.map((svc) => fetchServiceLogs(svc.path, limit))
  );
  const byService = {};
  list.forEach((svc, i) => {
    byService[svc.id] = results[i];
  });
  return byService;
}

/** Sources externes CONNUES (ont poussé au moins un message via
 * POST /push-log depuis le dernier redémarrage de prefs-api) --
 * livraison #142. undefined en cas d'échec réseau -- jamais une
 * exception, l'appelant retombe alors sur la liste fixe des 15
 * services seule (voir LogsManagerView.jsx). */
export async function fetchPushedSources(prefsApiBase) {
  try {
    const res = await fetch(`${prefsApiBase}/push-log/sources`);
    if (!res.ok) return undefined;
    const data = await res.json();
    return Array.isArray(data.sources) ? data.sources : undefined;
  } catch {
    return undefined;
  }
}
