import test from "node:test";
import assert from "node:assert/strict";
import { demandeBase, publicLinks, displayUrl, agentPublishedLinks } from "../src/publicLinks.js";

test("demandeBase : déduit la racine publique de l'URL d'admin", () => {
  assert.equal(demandeBase("https://hub.example:6443/demande/admin"), "https://hub.example:6443/demande/");
  assert.equal(demandeBase("https://hub.example:6443/demande/admin/"), "https://hub.example:6443/demande/");
  assert.equal(demandeBase("https://hub.example:6443/demande/admin?x=1"), "https://hub.example:6443/demande/");
  assert.equal(demandeBase("https://hub.example:6443/demande/"), "https://hub.example:6443/demande/");
  assert.equal(demandeBase("https://hub.example:6443/demande"), "https://hub.example:6443/demande/");
  assert.equal(demandeBase(""), null);
  assert.equal(demandeBase(undefined), null);
});

test("publicLinks : espace simple (#541) en premier, trois pages du pont + application historique", () => {
  const links = publicLinks({ demandeUrl: "https://h/demande/admin", frontendUrl: "https://h/app/" });
  assert.deepEqual(links.map((l) => l.id), ["simple", "demande", "demande-rapide", "demande-tableau", "supervision"]);
  assert.deepEqual(links.map((l) => l.url), ["https://h/demande/accueil", "https://h/demande/", "https://h/demande/rapide", "https://h/demande/tableau", "https://h/app/"]);
  for (const l of links) {
    assert.ok(l.name && l.description, l.id);
  }
});

test("publicLinks : rien sans variable, jamais d'exception", () => {
  assert.deepEqual(publicLinks({}), []);
  assert.deepEqual(publicLinks(), []);
  assert.deepEqual(publicLinks({ frontendUrl: " " }), []);
  assert.equal(publicLinks({ frontendUrl: "https://h/app/" }).length, 1);
  assert.equal(publicLinks({ demandeUrl: "https://h/demande/admin" }).length, 4);
});

test("displayUrl : sans schéma", () => {
  assert.equal(displayUrl("https://h:6443/demande/rapide"), "h:6443/demande/rapide");
  assert.equal(displayUrl("http://h/x"), "h/x");
  assert.equal(displayUrl(""), "");
});

test("agentPublishedLinks (#554) : agents qui publient seulement", () => {
  const links = agentPublishedLinks([{ agent_id: "a1", hostname: "pc-site", site: "campus", publish: { enabled: true, port: 8081, title: "Réseau du campus" } },
                                     { agent_id: "a2", last_ip: "192.0.2.5", publish: { enabled: false } }, { agent_id: "a3", publish: { enabled: true } }]);
  assert.deepEqual(links.map((l) => [l.name, l.url]), [["Réseau du campus", "http://pc-site:8081/"]]);
  assert.deepEqual(agentPublishedLinks(null), []);
});
