// Logique pure du module Zenoss. Autonome (pas de partage avec
// ipamLib.js/optickLib.js), même convention que les autres modules.

export function normalizeText(s) {
  return (s || "")
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "");
}

function searchableText(node) {
  const raw = node.raw || {};
  return [node.name, raw.path].filter(Boolean).join(" ");
}

export function nodeMatchesQuery(node, query) {
  const q = normalizeText(query).trim();
  if (!q) return true;
  return normalizeText(searchableText(node)).includes(q);
}

export function computeRelevantIds(tree, query) {
  const q = query ? query.trim() : "";
  if (!q) return null;
  if (!tree) return new Set();

  const matches = new Set();
  const hasMatchBelow = new Set();

  function markMatches(node) {
    const self = nodeMatchesQuery(node, q);
    if (self) matches.add(node.id);
    let below = self;
    for (const child of node.children || []) {
      if (markMatches(child)) below = true;
    }
    if (below) hasMatchBelow.add(node.id);
    return below;
  }
  markMatches(tree);

  const relevant = new Set();
  function collect(node, ancestorMatched) {
    const isRelevant = matches.has(node.id) || hasMatchBelow.has(node.id) || ancestorMatched;
    if (isRelevant) relevant.add(node.id);
    const childFlag = ancestorMatched || matches.has(node.id);
    for (const child of node.children || []) {
      collect(child, childFlag);
    }
  }
  collect(tree, false);

  return relevant;
}

export function findPathToNode(tree, targetId) {
  if (!tree) return null;
  function walk(node, path) {
    const nextPath = [...path, node];
    if (node.id === targetId) return nextPath;
    for (const child of node.children || []) {
      const found = walk(child, nextPath);
      if (found) return found;
    }
    return null;
  }
  return walk(tree, []);
}

export function truncateLabel(label, maxLen = 28) {
  const s = String(label || "");
  return s.length > maxLen ? `${s.slice(0, maxLen - 1)}…` : s;
}

export function fmtTimelineDate(ts) {
  if (typeof ts !== "number" || !Number.isFinite(ts)) return "—";
  return new Date(ts * 1000).toLocaleDateString("fr-FR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  });
}

/** Sévérité dominante d'un nœud (parmi ses événements actifs À LUI,
 * pas cumulée sur ses descendants) — pour la coloration de l'arbre.
 * null si aucun événement actif sur ce nœud précis. */
export function dominantSeverity(node) {
  const bySeverity = (node.raw || {}).activeBySeverity;
  if (!bySeverity || Object.keys(bySeverity).length === 0) return null;
  const order = ["Critical", "Error", "Warning", "Info", "Debug", "Clear"];
  for (const label of order) {
    if (bySeverity[label]) return label;
  }
  return Object.keys(bySeverity)[0];
}

export function severityClass(label) {
  switch (label) {
    case "Critical": return "zenoss-sev-critical";
    case "Error": return "zenoss-sev-error";
    case "Warning": return "zenoss-sev-warning";
    case "Info": return "zenoss-sev-info";
    case "Debug": return "zenoss-sev-debug";
    case "Clear": return "zenoss-sev-clear";
    default: return "zenoss-sev-unknown";
  }
}

export function highlightJsonLines(value) {
  const text = JSON.stringify(value === undefined ? null : value, null, 2);
  return text.split("\n").map((line) => tokenizeJsonLine(line));
}

const TOKEN_RE = /("(?:\\.|[^"\\])*"(\s*:)?|-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?|\btrue\b|\bfalse\b|\bnull\b)/g;

export function tokenizeJsonLine(line) {
  const segments = [];
  let lastIndex = 0;
  let m;
  TOKEN_RE.lastIndex = 0;
  while ((m = TOKEN_RE.exec(line)) !== null) {
    if (m.index > lastIndex) {
      segments.push({ text: line.slice(lastIndex, m.index), cls: "punct" });
    }
    const token = m[0];
    let cls;
    if (token.endsWith(":")) {
      cls = "key";
    } else if (token.startsWith('"')) {
      cls = "string";
    } else if (token === "true" || token === "false") {
      cls = "boolean";
    } else if (token === "null") {
      cls = "null";
    } else {
      cls = "number";
    }
    segments.push({ text: token, cls });
    lastIndex = m.index + token.length;
  }
  if (lastIndex < line.length) {
    segments.push({ text: line.slice(lastIndex), cls: "punct" });
  }
  return segments.length ? segments : [{ text: line, cls: "punct" }];
}
