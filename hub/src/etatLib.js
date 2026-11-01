// Migration › État des lieux des systèmes (livraison #857) : fonctions pures (tests : tests/etatLib.test.mjs).

export const NIVEAUX = ["urgent", "à planifier", "à surveiller", "ok", "inactif"];
export const TON = { urgent: "bad", "à planifier": "warn", "à surveiller": "warn", ok: "good", inactif: "neutral" };
export const TON_OS = { "obsolète": "bad", "fin proche": "warn", "supporté": "good", "maintenu par la distribution": "good", inconnu: "neutral", "non relevé": "neutral", "à vérifier": "warn" };
export const COULEUR = { urgent: "var(--danger)", "à planifier": "var(--warning)", "à surveiller": "#c9b458" };

export function filtrer(lignes, { texte = "", niveau = "", type = "", noeud = "" } = {}) {
  const t = texte.trim().toLowerCase();
  return (lignes || []).filter((l) => (!niveau || l.niveau === niveau) && (!type || l.type === type) && (!noeud || l.node === noeud)
    && (!t || `${l.name} ${l.libelle || ""} ${l.key} ${(l.roles || []).join(" ")} ${l.os?.nom || ""}`.toLowerCase().includes(t)));
}

/** Jours depuis la dernière mise à jour -> « 3 j », « 14 mois », « — ». */
export function depuis(j) {
  if (j == null) return "—";
  if (j < 60) return `${j} j`;
  if (j < 730) return `${Math.round(j / 30)} mois`;
  return `${Math.round(j / 365)} ans`;
}

/** Date AAAA-MM-JJ -> JJ/MM/AAAA. */
export function jour(d) {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(d || "");
  return m ? `${m[3]}/${m[2]}/${m[1]}` : "—";
}

/** Points SVG d'une série de la tendance (axe vertical commun `max`). */
export function points(tendance, cle, w = 300, h = 60, max = null) {
  const s = (tendance || []).map((t) => +(t[cle] || 0));
  if (s.length < 2) return "";
  const m = max ?? Math.max(1, ...s);
  return s.map((v, i) => `${((i / (s.length - 1)) * w).toFixed(1)},${(h - (v / m) * (h - 2) - 1).toFixed(1)}`).join(" ");
}

/** Maximum commun des séries tracées. */
export function maxTendance(tendance, cles) {
  return Math.max(1, ...(tendance || []).flatMap((t) => cles.map((k) => +(t[k] || 0))));
}

/** Nom affiché : libellé métier s'il existe. */
export function nom(l) {
  return l.libelle ? `${l.libelle} (${l.key})` : l.type === "nœud" ? `nœud ${l.name}` : `${l.name} (${l.key})`;
}
