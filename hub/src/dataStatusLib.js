// Bandeau « État des données » (#763) : pour un écran, l'état de chacune de ses sources (sondes remontées par les
// agents), le temps de réponse de l'API et les erreurs -- surtout utile quand l'écran est vide ou en période
// d'engorgement (réponses lentes, mesures en retard).

export const fmtAge = (s) => (s == null ? "?" : s < 90 ? `${s} s` : s < 5400 ? `${Math.round(s / 60)} min` : s < 172800 ? `${Math.round(s / 3600)} h` : `${Math.round(s / 86400)} j`);

/** Une source -> {tone, text, detail}. stale : âge au-delà duquel la mesure est « en retard » (s). */
export function sourceState(src, label, stale = 1800) {
  const ag = src?.agents || [];
  if (!ag.length) return { tone: "critical", text: `${label} : aucune mesure`, detail: src?.hint ? `à faire : ${src.hint}` : "" };
  const bad = ag.filter((a) => !a.ok);
  const late = ag.filter((a) => a.age_s != null && a.age_s > stale);
  const freshest = Math.min(...ag.map((a) => (a.age_s == null ? Infinity : a.age_s)));
  const names = (xs) => xs.map((a) => a.hostname || a.agent_id).join(", ");
  if (bad.length) return { tone: "critical", text: `${label} : ${bad.length} en erreur sur ${ag.length}`, detail: bad.map((a) => `${a.hostname || a.agent_id} : ${a.error || "échec"}`).join(" ; ") };
  if (late.length) return { tone: "warning", text: `${label} : ${late.length} en retard sur ${ag.length}`, detail: `dernière mesure : ${late.map((a) => `${a.hostname || a.agent_id} il y a ${fmtAge(a.age_s)}`).join(", ")}` };
  return { tone: "good", text: `${label} : ${ag.length} agent(s), il y a ${fmtAge(freshest)}`, detail: names(ag) };
}

/** Temps de réponse de l'API -> {tone, text}. */
export function latencyState(ms) {
  if (ms == null) return null;
  if (ms >= 8000) return { tone: "critical", text: `API très lente (${(ms / 1000).toFixed(1)} s) : engorgement probable` };
  if (ms >= 2500) return { tone: "warning", text: `API lente (${(ms / 1000).toFixed(1)} s)` };
  return { tone: "good", text: `API ${ms} ms` };
}
