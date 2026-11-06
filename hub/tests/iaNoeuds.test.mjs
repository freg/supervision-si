// #988 : nœuds IA -- accès par groupe, filtrage des tuiles, chemins, nœud retenu, cookie du jeton.
import test from "node:test";
import assert from "node:assert/strict";
import { accesIa, filtrerVuesIa, cheminNoeud, noeudRetenu, pageDeVue, cookieIa, VUES_IA } from "../src/iaNoeudsLib.js";

test("accès : groupe ia, administrateurs ou admin_hub (avec ou sans /)", () => {
  assert.equal(accesIa(["/ia"]), true);
  assert.equal(accesIa(["administrateurs"]), true);
  assert.equal(accesIa(["admin_hub"]), true);
  assert.equal(accesIa(["numeria", "techniciens"]), false);
  assert.equal(accesIa(undefined), false);
});

test("tuiles IA retirées sans le droit, conservées sinon", () => {
  const vues = new Set(["nebula", ...VUES_IA]);
  assert.deepEqual([...filtrerVuesIa(vues, ["numeria"])], ["nebula"]);
  assert.equal(filtrerVuesIa(vues, ["ia"]), vues);
});

test("chemins des pages d'un nœud", () => {
  assert.equal(cheminNoeud("prodia"), "/ia/prodia/");
  assert.equal(cheminNoeud("preprodia", "atelier"), "/ia/preprodia/atelier");
  assert.equal(cheminNoeud("../x", "atelier"), null);
  assert.equal(cheminNoeud("", ""), null);
});

test("nœud retenu et page d'une vue", () => {
  assert.equal(noeudRetenu(["prodia", "preprodia"], "preprodia"), "preprodia");
  assert.equal(noeudRetenu(["prodia"], "disparu"), "prodia");
  assert.equal(noeudRetenu([], "x"), null);
  assert.equal(pageDeVue("hermes"), "");
  assert.equal(pageDeVue("ia-atelier"), "atelier");
  assert.equal(pageDeVue("ia-apprentissage"), "apprentissage");
  assert.equal(pageDeVue("autre"), "");
});

test("cookie du jeton limité à /ia/, effacé quand le jeton est vide", () => {
  assert.equal(cookieIa("abc"), "si_ia_jeton=abc; Path=/ia/; SameSite=Strict; Secure");
  assert.equal(cookieIa("abc", false), "si_ia_jeton=abc; Path=/ia/; SameSite=Strict");
  assert.match(cookieIa(""), /Max-Age=0$/);
});

import { nomPropose, verifierFormulaire, etatNoeud } from "../src/iaNoeudsLib.js";

test("#996 nom proposé et formulaire de déploiement", () => {
  assert.equal(nomPropose("Prodia-IA"), "prodia"); assert.equal(nomPropose("srv_01"), "srv-01");
  const ok = { agent: "prodia", nom: "prodia", acces: "bastion", adresse: "192.0.2.30", shim: "campus", port: 8092 };
  assert.equal(verifierFormulaire(ok), null);
  assert.match(verifierFormulaire({ ...ok, agent: "" }), /agent/);
  assert.match(verifierFormulaire({ ...ok, shim: "" }), /shim/);
  assert.match(verifierFormulaire({ ...ok, adresse: "a b" }), /adresse/);
  assert.match(verifierFormulaire({ ...ok, port: 80 }), /port/);
  assert.equal(verifierFormulaire({ ...ok, acces: "direct", shim: "" }), null);
});

test("#996 état d'un nœud", () => {
  const c = (o) => ({ created_at: "2026-11-06T10:00:00Z", status: "done", params: { action: "deployer" }, result: { ok: true }, ...o });
  assert.equal(etatNoeud({ commande: c({ status: "pending" }) }).ton, "warn");
  assert.match(etatNoeud({ commande: c({ result: { ok: false, error: "intervention" } }) }).texte, /refusé/);
  assert.equal(etatNoeud({ commande: c(), evenement: { kind: "noeud-ia-deploye", at: "2026-11-06T10:20:00Z", message: "en service" } }).ton, "ok");
  assert.equal(etatNoeud({ commande: c(), evenement: { kind: "noeud-ia-echec", at: "2026-11-06T10:20:00Z", message: "échec" } }).ton, "bad");
  assert.match(etatNoeud({ commande: c(), evenement: { kind: "noeud-ia-deploye", at: "2026-11-05T10:00:00Z", message: "ancien" } }).texte, /en cours/);
  const et = c({ params: { action: "etat" }, result: { ok: true, result: { version: "0.29.0", sante_actuelle: { ok: true } } } });
  assert.equal(etatNoeud({ commande: et }).texte, "en service (0.29.0)");
  assert.equal(etatNoeud(undefined).texte, "état inconnu");
});

import { agentAJour } from "../src/iaNoeudsLib.js";
test("#996 version d'agent suffisante", () => {
  assert.equal(agentAJour("0.6.43"), true); assert.equal(agentAJour("0.6.100"), true); assert.equal(agentAJour("0.7"), true);
  assert.equal(agentAJour("0.6.42"), false); assert.equal(agentAJour(""), false); assert.equal(agentAJour("x.y"), false);
});

import { diagnosticNoeud } from "../src/iaNoeudsLib.js";
test("#998 diagnostic d'un nœud servi ou non par la passerelle", () => {
  assert.equal(diagnosticNoeud(200, "application/json").ok, true);
  assert.match(diagnosticNoeud(200, "text/html; charset=utf-8").texte, /ne sert pas encore/);
  assert.match(diagnosticNoeud(403, "text/html").texte, /groupe/);
  assert.match(diagnosticNoeud(502, "text/html").texte, /ne répond pas/);
});
