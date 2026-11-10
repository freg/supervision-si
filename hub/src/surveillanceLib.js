// Liste de surveillance (livraison #1001) -- logique pure, testée (hub/tests/surveillanceLib.test.mjs).
// Une cible s'identifie sur chacun des éléments qui la caractérisent ; les discordances servent à apprendre (confirmer)
// autant qu'à signaler une usurpation possible.

export const LOT = 0;

export const STATUTS = {
  reconnu: { libelle: "reconnu", couleur: "var(--ok)", urgence: "info" },
  probable: { libelle: "probable", couleur: "var(--warning)", urgence: "alerte" },
  lot: { libelle: "du lot, à attribuer", couleur: "var(--accent)", urgence: "alerte" },
  discordant: { libelle: "discordance", couleur: "var(--danger)", urgence: "critique" },
  verifier: { libelle: "reconnu, à vérifier", couleur: "var(--warning)", urgence: "alerte" },   // #1006 : reconnu malgré une discordance faible
};

/** #1006 : statut affiché -- un repère reconnu qui porte une discordance (ex. nom annoncé différent) est « à vérifier ». */
export function statutAffiche(r) {
  if (!r) return null;
  return r.statut === "reconnu" && !r.decision && (r.discordances || []).length ? "verifier" : r.statut;
}

export function dateFr(ts) {
  if (!ts) return "—";
  const d = new Date(Number(ts) * 1000);
  return Number.isNaN(d.getTime()) ? "—" : d.toLocaleString("fr-FR", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" });
}

export function libelleElement(e) {
  return (e && (e.libelle || e.serie || e.mac)) || "élément sans nom";
}

export function raccordement(c = {}) {
  return [c.device && `borne / commutateur ${c.device}`, c.port && `port ${c.port}`, c.ssid && `SSID ${c.ssid}`, c.vlan && `VLAN ${c.vlan}`].filter(Boolean).join(", ");
}

/** Texte complet (copiable) d'un repère : client vu, preuves pondérées, discordances, décision. */
export function texteRepere(r) {
  if (!r) return "";
  const c = r.client || {};
  const l = [
    `Liste : ${r.liste} — ${r.element_id === LOT ? "élément à attribuer (du lot)" : libelleElement(r)}`,
    `Statut : ${(STATUTS[r.statut] || {}).libelle || r.statut} — score ${r.score}/100${r.decision ? ` — décision : ${r.decision}${r.decide_par ? ` par ${r.decide_par}` : ""}` : ""}`,
    `Client vu : ${c.name || "sans nom"} — MAC ${r.mac}${c.ip ? ` — IP ${c.ip}` : ""}`,
    c.manufacturer || c.os ? `Fabricant / système annoncés : ${c.manufacturer || "?"} / ${c.os || "?"}` : null,
    raccordement(c) ? `Raccordement : ${raccordement(c)}` : null,
    `Vu du ${dateFr(r.premier)} au ${dateFr(r.dernier)}`,
    "",
    "Éléments concordants (poids) :",
    ...(r.preuves || []).map((p) => `  ${p.poids > 0 ? "+" : ""}${p.poids}  ${p.element} : ${p.texte}`),
  ];
  if ((r.discordances || []).length) {
    l.push("", "Discordances :", ...r.discordances.map((d) => `  [${d.force}] ${d.texte}`));
    l.push("", "Confirmer = c'est bien l'élément (la MAC est apprise) ; Rejeter = autre appareil, ne plus proposer.");
  }
  return l.filter((x) => x !== null).join("\n");
}

/** Repères à traiter : discordances et repères du lot sans décision, puis repères probables sans décision. */
export function aTraiter(reperes = []) {
  const ouverts = reperes.filter((r) => !r.decision);
  const rang = { discordant: 0, lot: 1, verifier: 2, probable: 3 };
  return ouverts.filter((r) => statutAffiche(r) in rang).sort((a, b) => rang[statutAffiche(a)] - rang[statutAffiche(b)] || (b.dernier || 0) - (a.dernier || 0));
}

export function etatElement(e) {
  const r = e && e.dernier_repere;
  if (!r) return { texte: "pas encore repéré", couleur: "var(--muted)" };
  const s = STATUTS[statutAffiche(r)] || { libelle: r.statut, couleur: "var(--muted)" };
  const pourquoi = statutAffiche(r) === "verifier" ? ` (${r.discordances[0].texte.split(" (")[0]})` : "";
  return { texte: `${s.libelle}${r.decision === "confirme" ? " (confirmé)" : ""}${pourquoi} — ${dateFr(r.dernier)}`, couleur: s.couleur };
}

export function parListe(elements = []) {
  const out = {};
  for (const e of elements) (out[e.liste] = out[e.liste] || []).push(e);
  return out;
}
