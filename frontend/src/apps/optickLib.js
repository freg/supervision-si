// Logique pure du module Optick. Délibérément autonome (pas de partage
// avec ipamLib.js) : chaque module de ce frontend reste indépendant et
// testable seul, même convention que tickets/portal vis-à-vis du
// frontend principal.

export function normalizeText(s) {
  return (s || "")
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "");
}

function searchableText(node) {
  const raw = node.raw || {};
  const domains = Array.isArray(raw.domainLabels) ? raw.domainLabels.join(" ") : "";
  return [node.name, domains].filter(Boolean).join(" ");
}

export function nodeMatchesQuery(node, query) {
  const q = normalizeText(query).trim();
  if (!q) return true;
  return normalizeText(searchableText(node)).includes(q);
}

/** Même algorithme que ipamLib.computeRelevantIds : match + ancêtres +
 * descendants restent pertinents, le reste est mis en retrait. */
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

/** Taux de tickets encore ouverts (0–100) pour une catégorie — signal
 * de charge/retard, ou null si non calculable (famille, ou aucun
 * ticket du tout : pas de backlog à mesurer). */
export function openRatioPercent(node) {
  const raw = node.raw || {};
  if (node.type !== "category") return null;
  const total = raw.ticketCount;
  if (!total) return null;
  return Math.min(100, (raw.openTicketCount / total) * 100);
}

/** Seuils : au-delà de 50% de tickets ouverts, backlog critique ; entre
 * 20 et 50%, à surveiller ; sinon, sain. */
export function loadClass(percent) {
  if (percent === null || percent === undefined) return "optick-load-unknown";
  if (percent >= 50) return "optick-load-critical";
  if (percent >= 20) return "optick-load-warn";
  return "optick-load-ok";
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
