// #987 : profil « campus » du hub (docs/hub-campus.md, tranche 1) -- logique pure, testée sous Node.
// - nœud du campus : hub construit avec VITE_HUB_PROFIL=campus (VM sur prodia) -> tuiles du campus seulement, y compris
//   celles qui ne montrent que les machines de CE nœud (agents, parc IA, espaces disques) ;
// - hub principal : un compte du groupe `numeria` sans droit d'administration voit le même périmètre, SANS les tuiles qui
//   montreraient les machines du bureau (agents, parc IA, espaces disques).

export const GROUPE_CAMPUS = "numeria";
export const VUES_CAMPUS = ["nebula", "equipements-site", "flux-editeurs", "reperage", "audit-securite", "datarf", "demos"];
export const VUES_NOEUD_CAMPUS = [...VUES_CAMPUS, "si-agent", "iapark", "espaces"];

const norm = (g) => String(g || "").replace(/^\//, "").toLowerCase();

/** -> "noeud" (hub du campus), "groupe" (compte du campus sur le hub principal) ou null (hub complet). */
export function profilActif(profilBuild, groups, estAdmin = false) {
  if (String(profilBuild || "").toLowerCase() === "campus") return "noeud";
  const gs = (groups || []).map(norm);
  if (!estAdmin && gs.includes(GROUPE_CAMPUS) && !gs.some((g) => ["administrateurs", "admin_hub", "techniciens", "technicien"].includes(g))) return "groupe";
  return null;
}

/** Vues autorisées par le profil (null = pas de restriction). */
export function vuesAutorisees(profil) {
  if (profil === "noeud") return new Set(VUES_NOEUD_CAMPUS);
  if (profil === "groupe") return new Set(VUES_CAMPUS);
  return null;
}

export function restreindre(vues, profil) {
  const ok = vuesAutorisees(profil);
  return ok ? new Set([...vues].filter((v) => ok.has(v))) : vues;
}

export const titreHub = (profil) => (profil ? "Hub Campus" : "Hub SI");
