// Thématiques de l'accueil (livraison #457) -- logique PURE, testée sous
// Node (hub/tests/hubThemes.test.mjs).
//
// Demandé : « revois toutes les tuiles pour fusionner ce qui peut l'être,
// il y a trop de tuiles et seulement quelques thématiques ». Une trentaine
// de vues et fronts sont regroupés en CINQ thématiques ; chaque
// thématique est une tuile de l'accueil et un menu de l'en-tête, qui
// ouvre une « super-tuile » (ThemeView) avec ses outils en onglets. Les
// vues elles-mêmes ne changent pas -- seule la porte d'entrée est
// regroupée. Une entrée `view` est une vue interne (viewMode) ; une
// entrée `front` renvoie à un front externe de lib.js (portail tickets,
// coffre-fort, consoles) par son identifiant.
//
// SOURCE UNIQUE : l'en-tête et l'accueil se construisent tous deux
// depuis cette liste -- jamais deux listes à maintenir.

export const THEMES = [
  { id: "supervision", name: "Supervision", icon: "🗺", description: "Supervisés, agents, sondes, onduleurs, SNMP, vigilance, cyber, logs",
    entries: [
      { view: "supervision-si", label: "Supervision SI" },
      { view: "si-agent", label: "Agents hôtes" },
      { view: "netprobe", label: "Sondes réseau" },
      { view: "ups", label: "Onduleurs (UPS)" },
      { view: "snmp", label: "SNMP" },
      { view: "vigilance", label: "Vigilance" },
      { view: "cyber", label: "Cyber" },
      { view: "logs", label: "Logs" },
      { view: "history", label: "Historique" },
      { view: "memory", label: "Mémoire" },
    ] },
  { id: "reseau", name: "Réseau", icon: "🕸", description: "Exploration, cycle agile, orchestrateur, architecture, fusion IP/MAC, Nebula, tunnels SSH",
    entries: [
      { view: "network-agent", label: "Exploration réseau" },
      { view: "network-cycle", label: "Cycle agile réseau" },
      { view: "netmap-orchestrator", label: "Orchestrateur" },
      { view: "architecture", label: "Architecture" },
      { view: "fusion", label: "Fusion IP/MAC" },
      { view: "nebula", label: "Nebula" },
      { view: "ssh-tunnels", label: "Tunnels SSH" },
    ] },
  { id: "donnees", name: "Données & référentiels", icon: "🗄", description: "Bases externes, GLPI, positions, classification, schémas, rétro-ingénierie, DBA",
    entries: [
      { view: "external-bases", label: "Bases externes" },
      { view: "glpi-inventory", label: "GLPI" },
      { view: "geo-catalog", label: "Catalogue de positions" },
      { view: "classifier", label: "Classification" },
      { view: "schema-analyzer", label: "Analyse de schémas" },
      { view: "retro", label: "Rétro-ingénierie" },
      { front: "dba", label: "DBA" },
    ] },
  { id: "documents", name: "Documents & ENT", icon: "📚", description: "ENT (agenda, tâches, relations), GED, fichiers, messagerie, tickets",
    entries: [
      { view: "ent", label: "ENT" },
      { view: "ged", label: "GED" },
      { view: "file-manager", label: "Gestionnaire de fichiers" },
      { view: "imap", label: "Client IMAP" },
      { front: "tickets", label: "Portail tickets" },
    ] },
  { id: "securite", name: "Sécurité & accès", icon: "🛡", description: "Bastion, droits, sauvegardes, coffre-fort, Keycloak, annuaire",
    entries: [
      { view: "si-proxy", label: "Bastion" },
      { view: "rights", label: "Droits" },
      { view: "backup-restore", label: "Sauvegardes" },
      { front: "vault", label: "Coffre-fort" },
      { front: "vault-admin", label: "Administration du coffre-fort" },
      { front: "keycloak-admin", label: "Administration Keycloak" },
      { front: "ldap-admin", label: "Administration OpenLDAP" },
    ] },
];

export const THEME_PREFIX = "theme:";
export const themeViewMode = (id) => `${THEME_PREFIX}${id}`;
export const isThemeViewMode = (vm) => typeof vm === "string" && vm.startsWith(THEME_PREFIX);
export const themeIdOf = (vm) => (isThemeViewMode(vm) ? vm.slice(THEME_PREFIX.length) : null);

// Tous les identifiants de fronts absorbés par une thématique (ils ne
// s'affichent plus comme tuiles isolées en mode thématique).
export function absorbedFrontIds(themes = THEMES) {
  const ids = new Set();
  for (const t of themes) for (const e of t.entries) if (e.front) ids.add(e.front);
  ids.add("supervision"); // le front « Supervision SI » est la vue supervision-si depuis #423
  return ids;
}

/** Construit les thématiques VISIBLES pour cette personne / ce déploiement.
 *  `available` : ensemble des viewModes disponibles (URL configurée, droit
 *  d'accès) ; `fronts` : liste de lib.js + tuiles internes (id, name, url,
 *  onClick). Une entrée absente est simplement omise ; une thématique sans
 *  entrée n'apparaît pas. Retourne aussi `leftover` : les fronts d'aucune
 *  thématique (liens externes déclarés par les administrateurs), à garder
 *  en tuiles à part. */
export function buildThemes({ available, fronts = [], themes = THEMES }) {
  const av = available instanceof Set ? available : new Set(available || []);
  const byId = new Map(fronts.map((f) => [f.id, f]));
  const absorbed = absorbedFrontIds(themes);
  const out = [];
  for (const t of themes) {
    const entries = [];
    for (const e of t.entries) {
      if (e.view && av.has(e.view)) entries.push({ id: e.view, label: e.label, kind: "view", view: e.view });
      else if (e.front && byId.has(e.front)) {
        const f = byId.get(e.front);
        entries.push({ id: `front:${e.front}`, label: e.label || f.name, kind: f.onClick ? "view-front" : "link", url: f.url || null, onClick: f.onClick || null, embeddable: !!f.embeddable });
      }
    }
    if (entries.length) out.push({ ...t, entries, count: entries.length, labels: entries.map((e) => e.label) });
  }
  const leftover = fronts.filter((f) => !absorbed.has(f.id) && !themes.some((t) => t.entries.some((e) => e.view === f.id)));
  return { themes: out, leftover };
}

export function findTheme(themes, id) {
  return (themes || []).find((t) => t.id === id) || null;
}

// La thématique qui contient une vue (pour l'état « actif » de l'en-tête).
export function themeOfView(themes, view) {
  for (const t of themes || []) if (t.entries.some((e) => e.view === view)) return t.id;
  return null;
}

export const HOME_MODES = { themes: "par thématiques", tiles: "toutes les tuiles" };
export function normalizeHomeMode(raw) {
  return raw === "tiles" ? "tiles" : "themes";
}
