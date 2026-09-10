// Construction de la structure hiérarchique + calcul d'échelle pour
// le radial tree pondéré (backlog item 58, "radial tree augmenté
// avec des liens d'épaisseur proportionnelle au volume échangé",
// livraison #389).
//
// ⚠️ Séparé DÉLIBÉRÉMENT du rendu D3 lui-même (WeightedRadialTree.jsx)
// -- `d3` (le paquet lui-même, pas seulement `d3-sankey`) s'est
// révélé INACCESSIBLE depuis cet environnement de développement
// (npm réseau restreint, confirmé par un essai réel, 403 Forbidden)
// -- CE fichier-ci (construction de données pures, aucun appel D3)
// reste testable sans le paquet ; le rendu SVG/D3 lui-même
// (WeightedRadialTree.jsx) calque fidèlement le motif déjà établi et
// PRÉSUMÉ fonctionnel d'OptickRadialTree.jsx, mais n'a PAS pu être
// exécuté ici -- à vérifier en priorité au premier rendu réel.
import { makeScale } from "./chartScales.js";

/**
 * Construit l'arbre hiérarchique {id, name, children} attendu par
 * d3.hierarchy -- racine unique -> un enfant par segment réseau ->
 * un enfant par appareil (feuille). Regroupe les appareils PAR
 * network_segment_id -- même hiérarchie naturelle que
 * network-agent-api lui-même (site -> segment -> appareil, voir
 * network-agent/api/store.py).
 */
export function buildDeviceHierarchy(devices, segmentLabels = {}) {
  const bySegment = new Map();
  for (const d of devices || []) {
    const segId = d.network_segment_id;
    if (!bySegment.has(segId)) bySegment.set(segId, []);
    bySegment.get(segId).push(d);
  }

  const children = [...bySegment.entries()].map(([segId, devs]) => ({
    id: `segment-${segId}`,
    name: segmentLabels[segId] || `Segment ${segId}`,
    type: "segment",
    children: devs.map((d) => ({
      id: `device-${d.id}`,
      deviceId: d.id,
      name: d.hostname || d.ip_address || d.mac_address || `#${d.id}`,
      type: "device",
      children: [],
    })),
  }));

  return { id: "root", name: "Réseau", type: "root", children };
}

/**
 * Échelle de largeur de trait entre minWidth/maxWidth, proportionnelle au
 * volume RELATIF au maximum observé (jamais un seuil absolu, cohérent avec
 * le principe déjà appliqué ailleurs dans ce projet -- voir pixel-grid,
 * mode "Activité", #371). Livraison #413 : échelle linéaire / racine / log
 * et gain via chartScales.makeScale (`scale` = {mode, gain}), la même
 * modulation que le diagramme alluvial.
 */
export function makeVolumeWidthScale(links, minWidth = 0.5, maxWidth = 8, scale = {}) {
  const volumes = (links || []).map((l) => l.bytes_total ?? 0);
  return makeScale(volumes, { mode: scale.mode, gain: scale.gain, minOut: minWidth, maxOut: maxWidth });
}

/**
 * Associe chaque lien (device_a_id/device_b_id) à l'identifiant de
 * nœud `device-<id>` utilisé dans la hiérarchie ci-dessus -- pour
 * retrouver la position (x, y) calculée par d3.hierarchy/d3.tree
 * côté composant de rendu, SANS dupliquer cette logique de recherche
 * dans le composant lui-même.
 */
export function prepareWeightedLinks(links, widthScale) {
  return (links || [])
    .filter((l) => (l.bytes_total ?? 0) > 0)
    .map((l) => ({
      sourceNodeId: `device-${l.device_a_id}`,
      destNodeId: `device-${l.device_b_id}`,
      strokeWidth: widthScale(l.bytes_total),
      bytesTotal: l.bytes_total,
      packetCount: l.packet_count,
    }));
}
