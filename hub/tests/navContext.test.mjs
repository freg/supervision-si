// Contexte de navigation (livraison #874) : vue gardée au rechargement, paramètres de la vue, états mémorisés.
import test from "node:test";
import assert from "node:assert/strict";

const store = new Map();
globalThis.sessionStorage = { getItem: (k) => (store.has(k) ? store.get(k) : null), setItem: (k, v) => store.set(k, String(v)) };
let href = "https://hub.exemple/";
globalThis.window = {
  get location() { const u = new URL(href); return { href, search: u.search, pathname: u.pathname, hash: u.hash }; },
  history: { state: null, replaceState: (_s, _t, url) => { href = new URL(url, href).toString(); } },
};
const nav = await import("../src/navContext.js");

test("vue initiale : lien profond, sinon dernière vue de l'onglet, sinon accueil", () => {
  assert.equal(nav.vueInitiale(), "grid");
  href = "https://hub.exemple/?view=nebula&tab=charge";
  assert.equal(nav.vueInitiale(), "nebula");
  nav.memoriserVue("nebula");
  assert.equal(new URL(href).searchParams.get("tab"), "charge");           // paramètres de la vue gardés
  href = "https://hub.exemple/";                                           // retour de Keycloak sur « / »
  assert.equal(nav.vueInitiale(), "nebula");
  assert.equal(nav.urlApresConnexion(), "/?view=nebula");
  href = "https://hub.exemple/?view=a%3Cscript%3E";
  assert.equal(nav.vueInitiale(), "nebula");                               // vue invalide ignorée
});

test("changement de vue : paramètres de l'ancienne vue retirés, accueil sans ?view", () => {
  href = "https://hub.exemple/?view=si-agent&agent=pve10&v=870";
  nav.memoriserVue("si-agent");
  nav.memoriserVue("migration");
  const u = new URL(href);
  assert.equal(u.searchParams.get("view"), "migration");
  assert.equal(u.searchParams.get("agent"), null);
  assert.equal(u.searchParams.get("v"), "870");
  nav.memoriserVue("grid");
  assert.equal(new URL(href).searchParams.get("view"), null);
});

test("états mémorisés par vue et par composant", () => {
  nav.memoriserVue("nebula");
  nav.memoriserEtat("NebulaView", "tab", "historique");
  assert.equal(nav.etatMemorise("NebulaView", "tab"), "historique");
  assert.equal(nav.etatMemorise("CampusView", "tab"), undefined);
  nav.memoriserVue("migration");
  assert.equal(nav.etatMemorise("NebulaView", "tab"), undefined);         // propre à la vue
});
