// Actions suggérées du cycle agile (étape Décider) -- livraison #418.
// Logique PURE (aucun React), testée sous Node (hub/tests/cycleActions.test.mjs).
//
// Retour de tests : « action suggérée => cliquable et renvoie vers l'outil
// préconisé, et case à cocher pour simplement lancer la préconisation en
// automatique si c'est possible ». L'orchestrateur (netmap-orchestrator,
// #388) produit des suggestions portant `suggested_action` + `action_params`
// sans jamais rien exécuter lui-même ; ce module est la TABLE de
// correspondance entre ces identifiants et (1) l'outil du hub qui les
// traite, (2) la séquence d'appels d'API qui les exécute quand c'est
// possible sans saisie humaine. Une action absente d'ici reste affichée
// telle quelle (identifiant brut), jamais perdue.

export const SUGGESTED_ACTIONS = {
  netprobe_nmap_scan: {
    id: "netprobe_nmap_scan",
    label: "Scan actif nmap",
    icon: "🔎",
    tool: "netprobe",
    toolLabel: "Sondes réseau",
    requires: ["netprobeApiBase"],
    // Exécutable sans saisie : la cible netprobe est créée (ou retrouvée)
    // depuis l'IP, puis scannée -- deux appels d'API existants.
    canAuto: true,
    describe: (p) => `Scanner ${p?.ip_address || "?"} avec nmap (Sondes réseau)`,
  },
  snmp_register_target: {
    id: "snmp_register_target",
    label: "Enregistrer en cible SNMP",
    icon: "📡",
    tool: "snmp",
    toolLabel: "SNMP",
    requires: ["snmpApiBase"],
    // PAS exécutable sans saisie : une cible SNMP exige une communauté
    // (secret) que la suggestion ne connaît pas -- on renvoie vers l'outil.
    canAuto: false,
    describe: (p) => `Déclarer ${p?.ip_address || "?"} comme cible SNMP (communauté à saisir)`,
  },
};

// Résout une suggestion en action affichable : null si elle n'en porte
// aucune. `apiBases` = { netprobeApiBase, snmpApiBase, … } : une action
// dont l'outil n'est pas configuré est renvoyée avec `available: false`.
export function resolveAction(suggestion, apiBases = {}) {
  const id = suggestion?.suggested_action;
  if (!id) return null;
  const def = SUGGESTED_ACTIONS[id];
  const params = suggestion.action_params || {};
  if (!def) {
    return { id, label: id, icon: "🏷️", tool: null, toolLabel: null, canAuto: false, available: false, params, description: id };
  }
  const available = (def.requires || []).every((k) => Boolean(apiBases[k]));
  return {
    id, label: def.label, icon: def.icon, tool: def.tool, toolLabel: def.toolLabel,
    canAuto: def.canAuto && available, available, params, description: def.describe(params),
  };
}

/**
 * Exécute une suggestion exécutable. Les clients sont INJECTÉS (testable
 * sans réseau) : { netprobe: { addTarget(apiBase, ip, label), scanTarget(apiBase, id, ports) },
 *                  orchestrator: { setSuggestionStatus(apiBase, id, status) } }.
 * Renvoie { ok, steps: [{step, ok, detail}], error, summary }. Une étape en
 * échec arrête la séquence ; la suggestion n'est marquée « traitée » QUE si
 * tout a réussi -- une suggestion dont le scan a échoué reste ouverte.
 */
export async function executeSuggestion(suggestion, { apiBases = {}, clients = {} } = {}) {
  const action = resolveAction(suggestion, apiBases);
  const steps = [];
  if (!action) return { ok: false, steps, error: "aucune action suggérée", summary: "" };
  if (!action.canAuto) return { ok: false, steps, error: `« ${action.label} » ne s'exécute pas sans saisie -- ouvrir ${action.toolLabel || "l'outil"}`, summary: "" };

  try {
    if (action.id === "netprobe_nmap_scan") {
      const ip = action.params.ip_address;
      if (!ip) return { ok: false, steps, error: "suggestion sans adresse IP", summary: "" };
      const label = action.params.device_id ? `appareil #${action.params.device_id}` : ip;
      const added = await clients.netprobe.addTarget(apiBases.netprobeApiBase, ip, label);
      if (!added || added.error || !added.id) {
        steps.push({ step: "cible netprobe", ok: false, detail: added?.error || "réponse inattendue" });
        return { ok: false, steps, error: `cible netprobe : ${added?.error || "réponse inattendue"}`, summary: "" };
      }
      steps.push({ step: "cible netprobe", ok: true, detail: added.created ? `créée (#${added.id})` : `existante (#${added.id})` });
      const scan = await clients.netprobe.scanTarget(apiBases.netprobeApiBase, added.id);
      if (!scan || scan.error || scan.success === false) {
        steps.push({ step: "scan nmap", ok: false, detail: scan?.error || "échec" });
        return { ok: false, steps, error: `scan nmap : ${scan?.error || "échec"}`, summary: "" };
      }
      const ports = Array.isArray(scan.open_ports) ? scan.open_ports : [];
      steps.push({ step: "scan nmap", ok: true, detail: `${ports.length} port(s) ouvert(s)${scan.scan_duration_seconds != null ? ` en ${scan.scan_duration_seconds} s` : ""}` });
      if (apiBases.netmapOrchestratorApiBase && suggestion.id != null && clients.orchestrator?.setSuggestionStatus) {
        const st = await clients.orchestrator.setSuggestionStatus(apiBases.netmapOrchestratorApiBase, suggestion.id, "done");
        steps.push({ step: "suggestion traitée", ok: !st?.error, detail: st?.error || "marquée traitée" });
      }
      return {
        ok: true, steps, error: null,
        summary: `${ip} : ${ports.length} port(s) ouvert(s)${ports.length ? ` (${ports.slice(0, 8).map((p) => p.port ?? p).join(", ")}${ports.length > 8 ? "…" : ""})` : ""}`,
      };
    }
    return { ok: false, steps, error: `exécution non implémentée pour ${action.id}`, summary: "" };
  } catch (err) {
    steps.push({ step: "erreur", ok: false, detail: err?.message || String(err) });
    return { ok: false, steps, error: err?.message || String(err), summary: "" };
  }
}

// Suggestions à lancer automatiquement : exécutables, ouvertes, et pas
// déjà lancées dans cette session (`ranIds`, Set d'identifiants).
export function selectAutoRunnable(suggestions, apiBases = {}, ranIds = new Set()) {
  return (suggestions || []).filter((s) => {
    if (s.id == null || ranIds.has(s.id)) return false;
    if (s.status && s.status !== "open") return false;
    const a = resolveAction(s, apiBases);
    return Boolean(a && a.canAuto);
  });
}

// Préférence « lancer automatiquement », locale au navigateur ; désactivée
// par défaut : un scan actif reste un geste qu'on choisit d'automatiser.
export const AUTO_RUN_STORAGE_KEY = "hub.cycle.autoRun";

export function loadAutoRunPreference(storage) {
  try {
    return storage?.getItem(AUTO_RUN_STORAGE_KEY) === "1";
  } catch {
    return false;
  }
}

export function saveAutoRunPreference(storage, enabled) {
  try {
    storage?.setItem(AUTO_RUN_STORAGE_KEY, enabled ? "1" : "0");
    return true;
  } catch {
    return false;
  }
}
