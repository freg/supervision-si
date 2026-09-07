// Logique PURE de la tuile UPS (livraison #415) -- aucun React, testée
// sous Node (hub/tests/upsMonitor.test.mjs). Le rendu vit dans UpsView.jsx.

// Champs de la fiche présentés en premier dans le tableau, dans cet ordre
// (les autres suivent, dans l'ordre de la page).
export const PRIMARY_KEYS = [
  "model", "communication", "output_source", "battery",
  "input_voltage", "output_voltage", "input_frequency", "output_frequency",
  "output_load", "battery_capacity",
];

// Champs numériques proposés pour la timeline (courbe) ; tout autre champ
// numérique présent dans la fiche est ajouté à la volée.
export const SERIES_KEYS = ["input_voltage", "output_voltage", "input_frequency", "output_frequency", "output_load", "battery_capacity"];

export const FIELD_LABELS_FR = {
  model: "Modèle",
  communication: "Communication",
  output_source: "Source de sortie",
  battery: "Batterie",
  input_voltage: "Tension d'entrée",
  output_voltage: "Tension de sortie",
  input_frequency: "Fréquence d'entrée",
  output_frequency: "Fréquence de sortie",
  output_load: "Charge de sortie",
  battery_capacity: "Capacité batterie",
  next_power_off: "Prochain arrêt programmé",
  next_power_on: "Prochain démarrage programmé",
  next_test: "Prochain test",
  time_to_power_off: "Délai avant arrêt",
};

export function fieldLabel(key, fallback) {
  return FIELD_LABELS_FR[key] || fallback || key;
}

// Ordonne les champs d'une fiche : champs principaux d'abord, puis le
// reste dans l'ordre des sections de la page. `sections` = tableau de
// {title, fields:[{key,...}]} (tel que renvoyé par l'API).
export function orderedFields(sections) {
  const all = [];
  for (const s of sections || []) {
    for (const f of s.fields || []) all.push({ ...f, section: s.title });
  }
  const byKey = new Map(all.map((f) => [f.key, f]));
  const first = PRIMARY_KEYS.filter((k) => byKey.has(k)).map((k) => byKey.get(k));
  const rest = all.filter((f) => !PRIMARY_KEYS.includes(f.key));
  return [...first, ...rest];
}

// Ton d'affichage d'un champ : les champs d'état connus (texte) sont
// « good » à leur valeur normale, « bad » sinon ; les autres « neutral ».
const NORMAL_VALUES = { communication: ["ok"], output_source: ["normal"], battery: ["normal"] };

export function fieldTone(field) {
  const normal = NORMAL_VALUES[field?.key];
  if (!normal) return "neutral";
  const v = (field.value || "").trim().toLowerCase();
  return normal.includes(v) ? "good" : "bad";
}

// État d'un onduleur pour la liste : { tone, text }.
export function deviceStatus(device, nowMs = Date.now(), staleFactor = 2.5, defaultInterval = 3600) {
  if (!device) return { tone: "neutral", text: "—" };
  if (!device.enabled) return { tone: "neutral", text: "désactivé" };
  if (!device.last_polled_at) return { tone: "neutral", text: "jamais relevé" };
  const interval = device.poll_interval_seconds || defaultInterval;
  const age = (nowMs - Date.parse(device.last_polled_at)) / 1000;
  if (Number.isFinite(age) && age > interval * staleFactor) {
    return { tone: "warn", text: `relevé ancien (${formatAge(age)})` };
  }
  if (device.last_ok === false) return { tone: "bad", text: device.last_error || "échec du relevé" };
  if (device.last_state === "alarm") return { tone: "bad", text: "alarme" };
  if (device.last_state === "ok") return { tone: "good", text: "normal" };
  return { tone: "neutral", text: device.last_state || "inconnu" };
}

export function formatAge(seconds) {
  if (!Number.isFinite(seconds) || seconds < 0) return "—";
  if (seconds < 90) return `${Math.round(seconds)} s`;
  if (seconds < 5400) return `${Math.round(seconds / 60)} min`;
  if (seconds < 172800) return `${Math.round(seconds / 3600)} h`;
  return `${Math.round(seconds / 86400)} j`;
}

export function formatInterval(seconds) {
  if (!seconds) return "";
  if (seconds % 3600 === 0) return `${seconds / 3600} h`;
  if (seconds % 60 === 0) return `${seconds / 60} min`;
  return `${seconds} s`;
}

// Résumé compact du dernier relevé (colonne de la liste) à partir de
// `last_summary` (JSON de l'API) : « 236 V → 229 V · 8 % · batt. 100 % ».
export function summarizeLast(summaryJson) {
  let s = summaryJson;
  if (typeof s === "string") {
    try { s = JSON.parse(s); } catch { return ""; }
  }
  if (!s || typeof s !== "object") return "";
  const parts = [];
  if (s.input_voltage || s.output_voltage) parts.push(`${s.input_voltage || "?"} → ${s.output_voltage || "?"}`);
  if (s.output_load) parts.push(`charge ${s.output_load}`);
  if (s.battery_capacity) parts.push(`batt. ${s.battery_capacity}`);
  return parts.join(" · ");
}

// Clés numériques disponibles pour la timeline, d'après la dernière fiche.
export function numericKeys(fields) {
  const keys = Object.entries(fields || {}).filter(([, f]) => typeof f?.number === "number").map(([k]) => k);
  const first = SERIES_KEYS.filter((k) => keys.includes(k));
  return [...first, ...keys.filter((k) => !SERIES_KEYS.includes(k))];
}

// Série API [{at, number, unit}] → points pour buildLinePath (netprobeAgents).
export function toLineSeries(points) {
  return (points || []).filter((p) => typeof p.number === "number").map((p) => ({ at: p.at, value: p.number }));
}

// Lignes de la timeline (tableau) : une par relevé, avec les repères qui
// changent d'un relevé à l'autre pour lire vite ce qui a bougé.
export function timelineRows(readings) {
  const rows = [];
  let prev = null;
  for (const r of readings || []) {
    const changes = [];
    if (prev) {
      for (const k of ["state", "input_voltage", "output_voltage", "output_load", "battery_capacity"]) {
        if (r[k] !== prev[k] && !(r[k] == null && prev[k] == null)) changes.push(k);
      }
      if (r.ok !== prev.ok) changes.push("ok");
    }
    rows.push({ ...r, changes });
    prev = r;
  }
  return rows;
}

// Fenêtres temporelles proposées pour la timeline.
export const TIME_WINDOWS = [
  { id: "24h", label: "24 h", seconds: 86400 },
  { id: "7d", label: "7 jours", seconds: 7 * 86400 },
  { id: "30d", label: "30 jours", seconds: 30 * 86400 },
  { id: "all", label: "tout", seconds: null },
];

export function windowStart(windowId, nowMs = Date.now()) {
  const w = TIME_WINDOWS.find((x) => x.id === windowId);
  if (!w || !w.seconds) return null;
  return new Date(nowMs - w.seconds * 1000).toISOString().replace(/\.\d{3}Z$/, "Z");
}
