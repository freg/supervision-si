import { test } from "node:test";
import assert from "node:assert/strict";
import {
  ICON_SETS, ICON_SET_IDS, DEFAULT_ICON_SET, CYCLE_STEP_IDS,
  EMOJI_ALTERNATIVES, REJECTED_ICONS,
  resolveIconSet, getStepIcon, getStepIconText,
  loadIconSetPreference, saveIconSetPreference, ICON_SET_STORAGE_KEY,
} from "../src/icons.js";

function fakeStorage(initial = {}) {
  const data = { ...initial };
  return {
    getItem: (k) => (k in data ? data[k] : null),
    setItem: (k, v) => { data[k] = String(v); },
    data,
  };
}

test("chaque jeu définit une icône pour chacune des cinq étapes", () => {
  for (const id of ICON_SET_IDS) {
    const set = ICON_SETS[id];
    for (const step of CYCLE_STEP_IDS) {
      assert.ok(set.icons[step], `${id}/${step}`);
    }
    assert.equal(Object.keys(set.icons).length, CYCLE_STEP_IDS.length, `${id} : pas d'étape en trop`);
    assert.ok(["text", "glyph", "svg"].includes(set.kind));
  }
});

test("les icônes écartées par la charte n'apparaissent dans aucun jeu ni aucune alternative", () => {
  const rejected = Object.keys(REJECTED_ICONS);
  for (const id of ICON_SET_IDS) {
    const set = ICON_SETS[id];
    if (set.kind === "svg") continue;
    for (const v of Object.values(set.icons)) assert.ok(!rejected.includes(v), `${id} contient ${v}`);
  }
  for (const list of Object.values(EMOJI_ALTERNATIVES)) {
    for (const v of list) assert.ok(!rejected.includes(v), `alternative ${v} écartée`);
  }
});

test("les tracés SVG sont des listes de chemins non vides", () => {
  for (const step of CYCLE_STEP_IDS) {
    const paths = ICON_SETS.line.icons[step];
    assert.ok(Array.isArray(paths) && paths.length > 0);
    for (const d of paths) assert.match(d, /^M[\d. -]/, `${step} : chemin SVG commence par M`);
  }
});

test("un jeu inconnu retombe sur le jeu par défaut, une étape inconnue sur un point", () => {
  assert.equal(resolveIconSet("n-existe-pas").id, DEFAULT_ICON_SET);
  assert.equal(resolveIconSet(undefined).id, DEFAULT_ICON_SET);
  assert.deepEqual(getStepIcon("n-existe-pas", "decider"), { kind: "text", value: ICON_SETS.emoji.icons.decider });
  assert.deepEqual(getStepIcon("emoji", "inconnue"), { kind: "text", value: "•" });
});

test("getStepIconText rend toujours du texte, y compris pour les tracés", () => {
  assert.equal(getStepIconText("line", "deployer"), ICON_SETS.emoji.icons.deployer);
  assert.equal(getStepIconText("glyph", "mesurer"), ICON_SETS.glyph.icons.mesurer);
  assert.equal(getStepIconText("emoji", "apprendre"), "📚");
});

test("préférence de jeu : lecture tolérante, écriture refusée pour un jeu inconnu", () => {
  assert.equal(loadIconSetPreference(undefined), DEFAULT_ICON_SET);
  assert.equal(loadIconSetPreference(fakeStorage({ [ICON_SET_STORAGE_KEY]: "bidon" })), DEFAULT_ICON_SET);
  assert.equal(loadIconSetPreference(fakeStorage({ [ICON_SET_STORAGE_KEY]: "line" })), "line");
  const broken = { getItem: () => { throw new Error("quota"); }, setItem: () => { throw new Error("quota"); } };
  assert.equal(loadIconSetPreference(broken), DEFAULT_ICON_SET);
  assert.equal(saveIconSetPreference(broken, "glyph"), false);
  const st = fakeStorage();
  assert.equal(saveIconSetPreference(st, "glyph"), true);
  assert.equal(st.data[ICON_SET_STORAGE_KEY], "glyph");
  assert.equal(saveIconSetPreference(st, "bidon"), false);
  assert.equal(st.data[ICON_SET_STORAGE_KEY], "glyph");
});
