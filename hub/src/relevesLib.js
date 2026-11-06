// #974 : calendrier des relèves de l'historique des clients Nebula -- une diode par heure (logique pure, testée sous Node).
// noir : pas de relève ; rouge : relève en erreur (rien d'enregistré) ; bleu : rien de nouveau ; vert : du neuf (MAC, IP, nom,
// fabricant, équipement de raccordement, correspondance avec le registre).

export const ETATS = {
  noir: { libelle: "pas de relève", couleur: "var(--bg)" },
  rouge: { libelle: "relève en erreur", couleur: "var(--danger)" },
  bleu: { libelle: "rien de nouveau", couleur: "var(--accent)" },
  vert: { libelle: "nouvelles informations", couleur: "var(--ok)" },
};
export const NOUVEAUTES = [
  ["correspondances", "correspondance(s) avec le registre"], ["macs", "nouvelle(s) MAC"], ["ips", "nouvelle(s) IP"],
  ["noms", "nouveau(x) nom(s)"], ["fabricants", "nouveau(x) fabricant(s)"], ["raccordements", "nouvel(s) équipement(s) de raccordement"],
];
const RANG = { vert: 3, bleu: 2, rouge: 1, noir: 0 };
const JOURS = ["dim.", "lun.", "mar.", "mer.", "jeu.", "ven.", "sam."];
const deux = (n) => String(n).padStart(2, "0");
export const cleJour = (d) => `${d.getFullYear()}-${deux(d.getMonth() + 1)}-${deux(d.getDate())}`;

/** Comptes de nouveautés additionnés. */
export function sommeN(a, b) {
  const out = { ...(a || {}) };
  for (const [k, v] of Object.entries(b || {})) out[k] = (out[k] || 0) + (v || 0);
  return out;
}

/** -> [{jour, libelle, cases: [{h, etat, ids, clients, n, erreurs, futur}]}], jour le plus récent en premier (heure locale).
 *  Plusieurs relèves dans la même heure : la plus parlante l'emporte (vert > bleu > rouge). */
export function grilleReleves(releves, { jours = 14, maintenant = Date.now() } = {}) {
  const parCle = new Map();
  for (const r of releves || []) {
    const d = new Date(r.at * 1000);
    const k = `${cleJour(d)}|${d.getHours()}`;
    const c = parCle.get(k) || { etat: "noir", ids: [], clients: null, n: {}, erreurs: [] };
    if (RANG[r.etat] > RANG[c.etat]) c.etat = r.etat;
    c.ids.push(r.id);
    if (r.clients != null) c.clients = Math.max(c.clients || 0, r.clients);
    c.n = sommeN(c.n, r.n);
    if (r.error) c.erreurs.push(r.error);
    parCle.set(k, c);
  }
  const now = new Date(maintenant);
  const out = [];
  for (let i = 0; i < jours; i++) {
    const d = new Date(now.getFullYear(), now.getMonth(), now.getDate() - i);
    const j = cleJour(d);
    out.push({
      jour: j, libelle: `${JOURS[d.getDay()]} ${deux(d.getDate())}/${deux(d.getMonth() + 1)}`,
      cases: Array.from({ length: 24 }, (_, h) => {
        const futur = i === 0 && h > now.getHours();
        const c = parCle.get(`${j}|${h}`);
        return { h, futur, ...(c || { etat: "noir", ids: [], clients: null, n: {}, erreurs: [] }) };
      }),
    });
  }
  return out;
}

/** Comptes par état sur la grille (cases passées seulement). */
export function bilan(grille) {
  const b = { noir: 0, rouge: 0, bleu: 0, vert: 0 };
  for (const j of grille || []) for (const c of j.cases) if (!c.futur) b[c.etat] += 1;
  return b;
}

/** Texte court des nouveautés : « 2 nouvelle(s) MAC · 1 nouvelle(s) IP ». */
export function texteNouveautes(n) {
  return NOUVEAUTES.filter(([k]) => n?.[k]).map(([k, l]) => `${n[k]} ${l}`).join(" · ");
}

// #976 : calendrier d'activité localisé d'un terminal -- une case par heure : lieu où il a passé le plus de temps (pièce
// du plan, sinon borne, sinon SSID), d'après ses sessions (historique des clients, /reperage/parc/terminal/<id>).
export const COULEURS_LIEUX = ["var(--accent)", "var(--ok)", "var(--warning)", "var(--danger)", "var(--text)"];
export const nomLieu = (l) => l?.piece || l?.borne || (l?.port ? `port ${l.port}` : null) || l?.ssid || "lieu inconnu";

export function grilleActivite(lieux, { jours = 14, maintenant = Date.now() } = {}) {
  const now = new Date(maintenant);
  const total = new Map();
  const lignes = [];
  for (let i = 0; i < jours; i++) {
    const d = new Date(now.getFullYear(), now.getMonth(), now.getDate() - i);
    const cases = [];
    for (let h = 0; h < 24; h++) {
      const t0 = new Date(d.getFullYear(), d.getMonth(), d.getDate(), h).getTime() / 1000;
      const t1 = t0 + 3600;
      const futur = t0 * 1000 > maintenant;
      const parLieu = new Map();
      const sessions = [];
      for (const l of lieux || []) {
        if (l.de < t1 && l.a >= t0) {                                  // une vue ponctuelle (de = a) compte pour son heure
          const k = nomLieu(l);
          parLieu.set(k, (parLieu.get(k) || 0) + Math.max(1, Math.min(l.a, t1) - Math.max(l.de, t0)));
          sessions.push(l);
        }
      }
      let lieu = null, max = 0;
      for (const [k, v] of parLieu) if (v > max) { lieu = k; max = v; }
      if (lieu) total.set(lieu, (total.get(lieu) || 0) + 1);
      cases.push({ h, futur, lieu, sessions });
    }
    lignes.push({ jour: cleJour(d), libelle: `${JOURS[d.getDay()]} ${deux(d.getDate())}/${deux(d.getMonth() + 1)}`, cases });
  }
  const legende = [...total.entries()].sort((a, b) => b[1] - a[1]).map(([lieu, heures], i) => ({ lieu, heures, couleur: COULEURS_LIEUX[i] || "var(--muted)" }));
  return { lignes, legende, couleur: Object.fromEntries(legende.map((l) => [l.lieu, l.couleur])) };
}
