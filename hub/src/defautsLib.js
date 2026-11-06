// #975 : défauts majeurs (notify-api /defauts) -- logique pure du bandeau, testée sous Node.
// Un défaut majeur = un mécanisme qui ne fait plus son travail ; affiché sur TOUTES les vues tant qu'il est ouvert et
// non ignoré. Réapparu après avoir été levé : de nouveau visible, même s'il avait été ignoré.

export const ouverts = (ds) => (ds || []).filter((d) => d.statut === "ouvert");
export const visibles = (ds) => ouverts(ds).filter((d) => !d.ignore);
export const ignores = (ds) => ouverts(ds).filter((d) => d.ignore);

const dt = (t) => (t ? new Date(t * 1000).toLocaleString("fr-FR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" }) : "—");

/** « 16 fois depuis le 05/11 17:40, dernière 06/11 08:40 » */
export function resume(d) {
  if (!d) return "";
  const n = d.occurrences || 1;
  return n > 1 ? `${n} fois depuis le ${dt(d.premiere)}, dernière ${dt(d.derniere)}` : `le ${dt(d.premiere)}`;
}

export function nomFichier(d, maintenant = Date.now()) {
  const j = new Date(maintenant);
  const p = (x) => String(x).padStart(2, "0");
  return `defaut-${String(d?.code || "inconnu").replace(/[^A-Za-z0-9_.-]/g, "-")}-${j.getFullYear()}${p(j.getMonth() + 1)}${p(j.getDate())}-${p(j.getHours())}${p(j.getMinutes())}.txt`;
}

/** Défaut « interne » quand les services ne peuvent pas signaler (jeton absent) : affiché comme les autres. */
export function defautsAffiches(reponse) {
  const ds = visibles(reponse?.defauts);
  if (reponse && reponse.jeton_interne === false) {
    ds.unshift({ id: "jeton", code: "notify.jeton-interne", service: "notify", titre: "Les services ne peuvent pas signaler leurs défauts majeurs",
      message: "NOTIFY_INTERNAL_TOKEN est vide dans le .env du serveur : aucun service ne peut écrire dans notify-api. Le renseigner (valeur aléatoire), puis reconstruire.",
      occurrences: 1, interne: true });
  }
  return ds;
}

/** Étiquette courte d'un défaut : le titre avant « : », 40 caractères au plus. */
export function etiquette(d) {
  const t = String(d?.titre || d?.code || "défaut").split(" : ")[0].trim();
  return t.length > 40 ? t.slice(0, 39) + "…" : t;
}

// -- #977 : erreurs à traiter des agents (si-agent /events/a-traiter) : ignorer pour la journée, lien vers l'objet --------
const SECTION_GENRE = {
  "probe-alert": "plugins", "plugin-failed": "plugins", "plugin-blocked": "plugins", "plugin-refused": "plugins",
  "backup-alert": "sauvegardes", "sauvegarde": "sauvegardes", "disk-full": "disks",
  "auth-refused": "settings", "central-auth-refused": "settings", "config-replayed": "settings", "agent-blocked": "settings",
  "agent-offline": "resume", "command": "historique",
};
export const sectionDuGenre = (kind) => SECTION_GENRE[kind] || (String(kind || "").startsWith("command") ? "historique" : "logs");

/** Lien de résolution : la fiche de l'agent, sur l'onglet de l'objet en cause ; sans agent, le journal des événements. */
export function lienAgent(item) {
  return item?.agent_id ? { view: "si-agent", agent: item.agent_id, section: sectionDuGenre(item.kind) } : { view: "si-agent", tab: "events" };
}

export const CLE_IGNORE_JOUR = "hub.alertes.ignore-jour";
export function aujourdhui(maintenant = Date.now()) {
  const d = new Date(maintenant);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}
/** {cle: "AAAA-MM-JJ"} -> seulement les clés ignorées aujourd'hui (les jours passés sont oubliés). */
export function ignoresDuJour(carte, jour = aujourdhui()) {
  return Object.fromEntries(Object.entries(carte || {}).filter(([, j]) => j === jour));
}
export function basculerIgnore(carte, cle, oui, jour = aujourdhui()) {
  const c = ignoresDuJour(carte, jour);
  if (oui) c[cle] = jour; else delete c[cle];
  return c;
}
export const actifs = (items, carte, jour = aujourdhui()) => (items || []).filter((x) => !ignoresDuJour(carte, jour)[x.cle]);
