// #937 : tuile « Sauvegardes » -- module pur (tons, textes, tri, filtres, export) ; testé par tests/sauvegardesLib.test.mjs.

/** Ton CSS (np-tone) d'un état d'aperçu. */
export function ton(etat) {
  return { ok: "good", attention: "warn", critique: "bad", erreur: "bad", jamais: "warn", "non relevé": "neutral", info: "neutral" }[etat] || "neutral";
}

/** Urgence du mini bouton de détail (BoutonDetail) selon l'état. */
export function urgence(etat) {
  return etat === "critique" || etat === "erreur" ? "critique" : etat === "attention" || etat === "jamais" ? "alerte" : "info";
}

/** Libellé lisible d'un état. */
export function libelle(etat) {
  return { ok: "à jour", attention: "à surveiller", critique: "critique", erreur: "injoignable / en erreur", jamais: "jamais sauvegardé", "non relevé": "non relevé" }[etat] || etat || "—";
}

const UN = (v, d = 1) => (v == null ? "—" : Number(v).toFixed(d).replace(".", ","));

/** Octets -> Go / To (virgule française). */
export function to(o) {
  if (o == null) return "—";
  if (o >= 1e12) return `${UN(o / 1e12)} To`;
  if (o >= 1e9) return `${UN(o / 1e9)} Go`;
  if (o >= 1e6) return `${UN(o / 1e6, 0)} Mo`;
  return `${Math.round(o / 1e3)} ko`;
}

/** Âge en jours -> « il y a 3 j » / « aujourd'hui ». */
export function ageTexte(j) {
  if (j == null) return "jamais";
  if (j < 1) return "aujourd'hui";
  if (j < 2) return "hier";
  return `il y a ${Math.round(j)} j`;
}

/** Texte complet (copiable) d'une ligne de poste : raison, destinations, PBS -- pour le mini bouton de détail. */
export function detailPoste(p) {
  if (!p) return "";
  const l = [`${p.hostname} (${p.agent_id}) : ${libelle(p.etat)}`];
  if (p.raison) l.push(`• ${p.raison}`);
  if (p.at) l.push(`• dernière sauvegarde de conf : ${p.at} (${ageTexte(p.age_j)})`);
  if (p.archive) l.push(`• archive : ${p.archive}${p.octets != null ? ` (${to(p.octets)})` : ""} -- ${p.confs} conf(s), ${p.montages} montage(s)`);
  if (p.destinations_ok?.length) l.push(`• destinations écrites : ${p.destinations_ok.join(", ")}`);
  if (p.destinations_ko?.length) l.push(`• destinations en échec : ${p.destinations_ko.join(", ")}`);
  if (p.pbs) l.push(p.pbs.ok ? `• PBS : poussée OK (${p.pbs.snapshot || "instantané"})` : `• PBS : poussée en échec -- ${p.pbs.erreur || "?"}`);
  else l.push("• PBS : jamais poussé vers pbs10");
  return l.join("\n");
}

/** Filtre des postes : « tous » | « a-traiter » (critique, jamais, attention) | « ok ». */
export function filtrerPostes(postes, filtre) {
  const l = postes || [];
  if (filtre === "a-traiter") return l.filter((p) => p.etat !== "ok");
  if (filtre === "ok") return l.filter((p) => p.etat === "ok");
  return l;
}

/** Récapitulatif host/VM : une ligne par hôte de secours { hote, copies, echecs, absentes, libre, plus_vieille_h, etat }. */
export function etatHote(h) {
  if (!h) return "non relevé";
  if (h.erreur) return "erreur";
  if (h.echecs > 0 || h.absentes > 0) return "critique";
  if (h.plus_vieille_h != null && h.plus_vieille_h > 48) return "attention";
  return "ok";
}

/** Points à traiter en premier (vue d'ensemble) : liste ordonnée de { etat, texte, lien? }. */
export function points(ap) {
  if (!ap) return [];
  const out = [];
  for (const p of ap.postes || []) {
    if (p.etat === "critique") out.push({ etat: "critique", texte: `${p.hostname} : ${p.raison}`, onglet: "postes" });
  }
  for (const b of ap.pbs || []) {
    if (b.etat === "erreur") out.push({ etat: "critique", texte: `PBS ${b.serveur} : ${b.erreur}`, onglet: "pbs" });
    for (const a of b.alertes || []) out.push({ etat: b.etat === "critique" ? "critique" : "attention", texte: `PBS ${b.serveur} : ${a}`, onglet: "pbs" });
  }
  for (const h of ap.copies?.hotes || []) {
    const e = etatHote(h);
    if (e !== "ok") out.push({ etat: e === "erreur" ? "critique" : e, texte: `copies ${h.hote} : ${h.erreur || `${h.echecs} échec(s), ${h.absentes} absente(s)`}`, onglet: "copies" });
  }
  if (ap.copies?.invites?.critique) out.push({ etat: "critique", texte: `${ap.copies.invites.critique} VM/CT sans copie fraîche`, onglet: "copies" });
  for (const n of ap.nas || []) {
    if (n.etat !== "ok") out.push({ etat: n.etat === "erreur" ? "critique" : n.etat, texte: `NAS ${n.nom} : ${n.erreur || "volume presque plein"}`, onglet: "nas" });
  }
  for (const p of ap.postes || []) {
    if (p.etat === "jamais") out.push({ etat: "attention", texte: `${p.hostname} : jamais sauvegardé`, onglet: "postes" });
    else if (p.etat === "attention") out.push({ etat: "attention", texte: `${p.hostname} : ${p.raison}`, onglet: "postes" });
  }
  const rang = { critique: 0, attention: 1 };
  return out.sort((a, b) => (rang[a.etat] ?? 2) - (rang[b.etat] ?? 2));
}

/** Export CSV (séparateur ; pour Excel français) des postes. */
export function csvPostes(postes) {
  const esc = (v) => `"${String(v ?? "").replace(/"/g, '""')}"`;
  const lignes = [["poste", "agent", "etat", "derniere_sauvegarde", "age_j", "archive", "octets", "confs", "montages", "destinations_ok", "destinations_ko", "pbs"].join(";")];
  for (const p of postes || []) {
    lignes.push([p.hostname, p.agent_id, p.etat, p.at || "", p.age_j != null ? String(p.age_j).replace(".", ",") : "", p.archive || "", p.octets ?? "", p.confs, p.montages,
      (p.destinations_ok || []).join(","), (p.destinations_ko || []).join(","), p.pbs ? (p.pbs.ok ? "ok" : "échec") : "jamais"].map(esc).join(";"));
  }
  return lignes.join("\r\n");
}

export const ONGLETS = [["ensemble", "Vue d'ensemble"], ["postes", "Postes"], ["pbs", "PBS (pbs10)"], ["copies", "Copies host / VM"], ["backuppc", "BackupPC"], ["nas", "NAS QNAP"]];
