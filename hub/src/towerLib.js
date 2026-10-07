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

// #659 : état git -> phrase ("#657 → #659 : 2 commit(s) en retard") et ce qui empêche la mise à jour (ou null).
export function gitText(g) {
  if (!g) return "";
  if (g.error) return g.error;
  const head = g.head ? `${g.head.hash} ${g.head.subject}` : "?";
  if (g.behind) return `#${g.current || "?"} → #${g.remote_number || "?"} : ${g.behind} commit(s) en retard sur origin/${g.branch} (en place : ${head})`;
  return `à jour sur origin/${g.branch} (#${g.current || "?"}, ${head})`;
}
// #700 : livraison compilée dans la page vs code du central (HEAD) vs origin.
// -> {state: ok|update|rebuild|unknown, target, text}
export function versionStatus(built, g) {
  const n = (x) => { const v = parseInt(x, 10); return Number.isFinite(v) ? v : null; };
  const b = n(built), cur = n(g?.current), rem = n(g?.remote_number);
  if (!g || g.error) return { state: "unknown", target: null, text: g?.error ? `contrôle impossible : ${g.error}` : "non contrôlé" };
  if (g.behind > 0) return { state: "update", target: rem ?? cur, text: `#${rem ?? "?"} disponible sur origin/${g.branch || "?"} (${g.behind} commit(s)), page en #${b ?? "?"}` };
  if (b !== null && cur !== null && cur > b) return { state: "rebuild", target: cur, text: `code #${cur} présent sur le central mais page compilée en #${b} : reconstruction à faire` };
  if (g.fetch_error) return { state: "unknown", target: null, text: `origin injoignable (${g.fetch_error}), page en #${b ?? "?"}` };
  return { state: "ok", target: cur, text: `à jour : page #${b ?? "?"}, central #${cur ?? "?"}, origin/${g.branch || "?"}` };
}

export function gitBlocker(g) {
  if (!g) return null;
  if (g.error) return g.error;
  if (g.hint) return g.hint;
  if (g.fetch_error) return `git fetch impossible : ${g.fetch_error}`;
  if ((g.dirty || []).length) return `fichiers modifiés localement : ${g.dirty.slice(0, 5).join(", ")}`;
  if (g.ahead) return `${g.ahead} commit(s) locaux non poussés : avance rapide impossible`;
  return null;
}

// #662 : répartition -- lignes cohorte -> nœud, déplacement (pur), résumé d'un nœud.
export function cohortRows(data) {
  const where = {};
  for (const n of data?.nodes || []) for (const c of n.cohorts || []) where[c] = n.name;
  return (data?.cohorts || []).map((c) => ({ ...c, node: where[c.name] || "", services: c.services || [], count: (c.services || []).length }));
}
export function moveCohort(nodes, cohort, target) {
  return (nodes || []).map((n) => {
    const cs = (n.cohorts || []).filter((c) => c !== cohort);
    return { ...n, cohorts: n.name === target ? [...cs, cohort] : cs };
  });
}
export function nodeText(st) {
  if (!st) return "—";
  if (st.error) return `injoignable : ${st.error}`;
  const miss = (st.missing || []).length;
  return `v${st.version || "?"} · ${(st.running || []).length} en marche` + (miss ? ` · ${miss} arrêté(s) : ${st.missing.slice(0, 4).join(", ")}` : "") + ((st.plan?.missing || []).length ? ` · sans relais : ${st.plan.missing.join(", ")}` : "");
}

// #663 : miroir -- phrase d'état et actions possibles (pur).
export function mirrorText(m) {
  if (!m) return "";
  if (!m.configured) return "pas de miroir configuré (deploy/mirror.local.json, modèle deploy/mirror.example.json)";
  const st = m.state || {}; const mir = m.mirror || {};
  const age = m.age_s == null ? "jamais synchronisé" : m.age_s < 3600 ? `synchronisé il y a ${Math.round(m.age_s / 60)} min` : `synchronisé il y a ${(m.age_s / 3600).toFixed(1)} h`;
  const side = mir.error ? `miroir ${m.config?.node} injoignable : ${mir.error}` : `miroir ${mir.node || m.config?.node} : ${(mir.archives || []).filter((a) => !a.name.endsWith(".manifest.json")).length} archive(s), ${(mir.running || []).length} service(s) en marche${mir.state?.last_restore ? `, restauré le ${mir.state.last_restore.replace("T", " ").slice(0, 16)}` : ""}`;
  return `${age}${st.last_archive ? ` (${st.last_archive})` : ""} · ${side}${st.mirror_active ? " · MIROIR ACTIF (bascule en cours)" : ""}`;
}
export function mirrorActions(m) {
  if (!m?.configured) return [];
  const active = !!(m.state || {}).mirror_active || ((m.mirror || {}).running || []).length > 0;
  return active ? ["failback"] : ["sync", "sync-full", "failover", "prune"];
}

export const JOB_LABEL = { running: "en cours", done: "terminé", failed: "échec", lost: "interrompu" };
export const JOB_TONE = { running: "orange", done: "green", failed: "red", lost: "red" };

/** Le hub a-t-il été reconstruit par ce job (il faudra recharger la page) ? */
export function touchesHub(job) {
  return (job?.steps || []).some((s) => /\bup -d --build\b.*\bhub\b/.test(s.cmd) || /tls-proxy/.test(s.cmd));
}
