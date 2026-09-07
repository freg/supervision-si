import { test } from "node:test";
import assert from "node:assert/strict";
import {
  SUGGESTED_ACTIONS, resolveAction, executeSuggestion, selectAutoRunnable,
  loadAutoRunPreference, saveAutoRunPreference, AUTO_RUN_STORAGE_KEY,
} from "../src/cycleActions.js";

const bases = { netprobeApiBase: "http://np", snmpApiBase: "http://snmp", netmapOrchestratorApiBase: "http://orch" };
const nmapSugg = { id: 7, status: "open", suggested_action: "netprobe_nmap_scan", action_params: { ip_address: "192.168.1.35", device_id: 4 } };
const snmpSugg = { id: 8, status: "open", suggested_action: "snmp_register_target", action_params: { ip_address: "192.168.1.2", device_id: 9 } };

test("résolution : outil, exécutabilité, disponibilité selon les API configurées", () => {
  const a = resolveAction(nmapSugg, bases);
  assert.equal(a.tool, "netprobe");
  assert.equal(a.canAuto, true);
  assert.match(a.description, /192\.168\.1\.35/);
  const b = resolveAction(snmpSugg, bases);
  assert.equal(b.tool, "snmp");
  assert.equal(b.canAuto, false, "communauté à saisir : jamais automatique");
  const off = resolveAction(nmapSugg, { snmpApiBase: "x" });
  assert.equal(off.available, false);
  assert.equal(off.canAuto, false, "outil non configuré : pas d'exécution");
  assert.equal(resolveAction({ suggested_action: null }, bases), null);
  assert.equal(resolveAction(undefined, bases), null);
  const unknown = resolveAction({ suggested_action: "truc_inconnu", action_params: { x: 1 } }, bases);
  assert.equal(unknown.label, "truc_inconnu");
  assert.equal(unknown.tool, null);
  assert.equal(unknown.canAuto, false);
  for (const def of Object.values(SUGGESTED_ACTIONS)) assert.equal(typeof def.describe({}), "string");
});

function fakeClients(overrides = {}) {
  const calls = [];
  return {
    calls,
    clients: {
      netprobe: {
        addTarget: async (base, ip, label) => { calls.push(["addTarget", base, ip, label]); return overrides.add ?? { id: 42, created: true }; },
        scanTarget: async (base, id) => { calls.push(["scanTarget", base, id]); return overrides.scan ?? { success: true, open_ports: [{ port: 22 }, { port: 80 }], scan_duration_seconds: 3.2 }; },
      },
      orchestrator: {
        setSuggestionStatus: async (base, id, status) => { calls.push(["setStatus", base, id, status]); return overrides.status ?? { status: "ok" }; },
      },
    },
  };
}

test("exécution d'un scan nmap : cible créée, scan, suggestion marquée traitée", async () => {
  const f = fakeClients();
  const r = await executeSuggestion(nmapSugg, { apiBases: bases, clients: f.clients });
  assert.equal(r.ok, true, r.error);
  assert.deepEqual(f.calls, [
    ["addTarget", "http://np", "192.168.1.35", "appareil #4"],
    ["scanTarget", "http://np", 42],
    ["setStatus", "http://orch", 7, "done"],
  ]);
  assert.equal(r.steps.length, 3);
  assert.match(r.summary, /2 port\(s\) ouvert\(s\) \(22, 80\)/);
});

test("échec du scan : la suggestion reste ouverte, l'erreur est explicite", async () => {
  const f = fakeClients({ scan: { success: false, error: "nmap absent" } });
  const r = await executeSuggestion(nmapSugg, { apiBases: bases, clients: f.clients });
  assert.equal(r.ok, false);
  assert.match(r.error, /nmap absent/);
  assert.ok(!f.calls.some((c) => c[0] === "setStatus"), "jamais marquée traitée après un échec");
  const g = fakeClients({ add: { error: "netprobe injoignable" } });
  const r2 = await executeSuggestion(nmapSugg, { apiBases: bases, clients: g.clients });
  assert.equal(r2.ok, false);
  assert.match(r2.error, /netprobe injoignable/);
  assert.equal(g.calls.length, 1);
});

test("cible existante réutilisée ; exception d'un client capturée", async () => {
  const f = fakeClients({ add: { id: 5, created: false } });
  const r = await executeSuggestion(nmapSugg, { apiBases: bases, clients: f.clients });
  assert.equal(r.ok, true);
  assert.match(r.steps[0].detail, /existante \(#5\)/);
  const boom = { netprobe: { addTarget: async () => { throw new Error("réseau coupé"); } } };
  const r2 = await executeSuggestion(nmapSugg, { apiBases: bases, clients: boom });
  assert.equal(r2.ok, false);
  assert.match(r2.error, /réseau coupé/);
});

test("refus propres : non exécutable, sans action, sans IP", async () => {
  const f = fakeClients();
  const r = await executeSuggestion(snmpSugg, { apiBases: bases, clients: f.clients });
  assert.equal(r.ok, false);
  assert.match(r.error, /ne s'exécute pas sans saisie/);
  assert.equal(f.calls.length, 0);
  assert.match((await executeSuggestion({ id: 1 }, { apiBases: bases, clients: f.clients })).error, /aucune action/);
  assert.match((await executeSuggestion({ id: 1, suggested_action: "netprobe_nmap_scan", action_params: {} }, { apiBases: bases, clients: f.clients })).error, /sans adresse IP/);
});

test("sélection automatique : exécutables, ouvertes, pas déjà lancées", () => {
  const list = [nmapSugg, snmpSugg, { ...nmapSugg, id: 9, status: "done" }, { ...nmapSugg, id: 10 }, { suggested_action: "netprobe_nmap_scan" }];
  assert.deepEqual(selectAutoRunnable(list, bases).map((s) => s.id), [7, 10]);
  assert.deepEqual(selectAutoRunnable(list, bases, new Set([7])).map((s) => s.id), [10]);
  assert.deepEqual(selectAutoRunnable(list, {}), [], "sans netprobe configuré : rien");
  assert.deepEqual(selectAutoRunnable(undefined, bases), []);
});

test("préférence d'exécution automatique : désactivée par défaut, tolérante", () => {
  const data = {};
  const st = { getItem: (k) => data[k] ?? null, setItem: (k, v) => { data[k] = v; } };
  assert.equal(loadAutoRunPreference(st), false);
  assert.equal(saveAutoRunPreference(st, true), true);
  assert.equal(data[AUTO_RUN_STORAGE_KEY], "1");
  assert.equal(loadAutoRunPreference(st), true);
  saveAutoRunPreference(st, false);
  assert.equal(loadAutoRunPreference(st), false);
  const broken = { getItem: () => { throw new Error("x"); }, setItem: () => { throw new Error("x"); } };
  assert.equal(loadAutoRunPreference(broken), false);
  assert.equal(saveAutoRunPreference(broken, true), false);
  assert.equal(loadAutoRunPreference(undefined), false);
});
