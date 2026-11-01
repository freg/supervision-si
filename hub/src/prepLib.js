// Migration › Préparer la réinstallation d'un nœud (livraison #815) : fonctions pures (tests : tests/prepLib.test.mjs).

export const TON = { ok: "good", attention: "warn", bloquant: "bad", inconnu: "neutral" };
export const SYMBOLE = { ok: "✔", attention: "⚠", bloquant: "⛔", inconnu: "?" };
export const HYPOTHESES = [
  ["debit_restore", "restauration (Mo/s)"], ["debit_lan", "envoi LAN → nœud (Mo/s)"], ["ip_min", "déplacement IP OVH (min)"],
  ["demarrage_min", "démarrage (min)"], ["quorum_min", "reprise du quorum (min)"],
];

/** Paramètres de /migration/preparation (vides omis, transférés triés). */
export function requete({ cible, accueil, params = {}, transferes = [] } = {}) {
  const p = new URLSearchParams();
  if (cible) p.set("cible", cible);
  if (accueil) p.set("accueil", accueil);
  for (const [k] of HYPOTHESES) if (params[k] !== undefined && params[k] !== "" && params[k] !== null) p.set(k, String(params[k]));
  if (transferes.length) p.set("transferes", [...transferes].sort((a, b) => a - b).join(","));
  return p.toString();
}

/** Âge en heures -> « 3 h », « 2 j », « — ». */
export function fmtAgeH(h) {
  if (h == null || Number.isNaN(Number(h))) return "—";
  if (h < 1) return `${Math.max(1, Math.round(h * 60))} min`;
  if (h < 48) return `${Math.round(h)} h`;
  return `${Math.round(h / 24)} j`;
}

/** Minutes -> « 25 min », « 1 h 40 », « — ». */
export function fmtMin(m) {
  if (m == null || Number.isNaN(Number(m))) return "—";
  if (m < 60) return `${Math.round(m)} min`;
  const h = Math.floor(m / 60), r = Math.round(m % 60);
  return `${h} h${r ? ` ${String(r).padStart(2, "0")}` : ""}`;
}

/** Octets -> « 370 Go », « 1,2 To ». */
export function fmtOctets(o) {
  if (!o) return "—";
  if (o >= 1e12) return `${(o / 1e12).toFixed(1).replace(".", ",")} To`;
  if (o >= 1e9) return `${Math.round(o / 1e9)} Go`;
  return `${Math.round(o / 1e6)} Mo`;
}

/** Taux de réponses HTTP 5xx en % (ou null). */
export function taux5xx(c) {
  if (!c?.http_total) return null;
  return Math.round((10000 * (c.http_5xx || 0)) / c.http_total) / 100;
}

/** Compteurs de verdicts d'une liste d'invités (clé : sante | sauvegardes | pra). */
export function compte(invites = [], cle) {
  const out = { ok: 0, attention: 0, bloquant: 0, inconnu: 0 };
  for (const i of invites) out[i?.[cle]?.verdict || "inconnu"] += 1;
  return out;
}
