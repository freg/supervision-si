// Activité des CT / VM (livraison #769) -- logique PURE de l'écran « Activité des VM » (testée sous Node :
// hub/tests/guestUsageLib.test.mjs). Données : si-agent-api /infra/guests (sonde guest-usage + inventaire Infra).
// Les dates des connexions unix (`last`) sont l'heure locale de l'invité, sans fuseau : lues comme heure locale.

const DAY = 86400000;

export function parseTime(s) {
  if (!s) return null;
  const t = Date.parse(s);
  return Number.isFinite(t) ? t : null;
}

export function ago(s, now = Date.now()) {
  const t = typeof s === "number" ? s : parseTime(s);
  if (t == null) return "—";
  const d = Math.max(0, now - t) / 1000;
  if (d < 90) return "à l'instant";
  if (d < 3600) return `il y a ${Math.round(d / 60)} min`;
  if (d < 86400) return `il y a ${Math.round(d / 3600)} h`;
  if (d < 86400 * 60) return `il y a ${Math.round(d / 86400)} j`;
  return `il y a ${Math.round(d / (86400 * 30))} mois`;
}

function ipv4(ip) {
  const p = String(ip || "").split(".");
  if (p.length !== 4 || p.some((x) => !/^\d{1,3}$/.test(x) || Number(x) > 255)) return null;
  return p.reduce((a, x) => a * 256 + Number(x), 0);
}

/** IP ignorée ? (adresse exacte, ou réseau IPv4 « a.b.c.d/n ») */
export function ipIgnored(ip, list) {
  for (const raw of list || []) {
    const [net, bits] = String(raw).split("/");
    if (bits == null) { if (net === ip) return true; continue; }
    const a = ipv4(ip), b = ipv4(net), n = Number(bits);
    if (a == null || b == null || !(n >= 0 && n <= 32)) continue;
    const size = 2 ** (32 - n);
    if (Math.floor(a / size) === Math.floor(b / size)) return true;
  }
  return false;
}

/** Dernier accès HTTP/HTTPS, hors IP ignorées de la fiche (supervision, sauvegarde…). */
export function webLast(row) {
  const w = row?.web;
  if (!w) return null;
  const ign = row.profile?.ignore_ips || [];
  if (!ign.length) return w.last ? { at: w.last.at, who: w.last.ip } : null;
  const ips = (w.ips || []).filter((i) => !ipIgnored(i.ip, ign) && i.last_at);
  if (!ips.length) return null;
  const best = ips.reduce((a, b) => ((parseTime(b.last_at) || 0) > (parseTime(a.last_at) || 0) ? b : a));
  return { at: best.last_at, who: best.ip };
}

/** Dernière connexion unix : celle des comptes de la fiche s'il y en a, sinon tous comptes confondus. */
export function loginLast(row) {
  const l = row?.login;
  if (!l?.last) return null;
  const watch = row.profile?.unix_accounts || [];
  if (!watch.length) return { at: l.last.at, who: `${l.last.user}${l.last.from ? `@${l.last.from}` : ""}` };
  const u = (l.users || []).filter((x) => watch.includes(x.user));
  if (!u.length) return null;
  const best = u.reduce((a, b) => ((parseTime(b.last_at) || 0) > (parseTime(a.last_at) || 0) ? b : a));
  return { at: best.last_at, who: `${best.user}${best.from ? `@${best.from}` : ""}` };
}

/** Dernière activité MySQL : compte de la fiche vu en session, sinon hausse du compteur de connexions. */
export function mysqlLast(row) {
  const m = row?.mysql;
  if (!m?.ok) return null;
  const user = row.profile?.mysql_user;
  if (user) {
    const u = (m.users_seen || []).find((x) => x.user === user);
    return u ? { at: u.last_seen, who: user } : null;
  }
  return m.last_activity_at ? { at: m.last_activity_at, who: (m.sessions || []).map((s) => s.user).filter((x, i, a) => a.indexOf(x) === i).slice(0, 3).join(", ") || null } : null;
}

export function ownLast(row) {
  const o = row?.web?.owncloud;
  return o?.last_at ? { at: o.last_at, who: o.last_user || null } : null;
}

/** Activité la plus récente, toutes sources -> {at, kind, who} | null */
/** #777 : dernière connexion SSH acceptée (journaux internes), si wtmp ne l'a pas. */
export function sshLast(row) {
  const s = row?.internal?.ssh_last;
  return s?.at ? { at: s.at, who: `${s.user || "?"}${s.from ? `@${s.from}` : ""}` } : null;
}

export function lastActivity(row) {
  const c = [["http", webLast(row)], ["owncloud", ownLast(row)], ["mysql", mysqlLast(row)], ["login", loginLast(row)], ["ssh", sshLast(row)],
    ["sudo", row?.internal?.sudo_last ? { at: row.internal.sudo_last } : null]]
    .filter(([, v]) => v && parseTime(v.at) != null);
  if (!c.length) return null;
  const [kind, v] = c.reduce((a, b) => (parseTime(b[1].at) > parseTime(a[1].at) ? b : a));
  return { at: v.at, kind, who: v.who };
}

export const IDLE = [
  ["actif", "moins d'1 jour", 1], ["recent", "moins de 7 jours", 7], ["calme", "moins de 30 jours", 30], ["dormant", "30 jours ou plus", Infinity],
];

/** Classe d'inactivité d'après la dernière activité : actif | recent | calme | dormant | inconnu (non relevé). */
export function idleClass(row, now = Date.now()) {
  const a = lastActivity(row);
  if (!a) return row?.collected ? "dormant" : "inconnu";
  const days = (now - parseTime(a.at)) / DAY;
  return IDLE.find(([, , lim]) => days < lim)[0];
}

/** Série de N jours (du plus ancien au plus récent), zéros compris : per_day [{day, <clé>}] -> [{day, v}] */
export function daySeries(perDay, key, days = 14, now = Date.now()) {
  const m = new Map((perDay || []).map((d) => [d.day, d[key] || 0]));
  const out = [];
  for (let i = days - 1; i >= 0; i--) {
    const d = new Date(now - i * DAY).toISOString().slice(0, 10);
    out.push({ day: d, v: m.get(d) || 0 });
  }
  return out;
}

const SORTERS = {
  node: (r) => `${r.node}/${String(r.vmid).padStart(9, "0")}`,
  name: (r) => (r.name || "").toLowerCase(),
  activity: (r) => parseTime(lastActivity(r)?.at) ?? -1,
  http: (r) => r.web?.hits7d ?? -1,
  mysql: (r) => r.mysql?.conn7d ?? (r.mysql ? 0 : -1),
  login: (r) => parseTime(loginLast(r)?.at) ?? -1,
  cpu: (r) => r.cpu?.avg24 ?? -1,
  idle: (r) => r.activity?.idle_days ?? (actClass(r) === "inactif" ? 1e6 : -1),
  months: (r) => totals12(r).active_days,
  decision: (r) => r.profile?.decision || "~",
};

export function sortGuests(rows, col = "node", dir = 1) {
  const f = SORTERS[col] || SORTERS.node;
  return [...(rows || [])].sort((a, b) => { const x = f(a), y = f(b); return (x < y ? -1 : x > y ? 1 : 0) * dir; });
}

export function filterGuests(rows, { node = "", q = "", idle = "", running = false, act = "", decision = "" } = {}, now = Date.now()) {
  const s = q.trim().toLowerCase();
  return (rows || []).filter((r) => (!node || r.node === node) && (!running || r.status === "running")
    && (!idle || idleClass(r, now) === idle)
    && (!act || actClass(r) === act)
    && (!decision || (decision === "aucune" ? !r.profile?.decision : r.profile?.decision === decision))
    && (!s || `${r.vmid} ${r.name} ${r.node} ${r.os || ""} ${r.profile?.role || ""} ${(r.profile?.https_urls || []).join(" ")}`.toLowerCase().includes(s)));
}

export function counts(rows, now = Date.now()) {
  const c = { total: rows.length, collected: 0, web: 0, mysql: 0, dormant: 0, unknown: 0 };
  for (const r of rows) {
    if (r.collected) c.collected++;
    if (r.web) c.web++;
    if (r.mysql) c.mysql++;
    const k = idleClass(r, now);
    if (k === "dormant" && r.status === "running") c.dormant++;
    if (k === "inconnu") c.unknown++;
  }
  return c;
}

// ---------------------------------------------------------------- fiche de paramétrage

export const PROFILE_FIELDS = [
  ["unix_accounts", "Comptes unix suivis", "list", "ex. www-data, deploy"],
  ["mysql_user", "Compte MySQL", "str", "ex. modoboa"],
  ["mysql_defaults_file", "Fichier d'options MySQL (dans l'invité)", "str", "/etc/mysql/debian.cnf"],
  ["https_urls", "URL HTTPS", "list", "https://…"],
  ["owncloud_url", "URL ownCloud", "str", "https://…/owncloud"],
  ["owncloud_user", "Compte ownCloud suivi", "str", ""],
  ["vault_ref", "Entrée du coffre-fort (mots de passe)", "str", "nom de l'entrée, jamais le mot de passe"],
  ["ignore_ips", "IP à ignorer (supervision, sauvegardes)", "list", "ex. 10.0.0.0/24, 192.0.2.10"],
  ["role", "Rôle", "str", "ex. messagerie, site public"],
  // #771 : décision et suivi de migration (liste pour les décideurs)
  ["decision", "Décision", "select:decision", ""],
  ["decision_reason", "Motif de la décision", "str", "ex. plus consulté depuis 2025"],
  ["decision_by", "Décidé par", "str", "ex. direction, 16/10/2026"],
  ["target", "Cible de migration", "str", "ex. pve10, archive PBS"],
  ["planned_for", "Date prévue", "date", ""],
  ["migration_status", "État de la migration", "select:status", ""],
  ["notes", "Notes", "text", ""],
];

export function profileToForm(p) {
  const f = {};
  for (const [k, , kind] of PROFILE_FIELDS) f[k] = kind === "list" ? (p?.[k] || []).join(", ") : (p?.[k] || "");
  return f;
}

const SECRET_TEXT = /(mot\s*de\s*passe|password|passwd|mdp|pwd)\s*[:=]\s*\S+/i;

/** Formulaire -> {profile, error} : listes découpées, aucun mot de passe recopié dans une note ou un champ. */
export function formToProfile(form) {
  const p = {};
  for (const [k, label, kind] of PROFILE_FIELDS) {
    const v = String(form?.[k] ?? "").trim();
    if (!v) continue;
    if (SECRET_TEXT.test(v)) return { profile: null, error: `${label} : pas de mot de passe ici -- le ranger dans le coffre-fort et indiquer le nom de l'entrée` };
    p[k] = kind === "list" ? v.split(/[,;\s]+/).map((x) => x.trim()).filter(Boolean) : v;
  }
  return { profile: p, error: null };
}

export function fmtPct(v) {
  return v == null ? "—" : `${v.toFixed(v < 10 ? 1 : 0)} %`;
}

export function fmtCount(n) {
  if (n == null) return "—";
  if (n >= 1e6) return `${(n / 1e6).toFixed(1)} M`;
  if (n >= 1e4) return `${Math.round(n / 1e3)} k`;
  return String(n);
}


// ---------------------------------------------------------------- #771 : activité réelle dans le temps

export const ACT = [
  ["actif", "activité réelle dans les 7 derniers jours", "ok"],
  ["faible", "dernière activité réelle il y a 8 à 30 jours", ""],
  ["dormant", "dernière activité réelle il y a 31 à 180 jours", "warning"],
  ["inactif", "plus de 180 jours, ou aucune sur toute la période relevée", "critical"],
  ["inconnu", "pas encore d'historique (sonde à mettre à jour, invité arrêté)", ""],
];
export const DECISIONS = [["garder", "garder"], ["migrer", "migrer"], ["archiver", "archiver puis arrêter"], ["arreter", "arrêter"], ["a_etudier", "à étudier"]];
export const MIG_STATUS = [["a_planifier", "à planifier"], ["planifiee", "planifiée"], ["en_cours", "en cours"], ["faite", "faite"], ["annulee", "annulée"]];
export const SELECTS = { decision: DECISIONS, status: MIG_STATUS };
const label = (list, k) => (list.find(([x]) => x === k) || [k, k || ""])[1];
export const decisionLabel = (k) => label(DECISIONS, k);
export const statusLabel = (k) => label(MIG_STATUS, k);

export function actClass(row) {
  return row?.activity?.class || "inconnu";
}

const frDay = (d) => (d ? `${d.slice(8, 10)}/${d.slice(5, 7)}/${d.slice(0, 4)}` : "");

/** « depuis le 01/03/2026 » ; « aucune depuis le 03/11/2025 » (début de l'historique) ; « » sans historique. */
export function idleSince(row) {
  const a = row?.activity;
  if (!a) return "";
  const ind = a.last_indirect_any && (!a.last_any || a.last_indirect_any > a.last_any) ? ` (signes indirects jusqu'au ${frDay(a.last_indirect_any)})` : "";
  if (a.last_any) return `depuis le ${frDay(a.last_any)}${ind}`;
  return a.first_day ? `aucune depuis le ${frDay(a.first_day)}${ind}` : ind.trim();
}

function monthKey(t) {
  const d = new Date(t);
  return `${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, "0")}`;
}

/** n derniers mois (du plus ancien au courant), zéros compris : [{month, v, m}] -- v = champ du mois (jours actifs par défaut). */
export function monthSeries(row, key = "active_days", n = 13, now = Date.now()) {
  const by = new Map((row?.activity?.months || []).map((m) => [m.month, m]));
  const d = new Date(now), out = [];
  for (let i = n - 1; i >= 0; i--) {
    const k = monthKey(Date.UTC(d.getUTCFullYear(), d.getUTCMonth() - i, 1));
    const m = by.get(k);
    out.push({ month: k, v: m ? (m[key] || 0) : 0, m: m || null });
  }
  return out;
}

/** Totaux des 12 derniers mois (mois courant compris). */
export function totals12(row, now = Date.now()) {
  const t = { req: 0, bytes: 0, logins: 0, mysql_q: 0, active_days: 0, bot: 0 };
  for (const { m } of monthSeries(row, "active_days", 12, now)) {
    if (m) for (const k of Object.keys(t)) t[k] += m[k] || 0;
  }
  return t;
}

const ACT_ORDER = { inactif: 0, dormant: 1, faible: 2, actif: 3, inconnu: 4 };

/** Liste pour les décideurs : les moins actifs d'abord. */
export function decisionOrder(rows) {
  return [...(rows || [])].sort((a, b) => (ACT_ORDER[actClass(a)] - ACT_ORDER[actClass(b)])
    || ((b.activity?.idle_days ?? 1e6) - (a.activity?.idle_days ?? 1e6)) || String(a.key).localeCompare(String(b.key)));
}

function csvCell(v) {
  const s = v == null ? "" : String(v);
  return /[;"\n\r]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

export const CSV_COLUMNS = [
  ["Nœud", (r) => r.node], ["VMID", (r) => r.vmid], ["Nom", (r) => r.name], ["Type", (r) => (r.type === "qemu" ? "VM" : "CT")],
  ["État", (r) => r.status], ["Rôle", (r) => r.profile?.role], ["Activité réelle", (r) => actClass(r)],
  ["Jours sans activité", (r) => r.activity?.idle_days], ["Dernière activité réelle", (r) => frDay(r.activity?.last_any)],
  ["Dernier accès web (humain)", (r) => frDay(r.activity?.last_active?.web)], ["Dernière connexion", (r) => frDay(r.activity?.last_active?.login)],
  ["Dernière activité MySQL", (r) => frDay(r.activity?.last_active?.mysql)],
  ["Accès web 12 mois", (r) => totals12(r).req], ["Volume web 12 mois (Mo)", (r) => Math.round(totals12(r).bytes / 1e6)],
  ["Connexions 12 mois", (r) => totals12(r).logins], ["Requêtes MySQL 12 mois", (r) => totals12(r).mysql_q],
  ["Jours actifs 12 mois", (r) => totals12(r).active_days], ["Historique depuis", (r) => frDay(r.activity?.first_day)],
  ["Décision", (r) => decisionLabel(r.profile?.decision)], ["Motif", (r) => r.profile?.decision_reason], ["Décidé par", (r) => r.profile?.decision_by],
  ["Cible", (r) => r.profile?.target], ["Date prévue", (r) => frDay(r.profile?.planned_for)], ["État de la migration", (r) => statusLabel(r.profile?.migration_status)],
];

/** CSV (séparateur « ; », BOM pour Excel) de la liste pour les décideurs. */
export function decisionsCsv(rows) {
  const lines = [CSV_COLUMNS.map(([h]) => csvCell(h)).join(";")];
  for (const r of decisionOrder(rows)) lines.push(CSV_COLUMNS.map(([, f]) => csvCell(f(r))).join(";"));
  return "\ufeff" + lines.join("\r\n") + "\r\n";
}
