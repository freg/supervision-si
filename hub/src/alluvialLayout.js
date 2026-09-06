// Calcul de layout pour un diagramme alluvial simple (2 colonnes :
// sources à gauche, destinations à droite) -- livraison #389,
// backlog item 58 ("graphe alluvial (flux tcpip/udp)"). PAS de
// dépendance d3-sankey (inaccessible depuis cet environnement de
// développement, réseau restreint -- confirmé, pas juste supposé)
// -- calcul MANUEL, volontairement simple : un appareil qui est à la
// fois source ET destination apparaît deux fois (motif standard pour
// ce type de diagramme avec des flux bidirectionnels, pas une
// approximation).
//
// Séparé du rendu (AlluvialFlowChart.jsx) pour rester testable sans
// navigateur -- pure fonction de données en entrée vers positions en
// sortie, aucun effet de bord.

/**
 * @param {Array} links - [{device_a_id, device_b_id, bytes_total, packet_count}, ...]
 * @param {Object} deviceLabels - {id: "label lisible"} déjà résolu par l'appelant
 * @param {Object} options - {width, height, nodeWidth, minLinkWidth, maxLinkWidth}
 */
export function computeAlluvialLayout(links, deviceLabels, options = {}) {
  const width = options.width ?? 700;
  const height = options.height ?? 500;
  const nodeWidth = options.nodeWidth ?? 12;
  const minLinkWidth = options.minLinkWidth ?? 1;
  const maxLinkWidth = options.maxLinkWidth ?? 24;

  const validLinks = (links || []).filter((l) => (l.bytes_total ?? 0) > 0);
  if (validLinks.length === 0) {
    return { sourceNodes: [], destNodes: [], linkPaths: [], isEmpty: true };
  }

  // Totaux par source/destination -- déterminent la hauteur de bande
  // de chaque nœud, proportionnelle à son volume total (convention
  // standard d'un diagramme de Sankey/alluvial).
  const sourceTotals = new Map();
  const destTotals = new Map();
  for (const l of validLinks) {
    sourceTotals.set(l.device_a_id, (sourceTotals.get(l.device_a_id) || 0) + l.bytes_total);
    destTotals.set(l.device_b_id, (destTotals.get(l.device_b_id) || 0) + l.bytes_total);
  }

  const grandTotal = validLinks.reduce((sum, l) => sum + l.bytes_total, 0);

  // Tri par volume décroissant -- les flux les plus importants en
  // haut, lecture plus naturelle.
  const sourceIds = [...sourceTotals.keys()].sort((a, b) => sourceTotals.get(b) - sourceTotals.get(a));
  const destIds = [...destTotals.keys()].sort((a, b) => destTotals.get(b) - destTotals.get(a));

  // Empilement vertical -- chaque nœud occupe une bande proportionnelle
  // à son total, avec un petit espacement fixe entre nœuds pour rester
  // lisible même avec beaucoup de nœuds de faible volume.
  const gap = 4;
  function layoutColumn(ids, totals) {
    const usableHeight = height - gap * (ids.length - 1);
    let y = 0;
    const nodes = [];
    for (const id of ids) {
      const h = Math.max(2, (totals.get(id) / grandTotal) * usableHeight);
      nodes.push({ id, y0: y, y1: y + h, total: totals.get(id) });
      y += h + gap;
    }
    return nodes;
  }

  const sourceNodesRaw = layoutColumn(sourceIds, sourceTotals);
  const destNodesRaw = layoutColumn(destIds, destTotals);
  const sourceById = new Map(sourceNodesRaw.map((n) => [n.id, n]));
  const destById = new Map(destNodesRaw.map((n) => [n.id, n]));

  // Position de départ DANS la bande de chaque nœud, pour empiler les
  // liens individuels sans qu'ils se chevauchent visuellement.
  const sourceCursor = new Map(sourceNodesRaw.map((n) => [n.id, n.y0]));
  const destCursor = new Map(destNodesRaw.map((n) => [n.id, n.y0]));

  const linkScale = (bytes) => {
    if (grandTotal === 0) return minLinkWidth;
    const ratio = bytes / Math.max(...validLinks.map((l) => l.bytes_total));
    return minLinkWidth + ratio * (maxLinkWidth - minLinkWidth);
  };

  const linkPaths = validLinks.map((l, i) => {
    const srcNode = sourceById.get(l.device_a_id);
    const dstNode = destById.get(l.device_b_id);
    const srcTotal = srcNode.total;
    const dstTotal = dstNode.total;
    const srcSpan = (l.bytes_total / srcTotal) * (srcNode.y1 - srcNode.y0);
    const dstSpan = (l.bytes_total / dstTotal) * (dstNode.y1 - dstNode.y0);
    const srcY = sourceCursor.get(l.device_a_id) + srcSpan / 2;
    const dstY = destCursor.get(l.device_b_id) + dstSpan / 2;
    sourceCursor.set(l.device_a_id, sourceCursor.get(l.device_a_id) + srcSpan);
    destCursor.set(l.device_b_id, destCursor.get(l.device_b_id) + dstSpan);
    return {
      key: `${l.device_a_id}-${l.device_b_id}-${i}`,
      sourceId: l.device_a_id,
      destId: l.device_b_id,
      sourceY: srcY,
      destY: dstY,
      strokeWidth: linkScale(l.bytes_total),
      bytesTotal: l.bytes_total,
      packetCount: l.packet_count,
    };
  });

  const sourceNodes = sourceNodesRaw.map((n) => ({
    ...n,
    x: 0,
    label: deviceLabels[n.id] || `#${n.id}`,
  }));
  const destNodes = destNodesRaw.map((n) => ({
    ...n,
    x: width - nodeWidth,
    label: deviceLabels[n.id] || `#${n.id}`,
  }));

  return { sourceNodes, destNodes, linkPaths, isEmpty: false, nodeWidth, width, height };
}
