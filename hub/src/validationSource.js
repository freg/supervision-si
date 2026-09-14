// Provenance d'un ticket à valider (livraison #497) : la file
// « imports à valider » reçoit les événements calendrier (#273), les
// demandes ProjeQtOr (#484), les e-mails (#489) et les tableaux importés
// (#497) -- le lecteur doit voir d'où vient chaque ligne. Module pur
// (testé par node --test), consommé par ValidationView.jsx.
export const SOURCE_LABELS = {
  calendar: "calendrier", ical: "calendrier", projeqtor: "ProjeQtOr", tableau: "tableau importé",
  demande: "demande (formulaire / tableau / import)",
  imap: "e-mail", supervision: "supervision", mikrotik: "MikroTik", portal: "portail", projet: "projet",
};

export function sourceText(t) {
  if (!t || !t.source_type) return "";
  const label = SOURCE_LABELS[t.source_type] || t.source_type;
  return t.source_nom ? `${label} — ${t.source_nom}` : label;
}
