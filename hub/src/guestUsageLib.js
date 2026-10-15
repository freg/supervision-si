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
export function lastActivity(row) {
  const c = [["http", webLast(row)], ["owncloud", ownLast(row)], ["mysql", mysqlLast(row)], ["login", loginLast(row)]]
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
};

export function sortGuests(rows, col = "node", dir = 1) {
  const f = SORTERS[col] || SORTERS.node;
  return [...(rows || [])].sort((a, b) => { const x = f(a), y = f(b); return (x < y ? -1 : x > y ? 1 : 0) * dir; });
}

export function filterGuests(rows, { node = "", q = "", idle = "", running = false } = {}, now = Date.now()) {
  const s = q.trim().toLowerCase();
  return (rows || []).filter((r) => (!node || r.node === node) && (!running || r.status === "running")
    && (!idle || idleClass(r, now) === idle)
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
