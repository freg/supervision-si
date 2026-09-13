// Helpers purs de la cloche de notifications du hub (livraison #490,
// généralisée #491 : SMS entrants + alertes supervision Zenoss) —
// temps relatif, titres et extraits, tons. Aucun accès réseau ici :
// tout est testable en Node nu.

/** « à l'instant », « il y a 3 min », « il y a 2 h », « il y a 5 j ».
 * Retourne "" si la date est illisible — jamais de « NaN min ». */
export function relativeTime(iso, now = new Date()) {
  if (!iso) return ""; // null/"" : new Date(null) = 1970, pas NaN !
  const t = new Date(iso);
  if (Number.isNaN(t.getTime())) return "";
  const sec = Math.floor((now.getTime() - t.getTime()) / 1000);
  if (sec < 0) return "à l'instant"; // horloge navigateur en avance
  if (sec < 60) return "à l'instant";
  const min = Math.floor(sec / 60);
  if (min < 60) return `il y a ${min} min`;
  const h = Math.floor(min / 60);
  if (h < 24) return `il y a ${h} h`;
  const d = Math.floor(h / 24);
  return `il y a ${d} j`;
}

/** Titre d'un SMS : l'expéditeur interprété, sinon le sujet, sinon
 * l'adresse d'enveloppe. */
export function smsTitle(item) {
  const sender = item?.fields?.sender;
  if (sender) return sender;
  if (item?.subject) return item.subject;
  return item?.from_addr || "?";
}

/** Extrait : le texte interprété, sinon le résumé stocké, tronqué
 * proprement (sur un espace quand c'est possible). */
export function notifExcerpt(item, max = 90) {
  const raw = (item?.fields?.text || item?.summary || "").trim();
  if (raw.length <= max) return raw;
  const cut = raw.slice(0, max);
  const lastSpace = cut.lastIndexOf(" ");
  return `${cut.slice(0, lastSpace > max / 2 ? lastSpace : max)}…`;
}

/** Titre d'une alerte Zenoss : l'équipement interprété, sinon le
 * sujet de l'e-mail. */
export function zenossTitle(item) {
  return item?.fields?.device || item?.subject || "?";
}

/** Extrait d'une alerte Zenoss : le message, complété par la
 * sévérité et la localisation quand elles sont connues. Une
 * résolution est préfixée — elle ne doit jamais passer pour une
 * alerte active. */
export function zenossExcerpt(item, max = 90) {
  const f = item?.fields || {};
  const parts = [];
  if (f.clear) parts.push("Résolution :");
  if (f.clear_message || f.message) parts.push(f.clear_message || f.message);
  if (f.severite) parts.push(`(${f.severite})`);
  if (f.localisation) parts.push(`— ${f.localisation}`);
  const raw = parts.join(" ").trim() || (item?.summary || "");
  if (raw.length <= max) return raw;
  const cut = raw.slice(0, max);
  const lastSpace = cut.lastIndexOf(" ");
  return `${cut.slice(0, lastSpace > max / 2 ? lastSpace : max)}…`;
}

/** Ton d'une ligne Zenoss : résolution = vert ; sévérité critique/
 * error = rouge ; warning = ambre ; inconnu = neutre. La sévérité
 * vient du corps de l'e-mail Zenoss (texte libre) — comparaison
 * tolérante, jamais de rouge par défaut sur du non reconnu. */
export function zenossLineTone(item) {
  const f = item?.fields || {};
  if (f.clear) return "ok";
  const sev = (f.severite || "").toLowerCase();
  if (sev.includes("crit") || sev.includes("error")) return "bad";
  if (sev.includes("warn")) return "warn";
  return "neutral";
}

/** Titre d'une notification diverse : le sujet interprété (c'est le
 * contenu, pour cette cible), sinon l'expéditeur d'enveloppe. */
export function notificationTitle(item) {
  return item?.fields?.subject || item?.subject || item?.from_addr || "?";
}

/** Extrait d'une notification diverse : l'expéditeur — le sujet est
 * déjà le titre. */
export function notificationExcerpt(item) {
  const from = item?.fields?.from || item?.from_addr;
  return from ? `de ${from}` : (item?.summary || "");
}

/** Ton du badge : rouge s'il y a des alertes supervision non lues,
 * ambre s'il reste des SMS ou des notifications diverses non lus,
 * neutre sinon. `failed` (API injoignable) reste neutre, signalé par
 * le title. */
export function bellTone({ smsUnread = 0, zenossUnread = 0, notifUnread = 0, failed = false } = {}) {
  if (failed) return "neutral";
  if (zenossUnread > 0) return "bad";
  if (smsUnread + notifUnread > 0) return "warn";
  return "neutral";
}
