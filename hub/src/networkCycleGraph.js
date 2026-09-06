// Logique PURE du graphique du cycle agile réseau : zoom, déplacement,
// placement de l'infobulle, contenu de l'infobulle.
//
// Module séparé DÉLIBÉRÉMENT -- même motif que `ldapTree.js` (buildColumns/
// buildTree) : aucun import React ici, donc testable directement sous Node
// sans navigateur ni transformation JSX (voir tests/networkCycleGraph.test.mjs).

// --- Graphique : zoom, déplacement, infobulle -- LOGIQUE PURE ---
// Extraite volontairement du composant pour être testable sans navigateur
// (voir hub/tests/networkCycleGraph.test.mjs).

export const GRAPH_ZOOM_MIN = 0.6;
export const GRAPH_ZOOM_MAX = 4;
export const GRAPH_ZOOM_STEP = 1.25;
export const GRAPH_VIEW_INITIAL = { zoom: 1, x: 0, y: 0 };
export const GRAPH_REFRESH_MS = 30000;
// Dimensions du viewBox -- partagées entre le rendu et les gestionnaires
// d'interaction, jamais redéclarées localement des deux côtés.
export const GRAPH_VB_WIDTH = 800;
export const GRAPH_VB_HEIGHT = 400;

export function clampZoom(z) {
  if (!Number.isFinite(z)) return 1;
  return Math.min(GRAPH_ZOOM_MAX, Math.max(GRAPH_ZOOM_MIN, z));
}

// Zoom centré sur un point EXPRIMÉ EN COORDONNÉES viewBox : ce point reste
// exactement sous le curseur après le zoom. Le groupe porte la transformation
// `translate(x y) scale(zoom)`, donc un point p du dessin s'affiche en
// (x + zoom*p) ; imposer que l'ancre c ne bouge pas donne
// x' = c - (c - x) * (zoom'/zoom).
// Le facteur réellement appliqué est recalculé APRÈS bornage -- sinon, une
// fois la butée de zoom atteinte, le dessin continuerait de glisser sous le
// curseur à chaque cran de molette supplémentaire.
export function zoomAtPoint(view, factor, anchorX, anchorY) {
  const zoom = clampZoom(view.zoom * factor);
  const applied = zoom / view.zoom;
  return {
    zoom,
    x: anchorX - (anchorX - view.x) * applied,
    y: anchorY - (anchorY - view.y) * applied,
  };
}

// Conversion d'un déplacement souris (pixels écran) en unités viewBox.
// preserveAspectRatio="xMidYMid meet" applique UNE SEULE échelle commune aux
// deux axes (celle du côté le plus contraint) -- diviser par rect.width sur x
// et par rect.height sur y ferait dériver le déplacement dès que le ratio du
// conteneur diffère de celui du viewBox (c'est le cas ici : 800x400 dans un
// conteneur de 420px de haut sur toute la largeur).
export function clientDeltaToViewBox(dxPx, dyPx, rect, vbWidth, vbHeight) {
  if (!rect || !(rect.width > 0) || !(rect.height > 0)) return { dx: 0, dy: 0 };
  const unitsPerPixel = Math.max(vbWidth / rect.width, vbHeight / rect.height);
  return { dx: dxPx * unitsPerPixel, dy: dyPx * unitsPerPixel };
}

// Position d'un point écran ramené en coordonnées viewBox NON transformées
// (avant translate/scale) -- nécessaire pour ancrer le zoom molette.
export function clientPointToViewBox(xPx, yPx, rect, vbWidth, vbHeight) {
  if (!rect || !(rect.width > 0) || !(rect.height > 0)) return { x: vbWidth / 2, y: vbHeight / 2 };
  const unitsPerPixel = Math.max(vbWidth / rect.width, vbHeight / rect.height);
  // "meet" centre le dessin dans le conteneur : les marges éventuelles
  // (letterboxing) doivent être retirées avant conversion.
  const drawnW = vbWidth / unitsPerPixel;
  const drawnH = vbHeight / unitsPerPixel;
  const offsetX = (rect.width - drawnW) / 2;
  const offsetY = (rect.height - drawnH) / 2;
  return { x: (xPx - offsetX) * unitsPerPixel, y: (yPx - offsetY) * unitsPerPixel };
}

// Position de l'infobulle DANS le conteneur. `.nc-graph-container` est en
// `overflow: hidden` -- piège déjà rencontré ailleurs dans ce projet : un
// popup positionné à l'intérieur d'un conteneur qui recadre est purement et
// simplement coupé. On borne donc la position et on bascule l'infobulle à
// GAUCHE du curseur quand elle déborderait à droite, plutôt que de compter
// sur un débordement qui n'arrivera jamais.
export function clampTooltipPosition(x, y, tipW, tipH, boxW, boxH, offset = 14) {
  let left = x + offset;
  if (left + tipW > boxW) left = x - offset - tipW;
  if (left < 0) left = Math.max(0, boxW - tipW);
  let top = y + offset;
  if (top + tipH > boxH) top = y - offset - tipH;
  if (top < 0) top = 0;
  return { left, top };
}

// Détail affiché dans l'infobulle -- COMPLÈTE le texte déjà présent sous le
// nœud (volontairement compact), jamais une répétition de celui-ci.
// N'utilise que des champs déjà consommés ailleurs dans ce fichier, jamais un
// champ d'API supposé.
export function getStepTooltipLines(stepId, data) {
  switch (stepId) {
    case "decider": {
      if (!data.netmapOrchestratorApiBase) return ["Orchestrateur réseau non configuré"];
      const s = data.orchestratorSummary;
      if (!s) return ["Aucune donnée de l'orchestrateur"];
      return [
        `${s.open ?? 0} suggestion(s) ouverte(s)`,
        `${s.done ?? 0} traitée(s) · ${s.dismissed ?? 0} rejetée(s)`,
      ];
    }
    case "explorer": {
      if (!data.networkAgentApiBase) return ["Agent réseau non configuré"];
      const status = data.captureStatus;
      if (!status) return ["Aucune donnée de capture"];
      return [
        status.running ? "Capture en cours" : "Capture arrêtée",
        `${data.sites?.length ?? 0} site(s) découvert(s)`,
      ];
    }
    case "deployer": {
      const tunnels = data.tunnels || [];
      const errors = tunnels.filter((t) => t.status === "error").length;
      const running = tunnels.filter((t) => t.status === "running").length;
      if (tunnels.length === 0 && (data.snmpTargets?.length ?? 0) === 0) {
        return ["Aucun tunnel ni cible SNMP"];
      }
      return [
        `${running}/${tunnels.length} tunnel(s) actif(s)` + (errors ? ` · ${errors} en erreur` : ""),
        `${data.snmpTargets?.length ?? 0} cible(s) SNMP · ${data.connections?.length ?? 0} connexion(s)`,
      ];
    }
    case "mesurer": {
      if (!data.netprobeApiBase) return ["Sondes réseau non configurées"];
      const samples = data.latestSamples || [];
      if (samples.length === 0) return ["Aucune mesure disponible"];
      const up = samples.filter((s) => s.success).length;
      const configs = data.probeConfigs || [];
      return [
        `${up}/${samples.length} cible(s) en ligne`,
        `${configs.filter((c) => c.enabled).length}/${configs.length} sonde(s) active(s)`,
      ];
    }
    case "apprendre": {
      if (!data.vigilanceApiBase && !data.backupRestoreApiBase) {
        return ["Vigilance et sauvegardes non configurées"];
      }
      const sum = data.vigilanceSummary || [];
      const critical = sum.filter((s) => s.severity === "critical").reduce((a, s) => a + (s.n || 0), 0);
      const warning = sum.filter((s) => s.severity === "warning").reduce((a, s) => a + (s.n || 0), 0);
      const lines = [`${critical} signal(aux) critique(s) · ${warning} avertissement(s)`];
      if (data.coverage) lines.push(`${data.coverage.without_backup ?? "?"} élément(s) sans sauvegarde`);
      return lines;
    }
    default:
      return [];
  }
}
