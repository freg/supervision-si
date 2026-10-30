// #922 : onglets de la fiche agent, pastille de collecte, état de version.
import { test } from "node:test";
import assert from "node:assert/strict";
import { ONGLETS, SANS_MESURE, ongletDe, sectionsDe, collecte, versionEtat } from "../src/agentFiche.js";

test("onglets : toute section a un onglet, liens profonds, sections par onglet", () => {
  const toutes = ["risks", "system", "network", "hardware", "activity", "disks", "storage", "ports", "services", "logs", "control", "plugins", "commands", "distance", "settings"];
  for (const s of toutes) assert.ok(ongletDe(s), s);
  assert.equal(ongletDe("settings"), "settings");
  assert.equal(ongletDe("storage"), "disks");
  assert.equal(ongletDe("commands"), "historique", "#929 : l'ancienne section commands est sous l'onglet Historique");
  assert.equal(ongletDe("distance"), "distance", "#929 : onglet Commandes à distance");
  assert.equal(ongletDe("inconnue"), null);
  assert.deepEqual(sectionsDe("resume"), { risks: true, system: true });
  assert.deepEqual(sectionsDe("historique"), { commands: true });
  assert.deepEqual(sectionsDe("distance"), { distance: true });
  assert.deepEqual(sectionsDe("n'existe pas"), { risks: true, system: true });
  assert.ok(SANS_MESURE.has("settings") && SANS_MESURE.has("distance") && SANS_MESURE.has("historique") && !SANS_MESURE.has("resume"));
  assert.ok(!SANS_MESURE.has("commands"), "#929 : plus d'onglet id « commands »");
  assert.equal(new Set(ONGLETS.map((o) => o[0])).size, ONGLETS.length);
});

test("pastille de collecte : vert, jaune, orange, rouge", () => {
  assert.equal(collecte({ online: "online", active: true }, 40).couleur, "vert");
  const j = collecte({ online: "online", active: true }, 400);
  assert.equal(j.couleur, "jaune");
  assert.match(j.lignes[0], /pas de relevé récent/);
  const o = collecte({ online: "online", active: true, summary: { partial: ["ports"] } }, 20);
  assert.equal(o.couleur, "orange");
  assert.ok(o.lignes.some((l) => l.includes("partielle : ports")));
  assert.equal(collecte({ online: "online", blocked: true, blocked_reason: "incident" }, 20).couleur, "orange");
  assert.equal(collecte({ online: "offline", active: true }, 3 * 86400).couleur, "rouge");
  assert.match(collecte({ online: "offline" }, 3 * 86400).lignes[0], /3 j/);
  assert.equal(collecte({ online: "never" }, null).couleur, "rouge");
  assert.equal(collecte({ online: "online", active: false }, 10).couleur, "rouge");
});

test("version : à jour, en retard, plus récente, inconnue", () => {
  assert.deepEqual(versionEtat("0.6.25", "0.6.25").ton, "good");
  const r = versionEtat("0.6.21", "0.6.25");
  assert.equal(r.ton, "warn");
  assert.match(r.titre, /0\.6\.25/);
  assert.equal(versionEtat("0.6.9", "0.6.10").ton, "warn", "comparaison numérique, pas alphabétique");
  assert.equal(versionEtat("0.7.0", "0.6.25").ton, "neutral");
  assert.equal(versionEtat(null, "0.6.25").texte, "?");
  assert.equal(versionEtat("0.4.3", undefined).ton, "neutral");
});
