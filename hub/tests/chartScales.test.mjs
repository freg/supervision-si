import { test } from "node:test";
import assert from "node:assert/strict";
import {
  SCALE_MODES, DEFAULT_SCALE_MODE, GAIN_MIN, GAIN_MAX, DEFAULT_GAIN,
  scaleRatio, makeScale, clampGain, loadScalePreference, saveScalePreference, SCALE_STORAGE_KEY,
} from "../src/chartScales.js";

const close = (a, b, msg) => assert.ok(Math.abs(a - b) < 1e-9, `${msg || ""} ${a} ≠ ${b}`);

test("scaleRatio : 0 en bas, 1 au maximum, ordre conservé dans les trois échelles", () => {
  for (const { id } of SCALE_MODES) {
    assert.equal(scaleRatio(0, 1000, id), 0, id);
    assert.equal(scaleRatio(-5, 1000, id), 0, id);
    assert.equal(scaleRatio(1000, 1000, id), 1, id);
    assert.equal(scaleRatio(5000, 1000, id), 1, `${id} : au-delà du max, 1`);
    assert.ok(scaleRatio(10, 1000, id) < scaleRatio(100, 1000, id), `${id} : croissante`);
  }
  assert.equal(scaleRatio(10, 0), 0, "max nul");
});

test("les échelles compressent de plus en plus : linéaire < racine < log pour un petit flux", () => {
  const lin = scaleRatio(10, 1000, "linear");
  const sq = scaleRatio(10, 1000, "sqrt");
  const lg = scaleRatio(10, 1000, "log");
  close(lin, 0.01);
  close(sq, 0.1);
  assert.ok(lg > sq && lg < 1, `log ${lg}`);
});

test("makeScale : bornes de sortie, gain, minimum garanti, mode inconnu → linéaire", () => {
  const values = [1000, 100, 10, 0];
  const f = makeScale(values, { minOut: 1, maxOut: 21 });
  assert.equal(f.max, 1000);
  assert.equal(f.mode, DEFAULT_SCALE_MODE);
  assert.equal(f(1000), 21);
  close(f(100), 1 + 0.1 * 20);
  assert.equal(f(0), 1, "valeur nulle : minimum");
  assert.equal(f(undefined), 1);
  const g = makeScale(values, { minOut: 1, maxOut: 21, gain: 2 });
  assert.equal(g(1000), 41, "gain sur la part au-dessus du minimum");
  close(g(0.0001), 1.000004, "le gain ne descend jamais sous le minimum");
  const h = makeScale(values, { minOut: 1, maxOut: 21, gain: 0.25 });
  close(h(1000), 6);
  const u = makeScale(values, { mode: "bidon" });
  assert.equal(u.mode, "linear");
  const empty = makeScale([], { minOut: 2 });
  assert.equal(empty.max, 0);
  assert.equal(empty(50), 2);
  const fixed = makeScale([5], { max: 100, minOut: 0, maxOut: 10 });
  close(fixed(50), 5, "maximum imposé");
});

test("clampGain borne et tolère", () => {
  assert.equal(clampGain(0), GAIN_MIN);
  assert.equal(clampGain(99), GAIN_MAX);
  assert.equal(clampGain("2"), 2);
  assert.equal(clampGain("abc"), DEFAULT_GAIN);
});

test("préférence d'échelle : tolérante en lecture, normalisée en écriture", () => {
  const data = {};
  const st = { getItem: (k) => data[k] ?? null, setItem: (k, v) => { data[k] = v; } };
  assert.deepEqual(loadScalePreference(st), { mode: "linear", gain: 1 });
  assert.equal(saveScalePreference(st, { mode: "log", gain: 50 }), true);
  assert.deepEqual(JSON.parse(data[SCALE_STORAGE_KEY]), { mode: "log", gain: GAIN_MAX });
  assert.deepEqual(loadScalePreference(st), { mode: "log", gain: GAIN_MAX });
  data[SCALE_STORAGE_KEY] = "{cassé";
  assert.deepEqual(loadScalePreference(st), { mode: "linear", gain: 1 });
  const broken = { getItem: () => { throw new Error("x"); }, setItem: () => { throw new Error("x"); } };
  assert.deepEqual(loadScalePreference(broken), { mode: "linear", gain: 1 });
  assert.equal(saveScalePreference(broken, { mode: "sqrt", gain: 1 }), false);
});
