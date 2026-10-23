// si-veille (#845) : mise en forme de l'icône GNOME (node --test veille-chaine/gnome/test_lib.mjs)
import { test } from "node:test";
import assert from "node:assert/strict";
import { resume } from "./si-veille@exemple.fr/lib.js";

const res = { dns: { statut: "ok", detail: "203.0.113.10", nom: "DNS" }, frontal: { statut: "ko", detail: "HTTP 503", nom: "Frontal https" } };

test("ok, panne, ancien, absent", () => {
  const ok = resume({ dernier_tour: 1000, intervalle_s: 120, ordre: ["dns", "frontal"], resultats: { dns: res.dns }, alertes: [] }, 1030);
  assert.equal(ok.etat, "ok");
  assert.equal(ok.texte, "");
  assert.equal(ok.derniere, null);
  const p = resume({ dernier_tour: 1000, intervalle_s: 120, ordre: ["dns", "frontal"], resultats: res,
    incident: { debut: 400, texte: "Cause probable : Frontal https — HTTP 503" },
    alertes: [{ ts: 1000, titre: "Chaîne du hub en panne", texte: "Cause probable : Frontal https — HTTP 503" }] }, 1030);
  assert.equal(p.etat, "panne");
  assert.equal(p.texte, "Frontal https");
  assert.match(p.titre, /^PANNE depuis 11 min/);
  assert.deepEqual(p.maillons, ["✓ DNS — 203.0.113.10", "✗ Frontal https — HTTP 503"]);
  assert.match(p.derniere, /Chaîne du hub en panne : Cause probable/);
  assert.equal(p.alertes.length, 1);
  assert.equal(resume({ dernier_tour: 1000, intervalle_s: 120, resultats: {} }, 1000 + 1000).etat, "ancien");
  assert.equal(resume(null, 0).etat, "absent");
});
