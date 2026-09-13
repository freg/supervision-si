// Helpers purs de la cloche SMS du hub (livraison #490) — temps
// relatif, titre et extrait d'une notification, ton du badge.
// Aucun accès réseau ici : tout est testable en Node nu.

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

/** Titre d'une notification : l'expéditeur du SMS si interprété,
 * sinon le sujet, sinon l'adresse d'enveloppe. */
export function notifTitle(item) {
  const sender = item?.fields?.sender;
  if (sender) return sender;
  if (item?.subject) return item.subject;
  return item?.from_addr || "?";
}

/** Extrait : le texte du SMS si interprété, sinon le résumé stocké,
 * tronqué proprement (sur un espace quand c'est possible). */
export function notifExcerpt(item, max = 90) {
  const raw = (item?.fields?.text || item?.summary || "").trim();
  if (raw.length <= max) return raw;
  const cut = raw.slice(0, max);
  const lastSpace = cut.lastIndexOf(" ");
  return `${cut.slice(0, lastSpace > max / 2 ? lastSpace : max)}…`;
}

/** Ton du badge : "warn" dès qu'il y a du non lu, "neutral" sinon —
 * un SMS en attente n'est pas une panne (jamais "bad"). `failed`
 * (API injoignable) reste "neutral" mais est signalé par le title. */
export function bellTone(unread, failed = false) {
  if (failed) return "neutral";
  return unread > 0 ? "warn" : "neutral";
}
