import test from "node:test";
import assert from "node:assert/strict";
import { flattenProxmox, otherNodes, makeStep, runSummary, stepText, OPS, replSummary, roleStepText } from "../src/pveOpsLib.js";

const data = [{ agent_id: "pve10", hostname: "pve10", node: { name: "pve10" }, vms: [{ vmid: 101, name: "super", type: "qemu", status: "running" }, { vmid: 900, name: "tpl", template: 1 }], storages: [{ storage: "local-zfs" }, { name: "pbs" }],
  replication: [{ vmid: 101, target: "pve11", ok: true, fail_count: 0, last_sync_age_s: 720 }] },
  { agent_id: "pve11", hostname: "pve11", node: {}, vms: [] }];

test("flattenProxmox et otherNodes", () => {
  const h = flattenProxmox(data);
  assert.deepEqual(h[0].vms.map((v) => [v.vmid, v.replication.length]), [[101, 1]]);
  assert.equal(replSummary(h[0].vms[0].replication), "→ pve11 ✔ il y a 12 min"); assert.equal(replSummary([{ target: "a", ok: false, fail_count: 3 }]), "→ a ✘ 3 échec(s)"); assert.equal(replSummary([]), "");
  assert.deepEqual(h[0].storages, ["local-zfs", "pbs"]); assert.equal(h[1].node, "pve11");
  assert.deepEqual(otherNodes(h, "pve10"), ["pve11"]);
});

test("makeStep ne garde que les champs de l'opération et type les nombres", () => {
  const h = flattenProxmox(data)[0];
  const s = makeStep(h, h.vms[0], "clone", { newid: "9101", name: "super-pra", storage: "", foo: "x" });
  assert.deepEqual(s, { agent_id: "pve10", vmid: 101, kind: "qemu", action: "clone", params: { newid: 9101, name: "super-pra" }, label: "super : Cloner" });
  assert.equal(makeStep(h, { vmid: 203, type: "lxc" }, "migrate", { target: "pve11", online: true }).kind, "lxc");
  assert.ok(Object.keys(OPS).includes("replicate"));
});

test("runSummary et stepText", () => {
  assert.equal(runSummary({ steps: [{ index: 1, status: "done" }, { index: 2, status: "failed", result: { error: "refusé" } }, { index: 3, status: "pending" }] }), "1/3 étape(s) — échec à l'étape 2 : refusé");
  assert.equal(runSummary({ steps: [{ index: 1, ok: true }, { index: 2, ok: false, error: "agent inconnu" }] }), "1/2 étape(s) — échec à l'étape 2 : agent inconnu");
  assert.equal(stepText({ agent_id: "pve10", params: { vmid: 101, action: "migrate", kind: "qemu", target: "pve11" } }), "pve10 · VM 101 · Migrer vers un nœud (target=pve11)");
});

test("étape de bascule de rôle", () => {
  const roles = [{ id: 4, name: "web", candidates: [{ label: "principal" }, { label: "secours" }] }];
  assert.equal(stepText({ agent_id: "central", params: { action: "role_switch", role_id: 4, to: 1 } }, roles), "bascule du rôle « web » → secours");
  assert.equal(roleStepText({ params: { role_id: 9, to: 0 } }, roles), "bascule du rôle n°9 → candidat 0");
});

// #658 : migration vers la virtualisation -- corps du formulaire, manques, boutons d'exécution, textes des nouvelles étapes
import { VM_OPS, MIGRATION_DEFAULTS, migrationBody, migrationMissing, runActions, waitingStep } from "../src/pveOpsLib.js";
test("migration : VM_OPS exclut les étapes de plan, corps nettoyé et typé", () => {
  assert.ok(!("create" in VM_OPS) && !("checkpoint" in VM_OPS) && ("migrate" in VM_OPS));
  const b = migrationBody({ ...MIGRATION_DEFAULTS, source_agent_id: "srv", pve_agent_id: "pve", vmid: "200", storage: "local-lvm", image_target: "/mnt/images", role_id: "3", role_to: "1", template: "x" });
  assert.equal(b.vmid, 200); assert.equal(b.role_id, 3); assert.equal(b.role_to, 1); assert.equal(b.template, undefined); assert.equal(b.ip, undefined); assert.equal(b.image_target, "/mnt/images"); assert.equal(b.purge_on_rollback, false);
  const r = migrationBody({ ...MIGRATION_DEFAULTS, method: "rebuild", template: "local:vztmpl/d.tar.zst", image_target: "/x" });
  assert.equal(r.image_target, undefined); assert.equal(r.template, "local:vztmpl/d.tar.zst"); assert.equal(r.ip, "dhcp");
});
test("migration : manques dans l'ordre", () => {
  const f = { ...MIGRATION_DEFAULTS };
  assert.match(migrationMissing(f), /source/); f.source_agent_id = "srv";
  assert.match(migrationMissing(f), /Proxmox/); f.pve_agent_id = "pve";
  assert.match(migrationMissing(f), /vmid/); f.vmid = 200;
  assert.match(migrationMissing(f), /stockage/); f.storage = "local-lvm";
  assert.match(migrationMissing(f), /image/); f.image_target = "/mnt/images";
  assert.equal(migrationMissing(f), null);
  assert.match(migrationMissing({ ...f, method: "rebuild" }), /modèle/);
});
test("exécution : boutons selon l'état et étape en attente", () => {
  const plan = { rollback_steps: [{ action: "shutdown" }] };
  assert.deepEqual(runActions({ mode: "simulate", status: "done" }, plan), []);
  assert.deepEqual(runActions({ mode: "execute", status: "paused" }, plan), ["resume", "abort"]);
  assert.deepEqual(runActions({ mode: "execute", status: "running" }, plan), ["abort"]);
  assert.deepEqual(runActions({ mode: "execute", status: "failed" }, plan), ["rollback"]);
  assert.deepEqual(runActions({ mode: "execute", status: "done" }, { rollback_steps: [] }), []);
  assert.deepEqual(runActions({ mode: "rollback", status: "done" }, plan), []);
  const run = { steps: [{ status: "done" }, { status: "waiting", label: "Transition 2 -- vérifier" }] };
  assert.equal(waitingStep(run).label, "Transition 2 -- vérifier"); assert.equal(waitingStep({ steps: [] }), null);
  assert.match(stepText({ agent_id: "central", action: "checkpoint", label: "Transition 1" }), /⏸ transition : Transition 1/);
  assert.match(stepText({ agent_id: "srv", action: "image_host", params: { target: "/mnt/images" } }), /image à chaud → \/mnt\/images/);
  assert.match(stepText({ agent_id: "srv", action: "host_shutdown", params: {} }), /arrêt du serveur physique/);
  assert.match(stepText({ agent_id: "pve", vmid: 200, action: "create", params: { name: "srv" } }), /VM 200 · Créer/);
});
