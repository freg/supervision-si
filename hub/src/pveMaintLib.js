// Logique pure de la tuile « Maintenance des Proxmox » (#705) : libellés, tonalités, saisie des actions, dates.

export const STATE_LABEL = { done: "fait", todo: "à faire", unknown: "inconnu", running: "en cours", failed: "échec", blocked: "bloquée", doing: "en cours" };
export const STATE_TONE = { done: "good", todo: "neutral", unknown: "warn", running: "info", failed: "bad", blocked: "neutral", doing: "info" };
export const HOW_LABEL = { detected: "constaté", manual: "coché", run: "exécuté" };
export const STATUS_LABEL = { draft: "brouillon", active: "active", done: "terminée", archived: "archivée" };

/** Champs d'un détecteur : "vmid?" -> {name: "vmid", optional: true}. */
export function detectorFields(catalog, type) {
  return ((catalog?.detectors?.[type]?.fields) || []).map((f) => ({ name: f.replace(/\?$/, ""), optional: f.endsWith("?") }));
}

/** "clé=valeur" par ligne <-> objet (nombres convertis). */
export function paramsToText(p) {
  return Object.entries(p || {}).map(([k, v]) => `${k}=${v}`).join("\n");
}
export function textToParams(text) {
  const out = {};
  for (const line of String(text || "").split(/\n|;/)) {
    const i = line.indexOf("=");
    if (i <= 0) continue;
    const k = line.slice(0, i).trim(); const v = line.slice(i + 1).trim();
    if (!k) continue;
    out[k] = /^-?\d+(\.\d+)?$/.test(v) ? Number(v) : v;
  }
  return out;
}

/** epoch (s) <-> valeur d'un <input type="datetime-local"> (heure locale). */
export function toLocalInput(epoch) {
  if (!epoch) return "";
  const d = new Date(epoch * 1000);
  const p = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(d.getHours())}:${p(d.getMinutes())}`;
}
export function fromLocalInput(v) {
  if (!v) return null;
  const t = new Date(v).getTime();
  return Number.isFinite(t) ? Math.round(t / 1000) : null;
}

export function emptyAction() {
  return { title: "", kind: "manual", notes: "", step: null, detector: null, at: null, auto: false };
}

/** Liste plate des actions planifiées de toutes les campagnes, triée par date. */
export function plannedList(campaigns) {
  return (campaigns || []).flatMap((c) => c.planned || []).sort((a, b) => a.at - b.at);
}

/** Paramètres requis (pra) manquants pour une action. */
export function missingParams(catalog, step) {
  const req = catalog?.required?.[step?.action] || [];
  return req.filter((k) => step?.params?.[k] === undefined || step.params[k] === "");
}

/** Déplace l'élément i de d (-1 / +1) ; renvoie une nouvelle liste. */
export function move(list, i, d) {
  const j = i + d;
  if (j < 0 || j >= list.length) return list;
  const out = [...list];
  [out[i], out[j]] = [out[j], out[i]];
  return out;
}

export function gb(n) { return n == null ? "—" : `${(n / 1024 ** 3).toFixed(0)} Go`; }


// #723 : liste de campagne pour pve-pull-batch.sh (#717) depuis l'inventaire des PVE distants (sonde pve-remote).
// Une ligne par CT retenu : « hôte vmid stop garder nom » ; CT arrêtés d'abord (aucune coupure de service), puis les CT
// en marche SEULEMENT si demandés (ils seront ARRÊTÉS pendant leur copie). VM QEMU exclues (le script tire des CT).
export function campaignLines(nodes, { includeRunning = false, exclude = [], keep = 2 } = {}) {
  const skip = new Set((exclude || []).map(String));
  const rows = [];
  for (const n of nodes || []) {
    if (!n || !n.ok) continue;
    for (const g of n.guests || []) {
      if (g.type !== "lxc" || skip.has(`${n.name}/${g.vmid}`)) continue;
      if (g.status !== "stopped" && !includeRunning) continue;
      rows.push({ n, g, order: g.status === "stopped" ? 0 : 1 });
    }
  }
  rows.sort((a, b) => a.order - b.order || String(a.n.name).localeCompare(String(b.n.name)) || a.g.vmid - b.g.vmid);
  const head = [`# Campagne de sauvegardes tirées générée par le hub (#723) -- ${rows.length} CT`, "# hôte vmid mode garder nom ; les CT « running » sont ARRÊTÉS pendant leur copie"];
  return head.concat(rows.map(({ n, g }) => `${n.host} ${g.vmid} stop ${keep} ${n.name}${g.status !== "stopped" ? "   # running : " + (g.name || "") : g.name ? "   # " + g.name : ""}`)).join("\n") + "\n";
}

// #724 : filtre de l'inventaire des snapshots et sauvegardes -- type, texte (sans casse ni accents), ancienneté.
const foldTxt = (x) => String(x ?? "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
export function filterInventory(rows, { kind = "", q = "", olderThanDays = 0, now = Date.now() / 1000 } = {}) {
  const f = foldTxt(q).trim();
  return (rows || []).filter((r) => (!kind || r.kind === kind)
    && (!olderThanDays || (r.at && now - r.at > olderThanDays * 86400))
    && (!f || foldTxt([r.source, r.node, r.vmid, r.name, r.where, r.at_text].join(" ")).includes(f)));
}
export function inventorySummary(rows, now = Date.now() / 1000) {
  const out = { snapshot: 0, sauvegarde: 0, oldSnapshots: 0, bySource: {} };
  for (const r of rows || []) {
    out[r.kind] = (out[r.kind] || 0) + 1;
    out.bySource[r.source] = (out.bySource[r.source] || 0) + 1;
    if (r.kind === "snapshot" && r.at && now - r.at > 30 * 86400) out.oldSnapshots += 1;
  }
  return out;
}
