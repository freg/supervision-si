// Parseur markdown minimal -- demandé explicitement ("rendu markdown
// correct : titres, gras, listes") pour la vue historique/backlog du
// hub. Volontairement PAS une bibliothèque externe (aucune utilisée
// ailleurs dans ce projet) : CHANGELOG.md/BACKLOG.md n'utilisent
// qu'un sous-ensemble simple et connu du markdown (titres #/##/###,
// **gras**, `code inline`, listes à puces -/*, paragraphes) --
// couvrir exactement ça plutôt que d'ajouter une dépendance pour un
// besoin aussi ciblé.
//
// Renvoie des BLOCS DE DONNÉES purs (jamais du JSX directement) --
// reste testable sans React, le rendu JSX est une étape séparée
// (voir MarkdownView dans App.jsx).

/** Découpe une ligne de texte en segments {type: "text"|"bold"|"code",
 * content} -- gère **gras** et `code`, jamais imbriqués l'un dans
 * l'autre (pas nécessaire pour ces fichiers). */
export function parseInline(text) {
  const segments = [];
  let remaining = text;
  const pattern = /(\*\*(.+?)\*\*|`(.+?)`)/;
  while (remaining.length > 0) {
    const match = remaining.match(pattern);
    if (!match) {
      segments.push({ type: "text", content: remaining });
      break;
    }
    if (match.index > 0) {
      segments.push({ type: "text", content: remaining.slice(0, match.index) });
    }
    if (match[2] !== undefined) {
      segments.push({ type: "bold", content: match[2] });
    } else {
      segments.push({ type: "code", content: match[3] });
    }
    remaining = remaining.slice(match.index + match[0].length);
  }
  return segments;
}

/** Découpe un texte markdown complet en blocs -- {type: "heading",
 * level, inline} | {type: "paragraph", inline} | {type: "list",
 * items: [inline, ...]}. Les lignes d'un même paragraphe (séparées
 * par un simple retour à la ligne, pas une ligne vide) sont fusionnées
 * avec un espace -- markdown standard, jamais un <br> par ligne. */
export function parseMarkdown(text) {
  const lines = (text || "").replace(/\r\n/g, "\n").split("\n");
  const blocks = [];
  let currentParagraph = [];
  let currentList = null;

  function flushParagraph() {
    if (currentParagraph.length > 0) {
      blocks.push({ type: "paragraph", inline: parseInline(currentParagraph.join(" ")) });
      currentParagraph = [];
    }
  }
  function flushList() {
    if (currentList) {
      blocks.push(currentList);
      currentList = null;
    }
  }

  for (const rawLine of lines) {
    const line = rawLine.trimEnd();
    const headingMatch = line.match(/^(#{1,3})\s+(.*)$/);
    if (headingMatch) {
      flushParagraph();
      flushList();
      blocks.push({ type: "heading", level: headingMatch[1].length, inline: parseInline(headingMatch[2]) });
      continue;
    }
    const listMatch = line.match(/^[-*]\s+(.*)$/);
    if (listMatch) {
      flushParagraph();
      if (!currentList) currentList = { type: "list", items: [] };
      currentList.items.push(parseInline(listMatch[1]));
      continue;
    }
    if (line.trim() === "") {
      flushParagraph();
      flushList();
      continue;
    }
    // Ligne de continuation -- jamais celle d'une liste (une liste
    // s'interrompt dès qu'une ligne ne commence plus par -/*).
    flushList();
    currentParagraph.push(line.trim());
  }
  flushParagraph();
  flushList();
  return blocks;
}
