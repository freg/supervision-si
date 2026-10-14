// Logique pure de la tuile « Vues de parc » (#753) : proposition de rangement des agents dans les vues (serveurs,
// postes, serveurs d'IA, postes personnels), tri des lignes htop, synthèse d'un groupe.
import { agentCategory } from "./siAgent.js";

const isServerOs = (a) => /server/i.test(String(a?.os || ""));
const hasOllama = (a) => (a?.plugin_ids || []).includes("ollama");
const isPerso = (a) => /#perso\b/i.test(String(a?.label || ""));

/** Rangement proposé, groupe par groupe, à partir de la catégorie (#742), de l'OS et des sondes portées.
 *  Les vues qui ont déjà des groupes ne sont pas touchées. */
export function suggestViews(views, fleet) {
  const by = (pred) => (fleet || []).filter(pred).map((a) => a.agent_id).sort();
  const proposals = {
    serveurs: [["Proxmox (PVE / PBS)", by((a) => agentCategory(a) === "proxmox")],
      ["Linux", by((a) => agentCategory(a) === "linux" && !isPerso(a))],
      ["Machines virtuelles", by((a) => agentCategory(a) === "vm")],
      ["Windows Server", by((a) => agentCategory(a) === "windows" && isServerOs(a))]],
    postes: [["Windows", by((a) => agentCategory(a) === "windows" && !isServerOs(a) && !isPerso(a))],
      ["macOS / autres", by((a) => agentCategory(a) === "other" && !isPerso(a))]],
    ia: [["Ollama", by(hasOllama)]],
    perso: [["Mes postes", by(isPerso)]],
  };
  return (views || []).map((v) => (v.groups?.length || !proposals[v.id] ? v
    : { ...v, groups: proposals[v.id].filter(([, ids]) => ids.length).map(([name, agents]) => ({ name, agents, note: "" })) }));
}

/** Agents d'une vue (tous groupes). */
export const viewAgents = (view) => new Set((view?.groups || []).flatMap((g) => g.agents || []));

/** Tri d'une liste de lignes htop : colonne numérique ou texte, valeurs absentes en fin. */
export function sortHtop(rows, col, dir = -1) {
  const val = (r) => (col === "load" ? r.load1 : col === "name" ? (r.hostname || r.agent_id || "").toLowerCase() : r[col]);
  return [...(rows || [])].sort((a, b) => {
    const x = val(a), y = val(b);
    if (x == null && y == null) return 0;
    if (x == null) return 1;
    if (y == null) return -1;
    return typeof x === "string" ? -dir * x.localeCompare(y) : dir * (x - y);
  });
}

/** État d'une ligne pour la pastille : hors ligne, critique, avertissement, ok. */
export function rowTone(r) {
  if (r.online === "offline" || r.online === "never") return "critical";
  if (r.risk_state === "critical" || (r.disk_max_pct ?? 0) >= 95) return "critical";
  if (r.risk_state === "warning" || (r.failed_services || 0) > 0 || (r.disk_max_pct ?? 0) >= 85 || (r.mem_pct ?? 0) >= 90) return "warning";
  return "good";
}

/** Déplace un agent d'un groupe à l'autre dans une vue (ou le retire si `to` est null). */
export function moveAgent(view, agentId, to) {
  const groups = (view.groups || []).map((g) => ({ ...g, agents: (g.agents || []).filter((a) => a !== agentId) }));
  if (to != null && groups[to]) groups[to].agents = [...groups[to].agents, agentId];
  return { ...view, groups };
}
