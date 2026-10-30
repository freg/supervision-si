// #919 : analyse technique à distance -- libellés, tons et durées (module pur, testé par hub/tests/shellDistance.test.mjs).

export const STATUTS = {
  en_attente: ["en attente de l'agent", "neutral"],
  lance: ["reçue par l'agent", "neutral"],
  file: ["en file sur le poste", "neutral"],
  en_cours: ["en cours", "warn"],
  fini: ["terminée", "good"],
  interrompu: ["interrompue", "warn"],
  delai: ["délai dépassé", "bad"],
  refuse: ["refusée par le poste", "bad"],
  refuse_agent: ["refusée", "bad"],
  erreur: ["erreur", "bad"],
  perdue: ["perdue (agent redémarré ?)", "bad"],
};

export const MODES = {
  off: ["désactivées", "bad"],
  lecture: ["lecture seule", "good"],
  intervention: ["intervention autorisée", "warn"],
};

export const NIVEAUX = {
  probable: ["cause probable", "bad"],
  suspect: ["indices", "warn"],
  info: ["observations", "neutral"],
  rien: ["rien de notable", "good"],
};

export const AXES = [["materiel", "Matériel"], ["systeme", "Système"], ["viral", "Viral"]];

/** [libellé, ton] d'un statut, d'un mode ou d'un niveau (repli : la valeur brute, ton neutre). */
export const libelle = (table, cle) => table[cle] || [cle || "—", "neutral"];

/** Une commande attend-elle encore l'agent ou tourne-t-elle ? (le hub relève alors toutes les 3 s) */
export const actif = (statut) => statut === "en_attente" || statut === "lance" || statut === "file" || statut === "en_cours";

/** Durée d'une commande (debut / fin en secondes Unix ; en cours : jusqu'à `maintenant`). */
export function duree(job, maintenant = Date.now() / 1000) {
  if (!job || job.debut == null) return "—";
  const fin = job.fin != null ? job.fin : maintenant;
  const s = Math.max(0, Math.round(fin - job.debut));
  if (s < 60) return `${s} s`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m} min ${String(s % 60).padStart(2, "0")}`;
  return `${Math.floor(m / 60)} h ${String(m % 60).padStart(2, "0")}`;
}

/** Motifs de refus de la garde du poste (lignes « SI-SHELL-REFUS : ... »). */
export const refus = (sortie) => String(sortie || "").split(/\r?\n/).filter((l) => l.startsWith("SI-SHELL-REFUS")).map((l) => l.replace(/^SI-SHELL-REFUS\s*:\s*/, ""));

/** Le mode demandé est-il permis par le réglage de l'agent ? */
export const permis = (reglage, mode) => reglage === "intervention" || (reglage === "lecture" && mode === "lecture");

/** Date ISO / « AAAA-MM-JJ HH:MM:SS » -> « JJ/MM HH:MM » (heure locale du navigateur). */
export function date(iso) {
  if (!iso) return "—";
  const d = new Date(String(iso).replace(" ", "T") + (/[zZ]|[+-]\d\d:?\d\d$/.test(String(iso)) ? "" : "Z"));
  if (Number.isNaN(d.getTime())) return String(iso);
  const p = (n) => String(n).padStart(2, "0");
  return `${p(d.getDate())}/${p(d.getMonth() + 1)} ${p(d.getHours())}:${p(d.getMinutes())}`;
}
