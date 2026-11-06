// Tests #987 : profil « campus » du hub.
import { test } from "node:test";
import assert from "node:assert/strict";
import { profilActif, restreindre, titreHub, VUES_CAMPUS } from "../src/hubProfil.js";

test("profil : nœud du campus, compte du groupe numeria, administrateurs", () => {
  assert.equal(profilActif("campus", ["/administrateurs"]), "noeud");
  assert.equal(profilActif("", ["/numeria"]), "groupe");
  assert.equal(profilActif("", ["/numeria", "/administrateurs"]), null);     // un admin garde tout
  assert.equal(profilActif("", ["/numeria"], true), null);
  assert.equal(profilActif(undefined, ["autre"]), null);
});

test("restriction des vues et titre", () => {
  const toutes = new Set(["nebula", "si-agent", "espaces", "accounts", "demos", "iapark"]);
  assert.deepEqual([...restreindre(toutes, "groupe")].sort(), ["demos", "nebula"]);
  assert.deepEqual([...restreindre(toutes, "noeud")].sort(), ["demos", "espaces", "iapark", "nebula", "si-agent"]);
  assert.equal(restreindre(toutes, null), toutes);
  assert.equal(titreHub("groupe"), "Hub Campus");
  assert.equal(titreHub(null), "Hub SI");
  assert.ok(!VUES_CAMPUS.includes("si-agent"));                              // pas les machines du bureau sur le hub principal
});
