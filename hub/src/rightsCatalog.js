// Matrice des droits (livraison #559) -- logique PURE, testée sous Node
// (hub/tests/rightsCatalog.test.mjs). Le hub publie son CATALOGUE (toutes
// les tuiles/vues/fronts des thématiques, et les actions « manage » des API
// qui vérifient un droit auprès de rights-api) ; la matrice croise ce
// catalogue avec des SUJETS (groupes Keycloak, ou user:<login>).

import { THEMES } from "./hubThemes.js";

export const RESOURCE_TYPE = "hub-tile";

/** Tuile -> type de ressource des API qui vérifient le droit `manage` auprès
 *  de rights-api (relevé dans le code des services, #559). */
export const MANAGE_API = {
  architecture: "architecture-api", "backup-restore": "backup-restore-api", classifier: "classifier-api", cortex: "cortex-api",
  dba: "dba-api", ged: "ged-api", "geo-catalog": "geo-catalog-api", "glpi-inventory": "glpi-api", imap: "imap-client-api",
  "ldap-admin": "ldap-admin-api", nebula: "nebula-api", "supervision-si": "pixel-grid-api", retro: "retro-api",
  "schema-analyzer": "schema-analyzer-api", snmp: "snmp-api", "ssh-tunnels": "ssh-tunnels-api", ent: "tasks-api",
  tickets: "tickets-api", vault: "vault-api", "vault-admin": "vault-admin-api", vigilance: "vigilance-api",
};

/** Catalogue : une entrée par tuile (vue ou front) des thématiques, dans
 *  l'ordre d'affichage, avec ses actions (`view` toujours ; `manage` quand
 *  une API le vérifie). */
export function buildCatalog(themes = THEMES) {
  const out = [];
  const seen = new Set();
  for (const t of themes) {
    for (const e of t.entries || []) {
      const id = e.view || e.front;
      if (!id || seen.has(id)) continue;
      seen.add(id);
      const actions = ["view"];
      if (MANAGE_API[id]) actions.push("manage");
      out.push({ identifier: id, label: e.label || id, theme: t.name, actions, manageType: MANAGE_API[id] || null });
    }
  }
  return out;
}

/** Sujet affiché -> clé stockée : les groupes tels quels, les personnes en user:<login>. */
export const subjectKey = (s) => (s.kind === "user" ? `user:${s.name}` : s.name);
export const subjectFromKey = (k) => (k.startsWith("user:") ? { kind: "user", name: k.slice(5) } : { kind: "group", name: k.startsWith("group:") ? k.slice(6) : k });

/** Index des octrois : clé "type|id|sujet|action" -> permission. */
export function grantIndex(permissions) {
  const idx = new Map();
  for (const p of permissions || []) idx.set(`${p.resource_type}|${p.resource_id ?? ""}|${p.group_name}|${p.action}`, p);
  return idx;
}

/** État d'une case : `view` porte sur (hub-tile, id) ; `manage` sur l'API
 *  de la tuile (resource_id nul = tout le type). Renvoie {allowed, wide}. */
export function cellState(idx, entry, subjectK, action) {
  if (action === "manage") {
    if (!entry.manageType) return { allowed: false, na: true };
    return { allowed: idx.has(`${entry.manageType}||${subjectK}|manage`), na: false };
  }
  const precise = idx.has(`${RESOURCE_TYPE}|${entry.identifier}|${subjectK}|view`);
  const wide = idx.has(`${RESOURCE_TYPE}||${subjectK}|view`);
  return { allowed: precise || wide, wide, na: false };
}

/** Octroi à envoyer pour une case. */
export function grantFor(entry, subjectK, action, allowed) {
  if (action === "manage") return { resource_type: entry.manageType, resource_id: null, subject: subjectK, action: "manage", allowed };
  return { resource_type: RESOURCE_TYPE, resource_id: entry.identifier, subject: subjectK, action: "view", allowed };
}

/** Sujets à afficher en colonnes : groupes connus (accounts-api ou realm),
 *  sujets déjà présents dans la matrice, personnes choisies. Triés : groupes
 *  puis personnes ; admin_hub / administrateurs en tête (toujours tout). */
export function columnSubjects({ groups = [], users = [], known = [] }) {
  const set = new Map();
  for (const g of groups) set.set(g, { kind: "group", name: g });
  for (const k of known) { const s = subjectFromKey(k); set.set(subjectKey(s), s); }
  for (const u of users) set.set(`user:${u}`, { kind: "user", name: u });
  const order = (s) => (s.kind === "group" ? (["admin_hub", "administrateurs"].includes(s.name) ? 0 : 1) : 2);
  return [...set.values()].sort((a, b) => order(a) - order(b) || a.name.localeCompare(b.name, "fr"));
}

/** Filtre la disponibilité des vues et des fronts selon les identifiants
 *  visibles (null = aucune restriction). */
export function applyVisibility(availableViews, fronts, visibleIds) {
  if (!visibleIds) return { views: availableViews, fronts };
  const allowed = new Set(visibleIds);
  return { views: new Set([...availableViews].filter((v) => allowed.has(v))), fronts: fronts.filter((f) => allowed.has(f.id)) };
}
