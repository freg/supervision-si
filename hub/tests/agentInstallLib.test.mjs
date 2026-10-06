import test from "node:test";
import assert from "node:assert/strict";
import { normalizeBase, isInternal, caFingerprintOf, installLines, pushHistory, loadHistory, saveHistory } from "../src/agentInstallLib.js";

test("adresse du hub : normalisation, interne / publique", () => {
  assert.equal(normalizeBase("hub.exemple.fr"), "https://hub.exemple.fr/api/si-agent");
  assert.equal(normalizeBase("https://192.0.2.5:6443/"), "https://192.0.2.5:6443/api/si-agent");
  assert.equal(normalizeBase("https://hub.exemple.fr/api/si-agent/"), "https://hub.exemple.fr/api/si-agent");
  assert.equal(normalizeBase(""), "");
  assert.ok(isInternal("https://192.0.2.5:6443/api/si-agent")); assert.ok(isInternal("https://super:6443")); assert.ok(isInternal("https://hub.lan"));
  assert.ok(!isInternal("https://hub.exemple.fr/api/si-agent"));
});

test("lignes d'installation selon l'adresse", () => {
  const pkg = { name: "si-agent-agent-0.5.32.tar.gz", sha256: "ab12" };
  const fp = caFingerprintOf("sudo ./install.sh --agent a --secret s --central x --site y --ca-fingerprint deadbeef");
  assert.equal(fp, "deadbeef");
  const lan = installLines({ base: "https://192.0.2.5:6443", agentId: "pve-3", site: "ovh", pkg, caFp: fp });
  assert.match(lan.download, /^curl -fsSk -o si-agent-agent-0\.5\.32\.tar\.gz https:\/\/192\.0\.2\.5:6443\/api\/si-agent\/package && echo 'ab12  si-agent-agent-0\.5\.32\.tar\.gz' \| sha256sum -c && tar xzf .* && cd si-agent-agent-0\.5\.32$/);
  assert.equal(lan.install, './install.sh --agent pve-3 --secret "$TOKEN" --central https://192.0.2.5:6443/api/si-agent --site ovh --ca-fingerprint deadbeef');
  const pub = installLines({ base: "hub.exemple.fr", agentId: "pve-3", site: "ovh", pkg, caFp: fp });
  assert.match(pub.download, /^curl -fsSL -o /); assert.ok(!pub.install.includes("--ca-fingerprint")); assert.ok(!pub.internal);
  assert.equal(installLines({ base: "hub.exemple.fr", agentId: "a", pkg: null }).download, "");
});

test("historique des adresses : plus récent d'abord, sans doublon, borné, stockage tolérant", () => {
  let h = pushHistory([], "hub.exemple.fr"); h = pushHistory(h, "https://192.0.2.5:6443"); h = pushHistory(h, "hub.exemple.fr");
  assert.deepEqual(h, ["https://hub.exemple.fr/api/si-agent", "https://192.0.2.5:6443/api/si-agent"]);
  assert.equal(pushHistory(Array.from({ length: 10 }, (_, i) => `https://h${i}.exemple.fr/api/si-agent`), "x.exemple.fr").length, 8);
  const mem = { v: {}, getItem(k) { return this.v[k] ?? null; }, setItem(k, x) { this.v[k] = x; } };
  saveHistory(h, mem); assert.deepEqual(loadHistory(mem), h);
  assert.deepEqual(loadHistory({ getItem() { throw new Error("bloqué"); } }), []);
});
