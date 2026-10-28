// #888 : onglet VPN -- opérateur d'origine (nom inverse de l'adresse publique) et stabilité des connexions par utilisateur.
// Sert au diagnostic des déconnexions : sessions courtes et reconnexions rapprochées, rapportées à l'opérateur / au type d'accès.

const OPERATEURS = [
  [/starlink\.com$/i, "Starlink", "satellite"],
  [/orangecustomers\.net$|wanadoo\.fr$|\.orange\.fr$/i, "Orange", null],
  [/sfr\.net$|numericable\.fr$|sfr\.fr$/i, "SFR", null],
  [/proxad\.net$|free\.fr$|freebox\.fr$/i, "Free", null],
  [/bbox\.fr$|bouyguestelecom\.fr$|bytel\.fr$/i, "Bouygues", null],
  [/nordnet\.fr$/i, "Nordnet", "satellite"],
  [/ovh\.(net|com|fr)$|ovh\.ca$/i, "OVH", "hébergeur"],
  [/scaleway\.com$|online\.net$/i, "Scaleway", "hébergeur"],
];

/** nom inverse -> { operateur, acces } ; accès « mobile » si le nom le dit, « fixe » par défaut pour un FAI connu. */
export function operateur(nom, ip) {
  const n = String(nom || "").trim().replace(/\.$/, "");
  if (!n || n === ip) return { operateur: "", acces: "" };
  const mobile = /(^|[.-])(mobile|mob|lte|4g|5g|gprs|umts)([.-]|$)/i.test(n);
  for (const [re, nomOp, acces] of OPERATEURS) {
    if (re.test(n)) return { operateur: nomOp, acces: acces || (mobile ? "mobile" : "fixe") };
  }
  const parts = n.split(".");
  return { operateur: parts.slice(-2).join("."), acces: mobile ? "mobile" : "" };
}

const ms = (iso) => { const t = Date.parse(iso || ""); return Number.isFinite(t) ? t : null; };

/** sessions (format onglet VPN) -> [{ nom, sessions, courtes, reconnexions, mediane_s, total_s, operateurs, dernier }]
 * courte : durée < `courte_s` (session terminée) ; reconnexion : début < `reco_s` après la fin de la précédente. */
export function stabilite(sessions, { courte_s = 300, reco_s = 300 } = {}) {
  const par = new Map();
  for (const s of sessions || []) {
    const k = s.nom || s.public_key || "?";
    if (!par.has(k)) par.set(k, []);
    par.get(k).push(s);
  }
  const out = [];
  for (const [nom, liste] of par) {
    const ss = [...liste].sort((a, b) => (ms(a.debut) ?? 0) - (ms(b.debut) ?? 0));
    let courtes = 0, reconnexions = 0, total = 0;
    const durees = [], ops = new Map();
    ss.forEach((s, i) => {
      const d = s.duree_s;
      if (Number.isFinite(d)) { durees.push(d); total += d; if (!s.en_cours && d < courte_s) courtes += 1; }
      const prec = ss[i - 1];
      if (prec && !prec.en_cours && ms(prec.fin) != null && ms(s.debut) != null && ms(s.debut) - ms(prec.fin) <= reco_s * 1000 && ms(s.debut) >= ms(prec.fin)) reconnexions += 1;
      const op = operateur(s.nom_origine, s.origine);
      const lib = op.operateur ? `${op.operateur}${op.acces ? ` (${op.acces})` : ""}` : "";
      if (lib) ops.set(lib, (ops.get(lib) || 0) + 1);
    });
    durees.sort((a, b) => a - b);
    out.push({ nom, sessions: ss.length, courtes, reconnexions, total_s: total,
               mediane_s: durees.length ? durees[Math.floor(durees.length / 2)] : null,
               operateurs: [...ops.entries()].sort((a, b) => b[1] - a[1]).map(([k]) => k),
               dernier: ss.length ? ss[ss.length - 1].debut : null });
  }
  return out.sort((a, b) => (b.courtes + b.reconnexions) - (a.courtes + a.reconnexions) || b.sessions - a.sessions);
}
