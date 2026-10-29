// #922 : fiche agent en onglets et résumé du tableau des agents (pastille de collecte, version) -- module pur,
// testé par hub/tests/agentFiche.test.mjs.

/** Onglets de la fiche : [id, libellé, sections affichées]. Une seule section à l'écran, toutes à un clic. */
export const ONGLETS = [
  ["resume", "Résumé", ["risks", "system"]],
  ["network", "Réseau", ["network"]],
  ["hardware", "Matériel", ["hardware"]],
  ["activity", "Activité", ["activity"]],
  ["disks", "Disques et stockage", ["disks", "storage"]],
  ["ports", "Ports et services", ["ports", "services"]],
  ["logs", "Journal", ["logs"]],
  ["control", "Poste", ["control"]],
  ["plugins", "Sondes", ["plugins"]],
  ["commands", "Commandes", ["commands"]],
  ["settings", "Réglages", ["settings"]],
];

/** Onglets utilisables même quand l'agent n'a encore rien remonté. */
export const SANS_MESURE = new Set(["plugins", "commands", "settings"]);

/** Onglet qui contient une section (lien profond ?section=settings) ; null si inconnue. */
export function ongletDe(section) {
  if (!section) return null;
  const o = ONGLETS.find(([id, , s]) => id === section || s.includes(section));
  return o ? o[0] : null;
}

/** Sections visibles pour un onglet, sous la forme { risks: true, system: true } attendue par la fiche. */
export function sectionsDe(onglet) {
  const o = ONGLETS.find(([id]) => id === onglet) || ONGLETS[0];
  return Object.fromEntries(o[2].map((k) => [k, true]));
}

function duree(s) {
  if (s == null) return "?";
  if (s < 90) return `${Math.round(s)} s`;
  if (s < 5400) return `${Math.round(s / 60)} min`;
  if (s < 172800) return `${Math.round(s / 3600)} h`;
  return `${Math.round(s / 86400)} j`;
}

export const RECENT_S = 150;   // au-delà, « pas de relevé récent » (l'agent pousse toutes les 30-60 s)

/**
 * Pastille de collecte d'un agent : vert (relevés à jour), jaune (pas de relevé récent), orange (collecte incomplète
 * ou entravée : partielle, sondes bloquées, TLS non vérifié), rouge (hors ligne, jamais vu, désactivé).
 * `age` = secondes depuis le dernier contact. Renvoie { couleur, lignes } (lignes = info-bulle).
 */
export function collecte(a, age) {
  const l = [];
  if (!a) return { couleur: "rouge", lignes: ["agent inconnu"] };
  if (a.online === "never") return { couleur: "rouge", lignes: ["jamais vu : aucun contact avec le central"] };
  if (a.active === false) l.push("désactivé (requêtes refusées)");
  if (a.online === "offline") l.push(`hors ligne : dernier contact il y a ${duree(age)}`);
  if (l.length) return { couleur: "rouge", lignes: l };
  const orange = [];
  if (a.summary?.partial?.length) orange.push(`collecte partielle : ${a.summary.partial.join(", ")}`);
  if (a.blocked || a.host_blocked) orange.push(`sondes bloquées${a.blocked_reason || a.host_blocked_reason ? ` (${a.blocked_reason || a.host_blocked_reason})` : ""}`);
  if (a.insecure_tls) orange.push("TLS non vérifié");
  const recent = age == null || age <= RECENT_S;
  const base = `${a.online === "online" ? "en ligne" : a.online || "état inconnu"} · dernier relevé il y a ${duree(age)}`;
  if (orange.length) return { couleur: "orange", lignes: [base, ...orange] };
  if (!recent) return { couleur: "jaune", lignes: [`pas de relevé récent : dernier il y a ${duree(age)}`] };
  return { couleur: "vert", lignes: [base] };
}

function tuple(v) {
  return String(v || "").split(".").map((x) => parseInt(x, 10) || 0);
}

/** Version d'un agent comparée à celle servie par le central : { texte, ton, titre }. */
export function versionEtat(v, servie) {
  if (!v) return { texte: "?", ton: "neutral", titre: "version inconnue (l'agent ne l'a pas encore déclarée)" };
  if (!servie) return { texte: v, ton: "neutral", titre: `version ${v}` };
  const a = tuple(v), b = tuple(servie);
  for (let i = 0; i < Math.max(a.length, b.length); i += 1) {
    const x = a[i] || 0, y = b[i] || 0;
    if (x < y) return { texte: v, ton: "warn", titre: `à mettre à jour : le central sert la ${servie}` };
    if (x > y) return { texte: v, ton: "neutral", titre: `plus récente que la version servie (${servie})` };
  }
  return { texte: v, ton: "good", titre: "à jour" };
}
