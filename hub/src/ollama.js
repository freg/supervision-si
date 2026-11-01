// Aides pures de la section Modèles IA (#746), testées par tests/ollama.test.mjs
export const gb = (n) => (n == null ? "?" : n >= 1e9 ? (n / 1e9).toFixed(1) + " Go" : Math.round(n / 1e6) + " Mo");
export const MODEL_RE = /^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$/;


export function pullText(p) {
  if (!p) return null;
  const pct = p.total ? Math.round((100 * (p.completed || 0)) / p.total) : null;
  if (p.running) return `téléchargement de ${p.model} : ${p.status || "…"}${pct != null ? ` ${pct} %` : ""}`;
  return `dernier téléchargement : ${p.model} ${p.ok ? "terminé" : `en échec (${p.error || "?"})`}`;
}

