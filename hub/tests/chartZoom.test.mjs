import { test } from "node:test";
import assert from "node:assert/strict";
import {
  ZOOM_MIN, ZOOM_MAX, ZOOM_STEP, VIEW_INITIAL,
  parseViewBox, clampZoom, zoomAtPoint, zoomAtCenter, unitsPerPixel,
  clientDeltaToViewBox, clientPointToViewBox, viewTransform, isInitialView, zoomPercent,
} from "../src/chartZoom.js";

const close = (a, b, msg) => assert.ok(Math.abs(a - b) < 1e-9, `${msg || ""} ${a} ≠ ${b}`);

test("parseViewBox accepte espaces et virgules, refuse l'invalide", () => {
  assert.deepEqual(parseViewBox("0 0 700 500"), { x: 0, y: 0, w: 700, h: 500 });
  assert.deepEqual(parseViewBox("-290,-290,580,580"), { x: -290, y: -290, w: 580, h: 580 });
  assert.equal(parseViewBox("0 0 700"), null);
  assert.equal(parseViewBox("0 0 0 500"), null);
  assert.equal(parseViewBox(undefined), null);
});

test("le zoom est borné et un facteur invalide ramène à 1", () => {
  assert.equal(clampZoom(0.01), ZOOM_MIN);
  assert.equal(clampZoom(100), ZOOM_MAX);
  assert.equal(clampZoom(NaN), 1);
});

test("le point sous le curseur reste immobile après un zoom, même avec une origine non nulle", () => {
  const vb = { x: -290, y: -290, w: 580, h: 580 };
  const anchor = { x: 100, y: -50 };
  let view = VIEW_INITIAL;
  for (let i = 0; i < 4; i++) view = zoomAtPoint(view, ZOOM_STEP, anchor.x, anchor.y);
  // Le point p=anchor s'affiche en x + zoom*p : doit rester égal à anchor.
  close(view.x + view.zoom * anchor.x, anchor.x, "x");
  close(view.y + view.zoom * anchor.y, anchor.y, "y");
  const back = zoomAtCenter(view, 1 / view.zoom, vb);
  close(back.zoom, 1);
});

test("en butée, le dessin ne glisse plus sous le curseur", () => {
  let view = { zoom: ZOOM_MAX, x: -100, y: -50 };
  const next = zoomAtPoint(view, ZOOM_STEP, 300, 200);
  assert.deepEqual(next, view);
});

test("unitsPerPixel : une échelle commune en meet (avec marges), une par axe en none", () => {
  const vb = { x: 0, y: 0, w: 800, h: 400 };
  const meet = unitsPerPixel({ width: 1000, height: 1000 }, vb, "meet");
  close(meet.ux, 0.8); close(meet.uy, 0.8);
  close(meet.offsetX, 0); close(meet.offsetY, (1000 - 500) / 2);
  const none = unitsPerPixel({ width: 1000, height: 100 }, vb, "none");
  close(none.ux, 0.8); close(none.uy, 4); close(none.offsetX, 0);
  assert.equal(unitsPerPixel({ width: 0, height: 10 }, vb), null);
});

test("conversions écran → viewBox dans les deux modes", () => {
  const vb = { x: -290, y: -290, w: 580, h: 580 };
  const rect = { width: 1160, height: 580 };  // meet : u = 1, dessin centré horizontalement (marge 290)
  assert.deepEqual(clientDeltaToViewBox(10, -20, rect, vb, "meet"), { dx: 10, dy: -20 });
  const p = clientPointToViewBox(580, 290, rect, vb, "meet");
  close(p.x, 0, "centre x"); close(p.y, 0, "centre y");
  const vbBars = { x: 0, y: 0, w: 320, h: 48 };
  const rectBars = { width: 640, height: 240 };
  assert.deepEqual(clientDeltaToViewBox(2, 5, rectBars, vbBars, "none"), { dx: 1, dy: 1 });
  const q = clientPointToViewBox(640, 240, rectBars, vbBars, "none");
  assert.deepEqual(q, { x: 320, y: 48 });
  assert.deepEqual(clientDeltaToViewBox(1, 1, null, vb), { dx: 0, dy: 0 });
  assert.deepEqual(clientPointToViewBox(1, 1, null, vb), { x: 0, y: 0 }, "sans rect : centre du viewBox");
});

test("transformation, état initial, pourcentage", () => {
  assert.equal(viewTransform({ zoom: 2, x: -10, y: 5 }), "translate(-10 5) scale(2)");
  assert.equal(isInitialView(VIEW_INITIAL), true);
  assert.equal(isInitialView({ zoom: 1, x: 1, y: 0 }), false);
  assert.equal(zoomPercent({ zoom: 1.25 }), 125);
});
