// Logique pure des onglets d'exploitation de la tuile Serveur de messagerie (#752) : incidents (constats de la sonde
// mail-server ouverts / clos, durée), conduite à tenir par constat, réglages modifiés, âges et tailles.

export const fmtAge = (s) => (s == null ? "—" : s < 90 ? `${s} s` : s < 5400 ? `${Math.round(s / 60)} min` : s < 172800 ? `${Math.round(s / 3600)} h` : `${Math.round(s / 86400)} j`);

// Conduite à tenir par code de constat de la sonde mail-server : ce qu'il faut regarder et l'onglet qui permet d'agir.
export const PLAYBOOK = {
  "queue-write-error": { label: "Refus temporaires 451 (filtre avant file)", todo: "Amavis ou l'antivirus ne répond plus : vérifier les services, le nombre de processus Amavis et le délai du filtre (Réglages : max_servers, smtpd_proxy_timeout).", tab: "reglages" },
  "amavis-trouble": { label: "Amavis en erreur", todo: "Lire le journal (onglet Journal, programme amavis) ; base SQL, antivirus, délai. Redémarrage d'Amavis par un réglage si besoin.", tab: "journal" },
  "service-down": { label: "Service arrêté", todo: "Redémarrer le service sur le serveur ; la file se videra seule (onglet File d'attente : « Relancer la file »).", tab: "file" },
  "queue-backlog": { label: "File chargée", todo: "Onglet File d'attente : domaine distant et motif qui bloquent ; relancer, retenir ou supprimer.", tab: "file" },
  "spam-false-positive": { label: "Faux positifs probables", todo: "Quarantaine : libérer, puis adoucir le score de l'expéditeur (règles de protection) ou relever le seuil de blocage.", tab: "quarantaine" },
  "blacklist-to": { label: "Destinataire en liste noire SpamAssassin", todo: "Retirer la règle blacklist_to de la configuration SpamAssassin (pénalité +10 sur tout son courrier).", tab: "listes" },
  "antivirus-outdated": { label: "Signatures antivirus anciennes", todo: "freshclam : accès réseau, miroir, quota ; relancer la mise à jour.", tab: "journal" },
  "dnsbl-ignored": { label: "Listes DNS consultées sans effet", todo: "Réglages : postscreen_dnsbl_action = enforce (ou drop).", tab: "reglages" },
  "spam-discard-silent": { label: "Spam supprimé sans quarantaine", todo: "Réglages : final_spam_destiny, ou politique Amavis avec quarantaine.", tab: "reglages" },
  "spam-threshold-low": { label: "Seuil de blocage bas", todo: "Réglages : sa_kill_level_deflt, ou politique du domaine / de la boîte.", tab: "reglages" },
  "quarantine-short": { label: "Quarantaine trop courte", todo: "Allonger la conservation de la quarantaine (Modoboa : paramètres Amavis).", tab: "quarantaine" },
  "log-retention-short": { label: "Journal conservé trop peu", todo: "logrotate de /var/log/mail.log : rotate / weekly à allonger.", tab: "journal" },
  "os-eol": { label: "Système hors support", todo: "Planifier la migration du serveur.", tab: null },
  "log-unreadable": { label: "Journal illisible", todo: "Chemin du journal dans les arguments de la sonde ; droits de lecture.", tab: null },
};
export const playbook = (code) => PLAYBOOK[code] || { label: code, todo: "Voir le message du constat.", tab: null };

const ts = (e) => (typeof e.at === "number" ? e.at * 1000 : Date.parse(e.at));

/** Événements probe-alert / probe-recovered de la sonde mail-server -> incidents {code, severity, opened, closed, duration_s, message}. */
export function incidentsFrom(events, now = Date.now()) {
  const evs = (events || []).filter((e) => (e.details || {}).task === "plugin:mail-server" && ["probe-alert", "probe-recovered"].includes(e.kind))
    .sort((a, b) => ts(a) - ts(b));
  const open = {}, closed = [];
  for (const e of evs) {
    for (const code of (e.details || {}).codes || []) {
      if (e.kind === "probe-alert") {
        if (open[code]) { open[code].severity = e.severity; continue; }      // aggravation : même incident
        open[code] = { code, severity: e.severity, opened: ts(e), closed: null, message: e.message };
      } else if (open[code]) {
        closed.push({ ...open[code], closed: ts(e), duration_s: Math.round((ts(e) - open[code].opened) / 1000) });
        delete open[code];
      }
    }
  }
  const opened = Object.values(open).map((i) => ({ ...i, duration_s: Math.round((now - i.opened) / 1000) }));
  const byCode = {};
  for (const i of [...opened, ...closed]) {
    const c = byCode[i.code] || (byCode[i.code] = { code: i.code, count: 0, total_s: 0 });
    c.count += 1; c.total_s += i.duration_s || 0;
  }
  return { open: opened.sort((a, b) => a.opened - b.opened), closed: closed.sort((a, b) => b.opened - a.opened),
    byCode: Object.values(byCode).sort((a, b) => b.count - a.count) };
}

/** Réglages modifiés seulement : {postfix: {clé: valeur}, amavis: {…}} ; null si rien n'a changé. */
export function settingsDiff(current, draft) {
  const out = { postfix: {}, amavis: {} };
  for (const g of ["postfix", "amavis"]) {
    for (const row of current?.[g] || []) {
      const v = draft?.[g]?.[row.key];
      if (v !== undefined && String(v).trim() !== "" && String(v).trim() !== String(row.value ?? "")) out[g][row.key] = String(v).trim();
    }
  }
  return Object.keys(out.postfix).length || Object.keys(out.amavis).length ? out : null;
}

export const LIST_TONE = { blanche: "good", noire: "bad", grise: "warn", neutre: "neutral" };

/** Entrées de toutes les tables, à plat, filtrées par couleur et texte : [{path, role, type, key, value, list, editable}]. */
export function flatEntries(lists, colour = "", text = "") {
  const t = text.trim().toLowerCase(), out = [];
  for (const m of lists?.maps || []) for (const e of m.entries || []) out.push({ path: m.path, role: m.role, type: m.type, editable: m.editable, ...e });
  for (const p of lists?.postgrey || []) for (const e of p.entries || []) out.push({ path: p.path, role: "postgrey (greylisting évité)", type: "postgrey", editable: p.editable, ...e });
  return out.filter((e) => (!colour || e.list === colour) && (!t || `${e.key} ${e.value} ${e.role}`.toLowerCase().includes(t)));
}
