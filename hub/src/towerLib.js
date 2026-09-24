// Tour de contrôle (livraison #586) -- logique pure du hub : fusion d'un
// import JSON dans un registre (mêmes règles que services/api/tower.py),
// lignes vides d'après le schéma, résumés de livraison et de job.

export function itemsOf(data, key) {
  if (Array.isArray(data)) return data;
  if (data && Array.isArray(data[key])) return data[key];
  throw new Error(`JSON attendu : {"${key}": [...]} ou une liste`);
}

export function mergeItems(existing, incoming, key = "name", mode = "merge") {
  const ex = (existing || []).filter((e) => e && typeof e === "object");
  const inc = (incoming || []).filter((e) => e && typeof e === "object");
  if (mode === "replace") return { items: [...inc], stats: { added: inc.length, updated: 0, unchanged: 0, removed: ex.length } };
  const out = [...ex];
  const idx = new Map(ex.map((e, i) => [e[key], i]));
  const stats = { added: 0, updated: 0, unchanged: 0, removed: 0 };
  for (const e of inc) {
    if (idx.has(e[key])) {
      const i = idx.get(e[key]);
      if (JSON.stringify(out[i]) === JSON.stringify(e)) stats.unchanged += 1;
      else { out[i] = e; stats.updated += 1; }
    } else { idx.set(e[key], out.length); out.push(e); stats.added += 1; }
  }
  return { items: out, stats };
}

export function emptyRow(fields) {
  const r = {};
  for (const f of fields || []) if (f.default != null) r[f.name] = f.default;
  return r;
}

/** Nettoie une ligne éditée : champs vides retirés, ports en nombres. */
export function cleanRow(row, fields) {
  const out = {};
  for (const f of fields || []) {
    let v = row?.[f.name];
    if (typeof v === "string") v = v.trim();
    if (v === "" || v == null) continue;
    if (f.type === "int") { const n = Number(v); out[f.name] = Number.isFinite(n) ? n : v; } else out[f.name] = v;
  }
  return out;
}

export function statsText(s) {
  if (!s) return "";
  const parts = [];
  if (s.added) parts.push(`${s.added} ajoutée(s)`);
  if (s.updated) parts.push(`${s.updated} mise(s) à jour`);
  if (s.unchanged) parts.push(`${s.unchanged} identique(s)`);
  if (s.removed) parts.push(`${s.removed} retirée(s)`);
  return parts.join(", ") || "aucun changement";
}

export function deliveryText(d) {
  if (!d) return "";
  const n = (a) => (Array.isArray(a) ? a.length : a || 0);
  return `${d.current || "?"} → ${d.number || "?"} : ${n(d.changed)} modifié(s), ${n(d.added)} ajouté(s), ${n(d.unchanged)} inchangé(s)`
    + (n(d.kept) ? `, ${n(d.kept)} donnée(s) locale(s) conservée(s)` : "") + (n(d.protected) ? `, ${n(d.protected)} protégé(s)` : "");
}

export const JOB_LABEL = { running: "en cours", done: "terminé", failed: "échec", lost: "interrompu" };
export const JOB_TONE = { running: "orange", done: "green", failed: "red", lost: "red" };

/** Le hub a-t-il été reconstruit par ce job (il faudra recharger la page) ? */
export function touchesHub(job) {
  return (job?.steps || []).some((s) => /\bup -d --build\b.*\bhub\b/.test(s.cmd) || /tls-proxy/.test(s.cmd));
}
