// Exports CSV de la tuile Serveur de messagerie (#713) : Excel en français (« ; », BOM UTF-8), jamais le contenu des messages.

export function toCsv(header, rows) {
  const esc = (v) => { const s = v == null ? "" : Array.isArray(v) ? v.join(", ") : String(v); return /[";\r\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s; };
  return "﻿" + [header, ...rows].map((r) => r.map(esc).join(";")).join("\r\n");
}

export function downloadCsv(name, header, rows) {
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([toCsv(header, rows)], { type: "text/csv;charset=utf-8" }));
  a.download = name; a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 2000);
}

const t = (s) => (s ? new Date(s * 1000).toLocaleString("fr-FR") : "");
export const MAIL_EXPORTS = {
  mailbox: { header: ["Reçu", "Boîte", "Dossier", "De", "À", "Cc", "Sujet", "Taille", "Message-ID"],
    row: (m) => [m.date, m.user, m.mailbox, m.from, m.to, m.cc, m.subject, m.size, m.message_id] },
  log: { header: ["Premier", "Dernier", "Clé", "De", "À", "États", "Verdict Amavis", "Score", "mail_id", "Message-ID", "Client", "Taille"],
    row: (m) => [t(m.first), t(m.last), m.key, m.from, m.to, m.states, m.amavis?.verdict, m.amavis?.hits, m.amavis?.mail_id, m.message_id, m.client, m.size] },
  quarantine: { header: ["Reçu", "Type", "Score", "De", "À", "Sujet", "Taille", "Stocké", "Libéré", "Origine", "mail_id"],
    row: (q) => [t(q.at), q.content_label, q.score, q.from, q.to, q.subject, q.size, q.stored == null ? "" : q.stored ? "oui" : "non", q.released ? "oui" : "", q.client, q.mail_id] },
};
