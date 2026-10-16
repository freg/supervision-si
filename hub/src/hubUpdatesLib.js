// Mises à jour du hub en pied de page (#762) : dernières livraisons (hubUpdates.json, généré depuis le CHANGELOG par
// scripts/gen-hub-updates.py) et, pour chacune, des boutons vers les écrans nouveaux ou modifiés.
import { SINCE, THEMES } from "./hubThemes.js";

// Écrans MODIFIÉS par une livraison (les tuiles NOUVELLES viennent de SINCE) : à compléter à chaque livraison visible.
export const UPDATE_LINKS = {
  747: [{ view: "nebula", hint: "Rapports › Occupation" }],
  748: [{ view: "pve-ops", hint: "Migration › méthode directe" }],
  750: [{ view: "pve-ops", hint: "Migration › Rapatriement distant → local" }],
  751: [{ view: "pve-ops", hint: "Migration › directe sur le LAN" }],
  752: [{ view: "mailserver", hint: "Incidents, File d'attente, Échecs, Listes, Réglages" }],
  754: [{ front: "assistant", hint: "Évaluation et Journal" }, { view: "iapark", hint: "Tests" }],
  755: [{ view: "si-agent", hint: "Mises à jour" }],
  758: [{ view: "nebula", hint: "Rapports › Occupation › Anticipation" }],
  759: [{ view: "nebula", hint: "Rapports › Occupation › Anticipation" }],
  760: [{ view: "cortex", hint: "incidents « cause Wi-Fi probable »" }],
  771: [{ view: "guest-usage", hint: "Colonnes 13 mois, Inactif réel, Décision ; liste décideurs (CSV) ; fiche ⚙ : décision et suivi de migration" }],
  770: [{ view: "mailserver", hint: "Onglet Contrôles : tests fabriqués (spam, virus) et indicateurs" }],
  769: [{ view: "guest-usage", hint: "Nouvel écran : activité de chaque CT / VM et fiche de paramétrage" }, { view: "proxmox", hint: "Lien vers l'activité de la VM" }],
  768: [{ view: "repatriation", hint: "Liens vers le journal dans les erreurs" }, { view: "si-agent", hint: "Événements filtrés par lien" }],
  766: [{ view: "infra", hint: "Transferts › Tâches Proxmox en cours" }],
  765: [{ view: "repatriation", hint: "Restes sur le nœud local" }],
  764: [{ view: "repatriation", hint: "Inventaire distant" }],
  763: [{ view: "repatriation", hint: "État des données" }, { view: "infra", hint: "État des données" }, { view: "fleetviews", hint: "État des données" }, { view: "iapark", hint: "État des données" }],
};

/** Libellé d'une vue ou d'un front d'après les thèmes du hub. */
export function entryLabel(target, themes = THEMES) {
  for (const t of themes) for (const e of t.entries || []) {
    if ((target.view && e.view === target.view) || (target.front && e.front === target.front)) return e.label;
  }
  return target.view || target.front;
}

/** Livraisons à afficher, chacune avec ses liens : nouvelles tuiles (SINCE) puis écrans modifiés (UPDATE_LINKS),
 *  sans doublon ; `available(view)` / `frontUrl(front)` décident si le bouton est actif. */
export function updatesWithLinks(items, { since = SINCE, links = UPDATE_LINKS, themes = THEMES } = {}) {
  const byDelivery = {};
  for (const [key, n] of Object.entries(since)) {
    if (key.includes(":")) continue;
    (byDelivery[n] = byDelivery[n] || []).push({ view: key, isNew: true });
  }
  return (items || []).map((u) => {
    const out = [];
    for (let n = u.from || u.n; n <= u.n; n += 1) out.push(...(byDelivery[n] || []), ...(links[n] || []));
    const seen = new Set();
    const uniq = out.filter((l) => { const k = (l.view || "") + "|" + (l.front || ""); if (seen.has(k)) return false; seen.add(k); return true; });
    return { ...u, links: uniq.map((l) => ({ ...l, label: entryLabel(l, themes) })) };
  });
}

export const shortDate = (d) => (d ? `${d.slice(8, 10)}/${d.slice(5, 7)}` : "");
