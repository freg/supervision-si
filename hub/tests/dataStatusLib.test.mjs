import test from "node:test";
import assert from "node:assert/strict";
import { sourceState, latencyState, fmtAge } from "../src/dataStatusLib.js";

test("#763 : état d'une source et temps de réponse", () => {
  assert.equal(sourceState({ agents: [], hint: "activer la sonde" }, "pve-remote").tone, "critical");
  assert.match(sourceState({ agents: [], hint: "activer la sonde" }, "pve-remote").detail, /activer la sonde/);
  const ok = sourceState({ agents: [{ agent_id: "pve10", ok: true, age_s: 120 }, { agent_id: "pve11", ok: true, age_s: 60 }] }, "proxmox");
  assert.equal(ok.tone, "good"); assert.match(ok.text, /2 agent\(s\), il y a 60 s/);
  const late = sourceState({ agents: [{ agent_id: "pbs", hostname: "pbs10", ok: true, age_s: 7200 }] }, "pbs");
  assert.equal(late.tone, "warning"); assert.match(late.detail, /pbs10 il y a 2 h/);
  const bad = sourceState({ agents: [{ agent_id: "a", ok: false, error: "ssh refusé" }, { agent_id: "b", ok: true, age_s: 5 }] }, "pve-remote");
  assert.equal(bad.tone, "critical"); assert.match(bad.detail, /ssh refusé/);
  assert.equal(latencyState(null), null); assert.equal(latencyState(300).tone, "good"); assert.equal(latencyState(3000).tone, "warning"); assert.match(latencyState(9000).text, /engorgement/);
  assert.equal(fmtAge(3600 * 30), "30 h");
});
