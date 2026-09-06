// Tests de la logique PURE du graphique du cycle agile réseau.
// Lancer : node --test hub/tests/  (aucune dépendance, aucun navigateur)
import { test } from "node:test";
import assert from "node:assert/strict";
import {
  GRAPH_ZOOM_MIN, GRAPH_ZOOM_MAX, GRAPH_ZOOM_STEP, GRAPH_VB_WIDTH, GRAPH_VB_HEIGHT,
  clampZoom, zoomAtPoint, clientDeltaToViewBox, clientPointToViewBox,
  clampTooltipPosition, getStepTooltipLines,
} from "../src/networkCycleGraph.js";

test("clampZoom borne des deux côtés et survit à une valeur invalide", () => {
  assert.equal(clampZoom(1), 1);
  assert.equal(clampZoom(100), GRAPH_ZOOM_MAX);
  assert.equal(clampZoom(0.001), GRAPH_ZOOM_MIN);
  assert.equal(clampZoom(NaN), 1);
  assert.equal(clampZoom(undefined), 1);
});

test("zoomAtPoint laisse le point d'ancrage strictement immobile à l'écran", () => {
  // Un point p du dessin s'affiche en (x + zoom * p). L'ancre doit donc
  // correspondre au MÊME p avant et après le zoom.
  const before = { zoom: 1, x: 0, y: 0 };
  const ax = 300, ay = 150;
  const after = zoomAtPoint(before, GRAPH_ZOOM_STEP, ax, ay);
  const pBefore = { x: (ax - before.x) / before.zoom, y: (ay - before.y) / before.zoom };
  const pAfter = { x: (ax - after.x) / after.zoom, y: (ay - after.y) / after.zoom };
  assert.ok(Math.abs(pBefore.x - pAfter.x) < 1e-9, "dérive horizontale");
  assert.ok(Math.abs(pBefore.y - pAfter.y) < 1e-9, "dérive verticale");
});

test("zoomAtPoint ne déplace plus rien une fois la butée atteinte", () => {
  // Le bug classique : appliquer le facteur DEMANDÉ au lieu du facteur
  // réellement appliqué après bornage -- le dessin continue alors de glisser
  // sous le curseur à chaque cran de molette supplémentaire.
  let v = { zoom: GRAPH_ZOOM_MAX, x: 42, y: -17 };
  const next = zoomAtPoint(v, GRAPH_ZOOM_STEP, 400, 200);
  assert.equal(next.zoom, GRAPH_ZOOM_MAX);
  assert.equal(next.x, 42);
  assert.equal(next.y, -17);
});

test("zoomAtPoint enchaîne zoom avant puis arrière sans dérive", () => {
  const start = { zoom: 1, x: 10, y: 20 };
  const zoomed = zoomAtPoint(start, GRAPH_ZOOM_STEP, 250, 120);
  const back = zoomAtPoint(zoomed, 1 / GRAPH_ZOOM_STEP, 250, 120);
  assert.ok(Math.abs(back.zoom - start.zoom) < 1e-9);
  assert.ok(Math.abs(back.x - start.x) < 1e-9);
  assert.ok(Math.abs(back.y - start.y) < 1e-9);
});

test("clientDeltaToViewBox utilise UNE échelle commune (preserveAspectRatio meet)", () => {
  // Conteneur 1000x420 pour un viewBox 800x400 : le côté contraignant est la
  // hauteur (400/420 > 800/1000). Diviser par axe donnerait 0.8 en x et
  // 0.952 en y -- le dessin dériverait en diagonale pendant un glisser droit.
  const rect = { width: 1000, height: 420 };
  const { dx, dy } = clientDeltaToViewBox(100, 100, rect, GRAPH_VB_WIDTH, GRAPH_VB_HEIGHT);
  assert.ok(Math.abs(dx - dy) < 1e-9, "les deux axes doivent partager l'échelle");
  assert.ok(Math.abs(dx - 100 * (400 / 420)) < 1e-9);
});

test("clientDeltaToViewBox neutralise un conteneur non mesuré", () => {
  assert.deepEqual(clientDeltaToViewBox(50, 50, null, 800, 400), { dx: 0, dy: 0 });
  assert.deepEqual(clientDeltaToViewBox(50, 50, { width: 0, height: 0 }, 800, 400), { dx: 0, dy: 0 });
});

test("clientPointToViewBox retire le letterboxing avant conversion", () => {
  // Conteneur 1000x400 pour un viewBox 800x400 : échelle 1, marge de 100px
  // de chaque côté. Le centre du conteneur (500) doit tomber sur 400 (centre
  // du viewBox), pas sur 500.
  const rect = { width: 1000, height: 400 };
  const p = clientPointToViewBox(500, 200, rect, 800, 400);
  assert.ok(Math.abs(p.x - 400) < 1e-9, `centre horizontal attendu 400, obtenu ${p.x}`);
  assert.ok(Math.abs(p.y - 200) < 1e-9);
  const origin = clientPointToViewBox(100, 0, rect, 800, 400);
  assert.ok(Math.abs(origin.x - 0) < 1e-9, "bord gauche du dessin");
});

test("clampTooltipPosition bascule à gauche plutôt que de déborder", () => {
  const boxW = 800, boxH = 420, tipW = 250, tipH = 90;
  const right = clampTooltipPosition(700, 50, tipW, tipH, boxW, boxH);
  assert.ok(right.left + tipW <= boxW, "déborde à droite (serait coupé par overflow:hidden)");
  const bottom = clampTooltipPosition(100, 400, tipW, tipH, boxW, boxH);
  assert.ok(bottom.top + tipH <= boxH, "déborde en bas");
  const normal = clampTooltipPosition(100, 50, tipW, tipH, boxW, boxH);
  assert.equal(normal.left, 114);
  assert.equal(normal.top, 64);
});

test("clampTooltipPosition reste dans le cadre même si l'infobulle est plus large que lui", () => {
  const r = clampTooltipPosition(10, 10, 400, 90, 300, 200);
  assert.ok(r.left >= 0 - 1e-9 || r.left === 0);
  assert.ok(r.top >= 0);
});

test("getStepTooltipLines dit 'non configuré' plutôt que d'inventer des chiffres", () => {
  const vide = {};
  assert.match(getStepTooltipLines("decider", vide)[0], /non configuré/i);
  assert.match(getStepTooltipLines("explorer", vide)[0], /non configuré/i);
  assert.match(getStepTooltipLines("mesurer", vide)[0], /non configuré/i);
  assert.deepEqual(getStepTooltipLines("inconnu", vide), []);
});

test("getStepTooltipLines résiste aux collections absentes", () => {
  const data = {
    netmapOrchestratorApiBase: "http://x", orchestratorSummary: {},
    networkAgentApiBase: "http://x", captureStatus: { running: true },
    netprobeApiBase: "http://x", latestSamples: [{ success: true }, { success: false }],
    vigilanceApiBase: "http://x",
  };
  assert.deepEqual(getStepTooltipLines("decider", data), [
    "0 suggestion(s) ouverte(s)",
    "0 traitée(s) · 0 rejetée(s)",
  ]);
  assert.deepEqual(getStepTooltipLines("explorer", data), [
    "Capture en cours",
    "0 site(s) découvert(s)",
  ]);
  assert.equal(getStepTooltipLines("mesurer", data)[0], "1/2 cible(s) en ligne");
  assert.equal(getStepTooltipLines("mesurer", data)[1], "0/0 sonde(s) active(s)");
  assert.equal(getStepTooltipLines("deployer", data)[0], "Aucun tunnel ni cible SNMP");
  assert.equal(getStepTooltipLines("apprendre", data)[0], "0 signal(aux) critique(s) · 0 avertissement(s)");
});

test("getStepTooltipLines agrège correctement des données réelles", () => {
  const data = {
    sshTunnelsApiBase: "http://x",
    tunnels: [{ status: "running" }, { status: "error" }, { status: "stopped" }],
    snmpTargets: [{}, {}],
    connections: [{}],
    vigilanceApiBase: "http://x",
    vigilanceSummary: [
      { severity: "critical", n: 2 }, { severity: "critical", n: 1 }, { severity: "warning", n: 5 },
    ],
    backupRestoreApiBase: "http://x",
    coverage: { without_backup: 4 },
  };
  assert.equal(getStepTooltipLines("deployer", data)[0], "1/3 tunnel(s) actif(s) · 1 en erreur");
  assert.equal(getStepTooltipLines("deployer", data)[1], "2 cible(s) SNMP · 1 connexion(s)");
  const app = getStepTooltipLines("apprendre", data);
  assert.equal(app[0], "3 signal(aux) critique(s) · 5 avertissement(s)");
  assert.equal(app[1], "4 élément(s) sans sauvegarde");
});
