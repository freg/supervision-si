import test from "node:test";
import assert from "node:assert/strict";

globalThis.window = { location: { pathname: "/", search: "" } };
const { agentJournalLinks } = await import("../src/hubLinks.js");
const { sourceState } = await import("../src/dataStatusLib.js");

test("#768 : liens journal d'un agent et état d'une source en erreur", () => {
  const l = agentJournalLinks("pve10", "pve-remote");
  assert.deepEqual(l.map((x) => x.label), ["événements", "sondes", "journal de l'hôte"]);
  assert.match(l[0].href, /view=si-agent&tab=events&agent=pve10&q=pve-remote/);
  assert.match(l[1].href, /section=plugins/);
  assert.deepEqual(agentJournalLinks(""), []);
  const s = sourceState({ agents: [{ agent_id: "a1", hostname: "pve10", ok: false, error: "Permission denied" }] }, "pve-remote");
  assert.deepEqual(s.agents, [{ id: "a1", name: "pve10" }]);
});
