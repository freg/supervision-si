// Contrôles et tests fabriqués du serveur de messagerie (livraison #770) -- logique PURE de l'onglet « Contrôles »
// (testée sous Node : hub/tests/mailChecksLib.test.mjs). La sonde mail-server envoie des messages fabriqués (GTUBE,
// EICAR, pièce jointe interdite, message libre) à une boîte de test et relit le verdict du filtre ; des indicateurs
// comptent une expression du journal. Le catalogue est modifiable ici et écrit sur l'agent (action mailctl checks_set).

export const TEMPLATES = {
  clean: { label: "Courriel ordinaire", expect: ["Passed CLEAN"], help: "doit être accepté et remis" },
  gtube: { label: "Spam de test (GTUBE)", expect: ["Blocked SPAM", "Passed SPAM"], help: "chaîne de test reconnue par SpamAssassin" },
  eicar: { label: "Virus de test (EICAR)", expect: ["Blocked INFECTED"], help: "fichier de test inoffensif reconnu par tous les antivirus" },
  banned: { label: "Pièce jointe interdite (.exe)", expect: ["Blocked BANNED"], help: "nom de fichier interdit par Amavis" },
  custom: { label: "Message libre", expect: ["Passed CLEAN"], help: "objet et texte au choix (hameçonnage, lien suspect…)" },
};
export const DEFAULT_IDS = ["clean", "spam-gtube", "virus-eicar", "banned-exe", "auth-failed", "bad-header", "dnsbl-rejects"];
const ID_RE = /^[a-z0-9][a-z0-9_-]{1,40}$/;
const EXPECT_RE = /^(Passed|Blocked) [A-Z][A-Z-]{1,30}$/;
const MAIL_RE = /^[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+$/;

/** Identifiant tiré d'un libellé : « Lien piégé (colis) » -> « lien-piege-colis ». */
export function slug(label) {
  return String(label || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 40) || "test";
}

export function newTest(template, label) {
  const t = TEMPLATES[template] || TEMPLATES.clean;
  const l = label || t.label;
  return { id: slug(l), label: l, template, expect: [...t.expect], enabled: true, ...(template === "custom" ? { subject: "", body: "" } : {}) };
}

export function newIndicator(label, regex) {
  return { id: slug(label), label: label || "", regex: regex || "", window_minutes: 60, warn_above: null, crit_above: null, enabled: true };
}

/** Catalogue -> liste d'erreurs (mêmes règles que l'agent). */
export function validate(cat) {
  const e = [];
  for (const k of ["to", "from"]) {
    const v = (cat?.canary?.[k] || "").trim();
    if (v && !MAIL_RE.test(v)) e.push(`adresse ${k === "to" ? "de la boîte de test" : "d'expéditeur"} invalide`);
  }
  const ids = new Set();
  for (const t of cat?.tests || []) {
    if (!ID_RE.test(t.id || "")) e.push(`test « ${t.label || t.id} » : identifiant invalide`);
    if (ids.has(t.id)) e.push(`identifiant en double : ${t.id}`);
    ids.add(t.id);
    if (!TEMPLATES[t.template]) e.push(`test ${t.id} : modèle inconnu`);
    if (!(t.expect || []).length || (t.expect || []).some((x) => !EXPECT_RE.test(x))) e.push(`test ${t.id} : verdict attendu de la forme « Blocked INFECTED »`);
  }
  for (const i of cat?.indicators || []) {
    if (!ID_RE.test(i.id || "")) e.push(`indicateur « ${i.label || i.id} » : identifiant invalide`);
    if (ids.has(i.id)) e.push(`identifiant en double : ${i.id}`);
    ids.add(i.id);
    try { if (!i.regex) throw new Error("vide"); new RegExp(i.regex); } catch (x) { e.push(`indicateur ${i.id} : expression invalide (${x.message})`); }
    for (const k of ["warn_above", "crit_above"]) if (i[k] != null && i[k] !== "" && !(Number(i[k]) >= 0)) e.push(`indicateur ${i.id} : seuil invalide`);
  }
  return e;
}

/** Catalogue édité -> contenu du fichier de l'agent : tout le catalogue + « remove » pour les éléments par défaut retirés. */
export function toPayload(cat) {
  const kept = new Set([...(cat.tests || []), ...(cat.indicators || [])].map((x) => x.id));
  const num = (v) => (v === "" || v == null ? null : Number(v));
  return {
    canary: { to: (cat.canary?.to || "").trim(), from: (cat.canary?.from || "").trim(), every_hours: Number(cat.canary?.every_hours) || 6, timeout_minutes: Number(cat.canary?.timeout_minutes) || 30 },
    tests: (cat.tests || []).map((t) => ({ ...t })),
    indicators: (cat.indicators || []).map((i) => ({ ...i, window_minutes: Number(i.window_minutes) || 60, warn_above: num(i.warn_above), crit_above: num(i.crit_above) })),
    remove: DEFAULT_IDS.filter((id) => !kept.has(id)),
  };
}

/** État lisible d'un test d'après le relevé : ok | echec | attente | jamais | inactif. */
export function testState(t) {
  if (!t?.enabled) return "inactif";
  if (t.pending) return "attente";
  if (!t.last) return "jamais";
  return t.last.ok ? "ok" : "echec";
}

export const STATE_LABEL = { ok: "réussi", echec: "en échec", attente: "en cours", jamais: "jamais lancé", inactif: "désactivé" };
export const STATE_TONE = { ok: "good", echec: "bad", attente: "neutral", jamais: "neutral", inactif: "neutral" };

/** Synthèse du bloc « checks » : {tests, ok, failed, pending, indicatorsAlert, configured}. */
export function summary(block) {
  const tests = block?.tests || [];
  const st = tests.map(testState);
  return {
    tests: tests.filter((t) => t.enabled).length, ok: st.filter((s) => s === "ok").length, failed: st.filter((s) => s === "echec").length,
    pending: st.filter((s) => s === "attente").length, indicatorsAlert: (block?.indicators || []).filter((i) => i.state !== "ok").length,
    configured: Boolean(block?.canary?.to),
  };
}
