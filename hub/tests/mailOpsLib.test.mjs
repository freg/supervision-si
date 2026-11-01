import test from "node:test";
import assert from "node:assert/strict";
import { incidentsFrom, settingsDiff, flatEntries, playbook, fmtAge } from "../src/mailOpsLib.js";

const T = (h) => new Date(Date.UTC(2026, 9, 14, h)).toISOString();
const ev = (kind, h, codes, severity = "warning") => ({ kind, at: T(h), severity, message: `m ${codes}`, details: { task: "plugin:mail-server", codes } });

test("#752 : incidents ouverts / clos à partir des constats de la sonde", () => {
  const evs = [ev("probe-alert", 1, ["queue-backlog"]), ev("probe-alert", 2, ["queue-write-error"], "critical"), ev("probe-recovered", 3, ["queue-backlog"]),
    ev("probe-alert", 4, ["queue-backlog"]), { kind: "probe-alert", at: T(5), details: { task: "plugin:wifi-probe", codes: ["x"] } }];
  const r = incidentsFrom(evs, Date.parse(T(6)));
  assert.deepEqual(r.open.map((i) => i.code), ["queue-write-error", "queue-backlog"]);
  assert.equal(r.open[0].duration_s, 4 * 3600); assert.equal(r.open[0].severity, "critical");
  assert.equal(r.closed.length, 1); assert.equal(r.closed[0].duration_s, 2 * 3600);
  assert.deepEqual(r.byCode[0], { code: "queue-backlog", count: 2, total_s: 4 * 3600 });
});

test("#752 : réglages modifiés seulement", () => {
  const cur = { postfix: [{ key: "smtpd_proxy_timeout", value: "300s" }, { key: "message_size_limit", value: "10240000" }], amavis: [{ key: "max_servers", value: "4" }] };
  assert.equal(settingsDiff(cur, { postfix: { smtpd_proxy_timeout: "300s" } }), null);
  assert.deepEqual(settingsDiff(cur, { postfix: { smtpd_proxy_timeout: " 600s " }, amavis: { max_servers: "", x: "1" } }), { postfix: { smtpd_proxy_timeout: "600s" }, amavis: {} });
});

test("#752 : listes à plat, filtres, conduite à tenir", () => {
  const lists = { maps: [{ path: "/etc/postfix/sender_access", role: "expéditeur", type: "hash", editable: true, entries: [{ key: "ami@exemple.fr", value: "OK", list: "blanche" }, { key: "@spam.exemple", value: "REJECT", list: "noire" }] }],
    postgrey: [{ path: "/etc/postgrey/whitelist_clients.local", editable: true, entries: [{ key: "exemple.org", value: "", list: "blanche" }] }] };
  assert.equal(flatEntries(lists).length, 3);
  assert.deepEqual(flatEntries(lists, "blanche").map((e) => e.key), ["ami@exemple.fr", "exemple.org"]);
  assert.deepEqual(flatEntries(lists, "", "SPAM").map((e) => e.key), ["@spam.exemple"]);
  assert.equal(playbook("queue-backlog").tab, "file"); assert.equal(playbook("inconnu").label, "inconnu");
  assert.equal(fmtAge(7200), "2 h"); assert.equal(fmtAge(null), "—");
});
